"""Terrain products compared by the render twins (a reported factor, never tuned).

Each product supplies the NEAR level over one fixed box per site (the PGDA 78 tile ∩ site centre ± 8 km, identical for every
product so the comparison is paired); every non-flat product shares the same FAR level (PGDA 90 LDEM_80S 80 m, ± 290 km) for
distant shadow casters. Heights: metres above the 1,737,400 m sphere, MOON_ME, south-polar stereographic grid (x = rho sin
lon, y = rho cos lon). Values are read as published; nothing is filled, smoothed or shifted.

Output (git-ignored): $POLARIS_DATA/v2/render_vs_real/terrain/<site>__<product>.npz with the blender/v2/terrain.Level fields
(h rows south -> north, x0/y0 node centres, step) and provenance.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .common import DATA, ROOT, WORK, sha256_file

EXT = ROOT / 'data' / 'external'
PRODUCTS = {
    'pgda78_5m': {'label': 'LOLA PGDA 78 5 m site tile (Barker et al. 2021)', 'native_m': 5.0},
    'lola_ldem875s_5m': {'label': 'LOLA LDEM_875S_5M (PDS LOLA GDR, polar 5 m)', 'native_m': 5.0},
    'pgda90_80m': {'label': 'LOLA PGDA 90 LDEM_80S_80MPP_ADJ 80 m', 'native_m': 80.0},
    'flat': {'label': 'flat-horizon control: smooth 1,737,400 m sphere (no terrain)', 'native_m': None},
}
SITE_TILE = {'site04_roi3': 'Site04', 'site01_roi6': 'Site01', 'site07_roi1': 'Site07', 'site11_roi4': 'Site11'}
NEAR_HALF_M = 8000.0
FAR_HALF_M = 290_000.0


def _paths():
    return {
        'pgda78_5m': lambda site: next((EXT / 'pgda78' / SITE_TILE[site]).glob('*_final_adj_5mpp_surf.tif')),
        'lola_ldem875s_5m': lambda site: DATA / 'v2/products/lola_ldem_polar/data/lola_gdr/polar/float_img/ldem_875s_5m_float.lbl',
        'pgda90_80m': lambda site: EXT / 'pgda90' / 'LDEM_80S_80MPP_ADJ.TIF',
    }


def _read_box(path, x0, x1, y0, y1, km=False):
    """Grid nodes (pixel centres) with x0 <= x <= x1, y0 <= y <= y1 -> (h rows south->north, xc0, yc0, step)."""
    import rasterio
    from rasterio.windows import Window
    with rasterio.open(path) as ds:
        t = ds.transform
        step = t.a
        if abs(t.e + step) > 1e-9 or t.b or t.d:
            raise ValueError(f'{path}: unexpected transform {t}')
        c0 = int(np.ceil((x0 - t.c) / step - 0.5)); c1 = int(np.floor((x1 - t.c) / step - 0.5))
        r0 = int(np.ceil((t.f - y1) / step - 0.5)); r1 = int(np.floor((t.f - y0) / step - 0.5))
        c0, r0 = max(c0, 0), max(r0, 0)
        c1, r1 = min(c1, ds.width - 1), min(r1, ds.height - 1)
        a = ds.read(1, window=Window(c0, r0, c1 - c0 + 1, r1 - r0 + 1)).astype(np.float64)
        nd = ds.nodata
    if nd is not None and np.isfinite(nd):
        a[a == nd] = np.nan
    a[~np.isfinite(a) | (np.abs(a) > 1e30)] = np.nan
    if km:
        a *= 1000.0           # LOLA GDR: km relative to the 1737.4 km sphere; the label OFFSET (radius) is NOT added
    xc0 = t.c + (c0 + 0.5) * step
    yc_top = t.f - (r0 + 0.5) * step
    h = a[::-1]               # rows south -> north
    yc0 = yc_top - (h.shape[0] - 1) * step
    return h, xc0, yc0, step


def near_box(site):
    """Common near box: the PGDA 78 tile's node extent ∩ site centre ± NEAR_HALF_M."""
    import rasterio
    from tools.imagery.sites import SITES
    from .nac_camera import stereo_xy
    cx, cy = (float(v) for v in stereo_xy(SITES[site]['lat'], SITES[site]['lon']))
    with rasterio.open(_paths()['pgda78_5m'](site)) as ds:
        b = ds.bounds
    return max(cx - NEAR_HALF_M, b.left + 2.5), min(cx + NEAR_HALF_M, b.right - 2.5), \
        max(cy - NEAR_HALF_M, b.bottom + 2.5), min(cy + NEAR_HALF_M, b.top - 2.5), (cx, cy)


