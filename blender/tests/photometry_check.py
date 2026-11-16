"""Radiometric check of the Hapke node material (runs inside Blender; called by run_all.py).

A flat plane lit by a SUN lamp of irradiance E at incidence i, seen by an orthographic camera at emission e with phase g,
Raw view transform, exposure 0, no bounces: the pixel value must equal r(i, e, g) * E from blender/v2/hapke.py.
Also the per-vertex-w path (WAC albedo, attribute polaris_w): a plane whose vertices carry w must render r(i, e, g; w) * E.
"""
import math
import sys
import tempfile
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v2 import astro, hapke, hapke_nodes  # noqa: E402

CASES = [(60.0, 0.0, 60.0), (30.0, 0.0, 30.0), (45.0, 30.0, 75.0), (70.0, 40.0, 30.0), (20.0, 20.0, 5.0), (80.0, 10.0, 75.0)]
CASES_W = [(60.0, 0.0, 60.0, 0.21), (45.0, 30.0, 75.0, 0.27), (20.0, 20.0, 5.0, 0.46)]     # mare-like .. far-side highland w


def render_case(i_deg, e_deg, g_deg, E=1.0, params=None, w_attr=None):
    params = params or hapke.params()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    # geometry: light at azimuth 0, camera at azimuth psi so that the phase is g
    mu0, mu = math.cos(math.radians(i_deg)), math.cos(math.radians(e_deg))
    si, se = math.sin(math.radians(i_deg)), math.sin(math.radians(e_deg))
    cpsi = 1.0 if si * se == 0 else max(-1.0, min(1.0, (math.cos(math.radians(g_deg)) - mu0 * mu) / (si * se)))
    psi = math.acos(cpsi)
    L = Vector((0.0, si, mu0))
    V = Vector((se * math.sin(psi), se * math.cos(psi), mu))
    g_true = math.degrees(L.angle(V))
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
    plane = bpy.context.object
    mat, _ = hapke_nodes.hapke_material('hapke test', params, tuple(L), w_attribute='polaris_w' if w_attr is not None else None)
    plane.data.materials.append(mat)
    if w_attr is not None:
        at = plane.data.attributes.new('polaris_w', 'FLOAT', 'POINT')
        at.data.foreach_set('value', np.full(len(plane.data.vertices), w_attr, np.float32))
        params = dict(params, w=w_attr)
    ld = bpy.data.lights.new('sun', 'SUN')
    ld.energy = E
    ld.angle = 0.0
    sun = bpy.data.objects.new('sun', ld)
    sc.collection.objects.link(sun)
    sun.rotation_mode = 'QUATERNION'
    sun.rotation_quaternion = L.to_track_quat('Z', 'Y')
    cd = bpy.data.cameras.new('cam')
    cd.type = 'ORTHO'
    cd.ortho_scale = 2.0
    cam = bpy.data.objects.new('cam', cd)
    sc.collection.objects.link(cam)
    cam.location = V * 50.0
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (-V).to_track_quat('-Z', 'Y')
    sc.camera = cam
    w = bpy.data.worlds.new('w')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0, 0, 0, 1)
    sc.world = w
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 4
    sc.cycles.max_bounces = 0
    sc.cycles.use_denoising = False
    sc.render.resolution_x = sc.render.resolution_y = 8
    sc.view_settings.view_transform = 'Raw'
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = 'OPEN_EXR'
    sc.render.image_settings.color_depth = '32'
    out = Path(tempfile.mkdtemp()) / 'plane.exr'
    sc.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(str(out))
    px = np.empty(len(im.pixels), np.float32)
    im.pixels.foreach_get(px)
    val = float(px.reshape(-1, 4)[:, 0].mean())
    expected = hapke.reference_r(params, i_deg, e_deg, g_true) * E
    return val, expected, g_true


def run(tol=0.02):
    rows, ok = [], True
    for i, e, g in CASES:
        v, x, gt = render_case(i, e, g)
        rel = abs(v - x) / x
        ok &= rel <= tol
        rows.append({'i': i, 'e': e, 'g': round(gt, 3), 'rendered': v, 'expected': x, 'relErr': rel})
        print(f'[photometry] i={i:5.1f} e={e:5.1f} g={gt:6.2f}  rendered {v:.6f}  hapke {x:.6f}  rel {rel:.2e}')
    for i, e, g, w in CASES_W:
        v, x, gt = render_case(i, e, g, w_attr=w)
        rel = abs(v - x) / x
        ok &= rel <= tol
        rows.append({'i': i, 'e': e, 'g': round(gt, 3), 'w': w, 'rendered': v, 'expected': x, 'relErr': rel})
        print(f'[photometry] w={w:.2f} (attribute) i={i:5.1f} e={e:5.1f} g={gt:6.2f}  rendered {v:.6f}  hapke {x:.6f}  rel {rel:.2e}')
    return ok, rows


if __name__ == '__main__':
    ok, _ = run()
    sys.exit(0 if ok else 1)
