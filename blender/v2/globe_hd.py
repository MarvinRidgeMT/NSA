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
NAME = {'moon': 'MOON', 'mars': 'MARS', 'mercury': 'MERCURY', 'earth': 'EARTH', 'venus': 'VENUS', 'jupiter': 'JUPITER',
        'saturn': 'SATURN', 'uranus': 'URANUS', 'neptune': 'NEPTUNE'}
OUTER = PROD / 'outer_planets_maps'
# IAU 2015 / NASA planetary fact sheet radii (km): equatorial, polar (1 bar level for the giant planets)
GIANTS = {'jupiter': (71_492.0, 66_854.0, 'hlsp_opal_hst_wfc3-uvis_jupiter-2025b_f395n-f502n-f631n_v1_globalmap.tif', 'OPAL 2025b'),
          'saturn': (60_268.0, 54_364.0, 'hlsp_opal_hst_wfc3-uvis_saturn-2025b_f395n-f502n-f631n_v1_globalmap.tif', 'OPAL 2025b'),
          'uranus': (25_559.0, 24_973.0, 'hlsp_opal_hst_wfc3-uvis_uranus-2024b_f657n-f547m-f467m_v1_globalmap.tif', 'OPAL 2024b'),
          'neptune': (24_764.0, 24_341.0, 'hlsp_opal_hst_wfc3-uvis_neptune-2025c_f467m-f547m-f657n_v1_globalmap.tif', 'OPAL 2025c')}
# Saturn's rings (NASA Saturn fact sheet radii, km) with representative normal optical depths (Cuzzi et al. 2009 review);
# MODEL: piecewise-constant tau, a colour per ring.
SATURN_RINGS = [(66_900, 74_510, 0.01, (0.40, 0.38, 0.35)), (74_658, 92_000, 0.10, (0.48, 0.45, 0.40)),
                (92_000, 117_580, 2.0, (0.86, 0.79, 0.66)), (117_580, 122_170, 0.10, (0.45, 0.42, 0.38)),
                (122_170, 133_410, 0.50, (0.76, 0.71, 0.61)), (133_410, 133_740, 0.0, (0, 0, 0)),
                (133_740, 136_775, 0.50, (0.74, 0.69, 0.60)), (140_130, 140_230, 0.5, (0.7, 0.66, 0.58))]


def args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bodies', default='moon,mars,mercury,earth,venus,sun,system,jupiter,saturn,uranus,neptune')
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


def uv_from_latlon(me, V, lon0_deg, ratio=1.0):
    """Seam-corrected equirect UV per face corner (for Solid / Texture view; renders use the shader lookup)."""
    x, y, z = V[:, 0], V[:, 1], V[:, 2]
    lon = np.degrees(np.arctan2(y, x))
    lat = np.degrees(np.arctan2(ratio * z, np.hypot(x, y)))
    u = ((lon - lon0_deg) % 360.0) / 360.0
    v = lat / 180.0 + 0.5
    vi = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get('vertex_index', vi)
    lu, lv = u[vi].reshape(-1, 4).copy(), v[vi].reshape(-1, 4)
    wrap = (lu.max(axis=1) - lu.min(axis=1)) > 0.5
    lu[wrap] = np.where(lu[wrap] < 0.5, lu[wrap] + 1.0, lu[wrap])
    uvl = me.uv_layers.new(name='equirect')
    uvl.data.foreach_set('uv', np.stack([lu.ravel(), lv.ravel()], 1).astype(np.float32).ravel())


def _tex(nt, path, vector, colorspace=None, extension='REPEAT'):
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = bpy.data.images.load(str(path), check_existing=True)
    if colorspace:
        tx.image.colorspace_settings.name = colorspace
    tx.extension = extension
    nt.links.new(vector, tx.inputs['Vector'])
    return tx