def build(site, product, out_dir=None):
    out_dir = Path(out_dir or WORK / 'terrain')
    out = out_dir / f'{site}__{product}.npz'
    if out.exists():
        return out
    out_dir.mkdir(parents=True, exist_ok=True)
    x0, x1, y0, y1, centre = near_box(site)
    if product == 'flat':
        step = 20.0
        nx, ny = int((x1 - x0) // step) + 1, int((y1 - y0) // step) + 1
        h = np.zeros((ny, nx))
        meta = {'source': 'none (sphere)', 'sha256': ''}
        xc0, yc0 = x0, y0
    else:
        path = _paths()[product](site)
        h, xc0, yc0, step = _read_box(path, x0, x1, y0, y1, km=product.startswith('lola_'))
        meta = {'source': str(path.relative_to(ROOT) if str(path).startswith(str(ROOT)) else path), 'sha256': sha256_file(path)}
    np.savez(out, h=h, x0=xc0, y0=yc0, step=step, centre=np.array(centre),
             meta=json.dumps({'site': site, 'product': product, 'label': PRODUCTS[product]['label'], 'nanNodes': int(np.isnan(h).sum()),
                              'box': [x0, x1, y0, y1], **meta}))
    return out


def build_far(site, out_dir=None):
    out_dir = Path(out_dir or WORK / 'terrain')
    out = out_dir / f'{site}__far_pgda90_80m.npz'
    if out.exists():
        return out
    out_dir.mkdir(parents=True, exist_ok=True)
    from tools.imagery.sites import SITES
    from .nac_camera import stereo_xy
    cx, cy = (float(v) for v in stereo_xy(SITES[site]['lat'], SITES[site]['lon']))
    path = _paths()['pgda90_80m'](site)
    h, xc0, yc0, step = _read_box(path, cx - FAR_HALF_M, cx + FAR_HALF_M, cy - FAR_HALF_M, cy + FAR_HALF_M)
    np.savez(out, h=h, x0=xc0, y0=yc0, step=step, centre=np.array((cx, cy)),
             meta=json.dumps({'site': site, 'product': 'far_pgda90_80m', 'label': PRODUCTS['pgda90_80m']['label'] + ' (far field)',
                              'source': str(path), 'sha256': sha256_file(path), 'nanNodes': int(np.isnan(h).sum())}))
    return out


def load(npz):
    z = np.load(npz)
    return {'h': z['h'], 'x0': float(z['x0']), 'y0': float(z['y0']), 'step': float(z['step']), 'centre': z['centre'],
            'meta': json.loads(str(z['meta']))}


def sample(level, x, y):
    """Bilinear height at grid (x, y) arrays; NaN outside."""
    h = level['h']
    fx = (np.asarray(x) - level['x0']) / level['step']
    fy = (np.asarray(y) - level['y0']) / level['step']
    ny, nx = h.shape
    ok = (fx >= 0) & (fx <= nx - 1) & (fy >= 0) & (fy <= ny - 1)
    i = np.clip(np.floor(fx).astype(int), 0, nx - 2); j = np.clip(np.floor(fy).astype(int), 0, ny - 2)
    tx, ty = fx - i, fy - j
    v = (h[j, i] * (1 - tx) + h[j, i + 1] * tx) * (1 - ty) + (h[j + 1, i] * (1 - tx) + h[j + 1, i + 1] * tx) * ty
    return np.where(ok, v, np.nan)
