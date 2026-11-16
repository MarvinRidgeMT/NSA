"""Synthetic rasters for the S3 pyramid tests (no NASA data)."""
from __future__ import annotations

import numpy as np

SP = '+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs'
NP = '+proj=stere +lat_0=90 +lat_ts=90 +lon_0=0 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs'
LONLAT = '+proj=longlat +R=1737400 +no_defs'
EQC = '+proj=eqc +lat_ts=0 +lon_0=0 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs'


def write_raster(path, Z, left, top, px, proj4, nodata=None, dtype='float32', scale=None, offset=None):
    import rasterio
    from rasterio.crs import CRS
    from rasterio.transform import from_origin
    Z = np.asarray(Z)
    prof = dict(driver='GTiff', width=Z.shape[1], height=Z.shape[0], count=1, dtype=dtype,
                crs=CRS.from_proj4(proj4), transform=from_origin(left, top, px, px))
    if nodata is not None:
        prof['nodata'] = nodata
    with rasterio.open(path, 'w', **prof) as ds:
        ds.write(Z.astype(dtype), 1)
        if scale is not None or offset is not None:
            ds.scales = (scale if scale is not None else 1.0,)
            ds.offsets = (offset if offset is not None else 0.0,)
    return str(path)


def plane(x, y, a=0.01, b=-0.02, c=100.0):
    return a * x + b * y + c


def grid_centres(left, top, px, ny, nx):
    xs = left + (np.arange(nx) + 0.5) * px
    ys = top - (np.arange(ny) + 0.5) * px
    return np.meshgrid(xs, ys)
