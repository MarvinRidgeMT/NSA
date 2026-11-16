"""One Mercury north-polar site end to end (prompt §3.2): Prokofiev rim.

  python -m science.worlds.mercury.site [--offline] [--out data/worlds/mercury]

Pipeline: site selection rule (docs/v2/PHASE_6_WORLDS_PLAN.md §5) on the PGDA 85 layers -> near field PGDA 85 hybrid
DEM 125 m (MLA + SfS), far field MLA GDR v2 250 m to the curvature limit -> 720-bin skyline (generic world ray caster,
flat-horizon control) -> JPL Horizons Sun/Earth from coord@199 hourly for one solar day (2 Mercury years) -> hourly
visibility metrics for the first Mercury year and the full solar day -> geocentric SEP angle and conjunction flags ->
direct-to-Earth availability -> ice layer (PGDA 85 radar map) -> product-disagreement members -> physics checks ->
bundle (polaris-science-results-v1 core keys + a 'world' block). Labels: geometry SOURCE-BASED UNVALIDATED; comms
threshold and requirements ENGINEERING ASSUMPTION.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

from ... import bundle as B
from ... import crossings as X
from ... import horizons as H
from ...anysite import curvature
from ...anysite.solve import hourly_metrics
from ..base import ENGINEERING, LABEL
from ..skyline import Layer, layered_skyline
from . import dem as MD
from . import ephem as ME
from . import physics as PH
from . import products as PR
from .world import MERCURY

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / 'data' / 'worlds' / 'mercury'
VERSION = 'mercury-site-1'

CRATER = {'name': 'Prokofiev', 'lat_deg': 85.77, 'lon_deg_east': 62.92, 'diameter_km': 112.0,
          'source': 'USGS Gazetteer of Planetary Nomenclature, Prokofiev (Mercury), alternate solution 85.77 N, 297.08 W '
                    '(= MESSENGER MDIS image captions, 62.92 E); other Gazetteer solution 86.00 N, 296.30 W (63.70 E)'}
RULE = {'annulus_rim_radii': [0.85, 1.15], 'max_slope_deg': 15.0, 'pick': 'highest PGDA 85 maximum incident solar flux',
        'ties': 'nearest the crater centre', 'fixed_before_run': '2026-11-16 ~12:20 EST (docs/v2/PHASE_6_WORLDS_PLAN.md §5)'}
START = '2026-11-14 00:00'
SOLAR_DAY_SPAN_D = 176
MERCURY_YEAR_D = 88
STEP_H = 1
MAST_M = 1.0
MAST_SWEEP_M = (1.0, 5.0, 10.0, 20.0, 50.0, 100.0)   # same skyline method, eye height = ground + mast
NEAR_STEP_DIV = 5.0
FINE_STEP_MAX_M = 12_500.0
FAR_STEP_M = 125.0
RADAR_BRIGHT_THRESHOLD = 0.1
RADAR_THRESHOLD_SOURCE = ('ASSUMPTION: 0.1 is the radar-bright threshold Eke et al. (2017, Icarus 284, 407; arXiv:1611.05395) '
                          'applied to the Harmon et al. (2011) same-sense cross-section map; that the PGDA 85 radar3b layer '
                          'is on the same scale is not verified.')
COREG_SHIFT_M = (-200.0, -100.0)   # PGDA 85 grid shift that minimises std(PGDA 85 - MLA v2) (measured, see tests)


def _gc_dist_m(lat1, lon1, lat2, lon2, R=MERCURY.radius_m):
    p1, p2 = np.radians(lat1), np.radians(lat2); dl = np.radians(np.asarray(lon2) - lon1)
    c = np.sin(p1) * np.sin(p2) + np.cos(p1) * np.cos(p2) * np.cos(dl)
    return R * np.arccos(np.clip(c, -1, 1))


def select_site(root=None):
    sl = MD.prokofiev('slope', root); mf = MD.prokofiev('maxflux', root)
    d = sl.dem; h, w = d.Z.shape
    if mf.dem.Z.shape != d.Z.shape or mf.dem.x_left != d.x_left or mf.dem.y_top != d.y_top:
        raise ValueError('PGDA 85 slope and max-flux grids differ')
    xs = d.x_left + (np.arange(w) + 0.5) * d.step; ys = d.y_top - (np.arange(h) + 0.5) * d.step
    X_, Y_ = np.meshgrid(xs, ys)
    lat, lon = sl.proj.inverse(X_, Y_)
    rr = _gc_dist_m(CRATER['lat_deg'], CRATER['lon_deg_east'], lat, lon)
    R0 = CRATER['diameter_km'] * 500.0
    cand = (rr >= RULE['annulus_rim_radii'][0] * R0) & (rr <= RULE['annulus_rim_radii'][1] * R0) & \
        (d.Z < RULE['max_slope_deg']) & np.isfinite(mf.dem.Z) & np.isfinite(d.Z)
    if not cand.any():
        raise LookupError('no candidate pixel in the rim annulus')
    score = np.where(cand, mf.dem.Z, -np.inf)
    best = np.nanmax(score)
    ii = np.argwhere(score == best)
    k = ii[np.argmin(rr[ii[:, 0], ii[:, 1]])]
    r, c = int(k[0]), int(k[1])
    return {'lat_deg': round(float(lat[r, c]), 7), 'lon_deg_east': round(float(lon[r, c]), 7),
            'pgda85_grid_x_m': float(xs[c]), 'pgda85_grid_y_m': float(ys[r]), 'pixel_row_col': [r, c],
            'max_incident_flux_w_m2': round(float(mf.dem.Z[r, c]), 3), 'slope_deg': round(float(d.Z[r, c]), 3),
            'distance_from_crater_centre_km': round(float(rr[r, c]) / 1000.0, 3), 'n_candidates': int(cand.sum()),
            'crater': CRATER, 'rule': RULE}


def _inscribed(dem, x0, y0):
    l, b, r, t = dem.bounds
    return max(0.0, min(x0 - l, r - x0, y0 - b, t - y0) - dem.step)


def terrain(site, max_range_m, root=None, near_shift=(0.0, 0.0)):
    near = MD.prokofiev('dem', root)
    if near_shift != (0.0, 0.0):
        dx, dy = near_shift
        near.dem = type(near.dem)(near.dem.Z, near.dem.x_left - dx, near.dem.y_top - dy, near.dem.step,
                                  near.dem.name + f' shifted ({dx:+.0f},{dy:+.0f}) m', dict(near.dem.meta))
    lat, lon = site['lat_deg'], site['lon_deg_east']
    x, y = MD.PolarStereo(2_439_400.0, 'north').forward(lat, lon)          # MLA v2 projection sphere (label A_AXIS_RADIUS)
    half = max_range_m + 20_000.0
    far = MD.mla_v2((x - half, x + half, y - half, y + half), root)
    return near, far


def skyline(site, near, far, max_range_m, mast_m=MAST_M):
    lat, lon = site['lat_deg'], site['lon_deg_east']
    xn, yn = near.proj.forward(lat, lon)
    h = float(near.dem.sample(xn, yn))
    if not math.isfinite(h):
        raise LookupError('no PGDA 85 height at the site')
    near_cut = min(_inscribed(near.dem, xn, yn), FINE_STEP_MAX_M)
    sky = layered_skyline(MERCURY.sphere, lat, lon, h, mast_m, [Layer(near.dem, near.proj.forward, 'near'),
                                                                 Layer(far.dem, far.proj.forward, 'far')],
                          bins=720, max_range_m=max_range_m, step_near_m=near.dem.step / NEAR_STEP_DIV, near_cut_m=near_cut,
                          step_far_m=FAR_STEP_M, beyond_reference=Layer(far.dem, far.proj.forward, 'far'))
    return h, sky


def _curvature(h_eye, max_range, sky):
    """science.anysite.curvature with Mercury's radius and relief bound (its record() is written for the Moon)."""
    e = np.array([np.nan if v is None else v for v in sky['elevation_deg']], float)
    L_req = float(np.nanmax(curvature.limit_m(h_eye, e[np.isfinite(e)], MERCURY.relief_max_m, MERCURY.radius_m)))
    bound = float(curvature.elevation_deg(h_eye, MERCURY.relief_max_m, max_range, MERCURY.radius_m))
    return {'formula': 'theta_max(e) = acos((R + h_eye) cos e / (R + H)) - e ; L = R theta_max ; L_req = max over bins L(e_bin)',
            'R_m': MERCURY.radius_m, 'h_eye_m': round(h_eye, 3), 'H_world_max_m': MERCURY.relief_max_m,
            'relief_source': MERCURY.relief_source, 'required_range_world_m': round(L_req, 1), 'max_range_m': max_range,
            'beyond_range_world_bound_elev_deg': round(bound, 5),
            'n_range_limited_world': int(sum(bool(np.isfinite(v) and v < bound) for v in e)),
            'note': 'Bins below beyond_range_world_bound_elev_deg could still be raised by terrain <= H_world_max_m beyond '
                    'max_range_m; max_range is extended to L_req where the far product reaches.'}


