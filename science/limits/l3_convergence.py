"""L3 (numerical part) — convergence of the skyline settings, at Site04 RoI 3 and Site01 RoI 6,
nominal map + clones 1 and 11, demo window, 1 m mast.

Refinements tested against the bundle baseline (720 bins, 1 m near step, near cut = inscribed
radius of the 5 m tile ~6.3 km, PGDA 90 80 m far field to 280 km):
  bins 720 -> 1440 -> 2880; near step 1 -> 0.5 m; far range 280 -> 289 km (edge of the loaded
  +-290 km far-DEM window; beyond that the L3 analytic bound applies).
Not testable on this Mac tonight: near radius 25/50 km (the 5 m tile is ~16 km wide, so the near
field cannot reach 25 km) and far DEM 40/20 m (PGDA 90 40/20 m rasters not cached).
Metrics: Sun % (hourly centre) and horizon elevation change, max and median |dE| over bins (the
finer-bin skyline is compared at the baseline bin azimuths).
Pass criterion: every refinement changes Sun % by < 0.1 pt.
"""
from __future__ import annotations

import numpy as np

from . import skylines as S
from .common import BUNDLES, load_bundle, write_result
from .l1_disc import hourly_terms

CASES = {
    'baseline': dict(bins=720, step_m=1.0, max_range_m=280_000.0),
    'bins1440': dict(bins=1440, step_m=1.0, max_range_m=280_000.0),
    'bins2880': dict(bins=2880, step_m=1.0, max_range_m=280_000.0),
    'step0.5': dict(bins=720, step_m=0.5, max_range_m=280_000.0),
    'range289km': dict(bins=720, step_m=1.0, max_range_m=289_000.0),
}
MAPS = (None,)  # nominal only tonight (time box); clones 1 and 11 open


def at_base_az(sky, n_base=720):
    E = np.array([np.nan if e is None else e for e in sky['elevation_deg']], float)
    k = sky['bins'] // n_base
    return E[::k]


def run():
    out = {}
    for site in BUNDLES:
        b = load_bundle(site); out[site] = {}
        for c in MAPS:
            name = 'nominal' if c is None else f'clone{c:02d}'
            base = None; rows = {}
            for case, kw in CASES.items():
                sky = S.skyline(site, clone=c, **kw)
                sun = 100 * float((hourly_terms(b, sky)['sun']['mp'] > 0).mean())
                E = at_base_az(sky)
                if base is None:
                    base = (sun, E)
                dE = np.abs(E - base[1])
                rows[case] = {'sun_pct': round(sun, 3), 'd_sun_pct': round(sun - base[0], 3),
                              'max_abs_dE_deg': round(float(np.nanmax(dE)), 5),
                              'median_abs_dE_deg': round(float(np.nanmedian(dE)), 6),
                              'n_truncated': sky['n_truncated']}
                print(site, name, case, rows[case], flush=True)
            out[site][name] = rows
    worst = {case: max(abs(out[s][m][case]['d_sun_pct']) for s in out for m in out[s]) for case in CASES}
    return {'item': 'L3_convergence', 'cases': CASES, 'sites': out, 'worst_abs_d_sun_pct': worst,
            'pass_lt_0p1pt': {k: v < 0.1 for k, v in worst.items()},
            'not_tested': {'near_radius_25_50km': '5 m tile is ~16 km wide; inscribed near cut ~6.3 km is the maximum',
                           'far_dem_40_20m': 'PGDA 90 40/20 m rasters not cached on this Mac',
                           'far_range_600km': 'far DEM window is +-290 km; L3 analytic bound covers beyond 280 km'}}


README = """# L3 (numerical part) — convergence of skyline settings

**Label:** PILOT · SOURCE-BASED · UNVALIDATED.

**Question.** Are the bundle settings (720 bins, 1 m near ray step, 280 km range) converged for Sun %?

**Method.** `python -m science.limits.l3_convergence`. Site04 RoI 3 and Site01 RoI 6, nominal + clones 1 and 11, 1 m mast,
337 hourly samples, 14–28 Nov 2026. Refinements: bins 1440 and 2880, near step 0.5 m, far range 289 km (the edge of the
loaded far-DEM window). Each is compared with the baseline: ΔSun %, and max/median |Δ horizon elevation| at the
baseline bin azimuths.

**Pass criterion.** Every refinement changes Sun % by < 0.1 pt. See `result.json` → `pass_lt_0p1pt` and `RESULT.md`.

**Not tested.** A 25/50 km near radius (the 5 m tile is ~16 km wide). The far DEM at 40/20 m (not cached on this Mac).
A 600 km range (outside the loaded far window; `L3_far_bound` shows no hour can change from terrain beyond 280 km).
"""


def table_md(res):
    L = ['| site | map | case | Sun % | ΔSun % | max |ΔE| ° | median |ΔE| ° |', '|---|---|---|---|---|---|---|']
    for s, maps in res['sites'].items():
        for m, rows in maps.items():
            for case, r in rows.items():
                L.append(f"| {s} | {m} | {case} | {r['sun_pct']:.3f} | {r['d_sun_pct']:+.3f} | {r['max_abs_dE_deg']:.4f} | {r['median_abs_dE_deg']:.5f} |")
    L += ['', '| case | worst |ΔSun %| | pass (< 0.1 pt) |', '|---|---|---|']
    for k, v in res['worst_abs_d_sun_pct'].items():
        L.append(f"| {k} | {v:.3f} | {'yes' if res['pass_lt_0p1pt'][k] else 'NO'} |")
    return '# L3 convergence table\n\nPILOT · SOURCE-BASED · UNVALIDATED.\n\n' + '\n'.join(L) + '\n'


def main():
    res = run()
    write_result('L3_convergence', res, list(BUNDLES.values()), README, {'RESULT.md': table_md(res)})
    print(table_md(res))


if __name__ == '__main__':
    main()
