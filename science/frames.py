"""Lunar reference frames for POLARIS X science.

Conventions (see docs/SCIENCE_RESULTS_CONTRACT.md):
  * Body: Moon as a sphere, R = 1 737 400 m (LOLA LDEM reference radius and the
    radius in the LDEM_80S_80MPP_ADJ.TIF CRS). Heights h are metres above it.
  * Moon-fixed Cartesian (mean-Earth/polar-axis body frame as used by LOLA and
    by JPL Horizons coord@301): P = (R+h) * [cos lat cos lon, cos lat sin lon, sin lat],
    planetocentric latitude, east-positive longitude.
  * Local ENU at (lat, lon): e = d/dlon, n = d/dlat, u = radial.
  * Azimuth: degrees clockwise from LOCAL north (0 N, 90 E) -- the JPL Horizons
    convention for surface observers.
  * Grid: south-polar stereographic, +proj=stere +lat_0=-90 +lon_0=0 +k=1 +R=1737400,
    x = rho sin(lon), y = rho cos(lon), rho = 2R tan(pi/4 + lat/2).
    At longitude L the local unit vectors expressed in grid (x, y) are
        north = (sin L, cos L),  east = (cos L, -sin L),
    so grid_azimuth = local_azimuth + L.
"""
from __future__ import annotations

import functools
import math
from pathlib import Path

import numpy as np

R_MOON_M = 1_737_400.0
LDEM_URL = 'https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF'
LDEM_VSI = '/vsicurl/' + LDEM_URL
_CRS_CACHE = Path(__file__).resolve().parents[1] / 'data' / 'raw' / 'LDEM_80S_80MPP_ADJ.crs.wkt'


# ---------------------------------------------------------------- grid <-> ENU
def local_north_in_grid(lon_deg):
    L = math.radians(lon_deg)
    return (math.sin(L), math.cos(L))


def local_east_in_grid(lon_deg):
    L = math.radians(lon_deg)
    return (math.cos(L), -math.sin(L))


def local_az_to_grid_az(az_deg, lon_deg):
    return (az_deg + lon_deg) % 360.0


def grid_az_to_local_az(grid_az_deg, lon_deg):
    return (grid_az_deg - lon_deg) % 360.0


def enu_to_grid(east, north, lon_deg):
    """Rotate a horizontal ENU vector to grid (dx, dy). Valid near the site only
    (stereographic scale k != 1 away from the pole; direction is exact at the point)."""
    ex, ey = local_east_in_grid(lon_deg)
    nx, ny = local_north_in_grid(lon_deg)
    return east * ex + north * nx, east * ey + north * ny


def grid_to_enu(dx, dy, lon_deg):
    ex, ey = local_east_in_grid(lon_deg)
    nx, ny = local_north_in_grid(lon_deg)
    return dx * ex + dy * ey, dx * nx + dy * ny


# ---------------------------------------------------------------- projection
def stereo_forward(lat, lon, crs=None):
    """lat/lon (deg) -> grid x, y (m). crs=None uses the closed form; otherwise pyproj."""
    if crs is None:
        lat = np.asarray(lat, dtype=float); lon = np.asarray(lon, dtype=float)
        rho = 2 * R_MOON_M * np.tan(np.pi / 4 + np.radians(lat) / 2)
        x = rho * np.sin(np.radians(lon)); y = rho * np.cos(np.radians(lon))
        return (float(x), float(y)) if x.ndim == 0 else (x, y)
    t = _transformer(crs.to_wkt(), forward=True)
    return t.transform(lon, lat)


def stereo_inverse(x, y, crs=None):
    if crs is None:
        x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
        rho = np.hypot(x, y)
        lat = np.degrees(2 * np.arctan(rho / (2 * R_MOON_M)) - np.pi / 2)
        lon = np.degrees(np.arctan2(x, y))
        return (float(lat), float(lon)) if lat.ndim == 0 else (lat, lon)
    t = _transformer(crs.to_wkt(), forward=False)
    lon, lat = t.transform(x, y)
    return lat, lon


@functools.lru_cache(maxsize=8)
def _transformer(wkt, forward):
    from pyproj import CRS, Transformer
    crs = CRS.from_wkt(wkt)
    geo = crs.geodetic_crs
    return (Transformer.from_crs(geo, crs, always_xy=True) if forward
            else Transformer.from_crs(crs, geo, always_xy=True))


def ldem_crs(path=LDEM_VSI, cache=_CRS_CACHE):
    """CRS read from the LDEM COG header itself (cached as WKT under data/raw/)."""
    from pyproj import CRS
    if cache and Path(cache).exists():
        return CRS.from_wkt(Path(cache).read_text())
    import rasterio
    with rasterio.open(path) as ds:
        wkt = ds.crs.to_wkt()
    if cache:
        Path(cache).parent.mkdir(parents=True, exist_ok=True)
        Path(cache).write_text(wkt)
    return CRS.from_wkt(wkt)


# ---------------------------------------------------------------- 3D model
def unit(lat, lon):
    la = np.radians(lat); lo = np.radians(lon)
    return np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], axis=-1)


def moon_fixed(lat, lon, h):
    return (R_MOON_M + np.asarray(h, dtype=float))[..., None] * unit(lat, lon) \
        if np.ndim(h) else (R_MOON_M + float(h)) * unit(lat, lon)


def up_vector(lat, lon):
    return unit(lat, lon)


def enu_basis(lat, lon):
    la = math.radians(lat); lo = math.radians(lon)
    e = np.array([-math.sin(lo), math.cos(lo), 0.0])
    n = np.array([-math.sin(la) * math.cos(lo), -math.sin(la) * math.sin(lo), math.cos(la)])
    u = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
    return e, n, u


def elevation_angle_deg(P_obs, up, P):
    """Elevation of P (N,3 or 3) above the observer's local horizontal plane."""
    v = np.asarray(P) - np.asarray(P_obs)
    r = np.linalg.norm(v, axis=-1)
    return np.degrees(np.arcsin(np.clip((v @ np.asarray(up)) / r, -1.0, 1.0)))


def destination(lat, lon, az_deg, s_m):
    """Great-circle destination on the R_MOON_M sphere (vectorised in s_m / az)."""
    la = math.radians(lat); lo = math.radians(lon)
    a = np.radians(az_deg); d = np.asarray(s_m, dtype=float) / R_MOON_M
    sla = np.sin(la) * np.cos(d) + np.cos(la) * np.sin(d) * np.cos(a)
    la2 = np.arcsin(np.clip(sla, -1, 1))
    lo2 = lo + np.arctan2(np.sin(a) * np.sin(d) * np.cos(la), np.cos(d) - np.sin(la) * sla)
    lat2 = np.degrees(la2); lon2 = (np.degrees(lo2) + 180.0) % 360.0 - 180.0
    if np.ndim(lat2) == 0:
        return float(lat2), float(lon2)
    return lat2, lon2
