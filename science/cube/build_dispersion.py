"""Phase 6 — landing dispersion x terrain (reuses the science-limits L9 idea on the full requirement set).

  python -m science.cube.build_dispersion [site ...]

"Share of sampled landing outcomes under an assumed dispersion" — NOT a probability of success.

Field: 25 m grid, +-300 m around the site (625 cells), every cell evaluated on all 21 maps (nominal + 20 clones):
  visibility = team requirement for the 2026-11-14 14-day window (Sun >= 70 %, Sun+Earth >= 40 %, Sun gap <= 120 h),
               mast 1 m, skyline at the cell (science/cube/compute, ephemeris direction transfer);
  slope      = 100 m plane-fit landing slope at the cell centre < limit (science/cube/slope.py).
DEVIATION from the prompt's 5-10 m field: 25 m cells (a 10 m field is 6x the skyline cost); a sample is assigned to
the nearest cell, and samples beyond the field are counted as 'outside field', never as pass or fail.

Monte Carlo: N = 2000 per dispersion, seed fixed. Dispersions: isotropic sigma 10/25/50/100 m, the default preset
sigma99 (99 % circle = 100 m: sigma = 100/sqrt(2 ln 100) = 32.9 m), and an elliptical option (semi-axes 1-sigma
a, b and orientation theta from grid north). Output per dispersion: distribution of k (clone maps of 20 on which the
sampled point passes all requirements), share passing on all 20, and the nominal-map share.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import sys

import numpy as np

from . import compute as C
from . import ephem_year as E
from . import slope as SL
from .build_cube import LABEL, NOT_PROB, OUT, site_inputs
from .build_visibility import add_to_index
from ..limits.common import git_commit, sha256_file

HALF, STEP = 300, 25
N_SAMPLES = 2000
SEED = 20261116
SIGMA99 = 100.0 / math.sqrt(2 * math.log(100.0))
DISPERSIONS = {
    'sigma99_100m': {'kind': 'iso', 'sigma': SIGMA99, 'label': f'isotropic, 99 % circle = 100 m (sigma {SIGMA99:.1f} m) — default'},
    'sigma10': {'kind': 'iso', 'sigma': 10.0, 'label': 'isotropic sigma 10 m'},
    'sigma25': {'kind': 'iso', 'sigma': 25.0, 'label': 'isotropic sigma 25 m'},
    'sigma50': {'kind': 'iso', 'sigma': 50.0, 'label': 'isotropic sigma 50 m'},
    'sigma100': {'kind': 'iso', 'sigma': 100.0, 'label': 'isotropic sigma 100 m'},
    'ellipse_60x20_30deg': {'kind': 'ell', 'a': 60.0, 'b': 20.0, 'theta_deg': 30.0,
                            'label': 'elliptical 1-sigma 60 m x 20 m, major axis 30 deg from grid north'},
}
SLOPE_LIMITS = (10.0, 8.0)
SHARE_LABEL = 'share of sampled landing outcomes under an assumed dispersion'


def field_offsets():
    return C.grid_offsets(HALF, STEP)


def field_pass(site, eph):
    """vis[T, cell], slope100[T, cell] on the field."""
    offs = field_offsets()
    s = C.sites.SITES[site]
    vis = np.zeros((len(C.T_IDS), len(offs)), bool)
    slope = np.zeros((len(C.T_IDS), len(offs)))
    x0, y0 = SL.site_xy(site)
    for i, t in enumerate(C.T_IDS):
        dem = C.sites.near_dem(site, clone=C._clone_of(t))
        S = SL.plane_slope_deg(dem.Z, dem.step, 100)
        for j, (dx, dy) in enumerate(offs):
            sky = C.skyline(site, t, 1.0, dx, dy)
            if (dx, dy) == (0, 0):
                f = C.visible_flags(eph, sky)
            else:
                la, lo = C.offset_latlon(site, dx, dy)
                f = C.visible_flags(eph, sky, s['lat'], s['lon'], la, lo)
            w = C.window_metrics(f['sun'], f['earth'], 1, E.WINDOW_H)
            n = E.WINDOW_H + 1
            vis[i, j] = (100 * w['sun_n'][0] / n >= 70 - 1e-9) and (100 * w['both_n'][0] / n >= 40 - 1e-9) and (w['sun_gap_h'][0] <= 120)
            slope[i, j] = SL.at_point(S, dem, x0 + dx, y0 + dy)
    return vis, slope


def samples(disp, n=N_SAMPLES, seed=SEED):
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((n, 2))
    if disp['kind'] == 'iso':
        return z * disp['sigma']
    th = math.radians(disp['theta_deg'])
    major = np.array([math.sin(th), math.cos(th)]); minor = np.array([math.cos(th), -math.sin(th)])
    return z[:, :1] * disp['a'] * major + z[:, 1:] * disp['b'] * minor


def assign(pts):
    """Nearest field cell index per sample, -1 outside the field."""
    offs = field_offsets()
    side = 2 * HALF // STEP + 1
    ix = np.rint((pts[:, 0] + HALF) / STEP).astype(int); iy = np.rint((pts[:, 1] + HALF) / STEP).astype(int)
    inside = (ix >= 0) & (ix < side) & (iy >= 0) & (iy < side)
    idx = np.where(inside, ix * side + iy, -1)
    assert offs[side * (HALF // STEP) + HALF // STEP] == (0, 0)
    return idx


def outcome(vis, slope, idx, limit):
    ok = vis & (slope < limit)                       # (T, cells)
    k = np.full(idx.size, -1)
    inside = idx >= 0
    k[inside] = ok[1:, idx[inside]].sum(axis=0)
    nom = np.zeros(idx.size, bool); nom[inside] = ok[0, idx[inside]]
    return k, nom, inside


def build(site):
    b, eph = site_inputs(site)
    vis, slope = field_pass(site, eph)
    D = list(DISPERSIONS)
    hist = np.zeros((len(SLOPE_LIMITS), len(D), 22), np.int32)      # k = 0..20, index 21 = outside field
    share20 = np.zeros((len(SLOPE_LIMITS), len(D))); nom_share = np.zeros_like(share20); outside = np.zeros_like(share20)
    for r, lim in enumerate(SLOPE_LIMITS):
        for d, name in enumerate(D):
            idx = assign(samples(DISPERSIONS[name]))
            k, nom, inside = outcome(vis, slope, idx, lim)
            for v in range(21):
                hist[r, d, v] = int((k == v).sum())
            hist[r, d, 21] = int((~inside).sum())
            share20[r, d] = 100 * float((k == 20).sum()) / idx.size
            nom_share[r, d] = 100 * float(nom.sum()) / idx.size
            outside[r, d] = 100 * float((~inside).sum()) / idx.size
    Rd = {'name': 'R_slope', 'kind': 'requirement', 'values': list(SLOPE_LIMITS), 'units': 'deg', 'nominal_index': 0,
          'label': 'Landing slope limit over 100 m (ENGINEERING ASSUMPTION)', 'value_labels': ['< 10° (CASSA assumption)', '< 8° (HLS limit)']}
    Dd = {'name': 'D_dispersion', 'kind': 'design', 'values': D, 'units': '', 'nominal_index': 0,
          'label': 'Assumed landing dispersion', 'value_labels': [DISPERSIONS[k]['label'] for k in D]}
    Kd = {'name': 'k', 'kind': 'uncertainty_terrain', 'values': list(range(21)) + ['outside_field'], 'units': 'maps of 20',
          'label': 'Clone maps (of 20) on which the sampled point passes all requirements', 'note': NOT_PROB}
    pct = lambda a, lab: {'units': '%', 'label': lab, 'dtype': 'float64', 'decimals': 1,
                          'values': [round(float(v), 3) for v in a.reshape(-1)], 'provenance': f'{N_SAMPLES} samples, seed {SEED}'}
    cube = {'schema': 'scenario-cube-v1', 'cube_id': f'{site}-dispersion-v1', 'site_id': site,
            'title': 'Landing dispersion x terrain', 'label': LABEL,
            'generated_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'description': f'{SHARE_LABEL.capitalize()}: k of 20 maps on which the landed point passes visibility and slope.',
            'fixed': {'field_half_m': HALF, 'field_step_m': STEP, 'samples': N_SAMPLES, 'seed': SEED, 'mast_m': 1.0,
                      'window': '2026-11-14 + 14 d', 'visibility': 'team requirement'},
            'dims': [Rd, Dd, Kd],
            'metrics': {'samples': {'units': 'samples', 'label': SHARE_LABEL, 'dtype': 'int32', 'decimals': 0,
                                    'values': hist.reshape(-1).astype(int).tolist(), 'provenance': f'{N_SAMPLES} samples, seed {SEED}'}},
            'missing': {'encoding': 'sparse-flat-index', 'by_metric': {'samples': []}},
            'derived': {'summary': {'dims': ['R_slope', 'D_dispersion'], 'metrics': {
                'share_pass_all_20_pct': pct(share20, f'{SHARE_LABEL}: passing on all 20 maps'),
                'share_pass_nominal_pct': pct(nom_share, f'{SHARE_LABEL}: passing on the nominal map'),
                'share_outside_field_pct': pct(outside, 'samples beyond the +-300 m field (not counted as pass or fail)')},
                'method': 'nearest 25 m cell; pass = team visibility AND 100 m slope < limit, per map', 'caveat': NOT_PROB}},
            'provenance': {'inputs': [{'path': f'data/cache/cube_sky/{site}_*.json', 'sha256': _hash(site), 'note': '625-cell field skylines, 21 maps'}],
                           'command': 'python -m science.cube.build_dispersion ' + ' '.join(sys.argv[1:]), 'code_commit': git_commit(),
                           'solver': 'science/skyline (batched) + slope plane fit'},
            'limitations': [f'{SHARE_LABEL.capitalize()}; not a probability of success.',
                            'Field at 25 m (prompt asks 5-10 m); nearest-cell assignment.', NOT_PROB]}
    return cube


def _hash(site):
    import hashlib
    h = hashlib.sha256()
    for dx, dy in field_offsets():
        for t in C.T_IDS:
            f = C.SKY / f'{C.sky_key(site, t, 1.0, dx, dy)}.json'
            h.update(f.name.encode()); h.update(f.read_bytes())
    return h.hexdigest()


def write(site):
    cube = build(site)
    p = OUT / site / 'dispersion.json'
    p.write_text(json.dumps(cube, separators=(',', ':')) + '\n')
    add_to_index(site, [{'file': p.name, 'cube_id': cube['cube_id'], 'title': cube['title'], 'bytes': p.stat().st_size,
                         'uncompressed_bytes': p.stat().st_size, 'sha256': sha256_file(p), 'dims': [d['name'] for d in cube['dims']]}])
    return cube


if __name__ == '__main__':
    for s in sys.argv[1:] or ['site04_roi3', 'site01_roi6']:
        c = write(s)
        sm = c['derived']['summary']['metrics']
        print(s, dict(zip(DISPERSIONS, sm['share_pass_all_20_pct']['values'][:len(DISPERSIONS)])),
              'outside', dict(zip(DISPERSIONS, sm['share_outside_field_pct']['values'][:len(DISPERSIONS)])))
