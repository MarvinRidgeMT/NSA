"""Mars terrain readers -> grids with heights in metres above the MOLA sphere (3 396 000 m). Radius first, then height.

  * MOLA MEGDR radius (megr*): value = DN + 3 396 000 m (label OFFSET) = planetary radius -> height = DN (m).
  * MOLA MEGDR areoid (mega*, 4/16 ppd): areoid radius - 3 396 000 m.
  * MOLA MEGDR topography (megt*): radius - areoid (median per bin) -> used only for the CTX datum test.
  * CTX DEMs (Mars 2020): float32 m ABOVE THE MOLA AREOID. The file names say "MOLAtopography_DeltaGeoid"; the XML prose
    says the values "refer to the Mars 2020 IAU Sphere with a radius of 3396190m". Tested on the data
    (science/worlds/tests/test_mars.py): CTX - MOLA topography median -0.6 m (science mosaic) / +1.7 m (TRN), MAD 8-10 m;
    CTX - (radius - 3 396 190 m) median +1 691 m. So: height above 3 396 000 m = CTX + (areoid radius - 3 396 000 m), with
    the areoid from the 16 ppd areoid product (bilinear; the areoid is smooth at 3.7 km). The areoid is NOT taken as
    megr - megt at 128 ppd: mean radius minus median topography differs by up to 1.5 km in rough bins (16 ppd: p99 67 m).
"""
from __future__ import annotations

import math
import os
from functools import lru_cache

import numpy as np

from ... import dem as demmod
from ..grids import LonLatGrid, read_geotiff, read_simple_cyl
from .world import R_MOLA_M

MEG004 = 'mars_mola_megdr_004'
MEG016 = 'mars_mola_megdr_016'
MEG128 = 'mars_mola_megdr_128_44n000'
CTX_SCI = ('mars_ctx_jezero_sci_20m', 'M20_JezeroCrater_CTXDEM_20m.tif')
CTX_TRN = ('mars_ctx_jezero_trn_20m', 'JEZ_ctx_B_soc_008_DTM_MOLAtopography_DeltaGeoid_20m_Eqc_latTs0_lon0.tif')
TILE128 = {'megr': 'meg128/megr44n000hb', 'megt': 'meg128/megt44n000hb', 'megc': 'meg128/megc44n000hb',
           'lat': (0.0, 44.0), 'lon': (0.0, 90.0)}


def products_root(root=None):
    base = root or os.environ.get('POLARIS_DATA') or os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'cache')
    return os.path.abspath(os.path.join(base, 'v2', 'products'))


def path(pid, rel, root=None):
    return os.path.join(products_root(root), pid, rel)


def _pds(pid, stem, R, **kw):
    return read_simple_cyl(path(pid, stem + '.img'), path(pid, stem + '.lbl'), R, **kw)


def mola_radius(ppd, lat, lon, half_m, name=None):
    """MOLA radius heights around (lat, lon): 128 ppd from the cached tile (if it holds the window centre), or the 16 ppd
    global grid. Window = latitude band lat +- half (deg on the sphere) and +- half / cos(lat) in longitude."""
    d = math.degrees(half_m / R_MOLA_M) + 0.2
    if ppd == 128:
        lo, hi = TILE128['lat']; w, e = TILE128['lon']
        if not (lo <= lat < hi and w <= lon % 360 < e):
            raise LookupError('MOLA 128 ppd tile 44n000 does not hold this site (only that tile is cached)')
        dl = min(179.0, d / max(math.cos(math.radians(min(89.0, abs(lat) + d))), 1e-3))
        return _pds(MEG128, TILE128['megr'], R_MOLA_M, lat_range=(lat - d, lat + d), lon_center=lon % 360, lon_half_deg=dl,
                    name=name or 'MOLA MEGDR radius 128 ppd (megr44n000hb)')
    return _pds(MEG016, 'meg016/megr90n000eb', R_MOLA_M, lat_range=(max(-90, lat - d), min(90, lat + d)),
                name=name or 'MOLA MEGDR radius 16 ppd (megr90n000eb)')


@lru_cache(maxsize=1)
def areoid16():
    return _pds(MEG016, 'meg016/mega90n000eb', R_MOLA_M, name='MOLA MEGDR areoid radius 16 ppd (mega90n000eb)')


def mola_topography128(lat_range, lon_center, lon_half):
    return _pds(MEG128, TILE128['megt'], 0.0, lat_range=lat_range, lon_center=lon_center, lon_half_deg=lon_half,
                name='MOLA MEGDR topography 128 ppd (megt44n000hb)')


def mola_counts128(lat_range, lon_center, lon_half):
    return _pds(MEG128, TILE128['megc'], 0.0, lat_range=lat_range, lon_center=lon_center, lon_half_deg=lon_half, raw=True,
                name='MOLA MEGDR shot counts 128 ppd (megc44n000hb)')


@lru_cache(maxsize=4)
def ctx(which='sci', convert=True):
    """CTX DEM as ArrayDEM in its own eqc grid (+ forward). convert=True: heights above 3 396 000 m (areoid-referenced
    values + MOLA 16 ppd areoid); False: the file values (areoid heights), for the datum test."""
    pid, rel = CTX_SCI if which == 'sci' else CTX_TRN
    d, fwd, crs = read_geotiff(path(pid, rel), f'Mars 2020 CTX DEM 20 m ({which})', R_MOLA_M)
    if not convert:
        return d, fwd, crs
    R, k = float(crs['R']), math.cos(math.radians(crs.get('lat_ts', 0.0)))
    lon0 = crs.get('lon_0', 0.0)
    h, w = d.Z.shape
    xs = d.x_left + (np.arange(w) + 0.5) * d.step
    lons = lon0 + np.degrees(xs / (R * k))
    A = areoid16()
    Z = np.empty_like(d.Z)
    for r0 in range(0, h, 512):
        ys = d.y_top - (np.arange(r0, min(h, r0 + 512)) + 0.5) * d.step
        LA, LO = np.meshgrid(np.degrees(ys / R), lons, indexing='ij')
        Z[r0:r0 + len(ys)] = d.Z[r0:r0 + len(ys)] + A.sample(LO, LA)
    meta = {**d.meta, 'height_reference_m': R_MOLA_M,
            'datum_conversion': 'file value (m above the MOLA areoid, tested) + (MOLA 16 ppd areoid radius - 3 396 000 m)',
            'areoid_product': 'mars_mola_megdr_016/meg016/mega90n000eb.img'}
    return demmod.ArrayDEM(Z, d.x_left, d.y_top, d.step, d.name + ' -> radius heights', meta), fwd, crs
