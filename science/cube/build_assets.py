"""Phases 8 + 9.1 + 9.2 — multi-asset layout, lander footprint, per-asset heights.

  python -m science.cube.build_assets [site ...]

Geometry is SOURCE-BASED · UNVALIDATED; the asset shapes are ILLUSTRATIVE (vertical cylinders, not a lander design).
Positions are polar-stereographic grid metres from the bundle site (+dy points to the near side, i.e. Earth side).

Per asset, horizon(az) = max(terrain skyline at the asset's own position and height, top elevation of every OTHER
asset's cylinder within its azimuth sector). A cylinder at grid distance d, radius r, top H above its ground g_j,
seen from height h above ground g_p, blocks |az - bearing| <= asin(r/d) up to atan((g_j + H - g_p - h)/(d - r)).
Ephemeris at an offset: direction transfer (science/cube/compute.transfer_azel).

Layouts (D_layout):
  single        one point at the site, 1 m, no bodies  (must equal the single-point cube)
  research      lander body r 2 m h 4 m at (0,0); array on the deck top (0,0) 4.5 m; antenna Earth side (0,5) 2 m
  bad           lander body; array on a ground mast (0,5) 1 m; antenna on the far side (0,-5) 2 m
  tower         lander body; array and antenna on a ~15 m boom/tower at (0,10) (r 0.3 m)
Power = array sees the Sun centre; link = antenna sees the Earth centre AND a DSN complex sees the Moon (>= 10 deg).

Footprint (D_pad): 9 m x 9 m pad, centre and four corners at 1 m; worst/best over the pad.
Heights (D_height): at the site, 1.0 (array on a ground mast), 1.7 (crew eye), 2.0 (antenna), 4.5 (deck camera/array),
15 m (tower).
Windows (S_window): the 2026-11-14 14-day demo window (337 h) and 12 months (8760 h).
"""
from __future__ import annotations

import datetime as dt
import json
import math
import sys

import numpy as np

from . import compute as C
from . import ephem_year as E
from . import link_dsn as DSN
from .build_cube import LABEL, NOT_PROB, OUT, site_inputs
from .build_visibility import add_to_index
from .. import frames
from ..limits.common import git_commit, sha256_file

ILL = 'ILLUSTRATIVE asset shapes (cylinders), not a lander design'
BODY = {'name': 'lander body', 'xy': (0.0, 0.0), 'r': 2.0, 'top': 4.0}
LAYOUTS = {
    'single': {'array': ((0, 0), 1.0), 'antenna': ((0, 0), 1.0), 'bodies': []},
    'research': {'array': ((0, 0), 4.5), 'antenna': ((0, 5), 2.0), 'bodies': [BODY]},
    'bad': {'array': ((0, 5), 1.0), 'antenna': ((0, -5), 2.0), 'bodies': [BODY]},
    'tower': {'array': ((0, 10), 15.0), 'antenna': ((0, 10), 15.0),
              'bodies': [BODY, {'name': 'tower', 'xy': (0.0, 10.0), 'r': 0.3, 'top': 15.0}]},
}
PAD = {'centre': (0, 0), 'ne': (4.5, 4.5), 'nw': (-4.5, 4.5), 'se': (4.5, -4.5), 'sw': (-4.5, -4.5)}
HEIGHTS = (1.0, 1.7, 2.0, 4.5, 15.0)
WINDOWS = {'demo_14d': slice(0, E.WINDOW_H + 1), 'year_8760h': slice(0, 8760)}


def _ok(v):
    return float(v) if not float(v).is_integer() else int(v)


def body_horizon(sky, site, at_xy, at_h, ground_at, bodies, ground_of):
    """Terrain skyline at the asset raised by other assets' cylinders (returns a new elevation list)."""
    s = C.sites.SITES[site]
    lat, lon = (s['lat'], s['lon']) if at_xy == (0, 0) else C.offset_latlon(site, *at_xy)
    el = np.array([np.nan if v is None else v for v in sky['elevation_deg']], float)
    az = np.arange(sky['bins']) * 360.0 / sky['bins']
    for b in bodies:
        dx, dy = b['xy'][0] - at_xy[0], b['xy'][1] - at_xy[1]
        d = math.hypot(dx, dy)
        if d <= b['r']:
            continue                                     # the asset sits on/inside this body: no self-block
        brg = float(frames.grid_az_to_local_az(math.degrees(math.atan2(dx, dy)), lon)) % 360
        half = math.degrees(math.asin(b['r'] / d))
        top = math.degrees(math.atan2(ground_of(b['xy']) + b['top'] - (ground_at + at_h), d - b['r']))
        sel = np.abs((az - brg + 180) % 360 - 180) <= half
        el[sel] = np.maximum(el[sel], top)
    out = dict(sky); out['elevation_deg'] = [None if not np.isfinite(v) else float(v) for v in el]
    return out


