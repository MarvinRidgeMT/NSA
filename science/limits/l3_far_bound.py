"""L3 (analytic part) — ignored-terrain bound beyond the 280 km far-field range.

For an observer at radius r0 = R + h_ground + mast, a terrain point at great-circle angle a = d/R
and radius r = R + H has elevation angle e with tan e = (r cos a - r0) / (r sin a), so the height
needed to reach elevation e at distance d is   H(d, e) = r0 cos e / cos(a + e) - R.
We compare H against (i) the highest height in the far DEM actually loaded (PGDA 90, +-290 km
window) and (ii) a global upper bound for lunar relief, 10.8 km above 1737.4 km (LOLA global max,
Smith et al. 2010, ~10.786 km) — terrain beyond 280 km cannot be taller than that.
The threshold elevation is the lowest skyline elevation in the azimuth range the Sun (or Earth)
actually crosses in the window minus the body radius (any part of the disc), i.e. the lowest
elevation at which extra terrain could change any L1 variant.
"""
from __future__ import annotations

import math

import numpy as np

from .. import frames
from .common import BUNDLES, load_bundle, write_result

R = frames.R_MOON_M
H_GLOBAL_MAX_M = 10_800.0
DISTANCES_KM = (280, 300, 400, 600, 800, 1000, 1500)


def h_needed(r0, d_m, e_deg):
    a = d_m / R; e = math.radians(e_deg)
    c = math.cos(a + e)
    return math.inf if c <= 0 else r0 * math.cos(e) / c - R


def e_of(r0, d_m, H):
    a = d_m / R; r = R + H
    return math.degrees(math.atan2(r * math.cos(a) - r0, r * math.sin(a)))


def site(site_id):
    b = load_bundle(site_id)
    r0 = R + b['site']['height_m'] + b['site']['observer_mast_m']
    sk = b['skyline']; E = np.array([np.nan if e is None else e for e in sk['elevation_deg']], float)
    w = 360.0 / sk['bins']
    out = {'observer_radius_m': r0, 'far_dem_max_height_m': sk['beyond_range_reference_height_m'],
           'bundle_beyond_range_max_possible_elev_deg': sk['beyond_range_max_possible_elev_deg']}
    for body in ('sun', 'earth'):
        az = np.array([s[body]['az_deg'] for s in b['samples']]); r = max(s[body]['radius_deg'] for s in b['samples'])
        idx = np.unique(np.round(az / w).astype(int) % sk['bins'])
        thr = float(np.nanmin(E[idx])) - r
        rows = []
        for dk in DISTANCES_KM:
            d = dk * 1000.0
            rows.append({'d_km': dk, 'H_needed_m': round(h_needed(r0, d, thr), 1),
                         'elev_of_far_dem_max_deg': round(e_of(r0, d, out['far_dem_max_height_m']), 4),
                         'elev_of_global_max_deg': round(e_of(r0, d, H_GLOBAL_MAX_M), 4)})
        emax = max(e_of(r0, dk * 1000.0, H_GLOBAL_MAX_M) for dk in np.arange(280, 3001, 5))
        # per-hour test: the bound changes an hour only if it rises above BOTH the current horizon at
        # that azimuth and the body's lower edge (el - r) -> it would become the horizon and cover disc.
        hz = np.array([s[body]['horizon_deg'] for s in b['samples']], float)
        el = np.array([s[body]['el_deg'] for s in b['samples']], float)
        rr = np.array([s[body]['radius_deg'] for s in b['samples']], float)
        aff = (emax > hz) & (emax > el - rr)
        slack = np.maximum(hz, el - rr) - emax
        out[body] = {'threshold_elev_deg': round(thr, 4), 'crossed_bins': int(idx.size), 'rows': rows,
                     'max_elev_of_global_max_beyond_280km_deg': round(emax, 4),
                     'margin_deg': round(thr - emax, 4),
                     'coarse_test_can_matter': bool(emax >= thr),
                     'hours_affected_by_bound': int(aff.sum()),
                     'min_per_hour_slack_deg': round(float(np.min(slack)), 4),
                     'ignored_terrain_can_matter': bool(aff.any())}
    return out


README = """# L3 (analytic part) — terrain ignored beyond 280 km

**Label:** PILOT · SOURCE-BASED · UNVALIDATED.

**Question.** The far field stops at 280 km. Could anything farther away rise above the local horizon in the azimuths the
Sun or Earth cross in the demo window?

**Method.** `python -m science.limits.l3_far_bound`. Exact spherical geometry (no small-angle approximation):
H(d, e) = r0·cos e / cos(d/R + e) − R is the height a point d away must have to appear at elevation e. Threshold e = the
lowest skyline elevation in the bins the body crosses, minus its apparent radius (so even "any part of the disc" is
covered). Compared with the tallest height in the loaded far DEM and with 10.8 km, an upper bound on all lunar relief
(LOLA global maximum ≈ 10.79 km).

**Result.** See `RESULT.md`. A coarse test (lowest skyline anywhere in the crossed azimuths) leaves only 0.08° at Site04
and fails at Site01, so it proves nothing. The per-hour test (the bound must rise above both the horizon at that hour's
azimuth and the disc's lower edge) shows that no hour in the demo window can change at either site: the minimum
per-hour slack is given in the table. Physically, 10.8 km terrain at 280 km would sit at ≈ −2.8°, below every horizon
and every lower limb actually reached in the window.

**What it does not show.** It bounds what is *outside* 280 km only; refinement of the DEM *inside* the range is the
numerical part of L3 (bins, steps, far DEM resolution), which is held until the submission is pushed.
"""


def table_md(res):
    L = ['| site | body | threshold elev (lowest crossed skyline − r) | max elev of 10.8 km terrain beyond 280 km | coarse margin | min per-hour slack | hours affected | H needed at 280 / 400 / 600 / 1000 km | can matter? |',
         '|---|---|---|---|---|---|---|---|---|']
    for s, v in res['sites'].items():
        for body in ('sun', 'earth'):
            x = v[body]; hh = {r['d_km']: r['H_needed_m'] for r in x['rows']}
            L.append(f"| {s} | {body} | {x['threshold_elev_deg']:+.3f}° | {x['max_elev_of_global_max_beyond_280km_deg']:+.3f}° | {x['margin_deg']:.3f}° | {x['min_per_hour_slack_deg']:+.3f}° | {x['hours_affected_by_bound']} | "
                     f"{hh[280]/1000:.1f} / {hh[400]/1000:.1f} / {hh[600]/1000:.1f} / {hh[1000]/1000:.1f} km | {'yes' if x['ignored_terrain_can_matter'] else 'no'} |")
    return '# L3 analytic bound\n\nPILOT · SOURCE-BASED · UNVALIDATED.\n\n' + '\n'.join(L) + '\n'


def main():
    res = {'item': 'L3_far_bound', 'H_global_max_m': H_GLOBAL_MAX_M, 'sites': {s: site(s) for s in BUNDLES}}
    write_result('L3_far_bound', res, list(BUNDLES.values()), README, {'RESULT.md': table_md(res)})
    print(table_md(res))


if __name__ == '__main__':
    main()
