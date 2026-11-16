"""12-month hourly JPL Horizons ephemeris for a cube site (Sun 10, Earth 399).

Window: 2026-11-14 00:00 UTC + 8760 h of starts + 14 d demo window = 9097 hourly samples, so every
hourly start over 12 months has a complete 14-day window. Same query as science/bundle.py (observer =
coord@301 at the bundle site lat/lon and near-DEM ground height, airless apparent az/el, quantities
4,13,20). Raw responses go to data/cache/cube_horizons/ (git-ignored) with SHA-256 in that folder's
MANIFEST.json; the parsed arrays are cached as .npz next to them. No ephemeris is interpolated.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from .. import horizons as H
from ..bundle import BODIES, _radius_deg

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'data' / 'cache' / 'cube_horizons'
START = '2026-11-14 00:00'
STOP = '2027-11-28 00:00'      # 9097 hourly samples
N_STARTS = 8761                # hourly starts 2026-11-14 00:00 .. 2027-11-14 00:00
WINDOW_H = 336                 # 14 d; a window has WINDOW_H + 1 samples (both endpoints), as the bundles


def load(site_id, lat, lon, h_m):
    """Returns dict t (unix s), {sun,earth}_{az,el,r,range_au} float64 arrays and provenance."""
    npz = RAW / f'{site_id}_year.npz'
    if npz.exists():
        z = np.load(npz, allow_pickle=False)
        out = {k: z[k] for k in z.files if k != 'prov'}
        out['prov'] = [dict(zip(('body', 'path', 'sha256'), p.split('|'))) for p in z['prov']]
        return out
    out, prov = {}, []
    for body in ('sun', 'earth'):
        tag = f'{site_id}_{body}_year_20261114'
        p = RAW / f'{tag}.txt'
        if p.exists():
            text = p.read_text(); sha = hashlib.sha256(p.read_bytes()).hexdigest()
        else:
            text, sha, _ = H.fetch(H.build_params(BODIES[body], lat, lon, h_m, START, STOP, '1 h'), tag, raw_dir=RAW)
        rows = H.parse_text(text)
        t = np.array([H.iso_to_unix(r['utc']) for r in rows])
        if 't' in out and not np.array_equal(out['t'], t):
            raise ValueError('sun/earth time grids differ')
        out['t'] = t
        out[f'{body}_az'] = np.array([r['az_deg'] for r in rows], float)
        out[f'{body}_el'] = np.array([r['el_deg'] for r in rows], float)
        out[f'{body}_r'] = np.array([_radius_deg(r)[0] for r in rows], float)
        out[f'{body}_range_au'] = np.array([r.get('range_au') or np.nan for r in rows], float)
        prov.append(f'{body}|data/cache/cube_horizons/{tag}.txt|{sha}')
    if out['t'].size != N_STARTS + WINDOW_H:
        raise ValueError(f'expected {N_STARTS + WINDOW_H} samples, got {out["t"].size}')
    np.savez(npz, prov=np.array(prov), **out)
    out['prov'] = [dict(zip(('body', 'path', 'sha256'), p.split('|'))) for p in prov]
    return out