def flags(site, eph, t_id, xy, h, bodies):
    """Hourly Sun- and Earth-centre visibility for an asset (bodies may be empty)."""
    xy = (_ok(xy[0]), _ok(xy[1]))
    sky = C.skyline(site, t_id, float(h), *xy)

    def ground(p):
        q = (_ok(p[0]), _ok(p[1]))
        if q == xy:
            return sky['ground_m']
        hit = sorted(C.SKY.glob(f'{site}_{t_id}_m*_x{q[0]}_y{q[1]}.json'))
        if not hit:
            raise FileNotFoundError(f'no cached skyline at {q} for {t_id}; run science.cube.compute --points')
        return json.loads(hit[0].read_text())['ground_m']
    if bodies:
        sky = body_horizon(sky, site, xy, h, sky['ground_m'], bodies, ground)
    s = C.sites.SITES[site]
    if xy == (0, 0):
        f = C.visible_flags(eph, sky)
    else:
        la, lo = C.offset_latlon(site, *xy)
        f = C.visible_flags(eph, sky, s['lat'], s['lon'], la, lo)
    return f['sun'], f['earth']


def _longest(f):
    idx = np.arange(f.size)
    return int((idx - np.maximum.accumulate(np.where(f, idx, -1))).max()) if f.size else 0


def _cube(site, cid, title, dims, metrics, desc, extra_lim=()):
    return {'schema': 'scenario-cube-v1', 'cube_id': f'{site}-{cid}-v1', 'site_id': site, 'title': title,
            'label': LABEL, 'generated_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'description': desc, 'dims': dims, 'metrics': metrics,
            'missing': {'encoding': 'sparse-flat-index', 'by_metric': {k: [] for k in metrics}},
            'provenance': {'inputs': [{'path': f'data/cache/cube_sky/{site}_*.json', 'sha256': _sky_hash(site),
                                       'note': 'cached skylines (PGDA 78 5 m + clones, PGDA 90 80 m)'}],
                           'command': 'python -m science.cube.build_assets ' + ' '.join(sys.argv[1:]), 'code_commit': git_commit(),
                           'solver': 'science/skyline (batched) + illustrative cylinders'},
            'limitations': [NOT_PROB, 'Local geometric visibility only; not power or link budgets.', *extra_lim]}


def _sky_hash(site):
    import hashlib
    h = hashlib.sha256()
    for f in sorted(C.SKY.glob(f'{site}_*.json')):
        h.update(f.name.encode()); h.update(f.read_bytes())
    return h.hexdigest()


def _m(vals, label, units='%', dec=2):
    return {'units': units, 'label': label, 'dtype': 'float64', 'decimals': dec,
            'values': [round(float(v), 4) for v in np.asarray(vals).reshape(-1)], 'provenance': 'science/cube/build_assets.py'}


