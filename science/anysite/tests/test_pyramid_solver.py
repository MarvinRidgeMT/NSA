"""R1 (v2 round 2): the merged whole-Moon pyramid as the any-site solver's default terrain.

Plan and rules: docs/v2/PHASE_1_R1_PLAN.md. Each test can fail; skips state their reason.
Run: python -m pytest -q science/anysite
"""
import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from science import frames
from science.anysite import solve as S
from science.anysite.stack import LegacyStack, PyramidStack, fine_radius_m
from science.terrain import stack as TS

ROOT = Path(__file__).resolve().parents[3]


def _real_pyramid():
    try:
        return TS.TerrainStack.open()
    except FileNotFoundError as exc:
        raise unittest.SkipTest(f'whole-Moon pyramid not built in $POLARIS_DATA ({exc})')


# ------------------------------------------------------------------------------------------------ sample_height
class SampleHeight(unittest.TestCase):
    """API addition to science.terrain.stack: heights only, one gather per level, optional level limits."""

    @classmethod
    def setUpClass(cls):
        cls.st = _real_pyramid()
        rng = np.random.default_rng(11)
        # few, clustered points: every random global point would load its own finest-level tiles
        lat = np.r_[rng.uniform(-90, 90, 60), 57.5 + rng.uniform(-1.2, 1.2, 60), -57.5 + rng.uniform(-1.2, 1.2, 60),
                    -89.78012 + rng.uniform(-0.05, 0.05, 100), 0.5 + rng.uniform(-0.2, 0.2, 100)]
        lon = np.r_[rng.uniform(-180, 180, 60), 10 + rng.uniform(-2, 2, 120), -156.3 + rng.uniform(-2, 2, 100),
                    179.9 + rng.uniform(0, 0.2, 100)]
        cls.lat, cls.lon = lat, lon

    def test_equals_sample(self):
        h_ref = self.st.sample(self.lat, self.lon)[0]
        h = self.st.sample_height(self.lat, self.lon)
        self.assertTrue(np.array_equal(np.isnan(h), np.isnan(h_ref)))
        self.assertTrue(np.array_equal(h[np.isfinite(h)], h_ref[np.isfinite(h_ref)]))      # bit-identical

    def test_blend_both_hemispheres_in_one_call(self):
        # regression (R1): _query_blended indexed the hemisphere subset twice and raised IndexError when one call held
        # blend-band points of both hemispheres
        lat = np.array([57.0, -57.0, 58.0, -56.9]); lon = np.array([10.0, 10.0, 11.0, 12.0])
        both = self.st.sample(lat, lon)[0]
        for i in range(4):
            self.assertEqual(both[i], self.st.sample(lat[i:i + 1], lon[i:i + 1])[0][0])

    def test_max_level_matches_query(self):
        for top in (2, 4):
            ref = self.st._query_blended(self.lat, self.lon, levels=list(range(0, top + 1)))['height']
            h = self.st.sample_height(self.lat, self.lon, max_level=top)
            self.assertTrue(np.array_equal(h, ref, equal_nan=True), top)

    def test_exact_level_and_zone_dict(self):
        lat = np.full(50, -89.78012); lon = np.linspace(-157.0, -155.5, 50)
        one = self.st.sample_height(lat, lon, max_level={'sp': 8}, min_level={'sp': 8})
        ref = self.st._query(lat, lon, levels=[8], zone='sp')['height']
        self.assertTrue(np.array_equal(one, ref, equal_nan=True))
        # a dict naming only 'eq' reads nothing at the south pole
        self.assertTrue(np.isnan(self.st.sample_height(lat, lon, max_level={'eq': 4})).all())

    def test_touched_tiles_exist(self):
        touched = set()
        self.st.sample_height(self.lat[:200], self.lon[:200], max_level={'sp': 4, 'np': 4, 'eq': 3}, touched=touched)
        self.assertGreater(len(touched), 10)
        self.assertTrue(all(self.st.has_tile(*t) for t in touched))
        self.assertTrue(all(t[1] <= (3 if t[0] == 'eq' else 4) for t in touched))


