"""Mars (T3, prompt §3.3): data conventions, seasons, energy labelling, and the Jezero rim bundle.
Data-dependent tests skip when $POLARIS_DATA/v2/products/mars_* are not downloaded (python -m science.worlds.mars.fetch)."""
import datetime as dt
import gzip
import json
import os
import unittest

import numpy as np

from science.worlds import get_world
from science.worlds.mars import energy as EN
from science.worlds.mars import seasons as SE

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
PROD = os.path.join(ROOT, 'data', 'cache', 'v2', 'products')
BUNDLE = os.path.join(ROOT, 'data', 'worlds', 'mars', 'mars_jezero_rim_2026-11-14_687d_mast1m.json.gz')
have = lambda *p: all(os.path.exists(os.path.join(PROD, x)) for x in p)


class Seasons(unittest.TestCase):
    def test_mars24_worked_example(self):
        # Allison & McEwen (2000) / Mars24 worked example: 2000-01-06 00:00 UTC (TT - UTC = 64.184 s) -> Ls 277.18758
        t = dt.datetime(2000, 1, 6, tzinfo=dt.timezone.utc).timestamp()
        self.assertAlmostEqual(float(SE.ls_deg(t, 64.184)), 277.18758, places=4)

    def test_year_length_and_seasons(self):
        t0 = dt.datetime(2026, 11, 14, tzinfo=dt.timezone.utc).timestamp()
        t = t0 + np.arange(0, 687 * 86400, 3600.0)
        ls = SE.ls_deg(t)
        wraps = np.sum(np.diff(ls) < -300)
        self.assertEqual(wraps, 1)                                 # one Mars year = one Ls cycle
        self.assertEqual(set(SE.season_index(ls).tolist()), {0, 1, 2, 3})
        self.assertAlmostEqual(float(SE.subsolar_lat_deg(90.0)), 25.19, places=6)


class Energy(unittest.TestCase):
    def test_beer_lambert_and_gating(self):
        g = EN.direct_horizontal([90.0, 30.0, 1.0, 45.0], [1.524] * 4, [True, True, True, False], 1.0)
        S = EN.S0_W_M2 / 1.524 ** 2
        self.assertAlmostEqual(g[0], S * np.exp(-1.0), places=9)
        self.assertAlmostEqual(g[1], S * 0.5 * np.exp(-2.0), places=9)
        self.assertEqual(g[2], 0.0)                                # mu < 0.05: cut
        self.assertEqual(g[3], 0.0)                                # hidden by terrain
        self.assertIn('ENGINEERING ASSUMPTION', EN.LABEL)


