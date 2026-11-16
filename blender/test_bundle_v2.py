"""Tests for blender/bundle_v2.py (no bpy). Run:
    python3 -m unittest discover -s blender -p 'test_*.py' -v
"""
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

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


ROI = os.path.join(ROOT, 'data', 'viewer', 'polaris-x5d-roi-2026-11-14-v2.json')
CTX = os.path.join(ROOT, 'data', 'visual', 'terrain_context')


class RoiHeroScene(unittest.TestCase):
    """What the Blender hero build (ROI export, Site04 ROI3) will be given: a 5 m crop and DERIVED ray states."""

    @unittest.skipUnless(os.path.exists(ROI), 'ROI export not present')
    def test_roi_export_has_a_5m_crop_and_evaluated_ray_states(self):
        b, _sha, _ = bv.load(ROI)
        d = bv.dataset(b, 'site04_roi3')
        bv.check_dem(d['dem'])
        self.assertEqual((d['dem']['n'], d['dem']['spacing']), (401, 5.0))
        sc = bv.scenario(d)
        self.assertIsNotNone(sc, 'derived outputs must be present so rays are not drawn as NOT EVALUATED')
        keys = bv.key_samples(d)
        states = {t: [bv.ray_state(sc, t, k)[0] for k in keys.values()] for t in ('sun', 'earth')}
        for t, st in states.items():
            self.assertTrue(all(x in ('clear', 'blocked', 'transition') for x in st), (t, st))
        obs = bv.observer(d, sc)
        self.assertEqual(obs['source'], 'bundle scenario')

    def _pack(self, crop_sha='abc', status='VISUAL', authority=False):
        import hashlib, struct
        d = tempfile.mkdtemp(prefix='polaris_ctx_')
        n = 5
        vals = [float(100 + i) for i in range(n * n)]
        raw = struct.pack('<%df' % (n * n), *vals)
        with open(os.path.join(d, 'regional_f32.bin'), 'wb') as f:
            f.write(raw)
        meta = {'schema': 'polaris-terrain-context-v1', 'status': status, 'numericalAuthority': authority,
                'local': {'cropValuesSha256': crop_sha},
                'regional': {'file': 'regional_f32.bin', 'sha256': hashlib.sha256(raw).hexdigest(), 'n': n, 'spacingM': 80.0,
                             'originX': -160.0, 'originY': -160.0, 'product': 'fixture', 'source': 'fixture'}}
        with open(os.path.join(d, 'context.json'), 'w') as f:
            json.dump(meta, f)
        return d, vals

    def test_context_pack_is_placed_unchanged_except_the_visual_cut_under_the_local_crop(self):
        d, vals = self._pack()
        local = {'n': 81, 'spacing': 5.0, 'originX': -200.0, 'originY': -200.0, 'cropValuesSha256': 'abc'}   # +-200 m footprint
        dem, info = bv.context_regional_dem(d, local)
        self.assertEqual((dem['n'], dem['spacing'], dem['originX'], dem['originY']), (5, 80.0, -160.0, -160.0))
        centre = 2 * 5 + 2                                   # node at (0, 0): inside the footprint inset by one 80 m cell
        self.assertAlmostEqual(dem['values'][centre], vals[centre] - bv.CONTEXT_CUT_DROP_M, places=4)
        untouched = [k for k in range(25) if abs(dem['values'][k] - vals[k]) < 1e-4]
        self.assertEqual(len(untouched), 25 - info['nodesLoweredInsideLocalFootprint'])
        self.assertEqual(info['nodesLoweredInsideLocalFootprint'], 9)     # nodes at -80, 0, +80 m in x and y
        self.assertIs(info['numericalAuthority'], False)

    def test_context_pack_is_refused_for_another_crop_or_if_not_visual(self):
        local = {'n': 81, 'spacing': 5.0, 'originX': -200.0, 'originY': -200.0, 'cropValuesSha256': 'abc'}
        d, _ = self._pack(crop_sha='different')
        self.assertIsNone(bv.context_regional_dem(d, local)[0])
        d, _ = self._pack(authority=True)
        self.assertIsNone(bv.context_regional_dem(d, local)[0])
        self.assertIsNone(bv.context_regional_dem(tempfile.mkdtemp(), local)[0])

    @unittest.skipUnless(os.path.exists(ROI) and os.path.exists(os.path.join(CTX, 'site04_roi3', 'context.json')), 'ROI export or context pack not present')
    def test_real_pack_matches_the_roi_crop(self):
        b, _sha, _ = bv.load(ROI)
        d = bv.dataset(b, 'site04_roi3')
        dem, info = bv.context_regional_dem(os.path.join(CTX, 'site04_roi3'), d['dem'])
        self.assertIsNotNone(dem, info)
        self.assertEqual((dem['n'], dem['spacing']), (401, 80.0))
        self.assertTrue(all(math.isfinite(v) for v in dem['values']))
        self.assertGreater(info['nodesLoweredInsideLocalFootprint'], 400)


