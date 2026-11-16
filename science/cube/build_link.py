"""Phase 4 — link-target cube: who can the site talk to? ENGINEERING ASSUMPTION (geometry only).

  python -m science.cube.build_link [site ...]

Targets (hourly booleans, per terrain map T and mast D_mast), with elevation margin x in R_margin = {0, 2, 5} deg
above the local terrain skyline for every link target (low-elevation multipath):
  sun                 Sun centre above terrain (not a link; margin not applied)
  earth_centre        Earth centre margin > x
  earth_any_limb      upper limb of Earth above terrain + x  (m_perp + r > x)
  earth_dsn           earth_centre AND >= 1 DSN complex sees the Moon at >= 10 deg (science/cube/link_dsn.py)
  relay_1, relay_2    LCRNS reference SV-1 / SV-2 above terrain + x AND that relay sees Earth (not occulted by the
                      Moon) AND >= 1 DSN complex sees the Moon
  relay_any           any of SV-1..SV-5 as above
  dte_or_relay        earth_dsn OR relay_any
  dte_plus_1_relay    earth_dsn OR the single relay that maximises nominal 1 m 12-month availability (chosen once per site)
  dte_plus_2_relays   earth_dsn OR the best pair chosen the same way
Relays: science/cube/link_relay.py (NASA LCRNS Reference Constellation 3.1 states; reduced force model; reference
constellation, not an operational schedule). No link budget, scheduling or outages.

Outputs data/cubes/<site>/link.json.gz: T(21) x D_mast(10) x target(10) x R_margin(3) x S(366 daily starts), metrics
link-available % and longest link gap; derived year_summary (first 8760 h) and model_sensitivity (J2 / Sun terms).
"""
from __future__ import annotations

import datetime as dt
import itertools
import json
import sys
from pathlib import Path

import numpy as np

from . import compute as C
from . import ephem_year as E
from . import link_dsn as DSN
from . import link_relay as LR
from .build_cube import LABEL, NOT_PROB, OUT, _dims, _gz, _provenance, site_inputs
from .build_visibility import add_to_index
from .. import horizons as H
from ..limits.common import sha256_file

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / 'data' / 'cache' / 'cube_link'
EA = 'ENGINEERING ASSUMPTION — reference constellation, not an operational schedule'
TARGETS = ('sun', 'earth_centre', 'earth_any_limb', 'earth_dsn', 'relay_1', 'relay_2', 'relay_any', 'dte_or_relay',
           'dte_plus_1_relay', 'dte_plus_2_relays')
MARGINS = (0.0, 2.0, 5.0)
SVS = tuple(LR.PAPER['states'])
DAILY = 24
YEAR_H = 8760


def relay_states(t, earth, sun, pole, model='full'):
    """Moon-centred ICRF states (n_sv, T, 6) for one force model, cached per model."""
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f'relays_{model}.npz'
    if p.exists():
        z = np.load(p)
        if np.array_equal(z['t'], t):
            return z['Y']
    t0 = H.iso_to_unix(LR.EPOCH_UTC)
    j2 = 0.0 if model == 'no_j2' else LR.J2_MOON
    sb = None if model == 'no_sun' else sun
    Y = np.array([LR.propagate(LR.PAPER['states'][sv], t0, t, earth, sb, pole, j2=j2) for sv in SVS])
    np.savez(p, t=t, Y=Y)
    return Y


def geometry(site, eph):
    """Site frame, site position, relay az/el and relay->Earth line of sight for each force model."""
    s = C.sites.SITES[site]
    b, _ = site_inputs(site)
    loc = (b['site']['lat_deg'], b['site']['lon_deg_east'], b['site']['height_m'])
    R, prov = LR.site_frame(site, loc, eph)
    from .. import frames
    e, n, u = frames.enu_basis(loc[0], loc[1])
    ME = np.einsum('ij,tjk->tik', np.array([e, n, u]).T, R)
    t = eph['t']
    _, ve, pe = LR.vectors('399', '500@301', corr='NONE', tag='moon_earth_vec_year_20261114')
    _, vs, ps = LR.vectors('10', '500@301', corr='NONE', tag='moon_sun_vec_year_20261114')
    earth, sun, pole = LR.Hermite(t, ve), LR.Hermite(t, vs), LR.PoleInterp(t, ME[:, 2, :])
    r_site = (LR.R_MOON_KM + loc[2] / 1000.0) * R[:, 2, :]
    out = {}
    for model in ('full', 'no_j2', 'no_sun'):
        Y = relay_states(t, earth, sun, pole, model)
        az, el, los = [], [], []
        for k in range(len(SVS)):
            a, e_, _ = LR.relay_azel(R, r_site, Y[k, :, :3]); az.append(a); el.append(e_)
            los.append(~LR.occulted_by_moon(Y[k, :, :3], ve[:, :3]))
        out[model] = {'az': np.array(az), 'el': np.array(el), 'sees_earth': np.array(los), 'Y': Y}
    return out, prov + [pe, ps], loc


