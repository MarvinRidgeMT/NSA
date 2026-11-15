"""Terrain-horizon crossings of Sun/Earth refined by bisection on real Horizons
evaluations (no interpolation of ephemerides), and visible-disk fraction.

margin m(t)  = el(t) - H(az(t))     [deg, vertical, H = terrain skyline]
m_perp       = m / sqrt(1 + s^2), s = dH/(daz cos el)  (local horizon treated as a
               straight line of slope s across the disk)
disk fraction= area of a circle of angular radius r lying above that line.
Events: centre (m_perp = 0), upper limb (m_perp = -r, first/last light),
lower limb (m_perp = +r, fully visible/starting to set).
"""
from __future__ import annotations

import math

import numpy as np

SUN_RADIUS_FALLBACK_DEG = 0.2666  # documented fallback only if Horizons Ang-diam missing


def disk_fraction_visible(m, r, horizon_slope=0.0):
    mp = m / math.sqrt(1.0 + horizon_slope ** 2)
    if mp >= r:
        return 1.0
    if mp <= -r:
        return 0.0
    seg = r * r * math.acos(mp / r) - mp * math.sqrt(r * r - mp * mp)
    return 1.0 - seg / (math.pi * r * r)


def horizon_at(sky, az):
    """Linear interpolation of skyline at az (deg). Returns (H, slope deg/deg, flag)
    flag in {'complete','truncated','unknown'}."""
    n = sky['bins']; w = 360.0 / n
    u = (az % 360.0) / w
    i0 = int(math.floor(u)) % n; i1 = (i0 + 1) % n; a = u - math.floor(u)
    e0, e1 = sky['elevation_deg'][i0], sky['elevation_deg'][i1]
    if e0 is None or e1 is None:
        return None, None, 'unknown'
    flag = 'complete' if sky['status'][i0] == sky['status'][i1] == 'complete' else 'truncated'
    return (1 - a) * e0 + a * e1, (e1 - e0) / w, flag


def margins(row, sky):
    H, s, flag = horizon_at(sky, row['az_deg'])
    if H is None:
        return None
    r = row['radius_deg']
    m = row['el_deg'] - H
    s_eff = s / max(math.cos(math.radians(row['el_deg'])), 1e-6)
    mp = m / math.sqrt(1 + s_eff ** 2)
    return {'horizon_deg': H, 'margin_deg': m, 'margin_perp_deg': mp, 'slope': s_eff,
            'disk_fraction': disk_fraction_visible(m, r, s_eff), 'horizon_flag': flag,
            'g': {'center': mp, 'upper_limb': mp + r, 'lower_limb': mp - r}}


def bisect_many(f_batch, brackets, tol_s=0.5, max_iter=40):
    """brackets: list of (t0, t1, g0) with sign change. f_batch(list_t) -> list g.
    One f_batch call per iteration evaluates every bracket's midpoint."""
    br = [list(b) for b in brackets]
    it = 0
    while br and it < max_iter and max(b[1] - b[0] for b in br) > tol_s:
        mids = [(b[0] + b[1]) / 2 for b in br]
        gs = f_batch(mids)
        for b, tm, gm in zip(br, mids, gs):
            if gm is None:
                continue
            if (gm > 0) == (b[2] > 0):
                b[0], b[2] = tm, gm
            else:
                b[1] = tm
        it += 1
    return [((b[0] + b[1]) / 2, b[1] - b[0]) for b in br], it


def bisect_crossing(f, t0, t1, tol_s=0.5):
    g0 = f([t0])[0]
    (res,), it = bisect_many(f, [(t0, t1, g0)], tol_s)
    return res[0], it
