"""Pure-Python (no bpy) GLB reader for parity checks: nodes, meshes, materials, units and bounding box.

glTF is metres and Y-up. The POLARIS export maps Blender (x grid-east, y grid-north, z up) to glTF (x, z, -y).
`inspect_glb` returns world-space bounds computed from accessor min/max and each node's translation/scale (rotation is
applied when present). Used by blender/test_bundle_v2.py and by the builder's manifest.
"""
import json
import math
import struct
from pathlib import Path


def _read(path):
    raw = Path(path).read_bytes()
    magic, version, length = struct.unpack_from('<4sII', raw, 0)
    if magic != b'glTF' or version != 2 or length != len(raw):
        raise ValueError(f'{path}: not a glTF 2.0 binary (magic {magic!r}, version {version}, length {length} vs {len(raw)})')
    clen, ctype = struct.unpack_from('<I4s', raw, 12)
    if ctype != b'JSON':
        raise ValueError('first chunk is not JSON')
    return json.loads(raw[20:20 + clen]), len(raw)


def _qrot(q, v):
    x, y, z, w = q
    vx, vy, vz = v
    # v' = v + 2w (q x v) + 2 q x (q x v)
    cx, cy, cz = y * vz - z * vy, z * vx - x * vz, x * vy - y * vx
    cx2, cy2, cz2 = y * cz - z * cy, z * cx - x * cz, x * cy - y * cx
    return (vx + 2 * (w * cx + cx2), vy + 2 * (w * cy + cy2), vz + 2 * (w * cz + cz2))


def inspect_glb(path):
    j, nbytes = _read(path)
    acc = j.get('accessors', [])
    meshes = j.get('meshes', [])
    out_nodes = []
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for node in j.get('nodes', []):
        info = {'name': node.get('name'), 'mesh': node.get('mesh') is not None, 'light': 'KHR_lights_punctual' in node.get('extensions', {})}
        if node.get('mesh') is not None:
            m = meshes[node['mesh']]
            verts = 0
            mats = set()
            t = node.get('translation', [0, 0, 0])
            s = node.get('scale', [1, 1, 1])
            q = node.get('rotation', [0, 0, 0, 1])
            for prim in m['primitives']:
                a = acc[prim['attributes']['POSITION']]
                verts += a['count']
                if 'material' in prim:
                    mats.add(prim['material'])
                for cx in (a['min'][0], a['max'][0]):
                    for cy in (a['min'][1], a['max'][1]):
                        for cz in (a['min'][2], a['max'][2]):
                            p = _qrot(q, (cx * s[0], cy * s[1], cz * s[2]))
                            p = (p[0] + t[0], p[1] + t[1], p[2] + t[2])
                            for k in range(3):
                                lo[k] = min(lo[k], p[k])
                                hi[k] = max(hi[k], p[k])
            info.update(vertices=verts, materials=sorted(mats))
        out_nodes.append(info)
    mats = [m.get('name') for m in j.get('materials', [])]
    return {'bytes': nbytes, 'generator': j.get('asset', {}).get('generator'), 'nodes': out_nodes, 'meshCount': len(meshes),
            'materials': mats, 'boundsGltfM': {'min': [round(v, 3) for v in lo], 'max': [round(v, 3) for v in hi]},
            'units': 'metres (glTF)', 'upAxis': 'Y'}