def hourly_targets(eph, sky, geo, dsn_any, margin, best1, best2):
    m_e, mp_e = C.margins_vec(eph['earth_az'], eph['earth_el'], sky)
    _, mp_s = C.margins_vec(eph['sun_az'], eph['sun_el'], sky)
    mp_e = np.nan_to_num(mp_e, nan=-1e9); mp_s = np.nan_to_num(mp_s, nan=-1e9)
    relay = []
    for k in range(len(SVS)):
        _, mp_r = C.margins_vec(geo['az'][k], geo['el'][k], sky)
        relay.append((np.nan_to_num(mp_r, nan=-1e9) > margin) & geo['sees_earth'][k] & dsn_any)
    relay = np.array(relay)
    earth_c = mp_e > margin
    edsn = earth_c & dsn_any
    out = {'sun': mp_s > 0, 'earth_centre': earth_c, 'earth_any_limb': (mp_e + eph['earth_r']) > margin,
           'earth_dsn': edsn, 'relay_1': relay[0], 'relay_2': relay[1], 'relay_any': relay.any(axis=0),
           'dte_or_relay': edsn | relay.any(axis=0)}
    out['dte_plus_1_relay'] = edsn | relay[best1]
    out['dte_plus_2_relays'] = edsn | relay[list(best2)].any(axis=0)
    return out, relay


def choose_relays(eph, sky, geo, dsn_any):
    """Best single relay and best pair on the nominal map, 1 m, margin 0, first 8760 h (fixed per site)."""
    _, relay = hourly_targets(eph, sky, geo, dsn_any, 0.0, 0, (0, 1))
    m_e, mp_e = C.margins_vec(eph['earth_az'], eph['earth_el'], sky)
    edsn = (np.nan_to_num(mp_e, nan=-1e9) > 0) & dsn_any
    sl = slice(0, YEAR_H)
    best1 = int(np.argmax([(edsn | relay[k])[sl].mean() for k in range(len(SVS))]))
    pairs = list(itertools.combinations(range(len(SVS)), 2))
    best2 = max(pairs, key=lambda pq: (edsn | relay[pq[0]] | relay[pq[1]])[sl].mean())
    return best1, best2


def _longest(f):
    idx = np.arange(f.size)
    return int((idx - np.maximum.accumulate(np.where(f, idx, -1))).max()) if f.size else 0


