"""Global analytics maps from the science pyramid (prompt §2.5, display-only). Plan §10.

    python -m tools.globe.analytics

Maps (git-ignored PNG under web/public/globe/analytics/, committed numbers in docs/v2/PYRAMID_QA.json "analytics"):
  * slope: surface slope from central differences on the level grid (Horn 3x3 not used: one-pixel central differences,
    i.e. a 2-pixel baseline): eq L1 (64 ppd, baseline ~948 m), polar L2 (320 m, baseline 640 m), converted to ground
    metres (eq: R cos(lat) dlon, R dlat; polar: grid metres / stereographic scale k).
  * roughness: RMS slope at a ~1 km baseline (RMS of height differences at lag 2 px on eq L1 = 948 m; lag 3 px on
    polar L2 = 960 m, both axes), per output cell. This is the LOLA-style RMS slope definition computed from the
    gridded pyramid, NOT the PGDA 70 / RMHE shot-based maps (not on disk tonight).
  * Earth-visibility fraction: NOT built (needs libration-aware Earth positions and per-point horizon masks from the
    any-site solver; a smooth-sphere version would be misleading near the limb).
Output grid: global equirectangular 0.125 deg (2880 x 1440), each cell aggregating the pixels of the zone that owns it
(polar for |lat| >= 57.5, eq below), area-weighted.
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
from tools.globe.coverage import counted, pixel_area
from tools.globe.seams import colormap, update_qa_doc, write_png

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / 'web' / 'public' / 'globe' / 'analytics'
CELL_DEG = 0.125
LEVEL = {'eq': 1, 'sp': 2, 'np': 2}
ROUGH_LAG = {"eq": 2, "sp": 3, "np": 3}      # total separation in level pixels: 948 m (eq L1), 960 m (polar L2)
LABEL = 'SOURCE-BASED · UNVALIDATED (display-only analytics)'


def _strip_rows(stack, zone, L, r0, r1, c0, c1):
    rr, cc = np.meshgrid(np.arange(r0, r1), np.arange(c0, c1), indexing='ij')
    return stack._gather(zone, L, rr, cc)[0].astype(np.float64)


def zone_maps(stack, zone, acc, log=print):
    Z = S.ZONES[zone]
    L = LEVEL[zone]
    if L not in stack.levels(zone):
        return
    p = Z.pixel(L); T = Z.tile_px
    npx, npy = Z.n_pixels(L)
    lag = ROUGH_LAG[zone]
    have = stack._tiles[(zone, L)]
    rows_with = sorted({iy for _, iy in have})
    cols_with = sorted({ix for ix, _ in have})
    c0 = (min(cols_with) * T) - lag if Z.kind == 'polar' else 0
    c1 = ((max(cols_with) + 1) * T) + lag if Z.kind == 'polar' else npx
    nx_out, ny_out = int(360 / CELL_DEG), int(180 / CELL_DEG)
    for iy in rows_with:
        r0 = iy * T - lag; r1 = (iy + 1) * T + lag
        if Z.kind == 'eq':
            H = _strip_rows(stack, zone, L, r0, r1, -lag, npx + lag)   # columns wrap in _gather
            u = Z.left + (np.arange(-lag, npx + lag) + 0.5) * p
        else:
            H = _strip_rows(stack, zone, L, r0, r1, c0, c1)
            u = Z.left + (np.arange(c0, c1) + 0.5) * p
        v = Z.top - (np.arange(r0, r1) + 0.5) * p
        U, V = np.meshgrid(u, v)
        lat, lon = Z.inverse(U, V)
        if Z.kind == 'eq':
            mx = S.R * np.cos(np.radians(lat)) * math.radians(p)     # metres per pixel east
            my = np.full(lat.shape, S.R * math.radians(p))            # metres per pixel north
        else:
            k = Z.scale_k(lat)
            mx = my = p / k
        # slope (central differences, interior only)
        dzdx = (H[1:-1, 2:] - H[1:-1, :-2]) / (2 * mx[1:-1, 1:-1])
        dzdy = (H[:-2, 1:-1] - H[2:, 1:-1]) / (2 * my[1:-1, 1:-1])
        slope = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
        # roughness: height differences over a total separation of `lag` px along both axes, assigned to the pixel
        # nearest the pair's midpoint; everything trimmed to the strip's own pixels H[lag:-lag, lag:-lag]
        nr, nc = H.shape[0] - 2 * lag, H.shape[1] - 2 * lag
        o = lag - lag // 2
        hx = (H[:, lag:] - H[:, :-lag])[lag:lag + nr, o:o + nc]
        hy = (H[:-lag, :] - H[lag:, :])[o:o + nr, lag:lag + nc]
        e = lag - 1
        slope = slope[e:e + nr, e:e + nc]
        bx = (lag * mx)[lag:-lag, lag:-lag]; by = (lag * my)[lag:-lag, lag:-lag]
        latc = lat[lag:-lag, lag:-lag]; lonc = lon[lag:-lag, lag:-lag]
        ok = counted(zone, latc) & np.isfinite(slope)
        if not ok.any():
            continue
        area = pixel_area(zone, latc, p)
        cx = np.clip(((lonc + 180.0) / CELL_DEG).astype(np.int64), 0, nx_out - 1)
        cy = np.clip(((90.0 - latc) / CELL_DEG).astype(np.int64), 0, ny_out - 1)
        f = (cy * nx_out + cx)[ok]; a = area[ok]
        acc['area'] += np.bincount(f, a, nx_out * ny_out)
        acc['slope'] += np.bincount(f, a * slope[ok], nx_out * ny_out)
        sx = (hx / bx) ** 2; sy = (hy / by) ** 2
        okr = ok & np.isfinite(sx) & np.isfinite(sy)
        fr = (cy * nx_out + cx)[okr]; ar = area[okr]
        acc['rough_area'] += np.bincount(fr, ar, nx_out * ny_out)
        acc['rough'] += np.bincount(fr, ar * 0.5 * (sx[okr] + sy[okr]), nx_out * ny_out)
        hist = np.histogram(slope[ok], bins=acc['bins'], weights=a)[0]
        acc['hist'][zone] = acc['hist'].get(zone, 0) + hist
    log(f'analytics {zone} L{L}: {len(rows_with)} tile rows')


def run(root=None, write=True, log=print):
    stack = S.TerrainStack.open(root or PY.pyramid_root())
    n = int(360 / CELL_DEG) * int(180 / CELL_DEG)
    acc = {'area': np.zeros(n), 'slope': np.zeros(n), 'rough': np.zeros(n), 'rough_area': np.zeros(n),
           'bins': np.arange(0, 91, 1.0), 'hist': {}}
    for zone in ('sp', 'np', 'eq'):
        zone_maps(stack, zone, acc, log=log)
    shape = (int(180 / CELL_DEG), int(360 / CELL_DEG))
    with np.errstate(invalid='ignore', divide='ignore'):
        slope = (acc['slope'] / acc['area']).reshape(shape)
        rough = np.degrees(np.arctan(np.sqrt(acc['rough'] / acc['rough_area']))).reshape(shape)
    slope[acc['area'].reshape(shape) == 0] = np.nan
    rough[acc['rough_area'].reshape(shape) == 0] = np.nan
    stats = {}
    tot = None
    for z, h in acc['hist'].items():
        tot = h if tot is None else tot + h
    for name, h in list(acc['hist'].items()) + [('moon', tot)]:
        if h is None or h.sum() == 0:
            continue
        c = np.cumsum(h) / h.sum()
        stats[name] = {'median_slope_deg': float(np.interp(0.5, c, acc['bins'][1:])),
                       'p90_slope_deg': float(np.interp(0.9, c, acc['bins'][1:])),
                       'pct_area_slope_gt_10deg': float(100 * h[10:].sum() / h.sum()),
                       'pct_area_slope_gt_20deg': float(100 * h[20:].sum() / h.sum()),
                       'pct_area_slope_gt_30deg': float(100 * h[30:].sum() / h.sum())}
    out = {'created_utc': _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'label': LABEL,
           'method': __doc__.strip().split('\n\n')[1], 'levels': LEVEL, 'roughness_lag_px': ROUGH_LAG,
           'cell_deg': CELL_DEG, 'slope_stats_area_weighted': stats,
           'roughness_median_rms_slope_deg_1km': float(np.nanmedian(rough)),
           'earth_visibility_fraction': 'not built (needs per-point horizon masks + libration-aware Earth positions)'}
    if write:
        OUT.mkdir(parents=True, exist_ok=True)
        write_png(OUT / 'slope_eqc.png', colormap(slope, 40.0))
        write_png(OUT / 'roughness_eqc.png', colormap(rough, 30.0))
        (OUT / 'legend.json').write_text(json.dumps({
            'label': LABEL, 'grid': 'equirectangular 0.125 deg, lon -180..180 left->right, lat 90..-90 top->bottom',
            'slope_eqc.png': 'area-weighted mean slope per cell, colour 0..40 deg (light -> dark)',
            'roughness_eqc.png': 'RMS slope at ~1 km baseline per cell, colour 0..30 deg (light -> dark)',
            'method': out['method']}, indent=1))
        update_qa_doc('analytics', out)
    return out


def main(argv=None):
    r = run()
    print(json.dumps(r['slope_stats_area_weighted'], indent=1), r['roughness_median_rms_slope_deg_1km'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
