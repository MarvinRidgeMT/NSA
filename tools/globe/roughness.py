"""VISUAL sub-resolution relief and the roughness check (prompt §2.3; S3 plan §9, R2 plan §1-2). Display only: never science.

Everything at or above a product's native posting comes from the data as-is (the science pyramid, bilinear). Below it,
fractal micro-relief is added whose amplitude is set by what LOLA measures at that scale:

  * Amplitude target: LOLA 5-spot roughness LDRM_32_50 (LRO-L-LOLA-4-GDR-V1.0, Smith/Neumann; label: RMS residual
    height of the five spots of one laser shot after removing a plane; point-to-point baseline 25 m at the nominal 50 km
    altitude, corrected to that distance; instrument noise ~0.15 m removed), 0.5-quantile per 1/32 deg bin, smoothed
    over a 3 km box weighted by the shot count LDRC_32 (bins with no shot, filled by LOLA's nearneighbor step, get
    weight 0.25). A plane fit is blind to regional tilt, which is what made S3's self-fit extrapolation 1.2-1.9x too
    strong (see docs/v2/PHASE_1_R2_PLAN.md §1).
  * Spectral shape: Hurst exponent H from PGDA 70 HE_8 (Rosenburg et al. 2011, 57 m - 2.7 km), clipped to [0.5, 1];
    the global median of HE_8 where the map has no value.
  * Noise: octaves of smooth 3-D value noise on a lattice in Moon-fixed Cartesian metres (one field for the whole Moon:
    eq and polar tiles agree wherever they overlap), each octave's lattice values a hash of (lattice index, octave
    wavelength, fixed SEED). A tile is a pure function of its id: deterministic, byte-identical rebuilds, seamless.
    Octave wavelengths are the fixed ladder lam_k = LAM_MIN 2^k (10 m, 20 m, ...); octave k has weight
    w_k(x) = clip(log2(2 res(x) / lam_k), 0, 1) (only wavelengths below twice the local native posting res(x), smoothed
    so the amplitude has no seam at product edges) and amplitude A(x) (lam_k / LAM_REF)^H(x). Octaves shorter than two
    VISUAL pixels are not drawn (they cannot be displayed).
  * A(x) = sqrt(max(T(x)^2 - sigma_base(x)^2, 0)) / g(H, 2 res): T = target LDRM_50, sigma_base = 5-spot roughness the
    bilinear real surface already has, g = median 5-spot roughness of the unit-amplitude field (Monte Carlo of the exact
    estimator, fixed seed, tabulated in H and 2 res).
Small craters and boulders are NOT added: see docs/v2/PHASE_1_R2_PLAN.md §3 and docs/v2/PYRAMID_QA.json
"visual_population" for the reasons.

    python -m tools.globe.roughness check            # hard roughness check (writes PYRAMID_QA.json "roughness")
    python -m tools.globe.roughness build --zone sp --level 6 --bbox l,b,r,t [--workers 3]
    python -m tools.globe.roughness prebuild         # the budgeted VISUAL set (R2 plan §2)

Output tiles: $POLARIS_DATA/v2/pyramid_visual/<zone>/<level>/<ix>_<iy>.tif, one band height_visual (float32), label VISUAL.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

from science.terrain import stack as S
from tools.globe import pyramid as PY
from tools.globe import pyramid_products as PP

LABEL = 'VISUAL'
SEED = 0x504F4C415249535F          # "POLARIS_"
PARAMS_SOURCE = 'lola-ldrm32-50 (amplitude) + pgda70-he8 (Hurst)'
LAM_MIN = 10.0                      # finest octave (m): two posts of the finest VISUAL level built (5 m)
LAM_REF = 25.0                      # octave amplitudes are referred to the 25 m LOLA spot baseline
SPOT_M = 25.0                       # LOLA centre-to-arm spot separation at 50 km (LDRM label: 25 m baseline)
SMOOTH_M = 3000.0                   # LDRM_50 smoothing box half-width
H_MIN, H_MAX = 0.5, 1.0
BASELINES_M = (15.0, 20.0, 40.0, 80.0, 160.0, 320.0, 640.0, 1280.0, 2560.0)   # ~17 m .. 2.7 km (multiples of 5 m)
SLOPE_BAND = (0.8, 1.25)            # displayed / real 5 m RMS slope at every baseline (hard, R2 plan §1b)
RESIDUAL_GUARD = 2.0                # added / real sub-80 m residual RMS slope (guard only; PGDA 78 is a lower bound)
HURST_GUARD = 0.1                   # |H displayed - H PGDA 70| (guard)
R_M = S.R


def visual_root():
    return PP.polaris_data() / 'v2' / 'pyramid_visual'


# ------------------------------------------------------------------------------------------ noise
_M1 = np.uint64(0x9E3779B97F4A7C15); _M2 = np.uint64(0xC2B2AE3D27D4EB4F); _M5 = np.uint64(0x165667B19E3779F9)
_M3 = np.uint64(0xBF58476D1CE4E5B9); _M4 = np.uint64(0x94D049BB133111EB)


def _hash01(i, j, seed, k=None):
    with np.errstate(over='ignore'):
        x = (i.astype(np.int64).astype(np.uint64) * _M1) ^ (j.astype(np.int64).astype(np.uint64) * _M2) ^ np.uint64(seed)
        if k is not None:
            x ^= k.astype(np.int64).astype(np.uint64) * _M5
        x ^= x >> np.uint64(30); x *= _M3
        x ^= x >> np.uint64(27); x *= _M4
        x ^= x >> np.uint64(31)
    return (x >> np.uint64(11)).astype(np.float64) / float(1 << 53)


def octave_seed(lam):
    """Seed of the octave with wavelength lam (m): a function of lam only, so every tile and level shares it."""
    e = int(round(math.log2(lam / 1.25) * 8))
    return (SEED ^ (e * 0x100000001B3)) & 0xFFFFFFFFFFFFFFFF


def _fade(t):
    return t * t * t * (t * (t * 6 - 15) + 10)


def value_noise(u, v, seed):
    """2-D smooth value noise (kept for tests and comparison); lattice values uniform in [-sqrt3, sqrt3]."""
    i = np.floor(u); j = np.floor(v)
    fu = _fade(u - i); fv = _fade(v - j)
    i = i.astype(np.int64); j = j.astype(np.int64)
    s3 = math.sqrt(3.0)

    def g(a, b):
        return (2 * _hash01(a, b, seed) - 1) * s3
    return ((1 - fu) * (1 - fv) * g(i, j) + fu * (1 - fv) * g(i + 1, j)
            + (1 - fu) * fv * g(i, j + 1) + fu * fv * g(i + 1, j + 1))


def value_noise3(P, lam, seed):
    """3-D smooth value noise at Moon-fixed points P (..., 3) in metres, lattice spacing lam; unit-variance lattice."""
    U = P / lam
    I = np.floor(U)
    F = _fade(U - I)
    I = I.astype(np.int64)
    s3 = math.sqrt(3.0)
    out = np.zeros(P.shape[:-1])
    for dx in (0, 1):
        wx = F[..., 0] if dx else 1 - F[..., 0]
        for dy in (0, 1):
            wy = F[..., 1] if dy else 1 - F[..., 1]
            for dz in (0, 1):
                wz = F[..., 2] if dz else 1 - F[..., 2]
                g = (2 * _hash01(I[..., 0] + dx, I[..., 1] + dy, seed, I[..., 2] + dz) - 1) * s3
                out += wx * wy * wz * g
    return out


def sphere_points(lat, lon):
    la, lo = np.radians(lat), np.radians(lon)
    return R_M * np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], -1)


def ladder(lam_top):
    """Fixed octave ladder LAM_MIN * 2^k up to lam_top."""
    out = []
    lam = LAM_MIN
    while lam <= lam_top * 1.0001:
        out.append(lam); lam *= 2.0
    return out


def octave_weight(lam_max, lam):
    return np.clip(np.log2(np.asarray(lam_max, float) / lam), 0.0, 1.0)


# ------------------------------------------------------------------------------------------ LOLA 5-spot roughness
def five_spot_sigma(h0, hE, hW, hN, hS):
    """LOLA single-shot roughness: RMS residual of the five spot heights (centre + cross arms at +-s) about their
    least-squares plane, divided by (5 - 3) degrees of freedom (LDRM label). For a symmetric cross the plane fit is
    closed-form: intercept = mean, slopes = arm differences, residuals r0 = h0 - m and (hE + hW)/2 - m, (hN + hS)/2 - m
    (each twice)."""
    m = (h0 + hE + hW + hN + hS) / 5.0
    r0 = h0 - m; rx = 0.5 * (hE + hW) - m; ry = 0.5 * (hN + hS) - m
    return np.sqrt((r0 * r0 + 2 * rx * rx + 2 * ry * ry) / 2.0)


def five_spot_shots(Z, q, n=20000, sep=SPOT_M, seed=1):
    """Emulated LOLA shots on a metric grid Z (pixel q m): random centres and orientations, spot heights bilinear.
    Returns the per-shot roughness (finite shots only)."""
    from scipy import ndimage
    rng = np.random.default_rng(seed)
    ny, nx = Z.shape
    m = sep / q + 2
    cy = rng.uniform(m, ny - 1 - m, n); cx = rng.uniform(m, nx - 1 - m, n); th = rng.uniform(0, np.pi / 2, n)
    c, s = np.cos(th) * sep / q, np.sin(th) * sep / q
    at = lambda dy, dx: ndimage.map_coordinates(Z, [cy + dy, cx + dx], order=1, mode='nearest', prefilter=False)
    v = five_spot_sigma(at(0, 0), at(s, c), at(-s, -c), at(c, -s), at(-c, s))
    return v[np.isfinite(v)]


_G = None


def g_table():
    """Median 5-spot roughness g(H, lam_max) of the unit-amplitude VISUAL field (A = 1), by Monte Carlo of the exact
    estimator on the 3-D noise itself (fixed seed: deterministic). Grid: H 0.5..1.0 step 0.05, lam_max = 10 m * 2^(k/4)."""
    global _G
    if _G is not None:
        return _G
    rng = np.random.default_rng(20261116)
    n = 20000
    lat = np.degrees(np.arcsin(rng.uniform(-0.9, 0.9, n))); lon = rng.uniform(-180, 180, n)
    th = rng.uniform(0, np.pi / 2, n)
    la, lo = np.radians(lat), np.radians(lon)
    e = np.stack([-np.sin(lo), np.cos(lo), np.zeros_like(lo)], -1)
    nn = np.stack([-np.sin(la) * np.cos(lo), -np.sin(la) * np.sin(lo), np.cos(la)], -1)
    a1 = np.cos(th)[:, None] * e + np.sin(th)[:, None] * nn
    a2 = -np.sin(th)[:, None] * e + np.cos(th)[:, None] * nn
    P0 = sphere_points(lat, lon)
    pts = [P0, P0 + SPOT_M * a1, P0 - SPOT_M * a1, P0 + SPOT_M * a2, P0 - SPOT_M * a2]
    lams = ladder(2560.0)
    oct_vals = np.array([[value_noise3(p, lam, octave_seed(lam)) for p in pts] for lam in lams])   # (k, 5, n)
    Hs = np.round(np.arange(H_MIN, H_MAX + 1e-9, 0.05), 3)
    LM = LAM_MIN * 2.0 ** (np.arange(0, 29) / 4.0)
    G = np.zeros((Hs.size, LM.size))
    lam_a = np.array(lams)
    for i, H in enumerate(Hs):
        for j, lm in enumerate(LM):
            a = (lam_a / LAM_REF) ** H * octave_weight(lm, lam_a)
            if not (a > 0).any():
                continue
            f = np.tensordot(a, oct_vals, axes=(0, 0))                    # (5, n)
            G[i, j] = float(np.median(five_spot_sigma(*f)))
    _G = (Hs, np.log2(LM), G)
    return _G


def g_unit(H, lam_max):
    from scipy.interpolate import RegularGridInterpolator
    Hs, LL, G = g_table()
    f = RegularGridInterpolator((Hs, LL), G, bounds_error=False, fill_value=None)
    H = np.clip(np.asarray(H, float), Hs[0], Hs[-1])
    L = np.clip(np.log2(np.maximum(np.asarray(lam_max, float), 1e-9)), LL[0], LL[-1])
    H, L = np.broadcast_arrays(H, L)
    return f(np.stack([H.ravel(), L.ravel()], -1)).reshape(H.shape)


# ------------------------------------------------------------------------------------------ LOLA parameter maps
LDRM_SHAPE = (5760, 11520)          # 32 ppd, row 0 centred on 89.984 N, column 0 on 0.0156 E (pixel registered)


class LolaRoughness:
    """LOLA LDRM_32 quantile maps (0.25 / 0.50 / 0.75, metres, DN * 0.001, missing -32768) and LDRC_32 shot counts,
    plus PGDA 70 HE_8 (Hurst). Geometry from the PDS3 labels (checked in tests)."""

    def __init__(self, gdr_dir=None):
        d = Path(gdr_dir) if gdr_dir else (PP.polaris_data() / 'v2' / 'products' / 'lola_roughness_gdr' / 'data' /
                                           'lola_gdr' / 'cylindrical' / 'img')
        if not (d / 'ldrm_32_50.img').exists():
            raise FileNotFoundError(f'LOLA LDRM_32 not on disk at {d}')
        self.dir = d
        self.q = {k: np.memmap(d / f'ldrm_32_{k}.img', dtype='<i2', mode='r', shape=LDRM_SHAPE) for k in ('25', '50', '75')}
        self.count = np.memmap(d / 'ldrc_32.img', dtype='<i2', mode='r', shape=LDRM_SHAPE)
        self._smooth = None
        self._p70 = None
        self._h_fallback = None

    @staticmethod
    def rc(lat, lon):
        lat = np.asarray(lat, float); lon = np.asarray(lon, float)
        r = np.clip(np.floor((90.0 - lat) * 32).astype(np.int64), 0, LDRM_SHAPE[0] - 1)
        c = np.floor(np.mod(lon, 360.0) * 32).astype(np.int64) % LDRM_SHAPE[1]
        return r, c

    def quantile(self, lat, lon, k):
        """Raw bin value (m) of quantile k ('25', '50', '75'); NaN where missing."""
        r, c = self.rc(lat, lon)
        v = self.q[k][r, c].astype(np.float64)
        v[v == -32768] = np.nan
        return v * 0.001

    def shots(self, lat, lon):
        r, c = self.rc(lat, lon)
        return self.count[r, c].astype(np.int64)

    def smooth50(self):
        """LDRM_50 smoothed over a +-SMOOTH_M box (geometric mean weighted by shot count; count-0 bins weight 0.25),
        cached as float32 under pyramid_visual/_params/."""
        if self._smooth is not None:
            return self._smooth
        cache = visual_root() / '_params' / f'ldrm50_box{int(SMOOTH_M)}m.npy'
        if cache.exists():
            self._smooth = np.load(cache, mmap_mode='r')
            return self._smooth
        L = np.asarray(self.q['50']).astype(np.float64)
        ok = (L != -32768) & (L > 0)
        W = np.where(ok, np.maximum(np.asarray(self.count).astype(np.float64), 0.25), 0.0)
        V = np.where(ok, np.log(np.where(ok, L, 1) * 0.001), 0.0) * W
        dlat_m = R_M * math.radians(1 / 32)
        kr = max(1, int(round(SMOOTH_M / dlat_m)))
        from scipy import ndimage
        Vr = ndimage.uniform_filter1d(V, 2 * kr + 1, axis=0, mode='nearest') * (2 * kr + 1)
        Wr = ndimage.uniform_filter1d(W, 2 * kr + 1, axis=0, mode='nearest') * (2 * kr + 1)
        out = np.full(LDRM_SHAPE, np.nan, np.float32)
        lat_c = 90.0 - (np.arange(LDRM_SHAPE[0]) + 0.5) / 32
        nx = LDRM_SHAPE[1]
        for r in range(LDRM_SHAPE[0]):
            dlon_m = R_M * math.radians(1 / 32) * max(math.cos(math.radians(lat_c[r])), 1e-6)
            kc = min(nx // 2 - 1, max(1, int(round(SMOOTH_M / dlon_m))))
            cv = np.concatenate([[0.0], np.cumsum(np.concatenate([Vr[r, -kc:], Vr[r], Vr[r, :kc]]))])
            cw = np.concatenate([[0.0], np.cumsum(np.concatenate([Wr[r, -kc:], Wr[r], Wr[r, :kc]]))])
            sv = cv[2 * kc + 1:] - cv[:nx]; sw = cw[2 * kc + 1:] - cw[:nx]
            out[r] = np.where(sw > 0, np.exp(sv / np.where(sw > 0, sw, 1)), np.nan)
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.save(cache, out)
        self._smooth = np.load(cache, mmap_mode='r')
        return self._smooth

    def target(self, lat, lon):
        """Smoothed LDRM_50 (m), bilinear between bin centres (longitude wraps)."""
        from scipy import ndimage
        M = self.smooth50()
        lat = np.asarray(lat, float); lon = np.asarray(lon, float)
        r = (90.0 - lat) * 32 - 0.5
        c = np.mod(lon, 360.0) * 32 - 0.5
        r0 = int(max(0, math.floor(np.nanmin(r)) - 1)); r1 = int(min(LDRM_SHAPE[0], math.ceil(np.nanmax(r)) + 3))
        cmin, cmax = math.floor(np.nanmin(c)) - 1, math.ceil(np.nanmax(c)) + 3
        if cmax - cmin >= LDRM_SHAPE[1] - 4:
            cols = np.arange(LDRM_SHAPE[1] + 2) - 1
            cmin = -1
        else:
            # handle the 0/360 wrap: shift c into a contiguous window
            if cmax - cmin > LDRM_SHAPE[1] / 2:
                c = np.where(c < LDRM_SHAPE[1] / 2, c + LDRM_SHAPE[1], c)
                cmin, cmax = math.floor(np.nanmin(c)) - 1, math.ceil(np.nanmax(c)) + 3
            cols = np.arange(cmin, cmax)
        sub = np.asarray(M[r0:r1][:, cols % LDRM_SHAPE[1]], dtype=np.float64)
        bad = ~np.isfinite(sub)
        if bad.all():
            return np.full(lat.shape, np.nan)
        if bad.any():
            sub = _fill_nan_nearest(sub)
        return ndimage.map_coordinates(sub, [r - r0, c - cmin], order=1, mode='nearest', prefilter=False)

    def hurst(self, lat, lon):
        if self._p70 is None:
            self._p70 = PGDA70()
            he = np.asarray(self._p70.he.read_block(0, 0, self._p70.he.h, self._p70.he.w), float) \
                if hasattr(self._p70.he, 'read_block') else None
            self._h_fallback = float(np.nanmedian(he)) if he is not None and np.isfinite(he).any() else 0.9
        lat = np.asarray(lat, float); lon = np.asarray(lon, float)
        h = self._p70.hurst(lat.ravel(), lon.ravel()).reshape(lat.shape)
        h = np.where(np.isfinite(h), h, self._h_fallback)
        return np.clip(h, H_MIN, H_MAX)


_LOLA = None


def lola():
    global _LOLA
    if _LOLA is None:
        _LOLA = LolaRoughness()
    return _LOLA


def _fill_nan_nearest(a):
    from scipy import ndimage
    m = np.isnan(a)
    if not m.any() or m.all():
        return a
    idx = ndimage.distance_transform_edt(m, return_distances=False, return_indices=True)
    return a[tuple(idx)]


# ------------------------------------------------------------------------------------------ statistics
def rms_dev(Z, lag):
    """RMS height difference at a lag of `lag` pixels, pooled over both grid axes (NaN pairs skipped)."""
    a = Z[:, lag:] - Z[:, :-lag]; b = Z[lag:, :] - Z[:-lag, :]
    d = np.concatenate([a[np.isfinite(a)], b[np.isfinite(b)]])
    return float(np.sqrt(np.mean(d * d))) if d.size else float('nan')


def rms_slope_profile(Z, px, baselines=BASELINES_M):
    """{baseline_m: RMS slope (deg)} with s(D) = atan(nu(D) / D), D a multiple of px (others skipped)."""
    out = {}
    for b in baselines:
        lag = b / px
        if abs(lag - round(lag)) > 1e-6 or round(lag) < 1 or round(lag) >= min(Z.shape) // 2:
            continue
        nu = rms_dev(Z, int(round(lag)))
        out[float(b)] = math.degrees(math.atan(nu / b))
    return out


def median_abs_slope_deg(Z, px, baseline):
    """Median |dz/D| (deg) along both grid axes at baseline D (linear interpolation between pixel multiples)."""
    lo, hi = math.floor(baseline / px), math.ceil(baseline / px)
    vals = []
    for lag in sorted({max(1, lo), max(1, hi)}):
        a = Z[:, lag:] - Z[:, :-lag]; b = Z[lag:, :] - Z[:-lag, :]
        d = np.abs(np.concatenate([a[np.isfinite(a)], b[np.isfinite(b)]])) / (lag * px)
        vals.append((lag * px, math.degrees(math.atan(float(np.median(d))))))
    if len(vals) == 1:
        return vals[0][1]
    (b0, v0), (b1, v1) = vals
    return v0 + (v1 - v0) * (baseline - b0) / (b1 - b0)


def deviogram_hurst(Z, px, b_min=57.0, b_max=2700.0):
    lags = [l for l in (12, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512) if b_min <= l * px <= b_max]
    nus = [rms_dev(Z, l) for l in lags]
    return float(np.polyfit(np.log(np.array(lags) * px), np.log(nus), 1)[0])


# ------------------------------------------------------------------------------------------ synthesis
def _sigma_base(base, qy, qx, sigma_px):
    """Local 5-spot roughness of the bilinear real surface (axis-aligned and 45-degree crosses averaged in quadrature),
    smoothed; qy, qx = metric pixel sizes along rows and columns."""
    from scipy import ndimage
    ny, nx = base.shape
    J, I = np.mgrid[0:ny, 0:nx].astype(np.float64)
    b = np.where(np.isfinite(base), base, np.nanmean(base) if np.isfinite(base).any() else 0.0)
    at = lambda dy, dx: ndimage.map_coordinates(b, [J + dy, I + dx], order=1, mode='nearest', prefilter=False)
    sy, sx = SPOT_M / qy, SPOT_M / qx
    h0 = b
    s_a = five_spot_sigma(h0, at(0, sx), at(0, -sx), at(-sy, 0), at(sy, 0))
    c = math.sqrt(0.5)
    s_b = five_spot_sigma(h0, at(c * sy, c * sx), at(-c * sy, -c * sx), at(-c * sy, c * sx), at(c * sy, -c * sx))
    v = 0.5 * (s_a ** 2 + s_b ** 2)
    return np.sqrt(ndimage.gaussian_filter(v, sigma_px, mode='nearest'))


def synthesize(stack, lat, lon, q_m, qy_m=None, qx_m=None, zone=None, real_levels=None, assume_native_m=None, pad=16,
               params=None):
    """VISUAL heights at a padded grid of pixel centres (lat, lon) (2-D arrays, `pad` pixels of margin on each side).
    q_m: nominal VISUAL pixel (m; octaves below 2 q_m are not drawn); qy_m/qx_m: metric pixel along rows/columns
    (default q_m). zone: zone whose merge supplies the real surface (default: the zone rule). real_levels: pyramid levels
    the real base may use (None = all). assume_native_m: treat the base as having this native resolution everywhere
    (the roughness check uses the 80 m level over a PGDA 78 site, whose pixels honestly carry native_res_m = 5 m).
    Returns vis, base, noise, diag (all on the padded grid)."""
    from scipy import ndimage
    P = params or lola()
    qy_m = q_m if qy_m is None else qy_m
    qx_m = q_m if qx_m is None else qx_m
    qy = stack._query(lat, lon, levels=real_levels, zone=zone)
    base = qy['height'].astype(np.float64)
    res = qy['native_res_m'].astype(np.float64)
    res = np.where(np.isfinite(res), res, q_m)
    if assume_native_m is not None:
        res = np.full(res.shape, float(assume_native_m))
    sig = max(pad / 2.0, 1.0)
    lam_max = 2.0 * np.exp2(ndimage.gaussian_filter(np.log2(res), sig, mode='nearest'))
    sb = _sigma_base(base, qy_m, qx_m, sig)
    T = P.target(lat, lon)
    T = np.where(np.isfinite(T), T, np.nan)
    H = P.hurst(lat, lon)
    tn = np.sqrt(np.maximum(np.nan_to_num(T) ** 2 - sb ** 2, 0.0))
    g = g_unit(H, lam_max)
    A = np.where(g > 1e-9, tn / np.where(g > 1e-9, g, 1.0), 0.0)
    Pm = sphere_points(lat, lon)
    lams = [lam for lam in ladder(float(np.nanmax(lam_max))) if lam >= 2.0 * q_m * 0.999]
    noise = np.zeros(lat.shape)
    used = []
    for lam in lams:
        w = octave_weight(lam_max, lam)
        if not (w > 0).any():
            continue
        used.append(lam)
        noise += A * (lam / LAM_REF) ** H * w * value_noise3(Pm, lam, octave_seed(lam))
    noise = np.where(np.isfinite(base), noise, np.nan)
    vis = base + noise
    sl = (slice(pad, lat.shape[0] - pad), slice(pad, lat.shape[1] - pad))
    diag = {'params_source': PARAMS_SOURCE, 'visual_pixel_m': float(q_m), 'octaves_m': used, 'seed': hex(SEED),
            'lam_min_m': LAM_MIN, 'lam_ref_m': LAM_REF,
            'target_ldrm50_median_m': _r(np.nanmedian(T[sl])) if np.isfinite(T[sl]).any() else None,
            'sigma_base_median_m': _r(np.nanmedian(sb[sl])),
            'H_range': [_r(np.nanmin(H[sl])), _r(np.nanmax(H[sl]))],
            'noise_rms_m': _r(np.sqrt(np.nanmean(noise[sl] ** 2))) if np.isfinite(noise[sl]).any() else None}
    return vis, base, noise, diag


def _r(x, n=4):
    return None if x is None or not np.isfinite(x) else round(float(x), n)


def tile_grid(zone, level, ix, iy, pad=16):
    """Padded pixel-centre lat/lon of a tile, plus (q_m, qy_m, qx_m) metric pixel sizes."""
    Z = S.ZONES[zone]
    U, V = Z.pixel_centres(level, ix, iy, pad=pad)
    lat, lon = Z.inverse(U, V)
    p = Z.pixel(level)
    if Z.kind == 'eq':
        qy = R_M * math.radians(p)
        qx = qy * np.cos(np.radians(lat))
        return lat, lon, qy, qy, qx
    k = Z.scale_k(lat)
    return lat, lon, p, p / k, p / k


def visual_tile(stack, zone, level, ix, iy, pad=16, params=None):
    lat, lon, q, qy, qx = tile_grid(zone, level, ix, iy, pad=pad)
    vis, base, noise, diag = synthesize(stack, lat, lon, q, qy_m=qy, qx_m=qx, zone=zone, pad=pad, params=params)
    sl = (slice(pad, -pad), slice(pad, -pad))
    return vis[sl], base[sl], noise[sl], diag


def visual_tile_path(zone, level, ix, iy, root=None):
    return (Path(root) if root else visual_root()) / zone / str(level) / f'{ix}_{iy}.tif'


def write_visual_tile(stack, zone, level, ix, iy, root=None, params=None):
    import rasterio
    from rasterio.crs import CRS
    from rasterio.transform import from_origin
    Z = S.ZONES[zone]
    l, b, r, t = Z.tile_bounds(level, ix, iy)
    q = Z.pixel(level)
    vis, base, noise, diag = visual_tile(stack, zone, level, ix, iy, params=params)
    if not np.isfinite(vis).any():
        return None
    path = visual_tile_path(zone, level, ix, iy, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f'.{os.getpid()}.tmp.tif')
    prof = dict(driver='COG', width=Z.tile_px, height=Z.tile_px, count=1, dtype='float32',
                crs=CRS.from_proj4(Z.proj4), transform=from_origin(l, t, q, q), nodata=float('nan'),
                compress='DEFLATE', predictor=3, blocksize=256, overviews='NONE')
    with rasterio.open(tmp, 'w', **prof) as ds:
        ds.write(vis.astype(np.float32), 1)
        ds.set_band_description(1, 'height_visual')
        ds.update_tags(label=LABEL, note='VISUAL sub-resolution relief: display only, never science',
                       zone=zone, level=str(level), ix=str(ix), iy=str(iy),
                       **{k: json.dumps(v) if not isinstance(v, str) else v for k, v in diag.items()})
    os.replace(tmp, path)
    return path


def ensure_visual_tile(zone, level, ix, iy, stack=None, root=None):
    """Path of a VISUAL tile, building it first if absent (deterministic: a rebuild is byte-identical). None where the
    science pyramid has no real terrain under the tile."""
    p = visual_tile_path(zone, level, ix, iy, root)
    if p.exists():
        return p
    return write_visual_tile(stack or S.TerrainStack.open(), zone, level, ix, iy, root=root)


# ------------------------------------------------------------------------------------------ PGDA 70 (LOLA roughness maps)
PGDA70_BASELINES = (57.0, 225.0, 560.0)


class PGDA70:
    """LOLA PGDA 70 maps (Rosenburg et al. 2011): Hurst exponent HE_8 (8 ppd; H = DN * 2.5e-5 + 0.5, fitted over 57 m
    to the deviogram breakover, <= 2.7 km) and median absolute along-track slope MAS_{57,225,560}M_16 (16 ppd; degrees =
    DN * 0.0015 + 45). Scales/offsets are read from the PDS labels by GDAL; both grids are lon 0..360 simple cylindrical."""

    def __init__(self, img_dir=None):
        d = Path(img_dir) if img_dir else PP.polaris_data() / 'v2' / 'products' / 'pgda70_roughness' / 'IMG'
        if not (d / 'HE_8.LBL').exists():
            raise FileNotFoundError(f'PGDA 70 not on disk at {d}')
        mk = lambda n, res: PP.ProductReader(PP.ProductSpec(f'pgda70_{n}', 0, str(d / f'{n}.LBL'), res))
        self.he = mk('HE_8', PP.R * math.radians(1 / 8))
        self.mas = {b: mk(f'MAS_{int(b)}M_16', PP.R * math.radians(1 / 16)) for b in PGDA70_BASELINES}

    def _at(self, rd, lat, lon):
        lat = np.atleast_1d(np.asarray(lat, float)); lon = np.atleast_1d(np.asarray(lon, float))
        return rd.sample(lat, lon, rd.native_px_m())[0]

    def hurst(self, lat, lon):
        return self._at(self.he, lat, lon)

    def median_abs_slope_deg(self, lat, lon, baseline):
        return self._at(self.mas[baseline], lat, lon)


# ------------------------------------------------------------------------------------------ roughness check
def _lola_spread(P, lat, lon, step=10):
    """Published spread of LOLA single-shot roughness over a window: medians over the window's LOLA bins of the
    0.25 / 0.50 / 0.75 quantile maps, plus the total shot count."""
    la, lo = lat[::step, ::step].ravel(), lon[::step, ::step].ravel()
    r, c = P.rc(la, lo)
    key = np.unique(r * LDRM_SHAPE[1] + c)
    rr, cc = key // LDRM_SHAPE[1], key % LDRM_SHAPE[1]
    q = {}
    for k in ('25', '50', '75'):
        v = P.q[k][rr, cc].astype(float); v[v == -32768] = np.nan
        q[k] = float(np.nanmedian(v * 0.001)) if np.isfinite(v).any() else float('nan')
    return {'q25_m': _r(q['25']), 'q50_m': _r(q['50']), 'q75_m': _r(q['75']), 'bins': int(key.size),
            'shots': int(P.count[rr, cc].astype(np.int64).clip(0).sum())}


def check_pgda78_site(stack, spec, half_m=4000.0, base_level=4, pad=16):
    """Independent check at one PGDA 78 site: VISUAL built from the 80 m level only vs the real 5 m surface."""
    P = lola()
    rd = PP.ProductReader(spec)
    try:
        cx = rd.left + rd.w * rd.px_x / 2; cy = rd.top - rd.h * rd.px_y / 2
        q = rd.px_x
        n = int(2 * half_m / q)
        x_left = cx - half_m; y_top = cy + half_m
        xs = x_left + (np.arange(-pad, n + pad) + 0.5) * q; ys = y_top - (np.arange(-pad, n + pad) + 0.5) * q
        X, Y = np.meshgrid(xs, ys)
        lat, lon = rd.grid_to_latlon(X, Y)
        sl = (slice(pad, -pad), slice(pad, -pad))
        real, _, _ = rd.sample(lat[sl], lon[sl], q)
        clat, clon = rd.grid_to_latlon(cx, cy)
    finally:
        rd.close()
    vis, base, noise, diag = synthesize(stack, lat, lon, q, zone='sp', real_levels=list(range(0, base_level + 1)),
                                        assume_native_m=S.ZONES['sp'].pixel_m(base_level), pad=pad)
    vis, base, noise = vis[sl], base[sl], noise[sl]
    lat, lon = lat[sl], lon[sl]
    pr, pv, pb_ = rms_slope_profile(real, q), rms_slope_profile(vis, q), rms_slope_profile(base, q)
    rr_, rn_ = rms_slope_profile(real - base, q), rms_slope_profile(noise, q)
    rows = []
    for bl in pr:
        rows.append({'baseline_m': bl, 'real_5m_deg': round(pr[bl], 3), 'visual_deg': round(pv[bl], 3),
                     'bilinear_80m_deg': round(pb_[bl], 3), 'ratio_visual': round(pv[bl] / pr[bl], 3),
                     'ratio_bilinear': round(pb_[bl] / pr[bl], 3),
                     'residual_real_deg': round(rr_[bl], 3), 'residual_visual_deg': round(rn_[bl], 3),
                     'ratio_residual': round(rn_[bl] / rr_[bl], 3) if rr_[bl] > 0 else None})
    spread = _lola_spread(P, lat, lon)
    five = {k: _r(np.median(five_spot_shots(a, q))) for k, a in
            (('real_5m', real), ('visual', vis), ('bilinear_80m', base), ('residual_real', real - base),
             ('added', noise))}
    pg = None
    try:
        p70 = PGDA70()
        pg = {'hurst_pgda70': _r(p70.hurst(clat, clon)[0]), 'hurst_real_5m': _r(deviogram_hurst(real, q)),
              'hurst_visual': _r(deviogram_hurst(vis, q)), 'hurst_bilinear_80m': _r(deviogram_hurst(base, q)), 'mas': []}
        for bl in PGDA70_BASELINES:
            ref = float(p70.median_abs_slope_deg(clat, clon, bl)[0])
            pg['mas'].append({'baseline_m': bl, 'pgda70_deg': _r(ref, 3),
                              'real_5m_deg': _r(median_abs_slope_deg(real, q, bl), 3),
                              'visual_deg': _r(median_abs_slope_deg(vis, q, bl), 3),
                              'bilinear_80m_deg': _r(median_abs_slope_deg(base, q, bl), 3)})
    except FileNotFoundError:
        pass
    sub = [r for r in rows if r['baseline_m'] < 160.0]
    res_ratio = round(float(np.mean([r['ratio_residual'] for r in sub])), 3) if sub else None
    slope_ok = all(SLOPE_BAND[0] <= r['ratio_visual'] <= SLOPE_BAND[1] for r in rows)
    spread_ok = spread['q25_m'] is not None and spread['q25_m'] <= five['visual'] <= spread['q75_m']
    hurst_ok = pg is None or abs(pg['hurst_visual'] - pg['hurst_pgda70']) <= HURST_GUARD
    res_ok = res_ratio is not None and res_ratio <= RESIDUAL_GUARD
    return {'product': spec.product_id, 'centre_latlon': [_r(clat, 5), _r(clon, 5)], 'half_m': half_m, 'rows': rows,
            'lola_spread': spread, 'five_spot_median_m': five,
            'pass_slope_band': slope_ok, 'pass_lola_spread': spread_ok, 'pass_hurst_guard': hurst_ok,
            'pass_residual_guard': res_ok, 'pass': bool(slope_ok and spread_ok and hurst_ok and res_ok),
            'sub_resolution_mean_ratio_residual': res_ratio, 'pgda70': pg, 'diag': diag}


def check_window(stack, name, lat0, lon0, half_m=2500.0, q=5.0, pad=16):
    """LOLA-spread check of the displayed surface (full science pyramid + VISUAL at 5 m) around any point: emulated
    5-spot roughness median inside [median LDRM_25, median LDRM_75] over the window's LOLA bins."""
    P = lola()
    n = int(2 * half_m / q)
    xs = (np.arange(-pad, n + pad) + 0.5) * q - half_m
    X, Y = np.meshgrid(xs, -xs)
    lat, lon = S.oblique_stereo_inverse(X, Y, lat0, lon0)
    zone = str(S.zone_name_for(lat0))
    vis, base, noise, diag = synthesize(stack, lat, lon, q, zone=zone, pad=pad)
    sl = (slice(pad, -pad), slice(pad, -pad))
    vis, base, noise, lat, lon = vis[sl], base[sl], noise[sl], lat[sl], lon[sl]
    if not np.isfinite(vis).all():
        return {'name': name, 'lat': lat0, 'lon': lon0, 'pass': False, 'error': 'real terrain missing in window'}
    spread = _lola_spread(P, lat, lon)
    rq = stack._query(np.array([lat0]), np.array([lon0]), zone=zone)
    five = {k: _r(np.median(five_spot_shots(a, q))) for k, a in (('visual', vis), ('real_bilinear', base))}
    ok = spread['q25_m'] is not None and spread['q25_m'] <= five['visual'] <= spread['q75_m']
    prof = rms_slope_profile(vis, q, baselines=(15.0, 40.0, 160.0, 640.0, 2560.0))
    return {'name': name, 'lat': lat0, 'lon': lon0, 'zone': zone, 'native_res_m': _r(rq['native_res_m'][0], 2),
            'source_id': int(rq['source_id'][0]), 'lola_spread': spread, 'five_spot_median_m': five,
            'rms_slope_deg': {str(int(k)): round(v, 3) for k, v in prof.items()},
            'pass': bool(ok), 'diag': diag}


