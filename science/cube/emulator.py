"""Phase 7 — position emulator, FOR SEARCH ONLY. Every number shown as a result is re-checked with the full solver.

  python -m science.cube.emulator propose [site ...]     rank off-grid candidates, print the --points string
  CUBE_WORKERS=4 python -m science.cube.compute <site> --points "dx,dy,1;..."   full solver at the candidates
  python -m science.cube.build_sensitivity [site ...]     re-check + indices -> data/cubes/<site>/sensitivity.json

Model (two-fidelity, extends the research surrogate research/long_features/code/step17_surrogate.py):
  m_emu(x, t) = m_coarse(x, t) + delta_GP(x, t)
* m_coarse: HOURLY Sun / Earth vertical margin (target elevation minus skyline elevation, deg) from a coarse
  skyline at x: the step17 surrogate settings (180 azimuth bins, 5 m near-field step to 3 km, PGDA 90 80 m
  beyond, to 280 km) on science/skyline.compute_skyline, nominal PGDA 78 map, mast 1 m.
* delta_GP: a Gaussian process over position (dx, dy) fitted to full-minus-coarse margins on the 81-cell grid
  of the committed position cube (full solver, cached). One Matern 5/2 kernel is shared by all 9097 hourly
  outputs (independent outputs, Kronecker form), so the fit is one 81 x 81 solve; constant mean per hour;
  length scale and nugget picked by closed-form leave-one-out (LOO) RMSE.
The start axis S enters exactly: the 14-day window metrics are computed from the emulated hourly flags
(margin > 0) with the same science/cube/compute.window_metrics as the cubes. A GP on the full margins alone
(no coarse term) is kept as a comparison (`gp_only`); its LOO rank correlation on the grid is far below 0.99
because the margin is not smooth where a near-field ridge enters the skyline.
The emulator is not a solver: its error is reported from full-solver re-checks of the top and random
candidates, and from LOO on the grid; target Spearman rho >= 0.99. Mast is not an emulator input: the
committed cubes have no position x mast joint (mast varies only at the centre), so it runs at mast 1 m.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from scipy.stats import spearmanr

from . import compute as C
from . import ephem_year as E
from .. import frames, sites
from ..skyline import compute_skyline
from .build_cube import series, site_inputs

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'data' / 'cache' / 'cube_emulator'
DAILY = 24
LENGTHS = (10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0, 65.0, 80.0, 100.0, 130.0, 170.0, 220.0)
NUGGETS = (1e-6, 1e-4, 1e-3, 1e-2, 3e-2, 1e-1, 0.3, 1.0, 3.0)   # ratio to the unit kernel amplitude
CAND_STEP = 12.5         # candidate lattice step (m) inside the grid's +-100 m square (grid midpoints)
COARSE = {'bins': 180, 'step_m': 5.0, 'near_range_m': 3000.0}   # step17 surrogate settings
N_TOP = 8
N_RANDOM = 8
MIN_SEP_M = 15.0         # top candidates are at least this far apart
SEED = 20261116


def matern52(X1, X2, ell):
    d = np.sqrt(((X1[:, None, :] - X2[None, :, :]) ** 2).sum(-1)) / ell
    s5 = np.sqrt(5.0) * d
    return (1.0 + s5 + 5.0 * d * d / 3.0) * np.exp(-s5)


class MultiGP:
    """GP with one isotropic Matern 5/2 kernel shared by many outputs (columns of Y)."""

    def __init__(self, X, Y, ell, nugget):
        self.X = np.asarray(X, float); self.ell = float(ell); self.nugget = float(nugget)
        self.Y = np.asarray(Y, float)
        self.mu = self.Y.mean(axis=0, keepdims=True)
        K = matern52(self.X, self.X, ell) + nugget * np.eye(len(self.X))
        self.Kinv = np.linalg.inv(K)
        self.alpha = self.Kinv @ (self.Y - self.mu)

    def predict(self, Xs):
        return self.mu + matern52(np.asarray(Xs, float), self.X, self.ell) @ self.alpha

    def loo_residuals(self):
        """Closed-form leave-one-out residuals y_i - mu_{-i} (Rasmussen & Williams 2006, eq. 5.12)."""
        return self.alpha / np.diag(self.Kinv)[:, None]

    def loo(self):
        """Leave-one-out predictions at the training points. The constant mean is the full-data mean
        (a small optimistic bias, stated in the output)."""
        return self.Y - self.loo_residuals()


BODIES = ('sun', 'earth')
_DEMS = {}


def _norm(dx, dy):
    return C._num(dx), C._num(dy)


def _dems(site):
    if site not in _DEMS:
        _DEMS[site] = (sites.near_dem(site), sites.far_dem(site))
    return _DEMS[site]


def position_latlon(site, dx, dy):
    s = sites.SITES[site]
    return (s['lat'], s['lon']) if (dx, dy) == (0, 0) else C.offset_latlon(site, dx, dy)


def coarse_skyline(site, dx, dy):
    """Coarse (step17 surrogate settings) skyline at an offset, nominal map, mast 1 m; cached under WORK/coarse."""
    dx, dy = _norm(dx, dy)
    p = WORK / 'coarse' / f'{C.sky_key(site, "nominal", 1.0, dx, dy)}.json'
    if p.exists():
        return json.loads(p.read_text())
    nd, fd = _dems(site)
    la, lo = position_latlon(site, dx, dy)
    x, y = frames.stereo_forward(la, lo)
    h = float(nd.sample(x, y))
    sky = compute_skyline(la, lo, h, 1.0, near=nd, far=fd, max_range_m=sites.MAX_RANGE_M, **COARSE)
    el = [None if v is None or not np.isfinite(v) else round(float(v), 5) for v in sky['elevation_deg']]
    out = {'bins': int(sky['bins']), 'elevation_deg': el, 'ground_m': h, 'settings': COARSE, 'map': 'nominal', 'mast_m': 1.0}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out))
    return out


def full_skyline_cached(site, t_id, dx, dy):
    """Full-solver skyline from the cube cache; never computes (run science.cube.compute --points first)."""
    dx, dy = _norm(dx, dy)
    p = C.SKY / f'{C.sky_key(site, t_id, 1.0, dx, dy)}.json'
    if not p.exists():
        raise FileNotFoundError(f'{p.name}: run CUBE_WORKERS=4 python -m science.cube.compute {site} --points "{dx},{dy},1"')
    return json.loads(p.read_text())


def margins_for(site, eph, dx, dy, sky):
    """Hourly vertical margins (deg) of Sun and Earth at an offset for a given skyline (ephemeris transferred)."""
    s = sites.SITES[site]
    out = {}
    for body in BODIES:
        az, el = eph[f'{body}_az'], eph[f'{body}_el']
        if (dx, dy) != (0, 0):
            la, lo = C.offset_latlon(site, dx, dy)
            az, el = C.transfer_azel(az, el, s['lat'], s['lon'], la, lo)
        out[body] = C.margins_vec(az, el, sky)[0]
    return out


def training(site, eph):
    """X (81 x 2) and hourly margins (81 x 9097) per body: full solver (cube cache) and coarse surrogate."""
    X = np.array(C.OFFSETS, float)
    full = {b: [] for b in BODIES}; coarse = {b: [] for b in BODIES}
    for dx, dy in C.OFFSETS:
        f = margins_for(site, eph, dx, dy, full_skyline_cached(site, 'nominal', dx, dy))
        c = margins_for(site, eph, dx, dy, coarse_skyline(site, dx, dy))
        for b in BODIES:
            full[b].append(f[b]); coarse[b].append(c[b])
    full = {b: np.array(v) for b, v in full.items()}; coarse = {b: np.array(v) for b, v in coarse.items()}
    for name, d in (('full', full), ('coarse', coarse)):
        for b, v in d.items():
            if not np.isfinite(v).all():
                raise ValueError(f'{site} {name} {b}: no-data skyline bins in training margins')
    return X, full, coarse


def select_hyper(X, Y):
    """(ell, nugget, loo_rmse_deg) minimising LOO RMSE over all bodies' outputs."""
    best = None
    for ell in LENGTHS:
        for nug in NUGGETS:
            err = 0.0; n = 0
            for v in Y.values():
                r = MultiGP(X, v, ell, nug).loo_residuals()
                err += float((r ** 2).sum()); n += r.size
            rmse = float(np.sqrt(err / n))
            if best is None or rmse < best[2]:
                best = (ell, nug, rmse)
    return best


