"""Pre-registered render-vs-real metrics (docs/v2/RENDER_VS_REAL_PROTOCOL.md §3–§4, implementation choices in Amendment A1).

Pure numpy/scipy; every function is unit-tested on synthetic images with known answers (tests/test_score.py).
Image arrays are 2-D on the binned real-image grid, rows = image lines (top-down), columns = samples.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import ndimage, stats

LOG_FLOOR = 1e-5
EDGE_UNMATCHED_PX = 50.0
BORDER_PX = 8           # protocol §3.1 (A1: applied on the binned crop)
EDGE_BORDER_PX = 3      # protocol §4.2


# ------------------------------------------------------------------------------------------------ window / normalisation
def border_mask(shape, n=BORDER_PX):
    m = np.zeros(shape, bool)
    m[n:shape[0] - n, n:shape[1] - n] = True
    return m


def analysis_window(in_square, real_special):
    """§3.1: render-side terrain hit inside the site square, minus real special pixels, minus BORDER_PX at the borders."""
    return in_square & ~real_special & border_mask(in_square.shape)


def normalise(x, mask):
    """§3.2: divide by the image's own median over `mask` (valid non-saturated window pixels). Returns (x/median, median)."""
    med = float(np.median(x[mask])) if mask.any() else float('nan')
    return x / med, med


def logv(x):
    return np.log10(np.maximum(x, LOG_FLOOR))


# ------------------------------------------------------------------------------------------------ §4.1 observed mask
def otsu(values, nbins=256):
    """Otsu on a 256-bin histogram between the 0.5th and 99.5th percentiles (values outside that range are not binned).
    Returns (threshold, between-class variance at the optimum, total variance of the binned values)."""
    lo, hi = np.percentile(values, [0.5, 99.5])
    if not hi > lo:
        return float(lo), 0.0, 0.0
    hist, edges = np.histogram(values, bins=nbins, range=(lo, hi))
    centres = (edges[:-1] + edges[1:]) / 2
    p = hist.astype(np.float64) / hist.sum()
    w0 = np.cumsum(p)
    m = np.cumsum(p * centres)
    mt = m[-1]
    w1 = 1.0 - w0
    with np.errstate(divide='ignore', invalid='ignore'):
        sb = (mt * w0 - m) ** 2 / (w0 * w1)
    sb[~np.isfinite(sb)] = -1
    sb[-1] = -1
    k = int(np.argmax(sb))
    total = float(np.sum(p * (centres - mt) ** 2))
    return float(edges[k + 1]), float(max(sb[k], 0.0)), total


def observed_shadow(real_norm, window, saturated):
    """§4.1 fixed rule on the valid non-saturated window pixels; saturated window pixels count as lit."""
    ns = window & ~saturated
    v = logv(real_norm)
    thr, sb, tot = otsu(v[ns])
    shadow = np.zeros(real_norm.shape, bool)
    shadow[ns] = v[ns] <= thr
    return shadow, {'otsuThresholdLog10': thr, 'betweenVar': sb, 'totalVar': tot,
                    'weakBimodality': bool(tot > 0 and sb < 0.5 * tot)}


# ------------------------------------------------------------------------------------------------ §4.1 agreement
def agreement(pred_shadow, obs_shadow, window):
    P, O = pred_shadow[window], obs_shadow[window]
    tp = float(np.sum(P & O)); tn = float(np.sum(~P & ~O)); fp = float(np.sum(P & ~O)); fn = float(np.sum(~P & O))
    n = tp + tn + fp + fn

    def div(a, b):
        return a / b if b > 0 else float('nan')
    iou = div(tp, tp + fp + fn)
    iou_lit = div(tn, tn + fp + fn)
    tpr, tnr = div(tp, tp + fn), div(tn, tn + fp)
    bal = np.nanmean([tpr, tnr]) if not (math.isnan(tpr) and math.isnan(tnr)) else float('nan')
    po = div(tp + tn, n)
    pe = div((tp + fp) * (tp + fn) + (tn + fn) * (tn + fp), n * n)
    kappa = div(po - pe, 1 - pe) if n else float('nan')
    edges = edge_pixels(pred_shadow, window, interior=window)
    band = ndimage.binary_dilation(edges, structure=np.ones((3, 3), bool), iterations=2)
    keep = window & ~band
    Pb, Ob = pred_shadow[keep], obs_shadow[keep]
    iou_band = div(float(np.sum(Pb & Ob)), float(np.sum(Pb | Ob)))
    return {'iouShadow': iou, 'iouLit': iou_lit, 'balancedAccuracy': float(bal), 'kappa': kappa, 'iouShadowExclEdgeBand2px': iou_band,
            'nWindow': int(n), 'predShadowFrac': div(tp + fp, n), 'obsShadowFrac': div(tp + fn, n)}


