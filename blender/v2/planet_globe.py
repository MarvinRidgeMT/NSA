"""Full-scale Mars and Mercury globes in Blender, built like the Moon's (globe.py): cube-sphere at the true radius,
1 Blender unit = 1 km, body-fixed axes (x -> lon 0, y -> lon 90 E, z -> north), heights from planet_pack.py, no vertical
exaggeration. Sun lamp from the world bundle's first sample (direction; 1361 / r^2 W m^-2), black sky, orthographic camera
along the bundle's Earth direction (whole disc as seen from Earth; parallax ignored), image up = north.

    blender -b --python-exit-code 1 -P blender/v2/planet_globe.py -- [--world mars|mercury|all] [--n 256]

Surface: diffuse, roughness 1. Mars: a uniform tint (VISUAL; no albedo map is used). Mercury: the MDIS enhanced-colour
mosaic (VISUAL: enhanced false colour, not albedo), looked up in the shader from each point's lat/lon (no UV seam).
Exposure: a presentation exposure (VISUAL) that maps albedo 0.25 at normal incidence to 0.8, recorded in the scene.
Output: blender/output/v2/showcase/planets/<world>/<world>_globe.blend + .png.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
from v2 import cubesphere  # noqa: E402

BASE = ROOT / 'blender' / 'output' / 'v2' / 'showcase' / 'planets'
NAMES = {'mars': 'MARS', 'mercury': 'MERCURY'}
MARS_TINT = (0.30, 0.17, 0.10)          # VISUAL uniform tint (no albedo product)


def args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--world', default='all', choices=['mars', 'mercury', 'all'])
    ap.add_argument('--n', type=int, default=256)
    ap.add_argument('--resolution', type=int, default=1024)
    ap.add_argument('--samples', type=int, default=32)
    return ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])


def material(world, meta, d):
    m = bpy.data.materials.new(f'{NAMES[world]} surface | diffuse | ' + ('MDIS enhanced colour, VISUAL' if world == 'mercury'
                                                                           else 'uniform tint, VISUAL'))
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bs = nt.nodes.new('ShaderNodeBsdfDiffuse')
    bs.inputs['Roughness'].default_value = 1.0
    nt.links.new(bs.outputs['BSDF'], out.inputs['Surface'])
    if world != 'mercury':
        bs.inputs['Color'].default_value = (*MARS_TINT, 1.0)
        m.diffuse_color = (*MARS_TINT, 1.0)
        return m
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs[0])

    def math_(op, a, b=None, val=None):
        n = nt.nodes.new('ShaderNodeMath')
        n.operation = op
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                nt.links.new(x, n.inputs[i])
        return n.outputs[0]
    X, Y, Z = sep.outputs['X'], sep.outputs['Y'], sep.outputs['Z']
    lon = math_('ARCTAN2', Y, X)                                        # radians, east-positive
    u = math_('FRACT', math_('ADD', math_('DIVIDE', math_('SUBTRACT', math_('MULTIPLY', lon, 180.0 / math.pi),
                                                                      meta['colourLon0']), 360.0), 1.0))
    r = nt.nodes.new('ShaderNodeVectorMath')
    r.operation = 'LENGTH'
    nt.links.new(tc.outputs['Object'], r.inputs[0])
    lat = math_('ARCSINE', math_('DIVIDE', Z, r.outputs['Value']))
    v = math_('ADD', math_('DIVIDE', lat, math.pi), 0.5)
    cmb = nt.nodes.new('ShaderNodeCombineXYZ')
    nt.links.new(u, cmb.inputs['X'])
    nt.links.new(v, cmb.inputs['Y'])
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = bpy.data.images.load(str(d / meta['colour']), check_existing=True)
    tx.extension = 'EXTEND'
    nt.links.new(cmb.outputs['Vector'], tx.inputs['Vector'])
    nt.links.new(tx.outputs['Color'], bs.inputs['Color'])
    m.diffuse_color = (0.5, 0.5, 0.5, 1.0)
    return m


def build(world, a):
    d = BASE / world
    meta = json.loads((d / 'pack.json').read_text())
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.name = f'{NAMES[world]} globe'
    sc.unit_settings.system, sc.unit_settings.scale_length = 'METRIC', 1000.0
    col = bpy.data.collections.new(f'POLARIS {world} globe')
    sc.collection.children.link(col)
    H = np.load(d / meta['heights'])
    V, F, fid, uv, dropped = cubesphere.mesh(meta['n'], H, radius_m=meta['radius_m'], scale=1e-3)
    me = bpy.data.meshes.new(world)
    me.from_pydata(V.tolist(), [], F.tolist())
    me.update()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(f"{NAMES[world]} | cube-sphere n={meta['n']} | {meta['dem']} | SOURCE-BASED UNVALIDATED | km, "
                              f"body-fixed axes, true radius {meta['radius_m'] / 1e3:.1f} km", me)
    col.objects.link(ob)
    ob.data.materials.append(material(world, meta, d))
    sky = meta['sky']
    E = 1361.0 / sky['sunRangeAu'] ** 2
    ld = bpy.data.lights.new(f"Sun | bundle direction ({sky['utc']}), 1361/r^2 = {E:.0f} W/m^2", 'SUN')
    ld.energy = E
    ld.angle = math.radians(0.53 / sky['sunRangeAu'])
    lo = bpy.data.objects.new(ld.name, ld)
    col.objects.link(lo)
    lo.rotation_mode = 'QUATERNION'
    lo.rotation_quaternion = Vector(sky['sun']).normalized().to_track_quat('Z', 'Y')
    w = bpy.data.worlds.new('Space (black)')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0, 0, 0, 1)
    sc.world = w
    R = meta['radius_m'] / 1e3
    cd = bpy.data.cameras.new('View from the Earth direction (orthographic)')
    cd.type = 'ORTHO'
    cd.ortho_scale = 2.08 * R
    cd.clip_start, cd.clip_end = 1.0, 40.0 * R
    cam = bpy.data.objects.new('CAMERA | Earth direction', cd)
    col.objects.link(cam)
    e = Vector(sky['earth']).normalized()
    cam.location = e * 10.0 * R
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (-e).to_track_quat('-Z', 'Y')
    sc.camera = cam
    # second camera: perpendicular to the Sun (the terminator through the disc centre), so relief reads under the true Sun
    sdir = Vector(sky['sun']).normalized()
    side = sdir.cross(Vector((0, 0, 1)))
    side = side.normalized() if side.length > 1e-6 else Vector((1, 0, 0))
    tdir = (side * 0.85 + sdir * 0.53).normalized()                 # 58 deg from the Sun: lit limb + terminator in view
    cd2 = bpy.data.cameras.new('View across the terminator (orthographic)')
    cd2.type = 'ORTHO'
    cd2.ortho_scale = 2.08 * R
    cd2.clip_start, cd2.clip_end = 1.0, 40.0 * R
    cam2 = bpy.data.objects.new('CAMERA | across the terminator', cd2)
    col.objects.link(cam2)
    cam2.location = tdir * 10.0 * R
    cam2.rotation_mode = 'QUATERNION'
    cam2.rotation_quaternion = (-tdir).to_track_quat('-Z', 'Y')
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = a.samples
    sc.cycles.device = 'CPU'
    sc.render.resolution_x = sc.render.resolution_y = a.resolution
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.exposure = math.log2(0.8 * math.pi / (0.25 * E))
    sc['polaris'] = json.dumps({'builder': 'blender/v2/planet_globe.py', 'pack': meta, 'exposureNote':
                                'presentation exposure (VISUAL): albedo 0.25 at normal incidence -> 0.8', 'droppedQuads': dropped})
    sc.render.filepath = str(d / f'{world}_globe.png')
    bpy.ops.render.render(write_still=True)
    sc.camera = cam2
    sc.render.filepath = str(d / f'{world}_globe_terminator.png')
    bpy.ops.render.render(write_still=True)
    sc.camera = cam
    bpy.ops.wm.save_as_mainfile(filepath=str(d / f'{world}_globe.blend'), compress=True)
    print(f'[POLARIS planet] {world}: {len(V)} vertices, heights {meta["heightRangeM"]}, wrote {d / (world + "_globe.blend")}')


def main():
    a = args()
    for world in (['mars', 'mercury'] if a.world == 'all' else [a.world]):
        build(world, a)


if __name__ == '__main__':
    main()
