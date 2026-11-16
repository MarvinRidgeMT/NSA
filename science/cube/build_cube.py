"""Assemble scenario cubes (schemas/scenario-cube-v1.schema.json) per site from solver runs.

  python -m science.cube.build_cube [site ...]        (default: site04_roi3 site01_roi6)

Writes data/cubes/<site>/{index.json, centre_mast_schedule.json.gz, position_schedule.json.gz,
products.json}. New files only: no bundle, viewer file or Decision Lab file is read for writing.

Cubes
  centre_mast_schedule  T(21) x D_mast(10) x S(8761 hourly starts)   at the bundle site position
  position_schedule     T(21) x D_pos(81)  x S(366 daily starts)     at mast 1 m
  products              M(4-5)                                       centre, mast 1 m, demo window,
                        values copied from research/long_features/results (lens_*.json, sfs_result.json)

Metrics per window (14 d, 337 hourly samples incl. both ends, as the bundles' *_hourly_samples):
Sun %, Sun+Earth %, Earth %, longest Sun gap h, longest Earth gap h (runs of hidden hourly samples x 1 h).
Percentages are stored as visible-sample counts with scale 100/337 so they are exact.

Derived (robust-decision outputs; Python only, the browser displays them):
  band_over_T          min / max over the 21 maps of every metric, per D x S cell
  k_of_N               clone maps (of 20) passing each requirement preset R, per D x S; nominal pass
  regret               per S: D* = argmax nominal Sun+Earth %; regret_k = max_D m_k(D) - m_k(D*); max over k
  decision_changes     per D: share of S starts where 0 < k < 20 (the verdict depends on the map)
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
from . import ephem_year as E
from ..limits.common import git_commit, sha256_file

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data' / 'cubes'
LABEL = 'SOURCE-BASED · UNVALIDATED'
BUNDLE = {s: ROOT / 'data' / 'bundles' / f'{s}_2026-11-14_14d_mast1m.json' for s in ('site04_roi3', 'site01_roi6')}
RESEARCH_KEY = {'site04_roi3': 'Site04_ROI3', 'site01_roi6': 'Site01_ROI6'}
RES = ROOT / 'research' / 'long_features' / 'results'
DAILY_STRIDE = 24
NOT_PROB = 'k of N maps is not a probability; the clones are deterministic alternates (PGDA 78 error realizations).'
# Requirement presets (kind=requirement). R0 is the team requirement (web/src/bundle/requirements.ts) plus the
# research "all3" longest-Sun-gap limit (step12_more.py); R1/R2 are stricter/looser sensitivity presets.
R_PRESETS = [
    {'id': 'team', 'label': 'Team: Sun ≥ 70 %, Sun+Earth ≥ 40 %, Sun gap ≤ 120 h', 'sun_pct': 70.0, 'both_pct': 40.0, 'sun_gap_h': 120},
    {'id': 'strict', 'label': 'Stricter: Sun ≥ 80 %, Sun+Earth ≥ 50 %, Sun gap ≤ 72 h', 'sun_pct': 80.0, 'both_pct': 50.0, 'sun_gap_h': 72},
    {'id': 'loose', 'label': 'Looser: Sun ≥ 60 %, Sun+Earth ≥ 30 %, Sun gap ≤ 168 h', 'sun_pct': 60.0, 'both_pct': 30.0, 'sun_gap_h': 168},
]
METRICS = {
    'sun_pct': ('sun_n', '%', 'Sun centre visible', True),
    'sun_earth_pct': ('both_n', '%', 'Sun and Earth centre visible', True),
    'earth_pct': ('earth_n', '%', 'Earth centre visible', True),
    'sun_gap_h': ('sun_gap_h', 'h', 'Longest Sun gap (hourly samples)', False),
    'earth_gap_h': ('earth_gap_h', 'h', 'Longest Earth gap (hourly samples)', False),
}


def _iso(t):
    return dt.datetime.fromtimestamp(float(t), dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ')


def site_inputs(site):
    b = json.loads(BUNDLE[site].read_text())
    s = b['site']
    eph = E.load(site, s['lat_deg'], s['lon_deg_east'], s['height_m'])
    return b, eph


def series(site, eph, t_id, mast=1.0, dx=0, dy=0, stride=1):
    sky = C.skyline(site, t_id, mast, dx, dy)
    if dx == 0 and dy == 0:
        f = C.visible_flags(eph, sky)
    else:
        s = C.sites.SITES[site]
        la, lo = C.offset_latlon(site, dx, dy)
        f = C.visible_flags(eph, sky, s['lat'], s['lon'], la, lo)
    w = C.window_metrics(f['sun'], f['earth'], E.N_STARTS, E.WINDOW_H, stride)
    w['missing'] = f['sun_missing'] | f['earth_missing']
    return w, sky


def _metric_block(arr, key, n_samples):
    src, units, label, is_pct = METRICS[key]
    m = {'units': units, 'label': label, 'dtype': 'int32', 'values': arr.reshape(-1).astype(int).tolist(),
         'provenance': 'science/cube/compute.py window_metrics on science/skyline.compute_skyline + JPL Horizons hourly'}
    if is_pct:
        m['scale'] = 100.0 / n_samples; m['decimals'] = 2
        m['description'] = f'stored = visible hourly samples of {n_samples}; display = stored x 100/{n_samples}'
    else:
        m['decimals'] = 0
    return m


def _pct(counts, n):
    return counts * (100.0 / n)


def robust(cube_vals, n, design_dim):
    """cube_vals[key] arrays shaped (T, D, S). Returns derived blocks."""
    sun = _pct(cube_vals['sun_n'], n); both = _pct(cube_vals['both_n'], n); gap = cube_vals['sun_gap_h']
    out = {}
    band = {}
    for key, (src, units, label, is_pct) in METRICS.items():
        a = cube_vals[src]
        for agg, fn in (('min', np.min), ('max', np.max)):
            band[f'{key}_{agg}'] = {'units': units, 'label': f'{label}: {agg} over T (21 maps)', 'dtype': 'int32',
                                    'values': fn(a, axis=0).reshape(-1).astype(int).tolist(),
                                    'provenance': 'min/max over the T axis of the parent cube',
                                    **({'scale': 100.0 / n, 'decimals': 2} if is_pct else {'decimals': 0})}
    out['band_over_T'] = {'dims': [design_dim, 'S'], 'metrics': band,
                          'method': 'element-wise min and max over T (nominal + 20 clones) of the parent metric',
                          'caveat': 'range over 21 deterministic maps, not a confidence interval'}
    k = np.zeros((len(R_PRESETS),) + sun.shape[1:], int); nom = np.zeros_like(k)
    for i, r in enumerate(R_PRESETS):
        ok = (sun >= r['sun_pct'] - 1e-9) & (both >= r['both_pct'] - 1e-9) & (gap <= r['sun_gap_h'])
        k[i] = ok[1:].sum(axis=0); nom[i] = ok[0]
    rdim = {'name': 'R', 'kind': 'requirement', 'values': [r['id'] for r in R_PRESETS],
            'value_labels': [r['label'] for r in R_PRESETS], 'units': '', 'label': 'Requirement preset', 'nominal_index': 0,
            'note': json.dumps([{kk: v for kk, v in r.items() if kk != 'label'} for r in R_PRESETS])}
    out['k_of_N'] = {'dims': [rdim, design_dim, 'S'], 'metrics': {
        'k_pass': {'units': 'maps of 20', 'label': 'Clone maps passing all of R', 'dtype': 'int32',
                   'values': k.reshape(-1).tolist(), 'provenance': 'count over clones 1-20 of the parent cube', 'decimals': 0},
        'nominal_pass': {'units': '', 'label': 'Nominal map passes all of R', 'dtype': 'bool',
                         'values': nom.reshape(-1).astype(bool).tolist(), 'provenance': 'nominal map of the parent cube'}},
        'method': 'pass = Sun % >= R.sun_pct AND Sun+Earth % >= R.both_pct AND longest Sun gap <= R.sun_gap_h',
        'caveat': NOT_PROB}
    # regret on Sun+Earth %: choose D on the nominal map, truth is clone k
    dstar = np.argmax(both[0], axis=0)                      # (S,)
    best_k = both[1:].max(axis=1)                           # (20, S)
    chosen_k = np.take_along_axis(both[1:], dstar[None, None, :], axis=1)[:, 0, :]
    reg = best_k - chosen_k
    out['regret'] = {'dims': ['S'], 'metrics': {
        'chosen_index': {'units': 'index', 'label': f'{design_dim} chosen on the nominal map (max Sun+Earth %)', 'dtype': 'int32',
                         'values': dstar.astype(int).tolist(), 'provenance': 'argmax over D of nominal Sun+Earth %'},
        'regret_max_pct': {'units': 'pct points', 'label': 'Max regret over clones (Sun+Earth %)', 'dtype': 'float64', 'decimals': 2,
                           'values': np.round(reg.max(axis=0), 4).tolist(), 'provenance': 'max_k [max_D m_k(D) - m_k(D*)]'},
        'regret_worst_clone': {'units': 'clone', 'label': 'Clone giving the max regret', 'dtype': 'int32',
                               'values': (np.argmax(reg, axis=0) + 1).astype(int).tolist(), 'provenance': 'argmax over k'}},
        'method': 'D* = argmax_D Sun+Earth % on the nominal map; regret_k = max_D m_k(D) - m_k(D*); reported max over k (ties -> lowest index)',
        'caveat': 'regret within this design set and these 20 maps only'}
    flips = (k[0] > 0) & (k[0] < 20)                       # (D, S) team preset
    out['decision_changes'] = {'dims': [design_dim], 'metrics': {
        'share_starts_verdict_depends_on_T': {'units': '%', 'label': 'Share of starts where the team verdict differs between clone maps',
                                              'dtype': 'float64', 'decimals': 1,
                                              'values': np.round(100 * flips.mean(axis=1), 3).tolist(), 'provenance': 'mean over S of 0 < k < 20 (team R)'},
        'flips_at_demo_start': {'units': '', 'label': 'Verdict depends on map at the 2026-11-14 start', 'dtype': 'bool',
                                'values': flips[:, 0].astype(bool).tolist(), 'provenance': '0 < k < 20 at S index 0 (team R)'}},
        'method': 'team preset; a D cell "changes under T" when some but not all 20 clone maps pass', 'caveat': NOT_PROB}
    return out


def _gz(path, obj):
    raw = json.dumps(obj, separators=(',', ':')).encode()
    path.write_bytes(gzip.compress(raw, mtime=0, compresslevel=9))
    return len(raw)


def _dims(eph, design, stride):
    starts = eph['t'][:E.N_STARTS:stride]
    T = {'name': 'T', 'kind': 'uncertainty_terrain', 'values': list(C.T_IDS), 'units': '', 'nominal_index': 0,
         'label': 'Terrain map: PGDA 78 nominal + 20 error clones', 'note': NOT_PROB}
    S = {'name': 'S', 'kind': 'schedule', 'values': [int(t) for t in starts], 'units': 'unix s (UTC)',
         'label': 'Window start (14 d window)' + (' — hourly' if stride == 1 else ' — daily 00:00 UTC'),
         'nominal_index': 0, 'value_labels': [_iso(t) for t in starts]}
    return [T, design, S]


def _provenance(site, eph, extra):
    ins = [{'path': str(BUNDLE[site].relative_to(ROOT)), 'sha256': sha256_file(BUNDLE[site]), 'note': 'site position + height, baseline'}]
    for p in eph['prov']:
        f = ROOT / p['path']
        ins.append({'path': p['path'], 'sha256': p['sha256'], 'url': 'https://ssd.jpl.nasa.gov/api/horizons.api',
                    'note': f'JPL Horizons {p["body"]} hourly 2026-11-14..2027-11-28 (git-ignored cache)'})
    sky_files = sorted(C.SKY.glob(f'{site}_*.json'))
    h = hashlib.sha256()
    for f in sky_files:
        h.update(f.name.encode()); h.update(f.read_bytes())
    ins.append({'path': f'data/cache/cube_sky/{site}_*.json', 'sha256': h.hexdigest(),
                'note': f'{len(sky_files)} cached skylines (combined hash of name+bytes); NASA PGDA 78 5 m + clones, PGDA 90 80 m'})
    ins += extra
    return {'inputs': ins, 'command': 'python -m science.cube.build_cube ' + ' '.join(sys.argv[1:]),
            'code_commit': git_commit(), 'solver': 'science/skyline.compute_skyline (float64), 720 bins, 1 m near step, 280 km'}


def build_centre_mast(site, eph):
    vals = {k: np.zeros((len(C.T_IDS), len(C.MASTS), E.N_STARTS), np.int32) for k in ('sun_n', 'both_n', 'earth_n', 'sun_gap_h', 'earth_gap_h')}
    miss = []
    for i, t in enumerate(C.T_IDS):
        for j, m in enumerate(C.MASTS):
            w, _ = series(site, eph, t, m)
            for k in vals:
                vals[k][i, j] = w[k]
            if w['missing'].any():
                miss.append((i, j, int(w['missing'].sum())))
    n = E.WINDOW_H + 1
    design = {'name': 'D_mast', 'kind': 'design', 'values': list(C.MASTS), 'units': 'm', 'nominal_index': 0,
              'label': 'Observer height above ground (mast)'}
    cube = {'schema': 'scenario-cube-v1', 'cube_id': f'{site}-centre-mast-schedule-v1', 'site_id': site,
            'title': 'Centre position: terrain map x mast height x start', 'label': LABEL,
            'generated_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'description': 'Centre-of-disk geometric visibility over a 14-day window, per window start, map and mast height.',
            'fixed': {'position': 'bundle site (PGDA 78 RoI centroid)', 'visibility_rule': 'centre', 'window_h': E.WINDOW_H},
            'dims': _dims(eph, design, 1),
            'metrics': {key: _metric_block(vals[src], key, n) for key, (src, *_r) in METRICS.items()},
            'missing': {'encoding': 'sparse-flat-index', 'by_metric': {k: [] for k in METRICS},
                        'reasons': {} if not miss else {'note': f'{len(miss)} (T, D) series touch no-data skyline bins; affected samples counted hidden'}},
            'derived': robust(vals, n, 'D_mast'),
            'provenance': _provenance(site, eph, []),
            'limitations': ['Local geometric visibility only: not power, not a DSN link.',
                            NOT_PROB, 'Gaps are runs of hidden hourly samples (x 1 h); the bundles also give bisection-refined gaps.']}
    return cube, vals


def build_position(site, eph):
    starts_idx = np.arange(0, E.N_STARTS, DAILY_STRIDE)
    vals = {k: np.zeros((len(C.T_IDS), len(C.OFFSETS), starts_idx.size), np.int32) for k in ('sun_n', 'both_n', 'earth_n', 'sun_gap_h', 'earth_gap_h')}
    for i, t in enumerate(C.T_IDS):
        for j, (dx, dy) in enumerate(C.OFFSETS):
            w, _ = series(site, eph, t, 1.0, dx, dy, DAILY_STRIDE)
            for k in vals:
                vals[k][i, j] = w[k]
    n = E.WINDOW_H + 1
    design = {'name': 'D_pos', 'kind': 'design', 'values': [f'{dx},{dy}' for dx, dy in C.OFFSETS], 'units': 'grid m (dx,dy)',
              'nominal_index': C.OFFSETS.index((0, 0)),
              'label': 'Position offset from the site, polar-stereographic grid metres (9 x 9, 25 m step)',
              'note': 'row-major: dx outer (-100..100), dy inner (-100..100)'}
    cube = {'schema': 'scenario-cube-v1', 'cube_id': f'{site}-position-schedule-v1', 'site_id': site,
            'title': 'Position grid: terrain map x position x daily start', 'label': LABEL,
            'generated_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'description': '81-cell position grid at mast 1 m; ephemeris re-expressed at each offset (direction transfer).',
            'fixed': {'mast_m': 1.0, 'visibility_rule': 'centre', 'window_h': E.WINDOW_H},
            'dims': _dims(eph, design, DAILY_STRIDE),
            'metrics': {key: _metric_block(vals[src], key, n) for key, (src, *_r) in METRICS.items()},
            'missing': {'encoding': 'sparse-flat-index', 'by_metric': {k: [] for k in METRICS}},
            'derived': robust(vals, n, 'D_pos'),
            'provenance': _provenance(site, eph, []),
            'limitations': ['Local geometric visibility only.', NOT_PROB,
                            'Daily starts (00:00 UTC) on this cube; hourly starts are on centre_mast_schedule.']}
    return cube, vals


def build_products(site):
    """M axis from the research results (not recomputed here)."""
    key = RESEARCH_KEY[site]
    lens_p = RES / f'lens_{key}.json'
    lens = json.loads(lens_p.read_text())
    prods = list(lens['products'])
    extra = [{'path': str(lens_p.relative_to(ROOT)), 'sha256': sha256_file(lens_p), 'note': 'M axis: four NASA terrain products'}]
    sfs_p = RES / 'sfs_result.json'
    sfs = json.loads(sfs_p.read_text()).get(key)
    sfs_row = None
    if sfs and 'region' in sfs or (sfs and site == 'site01_roi6'):
        m1 = next((m for m in sfs['masts'] if m['mast'] == 1), None)
        if m1 and 'region' not in sfs or (m1 and sfs.get('cover_frac', 1.0) > 0):
            sfs_row = {'label': 'GSFC SfS (Bertone et al. 2026) + PGDA 90 80 m', 'ground_m': m1['ground_m'], 'sun': m1['sun'],
                       'both': m1['both'], 'year': m1['year']}
            extra.append({'path': str(sfs_p.relative_to(ROOT)), 'sha256': sha256_file(sfs_p), 'note': 'M axis: SfS product'})
    labels = [p['label'] for p in prods] + ['GSFC SfS (Bertone et al. 2026) + PGDA 90 80 m']
    rows = prods + [sfs_row]
    vals = {'sun_pct': [], 'sun_earth_pct': [], 'year_sun_pct': []}
    miss = {k: [] for k in vals}
    for i, r in enumerate(rows):
        for k, src in (('sun_pct', 'sun'), ('sun_earth_pct', 'both'), ('year_sun_pct', 'year')):
            v = None if r is None else r.get(src)
            vals[k].append(v)
            if v is None:
                miss[k].append(i)
    mk = lambda k, lab, prov: {'units': '%', 'label': lab, 'dtype': 'float64', 'decimals': 2, 'values': vals[k], 'provenance': prov}
    return {'schema': 'scenario-cube-v1', 'cube_id': f'{site}-products-v1', 'site_id': site,
            'title': 'Terrain data product (M axis)', 'label': LABEL,
            'generated_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'description': 'Same 1 m mast, centre position and ephemeris on different NASA terrain products.',
            'fixed': {'mast_m': 1.0, 'position': 'bundle site', 'T': 'nominal', 'window': '2026-11-14 + 14 d (12 months for year_sun_pct)'},
            'dims': [{'name': 'M', 'kind': 'uncertainty_model', 'values': labels, 'units': '', 'label': 'Terrain data product', 'nominal_index': 0}],
            'metrics': {'sun_pct': mk('sun_pct', 'Sun centre visible (demo window)', 'research/long_features lens/sfs results'),
                        'sun_earth_pct': mk('sun_earth_pct', 'Sun and Earth centre visible (demo window)', 'research/long_features lens/sfs results'),
                        'year_sun_pct': mk('year_sun_pct', 'Sun centre visible (12 months hourly)', 'research/long_features lens/sfs results')},
            'missing': {'encoding': 'sparse-flat-index', 'by_metric': miss,
                        'reasons': {'sfs': 'SfS DEM does not cover this site in the research run' if sfs_row is None else ''}},
            'provenance': {'inputs': extra, 'command': 'python -m science.cube.build_cube', 'code_commit': git_commit(),
                           'solver': 'research/long_features (polaris_batch), copied not recomputed'},
            'limitations': ['Values copied from the research handoff; the research solver samples differently from the repo solver (fractions of a percent).']}


def build_site(site):
    b, eph = site_inputs(site)
    d = OUT / site
    d.mkdir(parents=True, exist_ok=True)
    files = []
    c1, v1 = build_centre_mast(site, eph)
    raw1 = _gz(d / 'centre_mast_schedule.json.gz', c1)
    c2, v2 = build_position(site, eph)
    raw2 = _gz(d / 'position_schedule.json.gz', c2)
    c3 = build_products(site)
    (d / 'products.json').write_text(json.dumps(c3, indent=1) + '\n')
    for name, raw, c in (('centre_mast_schedule.json.gz', raw1, c1), ('position_schedule.json.gz', raw2, c2), ('products.json', None, c3)):
        p = d / name
        files.append({'file': name, 'cube_id': c['cube_id'], 'title': c['title'], 'bytes': p.stat().st_size,
                      'uncompressed_bytes': raw or p.stat().st_size, 'sha256': sha256_file(p),
                      'dims': [x['name'] for x in c['dims']]})
    idx = {'schema': 'scenario-cube-index-v1', 'site_id': site, 'label': LABEL, 'cubes': files,
           'baseline': baseline_check(b, c1)}
    (d / 'index.json').write_text(json.dumps(idx, indent=1) + '\n')
    return idx


def baseline_check(b, c1):
    """Round-trip: cube cell (nominal, 1 m, start 0) vs the bundle's hourly-sample metrics."""
    m = b['metrics']; n = E.WINDOW_H + 1
    get = lambda k: c1['metrics'][k]['values'][0]
    return {'bundle': b['bundle_id'],
            'sun_pct': {'cube': round(get('sun_pct') * 100 / n, 3), 'bundle': m['sun_center_visible_pct_hourly_samples']},
            'sun_earth_pct': {'cube': round(get('sun_earth_pct') * 100 / n, 3), 'bundle': m['sun_and_earth_center_visible_pct_hourly_samples']},
            'earth_pct': {'cube': round(get('earth_pct') * 100 / n, 3), 'bundle': m['earth_center_visible_pct_hourly_samples']},
            'sun_gap_h': {'cube': get('sun_gap_h'), 'bundle_bisected_h': m['longest_sun_center_hidden_h']}}


if __name__ == '__main__':
    for s in sys.argv[1:] or ['site04_roi3', 'site01_roi6']:
        idx = build_site(s)
        print(json.dumps(idx, indent=1))
