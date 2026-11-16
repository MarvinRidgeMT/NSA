"""POLARIS X v2 — the whole Moon as a scripted Blender build (prompt §5.1a): cube-sphere base mesh displaced from the S3 pyramid's
level 0 (~1 km), Hapke regolith with the WAC albedo w per vertex, Sun from a solver bundle sample; plus the web globe GLB.

    blender -b --python-exit-code 1 -P blender/v2/globe.py -- [--bundle data/bundles/site01_roi6_2026-11-14_14d_mast1m.json]
            [--utc 2026-11-21T02:00Z] [--n 384] [--web-n 192] [--resolution 512] [--samples 16] [--no-render] [--no-glb]

Inputs come from a globe pack (blender/v2/pack.py globe, project venv; run automatically when missing). Outputs:
  <out>/<tag>.blend, <tag>_manifest.json, <tag>.png (view from the bundle's Earth direction, orthographic)
  web/public/globe/polaris_moon_globe.glb (git-ignored): Draco, Khronos exporter, scenes[0].extras.polaris names this builder.
Frames: the science globe is Moon-fixed ME (Blender x -> lon 0, y -> lon 90 E, z -> north), 1 Blender unit = 1 km. The web
globe is rotated so glTF +Y = north, +Z = lon 0, +X = lon 90 E (web/src/three/GlobalMoon.tsx angularPoint convention).
Labels: heights SOURCE-BASED · UNVALIDATED (pyramid L0, box-filtered to the mesh); Hapke photometry + w MODEL; web base colour
VISUAL (WAC morphologic mosaic: topographic shading baked in, not an albedo).
"""
import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from v2 import albedo, astro, cubesphere, hapke, hapke_nodes, spec as specmod, terrain as T  # noqa: E402

ROOT = HERE.parents[1]
BUILDER = 'blender/v2/globe.py'
WEB_GLB = ROOT / 'web' / 'public' / 'globe' / 'polaris_moon_globe.glb'
KM = 1e-3
DEFAULT_BUNDLE = 'data/bundles/site01_roi6_2026-11-14_14d_mast1m.json'


def parse(argv=None):
    if argv is None:
        argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--pack', default=None, help='globe pack directory (default: build/look up with pack.py globe)')
    p.add_argument('--n', type=int, default=384, help='cube-sphere face resolution of the .blend globe (must be in the pack)')
    p.add_argument('--web-n', type=int, default=192, help='face resolution of the web GLB (must be in the pack)')
    p.add_argument('--bundle', default=DEFAULT_BUNDLE, help='solver bundle giving the Sun (and Earth) direction for --utc')
    p.add_argument('--utc', default='2026-11-21T02:00Z')
    p.add_argument('--hapke-region', default='GLOBAL', choices=sorted(hapke.PARAMS_643NM))
    p.add_argument('--resolution', type=int, default=512)
    p.add_argument('--samples', type=int, default=16)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--no-render', action='store_true')
    p.add_argument('--no-glb', action='store_true')
    p.add_argument('--glb-path', default=str(WEB_GLB))
    p.add_argument('--out', default='blender/output/v2/globe')
    p.add_argument('--tag', default=None)
    return p.parse_args(argv)


def ensure_globe_pack(ns):
    import subprocess
    from v2.build_scene import project_python
    r = subprocess.run([project_python(), str(HERE / 'pack.py'), 'globe', '--faces', ','.join(str(n) for n in ns)],
                       capture_output=True, text=True, cwd=str(ROOT))
    if r.returncode != 0:
        raise SystemExit(f'pack.py globe failed ({r.returncode}):\n{r.stderr[-2000:]}')
    return Path(json.loads(r.stdout.strip().splitlines()[-1])['pack'])


def sky_vectors_me(bundle_path, utc):
    """Sun and Earth unit vectors in Moon-fixed ME from the bundle sample (topocentric az/el at the bundle site -> ME). The Sun's
    parallax across the Moon is < 0.0003 deg; the Earth's (~1 deg) does not matter for an orthographic whole-disc view."""
    b = json.loads(Path(bundle_path).read_text())
    k, off = astro.pick_sample(b['samples'], utc)
    s = b['samples'][k]
    site = b['site']
    M = T.EnuFrame(site['lat_deg'], site['lon_deg_east'], 0.0).M        # rows E, N, U in ME
    out = {}
    for body in ('sun', 'earth'):
        enu = np.array(astro.enu_direction(s[body]['az_deg'], s[body]['el_deg']))
        out[body] = (enu @ M).tolist()
        out[body + 'Sample'] = {k2: s[body][k2] for k2 in ('az_deg', 'el_deg', 'range_au')}
    out.update(utc=s['utc'], index=k, offsetS=off, site=site['id'], bundle=str(Path(bundle_path).resolve().relative_to(ROOT)),
               bundleSha256=specmod.sha256_file(bundle_path))
    return out


