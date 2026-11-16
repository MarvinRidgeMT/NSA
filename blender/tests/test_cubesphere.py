"""Cube-sphere base mesh geometry (blender/v2/cubesphere.py). Pure numpy."""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v2 import cubesphere as C  # noqa: E402


class CubeSphere(unittest.TestCase):
    def test_faces_right_handed_and_centres(self):
        for c, eu, ev in C.FACES:
            self.assertTrue(np.allclose(np.cross(eu, ev), c))
        d = np.array([C.directions(f, 0.0, 0.0) for f in range(6)])
        la, lo = C.latlon_deg(d)
        self.assertTrue(np.allclose(la, [0, 0, 0, 0, 90, -90]))
        self.assertTrue(np.allclose(lo[:4], [0, 90, 180, -90]))

    def test_welded_closed_outward_mesh(self):
        n = 8
        V, F, fid, uv, dropped = C.mesh(n, np.zeros((6, n + 1, n + 1)), radius_m=1.0)
        self.assertEqual(dropped, 0)
        self.assertEqual(len(V), 6 * n * n + 2)                 # Euler: V - E + F = 2 for a closed quad sphere
        self.assertEqual(len(F), 6 * n * n)
        self.assertTrue(np.allclose(np.linalg.norm(V, axis=1), 1.0))
        # every edge shared by exactly two quads (closed, no cracks), in opposite directions (consistent winding)
        e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 3]], F[:, [3, 0]]])
        fwd = {tuple(x) for x in e}
        self.assertEqual(len(fwd), len(e))
        self.assertTrue(all((b, a) in fwd for a, b in fwd))
        # outward normals
        P = V[F]
        nrm = np.cross(P[:, 1] - P[:, 0], P[:, 3] - P[:, 0])
        self.assertTrue(np.all(np.sum(nrm * P.mean(axis=1), axis=1) > 0))
        self.assertTrue(np.all((uv >= 0) & (uv <= 1)))

    def test_heights_scale_radius_and_nan_drops_quads(self):
        n = 4
        h = np.full((6, n + 1, n + 1), 1000.0)
        h[0, 2, 2] = np.nan
        V, F, fid, uv, dropped = C.mesh(n, h, radius_m=1_737_400.0, scale=1e-3)
        self.assertEqual(dropped, 4)
        r = np.linalg.norm(V, axis=1)
        self.assertAlmostEqual(float(np.nanmax(r)), 1738.4, places=6)

    def test_equal_angle_spacing_ratio(self):
        smax, smin = C.node_spacing_m(256)
        self.assertLess(smax / smin, 1.45)
        self.assertAlmostEqual(smax, 1_737_400 * (math.pi / 2) / 256, delta=0.02 * smax)

    def test_texel_params_orientation(self):
        A, B = C.texel_params(4)
        self.assertTrue(B[0, 0] > 0 > B[-1, 0])                # image row 0 = +v edge
        self.assertTrue(A[0, 0] < 0 < A[0, -1])


if __name__ == '__main__':
    unittest.main()
