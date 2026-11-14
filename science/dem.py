"""DEM containers. Heights in metres above the R=1737400 m reference sphere.

Sampling never extrapolates: queries outside the raster, or touching a nodata
pixel, return NaN, which the skyline code turns into an explicit 'truncated'.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

import numpy as np


@dataclass
class ArrayDEM:
    Z: np.ndarray            # rows north->south in grid y (row 0 = top = max y)
    x_left: float            # grid x of left edge of column 0 (m)
    y_top: float             # grid y of top edge of row 0 (m)
    step: float              # pixel size (m), square pixels
    name: str = 'unnamed'
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        self.Z = np.asarray(self.Z, dtype=np.float64)

    @property
    def bounds(self):
        h, w = self.Z.shape
        return (self.x_left, self.y_top - h * self.step, self.x_left + w * self.step, self.y_top)

    def sample(self, x, y):
        """Bilinear sample on pixel centres; NaN outside footprint or near nodata."""
        x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
        h, w = self.Z.shape
        c = (x - self.x_left) / self.step - 0.5
        r = (self.y_top - y) / self.step - 0.5
        ok = (c >= 0) & (c <= w - 1) & (r >= 0) & (r <= h - 1)
        c0 = np.clip(np.floor(c).astype(int), 0, w - 2)
        r0 = np.clip(np.floor(r).astype(int), 0, h - 2)
        a = c - c0; b = r - r0
        Z = self.Z
        z = ((1 - a) * (1 - b) * Z[r0, c0] + a * (1 - b) * Z[r0, c0 + 1]
             + (1 - a) * b * Z[r0 + 1, c0] + a * b * Z[r0 + 1, c0 + 1])
        return np.where(ok, z, np.nan)  # NaN in any corner propagates

    def digest(self):
        h = hashlib.sha256()
        h.update(json.dumps([self.x_left, self.y_top, self.step, list(self.Z.shape)]).encode())
        h.update(np.ascontiguousarray(self.Z, dtype=np.float32).tobytes())
        return h.hexdigest()


def read_window(path, cx, cy, half_m, decimate=1, name=None):
    """Read a square grid window centred at (cx, cy) from a GeoTIFF/COG
    (local path or /vsicurl/...). decimate>1 uses GDAL average resampling
    on read (out_shape) and is recorded in meta."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.windows import from_bounds
    with rasterio.open(path) as ds:
        if abs(ds.transform.a) != abs(ds.transform.e) or ds.transform.b or ds.transform.d:
            raise ValueError('expected north-up square pixels')
        b = ds.bounds
        x0 = max(b.left, cx - half_m); x1 = min(b.right, cx + half_m)
        y0 = max(b.bottom, cy - half_m); y1 = min(b.top, cy + half_m)
        win = from_bounds(x0, y0, x1, y1, ds.transform).round_offsets().round_lengths()
        hh = int(win.height // decimate); ww = int(win.width // decimate)
        data = ds.read(1, window=win, out_shape=(hh, ww),
                       resampling=Resampling.average if decimate > 1 else Resampling.nearest,
                       masked=True).astype('float64')
        Z = data.filled(np.nan)
        if ds.nodata is not None and not np.isnan(ds.nodata):
            Z[Z == ds.nodata] = np.nan
        t = ds.window_transform(win)
        step = abs(t.a) * (win.width / ww)
        meta = {'source_path': str(path), 'window_col_off': int(win.col_off), 'window_row_off': int(win.row_off),
                'window_width_px': int(win.width), 'window_height_px': int(win.height), 'decimate': decimate,
                'native_step_m': abs(ds.transform.a), 'crs_wkt': ds.crs.to_wkt(), 'nodata': ds.nodata,
                'resampling': 'average' if decimate > 1 else 'none'}
    return ArrayDEM(Z, x_left=t.c, y_top=t.f, step=step, name=name or str(path), meta=meta)
