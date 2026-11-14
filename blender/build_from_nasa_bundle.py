"""POLARIS X — Blender scene from a science-bundle-v2 (POLARIS-X5D-v2) file.

Run with Blender 4.5+ / 5.x:
  blender --background --python blender/build_from_nasa_bundle.py -- \
      --bundle app/data/polaris-source-site01-2026-11-14-v2.json --site connecting

  # or the DEMO fixture (always labelled DEMO):
  blender --background --python blender/build_from_nasa_bundle.py -- \
      --bundle web/public/bundles/demo-fixture.json

What it does (Blender is READ-ONLY with respect to science):
  * DEM mesh at 1:1 vertical scale (no exaggeration), 1 Blender unit = 1 m, grid axes
    x = grid east, y = grid north, z = elevation relative to the observer's ground.
  * Observer mast drawn to scale.
  * SUN lamp aimed along the bundle's JPL Sun direction for each sample (local az/el rotated
    into the DEM grid). Keyframed: frame k+1 = ephemeris sample k.
  * Sun and Earth rays from the mast top. If the bundle has `derived` outputs, a blocked ray
    ends at the bundle's first-hit distance; otherwise the ray is labelled "not evaluated".
  * Renders start / mid / end, exports .glb, writes scene_manifest.json with the bundle SHA-256.
It never computes a skyline, visibility, margin or metric.
"""
import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bundle_v2 as bv  # noqa: E402

COLL_NAMES = ('POLARIS Terrain', 'POLARIS Observer', 'POLARIS Sky', 'POLARIS Cameras')


def parse():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle', required=True, help='science-bundle-v2 JSON (POLARIS-X5D-v2)')
    p.add_argument('--site', default=None, help='siteId (default: first dataset)')
    p.add_argument('--scenario', default=None, help='derived scenario id (default: first, if any)')
    p.add_argument('--output', default='blender/output')
    p.add_argument('--max-vertices-per-axis', type=int, default=201)
    p.add_argument('--samples', type=int, default=24, help='Cycles samples per render')
    p.add_argument('--resolution', default='1600x900')
    p.add_argument('--no-render', action='store_true')
    return p.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    colls = {}
    for name in COLL_NAMES:
        c = bpy.data.collections.new(name)
        scene.collection.children.link(c)
        colls[name] = c
    return scene, colls


def link(obj, coll):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)
    return obj


def material(name, rgb, emission=0.0, roughness=0.95):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*rgb, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    if emission:
        bsdf.inputs['Emission Color'].default_value = (*rgb, 1)
        bsdf.inputs['Emission Strength'].default_value = emission
    m.diffuse_color = (*rgb, 1)
    return m


