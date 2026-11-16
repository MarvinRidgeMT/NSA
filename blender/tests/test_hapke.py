import math
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v2 import hapke as H  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PDS = ROOT / 'data' / 'cache' / 'v2' / 'blender' / 'lroc_wac_hapkeparammap' / H.PDS_FILE


def geometry(rng):
    i, e, psi = rng.uniform(0.5, 88), rng.uniform(0.5, 88), rng.uniform(0, 180)
    ri, re, rp = (math.radians(v) for v in (i, e, psi))
    g = math.degrees(math.acos(math.cos(ri) * math.cos(re) + math.sin(ri) * math.sin(re) * math.cos(rp)))
    return i, e, g


class GraphMatchesReference(unittest.TestCase):
    def test_graph_equals_straight_line_reference(self):
        """The expression graph (what becomes Blender nodes) equals the independent straight-line implementation."""
        rng = random.Random(7)
        for region in ('SOUTH_60_70', 'GLOBAL'):
            p = H.params(region)
            for _ in range(2000):
                i, e, g = geometry(rng)
                a, b = H.r_value(p, i, e, g), H.reference_r(p, i, e, g)
                self.assertLess(abs(a - b), 1e-9 * max(1.0, b), (region, i, e, g, a, b))

    def test_graph_size_is_bounded(self):
        r, _ = H.hapke_graph(H.params())
        self.assertLess(r.count(), 400)


class Physics(unittest.TestCase):
    p = H.params()

    def test_zero_roughness_has_no_shadowing(self):
        q = dict(self.p, theta_bar_deg=0.0)
        # smooth IMSA with K=1: r = w/4pi mu0/(mu0+mu) [p(1+B) + H H - 1]
        i, e, g = 40.0, 20.0, 50.0
        mu0, mu = math.cos(math.radians(i)), math.cos(math.radians(e))
        b, c, w = q['b'], q['c'], q['w']
        cg = math.cos(math.radians(g))
        pg = (1 + c) / 2 * (1 - b * b) / (1 - 2 * b * cg + b * b) ** 1.5 + (1 - c) / 2 * (1 - b * b) / (1 + 2 * b * cg + b * b) ** 1.5
        B = q['B_S0'] / (1 + math.tan(math.radians(g) / 2) / q['h_S'])
        want = w / 4 / math.pi * mu0 / (mu0 + mu) * (pg * (1 + B) + H.H_hapke2002(mu0, w) * H.H_hapke2002(mu, w) - 1)
        self.assertAlmostEqual(H.reference_r(q, i, e, g), want, places=12)
        self.assertAlmostEqual(H.r_value(q, i, e, g), want, places=9)

    def test_h_function_against_chandrasekhar(self):
        """Hapke (2002) H approximation vs Chandrasekhar's exact isotropic H (Chandrasekhar 1960, Table XIII):
        H(mu=1, w=1) = 2.9078, H(mu=0.5, w=1) = 2.0128; the approximation is good to ~1 %."""
        self.assertAlmostEqual(H.H_hapke2002(1.0, 0.999999) / 2.9078, 1.0, delta=0.01)
        self.assertAlmostEqual(H.H_hapke2002(0.5, 0.999999) / 2.0128, 1.0, delta=0.01)

    def test_opposition_surge(self):
        """Shadow-hiding opposition effect: r rises toward g = 0 at fixed i = e (both 30 deg, psi 0 -> g 0)."""
        self.assertGreater(H.reference_r(self.p, 30, 30, 0.1), H.reference_r(self.p, 30, 30, 10) * 1.3)

    def test_roughness_darkens_grazing_light(self):
        rough, smooth = self.p, dict(self.p, theta_bar_deg=0.0)
        self.assertLess(H.reference_r(rough, 85, 0, 85), H.reference_r(smooth, 85, 0, 85))

    def test_reflectance_in_lunar_range(self):
        """I/F at i = g = 30 deg, e = 0 must lie in the lunar range (~0.05 maria .. ~0.2 bright highlands)."""
        for region in ('SOUTH_60_70', 'GLOBAL'):
            iof = math.pi * H.reference_r(H.params(region), 30, 0, 30)
            self.assertTrue(0.05 < iof < 0.2, (region, iof))

    def test_diffuse_colour_reproduces_r(self):
        """Cycles Diffuse returns colour/pi * E mu0; with colour = pi r / mu0 that is r E (below the cap)."""
        col, r = H.diffuse_colour_graph(self.p)
        env = {'mu0': math.cos(math.radians(60)), 'mu': 1.0, 'cosg': math.cos(math.radians(60))}
        self.assertAlmostEqual(col.eval(env) / math.pi * env['mu0'], r.eval(env), places=12)

    def test_backlit_facets_still_reflect(self):
        """Regression (found on a ShadowCam render): facets facing away from the dominant light must keep a non-zero colour so
        earthshine and terrain-scattered light are reflected."""
        col, _ = H.diffuse_colour_graph(self.p)
        back = col.eval({'mu0': -0.3, 'mu': 0.8, 'cosg': 0.2})
        self.assertAlmostEqual(back, H.backlit_colour(self.p), places=12)
        self.assertTrue(0.05 < back < 0.3, back)
        lit = col.eval({'mu0': 0.5, 'mu': 1.0, 'cosg': 0.5})
        self.assertAlmostEqual(lit, math.pi * H.reference_r(self.p, 60, 0, 60) / 0.5, places=9)

    def test_fixed_parameters_from_pds_readme(self):
        self.assertEqual(H.FIXED, {'B_C0': 0.0, 'h_C': 1.0, 'theta_bar_deg': 23.657, 'K': 1.0})


@unittest.skipUnless(PDS.exists(), 'LROC WAC Hapke map not in data/cache (download: hapke.PDS_URL)')
class PdsMap(unittest.TestCase):
    def test_compiled_parameters_reproduce_the_map(self):
        import numpy  # noqa: F401
        maps, sha = H.read_pds_map(PDS)
        self.assertEqual(sha, H.PDS_SHA256)
        stats = H.map_statistics(maps)
        for region, vals in stats.items():
            for k, v in vals.items():
                self.assertAlmostEqual(H.PARAMS_643NM[region][k], v, places=4, msg=(region, k))

    def test_fixed_bands_are_constant(self):
        import numpy as np
        maps, _ = H.read_pds_map(PDS)
        self.assertTrue(np.allclose(maps['theta_bar_deg'], 23.6566, atol=1e-3))
        self.assertTrue(np.allclose(maps['B_C0'], 0.0))
        self.assertTrue(np.allclose(maps['h_C'], 1.0))


if __name__ == '__main__':
    unittest.main()
