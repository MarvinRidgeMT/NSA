"""glTF provenance check (prompt §5.3): every web 3D asset must come out of Blender, and ours out of build_scene.py.

Rule for every .glb / .gltf under web/public/:
  1. asset.generator starts with "Khronos glTF Blender I/O" (the exporter Blender ships);
  2. scenes[*].extras.polaris names a POLARIS builder, "blender/v2/build_scene.py" (close-ups) or "blender/v2/globe.py" (the
     whole-Moon globe), written via export_extras, so a file merely re-saved by some other Blender session does not pass;
unless the file is on WHITELIST with a reason AND still has the pinned SHA-256 (a changed file loses its exemption).
Pure Python; used by test_glb_proof.py and run_all.py.
"""
import hashlib
import json
import struct
from pathlib import Path

GENERATOR_PREFIX = 'Khronos glTF Blender I/O'
BUILDER = 'blender/v2/build_scene.py'
BUILDERS = (BUILDER, 'blender/v2/globe.py')

WHITELIST = {
    'web/public/globe/NASA_SVS_moon_small.glb': {
        'sha256': '12d3b0bb7fe214903f51447d1bc61710f442e92a11c703fcaca6d4e7ff8e67d4',
        'reason': ('Third-party NASA asset: NASA SVS 14959 "Moon_NASA_LRO_8k" colour-only fallback, credited to NASA Goddard '
                   '(docs/DATA_PROVENANCE.md). Its generator string reads "Khronos glTF Blender I/O v5.0.21" because NASA GSFC '
                   'exported it from Blender, not because POLARIS did, so it has no POLARIS build provenance. It is a VISUAL '
                   'whole-Moon navigation globe, never terrain for any calculation or close-up. Re-exporting it here would only '
                   'relabel NASA\'s mesh; it is replaced when the v2 global base mesh (cube-sphere from the S3 pyramid) is built '
                   'by build_scene.py.'),
        'kind': 'non-terrain UI globe (third party)',
    },
}


def read_gltf_json(path):
    p = Path(path)
    raw = p.read_bytes()
    if p.suffix.lower() == '.gltf':
        return json.loads(raw)
    magic, version, length = struct.unpack_from('<4sII', raw, 0)
    if magic != b'glTF' or version != 2:
        raise ValueError(f'{p}: not a glTF 2.0 binary')
    clen, ctype = struct.unpack_from('<I4s', raw, 12)
    if ctype != b'JSON':
        raise ValueError(f'{p}: first chunk is not JSON')
    return json.loads(raw[20:20 + clen])


def polaris_extras(j):
    for sc in j.get('scenes', []):
        x = (sc.get('extras') or {}).get('polaris')
        if isinstance(x, str):
            try:
                x = json.loads(x)
            except json.JSONDecodeError:
                return None
        if isinstance(x, dict):
            return x
    return None


def check(path, rel):
    """Returns (ok, reason)."""
    j = read_gltf_json(path)
    gen = (j.get('asset') or {}).get('generator') or ''
    if rel in WHITELIST:
        w = WHITELIST[rel]
        sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        if sha != w['sha256']:
            return False, f'whitelisted file changed (sha256 {sha} != pinned {w["sha256"]}): exemption lost'
        return True, f'WHITELISTED ({w["kind"]}): {w["reason"][:80]}...'
    if not gen.startswith(GENERATOR_PREFIX):
        return False, f'asset.generator {gen!r} is not the Blender glTF exporter'
    x = polaris_extras(j)
    if not x or x.get('builder') not in BUILDERS:
        return False, f'generator is Blender ({gen}) but scenes[].extras.polaris does not name a POLARIS builder {BUILDERS}'
    return True, f'Blender ({gen}), built by {x["builder"]} tag {x.get("tag")}'


def scan(root):
    root = Path(root)
    out = []
    web = root / 'web' / 'public'
    for p in sorted(list(web.rglob('*.glb')) + list(web.rglob('*.gltf'))):
        rel = p.relative_to(root).as_posix()
        ok, why = check(p, rel)
        out.append((rel, ok, why))
    return out
