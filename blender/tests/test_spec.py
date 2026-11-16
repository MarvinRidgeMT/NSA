import json
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v2 import astro, spec as S  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
B = ROOT / 'data' / 'bundles' / 'site01_roi6_2026-11-14_14d_mast1m.json'


@unittest.skipUnless(B.exists(), 'bundle not present')
class Spec(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = json.loads(B.read_text())
        cls.sp = S.build_spec(-89.47409, -137.3813, '2026-11-18T04:00Z', camera='eva_eye', bundle=str(B))

    def test_numbers_come_from_the_bundle_sample(self):
        s = self.b['samples'][100]
        self.assertEqual(self.sp['sample']['index'], 100)
        self.assertEqual(self.sp['sun']['azDeg'], s['sun']['az_deg'])
        self.assertEqual(self.sp['sun']['elDeg'], s['sun']['el_deg'])
        self.assertEqual(self.sp['sun']['radiusDeg'], s['sun']['radius_deg'])
        self.assertEqual(self.sp['earth']['radiusDeg'], s['earth']['radius_deg'])
        self.assertAlmostEqual(self.sp['sun']['discAngleDeg'], 2 * s['sun']['radius_deg'])
        self.assertAlmostEqual(self.sp['sun']['irradianceWm2'], 1361 / s['sun']['range_au'] ** 2)

    def test_sight_line_state_is_the_bundles(self):
        s = self.b['samples'][100]
        self.assertEqual(self.sp['sightLines']['sun']['state'], 'clear' if s['sun']['center_visible'] else 'blocked')
        self.assertEqual(self.sp['sightLines']['earth']['state'], 'clear' if s['earth']['center_visible'] else 'blocked')

    def test_blocked_ray_ends_at_critical_point(self):
        b = self.b
        k = next(i for i, s in enumerate(b['samples']) if not s['earth']['center_visible'])
        sp = S.build_spec(-89.47409, -137.3813, b['samples'][k]['utc'], bundle=str(B))
        sl = sp['sightLines']['earth']
        self.assertEqual(sl['state'], 'blocked')
        kb, _, dist = S.skyline_bin(b, sp['earth']['azDeg'])
        self.assertAlmostEqual(sl['lengthM'], dist / math.cos(math.radians(sp['earth']['elDeg'])))

    def test_bundle_found_by_lat_lon(self):
        f, d = S.find_bundle(-89.47409, -137.3813)
        self.assertIn('site01_roi6', f)
        self.assertLess(d, 1.0)
        f10, _ = S.find_bundle(-89.47409, -137.3813, mast=10.0)
        self.assertIn('mast10m', f10)

    def test_unknown_point_is_refused(self):
        with self.assertRaises(S.SpecError):
            S.find_bundle(-80.0, 10.0)

    def test_outside_samples_is_refused(self):
        with self.assertRaises(astro.SampleError):
            S.build_spec(-89.47409, -137.3813, '2026-12-01T00:00Z', bundle=str(B))

    def test_orbital_pose(self):
        sp = S.build_spec(-89.47409, -137.3813, '2026-11-14T00:00Z', camera='lroc_nac', bundle=str(B), emission_deg=20, look_az=90)
        pose = sp['camera']['pose']
        self.assertAlmostEqual(pose['posEnu'][2], 50_000.0)
        self.assertAlmostEqual(math.hypot(*pose['posEnu'][:2]), 50_000.0 * math.tan(math.radians(20)), places=6)
        self.assertLess(pose['posEnu'][0], 0)            # looking east -> spacecraft to the west
        self.assertFalse(sp['overlays'])

    def test_dominant_light_switches_to_earth_when_the_sun_is_down(self):
        sp = dict(self.sp)
        self.assertEqual(sp['dominantLight'], 'sun')

    def test_json_serialisable(self):
        json.dumps(self.sp)


class Layouts(unittest.TestCase):
    def test_layouts_mirror_science(self):
        try:
            sys.path.insert(0, str(ROOT))
            from science.cube.build_assets import LAYOUTS
        except Exception as e:  # pragma: no cover - environment without the science deps
            raise unittest.SkipTest(f'science.cube.build_assets not importable here ({type(e).__name__})')
        norm = lambda d: json.loads(json.dumps(d))
        self.assertEqual(norm(S.ASSET_LAYOUTS), norm(LAYOUTS))

    def test_grid_offset_rotation(self):
        # at L = 0 grid north (+y) is local north; at L = 90 grid +y is local west
        e, n = S.grid_offset_to_enu(0, 10, 0.0)
        self.assertAlmostEqual(e, 0.0)
        self.assertAlmostEqual(n, 10.0)
        e, n = S.grid_offset_to_enu(0, 10, 90.0)
        self.assertAlmostEqual(e, -10.0)
        self.assertAlmostEqual(n, 0.0, places=12)


if __name__ == '__main__':
    unittest.main()
