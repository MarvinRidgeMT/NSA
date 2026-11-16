"""Tests for the display-only terrain context (numpy required). Run with the science environment:
   .venv/bin/python -m unittest discover -s tools/terrain -p 'test_*.py' -v"""
import math, os, sys, unittest

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


@unittest.skipIf(np is None, "numpy not installed in this interpreter")
class HorizonMap(unittest.TestCase):
    def setUp(self):
        import terrain_context as tc
        self.tc = tc

    def flat(self, n=41, s=5.0, z=0.0):
        return self.tc.Grid(np.full(n * n, z), n, s, -(n - 1) * s / 2, -(n - 1) * s / 2)

    def test_flat_ground_has_a_slightly_negative_curved_horizon(self):
        g = self.flat()
        h = self.tc.horizon_map(g, 8, g, None, 5, 100, 0, 0)
        self.assertEqual(h.shape, (8, 41, 41))
        centre = h[:, 20, 20]
        self.assertTrue(np.all(centre <= 0) and np.all(centre > -0.01))   # only curvature: -d/(2R) radians

    def test_wall_to_grid_east_blocks_only_the_east_azimuth(self):
        g = self.flat()
        g.z[:, 30] = 10.0                       # a 10 m wall, 50 m toward +x from the centre column (i = 20)
        h = self.tc.horizon_map(g, 8, g, None, 5, 100, 0, 0)
        east, west, north = h[2, 20, 20], h[6, 20, 20], h[0, 20, 20]   # k=2 -> theta 90 deg -> +x
        self.assertAlmostEqual(east, math.degrees(math.atan((10 - 50 * 50 / (2 * self.tc.MOON_RADIUS_M)) / 50)), places=6)
        self.assertLess(west, 0.001)
        self.assertLess(north, 0.001)

    def test_row_order_is_south_to_north(self):
        g = self.flat()
        g.z[30, :] = 10.0                       # wall at larger row index = toward +y (grid north)
        h = self.tc.horizon_map(g, 8, g, None, 5, 100, 0, 0)
        self.assertGreater(h[0, 20, 20], 10)    # k=0 -> +y
        self.assertLess(h[4, 20, 20], 0.001)    # k=4 -> -y

    def test_far_grid_continues_beyond_the_near_crop_after_rebase(self):
        near = self.flat()
        far = self.tc.Grid(np.zeros(21 * 21), 21, 80.0, -800.0, -800.0)
        far.z[:, 16] = 100.0                    # ridge at x = +480 m in the far grid's own frame
        far_rel = self.tc.rebase(far, regional_site_xy=(1000.0, 0.0), dataset_site_xy=(1000.0, 0.0))
        h = self.tc.horizon_map(near, 4, near, far_rel, 5, 100, 80, 800)
        # far marching samples at 180, 260, ... m with nearest-cell lookup: the 80 m ridge cell (440-520 m) is met at d = 500 m
        self.assertAlmostEqual(h[1, 20, 20], math.degrees(math.atan((100 - 500 * 500 / (2 * self.tc.MOON_RADIUS_M)) / 500)), delta=1e-6)
        shifted = self.tc.rebase(far, regional_site_xy=(1080.0, 0.0), dataset_site_xy=(1000.0, 0.0))   # ridge now at +560 m
        h2 = self.tc.horizon_map(near, 4, near, shifted, 5, 100, 80, 800)
        self.assertLess(h2[1, 20, 20], h[1, 20, 20])

    def test_encoding_round_trip_and_clip(self):
        d = np.array([-10.0, -3.0, 0.0, 1.43, 9.75, 40.0])
        back = self.tc.decode_deg(self.tc.encode_deg(d))
        self.assertTrue(np.allclose(back, [-3.0, -3.0, 0.0, 1.45, 9.75, 9.75], atol=1e-9))

    def test_visibility_model(self):
        self.assertEqual(self.tc.sun_visibility(1.0, 0.5), 0.0)
        self.assertEqual(self.tc.sun_visibility(1.0, 1.5), 1.0)
        self.assertAlmostEqual(self.tc.sun_visibility(1.0, 1.0), 0.5)

    def test_subsample_keeps_exact_source_nodes(self):
        g = self.flat()
        g.z[20, 20] = 7.0
        s = g.subsample(21)
        self.assertEqual((s.n, s.s, s.z[10, 10]), (21, 10.0, 7.0))


if __name__ == "__main__":
    unittest.main()
