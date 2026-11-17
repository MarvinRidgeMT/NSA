"""Render twin of one real LROC WAC 643 nm window, inside Blender (Cycles CPU, OSL push-frame camera).

    blender -b --factory-startup --python-exit-code 1 -P tools/validation/render_vs_real/wac_twin.py -- \
        --geometry <geom.json> --osl <camera.osl> --products pgda78_5m,flat --out <dir> [--spp 32]

Identical to blender_twin.py (the NAC twin, frozen for A5; imported here, not edited): same terrain levels and tiles, Hapke /
lunar-Lambert / Lommel-Seeliger materials, Sun lamp, render passes and outputs. Two differences only:
  * the camera is the per-image OSL push-frame camera from wac_camera.osl_source;
  * the view cone for the tile planner comes from the geometry file (`view`, computed by wac_geometry.view_cone from the
    fitted WAC rays), and the planner's pixel angle is the WAC IFOV.
"""
import json
import math
import sys
import time
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import blender_twin as BT  # noqa: E402

T, hapke, hapke_nodes = BT.T, BT.hapke, BT.hapke_nodes


def main():
    a = BT.args()
    G = json.loads(Path(a.geometry).read_text())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    BT.reset_scene()
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    cy = sc.cycles
    cy.device = 'CPU'
    cy.shading_system = True
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = a.threads
    cy.use_denoising = False
    cy.use_adaptive_sampling = False
    cy.seed = 0
    sc.render.film_transparent = True
    sc.render.resolution_x = int(G['render_w'])
    sc.render.resolution_y = int(G['render_h'])
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = 'Raw'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = 0.0
    sc.view_settings.gamma = 1.0
    sc.render.image_settings.file_format = 'OPEN_EXR'
    sc.render.image_settings.color_depth = '32'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.render.use_persistent_data = True
    world = bpy.data.worlds.new('airless')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.0
    sc.world = world

    txt = bpy.data.texts.new('pushframe.osl')
    txt.write(Path(a.osl).read_text())
    cd = bpy.data.cameras.new('pushframe')
    cd.type = 'CUSTOM'
    cd.custom_mode = 'INTERNAL'
    cd.custom_shader = txt
    cd.clip_start = 1.0
    cd.clip_end = 5.0e6
    co = bpy.data.objects.new('pushframe', cd)
    sc.collection.objects.link(co)
    sc.camera = co

    sun = np.asarray(G['sunEnu'], float)
    sun /= np.linalg.norm(sun)
    dist = float(G['sunDistM'])
    ld = bpy.data.lights.new('Sun', type='SUN')
    ld.energy = BT.TSI_W_M2 / (dist / BT.AU_M) ** 2
    sun_angle = 2.0 * math.asin(BT.R_SUN_M / dist)
    ld.angle = sun_angle
    lo = bpy.data.objects.new('Sun', ld)
    sc.collection.objects.link(lo)
    from mathutils import Vector
    lo.rotation_mode = 'QUATERNION'
    lo.rotation_quaternion = Vector(sun.tolist()).to_track_quat('Z', 'Y')

    frame = T.EnuFrame(G['enu']['lat'], G['enu']['lon'], G['enu']['h0'])
    v = G['view']
    cone = float(v['cone'])
    half_h = half_v = math.atan(math.tan(cone) / math.sqrt(2))
    view = T.View(pos=tuple(v['pos']), fwd=tuple(v['fwd']), half_h=half_h, half_v=half_v, pixel_rad=float(v['ifov']),
                  sun_dir=tuple(sun), sun_radius_rad=sun_angle / 2)
    hp = hapke.params('SOUTH_60_70')
    if a.photometry == 'hapke':
        beauty_mat, _info = hapke_nodes.hapke_material('Hapke regolith', hp, tuple(sun))
    elif a.photometry.startswith('lunarlambert'):
        beauty_mat = BT.lunar_lambert_mat('lunar-Lambert', tuple(sun), float(a.photometry.split(':')[1]))
    elif a.photometry == 'lommel':
        beauty_mat = BT.lunar_lambert_mat('Lommel-Seeliger', tuple(sun), 1.0)
    else:
        raise SystemExit(f'unknown photometry {a.photometry}')
    mats = {'white': BT.node_mat('white', 'white'), 'pos': BT.node_mat('pos', 'pos'), 'nrm': BT.node_mat('nrm', 'nrm')}
    site = G['site']
    tdir = BT.WORK / 'terrain'
    log = {'geometry': a.geometry, 'blender': bpy.app.version_string, 'spp': a.spp, 'bounces': a.bounces,
           'sunAngleDeg': math.degrees(sun_angle), 'sunIrradiance': ld.energy, 'photometry': a.photometry, 'products': {},
           'camera': 'WAC 643 nm push-frame (wac_camera.osl_source)'}
    for prod in a.products.split(','):
        t0 = time.time()
        for o in [o for o in bpy.data.objects if o.name.startswith('TERRAIN')]:
            bpy.data.objects.remove(o, do_unlink=True)
        levels = [BT.level_from_npz(tdir / f'{site}__{prod}.npz', f'near {prod}')]
        if prod != 'flat':
            levels.append(BT.level_from_npz(tdir / f'{site}__far_pgda90_80m.npz', 'far PGDA 90 80 m'))
        tiles, rep = T.plan_tiles(levels, frame, view, budget=a.budget)
        objs = []
        for li, lv in enumerate(levels):
            finer = [levels[j].box() for j in range(li)]
            Vs, Fs, base = [], [], 0
            for t in tiles:
                if t['level'] != li:
                    continue
                V, F, _d = T.tile_mesh(lv, t, frame, finer)
                if len(F):
                    Vs.append(V)
                    Fs.append(F + base)
                    base += len(V)
            if Vs:
                objs.append(BT.mesh_object(f'TERRAIN {lv.name}', np.vstack(Vs), np.vstack(Fs), beauty_mat))
        t_build = time.time() - t0
        res, timings = {}, {}
        for ob in objs:
            ob.data.materials[0] = beauty_mat
        BT.set_smooth(objs, True)
        ld.angle = sun_angle
        cy.samples = a.spp
        cy.max_bounces = a.bounces
        cy.diffuse_bounces = a.bounces
        cy.pixel_filter_type = 'BOX'
        cy.filter_width = 1.0
        t1 = time.time()
        b = BT.render_to_array(out / f'_{prod}_beauty.exr')
        timings['beauty'] = time.time() - t1
        res['beauty'] = b[..., 0]
        res['alpha'] = b[..., 3]
        if a.beauty_only:
            np.savez_compressed(out / f'{prod}__{a.photometry.replace(":", "")}.npz', **res)
            log['products'][prod] = {'buildS': t_build, 'renderS': timings, 'beautyOnly': True}
            print(f'[WAC twin] {prod} {a.photometry}: build {t_build:.1f}s render {timings}', flush=True)
            continue
        BT.set_smooth(objs, False)
        ld.angle = 0.0
        cy.samples = 1
        cy.max_bounces = 0
        cy.diffuse_bounces = 0
        cy.filter_width = 0.01
        for key in ('white', 'pos', 'nrm'):
            for ob in objs:
                ob.data.materials[0] = mats[key]
            t1 = time.time()
            g = BT.render_to_array(out / f'_{prod}_{key}.exr')
            timings[key] = time.time() - t1
            if key == 'white':
                res['lit'] = g[..., 0] > 0.0
                res['hit'] = g[..., 3] > 0.5
            elif key == 'pos':
                res['pos'] = np.where(g[..., 3:4] > 0.5, g[..., :3] - BT.POS_OFFSET, np.nan).astype(np.float32)
            else:
                res['nrm'] = np.where(g[..., 3:4] > 0.5, g[..., :3] * 2 - 1, np.nan).astype(np.float32)
        np.savez_compressed(out / f'{prod}.npz', **res)
        log['products'][prod] = {'tileReport': {k: v2 for k, v2 in rep.items() if k != 'tiles'}, 'buildS': t_build,
                                 'renderS': timings, 'vertices': int(sum(len(o.data.vertices) for o in objs))}
        print(f'[WAC twin] {prod}: build {t_build:.1f}s render {timings}', flush=True)
    (out / f'render_log_{a.photometry.replace(":", "")}.json').write_text(json.dumps(log, indent=1, default=str))


if __name__ == '__main__':
    main()
