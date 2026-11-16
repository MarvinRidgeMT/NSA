"""Uncertainty members for any site (axis 5, X).

* T, PGDA 78 clones: published terrain realizations (Barker et al. 2021), used where the site's tile has clones cached.
* T, assumed error model: near-field DEM + a smooth Gaussian height-error field (σ, correlation length from
  products.ERROR_MODELS), deterministic seed per (site hash, member). Label: exactly "assumed error model".
  Only the near field (≤ 25 km) is perturbed; a 1 m error at 25 km moves an elevation angle by ≤ 0.0023°.
* M, product disagreement: the same solve with each other covering product as the near field.

`batched_skyline` is compute_skyline's KEEP fields for several near DEMs that share one ray geometry: the same operations
in the same order as science/skyline.compute_skyline (as science/cube/compute.multi_skyline, but with the step, near cut
and range as arguments). test_anysite checks it is bit-identical to compute_skyline.
"""
from __future__ import annotations

import numpy as np

from .. import dem as demmod
from .. import frames
from ..skyline import _distances

LABEL_ASSUMED = 'assumed error model'


def batched_skyline(lat, lon, near_by_t, far, mast_m, step_near, near_cut, step_far, max_range, bins=720, ground=None):
    """{t_id: skyline dict (bins, elevation_deg, status, n_truncated, max_range_m, near_cut_m, step_near_m, step_far_m,
    ground_m)}. ground[t_id] overrides the observer ground height (default: that member's near DEM at the site)."""
    d = _distances(step_near, near_cut, step_far, max_range)
    az = np.arange(bins) * 360.0 / bins
    A, D = np.meshgrid(az, d, indexing='ij')
    la2, lo2 = frames.destination(lat, lon, A, D)
    x, y = frames.stereo_forward(la2, lo2)
    hf = far.sample(x, y) if far is not None else np.full(A.shape, np.nan)
    mf_ok = np.isfinite(hf)
    U = frames.unit(la2, lo2)
    up = frames.up_vector(lat, lon)
    x0, y0 = frames.stereo_forward(lat, lon)
    out = {}
    for t_id, nd in near_by_t.items():
        h = np.full(A.shape, np.nan)
        hn = nd.sample(x, y); m = np.isfinite(hn); h[m] = hn[m]
        m = ~np.isfinite(h) & mf_ok; h[m] = hf[m]
        P = (frames.R_MOON_M + np.nan_to_num(h))[..., None] * U
        valid = np.isfinite(h)
        first_gap = np.where(valid.all(axis=1), d.size, np.argmin(valid, axis=1))
        g = float(nd.sample(x0, y0)) if ground is None or t_id not in ground else float(ground[t_id])
        P_obs = frames.moon_fixed(lat, lon, g + mast_m)
        el = frames.elevation_angle_deg(P_obs, up, P)
        el = np.where(valid, el, np.nan)
        el_masked = np.where(np.arange(d.size)[None, :] < first_gap[:, None], el, np.nan)
        any_valid = np.isfinite(el_masked).any(axis=1)
        k = np.where(any_valid, np.nanargmax(np.where(np.isfinite(el_masked), el_masked, -1e9), axis=1), -1)
        out_el, status = [], []
        for i in range(bins):
            if not any_valid[i]:
                out_el.append(None); status.append('truncated'); continue
            out_el.append(round(float(el_masked[i, k[i]]), 5))
            status.append('complete' if first_gap[i] == d.size else 'truncated')
        out[t_id] = {'bins': bins, 'elevation_deg': out_el, 'status': status,
                     'n_truncated': int(sum(s_ == 'truncated' for s_ in status)), 'max_range_m': float(max_range),
                     'near_cut_m': float(near_cut), 'step_near_m': float(step_near),
                     'step_far_m': None if step_far is None else float(step_far), 'ground_m': g}
    return out


def error_field(shape, step_m, sigma_m, corr_m, seed):
    """Smooth zero-mean Gaussian field with empirical std = sigma_m and correlation length ~corr_m (Gaussian kernel of
    std corr_m/2 applied to white noise on a grid of spacing min(step, corr/4), bilinearly brought to the DEM grid)."""
    from scipy.ndimage import gaussian_filter, zoom
    rng = np.random.default_rng(seed)
    coarse = max(step_m, corr_m / 4.0)
    f = max(1, int(round(coarse / step_m)))
    cs = (int(np.ceil(shape[0] / f)) + 2, int(np.ceil(shape[1] / f)) + 2)
    w = gaussian_filter(rng.standard_normal(cs), sigma=(corr_m / 2.0) / (f * step_m), mode='wrap')
    w = (w - w.mean()) / w.std() * sigma_m
    if f > 1:
        w = zoom(w, f, order=1)
    return w[:shape[0], :shape[1]]


def assumed_member(dem, product, k, site_seed, model):
    """DEM + error field. dem may be an ArrayDEM or SPView (perturbs the inner grid)."""
    if hasattr(dem, 'perturbed'):                 # EqDEM (global simple-cylindrical window)
        f = error_field(dem.Z.shape, dem.step, model['sigma_m'], model['corr_m'], (site_seed, k))
        return dem.perturbed(f, f'{dem.name} + {LABEL_ASSUMED} #{k:02d}',
                             {**dem.meta, 'member': f'assumed{k:02d}', 'label': LABEL_ASSUMED,
                              'error_model': {**model, 'product': product,
                                              'note': 'field on the lat/lon grid; correlation length along latitude'}})
    inner = getattr(dem, 'inner', dem)
    Z = inner.Z + error_field(inner.Z.shape, inner.step, model['sigma_m'], model['corr_m'], (site_seed, k))
    nd = demmod.ArrayDEM(Z, inner.x_left, inner.y_top, inner.step, f'{inner.name} + {LABEL_ASSUMED} #{k:02d}',
                         {**inner.meta, 'member': f'assumed{k:02d}', 'label': LABEL_ASSUMED,
                          'error_model': {**model, 'product': product}})
    if hasattr(dem, 'inner'):
        from .stack import SPView
        return SPView(nd, dem.entry)
    return nd
