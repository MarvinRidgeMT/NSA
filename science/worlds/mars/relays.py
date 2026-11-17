"""Relay-orbiter geometry at the Jezero rim site: when each Mars relay orbiter is above the site's terrain skyline.

    python -m science.worlds.mars.relays [--offline]

SOURCE-BASED · UNVALIDATED geometry. What it is:
  * the orbiter's apparent (airless) azimuth/elevation from JPL Horizons (observer table, QUANTITIES 4,20) at the site
    (`coord@499`, the same CYLINDRICAL site point and MOLA→Horizons longitude tie as the site bundle), one sample per
    minute, rotated from Horizons' ellipsoid normal to the sphere normal like the Sun and Earth;
  * compared with the terrain skyline already stored in the site bundle (`data/worlds/mars/mars_jezero_rim_*.json.gz`),
    linear in azimuth (science.crossings.horizon_at), and with a flat 0° horizon (control).
What it is not: relay availability. Orbiter relay scheduling, UHF link budget, antenna patterns, minimum-elevation masks
and orbiter operations are not modelled. A "pass" here is a run of 1-minute samples with the orbiter centre above the
skyline; pass edges are good to ±1 min, and Horizons' trajectories after their reconstruction end are planning
predictions (their own headers say so; quoted per orbiter in the output).

Window (fixed before any query): 2026-11-14 00:00 → 2026-11-30 00:00 UTC, 16 days at 1 min. It lies inside every
ephemeris used; an orbiter whose Horizons trajectory does not cover the whole window is reported "not available" with
Horizons' own message, never extrapolated (AGENTS.md invariant 7).
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

from ... import horizons as H
from ...anysite.ephem import fetch_cached
from ...crossings import horizon_at
from .. import ephem as WE
from .world import MARS

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / 'data' / 'worlds' / 'mars'
BUNDLE = OUT_DIR / 'mars_jezero_rim_2026-11-14_687d_mast1m.json.gz'
START, STOP, STEP = '2026-11-14 00:00', '2026-11-30 00:00', '1 m'
STEP_MIN = 1.0
AU_KM = 149_597_870.7
ORBITERS = [('relay-mro', '-74', 'Mars Reconnaissance Orbiter'), ('relay-tgo', '-143', 'ExoMars Trace Gas Orbiter'),
            ('relay-mex', '-41', 'Mars Express'), ('relay-maven', '-202', 'MAVEN')]
CHECK_MAX_EL_DIFF_DEG = 0.5
# Reading of each trajectory's status over the window, from Horizons' own object data (quoted in the output; the test
# checks the quoted lines still contain `evidence`). Error sizes are not quantified here.
TRAJECTORY_READING = {
    'relay-mro': {'evidence': 'after 2026-Nov-01 is a planning PREDICTION',
                  'reading': 'JPL MRO Nav planning prediction for the whole window (reconstruction ends 2026-11-01).'},
    'relay-tgo': {'evidence': 'data-fit through 2025-Jun-21',
                  'reading': 'ESA long-term reference trajectory; the last data fit is 2025-06-21, ~17 months before the '
                             'window. Pass times may be off by more than the 1-min sampling (not quantified): treat pass '
                             'counts and durations as indicative only.'},
    'relay-mex': {'evidence': 'tracking data through 2026-Oct-21',
                  'reading': 'ESA prediction for the whole window (reconstruction through 2026-10-21, 24-40 days before).'},
}
LABEL = 'SOURCE-BASED · UNVALIDATED (geometry only; not relay availability)'


def load_bundle(path=BUNDLE):
    return json.loads(gzip.decompress(Path(path).read_bytes()))


def passes(t_unix, vis, el, rng_km):
    """Runs of consecutive visible samples. A run touching the window edge is flagged `truncated_by_window`."""
    out, i, n = [], 0, len(vis)
    while i < n:
        if not vis[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and vis[j + 1]:
            j += 1
        seg = slice(i, j + 1)
        out.append({'start_unix': float(t_unix[i]), 'end_unix': float(t_unix[j]),
                    'duration_min': (j - i + 1) * STEP_MIN, 'max_el_deg': round(float(np.max(el[seg])), 3),
                    'min_range_km': round(float(np.min(rng_km[seg])), 1) if np.isfinite(rng_km[seg]).any() else None,
                    'max_range_km': round(float(np.max(rng_km[seg])), 1) if np.isfinite(rng_km[seg]).any() else None,
                    'truncated_by_window': i == 0 or j == n - 1})
        i = j + 1
    return out


def longest_gap_min(vis):
    best = cur = 0
    for v in vis:
        cur = 0 if v else cur + 1
        best = max(best, cur)
    return best * STEP_MIN


def summarise(t_unix, vis, el, rng_km, days):
    ps = passes(t_unix, vis, el, rng_km)
    full = [p for p in ps if not p['truncated_by_window']]
    dur = [p['duration_min'] for p in full]
    return {'visible_pct_minute_samples': round(100 * float(np.mean(vis)), 3),
            'visible_min_per_day': round(float(np.sum(vis)) * STEP_MIN / days, 2),
            'n_passes': len(ps), 'n_passes_complete': len(full),
            'passes_per_day': round(len(ps) / days, 3),
            'pass_duration_min': ({'median': float(np.median(dur)), 'min': float(np.min(dur)), 'max': float(np.max(dur))}
                                  if dur else None),
            'longest_gap_min': longest_gap_min(vis), 'passes': ps}


def trajectory_notes(rid, naif, site, allow_network=True):
    """Horizons' own object-data block for the spacecraft (trajectory segments: reconstruction vs planning prediction),
    quoted line by line. One-sample query with OBJ_DATA=YES, cached like every Horizons response."""
    p = MARS.horizons_params(naif, site['lat'], site['lon'] + site['lon_offset'], site['h_eye'], START, '2026-11-14 00:01',
                             STEP, quantities='4')
    p['OBJ_DATA'] = 'YES'
    body, src = fetch_cached(p, cache_dir=WE.cache_dir(MARS), allow_network=allow_network)
    lines = body.decode('utf-8', 'replace').splitlines()
    try:
        a = next(i for i, l in enumerate(lines) if l.startswith('*****'))
        b = next(i for i, l in enumerate(lines[a + 1:], a + 1) if l.startswith('*****'))
    except StopIteration:
        return {'lines': [], 'source': src.get('sha256')}
    keep = [l.rstrip() for l in lines[a + 1:b] if l.strip()]
    seg = [l for l in keep if re.search(r'predict|reconstruct|trajectory|segment|_rec|_psp|flp|ORM', l, re.I)]
    return {'lines': seg[:20], 'source': {k: src.get(k) for k in ('path', 'sha256', 'retrieved_utc') if k in src}}


def orbiter(rid, naif, name, site, sky, allow_network=True):
    lat, lon, h_eye = site['lat'], site['lon'], site['h_eye']
    p = MARS.horizons_params(naif, lat, lon + site['lon_offset'], h_eye, START, STOP, STEP, quantities='4,20')
    try:
        body, src = fetch_cached(p, cache_dir=WE.cache_dir(MARS), allow_network=allow_network)
    except Exception as e:      # noqa: BLE001 - recorded, not hidden
        return {'id': rid, 'naif_id': naif, 'name': name, 'status': 'not available', 'reason': f'{type(e).__name__}: {e}'[:400]}
    text = body.decode('utf-8', 'replace')
    if '$$SOE' not in text:
        msg = ' '.join(text.split())[-500:]
        return {'id': rid, 'naif_id': naif, 'name': name, 'status': 'not available',
                'reason': 'Horizons has no trajectory for this spacecraft over the whole window (no extrapolation)',
                'horizons_message': msg, 'source': {k: src.get(k) for k in ('path', 'sha256', 'retrieved_utc') if k in src}}
    rows = H.parse_text(text)
    t = np.array([H.iso_to_unix(r['utc']) for r in rows])
    expect = int(round((H.iso_to_unix('2026-11-30T00:00:00Z') - H.iso_to_unix('2026-11-14T00:00:00Z')) / 60)) + 1
    if len(rows) != expect or np.any(np.diff(t) != 60):
        raise ValueError(f'{rid}: {len(rows)} samples, expected {expect} one minute apart')
    az, el, _ = MARS.horizons_azel_to_sphere(np.array([r['az_deg'] for r in rows]), np.array([r['el_deg'] for r in rows]),
                                             lat, lon, h_eye)
    rng = np.array([(r.get('range_au') or np.nan) * AU_KM for r in rows])
    hz = [horizon_at(sky, a) for a in az]
    unknown = np.array([x[0] is None for x in hz])
    H_ = np.array([x[0] if x[0] is not None else np.nan for x in hz])
    vis = (el > H_) & ~unknown
    flat = el > 0.0
    days = (t[-1] - t[0] + 60) / 86400.0
    check = independent_check(site, list(zip(t, az, el)), naif, allow_network)
    return {'id': rid, 'naif_id': naif, 'name': name, 'status': 'computed', 'n_samples': len(rows),
            'independent_check': check,
            'n_unknown_skyline': int(unknown.sum()),
            'terrain': summarise(t, vis, el, rng, days),
            'flat_horizon_control': {k: v for k, v in summarise(t, flat, el, rng, days).items() if k != 'passes'},
            'minutes_hidden_by_terrain_while_above_flat_horizon': int(np.sum(flat & ~vis)),
            'max_el_deg': round(float(np.max(el)), 3),
            'horizons_trajectory_notes': trajectory_notes(rid, naif, site, allow_network),
            'trajectory_reading': TRAJECTORY_READING.get(rid),
            'source': {k: src.get(k) for k in ('path', 'sha256', 'retrieved_utc') if k in src},
            '_vis': vis, '_t': t}


def _sub_spacecraft(naif, allow_network=True, step='1 h'):
    """Independent route: Mars seen FROM the orbiter (CENTER 500@naif, QUANTITIES 14,20): sub-spacecraft point
    (IAU_MARS, west-positive longitude, planetodetic latitude on Horizons' ellipsoid) and range to Mars' centre."""
    p = {'format': 'text', 'COMMAND': "'499'", 'CENTER': f"'500@{naif}'", 'MAKE_EPHEM': 'YES', 'EPHEM_TYPE': 'OBSERVER',
         'START_TIME': f"'{START}'", 'STOP_TIME': f"'{STOP}'", 'STEP_SIZE': f"'{step}'", 'QUANTITIES': "'14,20'",
         'CSV_FORMAT': 'YES', 'ANG_FORMAT': 'DEG', 'EXTRA_PREC': 'YES', 'OBJ_DATA': 'NO', 'TIME_DIGITS': 'FRACSEC',
         'CAL_FORMAT': 'CAL', 'TIME_TYPE': 'UT'}
    body, src = fetch_cached(p, cache_dir=WE.cache_dir(MARS), allow_network=allow_network)
    text = body.decode('utf-8', 'replace')
    if '{West-longitude positive}' not in text:
        raise ValueError('expected IAU_MARS west-positive sub-observer longitudes')
    lines = text.splitlines()
    soe, eoe = lines.index('$$SOE'), lines.index('$$EOE')
    names = [h.strip() for h in next(l for l in reversed(lines[:soe]) if 'Date__' in l).split(',')]
    iw, il, idl = names.index('ObsSub-LON'), names.index('ObsSub-LAT'), names.index('delta')
    out = []
    for l in lines[soe + 1:eoe]:
        f = [x.strip() for x in l.split(',')]
        out.append((H.iso_to_unix(H._iso(f[0])), float(f[iw]), float(f[il]), float(f[idl]) * AU_KM * 1000.0))
    return out, src


def _ellipsoid_point(lon_e_deg, lat_d_deg, dist_m):
    """Body-fixed position on the planetodetic normal at (lon_e, lat_d) whose distance from the centre is dist_m."""
    a, _, c = (x * 1000.0 for x in MARS.horizons_radii_km)
    lam, phi = math.radians(lon_e_deg), math.radians(lat_d_deg)
    e2 = 1 - (c / a) ** 2
    N = a / math.sqrt(1 - e2 * math.sin(phi) ** 2)
    S = np.array([N * math.cos(phi) * math.cos(lam), N * math.cos(phi) * math.sin(lam), N * (1 - e2) * math.sin(phi)])
    n = np.array([math.cos(phi) * math.cos(lam), math.cos(phi) * math.sin(lam), math.sin(phi)])
    h = dist_m - np.linalg.norm(S)
    for _ in range(30):                          # |S + h n| = dist
        h += dist_m - np.linalg.norm(S + h * n)
    return S + h * n


def independent_check(site, minute_rows, naif, allow_network=True):
    """Elevation of the orbiter from the site computed in this module (sphere normal, site at the bundle's planetocentric
    point, longitude tie applied) from the orbiter-centred route, vs the site-topocentric Horizons elevation at the same
    hourly times. Also the wrong-longitude-sign hypothesis, which must disagree."""
    sub, src = _sub_spacecraft(naif, allow_network)
    t_min = {round(t): (az, el) for t, az, el in minute_rows}
    lat, lon_e = math.radians(site['lat']), math.radians(site['lon'] + site['lon_offset'])
    r = MARS.radius_m + site['h_eye']
    Sx = r * np.array([math.cos(lat) * math.cos(lon_e), math.cos(lat) * math.sin(lon_e), math.sin(lat)])
    u = Sx / np.linalg.norm(Sx)
    e_ = np.array([-math.sin(lon_e), math.cos(lon_e), 0.0])
    n_ = np.cross(u, e_)
    d_el, d_az, d_wrong = [], [], []
    for t, lon_w, lat_d, dist in sub:
        if round(t) not in t_min:
            continue
        az_h, el_h = t_min[round(t)]
        for sign, acc in ((1, 'ok'), (-1, 'wrong')):
            P = _ellipsoid_point((-lon_w) * sign % 360.0, lat_d, dist)
            v = P - Sx
            v /= np.linalg.norm(v)
            el = math.degrees(math.asin(float(v @ u)))
            if acc == 'ok':
                d_el.append(el - el_h)
                if el_h > 0 and el_h < 80:
                    az = math.degrees(math.atan2(float(v @ e_), float(v @ n_))) % 360.0
                    d_az.append(((az - az_h + 180) % 360) - 180)
            else:
                d_wrong.append(el - el_h)
    if not d_el:
        raise ValueError('no common sample times')
    mx, wrong = float(np.max(np.abs(d_el))), float(np.median(np.abs(d_wrong)))
    return {'status': 'pass' if mx < CHECK_MAX_EL_DIFF_DEG and wrong > 5.0 else 'fail',
            'criterion': f'max |el diff| < {CHECK_MAX_EL_DIFF_DEG} deg and the wrong-sign hypothesis off by > 5 deg (median)',
            'residual_note': 'Not explained to the last 0.1-0.3 deg; candidate: different light-time/aberration treatment of '
                             'the two routes. At the orbiters\' angular rates this moves pass edges by well under the 1-min '
                             'sampling.',
            'method': 'orbiter-centred Horizons route (CENTER 500@orbiter, sub-observer point + range, IAU_MARS '
                      'west-positive, planetodetic) -> body-fixed position -> elevation from the site on the sphere normal; '
                      'compared with the site-topocentric Horizons az/el at the same hourly times',
            'n': len(d_el), 'max_abs_el_diff_deg': round(float(np.max(np.abs(d_el))), 4),
            'max_abs_az_diff_deg_above_horizon_below_80': round(float(np.max(np.abs(d_az))), 4) if d_az else None,
            'wrong_longitude_sign_median_abs_el_diff_deg': round(float(np.median(np.abs(d_wrong))), 2),
            'source': {k: src.get(k) for k in ('path', 'sha256', 'retrieved_utc') if k in src}}


def build(allow_network=True, bundle_path=BUNDLE, out_dir=OUT_DIR, command='python -m science.worlds.mars.relays'):
    b = load_bundle(bundle_path)
    sky = {k: b['skyline'][k] for k in ('bins', 'elevation_deg', 'status')}
    site = {'lat': b['site']['lat_deg'], 'lon': b['site']['lon_deg_east'],
            'h_eye': b['site']['height_m'] + b['site']['observer_mast_m'],
            'lon_offset': b['frame']['horizons_longitude_offset_deg']}
    res = [orbiter(rid, naif, name, site, sky, allow_network) for rid, naif, name in ORBITERS]
    ok = [r for r in res if r['status'] == 'computed']
    union = None
    if ok:
        t = ok[0]['_t']
        if any(not np.array_equal(r['_t'], t) for r in ok):
            raise ValueError('orbiter sample grids differ')
        anyv = np.any([r['_vis'] for r in ok], axis=0)
        union = {'orbiters': [r['id'] for r in ok], 'any_visible_pct_minute_samples': round(100 * float(np.mean(anyv)), 3),
                 'longest_gap_with_no_orbiter_visible_min': longest_gap_min(anyv)}
    for r in ok:
        r.pop('_vis'); r.pop('_t')
    from science import gitinfo
    out = {'schema': 'polaris-relay-geometry-v1', 'label': LABEL,
           'site': {'bundle': str(Path(bundle_path).relative_to(ROOT)), 'bundle_id': b['bundle_id'], 'lat_deg': site['lat'],
                    'lon_deg_east': site['lon'], 'observer_height_m': site['h_eye'],
                    'horizons_longitude_offset_deg': site['lon_offset']},
           'window_utc': {'start': START, 'stop': STOP, 'step': STEP,
                          'rule': 'fixed before any query; inside every ephemeris used; no extrapolation'},
           'definition': 'Orbiter centre above the stored terrain skyline (linear in azimuth) at a 1-minute sample; flat '
                         'control: above 0 deg. Apparent airless az/el from Horizons, rotated to the sphere normal.',
           'not_modelled': 'relay scheduling and orbiter operations, UHF link budget and antenna patterns, minimum-elevation '
                           'masks, atmosphere; pass edges are good to +-1 min; post-reconstruction trajectories are planning '
                           'predictions.',
           'orbiters': res, 'any_orbiter': union,
           'generator': {'command': command, 'git_commit': gitinfo.head()}}
    p = Path(out_dir) / 'mars_jezero_rim_relays_2026-11-14_16d.json'
    p.write_text(json.dumps(out, indent=1, allow_nan=False) + '\n')
    return out, p


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--offline', action='store_true')
    a = ap.parse_args(argv)
    out, p = build(not a.offline, command='python -m science.worlds.mars.relays ' + ' '.join(argv or sys.argv[1:]))
    print(p)
    for r in out['orbiters']:
        if r['status'] == 'computed':
            t = r['terrain']
            print(f"{r['id']}: {t['visible_pct_minute_samples']} % of minutes, {t['n_passes']} passes, "
                  f"{t['visible_min_per_day']} min/day, longest gap {t['longest_gap_min']} min; flat "
                  f"{r['flat_horizon_control']['visible_pct_minute_samples']} %")
        else:
            print(f"{r['id']}: {r['status']} — {r['reason']}")
    print('any:', out['any_orbiter'])


if __name__ == '__main__':
    main()