def terrain_material(lo, hi):
    m = bpy.data.materials.new('Regolith | elevation ramp (visual only)')
    m.use_nodes = True
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes.get('Principled BSDF')
    bsdf.inputs['Roughness'].default_value = 0.97
    geo = nodes.new('ShaderNodeNewGeometry')
    sep = nodes.new('ShaderNodeSeparateXYZ')
    rng = nodes.new('ShaderNodeMapRange')
    rng.inputs['From Min'].default_value = lo
    rng.inputs['From Max'].default_value = hi if hi > lo else lo + 1
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.30, 0.31, 0.32, 1)
    ramp.color_ramp.elements[1].color = (0.62, 0.60, 0.56, 1)
    links.new(geo.outputs['Position'], sep.inputs[0])
    links.new(sep.outputs['Z'], rng.inputs['Value'])
    links.new(rng.outputs['Result'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    return m


def build_dem(dem, obs, max_axis, coll):
    """Mesh in grid metres relative to the observer; z relative to observer ground. NO exaggeration."""
    n = dem['n']
    m = min(n, max_axis)
    idx = sorted({round(k * (n - 1) / (m - 1)) for k in range(m)})
    m = len(idx)
    verts = []
    for j in idx:
        for i in idx:
            verts.append((dem['originX'] + i * dem['spacing'] - obs['x'],
                          dem['originY'] + j * dem['spacing'] - obs['y'],
                          dem['values'][j * n + i] - obs['ground']))
    faces = [(j * m + i, j * m + i + 1, (j + 1) * m + i + 1, (j + 1) * m + i) for j in range(m - 1) for i in range(m - 1)]
    mesh = bpy.data.meshes.new('DEM grid')
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    for p in mesh.polygons:
        p.use_smooth = True
    ob = link(bpy.data.objects.new(f"DEM | {dem.get('layer', dem.get('kind'))} | 1:1 metres", mesh), coll)
    zs = [v[2] for v in verts]
    ob.data.materials.append(terrain_material(min(zs), max(zs)))
    return ob, (n - 1) * dem['spacing'] / 2.0, m


def ray_object(name, length, radius, mat, coll):
    """Thin cylinder along +Z of length `length`, origin at its base (so rotation aims it from the mast top)."""
    mesh = bpy.data.meshes.new(name)
    seg = 12
    verts = []
    for z in (0.0, 1.0):
        for s in range(seg):
            a = 2 * math.pi * s / seg
            verts.append((radius * math.cos(a), radius * math.sin(a), z))
    faces = [(s, (s + 1) % seg, seg + (s + 1) % seg, seg + s) for s in range(seg)]
    mesh.from_pydata(verts, [], faces)
    ob = link(bpy.data.objects.new(name, mesh), coll)
    ob.data.materials.append(mat)
    ob.scale = (1, 1, length)
    return ob


def aim_z(ob, direction):
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = Vector(direction).normalized().to_track_quat('Z', 'Y')


def main():
    cfg = parse()
    bundle, sha, nbytes = bv.load(cfg.bundle)
    status = bv.display_status(bundle)
    d = bv.dataset(bundle, cfg.site)
    bv.check_dem(d['dem'])
    sc = bv.scenario(d, cfg.scenario)
    obs = bv.observer(d, sc)
    north, east, basis_src = bv.basis(d)
    samples = d['ephemeris']['samples']
    keys = bv.key_samples(d)
    site = d['siteId']
    tag = f"POLARIS_X_{site}_bundlev2" + ('_DEMO' if status == 'DEMO' else '')

    scene, C = reset_scene()
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0

    terrain, half, m_axis = build_dem(d['dem'], obs, cfg.max_vertices_per_axis, C['POLARIS Terrain'])
    edge = d['dem'].get('validCoverageRadiusM') or half

    # observer mast, to scale
    mast_mat = material('Observer mast (marker, not hardware)', (0.10, 0.80, 0.75), emission=2.0)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=max(half / 600, 0.5), depth=obs['mast'], location=(0, 0, obs['mast'] / 2))
    mast = link(bpy.context.object, C['POLARIS Observer'])
    mast.name = f"Observer mast {obs['mast']} m ({obs['source']})"
    mast.data.materials.append(mast_mat)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=max(half / 300, 2.0), location=(0, 0, obs['mast']))
    head = link(bpy.context.object, C['POLARIS Observer'])
    head.name = 'Observer eye point'
    head.data.materials.append(mast_mat)
    top = Vector((0, 0, obs['mast']))

    # sun lamp: Blender SUN lamps shine along their local -Z, so +Z must point TOWARD the Sun
    sun_data = bpy.data.lights.new('Sun | JPL direction from bundle', type='SUN')
    sun_data.energy = 6.0
    sun_data.angle = math.radians(0.53)  # angular diameter of the solar disk, for soft shadow edges only
    sun = link(bpy.data.objects.new('Sun lamp | aimed by bundle az/el', sun_data), C['POLARIS Sky'])
    sun.location = (0, 0, half)

    ray_r = max(half / 900, 0.8)
    rays = {
        'sun': ray_object('Sun ray', 1.0, ray_r, material('Sun ray', (1.0, 0.72, 0.25), emission=1.5), C['POLARIS Sky']),
        'earth': ray_object('Earth ray', 1.0, ray_r, material('Earth ray', (0.35, 0.66, 0.95), emission=1.5), C['POLARIS Sky']),
    }
    for r in rays.values():
        r.location = top

    world = bpy.data.worlds.new('Space')
    world.use_nodes = True
    # dim neutral fill so shadowed terrain stays readable (presentation only; recorded in the manifest)
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.055, 0.065, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.6
    scene.world = world

    frame_to_utc = []
    for k, s in enumerate(samples):
        f = k + 1
        scene.frame_set(f)
        sdir = bv.grid_direction(d, s['sun']['az'], s['sun']['el'])
        aim_z(sun, sdir)
        sun.keyframe_insert('rotation_quaternion', frame=f)
        sun_data.energy = 6.0 if s['sun']['el'] > -0.27 else 0.0  # below the horizon entirely: no direct sunlight
        sun_data.keyframe_insert('energy', frame=f)
        for t in ('sun', 'earth'):
            st, hit = bv.ray_state(sc, t, k)
            el = s[t]['el']
            length = (hit if hit is not None else edge) / max(math.cos(math.radians(el)), 1e-6)
            aim_z(rays[t], bv.grid_direction(d, s[t]['az'], el))
            rays[t].scale = (1, 1, length)
            rays[t].keyframe_insert('rotation_quaternion', frame=f)
            rays[t].keyframe_insert('scale', frame=f)
        frame_to_utc.append({'frame': f, 'sampleIndex': k, 'utc': s['time']})
    for ob in (sun, *rays.values()):
        if ob.animation_data and ob.animation_data.action:
            act = ob.animation_data.action
            curves = getattr(act, 'fcurves', None)
            if curves is None:  # Blender 5 layered actions
                curves = [fc for layer in act.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]
            for fc in curves:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'  # never interpolate between ephemeris samples in Blender
    scene.frame_start, scene.frame_end = 1, len(samples)

    # cameras
    cam_data = bpy.data.cameras.new('Oblique')
    cam_data.lens = 35
    cam_data.clip_start, cam_data.clip_end = 1.0, half * 20
    cam = link(bpy.data.objects.new('Camera | oblique over observer', cam_data), C['POLARIS Cameras'])
    se = Vector((-north[0] - east[0] * 0.6, -north[1] - east[1] * 0.6, 0)).normalized()
    cam.location = se * half * 1.05 + Vector((0, 0, half * 0.62))
    aim = (Vector((0, 0, 0)) - cam.location).normalized()
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = aim.to_track_quat('-Z', 'Y')
    scene.camera = cam

    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = cfg.samples
    scene.cycles.use_denoising = True
    rx, ry = (int(v) for v in cfg.resolution.split('x'))
    scene.render.resolution_x, scene.render.resolution_y = rx, ry
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.view_settings.view_transform = 'AgX' if 'AgX' in [t.identifier for t in bpy.types.ColorManagedViewSettings.bl_rna.properties['view_transform'].enum_items] else 'Filmic'

    out = Path(cfg.output).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    renders = []
    for label, k in keys.items():
        s = samples[k]
        f = k + 1
        scene.frame_set(f)
        entry = {
            'label': label, 'frame': f, 'sampleIndex': k, 'utc': s['time'],
            'sun': {'az': s['sun']['az'], 'el': s['sun']['el'], 'lampTowardSunGrid': [round(c, 9) for c in bv.grid_direction(d, s['sun']['az'], s['sun']['el'])],
                    'ray': dict(zip(('state', 'firstHitM'), bv.ray_state(sc, 'sun', k)))},
            'earth': {'az': s['earth']['az'], 'el': s['earth']['el'],
                      'ray': dict(zip(('state', 'firstHitM'), bv.ray_state(sc, 'earth', k)))},
        }
        if sc:
            entry['bundleMarginDeg'] = {t: sc['samples'][t]['marginDeg'][k] for t in ('sun', 'earth')}
        if not cfg.no_render:
            png = out / f'{tag}_{label}_frame{f:03d}.png'
            scene.render.filepath = str(png)
            bpy.ops.render.render(write_still=True)
            entry['png'] = png.name
            entry['pngSha256'] = bv.file_sha256(png)
        renders.append(entry)

    blend = out / f'{tag}.blend'
    glb = out / f'{tag}.glb'
    scene.frame_set(keys['start'] + 1)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
    bpy.ops.object.select_all(action='DESELECT')
    for ob in (terrain, mast, head, *rays.values(), sun):
        ob.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True, export_lights=True,
                              export_apply=True, export_yup=True, export_animations=False)

    manifest = {
        'schema': 'POLARIS-X-scene-manifest-v2',
        'generatedUTC': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'bundle': {'file': Path(cfg.bundle).name, 'sha256': sha, 'bytes': nbytes, 'format': bundle['format'],
                   'schemaVersion': bundle['schemaVersion'], 'generatedUTC': bundle.get('generatedUTC')},
        'status': status,
        'demo': status == 'DEMO',
        'site': {'siteId': site, 'name': d['site'].get('name'), 'latitudePlanetocentricDeg': d['site'].get('latitudePlanetocentricDeg'),
                 'longitudeEastDeg': d['site']['longitudeEastDeg']},
        'scenario': sc['id'] if sc else None,
        'derivedOutputsPresent': sc is not None,
        'blenderVersion': bpy.app.version_string,
        'units': '1 Blender unit = 1 metre',
        'axes': {'x': 'grid east (south-polar stereographic)', 'y': 'grid north', 'z': 'elevation relative to observer ground (m)',
                 'gltf': 'exported Y-up (glTF convention): gltf (x, y, z) = blender (x, z, -y)'},
        'verticalExaggeration': 1.0,
        'origin': {'gridX': obs['x'], 'gridY': obs['y'], 'groundElevationM': obs['ground'], 'source': obs['source']},
        'observerMastM': obs['mast'],
        'frame': {'localNorthInGrid': list(north), 'localEastInGrid': list(east), 'source': basis_src,
                  'azimuthConvention': d['ephemeris'].get('azimuthConvention')},
        'dem': {'layer': d['dem'].get('layer'), 'n': d['dem']['n'], 'spacingM': d['dem']['spacing'], 'meshVerticesPerAxis': m_axis,
                'cropValuesSha256': d['dem'].get('cropValuesSha256'), 'source': d['dem'].get('source')},
        'sunLamp': 'SUN lamp +Z aimed toward the bundle JPL Sun direction (lamp shines along -Z); keyframed per sample with CONSTANT interpolation; energy 0 when el <= -0.27 deg',
        'rays': 'blocked rays end at bundle firstHitM (horizontal) when derived outputs exist; otherwise drawn to the DEM coverage edge and marked not evaluated',
        'frameToUtc': {'first': frame_to_utc[0], 'last': frame_to_utc[-1], 'rule': 'frame = sampleIndex + 1'},
        'renders': renders,
        'assets': {'blend': {'file': blend.name, 'sha256': bv.file_sha256(blend)}, 'glb': {'file': glb.name, 'sha256': bv.file_sha256(glb)}},
        'limitations': [
            'Blender places geometry from bundle values only; it computes no skyline, visibility, margin or metric.',
            'Lighting energy, the dim world fill light, materials and camera are presentation choices; only the Sun lamp DIRECTION comes from the bundle.',
            'Visibility is target centre above a finite-DEM skyline; not power, not a DSN link.',
        ],
    }
    mpath = out / f'{tag}_scene_manifest.json'
    mpath.write_text(json.dumps(manifest, indent=2))
    print(f'[POLARIS] {status} · bundle sha256 {sha}')
    print(f'[POLARIS] wrote {blend.name}, {glb.name}, {mpath.name}, renders: {[r.get("png") for r in renders]}')


if __name__ == '__main__':
    main()
