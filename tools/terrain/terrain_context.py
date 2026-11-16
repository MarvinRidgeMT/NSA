"""Display-only terrain context: regional DEM placement and horizon maps for shading. numpy only.

Everything here is VISUAL. A horizon map stores, for each terrain point and each of K grid azimuths, the elevation
angle of the highest terrain seen in that direction over the DEMs that are *displayed* (5 m local crop, then the
80 m regional crop). The renderer compares it with the Sun's elevation at the current JPL sample to shade terrain
in shadow. It is not the solver: finite crops, ground points (no mast), coarse azimuths, 8-bit angles.
Nothing here is read by the horizon solver, and the outputs carry numericalAuthority = false.

Frame: grid axes of the bundles (x toward 90 E, y toward 0 E, metres), relative to the dataset's site point.
DEM arrays are rows south-to-north (row j -> y = originY + j*spacing), as in the bundles.
Azimuth index k -> grid angle theta = 2*pi*k/K measured from +y toward +x: direction (sin theta, cos theta).
"""
from __future__ import annotations
import math
import numpy as np

MOON_RADIUS_M = 1737400.0
ENC_MIN_DEG, ENC_STEP_DEG = -3.0, 0.05   # uint8: q = round((deg + 3) / 0.05), clipped to 0..255  ->  -3.00 .. +9.75 deg


def encode_deg(deg: np.ndarray) -> np.ndarray:
    return np.clip(np.rint((deg - ENC_MIN_DEG) / ENC_STEP_DEG), 0, 255).astype(np.uint8)


def decode_deg(q: np.ndarray) -> np.ndarray:
    return q.astype(np.float64) * ENC_STEP_DEG + ENC_MIN_DEG


class Grid:
    """Square DEM grid in site-relative grid metres; values[j, i], rows south-to-north."""

    def __init__(self, values, n: int, spacing: float, origin_x: float, origin_y: float):
        self.z = np.asarray(values, dtype=np.float64).reshape(n, n)
        self.n, self.s, self.x0, self.y0 = int(n), float(spacing), float(origin_x), float(origin_y)

    def sample_nearest(self, x: np.ndarray, y: np.ndarray):
        """Nearest-cell heights and an inside mask (outside or non-finite -> mask False)."""
        i = np.rint((x - self.x0) / self.s).astype(np.int64)
        j = np.rint((y - self.y0) / self.s).astype(np.int64)
        ok = (i >= 0) & (j >= 0) & (i < self.n) & (j < self.n)
        z = np.full(x.shape, np.nan)
        z[ok] = self.z[j[ok], i[ok]]
        ok &= np.isfinite(z)
        return z, ok

    def subsample(self, m: int) -> "Grid":
        """Every k-th node so the grid has m nodes per side (requires (n-1) % (m-1) == 0)."""
        if (self.n - 1) % (m - 1):
            raise ValueError("subsample size does not divide the grid")
        k = (self.n - 1) // (m - 1)
        return Grid(self.z[::k, ::k], m, self.s * k, self.x0, self.y0)


def rebase(regional: Grid, regional_site_xy, dataset_site_xy) -> Grid:
    """Regional grid expressed relative to another dataset's site point (pure translation in projected metres)."""
    dx = regional_site_xy[0] - dataset_site_xy[0]
    dy = regional_site_xy[1] - dataset_site_xy[1]
    return Grid(regional.z, regional.n, regional.s, regional.x0 + dx, regional.y0 + dy)


def horizon_map(points: Grid, k_az: int, near: Grid | None, far: Grid | None, near_step: float, near_reach: float,
                far_step: float, far_reach: float, lift_m: float = 0.0) -> np.ndarray:
    """Horizon elevation (degrees) for every node of `points`, shape (k_az, n, n).

    March from each node along each azimuth: `near_step` out to `near_reach` sampling `near` (falling back to `far`
    where `near` has no data), then `far_step` out to `far_reach` sampling `far`. Planet curvature lowers distant
    terrain by d^2 / (2R). Directions with no terrain sample at all keep the flat-sphere horizon (0 deg at ground).
    `lift_m` raises every sample point above its own surface: a display shadow bias so that sub-`lift_m` roughness in
    the gridded DEM does not speckle the shading (a ground point's horizon is otherwise set by its nearest neighbours).
    """
    n = points.n
    xs = points.x0 + np.arange(n) * points.s
    X, Y = np.meshgrid(xs, points.y0 + np.arange(n) * points.s)
    Z0 = points.z + lift_m
    dists = []
    if near is not None and near_reach > 0:
        dists += list(np.arange(near_step, near_reach + 1e-9, near_step))
    if far is not None and far_reach > 0:
        start = (dists[-1] if dists else 0.0) + far_step
        dists += list(np.arange(start, far_reach + 1e-9, far_step))
    out = np.empty((k_az, n, n), dtype=np.float64)
    for k in range(k_az):
        th = 2 * math.pi * k / k_az
        sx, cy = math.sin(th), math.cos(th)
        best = np.zeros((n, n))   # tan(elevation); 0 = flat horizon at ground level
        seen = np.zeros((n, n), dtype=bool)
        for d in dists:
            px, py = X + d * sx, Y + d * cy
            z = np.full((n, n), np.nan)
            ok = np.zeros((n, n), dtype=bool)
            if near is not None and d <= near_reach:
                z, ok = near.sample_nearest(px, py)
            if far is not None:
                miss = ~ok
                if miss.any():
                    zf, okf = far.sample_nearest(px[miss], py[miss])
                    z[miss] = zf
                    ok[miss] = okf
            t = (z - Z0 - d * d / (2 * MOON_RADIUS_M)) / d
            first = ok & ~seen
            best = np.where(first, t, np.where(ok, np.maximum(best, t), best))
            seen |= ok
        out[k] = np.degrees(np.arctan(best))
    return out


def sun_visibility(horizon_deg: float, sun_el_deg: float, sun_radius_deg: float = 0.266) -> float:
    """Fraction-like visibility used by the shader: smoothstep across the solar disc (display model)."""
    t = min(1.0, max(0.0, (sun_el_deg - (horizon_deg - sun_radius_deg)) / (2 * sun_radius_deg)))
    return t * t * (3 - 2 * t)
