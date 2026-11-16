"""WAC albedo (Hapke w per vertex) and the w-as-variable Hapke graph. Pure Python; the map tests need the cached PDS file."""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v2 import albedo, hapke  # noqa: E402


class WGraph(unittest.TestCase):
    def test_graph_with_w_variable_equals_constant_graph_and_reference(self):
        p = hapke.params('SOUTH_60_70')
        pv = dict(p, w=hapke.X.var('w'))
        col_c, r_c = hapke.diffuse_colour_graph(p)
        col_v, r_v = hapke.diffuse_colour_graph(pv)
        rng = np.random.default_rng(2)
        for _ in range(300):
            i, e = rng.uniform(0, 85), rng.uniform(0, 85)
            g = rng.uniform(abs(i - e), min(i + e, 175))
            w = float(rng.uniform(0.2, 0.7))
            env = {'mu0': math.cos(math.radians(i)), 'mu': math.cos(math.radians(e)), 'cosg': math.cos(math.radians(g)), 'w': w}
            ref = hapke.reference_r(dict(p, w=w), i, e, g)
            self.assertAlmostEqual(r_v.eval(env), ref, delta=1e-9 + 1e-7 * abs(ref))
            if abs(w - p['w']) < 1e-12:
                self.assertAlmostEqual(col_v.eval(env), col_c.eval(env), places=12)
        # at w = the constant, the variable graph is the constant graph (incl. the backlit branch)
        for mu0 in (0.5, 0.0, -0.3):
            env = {'mu0': mu0, 'mu': 0.9, 'cosg': 0.4, 'w': p['w']}
            self.assertAlmostEqual(col_v.eval(env), col_c.eval(env), places=9)

    def test_backlit_colour_scales_with_w(self):
        p = hapke.params('SOUTH_60_70')
        col_v, _ = hapke.diffuse_colour_graph(dict(p, w=hapke.X.var('w')))
        for w in (0.25, 0.42, 0.6):
            env = {'mu0': -0.5, 'mu': 0.9, 'cosg': 0.4, 'w': w}
            self.assertAlmostEqual(col_v.eval(env), hapke.backlit_colour(dict(p, w=w)), places=9)


class WMapSynthetic(unittest.TestCase):
    def wm(self):
        w = np.full((140, 360), 0.3)
        w[:, 10] = 0.5                       # cell centred at 10.5 E
        w[0, :] = 0.2                        # top line (69.5 N)
        w[139, :] = 0.6                      # bottom line (69.5 S)
        w[70, 200] = np.nan                  # a null cell (south half: line 70 is centred at 0.5 S)
        return albedo.WMap(w, 'synthetic', north_fallback=0.35, south_fallback=0.45)

    def test_registration_and_bilinear(self):
        m = self.wm()
        self.assertAlmostEqual(float(m.sample(0.5, 10.5)), 0.5)          # cell centre
        self.assertAlmostEqual(float(m.sample(0.5, 11.0)), 0.4)          # half-way to the next centre
        self.assertAlmostEqual(float(m.sample(0.5, 10.5 - 360)), 0.5)    # periodic longitude
        self.assertAlmostEqual(float(m.sample(0.5, 0.0)), 0.3)
        self.assertAlmostEqual(float(m.sample(69.5, 100)), 0.2)
        self.assertAlmostEqual(float(m.sample(-0.5, 200.5)), 0.45)       # null cell -> hemisphere fallback
        self.assertEqual(m.null_cells, 1)

    def test_polar_blend(self):
        m = self.wm()
        self.assertAlmostEqual(float(m.sample(70.0, 50)), 0.5 * 0.2 + 0.5 * 0.35)
        self.assertAlmostEqual(float(m.sample(-70.5, 50)), 0.45)
        self.assertAlmostEqual(float(m.sample(-89.5, 50)), 0.45)
        self.assertAlmostEqual(float(m.sample(80.0, 50)), 0.35)

    def test_south_polar_scene_is_the_old_constant_without_the_map(self):
        w, info = albedo.w_for_points(np.array([-89.4, -88.0, -71.0]), np.array([0.0, 10.0, 20.0]), wmap=None)
        self.assertTrue(np.all(w == hapke.PARAMS_643NM['SOUTH_60_70']['w']))
        self.assertIn('constant', info['mode'])


@unittest.skipUnless(albedo.MAP_PATH.exists(), 'WAC Hapke map not cached')
class WMapReal(unittest.TestCase):
    def test_real_map_values(self):
        m = albedo.WMap.load()
        self.assertEqual(m.sha256, hapke.PDS_SHA256)
        # the regional fallback is the published median of the ten southernmost lines (hapke.py)
        maps, _ = hapke.read_pds_map(albedo.MAP_PATH)
        self.assertAlmostEqual(float(np.nanmedian(maps['w'][130:140])), m.south, places=3)
        # maria are darker than highlands: Mare Imbrium (~33 N, 15 W) vs the central highlands near Apollo 16 (9 S, 15.5 E)
        self.assertLess(float(m.sample(33.0, -15.0)), float(m.sample(-8.97, 15.50)))
        w = m.sample(np.linspace(-70, 70, 50), np.linspace(-180, 180, 50))
        self.assertTrue(np.all((w > 0.05) & (w < 0.95)))


if __name__ == '__main__':
    unittest.main()
