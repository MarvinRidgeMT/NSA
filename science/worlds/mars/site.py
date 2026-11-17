"""One Mars site end to end (prompt §3.3): Jezero crater rim.

  python -m science.worlds.mars.site [--offline]

Site rule (fixed in docs/v2/PHASE_6_T3_PLAN.md §4 before the run): Jezero crater, USGS Gazetteer of Planetary
Nomenclature feature 14300 (MDIM 2.1 control network, planetocentric +E): centre 18.41 N, 77.69 E, diameter 47.52 km
(retrieved 2026-11-17). Pick the highest point (radius height) of the Mars 2020 science CTX DEM (20 m) inside the rim
annulus 0.85-1.15 R whose 3x3 slope is < 15 deg; ties -> nearest the centre. Not chosen by its Sun visibility.

Pipeline: generic world solver (science/worlds/anysite.py: CTX 20 m near field, MOLA 128 ppd far field to the curvature
limit, MOLA 16 ppd fill; Horizons coord@499 with the IAU 2000 -> 2015 longitude tie; hourly for one Mars year) ->
seasons by Ls -> direct-beam energy for explicit tau values (ENGINEERING ASSUMPTION) -> DTE with the SEP rule (relays not
available) -> physics and data checks -> bundle in data/worlds/mars/.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
from pathlib import Path

import numpy as np

from ... import horizons as H
from ..anysite import _np, member_metrics, solve as world_solve, terrain_and_skyline
from ..base import ENGINEERING, LABEL
from . import dem as MD
from . import energy as EN
from . import seasons as SE
from .world import MARS

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / 'data' / 'worlds' / 'mars'
START = '2026-11-14 00:00'
DAYS = 687                       # one Mars year (686.98 d) at hourly samples
MAST_M = 1.0
SOL_S = 88_775.244               # mean solar day (Allison & McEwen 2000)
CRATER = {'name': 'Jezero', 'lat_deg': 18.41, 'lon_deg_east': 77.69, 'diameter_km': 47.52,
          'source': 'USGS Gazetteer of Planetary Nomenclature, feature 14300 (Jezero, Mars), control network MDIM 2.1, '
                    'planetocentric +East 0-360; retrieved 2026-11-17 (https://planetarynames.wr.usgs.gov/Feature/14300)'}
RULE = {'annulus_rim_radii': [0.85, 1.15], 'max_slope_deg': 15.0, 'pick': 'highest CTX radius height',
        'slope': '3x3 central differences on the 20 m CTX grid', 'ties': 'nearest the crater centre',
        'fixed_before_run': '2026-11-17 (docs/v2/PHASE_6_T3_PLAN.md §4)'}
MEMBERS = ('mola_only', 'ctx_trn')


def _gc_m(lat1, lon1, lat2, lon2, R=MARS.radius_m):
    p1, p2 = np.radians(lat1), np.radians(lat2); dl = np.radians(np.asarray(lon2) - lon1)
    return R * np.arccos(np.clip(np.sin(p1) * np.sin(p2) + np.cos(p1) * np.cos(p2) * np.cos(dl), -1, 1))


def select_site():
    d, fwd, crs = MD.ctx('sci')
    R, k, lon0 = float(crs['R']), math.cos(math.radians(crs.get('lat_ts', 0.0))), crs.get('lon_0', 0.0)
    h, w = d.Z.shape
    lats = np.degrees((d.y_top - (np.arange(h) + 0.5) * d.step) / R)
    lons = lon0 + np.degrees((d.x_left + (np.arange(w) + 0.5) * d.step) / (R * k))
    LA, LO = np.meshgrid(lats, lons, indexing='ij')
    rr = _gc_m(CRATER['lat_deg'], CRATER['lon_deg_east'], LA, LO)
    R0 = CRATER['diameter_km'] * 500.0
    Z = d.Z
    dzdx = np.full_like(Z, np.nan); dzdy = np.full_like(Z, np.nan)
    # ground spacing: y = 20 m; x = 20 m x cos(lat) / cos(lat_ts) on the sphere
    gx = d.step * np.cos(np.radians(LA[:, 1:-1])) / k
    dzdx[:, 1:-1] = (Z[:, 2:] - Z[:, :-2]) / (2 * gx)
    dzdy[1:-1, :] = (Z[:-2, :] - Z[2:, :]) / (2 * d.step)
    slope = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    cand = (rr >= RULE['annulus_rim_radii'][0] * R0) & (rr <= RULE['annulus_rim_radii'][1] * R0) & np.isfinite(Z) & \
        np.isfinite(slope) & (slope < RULE['max_slope_deg'])
    score = np.where(cand, Z, -np.inf)
    ii = np.argwhere(score == score.max())
    r, c = (int(v) for v in ii[np.argmin(rr[ii[:, 0], ii[:, 1]])])
    return {'lat_deg': round(float(LA[r, c]), 7), 'lon_deg_east': round(float(LO[r, c]), 7), 'pixel_row_col': [r, c],
            'ctx_radius_height_m': round(float(Z[r, c]), 3), 'slope_deg': round(float(slope[r, c]), 3),
            'distance_from_crater_centre_km': round(float(rr[r, c]) / 1000.0, 3), 'n_candidates': int(cand.sum()),
            'crater': CRATER, 'rule': RULE}


def _vis(rows):
    return np.array([r['m'] is not None and r['m']['margin_perp_deg'] > 0 for r in rows])


def seasons_and_energy(rs, re_):
    t = np.array([r['t'] for r in rs]); ls = SE.ls_deg(t); si = SE.season_index(ls)
    sv, ev = _vis(rs), _vis(re_)
    el = np.array([r['el_deg'] for r in rs]); rau = np.array([r['range_au'] for r in rs])
    out = []
    for k, nm in enumerate(SE.SEASONS):
        m = si == k
        if not m.any():
            continue
        tk = t[m]
        row = {'season': nm, 'n_samples': int(m.sum()), 'utc_first': H.unix_to_iso(tk[0]), 'utc_last': H.unix_to_iso(tk[-1]),
               'sun_center_visible_pct': round(100 * float(sv[m].mean()), 3),
               'earth_center_visible_pct': round(100 * float(ev[m].mean()), 3),
               'flat_sun_center_visible_pct': round(100 * float((el[m] > 0).mean()), 3),
               'sun_max_elevation_deg': round(float(el[m].max()), 3),
               'mean_sun_distance_au': round(float(rau[m].mean()), 5),
               'toa_horizontal_wh_m2_per_sol': round(_daily(tk, EN.top_of_atmosphere_horizontal(el[m], rau[m])), 1),
               'direct_horizontal_wh_m2_per_sol': {}}
        for tau in EN.TAUS:
            g = EN.direct_horizontal(el[m], rau[m], sv[m], tau)
            gf = EN.direct_horizontal(el[m], rau[m], el[m] > 0, tau)
            row['direct_horizontal_wh_m2_per_sol'][f'tau_{tau:g}'] = {'terrain': round(_daily(tk, g), 1),
                                                                      'flat_horizon': round(_daily(tk, gf), 1)}
        out.append(row)
    return {'label': EN.LABEL, 'ls_source': SE.SOURCE, 'ls_at_start_deg': round(float(ls[0]), 3),
            'ls_at_stop_deg': round(float(ls[-1]), 3), 'taus': list(EN.TAUS), 'method': EN.__doc__.strip(),
            'per_season': out,
            'note': 'Energy is per unit horizontal area, direct beam only; diffuse sky light omitted (no sky MODEL '
                    'shipped). Seasons split the hourly samples by Ls quarter; a season shorter than its full span at the '
                    'window ends is labelled by its first/last UTC.'}


def _daily(t, g):
    return EN.mean_daily_wh_m2(t, g, SOL_S) if len(t) > 1 else float('nan')


def physics_checks(rs, site, h, allow_network=True):
    from .. import ephem as WE
    from ..frame_tie import planetodetic_lat
    t = np.array([r['t'] for r in rs]); el = np.array([r['el_deg'] for r in rs])
    # (a) Sun angular size vs distance (Horizons Ang-diam vs 2 asin(R_sun / r))
    from ..base import AU_KM, R_SUN_KM
    d_h = np.array([2 * r['radius_deg'] for r in rs]); rau = np.array([r['range_au'] for r in rs])
    d_a = np.degrees(2 * np.arcsin(R_SUN_KM / (rau * AU_KM)))
    a = {'horizons_min_deg': round(float(d_h.min()), 5), 'horizons_max_deg': round(float(d_h.max()), 5),
         'max_abs_diff_vs_analytic_deg': round(float(np.max(np.abs(d_h - d_a))), 6),
         'analytic_peri_aph_deg': [round(float(np.degrees(2 * math.asin(R_SUN_KM / (MARS.orbit.aphelion_au * AU_KM)))), 5),
                                   round(float(np.degrees(2 * math.asin(R_SUN_KM / (MARS.orbit.perihelion_au * AU_KM)))), 5)]}
    # (b) mean solar day from local-noon times (parabola through the 3 hourly samples around each elevation maximum)
    noons = []
    for i in range(1, len(el) - 1):
        if el[i] > el[i - 1] and el[i] >= el[i + 1] and el[i] > 0:
            y0, y1, y2 = el[i - 1], el[i], el[i + 1]
            den = y0 - 2 * y1 + y2
            noons.append(t[i] + (0.5 * (y0 - y2) / den if den != 0 else 0.0) * 3600.0)
    noons = np.array(noons)
    sol = float((noons[-1] - noons[0]) / (len(noons) - 1)) if len(noons) > 2 else None
    b = {'n_noons': int(len(noons)), 'mean_solar_day_s': round(sol, 1) if sol else None, 'reference_s': SOL_S,
         'diff_s': round(sol - SOL_S, 1) if sol else None,
         'method': 'mean interval between local noons (parabolic peak of hourly Sun elevation) over the window'}
    # (c) Ls vs Horizons sub-solar latitude, and (d) longitude sign via the sub-solar point (as for Mercury)
    stop = H.unix_to_iso(rs[-1]['t'])[:16].replace('T', ' ')
    ss, src = WE.subsolar_point(MARS, START, stop, '6 h', allow_network)
    ts = np.array([r['t'] for r in ss])
    lat_d = np.array([r['sub_lat_deg'] for r in ss])
    a_, _, c_ = MARS.horizons_radii_km
    lat_c = np.degrees(np.arctan((c_ / a_) ** 2 * np.tan(np.radians(lat_d))))     # planetodetic -> planetocentric
    pred = SE.subsolar_lat_deg(SE.ls_deg(ts))
    c = {'n': int(len(ts)), 'max_abs_diff_deg': round(float(np.max(np.abs(pred - lat_c))), 4),
         'median_abs_diff_deg': round(float(np.median(np.abs(pred - lat_c))), 4),
         'method': 'asin(sin 25.19 deg sin Ls(Allison & McEwen)) vs Horizons quantity 14 sub-solar latitude seen from the '
                   'Sun centre (planetodetic -> planetocentric on the Horizons radii)',
         'raw': {k: src.get(k) for k in ('path', 'sha256', 'retrieved_utc')}}
    by_t = {r['t']: r for r in rs}
    sph = MARS.sphere; P = sph.body_fixed(site['lat_deg'], site['lon_deg_east'], h)
    e_, n_, u_ = sph.enu_basis(site['lat_deg'], site['lon_deg_east'])
    off = MARS.horizons_lon_offset_deg(H.unix_to_jd(float(np.mean(ts))))
    res, wrong = [], []
    wdot = MARS.rotation.Wdot_deg_per_day
    for r, latc in zip(ss, lat_c):
        if r['t'] not in by_t:
            continue
        tr = by_t[r['t']]
        # The Sun-centred quantity 14 at t shows Mars' orientation at t - tau (tau = Sun-Mars light time); sunlight reaching
        # the site at t left the Sun at t - tau and meets Mars' orientation at t: advance the sub-solar W-longitude by
        # Wdot * tau (~3.1 deg for Mars; ~0.014 deg for Mercury, which is R6's reported residual).
        tau_d = r['delta_au'] * 149_597_870_700.0 / 299_792_458.0 / 86400.0
        for sign, acc in ((-1.0, res), (1.0, wrong)):
            lon_e = (sign * (r['sub_lon_deg'] + wdot * tau_d) - off) % 360.0   # W-lon -> E-lon (sign -1), Horizons -> DEM
            v = r['delta_au'] * 149_597_870_700.0 * sph.unit(latc, lon_e) - P; v = v / np.linalg.norm(v)
            elx = math.degrees(math.asin(float(v @ u_))); azx = math.degrees(math.atan2(float(v @ e_), float(v @ n_))) % 360
            cs = (math.sin(math.radians(elx)) * math.sin(math.radians(tr['el_deg'])) + math.cos(math.radians(elx)) *
                  math.cos(math.radians(tr['el_deg'])) * math.cos(math.radians(azx - tr['az_deg'])))
            acc.append(math.degrees(math.acos(max(-1.0, min(1.0, cs)))))
    d = {'n': len(res), 'max_sep_deg': round(max(res), 5), 'median_sep_deg': round(float(np.median(res)), 5),
         'wrong_sign_hypothesis_median_sep_deg': round(float(np.median(wrong)), 3),
         'target_pole_equ_header': src.get('target_pole_equ'),
         'method': 'Sun direction recomputed from the sub-solar point (Sun-centred quantity 14, planetocentric latitude, '
                   'W-longitude advanced by Wdot x Sun-Mars light time, frame tie removed) vs the topocentric table after '
                   'the ellipsoid -> sphere tie'}
    return {'sun_angular_size': a, 'solar_day': b, 'ls_vs_horizons_subsolar_latitude': c, 'subsolar_independent_check': d}


def data_checks(site):
    lat, lon = site['lat_deg'], site['lon_deg_east']
    out = {}
    for which in ('sci', 'trn'):
        d, fwd, _ = MD.ctx(which, convert=False)
        m_t = MD.mola_topography128((17.0, 20.0), 77.8, 2.0)
        cnt = MD.mola_counts128((17.0, 20.0), 77.8, 2.0)
        m_r = MD.mola_radius(128, 18.4, 77.8, 120_000.0)
        H_, W_ = m_t.Z.shape
        rr, cc = np.mgrid[0:H_, 0:W_]
        la = m_t.lat_top - (rr + 0.5) / 128; lo = m_t.lon_left + (cc + 0.5) / 128
        sel = cnt.Z >= 1
        v = d.sample(*fwd(la[sel], lo[sel])); ok = np.isfinite(v)
        topo = m_t.Z[sel][ok]; rad = m_r.sample(lo[sel][ok], la[sel][ok]) + MARS.radius_m
        hyp = {}
        for nm, ref in (('areoid_heights (MOLA topography)', topo), ('sphere_3396190', rad - 3_396_190.0)):
            dd = v[ok] - ref
            hyp[nm] = {'median_m': round(float(np.median(dd)), 2), 'mad_m': round(float(np.median(np.abs(dd - np.median(dd)))), 2)}
        out[f'ctx_{which}_datum_test'] = {'n_mola_bins_with_shots': int(ok.sum()), 'hypotheses': hyp,
                                          'verdict': min(hyp, key=lambda k: abs(hyp[k]['median_m']))}
    c = MD.mola_counts128((lat - 0.3, lat + 0.3), lon, 0.35)
    c0 = float(c.sample(lon, lat)) if False else None
    rr0 = int((c.lat_top - lat) * 128); cc0 = int(((lon - c.lon_left) % 360) * 128)
    blk = lambda km: c.Z[max(0, rr0 - int(km * 128 / 59.27)):rr0 + int(km * 128 / 59.27) + 1,
                         max(0, cc0 - int(km * 128 / 56.2)):cc0 + int(km * 128 / 56.2) + 1]
    out['mola_data_density'] = {'shots_in_site_bin': int(c.Z[rr0, cc0]),
                                **{f'fraction_of_128ppd_bins_with_shots_within_{km}km': round(float(np.mean(blk(km) > 0)), 4)
                                   for km in (2, 5, 20)},
                                'note': 'MOLA MEGDR counts (megc); bins without shots are interpolated in the MEGDR.'}
    return out


def build(allow_network=True, out_dir=OUT_DIR, command=None):
    site = select_site()
    lat, lon = site['lat_deg'], site['lon_deg_east']
    b = world_solve(MARS, lat, lon, MAST_M, START, DAYS, 1, allow_network, members=MEMBERS, write=False,
                    name='Jezero crater rim (Mars), rule-selected high point', site_id='mars_jezero_rim',
                    command=command or 'python -m science.worlds.mars.site')
    ctx = b.pop('_context')
    rs, re_, sky, h = ctx['rs'], ctx['re'], ctx['sky'], ctx['h']
    sweep = []
    for mast in (1.0, 10.0, 50.0):
        _, _, skm, _, _ = terrain_and_skyline(MARS, lat, lon, mast)
        mm, _, _ = member_metrics(skm, rs, re_, 1)
        sweep.append({'mast_m': mast, **mm})
    phys = physics_checks(rs, site, h, allow_network)
    data = data_checks(site)
    seas = seasons_and_energy(rs, re_)
    b['site'].update({'selection': site, 'coordinates_source': f'rule-selected; {LABEL}'})
    b['metrics']['window_label'] = 'one Mars year (687 d) of hourly samples'
    b['world'].update({'seasons_and_energy': seas, 'physics_checks': phys, 'data_checks': data, 'mast_sweep': sweep,
                       'sky_model': {'status': 'not available for this world',
                                     'reason': 'no Mars sky-brightness / diffuse MODEL shipped; energy is direct beam only'},
                       'requirements_check': [
                           {'requirement': rid, 'threshold': thr, 'nominal': b['metrics'][key], 'pass': b['metrics'][key] >= thr,
                            'threshold_source': MARS.default_requirements[rid]}
                           for rid, key, thr in (('sun_center_pct_ge_70', 'sun_center_visible_pct', 70),
                                                 ('both_center_pct_ge_40', 'sun_and_earth_center_visible_pct', 40))]})
    ck = lambda cond: 'pass' if cond else 'fail'
    b['validation_status']['checks'] = [
        {'id': 'horizons-model-iau2015-and-mola-tie', 'status': 'pass', 'evidence': 'science/worlds/tests/test_frame_tie.py; '
         f"offset applied {b['frame']['horizons_longitude_offset_deg']:.6f} deg"},
        {'id': 'ctx-datum-areoid', 'status': ck(all(v['verdict'].startswith('areoid') for k, v in data.items()
                                                    if k.endswith('datum_test'))),
         'evidence': json.dumps({k: v['hypotheses'] for k, v in data.items() if k.endswith('datum_test')})},
        {'id': 'ls-vs-horizons-subsolar-latitude', 'status': ck(phys['ls_vs_horizons_subsolar_latitude']['max_abs_diff_deg'] < 0.1),
         'evidence': f"max {phys['ls_vs_horizons_subsolar_latitude']['max_abs_diff_deg']} deg"},
        {'id': 'longitude-sign-azimuth-subsolar', 'status': ck(phys['subsolar_independent_check']['max_sep_deg'] < 0.05),
         'evidence': f"max {phys['subsolar_independent_check']['max_sep_deg']} deg; wrong sign median "
                     f"{phys['subsolar_independent_check']['wrong_sign_hypothesis_median_sep_deg']} deg"},
        {'id': 'sun-angular-size-vs-distance', 'status': ck(phys['sun_angular_size']['max_abs_diff_vs_analytic_deg'] < 1e-3),
         'evidence': json.dumps(phys['sun_angular_size'])},
        {'id': 'mean-solar-day', 'status': ck(phys['solar_day']['diff_s'] is not None and abs(phys['solar_day']['diff_s']) < 60),
         'evidence': json.dumps(phys['solar_day'])},
        {'id': 'independent-illumination-comparison', 'status': 'not-run',
         'evidence': 'no published Sun-visibility series for this point'}]
    b['limitations'] += ['Mars atmosphere: no refraction (estimated ~0.007 deg at the horizon), no sky model; energy = direct '
                         'beam only for explicit tau values (ENGINEERING ASSUMPTION).',
                         'Relay orbiters (MRO, MAVEN, TGO, Mars Express): not available for this world (no ephemerides '
                         'wired); comms = direct-to-Earth geometry and the SEP rule only.',
                         'CTX DEM heights are areoid heights (tested), converted with the MOLA 16 ppd areoid.',
                         'The site is a rule-selected rim high point, not a surveyed landing site.']
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    # gzip (mtime 0, deterministic): the 687-day hourly bundle is 10.3 MB as JSON, 1.6 MB compressed
    p = out_dir / f"{b['bundle_id']}.json.gz"
    p.write_bytes(gzip.compress(json.dumps(b, separators=(',', ':'), allow_nan=False, default=_np).encode(),
                                compresslevel=9, mtime=0))
    return b, p


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--offline', action='store_true')
    a = ap.parse_args(argv)
    b, p = build(not a.offline, command='python -m science.worlds.mars.site ' + ' '.join(argv or sys.argv[1:]))
    m = b['metrics']; w = b['world']
    print(json.dumps({'bundle': str(p), 'site': {k: b['site'][k] for k in ('lat_deg', 'lon_deg_east', 'height_m')},
                      'selection': {k: b['site']['selection'][k] for k in ('slope_deg', 'distance_from_crater_centre_km', 'n_candidates')},
                      'sun_pct': m['sun_center_visible_pct'], 'earth_pct': m['earth_center_visible_pct'],
                      'sun_earth_pct': m['sun_and_earth_center_visible_pct'], 'gap_h': m['longest_sun_center_hidden_h'],
                      'flat': w['flat_horizon_control'], 'comms': {k: v for k, v in w['comms'].items() if k != 'conjunctions'},
                      'conj': w['comms'].get('conjunctions', {}).get('spans'), 'members': w['uncertainty'],
                      'sweep': w['mast_sweep'], 'seasons': w['seasons_and_energy']['per_season'],
                      'physics': w['physics_checks'], 'data': w['data_checks'], 'range': b['skyline']['curvature_limit'],
                      'n_trunc': b['skyline']['n_truncated'], 'frame': b['frame']['horizons_longitude_offset_deg'],
                      'checks': b['validation_status']['checks'], 'timing': w['timing_s']}, indent=1, default=str))


if __name__ == '__main__':
    main()
