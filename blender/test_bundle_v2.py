"""Tests for blender/bundle_v2.py (no bpy). Run:
    python3 -m unittest discover -s blender -p 'test_*.py' -v
"""
import json
import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import bundle_v2 as bv  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, 'web', 'public', 'bundles', 'demo-fixture.json')
SITE01 = os.path.join(ROOT, 'app', 'data', 'polaris-source-site01-2026-11-14-v2.json')


def mini(lon=-137.49, status='SOURCE_BASED_UNVALIDATED', kind='nasa'):
    return {
        'format': 'POLARIS-X5D-v2', 'schemaVersion': '2.0.0', 'validation': {'status': status, 'gates': []},
        'datasets': [{
            'siteId': 's', 'site': {'longitudeEastDeg': lon},
            'dem': {'kind': kind, 'n': 4, 'spacing': 10.0, 'originX': -15.0, 'originY': -15.0, 'values': [0.0] * 16,
                    'rowOrder': 'south-to-north after explicit source flip', 'verticalUnits': 'meters'},
            'ephemeris': {'samples': [{'time': 't0'}, {'time': 't1'}, {'time': 't2'}, {'time': 't3'}, {'time': 't4'}]},
            'validation': {'status': status, 'gates': []},
        }],
    }


class FrameTests(unittest.TestCase):
    def test_az90_is_local_east_not_grid_east(self):
        d = mini()['datasets'][0]
        north, east, src = bv.basis(d)
        self.assertEqual(src, 'derived-from-longitude')
        v = bv.grid_direction(d, 90, 0)
        self.assertAlmostEqual(v[0], east[0], 12)
        self.assertAlmostEqual(v[1], east[1], 12)
        self.assertGreater(abs(v[0] - 1.0), 0.5)  # naive (sin az, cos az) would give (1, 0)

    def test_local_north_is_radial_at_site01(self):
        north, _, _ = bv.basis(mini()['datasets'][0])
        r = math.hypot(-10999.14, -11999.26)
        self.assertAlmostEqual(north[0], -10999.14 / r, 3)
        self.assertAlmostEqual(north[1], -11999.26 / r, 3)

    def test_elevation_and_unit_length(self):
        v = bv.grid_direction(mini(lon=0)['datasets'][0], 0, 30)
        self.assertAlmostEqual(v[2], 0.5, 12)
        self.assertAlmostEqual(math.hypot(*v), 1.0, 12)

    def test_bundle_declared_frame_wins(self):
        d = mini()['datasets'][0]
        d['derived'] = {'frame': {'localNorthInGrid': [0, 1], 'localEastInGrid': [1, 0]}}
        self.assertEqual(bv.basis(d)[2], 'bundle')
        v = bv.grid_direction(d, 90, 0)
        self.assertAlmostEqual(v[0], 1.0, 12)


class BundleTests(unittest.TestCase):
    def _write(self, obj):
        f = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
        json.dump(obj, f)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_refuses_v1(self):
        b = mini()
        b['format'] = 'POLARIS-X5D-v1'
        with self.assertRaises(bv.BundleError):
            bv.load(self._write(b))

    def test_sha256_is_of_the_bytes(self):
        p = self._write(mini())
        _, sha, n = bv.load(p)
        self.assertEqual(sha, bv.file_sha256(p))
        self.assertEqual(n, os.path.getsize(p))

    def test_status_is_most_cautious(self):
        self.assertEqual(bv.display_status(mini()), 'SOURCE-BASED UNVALIDATED')
        self.assertEqual(bv.display_status(mini(kind='demo', status='VALIDATED_NASA_JPL')), 'DEMO')
        self.assertEqual(bv.display_status(mini(status='VALIDATED_NASA_JPL')), 'VALIDATED')

    def test_key_samples_and_dem_checks(self):
        d = mini()['datasets'][0]
        self.assertEqual(bv.key_samples(d), {'start': 0, 'mid': 2, 'end': 4})
        bv.check_dem(d['dem'])
        d['dem']['values'].pop()
        with self.assertRaises(bv.BundleError):
            bv.check_dem(d['dem'])

    def test_png_pixel_hash_ignores_added_metadata_chunks(self):
        import struct
        import zlib

        def chunk(t, d):
            return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xFFFFFFFF)
        ihdr = struct.pack('>IIBBBBB', 2, 1, 8, 2, 0, 0, 0)
        idat = zlib.compress(b'\x00\xff\x00\x00\x00\x00\xff')
        a = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', idat) + chunk(b'IEND', b'')
        b = a[:33] + chunk(b'caBX', b'c2pa-like metadata') + a[33:]
        pa, pb = self._write_bytes(a), self._write_bytes(b)
        self.assertNotEqual(bv.file_sha256(pa), bv.file_sha256(pb))
        self.assertEqual(bv.png_pixel_sha256(pa), bv.png_pixel_sha256(pb))

    def _write_bytes(self, data):
        f = tempfile.NamedTemporaryFile('wb', suffix='.png', delete=False)
        f.write(data)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_no_derived_means_not_evaluated(self):
        self.assertEqual(bv.ray_state(None, 'sun', 0), ('not evaluated', None))

    @unittest.skipUnless(os.path.exists(DEMO), 'DEMO fixture not present')
    def test_demo_fixture_rays_come_from_bundle(self):
        b, _, _ = bv.load(DEMO)
        d = bv.dataset(b)
        sc = bv.scenario(d)
        self.assertEqual(bv.display_status(b), 'DEMO')
        k = 0
        state, hit = bv.ray_state(sc, 'sun', k)
        self.assertEqual(state, 'blocked' if not sc['samples']['sun']['visible'][k] else 'clear')
        if state == 'blocked':
            self.assertEqual(hit, sc['samples']['sun']['firstHitM'][k])

    @unittest.skipUnless(os.path.exists(SITE01), 'Site01 source bundle not present')
    def test_site01_source_bundle_reads(self):
        b, sha, _ = bv.load(SITE01)
        d = bv.dataset(b, 'connecting')
        bv.check_dem(d['dem'])
        self.assertEqual(bv.display_status(b), 'SOURCE-BASED UNVALIDATED')
        self.assertIsNone(bv.scenario(d))
        self.assertEqual(len(sha), 64)


if __name__ == '__main__':
    unittest.main()
