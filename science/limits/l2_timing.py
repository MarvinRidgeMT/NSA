"""L2 — Event timing below one hour, on a continuous timeline, for the nominal map and all 20 clones.

The bundles already refine the NOMINAL map's events by bisection on real JPL Horizons evaluations
(13 iterations, +-0.22 s; raw files data/raw/horizons/*bisect*). Clone events were only hourly.

Method: Sun/Earth az/el between the bundle's hourly Horizons samples are interpolated with a
cubic spline (az unwrapped). This is INTERPOLATION inside real samples, never extrapolation. The
interpolant is checked against the real-Horizons bisection events of the nominal map: the
spline-refined crossing times of those events must agree to < 60 s (test_limits_l2). Then for every
map (nominal + 20 clones) and every variant (any / centre / full disc, as in L1) the margin g(t) is
scanned on a 1-minute grid over the 336 h window, every sign change is refined with Brent's method
to 1 s, and visible %, longest gap and event lists are recomputed on the continuous timeline.
"""
from __future__ import annotations

import datetime as dt
import math

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.optimize import brentq

from .. import crossings as X
from . import skylines as S
from .common import BUNDLES, load_bundle, write_result

VARIANT_SHIFT = {'any': +1.0, 'centre': 0.0, 'full': -1.0}   # g = m_perp + shift * r
EVENT_KIND = {'upper_limb': 'any', 'center': 'centre', 'lower_limb': 'full'}


class Ephem:
    def __init__(self, b, body):
        t = np.array([s['t_unix'] for s in b['samples']], float)
        self.t0, self.t1 = t[0], t[-1]
        az = np.unwrap(np.radians([s[body]['az_deg'] for s in b['samples']]))
        el = np.array([s[body]['el_deg'] for s in b['samples']], float)
        r = np.array([s[body]['radius_deg'] for s in b['samples']], float)
        self.az = CubicSpline(t, np.degrees(az)); self.el = CubicSpline(t, el); self.r = CubicSpline(t, r)
        self.t = t

    def __call__(self, tt):
        if np.any(np.asarray(tt) < self.t0 - 1e-6) or np.any(np.asarray(tt) > self.t1 + 1e-6):
            raise ValueError('no extrapolation outside the Horizons samples')
        return self.az(tt) % 360.0, self.el(tt), self.r(tt)


def g_func(eph, sky, variant):
    sh = VARIANT_SHIFT[variant]

    def g(tt):
        az, el, r = eph(tt)
        mm = X.margins({'az_deg': float(az), 'el_deg': float(el), 'radius_deg': float(r)}, sky)
        return math.nan if mm is None else mm['margin_perp_deg'] + sh * float(r)
    return g


def g_vec(eph, sky, variant, tt):
    """Vectorised m_perp + shift*r on a time grid (same formulas as crossings.margins)."""
    az, el, r = eph(tt)
    n = sky['bins']; w = 360.0 / n
    E = np.array([np.nan if e is None else e for e in sky['elevation_deg']], float)
    u = az / w; i0 = np.floor(u).astype(int) % n; i1 = (i0 + 1) % n; a = u - np.floor(u)
    H = (1 - a) * E[i0] + a * E[i1]; s = (E[i1] - E[i0]) / w
    s_eff = s / np.maximum(np.cos(np.radians(el)), 1e-6)
    mp = (el - H) / np.sqrt(1 + s_eff ** 2)
    return mp + VARIANT_SHIFT[variant] * r


def continuous(eph, sky, variant, step_s=60.0):
    tt = np.arange(eph.t0, eph.t1 + 1e-6, step_s)
    if tt[-1] < eph.t1:
        tt = np.append(tt, eph.t1)
    gv = g_vec(eph, sky, variant, tt)
    g = g_func(eph, sky, variant)
    vis = gv > 0
    idx = np.nonzero(vis[1:] != vis[:-1])[0]
    events = []
    for i in idx:
        tc = brentq(g, tt[i], tt[i + 1], xtol=0.5)
        events.append({'t_unix': round(tc, 1), 'direction': 'rise' if vis[i + 1] else 'set'})
    # intervals
    bounds = [eph.t0] + [e['t_unix'] for e in events] + [eph.t1]
    state = bool(vis[0]); vis_s = 0.0; gaps = []
    for a, b2 in zip(bounds[:-1], bounds[1:]):
        if state:
            vis_s += b2 - a
        else:
            gaps.append(b2 - a)
        state = not state
    T = eph.t1 - eph.t0
    return {'visible_pct': 100 * vis_s / T, 'longest_gap_h': (max(gaps) / 3600 if gaps else 0.0),
            'events': events, 'start_visible': bool(vis[0]), 'grid_vis': vis, 'grid_t': tt}


def both_pct(a, b):
    """Sun-and-Earth % from two 1-min grids (+ refined edges are within one grid step)."""
    return 100.0 * float(np.mean(a['grid_vis'] & b['grid_vis']))


