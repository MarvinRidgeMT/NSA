"""Tests for the any-site solver (v2 Phase 1, §2.4). Each test can fail; skips state their reason.

Run: python -m pytest -q science/anysite science/tests
"""
import hashlib
import json
import math
import unittest
from pathlib import Path

import numpy as np

from science import dem as demmod
from science import frames
from science.skyline import compute_skyline
from science.anysite import curvature, ephem, members as MB, products as P, solve as S
from science.anysite.stack import LegacyStack, SPView

ROOT = Path(__file__).resolve().parents[3]
BUNDLE_ROI3 = ROOT / 'data' / 'bundles' / 'site04_roi3_2026-11-14_14d_mast1m.json'
ROI3 = (-89.78012, -156.32023)


def _have_roi3_data():
    return P.pgda90_file() is not None and P.pgda78_tile('Site04') is not None


# ------------------------------------------------------------------------------------------------ curvature limit
class CurvatureLimit(unittest.TestCase):
    def test_closed_form_matches_brute_force(self):
        for h_eye, H, e in [(0.0, 10786.0, 0.0), (1738.5, 10786.0, -1.5), (-4000.0, 7000.0, 2.0), (500.0, 3000.0, -0.7)]:
            L = float(curvature.limit_m(h_eye, e, H))
            s = np.linspace(1.0, 900_000.0, 900_001)
            el = curvature.elevation_deg(h_eye, H, s)
            L_bf = s[el >= e].max()
            self.assertLess(abs(L - L_bf), 2.0, (h_eye, H, e, L, L_bf))

    def test_elevation_formula_matches_frames(self):
        # closed form vs the solver's own 3D model (frames.elevation_angle_deg)
        lat, lon, h_eye, H = -89.0, 30.0, 1200.0, 6000.0
        for s in (5_000.0, 80_000.0, 250_000.0):
            la, lo = frames.destination(lat, lon, 77.0, s)
            el3d = frames.elevation_angle_deg(frames.moon_fixed(lat, lon, h_eye), frames.up_vector(lat, lon),
                                              frames.moon_fixed(la, lo, H))
            self.assertAlmostEqual(float(el3d), float(curvature.elevation_deg(h_eye, H, s)), places=9)

    def test_moon_relief_limit_value(self):
        # observer at the lowest point, highest summit at el = 0: about 262 km (documented in the plan)
        L = float(curvature.limit_m(curvature.MOON_MIN_HEIGHT_M, 0.0))
        self.assertTrue(255_000 < L < 270_000, L)