def check_windows():
    """Fixed test windows (not chosen by result): the any-site landing sites, plus two north-polar points on the LOLA
    20 m / 10 m LDEMs (the only zone with no landing site)."""
    sites = []
    p = Path(__file__).resolve().parents[2] / 'data' / 'anysite' / 'precompute_summary.json'
    if p.exists():
        for s in json.loads(p.read_text())['sites']:
            if s.get('group') == 'landing_sites' and s.get('lat') is not None:
                sites.append((s['id'], float(s['lat']), float(s['lon'])))
    sites += [('north_82n_090e', 82.0, 90.0), ('north_86n_m045e', 86.0, -45.0)]
    return sites


def run_check(write=True, log=print, windows=True):
    stack = S.TerrainStack.open()
    sites = [s for s in PP.local_products() if s.source_id == 3]
    res = []
    for s in sites:
        r = check_pgda78_site(stack, s)
        res.append(r)
        log(f"{s.product_id}: pass={r['pass']} (slope {r['pass_slope_band']}, LOLA spread {r['pass_lola_spread']}, "
            f"Hurst {r['pass_hurst_guard']}, residual {r['pass_residual_guard']}) 5-spot median "
            f"{r['five_spot_median_m']} LOLA {r['lola_spread']} residual ratio {r['sub_resolution_mean_ratio_residual']}")
        for row in r['rows']:
            log(f"   {row['baseline_m']:7.0f} m  real {row['real_5m_deg']:6.2f}  visual {row['visual_deg']:6.2f}  "
                f"ratio {row['ratio_visual']:.3f}   residual real {row['residual_real_deg']:5.2f} added "
                f"{row['residual_visual_deg']:5.2f} ratio {row['ratio_residual']}")
    win = []
    if windows:
        for name, la, lo in check_windows():
            w = check_window(stack, name, la, lo)
            win.append(w)
            log(f"window {name} ({la:.2f}, {lo:.2f}) {w.get('zone')} native {w.get('native_res_m')} m: "
                f"pass={w['pass']} 5-spot {w.get('five_spot_median_m')} LOLA {w.get('lola_spread')}")
    out = {'created_utc': _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
           'label': 'VISUAL roughness check (display layer QA; not science)',
           'model': {'params_source': PARAMS_SOURCE, 'lam_min_m': LAM_MIN, 'lam_ref_m': LAM_REF, 'spot_m': SPOT_M,
                     'ldrm_smoothing_box_m': SMOOTH_M, 'seed': hex(SEED), 'noise': '3-D value noise, Moon-fixed lattice'},
           'criteria': {'lola_spread': 'emulated LOLA 5-spot roughness (median over 20,000 shots) of the displayed '
                                       'surface within [median LDRM_32_25, median LDRM_32_75] over the window bins',
                        'slope_band': list(SLOPE_BAND), 'residual_guard': RESIDUAL_GUARD,
                        'hurst_guard': HURST_GUARD, 'baselines_m': list(BASELINES_M)},
           'previous_model_s3': {'note': 'S3 self-fit extrapolation (replaced 16 Nov by R2): added / real sub-80 m '
                                         'residual RMS slope, mean over 15-80 m', 'pgda78_site01_5m': 1.865,
                                 'pgda78_site04_5m': 1.202, 'pgda78_site07_5m': 1.902, 'pgda78_site11_5m': 1.365},
           'pgda78_sites': res, 'windows': win,
           'all_pass': all(r['pass'] for r in res) and all(w['pass'] for w in win)}
    if write:
        from tools.globe.seams import update_qa_doc
        update_qa_doc('roughness', out)
    return out