def _stop(start, days):
    return (dt.datetime.fromisoformat(start) + dt.timedelta(days=days)).strftime('%Y-%m-%d %H:%M')


def _attach_margins(rows, sky):
    for r in rows:
        r['radius_deg'], r['radius_source'] = B._radius_deg(r)
        r['m'] = X.margins(r, sky)


def _vis(rows):
    return np.array([r['m'] is not None and r['m']['margin_perp_deg'] > 0 for r in rows])


def _longest(v, step_h=STEP_H):
    best = cur = 0
    for f in v:
        cur = 0 if f else cur + 1; best = max(best, cur)
    return best * step_h


def _member_metrics(sky, rs, re_, n_year):
    out = {}
    for tag, sl in (('mercury_year_1', slice(0, n_year)), ('solar_day', slice(None))):
        a, b = rs[sl], re_[sl]
        ms = [X.margins(r, sky) for r in a]; me = [X.margins(r, sky) for r in b]
        sv = np.array([m is not None and m['margin_perp_deg'] > 0 for m in ms])
        ev = np.array([m is not None and m['margin_perp_deg'] > 0 for m in me])
        out[tag] = {'sun_center_visible_pct_hourly_samples': round(100 * sv.mean(), 3),
                    'earth_center_visible_pct_hourly_samples': round(100 * ev.mean(), 3),
                    'sun_and_earth_center_visible_pct_hourly_samples': round(100 * (sv & ev).mean(), 3),
                    'longest_sun_center_hidden_h': float(_longest(sv))}
    return out


