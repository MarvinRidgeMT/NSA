"""Mercury terrain readers -> science.dem.ArrayDEM in each product's own polar-stereographic grid, heights in metres above
the world datum sphere (MERCURY.radius_m = 2 439 400 m). Radius first, then height: never a silent datum shift.

  * MLA GDR (PDS3 .img + .lbl): DN int16 LSB; HEIGHT = DN * SCALING_FACTOR relative to OFFSET (m); projection sphere
    A_AXIS_RADIUS. Pixel centres (PDS3 DSMAP convention, 1-based sample/line):
        x = (sample - SAMPLE_PROJECTION_OFFSET - 1) * MAP_SCALE,   y = (LINE_PROJECTION_OFFSET - line + 1) * MAP_SCALE
    For hdem_75n_250m (5120 px, offset 2559.5, 250 m): x, y of the outer pixel edges = -/+ 640 000 m (a symmetric grid).
  * GeoTIFF / ISIS cube read by GDAL (PGDA 85 layers): geotransform + CRS radius from the file.
Never extrapolates; MISSING_CONSTANT / nodata -> NaN.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

import numpy as np

from ... import dem as demmod
from ..geometry import PolarStereo
from .world import MERCURY

ROOT_PRODUCTS = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'cache', 'v2', 'products')


def products_root(root: Optional[str] = None) -> str:
    base = root or os.environ.get('POLARIS_DATA') or os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'cache')
    return os.path.abspath(os.path.join(base, 'v2', 'products'))


def path(product_id: str, rel: str, root: Optional[str] = None) -> str:
    return os.path.join(products_root(root), product_id, rel)


def have(product_id: str, rel: str, root: Optional[str] = None) -> bool:
    return os.path.exists(path(product_id, rel, root))


@dataclass
class Grid:
    dem: demmod.ArrayDEM
    proj: PolarStereo
    meta: dict


def parse_pds3_label(text: str) -> dict:
    out = {}
    for k in ('LINES', 'LINE_SAMPLES', 'SAMPLE_BITS', 'SCALING_FACTOR', 'OFFSET', 'MISSING_CONSTANT', 'MAP_SCALE',
              'LINE_PROJECTION_OFFSET', 'SAMPLE_PROJECTION_OFFSET', 'A_AXIS_RADIUS', 'C_AXIS_RADIUS', 'CENTER_LATITUDE',
              'CENTER_LONGITUDE', 'MAXIMUM_LATITUDE', 'MINIMUM_LATITUDE', 'MAP_RESOLUTION'):
        m = re.search(rf'^\s*{k}\s*=\s*([-+0-9.Ee]+)', text, re.M)
        if m:
            out[k] = float(m.group(1))
    for k in ('SAMPLE_TYPE', 'MAP_PROJECTION_TYPE', 'POSITIVE_LONGITUDE_DIRECTION', 'KEYWORD_LATITUDE_TYPE', 'UNIT',
              'PRODUCT_ID', 'DATA_SET_ID', 'PRODUCT_CREATION_TIME'):
        m = re.search(rf'^\s*{k}\s*=\s*"?([^"\n]+?)"?\s*$', text, re.M)
        if m:
            out[k] = m.group(1).strip()
    return out


def read_mla_polar(img_path: str, lbl_path: str, name: Optional[str] = None, window=None) -> Grid:
    """MLA polar GDR -> Grid. `window` = (x_min, x_max, y_min, y_max) in grid m to read a sub-window (memory)."""
    lab = parse_pds3_label(open(lbl_path, encoding='latin-1').read())
    if lab.get('MAP_PROJECTION_TYPE') != 'POLAR STEREOGRAPHIC' or lab.get('CENTER_LATITUDE') != 90.0:
        raise ValueError(f'{lbl_path}: expected north polar stereographic, got {lab.get("MAP_PROJECTION_TYPE")}')
    if lab.get('SAMPLE_TYPE') != 'LSB_INTEGER' or lab.get('SAMPLE_BITS') != 16:
        raise ValueError(f'{lbl_path}: unexpected sample type {lab.get("SAMPLE_TYPE")}/{lab.get("SAMPLE_BITS")}')
    if lab.get('POSITIVE_LONGITUDE_DIRECTION') != 'EAST' or lab.get('KEYWORD_LATITUDE_TYPE') != 'PLANETOCENTRIC':
        raise ValueError(f'{lbl_path}: expected planetocentric east-positive')
    nl, ns = int(lab['LINES']), int(lab['LINE_SAMPLES'])
    sc = lab['MAP_SCALE']; s0 = lab['SAMPLE_PROJECTION_OFFSET']; l0 = lab['LINE_PROJECTION_OFFSET']
    a = np.memmap(img_path, dtype='<i2', mode='r', shape=(nl, ns))
    x_left_full = (1 - s0 - 1) * sc - sc / 2                 # left edge of sample 1
    y_top_full = (l0 - 1 + 1) * sc + sc / 2                  # top edge of line 1
    r0, r1, c0, c1 = 0, nl, 0, ns
    if window is not None:
        xmn, xmx, ymn, ymx = window
        c0 = max(0, int(np.floor((xmn - x_left_full) / sc))); c1 = min(ns, int(np.ceil((xmx - x_left_full) / sc)))
        r0 = max(0, int(np.floor((y_top_full - ymx) / sc))); r1 = min(nl, int(np.ceil((y_top_full - ymn) / sc)))
    dn = np.asarray(a[r0:r1, c0:c1], dtype=np.float64)
    radius = dn * lab.get('SCALING_FACTOR', 1.0) + lab['OFFSET']
    if 'MISSING_CONSTANT' in lab:
        radius[np.asarray(a[r0:r1, c0:c1]) == int(lab['MISSING_CONSTANT'])] = np.nan
    Z = radius - MERCURY.radius_m
    nm = name or lab.get('PRODUCT_ID', os.path.basename(img_path))
    meta = {'product_label': lab, 'height_reference_m': MERCURY.radius_m, 'source_offset_m': lab['OFFSET'],
            'datum_shift_applied_m': lab['OFFSET'] - MERCURY.radius_m, 'projection_radius_m': lab['A_AXIS_RADIUS'] * 1000.0,
            'path': img_path, 'pixel_rule': 'x = (sample - SAMPLE_PROJECTION_OFFSET - 1) * MAP_SCALE; '
                                             'y = (LINE_PROJECTION_OFFSET - line + 1) * MAP_SCALE (1-based, pixel centres)'}
    d = demmod.ArrayDEM(Z, x_left_full + c0 * sc, y_top_full - r0 * sc, sc, nm, meta)
    return Grid(d, PolarStereo(lab['A_AXIS_RADIUS'] * 1000.0, 'north'), meta)


def read_gdal_polar(file_path: str, name: str, scale_to_m: float = 1.0, height_reference_m: Optional[float] = None,
                    raw: bool = False) -> Grid:
    """Single-band GeoTIFF/ISIS cube in a polar stereographic CRS (+R=...). raw=True keeps values unchanged (layers that
    are not heights); otherwise Z = value * scale_to_m + height_reference_m - MERCURY.radius_m."""
    import rasterio
    with rasterio.open(file_path) as ds:
        crs = ds.crs.to_dict() if ds.crs else {}
        if crs.get('proj') != 'stere' or abs(abs(crs.get('lat_0', 0)) - 90) > 1e-9 or crs.get('lon_0', 0) != 0:
            raise ValueError(f'{file_path}: expected polar stereographic lon_0=0, got {crs}')
        t = ds.transform
        if abs(t.a + t.e) > 1e-9 or t.b != 0 or t.d != 0:
            raise ValueError(f'{file_path}: non-square or rotated pixels {t}')
        v = ds.read(1).astype(np.float64)
        nod = ds.nodata
    if nod is not None:
        v[v == nod] = np.nan
    v[~np.isfinite(v)] = np.nan
    v[np.abs(v) > 1e30] = np.nan
    pole = 'north' if crs['lat_0'] > 0 else 'south'
    Rp = float(crs['R'])
    if raw:
        Z = v; href = None
    else:
        href = height_reference_m if height_reference_m is not None else Rp
        Z = v * scale_to_m + href - MERCURY.radius_m
    meta = {'path': file_path, 'crs': crs, 'projection_radius_m': Rp, 'height_reference_m': href,
            'datum_shift_applied_m': None if raw else href - MERCURY.radius_m, 'scale_to_m': scale_to_m, 'raw': raw}
    return Grid(demmod.ArrayDEM(Z, t.c, t.f, t.a, name, meta), PolarStereo(Rp, pole), meta)


# --------------------------------------------------------------------------------------------------- named products
MLA_V2 = ('mercury_mla_gdr_v2', 'img/hdem_75n_250m.img', 'img/hdem_75n_250m.lbl')
MLA_V1_250 = ('mercury_mla_gdr_v1', 'img/hdem_45n_250m.img', 'img/hdem_45n_250m.lbl')
MLA_V1_COUNT_250 = ('mercury_mla_gdr_v1', 'img/hdec_45n_250m.img', 'img/hdec_45n_250m.lbl')
P85 = 'mercury_pgda85_prokofiev'
P85_DEM = 'raw/run-DEM-final-Prokofiev.tif'
P85_SLOPE = 'raw/run-DEM-final-Prokofiev_slp.tif'
P85_MAXFLUX = 'raw/maxincflx_1h_Prokofiev_SfS.tif'
P85_RADAR = 'raw/radar3b.map2.4rms.cub'
# PGDA 85 heights are in km; their reference radius is not stated in the files. 2 440 000 m (the MLA GDR v2 OFFSET and the
# file's own projection sphere) is the hypothesis, tested against MLA in tests/test_mercury_data.py (a 2 439 400 m reference
# would show as a 600 m median offset).
P85_HEIGHT_REFERENCE_M = 2_440_000.0


def mla_v2(window=None, root=None) -> Grid:
    pid, img, lbl = MLA_V2
    return read_mla_polar(path(pid, img, root), path(pid, lbl, root), 'MLA GDR v2 hdem_75n_250m', window)


def mla_counts(window=None, root=None) -> Grid:
    """Shot counts per 250 m pixel (v1, data through orbit year 3/4): DN = count (no scaling, OFFSET 0 expected)."""
    pid, img, lbl = MLA_V1_COUNT_250
    lab = parse_pds3_label(open(path(pid, lbl, root), encoding='latin-1').read())
    g = read_mla_polar(path(pid, img, root), path(pid, lbl, root), 'MLA GDR v1 hdec_45n_250m (counts)', window)
    cnt = g.dem.Z + MERCURY.radius_m - lab.get('OFFSET', 0.0)          # undo the radius conversion: plain counts
    cnt = cnt / lab.get('SCALING_FACTOR', 1.0)
    g.dem.Z = np.asarray(cnt)
    g.meta['raw'] = True
    return g


def prokofiev(layer: str = 'dem', root=None) -> Grid:
    if layer == 'dem':
        return read_gdal_polar(path(P85, P85_DEM, root), 'PGDA 85 Prokofiev hybrid DEM 125 m', 1000.0, P85_HEIGHT_REFERENCE_M)
    rel = {'slope': P85_SLOPE, 'maxflux': P85_MAXFLUX, 'radar': P85_RADAR}[layer]
    return read_gdal_polar(path(P85, rel, root), f'PGDA 85 {layer}', raw=True)