class Emulator:
    """m_emu = m_coarse + delta_GP (see module docstring)."""

    def __init__(self, X, full, coarse):
        self.X = X
        delta = {b: full[b] - coarse[b] for b in BODIES}
        self.ell, self.nugget, self.loo_rmse = select_hyper(X, delta)
        self.gp = {b: MultiGP(X, delta[b], self.ell, self.nugget) for b in BODIES}
        self.coarse_train = coarse

    def predict(self, Xs, coarse_m):
        return {b: coarse_m[b] + self.gp[b].predict(Xs) for b in BODIES}

    def loo(self):
        return {b: self.coarse_train[b] + self.gp[b].loo() for b in BODIES}


def gp_only_loo(X, full):
    ell, nug, rmse = select_hyper(X, full)
    return {b: MultiGP(X, full[b], ell, nug).loo() for b in BODIES}, (ell, nug, rmse)


def counts_daily(flags):
    """Visible-sample counts per daily start for a batch of hourly flag rows (n x 9097) -> (n x 366)."""
    L = E.WINDOW_H + 1
    starts = np.arange(0, E.N_STARTS, DAILY)
    c = np.concatenate([np.zeros((flags.shape[0], 1), np.int64), np.cumsum(flags.astype(np.int64), axis=1)], axis=1)
    return c[:, starts + L] - c[:, starts]


