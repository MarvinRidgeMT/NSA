"""Fails unless every .glb/.gltf under web/public/ was exported by Blender's Khronos glTF I/O and built by
blender/v2/build_scene.py, except whitelisted non-terrain UI assets (pinned SHA-256, reason per entry)."""
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import glb_proof as G  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def make_glb(path, asset, scenes=None):
    j = {'asset': asset, 'scenes': scenes or [{'nodes': []}], 'scene': 0}
    data = json.dumps(j).encode()
    data += b' ' * ((4 - len(data) % 4) % 4)
    blob = struct.pack('<4sII', b'glTF', 2, 12 + 8 + len(data)) + struct.pack('<I4s', len(data), b'JSON') + data
    Path(path).write_bytes(blob)


class WebPublic(unittest.TestCase):
    def test_every_web_glb_is_blender_built_or_whitelisted(self):
        rows = G.scan(ROOT)
        bad = [(r, why) for r, ok, why in rows if not ok]
        self.assertEqual(bad, [], '\n'.join(f'{r}: {w}' for r, w in bad))

    def test_whitelist_entries_have_reasons_and_hashes(self):
        for rel, w in G.WHITELIST.items():
            self.assertGreater(len(w['reason']), 80, rel)
            self.assertEqual(len(w['sha256']), 64, rel)
            self.assertNotIn('terrain', w['kind'].replace('non-terrain', ''), rel)


class Rules(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def test_non_blender_generator_fails(self):
        p = self.d / 'a.glb'
        make_glb(p, {'version': '2.0', 'generator': 'three.js GLTFExporter'})
        ok, why = G.check(p, 'web/public/a.glb')
        self.assertFalse(ok)
        self.assertIn('not the Blender glTF exporter', why)

    def test_blender_without_polaris_provenance_fails(self):
        p = self.d / 'b.glb'
        make_glb(p, {'version': '2.0', 'generator': 'Khronos glTF Blender I/O v5.3.0'})
        ok, why = G.check(p, 'web/public/b.glb')
        self.assertFalse(ok)
        self.assertIn('extras.polaris', why)

    def test_blender_with_polaris_provenance_passes(self):
        p = self.d / 'c.glb'
        prov = json.dumps({'builder': 'blender/v2/build_scene.py', 'tag': 't'})
        make_glb(p, {'version': '2.0', 'generator': 'Khronos glTF Blender I/O v5.3.0'}, [{'nodes': [], 'extras': {'polaris': prov}}])
        ok, _ = G.check(p, 'web/public/c.glb')
        self.assertTrue(ok)

    def test_changed_whitelisted_file_loses_exemption(self):
        rel = next(iter(G.WHITELIST))
        p = self.d / 'w.glb'
        make_glb(p, {'version': '2.0', 'generator': 'Khronos glTF Blender I/O v5.0.21'})
        ok, why = G.check(p, rel)
        self.assertFalse(ok)
        self.assertIn('exemption lost', why)

    def test_v2_build_output_passes_when_present(self):
        """Any GLB that build_scene.py wrote (blender/output/v2/**, git-ignored) must pass the same rule."""
        outs = sorted((ROOT / 'blender' / 'output' / 'v2').rglob('*.glb'))
        if not outs:
            self.skipTest('no v2 GLB built yet (build_scene.py --glb)')
        for p in outs:
            ok, why = G.check(p, p.relative_to(ROOT).as_posix())
            self.assertTrue(ok, f'{p.name}: {why}')


if __name__ == '__main__':
    unittest.main()
