"""World-aware terrain skyline (horizon elevation vs LOCAL azimuth) from DEM rays.

`compute_skyline(world, ...)`:
  * Moon with DEMs in the south-polar LDEM grid -> science.skyline.compute_skyline, unchanged (the Moon path is the
    existing code, not a copy).
  * any other world (or DEM layers in other projections) -> `layered_skyline`, the same algorithm with the radius and
    each layer's projection taken from the world/layer: great-circle rays on the world's sphere, each layer sampled in
    its own grid, priority fill (first layer with data wins, as near-before-far in the Moon code), 3D elevation against
    the sphere normal, the first no-data sample truncates the bin (value = lower bound), bound from terrain beyond range.
`layered_skyline` with the Moon's radius and the south-polar projection reproduces science.skyline.compute_skyline
exactly (science/worlds/tests/test_skyline_world.py), which is how the generic path is regression-tested.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

import numpy as np

from .geometry import Sphere


@dataclass
class Layer:
    dem: object                         # science.dem.ArrayDEM-like: .sample(x, y), .step, .Z, .name, .bounds
    forward: Callable                   # (lat, lon) -> grid (x, y) of this DEM
    role: str = 'near'


def _distances(step_near, near_cut, step_far, max_range):
    d1 = np.arange(step_near, min(near_cut, max_range) + 1e-9, step_near)
    if step_far is None or near_cut >= max_range:
        return d1
    start = (d1[-1] if d1.size else 0.0) + step_far
    return np.concatenate([d1, np.arange(start, max_range + 1e-9, step_far)])


def layered_skyline(sphere: Sphere, lat, lon, obs_height_m, mast_m, layers: List[Layer], bins=720, max_range_m=150_000.0,
                    step_near_m=None, near_cut_m=None, step_far_m=None, beyond_reference: Optional[Layer] = None):
    if not layers:
        raise ValueError('need at least one DEM layer')
    step_near = step_near_m or layers[0].dem.step
    near_cut = max_range_m if near_cut_m is None else near_cut_m
    d = _distances(step_near, near_cut, step_far_m, max_range_m)
    az = np.arange(bins) * 360.0 / bins
    A, D = np.meshgrid(az, d, indexing='ij')
    la2, lo2 = sphere.destination(lat, lon, A, D)
    h = np.full(A.shape, np.nan); src = np.full(A.shape, -1, dtype=np.int16)
    gx = np.full(A.shape, np.nan); gy = np.full(A.shape, np.nan)
    for k, L in enumerate(layers):
        x, y = L.forward(la2, lo2)
        hk = L.dem.sample(x, y)
        m = ~np.isfinite(h) & np.isfinite(hk)
        h[m] = hk[m]; src[m] = k; gx[m] = x[m]; gy[m] = y[m]

    P_obs = sphere.body_fixed(lat, lon, obs_height_m + mast_m)
    up = sphere.up(lat, lon)
    P = (sphere.R + np.nan_to_num(h))[..., None] * sphere.unit(la2, lo2)
    el = sphere.elevation_angle_deg(P_obs, up, P)
    el = np.where(np.isfinite(h), el, np.nan)

    valid = np.isfinite(h)
    first_gap = np.where(valid.all(axis=1), d.size, np.argmin(valid, axis=1))
    el_masked = np.where(np.arange(d.size)[None, :] < first_gap[:, None], el, np.nan)
    any_valid = np.isfinite(el_masked).any(axis=1)
    kk = np.where(any_valid, np.nanargmax(np.where(np.isfinite(el_masked), el_masked, -1e9), axis=1), -1)

    out_el, status, crit, reach = [], [], [], []
    for i in range(bins):
        complete = first_gap[i] == d.size
        reach.append(float(d[first_gap[i] - 1]) if first_gap[i] > 0 else 0.0)
        if not any_valid[i]:
            out_el.append(None); status.append('truncated'); crit.append(None); continue
        j = kk[i]
        out_el.append(round(float(el_masked[i, j]), 5))
        status.append('complete' if complete else 'truncated')
        crit.append({'distance_m': float(d[j]), 'lat_deg': round(float(la2[i, j]), 7), 'lon_deg': round(float(lo2[i, j]), 7),
                     'grid_x_m': round(float(gx[i, j]), 2), 'grid_y_m': round(float(gy[i, j]), 2),
                     'height_m': round(float(h[i, j]), 3), 'dem': layers[int(src[i, j])].dem.name})

    ref = beyond_reference or layers[-1]
    hmax = float(np.nanmax(ref.dem.Z))
    beyond = None
    if np.isfinite(hmax):
        dd = np.linspace(max_range_m, 3 * max_range_m, 400)
        la_b, lo_b = sphere.destination(lat, lon, 0.0, dd)
        Pb = (sphere.R + hmax) * sphere.unit(la_b, lo_b)
        beyond = float(np.max(sphere.elevation_angle_deg(P_obs, up, Pb)))
    range_limited = [bool(beyond is not None and e is not None and e < beyond) for e in out_el]
    return {
        'bins': bins, 'azimuth_deg': az.tolist(), 'elevation_deg': out_el, 'status': status, 'critical': crit,
        'valid_reach_m': reach, 'n_truncated': int(sum(s == 'truncated' for s in status)),
        'max_range_m': float(max_range_m), 'near_cut_m': float(near_cut), 'step_near_m': float(step_near),
        'step_far_m': None if step_far_m is None else float(step_far_m), 'n_samples_per_bin': int(d.size),
        'beyond_range_max_possible_elev_deg': beyond, 'range_limited': range_limited,
        'n_range_limited': int(sum(range_limited)), 'beyond_range_reference_height_m': hmax,
        'flat_baseline': {'elevation_deg': 0.0, 'smooth_sphere_dip_deg': round(sphere.smooth_dip_deg(obs_height_m + mast_m), 5),
                          'note': 'Flat-horizon control: mathematical horizon (0 deg) for every bin; smooth_sphere_dip_deg is '
                                  'the bare-sphere geometric dip at this observer height.'},
        'layers': [{'name': L.dem.name, 'role': L.role, 'step_m': L.dem.step} for L in layers],
        'sphere_radius_m': sphere.R,
        'method': 'great-circle rays on the world sphere, each DEM layer sampled bilinearly in its own grid (priority fill), '
                  'body-fixed 3D elevation vs the sphere normal, single ray per bin centre, no refraction',
    }


def compute_skyline(world, lat, lon, obs_height_m, mast_m, layers=None, near=None, far=None, **kw):
    """Moon + (near, far) in the LDEM south-polar grid -> the existing science.skyline.compute_skyline; otherwise the
    layered generic implementation with the world's sphere."""
    if world.name == 'moon' and layers is None:
        from ..skyline import compute_skyline as moon_skyline
        return moon_skyline(lat, lon, obs_height_m, mast_m, near=near, far=far, **kw)
    if layers is None:
        raise ValueError(f'{world.name}: pass DEM layers with their own projections')
    return layered_skyline(world.sphere, lat, lon, obs_height_m, mast_m, layers, **kw)
