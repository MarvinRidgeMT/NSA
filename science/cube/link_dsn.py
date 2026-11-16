"""Phase 4a — Deep Space Network geometry: does at least one DSN complex see the Moon above its mask?

For each hourly sample of the cube window (2026-11-14 00:00 .. 2027-11-28 00:00 UTC, 9097 samples) JPL Horizons
gives the airless apparent elevation of the Moon (301) from each DSN station, observer = '<station>@399'.
Station names are resolved by Horizons itself (each raw response states 'Center-site name' and geodetic
coordinates, recorded in the manifest). Stations: Goldstone DSS-14/-25, Madrid DSS-63/-56, Canberra DSS-43/-35.

A complex sees the Moon when any of its stations has Moon elevation >= the station mask (default 10 deg).
earth_dsn(t) = Earth centre visible from the lunar site over the terrain (cube rule) AND some complex sees the Moon.
This is geometry only (ENGINEERING ASSUMPTION): no scheduling, no link budget, no station downtime.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np

from .. import horizons as H
from . import ephem_year as E

ROOT = Path(__file__).resolve().parents[2]
RAW = E.RAW
STATIONS = {'goldstone': ('DSS-14', 'DSS-25'), 'madrid': ('DSS-63', 'DSS-56'), 'canberra': ('DSS-43', 'DSS-35')}
MASK_DEG = 10.0


def _params(station):
    return {'format': 'text', 'COMMAND': "'301'", 'OBJ_DATA': 'NO', 'MAKE_EPHEM': 'YES', 'EPHEM_TYPE': 'OBSERVER',
            'CENTER': f"'{station}@399'", 'QUANTITIES': "'4'", 'CSV_FORMAT': 'YES', 'ANG_FORMAT': 'DEG',
            'APPARENT': 'AIRLESS', 'EXTRA_PREC': 'YES', 'TIME_DIGITS': 'FRACSEC', 'CAL_FORMAT': 'CAL', 'TIME_TYPE': 'UT',
            'START_TIME': f"'{E.START}'", 'STOP_TIME': f"'{E.STOP}'", 'STEP_SIZE': "'1 h'"}


def station_series(station):
    """Returns (t unix, moon elevation deg, provenance dict)."""
    tag = f'dsn_{station.replace("-", "").lower()}_moon_year_20261114'
    p = RAW / f'{tag}.txt'
    if p.exists():
        text = p.read_text(); sha = hashlib.sha256(p.read_bytes()).hexdigest()
    else:
        text, sha, _ = H.fetch(_params(station), tag, raw_dir=RAW)
    name = re.search(r'Center-site name:\s*(.+)', text)
    geo = re.search(r'Center geodetic\s*:\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)', text)
    if not name or station not in name.group(1):
        raise ValueError(f'Horizons did not resolve {station}: {name.group(1) if name else "no site line"}')
    rows = H.parse_text(text)
    t = np.array([H.iso_to_unix(r['utc']) for r in rows])
    el = np.array([r['el_deg'] for r in rows], float)
    prov = {'station': station, 'horizons_site_name': name.group(1).strip(),
            'geodetic_elon_lat_altkm': [float(g) for g in geo.groups()] if geo else None,
            'path': f'data/cache/cube_horizons/{tag}.txt', 'sha256': sha, 'url': H.API}
    return t, el, prov


def complexes(mask_deg=MASK_DEG):
    """{complex: bool[9097]} Moon above mask from any station of the complex, plus 'any' and provenance."""
    out, prov, t0 = {}, [], None
    for cx, sts in STATIONS.items():
        v = None
        for st in sts:
            t, el, p = station_series(st)
            if t0 is None:
                t0 = t
            elif not np.array_equal(t, t0):
                raise ValueError('station time grids differ')
            prov.append(p)
            ok = el >= mask_deg
            v = ok if v is None else (v | ok)
        out[cx] = v
    out['any'] = out['goldstone'] | out['madrid'] | out['canberra']
    return out, t0, prov
