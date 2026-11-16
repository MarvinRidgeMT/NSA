"""G5 deterministic scenarios. Every scenario is a full recomputation (skyline from DEM,
Horizons samples for the scenario's position/time, bisection-refined events, metrics).
They are named alternatives, NOT a calibrated probability distribution."""
from __future__ import annotations

import math

import numpy as np

from . import bundle as B
from . import frames
from . import sites
from .dem import ArrayDEM

KEYS = ('sun_center_visible_pct', 'earth_center_visible_pct', 'sun_and_earth_center_visible_pct',
        'longest_sun_center_hidden_h', 'longest_earth_center_hidden_h',
        'sun_disk_mean_visible_fraction', 'earth_disk_mean_visible_fraction')


def _record(sid, family, params, r, base, method):
    m = r['metrics']
    sky = r['sky']
    e = [x for x in sky['elevation_deg'] if x is not None]
    man = {x['path']: x for x in __import__('json').loads((B.H.RAW_DIR / 'MANIFEST.json').read_text())}
    raws = [s['path'] for s in r['src']] + [s['path'] for s in r['raws']]
    return {
        'id': f'{sid}:{family}:' + ','.join(f'{k}={v}' for k, v in params.items()),
        'family': family, 'parameters': params, 'label': B.LABEL, 'method': method,
        'site_lat_deg': round(r['s']['lat'], 8), 'site_lon_deg_east': round(r['s']['lon'], 8),
        'site_height_m': round(r['h'], 3),
        'metrics': {k: m[k] for k in KEYS},
        'delta_vs_baseline': {k: round(m[k] - base['metrics'][k], 4) for k in KEYS},
        'skyline_summary': {'min_deg': min(e), 'max_deg': max(e), 'n_truncated': sky['n_truncated'],
                            'n_range_limited': sky['n_range_limited']},
        'n_events': len(r['events']),
        'events': [{k: ev[k] for k in ('body', 'event', 'utc')} for ev in r['events']],
        'horizons_raw': [{'path': p, 'sha256': man[p]['sha256']} for p in raws],
    }


def run_all(sid, base, start, days, step_h, mast_m, clones=(1, 2, 3, 4, 5), log=print):
    out = []
    near, far, s = base['near'], base['far'], base['s']
    lat0, lon0, h0 = s['lat'], s['lon'], base['h']

    # 1) 3x3 position offsets, +-100 m along LOCAL east/north
    for de in (-100, 0, 100):
        for dn in (-100, 0, 100):
            if de == 0 and dn == 0:
                r = base
            else:
                az = math.degrees(math.atan2(de, dn)) % 360; dist = math.hypot(de, dn)
                la, lo = frames.destination(lat0, lon0, az, dist)
                r = B.build(sid, start, days, step_h, mast_m, near=near, far=far,
                            tag_suffix=f'pos_e{de:+d}_n{dn:+d}', lat_lon_override=(la, lo))
            out.append(_record(sid, 'position-offset', {'east_m': de, 'north_m': dn}, r, base,
                               'site moved along great circle in local ENU; new DEM height, skyline, Horizons, events'))
            log('pos', de, dn, out[-1]['metrics'])

    # 2) mast height
    for mm in (2.0, 5.0, 10.0):
        r = base if mm == mast_m else B.build(sid, start, days, step_h, mm, near=near, far=far, tag_suffix=f'mast{mm:g}')
        out.append(_record(sid, 'mast-height', {'mast_m': mm}, r, base,
                           'skyline recomputed at eye height h+mast; Horizons altitude = DEM height (mast parallax < 1e-6 deg)'))
        log('mast', mm, out[-1]['metrics'])

    # 3) arrival +-12 h (window shifted, same length)
    import datetime as dt
    for dh in (-12, 12):
        st = (dt.datetime.fromisoformat(start) + dt.timedelta(hours=dh)).strftime('%Y-%m-%d %H:%M')
        r = B.build(sid, st, days, step_h, mast_m, near=near, far=far, tag_suffix=f'arr{dh:+d}h',
                    skyline_override=base['sky'])
        out.append(_record(sid, 'arrival-shift', {'shift_h': dh, 'start_utc': st}, r, base,
                           'same skyline; new Horizons window shifted by shift_h; events re-refined'))
        log('arr', dh, out[-1]['metrics'])

    # 4) DEM uncertainty: +-1 sigma (product-78 toterr) applied to near-field terrain, observer fixed
    err = sites.near_dem(sid, 'p78_err')
    if err.Z.shape != near.Z.shape or err.x_left != near.x_left or err.y_top != near.y_top:
        raise ValueError('toterr raster not co-registered with near DEM')
    for k in (-1, 1):
        nk = ArrayDEM(near.Z + k * err.Z, near.x_left, near.y_top, near.step,
                      name=f'{near.name} {k:+d}sigma(toterr)', meta=dict(near.meta))
        r = B.build(sid, start, days, step_h, mast_m, near=nk, far=far, tag_suffix=f'sig{k:+d}', h_override=h0)
        out.append(_record(sid, 'dem-uncertainty', {'kind': 'toterr-shift', 'sigma': k}, r, base,
                           'near-field heights shifted by k*toterr (fully correlated, a bounding case); observer height fixed; far field unchanged'))
        log('sig', k, out[-1]['metrics'])
    for c in clones:
        nc = sites.near_dem(sid, clone=c)
        r = B.build(sid, start, days, step_h, mast_m, near=nc, far=far, tag_suffix=f'clone{c:03d}')
        out.append(_record(sid, 'dem-uncertainty', {'kind': 'product-78-clone', 'clone': c}, r, base,
                           'near field replaced by a product-78 clone (Barker et al. 2021); observer height from that clone'))
        log('clone', c, out[-1]['metrics'])

    # 5) one recomputed repair: best position offset (max Sun+Earth) combined with a 10 m mast
    pos = [x for x in out if x['family'] == 'position-offset']
    best = max(pos, key=lambda x: (x['metrics']['sun_and_earth_center_visible_pct'], x['metrics']['sun_center_visible_pct']))
    de, dn = best['parameters']['east_m'], best['parameters']['north_m']
    la, lo = (lat0, lon0) if (de, dn) == (0, 0) else frames.destination(
        lat0, lon0, math.degrees(math.atan2(de, dn)) % 360, math.hypot(de, dn))
    r = B.build(sid, start, days, step_h, 10.0, near=near, far=far, tag_suffix=f'repair_e{de:+d}_n{dn:+d}_mast10',
                lat_lon_override=(la, lo))
    out.append(_record(sid, 'repair', {'east_m': de, 'north_m': dn, 'mast_m': 10.0,
                                       'selection': 'position offset with max sun_and_earth_center_visible_pct, then 10 m mast'},
                       r, base, 'combined change fully recomputed (not a sum of single-factor deltas)'))
    log('repair', out[-1]['parameters'], out[-1]['metrics'])
    return out
