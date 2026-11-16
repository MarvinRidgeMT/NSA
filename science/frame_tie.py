"""DE421 MOON_ME (LOLA DEMs) vs JPL Horizons MEAN_ME (DE441) frame-tie bound.

The LOLA products (PGDA 78/90) are in MOON_ME realised with DE421. Horizons reports
"Center pole/equ : MEAN_ME (high precision)" with Moon/Sun/Earth from DE441 (see any
raw response header in data/raw/horizons/).

Bound used (NAIF frame kernel moon_de440_220930.tf, section on the DE440 vs DE421 mean
Earth frames): the maximum rotation between the two ME realisations is
3.0709840342771e-07 rad over 2000-2040 (about 53.4 cm on a great circle on the
lunar surface) and 5.8204420784597e-07 rad over 1900-2051. DE441 lunar orientation
matches DE440 over this interval (DE441 differs mainly in long-term tidal damping).

What the rotation can change here:
  * Sun/Earth az/el at the site: by at most the rotation angle (1.76e-5 deg).
  * The DEM point that corresponds to the Horizons observer: by at most ~0.53 m.
This module compares the angle with the bundle margins and converts it to an upper
bound on event-time shift using the margin rate at each refined crossing.
It does NOT bound the 0.53 m position effect on the skyline; that is covered by the
position-offset scenarios (which move the site by 100 m) and is reported separately.

    python -m science.frame_tie data/bundles/site04_roi3_2026-11-14_14d_mast1m.json ...
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROT_MAX_RAD_2000_2040 = 3.0709840342771e-07
ROT_MAX_RAD_1900_2051 = 5.8204420784597e-07
SOURCE = ('NAIF generic_kernels/fk/satellites/moon_de440_220930.tf: "DE440 vs DE421 mean Earth frame '
          'difference" (max rotation 2000-2040 = 3.0709840342771E-07 rad, ~53.4 cm on the surface)')
R_MOON_M = 1737400.0


def bound_deg(window_years=(2000, 2040)):
    lo, hi = window_years
    rot = ROT_MAX_RAD_2000_2040 if lo >= 2000 and hi <= 2040 else ROT_MAX_RAD_1900_2051
    return math.degrees(rot), rot * R_MOON_M


def check_bundle(b):
    dang, dpos = bound_deg()
    S = b['samples']
    out = {'bundle_id': b['bundle_id'], 'bound_angle_deg': dang, 'bound_position_m': round(dpos, 3)}
    for body in ('sun', 'earth'):
        m = [s[body]['margin_deg'] for s in S]
        out[f'min_abs_{body}_margin_deg'] = round(min(abs(x) for x in m), 6)
        flips = sum((abs(x) <= dang) for x in m)
        out[f'{body}_samples_within_bound'] = flips  # samples whose visibility could flip
    # event-time shift bound: dt = dang / |d margin / dt| from the bracketing hourly samples
    ts = [s['t_unix'] for s in S]
    ev_out = []
    for e in b['events']:
        if e['kind'] != 'center':
            continue
        k = max(0, min(len(ts) - 2, max(i for i, t in enumerate(ts) if t <= e['t_unix'])))
        m0, m1 = S[k][e['body']]['margin_deg'], S[k + 1][e['body']]['margin_deg']
        rate = abs(m1 - m0) / ((ts[k + 1] - ts[k]) / 3600.0)  # deg per hour
        ev_out.append({'body': e['body'], 'event': e['event'], 'utc': e['utc'],
                       'margin_rate_deg_per_h': round(rate, 5),
                       'time_shift_bound_s': None if rate == 0 else round(dang / rate * 3600.0, 2)})
    out['center_events'] = ev_out
    worst = max([x['time_shift_bound_s'] or 0 for x in ev_out], default=0.0)
    out['max_event_time_shift_bound_s'] = worst
    span_h = (ts[-1] - ts[0]) / 3600.0
    # Interval metrics move by at most the summed crossing shifts; hourly-sample metrics by one sample per flip.
    out['interval_metric_shift_bound_pct'] = round(100 * sum(x['time_shift_bound_s'] or 0 for x in ev_out) / 3600.0 / span_h, 5)
    out['hourly_metric_shift_bound_pct'] = round(100 * max(out['sun_samples_within_bound'], out['earth_samples_within_bound']) / len(S), 3)
    out['status'] = 'pass' if out['interval_metric_shift_bound_pct'] < 0.01 else 'fail'
    return out


def evidence(rep):
    return (f'Bound {rep["bound_angle_deg"]:.2e} deg (~{rep["bound_position_m"]} m) from {SOURCE}. '
            f'Smallest |margin|: Sun {rep["min_abs_sun_margin_deg"]} deg, Earth {rep["min_abs_earth_margin_deg"]} deg; '
            f'samples that could flip: Sun {rep["sun_samples_within_bound"]}, Earth {rep["earth_samples_within_bound"]}. '
            f'Centre-event time shift <= {rep["max_event_time_shift_bound_s"]} s, interval metrics <= '
            f'{rep["interval_metric_shift_bound_pct"]} pct-pt, hourly-sample metrics <= {rep["hourly_metric_shift_bound_pct"]} pct-pt. '
            'Position effect (<= 0.53 m on the DEM) is not covered by this angle bound.')


def main(argv=None):
    reps = [check_bundle(json.loads(Path(p).read_text())) for p in (argv or sys.argv[1:])]
    print(json.dumps({'source': SOURCE, 'reports': reps}, indent=1))


if __name__ == '__main__':
    main()