# ------------------------------------------------------------------------------------------------ flat sphere
class FlatSphereAnalytic(unittest.TestCase):
    """Constant-height DEM: the skyline is the bare-sphere horizon. With terrain at height Hc and the eye at Hc + mast,
    a ray of finite range reaches the geometric horizon (tangent point at arc s_t = R*acos((R+Hc)/(R+Hc+mast))) only if
    max_range >= s_t; the maximum elevation along the ray is then the tangent elevation -acos((R+Hc)/(R+Hc+mast))."""

    def _flat(self, Hc, half=60_000.0, step=40.0):
        n = int(2 * half / step)
        return demmod.ArrayDEM(np.full((n, n), Hc), -half, half, step, 'flat')

    def test_dip_equals_closed_form(self):
        Hc, mast = 250.0, 30.0
        R = frames.R_MOON_M
        dip = -math.degrees(math.acos((R + Hc) / (R + Hc + mast)))
        s_t = R * math.acos((R + Hc) / (R + Hc + mast))       # ~10.2 km
        far = self._flat(Hc, half=300_000.0, step=400.0)
        near = self._flat(Hc)
        sky = compute_skyline(-90.0 + 1e-9, 0.0, Hc, mast, near=near, far=far, bins=72, max_range_m=200_000.0,
                              step_m=2.0, near_range_m=25_000.0, far_step_m=400.0)
        el = np.array(sky['elevation_deg'], float)
        self.assertTrue(s_t < 25_000)
        # sampling at 2 m around the tangent point: |Δel| <= (ds/R)^2/2-type error, far below 1e-4 deg
        self.assertLess(np.max(np.abs(el - dip)), 1e-4, (el.min(), el.max(), dip))
        self.assertTrue(all(s == 'complete' for s in sky['status']))

    def test_flat_sphere_through_lat_lon_wrapper(self):
        # same flat DEM presented in an equirectangular CRS through SPView: identical dip at 85 S
        from pyproj import CRS
        Hc, mast = 100.0, 10.0
        R = frames.R_MOON_M
        dip = -math.degrees(math.acos((R + Hc) / (R + Hc + mast)))
        crs = CRS.from_proj4(f'+proj=eqc +R={R} +units=m +no_defs')
        lat0, lon0 = -60.0, 20.0
        x0, y0 = math.radians(lon0) * R, math.radians(lat0) * R
        step = 40.0; half = 60_000.0; n = int(2 * half / step)   # eqc x is stretched 2x at 60 S
        d = demmod.ArrayDEM(np.full((n, n), Hc), x0 - half, y0 + half, step, 'flat-eqc')
        v = SPView(d, {'zone': 'eq', 'crs_wkt': crs.to_wkt()})
        sky = compute_skyline(lat0, lon0, Hc, mast, near=v, far=None, bins=36, max_range_m=20_000.0, step_m=2.0)
        el = np.array(sky['elevation_deg'], float)
        self.assertLess(np.max(np.abs(el - dip)), 1e-4)


# ------------------------------------------------------------------------------------------------ batched members
class BatchedSkylineIdentity(unittest.TestCase):
    def test_bit_identical_to_compute_skyline(self):
        rng = np.random.default_rng(3)
        near = demmod.ArrayDEM(rng.normal(0, 30, (400, 400)), -4000.0, -20_000.0 + 4000, 20.0, 'n')
        far = demmod.ArrayDEM(rng.normal(0, 300, (300, 300)), -60_000.0, -20_000.0 + 60_000, 400.0, 'f')
        lat, lon = frames.stereo_inverse(0.0, -20_000.0)
        g = float(near.sample(0.0, -20_000.0))
        ref = compute_skyline(lat, lon, g, 2.0, near=near, far=far, bins=720, max_range_m=50_000.0, step_m=4.0,
                              near_range_m=3000.0, far_step_m=400.0)
        out = MB.batched_skyline(lat, lon, {'a': near}, far, 2.0, 4.0, 3000.0, 400.0, 50_000.0)['a']
        self.assertEqual(out['elevation_deg'], ref['elevation_deg'])
        self.assertEqual(out['status'], ref['status'])

    def test_error_field_statistics(self):
        f = MB.error_field((500, 500), 80.0, 1.0, 400.0, (7, 1))
        self.assertAlmostEqual(float(f.std()), 1.0, delta=0.08)
        self.assertLess(abs(float(f.mean())), 0.1)
        # correlated: neighbour differences much smaller than sigma
        self.assertLess(float(np.abs(np.diff(f, axis=1)).mean()), 0.5)
        # deterministic
        self.assertTrue(np.array_equal(f, MB.error_field((500, 500), 80.0, 1.0, 400.0, (7, 1))))


