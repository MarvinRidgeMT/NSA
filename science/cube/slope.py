"""Phase 2 — terrain slope from the PGDA 78 5 m DEM (nominal + 20 clones), SOURCE-BASED · UNVALIDATED.

Slope at baseline b is the tilt of the least-squares plane fitted to the k x k pixel window whose outer
pixel centres span b metres: k = b/5 + 1 (5 m -> 2x2, 25 m -> 6x6, 100 m -> 21x21). For a centred
window the LSQ plane gradient is separable: dz/dx = sum(x z) / sum(x^2) (same for y), done as two
1-d correlations, so the whole tile is one pass. Even k places the value at a pixel corner (half-pixel
shift, documented). The slope is the angle from the local horizontal of the grid plane; over the 9 km
tile the polar-stereographic scale error is < 1e-5, ignored.

Per position cell (the 81-cell grid, 25 m cells centred on the offsets) we report the median and max of
the slope field inside the cell, for each baseline and each map. Landing uses the 100 m baseline at the
cell centre; EVA uses the share of a 2 km x 2 km region with 25 m slope < limit.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import correlate1d

from .. import frames, sites

BASELINES_M = (5, 25, 100)
PIX = 5.0


def plane_slope_deg(Z, step, baseline_m):
    k = int(round(baseline_m / step)) + 1
    off = (np.arange(k) - (k - 1) / 2.0) * step           # pixel-centre offsets, symmetric
    w = off / np.sum(off ** 2)                              # LSQ gradient weights along one axis
    box = np.full(k, 1.0 / k)
    Zf = np.asarray(Z, float)
    # columns -> +x (east of grid); rows run north->south, so +y is -row
    gx = correlate1d(correlate1d(Zf, w, axis=1, mode='nearest'), box, axis=0, mode='nearest')
    gy = -correlate1d(correlate1d(Zf, w, axis=0, mode='nearest'), box, axis=1, mode='nearest')
    s = np.degrees(np.arctan(np.hypot(gx, gy)))
    # mark windows touching nodata or the tile edge
    bad = ~np.isfinite(Zf)
    if bad.any():
        badw = correlate1d(correlate1d(bad.astype(float), np.ones(k), axis=0, mode='constant', cval=1),
                           np.ones(k), axis=1, mode='constant', cval=1) > 0
        s[badw] = np.nan
    h = k // 2
    if h:
        s[:h, :] = np.nan; s[-h:, :] = np.nan; s[:, :h] = np.nan; s[:, -h:] = np.nan
    return s


def pixel_of(dem, x, y):
    c = int(np.floor((x - dem.x_left) / dem.step)); r = int(np.floor((dem.y_top - y) / dem.step))
    return r, c


def cell_stats(S, dem, x0, y0, offsets, cell_m=25.0):
    """median / max of slope field S over each 25 m cell centred on (x0+dx, y0+dy)."""
    med, mx = [], []
    half = cell_m / 2.0
    for dx, dy in offsets:
        r0, c0 = pixel_of(dem, x0 + dx - half, y0 + dy + half)
        r1, c1 = pixel_of(dem, x0 + dx + half, y0 + dy - half)
        blk = S[r0:r1, c0:c1]
        med.append(float(np.nanmedian(blk))); mx.append(float(np.nanmax(blk)))
    return np.array(med), np.array(mx)


def at_point(S, dem, x, y):
    """Bilinear-free nearest-corner value: the plane-fit value of the pixel containing (x, y)."""
    r, c = pixel_of(dem, x, y)
    return float(S[r, c])


def region_share_below(S, dem, x0, y0, half_m, limit_deg):
    r0, c0 = pixel_of(dem, x0 - half_m, y0 + half_m)
    r1, c1 = pixel_of(dem, x0 + half_m, y0 - half_m)
    blk = S[r0:r1, c0:c1]
    ok = np.isfinite(blk)
    return float(100.0 * np.sum(blk[ok] < limit_deg) / max(ok.sum(), 1)), float(np.nanmax(blk))


def site_xy(site, dx=0.0, dy=0.0):
    s = sites.SITES[site]
    x0, y0 = frames.stereo_forward(s['lat'], s['lon'])
    return x0 + dx, y0 + dy
