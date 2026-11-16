"""WAC albedo for the v2 Blender scenes: the Hapke single-scattering albedo w per point, from the LROC WAC Hapke parameter map.
numpy only (works inside Blender). Unit-tested in blender/tests/test_albedo.py.

Source: PDS WAC_HAPKEPARAMMAP_643NM (LROLRC_2001, v1.1; Sato, Robinson, Hapke, Denevi & Boyd 2014, JGR Planets 119, 1775),
band 1 = w at 643 nm, 1 deg x 1 deg cells, 70 N - 70 S (blender/v2/hapke.py decodes it). Registration from the PDS3 attached
label (authoritative): MAP_RESOLUTION 1 px/deg, LINE_PROJECTION_OFFSET 69.5, SAMPLE_PROJECTION_OFFSET -0.5, i.e. with the DSMAP
relations line = LPO - lat + 1 and sample = SPO + lon + 1 (1-based), cell (line 1, sample 1) is centred at (69.5 N, 0.5 E) and the
grid edges are 70 N / 70 S / 0 / 360 E, matching MINIMUM/MAXIMUM_LATITUDE and WESTERN/EASTERNMOST_LONGITUDE in the same label.
(The PDS4 .xml upper-left corner reads 69.5 deg / -0.5 px: the label offsets copied as edges; like its wrong start byte, not used.)

Rule (MODEL, documented): bilinear between cell centres, longitude periodic. Poleward of the last cell centres (|lat| > 69.5)
w blends linearly to the regional median used for the polar sites (hapke.PARAMS_643NM['SOUTH_60_70'] in the south, the
60-70 N median in the north) over 69.5 -> 70.5 deg; beyond 70.5 deg it IS that median. The other Hapke parameters (b, c, B_S0,
h_S, theta-bar) are not changed by this module. Cells holding the PDS null constant are replaced by the regional fallback for
the hemisphere (counted). So south-polar scenes (all points beyond 70.5 S) get exactly the constant used before.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from . import hapke

ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = ROOT / 'data' / 'cache' / 'v2' / 'blender' / 'lroc_wac_hapkeparammap' / hapke.PDS_FILE
EDGE_LAT = 69.5          # centre of the last line
BLEND_DEG = 1.0          # 69.5 -> 70.5: blend to the regional constant
LABEL = 'MODEL: Hapke w from the LROC WAC 643 nm parameter map (1 deg), bilinear; regional median poleward of 70.5 deg'


class WMap:
    def __init__(self, w, sha256, north_fallback, south_fallback):
        self.w = np.asarray(w, dtype=np.float64)      # (140, 360), line 0 = 69.5 N, sample 0 = 0.5 E
        self.sha256 = sha256
        self.north, self.south = float(north_fallback), float(south_fallback)
        self.null_cells = int(np.isnan(self.w).sum())
        filled = self.w.copy()
        north_half = np.zeros_like(filled, bool)
        north_half[:70] = True
        filled[np.isnan(filled) & north_half] = self.north
        filled[np.isnan(filled) & ~north_half] = self.south
        self._wf = filled

    @classmethod
    def load(cls, path=MAP_PATH):
        maps, sha = hapke.read_pds_map(path)
        w = maps['w']
        north = float(np.nanmedian(w[0:10]))
        south = hapke.PARAMS_643NM['SOUTH_60_70']['w']
        return cls(w, sha, north, south)

    def describe(self):
        return {'source': hapke.PDS_URL, 'sha256': self.sha256, 'band': 'w (643 nm)', 'grid': '1 deg, 70N-70S, centres 69.5..-69.5, 0.5..359.5 E',
                'fallbackNorth60_70': self.north, 'fallbackSouth60_70': self.south, 'nullCellsFilledWithFallback': self.null_cells,
                'label': LABEL}

    def sample(self, lat_deg, lon_deg):
        lat = np.asarray(lat_deg, dtype=np.float64)
        lon = np.asarray(lon_deg, dtype=np.float64)
        lat, lon = np.broadcast_arrays(lat, lon)
        fy = np.clip(EDGE_LAT - lat, 0.0, 139.0)                 # fractional line (0-based) of the cell centres
        fx = np.mod(lon - 0.5, 360.0)                            # fractional sample (0-based), periodic
        j0 = np.clip(np.floor(fy).astype(int), 0, 138)
        i0 = np.floor(fx).astype(int) % 360
        i1 = (i0 + 1) % 360
        ty, tx = fy - j0, fx - np.floor(fx)
        W = self._wf
        w = (W[j0, i0] * (1 - tx) + W[j0, i1] * tx) * (1 - ty) + (W[j0 + 1, i0] * (1 - tx) + W[j0 + 1, i1] * tx) * ty
        a = np.abs(lat)
        fb = np.where(lat >= 0, self.north, self.south)
        t = np.clip((a - EDGE_LAT) / BLEND_DEG, 0.0, 1.0)
        return np.where(a >= EDGE_LAT + BLEND_DEG, fb, (1 - t) * w + t * fb)


def w_for_points(lat_deg, lon_deg, wmap=None, region='SOUTH_60_70'):
    """w at points. If every point is beyond 70.5 deg in one hemisphere the regional constant is returned without reading the
    map (committed-inputs reference build). Returns (w array, info)."""
    lat = np.asarray(lat_deg, dtype=np.float64)
    if lat.size and (np.all(lat <= -(EDGE_LAT + BLEND_DEG)) and region == 'SOUTH_60_70'):
        w0 = hapke.PARAMS_643NM['SOUTH_60_70']['w']
        return np.full(lat.shape, w0), {'mode': 'constant (all points poleward of 70.5 S: regional median SOUTH_60_70)', 'w': w0}
    if wmap is None:
        if not MAP_PATH.exists():
            raise FileNotFoundError(f'WAC Hapke map not cached at {MAP_PATH} (download: {hapke.PDS_URL})')
        wmap = WMap.load()
    w = wmap.sample(lat, lon_deg)
    return w, {'mode': 'per-vertex', 'wMin': float(np.min(w)), 'wMax': float(np.max(w)), 'wMedian': float(np.median(w)), **wmap.describe()}