# ------------------------------------------------------------------------------------------------ §4.2 edges
_N4 = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]], bool)


def edge_pixels(shadow, window, interior=None):
    """Shadow pixels inside the window with a 4-neighbour of the other class (the neighbour also inside the window), kept only
    where `interior` is true."""
    lit_in = window & ~shadow
    sh_in = window & shadow
    touches_lit = ndimage.binary_dilation(lit_in, structure=_N4)
    e = sh_in & touches_lit
    return e & (interior if interior is not None else window)


def edge_errors(pred_shadow, obs_shadow, window, gsd_m, pos=None, sun_h=None):
    """Symmetric shadow-edge distances (§4.2). Edge pixels must lie >= EDGE_BORDER_PX inside the window."""
    interior = ndimage.binary_erosion(window, structure=np.ones((3, 3), bool), iterations=EDGE_BORDER_PX, border_value=0)
    ep = edge_pixels(pred_shadow, window, interior)
    eo = edge_pixels(obs_shadow, window, interior)
    out = {'nEdgePred': int(ep.sum()), 'nEdgeObs': int(eo.sum())}
    if not ep.any() or not eo.any():
        return {**out, 'edgeMedianM': float('nan'), 'edgeP90M': float('nan'), 'edgeUnmatchedFrac': float('nan'),
                'edgeMedianPx': float('nan'), 'edgeSignedMedianM': float('nan')}
    d_to_o, idx_o = ndimage.distance_transform_edt(~eo, return_indices=True)
    d_to_p = ndimage.distance_transform_edt(~ep)
    dp = d_to_o[ep]
    do = d_to_p[eo]
    gp, go = gsd_m[ep], gsd_m[eo]
    d_px = np.concatenate([dp, do])
    d_m = np.concatenate([dp * gp, do * go])
    matched = d_px <= EDGE_UNMATCHED_PX
    signed = float('nan')
    if pos is not None and sun_h is not None:
        r, c = np.nonzero(ep)
        ro, co = idx_o[0][r, c], idx_o[1][r, c]
        disp = pos[r, c] - pos[ro, co]                      # predicted - observed (ENU m)
        s = disp[:, :2] @ (np.asarray(sun_h[:2]) / (np.linalg.norm(sun_h[:2]) or 1.0))
        ok = (dp <= EDGE_UNMATCHED_PX) & np.isfinite(s)
        signed = float(np.median(s[ok])) if ok.any() else float('nan')
    if not matched.any():
        return {**out, 'edgeMedianM': float('nan'), 'edgeP90M': float('nan'), 'edgeUnmatchedFrac': 1.0,
                'edgeMedianPx': float('nan'), 'edgeSignedMedianM': signed}
    return {**out, 'edgeMedianM': float(np.median(d_m[matched])), 'edgeP90M': float(np.percentile(d_m[matched], 90)),
            'edgeUnmatchedFrac': float(1 - matched.mean()), 'edgeMedianPx': float(np.median(d_px[matched])),
            'edgeSignedMedianM': signed}