def build(site):
    b, eph = site_inputs(site)
    dsn, t_dsn, dsn_prov = DSN.complexes()
    assert np.array_equal(t_dsn, eph['t'])
    geo_all, frame_prov, loc = geometry(site, eph)
    geo = geo_all['full']
    sky_nom = C.skyline(site, 'nominal', 1.0)
    best1, best2 = choose_relays(eph, sky_nom, geo, dsn['any'])
    nT, nM, nX, nR = len(C.T_IDS), len(C.MASTS), len(TARGETS), len(MARGINS)
    starts = np.arange(0, E.N_STARTS, DAILY)
    avail = np.zeros((nT, nM, nX, nR, starts.size), np.int32); gap = np.zeros_like(avail)
    y_pct = np.zeros((nT, nM, nX, nR)); y_gap = np.zeros((nT, nM, nX, nR), np.int32)
    for i, t_id in enumerate(C.T_IDS):
        for j, mast in enumerate(C.MASTS):
            sky = C.skyline(site, t_id, mast)
            for r, x in enumerate(MARGINS):
                tg, _ = hourly_targets(eph, sky, geo, dsn['any'], x, best1, best2)
                for k, name in enumerate(TARGETS):
                    f = tg[name]
                    w = C.window_metrics(f, f, E.N_STARTS, E.WINDOW_H, DAILY)
                    avail[i, j, k, r] = w['sun_n']; gap[i, j, k, r] = w['sun_gap_h']
                    y_pct[i, j, k, r] = 100.0 * f[:YEAR_H].mean(); y_gap[i, j, k, r] = _longest(f[:YEAR_H])
    # model sensitivity: nominal map, 1 m, margin 0, year availability of the relay targets per force model
    sens = {}
    for model, g in geo_all.items():
        tg, _ = hourly_targets(eph, sky_nom, g, dsn['any'], 0.0, best1, best2)
        sens[model] = {k: round(100.0 * tg[k][:YEAR_H].mean(), 3) for k in ('relay_1', 'relay_2', 'relay_any', 'dte_plus_1_relay', 'dte_plus_2_relays')}
    # NASA sanity check: pure line of sight (no DSN requirement), nominal map, 1 m, 12 months
    ones = np.ones(eph['t'].size, bool); sl = slice(0, YEAR_H); los = []
    for x in MARGINS:
        tg, relay = hourly_targets(eph, sky_nom, geo, ones, x, best1, best2)
        e_ = tg['earth_centre']
        b1 = max((e_ | relay[k])[sl].mean() for k in range(len(SVS)))
        b2 = max((e_ | relay[p_] | relay[q])[sl].mean() for p_, q in itertools.combinations(range(len(SVS)), 2))
        los += [round(100 * float(e_[sl].mean()), 2), round(100 * float(b1), 2), round(100 * float(b2), 2)]
    n = E.WINDOW_H + 1
    T, Dm, S = _dims(eph, {'name': 'D_mast', 'kind': 'design', 'values': list(C.MASTS), 'units': 'm', 'nominal_index': 0,
                           'label': 'Antenna / observer height above ground (mast)'}, DAILY)
    X = {'name': 'target', 'kind': 'target', 'values': list(TARGETS), 'units': '', 'nominal_index': 3,
         'label': 'Link target', 'note': f'best single relay {SVS[best1]}, best pair {SVS[best2[0]]}+{SVS[best2[1]]} (nominal map, 1 m, 12 months)'}
    Rm = {'name': 'R_margin', 'kind': 'requirement', 'values': list(MARGINS), 'units': 'deg', 'nominal_index': 0,
          'label': 'Elevation margin above the terrain skyline (link targets; not applied to Sun)'}
    dims = [T, Dm, X, Rm, S]
    pct = lambda a: {'units': '%', 'label': 'Link available (14-d window)', 'dtype': 'int32', 'scale': 100.0 / n, 'decimals': 2,
                     'values': a.reshape(-1).astype(int).tolist(), 'provenance': 'hourly target flags, 337 samples per window'}
    now = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    year_dims = ['T', 'D_mast', 'target', 'R_margin']
    cube = {
        'schema': 'scenario-cube-v1', 'cube_id': f'{site}-link-v1', 'site_id': site,
        'title': 'Link targets: map x mast x target x margin x daily start', 'label': f'{LABEL} · {EA}',
        'generated_utc': now,
        'description': 'Geometric link availability to Earth, DSN and LCRNS reference relays (who can we talk to?).',
        'fixed': {'position': 'bundle site', 'window_h': E.WINDOW_H, 'dsn_station_mask_deg': DSN.MASK_DEG,
                  'relay_source': LR.PAPER['source'], 'relay_force_model': 'Moon point mass + J2 + Earth + Sun (DOP853, rtol 1e-11)'},
        'dims': dims,
        'metrics': {'available_pct': pct(avail),
                    'longest_gap_h': {'units': 'h', 'label': 'Longest link gap (hourly samples)', 'dtype': 'int32', 'decimals': 0,
                                      'values': gap.reshape(-1).astype(int).tolist(), 'provenance': 'runs of unavailable hourly samples x 1 h'}},
        'missing': {'encoding': 'sparse-flat-index', 'by_metric': {'available_pct': [], 'longest_gap_h': []}},
        'derived': {
            'year_summary': {'dims': year_dims, 'metrics': {
                'available_pct': {'units': '%', 'label': 'Link available, 12 months (8760 h)', 'dtype': 'float64', 'decimals': 2,
                                  'values': np.round(y_pct, 4).reshape(-1).tolist(), 'provenance': 'mean of hourly flags 2026-11-14 .. 2027-11-14'},
                'longest_gap_h': {'units': 'h', 'label': 'Longest link gap, 12 months', 'dtype': 'int32', 'decimals': 0,
                                  'values': y_gap.reshape(-1).astype(int).tolist(), 'provenance': 'longest run of unavailable hours'}},
                'method': 'first 8760 hourly samples', 'caveat': NOT_PROB},
            'model_sensitivity': {'dims': [{'name': 'model', 'kind': 'uncertainty_model', 'values': list(sens), 'units': '',
                                            'label': 'Relay force model', 'value_labels': ['point mass + J2 + Earth + Sun', 'without J2', 'without Sun']},
                                           {'name': 'link', 'kind': 'target', 'values': list(next(iter(sens.values()))), 'units': '', 'label': 'Link'}],
                                  'metrics': {'year_available_pct': {'units': '%', 'label': 'Nominal map, 1 m, 12 months', 'dtype': 'float64', 'decimals': 2,
                                                                     'values': [v for m in sens.values() for v in m.values()],
                                                                     'provenance': 'same pipeline with one force term removed'}},
                                  'method': 'sensitivity of the relay results to the reduced force model', 'caveat': 'NASA recommends GRGM-900c 25x25 + 6 point masses + SRP; not used here'},
            'nasa_sanity_check': {'dims': ['R_margin', {'name': 'link', 'kind': 'target', 'values': ['dte_only', 'dte_plus_1_relay', 'dte_plus_2_relays'],
                                                         'units': '', 'label': 'Line of sight only (no DSN requirement)'}],
                                  'metrics': {'year_los_pct': {'units': '%', 'label': 'Nominal map, 1 m, 12 months, line of sight only', 'dtype': 'float64', 'decimals': 2,
                                                               'values': los, 'provenance': 'same geometry with the DSN term set to always available'}},
                                  'method': 'compare with the NASA 10-year line-of-sight figures quoted in the 5D prompt: DTE ~17-43 %, +1 relay ~80-86 %, +2 relays 100 % (worst to best south-pole sites)',
                                  'caveat': 'NASA mask and site set not known here; two relays reach 100 % as NASA; DTE falls inside NASA range for a 2-5 deg margin; one relay is 88-89 % at 5 deg, slightly above NASA 80-86 % (best relay chosen per site, ridge sites)'},
        },
        'provenance': _provenance(site, eph, [{'path': p['path'], 'sha256': p['sha256'], 'url': p.get('url', H.API),
                                               'note': p.get('horizons_site_name', 'Horizons')} for p in dsn_prov + frame_prov]
                                  + [{'path': 'science/cube/link_relay.py (PAPER)', 'sha256': sha256_file(ROOT / 'science' / 'cube' / 'link_relay.py'),
                                      'url': LR.PAPER['url'], 'note': LR.PAPER['source'] + '; states at ' + LR.PAPER['epoch_utc']}]),
        'limitations': [EA, 'Geometry only: no link budget, scheduling, station downtime or relay availability.', NOT_PROB,
                        'Relay orbits propagated with a reduced force model; see model_sensitivity.',
                        'The site frame is fitted hourly from Horizons (Sun, Earth, Mars, Jupiter); checked on LRO to < 0.001 deg.'],
    }
    summary = {'best_single_relay': SVS[best1], 'best_pair': [SVS[best2[0]], SVS[best2[1]]], 'model_sensitivity': sens}
    return cube, summary


