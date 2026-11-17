"""POLARIS X v2 showcase: one .blend that gathers the v2 work, one Blender scene per section (presentation only).

    blender -b --python-exit-code 1 -P blender/v2/showcase_v2.py -- [--dir blender/output/v2/showcase] [--qa]

Inputs (all built beforehand, git-ignored, in --dir):
  moon_globe.blend                  blender/v2/globe.py           whole Moon, Sun from the bundle at 2026-11-21T02:00Z
  site*_eva_eye / _lroc_* .blend    blender/v2/build_scene.py     site close-ups, Sun/Earth/skyline from spec.py
  showcase_inputs.json              blender/v2/showcase_prep.py   Mars skyline + relay tracks (Horizons), gallery list
Nothing here computes science. Scenes appended from the builders keep their own lights (bundle Sun/Earth), cameras and
labels. New scenes: render-vs-real galleries (real | render | ... thumbnails, crops of NASA images: local only) and the
Mars Jezero sky dome. Organisation follows the blender-skills `scene-assembly` / `camera-cinematography` conventions
(COL_* collections, CAM_* cameras); no art-directed lights are added anywhere (AGENTS.md: the Sun is never a lamp choice).
Output: <dir>/POLARIS_X_v2_showcase.blend (+ --qa: <dir>/qa/<scene>.png viewport-style renders of the new scenes).
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
LABELS = {
    'terrain': 'terrain SOURCE-BASED · UNVALIDATED', 'photometry': 'photometry MODEL', 'stars': 'stars VISUAL',
    'gallery': 'scores SOURCE-BASED · UNVALIDATED; thumbnails are crops of NASA LROC images (NASA/GSFC/ASU), local only',
    'mars': 'relay geometry SOURCE-BASED · UNVALIDATED (geometry only, not relay availability); dome layout VISUAL',
}


def args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=str(ROOT / 'blender' / 'output' / 'v2' / 'showcase'))
    ap.add_argument('--qa', action='store_true')
    return ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])


def eevee():
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try:
            bpy.context.scene.render.engine = eng
            return eng
        except TypeError:
            continue
    bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
    return 'BLENDER_WORKBENCH'


def new_scene(name, label):
    sc = bpy.data.scenes.new(name)
    sc['polaris_label'] = label
    w = bpy.data.worlds.new(f'{name} world')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    sc.world = w
    return sc


def collection(sc, name):
    c = bpy.data.collections.new(name)
    sc.collection.children.link(c)
    return c


def emission_mat(name, rgb=(1, 1, 1), strength=1.0, image=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value = strength
    if image is not None:
        tx = nt.nodes.new('ShaderNodeTexImage')
        tx.image = image
        tx.interpolation = 'Closest'
        nt.links.new(tx.outputs['Color'], em.inputs['Color'])
    else:
        em.inputs['Color'].default_value = (*rgb, 1.0)
        m.diffuse_color = (*rgb, 1.0)                    # Solid / Workbench view colour
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    return m


def text(col, body, loc, size=0.3, mat=None, name='TXT'):
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = body
    cu.size = size
    ob = bpy.data.objects.new(name, cu)
    ob.location = loc
    if mat:
        ob.data.materials.append(mat)
    col.objects.link(ob)
    return ob


def ortho_camera(sc, col, name, loc, scale, rot=(0, 0, 0)):
    cd = bpy.data.cameras.new(name)
    cd.type = 'ORTHO'
    cd.ortho_scale = scale
    cd.clip_end = 1e6
    ob = bpy.data.objects.new(name, cd)
    ob.location = loc
    ob.rotation_euler = rot
    col.objects.link(ob)
    sc.camera = ob
    return ob


def overview_camera(sc):
    """CAM_Overview_Oblique: a 35 mm camera 45 deg above the near terrain, looking at its centre (navigation aid; the
    builder's own camera stays the scene camera)."""
    meshes = [o for o in sc.objects if o.type == 'MESH' and o.name.upper().startswith('TERRAIN')] or \
             [o for o in sc.objects if o.type == 'MESH']
    if not meshes:
        return None
    pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    near = [o for o in meshes if 'near' in o.name.lower()] or meshes
    pn = [o.matrix_world @ Vector(c) for o in near for c in o.bound_box]
    ctr = sum(pn, Vector()) / len(pn)
    size = max((hi - lo).x, (hi - lo).y) * 0.15 if len(near) < len(meshes) else max((hi - lo).x, (hi - lo).y) * 0.6
    nm = f"CAM_Overview_Oblique_{sc.name.split(' ')[0]}"
    cd = bpy.data.cameras.new(nm)
    cd.lens = 35
    cd.clip_end = 1e7
    cam = bpy.data.objects.new(nm, cd)
    cam.location = ctr + Vector((0.0, -size, size))
    cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.collection.objects.link(cam)
    return cam


def append_scenes(path, prefix):
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.scenes = list(src.scenes)
    out = []
    for i, sc in enumerate(dst.scenes):
        sc.name = prefix if len(dst.scenes) == 1 else f'{prefix} ({i + 1})'
        out.append(sc)
    return out


def gallery_scene(name, items, label, note):
    sc = new_scene(name, label)
    bpy.context.window.scene = sc if bpy.context.window else sc
    cg, ct, cc = collection(sc, 'COL_Gallery'), collection(sc, 'COL_Labels'), collection(sc, 'COL_Cameras')
    white = emission_mat(f'{name} text', (0.9, 0.9, 0.9))
    ncol, w = 4, 4.0
    x0 = y0 = 0.0
    row_h = []
    for i, it in enumerate(items):
        img = bpy.data.images.load(it['path'], check_existing=True)
        iw, ih = img.size
        h = w * ih / max(iw, 1)
        r, c = divmod(i, ncol)
        while len(row_h) <= r:
            row_h.append(0.0)
        row_h[r] = max(row_h[r], h)
        y = -sum(row_h[:r]) - 1.0 * r
        bpy.ops.mesh.primitive_plane_add(size=1.0)
        pl = bpy.context.active_object
        for cl in pl.users_collection:
            cl.objects.unlink(pl)
        cg.objects.link(pl)
        pl.name = f"IMG_{it['product_id']}__{it['site']}"
        pl.scale = (w, h, 1)
        pl.location = (x0 + c * (w + 0.4) + w / 2, y - h / 2, 0)
        pl.data.materials.append(emission_mat(f'mat {pl.name}', image=img))
        iou = it.get('iouShadow')
        ed = it.get('edgeMedianM')
        cap = f"{it['product_id']} {it['site']}  IoU {iou:.3f}" if isinstance(iou, float) else f"{it['product_id']} {it['site']}"
        if isinstance(ed, float) and math.isfinite(ed):
            cap += f"  edge {ed:.1f} m"
        text(ct, cap, (x0 + c * (w + 0.4), y + 0.12, 0), 0.16, white, f'TXT_{pl.name}')
    total_w = ncol * (w + 0.4)
    total_h = sum(row_h) + 1.0 * len(row_h)
    text(ct, f'{name}\n{note}\n{label}', (0, 1.6, 0), 0.22, white, 'TXT_title')
    ortho_camera(sc, cc, 'CAM_Gallery_Ortho', (total_w / 2, -total_h / 2 + 0.8, 10), max(total_w, total_h + 2.5) * 1.05)
    sc.render.resolution_x, sc.render.resolution_y = 1600, int(1600 * (total_h + 2.5) / total_w) if total_w else 900
    return sc


def sky_xyz(az, el, R):
    a, e = math.radians(az), math.radians(el)
    return Vector((R * math.cos(e) * math.sin(a), R * math.cos(e) * math.cos(a), R * math.sin(e)))


def poly_curve(col, name, pts, mat, bevel=0.03):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = bevel
    for seg in pts:
        if len(seg) < 2:
            continue
        sp = cu.splines.new('POLY')
        sp.points.add(len(seg) - 1)
        for p, v in zip(sp.points, seg):
            p.co = (v.x, v.y, v.z, 1.0)
    ob = bpy.data.objects.new(name, cu)
    ob.data.materials.append(mat)
    col.objects.link(ob)
    return ob


def mars_scene(M):
    sc = new_scene('08 Mars — Jezero rim relay sky dome', LABELS['mars'])
    cs, co, ct, cc = (collection(sc, n) for n in ('COL_Sky', 'COL_Orbiters', 'COL_Labels', 'COL_Cameras'))
    R = 10.0
    grid = emission_mat('dome grid', (0.25, 0.25, 0.3))
    white = emission_mat('dome text', (0.9, 0.9, 0.9))
    rings = [[sky_xyz(a, e, R) for a in range(0, 361, 3)] for e in (0, 15, 30, 45, 60, 75)]
    spokes = [[sky_xyz(a, e, R) for e in range(0, 91, 3)] for a in range(0, 360, 30)]
    poly_curve(cs, 'GRID_alt_az', rings + spokes, grid, 0.01)
    sk = M['skyline']
    terr = emission_mat('terrain skyline (bundle)', (0.85, 0.55, 0.25))
    poly_curve(cs, 'SKYLINE_terrain_bundle', [[sky_xyz(a, e, R) for a, e in zip(sk['az'] + sk['az'][:1], sk['el'] + sk['el'][:1])]], terr, 0.04)
    for lab, az in (('N', 0), ('E', 90), ('S', 180), ('W', 270)):
        text(ct, lab, sky_xyz(az, -4, R * 1.08), 0.6, white, f'TXT_{lab}')
    colours = {'relay-mro': (0.05, 0.45, 1.0), 'relay-tgo': (0.1, 0.85, 0.15), 'relay-mex': (0.95, 0.1, 0.55), 'relay-maven': (1, 1, 0)}
    legend = []
    for o in M['orbiters']:
        if o['status'] != 'computed':
            legend.append(f"{o['name']}: {o['status']}")
            continue
        vis_m = emission_mat(f"{o['id']} visible", colours.get(o['id'], (1, 1, 1)), 1.0)
        hid_m = emission_mat(f"{o['id']} below terrain skyline", tuple(0.25 * c for c in colours.get(o['id'], (1, 1, 1))), 1.0)
        segs = {True: [], False: []}
        cur, state = [], None
        for az, el, v in zip(o['az'], o['el'], o['visible']):
            if el < -2:
                if len(cur) > 1:
                    segs[state].append(cur)
                cur, state = [], None
                continue
            if state is not None and v != state:
                segs[state].append(cur + [sky_xyz(az, el, R)])
                cur = []
            state = v
            cur.append(sky_xyz(az, el, R))
        if len(cur) > 1:
            segs[state].append(cur)
        poly_curve(co, f"TRACK_{o['id']}_visible", segs[True], vis_m, 0.05)
        poly_curve(co, f"TRACK_{o['id']}_hidden", segs[False], hid_m, 0.02)
        nvis = sum(o['visible'])
        cname = {'relay-mro': 'blue', 'relay-tgo': 'green', 'relay-mex': 'magenta'}.get(o['id'], '')
        legend.append(f"{o['name']} ({cname}): {nvis} min above the terrain skyline in the first {M['hours']} h")
    text(ct, f"Jezero crater rim (Mars) — relay orbiters, {M['window_start_utc']} UTC + {M['hours']} h\n"
             f"bright = above the bundle's terrain skyline (orange); dim = hidden by terrain\n" + '\n'.join(legend) +
         f"\n{LABELS['mars']}", (-R, -R - 3.5, 0), 0.32, white, 'TXT_legend')
    ortho_camera(sc, cc, 'CAM_Dome_Top', (0, -1.5, 40), 2 * R + 9)
    cp = bpy.data.cameras.new('CAM_Dome_Persp')
    cp.lens = 35
    ob = bpy.data.objects.new('CAM_Dome_Persp', cp)
    ob.location = (18, -26, 14)
    ob.rotation_euler = (math.radians(68), 0, math.radians(34))
    cc.objects.link(ob)
    sc.render.resolution_x = sc.render.resolution_y = 1400
    return sc


def everything_scene():
    """10 Everything at once: every section on one board as scaled collection instances (no copies), viewed in Solid
    mode with texture colours (no lamps are added; the appended site lamps are not instanced)."""
    sc = new_scene('10 Everything at once', 'board of all sections; scales differ per tile (each tile is labelled)')
    ct, cc, cb = collection(sc, 'COL_Labels'), collection(sc, 'COL_Cameras'), collection(sc, 'COL_Board')
    white = emission_mat('board text', (0.92, 0.92, 0.92))
    TILE = 100.0

    def pick(scene_prefix, keep):
        src = next((x for x in bpy.data.scenes if x.name.startswith(scene_prefix)), None)
        return src, ([o for o in src.objects if keep(o)] if src else [])

    tiles = [
        ('01', 'Whole Moon (globe.py)', lambda o: o.type == 'MESH' and o.name.startswith('MOON |'), 'fit'),
        ('02', 'Site01 RoI6 near terrain, PGDA 78 5 m', lambda o: o.type == 'MESH' and ('near' in o.name or o.name.startswith('ASSET')), 'fit'),
        ('03', 'Site04 RoI3 near terrain, PGDA 78 5 m', lambda o: o.type == 'MESH' and ('near' in o.name or o.name.startswith('ASSET')), 'fit'),
        ('08', 'Mars Jezero rim: relay sky dome', lambda o: o.type in ('CURVE', 'FONT'), 'fit'),
        ('06', 'Render vs real: LROC NAC held-out (A5)', lambda o: o.type in ('MESH', 'FONT'), 'fit'),
        ('07', 'Render vs real: LROC WAC dev (A6)', lambda o: o.type in ('MESH', 'FONT'), 'fit'),
        ('09', 'Render vs real: LROC WAC held-out (A7)', lambda o: o.type in ('MESH', 'FONT'), 'fit'),
    ]
    x = 0.0
    heights = []
    for i, (pref, title, keep, _mode) in enumerate(tiles):
        src, objs = pick(pref, keep)
        if not objs:
            continue
        col = bpy.data.collections.new(f'ALL_{pref}')
        for o in objs:
            col.objects.link(o)
        pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        gallery = pref in ('06', '07', '09')
        size = (hi.x - lo.x) if gallery else max(hi.x - lo.x, hi.y - lo.y)    # galleries fit their width
        k = TILE / size if size > 0 else 1.0
        ctr = (lo + hi) / 2
        flip = pref == '01'                                          # globe: show the south pole, where the sites are
        col.instance_offset = Vector((ctr.x, ctr.y, ctr.z)) if flip else Vector((ctr.x, hi.y, ctr.z))
        em = bpy.data.objects.new(f'BOARD_{pref}', None)
        em.instance_type = 'COLLECTION'
        em.instance_collection = col
        em.scale = (k, k, k)
        if flip:
            em.rotation_euler = (math.pi, 0.0, 0.0)
        em.location = (x + TILE / 2, -TILE / 2 if flip else 0.0, 0.0)
        cb.objects.link(em)
        heights.append((hi.y - lo.y) * k)
        sc_txt = f'1 : {1 / k:,.0f}' if k < 1 else f'x {k:,.1f}'
        text(ct, f'{pref}  {title}' + (' (south pole up)' if flip else '') + f'\n(scale {sc_txt} of its scene units)',
             (x, 14.0, 0), 3.2, white, f'TXT_board_{pref}')
        x += TILE * 1.15
    text(ct, 'POLARIS X v2 — everything at once (Solid view; each tile has its own scale; galleries are NASA crops, local only)',
         (0, 30, 0), 4.5, white, 'TXT_board_title')
    H = max(heights + [TILE]) + 40
    ortho_camera(sc, cc, 'CAM_Board_Top', (x / 2, 30 - H / 2, 1e4), max(x, H) * 1.02)
    sc.render.resolution_x = 3200 if x >= H else int(3200 * x / H)
    sc.render.resolution_y = int(3200 * H / x) if x >= H else 3200
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'TEXTURE'
    return sc


def index_scene(sections):
    sc = new_scene('00 Index — POLARIS X v2 showcase', 'index')
    ct, cc = collection(sc, 'COL_Labels'), collection(sc, 'COL_Cameras')
    white = emission_mat('index text', (0.92, 0.92, 0.92))
    body = 'POLARIS X v2 — showcase (switch scenes with the Scene selector, top right)\n\n' + '\n'.join(
        f'{n}\n    {d}' for n, d in sections) + ('\n\nNothing in this file computes science. Builders: blender/v2/globe.py, '
                                              'build_scene.py; Mars and galleries from showcase_prep.py.')
    text(ct, body, (0, 0, 0), 0.28, white, 'TXT_index')
    ortho_camera(sc, cc, 'CAM_Index', (8.5, -7.5, 10), 19)
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1200
    return sc


def main():
    a = args()
    d = Path(a.dir)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    default = bpy.context.scene
    sections = []
    for f, title, desc in (
            ('moon_globe.blend', '01 Whole Moon', 'globe.py: cube-sphere from the pyramid L0, Hapke + WAC albedo, Sun at 2026-11-21T02:00Z'),
            ('site01_roi6_eva_eye.blend', '02 Site01 RoI6 — 1.7 m eye', 'build_scene.py: PGDA 78 terrain, bundle Sun/Earth/skyline'),
            ('site04_roi3_eva_eye.blend', '03 Site04 RoI3 — 1.7 m eye', 'build_scene.py: as above'),
            ('site01_roi6_lroc_nac.blend', '04 Site01 RoI6 — LROC NAC view', 'build_scene.py: orbital NAC camera preset'),
            ('site04_roi3_lroc_wac.blend', '05 Site04 RoI3 — LROC WAC view', 'build_scene.py: orbital WAC camera preset')):
        p = d / f
        if p.exists():
            for sc in append_scenes(p, title):
                if not title.startswith('01'):
                    overview_camera(sc)
            sections.append((title, desc))
        else:
            sections.append((title, f'not built ({f} missing)'))
    M = json.loads((d / 'showcase_inputs.json').read_text())
    g = M['galleries']
    if g.get('nac_heldout'):
        gallery_scene('06 Render vs real — LROC NAC held-out (A5)', g['nac_heldout'], LABELS['gallery'],
                      'thumbnails: real | render | log difference | edges (report_heldout.py --gallery)')
        sections.append(('06 Render vs real — LROC NAC held-out (A5)', f"{len(g['nac_heldout'])} local thumbnails with their scores"))
    if g.get('wac_dev'):
        gallery_scene('07 Render vs real — LROC WAC dev pilot (A6)', g['wac_dev'], LABELS['gallery'],
                      'thumbnails: real | render | real with predicted shadow in blue (wac_report.py --gallery)')
        sections.append(('07 Render vs real — LROC WAC dev pilot (A6)', f"{len(g['wac_dev'])} local thumbnails with their scores"))
    if g.get('wac_heldout'):
        gallery_scene('09 Render vs real — LROC WAC held-out (A7)', g['wac_heldout'], LABELS['gallery'],
                      'thumbnails: real | render | real with predicted shadow in blue; claim not met (Otsu threshold at the floor)')
        sections.append(('09 Render vs real — LROC WAC held-out (A7)', f"{len(g['wac_heldout'])} local thumbnails with their scores"))
    mars_scene(M['mars'])
    sections.append(('08 Mars — Jezero rim relay sky dome', 'skyline from the Mars bundle; MRO/TGO/MEX per-minute tracks (Horizons)'))
    sections.append(('10 Everything at once', 'all sections on one board (opens here)'))
    allsc = everything_scene()
    idx = index_scene(sections)
    if default.name != idx.name and not default.objects:
        bpy.data.scenes.remove(default)
    for sc in bpy.data.scenes:
        if sc.get('polaris_label') is not None or sc.name.startswith(('00', '06', '07', '08', '09', '10')):
            bpy.context.window_manager.windows[0].scene = sc if bpy.context.window_manager.windows else sc
    for wm in bpy.data.window_managers:                      # open on the board, in Solid view with texture colours
        for win in wm.windows:
            win.scene = allsc
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == 'VIEW_3D':
                sp = area.spaces[0]
                sp.shading.type = 'SOLID'
                sp.shading.color_type = 'TEXTURE'
                sp.clip_end = 1e7
    txt = bpy.data.texts.new('README_POLARIS_v2_showcase')
    txt.write(__doc__ + '\n\nSections:\n' + '\n'.join(f'{n}: {s}' for n, s in sections))
    out = d / 'POLARIS_X_v2_showcase.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
    print('saved', out, 'scenes:', [s.name for s in bpy.data.scenes])
    if a.qa:
        qa = d / 'qa'
        qa.mkdir(exist_ok=True)
        for sc in bpy.data.scenes:
            if not sc.name.startswith(('00', '06', '07', '08', '09', '10')) or sc.camera is None:
                continue
            bpy.context.window.scene = sc if bpy.context.window else sc
            for eng in (() if sc.name.startswith('10') else ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE')):
                try:
                    sc.render.engine = eng
                    break
                except TypeError:
                    continue
            sc.render.filepath = str(qa / (sc.name.split(' ')[0] + '.png'))
            sc.render.image_settings.file_format = 'PNG'
            sc.view_settings.view_transform = 'Standard'
            bpy.ops.render.render(write_still=True, scene=sc.name)
            print('qa', sc.render.filepath)


if __name__ == '__main__':
    main()
