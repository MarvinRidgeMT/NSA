"""POLARIS X v2 — scripted Blender scene for one lunar point, time and camera.

    blender -b --python-exit-code 1 -P blender/v2/build_scene.py -- \
        --world moon --lat -89.47409 --lon -137.3813 --utc 2026-11-14T00:00Z --camera eva_eye

Blender is read-only with respect to science. blender/v2/spec.py resolves every number (Sun/Earth direction, angular size,
range, phase, earthshine, sight-line states, skyline, star orientation, camera optics, exposure) from the solver bundle and
published constants; this script only turns the spec into objects, renders, and writes:
    <out>/<tag>.blend, <tag>_spec.json, <tag>_manifest.json, <tag>.png, optional <tag>.glb
Labels: terrain SOURCE-BASED · UNVALIDATED; assets ILLUSTRATIVE; photometry, earthshine MODEL; stars VISUAL.
"""
import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from v2 import albedo, cameras, hapke, spec as specmod, terrain as T  # noqa: E402
from v2 import hapke_nodes  # noqa: E402

ROOT = HERE.parents[1]
SKY_DIST_M = 1.0e6                 # Sun disc and Earth sphere distance in the scene (angular sizes are true; distance is not)
STAR_MAP = ROOT / 'data' / 'cache' / 'v2' / 'blender' / 'svs4851' / 'starmap_2020_4k.exr'
STAR_MAP_SHA256 = '69b841cd048c2ef35543eb1c5819b322530e78aa4b0cab97ec1de3ef56a4ddcd'
STAR_MAP_URL = 'https://svs.gsfc.nasa.gov/vis/a000000/a004800/a004851/starmap_2020_4k.exr'
EARTH_LAMBERT_ALBEDO = 0.55        # Lambert sphere with geometric albedo 0.367 (p = 2/3 A)
COMMITTED_TERRAIN = {'site01': ('app/data/polaris-source-site01-2026-11-14-v2.json', 'connecting')}


def parse(argv=None):
    if argv is None:
        argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--world', default='moon', choices=['moon'])
    p.add_argument('--lat', type=float, required=True)
    p.add_argument('--lon', type=float, required=True)
    p.add_argument('--utc', required=True)
    p.add_argument('--camera', default='eva_eye', choices=sorted(cameras.PRESETS))
    p.add_argument('--bundle', default=None, help='solver bundle (default: the one whose site matches --lat/--lon)')
    p.add_argument('--mast', type=float, default=None)
    p.add_argument('--look-az', type=float, default=None)
    p.add_argument('--look-el', type=float, default=None)
    p.add_argument('--emission', type=float, default=0.0, help='orbital cameras: emission angle off nadir (deg)')
    p.add_argument('--alt-km', type=float, default=None)
    p.add_argument('--layout', default=None, choices=sorted(specmod.ASSET_LAYOUTS))
    p.add_argument('--terrain', default='cache', choices=['cache', 'committed', 'stack'],
                   help='cache: the solver DEM cache; committed: the 80 m crop in git (site01 only); stack: S3 global pyramid '
                        '(via blender/v2/pack.py in the project venv; run automatically when the pack is missing)')
    p.add_argument('--pack', default=None, help='--terrain stack: use this pack directory instead of building/looking one up')
    p.add_argument('--near-half', type=float, default=None, help='--terrain stack: near window half-width (m); default min(25 km, 1600 px)')
    p.add_argument('--mid-half', type=float, default=None, help='--terrain stack: optional middle window half-width (m), e.g. 100000')
    p.add_argument('--mid-res', type=float, default=None, help='--terrain stack: middle window posting (m), default 20')
    p.add_argument('--albedo', default='wac', choices=['wac', 'none'],
                   help='wac: Hapke w per vertex from the LROC WAC 643 nm map (70N-70S; regional median poleward); none: regional constant')
    p.add_argument('--hapke-region', default='SOUTH_60_70', choices=sorted(hapke.PARAMS_643NM),
                   help='constant Hapke b, c, B_S0, h_S (and w with --albedo none); unchanged default')
    p.add_argument('--micro-relief', type=float, default=0.0,
                   help='VISUAL sub-resolution relief: Cycles displacement of this amplitude (m) from a noise texture; 0 = off (default)')
    p.add_argument('--resolution', type=int, default=512, help='longest image side (px)')
    p.add_argument('--samples', type=int, default=32)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--device', default='CPU', choices=['CPU', 'GPU'])
    p.add_argument('--denoise', action='store_true')
    p.add_argument('--ev-comp', type=float, default=0.0, help='exposure compensation in stops on top of the physical exposure (recorded)')
    p.add_argument('--budget', type=int, default=2_500_000, help='terrain vertex budget')
    p.add_argument('--all-around', action='store_true', help='plan every terrain tile as in view at --all-around-deg angular pixel (skyline check)')
    p.add_argument('--all-around-deg', type=float, default=0.05, help='angular pixel (deg) for --all-around')
    p.add_argument('--no-stars', action='store_true')
    p.add_argument('--overlays', dest='overlays', action='store_true', default=None)
    p.add_argument('--no-overlays', dest='overlays', action='store_false')
    p.add_argument('--glb', action='store_true', help='also export the near terrain + assets as GLB (Draco)')
    p.add_argument('--no-render', action='store_true')
    p.add_argument('--out', default='blender/output/v2')
    p.add_argument('--tag', default=None)
    return p.parse_args(argv)