# ------------------------------------------------------------------------------------------ builds
def _build_worker(args):
    zone, level, tiles, root = args
    stack = S.TerrainStack.open()
    n = 0
    for ix, iy in tiles:
        p = visual_tile_path(zone, level, ix, iy, root)
        if p.exists():
            continue
        if write_visual_tile(stack, zone, level, ix, iy, root=root) is not None:
            n += 1
    return n


def build_tiles(zone, level, tiles, root=None, workers=1, log=print):
    """Build (skip existing) the given VISUAL tiles, in up to `workers` processes."""
    lola().smooth50(); g_table()
    tiles = list(tiles)
    if workers <= 1:
        n = _build_worker((zone, level, tiles, root))
    else:
        from multiprocessing import get_context
        chunks = [tiles[i::workers * 8] for i in range(workers * 8)]
        with get_context('spawn').Pool(workers) as pool:
            n = sum(pool.map(_build_worker, [(zone, level, c, root) for c in chunks if c]))
    log(f'wrote {n} VISUAL tiles ({zone} L{level}, {len(tiles)} requested)')
    return n


def build(zone, level, bbox, root=None, workers=1, log=print):
    return build_tiles(zone, level, PY.tiles_for_bbox(zone, level, bbox), root=root, workers=workers, log=log)


