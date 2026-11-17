"""Regression (T3): the per-product adapter (`LegacyStack`) must read SLDEM2015 512 ppd, which comes as 32 PDS tiles of
30 deg x 45 deg (60 S - 60 N). Before the fix `_point` / `_read_eq` indexed rows as (90 - lat) * ppd (row 0 at +90 deg),
so every tile row fell outside the tile and `covering()` never listed SLDEM2015 (R1, docs/v2/PHASE_1_R1_PLAN.md).

Independent reference: the raw .img read with numpy (float32 LE, km), indexed with the PDS3 label's own
LINE_PROJECTION_OFFSET / SAMPLE_PROJECTION_OFFSET / CENTER_LONGITUDE (simple cylindrical:
line = LPO - lat * ppd + 1, sample = SPO + ppd (lon - lon_c) + 1, 1-based pixel centres), not with the adapter's code.
"""
import math
import re
import unittest
from pathlib import Path

import numpy as np

from science import frames
from science.anysite.stack import LegacyStack, _to_zone

ROOT = Path(__file__).resolve().parents[3]
TILES = ROOT / 'data' / 'cache' / 'v2' / 'products' / 'sldem2015_512' / 'data' / 'sldem2015' / 'tiles' / 'float_img'


def _label(p):
    t = p.read_text(errors='replace')
    g = lambda k: float(re.search(rf'^\s*{k}\s*=\s*(-?[\d.]+)', t, re.M).group(1))
    return {k: g(k) for k in ('LINE_PROJECTION_OFFSET', 'SAMPLE_PROJECTION_OFFSET', 'CENTER_LONGITUDE', 'MAP_RESOLUTION',
                              'MAXIMUM_LATITUDE', 'MINIMUM_LATITUDE', 'WESTERNMOST_LONGITUDE', 'EASTERNMOST_LONGITUDE',
                              'LINES', 'LINE_SAMPLES')}


_LABELS = {}


def raw_height_m(lat, lon):
    """Height (m) of the pixel holding (lat, lon), from the tile whose label bounds contain it."""
    if not _LABELS:
        for p in sorted(TILES.glob('*_float.lbl')):
            _LABELS[p] = _label(p)
    lon = lon % 360.0
    for p, L in _LABELS.items():
        if L['MINIMUM_LATITUDE'] <= lat < L['MAXIMUM_LATITUDE'] and L['WESTERNMOST_LONGITUDE'] <= lon < L['EASTERNMOST_LONGITUDE']:
            ppd = L['MAP_RESOLUTION']
            line = L['LINE_PROJECTION_OFFSET'] - lat * ppd + 1.0
            samp = L['SAMPLE_PROJECTION_OFFSET'] + ppd * (lon - L['CENTER_LONGITUDE']) + 1.0
            r = int(math.floor(line - 0.5)); c = int(math.floor(samp - 0.5))
            a = np.memmap(p.with_suffix('.img'), dtype='<f4', mode='r', shape=(int(L['LINES']), int(L['LINE_SAMPLES'])))
            return float(a[r, c]) * 1000.0
    return float('nan')


def _have():
    return TILES.exists() and len(list(TILES.glob('*_float.img'))) == 32


@unittest.skipUnless(_have(), 'SLDEM2015 512 ppd tiles (32) not downloaded')
class SldemTiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.st = LegacyStack()
        cls.e = next(e for e in cls.st.entries if e['product'] == 'sldem2015')

    def test_one_mosaic_entry(self):
        e = self.e
        self.assertEqual(e['id'], 'sldem2015:sldem2015_512')
        self.assertEqual(len(e['tiles']), 32)
        self.assertEqual((e['lat_top'], e['lat_bot'], e['lon_left'], e['width'], e['height']), (60.0, -60.0, 0.0, 184320, 61440))
        self.assertEqual(sum(1 for x in self.st.entries if x['product'] == 'sldem2015'), 1)

    def test_covering_lists_sldem_first_at_eq_sites(self):
        for lat, lon in [(0.67416, 23.47314), (44.1214, -19.5117), (-30.0001, 135.0), (59.999, 0.0), (-59.999, 359.999),
                         (26.1322, 3.6339), (-8.97, -15.5)]:
            cov = self.st.covering(lat, lon)
            self.assertTrue(cov and cov[0]['id'] == 'sldem2015:sldem2015_512', (lat, lon, [c['id'] for c in cov]))
        self.assertNotIn('sldem2015:sldem2015_512', [c['id'] for c in self.st.covering(61.0, 10.0)])
        self.assertNotIn('sldem2015:sldem2015_512', [c['id'] for c in self.st.covering(-89.78, -156.3)])

    def test_point_equals_raw_label_indexing(self):
        rng = np.random.default_rng(42)
        pts = list(zip(rng.uniform(-59.99, 59.99, 40), rng.uniform(-180, 180, 40)))
        pts += [(30.0005, 44.9995), (29.9995, 45.0005), (-0.0005, 0.0005), (0.0005, 359.9995), (-29.9995, 180.0005)]
        for lat, lon in pts:
            x, y = _to_zone(lat, lon, self.e)
            v = LegacyStack._point(self.e, float(x), float(y))
            self.assertAlmostEqual(v, raw_height_m(lat, lon), delta=1e-3, msg=(lat, lon))

    def test_window_across_tile_corner_equals_raw(self):
        # 30 N, 45 E is the corner of four tiles; the window must paste them without a seam or offset
        d = self.st.window(30.0, 45.0, 8000.0, product=self.e['id'])
        self.assertEqual(len(d.meta['tiles']), 4)
        self.assertEqual(len({t['file_sha256'] for t in d.meta['tiles']}), 4)
        ppd = 512.0
        for dr in (-3, -1, 0, 1, 2):
            for dc in (-3, -1, 0, 1, 2):
                la = 30.0 - (dr + 0.5) / ppd; lo = 45.0 + (dc + 0.5) / ppd          # pixel centres around the corner
                h = float(d.sample(*frames.stereo_forward(la, lo)))
                self.assertAlmostEqual(h, raw_height_m(la, lo), delta=1e-3, msg=(dr, dc))
        self.assertTrue(np.isfinite(d.Z).all())

    def test_window_crossing_seam_and_eq(self):
        d = self.st.window(0.0, 0.0, 6000.0, product=self.e['id'])
        self.assertEqual(len(d.meta['tiles']), 4)                                   # 0/360 seam x equator
        for la, lo in [(0.01, -0.01), (-0.01, 0.01), (0.03, 0.04), (-0.04, -0.03)]:
            c_la = math.floor(la * 512) / 512 + 0.5 / 512 if la >= 0 else -(math.floor(-la * 512) / 512 + 0.5 / 512)
            c_lo = (math.floor((lo % 360) * 512) + 0.5) / 512
            self.assertAlmostEqual(float(d.sample(*frames.stereo_forward(c_la, c_lo))), raw_height_m(c_la, c_lo),
                                   delta=1e-3, msg=(la, lo))


if __name__ == '__main__':
    unittest.main()
