"""High-detail, full-scale globes (Moon, Mars, Mercury, Earth), the Sun, and the Earth-Moon-Sun system at true positions.

    blender -b --python-exit-code 1 -P blender/v2/globe_hd.py -- [--bodies moon,mars,mercury,earth,sun,system] [--qa]

Scale and frames: 1 Blender unit = 1 km, true radii; each globe in its body-fixed frame (x -> lon 0, y -> lon 90 E,
z -> north); the system scene in J2000, Earth-centred, with each body rotated by its SPICE body-fixed -> J2000 matrix.
Terrain: a viewport mesh (cube-sphere n = 384, heights at the nodes) plus render-time adaptive subdivision displaced by
(map height - mesh height), the map being the 23040 x 11520 (Earth 21600 x 10800) height grid of globe_hd_pack.py:
~0.47 km (Moon), 0.67 km (Mercury), 0.93 km (Mars), 1.85 km (Earth) per pixel at the equator, against 7-21 km node spacing
of the earlier globes. No vertical exaggeration anywhere.
Surfaces: Moon = Hapke 2012 with the WAC 643 nm w per vertex (MODEL, as globe.py); Mercury = MDIS enhanced colour (VISUAL);
Earth = Blue Marble Next Generation, November 2004, no relief shading (VISUAL; credit NASA Earth Observatory); Mars =
uniform tint (VISUAL; no albedo map); Sun = emission with a linear limb-darkening law u = 0.6 (MODEL, Allen's Astrophysical
Quantities, visible). No atmospheres are modelled (stated). Sun lamps from SPICE (geometry.json), no art-directed lights.
Output: blender/output/v2/showcase/hd/<body>/<body>_hd.blend (+ --qa renders), hd/sun.blend, hd/system.blend.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
from v2 import cubesphere  # noqa: E402

HD = ROOT / 'blender' / 'output' / 'v2' / 'showcase' / 'hd'
PROD = ROOT / 'data' / 'cache' / 'v2' / 'products'
COLOUR = {'earth': (PROD / 'earth_bmng_200411/world.200411.3x21600x10800.jpg', 180.0),
          'mercury': (PROD / 'mercury_mdis_color_665m/Mercury_MESSENGER_MDIS_Basemap_EnhancedColor_Mosaic_Global_665m.tif', 180.0)}
MARS_TINT = (0.30, 0.17, 0.10)
NAME = {'moon': 'MOON', 'mars': 'MARS', 'mercury': 'MERCURY', 'earth': 'EARTH'}


def args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bodies', default='moon,mars,mercury,earth,sun,system')
    ap.add_argument('--qa', action='store_true')
    ap.add_argument('--samples', type=int, default=24)
    return ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])


def new_file(name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.name = name
    sc.unit_settings.system, sc.unit_settings.scale_length = 'METRIC', 1000.0
    w = bpy.data.worlds.new('Space (black)')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0, 0, 0, 1)
    sc.world = w
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.view_settings.view_transform = 'Standard'
    return sc


def _math(nt, op, a, b=None):
    n = nt.nodes.new('ShaderNodeMath')
    n.operation = op
    for i, x in enumerate((a, b)):
        if x is None:
            continue
        if isinstance(x, (int, float)):
            n.inputs[i].default_value = float(x)
        else:
            nt.links.new(x, n.inputs[i])
    return n.outputs[0]


def equirect_uv(nt, lon0_deg):
    """(u, v) of the equirect texel under each shading point, from object-space position (no UV seam)."""
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs[0])
    X, Y, Z = sep.outputs
    lon = _math(nt, 'MULTIPLY', _math(nt, 'ARCTAN2', Y, X), 180.0 / math.pi)
    u = _math(nt, 'FRACT', _math(nt, 'ADD', _math(nt, 'DIVIDE', _math(nt, 'SUBTRACT', lon, lon0_deg), 360.0), 2.0))
    ln = nt.nodes.new('ShaderNodeVectorMath')
    ln.operation = 'LENGTH'
    nt.links.new(tc.outputs['Object'], ln.inputs[0])
    lat = _math(nt, 'ARCSINE', _math(nt, 'DIVIDE', Z, ln.outputs['Value']))
    v = _math(nt, 'ADD', _math(nt, 'DIVIDE', lat, math.pi), 0.5)
    c = nt.nodes.new('ShaderNodeCombineXYZ')
    nt.links.new(u, c.inputs['X'])
    nt.links.new(v, c.inputs['Y'])
    return c.outputs['Vector']


def _decoded_tap(nt, img, u, v, meta):
    """Height (km) of the texel containing (u, v): two packed bytes, sampled with Closest so they are never mixed."""
    c = nt.nodes.new('ShaderNodeCombineXYZ')
    nt.links.new(u, c.inputs['X'])
    nt.links.new(v, c.inputs['Y'])
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = img
    tx.interpolation = 'Closest'
    tx.extension = 'REPEAT'
    nt.links.new(c.outputs['Vector'], tx.inputs['Vector'])
    sp = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(tx.outputs['Color'], sp.inputs['Color'])
    q = _math(nt, 'ADD', _math(nt, 'MULTIPLY', sp.outputs['Red'], 255.0 * 256.0), _math(nt, 'MULTIPLY', sp.outputs['Green'], 255.0))
    return _math(nt, 'DIVIDE', _math(nt, 'ADD', _math(nt, 'MULTIPLY', q, (meta['hmax_m'] - meta['hmin_m']) / 65535.0),
                                     meta['hmin_m']), 1000.0)


def add_displacement(m, meta, d):
    """Displacement = bilinear(height map) - base mesh height. Bilinear interpolation is done here on four decoded
    Closest taps, so the packed bytes are never interpolated across a carry."""
    nt = m.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    img = bpy.data.images.load(str(d / meta['height_png']), check_existing=True)
    img.colorspace_settings.name = 'Non-Color'
    W, H = float(meta['width']), float(meta['height'])
    uvv = equirect_uv(nt, meta['lon0_deg'])
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(uvv, sep.inputs[0])
    px = _math(nt, 'SUBTRACT', _math(nt, 'MULTIPLY', sep.outputs['X'], W), 0.5)
    py = _math(nt, 'SUBTRACT', _math(nt, 'MULTIPLY', sep.outputs['Y'], H), 0.5)
    ix, iy = _math(nt, 'FLOOR', px), _math(nt, 'FLOOR', py)
    fx, fy = _math(nt, 'SUBTRACT', px, ix), _math(nt, 'SUBTRACT', py, iy)
    u0 = _math(nt, 'DIVIDE', _math(nt, 'ADD', ix, 0.5), W)
    u1 = _math(nt, 'DIVIDE', _math(nt, 'ADD', ix, 1.5), W)
    v0 = _math(nt, 'DIVIDE', _math(nt, 'MAXIMUM', _math(nt, 'ADD', iy, 0.5), 0.5), H)
    v1 = _math(nt, 'DIVIDE', _math(nt, 'MINIMUM', _math(nt, 'ADD', iy, 1.5), H - 0.5), H)
    h00, h10 = _decoded_tap(nt, img, u0, v0, meta), _decoded_tap(nt, img, u1, v0, meta)
    h01, h11 = _decoded_tap(nt, img, u0, v1, meta), _decoded_tap(nt, img, u1, v1, meta)

    def lerp(a, b, t):
        return _math(nt, 'ADD', a, _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', b, a), t))
    h_km = lerp(lerp(h00, h10, fx), lerp(h01, h11, fx), fy)
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_name = 'base_h_km'
    dh = _math(nt, 'SUBTRACT', h_km, at.outputs['Fac'])
    dn = nt.nodes.new('ShaderNodeDisplacement')
    dn.inputs['Midlevel'].default_value = 0.0
    dn.inputs['Scale'].default_value = 1.0
    dn.space = 'OBJECT'
    nt.links.new(dh, dn.inputs['Height'])
    nt.links.new(dn.outputs['Displacement'], out.inputs['Displacement'])
    m.displacement_method = 'DISPLACEMENT'
    m.max_vertex_displacement = max(abs(meta['hmax_m']), abs(meta['hmin_m'])) / 1000.0 + 1.0


def surface(body, meta, d, V):
    if body == 'moon':
        from v2 import albedo, hapke, hapke_nodes
        m, _info = hapke_nodes.hapke_material('MOON | Hapke 2012 (GLOBAL) | WAC w per vertex | MODEL', hapke.params('GLOBAL'),
                                              tuple(meta['geometry']['sun']), w_attribute='polaris_w')
        la, lo = cubesphere.latlon_deg(V)
        return m, albedo.WMap.load().sample(la, lo)
    m = bpy.data.materials.new(f"{NAME[body]} | diffuse | " + ('uniform tint, VISUAL' if body == 'mars' else 'imagery, VISUAL'))
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bs = nt.nodes.new('ShaderNodeBsdfDiffuse')
    nt.links.new(bs.outputs['BSDF'], out.inputs['Surface'])
    if body == 'mars':
        bs.inputs['Color'].default_value = (*MARS_TINT, 1)
        m.diffuse_color = (*MARS_TINT, 1)
    else:
        path, lon0 = COLOUR[body]
        tx = nt.nodes.new('ShaderNodeTexImage')
        tx.image = bpy.data.images.load(str(path), check_existing=True)
        tx.extension = 'EXTEND'
        nt.links.new(equirect_uv(nt, lon0), tx.inputs['Vector'])
        nt.links.new(tx.outputs['Color'], bs.inputs['Color'])
        m.diffuse_color = (0.5, 0.5, 0.5, 1)
    return m, None


def sun_lamp(coll, direction, range_km, label):
    E = 1361.0 / (range_km / 149_597_870.7) ** 2
    ld = bpy.data.lights.new(f'Sun | SPICE direction ({label}), 1361/r^2 = {E:.0f} W/m^2', 'SUN')
    ld.energy = E
    ld.angle = 2 * math.asin(695_700.0 / range_km)
    lo = bpy.data.objects.new(ld.name, ld)
    coll.objects.link(lo)
    lo.rotation_mode = 'QUATERNION'
    lo.rotation_quaternion = Vector(direction).normalized().to_track_quat('Z', 'Y')
    return E


def camera(coll, name, loc, look_at, lens=35.0, ortho=None, clip=1e7):
    cd = bpy.data.cameras.new(name)
    if ortho:
        cd.type, cd.ortho_scale = 'ORTHO', ortho
    else:
        cd.lens = lens
    cd.clip_start, cd.clip_end = 0.1, clip
    ob = bpy.data.objects.new(name, cd)
    coll.objects.link(ob)
    ob.location = Vector(loc)
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = (Vector(look_at) - Vector(loc)).to_track_quat('-Z', 'Y')
    return ob


def globe(body, a):
    d = HD / body
    meta = json.loads((d / 'meta.json').read_text())
    sc = new_file(f'{NAME[body]} HD globe')
    coll = bpy.data.collections.new(f'COL_{body}_hd')
    sc.collection.children.link(coll)
    Rk = meta['radius_m'] / 1e3
    base = np.load(d / meta['base'])
    V, F, fid, uv, dropped = cubesphere.mesh(meta['n'], base, radius_m=meta['radius_m'], scale=1e-3)
    me = bpy.data.meshes.new(body)
    me.from_pydata(V.tolist(), [], F.tolist())
    me.update()
    me.shade_smooth()
    hk = (np.linalg.norm(V, axis=1) - Rk).astype(np.float32)
    at = me.attributes.new('base_h_km', 'FLOAT', 'POINT')
    at.data.foreach_set('value', hk)
    ob = bpy.data.objects.new(f"{NAME[body]} | HD | {meta['source']} | {meta['px_km_equator']:.2f} km/px map, true radius "
                              f"{Rk:.1f} km | SOURCE-BASED UNVALIDATED", me)
    coll.objects.link(ob)
    m, w = surface(body, meta, d, V)
    if w is not None:
        aw = me.attributes.new('polaris_w', 'FLOAT', 'POINT')
        aw.data.foreach_set('value', np.asarray(w, np.float32))
    add_displacement(m, meta, d)
    me.materials.append(m)
    mod = ob.modifiers.new('Adaptive detail (render)', 'SUBSURF')
    mod.subdivision_type = 'SIMPLE'
    mod.levels = 0
    mod.render_levels = 0
    mod.use_adaptive_subdivision = True
    mod.adaptive_pixel_size = 1.0
    g = meta['geometry']
    E = sun_lamp(coll, g['sun'], g['sunRangeKm'], 'body-fixed')
    sc.view_settings.exposure = math.log2(0.8 * math.pi / (0.25 * E))
    v = Vector(g['viewer']).normalized()
    disc = camera(coll, f"CAM_{body}_disc_from_{g['viewerName']}", v * 10 * Rk, (0, 0, 0), ortho=2.08 * Rk, clip=40 * Rk)
    # close-up: the lit side 65 deg from the sub-solar point toward the evening terminator, oblique, 35 mm
    s = Vector(g['sun']).normalized()
    t = (Matrix.Rotation(math.radians(65), 3, 'Z') @ s).normalized() * Rk
    up = t.normalized()
    east = Vector((0, 0, 1)).cross(up).normalized()
    north = up.cross(east)
    loc = t + up * 0.06 * Rk - north * 0.12 * Rk
    close = camera(coll, f'CAM_{body}_closeup_terminator', loc, t, lens=35.0, clip=10 * Rk)
    lit = (s * 0.8 + east * 0.6).normalized()                         # mostly sunlit hemisphere, some relief at the limb
    camera(coll, f'CAM_{body}_sunlit_side', lit * 10 * Rk, (0, 0, 0), ortho=2.08 * Rk, clip=40 * Rk)
    sc.camera = disc
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    sc.cycles.samples = a.samples
    sc['polaris'] = json.dumps({'builder': 'blender/v2/globe_hd.py', 'meta': meta, 'exposure': 'presentation (VISUAL)'})
    if a.qa:
        for cam, tag in ((disc, 'disc'), (close, 'closeup'), (coll.objects[f'CAM_{body}_sunlit_side'], 'sunlit')):
            sc.camera = cam
            sc.render.resolution_x, sc.render.resolution_y = (1280, 720) if tag == 'closeup' else (900, 900)
            sc.render.filepath = str(d / f'{body}_hd_{tag}.png')
            bpy.ops.render.render(write_still=True)
        sc.camera = disc
    bpy.ops.wm.save_as_mainfile(filepath=str(d / f'{body}_hd.blend'), compress=False)
    print(f'[POLARIS HD] {body}: {len(V)} viewport vertices, map {meta["width"]}x{meta["height"]}, wrote {body}_hd.blend', flush=True)


def sun_material(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (1.0, 0.93, 0.85, 1)
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    dp = nt.nodes.new('ShaderNodeVectorMath')
    dp.operation = 'DOT_PRODUCT'
    nt.links.new(geo.outputs['Normal'], dp.inputs[0])
    nt.links.new(geo.outputs['Incoming'], dp.inputs[1])
    mu = _math(nt, 'ABSOLUTE', dp.outputs['Value'])                  # mu = cos(angle between the normal and the line of sight)
    ld = _math(nt, 'SUBTRACT', 1.0, _math(nt, 'MULTIPLY', 0.6, _math(nt, 'SUBTRACT', 1.0, mu)))
    nt.links.new(ld, em.inputs['Strength'])
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    m.diffuse_color = (1.0, 0.9, 0.7, 1)
    return m


def sun_scene(a):
    sc = new_file('SUN, true radius 695 700 km')
    coll = bpy.data.collections.new('COL_sun')
    sc.collection.children.link(coll)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=256, ring_count=128, radius=695_700.0)
    ob = bpy.context.active_object
    for c in ob.users_collection:
        c.objects.unlink(ob)
    coll.objects.link(ob)
    ob.name = 'SUN | sphere R = 695 700 km (IAU 2015 nominal) | linear limb darkening u = 0.6 | MODEL'
    ob.data.shade_smooth()
    ob.data.materials.append(sun_material('Sun photosphere | limb darkening | MODEL'))
    camera(coll, 'CAM_sun_disc', (0, -10 * 695_700.0, 0), (0, 0, 0), ortho=2.1 * 695_700.0, clip=1e8)
    sc.camera = [o for o in coll.objects if o.type == 'CAMERA'][0]
    sc.view_settings.exposure = 0.0
    sc.cycles.samples = 16
    if a.qa:
        sc.render.resolution_x = sc.render.resolution_y = 800
        sc.render.filepath = str(HD / 'sun_disc.png')
        bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(HD / 'sun.blend'), compress=False)
    print('[POLARIS HD] sun: wrote sun.blend', flush=True)


def system_scene(a):
    geo = json.loads((HD / 'geometry.json').read_text())['system']
    sc = new_file(f'EARTH-MOON-SUN system, true scale and positions (J2000, Earth-centred, {json.loads((HD / "geometry.json").read_text())["utc"]})')
    coll = bpy.data.collections.new('COL_system')
    sc.collection.children.link(coll)
    for body, key in (('earth', 'earthToJ2000'), ('moon', 'moonToJ2000')):
        p = HD / body / f'{body}_hd.blend'
        with bpy.data.libraries.load(str(p), link=False) as (src, dst):
            dst.objects = [n for n in src.objects if n.startswith(NAME[body] + ' | HD')]
        for ob in dst.objects:
            coll.objects.link(ob)
            Rm = Matrix(geo[key])
            ob.matrix_world = Rm.to_4x4()
            if body == 'moon':
                ob.location = Vector(geo['moonPosKm'])
    bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=695_700.0, location=Vector(geo['sunPosKm']))
    sun = bpy.context.active_object
    for c in sun.users_collection:
        c.objects.unlink(sun)
    coll.objects.link(sun)
    sun.name = 'SUN | true radius and position (de421) | MODEL'
    sun.visible_shadow = False          # the sphere sits on the lamp's shadow rays; it must not shadow the Earth and Moon
    sun.data.materials.append(sun_material('Sun photosphere (system) | MODEL'))
    rng = Vector(geo['sunPosKm']).length
    E = sun_lamp(coll, geo['sunPosKm'], rng, 'J2000')
    sc.view_settings.exposure = math.log2(0.8 * math.pi / (0.25 * E))
    m = Vector(geo['moonPosKm'])
    side = m.cross(Vector((0, 0, 1))).normalized()
    sdir = Vector(geo['sunPosKm']).normalized()
    camera(coll, 'CAM_system_earth_moon_true_distance_sunward', m / 2 + (sdir * 0.95 + side * 0.3).normalized() * 1_000_000.0,
           m / 2, lens=50.0, clip=5e8)
    camera(coll, 'CAM_system_earth_dayside', (sdir * 0.9 + side * 0.44).normalized() * 70_000.0, (0, 0, 0), lens=35.0, clip=5e8)
    camera(coll, 'CAM_system_earth_from_near_moon_night_side', m + (sdir * 0.6 + side * 0.8).normalized() * 40_000.0, (0, 0, 0),
           lens=200.0, clip=5e8)
    sc.camera = [o for o in coll.objects if o.name == 'CAM_system_earth_dayside'][0]
    sc.cycles.samples = 16
    if a.qa:
        sc.render.resolution_x, sc.render.resolution_y = 1280, 720
        for cam in [o for o in coll.objects if o.type == 'CAMERA']:
            sc.camera = cam
            sc.render.filepath = str(HD / f'system_{cam.name[11:]}.png')
            bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(HD / 'system.blend'), compress=False)
    print('[POLARIS HD] system: wrote system.blend', flush=True)


def main():
    a = args()
    for b in a.bodies.split(','):
        if b in NAME:
            globe(b, a)
        elif b == 'sun':
            sun_scene(a)
        elif b == 'system':
            system_scene(a)


if __name__ == '__main__':
    main()
