"""Coverage of the science pyramid: which product and native resolution back each point (prompt §2.2 item 5, plan §8).

    python -m tools.globe.coverage

Method: every tile of every level is read (decimated so each coverage cell gets >= 8 x 8 samples); each sample with a
finite height adds its area on the sphere to its cell, by native-resolution class and by source_id. Levels are walked
finest first and each level only adds area its cell has not already claimed, so a point is counted once at the finest
level that has data there. Each point is counted in one zone (polar for |lat| >= 57.5 deg, eq below: the same rule as
TerrainStack.sample). Cells: 2560 m (polar grids), 1/8 deg (eq).

Outputs
  docs/v2/COVERAGE_SUMMARY.json / .md (committed): % of the Moon per resolution class and per product.
  web/public/globe/coverage/ (git-ignored, derived from NASA rasters): coverage_res_eqc.png / coverage_src_eqc.png
  (global 0.25 deg equirectangular), coverage_res_sp.png / _np.png (polar stereographic, |lat| >= 55), legend.json.
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import sys
from pathlib import Path

import numpy as np

from science.terrain import stack as S
from tools.globe import pyramid as PY
from tools.globe.seams import write_png

REPO = Path(__file__).resolve().parents[2]
OUT_WEB = REPO / 'web' / 'public' / 'globe' / 'coverage'
SUMMARY_JSON = REPO / 'docs' / 'v2' / 'COVERAGE_SUMMARY.json'
SUMMARY_MD = REPO / 'docs' / 'v2' / 'COVERAGE_SUMMARY.md'
CELL = {'polar': 2560.0, 'eq': 1.0 / 8}
CLASSES = [(5.0, '<= 5 m'), (20.0, '5-20 m'), (40.0, '20-40 m'), (80.0, '40-80 m'), (160.0, '80-160 m'),
           (320.0, '160-320 m'), (math.inf, '> 320 m')]
CLASS_RGB = [(255, 255, 255), (255, 214, 102), (255, 159, 67), (238, 82, 83), (155, 89, 182), (72, 52, 212),
             (34, 47, 62)]
NONE_RGB = (0, 0, 0)
SRC_RGB = {1: (255, 255, 255), 2: (46, 204, 113), 3: (255, 214, 102), 4: (52, 152, 219), 5: (238, 82, 83),
           6: (155, 89, 182), 7: (26, 188, 156), 8: (127, 140, 141)}
MOON_AREA = 4 * math.pi * S.R ** 2


def class_of(res):
    res = np.asarray(res, float)
    out = np.full(res.shape, len(CLASSES) - 1, np.int8)
    for i in range(len(CLASSES) - 1, -1, -1):
        out = np.where(res <= CLASSES[i][0] * 1.0001, i, out)
    return out


def counted(zone, lat):
    lat = np.asarray(lat, float)
    if zone == 'eq':
        return np.abs(lat) < S.ZONE_SWITCH_ABS_LAT
    return lat <= -S.ZONE_SWITCH_ABS_LAT if zone == 'sp' else lat >= S.ZONE_SWITCH_ABS_LAT


def pixel_area(zone, lat, p):
    """Area on the sphere (m^2) of a zone pixel of grid size p centred at latitude lat."""
    lat = np.asarray(lat, float)
    if zone == 'eq':
        d = math.radians(p)
        la = np.radians(lat)
        return S.R ** 2 * d * (np.sin(np.minimum(la + d / 2, math.pi / 2)) - np.sin(np.maximum(la - d / 2, -math.pi / 2)))
    k = 2.0 / (1.0 + np.sin(np.radians(np.abs(lat))))
    return (p / k) ** 2


def cell_grid(zone):
    Z = S.ZONES[zone]
    c = CELL[Z.kind]
    return c, int(round((Z.right - Z.left) / c)), int(round((Z.top - Z.bottom) / c))


def cell_areas(zone, sub=8):
    """Counted area of every cell (sub x sub subsamples per cell)."""
    Z = S.ZONES[zone]
    c, nx, ny = cell_grid(zone)
    if zone == 'eq':
        # exact: R^2 dlon (sin lat2 - sin lat1); 57.5 deg lies on a 1/8 deg cell boundary
        top = Z.top - np.arange(ny) * c
        a = S.R ** 2 * math.radians(c) * (np.sin(np.radians(top)) - np.sin(np.radians(top - c)))
        a = np.where(counted('eq', top - c / 2), a, 0.0)
        return np.repeat(a[:, None], nx, axis=1)
    s = c / sub
    us = Z.left + (np.arange(nx * sub) + 0.5) * s
    out = np.zeros((ny, nx))
    for j in range(ny):
        vs = Z.top - (j * sub + np.arange(sub) + 0.5) * s
        U, V = np.meshgrid(us, vs)
        lat, _ = Z.inverse(U, V)
        a = np.where(counted(zone, lat), pixel_area(zone, lat, s), 0.0)
        out[j] = a.reshape(sub, nx, sub).sum(axis=(0, 2))
    return out


def zone_coverage(stack, zone, log=print):
    import rasterio
    from rasterio.enums import Resampling
    Z = S.ZONES[zone]
    c, nx, ny = cell_grid(zone)
    ncls = len(CLASSES)
    frac = np.zeros((ncls, ny, nx)); fsrc = np.zeros((9, ny, nx)); claimed = np.zeros((ny, nx))
    for L in sorted(stack.levels(zone), reverse=True):
        p = Z.pixel(L)
        T = Z.tile_px
        n = min(T, max(8, int(math.ceil(T * p / (c / 8)))))      # samples per tile side (>= 8 per cell side)
        q = T * p / n                                 # decimated pixel size
        aL = np.zeros((ncls, ny, nx)); sL = np.zeros((9, ny, nx))
        tiles = sorted(stack._tiles.get((zone, L), ()))
        for ix, iy in tiles:
            path = S.tile_path(stack.root, zone, L, ix, iy)
            with rasterio.open(path) as ds:
                a = ds.read((1, 2, 3), out_shape=(3, n, n), resampling=Resampling.nearest)
            l, b, r, t = Z.tile_bounds(L, ix, iy)
            us = l + (np.arange(n) + 0.5) * q; vs = t - (np.arange(n) + 0.5) * q
            U, V = np.meshgrid(us, vs)
            lat, _ = Z.inverse(U, V)
            ok = np.isfinite(a[0]) & counted(zone, lat)
            if not ok.any():
                continue
            area = pixel_area(zone, lat[ok], q)
            cx = np.clip(((U[ok] - Z.left) // c).astype(np.int64), 0, nx - 1)
            cy = np.clip(((Z.top - V[ok]) // c).astype(np.int64), 0, ny - 1)
            cls = class_of(a[2][ok]); src = np.clip(a[1][ok].astype(np.int64), 0, 8)
            # O(samples) accumulation (a dense bincount per tile was O(cells) = hours for 49k eq tiles)
            np.add.at(aL, (cls.astype(np.int64), cy, cx), area)
            np.add.at(sL, (src, cy, cx), area)
        tot = aL.sum(0)
        new = np.clip(tot - claimed, 0, None)
        share = np.where(tot > 0, new / np.where(tot > 0, tot, 1), 0.0)
        frac += aL * share; fsrc += sL * share; claimed += new
        log(f'coverage {zone} L{L}: {len(tiles)} tiles, +{new.sum() / MOON_AREA * 100:.4f} % of the Moon')
    return frac, fsrc, claimed


def run(root=None, write=True, log=print):
    root = Path(root) if root else PY.pyramid_root()
    stack = S.TerrainStack.open(root)
    per_class = np.zeros(len(CLASSES)); per_src = np.zeros(9); counted_area = {}
    maps = {}
    for zone in ('sp', 'np', 'eq'):
        ca = cell_areas(zone)
        counted_area[zone] = float(ca.sum())
        if stack.levels(zone):
            frac, fsrc, claimed = zone_coverage(stack, zone, log=log)
        else:
            c, nx, ny = cell_grid(zone)
            frac = np.zeros((len(CLASSES), ny, nx)); fsrc = np.zeros((9, ny, nx)); claimed = np.zeros((ny, nx))
        claimed = np.minimum(claimed, ca)
        per_class += frac.sum(axis=(1, 2)); per_src += fsrc.sum(axis=(1, 2))
        maps[zone] = (frac, fsrc, claimed, ca)
    total = sum(counted_area.values())
    none = max(0.0, MOON_AREA - per_class.sum())
    summary = {
        'created_utc': _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'label': 'SOURCE-BASED · UNVALIDATED',
        'what': 'share of the lunar sphere (4 pi R^2, R = 1737.4 km) backed by real terrain in the science pyramid, '
                'by native resolution of the finest product present and by product (source_id)',
        'method': __doc__.strip().split('\n\n')[1],
        'moon_area_km2': MOON_AREA / 1e6, 'counted_area_check_pct': 100 * total / MOON_AREA,
        'percent_by_resolution': {lab: round(100 * float(v) / MOON_AREA, 6) for (_, lab), v in zip(CLASSES, per_class)},
        'percent_no_terrain': round(100 * none / MOON_AREA, 6),
        'percent_by_source_id': {str(i): round(100 * float(per_src[i]) / MOON_AREA, 6) for i in range(1, 9) if per_src[i] > 0},
        'km2_by_resolution': {lab: round(float(v) / 1e6, 1) for (_, lab), v in zip(CLASSES, per_class)},
        'tiles': len(stack.index.get('tiles', [])),
        'levels': {z: stack.levels(z) for z in ('sp', 'np', 'eq')},
        'products': [{k: p.get(k) for k in ('product_id', 'source_id', 'native_res_m', 'version', 'url')}
                     for p in stack.index.get('products', [])],
    }
    if write:
        SUMMARY_JSON.write_text(json.dumps(summary, indent=1) + '\n')
        SUMMARY_MD.write_text(markdown(summary))
        write_layers(maps)
    return summary


def markdown(s):
    names = json.loads((REPO / 'docs' / 'v2' / 'SOURCE_IDS.json').read_text())
    lines = ['# Terrain coverage of the science pyramid (generated by `python -m tools.globe.coverage`)', '',
             f"Generated {s['created_utc']}. {s['label']}. {s['what']}.", '',
             '| Native resolution of the finest product | % of the Moon | km² |', '|---|---|---|']
    for lab, v in s['percent_by_resolution'].items():
        lines.append(f"| {lab} | {v:.4f} | {s['km2_by_resolution'][lab]:,.0f} |")
    lines.append(f"| no terrain in the pyramid yet | {s['percent_no_terrain']:.4f} | |")
    lines += ['', '| source_id | product family | % of the Moon (finest level) |', '|---|---|---|']
    for k, v in s['percent_by_source_id'].items():
        lines.append(f'| {k} | {names.get(k, "?")} | {v:.4f} |')
    lines += ['', 'Products merged:', '']
    for p in s['products']:
        lines.append(f"- `{p['product_id']}` (source {p['source_id']}, {p['native_res_m']} m): {p.get('version') or ''}")
    lines += ['', f"Pyramid tiles: {s['tiles']}; levels per zone: {s['levels']}.", '',
              'Method: ' + ' '.join(s['method'].split()), '']
    return '\n'.join(lines)


def _dominant(frac, claimed, ca):
    k = np.argmax(frac, axis=0).astype(np.int16)
    return np.where(claimed >= 0.5 * np.maximum(ca, 1e-9), k, -1)


def write_layers(maps, out=OUT_WEB):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    cls_rgb = np.array(CLASS_RGB + [NONE_RGB], np.uint8)
    src_rgb = np.array([NONE_RGB] + [SRC_RGB[i] for i in range(1, 9)] + [NONE_RGB], np.uint8)
    dom = {zone: (_dominant(frac, claimed, ca), _dominant(fsrc, claimed, ca))
           for zone, (frac, fsrc, claimed, ca) in maps.items()}

    def lookup(La, Lo):
        """Dominant class / source at lat/lon, each point read from the zone that owns it (57.5 deg rule)."""
        zn = S.zone_name_for(La)
        res = np.full(La.shape, len(CLASSES), np.int16); src = np.zeros(La.shape, np.int16)
        for zone in ('sp', 'np', 'eq'):
            m = zn == zone
            if not m.any():
                continue
            Z = S.ZONES[zone]
            c, nx, ny = cell_grid(zone)
            u, v = Z.forward(La[m], Lo[m])
            cx = np.clip(((u - Z.left) // c).astype(np.int64), 0, nx - 1)
            cy = np.clip(((Z.top - v) // c).astype(np.int64), 0, ny - 1)
            dc, ds = dom[zone]
            res[m] = np.where(dc[cy, cx] >= 0, dc[cy, cx], len(CLASSES)); src[m] = np.where(ds[cy, cx] >= 0, ds[cy, cx], 0)
        return res, src

    for zone in ('sp', 'np'):
        Z = S.ZONES[zone]
        c, nx, ny = cell_grid(zone)
        U, V = np.meshgrid(Z.left + (np.arange(nx) + 0.5) * c, Z.top - (np.arange(ny) + 0.5) * c)
        lat, lon = Z.inverse(U, V)
        res, _ = lookup(lat, lon)
        rgba = np.zeros((ny, nx, 4), np.uint8)
        rgba[..., :3] = cls_rgb[res]
        rgba[..., 3] = np.where(Z.in_zone(lat), 255, 0)
        write_png(out / f'coverage_res_{zone}.png', rgba)
    # global equirectangular 0.25 deg
    lat = 90 - (np.arange(720) + 0.5) * 0.25; lon = -180 + (np.arange(1440) + 0.5) * 0.25
    Lo, La = np.meshgrid(lon, lat)
    res, src = lookup(La, Lo)
    rgba = np.concatenate([cls_rgb[res], np.full(res.shape + (1,), 255, np.uint8)], axis=-1)
    write_png(out / 'coverage_res_eqc.png', rgba)
    rgba = np.concatenate([src_rgb[src], np.full(src.shape + (1,), 255, np.uint8)], axis=-1)
    write_png(out / 'coverage_src_eqc.png', rgba)
    names = json.loads((REPO / 'docs' / 'v2' / 'SOURCE_IDS.json').read_text())
    legend = {
        'label': 'SOURCE-BASED · UNVALIDATED', 'layer': 'terrain coverage (which product / native resolution backs each point)',
        'resolution_classes': [{'label': lab, 'max_m': (None if math.isinf(m) else m), 'rgb': list(rgb)}
                               for (m, lab), rgb in zip(CLASSES, CLASS_RGB)] + [{'label': 'no terrain', 'rgb': list(NONE_RGB)}],
        'sources': [{'source_id': i, 'name': names.get(str(i)), 'rgb': list(SRC_RGB[i])} for i in range(1, 9)],
        'files': {'coverage_res_eqc.png': 'equirectangular, 0.25 deg, lon -180..180 left->right, lat 90..-90 top->bottom',
                  'coverage_src_eqc.png': 'same grid, dominant source_id',
                  'coverage_res_sp.png': f'south polar stereographic {S.PROJ4["sp"]}, 2560 m cells, extent +-{S.POLAR_HALF_M:.0f} m',
                  'coverage_res_np.png': f'north polar stereographic {S.PROJ4["np"]}, 2560 m cells, extent +-{S.POLAR_HALF_M:.0f} m'},
        'cell_rule': 'cell shows the class (or source) with the largest area if >= 50 % of the cell has terrain, else "no terrain"',
    }
    (out / 'legend.json').write_text(json.dumps(legend, indent=1))


def main(argv=None):
    s = run()
    print(json.dumps({k: s[k] for k in ('percent_by_resolution', 'percent_no_terrain', 'percent_by_source_id')}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