def build(site):
    b, eph = site_inputs(site)
    dsn, _, _ = DSN.complexes()
    nT, nW = len(C.T_IDS), len(WINDOWS)
    T = {'name': 'T', 'kind': 'uncertainty_terrain', 'values': list(C.T_IDS), 'units': '', 'nominal_index': 0,
         'label': 'Terrain map: PGDA 78 nominal + 20 error clones', 'note': NOT_PROB}
    W = {'name': 'S_window', 'kind': 'schedule', 'values': list(WINDOWS), 'units': '', 'nominal_index': 0,
         'label': 'Window', 'value_labels': ['2026-11-14 + 14 d', '12 months from 2026-11-14']}
    # ---- layouts
    L = list(LAYOUTS)
    lay = {k: np.zeros((nT, len(L), nW)) for k in ('power', 'link', 'joint', 'gap')}
    for i, t in enumerate(C.T_IDS):
        for j, name in enumerate(L):
            cfg = LAYOUTS[name]
            (axy, ah), (nxy, nh) = cfg['array'], cfg['antenna']
            # every body is passed; one the asset stands on (distance <= radius) is skipped in body_horizon
            sun_a, _ = flags(site, eph, t, axy, ah, cfg['bodies'])
            _, earth_n = flags(site, eph, t, nxy, nh, cfg['bodies'])
            link = earth_n & dsn['any']
            for w, sl in enumerate(WINDOWS.values()):
                lay['power'][i, j, w] = 100 * sun_a[sl].mean(); lay['link'][i, j, w] = 100 * link[sl].mean()
                lay['joint'][i, j, w] = 100 * (sun_a & link)[sl].mean(); lay['gap'][i, j, w] = _longest(sun_a[sl])
    D_lay = {'name': 'D_layout', 'kind': 'design', 'values': L, 'units': '', 'nominal_index': 1,
             'label': 'Asset layout (ILLUSTRATIVE)', 'note': json.dumps({k: {'array': v['array'], 'antenna': v['antenna'],
                                                                              'bodies': [x['name'] for x in v['bodies']]} for k, v in LAYOUTS.items()})}
    layout = _cube(site, 'asset-layout', 'Multi-asset layout: power, link, joint', [T, D_lay, W],
                   {'power_pct': _m(lay['power'], 'Array sees the Sun centre'),
                    'link_pct': _m(lay['link'], 'Antenna sees the Earth centre and a DSN complex sees the Moon'),
                    'power_and_link_pct': _m(lay['joint'], 'Power AND link in the same hour'),
                    'longest_no_power_h': _m(lay['gap'], 'Longest hours with the array dark', 'h', 0)},
                   'Self-shadowing between assets (cylinders) plus terrain; joint power + link availability.', (ILL,))
    # ---- footprint
    P = list(PAD)
    pad = {k: np.zeros((nT, len(P), nW)) for k in ('sun', 'both')}
    for i, t in enumerate(C.T_IDS):
        for j, name in enumerate(P):
            s_, e_ = flags(site, eph, t, PAD[name], 1.0, [])
            for w, sl in enumerate(WINDOWS.values()):
                pad['sun'][i, j, w] = 100 * s_[sl].mean(); pad['both'][i, j, w] = 100 * (s_ & e_)[sl].mean()
    D_pad = {'name': 'D_pad', 'kind': 'design', 'values': P, 'units': '', 'nominal_index': 0,
             'label': 'Point on a 9 m x 9 m lander pad (centre and corners, 1 m)', 'note': json.dumps(PAD)}
    foot = _cube(site, 'footprint', 'Lander footprint: centre and corners of a 9 m pad', [T, D_pad, W],
                 {'sun_pct': _m(pad['sun'], 'Sun centre visible'), 'sun_earth_pct': _m(pad['both'], 'Sun and Earth centre visible')},
                 'Footprint check: worst and best point of the pad.')
    foot['derived'] = {'pad_range': {'dims': ['T', 'S_window'], 'metrics': {
        'sun_worst_pct': _m(pad['sun'].min(axis=1), 'Sun: worst point of the pad'),
        'sun_best_pct': _m(pad['sun'].max(axis=1), 'Sun: best point of the pad'),
        'sun_earth_worst_pct': _m(pad['both'].min(axis=1), 'Sun+Earth: worst point of the pad'),
        'sun_earth_best_pct': _m(pad['both'].max(axis=1), 'Sun+Earth: best point of the pad')},
        'method': 'min / max over the five pad points', 'caveat': 'pad size 9 m (configurable in build_assets.PAD)'}}
    # ---- heights
    hts = {k: np.zeros((nT, len(HEIGHTS), nW)) for k in ('sun', 'earth', 'both')}
    for i, t in enumerate(C.T_IDS):
        for j, h in enumerate(HEIGHTS):
            s_, e_ = flags(site, eph, t, (0, 0), h, [])
            for w, sl in enumerate(WINDOWS.values()):
                hts['sun'][i, j, w] = 100 * s_[sl].mean(); hts['earth'][i, j, w] = 100 * e_[sl].mean()
                hts['both'][i, j, w] = 100 * (s_ & e_)[sl].mean()
    D_h = {'name': 'D_height', 'kind': 'design', 'values': list(HEIGHTS), 'units': 'm', 'nominal_index': 0, 'label': 'Asset height above ground',
           'value_labels': ['1.0 m array on ground mast', '1.7 m crew eye', '2.0 m antenna', '4.5 m deck camera / array', '15 m tower']}
    heights = _cube(site, 'asset-heights', 'Per-asset heights at the site', [T, D_h, W],
                    {'sun_pct': _m(hts['sun'], 'Sun centre visible'), 'earth_pct': _m(hts['earth'], 'Earth centre visible'),
                     'sun_earth_pct': _m(hts['both'], 'Sun and Earth centre visible')},
                    'Visibility at the heights of individual assets (no bodies).')
    return layout, foot, heights


def write(site):
    entries = []
    for c, name in zip(build(site), ('asset_layout.json', 'footprint.json', 'asset_heights.json')):
        p = OUT / site / name
        p.write_text(json.dumps(c, separators=(',', ':')) + '\n')
        entries.append({'file': name, 'cube_id': c['cube_id'], 'title': c['title'], 'bytes': p.stat().st_size,
                        'uncompressed_bytes': p.stat().st_size, 'sha256': sha256_file(p), 'dims': [d['name'] for d in c['dims']]})
    add_to_index(site, entries)
    return entries


if __name__ == '__main__':
    for s in sys.argv[1:] or ['site04_roi3', 'site01_roi6']:
        write(s)
        lay = json.loads((OUT / s / 'asset_layout.json').read_text())
        v = np.array(lay['metrics']['link_pct']['values']).reshape(21, len(LAYOUTS), 2)
        p = np.array(lay['metrics']['power_and_link_pct']['values']).reshape(21, len(LAYOUTS), 2)
        print(s, 'nominal 12-month link % by layout', dict(zip(LAYOUTS, v[0, :, 1].round(2))), 'power&link', dict(zip(LAYOUTS, p[0, :, 1].round(2))))