def polar_cap_tiles(zone, level, lat_lo, lat_hi=90.0):
    """Tiles of a polar zone that intersect the ring lat_lo <= |lat| <= lat_hi (by tile corners and centre)."""
    Z = S.ZONES[zone]
    nx, ny = Z.n_tiles(level)
    rho = lambda a: 2 * R_M * math.tan(math.pi / 4 - math.radians(a) / 2)
    r_out, r_in = rho(lat_lo), rho(lat_hi)
    s = Z.pixel(level) * Z.tile_px
    out = []
    for iy in range(ny):
        for ix in range(nx):
            l, b, r, t = Z.tile_bounds(level, ix, iy)
            dmin = math.hypot(max(l, min(0.0, r)), max(b, min(0.0, t)))
            dmax = max(math.hypot(x, y) for x in (l, r) for y in (b, t))
            if dmin <= r_out and dmax >= r_in:
                out.append((ix, iy))
    return out


def eq_box_tiles(level, lat0, lon0, half_km):
    Z = S.ZONES['eq']
    dlat = math.degrees(half_km * 1000 / R_M)
    dlon = dlat / max(math.cos(math.radians(lat0)), 0.05)
    return PY.tiles_for_bbox('eq', level, (lon0 - dlon, lat0 - dlat, lon0 + dlon, lat0 + dlat))


