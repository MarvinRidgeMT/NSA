"""blender/v2/pack.py against science.terrain.stack (needs the project venv with rasterio and the built S3 pyramid)."""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT))
INDEX = ROOT / 'data' / 'cache' / 'v2' / 'pyramid' / 'index.json'

try:
    import rasterio  # noqa: F401
    HAVE = INDEX.exists()
except Exception:
    HAVE = False


@unittest.skipUnless(HAVE, 'needs rasterio (project venv) and the S3 pyramid')
class PackVsStack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from science.terrain.stack import TerrainStack
        from v2 import pack
        cls.st, cls.pack = TerrainStack.open(max_tiles=256), pack

    def test_chunked_eq_window_equals_stack_window(self):
        for lat, lon in ((26.13239, 3.6333), (-8.9734, 15.5011)):
            a = self.st.window(lat, lon, 2500, 80, fill_coarser=True)
            b = self.pack.eq_window_chunked(self.st, lat, lon, 2500, 80, rows_per_chunk=11)
            self.assertTrue(np.array_equal(a.Z, b.Z, equal_nan=True))
            self.assertEqual((a.x_left, a.y_top, a.step, a.proj), (b.x_left, b.y_top, b.step, b.proj))

    def test_south_grid_view_samples_the_window(self):
        from science import frames
        d = self.st.window(26.13239, 3.6333, 3000, None, fill_coarser=True)
        v = self.pack.SouthGridView(d)
        la = 26.13239 + np.array([0.0, 0.01, -0.02]); lo = 3.6333 + np.array([0.0, 0.015, -0.01])
        x, y = frames.stereo_forward(la, lo)
        self.assertTrue(np.allclose(v.sample(x, y), d.sample_latlon(la, lo), rtol=0, atol=1e-6))

    def test_globe_heights_are_level0(self):
        h, st = self.pack.globe_heights(self.st, 2, s=1)
        self.assertEqual(st['nanNodes'], 0)
        # face centres: the stack's own level-0 value at lat/lon (0,0), (0,90), (0,180), (0,-90), poles
        from v2 import cubesphere
        for f, (la, lo) in enumerate(((0, 0), (0, 90), (0, 180), (0, -90), (90, 0), (-90, 0))):
            ref = float(self.st._query_blended(np.array([la]), np.array([lo]), levels=[0])['height'][0])
            self.assertAlmostEqual(h[f, 1, 1], ref, places=3)


if __name__ == '__main__':
    unittest.main()
