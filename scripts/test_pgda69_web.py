#!/usr/bin/env python3
"""The web copy of NASA PGDA 69 (web/public/pgda69-spot, built by scripts/build_pgda69_web.py) equals the original TIFs.

Needs the two NASA TIFs (kept out of git; default tmp/pgda69, or PGDA69_SRC) and rasterio, pyproj, numpy:
  tmp/pgda69-venv/bin/python -m unittest scripts/test_pgda69_web.py -v
Without the TIFs every test is skipped with a message saying so; that is not a pass.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import random
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(os.environ.get('PGDA69_SRC', ROOT / 'tmp' / 'pgda69'))
OUT = ROOT / 'web' / 'public' / 'pgda69-spot'
SUN_TIF = SRC / 'AVGVISIB_85S_060M_201608.TIF'
EARTH_TIF = SRC / 'AVGVISIB_85S_060M_201608_EARTH.TIF'

try:
    import numpy as np
    import rasterio
    from pyproj import Transformer

    HAVE = SUN_TIF.exists() and EARTH_TIF.exists()
    WHY = f'NASA TIFs not found in {SRC}'
except ImportError as err:  # pragma: no cover
    HAVE = False
    WHY = f'missing Python package: {err}'

# The plan's "PGDA 69 checked (18 Nov)" table, to one decimal: site id -> (Sun %, Sun 3x3 low, high, Earth %, low, high).
# Written here on purpose: this is the acceptance table the web copy must reproduce.
PLAN_TABLE = {
    'site01_roi6': (88.4, 39.8, 88.4, 58.1, 50.4, 58.1),
    'site04_roi3': (85.2, 6.3, 85.2, 55.0, 29.3, 55.0),
    'site04_roi4': (85.5, 43.2, 85.5, 56.7, 42.3, 56.7),
}


@unittest.skipUnless(HAVE, WHY if not HAVE else '')
class WebCopyEqualsTifs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = json.loads((OUT / 'manifest.json').read_text())
        with rasterio.open(SUN_TIF) as s, rasterio.open(EARTH_TIF) as e:
            cls.sun = s.read(1)
            cls.earth = e.read(1)
            cls.crs = s.crs
            cls.transform = s.transform
        c = cls.m['copy']
        t = c['tilePx']
        cls.web_sun = np.empty((c['heightPx'], c['widthPx']), dtype='<i2')
        cls.web_earth = np.empty_like(cls.web_sun)
        for tile in cls.m['tiles']:
            blob = (OUT / tile['file']).read_bytes()
            assert hashlib.sha256(blob).hexdigest() == tile['sha256'], tile['file']
            raw = np.frombuffer(gzip.decompress(blob), dtype=np.uint8)
            assert raw.size == 4 * t * t, tile['file']
            sl = (slice(tile['r'] * t, (tile['r'] + 1) * t), slice(tile['c'] * t, (tile['c'] + 1) * t))
            cls.web_sun[sl] = cls.unpack(raw[: 2 * t * t], t)
            cls.web_earth[sl] = cls.unpack(raw[2 * t * t :], t)

    @staticmethod
    def unpack(layer, t):
        """Undo the tile encoding (manifest copy.tileLayout): low bytes then high bytes of row-wise differences."""
        n = t * t
        d = (layer[:n].astype(np.uint16) | (layer[n:].astype(np.uint16) << 8)).reshape(t, t)
        return np.cumsum(d, axis=1, dtype=np.uint16).astype('<u2').view('<i2')

    def test_sources_are_the_pinned_files(self):
        for src, path in zip(self.m['sources'], (SUN_TIF, EARTH_TIF)):
            self.assertEqual(src['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_grid_matches_the_tif(self):
        g = self.m['grid']
        t = self.transform
        self.assertEqual((g['cellM'], g['fullX0M'], g['fullY0M']), (t.a, t.c, t.f))
        self.assertEqual((g['fullHeightPx'], g['fullWidthPx']), self.sun.shape)
        self.assertEqual(self.sun.dtype, np.int16)

    def test_every_shipped_cell_equals_the_tif(self):
        c = self.m['copy']
        r0, c0, h, w = c['row0'], c['col0'], c['heightPx'], c['widthPx']
        self.assertEqual(len(self.m['tiles']), (h // c['tilePx']) * (w // c['tilePx']))
        self.assertTrue(np.array_equal(self.web_sun, self.sun[r0 : r0 + h, c0 : c0 + w]))
        self.assertTrue(np.array_equal(self.web_earth, self.earth[r0 : r0 + h, c0 : c0 + w]))

    def test_random_lat_lon_points_through_pyproj(self):
        """20 000 points placed by latitude and longitude, projected with pyproj and indexed with rasterio."""
        c = self.m['copy']
        to_xy = Transformer.from_crs(self.crs.geodetic_crs, self.crs, always_xy=True)
        rng = random.Random(1806)
        n = 0
        with rasterio.open(SUN_TIF) as ds:
            while n < 20000:
                lat = rng.uniform(-90, c['inscribedLatDeg'])
                lon = rng.uniform(-180, 180)
                x, y = to_xy.transform(lon, lat)
                row, col = ds.index(x, y)
                wr, wc = row - c['row0'], col - c['col0']
                self.assertTrue(0 <= wr < c['heightPx'] and 0 <= wc < c['widthPx'], (lat, lon))
                self.assertEqual(int(self.web_sun[wr, wc]), int(self.sun[row, col]))
                self.assertEqual(int(self.web_earth[wr, wc]), int(self.earth[row, col]))
                n += 1

    def test_manifest_check_points_equal_the_tif(self):
        for k in self.m['checks']:
            self.assertEqual(k['sunRaw'], int(self.sun[k['row'], k['col']]), k['name'])
            self.assertEqual(k['earthRaw'], int(self.earth[k['row'], k['col']]), k['name'])

    def test_the_three_sites_match_the_plan_table(self):
        scale = self.m['grid']['scale']
        pct = lambda raw: round(raw * scale * 100, 1)
        c = self.m['copy']
        seen = set()
        for k in self.m['checks']:
            want = PLAN_TABLE.get(k.get('siteId'))
            if not want:
                continue
            seen.add(k['siteId'])
            wr, wc = k['row'] - c['row0'], k['col'] - c['col0']
            sun9 = self.web_sun[wr - 1 : wr + 2, wc - 1 : wc + 2]
            earth9 = self.web_earth[wr - 1 : wr + 2, wc - 1 : wc + 2]
            got = (pct(int(self.web_sun[wr, wc])), pct(int(sun9.min())), pct(int(sun9.max())), pct(int(self.web_earth[wr, wc])), pct(int(earth9.min())), pct(int(earth9.max())))
            self.assertEqual(got, want, k['siteId'])
        self.assertEqual(seen, set(PLAN_TABLE))

    def test_orientation_site01_roi6_is_the_brightest_sun_cell(self):
        k = next(x for x in self.m['checks'] if x.get('siteId') == 'site01_roi6')
        self.assertEqual(np.unravel_index(int(self.sun.argmax()), self.sun.shape), (k['row'], k['col']))
        self.assertEqual(int((self.sun == self.sun.max()).sum()), 1)

    def test_copy_edge_latitude(self):
        c, g = self.m['copy'], self.m['grid']
        self.assertAlmostEqual(c['inscribedLatDeg'], -90 + math.degrees(2 * math.atan(c['halfWidthM'] / (2 * g['radiusM']))), places=12)


if __name__ == '__main__':
    unittest.main()