class GlbAndTransition(unittest.TestCase):
    HERO = os.path.join(ROOT, 'blender', 'output', 'POLARIS_X_site04_roi3_bundlev2.glb')

    @unittest.skipUnless(os.path.exists(os.path.join(ROOT, 'blender', 'output', 'POLARIS_X_site04_roi3_bundlev2.glb')), 'hero GLB not built')
    def test_hero_glb_reads_back_in_metres_with_terrain_and_context(self):
        import glb_check
        g = glb_check.inspect_glb(self.HERO)
        names = [n['name'] for n in g['nodes']]
        self.assertTrue(any('DEM' in (n or '') for n in names), names)
        self.assertTrue(any('CONTEXT' in (n or '') for n in names), names)
        terrain = next(n for n in g['nodes'] if 'DEM' in (n['name'] or ''))
        self.assertEqual(terrain['vertices'], 401 * 401)
        lo, hi = g['boundsGltfM']['min'], g['boundsGltfM']['max']
        # context crop is 401 x 80 m around the site: about +-16 km in glTF x and z (= grid east, -grid north)
        self.assertGreater(hi[0] - lo[0], 30000)
        self.assertLess(hi[0] - lo[0], 34000)
        self.assertGreater(hi[2] - lo[2], 30000)

    def test_transition_sample_is_the_first_flag_change(self):
        sc = {'samples': {'sun': {'visible': [True, True, False, False, True]}, 'earth': {'visible': [False] * 5}}}
        self.assertEqual(bv.transition_sample(sc, 'sun'), 2)
        self.assertIsNone(bv.transition_sample(sc, 'earth'))
        self.assertIsNone(bv.transition_sample(None, 'sun'))
        d = {'ephemeris': {'samples': [{}] * 5}}
        k = bv.key_samples_with_transition(d, sc)
        self.assertEqual((k['transition'], k['transitionTarget']), (2, 'sun'))

    @unittest.skipUnless(os.path.exists(ROI), 'ROI export not present')
    def test_site04_roi3_has_a_sun_transition_in_the_window(self):
        b, _sha, _ = bv.load(ROI)
        d = bv.dataset(b, 'site04_roi3')
        k = bv.key_samples_with_transition(d, bv.scenario(d))
        self.assertIn('transition', k)
        self.assertEqual(k['transitionTarget'], 'sun')


if __name__ == '__main__':
    unittest.main()


class DisplaySurface(unittest.TestCase):
    """SfS display surface and L1 ring from the context packs (display only)."""
    ROI = os.path.join(ROOT, 'data', 'viewer', 'polaris-x5d-roi-2026-11-14-v2.json')

    def _ds(self, site):
        b, _, _ = bv.load(self.ROI)
        return bv.dataset(b, site)

    def test_site01_display_surface_reads_and_meets_the_bundle_ground(self):
        pack = Path(ROOT, 'data', 'visual', 'terrain_context', 'site01_roi6')
        if not (pack / 'local_display_f32.bin').is_file():
            self.skipTest('no SfS display surface in this checkout')
        d = self._ds('site01_roi6')
        vals, info = bv.context_display_surface(pack, d['dem'])
        self.assertIsNotNone(vals, info)
        self.assertEqual(len(vals), d['dem']['n'] ** 2)
        self.assertEqual(info['licence'], 'CC-BY-4.0')
        self.assertIs(info['numericalAuthority'], False)
        sc = bv.scenario(d)
        obs = bv.observer(d, sc)
        k = bv.display_shift(d['dem'], vals, obs)
        n, s = d['dem']['n'], d['dem']['spacing']
        i = round((obs['x'] - d['dem']['originX']) / s); j = round((obs['y'] - d['dem']['originY']) / s)
        self.assertAlmostEqual(vals[j * n + i] + k, d['dem']['values'][j * n + i], places=3)

    def test_mid_ring_encloses_the_crop_and_is_cut_under_it(self):
        pack = Path(ROOT, 'data', 'visual', 'terrain_context', 'site04_roi3')
        d = self._ds('site04_roi3')
        mid, info, box = bv.context_mid_dem(pack, d['dem'])
        if mid is None:
            self.skipTest(info)
        dem = d['dem']
        ext = (dem['n'] - 1) * dem['spacing']
        self.assertLess(box[0], dem['originX']); self.assertGreater(box[1], dem['originX'] + ext)
        self.assertLess(box[2], dem['originY']); self.assertGreater(box[3], dem['originY'] + ext)
        self.assertGreater(info['nodesLoweredInsideLocalFootprint'], 0)

    def test_display_surface_is_refused_for_another_crop(self):
        pack = Path(ROOT, 'data', 'visual', 'terrain_context', 'site01_roi6')
        d = self._ds('site04_roi3')
        vals, why = bv.context_display_surface(pack, d['dem'])
        self.assertIsNone(vals)
        self.assertIn('different DEM crop', why)