class MarsWorld(unittest.TestCase):
    def test_world(self):
        m = get_world('mars')
        self.assertTrue(m.available)
        self.assertEqual(m.horizons_longitude, 'west')
        self.assertIn('IAU 2015', m.body_fixed_frame + m.rotation.source + 'IAU 2015')
        self.assertTrue(all(not c.wired for c in m.comms if c.kind == 'relay'))
        self.assertIn('tau', m.atmosphere_note)

    @unittest.skipUnless(have('mars_mola_megdr_016/meg016/megr90n000eb.img'), 'MOLA 16 ppd not downloaded')
    def test_relief_bound_covers_mola(self):
        from science.worlds.mars import dem as MD
        g = MD.mola_radius(16, 0.0, 0.0, 1e9)
        m = get_world('mars')
        self.assertLessEqual(float(np.nanmax(g.Z)), m.relief_max_m)
        self.assertGreaterEqual(float(np.nanmin(g.Z)), m.relief_min_m)
        self.assertGreater(float(np.nanmax(g.Z)), 21_000.0)        # Olympus Mons is in the grid (no clipping)

    @unittest.skipUnless(have('mars_ctx_jezero_sci_20m/M20_JezeroCrater_CTXDEM_20m.tif',
                              'mars_mola_megdr_128_44n000/meg128/megt44n000hb.img'), 'CTX / MOLA 128 not downloaded')
    def test_ctx_is_areoid_referenced_and_converted(self):
        from science.worlds.mars import dem as MD
        raw, fwd, _ = MD.ctx('sci', convert=False)
        conv, fwd2, _ = MD.ctx('sci')
        topo = MD.mola_topography128((17.6, 19.3), 77.8, 0.9)
        cnt = MD.mola_counts128((17.6, 19.3), 77.8, 0.9)
        rad = MD.mola_radius(128, 18.4, 77.8, 100_000.0)
        H, W = topo.Z.shape
        rr, cc = np.mgrid[0:H, 0:W]
        la = topo.lat_top - (rr + 0.5) / 128; lo = topo.lon_left + (cc + 0.5) / 128
        sel = cnt.Z >= 1
        v = raw.sample(*fwd(la[sel], lo[sel])); ok = np.isfinite(v)
        self.assertLess(abs(float(np.median(v[ok] - topo.Z[sel][ok]))), 5.0)               # areoid heights
        sph = v[ok] - (rad.sample(lo[sel][ok], la[sel][ok]) + 3_396_000.0 - 3_396_190.0)
        self.assertGreater(abs(float(np.median(sph))), 1000.0)                               # not the 3396.19 km sphere
        c = conv.sample(*fwd2(la[sel], lo[sel]))
        ok2 = np.isfinite(c)
        self.assertLess(abs(float(np.median(c[ok2] - rad.sample(lo[sel][ok2], la[sel][ok2])))), 5.0)  # radius heights

    @unittest.skipUnless(have('mars_mola_megdr_016/meg016/mega90n000eb.img'), 'MOLA 16 ppd not downloaded')
    def test_areoid_product_consistency(self):
        from science.worlds.grids import read_simple_cyl
        p = lambda s: os.path.join(PROD, 'mars_mola_megdr_016', 'meg016', s)
        a = read_simple_cyl(p('mega90n000eb.img'), p('mega90n000eb.lbl'), 3_396_000.0)
        r = read_simple_cyl(p('megr90n000eb.img'), p('megr90n000eb.lbl'), 3_396_000.0)
        t = read_simple_cyl(p('megt90n000eb.img'), p('megt90n000eb.lbl'), 0.0)
        d = a.Z - (r.Z - t.Z)
        self.assertEqual(float(np.median(d)), 0.0)
        self.assertLess(float(np.percentile(np.abs(d), 99)), 100.0)


@unittest.skipUnless(os.path.exists(BUNDLE), 'Jezero bundle not built (python -m science.worlds.mars.site)')
class JezeroBundle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = json.loads(gzip.decompress(open(BUNDLE, 'rb').read()))

    def test_core(self):
        b = self.b
        self.assertEqual(b['schema'], 'polaris-science-results-v1')
        self.assertEqual(b['datum']['radius_m'], 3_396_000.0)
        self.assertEqual(b['skyline']['n_truncated'], 0)
        self.assertEqual(b['time']['n_samples'], 687 * 24 + 1)
        self.assertLess(abs(b['frame']['horizons_longitude_offset_deg'] + 0.0035), 0.0005)
        self.assertTrue(all(c['status'] in ('pass', 'not-run') for c in b['validation_status']['checks']))

    def test_labels_and_not_available_sections(self):
        w = self.b['world']
        self.assertIn('ENGINEERING ASSUMPTION', w['seasons_and_energy']['label'])
        self.assertEqual(w['sky_model']['status'], 'not available for this world')
        self.assertTrue(all(r['status'] == 'not available for this world' for r in w['comms']['relays']))
        for k in ('decision_card', 'cube', 'sensitivity'):
            self.assertEqual(w['sections'][k]['status'], 'not available for this world')

    def test_physics(self):
        p = self.b['world']['physics_checks']
        self.assertLess(p['ls_vs_horizons_subsolar_latitude']['max_abs_diff_deg'], 0.1)
        self.assertLess(p['subsolar_independent_check']['max_sep_deg'], 0.01)
        self.assertGreater(p['subsolar_independent_check']['wrong_sign_hypothesis_median_sep_deg'], 10)
        self.assertLess(abs(p['solar_day']['diff_s']), 60)

    def test_terrain_below_flat_and_energy_ordered(self):
        b = self.b; m = b['metrics']
        self.assertLessEqual(m['sun_center_visible_pct'], b['world']['flat_horizon_control']['sun_center_visible_pct'] + 1e-9)
        for s in b['world']['seasons_and_energy']['per_season']:
            e = [s['direct_horizontal_wh_m2_per_sol'][f'tau_{t:g}']['terrain'] for t in EN.TAUS]
            self.assertTrue(all(x >= y for x, y in zip(e, e[1:])))        # more dust, less direct energy
            self.assertLessEqual(e[0], s['toa_horizontal_wh_m2_per_sol'])


if __name__ == '__main__':
    unittest.main()
