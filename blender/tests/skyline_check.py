"""Skyline consistency: does the terrain Blender draws produce the solver's skyline? (runs inside Blender)

    blender -b -P blender/tests/skyline_check.py -- --site site01_roi6 [--terrain cache|committed] [--deg 0.05]

Builds the scene for the bundle site with every terrain tile planned as in view (angular pixel --deg), then for each of the
bundle's 720 skyline bins bisects, by Blender ray casts from the mast top (site ground + bundle mast), the elevation where the
drawn terrain stops blocking. Reports blender_el - bundle_el per bin. Pure display check: the solver's skyline is the science;
this measures how faithfully the 3D picture reproduces it (LOD decimation, mesh interpolation, far-ring reach).
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent))
ROOT = TESTS.parents[1]

SITES = {'site01_roi6': (-89.47409, -137.3813), 'site04_roi3': (-89.78012, -156.32023), 'site04_roi4': (-89.7848, -155.94606),
         'site01': (-89.4632, -137.49)}


def measure(site, terrain='cache', deg=0.05, budget=6_000_000, utc='2026-11-14T00:00Z', out=None):
    from v2 import astro, build_scene
    lat, lon = SITES[site]
    out = out or str(ROOT / 'blender' / 'output' / 'v2' / 'skyline')
    args = ['--lat', str(lat), '--lon', str(lon), '--utc', utc, '--camera', 'eva_eye', '--terrain', terrain, '--no-stars',
            '--no-overlays', '--no-render', '--all-around', '--all-around-deg', str(deg), '--budget', str(budget),
            '--layout', 'single', '--out', out, '--tag', f'skyline_{site}_{terrain}']
    manifest, _, _ = build_scene.build(build_scene.parse(args))
    sp = json.loads((Path(out) / f'skyline_{site}_{terrain}_spec.json').read_text())
    for ob in list(bpy.data.objects):                       # keep terrain only
        if not ob.name.startswith('TERRAIN'):
            bpy.data.objects.remove(ob, do_unlink=True)
    dg = bpy.context.evaluated_depsgraph_get()
    sc = bpy.context.scene
    eye = Vector((0.0, 0.0, sp['site']['mastM']))
    reach = 400_000.0

    def blocked(az, el):
        d = Vector(astro.enu_direction(az, el))
        hit, *_ = sc.ray_cast(dg, eye + d * 0.05, d, distance=reach)
        return hit

    az, el_b, cd = sp['skyline']['azimuthDeg'], sp['skyline']['elevationDeg'], sp['skyline']['criticalDistanceM']
    rows, dist = [], []
    for a, e, c in zip(az, el_b, cd):
        if e is None:
            continue
        dist.append(c or 0.0)
        lo, hi = e - 3.0, e + 3.0
        if not blocked(a, lo) or blocked(a, hi):
            rows.append((a, e, None))
            continue
        for _ in range(16):                                  # 6 deg / 2^16 ~ 1e-4 deg
            mid = (lo + hi) / 2
            if blocked(a, mid):
                lo = mid
            else:
                hi = mid
        rows.append((a, e, (lo + hi) / 2))
    d = np.array([r[2] - r[1] for r in rows if r[2] is not None])
    res = {'site': site, 'terrain': terrain, 'angularPixelDeg': deg, 'bins': len(rows), 'bracketed': int(len(d)),
           'unbracketed': int(sum(r[2] is None for r in rows)),
           'medianDeg': float(np.median(d)), 'medianAbsDeg': float(np.median(np.abs(d))), 'p95AbsDeg': float(np.percentile(np.abs(d), 95)),
           'maxAbsDeg': float(np.abs(d).max()), 'meanDeg': float(d.mean()),
           'tiles': manifest['terrain']['byLevel'], 'vertexEstimate': manifest['terrain']['vertexEstimate'], 'k': manifest['terrain']['k']}
    dd = np.array([c for c, r in zip(dist, rows) if r[2] is not None])
    for name, sel in (('near (critical point < 100 m)', dd < 100), ('far (critical point >= 100 m)', dd >= 100)):
        x = np.abs(d[sel])
        res[name] = {'bins': int(sel.sum()), 'medianAbsDeg': float(np.median(x)) if len(x) else None,
                     'p95AbsDeg': float(np.percentile(x, 95)) if len(x) else None, 'maxAbsDeg': float(x.max()) if len(x) else None}
    res['note'] = ('near bins: Blender triangulates 5 m cells, the solver samples the DEM bilinearly every 1 m, so a critical point a few '
                   'tens of metres away differs by decimetres (tenths of a degree); far bins also carry LOD decimation')
    worst = sorted(((abs(r[2] - r[1]), r[0], r[1], r[2]) for r in rows if r[2] is not None), reverse=True)[:5]
    res['worstBins'] = [{'azDeg': w[1], 'bundleElDeg': w[2], 'blenderElDeg': round(w[3], 4)} for w in worst]
    return res


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument('--site', default='site01_roi6')
    p.add_argument('--terrain', default='cache')
    p.add_argument('--deg', type=float, default=0.05)
    p.add_argument('--budget', type=int, default=6_000_000)
    a = p.parse_args(argv)
    r = measure(a.site, a.terrain, a.deg, a.budget)
    print('[skyline] ' + json.dumps(r))
