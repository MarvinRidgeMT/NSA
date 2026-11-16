"""L7 — Knife-edge reporting: how close is the verdict to flipping?

For each site (1 m mast, 14-28 Nov 2026):
  1. distribution of the hourly Sun-centre perpendicular margin (nominal map; and pooled over the
     20 clones), counts within +-0.1 / 0.25 / 0.5 / 1.0 deg;
  2. uniform horizon error: raise (and lower) the whole skyline by delta = 0.05/0.1/0.25/0.5 deg and
     recompute Sun % and Sun+Earth % on the continuous timeline (L2 method). delta* = the smallest
     uniform raise that takes Sun % below the 70 % mission threshold (bisection to 0.001 deg); same for
     the 40 % Sun+Earth threshold (thresholds from the bundle's derived.flip_forecast);
  3. height change at the controlling DEM cell: per hour, dh_i = m_i / (dE/dh)_i with the exact
     Jacobian of the Moon-fixed elevation angle of that hour's controlling terrain sample
     (finite difference, +-1 cm); and delta*/(dE/dh) at the dominant controlling cell.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

from .. import frames, sites
from . import skylines as S
from .common import BUNDLES, load_bundle, write_result
from .l1_disc import hourly_terms
from .l2_timing import Ephem, both_pct, continuous

DELTAS = (0.05, 0.1, 0.25, 0.5)
BANDS = (0.1, 0.25, 0.5, 1.0)


def shifted(sky, delta):
    s = dict(sky)
    s['elevation_deg'] = [None if e is None else e + delta for e in sky['elevation_deg']]
    return s


def pct_under(ephs, sky, delta):
    sk = shifted(sky, delta)
    cs = continuous(ephs['sun'], sk, 'centre'); ce = continuous(ephs['earth'], sk, 'centre')
    return cs['visible_pct'], both_pct(cs, ce), cs['longest_gap_h']


def jacobian_deg_per_m(site, sky, mast_m, crit):
    """dE/dh of the elevation angle of terrain sample `crit` seen from the observer."""
    s = sites.SITES[site]
    P_obs = frames.moon_fixed(s['lat'], s['lon'], sky['ground_m'] + mast_m)
    up = frames.up_vector(s['lat'], s['lon'])
    def E(h):
        P = frames.moon_fixed(crit['lat_deg'], crit['lon_deg'], h)
        return float(frames.elevation_angle_deg(P_obs, up, P))
    return (E(crit['height_m'] + 0.01) - E(crit['height_m'] - 0.01)) / 0.02


def site_result(site):
    b = load_bundle(site); mast = b['site']['observer_mast_m']
    thr = b['derived']['flip_forecast']['thresholds']
    t_sun, t_both = thr['sun_center_visible_pct_min'], thr['sun_and_earth_center_visible_pct_min']
    nom = S.skyline(site)
    ephs = {k: Ephem(b, k) for k in ('sun', 'earth')}
    terms = hourly_terms(b, nom)
    mp = terms['sun']['mp']
    pooled = np.concatenate([hourly_terms(b, S.skyline(site, clone=c))['sun']['mp'] for c in range(1, 21)])
    edges = np.round(np.arange(-3.0, 3.0001, 0.1), 3)
    dist = {'hist_edges_deg': edges.tolist(),
            'hist_nominal': np.histogram(np.clip(mp, -3, 3), edges)[0].tolist(),
            'hist_clones_pooled_per_clone_avg': (np.histogram(np.clip(pooled, -3, 3), edges)[0] / 20).round(2).tolist(),
            'within_nominal': {f'{x}': int(np.sum(np.abs(mp) <= x)) for x in BANDS},
            'within_clones_pooled_per_clone_avg': {f'{x}': round(float(np.sum(np.abs(pooled) <= x)) / 20, 2) for x in BANDS},
            'n_hours': int(mp.size)}
    base = pct_under(ephs, nom, 0.0)
    rob = {'nominal': {'sun_pct': round(base[0], 3), 'sun_earth_pct': round(base[1], 3), 'longest_gap_h': round(base[2], 2)}}
    for d in DELTAS:
        for sg in (+1, -1):
            r = pct_under(ephs, nom, sg * d)
            rob[f'{sg * d:+.2f}'] = {'sun_pct': round(r[0], 3), 'sun_earth_pct': round(r[1], 3), 'longest_gap_h': round(r[2], 2),
                                     'sun_verdict_pass': r[0] >= t_sun, 'sun_earth_verdict_pass': r[1] >= t_both}

    def crit_delta(idx, thr_):
        f = lambda d: pct_under(ephs, nom, d)[idx] - thr_
        if f(0.0) < 0:
            return 0.0
        hi = 0.5
        while f(hi) >= 0 and hi < 16:
            hi *= 2
        return None if f(hi) >= 0 else round(brentq(f, 0.0, hi, xtol=1e-3), 4)
    d_sun, d_both = crit_delta(0, t_sun), crit_delta(1, t_both)

    # per-hour height change at the controlling cell
    az = np.array([s_['sun']['az_deg'] for s_ in b['samples']])
    J, dh, dist_m, cell = [], [], [], []
    w = 360.0 / nom['bins']
    for a, m in zip(az, mp):
        i = int(round(a / w)) % nom['bins']
        c = nom['critical'][i]
        j = jacobian_deg_per_m(site, nom, mast, c)
        J.append(j); dh.append(m / j); dist_m.append(c['distance_m'])
        cell.append((int(np.floor(c['grid_x_m'] / 5.0)) * 5, int(np.floor(c['grid_y_m'] / 5.0)) * 5))  # 5 m DEM cell (lower-left corner)
    J = np.array(J); dh = np.array(dh); dist_m = np.array(dist_m)
    vis = mp > 0
    # dominant controlling cell among the near-critical hours (|m| <= 0.5 deg); fall back to all hours
    from collections import Counter
    near = np.abs(mp) <= 0.5
    sel = near if near.any() else np.zeros_like(near)
    cnt = Counter(tuple(cell[k]) for k in range(len(cell)) if sel[k])
    if cnt:
        dom, n_dom = cnt.most_common(1)[0]
        kdom = [k for k in range(len(cell)) if tuple(cell[k]) == dom]
        Jdom = float(np.median(J[kdom])); ddom = float(np.median(dist_m[kdom]))
    else:
        dom, n_dom, Jdom, ddom = None, 0, None, None
    hv = np.abs(dh[vis])
    res = {
        'thresholds': {'sun_pct': t_sun, 'sun_earth_pct': t_both},
        'margin_distribution': dist,
        'uniform_horizon_error': rob,
        'critical_uniform_raise_deg': {'sun_70pct': d_sun, 'sun_earth_40pct': d_both},
        'controlling_cell': {
            'dominant_cell_grid_xy_m': dom, 'selection': 'near-critical hours |m|<=0.5 deg' if near.any() else 'none: no hour within 0.5 deg',
            'hours_controlled_in_selection': n_dom, 'n_hours_in_selection': int(sel.sum()),
            'near_critical_controlling_distances_m': sorted(set(round(float(x), 1) for x in dist_m[sel]))[:40], 'distance_m': None if ddom is None else round(ddom, 1),
            'dE_dh_deg_per_m': None if Jdom is None else round(Jdom, 4),
            'height_raise_to_flip_sun_70pct_m': None if (d_sun is None or Jdom is None) else round(d_sun / Jdom, 3),
            'height_raise_to_flip_sun_earth_40pct_m': None if (d_both is None or Jdom is None) else round(d_both / Jdom, 3),
            'note': 'delta*/(dE/dh) at the dominant cell: the height error at that one cell that equals the uniform '
                    'angular error delta*; a single-cell raise only moves the bins that cell controls, so this is the '
                    'equivalent, not a proof that one cell alone flips the verdict.'},
        'per_hour_dh_to_flip_m': {
            'visible_hours_quantiles_abs_m': {q: round(float(np.quantile(hv, q)), 4) for q in (0.05, 0.1, 0.25, 0.5)} if hv.size else None,
            'n_visible_hours_flipped_by_dh_le': {f'{x}': int(np.sum(hv <= x)) for x in (0.01, 0.05, 0.1, 0.25, 0.5, 1.0)},
            'median_controlling_distance_m': round(float(np.median(dist_m)), 1)},
    }
    return res


README = """# L7 — Knife-edge reporting