# ------------------------------------------------------------------------------------------------ adapter + caches
@unittest.skipUnless(_have_roi3_data(), 'PGDA 78 Site04 tile or PGDA 90 file not in data/cache or data/external')
class Adapter(unittest.TestCase):
    def test_far_window_bit_identical_to_committed_bundle(self):
        b = json.loads(BUNDLE_ROI3.read_text())
        far_ref = next(l for l in b['skyline']['dem_layers'] if l['role'] == 'far')
        st = LegacyStack()
        far = st.window(*ROI3, 290_000.0, 80.0)
        self.assertEqual(far.meta['file_sha256'], far_ref['file_sha256'])
        self.assertEqual(far.digest(), far_ref['array_sha256'])

    def test_legacy_9km_near_window_matches_bundle(self):
        b = json.loads(BUNDLE_ROI3.read_text())
        near_ref = next(l for l in b['skyline']['dem_layers'] if l['role'] == 'near')
        near = LegacyStack().window(*ROI3, 9000.0, 5.0)
        self.assertEqual(near.meta['file_sha256'], near_ref['file_sha256'])
        self.assertEqual(near.digest(), near_ref['array_sha256'])

    def test_coverage_and_sample(self):
        st = LegacyStack()
        cov = st.coverage(*ROI3)
        self.assertEqual(cov['source_id'], 'pgda78_Site04'); self.assertEqual(cov['native_res_m'], 5.0)
        self.assertIn('pgda90_80m', [p['id'] for p in cov['products']])
        h, src, res = st.sample([ROI3[0]], [ROI3[1]])
        x, y = frames.stereo_forward(*ROI3)
        near = st.window(*ROI3, 9000.0, 5.0)
        self.assertLess(abs(h[0] - float(near.sample(x, y))), 0.05)   # nearest-pixel point read vs bilinear, 5 m DEM
        sp_only = LegacyStack([e for e in st.entries if e['zone'] == 'sp'])
        self.assertEqual(sp_only.coverage(10.0, 20.0)['products'], [])   # south-polar products do not reach the equator

    def test_site_hash_stable(self):
        a = S.site_hash(*ROI3, 1.0, '2026-11-14 00:00', 14, 1, ['b', 'a'])
        self.assertEqual(a, S.site_hash(-89.780120000001, -156.32023 + 360, 1.0, '2026-11-14 00:00', 14, 1, ['a', 'b']))
        self.assertNotEqual(a, S.site_hash(*ROI3, 2.0, '2026-11-14 00:00', 14, 1, ['a', 'b']))
        # regression (found in the first precompute run): a bundle cached without clones answered a request with clones
        self.assertNotEqual(S.site_hash(*ROI3, 1.0, '2026-11-14 00:00', 14, 1, ['a'], ('products',)),
                            S.site_hash(*ROI3, 1.0, '2026-11-14 00:00', 14, 1, ['a'], ('clones', 'products')))


class HorizonsCache(unittest.TestCase):
    def test_tampered_cache_is_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            params = {'COMMAND': "'10'", 'X': 'test-only'}
            key = ephem.params_key(params)
            body = b'header\n$$SOE\n$$EOE\n'
            (Path(td) / f'{key}.txt').write_bytes(body)
            (Path(td) / f'{key}.json').write_text(json.dumps({'sha256': hashlib.sha256(body).hexdigest(),
                                                              'retrieved_utc': 'x'}))
            got, src = ephem.fetch_cached(params, cache_dir=td, allow_network=False)
            self.assertEqual(got, body)
            (Path(td) / f'{key}.txt').write_bytes(body + b'x')
            with self.assertRaises(ephem.TamperedCache):
                ephem.fetch_cached(params, cache_dir=td, allow_network=False)

    def test_roi3_query_hits_committed_archive(self):
        from science import horizons as H
        b = json.loads(BUNDLE_ROI3.read_text())
        p = H.build_params('10', ROI3[0], ROI3[1], b['site']['height_m'], '2026-11-14 00:00', '2026-11-28 00:00', '1 h')
        # the bundle's height is rounded to 1 mm; the archive params carry 1e-6 km, i.e. the same string
        hit = ephem._archive_hit(p)
        self.assertIsNotNone(hit)
        self.assertEqual(hit[1]['path'], 'data/raw/horizons/site04_roi3_sun_20261114_m1.txt')


# ------------------------------------------------------------------------------------------------ Site04 RoI 3
@unittest.skipUnless(_have_roi3_data() and P.pgda78_tile('Site04', 20) is not None,
                     'Site04 tile, its 20 clones or PGDA 90 not cached')