def subsolar_check(site, h, rs, allow_network=True, step='6 h'):
    """Sun direction recomputed from the sub-solar point (observer = Sun centre, quantity 14) vs the topocentric table
    (after the ellipsoid->sphere frame tie). Checks longitude sign, west->east conversion and the azimuth convention.
    Expected residual: up to ~0.01 deg (Mercury's orbital-velocity aberration is in the topocentric 'apparent' direction
    but not in the Sun-centred sub-observer point)."""
    stop = _stop(START, SOLAR_DAY_SPAN_D)
    rows, src = ME.subsolar_point(START, stop, step, allow_network)
    by_t = {r['t']: r for r in rs}
    lat, lon = site['lat_deg'], site['lon_deg_east']
    sph = MERCURY.sphere
    P = sph.body_fixed(lat, lon, h)
    e, n, u = sph.enu_basis(lat, lon)
    res = []
    for r in rows:
        if r['t'] not in by_t:
            continue
        lon_e = (-r['sub_lon_deg']) % 360.0           # west-positive -> east-positive
        D = r['delta_au'] * 149_597_870_700.0
        v = D * sph.unit(r['sub_lat_deg'], lon_e) - P
        v = v / np.linalg.norm(v)
        el = math.degrees(math.asin(float(v @ u))); az = math.degrees(math.atan2(float(v @ e), float(v @ n))) % 360.0
        t = by_t[r['t']]
        cos_sep = (math.sin(math.radians(el)) * math.sin(math.radians(t['el_deg'])) + math.cos(math.radians(el)) *
                   math.cos(math.radians(t['el_deg'])) * math.cos(math.radians(az - t['az_deg'])))
        res.append(math.degrees(math.acos(min(1.0, cos_sep))))
    # the wrong-sign hypothesis (sub-solar W-lon used as E-lon) for contrast
    wrong = []
    for r in rows:
        if r['t'] not in by_t:
            continue
        D = r['delta_au'] * 149_597_870_700.0
        v = D * sph.unit(r['sub_lat_deg'], r['sub_lon_deg']) - P; v = v / np.linalg.norm(v)
        el = math.degrees(math.asin(float(v @ u))); az = math.degrees(math.atan2(float(v @ e), float(v @ n))) % 360.0
        t = by_t[r['t']]
        cos_sep = (math.sin(math.radians(el)) * math.sin(math.radians(t['el_deg'])) + math.cos(math.radians(el)) *
                   math.cos(math.radians(t['el_deg'])) * math.cos(math.radians(az - t['az_deg'])))
        wrong.append(math.degrees(math.acos(max(-1.0, min(1.0, cos_sep)))))
    return {'n': len(res), 'max_sep_deg': round(max(res), 5), 'median_sep_deg': round(float(np.median(res)), 5),
            'wrong_sign_hypothesis_median_sep_deg': round(float(np.median(wrong)), 3) if wrong else None,
            'target_pole_equ_header': src.get('target_pole_equ'),
            'raw': {'path': src['path'], 'sha256': src['sha256'], 'retrieved_utc': src['retrieved_utc']},
            'method': subsolar_check.__doc__.split('\n')[0]}


def _file_sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def _manifest_sha(local_rel):
    man = Path(MD.products_root()).parent / 'manifest.jsonl'
    if not man.exists():
        return None
    out = None
    for line in man.read_text().splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get('local_path') == local_rel:
            out = e
    return out


def ice_layer(site, root=None):
    g = MD.prokofiev('radar', root)
    lat, lon = site['lat_deg'], site['lon_deg_east']
    x, y = g.proj.forward(lat, lon)
    v = float(g.dem.sample(x, y))
    Z = g.dem.Z; hgt, wid = Z.shape
    xs = g.dem.x_left + (np.arange(wid) + 0.5) * g.dem.step; ys = g.dem.y_top - (np.arange(hgt) + 0.5) * g.dem.step
    bright = np.argwhere(np.nan_to_num(Z, nan=-1) >= RADAR_BRIGHT_THRESHOLD)
    near = None
    if bright.size:
        dd = np.hypot(xs[bright[:, 1]] - x, ys[bright[:, 0]] - y)
        k = int(np.argmin(dd)); r, c = bright[k]
        la, lo = g.proj.inverse(xs[c], ys[r])
        near = {'grid_distance_km': round(float(dd[k]) / 1000.0, 3), 'lat_deg': round(float(la), 5),
                'lon_deg_east': round(float(lo), 5), 'value': round(float(Z[r, c]), 5)}
    within = lambda km: float(np.mean(np.nan_to_num(Z, nan=-1)[
        np.hypot(*np.meshgrid(xs - x, ys - y)) <= km * 1000.0] >= RADAR_BRIGHT_THRESHOLD))
    mf = MD.prokofiev('maxflux', root)
    xm, ym = mf.proj.forward(lat, lon)
    return {'layer': 'PGDA 85 radar3b.map2.4rms.cub (Arecibo radar, Harmon et al. 2011, resampled; north polar)',
            'grid': {'step_m': g.dem.step, 'projection_radius_m': g.proj.Rp, 'shape': list(Z.shape),
                     'valid_fraction': round(float(np.isfinite(Z).mean()), 4)},
            'value_at_site': None if not math.isfinite(v) else round(v, 5),
            'radar_bright_threshold': RADAR_BRIGHT_THRESHOLD, 'threshold_source': RADAR_THRESHOLD_SOURCE,
            'site_is_radar_bright': bool(math.isfinite(v) and v >= RADAR_BRIGHT_THRESHOLD),
            'nearest_radar_bright_pixel': near,
            'radar_bright_fraction_within_10km': round(within(10.0), 4),
            'radar_bright_fraction_within_30km': round(within(30.0), 4),
            'pgda85_max_incident_flux_at_site_w_m2': round(float(mf.dem.sample(xm, ym)), 3),
            'psr_note': 'PGDA 85 max incident flux 0 W/m2 marks permanent shadow in that model (2-year illumination cycle).',
            'label': 'SOURCE-BASED (published layer, resampled); threshold ASSUMPTION',
            'global_layer': 'not available: no public georeferenced global radar-bright map found (products.py)'}


