"""Earth and Sun geometry in the Moon's body-fixed frame for the global analytics maps (R2 plan §4). Display analytics only.

One JPL Horizons OBSERVER request per span: observer Earth geocentre (CENTER 500@399), target Moon (301),
QUANTITIES 14,15,19,20:
  ObsSub-LON/LAT  sub-Earth point on the Moon (the Earth's direction from the Moon's centre), MOON_ME, east-positive,
                  1737.4 km sphere (both read back from the response header and checked);
  SunSub-LON/LAT  sub-solar point on the Moon;
  r               Sun-Moon distance (au);   delta  Earth-Moon distance (au).
Every raw response is archived byte-for-byte under $POLARIS_DATA/v2/analytics/horizons/ with its SHA-256 in
MANIFEST.json; parsing locates columns by header name. The parsed series is cached as geometry_<tag>.npz.

Topocentric directions (vectors in the Moon ME frame, metres):
  Earth centre seen from P = delta * u(subEarth) - P          (parallax ~0.26 deg included)
  Sun centre seen from P   ~ u(subSolar)                       (P / r < 1e-5 rad: neglected)
Cross-check (`python -m tools.globe.ephem check`): az/el derived here at a site vs Horizons coord@301 az/el (an
independent query path through the observer-site machinery).

    python -m tools.globe.ephem fetch          # 2026-01-01 .. 2044-08-01 at 3 h (>= one 18.6-year nodal cycle)
    python -m tools.globe.ephem check
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

from tools.globe import pyramid_products as PP

API = 'https://ssd.jpl.nasa.gov/api/horizons.api'
R_MOON = 1737400.0
AU_M = 149_597_870_700.0
R_EARTH_EQ_M = 6_378_137.0
R_SUN_M = 695_700_000.0                 # IAU 2015 nominal solar radius
SPAN = ('2026-01-01', '2044-08-01')     # 18.58 years >= one lunar nodal cycle (18.61 y)
STEP = '3h'
CHUNKS = (('2026-01-01', '2035-05-01'), ('2035-05-01', '2044-08-01'))
MONTHS = {m: i + 1 for i, m in enumerate('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split())}


def root():
    return PP.polaris_data() / 'v2' / 'analytics' / 'horizons'


def params(start, stop, step=STEP):
    return {'format': 'text', 'COMMAND': "'301'", 'OBJ_DATA': 'NO', 'MAKE_EPHEM': 'YES', 'EPHEM_TYPE': 'OBSERVER',
            'CENTER': "'500@399'", 'START_TIME': f"'{start}'", 'STOP_TIME': f"'{stop}'", 'STEP_SIZE': f"'{step}'",
            'QUANTITIES': "'14,15,19,20'", 'CSV_FORMAT': 'YES', 'ANG_FORMAT': 'DEG', 'EXTRA_PREC': 'YES',
            'TIME_TYPE': 'UT', 'CAL_FORMAT': 'CAL'}


def _fetch(p, tag, retries=4):
    d = root(); d.mkdir(parents=True, exist_ok=True)
    out = d / f'{tag}.txt'
    if out.exists():
        return out.read_text()
    url = API + '?' + urllib.parse.urlencode(p)
    for k in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=600) as r:
                body = r.read()
            break
        except Exception:
            if k == retries - 1:
                raise
            time.sleep(10 * (k + 1))
    out.write_bytes(body)
    man = d / 'MANIFEST.json'
    m = json.loads(man.read_text()) if man.exists() else {}
    m[out.name] = {'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body), 'params': p, 'api': API,
                   'fetched_utc': _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
    man.write_text(json.dumps(m, indent=1))
    return body.decode()


def parse(text):
    """-> dict of arrays: unix (s, UT), se_lat, se_lon, ss_lat, ss_lon (deg), r_m (Sun-Moon), d_m (Earth-Moon)."""
    if 'Target pole/equ : MOON_ME' not in text:
        raise ValueError('Horizons response is not in MOON_ME')
    if not re.search(r'Target radii\s*:\s*1737\.4, 1737\.4, 1737\.4 km', text):
        raise ValueError('Horizons target radii are not the 1737.4 km sphere')
    lines = text.splitlines()
    soe = lines.index('$$SOE'); eoe = lines.index('$$EOE')
    head = next(l for l in reversed(lines[:soe]) if 'Date__' in l)
    names = [h.strip() for h in head.split(',')]
    col = {k: names.index(n) for k, n in (('se_lon', 'ObsSub-LON'), ('se_lat', 'ObsSub-LAT'), ('ss_lon', 'SunSub-LON'),
                                          ('ss_lat', 'SunSub-LAT'), ('r', 'r'), ('d', 'delta'))}
    rows = {k: [] for k in col}; t = []
    for l in lines[soe + 1:eoe]:
        f = [x.strip() for x in l.split(',')]
        d, hm = f[0].split()
        y, mo, dd = d.split('-')
        hh, mi = hm.split(':')[:2]
        t.append(_dt.datetime(int(y), MONTHS[mo], int(dd), int(hh), int(mi), tzinfo=_dt.timezone.utc).timestamp())
        for k, i in col.items():
            rows[k].append(float(f[i]))
    lon = lambda a: (np.asarray(a) + 180.0) % 360.0 - 180.0
    return {'unix': np.asarray(t), 'se_lat': np.asarray(rows['se_lat']), 'se_lon': lon(rows['se_lon']),
            'ss_lat': np.asarray(rows['ss_lat']), 'ss_lon': lon(rows['ss_lon']),
            'r_m': np.asarray(rows['r']) * AU_M, 'd_m': np.asarray(rows['d']) * AU_M}


def geometry(fetch=False):
    """The cached series for SPAN (fetching it if `fetch`)."""
    cache = root() / 'geometry_2026_2044_3h.npz'
    if cache.exists():
        z = np.load(cache)
        return {k: z[k] for k in z.files}
    if not fetch:
        raise FileNotFoundError(f'{cache} missing: run python -m tools.globe.ephem fetch')
    parts = [parse(_fetch(params(a, b), f'moon_from_earth_{a}_{b}_{STEP}')) for a, b in CHUNKS]
    g = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    _, keep = np.unique(g['unix'], return_index=True)      # chunk boundaries overlap by one sample
    g = {k: v[keep] for k, v in g.items()}
    np.savez(cache, **g)
    return g


def unit(lat, lon):
    la, lo = np.radians(lat), np.radians(lon)
    return np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], -1)


def enu(lat, lon):
    la, lo = np.radians(lat), np.radians(lon)
    e = np.stack([-np.sin(lo), np.cos(lo), np.zeros_like(lo)], -1)
    n = np.stack([-np.sin(la) * np.cos(lo), -np.sin(la) * np.sin(lo), np.cos(la)], -1)
    u = np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], -1)
    return e, n, u


def topo_azel(lat, lon, h_m, vec_body):
    """Az (deg, 0 = north, 90 = east) and elevation (deg) of body-fixed target vectors `vec_body` (..., 3, metres,
    Moon-centred) seen from the surface point (lat, lon, h above the 1737.4 km sphere)."""
    e, n, u = enu(lat, lon)
    P = (R_MOON + h_m) * u
    v = vec_body - P
    v = v / np.linalg.norm(v, axis=-1, keepdims=True)
    az = np.degrees(np.arctan2(v @ e, v @ n)) % 360.0
    el = np.degrees(np.arcsin(np.clip(v @ u, -1, 1)))
    return az, el


def check(lat=-89.45, lon=-137.31, h_m=1800.0, n=40):
    """Earth and Sun az/el from the sub-point series vs Horizons coord@301 site az/el at the same times."""
    from science import horizons as HZ
    g = geometry()
    idx = np.linspace(0, g['unix'].size - 1, n).astype(int)
    E = g['d_m'][idx, None] * unit(g['se_lat'][idx], g['se_lon'][idx])
    S = g['r_m'][idx, None] * unit(g['ss_lat'][idx], g['ss_lon'][idx])
    out = {}
    for name, tgt, V in (('earth', '399', E), ('sun', '10', S)):
        az, el = topo_azel(lat, lon, h_m, V)
        p = HZ.build_params(tgt, lat, lon, h_m, tlist=[g['unix'][i] / 86400.0 + 2440587.5 for i in idx])
        rows = HZ.parse_text(_fetch(p, f'check_{name}_{lat}_{lon}_{h_m}_{n}'))
        az_h = np.array([r['az_deg'] for r in rows]); el_h = np.array([r['el_deg'] for r in rows])
        daz = (az - az_h + 180) % 360 - 180
        out[name] = {'n': int(n), 'max_abs_del_deg': float(np.max(np.abs(el - el_h))),
                     'max_abs_daz_deg': float(np.max(np.abs(daz))), 'site': [lat, lon, h_m]}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.globe.ephem')
    ap.add_argument('cmd', choices=['fetch', 'check'])
    a = ap.parse_args(argv)
    if a.cmd == 'fetch':
        g = geometry(fetch=True)
        print(f"{g['unix'].size} samples; sub-Earth lat {g['se_lat'].min():.2f}..{g['se_lat'].max():.2f}, "
              f"lon {g['se_lon'].min():.2f}..{g['se_lon'].max():.2f}; sub-solar lat {g['ss_lat'].min():.3f}.."
              f"{g['ss_lat'].max():.3f}")
    else:
        print(json.dumps(check(), indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