class Site04Roi3Reproduction(unittest.TestCase):
    """Through the any-site path (lat/lon only): hourly Sun 94.36 %, Sun+Earth 72.11 %, longest hourly Sun gap 19 h;
    20 PGDA 78 clones 87.54-97.33 % (docs/LONG_FEATURES_2026-11-15.md, float64 rerun; committed bundle metrics)."""

    @classmethod
    def setUpClass(cls):
        cls.b = S.solve(*ROI3, mast_m=1.0, member_kinds=('clones', 'products'), n_members=20, use_cache=False,
                        allow_network=False, out_dir=ROOT / 'data' / 'cache' / 'anysite' / 'test_bundles')

    def test_nominal(self):
        m = self.b['metrics']
        self.assertEqual(round(m['sun_center_visible_pct_hourly_samples'], 2), 94.36)
        self.assertEqual(round(m['sun_and_earth_center_visible_pct_hourly_samples'], 2), 72.11)
        self.assertEqual(m['longest_sun_center_hidden_h'], 19.0)

    def test_skyline_equals_committed_bundle(self):
        ref = json.loads(BUNDLE_ROI3.read_text())['skyline']
        sky = self.b['skyline']
        self.assertEqual(sky['near_cut_m'], ref['near_cut_m'])
        self.assertEqual(sky['max_range_m'], ref['max_range_m'])
        d = [abs(a - b) for a, b in zip(sky['elevation_deg'], ref['elevation_deg'])]
        self.assertLessEqual(max(d), 1e-5, 'near window grew from 9 km to the whole tile; must not move the skyline')

    def test_clones(self):
        s = self.b['anysite']['uncertainty']['summary']['pgda78-clone']['sun_center_visible_pct_hourly_samples']
        self.assertEqual(s['n'], 20)
        self.assertEqual(round(s['min'], 2), 87.54)
        self.assertEqual(round(s['max'], 2), 97.33)

    def test_curvature_recorded(self):
        c = self.b['skyline']['curvature_limit']
        self.assertLess(c['required_range_world_m'], c['max_range_m'])
        self.assertEqual(c['n_range_limited_world'], 0)

    def test_product_disagreement_present(self):
        ms = [m for m in self.b['anysite']['uncertainty']['members'] if m['kind'] == 'product']
        ids = [m['id'] for m in ms]
        self.assertEqual(ids[0], 'product:pgda90_80m')
        self.assertEqual(len(ids), len({i.split(':')[1] for i in ids}))      # one member per product family

    def test_schema(self):
        import jsonschema
        schema = json.loads((ROOT / 'schemas' / 'science-results-v1.schema.json').read_text())
        jsonschema.validate(self.b, schema)


# ------------------------------------------------------------------------------------------------ API stub
class ApiStub(unittest.TestCase):
    def test_no_data_point_is_an_error(self):
        from science.anysite import api
        with self.assertRaises(ValueError):
            api.handle({'lat': 95.0, 'lon': 20.0, 'allow_network': False})
        sp_only = LegacyStack([e for e in LegacyStack().entries if e['zone'] == 'sp'])
        with self.assertRaises(LookupError):
            S.solve(10.0, 20.0, stack=sp_only, allow_network=False, use_cache=False)

    def test_http_roundtrip(self):
        if not _have_roi3_data():
            self.skipTest('PGDA 78 Site04 / PGDA 90 not cached')
        import threading
        import urllib.request
        from http.server import HTTPServer
        from science.anysite import api
        srv = HTTPServer(('127.0.0.1', 0), api._H)
        th = threading.Thread(target=srv.serve_forever, daemon=True); th.start()
        try:
            url = f'http://127.0.0.1:{srv.server_port}/anysite'
            req = urllib.request.Request(url, data=json.dumps({'lat': ROI3[0], 'lon': ROI3[1], 'members': [],
                                                               'allow_network': False}).encode(), method='POST')
            out = json.loads(urllib.request.urlopen(req, timeout=120).read())
            self.assertEqual(out['sun_center_visible_pct_hourly_samples'], 94.362)
            req = urllib.request.Request(url, data=b'{"lat": 95, "lon": 20, "allow_network": false}', method='POST')
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(req, timeout=60)
            self.assertEqual(cm.exception.code, 400)
        finally:
            srv.shutdown()