def atmosphere(coll, name, R_km, top_km, H_km, sigma0, colour, anisotropy=0.0):
    """Exponential scattering shell: density sigma0 * exp(-(r - R) / H) per km between R and R + top (MODEL)."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=R_km + top_km)
    ob = bpy.context.active_object
    for c in ob.users_collection:
        c.objects.unlink(ob)
    coll.objects.link(ob)
    ob.name = name
    ob.data.shade_smooth()
    m = bpy.data.materials.new(name + ' | volume')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    vs = nt.nodes.new('ShaderNodeVolumeScatter')
    vs.inputs['Color'].default_value = (*colour, 1)
    vs.inputs['Anisotropy'].default_value = anisotropy
    tc = nt.nodes.new('ShaderNodeTexCoord')
    ln = nt.nodes.new('ShaderNodeVectorMath')
    ln.operation = 'LENGTH'
    nt.links.new(tc.outputs['Object'], ln.inputs[0])
    h = _math(nt, 'MAXIMUM', _math(nt, 'SUBTRACT', ln.outputs['Value'], R_km), 0.0)
    dens = _math(nt, 'MULTIPLY', _math(nt, 'EXPONENT', _math(nt, 'DIVIDE', h, -H_km)), sigma0)
    nt.links.new(dens, vs.inputs['Density'])
    nt.links.new(vs.outputs['Volume'], out.inputs['Volume'])
    m.diffuse_color = (*colour, 0.1)
    ob.data.materials.append(m)
    ob.display_type = 'WIRE'
    return ob


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
    if body == 'mars' and (d / 'colour.json').exists():
        ci = json.loads((d / 'colour.json').read_text())
        tx = _tex(nt, ci['path'], equirect_uv(nt, ci['lon0_deg']))
        nt.links.new(tx.outputs['Color'], bs.inputs['Color'])
        m.name = 'MARS | diffuse | Viking MDIM colour mosaic 925 m (USGS), VISUAL'
        m.diffuse_color = (0.5, 0.5, 0.5, 1)
    elif body == 'mars':
        bs.inputs['Color'].default_value = (*MARS_TINT, 1)
        m.diffuse_color = (*MARS_TINT, 1)
    elif body == 'venus':
        bs.inputs['Color'].default_value = (0.20, 0.17, 0.14, 1)
        m.name = 'VENUS surface | uniform basalt tone (radar has no visible colour), VISUAL'
        m.diffuse_color = (0.20, 0.17, 0.14, 1)
    elif body == 'earth' and (d / 'day_colour.json').exists():
        dc = json.loads((d / 'day_colour.json').read_text())
        tx = _tex(nt, d / 'day_colour.png', equirect_uv(nt, dc['lon0_deg']))
        nt.links.new(tx.outputs['Color'], bs.inputs['Color'])
        m.name = 'EARTH | day: VIIRS true colour 2026-11-16 (real clouds) + Blue Marble fill | night: Black Marble 2016 | VISUAL'
        # night lights on the dark side only (object-space normal . body-fixed Sun direction from SPICE)
        bm = _tex(nt, PROD / 'earth_blackmarble_2016/BlackMarble_2016_3km_gray.jpg', equirect_uv(nt, 180.0), 'Non-Color')
        tc = nt.nodes.new('ShaderNodeTexCoord')
        dp = nt.nodes.new('ShaderNodeVectorMath')
        dp.operation = 'DOT_PRODUCT'
        nt.links.new(tc.outputs['Normal'], dp.inputs[0])
        dp.inputs[1].default_value = tuple(meta['geometry']['sun'])
        night = _math(nt, 'MINIMUM', _math(nt, 'MAXIMUM', _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', 0.05, dp.outputs['Value']), 8.0), 0.0), 1.0)
        em = nt.nodes.new('ShaderNodeEmission')
        em.inputs['Color'].default_value = (1.0, 0.78, 0.45, 1)
        sep = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(bm.outputs['Color'], sep.inputs['Color'])
        lights = _math(nt, 'POWER', sep.outputs['Red'], 2.2)
        nt.links.new(_math(nt, 'MULTIPLY', _math(nt, 'MULTIPLY', lights, night), 40.0), em.inputs['Strength'])
        add = nt.nodes.new('ShaderNodeAddShader')
        nt.links.new(bs.outputs['BSDF'], add.inputs[0])
        nt.links.new(em.outputs['Emission'], add.inputs[1])
        nt.links.new(add.outputs['Shader'], out.inputs['Surface'])
        nt.nodes.active = tx
        m.diffuse_color = (0.5, 0.5, 0.5, 1)
    else:
        path, lon0 = COLOUR[body]
        tx = nt.nodes.new('ShaderNodeTexImage')
        tx.image = bpy.data.images.load(str(path), check_existing=True)
        tx.extension = 'EXTEND'
        nt.links.new(equirect_uv(nt, lon0), tx.inputs['Vector'])
        nt.links.new(tx.outputs['Color'], bs.inputs['Color'])
        m.diffuse_color = (0.5, 0.5, 0.5, 1)
    for n in nt.nodes:                                          # Solid view shows the active image node with the UV map
        if n.type == 'TEX_IMAGE' and 'Black' not in n.image.name and 'height' not in n.image.name:
            nt.nodes.active = n
            break
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
    lon0_uv = {'earth': 180.0, 'mercury': 180.0}.get(body, 0.0)
    if body == 'mars' and (d / 'colour.json').exists():
        lon0_uv = json.loads((d / 'colour.json').read_text())['lon0_deg']
    uv_from_latlon(me, V, lon0_uv)
    extras = []
    if body == 'earth':     # Rayleigh scattering at sea level ~ (5.8, 13.5, 33.1) x 1e-6 /m, scale height 8.5 km (MODEL)
        extras.append(atmosphere(coll, 'EARTH | atmosphere | Rayleigh, H = 8.5 km | MODEL', Rk, 100.0, 8.5, 0.0331,
                                 (0.175, 0.408, 1.0)))
    if body == 'mars':      # dust haze: vertical optical depth ~0.2 (clear season), scale height 11 km, forward scattering (MODEL)
        extras.append(atmosphere(coll, 'MARS | dust haze | tau ~0.2 (clear season), H = 11 km | MODEL', Rk, 70.0, 11.0, 0.018,
                                 (1.0, 0.72, 0.52), anisotropy=0.6))
    deck = None
    if body == 'venus':     # the visible Venus is its cloud deck (~70 km), uniform pale yellow at visible wavelengths
        bpy.ops.mesh.primitive_uv_sphere_add(segments=192, ring_count=96, radius=Rk + 70.0)
        deck = bpy.context.active_object
        for c in deck.users_collection:
            c.objects.unlink(deck)
        coll.objects.link(deck)
        deck.name = 'VENUS | cloud deck at ~70 km (hide it to see the Magellan surface) | VISUAL'
        deck.data.shade_smooth()
        dm = bpy.data.materials.new('Venus cloud tops | diffuse, Bond albedo ~0.77 | VISUAL')
        dm.diffuse_color = (0.92, 0.86, 0.70, 1)
        dm.use_nodes = True
        dm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.92, 0.86, 0.70, 1)
        dm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 1.0
        deck.data.materials.append(dm)
        extras.append(deck)
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
            if deck is not None:
                deck.hide_render = (tag == 'closeup')       # the close-up shows the Magellan surface under the deck
            sc.render.resolution_x, sc.render.resolution_y = (1280, 720) if tag == 'closeup' else (900, 900)
            sc.render.filepath = str(d / f'{body}_hd_{tag}.png')
            bpy.ops.render.render(write_still=True)
        sc.camera = disc
        if deck is not None:
            deck.hide_render = False
    bpy.ops.wm.save_as_mainfile(filepath=str(d / f'{body}_hd.blend'), compress=False)
    print(f'[POLARIS HD] {body}: {len(V)} viewport vertices, map {meta["width"]}x{meta["height"]}, wrote {body}_hd.blend', flush=True)


def giant(body, a):
    """Jupiter, Saturn, Uranus, Neptune: oblate spheroid at the true equatorial / polar radii (1 bar), the OPAL Hubble
    global colour map (System III east longitude from 0 at the left edge, planetographic latitude), Sun from SPICE; Saturn
    with its main rings (MODEL). No surface exists, so no terrain."""
    Ra, Rb, tif, epoch = GIANTS[body]
    geo = json.loads((HD / 'geometry.json').read_text())[body]
    d = HD / body
    d.mkdir(parents=True, exist_ok=True)
    sc = new_file(f'{NAME[body]} globe, true radii')
    coll = bpy.data.collections.new(f'COL_{body}')
    sc.collection.children.link(coll)
    n = 192
    V, F, fid, uv, dropped = cubesphere.mesh(n, np.zeros((6, n + 1, n + 1), np.float32), radius_m=1.0, scale=1.0)
    me = bpy.data.meshes.new(body)
    me.from_pydata(V.tolist(), [], F.tolist())
    me.update()
    me.shade_smooth()
    ratio = Ra / Rb
    uv_from_latlon(me, V, 0.0, ratio)
    ob = bpy.data.objects.new(f'{NAME[body]} | oblate spheroid a = {Ra:,.0f} km, b = {Rb:,.0f} km (1 bar) | {epoch} Hubble map', me)
    ob.scale = (Ra, Ra, Rb)
    coll.objects.link(ob)
    m = bpy.data.materials.new(f'{NAME[body]} | Hubble OPAL {epoch} colour map (clouds of that epoch) | VISUAL')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bs = nt.nodes.new('ShaderNodeBsdfDiffuse')
    nt.links.new(bs.outputs['BSDF'], out.inputs['Surface'])
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs[0])
    X, Y, Z = sep.outputs
    lon = _math(nt, 'MULTIPLY', _math(nt, 'ARCTAN2', Y, X), 180.0 / math.pi)
    u = _math(nt, 'FRACT', _math(nt, 'ADD', _math(nt, 'DIVIDE', lon, 360.0), 2.0))
    rxy = _math(nt, 'SQRT', _math(nt, 'ADD', _math(nt, 'MULTIPLY', X, X), _math(nt, 'MULTIPLY', Y, Y)))
    lat = _math(nt, 'ARCTAN2', _math(nt, 'MULTIPLY', Z, ratio), rxy)        # planetographic from the mesh (parametric) latitude
    v = _math(nt, 'ADD', _math(nt, 'DIVIDE', lat, math.pi), 0.5)
    c = nt.nodes.new('ShaderNodeCombineXYZ')
    nt.links.new(u, c.inputs['X'])
    nt.links.new(v, c.inputs['Y'])
    filled = d / 'map.png'                                   # gap-filled by giants_pack.py (latitude-row medians)
    tx = _tex(nt, filled if filled.exists() else OUTER / tif, c.outputs['Vector'], extension='EXTEND')
    nt.links.new(tx.outputs['Color'], bs.inputs['Color'])
    nt.nodes.active = tx
    m.diffuse_color = (0.6, 0.55, 0.5, 1)
    me.materials.append(m)
    if body == 'saturn':
        rings(coll)
    E = sun_lamp(coll, geo['sun'], geo['sunRangeKm'], 'body-fixed')
    sc.view_settings.exposure = math.log2(0.8 * math.pi / (0.85 * E))       # presentation exposure (VISUAL)
    span = 2.5 * 140_300.0 if body == 'saturn' else 2.1 * Ra
    v_ = Vector(geo['viewer']).normalized()
    disc = camera(coll, f'CAM_{body}_from_Earth', v_ * 20 * Ra, (0, 0, 0), ortho=span, clip=80 * Ra)
    s_ = Vector(geo['sun']).normalized()
    side = (s_ * 0.85 + s_.cross(Vector((0, 0, 1))).normalized() * 0.5).normalized()
    camera(coll, f'CAM_{body}_sunlit_side', side * 20 * Ra, (0, 0, 0), ortho=span, clip=80 * Ra)
    sc.camera = disc
    sc.cycles.samples = a.samples
    sc['polaris'] = json.dumps({'builder': 'blender/v2/globe_hd.py', 'radii_km': [Ra, Rb], 'map': tif, 'geometry': geo})
    if a.qa:
        sc.render.resolution_x = sc.render.resolution_y = 900
        for cam in [o for o in coll.objects if o.type == 'CAMERA']:
            sc.camera = cam
            sc.render.filepath = str(d / f'{body}_{cam.name.split("_", 2)[2]}.png')
            bpy.ops.render.render(write_still=True)
        sc.camera = disc
    bpy.ops.wm.save_as_mainfile(filepath=str(d / f'{body}.blend'), compress=False)
    print(f'[POLARIS HD] {body}: wrote {body}.blend', flush=True)


def rings(coll):
    r0, r1 = SATURN_RINGS[0][0], SATURN_RINGS[-1][1]
    N = 4096
    img = bpy.data.images.new('saturn_ring_profile', N, 1, alpha=True, float_buffer=True)
    px = np.zeros((N, 4), np.float32)
    rr = r0 + (np.arange(N) + 0.5) / N * (r1 - r0)
    for a_, b_, tau, col in SATURN_RINGS:
        k = (rr >= a_) & (rr < b_)
        px[k, :3] = col
        px[k, 3] = tau / 10.0                               # tau stored / 10 in alpha (tau <= 2)
    img.pixels.foreach_set(px.ravel())
    img.pack()
    bpy.ops.mesh.primitive_circle_add(vertices=512, radius=r1, fill_type='NOTHING')
    ob = bpy.context.active_object
    for c in ob.users_collection:
        c.objects.unlink(ob)
    coll.objects.link(ob)
    me = ob.data
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    inner = [bm.verts.new(v.co * (r0 / r1)) for v in list(bm.verts)]
    outer = [v for v in bm.verts if v not in inner]
    nv = len(outer)
    for i in range(nv):
        bm.faces.new((outer[i], outer[(i + 1) % nv], inner[(i + 1) % nv], inner[i]))
    bm.to_mesh(me)
    bm.free()
    ob.name = 'SATURN | main rings D-F (fact-sheet radii, representative optical depths) | MODEL'
    m = bpy.data.materials.new('Saturn rings | 1 - exp(-tau / mu) | MODEL')
    m.use_nodes = True
    m.blend_method = 'BLEND' if hasattr(m, 'blend_method') else None
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    ln = nt.nodes.new('ShaderNodeVectorMath')
    ln.operation = 'LENGTH'
    nt.links.new(tc.outputs['Object'], ln.inputs[0])
    u = _math(nt, 'DIVIDE', _math(nt, 'SUBTRACT', ln.outputs['Value'], r0), r1 - r0)
    cmb = nt.nodes.new('ShaderNodeCombineXYZ')
    nt.links.new(u, cmb.inputs['X'])
    cmb.inputs['Y'].default_value = 0.5
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = img
    tx.interpolation = 'Closest'
    tx.extension = 'EXTEND'
    nt.links.new(cmb.outputs['Vector'], tx.inputs['Vector'])
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    dp = nt.nodes.new('ShaderNodeVectorMath')
    dp.operation = 'DOT_PRODUCT'
    nt.links.new(geo.outputs['Normal'], dp.inputs[0])
    nt.links.new(geo.outputs['Incoming'], dp.inputs[1])
    mu = _math(nt, 'MAXIMUM', _math(nt, 'ABSOLUTE', dp.outputs['Value']), 0.02)
    tau = _math(nt, 'MULTIPLY', tx.outputs['Alpha'], 10.0)
    alpha = _math(nt, 'SUBTRACT', 1.0, _math(nt, 'EXPONENT', _math(nt, 'DIVIDE', _math(nt, 'MULTIPLY', tau, -1.0), mu)))
    df = nt.nodes.new('ShaderNodeBsdfDiffuse')
    nt.links.new(tx.outputs['Color'], df.inputs['Color'])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(alpha, mix.inputs['Fac'])
    nt.links.new(tr.outputs['BSDF'], mix.inputs[1])
    nt.links.new(df.outputs['BSDF'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    m.diffuse_color = (0.8, 0.75, 0.62, 1)
    me.materials.append(m)


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
            dst.objects = [n for n in src.objects if n.startswith(NAME[body] + ' |')]   # globe + atmosphere
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
        if b in GIANTS:
            giant(b, a)
        elif b in NAME:
            globe(b, a)
        elif b == 'sun':
            sun_scene(a)
        elif b == 'system':
            system_scene(a)


if __name__ == '__main__':
    main()
