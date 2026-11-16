"""Phase 5 energy cube per site. Label: ENGINEERING ASSUMPTION (assumptions in science/energy/assumptions.yaml).

  python -m science.energy.build_energy [site ...]      (default: site04_roi3 site01_roi6)

Inputs (no new skylines): data/cubes/<site>/disc_fraction_hourly.json.gz (Sun visible disc fraction,
T(21) x D_mast(10) x H(9097), per-mille) and the cached 12-month JPL Horizons ephemeris
(science/cube/ephem_year.load: Sun az/el/range).

Output data/cubes/<site>/energy.json.gz:   T(21) x D_array(2) x D_mast(10) x S(366 daily 14-day window starts)
  battery_needed_kwh     capacity so SoC >= reserve at every sample of the window (bisection, 1 Wh)
  min_soc_pct            minimum SoC over the window at the configured capacity
  hours_below_reserve_h  hours with SoC < reserve at the configured capacity
  mean_power_w           mean array power over the window
derived: band_over_T, battery_for_k_maps (capacity so >= k of 20 clone maps pass), pass_at_capacity (k of 20 at
the configured capacity), trade (mast height vs battery needed: nominal / worst of 20, demo start / worst start).
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import sys

import numpy as np

from . import model as M
from ..cube import compute as C
from ..cube import ephem_year as E
from ..cube.build_cube import NOT_PROB, OUT, _dims, _gz, _provenance, site_inputs
from ..cube.build_visibility import add_to_index
from ..limits.common import sha256_file

DAILY = 24
METRIC_KEYS = ('battery_needed_kwh', 'min_soc_pct', 'hours_below_reserve_h', 'mean_power_w')


def load_inputs(site):
    """Sun disc fraction (T, D_mast, H) in [0, 1] plus the Sun and Earth ephemeris (Earth is never used by power)."""
    _, eph = site_inputs(site)
    p = OUT / site / 'disc_fraction_hourly.json.gz'
    cube = json.loads(gzip.decompress(p.read_bytes()))
    dims = {d['name']: d for d in cube['dims']}
    if [d['name'] for d in cube['dims']] != ['T', 'D_mast', 'H']:
        raise ValueError('unexpected disc-fraction dims')
    if list(dims['T']['values']) != list(C.T_IDS) or [float(m) for m in dims['D_mast']['values']] != list(C.MASTS):
        raise ValueError('disc-fraction T / D_mast axes differ from science/cube/compute')
    if not np.array_equal(np.asarray(dims['H']['values'], float), eph['t']):
        raise ValueError('disc-fraction hours differ from the cached ephemeris')
    m = cube['metrics']['sun_fraction']
    f = np.asarray(m['values'], float).reshape(len(C.T_IDS), len(C.MASTS), eph['t'].size) * m['scale']
    return {'sun_fraction': f, 'eph': eph, 'disc_path': p, 'disc_sha256': sha256_file(p)}


def hourly_power(inp, cfg, arrays=M.ARRAYS):
    """(T, A, D_mast, H) array power in W."""
    e = inp['eph']
    return np.stack([M.power_w(cfg, a, inp['sun_fraction'], e['sun_el'][None, None], e['sun_az'][None, None],
                               e['sun_range_au'][None, None]) for a in arrays], axis=1)


def compute(site, cfg, inp=None, starts=None):
    inp = inp or load_inputs(site)
    e = inp['eph']
    dt_h = float(cfg.get('timestep_h', 1.0))
    starts = np.arange(0, E.N_STARTS, DAILY) if starts is None else np.asarray(starts)
    P = hourly_power(inp, cfg)                                  # (T, A, Dm, H)
    L = M.load_w(cfg, e['t'])                                   # (H,)
    n = E.WINDOW_H                                              # 336 one-hour steps over 337 samples
    Lw = M.windows(L * dt_h, starts, n)                         # (S, n)
    cap = cfg['battery']['capacity_wh']
    shp = P.shape[:3] + (starts.size,)
    out = {k: np.zeros(shp) for k in ('need_wh', 'min_soc', 'hours_below', 'mean_w', 'ok')}
    for i in range(P.shape[0]):
        G = M.windows(P[i] * dt_h, starts, n)                  # (A, Dm, S, n)
        Lb = np.broadcast_to(Lw, G.shape)
        out['need_wh'][i] = M.capacity_needed(G, Lb, cfg)
        r = M.simulate(G, Lb, cap, cfg)
        out['min_soc'][i] = r['min_soc_frac']; out['hours_below'][i] = r['hours_below_reserve']; out['ok'][i] = r['ok']
        out['mean_w'][i] = G.mean(axis=-1) / dt_h
    out['starts'] = starts
    out['P'] = P
    return out, inp


def _m(units, label, values, prov, scale=None, decimals=0):
    d = {'units': units, 'label': label, 'dtype': 'int32', 'values': np.asarray(values).reshape(-1).astype(int).tolist(),
         'provenance': prov, 'decimals': decimals}
    if scale is not None:
        d['scale'] = scale
    return d


def _stored(out):
    return {'battery_needed_kwh': np.ceil(out['need_wh'] - 1e-9),               # Wh, sufficient side
            'min_soc_pct': np.floor(out['min_soc'] * 1000 + 1e-9),             # per-mille, conservative
            'hours_below_reserve_h': np.rint(out['hours_below']),
            'mean_power_w': np.rint(out['mean_w'])}


SPEC = {'battery_needed_kwh': ('kWh', 'Battery capacity needed (SoC ≥ reserve all window)', 0.001, 2,
                               'science/energy/model.capacity_needed (bisection, 1 Wh, stored Wh rounded up)'),
        'min_soc_pct': ('%', 'Minimum state of charge at the configured capacity', 0.1, 1,
                        'science/energy/model.simulate (stored per-mille, rounded down)'),
        'hours_below_reserve_h': ('h', 'Hours below reserve at the configured capacity', None, 0, 'science/energy/model.simulate'),
        'mean_power_w': ('W', 'Mean array power over the window', None, 0, 'science/energy/model.power_w')}


def build(site, cfg=None):
    cfg = cfg or M.load_config()
    out, inp = compute(site, cfg)
    e = inp['eph']
    st = _stored(out)
    A = {'name': 'D_array', 'kind': 'design', 'values': list(M.ARRAYS), 'units': '', 'nominal_index': 0,
         'label': 'Array type (vertical)',
         'value_labels': ['vertical single-axis Sun tracking (VSAT-style)',
                          f'fixed vertical, normal at azimuth {cfg["array"]["fixed_azimuth_deg"]:g}°'],
         'note': 'cos(incidence) = cos(el) for tracking; max(0, cos(el) cos(az - phi)) for fixed'}
    T, Dm, S = _dims(e, {'name': 'D_mast', 'kind': 'design', 'values': list(C.MASTS), 'units': 'm', 'nominal_index': 0,
                         'label': 'Array top height above ground (mast)'}, DAILY)
    metrics = {k: _m(SPEC[k][0], SPEC[k][1], st[k], SPEC[k][4], SPEC[k][2], SPEC[k][3]) for k in METRIC_KEYS}
    band = {}
    for k in METRIC_KEYS:
        u, lab, sc, dec, _ = SPEC[k]
        for agg, fn in (('min', np.min), ('max', np.max)):
            band[f'{k}_{agg}'] = _m(u, f'{lab}: {agg} over T (21 maps)', fn(st[k], axis=0), 'min/max over T of the parent metric', sc, dec)
    need = st['battery_needed_kwh']                             # (T, A, Dm, S) Wh
    clones_sorted = np.sort(need[1:], axis=0)                  # (20, A, Dm, S)
    K = {'name': 'K', 'kind': 'requirement', 'values': list(range(1, 21)), 'units': 'maps of 20', 'nominal_index': 19,
         'label': 'Clone maps that must pass (k of 20)', 'note': NOT_PROB}
    ok = out['ok'].astype(bool)
    worst_s = need.max(axis=3)                                 # (T, A, Dm)
    argw = need.max(axis=0).argmax(axis=-1)                   # (A, Dm) start index of the worst of 21 maps
    trade = {
        'nominal_demo_kwh': _m('kWh', 'Battery needed, nominal map, 2026-11-14 start', need[0, :, :, 0], 'energy metric at S index 0', 0.001, 2),
        'worst20_demo_kwh': _m('kWh', 'Battery needed, worst of 20 clone maps, 2026-11-14 start', need[1:, :, :, 0].max(axis=0), 'max over clones at S index 0', 0.001, 2),
        'nominal_worst_start_kwh': _m('kWh', 'Battery needed, nominal map, worst of 366 daily starts', worst_s[0], 'max over S, nominal', 0.001, 2),
        'worst20_worst_start_kwh': _m('kWh', 'Battery needed, worst of 20 clone maps and 366 daily starts', worst_s[1:].max(axis=0), 'max over clones and S', 0.001, 2),
        'worst_start_index': _m('index', 'Daily start (S index) giving the worst battery need over all 21 maps', argw, 'argmax over S of max over T'),
    }
    b, ld = cfg['battery'], cfg['load']
    sched = '; '.join(f"{s['name']} {s['power_w']:g} W {int(s['utc_hour_start']):02d}:00+{s['duration_h']:g} h UTC daily"
                      for s in ld.get('scheduled') or [])
    fixed = {'position': 'bundle site', 'window_h': E.WINDOW_H, 'timestep_h': cfg.get('timestep_h', 1.0),
             'solar_constant_w_m2': cfg['solar_constant_w_m2'], 'array_area_m2': cfg['array']['area_m2'],
             'array_efficiency': cfg['array']['efficiency'], 'fixed_azimuth_deg': cfg['array']['fixed_azimuth_deg'],
             'battery_capacity_wh': b['capacity_wh'], 'charge_efficiency': b['charge_efficiency'],
             'discharge_efficiency': b['discharge_efficiency'], 'reserve_wh': b['reserve_wh'], 'initial_soc': b['initial_soc'],
             'load_constant_w': ld['constant_w'], 'load_scheduled': sched or 'none',
             'assumptions_file': 'science/energy/assumptions.yaml', 'label': M.LABEL}
    cfg_path = M.DEFAULT_CONFIG
    prov = _provenance(site, e, [
        {'path': str(inp['disc_path'].relative_to(OUT.parents[1])), 'sha256': inp['disc_sha256'], 'note': 'Sun visible disc fraction (per-mille)'},
        {'path': str(cfg_path.relative_to(OUT.parents[1])), 'sha256': sha256_file(cfg_path), 'note': 'ENGINEERING ASSUMPTION parameters'}])
    prov['command'] = 'python -m science.energy.build_energy ' + ' '.join(sys.argv[1:])
    prov['solver'] = 'science/energy/model (hourly sample-and-hold SoC; bisection for capacity)'
    cube = {'schema': 'scenario-cube-v1', 'cube_id': f'{site}-energy-v1', 'site_id': site,
            'title': 'Energy margin: map x array x mast x daily start (ENGINEERING ASSUMPTION)', 'label': M.LABEL,
            'generated_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'description': ('P = S0 (1 au / r)^2 x A x eta x f_disc x cos(incidence) at the mast top, battery SoC through each '
                            '14-day window; geometry SOURCE-BASED · UNVALIDATED, energy ENGINEERING ASSUMPTION.'),
            'fixed': fixed, 'dims': [T, A, Dm, S], 'metrics': metrics,
            'missing': {'encoding': 'sparse-flat-index', 'by_metric': {k: [] for k in METRIC_KEYS}},
            'derived': {
                'band_over_T': {'dims': ['D_array', 'D_mast', 'S'], 'metrics': band,
                                'method': 'element-wise min and max over T (nominal + 20 clones)',
                                'caveat': 'range over 21 deterministic maps, not a confidence interval'},
                'battery_for_k_maps': {'dims': [K, 'D_array', 'D_mast', 'S'], 'metrics': {
                    'battery_kwh': _m('kWh', 'Battery needed so at least k of 20 clone maps keep SoC ≥ reserve', clones_sorted,
                                      'k-th smallest clone value of battery_needed_kwh', 0.001, 2)},
                    'method': 'sort the 20 clone values per cell; k = 20 is the worst of 20', 'caveat': NOT_PROB},
                'pass_at_capacity': {'dims': ['D_array', 'D_mast', 'S'], 'metrics': {
                    'k_pass': _m('maps of 20', 'Clone maps keeping SoC ≥ reserve at the configured capacity', ok[1:].sum(axis=0), 'count over clones'),
                    'nominal_pass': {'units': '', 'label': 'Nominal map keeps SoC ≥ reserve at the configured capacity', 'dtype': 'bool',
                                     'values': ok[0].reshape(-1).astype(bool).tolist(), 'provenance': 'nominal map'}},
                    'method': f'SoC ≥ {b["reserve_wh"]:g} Wh at every hourly sample with a {b["capacity_wh"]:g} Wh battery', 'caveat': NOT_PROB},
                'trade': {'dims': ['D_array', 'D_mast'], 'metrics': trade,
                          'method': 'mast height vs battery capacity needed; worst = max over the named set',
                          'caveat': 'ENGINEERING ASSUMPTION; ' + NOT_PROB},
            },
            'provenance': prov,
            'limitations': [
                'ENGINEERING ASSUMPTION: array area, efficiency, load and battery parameters are illustrative, not a mission design.',
                'Power uses only the Sun: visible disc fraction (flat local horizon, uniform disc, no limb darkening), Horizons range and elevation.',
                'No thermal, dust, degradation, shadowing by the lander/mast, or regolith-reflected light.',
                'Hourly sample-and-hold; events shorter than an hour are not resolved.',
                'Geometry is SOURCE-BASED · UNVALIDATED; not certified illumination or power.', NOT_PROB]}
    return cube, out


def write(site, cfg=None):
    cube, out = build(site, cfg)
    p = OUT / site / 'energy.json.gz'
    raw = _gz(p, cube)
    add_to_index(site, [{'file': 'energy.json.gz', 'cube_id': cube['cube_id'], 'title': cube['title'], 'bytes': p.stat().st_size,
                         'uncompressed_bytes': raw, 'sha256': sha256_file(p), 'dims': [d['name'] for d in cube['dims']]}])
    return cube


def headline(cube):
    tr = cube['derived']['trade']['metrics']
    nM = len(C.MASTS)
    rows = {}
    for a, arr in enumerate(M.ARRAYS):
        for mast in (1, 5, 10):
            j = C.MASTS.index(float(mast))
            g = lambda k: round(tr[k]['values'][a * nM + j] / 1000, 2)
            rows[f'{arr} {mast} m'] = {k: g(k) for k in ('nominal_demo_kwh', 'worst20_demo_kwh', 'nominal_worst_start_kwh', 'worst20_worst_start_kwh')}
    return rows


if __name__ == '__main__':
    for s in sys.argv[1:] or ['site04_roi3', 'site01_roi6']:
        c = write(s)
        print(s, json.dumps(headline(c), indent=1))
