"""VISUAL sub-resolution relief and the roughness check (prompt §2.3, plan §9). Display only: never science.

Everything at or above a product's native posting comes from the data as-is (the science pyramid, bilinear). Below it,
fractal micro-relief is added whose RMS deviation follows the local self-affine law
    nu(D) = nu0 * (D / D0)^H          (RMS slope s(D) = nu(D) / D = s0 (D / D0)^(H - 1))
with the Hurst exponent H and nu0 per parameter cell. Parameter source:
  * "self-fit" (tonight): fitted on the real DEM's own resolved relief at lags of 2, 4 and 8 base pixels and
    extrapolated below the posting. Labelled as such in every tile.
  * "pgda70" (when S2 delivers LOLA PGDA 70 / RMHE Hurst and slope maps): not implemented yet (raises).

Noise: a sum of octaves of smooth value noise (quintic fade) on a GLOBAL lattice whose values are a hash of the
lattice index, the octave wavelength and a fixed seed. A tile is therefore a pure function of its tile id (deterministic
renders) and adjacent tiles agree at their edges. Octave j has wavelength lam_j, weight w_j(x) = clip(log2(2 res(x) /
lam_j), 0, 1) (only wavelengths below twice the local native resolution res(x); res smoothed so the amplitude has no
seam at product edges) and amplitude a_j = A(x) lam_j^H(x). A(x) makes the displayed structure function at the reference
baseline Dref = 2 q (q = VISUAL pixel) equal the extrapolated law: nu_t(Dref)^2 = (s1 Dref)^2 + A^2 sum_j lam_j^2H w_j^2
D1(Dref / lam_j), where s1 Dref is what bilinear interpolation of the real surface already carries and D1 is the
calibrated single-octave structure function. Small craters and boulders are NOT added (no published size-frequency
statistics were checked and cited tonight).

    python -m tools.globe.roughness check            # roughness check at the PGDA 78 sites (writes PYRAMID_QA.json)
    python -m tools.globe.roughness build --zone sp --level 8 --base-level 4 --bbox l,b,r,t

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
PARAM_CELL_PX = 32                  # parameter cell, in base-level pixels (2.56 km at 80 m)
H_MIN, H_MAX = 0.3, 1.0
BASELINES_M = (15.0, 20.0, 40.0, 80.0, 160.0, 320.0, 640.0, 1280.0, 2560.0)   # ~17 m .. 2.7 km (multiples of 5 m)
RATIO_BAND = (0.67, 1.5)           # provisional pass band of displayed / reference RMS slope [decision, plan §9]


def visual_root():
    return PP.polaris_data() / 'v2' / 'pyramid_visual'


# ------------------------------------------------------------------------------------------ noise
_M1 = np.uint64(0x9E3779B97F4A7C15); _M2 = np.uint64(0xC2B2AE3D27D4EB4F)
_M3 = np.uint64(0xBF58476D1CE4E5B9); _M4 = np.uint64(0x94D049BB133111EB)


def _hash01(i, j, seed):
    with np.errstate(over='ignore'):
        x = (i.astype(np.int64).astype(np.uint64) * _M1) ^ (j.astype(np.int64).astype(np.uint64) * _M2) ^ np.uint64(seed)
        x ^= x >> np.uint64(30); x *= _M3
        x ^= x >> np.uint64(27); x *= _M4
        x ^= x >> np.uint64(31)
    return (x >> np.uint64(11)).astype(np.float64) / float(1 << 53)


def octave_seed(lam):
    """Seed of the octave with wavelength lam (m): a function of lam only, so every tile/base level shares it."""
    e = int(round(math.log2(lam / 1.25) * 8))
    return (SEED ^ (e * 0x100000001B3)) & 0xFFFFFFFFFFFFFFFF


def value_noise(u, v, seed):
    """Unit-variance smooth value noise at lattice coordinates (u, v); lattice values uniform in [-sqrt3, sqrt3]."""
    i = np.floor(u); j = np.floor(v)
    fu = u - i; fv = v - j
    fu = fu * fu * fu * (fu * (fu * 6 - 15) + 10); fv = fv * fv * fv * (fv * (fv * 6 - 15) + 10)
    i = i.astype(np.int64); j = j.astype(np.int64)
    s3 = math.sqrt(3.0)

    def g(a, b):
        return (2 * _hash01(a, b, seed) - 1) * s3
    return ((1 - fu) * (1 - fv) * g(i, j) + fu * (1 - fv) * g(i + 1, j)
            + (1 - fu) * fv * g(i, j + 1) + fu * fv * g(i + 1, j + 1))


_D1 = None


def d1(rho):
    """Structure function E[(n(x + rho) - n(x))^2] of one octave (lattice spacing 1) at distance rho, calibrated by
    Monte Carlo with a fixed seed (deterministic) and interpolated in log rho."""
    global _D1
    if _D1 is None:
        rng = np.random.default_rng(12345)
        rr = np.logspace(-3, 1.5, 46)
        n = 40000
        x = rng.uniform(0, 1000, n); y = rng.uniform(0, 1000, n); th = rng.uniform(0, 2 * np.pi, n)
        n0 = value_noise(x, y, 7)
        vals = [float(np.mean((value_noise(x + r * np.cos(th), y + r * np.sin(th), 7) - n0) ** 2)) for r in rr]
        _D1 = (np.log(rr), np.log(np.maximum(vals, 1e-30)))
    lr, lv = _D1
    return np.exp(np.interp(np.log(np.asarray(rho, float)), lr, lv))


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


# Tried 16 Nov: detrending each cell before the fit makes the added sub-resolution relief 2.0-2.4x the PGDA 78 5 m
# residual (vs 1.2-2.0x without), so the default is off. See docs/v2/PYRAMID_QA.json "roughness".
DETREND = False


def _detrend(c):
    """Remove the least-squares plane of a cell (the resolved regional tilt is carried by the real surface itself;
    only the relief about it is self-affine roughness)."""
    ny, nx = c.shape
    J, I = np.mgrid[0:ny, 0:nx]
    m = np.isfinite(c)
    A = np.stack([I[m], J[m], np.ones(m.sum())], 1)
    coef = np.linalg.lstsq(A, c[m], rcond=None)[0]
    return c - (coef[0] * I + coef[1] * J + coef[2])


def fit_params(Zb, pb, cell_px=PARAM_CELL_PX, detrend=None):
    """Self-fit per cell of a base-level mosaic Zb (pixel pb), on the cell minus its best-fit plane (detrend=True):
    H from log nu vs log D at lags 2, 4, 8 px; nu0 = nu(2 px); s1 = nu(1 px) / pb (the roughness bilinear
    interpolation already carries). Returns arrays on the cell grid."""
    detrend = DETREND if detrend is None else detrend
    ny, nx = Zb.shape[0] // cell_px, Zb.shape[1] // cell_px
    H = np.full((ny, nx), np.nan); nu0 = np.full((ny, nx), np.nan); s1 = np.full((ny, nx), np.nan)
    lags = np.array([2, 4, 8]); ll = np.log(lags * pb)
    for j in range(ny):
        for i in range(nx):
            c = Zb[j * cell_px:(j + 1) * cell_px, i * cell_px:(i + 1) * cell_px]
            if np.isfinite(c).mean() < 0.5:
                continue
            if detrend:
                c = _detrend(c)
            nus = np.array([rms_dev(c, int(l)) for l in lags])
            if not np.all(np.isfinite(nus)) or np.any(nus <= 0):
                continue
            h = np.polyfit(ll, np.log(nus), 1)[0]
            H[j, i] = np.clip(h, H_MIN, H_MAX); nu0[j, i] = nus[0]; s1[j, i] = rms_dev(c, 1) / pb
    return _fill_nan_nearest(H), _fill_nan_nearest(nu0), _fill_nan_nearest(s1)


def _fill_nan_nearest(a):
    from scipy import ndimage
    m = np.isnan(a)
    if not m.any() or m.all():
        return a
    idx = ndimage.distance_transform_edt(m, return_distances=False, return_indices=True)
    return a[tuple(idx)]


# ------------------------------------------------------------------------------------------ synthesis
def _mosaic(stack, zone, L, l, b, r, t):
    Z = S.ZONES[zone]
    p = Z.pixel(L)
    c0 = int(math.floor((l - Z.left) / p)); c1 = int(math.ceil((r - Z.left) / p))
    r0 = int(math.floor((Z.top - t) / p)); r1 = int(math.ceil((Z.top - b) / p))
    rr, cc = np.meshgrid(np.arange(r0, r1), np.arange(c0, c1), indexing='ij')
    g = stack._gather(zone, L, rr, cc)
    return g[0].astype(np.float64), Z.left + c0 * p, Z.top - r0 * p


def visual_grid(stack, zone, x_left, y_top, q, ny, nx, base_level, real_levels=None, pad=16, assume_native_m=None):
    """VISUAL heights on an aligned polar grid (pixel q, ny x nx) plus diagnostics.
    real_levels: levels the real base surface may use (None = all; the roughness check passes <= base_level).
    assume_native_m: treat the base as having this native resolution everywhere (the roughness check uses the 80 m
    level over a PGDA 78 site, whose pixels honestly carry native_res_m = 5 m)."""
    Z = S.ZONES[zone]
    if Z.kind != 'polar':
        raise NotImplementedError('VISUAL synthesis is implemented for the polar zones first (eq: not done tonight)')
    pb = Z.pixel(base_level)
    # parameters from the base level, on a margin of two cells
    m = 2 * PARAM_CELL_PX * pb
    l, t = x_left - m, y_top + m
    r, b = x_left + nx * q + m, y_top - ny * q - m
    l = Z.left + math.floor((l - Z.left) / (PARAM_CELL_PX * pb)) * PARAM_CELL_PX * pb
    t = Z.top - math.floor((Z.top - t) / (PARAM_CELL_PX * pb)) * PARAM_CELL_PX * pb
    Zb, bl, bt = _mosaic(stack, zone, base_level, l, b, r, t)
    H, nu0, s1 = fit_params(Zb, pb)
    D0 = 2 * pb
    # pixel grid (+pad for smoothing res)
    xs = x_left + (np.arange(-pad, nx + pad) + 0.5) * q
    ys = y_top - (np.arange(-pad, ny + pad) + 0.5) * q
    X, Y = np.meshgrid(xs, ys)
    lat, lon = Z.inverse(X, Y)
    qy = stack._query(lat, lon, levels=real_levels)
    base = qy['height']
    res = qy['native_res_m'].astype(np.float64)
    res = np.where(np.isfinite(res), res, pb)
    if assume_native_m is not None:
        res = np.full(res.shape, float(assume_native_m))
    from scipy import ndimage
    lres = ndimage.gaussian_filter(np.log2(res), sigma=pad / 2.0, mode='nearest')
    lam_max = 2.0 * np.exp2(lres)
    # parameters at pixels (bilinear on cell centres)
    cs = PARAM_CELL_PX * pb
    ci = (X - bl) / cs - 0.5; cj = (bt - Y) / cs - 0.5
    Hp = ndimage.map_coordinates(H, [cj, ci], order=1, mode='nearest')
    nup = ndimage.map_coordinates(nu0, [cj, ci], order=1, mode='nearest')
    s1p = ndimage.map_coordinates(s1, [cj, ci], order=1, mode='nearest')
    Dref = 2.0 * q
    nu_t2 = (nup * (Dref / D0) ** Hp) ** 2
    carried = (s1p * Dref) ** 2
    lams = []
    lam = 2.0 * float(np.nanmax(lam_max))
    while lam >= 2 * q * 0.999:
        lams.append(lam); lam /= 2.0
    denom = np.zeros(X.shape); W = []
    for lam in lams:
        w = np.clip(np.log2(lam_max / lam), 0.0, 1.0)
        W.append(w)
        denom += lam ** (2 * Hp) * w * w * d1(Dref / lam)
    A = np.sqrt(np.maximum(nu_t2 - carried, 0.0) / np.where(denom > 0, denom, np.inf))
    noise = np.zeros(X.shape)
    for lam, w in zip(lams, W):
        if not (w > 0).any():
            continue
        noise += A * lam ** Hp * w * value_noise(X / lam, Y / lam, octave_seed(lam))
    vis = base + noise
    sl = (slice(pad, pad + ny), slice(pad, pad + nx))
    diag = {'params_source': 'self-fit', 'base_level': base_level, 'base_pixel_m': pb, 'visual_pixel_m': q,
            'octaves_m': lams, 'H_range': [float(np.nanmin(H)), float(np.nanmax(H))],
            'noise_rms_m': float(np.sqrt(np.nanmean(noise[sl] ** 2))), 'seed': hex(SEED)}
    return vis[sl], base[sl], noise[sl], diag


def write_visual_tile(stack, zone, level, ix, iy, base_level, root=None, real_levels=None):
    import rasterio
    from rasterio.crs import CRS
    from rasterio.transform import from_origin
    Z = S.ZONES[zone]
    l, b, r, t = Z.tile_bounds(level, ix, iy)
    q = Z.pixel(level)
    vis, base, noise, diag = visual_grid(stack, zone, l, t, q, Z.tile_px, Z.tile_px, base_level, real_levels=real_levels)
    if not np.isfinite(vis).any():
        return None
    root = Path(root) if root else visual_root()
    path = root / zone / str(level) / f'{ix}_{iy}.tif'
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp.tif')
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


# ------------------------------------------------------------------------------------------ roughness check
def check_site(stack, spec, half_m=4000.0, base_level=4):
    """Displayed RMS slope vs the real 5 m PGDA 78 surface at one site, with VISUAL built from the 80 m level only."""
    rd = PP.ProductReader(spec)
    try:
        cx = rd.left + rd.w * rd.px_x / 2; cy = rd.top - rd.h * rd.px_y / 2
        q = rd.px_x
        n = int(2 * half_m / q)
        x_left = cx - half_m; y_top = cy + half_m
        xs = x_left + (np.arange(n) + 0.5) * q; ys = y_top - (np.arange(n) + 0.5) * q
        X, Y = np.meshgrid(xs, ys)
        lat, lon = rd.grid_to_latlon(X, Y)
        real, _, _ = rd.sample(lat, lon, q)
    finally:
        rd.close()
    vis, base, noise, diag = visual_grid(stack, 'sp', x_left, y_top, q, n, n, base_level,
                                         real_levels=list(range(0, base_level + 1)),
                                         assume_native_m=S.ZONES['sp'].pixel_m(base_level))
    pr, pv, pb_ = rms_slope_profile(real, q), rms_slope_profile(vis, q), rms_slope_profile(base, q)
    # sub-resolution component alone: what the real 5 m surface has beyond the bilinear 80 m one, vs the added relief
    rr_, rn_ = rms_slope_profile(real - base, q), rms_slope_profile(noise, q)
    rows = []
    for bl in pr:
        rows.append({'baseline_m': bl, 'real_5m_deg': round(pr[bl], 3), 'visual_deg': round(pv[bl], 3),
                     'bilinear_80m_deg': round(pb_[bl], 3), 'ratio_visual': round(pv[bl] / pr[bl], 3),
                     'ratio_bilinear': round(pb_[bl] / pr[bl], 3),
                     'residual_real_deg': round(rr_[bl], 3), 'residual_visual_deg': round(rn_[bl], 3),
                     'ratio_residual': round(rn_[bl] / rr_[bl], 3) if rr_[bl] > 0 else None})
    sub = [r for r in rows if r['baseline_m'] < 2 * diag['base_pixel_m']]
    ok = all(RATIO_BAND[0] <= r['ratio_visual'] <= RATIO_BAND[1] for r in rows)
    return {'product': spec.product_id, 'centre_grid_m': [cx, cy], 'half_m': half_m, 'rows': rows,
            'pass': ok, 'ratio_band': list(RATIO_BAND),
            'sub_resolution_mean_ratio_visual': round(float(np.mean([r['ratio_visual'] for r in sub])), 3) if sub else None,
            'sub_resolution_mean_ratio_bilinear': round(float(np.mean([r['ratio_bilinear'] for r in sub])), 3) if sub else None,
            'sub_resolution_mean_ratio_residual': round(float(np.mean([r['ratio_residual'] for r in sub])), 3) if sub else None,
            'diag': diag}


def run_check(write=True, log=print):
    stack = S.TerrainStack.open()
    sites = [s for s in PP.local_products() if s.source_id == 3]
    res = []
    for s in sites:
        r = check_site(stack, s)
        res.append(r)
        log(f"{s.product_id}: pass={r['pass']} sub-res ratio visual {r['sub_resolution_mean_ratio_visual']} "
            f"vs bilinear {r['sub_resolution_mean_ratio_bilinear']}")
        for row in r['rows']:
            log(f"   {row['baseline_m']:7.0f} m  real {row['real_5m_deg']:6.2f}  visual {row['visual_deg']:6.2f}  "
                f"bilinear {row['bilinear_80m_deg']:6.2f}  ratio {row['ratio_visual']:.2f}   residual real "
                f"{row['residual_real_deg']:5.2f} added {row['residual_visual_deg']:5.2f} ratio {row['ratio_residual']}")
    out = {'created_utc': _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
           'label': 'VISUAL roughness check (display layer QA; not science)',
           'reference': 'PGDA 78 LOLA 5 m surface at each site (real); VISUAL built from the 80 m level only (PGDA 90), '
                        'params self-fit; PGDA 70 comparison: not done (product not on disk)',
           'baselines_m': list(BASELINES_M), 'ratio_band': list(RATIO_BAND), 'sites': res,
           'all_pass': all(r['pass'] for r in res)}
    if write:
        from tools.globe.seams import update_qa_doc
        update_qa_doc('roughness', out)
    return out


def build(zone, level, base_level, bbox, root=None, log=print):
    stack = S.TerrainStack.open()
    tiles = PY.tiles_for_bbox(zone, level, bbox)
    n = 0
    for ix, iy in tiles:
        if write_visual_tile(stack, zone, level, ix, iy, base_level, root=root) is not None:
            n += 1
    log(f'wrote {n} VISUAL tiles ({zone} L{level}, base L{base_level})')
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.globe.roughness')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('check')
    b = sub.add_parser('build')
    b.add_argument('--zone', default='sp'); b.add_argument('--level', type=int, default=8)
    b.add_argument('--base-level', type=int, default=4); b.add_argument('--bbox', required=True)
    a = ap.parse_args(argv)
    if a.cmd == 'check':
        r = run_check()
        return 0 if r['all_pass'] else 1
    build(a.zone, a.level, a.base_level, tuple(float(v) for v in a.bbox.split(',')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