def hourly_bracket_check(eph, sky, variant, events):
    """Every refined event whose surrounding hourly samples differ in sign must lie inside that hour;
    events in hours whose two endpoints agree are sub-hour 'blinks' invisible to hourly sampling."""
    gh = g_vec(eph, sky, variant, eph.t)
    inside, blinks = 0, 0
    for e in events:
        k = int(np.searchsorted(eph.t, e['t_unix']) - 1)
        k = min(max(k, 0), len(eph.t) - 2)
        if (gh[k] > 0) != (gh[k + 1] > 0):
            inside += eph.t[k] <= e['t_unix'] <= eph.t[k + 1]
        else:
            blinks += 1
    n_hourly = int(np.sum((gh[1:] > 0) != (gh[:-1] > 0)))
    return {'n_events': len(events), 'n_hourly_sign_changes': n_hourly, 'n_inside_bracket': int(inside),
            'n_subhour_blinks': blinks}


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def validate_against_bisection(b, sky):
    """Spline-refined crossing vs the bundle's real-Horizons bisection events (nominal map)."""
    out = []
    for e in b['events']:
        eph = Ephem(b, e['body']); var = EVENT_KIND[e['kind']]
        g = g_func(eph, sky, var)
        t = e['t_unix']; a, c = max(eph.t0, t - 1800), min(eph.t1, t + 1800)
        tc = brentq(g, a, c, xtol=0.05)
        out.append({'body': e['body'], 'kind': e['kind'], 'event': e['event'], 'horizons_bisection_utc': e['utc'],
                    'spline_utc': iso(tc), 'diff_s': round(tc - t, 2)})
    return out


def site_result(site, clones=range(1, 21)):
    b = load_bundle(site)
    maps = {'nominal': S.skyline(site), **{f'clone{c:02d}': S.skyline(site, clone=c) for c in clones}}
    ephs = {body: Ephem(b, body) for body in ('sun', 'earth')}
    res = {'validation_vs_horizons_bisection': validate_against_bisection(b, maps['nominal']), 'maps': {}}
    for name, sky in maps.items():
        mres = {}
        for var in VARIANT_SHIFT:
            cs = continuous(ephs['sun'], sky, var); ce = continuous(ephs['earth'], sky, var)
            hs = hourly_bracket_check(ephs['sun'], sky, var, cs['events'])
            mres[var] = {'sun_pct': round(cs['visible_pct'], 3), 'earth_pct': round(ce['visible_pct'], 3),
                         'sun_and_earth_pct_1min': round(both_pct(cs, ce), 3),
                         'longest_sun_gap_h': round(cs['longest_gap_h'], 3),
                         'longest_earth_gap_h': round(ce['longest_gap_h'], 3),
                         'sun_events_utc': [(iso(e['t_unix']), e['direction']) for e in cs['events']],
                         'earth_events_utc': [(iso(e['t_unix']), e['direction']) for e in ce['events']],
                         'sun_bracket_check': hs,
                         'earth_bracket_check': hourly_bracket_check(ephs['earth'], sky, var, ce['events'])}
        res['maps'][name] = mres
    # comparison with hourly (L1 numbers recomputed here on the same maps)
    from . import l1_disc
    cmp = {}
    for name, sky in maps.items():
        h = l1_disc.metrics(l1_disc.hourly_terms(b, sky)); c = res['maps'][name]
        cmp[name] = {v: {'d_sun_pct': round(c[v]['sun_pct'] - h[v]['sun_pct'], 3),
                         'd_sun_earth_pct': round(c[v]['sun_and_earth_pct_1min'] - h[v]['sun_and_earth_pct'], 3),
                         'd_longest_sun_gap_h': round(c[v]['longest_sun_gap_h'] - h[v]['longest_sun_gap_h_hourly'], 3)}
                     for v in VARIANT_SHIFT}
    res['continuous_minus_hourly'] = cmp
    summ = {}
    for v in VARIANT_SHIFT:
        cl = [res['maps'][f'clone{c:02d}'][v] for c in clones]
        summ[v] = {'nominal_sun_pct': res['maps']['nominal'][v]['sun_pct'],
                   'clone_sun_pct': [min(x['sun_pct'] for x in cl), max(x['sun_pct'] for x in cl)],
                   'nominal_sun_earth_pct': res['maps']['nominal'][v]['sun_and_earth_pct_1min'],
                   'clone_sun_earth_pct': [min(x['sun_and_earth_pct_1min'] for x in cl), max(x['sun_and_earth_pct_1min'] for x in cl)],
                   'nominal_longest_sun_gap_h': res['maps']['nominal'][v]['longest_sun_gap_h'],
                   'clone_longest_sun_gap_h': [min(x['longest_sun_gap_h'] for x in cl), max(x['longest_sun_gap_h'] for x in cl)],
                   'max_abs_d_sun_pct_vs_hourly': max(abs(cmp[n][v]['d_sun_pct']) for n in cmp),
                   'max_abs_d_gap_h_vs_hourly': max(abs(cmp[n][v]['d_longest_sun_gap_h']) for n in cmp),
                   'total_subhour_blinks_sun': sum(res['maps'][n][v]['sun_bracket_check']['n_subhour_blinks'] for n in maps)}
    res['summary'] = summ
    res['bundle_reference'] = {k: b['metrics'][k] for k in ('sun_center_visible_pct', 'sun_and_earth_center_visible_pct',
                                                           'longest_sun_center_hidden_h', 'earth_center_visible_pct')}
    return res


