"""Terrain skyline (horizon elevation vs LOCAL azimuth) from DEM rays.

Each bin i has one ray at azimuth i*360/bins, clockwise from LOCAL north.
Rays follow great circles on the R_MOON_M sphere (so they are correct across
the pole), are projected to grid with the closed-form south-polar stereographic
formula (verified equal to the COG CRS via pyproj to < 1 mm in tests), sampled
bilinearly, lifted to Moon-fixed 3D P = (R+h) u(lat,lon), and converted to an
elevation angle against the observer's local up vector. No refraction (airless).

Near field (if given) is preferred where it has data; far field fills the rest.
A NaN at any distance <= max_range_m marks the bin 'truncated': its angle is then
only a lower bound computed from real samples; nothing is filled in.
"""
from __future__ import annotations

import math

import numpy as np

from . import frames


def _distances(step_near, near_cut, step_far, max_range):
    d1 = np.arange(step_near, min(near_cut, max_range) + 1e-9, step_near)
    if step_far is None or near_cut >= max_range:
        return d1
    start = (d1[-1] if d1.size else 0.0) + step_far
    return np.concatenate([d1, np.arange(start, max_range + 1e-9, step_far)])


def compute_skyline(lat, lon, obs_height_m, mast_m, near=None, far=None, bins=720,
                    max_range_m=150_000.0, step_m=None, near_range_m=None, far_step_m=None):
    if near is None and far is None:
        raise ValueError('need at least one DEM')
    step_near = step_m or (near.step if near is not None else far.step)
    near_cut = (near_range_m if near_range_m is not None else
                (max_range_m if far is None else _near_extent(near, lat, lon)))
    step_far = (far_step_m or far.step) if far is not None else None
    if near is None:
        step_near, near_cut = step_far, max_range_m
        step_far = None
    d = _distances(step_near, near_cut, step_far, max_range_m)
    az = np.arange(bins) * 360.0 / bins

    A, D = np.meshgrid(az, d, indexing='ij')           # (bins, nd)
    la2, lo2 = frames.destination(lat, lon, A, D)
    x, y = frames.stereo_forward(la2, lo2)
    h = np.full(A.shape, np.nan); src = np.zeros(A.shape, dtype=np.int8)  # 1 near, 2 far
    if near is not None:
        hn = near.sample(x, y); m = np.isfinite(hn); h[m] = hn[m]; src[m] = 1
    if far is not None:
        hf = far.sample(x, y); m = ~np.isfinite(h) & np.isfinite(hf); h[m] = hf[m]; src[m] = 2

    P_obs = frames.moon_fixed(lat, lon, obs_height_m + mast_m)
    up = frames.up_vector(lat, lon)
    P = (frames.R_MOON_M + np.nan_to_num(h))[..., None] * frames.unit(la2, lo2)
    el = frames.elevation_angle_deg(P_obs, up, P)
    el = np.where(np.isfinite(h), el, np.nan)

    valid = np.isfinite(h)
    first_gap = np.where(valid.all(axis=1), d.size, np.argmin(valid, axis=1))
    el_masked = np.where(np.arange(d.size)[None, :] < first_gap[:, None], el, np.nan)
    any_valid = np.isfinite(el_masked).any(axis=1)
    k = np.where(any_valid, np.nanargmax(np.where(np.isfinite(el_masked), el_masked, -1e9), axis=1), -1)

    names = {1: near.name if near is not None else None, 2: far.name if far is not None else None}
    out_el, status, crit, reach = [], [], [], []
    for i in range(bins):
        complete = first_gap[i] == d.size
        reach.append(float(d[first_gap[i] - 1]) if first_gap[i] > 0 else 0.0)
        if not any_valid[i]:
            out_el.append(None); status.append('truncated'); crit.append(None); continue
        j = k[i]
        out_el.append(round(float(el_masked[i, j]), 5))
        status.append('complete' if complete else 'truncated')
        crit.append({'distance_m': float(d[j]), 'lat_deg': round(float(la2[i, j]), 7),
                     'lon_deg': round(float(lo2[i, j]), 7), 'grid_x_m': round(float(x[i, j]), 2),
                     'grid_y_m': round(float(y[i, j]), 2), 'height_m': round(float(h[i, j]), 3),
                     'dem': names[int(src[i, j])]})

    # Upper bound on what terrain beyond max_range could contribute, using the
    # max height present in the far DEM (smooth-sphere geometry).
    beyond = None
    hmax_src = far if far is not None else near
    hmax = float(np.nanmax(hmax_src.Z))
    if np.isfinite(hmax):
        dd = np.linspace(max_range_m, 3 * max_range_m, 400)
        la_b, lo_b = frames.destination(lat, lon, 0.0, dd)
        Pb = (frames.R_MOON_M + hmax) * frames.unit(la_b, lo_b)
        beyond = float(np.max(frames.elevation_angle_deg(P_obs, up, Pb)))

    range_limited = [bool(beyond is not None and e is not None and e < beyond) for e in out_el]
    dip = -math.degrees(math.acos(frames.R_MOON_M / (frames.R_MOON_M + obs_height_m + mast_m))) \
        if obs_height_m + mast_m > 0 else 0.0
    return {
        'bins': bins, 'azimuth_deg': az.tolist(), 'elevation_deg': out_el, 'status': status,
        'critical': crit, 'valid_reach_m': reach,
        'n_truncated': int(sum(s == 'truncated' for s in status)),
        'max_range_m': float(max_range_m), 'near_cut_m': float(near_cut),
        'step_near_m': float(step_near), 'step_far_m': None if step_far is None else float(step_far),
        'n_samples_per_bin': int(d.size),
        'beyond_range_max_possible_elev_deg': beyond,
        'range_limited': range_limited, 'n_range_limited': int(sum(range_limited)), 'beyond_range_reference_height_m': hmax,
        'flat_baseline': {'elevation_deg': 0.0,
                          'smooth_sphere_dip_deg': round(dip, 5),
                          'note': 'Flat-horizon control: mathematical horizon (0 deg) for every bin; '
                                  'smooth_sphere_dip_deg is the bare-sphere geometric dip at this observer height.'},
        'method': 'great-circle rays, closed-form polar stereographic, bilinear DEM, Moon-fixed 3D elevation vs local up, single ray per bin centre, no refraction',
    }


def _near_extent(near, lat, lon):
    """Largest distance for which the near DEM can cover every azimuth (inscribed radius)."""
    x0, y0 = frames.stereo_forward(lat, lon)
    l, b, r, t = near.bounds
    return max(0.0, min(x0 - l, r - x0, y0 - b, t - y0) - near.step)
