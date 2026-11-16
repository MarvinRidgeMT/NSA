"""Phase 2 — terrain safety cube + "safe and lit" layer, per site.

  python -m science.cube.build_safety [site ...]

Writes data/cubes/<site>/terrain_safety.json (scenario-cube-v1), dims T(21) x D_pos(81):
  slope_{5,25,100}m_median / _max   slope field statistics inside each 25 m position cell
  landing_slope_100m                 100 m-baseline plane-fit slope at the cell centre
and derived:
  eva_region                         per T: share of the 2 km x 2 km region (centred on the site) with
                                     25 m slope < EVA limit, and the max 25 m slope there
  safe_and_lit                       per landing-slope limit R_slope x D_pos: slope < limit on ALL 20 clone
                                     maps, and the k (of 20) clone maps on which the team visibility
                                     requirement passes for the 2026-11-14 window (position cube k_of_N)
  barker_check                       clone spread (std over 20 clones) of 25 m / 100 m slope vs Barker et al.
                                     (typical slope RMS uncertainty 1.5-2.5 deg)
Requirement thresholds (CASSA landing 10 deg, HLS alternative 8 deg; EVA 20 deg) are ENGINEERING
ASSUMPTIONS, stored as an R axis and editable in the UI.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import sys
from pathlib import Path

import numpy as np

from . import compute as C
from . import slope as SL
from .build_cube import LABEL, NOT_PROB, OUT
from ..limits.common import git_commit, sha256_file

ROOT = Path(__file__).resolve().parents[2]
LANDING_LIMITS = (10.0, 8.0)
EVA_LIMIT = 20.0
EVA_HALF_M = 1000.0


def _metric(vals, label, units='deg', dec=2, prov='science/cube/slope.py plane fit on PGDA 78 5 m'):
    return {'units': units, 'label': label, 'dtype': 'float64', 'decimals': dec,
            'values': [round(float(v), 4) for v in np.asarray(vals).reshape(-1)], 'provenance': prov}


def build(site):
    x0, y0 = SL.site_xy(site)
    nT, nP = len(C.T_IDS), len(C.OFFSETS)
    stats = {f'slope_{b}m_{a}': np.zeros((nT, nP)) for b in SL.BASELINES_M for a in ('median', 'max')}
    landing = np.zeros((nT, nP)); eva_share = np.zeros(nT); eva_max = np.zeros(nT)
    fields5, fields25, fields100 = [], [], []
    ins = []
    for i, t in enumerate(C.T_IDS):
        dem = C.sites.near_dem(site, clone=C._clone_of(t))
        ins.append({'path': f'data/cache/{site}_p78_{"p78" if t == "nominal" else "clone%04d" % C._clone_of(t)}.npy',
                    'sha256': dem.meta.get('file_sha256') or dem.digest(), 'url': dem.meta.get('source_url', ''),
                    'note': f'PGDA 78 5 m {t} (sha256 of source GeoTIFF; git-ignored cache)'})
        for b in SL.BASELINES_M:
            S = SL.plane_slope_deg(dem.Z, dem.step, b)
            med, mx = SL.cell_stats(S, dem, x0, y0, C.OFFSETS)
            stats[f'slope_{b}m_median'][i] = med; stats[f'slope_{b}m_max'][i] = mx
            if b == 100:
                landing[i] = [SL.at_point(S, dem, x0 + dx, y0 + dy) for dx, dy in C.OFFSETS]
                if t != 'nominal':
                    fields100.append(SL.cell_window(S, dem, x0, y0, 150.0))
            if b == 5 and t != 'nominal':
                fields5.append(SL.cell_window(S, dem, x0, y0, 150.0))
            if b == 25:
                eva_share[i], eva_max[i] = SL.region_share_below(S, dem, x0, y0, EVA_HALF_M, EVA_LIMIT)
                if t != 'nominal':
                    fields25.append(SL.cell_window(S, dem, x0, y0, 150.0))
    # Barker comparison: per-pixel std over the 20 clones in the +-150 m block around the site
    spread = {}
    for b, f in ((5, fields5), (25, fields25), (100, fields100)):
        sd = np.nanstd(np.array(f), axis=0)
        med = float(np.nanmedian(sd))
        spread[f'{b}m'] = {'median_std_deg': round(med, 3), 'p95_std_deg': round(float(np.nanpercentile(sd, 95)), 3),
                           'ratio_to_barker_1p5deg': round(med / 1.5, 3),
                           # "same order" = within a factor of 3 of Barker's 1.5-2.5 deg range
                           'within_factor_3_of_barker': bool(1.5 / 3 <= med <= 2.5 * 3)}
    spread['barker_reference'] = 'Barker et al. 2021 (PGDA 78): typical slope RMS uncertainty 1.5-2.5 deg'
    spread['block'] = 'per-pixel std over clones 1-20 in the +-150 m block around the site'
    # safe and lit
    pos = _load_gz(OUT / site / 'position_schedule.json.gz')
    k = np.array(pos['derived']['k_of_N']['metrics']['k_pass']['values']).reshape(3, nP, -1)[0, :, 0]
    nom_vis = np.array(pos['derived']['k_of_N']['metrics']['nominal_pass']['values']).reshape(3, nP, -1)[0, :, 0]
    safe = np.array([[bool(np.all(landing[1:, j] < lim)) for j in range(nP)] for lim in LANDING_LIMITS])
    safe_k = np.where(safe, k[None, :], 0)
    T = {'name': 'T', 'kind': 'uncertainty_terrain', 'values': list(C.T_IDS), 'units': '', 'nominal_index': 0,
         'label': 'Terrain map: PGDA 78 nominal + 20 error clones', 'note': NOT_PROB}
    P = {'name': 'D_pos', 'kind': 'design', 'values': [f'{dx},{dy}' for dx, dy in C.OFFSETS], 'units': 'grid m (dx,dy)',
         'nominal_index': C.OFFSETS.index((0, 0)), 'label': 'Position offset, polar-stereographic grid metres (9 x 9, 25 m step)',
         'note': 'row-major: dx outer (-100..100), dy inner (-100..100)'}
    R = {'name': 'R_slope', 'kind': 'requirement', 'values': list(LANDING_LIMITS), 'units': 'deg', 'nominal_index': 0,
         'label': 'Landing slope limit over 100 m (ENGINEERING ASSUMPTION)',
         'value_labels': ['< 10° (CASSA assumption)', '< 8° (HLS limit)']}
    metrics = {k_: _metric(v, f'Slope {k_.split("_")[1]} baseline, {k_.split("_")[2]} in 25 m cell') for k_, v in stats.items()}
    metrics['landing_slope_100m'] = _metric(landing, 'Landing slope (100 m plane fit) at cell centre')
    cube = {
        'schema': 'scenario-cube-v1', 'cube_id': f'{site}-terrain-safety-v1', 'site_id': site,
        'title': 'Terrain safety: slope per map and position, safe-and-lit', 'label': LABEL,
        'generated_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'description': 'Plane-fit slope from the PGDA 78 5 m DEM at 5, 25 and 100 m baselines, nominal and 20 clones.',
        'fixed': {'eva_region_m': 2 * EVA_HALF_M, 'eva_limit_deg': EVA_LIMIT, 'visibility_window': '2026-11-14 + 14 d, team R'},
        'dims': [T, P],
        'metrics': metrics,
        'missing': {'encoding': 'sparse-flat-index', 'by_metric': {k_: [] for k_ in metrics}},
        'derived': {
            'eva_region': {'dims': ['T'], 'metrics': {
                'share_below_limit_pct': _metric(eva_share, f'Share of 2 km region with 25 m slope < {EVA_LIMIT:g}°', '%', 1),
                'max_slope_25m_deg': _metric(eva_max, 'Max 25 m slope in 2 km region')},
                'method': f'25 m-baseline plane fit; square region {2 * EVA_HALF_M:g} m centred on the site; limit {EVA_LIMIT:g}° (ENGINEERING ASSUMPTION)'},
            'safe_and_lit': {'dims': [R, 'D_pos'], 'metrics': {
                'safe_all_20': {'units': '', 'label': 'Landing slope below limit on all 20 clone maps', 'dtype': 'bool',
                                'values': safe.reshape(-1).tolist(), 'provenance': 'landing_slope_100m, clones 1-20'},
                'k_lit': {'units': 'maps of 20', 'label': 'Clone maps passing the team visibility requirement (2026-11-14 window)',
                          'dtype': 'int32', 'values': np.repeat(k[None, :], len(LANDING_LIMITS), 0).reshape(-1).astype(int).tolist(),
                          'provenance': 'position_schedule.json.gz derived.k_of_N (R=team, S=0)'},
                'k_safe_and_lit': {'units': 'maps of 20', 'label': 'Safe on all 20 maps AND lit on k of 20 maps (0 if not safe)',
                                   'dtype': 'int32', 'values': safe_k.reshape(-1).astype(int).tolist(), 'provenance': 'safe_all_20 x k_lit'},
                'nominal_lit': {'units': '', 'label': 'Nominal map passes the team visibility requirement', 'dtype': 'bool',
                                'values': np.repeat(nom_vis[None, :], len(LANDING_LIMITS), 0).reshape(-1).astype(bool).tolist(),
                                'provenance': 'position_schedule.json.gz derived.k_of_N nominal_pass'}},
                'method': 'a cell passes only if the 100 m landing slope < limit on all 20 clone maps; its lit count is k of 20 clone maps passing Sun >= 70 %, Sun+Earth >= 40 %, Sun gap <= 120 h',
                'caveat': NOT_PROB},
        },
        'provenance': {'inputs': ins + [{'path': f'data/cubes/{site}/position_schedule.json.gz',
                                         'sha256': sha256_file(OUT / site / 'position_schedule.json.gz'), 'note': 'visibility k of N'}],
                       'command': 'python -m science.cube.build_safety ' + ' '.join(sys.argv[1:]), 'code_commit': git_commit(),
                       'solver': 'science/cube/slope.plane_slope_deg (separable LSQ plane fit)'},
        'limitations': ['Slope from a 5 m DEM; boulders and sub-5 m roughness are not resolved.',
                        'Landing/EVA thresholds are ENGINEERING ASSUMPTIONS, not mission requirements.', NOT_PROB],
        'barker_check': spread,
    }
    return cube


def _load_gz(p):
    raw = Path(p).read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)


def write(site):
    cube = build(site)
    bc = cube.pop('barker_check')
    cube['limitations'].append('Clone spread vs Barker: ' + json.dumps(bc))
    p = OUT / site / 'terrain_safety.json'
    p.write_text(json.dumps(cube, separators=(',', ':')) + '\n')
    idx_p = OUT / site / 'index.json'
    idx = json.loads(idx_p.read_text())
    idx['cubes'] = [c for c in idx['cubes'] if c['file'] != p.name] + [
        {'file': p.name, 'cube_id': cube['cube_id'], 'title': cube['title'], 'bytes': p.stat().st_size,
         'uncompressed_bytes': p.stat().st_size, 'sha256': sha256_file(p), 'dims': [d['name'] for d in cube['dims']]}]
    idx['barker_check'] = bc
    idx_p.write_text(json.dumps(idx, indent=1) + '\n')
    return cube, bc


if __name__ == '__main__':
    for s in sys.argv[1:] or ['site04_roi3', 'site01_roi6']:
        c, bc = write(s)
        sl = c['derived']['safe_and_lit']['metrics']['k_safe_and_lit']['values']
        print(s, json.dumps(bc), 'cells safe&lit(k=20) at 10deg:', sum(v == 20 for v in sl[:81]))
