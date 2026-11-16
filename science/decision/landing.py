""""Find the best landing point within R km of here": emulator screen, full-solver re-check (PHASE_3_DECISION_PLAN §3).

  python -m science.decision.landing [site ...]     -> data/cache/decision/<site>_landing.json (then rerun build)

1. Lattice: square grid clipped to the disc of radius R around the site ("here"), R = 0.5 km (50 m step) and 2 km
   (200 m step).
2. Requirement filter: landing slope (100 m plane fit, science/cube/slope.py, nominal PGDA 78 5 m) <= 10 deg
   (science/cube/build_safety.LANDING_LIMITS[0]). Candidates whose slope window or coarse near field (3 km) leaves the
   5 m tile are dropped and counted.
3. Screen: the Phase 7 emulator (science/cube/emulator.py: coarse step17 skyline + GP correction over position, nominal
   map, 1 m mast). The GP was trained on the 81 cells of the ±100 m grid: outside that square it reverts to its mean, so
   there the screen is the coarse surrogate plus a constant correction. Objective: share of the 8761 hourly samples
   2026-11-14 00:00 .. 2027-11-14 00:00 UTC with the Sun centre above the skyline.
4. Re-check: "here" + the N_TOP best (>= 2 lattice steps apart) + N_RANDOM random survivors (seeded) with the any-site
   solver (science/anysite/solve.py: 720 bins, native/5 ray step, its own JPL Horizons query at the point, same
   window), with its PGDA 78 clone members and product members. Error = emulator - solver (nominal map).
Nothing here is a probability. The robust choice is over the 21 PGDA 78 maps at the re-checked points only.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import time
from pathlib import Path

import numpy as np

from .. import frames
from ..cube import compute as C
from ..cube import emulator as EM
from ..cube import ephem_year as E
from ..cube import slope as SL
from ..cube.build_cube import site_inputs
from ..cube.build_safety import LANDING_LIMITS
from . import questions as Q

ROOT = Q.ROOT
RUNS = ROOT / 'data' / 'cache' / 'decision'
SEARCHES = ({'id': 'r0p5km', 'radius_m': 500.0, 'step_m': 50.0}, {'id': 'r2km', 'radius_m': 2000.0, 'step_m': 200.0})
N_TOP = 6
N_RANDOM = 2
SEED = 20261116
SLOPE_LIMIT = LANDING_LIMITS[0]
N_SAMPLES = E.N_STARTS                       # 8761 hourly samples = 365 d, both endpoints (= any-site days=365)
START = E.START
DAYS = 365
GP_HALF_M = 100.0
NEAR_RANGE_M = EM.COARSE['near_range_m']


def lattice(radius_m, step_m):
    n = int(round(radius_m / step_m))
    pts = [(C._num(i * step_m), C._num(j * step_m)) for i in range(-n, n + 1) for j in range(-n, n + 1)
           if np.hypot(i * step_m, j * step_m) <= radius_m + 1e-9]
    return pts


def _inside(dem, x, y, half):
    x1 = dem.x_left + dem.Z.shape[1] * dem.step; y1 = dem.y_top - dem.Z.shape[0] * dem.step
    return dem.x_left <= x - half and x + half <= x1 and y1 <= y - half and y + half <= dem.y_top


def screen(site, search, emu, eph, S100, dem):
    s = C.sites.SITES[site]
    x0, y0 = frames.stereo_forward(s['lat'], s['lon'])
    rows, Xs, cm = [], [], {b: [] for b in EM.BODIES}
    n_off = 0
    for dx, dy in lattice(search['radius_m'], search['step_m']):
        x, y = x0 + dx, y0 + dy
        if not _inside(dem, x, y, NEAR_RANGE_M):
            n_off += 1
            continue
        sl = SL.at_point(S100, dem, x, y)
        if not np.isfinite(sl):
            n_off += 1
            continue
        m = EM.margins_for(site, eph, dx, dy, EM.coarse_skyline(site, dx, dy))
        for b in EM.BODIES:
            cm[b].append(m[b][:N_SAMPLES])
        Xs.append((dx, dy))
        rows.append({'dx': dx, 'dy': dy, 'dist_km': round(float(np.hypot(dx, dy)) / 1000, 4), 'slope_100m_deg': round(sl, 4),
                     'slope_ok': bool(sl <= SLOPE_LIMIT), 'gp_in_domain': bool(abs(dx) <= GP_HALF_M and abs(dy) <= GP_HALF_M)})
    cm = {b: np.array(v) for b, v in cm.items()}
    pred = {b: cm[b] + emu.gp[b].predict(np.array(Xs, float))[:, :N_SAMPLES] for b in EM.BODIES}
    sun = (pred['sun'] > 0).mean(axis=1) * 100
    both = ((pred['sun'] > 0) & (pred['earth'] > 0)).mean(axis=1) * 100
    coarse_sun = (cm['sun'] > 0).mean(axis=1) * 100
    for r, a, b_, c in zip(rows, sun, both, coarse_sun):
        r['emulated_sun_pct'] = round(float(a), 4); r['emulated_sun_earth_pct'] = round(float(b_), 4)
        r['coarse_sun_pct'] = round(float(c), 4)
    return rows, n_off


def pick(rows, search):
    ok = [i for i, r in enumerate(rows) if r['slope_ok']]
    order = sorted(ok, key=lambda i: (-rows[i]['emulated_sun_pct'], rows[i]['dist_km'], i))
    sep = 2 * search['step_m']
    here = next(i for i, r in enumerate(rows) if r['dx'] == 0 and r['dy'] == 0)
    top = []
    for i in order:
        if i != here and all(np.hypot(rows[i]['dx'] - rows[j]['dx'], rows[i]['dy'] - rows[j]['dy']) >= sep for j in top):
            top.append(i)
        if len(top) == N_TOP:
            break
    rng = np.random.default_rng(SEED)
    pool = [i for i in ok if i not in top and i != here]
    rnd = sorted(int(i) for i in rng.choice(pool, min(N_RANDOM, len(pool)), replace=False))
    return [(here, 'here')] + [(i, 'top') for i in top] + [(i, 'random') for i in rnd]


def recheck(site, dx, dy):
    from ..anysite.solve import SOLVER_VERSION, solve
    s = C.sites.SITES[site]
    la, lo = (s['lat'], s['lon']) if (dx, dy) == (0, 0) else C.offset_latlon(site, dx, dy)
    t = time.time()
    b = solve(la, lo, 1.0, START, DAYS, 1, ('clones', 'products'), 20)
    m = b['metrics']
    mem = b['anysite']['uncertainty']['members']
    clones = sorted((x for x in mem if x['kind'] == 'pgda78-clone'), key=lambda x: x['id'])
    prods = [x for x in mem if x['kind'] == 'product']
    key = 'sun_center_visible_pct_hourly_samples'
    return {'lat': la, 'lon': lo, 'solver_version': SOLVER_VERSION, 'site_hash': b['anysite']['site_hash'],
            'near_product': b['anysite']['near_field']['product_id'], 'far_product': b['anysite']['far_field']['product_id'],
            'n_samples': m['n_samples'], 'window_utc': m['window_utc'],
            'sun_pct_by_T': [m[key]] + [x['metrics'][key] for x in clones],
            'sun_earth_pct_by_T': [m['sun_and_earth_center_visible_pct_hourly_samples']] +
                                  [x['metrics']['sun_and_earth_center_visible_pct_hourly_samples'] for x in clones],
            'earth_pct_nominal': m['earth_center_visible_pct_hourly_samples'],
            'longest_sun_gap_h_by_T': [m['longest_sun_center_hidden_h']] + [x['metrics']['longest_sun_center_hidden_h'] for x in clones],
            't_ids': ['nominal'] + [x['id'] for x in clones],
            'products': {x['id']: x['metrics'][key] for x in prods},
            'n_truncated': b['skyline']['n_truncated'], 'n_unknown_sun': m['n_unknown_sun'],
            'cache_hit': b['anysite'].get('cache_hit', False), 'seconds': round(time.time() - t, 1)}


def run(site):
    b, eph = site_inputs(site)
    if eph['t'][N_SAMPLES - 1] - eph['t'][0] != DAYS * 86400:
        raise ValueError('cube ephemeris does not span the 365-day re-check window')
    X, full, coarse = EM.training(site, eph)
    emu = EM.Emulator(X, full, coarse)
    dem = C.sites.near_dem(site)
    S100 = SL.plane_slope_deg(dem.Z, dem.step, 100)
    out = {'site': site, 'generated_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
           'window': {'start_utc': START, 'days': DAYS, 'n_samples': N_SAMPLES, 'step_h': 1},
           'emulator': {'module': 'science/cube/emulator.py', 'length_m': emu.ell, 'nugget': emu.nugget,
                        'loo_rmse_delta_deg': emu.loo_rmse, 'gp_domain_half_m': GP_HALF_M, 'coarse_settings': EM.COARSE},
           'slope_limit_deg': SLOPE_LIMIT, 'seed': SEED, 'n_top': N_TOP, 'n_random': N_RANDOM, 'searches': []}
    done = {}
    for search in SEARCHES:
        t = time.time()
        rows, n_off = screen(site, search, emu, eph, S100, dem)
        picks = pick(rows, search)
        checked = []
        for i, role in picks:
            r = rows[i]
            k = (r['dx'], r['dy'])
            if k not in done:
                done[k] = recheck(site, *k)
            rc = done[k]
            checked.append({**r, 'role': role, 'lattice_index': i, **rc,
                            'error_pct': round(r['emulated_sun_pct'] - rc['sun_pct_by_T'][0], 4)})
            print(f'  {site} {search["id"]} {role:6s} ({r["dx"]:7.1f},{r["dy"]:7.1f}) emu {r["emulated_sun_pct"]:7.3f} '
                  f'solver {rc["sun_pct_by_T"][0]:7.3f} worst-T {min(rc["sun_pct_by_T"]):7.3f} ({rc["seconds"]} s)', flush=True)
        out['searches'].append({**search, 'n_lattice': len(rows) + n_off, 'n_off_tile': n_off,
                                'n_slope_fail': sum(not r['slope_ok'] for r in rows),
                                'n_screened': sum(r['slope_ok'] for r in rows), 'lattice': rows, 'checked': checked,
                                'stats': stats(checked), 'seconds': round(time.time() - t, 1)})
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / f'{site}_landing.json').write_text(json.dumps(out))
    return out


def stats(checked):
    e = np.array([c['emulated_sun_pct'] for c in checked]); f = np.array([c['sun_pct_by_T'][0] for c in checked])
    err = e - f
    from scipy.stats import spearmanr
    rho = float(spearmanr(e, f).correlation) if np.ptp(e) > 0 and np.ptp(f) > 0 else float('nan')
    emu_top = int(np.argmax(e)); sol_top = int(np.argmax(f))
    return {'n': int(len(checked)), 'mae_pct': float(np.abs(err).mean()), 'max_abs_pct': float(np.abs(err).max()),
            'bias_pct': float(err.mean()), 'spearman': rho,
            'emulator_top_is_solver_top': bool(emu_top == sol_top),
            'solver_best': {'dx': checked[sol_top]['dx'], 'dy': checked[sol_top]['dy'], 'sun_pct': float(f[sol_top])},
            'in_gp_domain_mae_pct': _mae(checked, True), 'outside_gp_domain_mae_pct': _mae(checked, False)}


def _mae(checked, inside):
    e = [abs(c['error_pct']) for c in checked if c['gp_in_domain'] == inside]
    return float(np.mean(e)) if e else None


def _cand_label(c):
    if c['dx'] == 0 and c['dy'] == 0:
        return 'here (0, 0)'
    return f'{c["dx"]:+g} m E, {c["dy"]:+g} m N ({c["dist_km"]:.2f} km)'


def to_blocks(site, run_):
    """Blocks for decision6d.json plus one robust/regret/VoI question per search radius."""
    from .build import inline_dim, metric, question_blocks
    from .core import Axis, analyse
    blocks, items, summary = {}, [], {}
    sha = Q.sha256_of(RUNS / f'{site}_landing.json')
    for s in run_['searches']:
        sid = s['id']; st = s['stats']
        # every point re-checked by a smaller search is also within this radius: include it (marked), so the larger
        # radius never answers worse than the smaller one just because its coarser lattice missed a point
        own = {(c['dx'], c['dy']) for c in s['checked']}
        nested = [{**c, 'role': 'nested', 'nested_from': o['id']} for o in run_['searches'] if o['radius_m'] < s['radius_m']
                  for c in o['checked'] if (c['dx'], c['dy']) not in own and np.hypot(c['dx'], c['dy']) <= s['radius_m'] + 1e-9]
        seen = set(); nested = [c for c in nested if not ((c['dx'], c['dy']) in seen or seen.add((c['dx'], c['dy'])))]
        ch = s['checked'] + nested
        L = inline_dim('L', 'design', 'decision', list(range(len(ch))), [_cand_label(c) for c in ch],
                       f'What we choose: landing point within {s["radius_m"] / 1000:g} km (re-checked candidates)', nominal=0)
        prov_s = 'science/decision/landing.py screen (science/cube/emulator.py)'
        prov_f = 'science/anysite/solve.py (full solver, 12 months hourly)'
        cm = {
            'dx_m': metric('m', 'East offset from here', [c['dx'] for c in ch], 'polar stereographic offset'),
            'dy_m': metric('m', 'North offset from here', [c['dy'] for c in ch], 'polar stereographic offset'),
            'lat_deg': metric('deg', 'Latitude', [round(c['lat'], 7) for c in ch], 'science/cube/compute.offset_latlon'),
            'lon_deg': metric('deg', 'Longitude (east)', [round(c['lon'], 7) for c in ch], 'science/cube/compute.offset_latlon'),
            'dist_km': metric('km', 'Distance from here', [c['dist_km'] for c in ch], 'hypot(dx, dy)', decimals=3),
            'slope_100m_deg': metric('deg', 'Landing slope (100 m plane fit, nominal map)', [c['slope_100m_deg'] for c in ch],
                                     'science/cube/slope.py', decimals=2),
            'is_top_pick': metric('', 'Emulator top pick (not a random check or here)', [c['role'] == 'top' for c in ch],
                                  'science/decision/landing.py pick', dtype='bool'),
            'in_this_search': metric('', 'Re-checked by this search (false = re-checked by a smaller-radius search)',
                                     [c['role'] != 'nested' for c in ch], 'science/decision/landing.py', dtype='bool'),
            'gp_in_domain': metric('', 'Inside the emulator GP training square (±100 m)', [c['gp_in_domain'] for c in ch],
                                   'science/decision/landing.py', dtype='bool'),
            'emulated_sun_pct': metric('%', 'Emulator: Sun centre visible, 12 months (nominal map)', [c['emulated_sun_pct'] for c in ch],
                                       prov_s, decimals=2),
            'solver_sun_pct': metric('%', 'Full solver: Sun centre visible, 12 months (nominal map)', [c['sun_pct_by_T'][0] for c in ch],
                                     prov_f, decimals=2),
            'recheck_error_pct': metric('pct points', 'Re-check error: emulator minus full solver', [c['error_pct'] for c in ch],
                                        'emulated_sun_pct - solver_sun_pct', decimals=2),
            'solver_sun_pct_worst_T': metric('%', 'Full solver: worst of 21 PGDA 78 maps', [min(c['sun_pct_by_T']) for c in ch],
                                             prov_f, decimals=2),
            'solver_sun_pct_best_T': metric('%', 'Full solver: best of 21 PGDA 78 maps', [max(c['sun_pct_by_T']) for c in ch],
                                            prov_f, decimals=2),
            'solver_sun_earth_pct': metric('%', 'Full solver: Sun and Earth centre visible, 12 months (nominal map)',
                                           [c['sun_earth_pct_by_T'][0] for c in ch], prov_f, decimals=2),
            'product_sun_pct_min': metric('%', 'Other terrain products (M): lowest Sun %', [min(c['products'].values()) if c['products'] else None for c in ch],
                                          prov_f + ' product members; not part of the robust choice', decimals=2),
            'product_sun_pct_max': metric('%', 'Other terrain products (M): highest Sun %', [max(c['products'].values()) if c['products'] else None for c in ch],
                                          prov_f + ' product members; not part of the robust choice', decimals=2),
        }
        blocks[f'landing__{sid}__candidates'] = {'dims': [L], 'metrics': cm, 'method': (
            f'Lattice step {s["step_m"]:g} m within {s["radius_m"]:g} m; slope <= {run_["slope_limit_deg"]:g} deg filter; '
            f'emulator screen; re-check of here + {run_["n_top"]} top (>= {2 * s["step_m"]:g} m apart) + {run_["n_random"]} '
            f'random (seed {run_["seed"]}) with the any-site solver over {run_["window"]["start_utc"]} + {run_["window"]["days"]} d '
            f'hourly ({run_["window"]["n_samples"]} samples). Products checked: '
            f'{", ".join(sorted({k for c in ch for k in c["products"]}))}. Run file sha256 {sha[:16]}…'),
            'caveat': ('SOURCE-BASED · UNVALIDATED. Rows with in_this_search = false were re-checked by a smaller-radius '
                       'search and are included because they lie within this radius; the screen statistics use this '
                       'search\'s own rows only. Outside the ±100 m square the emulator\'s GP term is its mean (coarse '
                       'surrogate + constant): the re-check error is the measure of that. Product members (M) can disagree by '
                       'tens of percentage points at rim sites; they are shown, not optimised over.')}
        lat = s['lattice']
        LL = inline_dim('C', 'design', 'decision', list(range(len(lat))), [_cand_label(r) for r in lat],
                        f'Screened lattice within {s["radius_m"] / 1000:g} km')
        blocks[f'landing__{sid}__lattice'] = {'dims': [LL], 'method': 'every lattice point inside the 5 m tile (screen only)',
                                              'caveat': 'Emulator values (search only); every reported result is re-checked.',
                                              'metrics': {
            'dx_m': metric('m', 'East offset', [r['dx'] for r in lat], 'lattice'),
            'dy_m': metric('m', 'North offset', [r['dy'] for r in lat], 'lattice'),
            'slope_100m_deg': metric('deg', 'Landing slope (100 m)', [r['slope_100m_deg'] for r in lat], 'science/cube/slope.py', decimals=2),
            'slope_ok': metric('', f'Slope <= {run_["slope_limit_deg"]:g} deg', [r['slope_ok'] for r in lat], 'requirement filter', dtype='bool'),
            'emulated_sun_pct': metric('%', 'Emulator: Sun centre visible, 12 months', [r['emulated_sun_pct'] for r in lat], prov_s, decimals=2)}}
        sm = {
            'n_lattice': metric('points', 'Lattice points', [s['n_lattice']], 'count', dtype='int32'),
            'n_off_tile': metric('points', 'Dropped: slope window or 3 km near field leaves the 5 m tile', [s['n_off_tile']], 'count', dtype='int32'),
            'n_slope_fail': metric('points', f'Dropped: slope > {run_["slope_limit_deg"]:g} deg', [s['n_slope_fail']], 'count', dtype='int32'),
            'n_screened': metric('points', 'Screened candidates passing the slope filter', [s['n_screened']], 'count', dtype='int32'),
            'n_rechecked': metric('points', 'Re-checked with the full solver', [st['n']], 'count', dtype='int32'),
            'recheck_mae_pct': metric('pct points', 'Re-check error: mean |emulator - solver|', [round(st['mae_pct'], 4)], 'stats', decimals=2),
            'recheck_max_abs_pct': metric('pct points', 'Re-check error: max |emulator - solver|', [round(st['max_abs_pct'], 4)], 'stats', decimals=2),
            'recheck_bias_pct': metric('pct points', 'Re-check error: mean (emulator - solver)', [round(st['bias_pct'], 4)], 'stats', decimals=2),
            'recheck_spearman': metric('', 'Rank correlation emulator vs solver (re-checked points)',
                                       [None if not np.isfinite(st['spearman']) else round(st['spearman'], 4)], 'scipy spearmanr', decimals=3),
            'emulator_top_is_solver_top': metric('', 'Emulator\'s best re-checked point is the solver\'s best', [st['emulator_top_is_solver_top']],
                                                 'stats', dtype='bool'),
        }
        blocks[f'landing__{sid}__screen'] = {'dims': [], 'metrics': sm, 'method': 'screen and re-check statistics',
                                             'caveat': f'{len(ch)} re-checked points; a small sample, not a validation of the emulator.'}
        # robust choice over the 21 PGDA 78 maps among the re-checked points
        a = np.array([c['sun_pct_by_T'] for c in ch], float).T                  # (T, L)
        tids = ch[0]['t_ids']
        if not all(c['t_ids'] == tids for c in ch):
            raise ValueError('re-checked points have different member sets')
        qid = f'landing_{sid}'
        q = Q.Question(qid, f'data/cache/decision/{site}_landing.json', 'sun_pct_by_T', 'max', ['T'], ['L'],
                       f'Best landing point within {s["radius_m"] / 1000:g} km of here (Sun, 12 months, 1 m mast; '
                       'emulator screen, full-solver re-check)', measure='Sun centre visible, 12 months hourly (full solver)')
        tb = {'values': a, 'source_flat_index': [[None] * a.shape[1] for _ in range(a.shape[0])],
              'x_labels': tids, 'l_labels': [_cand_label(c) for c in ch],
              'x_dims': [{'name': 'T', 'kind': 'uncertainty_terrain', 'values': tids}],
              'l_dims': [{'name': 'D_landing', 'kind': 'design', 'values': list(range(len(ch)))}],
              'nominal_x': 0, 'nominal_l': 0, 'fixed': {}, 'fixed_labels': {'mast': '1 m', 'window': '2026-11-14 + 365 d'},
              'metric_label': 'Sun centre visible, 12 months hourly (full solver)', 'units': '%', 'decimals': 2}
        r = analyse(a, 'max', 0, 0, axes=[Axis('T', a.shape[0])])
        qb = question_blocks(qid, q, tb, r, f'{site}_landing.json (data/cache/decision)', sha, Q.GEOMETRY)
        meta = {'id': qid, 'text': q.text, 'kind': 'landing', 'source_file': f'data/cache/decision/{site}_landing.json',
                'source_sha256': sha, 'metric': 'sun_pct_by_T', 'measure': tb['metric_label'], 'units': '%', 'sense': 'max',
                'label': Q.GEOMETRY, 'x_axes': ['T'], 'l_axes': ['D_landing'], 'fixed': tb['fixed_labels'], 'reduce': {},
                'threshold': None, 'threshold_text': None, 'ordered': False, 'radius_km': s['radius_m'] / 1000,
                'candidates_block': f'landing__{sid}__candidates', 'screen_block': f'landing__{sid}__screen'}
        items.append({'blocks': qb, 'meta': meta, 'analysis': r})
        summary[sid] = {'robust': _cand_label(ch[r['robust_choice']]), 'robust_worst_sun_pct': r['robust_worst'],
                        'recheck_mae_pct': round(st['mae_pct'], 3), 'recheck_max_abs_pct': round(st['max_abs_pct'], 3)}
    return {'blocks': blocks, 'questions': items, 'summary': summary}


if __name__ == '__main__':
    for site in sys.argv[1:] or ['site04_roi3', 'site01_roi6']:
        o = run(site)
        for s in o['searches']:
            print(site, s['id'], json.dumps(s['stats']))