# ------------------------------------------------------------------------------------------------ S2 PDS products
def _entry(st, prefix):
    return next((e for e in st.entries if e['id'].startswith(prefix)), None)


class PdsProducts(unittest.TestCase):
    """LOLA PDS LDEMs from S2 ($POLARIS_DATA/v2/products): km -> m, georeferencing, seam and pole handling."""

    @classmethod
    def setUpClass(cls):
        cls.st = LegacyStack()

    def _direct(self, e, lat, lon):
        from science.anysite.stack import _to_zone
        x, y = _to_zone(lat, lon, e)
        return LegacyStack._point(e, float(x), float(y))

    def test_global_eq_window_matches_point_reads(self):
        e = _entry(self.st, 'lola_global_ldem:ldem_64')
        if e is None:
            self.skipTest('LOLA global LDEM 64 ppd not downloaded by S2')
        # pixel centres (bilinear = the pixel value there), incl. across the 0/360 seam and next to both poles
        for lat0, lon0 in [(0.3, 0.004), (-45.0, 179.99), (88.0, -0.01), (-89.8, 120.0), (26.13, 3.63)]:
            d = self.st.window(lat0, lon0, 30_000.0, product=e['id'])
            for dlat, dlon in [(0, 0), (0.05, -0.08), (-0.1, 0.12)]:
                r = int(np.floor((90 - (lat0 + dlat)) * 64)); c = int(np.floor(((lon0 + dlon) % 360) * 64))
                la = 90 - (r + 0.5) / 64; lo = (c + 0.5) / 64
                x, y = frames.stereo_forward(la, lo)
                self.assertAlmostEqual(float(d.sample(x, y)), self._direct(e, la, lo), delta=1e-3, msg=(la, lo))

    def test_pole_crossing_ray_has_data(self):
        e = _entry(self.st, 'lola_global_ldem:ldem_64')
        if e is None:
            self.skipTest('LOLA global LDEM 64 ppd not downloaded by S2')
        d = self.st.window(89.5, 0.0, 120_000.0, product=e['id'])
        self.assertTrue(d.full_ring)
        la, lo = frames.destination(89.5, 0.0, 0.0, np.linspace(0, 100_000.0, 400))   # straight over the north pole
        h = d.sample(*frames.stereo_forward(la, lo))
        self.assertTrue(np.isfinite(h).all())

    def test_polar_5m_coregistered_with_pgda78(self):
        e = _entry(self.st, 'lola_polar_ldem:ldem_875s')
        if e is None or not _have_roi3_data():
            self.skipTest('LOLA 87.5 S 5 m or PGDA 78 Site04 not cached')
        a = self.st.window(*ROI3, 8000.0, product='pgda78_Site04')
        b = self.st.window(*ROI3, 8000.0, product=e['id'])
        x0, y0 = frames.stereo_forward(*ROI3)
        rng = np.random.default_rng(0)
        xs = x0 + rng.uniform(-5000, 5000, 3000); ys = y0 + rng.uniform(-5000, 5000, 3000)
        ref = a.sample(xs, ys)
        mad = {s: float(np.nanmedian(np.abs(b.sample(xs + s[0], ys + s[1]) - ref)))
               for s in [(0, 0), (5, 0), (-5, 0), (0, 5), (0, -5)]}
        self.assertEqual(min(mad, key=mad.get), (0, 0), mad)                  # no pixel shift / flip
        self.assertLess(abs(float(np.nanmedian(b.sample(xs, ys) - ref))), 0.5)  # km -> m and datum agree
        self.assertLess(mad[(0, 0)], 2.0)


