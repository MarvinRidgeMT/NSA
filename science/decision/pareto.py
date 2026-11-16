"""Pareto view over the 81 positions of the ±100 m grid (docs/v2/PHASE_3_DECISION_PLAN.md §4).

  python -m science.decision.pareto [site ...]     -> data/cache/decision/<site>_pareto.json (then rerun build)

Axes (each stored as nominal map, min and max over T = nominal + 20 PGDA 78 clones):
  sun_12mo     Sun centre visible, mean of the 14-day window % over 366 daily starts (position_schedule)   max
  earth_12mo   Earth centre visible, same (geometric line of sight; the link cube exists only at the centre)  max
  slope        landing slope, 100 m plane fit at the cell centre (terrain_safety)                              min
  energy       share of the 366 daily start dates (12 months) on which the assumed 10 kWh battery holds the 20 %
               reserve over the 14-day window (battery needed <= capacity). NEW numbers: the Phase 5 energy model
               (science/energy/model.py, same assumptions YAML, VSAT array, 1 m mast) run on hourly Sun disc
               fractions at each position from the cached full-solver skylines. ENGINEERING ASSUMPTION. A share of
               start dates, not a probability. The worst-window margin (10 kWh - battery needed) is stored too
               (`energy_worst_margin_kwh`) but is not a front axis: at both sites some 14-day windows are fully dark,
               so it sits at the zero-generation bound for most positions and does not separate them.
  distance to ice: NOT AVAILABLE (no cited M3 / LAMP / Diviner layer in $POLARIS_DATA).
Check: at the centre (0, 0) the energy recomputation equals the committed energy.json.gz (vsat, 1 m) for every map.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

from ..cube import compute as C
from ..cube import ephem_year as E
from ..cube.build_cube import site_inputs
from ..cube.build_visibility import disc_fraction_flat
from ..energy import model as M
from . import questions as Q

ROOT = Q.ROOT
RUNS = ROOT / 'data' / 'cache' / 'decision'
DAILY = 24
AXES = {
    'sun_12mo': {'sense': 'max', 'units': '%', 'label': 'Sun centre visible (12-month mean of 14-day window %)',
                 'source': 'position_schedule.json.gz sun_pct, mean over 366 daily starts', 'tag': Q.GEOMETRY},
    'earth_12mo': {'sense': 'max', 'units': '%',
                   'label': 'Earth centre visible (12-month mean; geometric line of sight, not a link budget)',
                   'source': 'position_schedule.json.gz earth_pct, mean over 366 daily starts', 'tag': Q.GEOMETRY},
    'slope': {'sense': 'min', 'units': 'deg', 'label': 'Landing slope (100 m plane fit)',
              'source': 'terrain_safety.json landing_slope_100m', 'tag': Q.GEOMETRY},
    'energy': {'sense': 'max', 'units': '%',
               'label': 'Energy: share of 366 daily starts on which the assumed 10 kWh battery holds the reserve',
               'source': 'science/energy/model.py on hourly Sun disc fractions per position (new; this run)',
               'tag': Q.ENGINEERING},
}
NOT_AVAILABLE = {'distance_to_ice': 'No cited public ice layer (LRO LAMP, Diviner, Chandrayaan-1 M3) is in $POLARIS_DATA; '
                                    'not downloaded in this phase, so the axis is not shown.'}


def _site_disc(site, eph):
    """(T, P, H) Sun disc fraction at mast 1 m per position, per-mille-rounded as the committed disc cube; plus the
    transferred Sun elevation per position (P, H)."""
    s = C.sites.SITES[site]
    nT, nP, nH = len(C.T_IDS), len(C.OFFSETS), eph['t'].size
    f = np.zeros((nT, nP, nH), np.float64)
    el = np.zeros((nP, nH))
    for j, (dx, dy) in enumerate(C.OFFSETS):
        if (dx, dy) == (0, 0):
            az, e = eph['sun_az'], eph['sun_el']
        else:
            la, lo = C.offset_latlon(site, dx, dy)
            az, e = C.transfer_azel(eph['sun_az'], eph['sun_el'], s['lat'], s['lon'], la, lo)
        el[j] = e
        for i, t_id in enumerate(C.T_IDS):
            sky = C.skyline(site, t_id, 1.0, dx, dy)
            m, _ = C.margins_vec(az, e, sky)
            fd = disc_fraction_flat(m, eph['sun_r'])
            f[i, j] = np.rint(np.nan_to_num(fd, nan=0.0) * 1000) / 1000.0
    return f, el


def energy_by_position(site, cfg=None):
    """battery needed (Wh) for every daily start: (T, P, S) and the min over starts of ... (vsat, mast 1 m)."""
    cfg = cfg or M.load_config()
    _b, eph = site_inputs(site)
    f, el = _site_disc(site, eph)
    P = M.power_w(eph['sun_range_au'], el[None], None, f, cfg.area_m2, cfg.efficiency, 'vsat')
    e_gen = M.interval_energy_wh(P)
    e_load = M.load_w(eph['t'][:-1], cfg) * 1.0
    starts = np.arange(0, E.N_STARTS, DAILY)
    n = E.WINDOW_H
    step = M.window_stepper(e_gen, e_load, starts)
    c = np.cumsum(np.concatenate([[0.0], e_load]))
    load_tot = np.broadcast_to(c[starts + n] - c[starts], e_gen.shape[:-1] + (starts.size,))
    need = M.round_up(M.battery_needed(bat=cfg.battery, n_steps=n, step=step, load_total_wh=load_tot))
    return need, cfg


def _cube_axis(site, file, metric, reduce_s):
    cube, sha = Q.load(site, file)
    names = [d['name'] for d in cube['dims']]
    sizes = [len(d['values']) for d in cube['dims']]
    m = cube['metrics'][metric]
    a = np.array([np.nan if v is None else v for v in m['values']], float).reshape(sizes) * m.get('scale', 1.0)
    if reduce_s:
        a = a.mean(axis=names.index('S'))
    assert a.shape == (len(C.T_IDS), len(C.OFFSETS)), a.shape
    return a, sha


def pareto_front(pts: np.ndarray, senses) -> np.ndarray:
    """Boolean mask of non-dominated rows. pts (N, K); senses 'max'/'min' per column. Equal points are all kept."""
    s = np.array([1.0 if x == 'max' else -1.0 for x in senses])
    u = pts * s
    n = len(u)
    keep = np.ones(n, bool)
    for i in range(n):
        ge = (u >= u[i] - 1e-12).all(axis=1)
        gt = (u > u[i] + 1e-12).any(axis=1)
        if (ge & gt).any():
            keep[i] = False
    return keep


def run(site):
    vals, shas = {}, {}
    vals['sun_12mo'], shas['position_schedule.json.gz'] = _cube_axis(site, 'position_schedule.json.gz', 'sun_pct', True)
    vals['earth_12mo'], _ = _cube_axis(site, 'position_schedule.json.gz', 'earth_pct', True)
    vals['slope'], shas['terrain_safety.json'] = _cube_axis(site, 'terrain_safety.json', 'landing_slope_100m', False)
    need, cfg = energy_by_position(site)                                   # (T, P, S) Wh
    cap = cfg.battery.capacity_wh
    vals['energy'] = 100.0 * (need <= cap).mean(axis=-1)
    worst_margin = (cap - need.max(axis=-1)) / 1000.0
    # centre check against the committed energy cube (vsat, mast 1 m, every map and start)
    ecube, esha = Q.load(site, 'energy.json.gz')
    shas['energy.json.gz'] = esha
    dims = [d['name'] for d in ecube['dims']]
    em = ecube['metrics']['battery_needed_kwh']
    ea = np.array(em['values'], float).reshape([len(d['values']) for d in ecube['dims']])
    committed = ea[:, 0, 0, :]                                             # (T, S) stored Wh, vsat, 1 m
    centre = C.OFFSETS.index((0, 0))
    diff = np.abs(need[:, centre, :] - committed)
    check = {'max_abs_diff_wh': float(diff.max()), 'n_cells': int(diff.size), 'dims': dims,
             'passes': bool(diff.max() == 0)}
    out = {'site': site, 'generated_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
           'positions': [f'{dx},{dy}' for dx, dy in C.OFFSETS], 't_ids': list(C.T_IDS), 'axes': AXES,
           'not_available': NOT_AVAILABLE, 'battery_capacity_wh': cap, 'assumptions_file': cfg.source,
           'values': {k: np.round(v, 6).tolist() for k, v in vals.items()},
           'battery_needed_demo_wh': need[:, :, 0].tolist(), 'energy_worst_margin_kwh': np.round(worst_margin, 6).tolist(),
           'energy_centre_check': check, 'input_sha256': shas}
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / f'{site}_pareto.json').write_text(json.dumps(out))
    return out


def analyse(run_: dict) -> dict:
    keys = list(AXES)
    senses = [AXES[k]['sense'] for k in keys]
    V = {k: np.array(run_['values'][k], float) for k in keys}              # (T, P)
    nom = np.stack([V[k][0] for k in keys], axis=1)
    worst = np.stack([V[k].min(axis=0) if AXES[k]['sense'] == 'max' else V[k].max(axis=0) for k in keys], axis=1)
    return {'keys': keys, 'senses': senses, 'V': V, 'front_nominal': pareto_front(nom, senses),
            'front_robust': pareto_front(worst, senses)}


def to_blocks(site, run_):
    from .build import inline_dim, metric
    a = analyse(run_)
    P = inline_dim('L', 'design', 'decision', run_['positions'], [f'{p} m (east, north)' for p in run_['positions']],
                   'What we choose: position in the ±100 m square (1 m mast)', units='m', nominal=C.OFFSETS.index((0, 0)))
    ms = {}
    for k in a['keys']:
        ax = AXES[k]; v = a['V'][k]
        prov = f'{ax["source"]} [{ax["tag"]}]'
        ms[f'{k}_nominal'] = metric(ax['units'], f'{ax["label"]}: nominal map', np.round(v[0], 4).tolist(), prov, decimals=2)
        ms[f'{k}_min'] = metric(ax['units'], f'{ax["label"]}: min over T (21 maps)', np.round(v.min(0), 4).tolist(), prov, decimals=2)
        ms[f'{k}_max'] = metric(ax['units'], f'{ax["label"]}: max over T (21 maps)', np.round(v.max(0), 4).tolist(), prov, decimals=2)
    wm = np.array(run_['energy_worst_margin_kwh'], float)
    ms['energy_worst_margin_kwh_nominal'] = metric(
        'kWh', 'Energy margin in the worst 14-day window of 12 months (10 kWh minus battery needed): nominal map',
        np.round(wm[0], 4).tolist(), f'science/energy/model.py [{Q.ENGINEERING}]; not a front axis (saturates at the '
        'zero-generation bound where a window is fully dark)', decimals=2)
    ms['energy_worst_margin_kwh_min'] = metric('kWh', 'Same: min over T (21 maps)', np.round(wm.min(0), 4).tolist(),
                                               f'science/energy/model.py [{Q.ENGINEERING}]', decimals=2)
    ms['on_front_nominal'] = metric('', 'Not dominated on the nominal map', a['front_nominal'].tolist(),
                                    'science/decision/pareto.py pareto_front', dtype='bool')
    ms['on_front_robust'] = metric('', 'Not dominated on the worst-over-T value of every axis', a['front_robust'].tolist(),
                                   'science/decision/pareto.py pareto_front', dtype='bool')
    axes_meta = {k: {**AXES[k]} for k in a['keys']}
    block = {'dims': [P], 'metrics': ms, 'method': (
        'Pareto (non-dominated) sets over the 81 positions on four axes: ' +
        '; '.join(f'{k} ({AXES[k]["sense"]}, {AXES[k]["tag"]}): {AXES[k]["source"]}' for k in a['keys']) +
        '. Robust front uses the worst of the 21 maps on each axis separately (a conservative corner, not a joint '
        f'member). Axis metadata: {json.dumps(axes_meta, ensure_ascii=False)}. Not available: '
        f'{json.dumps(NOT_AVAILABLE, ensure_ascii=False)}. Energy centre check vs energy.json.gz: '
        f'{json.dumps(run_["energy_centre_check"])}'),
        'caveat': ('Ranges are over 21 deterministic maps, not confidence intervals; k of N maps is not a probability. '
                   'Energy margin is an ENGINEERING ASSUMPTION (illustrative array, battery, load). Earth visibility is '
                   'geometric line of sight, not link availability.')}
    summary = {'n_positions': len(run_['positions']), 'n_front_nominal': int(a['front_nominal'].sum()),
               'n_front_robust': int(a['front_robust'].sum()),
               'energy_centre_check_passes': run_['energy_centre_check']['passes']}
    return {'blocks': {'pareto__positions': block}, 'summary': summary}


if __name__ == '__main__':
    for s in sys.argv[1:] or ['site04_roi3', 'site01_roi6']:
        r = run(s)
        a = analyse(r)
        print(s, 'energy centre check', r['energy_centre_check'], 'front nominal', int(a['front_nominal'].sum()),
              'robust', int(a['front_robust'].sum()))
