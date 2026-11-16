"""Global Earth-visibility and polar Sun-visibility fraction maps (prompt §2.5, R2 plan §4). DISPLAY-ONLY analytics,
SOURCE-BASED · UNVALIDATED: terrain-horizon geometry only (no link budget, no power, no DSN schedule).

Geometry: JPL Horizons sub-Earth and sub-solar points on the Moon (MOON_ME, 1737.4 km sphere) every 3 h over
2026-01-01 .. 2044-08-01 (18.58 years, ~one 18.61-year nodal cycle), `tools.globe.ephem` (checked against Horizons coord@301 az/el:
Earth < 0.001 deg, Sun < 1e-5 deg). Libration-aware by construction: the Earth's direction from each point follows the
sub-Earth point (+-6.9 deg lat, +-8.1 deg lon) and the Earth-Moon distance (topocentric parallax included).

Visible = any part of the disc above the terrain horizon (el_centre + angular radius > horizon at that azimuth), the
PGDA 69 definition (Mazarico et al. 2011: "sunlit by any fraction of the solar disc"); the disc-centre fraction is kept
too. Observer on the DEM surface (0 m mast).

Horizon: rays along exact great circles (destination formula on the 1737.4 km sphere) with Earth-free curvature
(el = atan2(r_t cos g - r_o, r_t sin g)), terrain from the science pyramid (never VISUAL):
  * poles (1 km grids, polar stereographic): 80 m level to NEAR_M, 320 m level beyond, to 300 km;
    Earth maps poleward of 80 deg, Sun maps poleward of 85 deg (360 deg horizons, 2 deg bins);
  * global Earth map 0.125 deg: a 16 ppd (~1.9 km) mosaic of the pyramid's coarsest levels, rays to 300 km, only over
    the azimuth range the Earth visits from that cell. Cells whose Earth elevation is always >= CAP_DEG are set visible
    (horizons above CAP_DEG are not resolved at 1.9 km; checked on a sample) and cells whose Earth elevation is always
    below -DIP_DEG are set 0 (no terrain can lower the horizon that far). Obstructions narrower than ~4 km are missed.

    python -m tools.globe.visibility polar-sun --pole sp
    python -m tools.globe.visibility polar-earth --pole sp
    python -m tools.globe.visibility global-earth [--cell 0.125]
    python -m tools.globe.visibility compare        # vs PGDA 69 (85-90 S) -> PYRAMID_QA.json "analytics_r2"
Outputs: $POLARIS_DATA/v2/analytics/*.npz, web/public/globe/analytics/*.png (git-ignored), legend JSON.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

from science.terrain import stack as S
from tools.globe import ephem as EP
from tools.globe import pyramid_products as PP

LABEL = 'SOURCE-BASED · UNVALIDATED (display-only analytics: terrain-horizon geometry, not link or power availability)'
REPO = Path(__file__).resolve().parents[2]
OUT = REPO / 'web' / 'public' / 'globe' / 'analytics'
R = S.R
R_EARTH_M = 6_371_000.0
NEAR_M = 20_000.0
MAX_M = 300_000.0
CAP_DEG = 40.0
DIP_DEG = 7.0                  # max horizon dip: sqrt(2 dh / R) for dh = 13 km of relief is 7.0 deg
TIME_STRIDE = 2                # 6 h samples (27k over 18.6 y)


def cache_dir():
    d = PP.polaris_data() / 'v2' / 'analytics'
    d.mkdir(parents=True, exist_ok=True)
    return d


# ------------------------------------------------------------------------------------------ terrain mosaics
def zone_mosaic(stack, zone, L, half_m):
    """Heights of a polar zone level on the square [-half_m, half_m]^2 (grid metres), NaN where no tile."""
    Z = S.ZONES[zone]
    p = Z.pixel(L); T = Z.tile_px
    c0 = int(math.floor((-half_m - Z.left) / p)); c1 = int(math.ceil((half_m - Z.left) / p))
    c0 -= c0 % T; c1 += (-c1) % T
    out = np.full((c1 - c0, c1 - c0), np.nan, np.float32)        # square, symmetric about the pole
    r0 = c0                                                          # top == -left for polar zones
    for iy in range(r0 // T, c1 // T):
        for ix in range(c0 // T, c1 // T):
            if stack.has_tile(zone, L, ix, iy):
                a = stack._load(zone, L, ix, iy)[0]
                out[iy * T - r0:(iy + 1) * T - r0, ix * T - c0:(ix + 1) * T - c0] = a
    return out, Z.left + c0 * p, Z.top - r0 * p, p


class PolarDEM:
    def __init__(self, stack, zone, reach_m, near_level=4, far_level=2):
        self.Z = S.ZONES[zone]
        self.near = zone_mosaic(stack, zone, near_level, reach_m + NEAR_M + 2000)
        self.far = zone_mosaic(stack, zone, far_level, reach_m + MAX_M + 5000)

    @staticmethod
    def _at(m, x, y):
        from scipy import ndimage
        a, left, top, p = m
        return ndimage.map_coordinates(a, [(top - y) / p - 0.5, (x - left) / p - 0.5], order=1, mode='constant',
                                       cval=np.nan, prefilter=False)

    def sample(self, lat, lon, near):
        x, y = self.Z.forward(lat, lon)
        if near:
            h = self._at(self.near, x, y)
            bad = ~np.isfinite(h)
            if bad.any():
                h[bad] = self._at(self.far, x[bad], y[bad])
            return h
        return self._at(self.far, x, y)


class GlobalDEM:
    """16 ppd lat/lon mosaic of the pyramid (eq level 0 = 32 ppd, polar level 0 = 1280 m, sampled bilinearly)."""

    def __init__(self, stack, ppd=16):
        self.ppd = ppd
        cache = cache_dir() / f'global_dem_{ppd}ppd.npy'
        if cache.exists():
            self.H = np.load(cache)
        else:
            lat = 90.0 - (np.arange(180 * ppd) + 0.5) / ppd
            lon = -180.0 + (np.arange(360 * ppd) + 0.5) / ppd
            H = np.empty((lat.size, lon.size), np.float32)
            for i in range(0, lat.size, 90):
                La, Lo = np.meshgrid(lat[i:i + 90], lon, indexing='ij')
                H[i:i + 90] = stack._query(La, Lo, levels=[0])['height']
            np.save(cache, H)
            self.H = H
        W = 4
        self.P = np.concatenate([self.H[:, -W:], self.H, self.H[:, :W]], 1)
        self.W = W

    def sample(self, lat, lon, near=False):
        from scipy import ndimage
        r = (90.0 - lat) * self.ppd - 0.5
        c = (np.mod(lon + 180.0, 360.0)) * self.ppd - 0.5 + self.W
        return ndimage.map_coordinates(self.P, [r, c], order=1, mode='nearest', prefilter=False)


# ------------------------------------------------------------------------------------------ horizon
def distances(near_step, far_step, ratio=1.02):
    d = list(np.arange(1.5 * near_step, NEAR_M, near_step))
    x = NEAR_M
    while x < 60_000.0:
        d.append(x); x += far_step
    while x <= MAX_M:
        d.append(x); x *= ratio
    return np.array(d)


def horizon(dem, lat, lon, h0, az, dists):
    """Max terrain elevation angle (deg) from (lat, lon, h0) along azimuths az (N, K) (deg from north, east positive)
    at great-circle distances dists (m)."""
    la = np.radians(lat)[:, None]; lo = np.radians(lon)[:, None]
    sla, cla = np.sin(la), np.cos(la)
    a = np.radians(az); sa, ca = np.sin(a), np.cos(a)
    ro = (R + h0)[:, None]
    best = np.full(az.shape, -90.0)
    for d in dists:
        g = d / R
        sg, cg = math.sin(g), math.cos(g)
        sl2 = np.clip(sla * cg + cla * sg * ca, -1, 1)
        la2 = np.arcsin(sl2)
        lo2 = lo + np.arctan2(sa * sg * cla, cg - sla * sl2)
        h = dem.sample(np.degrees(la2), np.degrees(lo2), d <= NEAR_M)
        rt = R + h
        el = np.degrees(np.arctan2(rt * cg - ro, rt * sg))
        best = np.fmax(best, el)
    return best


# ------------------------------------------------------------------------------------------ visibility
def body_samples(kind, stride=TIME_STRIDE, bin_deg=None):
    """Unit vectors (T, 3) of the body's direction from the Moon's centre, distance (T,) m, weights (T,)."""
    g = EP.geometry()
    if kind == 'sun':
        la, lo, d = g['ss_lat'][::stride], g['ss_lon'][::stride], g['r_m'][::stride]
    else:
        la, lo, d = g['se_lat'][::stride], g['se_lon'][::stride], g['d_m'][::stride]
    if bin_deg:
        kl = np.round(la / bin_deg).astype(int); ko = np.round(lo / bin_deg).astype(int)
        key = kl * 100000 + ko
        u, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
        la = np.bincount(inv, la) / cnt; lo = np.bincount(inv, lo) / cnt; d = np.bincount(inv, d) / cnt
        w = cnt / cnt.sum()
    else:
        w = np.full(la.size, 1.0 / la.size)
    return EP.unit(la, lo), d, w


def az_el(lat, lon, h0, U, d, kind):
    """Topocentric az/el (deg) and disc angular radius (deg) of samples (U, d) from points: (N, T) arrays."""
    e, n, u = EP.enu(lat, lon)
    ue, un, uu = e @ U.T, n @ U.T, u @ U.T
    if kind == 'sun':
        ve, vn, vu = ue, un, uu
        rad = np.degrees(np.arcsin(EP.R_SUN_M / d))[None, :]
    else:
        ve, vn, vu = d * ue, d * un, d * uu - (R + h0)[:, None]
        dist = np.sqrt(ve * ve + vn * vn + vu * vu)
        rad = np.degrees(np.arcsin(R_EARTH_M / dist))
    az = np.degrees(np.arctan2(ve, vn)) % 360.0
    el = np.degrees(np.arctan2(vu, np.hypot(ve, vn)))
    return az, el, rad


def _interp_periodic(hz, az, az0, step):
    """Horizon hz (N, K) sampled at az0 + k step (deg, K covers 360) evaluated at az (N, T)."""
    K = hz.shape[1]
    x = ((az - az0) % 360.0) / step
    i0 = np.floor(x).astype(np.int64) % K; f = x - np.floor(x)
    rows = np.arange(hz.shape[0])[:, None]
    return hz[rows, i0] * (1 - f) + hz[rows, (i0 + 1) % K] * f


def _interp_window(hz, az, azc, W):
    """Horizon hz (N, K) sampled uniformly on [azc - W, azc + W] evaluated at az (N, T) (clamped)."""
    K = hz.shape[1]
    rel = (az - azc[:, None] + 180.0) % 360.0 - 180.0
    x = np.clip((rel + W[:, None]) / (2 * W[:, None]) * (K - 1), 0, K - 1)
    i0 = np.minimum(np.floor(x).astype(np.int64), K - 2); f = x - i0
    rows = np.arange(hz.shape[0])[:, None]
    return hz[rows, i0] * (1 - f) + hz[rows, i0 + 1] * f


def fraction_full(dem, lat, lon, h0, kind, dists, n_az=180, chunk=400, samples=None, log=None):
    """Fraction of samples with any part / the centre of the disc above a full 360-degree horizon (n_az bins)."""
    U, d, w = samples or body_samples(kind)
    step = 360.0 / n_az
    az_k = np.arange(n_az) * step
    any_f = np.empty(lat.size); ctr_f = np.empty(lat.size); hmax = np.empty(lat.size)
    t0 = time.time()
    for i in range(0, lat.size, chunk):
        s = slice(i, i + chunk)
        hz = horizon(dem, lat[s], lon[s], h0[s], np.broadcast_to(az_k, (lat[s].size, n_az)), dists)
        az, el, rad = az_el(lat[s], lon[s], h0[s], U, d, kind)
        h = _interp_periodic(hz, az, 0.0, step)
        any_f[s] = ((el + rad) > h) @ w
        ctr_f[s] = (el > h) @ w
        hmax[s] = np.nanmax(hz, axis=1)
        if log and (i // chunk) % 20 == 0:
            log(f'  {kind} {i + chunk}/{lat.size} points, {time.time() - t0:.0f} s')
    return any_f, ctr_f, hmax


def fraction_window(dem, lat, lon, h0, kind, dists, n_az=24, chunk=400, samples=None, log=None):
    """Same, horizon only over the azimuth range the body visits from each point (Earth)."""
    U, d, w = samples or body_samples(kind)
    any_f = np.empty(lat.size); ctr_f = np.empty(lat.size); hmax = np.empty(lat.size)
    t0 = time.time()
    for i in range(0, lat.size, chunk):
        s = slice(i, i + chunk)
        az, el, rad = az_el(lat[s], lon[s], h0[s], U, d, kind)
        c = np.exp(1j * np.radians(az)) @ w
        azc = np.degrees(np.angle(c)) % 360.0
        rel = (az - azc[:, None] + 180.0) % 360.0 - 180.0
        W = np.clip(np.abs(rel).max(axis=1) + 1.0, 2.0, 180.0)
        k = np.linspace(-1, 1, n_az)
        azs = (azc[:, None] + W[:, None] * k[None, :]) % 360.0
        hz = horizon(dem, lat[s], lon[s], h0[s], azs, dists)
        h = _interp_window(hz, az, azc, W)
        any_f[s] = ((el + rad) > h) @ w
        ctr_f[s] = (el > h) @ w
        hmax[s] = np.nanmax(hz, axis=1)
        if log and (i // chunk) % 50 == 0:
            log(f'  {kind} {i + chunk}/{lat.size} points, {time.time() - t0:.0f} s')
    return any_f, ctr_f, hmax


# ------------------------------------------------------------------------------------------ products
def polar_grid(zone, lat_min_abs, cell_m=1000.0):
    rho = 2 * R * math.tan(math.pi / 4 - math.radians(lat_min_abs) / 2)
    n = int(math.ceil(rho / cell_m))
    c = (np.arange(-n, n) + 0.5) * cell_m
    X, Y = np.meshgrid(c, -c)
    lat, lon = S.ZONES[zone].inverse(X, Y)
    return X, Y, lat, lon, np.hypot(X, Y) <= rho


def run_polar(kind, zone, cell_m=1000.0, workers=1, log=print):
    stack = S.TerrainStack.open()
    lat_min = 85.0 if kind == 'sun' else 80.0
    X, Y, lat, lon, inside = polar_grid(zone, lat_min, cell_m)
    reach = float(np.hypot(X, Y)[inside].max())
    t0 = time.time()
    dem = PolarDEM(stack, zone, reach)
    log(f'polar {kind} {zone}: {inside.sum()} points, mosaics in {time.time() - t0:.0f} s')
    la, lo = lat[inside], lon[inside]
    h0 = dem.sample(la, lo, True)
    dists = distances(80.0, 320.0)
    if kind == 'sun':
        f_any, f_ctr, hmax = fraction_full(dem, la, lo, h0, 'sun', dists, log=log)
    else:
        f_any, f_ctr, hmax = fraction_window(dem, la, lo, h0, 'earth', dists, n_az=32, log=log)
    out = {}
    for k, v in (('any', f_any), ('centre', f_ctr), ('hmax', hmax), ('h0', h0)):
        a = np.full(lat.shape, np.nan); a[inside] = v; out[k] = a
    np.savez(cache_dir() / f'{kind}_{zone}_{int(cell_m)}m.npz', x=X[0], y=Y[:, 0], **out,
             meta=json.dumps({'kind': kind, 'zone': zone, 'cell_m': cell_m, 'lat_min_abs': lat_min,
                              'n_dist': int(dists.size), 'time_stride': TIME_STRIDE, 'label': LABEL}))
    log(f'polar {kind} {zone}: done in {time.time() - t0:.0f} s; median any {np.nanmedian(f_any):.3f}')
    write_polar_png(kind, zone, out['any'], cell_m)
    return out


def run_global_earth(cell_deg=0.125, log=print, limit=None):
    stack = S.TerrainStack.open()
    t0 = time.time()
    dem = GlobalDEM(stack)
    log(f'global DEM ready in {time.time() - t0:.0f} s')
    ny, nx = int(180 / cell_deg), int(360 / cell_deg)
    lat = 90.0 - (np.arange(ny) + 0.5) * cell_deg; lon = -180.0 + (np.arange(nx) + 0.5) * cell_deg
    LA, LO = np.meshgrid(lat, lon, indexing='ij')
    U, d, w = body_samples('earth', stride=1, bin_deg=0.25)
    # bounds on the Earth's elevation: every sub-Earth sample lies within Lmax of (0, 0)
    Lmax = float(np.degrees(np.arccos(np.clip(U[:, 0], -1, 1))).max())
    th0 = np.degrees(np.arccos(np.clip(np.cos(np.radians(LA)) * np.cos(np.radians(LO)), -1, 1))).ravel()
    th_min, th_max = th0 - Lmax, th0 + Lmax
    par = 0.3; rad = 1.0
    always = (90.0 - th_max - par - rad) >= CAP_DEG
    never = (90.0 - th_min + par + rad) < -DIP_DEG
    belt = ~always & ~never
    idx = np.flatnonzero(belt)
    if limit:
        idx = idx[:: max(1, idx.size // limit)]
    log(f'global earth: {belt.sum()} belt cells of {belt.size} ({len(U)} Earth direction bins); computing {idx.size}')
    la, lo = LA.ravel()[idx], LO.ravel()[idx]
    h0 = dem.sample(la, lo)
    dists = distances(1900.0, 1900.0, ratio=1.03)
    f_any, f_ctr, hmax = fraction_window(dem, la, lo, h0, 'earth', dists, n_az=24, chunk=2000, samples=(U, d, w),
                                         log=log)
    A = np.where(always, 1.0, np.where(never, 0.0, np.nan)).astype(np.float64)
    C = A.copy(); HM = np.full(A.shape, np.nan)
    A[idx] = f_any; C[idx] = f_ctr; HM[idx] = hmax
    A = A.reshape(ny, nx); C = C.reshape(ny, nx); HM = HM.reshape(ny, nx)
    # check the CAP assumption on a sample of 'always' cells
    rng = np.random.default_rng(0)
    al = np.flatnonzero(always)
    chk = rng.choice(al, size=min(4000, al.size), replace=False)
    lac, loc = LA.ravel()[chk], LO.ravel()[chk]
    _, _, hm_chk = fraction_window(dem, lac, loc, dem.sample(lac, loc), 'earth', dists, n_az=24, chunk=2000,
                                   samples=(U, d, w))
    meta = {'cell_deg': cell_deg, 'cap_deg': CAP_DEG, 'dip_deg': DIP_DEG, 'n_earth_bins': int(len(U)),
            'belt_cells': int(belt.sum()), 'computed_cells': int(idx.size),
            'cap_check': {'n': int(chk.size), 'max_horizon_deg_toward_earth': float(np.nanmax(hm_chk)),
                          'p999_deg': float(np.nanpercentile(hm_chk, 99.9))}, 'label': LABEL}
    np.savez(cache_dir() / f'earth_global_{cell_deg}.npz', any=A, centre=C, hmax=HM, meta=json.dumps(meta))
    log(f'global earth done in {time.time() - t0:.0f} s; cap check {meta["cap_check"]}')
    write_global_png(A, cell_deg)
    return A, C, meta


# ------------------------------------------------------------------------------------------ PNG output
def _ramp(v):
    """Dark (0) -> light (1) sequential ramp, NaN transparent."""
    stops = np.array([[13, 8, 135], [84, 2, 163], [139, 10, 165], [185, 50, 137], [219, 92, 104], [244, 136, 73],
                      [254, 188, 43], [240, 249, 33]], float)
    t = np.clip(np.nan_to_num(v), 0, 1) * (len(stops) - 1)
    i = np.clip(np.floor(t).astype(int), 0, len(stops) - 2); f = (t - i)[..., None]
    rgb = stops[i] * (1 - f) + stops[i + 1] * f
    a = np.where(np.isfinite(v), 255, 0)[..., None]
    return np.concatenate([rgb, a], -1).astype(np.uint8)


def write_polar_png(kind, zone, frac, cell_m):
    from tools.globe.seams import write_png
    write_png(OUT / f'{kind}_visibility_{zone}_{int(cell_m)}m.png', _ramp(frac))
    _legend()


def write_global_png(frac, cell_deg):
    from tools.globe.seams import write_png
    write_png(OUT / 'earth_visibility_eqc.png', _ramp(frac))
    _legend()


def _legend():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'visibility_legend.json').write_text(json.dumps({
        'label': LABEL,
        'value': 'fraction of 6-h (polar) / 3-h binned (global) samples, 2026-01-01..2044-08-01, with any part of the '
                 'disc above the terrain horizon; colour ramp dark (0) -> light (1)',
        'earth_visibility_eqc.png': 'global, equirectangular 0.125 deg, lon -180..180 left->right, lat 90..-90 top->bottom',
        '<kind>_visibility_<sp|np>_1000m.png': 'polar stereographic 1 km, +x toward 90 E (sp: +y toward 0 E; np: -y '
                                               'toward 0 E), centred on the pole, row 0 = +y edge',
        'method': __doc__.strip().split('\n\n')[2]}, indent=1))


# ------------------------------------------------------------------------------------------ PGDA 69 comparison
def compare_pgda69(log=print):
    import rasterio
    d = PP.polaris_data() / 'v2' / 'products' / 'pgda69'
    res = {}
    for kind, fname in (('sun', 'AVGVISIB_85S_060M_201608.TIF'), ('earth', 'AVGVISIB_85S_060M_201608_EARTH.TIF')):
        f = cache_dir() / f'{kind}_sp_1000m.npz'
        if not f.exists():
            continue
        z = np.load(f)
        X, Y = np.meshgrid(z['x'], z['y'])
        mine = z['any']
        with rasterio.open(d / fname) as ds:
            a = ds.read(1).astype(np.float64)
            nod = ds.nodata
            a = np.where(a == nod, np.nan, a * ds.scales[0] + ds.offsets[0])
            col, row = ~ds.transform * (X, Y)
        from scipy import ndimage
        # PGDA 69 averaged over the 1 km cell (block mean of 60 m pixels ~ 17 x 17) and at the cell centre
        k = 17
        am = ndimage.uniform_filter(np.nan_to_num(a), k) / np.maximum(ndimage.uniform_filter(np.isfinite(a) * 1.0, k), 1e-9)
        ref_c = ndimage.map_coordinates(a, [row - 0.5, col - 0.5], order=0, mode='constant', cval=np.nan)
        ref_m = ndimage.map_coordinates(am, [row - 0.5, col - 0.5], order=1, mode='constant', cval=np.nan)
        lat = S.ZONES['sp'].inverse(X, Y)[0]
        ok = np.isfinite(mine) & np.isfinite(ref_m) & (lat <= -85.0)
        dd = mine[ok] - ref_m[ok]; dc = mine[ok] - ref_c[ok]
        res[kind] = {'n_points': int(ok.sum()), 'pgda69': fname, 'definition_both': 'any part of the disc',
                     'mine_minus_pgda69_cellmean': {'median': round(float(np.median(dd)), 4),
                                                    'median_abs': round(float(np.median(np.abs(dd))), 4),
                                                    'p90_abs': round(float(np.percentile(np.abs(dd), 90)), 4),
                                                    'rms': round(float(np.sqrt(np.mean(dd ** 2))), 4)},
                     'mine_minus_pgda69_centre_pixel': {'median_abs': round(float(np.median(np.abs(dc))), 4),
                                                        'p90_abs': round(float(np.percentile(np.abs(dc), 90)), 4)},
                     'pearson_r_cellmean': round(float(np.corrcoef(mine[ok], ref_m[ok])[0, 1]), 4),
                     'mean_mine': round(float(np.mean(mine[ok])), 4), 'mean_pgda69': round(float(np.mean(ref_m[ok])), 4),
                     'pct_points_never_visible_mine': round(float(100 * np.mean(mine[ok] == 0)), 3),
                     'pct_points_never_visible_pgda69_centre': round(float(100 * np.mean(ref_c[ok] == 0)), 3)}
        log(f'{kind}: {res[kind]}')
    return res


def write_qa(extra=None, log=print):
    from tools.globe.seams import update_qa_doc
    out = {'created_utc': _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'label': LABEL,
           'method': __doc__.strip().split('\n\n')[1:4], 'ephemeris_check': EP.check(),
           'pgda69_comparison_85_90S': compare_pgda69(log=log)}
    for kind, zone in (('sun', 'sp'), ('sun', 'np'), ('earth', 'sp'), ('earth', 'np')):
        f = cache_dir() / f'{kind}_{zone}_1000m.npz'
        if f.exists():
            z = np.load(f)
            a = z['any'][np.isfinite(z['any'])]
            out[f'{kind}_{zone}_1km'] = {'n_points': int(a.size), 'median': round(float(np.median(a)), 4),
                                         'pct_never': round(float(100 * np.mean(a == 0)), 3),
                                         'pct_always': round(float(100 * np.mean(a == 1)), 3),
                                         'max': round(float(a.max()), 4), **json.loads(str(z['meta']))}
    f = cache_dir() / 'earth_global_0.125.npz'
    if f.exists():
        z = np.load(f)
        A = z['any']
        lat = 90.0 - (np.arange(A.shape[0]) + 0.5) * 0.125
        w = np.cos(np.radians(lat))[:, None] * np.ones_like(A)
        ok = np.isfinite(A)
        out['earth_global_0.125deg'] = {
            'area_pct_always_visible': round(float(100 * (w * (A == 1))[ok].sum() / w[ok].sum()), 3),
            'area_pct_never_visible': round(float(100 * (w * (A == 0))[ok].sum() / w[ok].sum()), 3),
            'area_pct_sometimes': round(float(100 * (w * ((A > 0) & (A < 1)))[ok].sum() / w[ok].sum()), 3),
            'area_weighted_mean_fraction': round(float((w * A)[ok].sum() / w[ok].sum()), 4),
            **json.loads(str(z['meta']))}
    if extra:
        out.update(extra)
    update_qa_doc('analytics_r2', out)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.globe.visibility')
    ap.add_argument('cmd', choices=['polar-sun', 'polar-earth', 'global-earth', 'compare', 'qa'])
    ap.add_argument('--pole', default='sp'); ap.add_argument('--cell', type=float, default=0.125)
    ap.add_argument('--limit', type=int, default=None); ap.add_argument('--cell-m', type=float, default=1000.0)
    a = ap.parse_args(argv)
    if a.cmd == 'polar-sun':
        run_polar('sun', a.pole, cell_m=a.cell_m)
    elif a.cmd == 'polar-earth':
        run_polar('earth', a.pole, cell_m=a.cell_m)
    elif a.cmd == 'global-earth':
        run_global_earth(a.cell, limit=a.limit)
    elif a.cmd == 'compare':
        print(json.dumps(compare_pgda69(), indent=1))
    else:
        print(json.dumps(write_qa(), indent=1)[:3000])
    return 0


if __name__ == '__main__':
    sys.exit(main())