# ------------------------------------------------------------------------------------------------ §4.4 SSIM
def ssim_masked(x, y, valid, L, sigma=1.5, size=11, k1=0.01, k2=0.03, min_valid=0.9):
    """Mean SSIM over windows whose centre is valid and whose size x size box is >= 90 % valid. Local moments are Gaussian-
    weighted over the valid pixels only (weights renormalised). Returns (mean, n_windows)."""
    if not valid.any() or not L > 0:
        return float('nan'), 0
    v = valid.astype(np.float64)
    trunc = (size // 2) / sigma

    def g(a):
        return ndimage.gaussian_filter(a, sigma, truncate=trunc, mode='constant')
    xv, yv = np.where(valid, x, 0.0), np.where(valid, y, 0.0)
    w = g(v)
    with np.errstate(invalid='ignore', divide='ignore'):
        mx, my = g(xv) / w, g(yv) / w
        sxx = g(xv * xv) / w - mx * mx
        syy = g(yv * yv) / w - my * my
        sxy = g(xv * yv) / w - mx * my
    c1, c2 = (k1 * L) ** 2, (k2 * L) ** 2
    s = ((2 * mx * my + c1) * (2 * sxy + c2)) / ((mx * mx + my * my + c1) * (sxx + syy + c2))
    frac = ndimage.uniform_filter(v, size=size, mode='constant')
    use = valid & (frac >= min_valid - 1e-9)
    if not use.any():
        return float('nan'), 0
    return float(np.mean(s[use])), int(use.sum())


# ------------------------------------------------------------------------------------------------ §4.5 histogram distance
def histogram_distances(real_norm, rend_norm, mask):
    a = np.clip(logv(real_norm[mask]), -3, 1)
    b = np.clip(logv(rend_norm[mask]), -3, 1)
    w1 = float(stats.wasserstein_distance(a, b))
    edges = np.linspace(-3, 1, 65)
    pa = np.histogram(a, edges)[0].astype(float); pb = np.histogram(b, edges)[0].astype(float)
    pa /= pa.sum(); pb /= pb.sum()
    m = 0.5 * (pa + pb)

    def kl(p, q):
        nz = p > 0
        return float(np.sum(p[nz] * np.log2(p[nz] / q[nz])))
    return {'wasserstein1': w1, 'jsdBits': 0.5 * kl(pa, m) + 0.5 * kl(pb, m)}


# ------------------------------------------------------------------------------------------------ §3.1 registration
def sobel_mag(x):
    x = np.nan_to_num(x, nan=0.0)
    return np.hypot(ndimage.sobel(x, 0), ndimage.sobel(x, 1))


def masked_ncc(a, b, m, dy, dx):
    """NCC between a and b shifted by (dy, dx) (b sampled at x - offset, bilinear) over mask m ∩ shifted validity."""
    bs = ndimage.shift(b, (dy, dx), order=1, mode='constant', cval=np.nan)
    ok = m & np.isfinite(bs)
    if ok.sum() < 100:
        return -1.0
    u, v = a[ok], bs[ok]
    u = u - u.mean(); v = v - v.mean()
    den = math.sqrt(float(u @ u) * float(v @ v))
    return float(u @ v) / den if den > 0 else -1.0


def register(real_norm, rend_norm, mask, max_px, refine=1.0, step=0.25):
    """One rigid translation (render moves, real never moves): integer search over ±max_px by masked NCC computed with FFTs
    (Padfield 2012), then the exact 0.25 px grid within ±refine px of the best integer offset (A1). Returns dict."""
    A = sobel_mag(real_norm) * mask
    B = sobel_mag(rend_norm) * mask
    M = mask.astype(np.float64)
    R = int(math.ceil(max_px))
    H, W = A.shape
    shp = (H + 2 * R + 1, W + 2 * R + 1)
    fft = np.fft.rfft2

    def corr(x, y):
        return np.fft.irfft2(fft(x, shp) * np.conj(fft(y, shp)), shp)
    # sums over the overlap of mask(x) and mask(x - s) for every shift s (render shifted by s)
    n = corr(M, M)
    sa, sb = corr(A, M), corr(M, B)
    saa, sbb = corr(A * A, M), corr(M, B * B)
    sab = corr(A, B)
    best, bs = -2.0, (0, 0)
    surf = {}
    for dy in range(-R, R + 1):
        for dx in range(-R, R + 1):
            iy, ix = dy % shp[0], dx % shp[1]
            nn = n[iy, ix]
            if nn < 100:
                continue
            cov = sab[iy, ix] - sa[iy, ix] * sb[iy, ix] / nn
            va = saa[iy, ix] - sa[iy, ix] ** 2 / nn
            vb = sbb[iy, ix] - sb[iy, ix] ** 2 / nn
            if va <= 0 or vb <= 0:
                continue
            c = cov / math.sqrt(va * vb)
            surf[(dy, dx)] = c
            if c > best:
                best, bs = c, (dy, dx)
    Bfull = sobel_mag(rend_norm)
    Afull = sobel_mag(real_norm)
    fine_best, fine = -2.0, bs
    grid = np.arange(-refine, refine + 1e-9, step)
    for ddy in grid:
        for ddx in grid:
            c = masked_ncc(Afull, Bfull, mask, bs[0] + ddy, bs[1] + ddx)
            if c > fine_best:
                fine_best, fine = c, (bs[0] + ddy, bs[1] + ddx)
    at_bound = abs(fine[0]) >= R - 1e-9 or abs(fine[1]) >= R - 1e-9
    zero = masked_ncc(Afull, Bfull, mask, 0.0, 0.0)
    return {'dy': float(fine[0]), 'dx': float(fine[1]), 'ncc': fine_best, 'nccZero': zero, 'searchPx': R, 'atBound': bool(at_bound)}


def shift(a, dy, dx, order=1, cval=np.nan):
    if dy == 0 and dx == 0:
        return a
    if a.dtype == bool:
        return ndimage.shift(a.astype(np.float32), (dy, dx), order=1, mode='constant', cval=0.0) >= 0.5
    if a.ndim == 3:
        return np.stack([ndimage.shift(a[..., k], (dy, dx), order=order, mode='constant', cval=cval) for k in range(a.shape[2])], -1)
    return ndimage.shift(a, (dy, dx), order=order, mode='constant', cval=cval)