# ------------------------------------------------------------------------------------------------ synthetic flat pyramid
def _flat_pyramid(root, Hc, zones=('eq', 'np')):
    """Constant-height science pyramid at level 0 (eq: 15 deg tiles, polar: 655 km tiles), all four bands."""
    import rasterio
    tiles = []
    for z in zones:
        Z = TS.ZONES[z]
        nx, ny = Z.n_tiles(0)
        T = Z.tile_px
        a = np.empty((4, T, T), np.float32)
        a[0] = Hc; a[1] = 6; a[2] = Z.pixel_m(0); a[3] = 2
        for iy in range(ny):
            for ix in range(nx):
                p = TS.tile_path(root, z, 0, ix, iy)
                p.parent.mkdir(parents=True, exist_ok=True)
                with rasterio.open(p, 'w', driver='GTiff', width=T, height=T, count=4, dtype='float32',
                                   compress='deflate') as ds:
                    ds.write(a)
                tiles.append({'zone': z, 'level': 0, 'ix': ix, 'iy': iy, 'sha256': 'synthetic'})
    (Path(root) / 'index.json').write_text(json.dumps({'label': 'synthetic flat test pyramid', 'tiles': tiles}))
    return TS.TerrainStack.open(root)


class FlatSpherePyramid(unittest.TestCase):
    """Constant-height pyramid through the whole default path (PyramidStack -> near window / native-grid sampler ->
    LatLonView / PyramidField -> compute_skyline): every bin equals the bare-sphere dip -acos((R+Hc)/(R+Hc+mast)) within
    1e-4 deg, at an equatorial and a mid-latitude site (eq zone, 'local-stere' window), a site at 57 N whose rays cross
    the eq/np switch and blend band, and a north-polar site (np zone). Mast 30 m puts the tangent point at ~10.4 km,
    inside the near field; the ray step there is pixel/5 (~190-256 m), whose sampling error at the tangent is ~1e-5 deg."""

    @classmethod
    def setUpClass(cls):
        cls.td = tempfile.TemporaryDirectory()
        cls.Hc = 350.0
        cls.pyr = _flat_pyramid(Path(cls.td.name) / 'pyramid', cls.Hc)
        cls.st = PyramidStack(pyramid=cls.pyr, products=LegacyStack(entries=[]))

    @classmethod
    def tearDownClass(cls):
        cls.td.cleanup()

    def _check(self, lat, lon, zone, proj):
        mast = 30.0
        T = S.terrain_stage(self.st, lat, lon, mast)
        R = frames.R_MOON_M
        dip = -math.degrees(math.acos((R + self.Hc) / (R + self.Hc + mast)))
        el = np.array(T['sky']['elevation_deg'], float)
        self.assertEqual(T['sky']['n_truncated'], 0)
        self.assertAlmostEqual(T['h'], self.Hc, places=6)
        self.assertLess(float(np.max(np.abs(el - dip))), 1e-4, (lat, el.min(), el.max(), dip))
        info = T['near_e']['pyramid']
        self.assertEqual((info['zone'], info['window_proj']), (zone, proj))
        self.assertGreater(T['near_cut'], 10_500.0)        # the tangent point lies inside the fine-step range
        self.assertAlmostEqual(float(np.nanmax(T['far'].Z)), self.Hc)

    def test_equatorial(self):
        self._check(2.5, 7.0, 'eq', 'local-stere')

    def test_mid_latitude(self):
        self._check(-41.0, 123.4, 'eq', 'local-stere')

    def test_across_zone_switch(self):
        self._check(57.0, -30.0, 'eq', 'local-stere')

    def test_north_polar(self):
        self._check(75.0, 200.0 - 360.0, 'np', 'np')

    def test_near_cut_rule_on_feathered_window(self):
        # a window whose pixels beyond 3 km carry a coarser native_res_m (feather band): d_fine = 3 km (+- 1 px)
        zd = self.pyr.window(2.5, 7.0, 10_000.0, TS.ZONES['eq'].pixel_m(0))
        n = zd.Z.shape[0]
        xs = zd.x_left + (np.arange(n) + 0.5) * zd.step
        X, Y = np.meshgrid(xs, zd.y_top - (np.arange(n) + 0.5) * zd.step)
        x0, y0 = zd.forward(2.5, 7.0)
        nr = zd.layers['native_res_m'].copy()
        nr[np.hypot(X - float(x0), Y - float(y0)) > 3000.0] = 1e4
        zd.layers['native_res_m'] = nr
        d = fine_radius_m(zd, 2.5, 7.0)
        self.assertTrue(3000.0 <= d <= 3000.0 + zd.step, d)


