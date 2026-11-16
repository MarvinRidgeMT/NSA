"""Phase 7 — "what matters" sensitivity indices + position-emulator re-check -> data/cubes/<site>/sensitivity.json

  python -m science.cube.emulator propose [site ...]
  CUBE_WORKERS=4 python -m science.cube.compute <site> --points "<printed by propose>"
  python -m science.cube.build_sensitivity [site ...]

The file is a scenario-cube-v1 cube:
* top-level dims  D_cand: the emulator's re-checked candidate positions (off the 81-cell grid; top + random);
  metrics: emulated and full-solver 12-month Sun %, Sun+Earth %, worst/best map, errors.
* derived  emulator_check: rank correlation and errors of the emulator against the full solver (scalars).
* derived  sobol__<source>__<metric>: exact full-factorial variance decomposition of one metric of one
  committed cube (scalars: first-order, total and Shapley shares per axis, in % of the variance).
  Sources: centre (T x D_mast x S hourly), position (T x D_pos x S daily), and the same two at the demo start
  only (S fixed at 2026-11-14 00:00 UTC). `fixed` lists sources, axes and metrics for the browser.
D_mast and D_pos are never varied together in the committed cubes, so there is no single 4-axis
decomposition; each source is decomposed on its own full grid and the shares are only comparable within it.
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from . import compute as C
from . import emulator as EM
from .build_cube import LABEL, NOT_PROB, OUT, site_inputs
from .build_visibility import add_to_index
from . import sensitivity as SE
from ..limits.common import git_commit, sha256_file

ROOT = Path(__file__).resolve().parents[2]
FILE = 'sensitivity.json'
ENERGY = 'energy.json.gz'
METRICS = (('sun_pct', 'Sun %'), ('sun_earth_pct', 'Sun+Earth %'), ('sun_gap_h', 'Longest Sun gap'))
SOURCES = (
    ('centre', 'centre_mast_schedule.json.gz', False, 'Centre: terrain map x mast height x hourly start (12 months)'),
    ('position', 'position_schedule.json.gz', False, 'Position grid: terrain map x position x daily start (12 months), mast 1 m'),
    ('centre_demo', 'centre_mast_schedule.json.gz', True, 'Centre at the demo start 2026-11-14 00:00 UTC: terrain map x mast height'),
    ('position_demo', 'position_schedule.json.gz', True, 'Position grid at the demo start 2026-11-14 00:00 UTC: terrain map x position, mast 1 m'),
)


def load(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)


def decompose(cube, metric, demo_start=False):
    """(axis names, indices dict) for one metric of a cube; demo_start fixes S at index 0."""
    names = [d['name'] for d in cube['dims']]
    Y = SE.cube_array(cube, metric)
    if demo_start:
        s = names.index('S')
        Y = np.take(Y, 0, axis=s)
        names = names[:s] + names[s + 1:]
    return names, SE.indices(Y, names)


def _f(v, units, label, prov, decimals=2, dtype='float64'):
    return {'units': units, 'label': label, 'dtype': dtype, 'decimals': decimals, 'provenance': prov,
            'values': [None if v is None else (bool(v) if dtype == 'bool' else round(float(v), 6))]}


def _pct(x):
    return None if x is None else 100 * x


def sobol_block(src, file, cube, metric, mlabel, demo, title):
    names, r = decompose(cube, metric, demo)
    units = cube['metrics'][metric]['units']
    prov = f'science/cube/sensitivity.indices on data/cubes/<site>/{file} metric {metric}' + (' at S index 0' if demo else '')
    m = {'variance': _f(r['variance'], f'{units}^2', f'{mlabel}: variance over the grid', prov, 4),
         'sd': _f(r['sd'], units, f'{mlabel}: standard deviation over the grid', prov, 2),
         'mean': _f(r['mean'], units, f'{mlabel}: mean over the grid', prov, 2),
         'interaction_pct': _f(_pct(r['interaction_share']), '% of variance', f'{mlabel}: share in interactions', prov, 1),
         'closure': _f(r['closure'], 'ratio', 'sum of ANOVA terms / variance (1 = exact)', prov, 6),
         'no_spread': _f(r['no_spread'], '', 'every cell equal: shares undefined (null)', prov, 0, 'bool')}
    for a in names:
        for kind, lab in (('first', 'first-order'), ('total', 'total'), ('shapley', 'Shapley')):
            m[f'{kind}_pct__{a}'] = _f(_pct(r['axes'][a][kind]), '% of variance', f'{mlabel}: {lab} share of {a}', prov, 1)
    for u, v in r['interactions'].items():
        m[f'interaction_pct__{u.replace("×", "_x_")}'] = _f(100 * v, '% of variance', f'{mlabel}: interaction {u}', prov, 1)
    return {'dims': [], 'metrics': m,
            'method': f'{SE.METHOD} Source: {title} ({file}); axes {", ".join(names)}.',
            'caveat': SE.CAVEAT}, names, r


def _hash_files(paths):
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.name.encode()); h.update(p.read_bytes())
    return h.hexdigest()


def build(site):
    d = OUT / site
    b, eph = site_inputs(site)
    cubes = {f: load(d / f) for f in {s[1] for s in SOURCES}}
    derived, fixed, tops = {}, {}, {}
    for src, file, demo, title in SOURCES:
        for metric, mlabel in METRICS:
            blk, names, r = sobol_block(src, file, cubes[file], metric, mlabel, demo, title)
            derived[f'sobol__{src}__{metric}'] = blk
            tops[(src, metric)] = 'no spread' if r['no_spread'] else max(names, key=lambda a: r['axes'][a]['shapley'])
        fixed[f'axes__{src}'] = ','.join(names)
        fixed[f'title__{src}'] = title
    fixed['sources'] = ','.join(s[0] for s in SOURCES)
    fixed['metrics'] = ','.join(m for m, _ in METRICS)
    fixed['metric_labels'] = ','.join(lab for _, lab in METRICS)
    missing_reasons = {}
    energy_p = d / ENERGY
    if energy_p.exists():
        ec = load(energy_p)
        ok = [k for k, m in ec['metrics'].items() if m['dtype'] != 'bool' and not ec['missing']['by_metric'].get(k)]
        for k in ok:
            blk, names, r = sobol_block('energy', ENERGY, ec, k, ec['metrics'][k]['label'], False, ec.get('title', 'energy'))
            derived[f'sobol__energy__{k}'] = blk
        fixed['energy_margin'] = f'decomposed: {",".join(ok)}' if ok else 'in bundle, no complete metric'
        if ok:
            fixed['axes__energy'] = ','.join(x['name'] for x in ec['dims'])
            fixed['title__energy'] = ec.get('title', 'energy')
            fixed['metrics__energy'] = ','.join(ok)
    else:
        fixed['energy_margin'] = 'not in bundle'
        missing_reasons['energy_margin'] = (f'not in bundle: data/cubes/{site}/{ENERGY} (Phase 5, ENGINEERING ASSUMPTION) '
                                            'is not on this branch, so energy margin is not decomposed')
    fixed['M_axis'] = 'not decomposed: the M cube (products.json) holds one cell per product, no factorial with T, D or S'

    # ---- emulator re-check
    prop = EM.load_proposal(site)
    rc = EM.recheck(site, prop)
    rows = rc['rows']
    dim = {'name': 'D_cand', 'kind': 'design', 'values': [f'{r["dx"]},{r["dy"]}' for r in rows], 'units': 'grid m (dx,dy)',
           'label': 'Emulator candidate position (off the 81-cell grid), polar-stereographic grid metres',
           'value_labels': [f'{r["dx"]},{r["dy"]} ({r["role"]})' for r in rows],
           'note': f'{sum(r["role"] == "top" for r in rows)} emulator top picks (>= {EM.MIN_SEP_M:g} m apart) + '
                   f'{sum(r["role"] == "random" for r in rows)} random lattice points (seed {EM.SEED}); '
                   f'{EM.CAND_STEP:g} m candidate lattice inside +-100 m, grid cells excluded', 'nominal_index': 0}
    col = lambda k: [round(float(r[k]), 4) for r in rows]
    pe = 'science/cube/emulator (coarse surrogate + GP correction); SURROGATE, search only'
    pf = 'full solver: science.cube.compute --points + build_cube.series (720 bins, 1 m step, 280 km)'
    mk = lambda k, lab, prov, units='%': {'units': units, 'label': lab, 'dtype': 'float64', 'decimals': 2, 'values': col(k), 'provenance': prov}
    metrics = {
        'emulated_sun_12mo': mk('emulated_sun_12mo', 'Emulated 12-month mean Sun % (nominal map, 1 m)', pe),
        'full_sun_12mo': mk('full_sun_12mo', 'Full-solver 12-month mean Sun % (nominal map, 1 m)', pf),
        'coarse_sun_12mo': mk('coarse_sun_12mo', 'Coarse surrogate alone, 12-month mean Sun %', 'science/cube/emulator.coarse_skyline (step17 settings)'),
        'emulated_sun_earth_12mo': mk('emulated_sun_earth_12mo', 'Emulated 12-month mean Sun+Earth %', pe),
        'full_sun_earth_12mo': mk('full_sun_earth_12mo', 'Full-solver 12-month mean Sun+Earth %', pf),
        'full_sun_12mo_worst_map': mk('full_sun_12mo_worst_map', 'Full solver: worst of 21 maps, 12-month mean Sun %', pf),
        'full_sun_12mo_best_map': mk('full_sun_12mo_best_map', 'Full solver: best of 21 maps, 12-month mean Sun %', pf),
        'cell_sun_mae': mk('cell_sun_mae', 'Emulator error per window (mean abs over 366 daily starts), Sun', pf + ' vs ' + pe, 'pct pts'),
        'is_top_pick': {'units': '', 'label': 'Emulator top pick (1) or random check (0)', 'dtype': 'int32', 'decimals': 0,
                        'values': [int(r['role'] == 'top') for r in rows], 'provenance': 'science/cube/emulator.propose'},
    }
    o, oc, c1, c2, c3 = rc['objective_sun_12mo'], rc['objective_sun_12mo_coarse_only'], rc['cell_sun_pct'], rc['cell_sun_earth_pct'], rc['cell_sun_gap_h']
    loo = rc['loo']
    pr = 'science/cube/emulator.recheck (full solver vs emulator at the D_cand positions)'
    pl = 'science/cube/emulator.loo_report (closed-form leave-one-out on the 81 grid cells)'
    chk = {
        'spearman_objective': _f(o['spearman'], 'rho', 'Spearman rho, 12-month Sun %, emulator vs full solver (D_cand)', pr, 4),
        'mae_objective': _f(o['mae'], 'pct pts', 'Mean abs error, 12-month Sun %', pr, 2),
        'max_abs_objective': _f(o['max_abs'], 'pct pts', 'Max abs error, 12-month Sun %', pr, 2),
        'spearman_objective_coarse_only': _f(oc['spearman'], 'rho', 'Spearman rho, coarse surrogate alone', pr, 4),
        'mae_objective_coarse_only': _f(oc['mae'], 'pct pts', 'Mean abs error, coarse surrogate alone', pr, 2),
        'spearman_objective_sun_earth': _f(rc['objective_sun_earth_12mo']['spearman'], 'rho', 'Spearman rho, 12-month Sun+Earth %', pr, 4),
        'spearman_cell_sun_pct': _f(c1['spearman'], 'rho', 'Spearman rho per window (candidate x daily start), Sun %', pr, 4),
        'mae_cell_sun_pct': _f(c1['mae'], 'pct pts', 'Mean abs error per window, Sun %', pr, 2),
        'max_abs_cell_sun_pct': _f(c1['max_abs'], 'pct pts', 'Max abs error per window, Sun %', pr, 2),
        'spearman_cell_sun_earth_pct': _f(c2['spearman'], 'rho', 'Spearman rho per window, Sun+Earth %', pr, 4),
        'mae_cell_sun_earth_pct': _f(c2['mae'], 'pct pts', 'Mean abs error per window, Sun+Earth %', pr, 2),
        'mae_cell_sun_gap_h': _f(c3['mae'], 'h', 'Mean abs error per window, longest Sun gap', pr, 1),
        'loo_spearman_objective': _f(loo['emulator']['objective_sun_12mo']['spearman'], 'rho', 'LOO on the grid: emulator', pl, 4),
        'loo_mae_objective': _f(loo['emulator']['objective_sun_12mo']['mae'], 'pct pts', 'LOO on the grid: emulator mean abs error', pl, 2),
        'loo_spearman_gp_only': _f(loo['gp_only']['objective_sun_12mo']['spearman'], 'rho', 'LOO on the grid: GP on full margins alone (no coarse term)', pl, 4),
        'grid_best_sun_12mo': _f(rc['grid_best']['sun_12mo'], '%', f'Best 81-grid cell {rc["grid_best"]["offset"]}, 12-month Sun % (full solver)', 'position cube, nominal map', 2),
        'best_checked_sun_12mo': _f(rc['best_checked']['full_sun_12mo'], '%', f'Best re-checked candidate ({rc["best_checked"]["dx"]},{rc["best_checked"]["dy"]}), full solver', pr, 2),
        'best_checked_worst_map_sun_12mo': _f(rc['best_checked']['worst_map_sun_12mo'], '%', 'Best re-checked candidate: worst of 21 maps', pr, 2),
        'gp_length_m': _f(rc['hyper']['length_m'], 'm', 'GP correction length scale (LOO-selected)', 'science/cube/emulator.select_hyper', 1),
        'gp_nugget': _f(rc['hyper']['nugget'], 'ratio', 'GP correction nugget / kernel amplitude (LOO-selected)', 'science/cube/emulator.select_hyper', 4),
        'target_rho': _f(rc['target_rho'], 'rho', 'Target Spearman rho', 'docs/5D_UPGRADES_STATUS.md Phase 7', 2),
        'passes_target': _f(rc['passes_target'], '', 'Re-check rho >= target', pr, 0, 'bool'),
    }
    derived = {'emulator_check': {
        'dims': [], 'metrics': chk,
        'method': ('Emulator = coarse surrogate skyline (step17 settings: 180 bins, 5 m step to 3 km, 80 m beyond) + Gaussian-process '
                   'correction of the full-minus-coarse hourly margins over position (Matern 5/2, 81-cell training grid, LOO-selected). '
                   'Window metrics from emulated hourly flags with the cube window helper. Candidates ranked by emulated 12-month '
                   'Sun % on a 12.5 m lattice; the top picks and random lattice points re-checked with the full solver on all 21 maps.'),
        'caveat': ('SURROGATE for search only: rank and error from the re-check, nominal map, mast 1 m; it is not a solver and '
                   'its numbers are not results. Re-checked values are full-solver geometry, SOURCE-BASED · UNVALIDATED.')},
        **derived}

    cube_inputs = [{'path': f'data/cubes/{site}/{f}', 'sha256': sha256_file(d / f), 'note': 'committed scenario cube (decomposed)'}
                   for f in sorted(cubes)]
    eph_inputs = [{'path': p['path'], 'sha256': p['sha256'], 'url': 'https://ssd.jpl.nasa.gov/api/horizons.api',
                   'note': f'JPL Horizons {p["body"]} hourly (git-ignored cache)'} for p in eph['prov']]
    full_files = [C.SKY / f'{C.sky_key(site, "nominal", 1.0, dx, dy)}.json' for dx, dy in C.OFFSETS]
    full_files += [C.SKY / f'{C.sky_key(site, t, 1.0, r["dx"], r["dy"])}.json' for r in rows for t in C.T_IDS]
    coarse_files = [EM.WORK / 'coarse' / f'{C.sky_key(site, "nominal", 1.0, *EM._norm(dx, dy))}.json'
                    for dx, dy in list(C.OFFSETS) + [(r['dx'], r['dy']) for r in rows]]
    extra = [{'path': f'data/cache/cube_sky/{site}_*.json', 'sha256': _hash_files(full_files),
              'note': f'{len(full_files)} full-solver skylines used (81 grid nominal + candidates x 21 maps; combined name+bytes hash)'},
             {'path': f'data/cache/cube_emulator/coarse/{site}_*.json', 'sha256': _hash_files(coarse_files),
              'note': f'{len(coarse_files)} coarse surrogate skylines used (combined hash)'},
             {'path': f'data/cache/cube_emulator/{site}_proposal.json', 'sha256': sha256_file(EM.WORK / f'{site}_proposal.json'),
              'note': 'emulator proposal (candidates, hyperparameters, LOO)'}]
    if energy_p.exists():
        cube_inputs.append({'path': f'data/cubes/{site}/{ENERGY}', 'sha256': sha256_file(energy_p), 'note': 'energy cube (Phase 5)'})
    now = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    cube = {'schema': 'scenario-cube-v1', 'cube_id': f'{site}-sensitivity-v1', 'site_id': site,
            'title': 'What matters: sensitivity indices + emulator re-check', 'label': LABEL, 'generated_utc': now,
            'description': ('Exact full-factorial variance shares of Sun %, Sun+Earth % and longest Sun gap over the committed cubes; '
                            'top-level cells are the position emulator candidates re-checked with the full solver.'),
            'fixed': {**fixed, 'mast_m_emulator': 1.0, 'map_emulator': 'nominal'},
            'dims': [dim], 'metrics': metrics,
            'missing': {'encoding': 'sparse-flat-index', 'by_metric': {k: [] for k in metrics}, 'reasons': missing_reasons},
            'derived': derived,
            'provenance': {'inputs': cube_inputs + eph_inputs + extra,
                           'command': 'python -m science.cube.build_sensitivity ' + ' '.join(sys.argv[1:]),
                           'code_commit': git_commit(),
                           'solver': 'indices: exact ANOVA on stored cube values; re-check: science/skyline.compute_skyline (float64), 720 bins, 1 m step, 280 km'},
            'limitations': [SE.CAVEAT, NOT_PROB,
                            'D_mast and D_pos are never varied together in the committed cubes: each source has its own decomposition, and shares are comparable only within one source.',
                            'S weights every start equally over 12 months; the S share is mostly the seasonal and monthly Sun/Earth geometry.',
                            'Emulator: SURROGATE for search only, nominal map, mast 1 m; every candidate value shown is re-checked with the full solver.',
                            'Local geometric visibility only: not power, not a DSN link.']}
    return cube, tops, rc


def write(site):
    cube, tops, rc = build(site)
    p = OUT / site / FILE
    text = json.dumps(cube, indent=1) + '\n'
    p.write_text(text)
    add_to_index(site, [{'file': FILE, 'cube_id': cube['cube_id'], 'title': cube['title'], 'bytes': p.stat().st_size,
                         'uncompressed_bytes': len(text.encode()), 'sha256': sha256_file(p), 'dims': [x['name'] for x in cube['dims']]}])
    return cube, tops, rc


if __name__ == '__main__':
    for s in sys.argv[1:] or ['site04_roi3', 'site01_roi6']:
        cube, tops, rc = write(s)
        print(s, 'top Shapley axis:', {f'{a}/{m}': v for (a, m), v in tops.items()})
        print('  emulator re-check', json.dumps({k: rc[k] for k in ('objective_sun_12mo', 'objective_sun_12mo_coarse_only', 'cell_sun_pct', 'cell_sun_earth_pct', 'cell_sun_gap_h', 'best_checked', 'grid_best', 'passes_target')}))