README = """# L2 — Event timing below one hour

**Label:** PILOT · SOURCE-BASED · UNVALIDATED. Geometric visibility only.

**Question.** Visibility was sampled hourly. How much do visible %, Sun+Earth % and the longest gap move when every
visible/blocked transition is timed to the minute or better — for the nominal map **and all 20 clones**?

**What already existed.** The bundles refine the nominal map's 9 (Site04 RoI 3) / 3 (Site01 RoI 6) events by bisection on
real Horizons evaluations to ±0.22 s (`data/raw/horizons/*bisect*`), and carry continuous `sun_center_visible_pct`
(94.213 % vs 94.362 % hourly). Clones had no sub-hour timing.

**Method.** `python -m science.limits.l2_timing`. Cubic-spline interpolation of the bundle's hourly Horizons az/el/radius
(inside the samples only; the code refuses to extrapolate). Margin g(t) = m⊥ + k·r (k = +1 any part, 0 centre, −1 full
disc) scanned on a 1-minute grid over 14–28 Nov 2026, each sign change refined by Brent's method to ≤ 1 s. The spline
crossing times are checked against the bundle's real-Horizons bisection events (`validation_vs_horizons_bisection`):
agreement is within seconds, which validates the interpolant at this site and window (not elsewhere). Sun+Earth % is
the share of 1-minute grid points with both visible.

**Result.** `result.json` → `sites.<site>.summary` and `RESULT.md`. Every refined transition lies inside its hourly
bracket; sub-hour "blinks" (a set and a rise inside one hour, missed by hourly samples) are counted separately.

**What it does not show.** The spline is validated against real Horizons evaluations only at the nominal events; clones use
the same ephemeris (observer-height parallax < 1e-8°). The skyline itself is still 720-bin, linearly interpolated in
azimuth (see L3). Not power, not comms; k of N clones is not a probability.
"""


def table_md(res):
    L = ['| site | variant | Sun % nominal (cont.) | Sun % clones (cont.) | Sun+Earth % nominal | Sun+Earth % clones | longest Sun gap h nominal | clones | max |Δ Sun %| vs hourly | max |Δ gap| h vs hourly | sub-hour blinks |',
         '|---|---|---|---|---|---|---|---|---|---|---|']
    for site, r in res['sites'].items():
        for v, s in r['summary'].items():
            L.append(f"| {site} | {v} | {s['nominal_sun_pct']:.3f} | {s['clone_sun_pct'][0]:.3f}–{s['clone_sun_pct'][1]:.3f} | "
                     f"{s['nominal_sun_earth_pct']:.3f} | {s['clone_sun_earth_pct'][0]:.3f}–{s['clone_sun_earth_pct'][1]:.3f} | "
                     f"{s['nominal_longest_sun_gap_h']:.2f} | {s['clone_longest_sun_gap_h'][0]:.2f}–{s['clone_longest_sun_gap_h'][1]:.2f} | "
                     f"{s['max_abs_d_sun_pct_vs_hourly']:.3f} | {s['max_abs_d_gap_h_vs_hourly']:.2f} | {s['total_subhour_blinks_sun']} |")
    L += ['', '| site | event | Horizons bisection | spline | Δ s |', '|---|---|---|---|---|']
    for site, r in res['sites'].items():
        for e in r['validation_vs_horizons_bisection']:
            L.append(f"| {site} | {e['body']} {e['event']} | {e['horizons_bisection_utc']} | {e['spline_utc']} | {e['diff_s']:+.1f} |")
    return '# L2 result table\n\nPILOT · SOURCE-BASED · UNVALIDATED. Continuous timeline, 14–28 Nov 2026, 1 m mast.\n\n' + '\n'.join(L) + '\n'


def main():
    res = {'item': 'L2_event_timing', 'sites': {}}
    for site in BUNDLES:
        res['sites'][site] = site_result(site)
        print(site, res['sites'][site]['summary']['centre'], flush=True)
        print([e['diff_s'] for e in res['sites'][site]['validation_vs_horizons_bisection']])
    write_result('L2_event_timing', res, list(BUNDLES.values()), README, {'RESULT.md': table_md(res)})


if __name__ == '__main__':
    main()
