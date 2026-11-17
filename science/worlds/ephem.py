"""JPL Horizons for any world's surface site (generic form of science/worlds/mercury/ephem.py).

Raw responses cached by the SHA-256 of the query (science.anysite.ephem.fetch_cached) under
$POLARIS_DATA/v2/products/<world>_horizons/. Columns located by header name. No interpolation or extrapolation.

Frame tie: `horizons_lon_offset_deg` is added to the DEM-frame east longitude before the query (the site's longitude in
Horizons' body-fixed frame, science/worlds/frame_tie.py); 0 when the DEM frame and Horizons' frame use the same model.
Horizons az/el (ellipsoid normal) are rotated to the sphere normal used by the skyline (World.horizons_azel_to_sphere).
"""
from __future__ import annotations

import os

import numpy as np

from .. import horizons as H
from ..anysite.ephem import fetch_cached, params_key

BODIES = {'sun': '10', 'earth': '399', 'mercury': '199', 'mars': '499'}


def cache_dir(world):
    base = os.environ.get('POLARIS_DATA') or os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'cache')
    return os.path.abspath(os.path.join(base, 'v2', 'products', f'{world.name}_horizons'))


def header_value(text, key):
    import re
    m = re.search(rf'^{re.escape(key)}\s*:\s*(.+)$', text, re.M)
    return m.group(1).strip() if m else None


def site_series(world, body, lat, lon, height_m, start, stop, step, allow_network=True, horizons_lon_offset_deg=0.0):
    lon_h = lon + horizons_lon_offset_deg
    p = world.horizons_params(BODIES[body], lat, lon_h, height_m, start, stop, step)
    body_txt, src = fetch_cached(p, cache_dir=cache_dir(world), allow_network=allow_network)
    text = body_txt.decode('utf-8')
    rows = H.parse_text(text)
    for r in rows:
        r['t'] = H.iso_to_unix(r['utc'])
    az_c, el_c, dlat = world.horizons_azel_to_sphere(np.array([r['az_deg'] for r in rows]),
                                                     np.array([r['el_deg'] for r in rows]), lat, lon, height_m)
    for r, a, e in zip(rows, az_c, el_c):
        r['az_horizons_deg'], r['el_horizons_deg'] = r['az_deg'], r['el_deg']
        r['az_deg'], r['el_deg'] = float(a), float(e)
    src.update({'params_key': params_key(p), 'horizons_lon_offset_deg': horizons_lon_offset_deg, 'center_site_header': {
        k: header_value(text, k) for k in ('Center geodetic', 'Center cylindric', 'Center pole/equ', 'Center radii')},
        'frame_tie_geodetic_minus_centric_lat_deg': dlat})
    return rows, src


def geocentric_sep(world, start, stop, step, allow_network=True):
    """The world seen from the geocentre: S-O-T = Sun-Earth-world (SEP) angle, delta, r."""
    from .mercury.ephem import _base, parse_columns
    p = _base(str(world.naif_id), '500@399', start, stop, step, '19,20,23')
    body_txt, src = fetch_cached(p, cache_dir=cache_dir(world), allow_network=allow_network)
    rows = parse_columns(body_txt.decode('utf-8'), {'r_au': r'^r$', 'delta_au': r'^delta$', 'sep_deg': r'^S-O-T$',
                                                    'sep_flag': r'^/r$'})
    src['params_key'] = params_key(p)
    return rows, src


def subsolar_point(world, start, stop, step, allow_network=True):
    """Sub-observer point seen from the Sun's centre (= sub-solar point; W-longitude for west-positive bodies,
    planetodetic latitude)."""
    from .mercury.ephem import _base, parse_columns
    p = _base(str(world.naif_id), '500@10', start, stop, step, '14,20')
    body_txt, src = fetch_cached(p, cache_dir=cache_dir(world), allow_network=allow_network)
    text = body_txt.decode('utf-8')
    rows = parse_columns(text, {'sub_lon_deg': r'^ObsSub-LON', 'sub_lat_deg': r'^ObsSub-LAT', 'delta_au': r'^delta$'})
    src.update({'params_key': params_key(p), 'target_pole_equ': header_value(text, 'Target pole/equ')})
    return rows, src
