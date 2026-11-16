"""Curvature limit: how far away terrain can still matter for a skyline on a sphere.

A point at height H above the R sphere, at central angle θ from an observer whose eye is at radius r0 = R + h_eye, has
elevation  el(θ) = atan2((R+H) cos θ − r0, (R+H) sin θ), which decreases monotonically with θ (0 < θ < π/2).
Setting el = e gives (R+H) cos(θ + e) = r0 cos e, so terrain no higher than H can reach elevation e only within

    θ_max(e) = acos(r0 cos e / (R + H)) − e,      L(e) = R θ_max(e)    (arc length on the reference sphere).

H = the Moon's highest point makes L a conservative limit for the Moon's relief. Published values for the summit near
Engel'gardt differ with datum/epoch (10.63-10.79 km); the largest, 10 786 m (LOLA, Smith et al. 2010, GRL 37, L18204),
is used so the limit errs long. The lowest point (Antoniadi, about -9.1 to -9.2 km) bounds the observer side.
"""
from __future__ import annotations

import math

import numpy as np

from ..frames import R_MOON_M

MOON_MAX_HEIGHT_M = 10_786.0
MOON_MIN_HEIGHT_M = -9_178.0
RELIEF_SOURCE = ('Moon highest point +10 786 m (Selenean summit, LOLA; Smith et al. 2010 GRL 37 L18204; largest published '
                 'value, chosen to be conservative); lowest point about -9.18 km (Antoniadi). Heights above 1 737 400 m.')


def max_angle_rad(h_eye_m, e_deg, H_m=MOON_MAX_HEIGHT_M, R=R_MOON_M):
    """Largest central angle at which terrain of height H_m can still reach elevation e_deg. NaN if never."""
    e = np.radians(np.asarray(e_deg, float))
    c = (R + h_eye_m) * np.cos(e) / (R + H_m)
    with np.errstate(invalid='ignore'):
        th = np.arccos(np.clip(c, -1, 1)) - e
    return np.where(c <= 1.0, th, np.nan)


def limit_m(h_eye_m, e_deg=0.0, H_m=MOON_MAX_HEIGHT_M, R=R_MOON_M):
    return R * max_angle_rad(h_eye_m, e_deg, H_m, R)


def elevation_deg(h_eye_m, H_m, s_m, R=R_MOON_M):
    """Elevation of a point at height H_m and arc distance s_m (closed form above, for tests and bounds)."""
    th = np.asarray(s_m, float) / R
    rH = R + H_m; r0 = R + h_eye_m
    return np.degrees(np.arctan2(rH * np.cos(th) - r0, rH * np.sin(th)))


def required_range(h_eye_m, skyline_el_deg, H_m=MOON_MAX_HEIGHT_M):
    """L_req = max over bins of L(e_bin): beyond it no terrain <= H_m can rise above any bin's skyline."""
    e = np.array([np.nan if v is None else v for v in skyline_el_deg], float)
    if not np.isfinite(e).any():
        return float('nan')
    return float(np.nanmax(limit_m(h_eye_m, e[np.isfinite(e)], H_m)))


def record(h_eye_m, max_range_m, skyline_el_deg, regional_H_m=None):
    """Bundle record: the limit, the inputs, and which bins could still be raised by terrain beyond max_range_m."""
    e = np.array([np.nan if v is None else v for v in skyline_el_deg], float)
    bound_world = float(elevation_deg(h_eye_m, MOON_MAX_HEIGHT_M, max_range_m))
    flagged = [bool(np.isfinite(v) and v < bound_world) for v in e]
    out = {
        'formula': 'theta_max(e) = acos((R + h_eye) cos e / (R + H)) - e ; L = R theta_max ; L_req = max over bins L(e_bin)',
        'R_m': R_MOON_M, 'h_eye_m': round(float(h_eye_m), 3), 'H_world_max_m': MOON_MAX_HEIGHT_M,
        'relief_source': RELIEF_SOURCE,
        'limit_e0_world_m': round(float(limit_m(h_eye_m, 0.0)), 1),
        'required_range_world_m': round(required_range(h_eye_m, skyline_el_deg), 1),
        'max_range_m': float(max_range_m),
        'beyond_range_world_bound_elev_deg': round(bound_world, 5),
        'range_limited_world': flagged, 'n_range_limited_world': int(sum(flagged)),
        'note': ('Bins flagged range_limited_world have a skyline below the highest elevation any terrain on the Moon '
                 '(<= +10 786 m) could reach from beyond max_range_m: their value is a lower bound in that sense only.'),
    }
    if regional_H_m is not None and math.isfinite(regional_H_m):
        out['H_regional_max_m'] = round(float(regional_H_m), 1)
        out['required_range_regional_m'] = round(required_range(h_eye_m, skyline_el_deg, regional_H_m), 1)
    return out
