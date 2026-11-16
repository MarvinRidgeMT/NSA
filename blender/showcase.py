"""POLARIS X showcase renders (Blender, Cycles) from a built hero scene.

Run through `showcase_render.command`, which opens blender/output/POLARIS_X_<site>_bundlev2.blend (built by
rebuild_blender_hero.command) and runs this script:
    blender -b <hero.blend> --python blender/showcase.py -- --bundle <ROI export> --site site01_roi6

What it changes (all PRESENTATION; nothing here is data):
  * regolith material on every terrain level: albedo ~0.13 with low-frequency variation, fully rough, no specular,
    and a synthetic sub-5 m surface (grit bump + small craterlet pits). Geometry stays the DEM / SfS display surface.
  * a synthetic boulder field (Geometry Nodes on the 5 m crop): Poisson-distributed, denser on slopes, at most ~0.8 m
    tall, and none within KEEP_CLEAR_M of the observer, so no synthetic rock stands between the mast and the
    terrain that sets the bundle's skyline near it. Its own collection/modifier, labelled VISUAL / synthetic.
  * showcase cameras and renders at the bundle's start sample: aerial, ground-level (1.7 m eye), low-Sun hero;
    and, where the bundle has a Sun transition with the 1 m mast blocked and the 10 m mast clear at that hour,
    an obstruction pair (1 m vs 10 m) using the bundle's own ray states and first-hit distances.
  * a web-ready Draco-compressed GLB of the terrain levels, mast and rays (boulders left out).
Every ray, ray length and visible/blocked state is read from the bundle (bundle_v2.ray_state); nothing is computed here.
"""
import argparse
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bundle_v2 as bv  # noqa: E402

KEEP_CLEAR_M = 150.0   # no synthetic boulder within this horizontal distance of the observer
ROCK_MAX_RADIUS_M = 1.3  # before the 0.6 vertical squash -> about 0.8 m tall at most


def parse():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument('--bundle', required=True)
    p.add_argument('--site', required=True)
    p.add_argument('--out', default='blender/output')
    p.add_argument('--samples', type=int, default=256)
    p.add_argument('--resolution', default='1920x1080')
    p.add_argument('--no-rocks', action='store_true')
    p.add_argument('--seed', type=int, default=7)
    return p.parse_args(argv)


def find(prefix):
    return next((o for o in bpy.data.objects if o.name.startswith(prefix)), None)


def sock(sockets, name, enabled_only=True):
    """Socket by name; when several share the name (Random Value, Compare), the enabled one."""
    c = [s for s in sockets if s.name == name and (s.enabled or not enabled_only)]
    return c[0] if c else sockets[name]


def first_enabled(sockets):
    return next(s for s in sockets if s.enabled)


def of_type(sockets, kind):
    """First socket of a socket type ('VALUE', 'VECTOR', ...): robust when a node's per-type sockets share one name."""
    return next(s for s in sockets if s.type == kind)


def set_all(sockets, name, value):
    for s in sockets:
        if s.name == name:
            try:
                s.default_value = value
            except (TypeError, ValueError):
                pass


def use_gpu(scene):
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        for t in ('METAL', 'OPTIX', 'CUDA', 'HIP', 'ONEAPI'):
            try:
                prefs.compute_device_type = t
            except TypeError:
                continue
            prefs.get_devices()
            devs = [d for d in prefs.devices if d.type == t]
            if devs:
                for d in prefs.devices:
                    d.use = d.type == t
                scene.cycles.device = 'GPU'
                return t
    except Exception as e:  # noqa: BLE001
        print(f'[POLARIS] GPU setup failed, using CPU: {e}')
    scene.cycles.device = 'CPU'
    return 'CPU'