# ---------------------------------------------------------------- helpers
def collection(scene, name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c


def put(ob, coll):
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    coll.objects.link(ob)
    return ob


def camera_only(ob):
    """Overlay or sky object: seen by the camera, never lights, shadows or reflects into the scene."""
    for a in ('visible_diffuse', 'visible_glossy', 'visible_transmission', 'visible_volume_scatter', 'visible_shadow'):
        setattr(ob, a, False)
    return ob


def emissive(name, rgb, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    e = nt.nodes.new('ShaderNodeEmission')
    e.inputs['Color'].default_value = (*rgb, 1)
    e.inputs['Strength'].default_value = strength
    o = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(e.outputs[0], o.inputs['Surface'])
    return m


def diffuse(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    d = nt.nodes.new('ShaderNodeBsdfDiffuse')
    d.inputs['Color'].default_value = (*rgb, 1)
    o = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(d.outputs[0], o.inputs['Surface'])
    m.diffuse_color = (*rgb, 1)
    return m


def mesh_object(name, V, F, coll, mat=None, smooth=True):
    me = bpy.data.meshes.new(name)
    V = np.asarray(V, dtype=np.float32)
    F = np.asarray(F, dtype=np.int32)
    me.vertices.add(len(V))
    me.vertices.foreach_set('co', V.ravel())
    me.loops.add(F.size)
    me.loops.foreach_set('vertex_index', F.ravel())
    me.polygons.add(len(F))
    me.polygons.foreach_set('loop_start', np.arange(0, F.size, F.shape[1], dtype=np.int32))
    me.update(calc_edges=True)
    if smooth:
        me.polygons.foreach_set('use_smooth', np.ones(len(F), dtype=bool))
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if mat:
        me.materials.append(mat)
    return ob


def sphere(name, radius, location, coll, mat, segs=64):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segs, ring_count=segs // 2, radius=radius, location=location)
    ob = put(bpy.context.object, coll)
    ob.name = name
    ob.data.materials.append(mat)
    for poly in ob.data.polygons:
        poly.use_smooth = True
    return ob


def cylinder(name, radius, z0, z1, xy, coll, mat, verts=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=z1 - z0, location=(xy[0], xy[1], (z0 + z1) / 2))
    ob = put(bpy.context.object, coll)
    ob.name = name
    ob.data.materials.append(mat)
    return ob


def aim(ob, direction, track='-Z', up='Y'):
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = Vector(direction).normalized().to_track_quat(track, up)


def sun_lamp(name, direction, strength, angle_deg, coll):
    """SUN lamps shine along their local -Z: +Z points TOWARD the source."""
    ld = bpy.data.lights.new(name, type='SUN')
    ld.energy = strength
    ld.angle = math.radians(angle_deg)
    ld.color = (1.0, 1.0, 1.0)
    ob = bpy.data.objects.new(name, ld)
    coll.objects.link(ob)
    aim(ob, direction, track='Z')
    return ob


# ---------------------------------------------------------------- terrain
def project_python():
    """The project venv's Python (has rasterio for the pyramid): $POLARIS_PYTHON, else the nearest .venv up the tree."""
    env = os.environ.get('POLARIS_PYTHON')
    if env:
        return env
    for d in [ROOT, *ROOT.parents]:
        c = d / '.venv' / 'bin' / 'python'
        if c.exists():
            return str(c)
    raise SystemExit('--terrain stack needs the project venv (rasterio); set POLARIS_PYTHON')


def ensure_site_pack(lat, lon, site_id, near_half=None, skyline=False, mid_half=None, mid_res=None):
    """Run blender/v2/pack.py site (returns at once when the pack exists) and return its directory."""
    import subprocess
    cmd = [project_python(), str(HERE / 'pack.py'), 'site', '--lat', repr(lat), '--lon', repr(lon), '--id', str(site_id)]
    if near_half:
        cmd += ['--near-half', repr(near_half)]
    if mid_half:
        cmd += ['--mid-half', repr(mid_half), '--mid-res', repr(mid_res or 20.0)]
    if skyline:
        cmd += ['--skyline']
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    if r.returncode != 0:
        raise SystemExit(f'pack.py failed ({r.returncode}):\n{r.stderr[-2000:]}')
    return Path(json.loads(r.stdout.strip().splitlines()[-1])['pack'])


def load_levels(sp, mode, cfg_pack=None, near_half=None, mid_half=None, mid_res=None):
    site = sp['site']['id']
    if mode == 'committed':
        key = site.split('_')[0]
        if key not in COMMITTED_TERRAIN or site != key:
            raise SystemExit(f'--terrain committed exists only for {sorted(COMMITTED_TERRAIN)} (the only DEM crop in git)')
        f, ds = COMMITTED_TERRAIN[key]
        return [T.load_bundle_v2_level(ROOT / f, ds, name=f'committed PGDA 90 80 m crop ({ds})')]
    if mode == 'stack':
        pack_dir = Path(cfg_pack) if cfg_pack else ensure_site_pack(sp['site']['latDeg'], sp['site']['lonEastDeg'], site, near_half,
                                                                    mid_half=mid_half, mid_res=mid_res)
        levels, meta = T.load_pack_levels(pack_dir)
        for lv in levels:
            lv.info['packId'] = meta['id']
        return levels
    cache = ROOT / 'data' / 'cache'
    near, far = cache / f'{site}_p78_p78.npy', cache / f'{site}_ldem80_290km.npy'
    levels = []
    if near.exists():
        levels.append(T.load_cache_level(near, 'near PGDA 78 5 m'))
    if far.exists():
        levels.append(T.load_cache_level(far, 'far PGDA 90 LDEM_80S 80 m'))
    if not levels:
        raise SystemExit(f'no cached DEM for {site} under {cache} (expected {near.name}, {far.name}); use --terrain committed for site01')
    return levels


def build_terrain(sp, levels, frame, view, coll, hapke_params, light_dir, budget, all_around=False, albedo_mode='wac',
                  hapke_region='SOUTH_60_70', micro_relief_m=0.0):
    """Terrain meshes + the Hapke material. With albedo 'wac' each vertex carries attribute polaris_w (Hapke w from the WAC map,
    blender/v2/albedo.py); when every vertex is poleward of 70.5 S the constant material is used exactly as before."""
    tiles, report = T.plan_tiles(levels, frame, view, budget=budget, all_around=all_around)
    built = []
    for li, lv in enumerate(levels):
        finer = [levels[j].box() for j in range(li)]
        Vs, Fs, base, dropped = [], [], 0, 0
        for t in tiles:
            if t['level'] != li:
                continue
            V, F, d = T.tile_mesh(lv, t, frame, finer)
            if len(F) == 0:
                continue
            Vs.append(V)
            Fs.append(F + base)
            base += len(V)
            dropped += d
        if not Vs:
            continue
        built.append((lv, np.vstack(Vs), np.vstack(Fs), dropped))
    ws, alb = [], {'mode': albedo_mode}
    if albedo_mode == 'wac':
        wmap = None
        for lv, V, F, _ in built:
            la, lo = frame.enu_to_latlon_deg(V)
            w, info = albedo.w_for_points(la, lo, wmap=wmap, region=hapke_region)
            if info['mode'] == 'per-vertex' and wmap is None:
                wmap = albedo.WMap.load()
            ws.append(w)
            alb[lv.name] = {k: v for k, v in info.items() if k in ('mode', 'w', 'wMin', 'wMax', 'wMedian')}
            if info['mode'] == 'per-vertex':
                alb['map'] = {k: v for k, v in info.items() if k not in ('mode', 'w', 'wMin', 'wMax', 'wMedian')}
    per_vertex = albedo_mode == 'wac' and any(alb.get(lv.name, {}).get('mode') == 'per-vertex' for lv, *_ in built)
    alb['perVertex'] = per_vertex
    alb['label'] = albedo.LABEL if per_vertex else f'regional constant w = {hapke_params["w"]} ({hapke_region})'
    name = 'Regolith | Hapke 2012, LROC WAC 643 nm params' + (' | w per vertex (WAC map)' if per_vertex else '') + ' | MODEL'
    mat, mat_info = hapke_nodes.hapke_material(name, hapke_params, light_dir, w_attribute='polaris_w' if per_vertex else None)
    if micro_relief_m > 0:
        mat_info['microRelief'] = add_micro_relief(mat, micro_relief_m)
    objs, stats = [], {}
    for k, (lv, V, F, dropped) in enumerate(built):
        label = ' | micro-relief VISUAL' if micro_relief_m > 0 else ''
        ob = mesh_object(f'TERRAIN | {lv.name} | SOURCE-BASED UNVALIDATED | ENU metres{label}', V, F, coll, mat)
        if per_vertex:
            at = ob.data.attributes.new('polaris_w', 'FLOAT', 'POINT')
            at.data.foreach_set('value', np.asarray(ws[k], dtype=np.float32))
        ob['polaris_level'] = json.dumps(lv.describe())
        objs.append(ob)
        stats[lv.name] = {'vertices': int(len(V)), 'faces': int(len(F)), 'cellsLeftToFinerOrNaN': dropped}
    report['meshes'] = stats
    return objs, report, mat_info, alb


def add_micro_relief(mat, amplitude_m, scale_m=2.0):
    """VISUAL sub-resolution relief: Cycles displacement (method DISPLACEMENT_AND_BUMP) from a fractal noise texture in object
    space, amplitude metres. Not data; never used by any check (Blender ray casts and the solver ignore it)."""
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 1.0 / scale_m
    nz.inputs['Detail'].default_value = 6.0
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    dp = nt.nodes.new('ShaderNodeDisplacement')
    dp.inputs['Midlevel'].default_value = 0.5
    dp.inputs['Scale'].default_value = amplitude_m
    nt.links.new(nz.outputs['Fac'], dp.inputs['Height'])
    nt.links.new(dp.outputs['Displacement'], out.inputs['Displacement'])
    mat.displacement_method = 'BOTH'
    return {'label': 'VISUAL (synthetic, not data)', 'amplitudeM': amplitude_m, 'noiseScaleM': scale_m, 'method': 'Cycles displacement + bump'}


# ---------------------------------------------------------------- world: black space + stars
def build_world(scene, sp, use_stars):
    world = bpy.data.worlds.new('Space (airless)')
    world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputWorld')
    info = {'background': 'black (no atmosphere, no fill light)', 'stars': {'present': False}}
    if use_stars and STAR_MAP.exists():
        tc = nt.nodes.new('ShaderNodeTexCoord')
        M = sp['stars']['icrfToEnu']          # rows: ENU axes in ICRF -> icrf = M^T enu
        # texture vector = the ICRF direction itself: Cycles' equirect lookup is u = 0.5 - atan2(y, x) / 2 pi, and the SVS map
        # has RA 0 at the centre increasing to the left (u = 0.5 - RA/360), so (X, Y, Z)_ICRF maps straight onto it.
        # Checked by blender/tests/star_check.py (LMC/SMC and Canopus/Achernar land where the spec predicts).
        rows = [[M[0][0], M[1][0], M[2][0]], [M[0][1], M[1][1], M[2][1]], [M[0][2], M[1][2], M[2][2]]]
        comb = nt.nodes.new('ShaderNodeCombineXYZ')
        for k, r in enumerate(rows):
            dn = nt.nodes.new('ShaderNodeVectorMath')
            dn.operation = 'DOT_PRODUCT'
            nt.links.new(tc.outputs['Generated'], dn.inputs[0])
            dn.inputs[1].default_value = r
            nt.links.new(dn.outputs['Value'], comb.inputs[k])
        env = nt.nodes.new('ShaderNodeTexEnvironment')
        env.image = bpy.data.images.load(str(STAR_MAP))
        env.image.colorspace_settings.name = 'Linear Rec.709'
        env.interpolation = 'Closest'
        nt.links.new(comb.outputs[0], env.inputs['Vector'])
        bg = nt.nodes.new('ShaderNodeBackground')
        # VISUAL brightness: the SVS map is display-scaled (bright stars clip at 1.0; no flux units given), so pixel 1.0 is set
        # to the radiance of a V = 1 star filling one equatorial map pixel.
        from v2 import astro
        pix_sr = (2 * math.pi / 4096) * (math.pi / 2048)
        strength = astro.star_irradiance_w_m2(1.0) / pix_sr
        bg.inputs['Strength'].default_value = strength
        nt.links.new(env.outputs['Color'], bg.inputs['Color'])
        black = nt.nodes.new('ShaderNodeBackground')
        black.inputs['Color'].default_value = (0, 0, 0, 1)
        lp = nt.nodes.new('ShaderNodeLightPath')
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
        nt.links.new(black.outputs[0], mix.inputs[1])
        nt.links.new(bg.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
        info['stars'] = {'present': True, 'file': STAR_MAP.name, 'url': STAR_MAP_URL, 'sha256': STAR_MAP_SHA256,
                         'credit': 'NASA/Goddard Space Flight Center Scientific Visualization Studio. Gaia DR2: ESA/Gaia/DPAC',
                         'strengthPerUnitPixel': strength, 'cameraRaysOnly': True,
                         'brightness': 'VISUAL: pixel 1.0 = V=1 star in one map pixel (map is display-scaled, clips at 1.0)',
                         'orientation': 'MODEL: ICRF->ENU by TRIAD (IAU 2009 pole + almanac Sun vs Horizons Sun)',
                         'orientationCheckDeg': sp['stars']['check']['differenceDeg']}
    else:
        bg = nt.nodes.new('ShaderNodeBackground')
        bg.inputs['Color'].default_value = (0, 0, 0, 1)
        nt.links.new(bg.outputs[0], out.inputs['Surface'])
        if use_stars:
            info['stars'] = {'present': False, 'reason': f'{STAR_MAP} not in the cache (download: {STAR_MAP_URL})'}
    scene.world = world
    return info


# ---------------------------------------------------------------- main
def build(cfg):
    t_start = time.time()
    layout = cfg.layout or ('research' if cfg.camera == 'lander_cam' else 'single')
    sp = specmod.build_spec(cfg.lat, cfg.lon, cfg.utc, camera=cfg.camera, bundle=cfg.bundle, mast=cfg.mast, look_az=cfg.look_az,
                            look_el=cfg.look_el, emission_deg=cfg.emission, altitude_m=(cfg.alt_km * 1000 if cfg.alt_km else None),
                            layout=layout, resolution=cfg.resolution, samples=cfg.samples, seed=cfg.seed, device=cfg.device,
                            terrain=cfg.terrain, overlays=cfg.overlays, stars=not cfg.no_stars, hapke_region=cfg.hapke_region)
    tag = cfg.tag or f"v2_{sp['site']['id']}_{sp['sample']['utc'][:13].replace('-', '').replace(':', '')}_{cfg.camera}"
    out = Path(cfg.out)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system, scene.unit_settings.scale_length = 'METRIC', 1.0
    C = {n: collection(scene, n) for n in ('POLARIS Terrain', 'POLARIS Sky', 'POLARIS Assets (ILLUSTRATIVE)', 'POLARIS Overlays', 'POLARIS Cameras')}

    # --- terrain -----------------------------------------------------------------------------------------------------
    t0 = time.time()
    levels = load_levels(sp, cfg.terrain, cfg.pack, cfg.near_half, cfg.mid_half, cfg.mid_res)
    south_grid = levels[0].proj == 'sp'
    gx, gy = sp['site']['gridXM'], sp['site']['gridYM']
    if gx is None or not south_grid:
        gx, gy = T.stereo_forward(sp['site']['latDeg'], sp['site']['lonEastDeg'])
    if south_grid:
        h0, h_src = T.ground_height(levels, gx, gy)
    else:
        h0, h_src, _ = T.ground_height_latlon(levels, sp['site']['latDeg'], sp['site']['lonEastDeg'])
    if not math.isfinite(h0):
        raise SystemExit(f'no terrain height at the site ({sp["site"]["latDeg"]}, {sp["site"]["lonEastDeg"]})')
    frame = T.EnuFrame(sp['site']['latDeg'], sp['site']['lonEastDeg'], h0)
    cam_p = sp['camera']
    lay = cam_p['layout']
    rx, ry = lay['resolution']
    sensor = lay['sensor_mm']
    half_h = math.atan(sensor / 2 / cam_p['focal_mm'])
    half_v = math.atan(sensor * ry / rx / 2 / cam_p['focal_mm'])
    view = T.View(pos=tuple(cam_p['pose']['posEnu']), fwd=tuple(cam_p['pose']['lookDir']), half_h=half_h, half_v=half_v,
                  pixel_rad=2 * half_h / rx, sun_dir=tuple(sp['sun']['dirEnu']), sun_radius_rad=math.radians(sp['sun']['radiusDeg']))
    light = sp['sun'] if sp['dominantLight'] == 'sun' else sp['earth']
    if cfg.all_around:
        view.pixel_rad = math.radians(cfg.all_around_deg)
    terrain_objs, tile_report, mat_info, albedo_info = build_terrain(
        sp, levels, frame, view, C['POLARIS Terrain'], sp['photometry']['params'], light['dirEnu'], cfg.budget, cfg.all_around,
        cfg.albedo, cfg.hapke_region, cfg.micro_relief)
    t_terrain = time.time() - t0

    # --- Sun, Earth, earthshine, sky -----------------------------------------------------------------------------------
    sun, earth = sp['sun'], sp['earth']
    sun_obj = sun_lamp('Sun | Horizons direction, true angular diameter, 1361/r^2 W/m^2', sun['dirEnu'],
                       sun['irradianceWm2'] if sun['lampOn'] else 0.0, sun['discAngleDeg'], C['POLARIS Sky'])
    es_obj = sun_lamp('Earthshine | from Earth direction, scaled by phase x albedo | MODEL', earth['dirEnu'],
                      earth['earthshineIrradianceWm2'] if earth['lampOn'] else 0.0, 2 * earth['radiusDeg'], C['POLARIS Sky'])
    sun_rad = SKY_DIST_M * math.tan(math.radians(sun['radiusDeg']))
    sun_radiance = sun['irradianceWm2'] / (math.pi * math.sin(math.radians(sun['radiusDeg'])) ** 2)
    disc = sphere('Sun disc | true direction + angular size (distance not to scale)', sun_rad,
                  tuple(SKY_DIST_M * c for c in sun['dirEnu']), C['POLARIS Sky'], emissive('Sun photosphere (mean radiance)', (1, 1, 1), sun_radiance), 48)
    camera_only(disc)
    e_rad = SKY_DIST_M * math.tan(math.radians(earth['radiusDeg']))
    earth_obj = sphere('Earth | true direction + angular size, lit by the Sun lamp (phase) | VISUAL albedo', e_rad,
                       tuple(SKY_DIST_M * c for c in earth['dirEnu']), C['POLARIS Sky'], diffuse('Earth Lambert albedo 0.55', (EARTH_LAMBERT_ALBEDO,) * 3), 96)
    for a in ('visible_diffuse', 'visible_glossy', 'visible_transmission', 'visible_volume_scatter', 'visible_shadow'):
        setattr(earth_obj, a, False)     # earthshine is the lamp, not a bounce; the Earth never shadows the scene (no eclipses)
    world_info = build_world(scene, sp, not cfg.no_stars)

    # --- assets (ILLUSTRATIVE) -----------------------------------------------------------------------------------------
    lon = sp['site']['lonEastDeg']
    asset_info = []
    gmat = diffuse('Asset | ILLUSTRATIVE grey', (0.55, 0.55, 0.55))
    foil = diffuse('Asset | ILLUSTRATIVE gold foil', (0.7, 0.5, 0.15))

    def ground_enu(e, n):
        """z of the drawn ground at ENU (e, n), non-south-polar grids (lat/lon placement)."""
        la, lo = frame.offset_latlon_deg(e, n)
        h, _, _ = T.ground_height_latlon(levels, la, lo)
        return float(frame.from_latlon_rad(np.radians([la]), np.radians([lo]), np.array([h]))[0][2])

    def ground_at(dx, dy):
        """Layout offsets are south-polar grid metres (science/cube/build_assets.py); elsewhere they are read as (east, north) m."""
        if not south_grid:
            return (dx, dy), ground_enu(dx, dy)
        h, _ = T.ground_height(levels, gx + dx, gy + dy)
        e, n = specmod.grid_offset_to_enu(dx, dy, lon)
        return (e, n), frame.from_grid(np.array([gx + dx]), np.array([gy + dy]), np.array([h]))[0][2]

    cfgA = sp['assets']['config']
    for b in cfgA['bodies']:
        (e, n), z = ground_at(*b['xy'])
        ob = cylinder(f"ASSET | {b['name']} | r {b['r']} m top {b['top']} m | ILLUSTRATIVE", b['r'], z, z + b['top'], (e, n),
                      C['POLARIS Assets (ILLUSTRATIVE)'], foil if 'lander' in b['name'] else gmat)
        asset_info.append({'name': b['name'], 'enu': [e, n, z], 'r': b['r'], 'top': b['top']})
    for role in ('array', 'antenna') if layout != 'single' else ():
        (dx, dy), hgt = cfgA[role]
        (e, n), z = ground_at(dx, dy)
        ob = cylinder(f'ASSET | {role} mast to {hgt} m | ILLUSTRATIVE', 0.05, z, z + hgt, (e, n), C['POLARIS Assets (ILLUSTRATIVE)'], gmat, 12)
        if role == 'antenna':
            bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=0.45, radius2=0.05, depth=0.25, location=(e, n, z + hgt))
            dish = put(bpy.context.object, C['POLARIS Assets (ILLUSTRATIVE)'])
            dish.name = 'ASSET | antenna dish (pointed at the bundle Earth direction) | ILLUSTRATIVE'
            dish.data.materials.append(gmat)
            aim(dish, earth['dirEnu'], track='Z')
        else:
            bpy.ops.mesh.primitive_plane_add(size=1.2, location=(e, n, z + hgt))
            panel = put(bpy.context.object, C['POLARIS Assets (ILLUSTRATIVE)'])
            panel.name = 'ASSET | solar array panel (faces the bundle Sun azimuth) | ILLUSTRATIVE'
            panel.data.materials.append(diffuse('Array cells', (0.05, 0.07, 0.15)))
            aim(panel, (sun['dirEnu'][0], sun['dirEnu'][1], 0.0), track='Z')
        asset_info.append({'name': role, 'enu': [e, n, z], 'heightM': hgt})
    mast = sp['site']['mastM']
    cylinder(f'ASSET | observer mast {mast} m (bundle observer height) | ILLUSTRATIVE', 0.04, 0.0, mast, (0, 0), C['POLARIS Assets (ILLUSTRATIVE)'], gmat, 12)

    # --- overlays: sight lines + skyline from the bundle ---------------------------------------------------------------
    overlay_info = {'present': bool(sp['overlays'])}
    if sp['overlays']:
        top = Vector((0, 0, mast))
        glow = 0.6 / (2.0 ** (cam_p['exposureStops'] + cfg.ev_comp))     # overlay radiance that lands at ~0.6 of full scale at this exposure
        overlay_info['rays'] = {}
        for name, body, rgb in (('sun', sun, (1.0, 0.75, 0.3)), ('earth', earth, (0.35, 0.7, 1.0))):
            sl = sp['sightLines'][name]
            if body['elDeg'] < -body['radiusDeg']:
                overlay_info['rays'][name] = 'not drawn: body below the mathematical horizon (bundle el %.3f deg)' % body['elDeg']
                continue
            overlay_info['rays'][name] = 'drawn'
            length = sl['lengthM'] or 20000.0
            d = Vector(body['dirEnu'])
            col = rgb if sl['state'] == 'clear' else tuple(0.4 * c for c in rgb)
            # cone: ~0.01 m at the mast top, widening to a constant ~0.02 deg seen from the observer
            bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=0.01, radius2=max(0.01, length * 3.5e-4), depth=length,
                                            location=top + d * (length / 2))
            ray = put(bpy.context.object, C['POLARIS Overlays'])
            ray.name = f"OVERLAY | {name} sight line | bundle state {sl['state']}" + (f" | ends at {sl['criticalDistanceM']} m" if sl['lengthM'] else '')
            aim(ray, d, track='Z')
            ray.data.materials.append(emissive(f'{name} ray', col, glow))
            camera_only(ray)
        az, el, dist = sp['skyline']['azimuthDeg'], sp['skyline']['elevationDeg'], sp['skyline']['criticalDistanceM']
        cu = bpy.data.curves.new('skyline', type='CURVE')
        cu.dimensions = '3D'
        cu.bevel_depth = 1.0
        run = []
        def flush():
            if len(run) > 1:
                spl = cu.splines.new('POLY')
                spl.points.add(len(run) - 1)
                for pnt, (c, rad) in zip(spl.points, run):
                    pnt.co = (*c, 1.0)
                    pnt.radius = rad
            run.clear()
        for a_, e_, d_ in zip(az, el, dist):
            if e_ is None or not d_:
                flush()
                continue
            R = 0.97 * d_ / max(math.cos(math.radians(e_)), 1e-6)
            from v2 import astro
            v = astro.enu_direction(a_, e_)
            run.append(((v[0] * R, v[1] * R, mast + v[2] * R), R * 3.5e-4))   # constant ~0.02 deg half-width
        flush()
        sk = bpy.data.objects.new('OVERLAY | bundle skyline (720 bins, 0.97 x critical distance, from mast-top height)', cu)
        C['POLARIS Overlays'].objects.link(sk)
        cu.bevel_depth = 1.0      # x per-point radius
        sk.data.materials.append(emissive('skyline', (0.9, 0.9, 0.85), glow * 0.6))
        camera_only(sk)
        overlay_info.update(sightLines=sp['sightLines'], skyline='bundle bins drawn at 0.97 x critical distance (true angles from the mast top)')

    # --- camera --------------------------------------------------------------------------------------------------------
    cd = bpy.data.cameras.new(cam_p['label'])
    cd.lens = cam_p['focal_mm']
    cd.sensor_fit = 'HORIZONTAL'
    cd.sensor_width = sensor
    cd.clip_start = 0.05 if cam_p['kind'] == 'surface' else 100.0
    cd.clip_end = SKY_DIST_M * 1.5
    cam = bpy.data.objects.new(f"CAMERA | {cam_p['name']}", cd)
    C['POLARIS Cameras'].objects.link(cam)
    pos = Vector(cam_p['pose']['posEnu'])
    if cam_p['kind'] == 'surface':
        (gx_ofs, gy_ofs) = (0.0, 0.0)
        # stand on the drawn ground at the camera's (east, north): z = local ground + height
        e, n = pos.x, pos.y
        if south_grid:
            L = math.radians(lon)
            dx, dy = e * math.cos(L) + n * math.sin(L), -e * math.sin(L) + n * math.cos(L)
            h, _ = T.ground_height(levels, gx + dx, gy + dy)
            z = frame.from_grid(np.array([gx + dx]), np.array([gy + dy]), np.array([h]))[0][2]
        else:
            z = ground_enu(e, n)
        pos.z = z + cam_p['height_m']
    cam.location = pos
    aim(cam, cam_p['pose']['lookDir'], track='-Z', up='Y' if cam_p['kind'] == 'surface' else 'Y')
    if cam_p['kind'] != 'surface':
        cam.rotation_mode = 'QUATERNION'
        cam.rotation_quaternion = Vector(cam_p['pose']['lookDir']).to_track_quat('-Z', 'Y')
    scene.camera = cam

    # --- render settings -----------------------------------------------------------------------------------------------
    scene.render.engine = 'CYCLES'
    cyc = scene.cycles
    cyc.samples = sp['render']['samples']
    cyc.seed = sp['render']['seed']
    cyc.use_denoising = bool(cfg.denoise)
    cyc.use_adaptive_sampling = False
    cyc.max_bounces, cyc.diffuse_bounces, cyc.glossy_bounces = 4, 2, 0
    cyc.transmission_bounces = cyc.volume_bounces = cyc.transparent_max_bounces = 0
    cyc.sample_clamp_indirect = 0.0
    if cfg.device == 'GPU':
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'METAL'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        cyc.device = 'GPU'
    else:
        cyc.device = 'CPU'
    scene.render.resolution_x, scene.render.resolution_y = rx, ry
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    vs = scene.view_settings
    raw = cam_p['kind'] == 'instrument'
    vs.view_transform = 'Raw' if raw else 'Standard'
    vs.look = 'None'
    vs.exposure = cam_p['exposureStops'] + cfg.ev_comp
    vs.gamma = 1.0
    scene.display_settings.display_device = 'sRGB'
    ims = scene.render.image_settings
    ims.file_format = 'PNG'
    ims.color_mode = 'BW' if raw else 'RGB'
    ims.color_depth = '16' if raw else '8'
    ims.compression = 90

    renders = []
    png = out / f'{tag}.png'
    t_render = None
    if not cfg.no_render:
        scene.render.filepath = str(png)
        t1 = time.time()
        bpy.ops.render.render(write_still=True)
        t_render = time.time() - t1
        renders.append({'png': png.name, 'sha256': specmod.sha256_file(png), 'seconds': round(t_render, 2), 'resolution': [rx, ry]})

    # --- provenance in the file, .blend, optional GLB, manifest --------------------------------------------------------
    spec_path = out / f'{tag}_spec.json'
    spec_path.write_text(json.dumps(sp, indent=1))
    spec_sha = specmod.sha256_file(spec_path)
    scripts = {p.name: specmod.sha256_file(p) for p in sorted(HERE.glob('*.py'))}
    scene['polaris'] = json.dumps({'builder': 'blender/v2/build_scene.py', 'tag': tag, 'specSha256': spec_sha,
                                   'scriptsSha256': scripts, 'blender': bpy.app.version_string,
                                   'labels': sp['labels']})
    blend = out / f'{tag}.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
    glb_info = None
    if cfg.glb:
        glb = out / f'{tag}.glb'
        bpy.ops.object.select_all(action='DESELECT')
        for ob in terrain_objs[:1] + list(C['POLARIS Assets (ILLUSTRATIVE)'].objects):
            ob.select_set(True)
        bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True, export_extras=True,
                                  export_yup=True, export_apply=True, export_animations=False, export_lights=False,
                                  export_draco_mesh_compression_enable=True)
        glb_info = {'file': glb.name, 'sha256': specmod.sha256_file(glb), 'bytes': glb.stat().st_size,
                    'contains': 'finest terrain level mesh + ILLUSTRATIVE assets; scenes[0].extras.polaris = build provenance'}
    manifest = {
        'schema': 'polaris-blender-v2-manifest-v1',
        'generatedUtc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'blenderVersion': bpy.app.version_string,
        'blenderBuildHash': bpy.app.build_hash.decode() if isinstance(bpy.app.build_hash, bytes) else str(bpy.app.build_hash),
        'command': 'blender -b -P blender/v2/build_scene.py -- ' + ' '.join(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []),
        'scriptsSha256': scripts,
        'inputs': {'bundle': {'file': sp['bundle']['file'], 'sha256': sp['bundle']['sha256']},
                   'terrainLevels': [lv.describe() for lv in levels],
                   'hapkeMap': {'url': hapke.PDS_URL, 'sha256': hapke.PDS_SHA256, 'note': 'regional constants compiled into blender/v2/hapke.py; '
                                'with --albedo wac the w band is read per vertex (photometry.albedo)'},
                   'starMap': world_info['stars'] if world_info['stars'].get('present') else None},
        'spec': {'file': spec_path.name, 'sha256': spec_sha},
        'render': {'engine': scene.render.engine, 'samples': cyc.samples, 'seed': cyc.seed, 'device': cyc.device,
                   'denoise': cyc.use_denoising, 'resolution': [rx, ry], 'viewTransform': vs.view_transform,
                   'exposureStops': vs.exposure, 'physicalExposureStops': cam_p['exposureStops'], 'evCompensation': cfg.ev_comp, 'output': f"{ims.color_mode} {ims.color_depth}-bit PNG",
                   'bounces': {'max': cyc.max_bounces, 'diffuse': cyc.diffuse_bounces}},
        'observer': {'groundHeightM': h0, 'groundSource': h_src, 'frame': frame.describe(), 'bundleSiteHeightM': sp['site']['heightM']},
        'terrain': tile_report,
        'photometry': {**sp['photometry'], 'material': mat_info, 'dominantLight': sp['dominantLight'], 'albedo': albedo_info},
        'lighting': {'sun': {k: sun[k] for k in ('azDeg', 'elDeg', 'radiusDeg', 'rangeAu', 'irradianceWm2', 'discAngleDeg', 'lampOn')},
                     'sunDiscRadiance': sun_radiance,
                     'earth': {k: earth[k] for k in ('azDeg', 'elDeg', 'radiusDeg', 'rangeAu', 'phaseAngleDeg', 'illuminatedFraction',
                                                     'earthshineIrradianceWm2', 'lampOn')},
                     'earthSphere': f'Lambert albedo {EARTH_LAMBERT_ALBEDO}, lit by the Sun lamp; no shadow, no bounce (earthshine is its own lamp)',
                     'world': world_info, 'skyObjectsDistanceM': SKY_DIST_M},
        'camera': {k: cam_p[k] for k in cam_p if k not in ('layout',)},
        'cameraLayout': lay,
        'assets': {'layout': layout, 'placed': asset_info, 'label': sp['assets']['label']},
        'overlays': overlay_info,
        'outputs': {'blend': {'file': blend.name, 'sha256': specmod.sha256_file(blend)}, 'renders': renders, 'glb': glb_info},
        'timingsS': {'terrain': round(t_terrain, 2), 'render': round(t_render, 2) if t_render else None, 'total': round(time.time() - t_start, 2)},
        'labels': sp['labels'],
        'limitations': [
            'Blender places geometry and lights from the spec only; it computes no skyline, visibility, margin or metric.',
            'Instrument cameras are frame approximations of line-scan cameras (no motion, no TDI, no distortion); grayscale is Rec.709 luminance, not the instrument bandpass.',
            'Hapke shading uses the dominant light geometry for all light (earthshine while the Sun is up and inter-reflections are approximations).',
            'Earthshine is a Lambert-sphere MODEL with geometric albedo 0.367; Earth has no texture and casts no eclipse shadow.',
            'Stars: orientation MODEL (TRIAD), brightness VISUAL (display-scaled map).',
            'Orbital camera positions are placed above the site, not from a spacecraft ephemeris.',
            'Albedo: Hapke w from the 1-deg LROC WAC map (70N-70S); poleward the regional median. No NAC albedo (cached NAC mosaics carry shadows).',
        ] + (['VISUAL micro-relief displacement is ON (synthetic noise, not data).'] if cfg.micro_relief > 0 else []),
    }
    mpath = out / f'{tag}_manifest.json'
    mpath.write_text(json.dumps(manifest, indent=1, default=str))
    print(f"[POLARIS v2] {tag}: terrain {tile_report['vertexEstimate']} verts est., {t_terrain:.1f} s; render {t_render and round(t_render, 1)} s; wrote {blend.name}, {mpath.name}")
    return manifest, out, tag


if __name__ == '__main__':
    try:
        build(parse())
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