**Label:** PILOT · SOURCE-BASED · UNVALIDATED. Geometric visibility only.

**Question.** The Site04 RoI 3 result hinges on a rise 15–16 m from the lander. Turn "fragile" into numbers: how many
hours sit near the horizon, how much uniform horizon error flips the 70 % Sun verdict, and what height change at the
controlling DEM cell that corresponds to.

**Method.** `python -m science.limits.l7_knife_edge`. Hourly Sun-centre perpendicular margins (nominal map and the 20
clones, as in L1). Uniform horizon error: every skyline bin raised/lowered by δ, Sun % and Sun+Earth % recomputed on the
continuous timeline (L2). δ* = smallest raise that drops Sun % below 70 % (or Sun+Earth below 40 %; thresholds from the
bundle's `derived.flip_forecast`), by bisection. dE/dh = exact derivative of the Moon-fixed elevation angle of each hour's
controlling terrain sample (finite difference ±1 cm, float64). Height to flip hour i = m_i / (dE/dh)_i.

**Result.** `result.json` and `RESULT.md`.

**What it does not show.** A uniform error is a worst-case shape, not a modelled DEM error (L4 has the error model). The
single-cell height equivalent δ*/(dE/dh) is an equivalence at the dominant cell, not a proof that raising one cell alone
flips the verdict (one cell controls only some bins). Not power, not comms.
"""


def table_md(res):
    L = ['| site | hours within ±0.1/±0.25/±0.5/±1° (nominal) | same, clone average | Sun % at −0.5/−0.25/−0.1/−0.05/0/+0.05/+0.1/+0.25/+0.5° horizon shift | δ* Sun 70 % | δ* Sun+Earth 40 % | dominant cell: distance, dE/dh | Δh to flip Sun 70 % |',
         '|---|---|---|---|---|---|---|---|']
    for site, r in res['sites'].items():
        d = r['margin_distribution']; u = r['uniform_horizon_error']; c = r['controlling_cell']
        w = '/'.join(str(d['within_nominal'][f'{x}']) for x in BANDS)
        wc = '/'.join(str(d['within_clones_pooled_per_clone_avg'][f'{x}']) for x in BANDS)
        seq = '/'.join(f"{u[k]['sun_pct']:.1f}" for k in ('-0.50', '-0.25', '-0.10', '-0.05')) + f"/{u['nominal']['sun_pct']:.1f}/" + \
              '/'.join(f"{u[k]['sun_pct']:.1f}" for k in ('+0.05', '+0.10', '+0.25', '+0.50'))
        cr = r['critical_uniform_raise_deg']
        L.append(f"| {site} | {w} | {wc} | {seq} | {cr['sun_70pct']}° | {cr['sun_earth_40pct']}° | {c['distance_m']} m, {c['dE_dh_deg_per_m']}°/m | "
                 f"{c['height_raise_to_flip_sun_70pct_m']} m |")
    return '# L7 result table\n\nPILOT · SOURCE-BASED · UNVALIDATED. 14–28 Nov 2026, 1 m mast, nominal PGDA 78 map; δ* = uniform skyline raise that flips the verdict.\n\n' + '\n'.join(L) + '\n'


def main():
    res = {'item': 'L7_knife_edge', 'sites': {}}
    for site in BUNDLES:
        res['sites'][site] = site_result(site)
        r = res['sites'][site]
        print(site, r['margin_distribution']['within_nominal'], r['critical_uniform_raise_deg'], r['controlling_cell'], flush=True)
    write_result('L7_knife_edge', res, list(BUNDLES.values()), README, {'RESULT.md': table_md(res)})


if __name__ == '__main__':
    main()