def regolith_material():
    m = bpy.data.materials.new('Regolith v2 | albedo variation + synthetic micro-relief (VISUAL)')
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    bsdf = N.get('Principled BSDF')
    bsdf.inputs['Roughness'].default_value = 1.0
    for name in ('Specular IOR Level', 'Specular'):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = 0.0
    tc = N.new('ShaderNodeTexCoord')
    # albedo: two scales of variation around ~0.13 (lunar highland regolith), slightly warm
    big = N.new('ShaderNodeTexNoise'); big.inputs['Scale'].default_value = 0.0035; big.inputs['Detail'].default_value = 5.0
    mid = N.new('ShaderNodeTexNoise'); mid.inputs['Scale'].default_value = 0.06; mid.inputs['Detail'].default_value = 4.0
    L.new(tc.outputs['Object'], big.inputs['Vector']); L.new(tc.outputs['Object'], mid.inputs['Vector'])
    mix = N.new('ShaderNodeMath'); mix.operation = 'MULTIPLY_ADD'
    L.new(mid.outputs['Fac'], mix.inputs[0]); mix.inputs[1].default_value = 0.35; L.new(big.outputs['Fac'], mix.inputs[2])
    ramp = N.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.25; ramp.color_ramp.elements[0].color = (0.095, 0.091, 0.086, 1)
    ramp.color_ramp.elements[1].position = 1.05; ramp.color_ramp.elements[1].color = (0.165, 0.157, 0.147, 1)
    L.new(mix.outputs[0], ramp.inputs['Fac'])
    L.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    # synthetic micro-relief: grit (~0.3 m) + small craterlet pits (Voronoi bowls, ~4-10 m cells, about a third of cells)
    grit = N.new('ShaderNodeTexNoise'); grit.inputs['Scale'].default_value = 3.2; grit.inputs['Detail'].default_value = 8.0
    grit.inputs['Roughness'].default_value = 0.62
    L.new(tc.outputs['Object'], grit.inputs['Vector'])
    vor = N.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = 0.14
    L.new(tc.outputs['Object'], vor.inputs['Vector'])
    bowl = N.new('ShaderNodeValToRGB')  # distance to cell point -> crater profile: deep centre, raised rim, flat outside
    e = bowl.color_ramp.elements
    e[0].position = 0.0; e[0].color = (0.0, 0.0, 0.0, 1)
    e[1].position = 0.30; e[1].color = (0.62, 0.62, 0.62, 1)
    e.new(0.36).color = (0.70, 0.70, 0.70, 1)
    e.new(0.46).color = (0.5, 0.5, 0.5, 1)
    L.new(vor.outputs['Distance'], bowl.inputs['Fac'])
    mask = N.new('ShaderNodeTexNoise'); mask.inputs['Scale'].default_value = 0.09; mask.inputs['Detail'].default_value = 1.0
    L.new(tc.outputs['Object'], mask.inputs['Vector'])
    mk = N.new('ShaderNodeMapRange'); mk.inputs['From Min'].default_value = 0.52; mk.inputs['From Max'].default_value = 0.58
    L.new(mask.outputs['Fac'], mk.inputs['Value'])
    craters = N.new('ShaderNodeMix'); craters.data_type = 'FLOAT'
    L.new(of_type(mk.outputs, 'VALUE'), of_type([i for i in craters.inputs if i.name == 'Factor'], 'VALUE'))
    of_type([i for i in craters.inputs if i.name == 'A'], 'VALUE').default_value = 0.5
    L.new(bowl.outputs['Color'], of_type([i for i in craters.inputs if i.name == 'B'], 'VALUE'))
    h = N.new('ShaderNodeMath'); h.operation = 'MULTIPLY_ADD'
    L.new(grit.outputs['Fac'], h.inputs[0]); h.inputs[1].default_value = 0.35; L.new(of_type(craters.outputs, 'VALUE'), h.inputs[2])
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.55; bump.inputs['Distance'].default_value = 0.35
    L.new(h.outputs[0], bump.inputs['Height'])
    L.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    m['polaris_visual_only'] = 'albedo variation, grit and craterlet pits are synthetic; geometry is the DEM / SfS display surface'
    return m


