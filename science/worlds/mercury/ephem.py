"""JPL Horizons for Mercury: topocentric Sun/Earth from a surface site, geocentric Sun-Earth-probe angle, and the sub-solar
point (independent check of longitude sign and azimuth convention).

Raw responses are cached by the SHA-256 of the query (science.anysite.ephem.fetch_cached, read-only use) under
$POLARIS_DATA/v2/products/mercury_horizons/ with a JSON sidecar (sha256, retrieved_utc, params). Columns are located by
header name, never by position. No interpolation or extrapolation: values exist only at Horizons-evaluated times.
"""
from __future__ import annotations

import os
import re

from ... import horizons as H
from ...anysite.ephem import fetch_cached, params_key
from .world import MERCURY

CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'cache', 'v2', 'products',
                                         'mercury_horizons'))
BODIES = {'sun': '10', 'earth': '399', 'mercury': '199'}


def _base(command, center, start, stop, step, quantities):
    return {'format': 'text', 'COMMAND': f"'{command}'", 'OBJ_DATA': 'NO', 'MAKE_EPHEM': 'YES', 'EPHEM_TYPE': 'OBSERVER',
            'CENTER': f"'{center}'", 'START_TIME': f"'{start}'", 'STOP_TIME': f"'{stop}'", 'STEP_SIZE': f"'{step}'",
            'QUANTITIES': f"'{quantities}'", 'CSV_FORMAT': 'YES', 'ANG_FORMAT': 'DEG', 'APPARENT': 'AIRLESS',
            'EXTRA_PREC': 'YES', 'TIME_DIGITS': 'FRACSEC', 'CAL_FORMAT': 'CAL', 'TIME_TYPE': 'UT'}


def parse_columns(text, wanted):
    """{key: regex on header name} -> rows with 'utc', 't' and the wanted floats (None for n.a.)."""
    lines = text.splitlines()
    soe = next(i for i, l in enumerate(lines) if l.strip() == '$$SOE')
    eoe = next(i for i, l in enumerate(lines) if l.strip() == '$$EOE')
    header = next(l for l in reversed(lines[:soe]) if 'Date__' in l)
    names = [h.strip() for h in header.split(',')]
    idx = {}
    for k, rx in wanted.items():
        hits = [i for i, n in enumerate(names) if re.search(rx, n)]
        if not hits:
            raise ValueError(f'column {k} ({rx}) missing from header {names}')
        idx[k] = hits[0]
    rows = []
    for l in lines[soe + 1:eoe]:
        f = [x.strip() for x in l.split(',')]
        r = {'utc': H._iso(f[0])}
        r['t'] = H.iso_to_unix(r['utc'])
        for k, i in idx.items():
            v = f[i]
            try:
                r[k] = float(v)
            except ValueError:
                r[k] = v if v not in ('', 'n.a.') else None
        rows.append(r)
    return rows


def header_value(text, key):
    m = re.search(rf'^{re.escape(key)}\s*:\s*(.+)$', text, re.M)
    return m.group(1).strip() if m else None


def site_series(body, lat, lon, height_m, start, stop, step, allow_network=True, world=MERCURY):
    """Topocentric az/el/ang-diam/range of `body` from the site. Adds sphere-normal az/el (frame tie) next to the raw
    Horizons values. Returns rows, source record."""
    p = world.horizons_params(BODIES[body], lat, lon, height_m, start, stop, step)
    body_txt, src = fetch_cached(p, cache_dir=CACHE_DIR, allow_network=allow_network)
    text = body_txt.decode('utf-8')
    rows = H.parse_text(text)
    for r in rows:
        r['t'] = H.iso_to_unix(r['utc'])
    import numpy as np
    az_c, el_c, dlat = world.horizons_azel_to_sphere(np.array([r['az_deg'] for r in rows]),
                                                     np.array([r['el_deg'] for r in rows]), lat, lon, height_m)
    for r, a, e in zip(rows, az_c, el_c):
        r['az_horizons_deg'], r['el_horizons_deg'] = r['az_deg'], r['el_deg']
        r['az_deg'], r['el_deg'] = float(a), float(e)
    src.update({'params_key': params_key(p), 'center_site_header': {
        k: header_value(text, k) for k in ('Center geodetic', 'Center cylindric', 'Center pole/equ', 'Center radii')},
        'frame_tie_geodetic_minus_centric_lat_deg': dlat})
    return rows, src


def geocentric_sep(start, stop, step, allow_network=True):
    """Mercury seen from the geocentre: S-O-T = Sun-Earth-Mercury (SEP) angle, delta (Earth-Mercury), r (Sun-Mercury)."""
    p = _base(BODIES['mercury'], '500@399', start, stop, step, '19,20,23')
    body_txt, src = fetch_cached(p, cache_dir=CACHE_DIR, allow_network=allow_network)
    rows = parse_columns(body_txt.decode('utf-8'), {'r_au': r'^r$', 'delta_au': r'^delta$', 'sep_deg': r'^S-O-T$',
                                                    'sep_flag': r'^/r$'})
    src['params_key'] = params_key(p)
    return rows, src


def subsolar_point(start, stop, step, allow_network=True):
    """Sub-observer point on Mercury seen from the Sun's centre (= sub-solar point, Sun-frame apparent): Horizons quantity
    14 gives planetodetic W-longitude for west-positive bodies (checked: header 'Target pole/equ')."""
    p = _base(BODIES['mercury'], '500@10', start, stop, step, '14,20')
    body_txt, src = fetch_cached(p, cache_dir=CACHE_DIR, allow_network=allow_network)
    text = body_txt.decode('utf-8')
    rows = parse_columns(text, {'sub_lon_deg': r'^ObsSub-LON', 'sub_lat_deg': r'^ObsSub-LAT', 'delta_au': r'^delta$'})
    src.update({'params_key': params_key(p), 'target_pole_equ': header_value(text, 'Target pole/equ')})
    return rows, src