def pct_daily(m):
    """{'sun', 'sun_earth'}: window % per daily start (n x 366) from hourly margins."""
    k = 100.0 / (E.WINDOW_H + 1)
    s = m['sun'] > 0
    return {'sun': counts_daily(s) * k, 'sun_earth': counts_daily(s & (m['earth'] > 0)) * k}


def objective(pct_sun):
    """Search objective: 12-month mean over daily starts of the window Sun % (nominal map, mast 1 m)."""
    return pct_sun.mean(axis=-1)


def compare(pred, true):
    """Rank and error statistics of emulated vs full-solver values (pct points)."""
    pred = np.asarray(pred, float).ravel(); true = np.asarray(true, float).ravel()
    rho = spearmanr(pred, true).correlation if np.ptp(true) > 0 and np.ptp(pred) > 0 else float('nan')
    e = pred - true
    return {'spearman': float(rho), 'mae': float(np.abs(e).mean()), 'max_abs': float(np.abs(e).max()),
            'bias': float(e.mean()), 'n': int(true.size)}


def loo_report(site, eph, X, full, coarse, emu):
    """LOO on the 81-cell grid: emulator, coarse surrogate alone and GP alone vs the full solver."""
    t = pct_daily(full)
    out = {}
    gpo, gh = gp_only_loo(X, full)
    for name, m in (('emulator', emu.loo()), ('coarse_only', coarse), ('gp_only', gpo)):
        p = pct_daily(m)
        out[name] = {'objective_sun_12mo': compare(objective(p['sun']), objective(t['sun'])),
                     'cell_sun_pct': compare(p['sun'], t['sun']),
                     'cell_sun_earth_pct': compare(p['sun_earth'], t['sun_earth'])}
    out['gp_only']['hyper'] = {'length_m': gh[0], 'nugget': gh[1], 'loo_rmse_margin_deg': gh[2]}
    out['note'] = ('closed-form LOO on the 81 grid cells (edge cells extrapolate); coarse_only needs no fit, '
                   'so its row is a direct comparison, not LOO')
    return out


