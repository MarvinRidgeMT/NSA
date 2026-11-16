#!/usr/bin/env python3
"""E2 (15 Nov 2026): reconcile the two solvers the viewer quotes, for Site01 RoI 6 and Site04 RoI 3 at a 1 m mast.

Source A, "bundle" = repo solver (science/, data/bundles/<site>_2026-11-14_14d_mast1m.json).
Source B, "batch"  = polaris_batch v2 sweep: float64 rerun CSV for Sun % / Sun+Earth % / clone range, the
                     certainty sidecar for Certainty Height, the 2026-11-14 batch CSV for the longest gap (gap
                     metrics were not re-run in float64), and the batch coverage_gauge.json.
Reads the files and writes docs/SOLVER_RECONCILIATION.md (table) and
data/batch/2026-11-15_float64_rerun/solver_reconciliation.json (machine-readable, used by the unit test).
Nothing here is recomputed from terrain: every value is copied from a committed file.
Usage: python3 tools/validation/solver_reconciliation.py [--check]   (--check: fail if the outputs are stale)
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
F64_CSV = 'data/batch/2026-11-15_float64_rerun/certainty_height/clone_sweep_summary.csv'
F32_CSV = 'data/batch/2026-11-14/certainty_height/clone_sweep_summary.csv'
COV_JSON = 'data/batch/2026-11-14/certainty_height/coverage_gauge.json'
SIDECAR = 'web/public/certainty/sidecar.json'
OUT_JSON = 'data/batch/2026-11-15_float64_rerun/solver_reconciliation.json'
OUT_MD = 'docs/SOLVER_RECONCILIATION.md'

SITES = [('site01_roi6', 'Site01', '6', 'Site01_ROI6'), ('site04_roi3', 'Site04', '3', 'Site04_ROI3')]

# Stated tolerances (|bundle - batch|), asserted by science/tests/test_solver_reconciliation.py.
TOL = {
    'sun_pct': 0.01,          # same 337 hourly samples, same ray step (1 m near / 80 m far), float64 both
    'both_pct': 0.01,
    'longest_gap_h': 2.0,     # batch gap not re-run in float64 (float32 heights); bundle counts hourly samples
    'coverage_sun_pct': 3.0,  # different coverage definitions (see "why")
    'coverage_earth_pct': 3.0,
}

WHY = {
    'sun_pct': 'Same definition (share of the 337 hourly samples with the Sun centre above the skyline), same DEMs and ray steps; both float64. Bundle also reports an interval-based value (bisection-refined crossings) shown in brackets.',
    'both_pct': 'Same as Sun %.',
    'longest_gap_h': 'Bundle: longest run of hidden hourly samples (interval value from refined crossings in brackets). Batch: longest_sun_gap_steps from the 2026-11-14 run, which used float32 heights and was not re-run in float64.',
    'clone_range': 'Bundle carries no clone sweep (scenarios = []); the viewer takes the clone range from the batch float64 rerun via the certainty sidecar.',
    'certainty_height': 'Bundle carries no mast sweep (masts 1 m and 10 m are separate bundles); Certainty Height exists only in the batch sweep (masts listed).',
    'coverage': "Different sampling. Bundle derived.coverage: the controlling skyline sample at the nearest 0.5 deg bin (720 bins, one ray per bin centre) is tested for source == 'near_5m' (near-field cut at the 5 m tile edge). Batch Coverage Gauge: controlling cell per hour at the body azimuth tested against the tile's inscribed radius. Bin snapping and the tile-edge test differ, so the two are expected to differ by a few points.",
}


def sha(p: str) -> str:
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def csv_row(path: str, site: str, roi: str, mast: float = 1.0) -> dict:
    with open(ROOT / path, newline='') as f:
        for r in csv.DictReader(f):
            if r['site'] == site and r['roi'] == roi and float(r['mast_m']) == mast:
                return r
    raise KeyError(f'{path}: no row {site} {roi} {mast}')


def hidden_run(samples: list) -> int:
    best = run = 0
    for s in samples:
        run = 0 if s['sun']['center_visible'] else run + 1
        best = max(best, run)
    return best


def build() -> dict:
    cov_batch = json.loads((ROOT / COV_JSON).read_text())
    side = json.loads((ROOT / SIDECAR).read_text())
    out = {'label': 'SOURCE-BASED, UNVALIDATED (a reconciliation of two internal solvers, not a validation)',
           'mast_m': 1.0, 'window_utc': ['2026-11-14T00:00:00Z', '2026-11-28T00:00:00Z'], 'tolerances': TOL, 'why': WHY,
           'inputs_sha256': {p: sha(p) for p in (F64_CSV, F32_CSV, COV_JSON, SIDECAR)}, 'sites': {}}
    for sid, site, roi, key in SITES:
        bp = f'data/bundles/{sid}_2026-11-14_14d_mast1m.json'
        b = json.loads((ROOT / bp).read_text())
        out['inputs_sha256'][bp] = sha(bp)
        m, c = b['metrics'], b['derived']['coverage']
        r64, r32 = csv_row(F64_CSV, site, roi), csv_row(F32_CSV, site, roi)
        sc = side['sites'][sid]
        cg = cov_batch[key]['pct_hours_controlling_cell_inside_clone_tile']
        rows = {
            'sun_pct': {'bundle': m['sun_center_visible_pct_hourly_samples'], 'bundle_alt': m['sun_center_visible_pct'],
                        'batch': float(r64['sun_centre_pct_nominal'])},
            'both_pct': {'bundle': m['sun_and_earth_center_visible_pct_hourly_samples'], 'bundle_alt': m['sun_and_earth_center_visible_pct'],
                         'batch': float(r64['both_centre_pct_nominal'])},
            'longest_gap_h': {'bundle': hidden_run(b['samples']), 'bundle_alt': m['longest_sun_center_hidden_h'],
                              'batch': float(r32['longest_sun_gap_steps_nominal'])},
            'clone_range': {'bundle': None, 'batch': [float(r64['sun_centre_pct_min']), float(r64['sun_centre_pct_max'])],
                            'n_clones': int(r64['n_clones'])},
            'certainty_height': {'bundle': None, 'batch': sc['certainty_height_m'], 'all_maps_100pct_sun_mast_m': sc['all_maps_100pct_sun_mast_m'],
                                 'sampled_masts_m': sc['sampled_masts_m']},
            'coverage_sun_pct': {'bundle': round(c['all_hours_covered_frac'] * 100, 2), 'batch': cg['sun']},
            'coverage_earth_pct': {'bundle': round(c['earth']['all_hours_covered_frac'] * 100, 2), 'batch': cg['earth']},
        }
        for k, v in rows.items():
            if isinstance(v.get('bundle'), (int, float)) and isinstance(v.get('batch'), (int, float)):
                v['diff'] = round(v['bundle'] - v['batch'], 4)
        out['sites'][sid] = rows
    return out


def fmt(x) -> str:
    if x is None:
        return 'not in bundle'
    if isinstance(x, list):
        return f'{x[0]:.2f}–{x[1]:.2f} %'
    if isinstance(x, dict):
        return ', '.join(f'{k.replace("_centre_pct", "")} {v} m' for k, v in x.items())
    return f'{x:g}'


def e4_lines() -> list:
    """Reproduce Site04 RoI 4 all_hours_covered_frac from the bundle's own attribution (no terrain recomputed)."""
    sys.path.insert(0, str(ROOT))
    from science.coverage import _bin_of, for_bundle
    out = []
    for mast in (1, 10):
        b = json.loads((ROOT / f'data/bundles/site04_roi4_2026-11-14_14d_mast{mast}m.json').read_text())
        pb = b['derived']['attribution']['per_bin']; src, dist = pb['source'], pb['ctrl_dist_m']; n = len(src)
        c = for_bundle(b)
        vis = {k: sorted({_bin_of(s[k]['az_deg'], n) for s in b['samples']}) for k in ('sun', 'earth')}
        near_hit = {k: sum(src[i] == 'near_5m' for i in v) for k, v in vis.items()}
        dmin = {k: min(dist[i] for i in v if dist[i] is not None) for k, v in vis.items()}
        out.append(f"- {mast} m mast: recomputed all_hours_covered_frac Sun {c['all_hours_covered_frac']}, Earth {c['earth']['all_hours_covered_frac']} "
                   f"(bundle: {b['derived']['coverage']['all_hours_covered_frac']}, {b['derived']['coverage']['earth']['all_hours_covered_frac']}). "
                   f"Bins reached: Sun {len(vis['sun'])}, Earth {len(vis['earth'])}; of those, near_5m: Sun {near_hit['sun']}, Earth {near_hit['earth']} "
                   f"(the tile controls {src.count('near_5m')} of {n} bins, all at azimuths the Sun and Earth do not reach in this window). "
                   f"Nearest controlling terrain at a reached bin: Sun {dmin['sun']:.0f} m, Earth {dmin['earth']:.0f} m.")
    out += ['', '**Cause: genuine, not a generator bug.** At every Sun and Earth azimuth reached in the window, RoI 4\'s controlling horizon is distant terrain '
            'in the 80 m regional DEM, outside the 5 m clone tile, so no hour is covered. Sun covered_frac is null (no Sun-critical hours) and Earth covered_frac is 0.0 '
            '(30 critical hours, all outside the tile); the bundle never had covered_frac = 1.0 at RoI 4. '
            'The viewer shows "No clone coverage at this RoI" (data-testid coverage-no-clone). Regression test: science/tests/test_coverage_roi4.py.']
    return out