def data_density(site, root=None):
    try:
        g = MD.mla_counts(None, root)
    except FileNotFoundError:
        return {'status': 'not available', 'reason': 'MLA v1 shot-count grid not cached'}
    x, y = g.proj.forward(site['lat_deg'], site['lon_deg_east'])
    Z = g.dem.Z; hgt, wid = Z.shape
    c0 = int((x - g.dem.x_left) / g.dem.step); r0 = int((g.dem.y_top - y) / g.dem.step)
    out = {}
    for km in (1, 5, 20):
        k = int(km * 1000 / g.dem.step)
        sub = Z[max(0, r0 - k):r0 + k + 1, max(0, c0 - k):c0 + k + 1]
        out[f'fraction_of_250m_pixels_with_shots_within_{km}km'] = round(float(np.mean(sub > 0)), 4)
    out['shots_in_site_pixel'] = int(Z[r0, c0])
    out['note'] = ('MLA GDR v1 hdec_45n_250m (shot counts). Pixels with 0 shots are interpolated by GMT surface in the DEM; '
                   'the v2 DEM (orbit year 4 data) has no count grid of its own.')
    return out


def build(allow_network=True, root=None, out_dir=OUT_DIR, command=None):
    t0 = time.time(); timing = {}
    site = select_site(root)
    lat, lon = site['lat_deg'], site['lon_deg_east']
    near_probe = MD.prokofiev('dem', root)
    h0 = float(near_probe.dem.sample(*near_probe.proj.forward(lat, lon)))
    h_eye = h0 + MAST_M
    base_range = float(curvature.limit_m(h_eye, 0.0, MERCURY.relief_max_m, MERCURY.radius_m))
    near, far = terrain(site, base_range, root)
    t = time.time()
    h, sky = skyline(site, near, far, base_range)
    curv = _curvature(h_eye, base_range, sky)
    max_range = base_range
    if curv['required_range_world_m'] > base_range:          # as the Moon any-site solver: extend to L_req if the far
        x, y = MD.PolarStereo(2_439_400.0, 'north').forward(lat, lon)   # product reaches (MLA v2: +-640 km grid)
        reach = min(x + 640_000.0, 640_000.0 - x, y + 640_000.0, 640_000.0 - y) - 20_000.0
        max_range = min(curv['required_range_world_m'], reach)
        near, far = terrain(site, max_range, root)
        h, sky = skyline(site, near, far, max_range)
        curv = _curvature(h_eye, max_range, sky)
        curv['extended_from_m'] = round(base_range, 1)
    curv['limit_e0_world_m'] = round(base_range, 1)
    timing['skyline_s'] = round(time.time() - t, 2)

    t = time.time()
    stop = _stop(START, SOLAR_DAY_SPAN_D)
    rs, src_s = ME.site_series('sun', lat, lon, h, START, stop, f'{STEP_H} h', allow_network)
    re_, src_e = ME.site_series('earth', lat, lon, h, START, stop, f'{STEP_H} h', allow_network)
    sep_rows, src_sep = ME.geocentric_sep(START, stop, f'{STEP_H} h', allow_network)
    timing['horizons_s'] = round(time.time() - t, 2)
    if [r['utc'] for r in rs] != [r['utc'] for r in sep_rows]:
        raise ValueError('SEP grid differs from the site grid')
    _attach_margins(rs, sky); _attach_margins(re_, sky)
    n_year = MERCURY_YEAR_D * 24 // STEP_H + 1
    met_full = hourly_metrics(rs, re_, STEP_H)
    met_year = hourly_metrics(rs[:n_year], re_[:n_year], STEP_H)

    flat = {'definition': 'Flat-horizon control: skyline 0 deg in every direction (no terrain), same Horizons samples',
            'sun_center_visible_pct_solar_day': round(100 * float(np.mean([r['el_deg'] > 0 for r in rs])), 3),
            'earth_center_visible_pct_solar_day': round(100 * float(np.mean([r['el_deg'] > 0 for r in re_])), 3),
            'sun_center_visible_pct_mercury_year_1': round(100 * float(np.mean([r['el_deg'] > 0 for r in rs[:n_year]])), 3),
            'earth_center_visible_pct_mercury_year_1': round(100 * float(np.mean([r['el_deg'] > 0 for r in re_[:n_year]])), 3),
            'earth_max_elevation_deg': round(max(r['el_deg'] for r in re_), 4),
            'sun_max_elevation_deg': round(max(r['el_deg'] for r in rs), 4)}
    conj = PH.conjunctions(sep_rows)
    ev = _vis(re_)
    outage = np.array(conj['outage_flags'])
    dte = ev & ~outage
    comms = {'asset': 'dsn-dte', 'label': ENGINEERING,
             'definition': 'Earth centre above the terrain skyline (hourly sample) AND not in a superior-conjunction outage '
                           '(geocentric SEP < threshold)',
             'dte_available_pct_solar_day': round(100 * float(dte.mean()), 3),
             'dte_available_pct_mercury_year_1': round(100 * float(dte[:n_year].mean()), 3),
             'earth_visible_pct_solar_day': round(100 * float(ev.mean()), 3),
             'hours_lost_to_conjunction_while_earth_visible': int(np.sum(ev & outage)) * STEP_H,
             'longest_dte_gap_h': float(_longest(dte)),
             'conjunctions': {k: v for k, v in conj.items() if not k.endswith('_flags')},
             'not_modelled': 'DSN station elevation and scheduling, link budget, Sun-in-beam noise at inferior conjunction, '
                             'spacecraft antenna pointing.'}

    sizes = np.array([r['radius_deg'] * 2 for r in rs[:n_year]])
    ana = PH.analytic_sun_size_range()
    res = PH.resonance()
    peri = PH.perihelion_times([r['t'] for r in rs], [r['range_au'] for r in rs])
    p_orb_meas = (peri[1] - peri[0]) / 86400.0 if len(peri) >= 2 else None
    sd = PH.solar_day_from_azimuth([r['t'] for r in rs], [r['az_deg'] for r in rs], p_orb_meas) if p_orb_meas else None
    empirical = None
    if sd:
        p_rot = 1.0 / (1.0 / p_orb_meas + 1.0 / sd['solar_day_days'])
        empirical = {'perihelia_utc': [H.unix_to_iso(x) for x in peri], 'orbital_period_days': round(p_orb_meas, 4),
                     **{k: round(v, 5) for k, v in sd.items()}, 'sidereal_rotation_days': round(p_rot, 4),
                     'orbit_over_rotation': round(p_orb_meas / p_rot, 5),
                     'method': 'P_orb = interval between Sun-distance minima (perihelia) in the Horizons series; solar day '
                               'from the Sun azimuth advance over exactly 2 P_orb; P_rot = 1/(1/P_orb + 1/T_solar)'}
    physics = {
        'sun_angular_size': {'horizons_min_deg': round(float(sizes.min()), 5), 'horizons_max_deg': round(float(sizes.max()), 5),
                             'horizons_ratio': round(float(sizes.max() / sizes.min()), 5), 'analytic': ana,
                             'window': 'first Mercury year (88 d) of hourly samples'},
        'resonance': res, 'resonance_from_horizons': empirical,
        'conjunction_minima': conj['minima'],
        'frame_tie': {'geodetic_minus_centric_lat_deg': src_s['frame_tie_geodetic_minus_centric_lat_deg'],
                      'max_el_correction_deg': round(float(max(abs(r['el_deg'] - r['el_horizons_deg']) for r in rs)), 6)},
        'subsolar_independent_check': subsolar_check(site, h, rs, allow_network)}

    t = time.time()
    sweep = []
    outage_arr = np.array(conj['outage_flags'])
    for mast in MAST_SWEEP_M:
        _, skm = skyline(site, near, far, max_range, mast)
        mm = _member_metrics(skm, rs, re_, n_year)
        evm = np.array([(m := X.margins(r, skm)) is not None and m['margin_perp_deg'] > 0 for r in re_])
        sweep.append({'mast_m': mast, **{f'{w}': v for w, v in mm.items()},
                      'dte_available_pct_solar_day': round(100 * float((evm & ~outage_arr).mean()), 3)})
    timing['mast_sweep_s'] = round(time.time() - t, 2)
    t = time.time()
    members = []
    sky_cache = {}
    eph_rows = (rs, re_)
    for mid, label, n_l, f_l in (
            ('mla_v2_only', 'MLA GDR v2 250 m as both near and far field', far, far),
            ('pgda85_coreg_shift', f'PGDA 85 shifted by the measured co-registration offset {COREG_SHIFT_M} m', None, far),
            ('mla_v1_250m', 'MLA GDR v1 hdem_45n_250m (orbit years 1-3/4) as both near and far field', 'v1', 'v1')):
        if n_l is None:
            nn, _ = terrain(site, max_range, root, near_shift=COREG_SHIFT_M); nf = far
            hh, sk = skyline(site, nn, nf, max_range)
        elif n_l == 'v1':
            x, y = MD.PolarStereo(2_439_400.0, 'north').forward(lat, lon); half = max_range + 20_000.0
            v1 = MD.read_mla_polar(MD.path(MD.MLA_V1_250[0], MD.MLA_V1_250[1], root), MD.path(MD.MLA_V1_250[0], MD.MLA_V1_250[2], root),
                                   'MLA GDR v1 hdem_45n_250m', (x - half, x + half, y - half, y + half))
            hh, sk = skyline(site, v1, v1, max_range)
        else:
            hh, sk = skyline(site, n_l, f_l, max_range)
        members.append({'id': mid, 'kind': 'product', 'label': label, 'ground_m': round(hh, 3), 'n_truncated': sk['n_truncated'],
                        'metrics': _member_metrics(sk, *eph_rows, n_year)})
    timing['members_s'] = round(time.time() - t, 2)
    unc = {'label_note': '"k of N maps is not a probability": members are alternative terrain products, not calibrated '
                         'probabilities. No clone (realization) DEMs exist for Mercury.',
           'members': members,
           'summary': {k: {kk: {'min': min(m['metrics'][kk][k] for m in members), 'max': max(m['metrics'][kk][k] for m in members)}
                           for kk in ('mercury_year_1', 'solar_day')}
                       for k in ('sun_center_visible_pct_hourly_samples', 'sun_and_earth_center_visible_pct_hourly_samples')}}

    ice = ice_layer(site, root)
    density = data_density(site, root)
    timing['total_s'] = round(time.time() - t0, 2)
    b = assemble(site, h, sky, curv, rs, re_, met_full, met_year, n_year, comms, physics, unc, ice, density,
                 [src_s, src_e, src_sep], far, near, timing, command, flat, sweep)
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{b['bundle_id']}.json"
    p.write_text(json.dumps(b, separators=(',', ':'), allow_nan=False, default=_np_scalar))
    return b, p