def candidate_lattice():
    n = int(round(200 / CAND_STEP))
    r = [C._num(-100 + i * CAND_STEP) for i in range(n + 1)]
    grid = set(C.OFFSETS)
    return [(dx, dy) for dx in r for dy in r if (dx, dy) not in grid]


def propose(site):
    b, eph = site_inputs(site)
    X, full, coarse = training(site, eph)
    emu = Emulator(X, full, coarse)
    cands = candidate_lattice()
    Xs = np.array(cands, float)
    cm = {bd: [] for bd in BODIES}
    for dx, dy in cands:
        m = margins_for(site, eph, dx, dy, coarse_skyline(site, dx, dy))
        for bd in BODIES:
            cm[bd].append(m[bd])
    cm = {bd: np.array(v) for bd, v in cm.items()}
    p = pct_daily(emu.predict(Xs, cm))
    obj = objective(p['sun']); both = objective(p['sun_earth'])
    order = np.argsort(-obj, kind='stable')
    top = []
    for i in order:
        if all(np.hypot(cands[i][0] - cands[j][0], cands[i][1] - cands[j][1]) >= MIN_SEP_M for j in top):
            top.append(int(i))
        if len(top) == N_TOP:
            break
    rng = np.random.default_rng(SEED)
    pool = [i for i in range(len(cands)) if i not in top]
    rnd = sorted(int(i) for i in rng.choice(pool, N_RANDOM, replace=False))
    grid_obj = objective(pct_daily(full)['sun'])
    row = lambda i, role: {'dx': cands[i][0], 'dy': cands[i][1], 'role': role, 'emulated_sun_12mo': float(obj[i]),
                           'emulated_sun_earth_12mo': float(both[i])}
    out = {'site': site, 'model': 'coarse surrogate (step17 settings) + GP correction over position',
           'coarse_settings': COARSE,
           'hyper': {'length_m': emu.ell, 'nugget': emu.nugget, 'loo_rmse_delta_deg': emu.loo_rmse},
           'n_candidates': len(cands), 'candidate_step_m': CAND_STEP, 'seed': SEED, 'min_sep_m': MIN_SEP_M,
           'candidates': [row(i, 'top') for i in top] + [row(i, 'random') for i in rnd],
           'grid_best': {'offset': list(C.OFFSETS[int(np.argmax(grid_obj))]), 'sun_12mo': float(grid_obj.max())},
           'loo': loo_report(site, eph, X, full, coarse, emu)}
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / f'{site}_proposal.json').write_text(json.dumps(out, indent=1))
    return out


def load_proposal(site):
    p = WORK / f'{site}_proposal.json'
    if not p.exists():
        raise FileNotFoundError(f'{p}: run python -m science.cube.emulator propose {site}')
    return json.loads(p.read_text())