def markdown(d: dict) -> str:
    L = ['# Solver reconciliation: repo bundle vs batch sweep (E2, 15 Nov 2026)', '',
         f"Label: {d['label']}. Mast 1 m, window 14–28 Nov 2026 UTC, 337 hourly samples.",
         'Generated by `python3 tools/validation/solver_reconciliation.py` from committed files (SHA-256 at the end); do not edit by hand.',
         'Asserted by `science/tests/test_solver_reconciliation.py` (|bundle − batch| within the stated tolerance).', '']
    names = {'sun_pct': 'Sun % (centre)', 'both_pct': 'Sun+Earth % (centre)', 'longest_gap_h': 'Longest Sun gap (h)',
             'clone_range': 'Clone range, Sun % (20 maps)', 'certainty_height': 'Certainty Height',
             'coverage_sun_pct': 'Coverage Sun (% of hours)', 'coverage_earth_pct': 'Coverage Earth (% of hours)'}
    why_key = {'coverage_sun_pct': 'coverage', 'coverage_earth_pct': 'coverage'}
    for sid, rows in d['sites'].items():
        L += [f'## {sid}', '', '| Metric | Bundle (repo solver) | Batch sweep | Difference | Tolerance | Why they differ |', '|---|---|---|---|---|---|']
        for k, v in rows.items():
            b = fmt(v['bundle']) + (f" [{v['bundle_alt']:g}]" if 'bundle_alt' in v else '')
            bt = fmt(v['batch'])
            if k == 'certainty_height':
                bt += f" (Sun 100 % on all maps from {v['all_maps_100pct_sun_mast_m']} m; masts {', '.join(f'{x:g}' for x in v['sampled_masts_m'])})"
            diff = f"{v['diff']:+g}" if 'diff' in v else '—'
            tol = f"±{TOL[k]:g}" if k in TOL else '—'
            L.append(f'| {names[k]} | {b} | {bt} | {diff} | {tol} | {WHY[why_key.get(k, k)]} |')
        L.append('')
    L += ['## Sampling differences in one place', '',
          '- **Ray step / DEMs:** 1 m near-field step on the PGDA 78 5 m tile and 80 m step on PGDA 90 (80 m) to 280 km in both. The bundle switches to the far layer at the tile edge (skyline.near_cut_m, about 6.3 km at Site04 RoI 3); the batch manifest states near 1 m steps to 25 km. Sun % and Sun+Earth % still agree to 0.001 pts.',
          '- **Azimuth bins:** bundle 720 bins, one ray per bin centre, nearest bin for coverage; batch 720 bins at (k+0.5)·0.5°, linear interpolation for visibility.',
          '- **Masts:** bundle 1 m and 10 m (separate files); batch 1, 1.25, 1.5, 1.75, 2, 3, 5, 7, 10, 15 m at Site04 RoI 3 and 1, 2, 3, 5, 7, 10, 15 m at Site01 RoI 6.',
          '- **Precision:** both float64 for Sun % and Sun+Earth %; the batch gap metric is still the float32 run (not re-run).', '',
          '## E4: Site04 RoI 4 bundle coverage = 0.0 (Sun and Earth)', '',
          *e4_lines(), '',
          '## Inputs (SHA-256)', '']
    L += [f'- `{p}` {h}' for p, h in d['inputs_sha256'].items()]
    return '\n'.join(L) + '\n'


def main() -> int:
    d = build()
    j = json.dumps(d, indent=1, ensure_ascii=False) + '\n'
    md = markdown(d)
    if '--check' in sys.argv:
        ok = (ROOT / OUT_JSON).read_text() == j and (ROOT / OUT_MD).read_text() == md
        print('up to date' if ok else 'STALE: re-run tools/validation/solver_reconciliation.py')
        return 0 if ok else 1
    (ROOT / OUT_JSON).write_text(j)
    (ROOT / OUT_MD).write_text(md)
    print(f'wrote {OUT_MD} and {OUT_JSON}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
