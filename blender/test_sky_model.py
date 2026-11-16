"""Sky model geometry (blender/sky_model.py): pure Python, no bpy."""
import math
import unittest

import sky_model as skm

N, E = (0.0, 1.0), (1.0, 0.0)  # grid north = local north (longitude 0 in the south-polar grid)


def samples(az_el):
    return [{'time': f't{k}', 'sun': {'az': a, 'el': e}, 'earth': {'az': a + 180, 'el': e + 3}} for k, (a, e) in enumerate(az_el)]


class SkyModel(unittest.TestCase):
    def test_shell_point_true_direction_and_radius(self):
        p = skm.shell_point(N, E, (0, 0, 2), 20000, 90.0, 0.0)
        self.assertAlmostEqual(p[0], 20000, places=6)  # due local east, on the horizontal
        self.assertAlmostEqual(p[1], 0, places=6)
        self.assertAlmostEqual(p[2], 2, places=6)
        q = skm.shell_point(N, E, (0, 0, 0), 1000, 0.0, 1.5)
        self.assertAlmostEqual(math.degrees(math.atan2(q[2], math.hypot(q[0], q[1]))), 1.5, places=9)

    def test_rotated_basis_matches_bundle_v2_formula(self):
        L = math.radians(-156.32)
        n, e = (math.sin(L), math.cos(L)), (math.cos(L), -math.sin(L))
        d = skm.direction(n, e, 37.0, 2.0)
        import bundle_v2 as bv
        ref = bv.grid_direction({'site': {'longitudeEastDeg': -156.32}}, 37.0, 2.0)
        for a, b in zip(d, ref):
            self.assertAlmostEqual(a, b, places=12)

    def test_chart_only_scales_elevation(self):
        p = skm.chart_point(N, E, (0, 0, 0), 800, 45.0, 2.0, 5.0)
        self.assertAlmostEqual(math.degrees(math.atan2(p[2], math.hypot(p[0], p[1]))), 10.0, places=9)
        self.assertAlmostEqual(math.degrees(math.atan2(p[0], p[1])), 45.0, places=9)
        self.assertLess(skm.chart_point(N, E, (0, 0, 0), 800, 0, 30, 5)[2], 800)  # clamped below the zenith

    def test_true_angular_size(self):
        r = skm.body_radius(20000, skm.SUN_RADIUS_DEG)
        self.assertAlmostEqual(math.degrees(math.atan(r / 20000)), 0.2666, places=9)
        self.assertAlmostEqual(skm.EARTH_RADIUS_DEG, 0.9497, places=3)

    def test_skyline_ring_closes_and_breaks_at_missing_bins(self):
        pt = lambda a, e: (a, e, 0)
        ring = skm.skyline_polylines({'azimuthDeg': [0, 90, 180, 270], 'elevationDeg': [1, 2, 3, 4]}, pt)
        self.assertEqual(len(ring), 1)
        self.assertEqual(ring[0][0], ring[0][-1])
        gap = skm.skyline_polylines({'azimuthDeg': [0, 90, 180, 270], 'elevationDeg': [1, 2, None, 4]}, pt)
        self.assertEqual([len(r) for r in gap], [2])  # the lone bin after the gap is not a line, and nothing is filled in

    def test_path_runs_follow_bundle_flags_and_join(self):
        s = samples([(k * 10, 1.0) for k in range(6)])
        runs = skm.path_runs(s, 'sun', [True, True, False, False, True, None], lambda a, e: (a, e, 0))
        self.assertEqual([r[0] for r in runs], ['clear', 'blocked', 'clear', 'not evaluated'])
        self.assertEqual([(r[2], r[3]) for r in runs], [(0, 2), (2, 4), (4, 5), (5, 5)])
        self.assertEqual(runs[0][1][-1], runs[1][1][0])  # no gap between runs
        none = skm.path_runs(s, 'earth', None, lambda a, e: (a, e, 0))
        self.assertEqual([r[0] for r in none], ['not evaluated'])

    def test_chart_excludes_skylines_from_other_points(self):
        sc = [{'id': 'baseline', 'kind': 'baseline', 'skyline': {'azimuthDeg': [0]}}, {'id': 'mast10', 'kind': 'mast_height', 'skyline': {'azimuthDeg': [0]}},
              {'id': 'clone003', 'family': 'dem-clone', 'skyline': {'azimuthDeg': [0]}}, {'id': 'pos_e+100_n+0', 'family': 'position-offset', 'skyline': {'azimuthDeg': [0]}},
              {'id': 'metrics-only', 'kind': 'x'}]
        self.assertEqual([x[0] for x in skm.chart_scenarios(sc)], ['baseline', 'mast10', 'clone003'])

    def test_summary_counts_bundle_flags(self):
        s = samples([(0, 1.0), (10, 2.0), (20, -0.5)])
        sc = {'samples': {'sun': {'visible': [True, False, False]}, 'earth': {'visible': [True, True, True]}}}
        out = skm.summary(s, sc)
        self.assertEqual((out['sun']['clear'], out['sun']['blocked']), (1, 2))
        self.assertEqual(out['sun']['elevationRangeDeg'], [-0.5, 2.0])


if __name__ == '__main__':
    unittest.main()