def write(site):
    cube, summary = build(site)
    p = OUT / site / 'link.json.gz'
    raw = _gz(p, cube)
    add_to_index(site, [{'file': p.name, 'cube_id': cube['cube_id'], 'title': cube['title'], 'bytes': p.stat().st_size,
                         'uncompressed_bytes': raw, 'sha256': sha256_file(p), 'dims': [d['name'] for d in cube['dims']]}])
    return cube, summary


def headline(cube):
    """Year availability (nominal map, margin 0) for DTE / +1 / +2 relays at 1 m and 5 m."""
    d = cube['derived']['year_summary']['metrics']['available_pct']['values']
    nM, nX, nR = len(C.MASTS), len(TARGETS), len(MARGINS)
    idx = lambda t, j, k, r: ((t * nM + j) * nX + k) * nR + r
    return {f'{m:g} m': {k: round(d[idx(0, C.MASTS.index(m), TARGETS.index(k), 0)], 2)
                         for k in ('earth_centre', 'earth_dsn', 'dte_plus_1_relay', 'dte_plus_2_relays', 'relay_any')}
            for m in (1.0, 5.0)}


if __name__ == '__main__':
    for s in sys.argv[1:] or ['site04_roi3', 'site01_roi6']:
        c, summ = write(s)
        print(s, json.dumps(summ), json.dumps(headline(c)))