def rock_material():
    m = bpy.data.materials.new('Boulder | synthetic (VISUAL)')
    m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links
    bsdf = N.get('Principled BSDF')
    bsdf.inputs['Roughness'].default_value = 0.92
    for name in ('Specular IOR Level', 'Specular'):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = 0.05
    tc = N.new('ShaderNodeTexCoord')
    n = N.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = 2.5; n.inputs['Detail'].default_value = 6.0
    L.new(tc.outputs['Object'], n.inputs['Vector'])
    ramp = N.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.10, 0.098, 0.094, 1); ramp.color_ramp.elements[1].color = (0.21, 0.20, 0.19, 1)
    L.new(n.outputs['Fac'], ramp.inputs['Fac']); L.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    b = N.new('ShaderNodeBump'); b.inputs['Strength'].default_value = 0.6
    n2 = N.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = 9.0; n2.inputs['Detail'].default_value = 8.0
    L.new(tc.outputs['Object'], n2.inputs['Vector']); L.new(n2.outputs['Fac'], b.inputs['Height']); L.new(b.outputs['Normal'], bsdf.inputs['Normal'])
    m['polaris_visual_only'] = 'synthetic boulders, not measured'
    return m


def add_boulders(dem_ob, seed, mat):
    """Geometry Nodes boulder field on the 5 m crop (VISUAL, synthetic)."""
    ng = bpy.data.node_groups.new('POLARIS synthetic boulders (VISUAL)', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    dist = N.new('GeometryNodeDistributePointsOnFaces')
    dist.distribute_method = 'POISSON'
    sock(dist.inputs, 'Distance Min').default_value = 2.5
    sock(dist.inputs, 'Density Max').default_value = 0.02
    sock(dist.inputs, 'Seed').default_value = seed
    L.new(gi.outputs[0], sock(dist.inputs, 'Mesh'))
    # density factor: more boulders on slopes and crater walls (1 - normal.z), never zero on flats
    nrm = N.new('GeometryNodeInputNormal'); sx = N.new('ShaderNodeSeparateXYZ'); L.new(nrm.outputs[0], sx.inputs[0])
    m1 = N.new('ShaderNodeMath'); m1.operation = 'SUBTRACT'; m1.inputs[0].default_value = 1.0; L.new(sx.outputs['Z'], m1.inputs[1])
    m2 = N.new('ShaderNodeMath'); m2.operation = 'MULTIPLY'; m2.use_clamp = True; m2.inputs[1].default_value = 9.0; L.new(m1.outputs[0], m2.inputs[0])
    m3 = N.new('ShaderNodeMath'); m3.operation = 'MAXIMUM'; m3.inputs[1].default_value = 0.035; L.new(m2.outputs[0], m3.inputs[0])
    L.new(m3.outputs[0], sock(dist.inputs, 'Density Factor'))
    # keep-clear disc around the observer (horizontal distance > KEEP_CLEAR_M)
    pos = N.new('GeometryNodeInputPosition'); sp = N.new('ShaderNodeSeparateXYZ'); L.new(pos.outputs[0], sp.inputs[0])
    cb = N.new('ShaderNodeCombineXYZ'); L.new(sp.outputs['X'], cb.inputs['X']); L.new(sp.outputs['Y'], cb.inputs['Y'])
    ln = N.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'; L.new(cb.outputs[0], ln.inputs[0])
    cmp = N.new('ShaderNodeMath'); cmp.operation = 'GREATER_THAN'; cmp.inputs[1].default_value = KEEP_CLEAR_M
    L.new(sock(ln.outputs, 'Value'), cmp.inputs[0])
    L.new(cmp.outputs[0], sock(dist.inputs, 'Selection'))
    # one lumpy, squashed, partly buried rock shape
    ico = N.new('GeometryNodeMeshIcoSphere')
    sock(ico.inputs, 'Radius').default_value = 1.0
    sock(ico.inputs, 'Subdivisions').default_value = 3
    tex = N.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value = 1.4; tex.inputs['Detail'].default_value = 3.0
    sub = N.new('ShaderNodeMath'); sub.operation = 'SUBTRACT'; L.new(tex.outputs['Fac'], sub.inputs[0]); sub.inputs[1].default_value = 0.5
    amp = N.new('ShaderNodeMath'); amp.operation = 'MULTIPLY'; L.new(sub.outputs[0], amp.inputs[0]); amp.inputs[1].default_value = 0.9
    n2 = N.new('GeometryNodeInputNormal'); scl = N.new('ShaderNodeVectorMath'); scl.operation = 'SCALE'
    L.new(n2.outputs[0], scl.inputs[0]); L.new(amp.outputs[0], sock(scl.inputs, 'Scale'))
    setp = N.new('GeometryNodeSetPosition')
    L.new(sock(ico.outputs, 'Mesh'), sock(setp.inputs, 'Geometry')); L.new(sock(scl.outputs, 'Vector'), sock(setp.inputs, 'Offset'))
    tr = N.new('GeometryNodeTransform')
    sock(tr.inputs, 'Scale').default_value = (1.0, 0.85, 0.6)
    sock(tr.inputs, 'Translation').default_value = (0.0, 0.0, 0.12)
    L.new(sock(setp.outputs, 'Geometry'), sock(tr.inputs, 'Geometry'))
    smat = N.new('GeometryNodeSetMaterial'); smat.inputs['Material'].default_value = mat
    L.new(sock(tr.outputs, 'Geometry'), sock(smat.inputs, 'Geometry'))
    # random rotation and a steep size distribution (many small, few large)
    rr = N.new('FunctionNodeRandomValue'); rr.data_type = 'FLOAT_VECTOR'
    set_all(rr.inputs, 'Max', (6.2832, 6.2832, 6.2832))
    sock(rr.inputs, 'Seed').default_value = seed + 1
    rs = N.new('FunctionNodeRandomValue'); rs.data_type = 'FLOAT'
    sock(rs.inputs, 'Seed').default_value = seed + 2
    pw = N.new('ShaderNodeMath'); pw.operation = 'POWER'; L.new(of_type(rs.outputs, 'VALUE'), pw.inputs[0]); pw.inputs[1].default_value = 5.0
    sz = N.new('ShaderNodeMath'); sz.operation = 'MULTIPLY_ADD'; L.new(pw.outputs[0], sz.inputs[0])
    sz.inputs[1].default_value = ROCK_MAX_RADIUS_M - 0.15; sz.inputs[2].default_value = 0.15
    iop = N.new('GeometryNodeInstanceOnPoints')
    L.new(sock(dist.outputs, 'Points'), sock(iop.inputs, 'Points'))
    L.new(sock(smat.outputs, 'Geometry'), sock(iop.inputs, 'Instance'))
    L.new(of_type(rr.outputs, 'VECTOR'), sock(iop.inputs, 'Rotation'))
    L.new(sz.outputs[0], sock(iop.inputs, 'Scale'))
    join = N.new('GeometryNodeJoinGeometry')
    L.new(gi.outputs[0], join.inputs[0]); L.new(sock(iop.outputs, 'Instances'), join.inputs[0])
    L.new(join.outputs[0], go.inputs[0])
    mod = dem_ob.modifiers.new('POLARIS synthetic boulders (VISUAL)', 'NODES')
    mod.node_group = ng
    return mod


def look_at(cam, target):
    d = (Vector(target) - cam.location).normalized()
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = d.to_track_quat('-Z', 'Y')


def ground_z(x, y):
    dg = bpy.context.evaluated_depsgraph_get()
    hit, loc, *_ = bpy.context.scene.ray_cast(dg, Vector((x, y, 3000.0)), Vector((0, 0, -1)))
    return loc.z if hit else 0.0


def new_cam(name, coll, lens):
    data = bpy.data.cameras.new(name)
    data.lens = lens
    data.clip_start, data.clip_end = 0.3, 60000.0
    ob = bpy.data.objects.new(name, data)
    coll.objects.link(ob)
    return ob


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    cfg = parse()
    scene = bpy.context.scene
    bundle, bsha, _ = bv.load(cfg.bundle)
    d = bv.dataset(bundle, cfg.site)
    scs = d['derived']['scenarios']
    base = next((s for s in scs if s['id'] == 'baseline'), scs[0])
    tall = next((s for s in scs if s['id'] == 'mast10'), None)
    obs = bv.observer(d, base)
    samples = d['ephemeris']['samples']
    keys = bv.key_samples_with_transition(d, base)
    tgt = keys.pop('transitionTarget', None)
    tag = f'POLARIS_X_{cfg.site}_bundlev2'
    out = Path(cfg.out).resolve()
    if not bpy.data.filepath.endswith(f'{tag}.blend'):
        raise SystemExit(f'open {tag}.blend first (got {bpy.data.filepath!r})')

    dem, l1, ctx = find('DEM |'), find('CONTEXT L1'), find('CONTEXT | PGDA 90')
    mast, head, sun = find('Observer mast'), find('Observer eye point'), find('Sun lamp')
    rays = {'sun': bpy.data.objects.get('Sun ray'), 'earth': bpy.data.objects.get('Earth ray')}
    terrain = [o for o in (dem, l1, ctx) if o]
    reg = regolith_material()
    for o in terrain:
        o.data.materials.clear()
        o.data.materials.append(reg)

    rocks = None
    rock_note = 'not requested'
    if not cfg.no_rocks and dem:
        try:
            rocks = add_boulders(dem, cfg.seed, rock_material())
            rock_note = 'drawn'
        except Exception as e:  # noqa: BLE001
            rock_note = f'failed: {e}'
            print(f'[POLARIS] boulder field skipped: {e}')

    # airless sky: camera rays see black (some older hero files carried a grey world colour)
    if scene.world is None:
        scene.world = bpy.data.worlds.new('POLARIS black sky')
    scene.world.use_nodes = True
    for n in scene.world.node_tree.nodes:
        if n.type == 'BACKGROUND':
            n.inputs['Color'].default_value = (0, 0, 0, 1)
            n.inputs['Strength'].default_value = 0.0

    dev = use_gpu(scene)
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = cfg.samples
    scene.cycles.use_denoising = True
    scene.cycles.diffuse_bounces = 4
    scene.cycles.max_bounces = 6
    rx, ry = (int(v) for v in cfg.resolution.split('x'))
    scene.render.resolution_x, scene.render.resolution_y = rx, ry
    scene.render.resolution_percentage = 100
    if sun and sun.data:
        sun.data.angle = math.radians(0.53)
    coll = bpy.data.collections.get('POLARIS Cameras') or scene.collection

    k0 = keys['start']
    s0 = samples[k0]
    sd = Vector(bv.grid_direction(d, s0['sun']['az'], 0.0)).normalized()
    perp = Vector((-sd.y, sd.x, 0)).normalized()
    half = (d['dem']['n'] - 1) * d['dem']['spacing'] / 2

    views = []
    # aerial: across the Sun's azimuth, high, the crop and its surroundings
    aer = new_cam('Camera | showcase aerial', coll, 32)
    aer.location = perp * (half * 1.6) - sd * (half * 0.35) + Vector((0, 0, half * 0.55))
    look_at(aer, (0, 0, 0))
    views.append(('aerial', aer, k0, 0.0))
    # ground level: a 1.7 m eye on the Sun side of the mast, Sun behind the viewer's shoulder, looking past
    # the mast down-Sun so lit slopes and the long shadows are in view (looking into the Sun showed only backlit black)
    gp = sd * 45 - perp * 20
    gnd = new_cam('Camera | showcase ground 1.7 m', coll, 24)
    gnd.location = Vector((gp.x, gp.y, ground_z(gp.x, gp.y) + 1.7))
    tgt_pt = -sd * 300 + perp * 40
    look_at(gnd, (tgt_pt.x, tgt_pt.y, ground_z(tgt_pt.x, tgt_pt.y) + 2))
    views.append(('ground', gnd, k0, 0.7))
    low = bpy.data.objects.get('Camera | low cross-lit hero')
    if low:
        views.append(('low_sun', low, k0, 1.0))

    scene.render.image_settings.file_format = 'PNG'
    exp0 = scene.view_settings.exposure
    renders = []

    def render(label, cam, k, exp, extra=None):
        scene.frame_set(k + 1)
        scene.camera = cam
        scene.view_settings.exposure = exp0 + exp
        png = out / f'{tag}_showcase_{label}.png'
        scene.render.filepath = str(png)
        bpy.ops.render.render(write_still=True)
        s = samples[k]
        e = {'label': label, 'camera': cam.name, 'frame': k + 1, 'sampleIndex': k, 'utc': s['time'],
             'sun': {'az': s['sun']['az'], 'el': s['sun']['el']}, 'exposureStops': exp, 'png': png.name, 'pngSha256': sha(png)}
        if extra:
            e.update(extra)
        renders.append(e)
        print(f'[POLARIS] showcase render {label}: {png.name}')

    for label, cam, k, exp in views:
        render(label, cam, k, exp, {'rays': {t: dict(zip(('state', 'firstHitM'), bv.ray_state(base, t, k))) for t in ('sun', 'earth')}})

    # obstruction pair: same hour, 1 m mast (bundle baseline) vs 10 m mast (bundle mast10), rays from each scenario
    obstruction = {'present': False}
    kt = keys.get('transition')
    if kt is not None and tgt == 'sun' and tall and mast and head and rays['sun']:
        st1, hit1 = bv.ray_state(base, 'sun', kt)
        st10, hit10 = bv.ray_state(tall, 'sun', kt)
        if st1 == 'blocked' and st10 == 'clear':
            st = samples[kt]
            tdir = Vector(bv.grid_direction(d, st['sun']['az'], st['sun']['el']))
            hdir = Vector(bv.grid_direction(d, st['sun']['az'], 0.0)).normalized()
            hp = Vector((-hdir.y, hdir.x, 0)).normalized()
            cam = new_cam('Camera | showcase obstruction', coll, 30)
            cx, cy = (hp * 28 + hdir * 6).x, (hp * 28 + hdir * 6).y
            cam.location = Vector((cx, cy, ground_z(cx, cy) + 3.2))
            fx, fy = (hdir * 10).x, (hdir * 10).y
            look_at(cam, (fx, fy, ground_z(fx, fy) + 1.5))
            for r in rays.values():
                if r and r.animation_data:
                    r.animation_data_clear()
            m0 = float(obs['mast'])
            edge = d['dem'].get('validCoverageRadiusM') or half
            head.scale = (0.4, 0.4, 0.4)  # smaller eye marker so the 1 m mast stays visible
            for label, sc, stt, hit in (('obstruction_mast1m', base, st1, hit1), ('obstruction_mast10m', tall, st10, hit10)):
                mh = float(sc['observer']['mastM'])
                mast.scale = (1.0, 1.0, mh / m0)
                mast.location = (0.0, 0.0, mh / 2.0)
                head.location = (0.0, 0.0, mh)
                r = rays['sun']
                r.location = (0.0, 0.0, mh)
                r.rotation_mode = 'QUATERNION'
                r.rotation_quaternion = tdir.normalized().to_track_quat('Z', 'Y')
                length = (hit if hit is not None else edge) / max(math.cos(math.radians(st['sun']['el'])), 1e-6)
                r.scale = (1.0, 1.0, length)
                if rays['earth']:
                    rays['earth'].hide_render = True
                render(label, cam, kt, 0.6, {'scenario': sc['id'], 'mastM': mh, 'sunRay': {'state': stt, 'firstHitM': hit},
                                             'bundleMarginDeg': sc['samples']['sun']['marginDeg'][kt]})
            obstruction = {'present': True, 'sampleIndex': kt, 'utc': samples[kt]['time'], 'mast1m': {'state': st1, 'firstHitM': hit1},
                           'mast10m': {'state': st10, 'firstHitM': hit10},
                           'note': 'both states from the bundle (baseline and mast10 scenarios); the 1.75 m Certainty Height has no hourly bundle series, so it is not drawn'}
        else:
            obstruction = {'present': False, 'reason': f'at the transition hour the bundle gives 1 m {st1}, 10 m {st10}'}
    else:
        obstruction = {'present': False, 'reason': 'no Sun transition in this window for the baseline mast' if tgt != 'sun' else 'scene objects missing'}

    rock_count = None
    if rocks:
        try:
            dg = bpy.context.evaluated_depsgraph_get()
            rock_count = sum(1 for i in dg.object_instances if i.is_instance and i.parent and i.parent.original == dem)
        except Exception:  # noqa: BLE001
            rock_count = None

    blend = out / f'{tag}_showcase.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True, copy=True)
    # web-ready GLB: terrain levels + mast + rays, Draco-compressed, boulders left out
    web = out / f'{tag}_web.glb'
    if rocks:
        rocks.show_viewport = False
        rocks.show_render = False
    bpy.ops.object.select_all(action='DESELECT')
    for o in [*terrain, mast, head, *[r for r in rays.values() if r]]:
        if o:
            o.hide_set(False)
            o.select_set(True)
    glb_info = {}
    try:
        bpy.ops.export_scene.gltf(filepath=str(web), export_format='GLB', use_selection=True, export_apply=True, export_yup=True,
                                  export_animations=False, export_lights=False, export_draco_mesh_compression_enable=True,
                                  export_draco_mesh_compression_level=6)
        glb_info = {'file': web.name, 'bytes': web.stat().st_size, 'sha256': sha(web), 'draco': True}
    except Exception as e:  # noqa: BLE001
        glb_info = {'error': str(e)}

    man = {
        'schema': 'polaris-blender-showcase-v1', 'generatedUTC': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'status': bv.display_status(bundle), 'site': cfg.site, 'bundle': {'file': os.path.basename(cfg.bundle), 'sha256': bsha},
        'blenderVersion': bpy.app.version_string, 'device': dev, 'samples': cfg.samples, 'resolution': cfg.resolution,
        'renders': renders, 'obstructionPair': obstruction, 'showcaseBlend': blend.name, 'webGlb': glb_info,
        'syntheticDetail': {
            'boulders': {'status': rock_note, 'count': rock_count, 'keepClearRadiusM': KEEP_CLEAR_M,
                         'maxHeightM': round(ROCK_MAX_RADIUS_M * 0.6 + 0.12, 2), 'seed': cfg.seed,
                         'label': 'VISUAL / synthetic: not measured; Poisson-distributed, denser on slopes'},
            'regolithMaterial': 'albedo variation, grit and craterlet bump are synthetic shading; geometry unchanged',
        },
        'limitations': [
            'Showcase renders are presentation. Terrain geometry is the bundle crop or the NASA GSFC SfS display surface (see the hero manifest).',
            'Rays, ray lengths and visible/blocked states come from the bundle; nothing in this script computes visibility.',
            'Boulders, albedo variation and micro-relief are synthetic; none lies within the keep-clear radius of the observer.',
            'Lighting energy, exposure and the dim fill seen by terrain (not by the camera) are presentation choices.',
        ],
    }
    (out / f'{tag}_showcase_manifest.json').write_text(json.dumps(man, indent=1))
    print(f'[POLARIS] showcase done: {len(renders)} renders, boulders {rock_note} ({rock_count}), device {dev}, web GLB {glb_info.get("bytes")}')


if __name__ == '__main__':
    main()
