"""Solver runs behind the scenario cube (float64 heights, the bundle skyline settings).

Skylines: 720 bins, 1 m near-field ray step on the PGDA 78 5 m tile (nominal or clone k), PGDA 90 80 m
far field to 280 km, observer = near-DEM ground + mast (science/skyline.compute_skyline, unchanged).
Centre-position skylines at mast 1 m reuse the science-limits cache (bit-identical settings).

Position offsets (D_pos) are in polar-stereographic grid metres (dx east-of-grid, dy north-of-grid),
as the research 81-cell grid (dx, dy in -100..100 step 25, step11_sfs_analyze.py / step12_more.py).
Ephemeris at an offset position: the centre Horizons az/el is turned into a Moon-fixed direction and
re-expressed in the offset site's local ENU. Parallax over <=142 m is < 2.2e-5 deg for Earth and
negligible for the Sun (stated in docs/SCENARIO_CUBE_CONTRACT.md).

Visibility margins are vectorised copies of science/crossings.margins (same linear skyline
interpolation and perpendicular margin); test_cube checks they agree with crossings.margins.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from .. import frames, sites
from ..skyline import compute_skyline

ROOT = Path(__file__).resolve().parents[2]
SKY = ROOT / 'data' / 'cache' / 'cube_sky'
LIMITS_SKY = ROOT / 'data' / 'cache' / 'science_limits'
MASTS = tuple(float(m) for m in range(1, 11))
OFFSETS = tuple((dx, dy) for dx in range(-100, 101, 25) for dy in range(-100, 101, 25))   # 81, row-major dx then dy
CLONES = tuple(range(1, 21))
T_IDS = ('nominal',) + tuple(f'clone{c:02d}' for c in CLONES)
KEEP = ('bins', 'elevation_deg', 'status', 'n_truncated', 'max_range_m', 'near_cut_m', 'step_near_m', 'step_far_m')


def _clone_of(t_id):
    return None if t_id == 'nominal' else int(t_id[5:])


def offset_latlon(site, dx, dy):
    s = sites.SITES[site]
    x0, y0 = frames.stereo_forward(s['lat'], s['lon'])
    la, lo = frames.stereo_inverse(x0 + dx, y0 + dy)
    return float(la), float(lo)


def sky_key(site, t_id, mast, dx, dy):
    return f'{site}_{t_id}_m{mast:g}_x{dx}_y{dy}'


def skyline(site, t_id, mast=1.0, dx=0, dy=0, near=None, far=None):
    """Cached skyline dict (elevation_deg list with None for no-data bins) + ground_m."""
    p = SKY / f'{sky_key(site, t_id, mast, dx, dy)}.json'
    if p.exists():
        return json.loads(p.read_text())
    clone = _clone_of(t_id)
    if dx == 0 and dy == 0 and mast == 1.0:
        lim = LIMITS_SKY / (f'{site}_{"nom" if clone is None else f"c{clone:02d}"}_b720_s1.0_r280000_nNone_m1.0.json')
        if lim.exists():
            d = json.loads(lim.read_text())
            out = {k: d[k] for k in KEEP}; out['ground_m'] = d['ground_m']; out['source_cache'] = lim.name
            SKY.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(out))
            return out
    nd = near if near is not None else sites.near_dem(site, clone=clone)
    fd = far if far is not None else sites.far_dem(site)
    if dx == 0 and dy == 0:
        s = sites.SITES[site]; lat, lon = s['lat'], s['lon']
    else:
        lat, lon = offset_latlon(site, dx, dy)
    x, y = frames.stereo_forward(lat, lon)
    h = float(nd.sample(x, y))
    sky = compute_skyline(lat, lon, h, mast, near=nd, far=fd, bins=720, max_range_m=sites.MAX_RANGE_M,
                          step_m=sites.NEAR_RAY_STEP_M)
    out = {k: sky[k] for k in KEEP}; out['ground_m'] = h; out['lat'] = lat; out['lon'] = lon
    SKY.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(out))
    return out


def transfer_azel(az, el, lat0, lon0, lat1, lon1):
    """Re-express directions (az/el at site 0) in the local frame of site 1 (direction only)."""
    e0, n0, u0 = frames.enu_basis(lat0, lon0)
    a = np.radians(az); e = np.radians(el)
    v = (np.cos(e) * np.sin(a))[:, None] * e0 + (np.cos(e) * np.cos(a))[:, None] * n0 + np.sin(e)[:, None] * u0
    e1, n1, u1 = frames.enu_basis(lat1, lon1)
    ve, vn, vu = v @ e1, v @ n1, v @ u1
    return np.degrees(np.arctan2(ve, vn)) % 360.0, np.degrees(np.arcsin(np.clip(vu, -1, 1)))


def margins_vec(az, el, sky):
    """Vectorised science/crossings.margins: returns (margin_deg, margin_perp_deg) with NaN where
    either neighbouring skyline bin has no data."""
    n = sky['bins']; w = 360.0 / n
    E = np.array([np.nan if v is None else v for v in sky['elevation_deg']], float)
    u = (np.asarray(az) % 360.0) / w
    fl = np.floor(u); i0 = fl.astype(int) % n; i1 = (i0 + 1) % n; a = u - fl
    e0, e1 = E[i0], E[i1]
    Hh = (1 - a) * e0 + a * e1
    s = (e1 - e0) / w
    s_eff = s / np.maximum(np.cos(np.radians(el)), 1e-6)
    m = np.asarray(el) - Hh
    return m, m / np.sqrt(1 + s_eff ** 2)


def visible_flags(eph, sky, lat0=None, lon0=None, lat1=None, lon1=None):
    """Hourly centre-visibility flags (bool) for Sun and Earth, plus a missing mask."""
    out = {}
    for body in ('sun', 'earth'):
        az, el = eph[f'{body}_az'], eph[f'{body}_el']
        if lat1 is not None:
            az, el = transfer_azel(az, el, lat0, lon0, lat1, lon1)
        m, mp = margins_vec(az, el, sky)
        out[body] = np.nan_to_num(mp, nan=-1.0) > 0
        out[f'{body}_missing'] = ~np.isfinite(mp)
        out[f'{body}_mp'] = mp
    return out


def window_metrics(sun, earth, n_starts, window_h, stride=1):
    """Per-start 14-day window metrics from hourly flags (window = window_h + 1 samples, both ends):
    visible-sample counts (Sun, Sun AND Earth, Earth) and longest runs of hidden samples (h, x 1 h)."""
    from numpy.lib.stride_tricks import sliding_window_view as swv
    L = window_h + 1
    starts = np.arange(0, n_starts, stride)

    def counts(f):
        c = np.concatenate([[0], np.cumsum(f.astype(np.int32))])
        return (c[starts + L] - c[starts]).astype(np.int32)

    def longest(f):
        run = np.zeros(f.size, np.int32); cur = 0
        for i, v in enumerate(f):
            cur = 0 if v else cur + 1; run[i] = cur
        W = swv(run, L)[starts]
        return np.minimum(W, np.arange(1, L + 1, dtype=np.int32)[None, :]).max(axis=1).astype(np.int32)

    both = sun & earth
    return {'sun_n': counts(sun), 'both_n': counts(both), 'earth_n': counts(earth),
            'sun_gap_h': longest(sun), 'earth_gap_h': longest(earth), 'n_samples': L}


def multi_skyline(lat, lon, near_by_t, far, masts_by_t):
    """Exact batched form of science/skyline.compute_skyline for one (lat, lon): the ray geometry and
    the far-field samples are computed once and shared by every terrain map T and mast height; the
    near DEM is sampled per T and the elevation angles per (T, mast). Same operations in the same
    order as compute_skyline, so the KEEP fields are bit-identical (test_cube checks this).
    Returns {(t_id, mast): skyline dict}."""
    from ..skyline import _distances, _near_extent
    any_near = next(iter(near_by_t.values()))
    near_cut = _near_extent(any_near, lat, lon)
    for nd in near_by_t.values():
        if nd.bounds != any_near.bounds or nd.step != any_near.step:
            raise ValueError('near DEMs differ in footprint; batch by footprint')
    step_near = sites.NEAR_RAY_STEP_M; step_far = far.step; max_range = sites.MAX_RANGE_M
    d = _distances(step_near, near_cut, step_far, max_range)
    bins = 720
    az = np.arange(bins) * 360.0 / bins
    A, D = np.meshgrid(az, d, indexing='ij')
    la2, lo2 = frames.destination(lat, lon, A, D)
    x, y = frames.stereo_forward(la2, lo2)
    hf = far.sample(x, y); mf_ok = np.isfinite(hf)
    U = frames.unit(la2, lo2)
    up = frames.up_vector(lat, lon)
    x0, y0 = frames.stereo_forward(lat, lon)
    out = {}
    for t_id, nd in near_by_t.items():
        h = np.full(A.shape, np.nan)
        hn = nd.sample(x, y); m = np.isfinite(hn); h[m] = hn[m]
        m = ~np.isfinite(h) & mf_ok; h[m] = hf[m]
        P = (frames.R_MOON_M + np.nan_to_num(h))[..., None] * U
        valid = np.isfinite(h)
        first_gap = np.where(valid.all(axis=1), d.size, np.argmin(valid, axis=1))
        ground = float(nd.sample(x0, y0))
        for mast in masts_by_t[t_id]:
            P_obs = frames.moon_fixed(lat, lon, ground + mast)
            el = frames.elevation_angle_deg(P_obs, up, P)
            el = np.where(valid, el, np.nan)
            el_masked = np.where(np.arange(d.size)[None, :] < first_gap[:, None], el, np.nan)
            any_valid = np.isfinite(el_masked).any(axis=1)
            k = np.where(any_valid, np.nanargmax(np.where(np.isfinite(el_masked), el_masked, -1e9), axis=1), -1)
            out_el, status = [], []
            for i in range(bins):
                if not any_valid[i]:
                    out_el.append(None); status.append('truncated'); continue
                out_el.append(round(float(el_masked[i, k[i]]), 5))
                status.append('complete' if first_gap[i] == d.size else 'truncated')
            out[(t_id, float(mast))] = {'bins': bins, 'elevation_deg': out_el, 'status': status,
                                        'n_truncated': int(sum(s_ == 'truncated' for s_ in status)),
                                        'max_range_m': float(max_range), 'near_cut_m': float(near_cut),
                                        'step_near_m': float(step_near), 'step_far_m': float(step_far),
                                        'ground_m': ground, 'lat': lat, 'lon': lon, 'solver': 'multi_skyline'}
    return out


def run_position(args):
    """Worker: all T maps at one position offset. args = (site, dx, dy) -> 10 masts at the centre, 1 m
    elsewhere; or (site, dx, dy, masts) with an explicit mast tuple."""
    site, dx, dy = args[:3]
    masts = args[3] if len(args) > 3 else (MASTS if (dx, dy) == (0, 0) else (1.0,))
    todo = {t: [m for m in masts if not (SKY / f'{sky_key(site, t, m, dx, dy)}.json').exists()] for t in T_IDS}
    todo = {t: ms for t, ms in todo.items() if ms}
    if not todo:
        return site, dx, dy, 0
    near = {t: sites.near_dem(site, clone=_clone_of(t)) for t in todo}
    far = sites.far_dem(site)
    if (dx, dy) == (0, 0):
        s = sites.SITES[site]; lat, lon = s['lat'], s['lon']
    else:
        lat, lon = offset_latlon(site, dx, dy)
    res = multi_skyline(lat, lon, near, far, todo)
    SKY.mkdir(parents=True, exist_ok=True)
    for (t, m), sky in res.items():
        (SKY / f'{sky_key(site, t, m, dx, dy)}.json').write_text(json.dumps(sky))
    return site, dx, dy, len(res)


def grid_offsets(half_m, step_m):
    r = range(-int(half_m), int(half_m) + 1, int(step_m))
    return tuple((dx, dy) for dx in r for dy in r)


def _num(v):
    f = float(v)
    return int(f) if f.is_integer() else f


if __name__ == '__main__':
    import argparse
    import os
    from multiprocessing import Pool
    ap = argparse.ArgumentParser()
    ap.add_argument('sites', nargs='*', default=['site04_roi3', 'site01_roi6'])
    ap.add_argument('--grid', nargs=2, type=float, metavar=('HALF_M', 'STEP_M'), help='square offset grid at 1 m mast')
    ap.add_argument('--points', help='"dx,dy,mast[,mast...];..." explicit offsets (m) and masts')
    a = ap.parse_args()
    if a.grid:
        jobs = [(s, dx, dy, (1.0,)) for s in a.sites for dx, dy in grid_offsets(*a.grid)]
    elif a.points:
        pts = [p.split(',') for p in a.points.split(';') if p.strip()]
        jobs = [(s, _num(p[0]), _num(p[1]), tuple(float(m) for m in p[2:]) or (1.0,)) for s in a.sites for p in pts]
    else:
        jobs = [(s, 0, 0) for s in a.sites] + [(s, dx, dy) for s in a.sites for dx, dy in OFFSETS if (dx, dy) != (0, 0)]
    with Pool(int(os.environ.get('CUBE_WORKERS', '6'))) as pool:
        for r in pool.imap_unordered(run_position, jobs):
            print('done', *r, flush=True)
