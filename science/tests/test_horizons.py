"""T3 tests: Horizons parsing by header column names, raw archive integrity,
bisection crossings and visible-disk fraction."""
import hashlib
import json
import math
import unittest
from pathlib import Path

from science import horizons
from science.crossings import bisect_crossing, disk_fraction_visible

ROOT = Path(__file__).resolve().parents[2]

# Minimal hand-made CSV in Horizons layout. TEST FIXTURE ONLY, not ephemeris data.
_FAKE = """header junk
 Date__(UT)__HR:MN:SC.fff, , ,{c1}, {c2},  Ang-diam,             delta,     deldot,
***
$$SOE
 2026-Nov-14 00:00:00.000,*, ,  {a},       {b},  1942.009,  0.98787542930163,  0.2967345,
$$EOE
"""


class ParseByHeader(unittest.TestCase):
    def test_columns_found_by_name_not_position(self):
        t1 = _FAKE.format(c1='Azimuth_(a-app)', c2='Elevation_(a-app)', a='264.1', b='1.5')
        t2 = _FAKE.format(c1='Elevation_(a-app)', c2='Azimuth_(a-app)', a='1.5', b='264.1')
        for t in (t1, t2):
            rows = horizons.parse_text(t)
            self.assertEqual(len(rows), 1)
            self.assertAlmostEqual(rows[0]['az_deg'], 264.1)
            self.assertAlmostEqual(rows[0]['el_deg'], 1.5)
            self.assertAlmostEqual(rows[0]['ang_diam_arcsec'], 1942.009)
            self.assertEqual(rows[0]['utc'], '2026-11-14T00:00:00.000Z')

    def test_missing_required_column_raises(self):
        t = _FAKE.format(c1='Foo', c2='Elevation_(a-app)', a='1', b='2')
        with self.assertRaises(ValueError):
            horizons.parse_text(t)

    def test_site_coord_uses_east_lon_and_km(self):
        p = horizons.build_params('10', -89.4632, -137.49, 1943.32, start='2026-11-14 00:00',
                                  stop='2026-11-28 00:00', step='1 h')
        self.assertEqual(p['SITE_COORD'], "'222.5100000,-89.4632000,1.943320'")
        self.assertEqual(p['CENTER'], "'coord@301'")
        self.assertEqual(p['APPARENT'], 'AIRLESS')


class ArchivedRaw(unittest.TestCase):
    def test_archived_files_match_manifest_hashes(self):
        man = ROOT / 'data' / 'raw' / 'horizons' / 'MANIFEST.json'
        if not man.exists():
            self.skipTest('no Horizons archive yet')
        entries = json.loads(man.read_text())
        self.assertGreater(len(entries), 0)
        for e in entries:
            b = (ROOT / e['path']).read_bytes()
            self.assertEqual(hashlib.sha256(b).hexdigest(), e['sha256'], e['path'])


class Crossings(unittest.TestCase):
    def test_bisection_finds_root(self):
        f = lambda ts: [t - 1234.5678 for t in ts]
        t, it = bisect_crossing(f, 0.0, 3600.0, tol_s=0.5)
        self.assertLess(abs(t - 1234.5678), 0.5)

    def test_disk_fraction(self):
        r = 0.2666
        self.assertAlmostEqual(disk_fraction_visible(0.0, r), 0.5, places=12)
        self.assertEqual(disk_fraction_visible(r, r), 1.0)
        self.assertEqual(disk_fraction_visible(-r, r), 0.0)
        # monotone
        vals = [disk_fraction_visible(m, r) for m in [-0.2, -0.1, 0, 0.1, 0.2]]
        self.assertEqual(vals, sorted(vals))
        # slope reduces perpendicular distance
        self.assertLess(disk_fraction_visible(0.1, r, horizon_slope=1.0), disk_fraction_visible(0.1, r))


if __name__ == '__main__':
    unittest.main()