# ------------------------------------------------------------------------------------------------ north pole
class NorthPoleSanity(unittest.TestCase):
    def test_north_pole_run(self):
        st = LegacyStack()
        lat, lon = 89.5, 0.0
        cov = st.covering(lat, lon)
        if not cov:
            self.skipTest('no product in the cache covers (89.5 N, 0 E): PGDA 90 / PGDA 78 are south-polar only and S2 '
                          'has not downloaded a LOLA global or north-polar LDEM into $POLARIS_DATA/v2/products')
        b = S.solve(lat, lon, 1.0, member_kinds=(), use_cache=False,
                    out_dir=ROOT / 'data' / 'cache' / 'anysite' / 'test_bundles')
        self.assertEqual(b['skyline']['n_truncated'], 0)                 # rays over the pole stay inside the product
        el = [v for v in b['skyline']['elevation_deg'] if v is not None]
        self.assertGreater(len(el), 700)
        self.assertTrue(all(-6.0 < v < 15.0 for v in el))             # plausible lunar polar horizons
        m = b['metrics']
        self.assertTrue(0 <= m['sun_center_visible_pct'] <= 100)
        # Sun elevation at 89.5 N never exceeds ~2.1 deg (0.5 deg colatitude + 1.54 deg obliquity + parallax)
        self.assertLess(max(s['sun']['el_deg'] for s in b['samples']), 2.2)


# ------------------------------------------------------------------------------------------------ pyramid agreement
class _ContractOnlyStack:
    """Exposes only the contract API (no product/member kwargs, coverage without 'products'), as S3's stack will."""

    def __init__(self):
        self._s = LegacyStack()

    def coverage(self, lat, lon):
        c = self._s.coverage(lat, lon)
        return {k: c[k] for k in ('source_id', 'native_res_m', 'quality', 'level')}

    def window(self, lat0, lon0, half_m, res_m=None):
        return self._s.window(lat0, lon0, half_m, res_m)

    def sample(self, lat, lon):
        return self._s.sample(lat, lon)


@unittest.skipUnless(_have_roi3_data(), 'PGDA 78 Site04 / PGDA 90 not cached')
class ContractOnlyStackShim(unittest.TestCase):
    def test_solver_runs_on_contract_api_alone(self):
        b = S.solve(*ROI3, 1.0, member_kinds=(), stack=_ContractOnlyStack(), use_cache=False, allow_network=False,
                    out_dir=ROOT / 'data' / 'cache' / 'anysite' / 'test_bundles')
        self.assertEqual(b['metrics']['sun_center_visible_pct_hourly_samples'], 94.362)
        self.assertEqual(b['metrics']['sun_and_earth_center_visible_pct_hourly_samples'], 72.107)


class PyramidAgreement(unittest.TestCase):
    """At Site04 RoI 3 (covered by PGDA 78 and the merged pyramid) the masks must agree: median |Δ| <= 0.05 deg and
    95th percentile <= 0.3 deg. Tolerance: the pyramid's finest level there should be the same PGDA 78 data; differences
    come only from tiling/feathering, and 0.3 deg is ~5 % of the Sun-margin range seen at this site."""

    def test_masks_agree(self):
        try:
            from science.terrain.stack import TerrainStack
            st = TerrainStack.open()
        except Exception as exc:
            self.skipTest(f'S3 pyramid not available yet ({type(exc).__name__}: {exc})')
        if not _have_roi3_data():
            self.skipTest('PGDA 78 / PGDA 90 reference data not cached')
        a = S.solve(*ROI3, 1.0, member_kinds=(), stack=st, use_cache=False, allow_network=False,
                    out_dir=ROOT / 'data' / 'cache' / 'anysite' / 'test_bundles')
        ref = json.loads(BUNDLE_ROI3.read_text())['skyline']['elevation_deg']
        d = np.array([abs(x - y) for x, y in zip(a['skyline']['elevation_deg'], ref) if x is not None and y is not None])
        self.assertGreater(d.size, 700)
        self.assertLessEqual(float(np.median(d)), 0.05)
        self.assertLessEqual(float(np.percentile(d, 95)), 0.3)


if __name__ == '__main__':
    unittest.main()