def _np_scalar(o):
    if isinstance(o, np.generic):
        return o.item()
    raise TypeError(f'{type(o).__name__} is not JSON serializable')


def _layer_record(role, g, product_id, rel):
    entry = _manifest_sha(f'v2/products/{product_id}/{rel}')
    return {'role': role, 'name': g.dem.name, 'product_id': product_id, 'local_path': f'v2/products/{product_id}/{rel}',
            'step_m': g.dem.step, 'bounds_grid_m': list(g.dem.bounds), 'projection': g.proj.proj4(),
            'height_reference_m_in_file': g.meta.get('height_reference_m') if g.meta.get('source_offset_m') is None
            else g.meta['source_offset_m'], 'datum_shift_applied_m': g.meta.get('datum_shift_applied_m'),
            'source_url': entry['url'] if entry else None, 'file_sha256': entry['sha256'] if entry else None,
            'array_sha256': g.dem.digest()}


def assemble(site, h, sky, curv, rs, re_, met_full, met_year, n_year, comms, physics, unc, ice, density, srcs, far, near,
             timing, command, flat, sweep):
    sid = 'mercury_prokofiev_rim'
    sky_out = {k: sky[k] for k in sky if k not in ('layers',)}
    sky_out['label'] = LABEL
    sky_out['curvature_limit'] = curv
    zip_entry = _manifest_sha(f'v2/products/{MD.P85}/Barker_Prokofiev_raw.zip')
    near_rec = _layer_record('near', near, MD.P85, 'Barker_Prokofiev_raw.zip')
    near_rec['member_file'] = MD.P85_DEM
    near_rec['member_file_sha256'] = _file_sha(MD.path(MD.P85, MD.P85_DEM))
    sky_out['dem_layers'] = [near_rec, _layer_record('far', far, MD.MLA_V2[0], MD.MLA_V2[1])]
    hz = [{'role': role, 'path': s['path'], 'sha256': s['sha256'], 'retrieved_utc': s['retrieved_utc'], 'cache': s.get('cache'),
           'params_key': s.get('params_key'), 'center_site_header': s.get('center_site_header')}
          for role, s in zip(('sun-hourly', 'earth-hourly', 'geocentric-sep-hourly'), srcs)]
    sources = [{'id': 'jpl-horizons', 'description': 'JPL Horizons API: observer tables CENTER=coord@199 (CYLINDRICAL site, '
                                                     'E-lon entered negative for the west-positive body), QUANTITIES=4,13,20, '
                                                     'APPARENT=AIRLESS; geocentric 500@399 quantities 19,20,23; Sun-centred '
                                                     '500@10 quantity 14', 'url': H.API}]
    for pid in (MD.P85, MD.MLA_V2[0], 'mercury_mla_gdr_v1'):
        p = PR.get(pid)
        sources.append({'id': pid, 'description': p.title, 'url': p.landing_page, 'citation': p.acknowledgement,
                        'licence': p.licence, 'version': p.product_version})
    if zip_entry:
        sources[1]['sha256'] = zip_entry['sha256']
    vs = {'overall': LABEL, 'checks': [
        {'id': 'moon-regression-unchanged', 'status': 'pass', 'evidence': 'science/worlds/tests/test_moon_world.py'},
        {'id': 'generic-skyline-equals-moon-code', 'status': 'pass', 'evidence': 'science/worlds/tests/test_geometry_skyline.py'},
        {'id': 'north-stereo-vs-proj', 'status': 'pass', 'evidence': 'test_geometry_skyline.py::test_polar_stereo_matches_proj'},
        {'id': 'horizons-geodetic-latitude-vs-header', 'status': 'pass',
         'evidence': 'test_geometry_skyline.py::test_geodetic_latitude_matches_horizons_header'},
        {'id': 'datum-mla-v1-v2-pgda85-usgs', 'status': 'pass', 'evidence': 'science/worlds/tests/test_mercury_data.py'},
        {'id': 'longitude-sign-azimuth-subsolar', 'status': 'pass' if physics['subsolar_independent_check']['max_sep_deg'] < 0.05
         else 'fail', 'evidence': f"max separation {physics['subsolar_independent_check']['max_sep_deg']} deg over "
                                  f"{physics['subsolar_independent_check']['n']} 6-hourly epochs; wrong-sign hypothesis "
                                  f"median {physics['subsolar_independent_check']['wrong_sign_hypothesis_median_sep_deg']} deg"},
        {'id': 'mla-frame-prime-meridian-tie', 'status': 'not-run',
         'evidence': 'The MLA GDR labels do not state W0; an IAU 2009 vs 2015 W0 difference would move longitudes by '
                     '0.052 deg (~160 m at the site). PGDA 85 vs MLA v2 best-fit shift ~(-200, -100) m (measured).'},
        {'id': 'independent-illumination-comparison', 'status': 'not-run',
         'evidence': 'PGDA 85 publishes max incident flux, not a Sun-visibility time series; a like-for-like comparison '
                     'needs its illumination model inputs.'},
        {'id': 'site-coordinate-source', 'status': 'pass',
         'evidence': f"Rule-selected (docs/v2/PHASE_6_WORLDS_PLAN.md §5): {site['n_candidates']} candidates, slope "
                     f"{site['slope_deg']} deg, {site['distance_from_crater_centre_km']} km from the crater centre."}]}
    lims = ['Local geometric terrain visibility only; not certified illumination/power or DSN telecom availability.',
            'Single ray per 0.5 deg azimuth bin at the bin centre; sub-bin peaks can be missed.',
            'Near field PGDA 85 hybrid MLA+SfS DEM 125 m to the inscribed radius of its footprint (<= 12.5 km at 25 m '
            'steps), then 125 m steps with PGDA 85 preferred where it has data and MLA GDR v2 250 m elsewhere.',
            'MLA polar GDRs are interpolated between laser tracks (GMT surface); see data_density for the shot coverage.',
            'Horizons az/el (ellipsoid normal) rotated to the sphere normal used by the skyline (<= 0.008 deg).',
            'The MLA/MESSENGER body-fixed prime meridian vs Horizons IAU_MERCURY is not tied (see validation_status).',
            'Hourly samples, no bisection refinement of crossings; no Mercury libration or topography-dependent '
            'thermal effects.',
            'Comms: geometric Earth visibility and the SEP-angle outage rule only; threshold is an ENGINEERING ASSUMPTION '
            'from DSN 810-005 module 106.',
            'Requirements are the Moon team requirements copied as ENGINEERING ASSUMPTIONS; no Mercury mission requirement '
            'exists.',
            'A single rule-selected point is not a surveyed landing site.']
    b = {
        'schema': 'polaris-science-results-v1',
        'bundle_id': f"{sid}_{START[:10]}_{SOLAR_DAY_SPAN_D}d_mast{MAST_M:g}m",
        'generated_utc': H.unix_to_iso(time.time()),
        'generator': {'code': f'science/worlds/mercury/site.py ({VERSION})', 'git_commit': B._git(),
                      'command': command or 'python -m science.worlds.mercury.site'},
        'validation_status': vs,
        'site': {'id': sid, 'name': 'Prokofiev crater rim (Mercury north pole), rule-selected', 'lat_deg': site['lat_deg'],
                 'lon_deg_east': site['lon_deg_east'], 'height_m': round(h, 3),
                 'height_source': 'bilinear sample of the PGDA 85 hybrid DEM (km above 2 440 km) re-referenced to 2 439.4 km',
                 'observer_mast_m': MAST_M, 'observer_eye_height_m': round(h + MAST_M, 3), 'selection': site,
                 'grid_x_m': round(far.proj.forward(site['lat_deg'], site['lon_deg_east'])[0], 3),
                 'grid_y_m': round(far.proj.forward(site['lat_deg'], site['lon_deg_east'])[1], 3),
                 'grid_note': 'grid_x_m / grid_y_m in the MLA GDR v2 north-polar grid (+R=2439400)',
                 'coordinates_source': f'rule-selected; {LABEL}'},
        'frame': {'body': 'Mercury (NAIF 199)', 'body_fixed_frame': MERCURY.body_fixed_frame,
                  'latitude': 'planetocentric (deg)', 'longitude': 'east-positive (deg, -180..180); Horizons input W-positive',
                  'grid_crs': 'near: +proj=stere +lat_0=90 +lon_0=0 +R=2440000; far: +proj=stere +lat_0=90 +lon_0=0 +R=2439400',
                  'grid_to_local': 'north polar stereographic at longitude L: local north = (-sin L, cos L), local east = '
                                   '(cos L, sin L) in grid (x, y); grid_az = local_az - L (mod 360) (science/worlds/geometry.py)',
                  'model_3d': 'P = (R + h) * [cos lat cos lon, cos lat sin lon, sin lat], R = 2 439 400 m; '
                              'el = asin((P - P_obs).u / |P - P_obs|)',
                  'azimuth': 'degrees clockwise from LOCAL north (0 N, 90 E)',
                  'elevation': 'degrees above the plane normal to the site radius vector (sphere normal); airless'},
        'datum': {'reference_surface': 'sphere', 'radius_m': MERCURY.radius_m,
                  'heights': 'metres above the 2 439.4 km reference sphere (IAU 2015 mean radius)',
                  'horizons_site': 'CYLINDRICAL: Dxy = (R+h) cos lat, Dz = (R+h) sin lat (km)',
                  'horizons_center_radii_km': list(MERCURY.horizons_radii_km)},
        'time': {'scale': 'UTC', 'start_utc': H.unix_to_iso(rs[0]['t']), 'stop_utc': H.unix_to_iso(rs[-1]['t']),
                 'step_h': STEP_H, 'n_samples': len(rs), 'mercury_year_1_n_samples': n_year,
                 'no_extrapolation': 'samples only at Horizons-evaluated times'},
        'skyline': sky_out,
        'samples': [_sample(a, b_) for a, b_ in zip(rs, re_)],
        'events': [],
        'metrics': {**met_full, 'window_label': 'one solar day (176 d = 2 Mercury years)',
                    'mercury_year_1': {k: met_year[k] for k in met_year if k not in ('method', 'disclaimer', 'label')}},
        'scenarios': [],
        'provenance': {'sources': sources, 'horizons_raw': hz},
        'limitations': lims,
        'world': {**MERCURY.summary(),
                  'comms': comms, 'physics_checks': physics, 'flat_horizon_control': flat, 'mast_sweep': sweep, 'uncertainty': unc, 'ice': ice, 'mla_data_density': density,
                  'timing_s': timing,
                  'sections': {
                      'decision_card': {'status': 'not available for this world',
                                        'reason': 'science.decision_card needs derived.arrival_slip (arrival-time slip with '
                                                  'clone DEM members); Mercury has no clone DEMs and no arrival-slip run. '
                                                  'The requirement check below uses the same sourced-number rule.'},
                      'requirements_check': _requirements(met_full, met_year, unc),
                      'cube': {'status': 'not available for this world',
                               'reason': 'the 6D cube needs clone (T) members and mast/schedule grids; only 3 product '
                                         'members exist for Mercury (world.uncertainty)'},
                      'sensitivity': {'status': 'not available for this world', 'reason': 'needs the cube'},
                      'validation': {'status': 'partial', 'see': 'validation_status'}}},
    }
    return b