# ------------------------------------------------------------------------------------------------ real eq data
def _sldem_tile(lat, lon):
    """Path of the SLDEM2015 512 ppd tile (PDS) holding (lat, lon), and its top latitude / west longitude."""
    base = ROOT / 'data' / 'cache' / 'v2' / 'products' / 'sldem2015_512' / 'data' / 'sldem2015' / 'tiles' / 'float_img'
    top = 30 * math.floor(lat / 30) + 30
    bot = top - 30
    west = 45 * math.floor((lon % 360) / 45)
    fmt = lambda v, other: (f'{abs(v):02d}{"n" if v > 0 else "s"}' if v != 0 else ('00n' if other > 0 else '00s'))
    name = f'sldem2015_512_{fmt(bot, top)}_{fmt(top, bot)}_{west:03d}_{west + 45:03d}'
    p = base / f'{name}_float.lbl'
    return (p if p.exists() else None), top, west


class EqZoneRealData(unittest.TestCase):
    """Apollo 11 (0.67 N, mare) and Chang'e 3 (44.1 N) end to end on the pyramid: no truncated bins, plausible mare
    horizons, and the near field equals an independent read of the SLDEM2015 tile (raw PDS float, km -> m, bilinear
    on its own 1/512 deg grid) to 1 mm -- i.e. the eq path samples the native grid with no reprojection."""

    @classmethod
    def setUpClass(cls):
        cls.st = PyramidStack()

    def _raw_sldem(self, lat, lon, la, lo):
        import rasterio
        from rasterio.windows import Window
        p, top, west = _sldem_tile(lat, lon)
        if p is None:
            self.skipTest('SLDEM2015 512 ppd tile not downloaded')
        ppd = 512.0
        r0 = int((top - lat - 0.5) * ppd); c0 = int(((lon - west) % 360 - 0.5) * ppd)
        with rasterio.open(p) as ds:
            A = ds.read(1, window=Window(c0, r0, 512, 512)).astype(np.float64) * 1000.0
        r = (top - la) * ppd - 0.5 - r0; c = ((lo - west) % 360) * ppd - 0.5 - c0
        i = np.floor(r).astype(int); j = np.floor(c).astype(int); a = r - i; b = c - j
        return (1 - a) * (1 - b) * A[i, j] + (1 - a) * b * A[i, j + 1] + a * (1 - b) * A[i + 1, j] + a * b * A[i + 1, j + 1]

    def _run(self, lat, lon):
        T = S.terrain_stage(self.st, lat, lon, 1.0)
        info = T['near_e']['pyramid']
        self.assertEqual((info['zone'], info['level'], info['window_proj']), ('eq', 4, 'local-stere'))
        self.assertEqual(T['sky']['n_truncated'], 0)
        el = np.array(T['sky']['elevation_deg'], float)
        self.assertTrue(np.all((el > -2.0) & (el < 8.0)), (el.min(), el.max()))
        self.assertEqual(T['step_near'], TS.ZONES['eq'].pixel_m(4) / 5)
        self.assertEqual(T['far'].step, TS.ZONES['eq'].pixel_m(3))
        rng = np.random.default_rng(5)
        la = lat + rng.uniform(-0.25, 0.25, 5000); lo = lon + rng.uniform(-0.25, 0.25, 5000)
        hp = T['near'].sample(*frames.stereo_forward(la, lo))
        hr = self._raw_sldem(lat, lon, la, lo)
        self.assertLess(float(np.nanmax(np.abs(hp - hr))), 1e-3)
        self.assertTrue(np.isfinite(hp).all())
        return T, el

    def test_apollo11(self):
        T, el = self._run(0.67416, 23.47314)
        self.assertLess(float(np.median(el)), 3.0)

    def test_change3(self):
        self._run(44.1214, -19.5117)


class GetStack(unittest.TestCase):
    def test_env_selects_legacy(self):
        import os
        from science.anysite import stack as STK
        old = os.environ.get('POLARIS_ANYSITE_STACK')
        try:
            os.environ['POLARIS_ANYSITE_STACK'] = 'legacy'
            self.assertIsInstance(STK.get_stack(), LegacyStack)
        finally:
            if old is None:
                os.environ.pop('POLARIS_ANYSITE_STACK', None)
            else:
                os.environ['POLARIS_ANYSITE_STACK'] = old


if __name__ == '__main__':
    unittest.main()
