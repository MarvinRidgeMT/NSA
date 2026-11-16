"""Phase 5 — energy margin cube (ENGINEERING ASSUMPTION).

  python -m science.energy.build_energy [site ...]     (default: site04_roi3 site01_roi6)

Inputs (no new skylines):
  data/cubes/<site>/disc_fraction_hourly.json.gz   Sun visible disc fraction, T(21) x D_mast(10) x H(9097), per-mille
  data/cache/cube_horizons/<site>_year.npz         Sun range (au), elevation, azimuth (science/cube/ephem_year.load)
  science/energy/assumptions.yaml                  array, battery and load parameters (shown on screen)

Output data/cubes/<site>/energy.json.gz            T(21) x D_array(2) x D_mast(10) x S(366 daily starts, 14 d windows)
  metrics: min SoC (% of capacity), hours below reserve, battery needed (kWh), unserved energy (kWh), mean power (W)
  derived: band_over_T, k_of_N_capacity (clone maps on which the YAML capacity holds the reserve), trade (mast vs
           battery needed: nominal / worst of 20, demo start and every start), needed_by_k (k-th smallest over clones)
and appends it to data/cubes/<site>/index.json (science.cube.build_visibility.add_to_index).
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
from ..cube.build_cube import NOT_PROB, OUT, ROOT, _dims, _gz, _provenance, site_inputs
from ..cube.build_visibility import add_to_index
from ..limits.common import sha256_file

DAILY = 24
NOT_POWER_SPEC = ('ENGINEERING ASSUMPTION: illustrative array, battery and load numbers from '
                  'science/energy/assumptions.yaml; not a lander design, not certified power.')


def load_disc(site):
    p = OUT / site / 'disc_fraction_hourly.json.gz'
    c = json.loads(gzip.decompress(p.read_bytes()))
    sizes = [len(d['values']) for d in c['dims']]
    m = c['metrics']['sun_fraction']
    f = np.asarray(m['values'], float).reshape(sizes) * m['scale']
    masts = np.asarray(c['dims'][1]['values'], float)
    t = np.asarray(c['dims'][2]['values'], float)
    return f, masts, t, p


def site_series(site, cfg):
    """Hourly power for every map, array type and mast: (T, A, D_mast, H) W, plus metadata."""
    _b, eph = site_inputs(site)
    f, masts, t, p = load_disc(site)
    if not np.array_equal(t, eph['t']):
        raise ValueError('disc-fraction hours differ from the cached ephemeris')
    if not np.all(np.isfinite(eph['sun_range_au'])):
        raise ValueError('Sun range missing in ephemeris')
    az = cfg.fixed_azimuth_deg
    if az == 'auto':
        az = M.best_fixed_azimuth(eph['sun_range_au'], eph['sun_el'], eph['sun_az'], f[0, 0])
    P = np.stack([M.power_w(eph['sun_range_au'], eph['sun_el'], eph['sun_az'], f, cfg.area_m2, cfg.efficiency, a, az)
                  for a in M.ARRAY_TYPES], axis=1)
    return {'P': P, 'eph': eph, 'masts': masts, 't': t, 'disc_path': p, 'azimuth': float(az), 'f': f}


def run(site, cfg):
    s = site_series(site, cfg)
    e_gen = M.interval_energy_wh(s['P'])                 # (T, A, D, H-1)
    e_load = M.load_w(s['t'][:-1], cfg) * 1.0            # Wh per 1 h interval, by interval start
    starts = np.arange(0, E.N_STARTS, DAILY)
    n = E.WINDOW_H
    step = M.window_stepper(e_gen, e_load, starts)
    c = np.cumsum(np.concatenate([[0.0], e_load]))
    load_tot = np.broadcast_to(c[starts + n] - c[starts], e_gen.shape[:-1] + (starts.size,))
    led = M.simulate(None, None, cfg.battery.capacity_wh, cfg.battery, n_steps=n, step=step)
    need = M.battery_needed(bat=cfg.battery, n_steps=n, step=step, load_total_wh=load_tot)
    cg = np.cumsum(np.concatenate([np.zeros(e_gen.shape[:-1] + (1,)), e_gen], axis=-1), axis=-1)
    gen_mean = (cg[..., starts + n] - cg[..., starts]) / n
    return {'series': s, 'starts': starts, 'ledger': led, 'need_wh': need, 'gen_mean_w': gen_mean, 'load_tot': load_tot}


def _metric(units, label, values, prov, scale=None, decimals=0, description=None):
    m = {'units': units, 'label': label, 'dtype': 'int32', 'values': np.asarray(values).reshape(-1).astype(int).tolist(),
         'provenance': prov, 'decimals': decimals}
    if scale is not None:
        m['scale'] = scale
    if description:
        m['description'] = description
    return m


def build(site, cfg=None):
    cfg = cfg or M.load_config()
    r = run(site, cfg)
    s, led = r['series'], r['ledger']
    bat = cfg.battery
    prov = 'science/energy/model.py simulate / battery_needed on P = S·A·η·f_disc·cos(inc)'
    vals = {
        'min_soc_pct': np.rint(1000 * led['min_soc'] / bat.capacity_wh),
        'hours_below_reserve': led['hours_below_reserve'],
        'battery_needed_kwh': M.round_up(r['need_wh']),
        'unserved_kwh': np.rint(led['unserved']),
        'mean_power_w': np.rint(r['gen_mean_w']),
    }
    spec = {
        'min_soc_pct': ('%', f'Minimum state of charge with a {bat.capacity_wh / 1000:g} kWh battery', 0.1, 1,
                        'stored per-mille of capacity; display = stored x 0.1'),
        'hours_below_reserve': ('h', f'Hours below the {100 * bat.min_reserve_fraction:g} % reserve ({bat.capacity_wh / 1000:g} kWh battery)', None, 0, None),
        'battery_needed_kwh': ('kWh', 'Battery capacity needed to stay at or above the reserve', 0.001, 2,
                               'stored Wh (bisection, rounded up); display = stored x 0.001'),
        'unserved_kwh': ('kWh', f'Load not served with a {bat.capacity_wh / 1000:g} kWh battery', 0.001, 2, 'stored Wh'),
        'mean_power_w': ('W', 'Mean array power over the window', None, 0, None),
    }
    metrics = {k: _metric(u, lab, vals[k], prov, sc, dec, desc) for k, (u, lab, sc, dec, desc) in spec.items()}

    _b, eph = site_inputs(site)
    T, Dm, S = _dims(eph, {'name': 'D_mast', 'kind': 'design', 'values': [float(m) for m in s['masts']], 'units': 'm',
                           'nominal_index': 0, 'label': 'Array top height above ground (mast)',
                           'note': 'array top only; antenna height never enters the power model'}, DAILY)
    A = {'name': 'D_array', 'kind': 'design', 'values': list(M.ARRAY_TYPES), 'units': '', 'nominal_index': 0,
         'label': 'Array type',
         'value_labels': ['vertical Sun-tracking (VSAT-style)', f'fixed vertical, normal at {s["azimuth"]:g}° az']}

    clones = slice(1, None)
    ok = led['hours_below_reserve'] == 0                                   # (T, A, D, S)
    need = vals['battery_needed_kwh']
    band = {}
    for k, m in metrics.items():
        a = np.asarray(vals[k])
        for agg, fn in (('min', np.min), ('max', np.max)):
            band[f'{k}_{agg}'] = {**{kk: vv for kk, vv in m.items() if kk != 'values'},
                                  'label': f'{m["label"]}: {agg} over T (21 maps)',
                                  'values': fn(a, axis=0).reshape(-1).astype(int).tolist(),
                                  'provenance': 'min/max over the T axis of the parent cube'}
    kW = {'scale': 0.001, 'decimals': 2}
    K = {'name': 'K', 'kind': 'requirement', 'values': list(range(1, 21)), 'units': 'maps',
         'label': 'Battery must work on at least k of the 20 clone maps', 'nominal_index': 19}
    need_c = np.sort(need[clones], axis=0)                                 # (20, A, D, S) ascending
    need_c_all = np.sort(need[clones].max(axis=-1), axis=0)                # (20, A, D) per-clone max over starts
    derived = {
        'band_over_T': {'dims': ['D_array', 'D_mast', 'S'], 'metrics': band,
                        'method': 'element-wise min and max over T (nominal + 20 clones) of the parent metric',
                        'caveat': 'range over 21 deterministic maps, not a confidence interval'},
        'k_of_N_capacity': {
            'dims': ['D_array', 'D_mast', 'S'],
            'metrics': {
                'k_ok': _metric('maps', f'Clone maps (of 20) on which {bat.capacity_wh / 1000:g} kWh holds the reserve', ok[clones].sum(axis=0), 'count over T clones of hours_below_reserve == 0'),
                'nominal_ok': _metric('', 'Nominal map holds the reserve', ok[0], 'hours_below_reserve == 0 on the nominal map'),
            },
            'method': 'count of clone maps 1-20 with zero hours below reserve at the YAML capacity, per array x mast x start',
            'caveat': NOT_PROB},
        'trade': {
            'dims': ['D_array', 'D_mast'],
            'metrics': {
                'needed_demo_nominal': _metric('kWh', 'Battery needed, 2026-11-14 start, nominal map', need[0, ..., 0], 'battery_needed_kwh at S index 0', **kW),
                'needed_demo_worst20': _metric('kWh', 'Battery needed, 2026-11-14 start, worst of 20 clone maps', need[clones, ..., 0].max(axis=0), 'max over clones 1-20 at S index 0', **kW),
                'needed_all_nominal': _metric('kWh', 'Battery needed for every daily start (12 months), nominal map', need[0].max(axis=-1), 'max over S on the nominal map', **kW),
                'needed_all_worst20': _metric('kWh', 'Battery needed for every daily start, worst of 20 clone maps', need[clones].max(axis=(0, -1)), 'max over clones 1-20 and S', **kW),
                'k_ok_demo': _metric('maps', f'Clone maps (of 20) where {bat.capacity_wh / 1000:g} kWh holds the reserve, 2026-11-14 start', ok[clones, ..., 0].sum(axis=0), 'count'),
                'k_ok_all': _metric('maps', f'Clone maps (of 20) where {bat.capacity_wh / 1000:g} kWh holds the reserve for every start', ok[clones].all(axis=-1).sum(axis=0), 'count'),
                'share_starts_ok_all20': _metric('%', f'Starts where {bat.capacity_wh / 1000:g} kWh holds the reserve on all 20 clone maps', np.rint(1000 * ok[clones].all(axis=0).mean(axis=-1)), 'share of 366 daily starts; per-mille', 0.1, 1),
            },
            'method': 'mast height vs battery needed (bisection) for the demo start and the worst daily start over 12 months',
            'caveat': NOT_PROB + ' Battery sizes are ENGINEERING ASSUMPTION outputs of the YAML load and array.'},
        'needed_by_k': {
            'dims': ['D_array', 'D_mast', K],
            'metrics': {
                'needed_demo': _metric('kWh', 'Battery that works on at least k of 20 clone maps, 2026-11-14 start', np.moveaxis(need_c[..., 0], 0, -1), 'k-th smallest over clones 1-20 at S index 0', **kW),
                'needed_all': _metric('kWh', 'Battery that works on at least k of 20 clone maps for every daily start', np.moveaxis(need_c_all, 0, -1), 'k-th smallest over clones of the per-clone max over S', **kW),
            },
            'method': 'order statistic over the 20 clone maps of battery_needed_kwh',
            'caveat': NOT_PROB},
    }
    sched = '; '.join(f"{x['name']}: +{x['power_w']} W for {x['duration_h']} h from {x['start_utc_hour']}:00 UTC every {x['every_h']} h"
                      for x in cfg.scheduled) or 'none'
    fixed = {
        'label': M.LABEL, 'assumptions_file': cfg.source, 'position': 'bundle site', 'window_h': E.WINDOW_H,
        'solar_constant_w_m2': M.SOLAR_CONSTANT_W_M2, 'array_area_m2': cfg.area_m2, 'array_efficiency': cfg.efficiency,
        'fixed_array_azimuth_deg': s['azimuth'],
        'fixed_array_azimuth_rule': 'auto: best year-mean power on the nominal map at 1 m' if cfg.fixed_azimuth_deg == 'auto' else 'from YAML',
        'battery_capacity_wh': bat.capacity_wh, 'charge_efficiency': bat.charge_efficiency,
        'discharge_efficiency': bat.discharge_efficiency, 'min_reserve_fraction': bat.min_reserve_fraction,
        'initial_soc_fraction': bat.initial_soc_fraction, 'load_constant_w': cfg.constant_w, 'load_scheduled': sched,
        'antenna_height': 'not an input (power uses the array top only)',
    }
    extra = [{'path': str(s['disc_path'].relative_to(ROOT)), 'sha256': sha256_file(s['disc_path']),
              'note': 'Sun visible disc fraction per hour (Phase 3 cube)'},
             {'path': cfg.source, 'sha256': sha256_file(ROOT / cfg.source), 'note': 'ENGINEERING ASSUMPTION parameters'}]
    pv = _provenance(site, eph, extra)
    pv['command'] = 'python -m science.energy.build_energy ' + ' '.join(sys.argv[1:])
    pv['solver'] = 'science/energy/model.py (float64), hourly trapezoid energy, bisection 32 iterations'
    return {
        'schema': 'scenario-cube-v1', 'cube_id': f'{site}-energy-v1', 'site_id': site,
        'title': 'Energy margin: map x array x mast x daily start (ENGINEERING ASSUMPTION)', 'label': M.LABEL,
        'generated_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'description': ('Array power P = S·A·η·f_disc·cos(incidence) with S = 1361 W/m² × (1 au / r)², f_disc = visible Sun '
                        'disc fraction at the array top, and a battery state-of-charge simulation over each 14-day window. '
                        'Inputs are SOURCE-BASED · UNVALIDATED geometry; array, battery and load are ENGINEERING ASSUMPTION.'),
        'fixed': fixed, 'dims': [T, A, Dm, S], 'metrics': metrics,
        'missing': {'encoding': 'sparse-flat-index', 'by_metric': {k: [] for k in metrics}},
        'derived': derived, 'provenance': pv,
        'limitations': [NOT_POWER_SPEC, NOT_PROB,
                        'Each 14-day window starts at the initial state of charge; windows are independent.',
                        'Disc fraction uses the flat-local-horizon model, rounded to 0.001; no diffuse light, dust, '
                        'thermal derating, cell degradation or self-shadowing by the lander.',
                        'Local geometric visibility only; not certified illumination or power.']}


def write(site, cfg=None):
    cube = build(site, cfg)
    d = OUT / site
    name = 'energy.json.gz'
    raw = _gz(d / name, cube)
    add_to_index(site, [{'file': name, 'cube_id': cube['cube_id'], 'title': cube['title'], 'label': cube['label'],
                         'bytes': (d / name).stat().st_size, 'uncompressed_bytes': raw,
                         'sha256': sha256_file(d / name), 'dims': [x['name'] for x in cube['dims']]}])
    return cube


def summary(cube):
    tr = cube['derived']['trade']
    masts = cube['dims'][2]['values']
    arrays = cube['dims'][1]['values']
    out = {}
    for i, a in enumerate(arrays):
        for j, m in enumerate(masts):
            if m in (1.0, 5.0):
                f = i * len(masts) + j
                out[f'{a} {m:g} m'] = {k: tr['metrics'][k]['values'][f] / 1000 if 'needed' in k else tr['metrics'][k]['values'][f]
                                        for k in tr['metrics']}
    return out


if __name__ == '__main__':
    for site in sys.argv[1:] or ['site04_roi3', 'site01_roi6']:
        c = write(site)
        print(site, 'fixed az', c['fixed']['fixed_array_azimuth_deg'])
        for k, v in summary(c).items():
            print(' ', k, v)