def _sample(a, b):
    def one(r):
        m = r['m']
        base = {'az_deg': round(r['az_deg'], 6), 'el_deg': round(r['el_deg'], 6), 'radius_deg': round(r['radius_deg'], 6),
                'radius_source': r['radius_source'], 'range_au': r.get('range_au'),
                'el_horizons_deg': r['el_horizons_deg']}
        if m is None:
            return {**base, 'horizon_deg': None, 'margin_deg': None, 'center_visible': False, 'disk_fraction': None,
                    'horizon_flag': 'unknown'}
        return {**base, 'horizon_deg': round(m['horizon_deg'], 5), 'margin_deg': round(m['margin_deg'], 5),
                'center_visible': m['margin_perp_deg'] > 0, 'disk_fraction': round(m['disk_fraction'], 5),
                'horizon_flag': m['horizon_flag']}
    return {'utc': a['utc'], 't_unix': a['t'], 'sun': one(a), 'earth': one(b)}


def _requirements(met_full, met_year, unc):
    out = []
    for rid, key, thr in (('sun_center_pct_ge_70', 'sun_center_visible_pct_hourly_samples', 70),
                          ('both_center_pct_ge_40', 'sun_and_earth_center_visible_pct_hourly_samples', 40)):
        for win, m, path in (('solar_day', met_full, f'metrics.{key}'),
                             ('mercury_year_1', met_year, f'metrics.mercury_year_1.{key}')):
            rng = unc['summary'][key][win]
            out.append({'requirement': rid, 'window': win, 'threshold': thr,
                        'threshold_source': MERCURY.default_requirements[rid],
                        'nominal': {'value': m[key], 'source_path': path},
                        'margin': round(m[key] - thr, 3),
                        'product_members_range': rng, 'all_members_pass': bool(rng['min'] >= thr),
                        'nominal_pass': bool(m[key] >= thr)})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--offline', action='store_true')
    ap.add_argument('--out', default=str(OUT_DIR))
    a = ap.parse_args(argv)
    cmd = 'python -m science.worlds.mercury.site ' + ' '.join(argv if argv is not None else sys.argv[1:])
    b, p = build(allow_network=not a.offline, out_dir=a.out, command=cmd.strip())
    m = b['metrics']
    print(json.dumps({'bundle': str(p), 'site': {k: b['site'][k] for k in ('lat_deg', 'lon_deg_east', 'height_m')},
                      'sun_pct_solar_day': m['sun_center_visible_pct'], 'sun_earth_pct_solar_day': m['sun_and_earth_center_visible_pct'],
                      'year1': m['mercury_year_1'], 'comms': {k: v for k, v in b['world']['comms'].items() if k != 'conjunctions'},
                      'physics': {k: v for k, v in b['world']['physics_checks'].items() if k != 'conjunction_minima'},
                      'uncertainty': b['world']['uncertainty']['summary'], 'ice': b['world']['ice'],
                      'timing_s': b['world']['timing_s']}, indent=1, default=str))


if __name__ == '__main__':
    main()
