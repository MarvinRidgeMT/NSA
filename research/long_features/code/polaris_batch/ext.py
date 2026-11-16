"""Extensions for the long-feature pilots (15 Nov 2026): horizon with controlling-point geometry,
analytic Jacobian dH/dh, a finite-difference check, and helpers. Builds on core.py (batch v2)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import core

RUNNER_UP_GAP_M = 25.0   # a runner-up ridge must be at least this far (along the ray) from the controlling point


@dataclass
class HorizonX:
    az: np.ndarray
    elev: np.ndarray          # controlling elevation angle, deg
    dist: np.ndarray          # distance of controlling sample, m
    x: np.ndarray             # stereographic x of controlling sample (near-DEM CRS), m
    y: np.ndarray
    hgt: np.ndarray           # terrain height of controlling sample, m
    jac: np.ndarray           # dE/dh at the controlling sample, deg per m (analytic)
    elev2: np.ndarray         # runner-up elevation angle (>= RUNNER_UP_GAP_M from the controlling sample), deg
    dist2: np.ndarray
    x2: np.ndarray
    y2: np.ndarray
    jac2: np.ndarray
    in_near: np.ndarray       # controlling sample lies on the 5 m tile (clones can change it)
    in_near2: np.ndarray
    h0: float
    z0: float
    # top-K distinct ridge candidates per bin (>= RUNNER_UP_GAP_M apart along the ray), shape (n_az, K)
    cand_elev: np.ndarray = None
    cand_dist: np.ndarray = None
    cand_x: np.ndarray = None
    cand_y: np.ndarray = None
    cand_h: np.ndarray = None
    cand_near: np.ndarray = None

    def base(self) -> core.Horizon:
        return core.Horizon(self.az, self.elev, self.dist, np.ones_like(self.az, bool), self.h0)


def dE_dh(h0, h, d):
    """Analytic derivative of core.elevation_angle_deg with respect to the target height h (deg/m)."""
    th = np.asarray(d) / core.R_MOON
    r0, r = core.R_MOON + h0, core.R_MOON + np.asarray(h)
    a = r * np.cos(th) - r0
    b = r * np.sin(th)
    # E = atan2(a, b); dE/dr = (b*cos th - a*sin th)/(a^2+b^2)
    return np.degrees((b * np.cos(th) - a * np.sin(th)) / (a * a + b * b))


def compute_horizon_x(lon0, lat0, near, far, mast_m=1.0, n_az=720, near_max_m=25000.0, far_max_m=280000.0,
                      near_step=1.0, az_chunk=40, z_override=None, k_cand=16) -> HorizonX:
    """Same ray march as core.compute_horizon (same samples, same argmax) plus controlling-point geometry."""
    far_step = far.res
    z0 = float(near.sample_lonlat(np.array([lon0]), np.array([lat0]))[0]) if z_override is None else z_override
    h0 = z0 + mast_m
    az = (np.arange(n_az) + 0.5) * 360.0 / n_az
    d = np.concatenate([np.arange(near_step, near_max_m, near_step), np.arange(near_max_m, far_max_m + 1, far_step)])
    out = {k: np.full(n_az, np.nan) for k in ("elev", "dist", "x", "y", "hgt", "jac", "elev2", "dist2", "x2", "y2", "jac2")}
    in_near = np.zeros(n_az, bool); in_near2 = np.zeros(n_az, bool)
    C = {k: np.full((n_az, k_cand), np.nan) for k in ("cand_elev", "cand_dist", "cand_x", "cand_y", "cand_h")}
    C["cand_near"] = np.zeros((n_az, k_cand), bool)
    for s in range(0, n_az, az_chunk):
        sl = slice(s, min(s + az_chunk, n_az))
        lon, lat = core.destination(lon0, lat0, az[sl], d)
        x, y = near.to_grid.transform(lon, lat)
        hn = near.sample_xy(x, y)
        hf = far.sample_xy(x, y)
        isn = np.isfinite(hn)
        h = np.where(isn, hn, hf)
        e = core.elevation_angle_deg(h0, h, d[None, :])
        em = np.where(np.isfinite(e), e, -np.inf)
        rows = np.arange(em.shape[0])
        k = np.argmax(em, axis=1)
        dk = d[k]
        far_mask = np.abs(d[None, :] - dk[:, None]) >= RUNNER_UP_GAP_M
        em2 = np.where(far_mask, em, -np.inf)
        k2 = np.argmax(em2, axis=1)
        for tag, kk in (("", k), ("2", k2)):
            out["elev" + tag][sl] = em[rows, kk]
            out["dist" + tag][sl] = d[kk]
            out["x" + tag][sl] = x[rows, kk]
            out["y" + tag][sl] = y[rows, kk]
            out["jac" + tag][sl] = dE_dh(h0, h[rows, kk], d[kk])
        out["hgt"][sl] = h[rows, k]
        in_near[sl] = isn[rows, k]; in_near2[sl] = isn[rows, k2]
        emc = em.copy()
        for j in range(k_cand):
            kj = np.argmax(emc, axis=1)
            C["cand_elev"][sl, j] = emc[rows, kj]; C["cand_dist"][sl, j] = d[kj]
            C["cand_x"][sl, j] = x[rows, kj]; C["cand_y"][sl, j] = y[rows, kj]
            C["cand_h"][sl, j] = h[rows, kj]; C["cand_near"][sl, j] = isn[rows, kj]
            gap = np.maximum(3.0, 0.05 * d[kj])[:, None]
            emc[np.abs(d[None, :] - d[kj][:, None]) < gap] = -np.inf
    return HorizonX(az=az, in_near=in_near, in_near2=in_near2, h0=h0, z0=z0, **out, **C)


def sample_sigma(dem_err: core.Dem, x, y):
    """Bilinear sample of an error raster (e.g. PGDA 78 toterr) at controlling points."""
    return dem_err.sample_xy(np.asarray(x), np.asarray(y))


def nearest_bin(az_deg, n_az=720):
    return (np.floor(np.mod(np.asarray(az_deg), 360.0) / (360.0 / n_az))).astype(int) % n_az


def sun_state(hz: core.Horizon, sun):
    hs = hz.at(sun["az"])
    return sun["el"] - hs   # signed margin, deg (>0 visible)


def norm_sf(z):
    """Upper-tail standard normal probability."""
    from scipy.special import erfc
    return 0.5 * erfc(np.asarray(z) / math.sqrt(2.0))