def recheck(site, prop=None):
    """Full-solver re-check of every proposed candidate (cube helpers: build_cube.series on cached skylines)."""
    prop = prop or load_proposal(site)
    b, eph = site_inputs(site)
    X, full, coarse = training(site, eph)
    emu = Emulator(X, full, coarse)
    rows, emu_cells, full_cells = [], {'sun': [], 'sun_earth': [], 'gap': []}, {'sun': [], 'sun_earth': [], 'gap': []}
    coarse_obj = []
    n = E.WINDOW_H + 1
    for c in prop['candidates']:
        dx, dy = _norm(c['dx'], c['dy'])
        cm = margins_for(site, eph, dx, dy, coarse_skyline(site, dx, dy))
        em = emu.predict(np.array([[dx, dy]], float), {bd: cm[bd][None, :] for bd in BODIES})
        we = window_from_margins(em['sun'][0], em['earth'][0])
        wc = window_from_margins(cm['sun'], cm['earth'])
        per_t = {}
        for t_id in C.T_IDS:
            full_skyline_cached(site, t_id, dx, dy)           # raises if the full solver has not run here
            w, _ = series(site, eph, t_id, 1.0, dx, dy, DAILY)
            per_t[t_id] = w
        wn = per_t['nominal']
        sun_T = np.array([per_t[t]['sun_n'].mean() * 100.0 / n for t in C.T_IDS])
        emu_cells['sun'].append(we['sun_n'] * 100.0 / n); full_cells['sun'].append(wn['sun_n'] * 100.0 / n)
        emu_cells['sun_earth'].append(we['both_n'] * 100.0 / n); full_cells['sun_earth'].append(wn['both_n'] * 100.0 / n)
        emu_cells['gap'].append(we['sun_gap_h']); full_cells['gap'].append(wn['sun_gap_h'])
        coarse_obj.append(wc['sun_n'].mean() * 100.0 / n)
        rows.append({'dx': dx, 'dy': dy, 'role': c['role'],
                     'emulated_sun_12mo': float(we['sun_n'].mean() * 100.0 / n),
                     'full_sun_12mo': float(wn['sun_n'].mean() * 100.0 / n),
                     'coarse_sun_12mo': float(coarse_obj[-1]),
                     'emulated_sun_earth_12mo': float(we['both_n'].mean() * 100.0 / n),
                     'full_sun_earth_12mo': float(wn['both_n'].mean() * 100.0 / n),
                     'full_sun_12mo_worst_map': float(sun_T.min()), 'full_sun_12mo_best_map': float(sun_T.max()),
                     'cell_sun_mae': float(np.abs(emu_cells['sun'][-1] - full_cells['sun'][-1]).mean())})
    eo = [r['emulated_sun_12mo'] for r in rows]; fo = [r['full_sun_12mo'] for r in rows]
    best = max(rows, key=lambda r: r['full_sun_12mo'])
    out = {'rows': rows,
           'objective_sun_12mo': compare(eo, fo),
           'objective_sun_12mo_coarse_only': compare(coarse_obj, fo),
           'objective_sun_earth_12mo': compare([r['emulated_sun_earth_12mo'] for r in rows], [r['full_sun_earth_12mo'] for r in rows]),
           'cell_sun_pct': compare(np.concatenate(emu_cells['sun']), np.concatenate(full_cells['sun'])),
           'cell_sun_earth_pct': compare(np.concatenate(emu_cells['sun_earth']), np.concatenate(full_cells['sun_earth'])),
           'cell_sun_gap_h': compare(np.concatenate(emu_cells['gap']), np.concatenate(full_cells['gap'])),
           'top_candidates_full_min': float(min(r['full_sun_12mo'] for r in rows if r['role'] == 'top')),
           'random_full_median': float(np.median([r['full_sun_12mo'] for r in rows if r['role'] == 'random'])),
           'best_checked': {'dx': best['dx'], 'dy': best['dy'], 'full_sun_12mo': best['full_sun_12mo'],
                            'worst_map_sun_12mo': best['full_sun_12mo_worst_map']},
           'grid_best': prop['grid_best'], 'hyper': prop['hyper'], 'loo': prop['loo']}
    out['target_rho'] = 0.99
    out['passes_target'] = bool(out['objective_sun_12mo']['spearman'] >= 0.99)
    return out


def window_from_margins(m_sun, m_earth, stride=DAILY):
    """Window metrics from hourly margins, same helper and flag rule (margin > 0) as the cubes."""
    return C.window_metrics(np.asarray(m_sun) > 0, np.asarray(m_earth) > 0, E.N_STARTS, E.WINDOW_H, stride)


def points_arg(prop):
    return ';'.join(f'{c["dx"]},{c["dy"]},1' for c in prop['candidates'])


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] != 'propose':
        raise SystemExit(__doc__)
    for s in sys.argv[2:] or ['site04_roi3', 'site01_roi6']:
        p = propose(s)
        print(s, json.dumps(p['hyper']), 'grid best', p['grid_best'])
        print('  LOO', json.dumps({k: v['objective_sun_12mo'] for k, v in p['loo'].items() if isinstance(v, dict) and 'objective_sun_12mo' in v}))
        for r in p['candidates']:
            print('  ', r)
        print(f'  --points "{points_arg(p)}"')