def prebuild_plan():
    """The budgeted pre-built VISUAL set (R2 plan §2); everything else is built on demand by ensure_visual_tile."""
    plan = [('sp', 6, polar_cap_tiles('sp', 6, 80.0)),          # 20 m over PGDA 90 80 m
            ('sp', 7, polar_cap_tiles('sp', 7, 85.0)),          # 10 m near the south pole
            ('np', 7, polar_cap_tiles('np', 7, 80.0, 85.0))]    # 10 m over the LOLA 20 m LDEM ring
    for name, la, lo in check_windows():
        if abs(la) < S.ZONE_SWITCH_ABS_LAT:
            plan.append(('eq', 6, eq_box_tiles(6, la, lo, 20.0)))
    return plan


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.globe.roughness')
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('check'); c.add_argument('--no-windows', action='store_true')
    b = sub.add_parser('build')
    b.add_argument('--zone', default='sp'); b.add_argument('--level', type=int, default=6)
    b.add_argument('--bbox', required=True); b.add_argument('--workers', type=int, default=1)
    pb = sub.add_parser('prebuild'); pb.add_argument('--workers', type=int, default=3)
    pb.add_argument('--only', default=None, help='zone filter')
    sub.add_parser('params')
    a = ap.parse_args(argv)
    if a.cmd == 'check':
        r = run_check(windows=not a.no_windows)
        return 0 if r['all_pass'] else 1
    if a.cmd == 'params':
        lola().smooth50(); print(g_table()[2].round(3))
        return 0
    if a.cmd == 'prebuild':
        for zone, level, tiles in prebuild_plan():
            if a.only and zone != a.only:
                continue
            build_tiles(zone, level, tiles, workers=a.workers)
        return 0
    build(a.zone, a.level, tuple(float(v) for v in a.bbox.split(',')), workers=a.workers)
    return 0


if __name__ == '__main__':
    sys.exit(main())