def mesh_from_arrays(name, V, F, coll, uv=None, mat_index=None):
    me = bpy.data.meshes.new(name)
    V = np.asarray(V, np.float32)
    F = np.asarray(F, np.int32)
    me.vertices.add(len(V))
    me.vertices.foreach_set('co', V.ravel())
    me.loops.add(F.size)
    me.loops.foreach_set('vertex_index', F.ravel())
    me.polygons.add(len(F))
    me.polygons.foreach_set('loop_start', np.arange(0, F.size, 4, dtype=np.int32))
    me.update(calc_edges=True)
    me.polygons.foreach_set('use_smooth', np.ones(len(F), dtype=bool))
    if uv is not None:
        lay = me.uv_layers.new(name='face_uv')
        lay.data.foreach_set('uv', np.asarray(uv, np.float32).ravel())
    if mat_index is not None:
        me.polygons.foreach_set('material_index', np.asarray(mat_index, np.int32))
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def face_material(f, tex, out_dir):
    """Principled BSDF with the face's WAC texture (VISUAL base colour for the web; the exporter maps it to baseColorTexture)."""
    n = tex.shape[0]
    img = bpy.data.images.new(f'wac_face_{f}', n, n, alpha=False)
    g = (tex[::-1].astype(np.float32) / 255.0)                     # image row 0 = bottom in Blender
    px = np.ones((n, n, 4), np.float32)
    px[..., 0] = px[..., 1] = px[..., 2] = g
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = str(out_dir / f'wac_face_{f}.png')
    img.file_format = 'PNG'
    img.save()
    m = bpy.data.materials.new(f'WAC face {f} ({cubesphere.FACE_NAMES[f]}) | VISUAL base colour, shading baked in')
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(nd for nd in nt.nodes if nd.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Roughness'].default_value = 1.0
    t = nt.nodes.new('ShaderNodeTexImage')
    t.image = img
    t.extension = 'EXTEND'
    nt.links.new(t.outputs['Color'], bsdf.inputs['Base Color'])
    return m


def build(cfg):
    t0 = time.time()
    pack_dir = Path(cfg.pack) if cfg.pack else ensure_globe_pack(sorted({cfg.n, cfg.web_n}, reverse=True))
    pk = json.loads((pack_dir / 'pack.json').read_text())
    meshes = {m['n']: m for m in pk['meshes']}
    for n in (cfg.n, cfg.web_n):
        if n not in meshes:
            raise SystemExit(f'pack {pk["id"]} has face resolutions {sorted(meshes)}, not {n}')
    out = Path(cfg.out)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    tag = cfg.tag or f'globe_n{cfg.n}_{cfg.utc[:13].replace("-", "").replace(":", "")}'
    bundle = Path(cfg.bundle) if Path(cfg.bundle).is_absolute() else ROOT / cfg.bundle
    sky = sky_vectors_me(bundle, cfg.utc)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system, scene.unit_settings.scale_length = 'METRIC', 1000.0     # 1 BU = 1 km
    coll = bpy.data.collections.new('POLARIS Globe')
    scene.collection.children.link(coll)
    web_coll = bpy.data.collections.new('POLARIS Web globe (export)')
    scene.collection.children.link(web_coll)

    # --- science globe: pyramid L0 heights, Hapke with per-vertex WAC w ------------------------------------------------
    t = time.time()
    H = np.load(pack_dir / meshes[cfg.n]['file'])
    V, F, fid, uv, dropped = cubesphere.mesh(cfg.n, H, scale=KM)
    la, lo = cubesphere.latlon_deg(V)
    wmap = albedo.WMap.load()
    w = wmap.sample(la, lo)
    params = hapke.params(cfg.hapke_region)
    mat, mat_info = hapke_nodes.hapke_material(f'Regolith | Hapke 2012 ({cfg.hapke_region}) | w per vertex (WAC map) | MODEL', params,
                                               sky['sun'], w_attribute='polaris_w')
    ob = mesh_from_arrays(f'MOON | cube-sphere n={cfg.n} | pyramid L0 heights | SOURCE-BASED UNVALIDATED | km, ME axes', V, F, coll)
    ob.data.materials.append(mat)
    at = ob.data.attributes.new('polaris_w', 'FLOAT', 'POINT')
    at.data.foreach_set('value', w.astype(np.float32))
    t_mesh = time.time() - t

    # --- Sun lamp from the bundle; black airless sky -------------------------------------------------------------------
    sun_irr = astro.solar_irradiance(sky['sunSample']['range_au'])
    ld = bpy.data.lights.new('Sun | bundle direction (ME), 1361/r^2', 'SUN')
    ld.energy = sun_irr
    ld.angle = math.radians(0.53)
    lo_ = bpy.data.objects.new(ld.name, ld)
    coll.objects.link(lo_)
    lo_.rotation_mode = 'QUATERNION'
    lo_.rotation_quaternion = Vector(sky['sun']).normalized().to_track_quat('Z', 'Y')
    world = bpy.data.worlds.new('Space (airless)')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0, 0, 0, 1)
    scene.world = world

    # --- camera: orthographic along the Earth direction (whole disc as seen from Earth at this sample, parallax ignored) -
    cd = bpy.data.cameras.new('View from the Earth direction (orthographic)')
    cd.type = 'ORTHO'
    cd.ortho_scale = 2.08 * 1737.4
    cd.clip_start, cd.clip_end = 1.0, 20000.0
    cam = bpy.data.objects.new('CAMERA | Earth direction', cd)
    coll.objects.link(cam)
    e = Vector(sky['earth']).normalized()
    cam.location = e * 10000.0
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (-e).to_track_quat('-Z', 'Y')     # image up = north
    scene.camera = cam

    # --- web globe (exported; hidden from the render) ------------------------------------------------------------------
    t = time.time()
    tex = np.load(pack_dir / pk['texture']['file'])
    Hw = np.load(pack_dir / meshes[cfg.web_n]['file'])
    Vw, Fw, fidw, uvw, dropped_w = cubesphere.mesh(cfg.web_n, Hw, scale=KM)
    Vw = np.stack([Vw[:, 1], -Vw[:, 0], Vw[:, 2]], axis=1)       # ME -> Blender so that glTF +Z = lon 0, +X = lon 90 E, +Y = north
    tex_dir = out / f'{tag}_textures'
    tex_dir.mkdir(exist_ok=True)
    web = mesh_from_arrays(f'MOON WEB | cube-sphere n={cfg.web_n} | pyramid L0 | WAC morphologic base colour VISUAL', Vw, Fw, web_coll,
                           uv=uvw.reshape(-1, 2), mat_index=fidw)
    for f in range(6):
        web.data.materials.append(face_material(f, tex[f], tex_dir))
    web.hide_render = True
    t_web = time.time() - t

    # --- render ---------------------------------------------------------------------------------------------------------
    scene.render.engine = 'CYCLES'
    cyc = scene.cycles
    cyc.samples, cyc.seed, cyc.device = cfg.samples, cfg.seed, 'CPU'
    cyc.use_adaptive_sampling = False
    cyc.use_denoising = False
    cyc.max_bounces, cyc.diffuse_bounces, cyc.glossy_bounces = 2, 1, 0
    scene.render.resolution_x = scene.render.resolution_y = cfg.resolution
    scene.render.resolution_percentage = 100
    vs = scene.view_settings
    vs.view_transform, vs.look, vs.gamma = 'Standard', 'None', 1.0
    # display exposure: I/F 0.25 (bright highlands near full Sun) maps to 0.8 of full scale; stated, not physical camera exposure
    vs.exposure = math.log2(0.8 / (0.25 / math.pi * sun_irr))
    ims = scene.render.image_settings
    ims.file_format, ims.color_mode, ims.color_depth = 'PNG', 'BW', '8'
    renders, t_render = [], None
    if not cfg.no_render:
        png = out / f'{tag}.png'
        scene.render.filepath = str(png)
        t = time.time()
        bpy.ops.render.render(write_still=True)
        t_render = time.time() - t
        renders.append({'png': png.name, 'sha256': specmod.sha256_file(png), 'seconds': round(t_render, 2), 'resolution': [cfg.resolution] * 2})

    scripts = {p.name: specmod.sha256_file(p) for p in sorted(HERE.glob('*.py'))}
    labels = {'heights': 'SOURCE-BASED · UNVALIDATED (S3 pyramid level 0, box-filtered)', 'photometry': 'MODEL (Hapke 2012, WAC 643 nm)',
              'albedo': albedo.LABEL, 'webBaseColour': pk['texture']['label']}
    prov = {'builder': BUILDER, 'tag': tag, 'pack': pk['id'], 'scriptsSha256': scripts, 'blender': bpy.app.version_string,
            'labels': labels, 'units': 'km', 'axes': 'glTF +Y north, +Z lon 0, +X lon 90 E (Moon-fixed ME, rotated for the web viewer)',
            'radiusKm': 1737.4, 'heightsSource': 'S3 pyramid level 0 (eq 947 m, polar 1280 m) via blender/v2/pack.py',
            'textureCredit': pk['texture']['credit']}
    scene['polaris'] = json.dumps(prov)
    blend = out / f'{tag}.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
    glb_info = None
    if not cfg.no_glb:
        glb = Path(cfg.glb_path)
        glb.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.object.select_all(action='DESELECT')
        web.select_set(True)
        bpy.context.view_layer.objects.active = web
        t = time.time()
        bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True, export_extras=True, export_yup=True,
                                  export_apply=True, export_animations=False, export_lights=False, export_cameras=False,
                                  export_image_format='JPEG', export_jpeg_quality=85,
                                  export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6)
        glb_info = {'file': str(glb.relative_to(ROOT)) if glb.is_relative_to(ROOT) else str(glb), 'sha256': specmod.sha256_file(glb),
                    'bytes': glb.stat().st_size, 'seconds': round(time.time() - t, 2), 'faceN': cfg.web_n,
                    'vertices': int(len(Vw)), 'quads': int(len(Fw)), 'textures': '6 x %d^2 JPEG (q85)' % tex.shape[1]}
    manifest = {
        'schema': 'polaris-blender-v2-globe-manifest-v1',
        'generatedUtc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'blenderVersion': bpy.app.version_string,
        'blenderBuildHash': bpy.app.build_hash.decode() if isinstance(bpy.app.build_hash, bytes) else str(bpy.app.build_hash),
        'command': 'blender -b -P blender/v2/globe.py -- ' + ' '.join(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []),
        'scriptsSha256': scripts,
        'inputs': {'pack': {'id': pk['id'], 'pyramidIndexSha256': pk['request']['pyramidIndexSha256'], 'heights': meshes[cfg.n],
                            'webHeights': meshes[cfg.web_n], 'heightsRule': pk['heightsRule'], 'texture': pk['texture']},
                   'bundle': {'file': sky['bundle'], 'sha256': sky['bundleSha256'], 'sample': sky['utc'], 'site': sky['site'], 'offsetS': sky['offsetS']},
                   'hapkeMap': wmap.describe()},
        'globe': {'faceN': cfg.n, 'vertices': int(len(V)), 'quads': int(len(F)), 'droppedQuads': dropped,
                  'nodeSpacingM': meshes[cfg.n]['nodeSpacingM'], 'heightRangeM': [meshes[cfg.n]['hMinM'], meshes[cfg.n]['hMaxM']],
                  'wRange': [float(w.min()), float(w.max())], 'wMedian': float(np.median(w))},
        'lighting': {'sunDirMe': sky['sun'], 'sunSample': sky['sunSample'], 'sunIrradianceWm2': sun_irr, 'earthDirMe': sky['earth'],
                     'rule': 'topocentric Horizons az/el at the bundle site rotated to Moon-fixed ME (ENU axes of that site)'},
        'photometry': {'region': cfg.hapke_region, 'params': params, 'material': mat_info, 'albedo': wmap.describe()},
        'render': {'engine': 'CYCLES', 'samples': cfg.samples, 'seed': cfg.seed, 'device': 'CPU', 'resolution': [cfg.resolution] * 2,
                   'camera': 'orthographic along the bundle Earth direction (Earth parallax ignored)', 'exposureStops': vs.exposure,
                   'exposureRule': 'display: I/F 0.25 -> 0.8 of full scale', 'output': '8-bit BW PNG'},
        'outputs': {'blend': {'file': blend.name, 'sha256': specmod.sha256_file(blend)}, 'renders': renders, 'glb': glb_info},
        'provenance': prov,
        'timingsS': {'mesh': round(t_mesh, 2), 'webMesh': round(t_web, 2), 'render': round(t_render, 2) if t_render else None,
                     'total': round(time.time() - t0, 2)},
        'limitations': [
            'Heights are the pyramid\'s ~1 km level box-filtered onto a 5-7 km (n=384) / 10-14 km (n=192) mesh: no close-up use; close-ups use build_scene.py.',
            'Albedo w is the 1-deg WAC Hapke map (70N-70S); poleward the regional medians. Other Hapke parameters are constant.',
            'Web base colour is the WAC morphologic mosaic (shading baked in, VISUAL), area-averaged to ~1.3 km then sampled per face texel (2.7 km).',
            'No earthshine, no Earth in the scene; Sun lamp only.',
        ],
    }
    mpath = out / f'{tag}_manifest.json'
    mpath.write_text(json.dumps(manifest, indent=1, default=str))
    print(f'[POLARIS globe] {tag}: {len(V)} verts, mesh {t_mesh:.1f} s, render {t_render and round(t_render, 1)} s, '
          f'glb {glb_info and glb_info["bytes"]} bytes; wrote {blend.name}, {mpath.name}')
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
