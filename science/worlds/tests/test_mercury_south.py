"""PGDA 88 south-polar DEM conventions (T3) and the south-polar site bundle."""
import json
import os
import unittest

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
P88 = os.path.join(ROOT, 'data', 'cache', 'v2', 'products', 'mercury_pgda88_south_pole')
BUNDLE = os.path.join(ROOT, 'data', 'worlds', 'mercury', 'mercury_south_pole_high_2026-11-14_176d_mast1m.json')


@unittest.skipUnless(os.path.exists(os.path.join(P88, 'HDEM_75S250M_ref2439p4km.tif')), 'PGDA 88 not downloaded')
class Pgda88(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from science.worlds.mercury import terrain as T
        cls.near, _ = T.pgda88_layer(); cls.us, _ = T.usgs_layer(-85.0, 600e3)
        rng = np.random.default_rng(1)
        cls.la = rng.uniform(-89.5, -76, 20000); cls.lo = rng.uniform(-180, 180, 20000)
        cls.a = cls.near.dem.sample(*cls.near.forward(cls.la, cls.lo))
        cls.b = cls.us.dem.sample(*cls.us.forward(cls.la, cls.lo))

    def test_orientation_vs_usgs(self):
        ok = np.isfinite(self.a) & np.isfinite(self.b)
        r = np.corrcoef(self.a[ok], self.b[ok])[0, 1]
        x, y = self.near.forward(self.la, self.lo)
        for fx, fy in ((1, -1), (-1, 1)):                    # mirrored grids (the file history records a FLIPUD)
            af = self.near.dem.sample(fx * x, fy * y); o2 = np.isfinite(af) & np.isfinite(self.b)
            self.assertGreater(r, 4 * np.corrcoef(af[o2], self.b[o2])[0, 1])
        self.assertGreater(r, 0.6)

    def test_datum_vs_published_difference_layer(self):
        import rasterio
        with rasterio.open(os.path.join(P88, 'HDEM_75S250M_minus_USGS.tif')) as ds:
            t = ds.transform; v = ds.read(1)
        x, y = self.near.forward(self.la, self.lo)
        pub = v[((t.f - y) / t.a).astype(int), ((x - t.c) / t.a).astype(int)]
        ok = np.isfinite(pub) & np.isfinite(self.a) & np.isfinite(self.b)
        self.assertLess(abs(float(np.median((self.a - self.b)[ok] - pub[ok]))), 5.0)   # a wrong datum would be >= 600 m


@unittest.skipUnless(os.path.exists(BUNDLE), 'south-polar bundle not built')
class SouthBundle(unittest.TestCase):
    def test_bundle(self):
        b = json.load(open(BUNDLE))
        self.assertEqual(b['schema'], 'polaris-science-results-v1')
        self.assertLessEqual(b['site']['lat_deg'], -88.0)
        self.assertEqual(b['skyline']['n_truncated'], 0)
        self.assertEqual(b['skyline']['curvature_limit']['n_range_limited_world'], 0)
        self.assertEqual(b['time']['n_samples'], 176 * 24 + 1)
        m = b['metrics']
        self.assertGreaterEqual(m['sun_center_visible_pct'], b['world']['flat_horizon_control']['sun_center_visible_pct'] - 1e-9)
        self.assertEqual(b['world']['sections']['cube']['status'], 'not available for this world')
        self.assertIn(b['world']['ice']['value_at_site'], (0, 1))


if __name__ == '__main__':
    unittest.main()
