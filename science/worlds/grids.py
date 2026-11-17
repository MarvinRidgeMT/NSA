"""Terrain grids for non-Moon worlds, each sampled in its OWN projection (worlds/skyline.layered_skyline calls
`layer.forward(lat, lon)` and then `dem.sample(x, y)`), heights in metres above the world's reference sphere.

  * `LonLatGrid`: pixel-registered simple-cylindrical (lat/lon) grid, row 0 at `lat_top`, column 0 at `lon_left`, `ppd`
    pixels per degree; a full 360 deg ring wraps across the 0/360 seam. forward(lat, lon) = (lon, lat). Bilinear on pixel
    centres; NaN outside the grid or next to no-data (never extrapolated).
  * Polar stereographic and local equirectangular (metre) grids are `science.dem.ArrayDEM` + a forward function
    (geometry.PolarStereo.forward or `eqc_forward`).

Readers never fill or resample: a window is a sub-array of the product with its exact geolocation.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field

import numpy as np

from .. import dem as demmod


@dataclass
class LonLatGrid:
    Z: np.ndarray
    lat_top: float
    lon_left: float
    ppd: float
    full_ring: bool
    radius_m: float                 # sphere used for the nominal metre step (provenance / default ray step)
    name: str = 'lon/lat grid'
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        self.Z = np.asarray(self.Z, dtype=np.float64)

    @property
    def step(self):
        return self.radius_m * math.radians(1.0 / self.ppd)

    @property
    def bounds(self):
        h, w = self.Z.shape
        return (self.lon_left, self.lat_top - h / self.ppd, self.lon_left + w / self.ppd, self.lat_top)

    def sample(self, lon, lat):
        lon = np.asarray(lon, float); lat = np.asarray(lat, float)
        h, w = self.Z.shape
        r = (self.lat_top - lat) * self.ppd - 0.5
        c = ((lon - self.lon_left) % 360.0) * self.ppd - 0.5
        if self.full_ring:
            ok = (r >= 0) & (r <= h - 1)
            c = c % w
            c0 = np.floor(c).astype(int) % w; c1 = (c0 + 1) % w; a = c - np.floor(c)
        else:
            ok = (r >= 0) & (r <= h - 1) & (c >= 0) & (c <= w - 1)
            c0 = np.clip(np.floor(c).astype(int), 0, max(w - 2, 0)); c1 = c0 + 1; a = c - c0
        r0 = np.clip(np.floor(r).astype(int), 0, max(h - 2, 0)); r1 = r0 + 1; b = r - r0
        Z = self.Z
        z = (1 - a) * (1 - b) * Z[r0, c0] + a * (1 - b) * Z[r0, c1] + (1 - a) * b * Z[r1, c0] + a * b * Z[r1, c1]
        return np.where(ok, z, np.nan)

    @staticmethod
    def forward(lat, lon):
        return lon, lat

    def digest(self):
        hh = hashlib.sha256()
        hh.update(json.dumps([self.lat_top, self.lon_left, self.ppd, self.full_ring, list(self.Z.shape)]).encode())
        hh.update(np.ascontiguousarray(self.Z, dtype=np.float32).tobytes())
        return hh.hexdigest()


def eqc_forward(R, lon0_deg, lat_ts_deg):
    """Equirectangular (PROJ eqc): x = R (lon - lon0) cos(lat_ts), y = R lat (radians); lon - lon0 wrapped to +-180."""
    k = math.cos(math.radians(lat_ts_deg))

    def f(lat, lon):
        dl = (np.asarray(lon, float) - lon0_deg + 180.0) % 360.0 - 180.0
        return R * np.radians(dl) * k, R * np.radians(np.asarray(lat, float))
    return f


# --------------------------------------------------------------------------------------------------- PDS3 readers
def parse_label(text):
    out = {}
    for k in ('LINES', 'LINE_SAMPLES', 'SAMPLE_BITS', 'SCALING_FACTOR', 'OFFSET', 'MISSING_CONSTANT', 'MAP_RESOLUTION',
              'MAXIMUM_LATITUDE', 'MINIMUM_LATITUDE', 'WESTERNMOST_LONGITUDE', 'EASTERNMOST_LONGITUDE', 'A_AXIS_RADIUS',
              'LINE_PROJECTION_OFFSET', 'SAMPLE_PROJECTION_OFFSET', 'CENTER_LONGITUDE', 'CENTER_LATITUDE'):
        m = re.search(rf'^\s*{k}\s*=\s*([-+0-9.Ee]+)', text, re.M)
        if m:
            out[k] = float(m.group(1))
    for k in ('SAMPLE_TYPE', 'MAP_PROJECTION_TYPE', 'POSITIVE_LONGITUDE_DIRECTION', 'COORDINATE_SYSTEM_NAME', 'UNIT', 'NAME',
              'PRODUCT_ID', 'DATA_SET_ID'):
        m = re.search(rf'^\s*{k}\s*=\s*"?([^"\n]+?)"?\s*$', text, re.M)
        if m:
            out[k] = m.group(1).strip()
    return out


def read_simple_cyl(img, lbl, radius_m, lat_range=None, lon_center=None, lon_half_deg=None, name=None,
                    height_offset_m=None, raw=False):
    """PDS3 SIMPLE CYLINDRICAL image (MOLA MEGDR) -> LonLatGrid. Value = DN * SCALING_FACTOR + OFFSET (m); heights =
    value - radius_m unless raw (counts). height_offset_m overrides the label OFFSET (megt: topography has OFFSET 0).
    Sub-window: rows for lat_range = (lat_lo, lat_hi); columns within lon_half_deg of lon_center (None = all columns)."""
    lab = parse_label(open(lbl, encoding='latin-1').read())
    if lab.get('MAP_PROJECTION_TYPE') != 'SIMPLE CYLINDRICAL':
        raise ValueError(f'{lbl}: expected SIMPLE CYLINDRICAL, got {lab.get("MAP_PROJECTION_TYPE")}')
    if lab.get('POSITIVE_LONGITUDE_DIRECTION') != 'EAST':
        raise ValueError(f'{lbl}: expected east-positive longitudes')
    st = lab.get('SAMPLE_TYPE', '')
    dt = {('MSB_INTEGER', 16): '>i2', ('LSB_INTEGER', 16): '<i2', ('PC_REAL', 32): '<f4', ('IEEE_REAL', 32): '>f4'}[
        (st, int(lab['SAMPLE_BITS']))]
    nl, ns, ppd = int(lab['LINES']), int(lab['LINE_SAMPLES']), lab['MAP_RESOLUTION']
    lat_top, lon_left = lab['MAXIMUM_LATITUDE'], lab['WESTERNMOST_LONGITUDE'] % 360.0
    # cross-check the label's projection offsets against the edge convention used here (row 0 top edge = lat_top)
    lpo = lab.get('LINE_PROJECTION_OFFSET')
    if lpo is not None and min(abs(lpo - lat_top * ppd - 0.5), abs(lpo - lat_top * ppd + 0.5)) > 1e-6:
        raise ValueError(f'{lbl}: LINE_PROJECTION_OFFSET {lpo} inconsistent with MAXIMUM_LATITUDE {lat_top} x {ppd}')
    full = abs(ns / ppd - 360.0) < 1e-9
    a = np.memmap(img, dtype=dt, mode='r', shape=(nl, ns))
    r0, r1 = 0, nl
    if lat_range is not None:
        lo, hi = lat_range
        r0 = max(0, int(math.floor((lat_top - hi) * ppd)) - 1); r1 = min(nl, int(math.ceil((lat_top - lo) * ppd)) + 1)
    if lon_center is None or lon_half_deg is None or (full and lon_half_deg >= 179.0):
        cols = np.arange(ns); c_left = 0; ring = full
    else:
        c_mid = ((lon_center - lon_left) % 360.0) * ppd
        c_left = int(math.floor(c_mid - lon_half_deg * ppd)) - 1
        n = int(math.ceil(2 * lon_half_deg * ppd)) + 3
        cols = np.arange(c_left, c_left + n)
        if full:
            cols = cols % ns
        else:
            cols = cols[(cols >= 0) & (cols < ns)]
            c_left = int(cols[0])
        ring = False
    dn = np.asarray(a[r0:r1][:, cols], dtype=np.float64)
    val = dn * lab.get('SCALING_FACTOR', 1.0) + (lab.get('OFFSET', 0.0) if height_offset_m is None else height_offset_m)
    if 'MISSING_CONSTANT' in lab:
        val[np.asarray(a[r0:r1][:, cols]) == lab['MISSING_CONSTANT']] = np.nan
    Z = val if raw else val - radius_m
    meta = {'path': str(img), 'label': {k: lab.get(k) for k in ('PRODUCT_ID', 'NAME', 'OFFSET', 'SCALING_FACTOR', 'UNIT',
                                                                 'MAP_RESOLUTION', 'A_AXIS_RADIUS', 'COORDINATE_SYSTEM_NAME')},
            'rows': [r0, r1], 'col_left': int(c_left), 'n_cols': int(len(cols)), 'height_reference_m': None if raw else radius_m,
            'value_rule': 'DN * SCALING_FACTOR + OFFSET (label), minus the reference sphere', 'raw': raw}
    lon_l = (lon_left + c_left / ppd) % 360.0
    return LonLatGrid(Z, lat_top - r0 / ppd, lon_l, ppd, ring, radius_m, name or lab.get('PRODUCT_ID', str(img)), meta)


def read_geotiff(path, name, radius_m, window_lonlat=None, scale=None, offset_m=0.0):
    """GeoTIFF in a polar-stereographic or equirectangular CRS -> (ArrayDEM | LonLatGrid, forward, crs dict).
    Value = raw * (scale or file scale or 1) + offset_m (m above the sphere stated by the caller's datum test)."""
    import rasterio
    from rasterio.windows import Window
    import warnings
    with rasterio.open(path) as ds, warnings.catch_warnings():
        warnings.simplefilter('ignore')
        crs = ds.crs.to_dict()
        t = ds.transform
        sc = scale if scale is not None else (ds.scales[0] if ds.scales and ds.scales[0] else 1.0)
        nod = ds.nodata
        if crs.get('proj') == 'eqc' and abs(crs.get('lat_ts', 0.0)) < 1e-12 and \
                abs(ds.width * t.a - 2 * math.pi * crs['R']) < 2 * t.a:
            # global eqc grid = lon/lat grid; read latitude band rows only
            ppd = 1.0 / math.degrees(t.a / crs['R'])
            lat_top = math.degrees(t.f / crs['R']); lon_left = (crs.get('lon_0', 0.0) + math.degrees(t.c / crs['R'])) % 360.0
            r0, r1 = 0, ds.height
            if window_lonlat is not None:
                lo, hi = window_lonlat[1], window_lonlat[3]
                r0 = max(0, int(math.floor((lat_top - hi) * ppd)) - 1); r1 = min(ds.height, int(math.ceil((lat_top - lo) * ppd)) + 1)
            v = ds.read(1, window=Window(0, r0, ds.width, r1 - r0)).astype(np.float64)
            if nod is not None:
                v[v == nod] = np.nan
            g = LonLatGrid(v * sc + offset_m, lat_top - r0 / ppd, lon_left, ppd, True, radius_m, name,
                           {'path': str(path), 'crs': crs, 'scale': sc, 'offset_m': offset_m, 'rows': [r0, r1]})
            return g, LonLatGrid.forward, crs
        if crs.get('proj') == 'eqc':
            fwd = eqc_forward(crs['R'], crs.get('lon_0', 0.0), crs.get('lat_ts', 0.0))
        elif crs.get('proj') == 'stere' and abs(abs(crs.get('lat_0', 0)) - 90) < 1e-9 and crs.get('lon_0', 0) == 0:
            from .geometry import PolarStereo
            fwd = PolarStereo(float(crs['R']), 'north' if crs['lat_0'] > 0 else 'south').forward
        else:
            raise ValueError(f'{path}: unsupported CRS {crs}')
        if abs(t.a + t.e) > 1e-9 or t.b != 0 or t.d != 0:
            raise ValueError(f'{path}: non-square or rotated pixels {t}')
        r0, r1, c0, c1 = 0, ds.height, 0, ds.width
        if window_lonlat is not None:
            lo_l, la_l, lo_h, la_h = window_lonlat
            LA, LO = np.meshgrid(np.linspace(la_l, la_h, 41), np.linspace(lo_l, lo_h, 41))
            X, Y = fwd(LA, LO)
            c0 = max(0, int(math.floor((np.min(X) - t.c) / t.a)) - 2); c1 = min(ds.width, int(math.ceil((np.max(X) - t.c) / t.a)) + 2)
            r0 = max(0, int(math.floor((t.f - np.max(Y)) / t.a)) - 2); r1 = min(ds.height, int(math.ceil((t.f - np.min(Y)) / t.a)) + 2)
        v = ds.read(1, window=Window(c0, r0, max(0, c1 - c0), max(0, r1 - r0))).astype(np.float64)
    if nod is not None and not (isinstance(nod, float) and math.isnan(nod)):
        v[v == nod] = np.nan
    v[~np.isfinite(v)] = np.nan
    v[np.abs(v) > 1e30] = np.nan
    d = demmod.ArrayDEM(v * sc + offset_m, t.c + c0 * t.a, t.f - r0 * t.a, t.a, name,
                        {'path': str(path), 'crs': crs, 'scale': sc, 'offset_m': offset_m, 'window_px': [r0, r1, c0, c1]})
    return d, fwd, crs
