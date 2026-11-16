"""Whole-Moon terrain stack: read API over the science pyramid (v2 Phase 1, owner S3).

Contract: docs/v2/TERRAIN_STACK_CONTRACT.md. Plan: docs/v2/PHASE_1_PYRAMID_PLAN.md.

    stack = TerrainStack.open(root=None)           # root defaults to $POLARIS_DATA/v2/pyramid
    h, src, res = stack.sample(lat, lon)           # vectorised; bilinear on the finest level with data; NaN outside
    dem = stack.window(lat0, lon0, half_m, res_m)  # science.dem.ArrayDEM (subclass ZoneDEM)
    stack.coverage(lat, lon) -> dict               # source_id, native_res_m, quality, level, zone

Heights are metres above the 1,737,400 m sphere (MOON_ME, east-positive longitude), stored float32 and returned float64.
This module also holds the zone/level/tile geometry shared with the builder (tools/globe/pyramid.py), so the solver
and the builder cannot disagree on a grid.

Zones
  sp / np : polar stereographic on the 1,737,400 m sphere, true scale at the pole, |lat| >= 55 deg.
            sp: x = rho sin(lon), y =  rho cos(lon), rho = 2R tan(pi/4 + lat/2)   (== science.frames.stereo_forward)
            np: x = rho sin(lon), y = -rho cos(lon), rho = 2R tan(pi/4 - lat/2)   (+proj=stere +lat_0=90 +lon_0=0)
            extent +-1,310,720 m, level L pixel = 1280 m / 2^L, tiles 512 px.
  eq      : simple cylindrical lon/lat (deg), lat -60..60, lon -180..180, level L = 32 * 2^L pixels/deg, tiles 480 px.
`sample`/`coverage` use the polar zones for |lat| >= 57.5 deg and eq below, blending the two linearly across
56.5-58.5 deg (contract amendment 2026-11-16 §2 of the second amendment); each zone is a full merge on its own grid.

Science code must never read the VISUAL tree (pyramid_visual): `open` and every tile read refuse such paths.
"""
from __future__ import annotations

import json
import math
import os
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .. import frames
from ..dem import ArrayDEM

R = frames.R_MOON_M
BANDS = ('height', 'source_id', 'native_res_m', 'quality')
POLAR_HALF_M = 1_310_720.0
POLAR_L0_M = 1280.0
POLAR_TILE_PX = 512
POLAR_MIN_ABS_LAT = 55.0
EQ_L0_PPD = 32
EQ_TILE_PX = 480
EQ_MAX_ABS_LAT = 60.0
ZONE_SWITCH_ABS_LAT = 57.5
ZONE_BLEND_ABS_LAT = (56.5, 58.5)   # sample/coverage blend eq and polar linearly across this band (amendment 2)
MAX_LEVEL = 10
VISUAL_DIRNAME = 'pyramid_visual'
LABEL = 'SOURCE-BASED · UNVALIDATED'

PROJ4 = {
    'sp': '+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs',
    'np': '+proj=stere +lat_0=90 +lat_ts=90 +lon_0=0 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs',
    'eq': '+proj=longlat +R=1737400 +no_defs',
}


def default_root():
    base = os.environ.get('POLARIS_DATA') or str(Path(__file__).resolve().parents[2] / 'data' / 'cache')
    return Path(base) / 'v2' / 'pyramid'


def refuse_visual(path):
    """Raise if `path` lies in the VISUAL tree. Science code must never read synthetic relief."""
    parts = Path(path).resolve().parts + Path(path).parts
    if VISUAL_DIRNAME in parts:
        raise PermissionError(f'science code must not read the VISUAL tree ({VISUAL_DIRNAME}): {path}')


# ---------------------------------------------------------------------------------------------- zone geometry
class Zone:
    """Grid of one zone. Grid units: metres (polar) or degrees (eq). (u, v) = (x, y) or (lon, lat)."""

    def __init__(self, name):
        if name not in PROJ4:
            raise KeyError(name)
        self.name = name
        self.kind = 'eq' if name == 'eq' else 'polar'
        self.tile_px = EQ_TILE_PX if name == 'eq' else POLAR_TILE_PX
        self.proj4 = PROJ4[name]
        if name == 'eq':
            self.left, self.top, self.right, self.bottom = -180.0, EQ_MAX_ABS_LAT, 180.0, -EQ_MAX_ABS_LAT
        else:
            self.left, self.top, self.right, self.bottom = -POLAR_HALF_M, POLAR_HALF_M, POLAR_HALF_M, -POLAR_HALF_M

    def __repr__(self):
        return f'Zone({self.name!r})'

    # levels
    def pixel(self, level):
        """Pixel size in grid units (m polar, deg eq)."""
        return (1.0 / (EQ_L0_PPD * 2 ** level)) if self.kind == 'eq' else POLAR_L0_M / 2 ** level

    def pixel_m(self, level):
        """Nominal pixel size in metres: polar = grid metres; eq = latitude-direction metres (the larger axis)."""
        return R * math.radians(self.pixel(level)) if self.kind == 'eq' else self.pixel(level)

    def n_pixels(self, level):
        p = self.pixel(level)
        return int(round((self.right - self.left) / p)), int(round((self.top - self.bottom) / p))

    def n_tiles(self, level):
        nx, ny = self.n_pixels(level)
        return nx // self.tile_px, ny // self.tile_px

    def tile_bounds(self, level, ix, iy):
        s = self.pixel(level) * self.tile_px
        left = self.left + ix * s
        top = self.top - iy * s
        return (left, top - s, left + s, top)

    def level_for_res(self, res_m):
        """Finest level whose pixel is not finer than res_m (never upsample a product of native res_m)."""
        for L in range(MAX_LEVEL, -1, -1):
            if self.pixel_m(L) >= res_m / 1.01:
                return L
        return 0

    # projection
    def forward(self, lat, lon):
        lat = np.asarray(lat, dtype=float); lon = np.asarray(lon, dtype=float)
        if self.kind == 'eq':
            return (lon + 180.0) % 360.0 - 180.0, lat
        if self.name == 'sp':
            rho = 2 * R * np.tan(np.pi / 4 + np.radians(lat) / 2)
            return rho * np.sin(np.radians(lon)), rho * np.cos(np.radians(lon))
        rho = 2 * R * np.tan(np.pi / 4 - np.radians(lat) / 2)
        return rho * np.sin(np.radians(lon)), -rho * np.cos(np.radians(lon))

    def inverse(self, u, v):
        u = np.asarray(u, dtype=float); v = np.asarray(v, dtype=float)
        if self.kind == 'eq':
            return v, (u + 180.0) % 360.0 - 180.0
        rho = np.hypot(u, v)
        c = 2 * np.arctan(rho / (2 * R))
        if self.name == 'sp':
            return np.degrees(c - np.pi / 2), np.degrees(np.arctan2(u, v))
        return np.degrees(np.pi / 2 - c), np.degrees(np.arctan2(u, -v))

    def scale_k(self, lat):
        """Polar stereographic point scale (true at the pole): k = 2 / (1 + sin|lat|). eq: 1 along meridians."""
        lat = np.asarray(lat, dtype=float)
        if self.kind == 'eq':
            return np.ones_like(lat)
        return 2.0 / (1.0 + np.sin(np.radians(np.abs(lat))))

    def in_zone(self, lat):
        lat = np.asarray(lat, dtype=float)
        if self.kind == 'eq':
            return np.abs(lat) <= EQ_MAX_ABS_LAT
        return lat <= -POLAR_MIN_ABS_LAT if self.name == 'sp' else lat >= POLAR_MIN_ABS_LAT

    def pixel_centres(self, level, ix, iy, pad=0):
        """Grid coordinates (u, v) of the pixel centres of a tile (optionally padded by `pad` pixels)."""
        p = self.pixel(level)
        left, _, _, top = self.tile_bounds(level, ix, iy)
        n = self.tile_px + 2 * pad
        u = left + (np.arange(n) - pad + 0.5) * p
        v = top - (np.arange(n) - pad + 0.5) * p
        return np.meshgrid(u, v)


ZONES = {n: Zone(n) for n in ('sp', 'np', 'eq')}


def zone_name_for(lat):
    lat = np.asarray(lat, dtype=float)
    return np.where(lat >= ZONE_SWITCH_ABS_LAT, 'np', np.where(lat <= -ZONE_SWITCH_ABS_LAT, 'sp', 'eq'))


def tile_path(root, zone, level, ix, iy):
    return Path(root) / zone / str(level) / f'{ix}_{iy}.tif'


# ---------------------------------------------------------------------------------------------- window DEM
def oblique_stereo_forward(lat, lon, lat0, lon0):
    """Oblique stereographic on the R sphere centred at (lat0, lon0), scale 1 at the centre.
    Scale k = 2/(1+cos c) (c = angular distance): 1 + 5.2e-5 at 25 km, 1 + 7e-3 at 290 km."""
    la = np.radians(np.asarray(lat, dtype=float)); lo = np.radians(np.asarray(lon, dtype=float))
    la0, lo0 = math.radians(lat0), math.radians(lon0)
    cosc = math.sin(la0) * np.sin(la) + math.cos(la0) * np.cos(la) * np.cos(lo - lo0)
    k = 2 * R / (1 + cosc)
    x = k * np.cos(la) * np.sin(lo - lo0)
    y = k * (math.cos(la0) * np.sin(la) - math.sin(la0) * np.cos(la) * np.cos(lo - lo0))
    return x, y


def oblique_stereo_inverse(x, y, lat0, lon0):
    x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
    la0, lo0 = math.radians(lat0), math.radians(lon0)
    rho = np.hypot(x, y)
    c = 2 * np.arctan(rho / (2 * R))
    with np.errstate(invalid='ignore', divide='ignore'):
        la = np.arcsin(np.clip(np.cos(c) * math.sin(la0) + np.where(rho > 0, y * np.sin(c) * math.cos(la0) / rho, 0.0), -1, 1))
    lo = lo0 + np.arctan2(x * np.sin(c), rho * math.cos(la0) * np.cos(c) - y * math.sin(la0) * np.sin(c))
    return np.degrees(la), (np.degrees(lo) + 180.0) % 360.0 - 180.0


@dataclass
class ZoneDEM(ArrayDEM):
    """ArrayDEM with its own projection. `proj` is 'sp' / 'np' (zone grid) or 'local-stere' (oblique stereographic
    centred at (lat0, lon0), used for the eq zone). Use `sample_latlon` (science.skyline hard-codes the south formula,
    so only proj == 'sp' windows can go straight into compute_skyline)."""
    proj: str = 'sp'
    lat0: float = float('nan')
    lon0: float = float('nan')
    layers: dict = field(default_factory=dict)

    def forward(self, lat, lon):
        if self.proj == 'local-stere':
            return oblique_stereo_forward(lat, lon, self.lat0, self.lon0)
        return ZONES[self.proj].forward(lat, lon)

    def inverse(self, x, y):
        if self.proj == 'local-stere':
            return oblique_stereo_inverse(x, y, self.lat0, self.lon0)
        return ZONES[self.proj].inverse(x, y)

    def sample_latlon(self, lat, lon):
        x, y = self.forward(lat, lon)
        return self.sample(x, y)


# ---------------------------------------------------------------------------------------------- the stack
class TerrainStack:
    def __init__(self, root, index, max_tiles=192):
        refuse_visual(root)
        self.root = Path(root)
        self.index = index
        self.zones = ZONES
        self._tiles = {}
        for t in index.get('tiles', []):
            self._tiles.setdefault((t['zone'], int(t['level'])), set()).add((int(t['ix']), int(t['iy'])))
        self._cache = OrderedDict()
        self._max = max_tiles

    @classmethod
    def open(cls, root=None, max_tiles=192):
        root = Path(root) if root is not None else default_root()
        refuse_visual(root)
        p = root / 'index.json'
        if not p.exists():
            raise FileNotFoundError(f'no pyramid index at {p} (build with python -m tools.globe.pyramid build)')
        return cls(root, json.loads(p.read_text()), max_tiles)

    def levels(self, zone):
        return sorted(L for (z, L) in self._tiles if z == zone)

    def has_tile(self, zone, level, ix, iy):
        return (ix, iy) in self._tiles.get((zone, level), ())

    # ---- tile access
    def _load(self, zone, level, ix, iy):
        key = (zone, level, ix, iy)
        a = self._cache.get(key)
        if a is not None:
            self._cache.move_to_end(key)
            return a
        path = tile_path(self.root, zone, level, ix, iy)
        refuse_visual(path)
        import rasterio
        with rasterio.open(path) as ds:
            a = ds.read().astype(np.float32)
        self._cache[key] = a
        if len(self._cache) > self._max:
            self._cache.popitem(last=False)
        return a

    def _gather(self, zone, level, rows, cols):
        """Values of all bands at global pixel (rows, cols) of a level; NaN/0 where no tile or outside."""
        Z = ZONES[zone]
        T = Z.tile_px
        npx, npy = Z.n_pixels(level)
        rows = np.asarray(rows, dtype=np.int64); cols = np.asarray(cols, dtype=np.int64)
        if Z.kind == 'eq':
            cols = cols % npx
        out = np.full((4,) + rows.shape, np.nan, dtype=np.float32)
        out[1] = 0; out[3] = 0
        ok = (rows >= 0) & (rows < npy) & (cols >= 0) & (cols < npx)
        have = self._tiles.get((zone, level))
        if not have or not ok.any():
            return out
        nx = npx // T
        flat_out = out.reshape(4, -1)
        r = rows.ravel(); c = cols.ravel()
        idx = np.flatnonzero(ok.ravel())
        key = (r[idx] // T) * nx + (c[idx] // T)
        order = np.argsort(key, kind='stable')
        key_s = key[order]; idx_s = idx[order]
        cuts = np.flatnonzero(np.diff(key_s)) + 1
        for grp in np.split(np.arange(key_s.size), cuts):
            if grp.size == 0:
                continue
            k = int(key_s[grp[0]])
            tx, ty = k % nx, k // nx
            if (tx, ty) not in have:
                continue
            a = self._load(zone, level, tx, ty)
            j = idx_s[grp]
            flat_out[:, j] = a[:, r[j] - ty * T, c[j] - tx * T]
        return out

    def _query(self, lat, lon, levels=None, zone=None):
        """All bands at points; `zone` forces one zone (seam QA of the eq/polar overlap), else the 57.5 deg rule."""
        lat = np.asarray(lat, dtype=float); lon = np.asarray(lon, dtype=float)
        lat, lon = np.broadcast_arrays(lat, lon)
        shape = lat.shape
        la = lat.ravel(); lo = lon.ravel()
        n = la.size
        out = {'height': np.full(n, np.nan), 'source_id': np.zeros(n, np.uint8),
               'native_res_m': np.full(n, np.nan), 'quality': np.zeros(n, np.uint8),
               'level': np.full(n, -1, np.int16), 'zone': np.full(n, '', dtype='<U2')}
        zn = zone_name_for(la) if zone is None else np.full(n, zone)
        for zone in ('sp', 'np', 'eq'):
            m = np.flatnonzero((zn == zone) & np.isfinite(la) & np.isfinite(lo))
            if m.size == 0:
                continue
            Z = ZONES[zone]
            u, v = Z.forward(la[m], lo[m])
            todo = np.ones(m.size, bool)
            lv = self.levels(zone) if levels is None else [L for L in levels if L in self.levels(zone)]
            for L in sorted(lv, reverse=True):
                if not todo.any():
                    break
                i = np.flatnonzero(todo)
                p = Z.pixel(L)
                c = (u[i] - Z.left) / p - 0.5
                r = (Z.top - v[i]) / p - 0.5
                c0 = np.floor(c).astype(np.int64); r0 = np.floor(r).astype(np.int64)
                a = c - c0; b = r - r0
                g00 = self._gather(zone, L, r0, c0)[0]; g01 = self._gather(zone, L, r0, c0 + 1)[0]
                g10 = self._gather(zone, L, r0 + 1, c0)[0]; g11 = self._gather(zone, L, r0 + 1, c0 + 1)[0]
                h = ((1 - a) * (1 - b) * g00 + a * (1 - b) * g01 + (1 - a) * b * g10 + a * b * g11)
                ok = np.isfinite(h)
                if not ok.any():
                    continue
                near = self._gather(zone, L, np.rint(r[ok]).astype(np.int64), np.rint(c[ok]).astype(np.int64))
                j = m[i[ok]]
                out['height'][j] = h[ok]
                out['source_id'][j] = near[1].astype(np.uint8)
                out['native_res_m'][j] = near[2]
                out['quality'][j] = near[3].astype(np.uint8)
                out['level'][j] = L
                out['zone'][j] = zone
                todo[i[ok]] = False
        return {k: v.reshape(shape) for k, v in out.items()}

    def _query_blended(self, lat, lon, levels=None):
        """_query with the eq<->polar switch smoothed: for 56.5 <= |lat| <= 58.5 the height is a linear blend of
        both zones (weight of the polar zone (|lat| - 56.5) / 2), so the posting change at the switch (SLDEM at 59 m
        in eq vs resampled onto 80 m polar pixels; p99 |diff| 14 m south, 22 m north) becomes a gradient over ~60 km.
        Other bands come from the zone holding the larger weight; where one zone has no data the other is used."""
        q = self._query(lat, lon, levels=levels)
        la = np.asarray(lat, dtype=float); lo = np.asarray(lon, dtype=float)
        la, lo = np.broadcast_arrays(la, lo)
        a0, a1 = ZONE_BLEND_ABS_LAT
        b = (np.abs(la) >= a0) & (np.abs(la) <= a1) & np.isfinite(la)
        if not b.any():
            return q
        lb, lob = la[b], lo[b]
        qe = self._query(lb, lob, levels=levels, zone='eq')
        out = {k: v.copy() for k, v in q.items()}
        for pole, m in (('np', lb > 0), ('sp', lb < 0)):
            if not m.any():
                continue
            qp = self._query(lb[m], lob[m], levels=levels, zone=pole)
            w = (np.abs(lb[m]) - a0) / (a1 - a0)
            he, hp = qe['height'][m], qp['height']          # qp holds only the points of this hemisphere (R1 fix)
            h = np.where(np.isfinite(he) & np.isfinite(hp), (1 - w) * he + w * hp, np.where(np.isfinite(hp), hp, he))
            dom_p = np.where(np.isfinite(hp) & np.isfinite(he), w >= 0.5, np.isfinite(hp))
            idx = np.flatnonzero(b)[m]
            flat = {k: v.reshape(-1) for k, v in out.items()}
            flat['height'][idx] = h
            for k in ('source_id', 'native_res_m', 'quality', 'level', 'zone'):
                flat[k][idx] = np.where(dom_p, qp[k], qe[k][m])
            # a blend of two postings: report the coarser native resolution where both contribute
            both = np.isfinite(he) & np.isfinite(hp)
            flat['native_res_m'][idx] = np.where(both, np.fmax(qp['native_res_m'], qe['native_res_m'][m]),
                                                 flat['native_res_m'][idx])
        return out

    # ---- contract API
    def sample(self, lat, lon):
        """Height (m, float64), source_id (uint8), native_res_m (float) at lat/lon (deg). Bilinear on the finest level
        with a finite value at that point; NaN where no level has data. Never extrapolates."""
        q = self._query_blended(lat, lon)
        return q['height'], q['source_id'], q['native_res_m']

    def coverage(self, lat, lon, zone=None):
        """zone=None: the contract rule (57.5 deg switch, 56.5-58.5 deg blend). zone='sp'/'np'/'eq' (API addition, R1):
        that zone's grid only, no blend -- what a `window` centred here (which uses one zone) reads."""
        q = self._query_blended(lat, lon) if zone is None else self._query(lat, lon, zone=zone)
        return {k: q[k] for k in ('source_id', 'native_res_m', 'quality', 'level', 'zone')}

    # ---- API addition (R1, any-site far field): heights only, one tile gather per level
    def sample_height(self, lat, lon, max_level=None, touched=None, min_level=None):
        """Height (m, float64) at lat/lon: bilinear on the finest level <= max_level with a finite value at each point,
        coarser levels filling the rest; zone rule and 56.5-58.5 deg blend exactly as `sample` (equal to
        `sample(lat, lon)[0]` for max_level=None). max_level / min_level: int, or {zone: level} (a dict max_level reads only
        the zones it names; min_level=L stops the coarser fill at L, e.g. min = max = L reads exactly one level). touched: optional set that receives
        (zone, level, ix, iy) of every tile read (provenance). The four bilinear corners are gathered in one call, so a
        tile is decompressed once per level per call (sample() gathers four times, all bands)."""
        lat = np.asarray(lat, dtype=float); lon = np.asarray(lon, dtype=float)
        lat, lon = np.broadcast_arrays(lat, lon)
        shape = lat.shape
        la = lat.ravel(); lo = lon.ravel()
        out = self._height(la, lo, max_level, None, touched, min_level)
        a0, a1 = ZONE_BLEND_ABS_LAT
        b = np.flatnonzero((np.abs(la) >= a0) & (np.abs(la) <= a1) & np.isfinite(la))
        if b.size:
            lb, lob = la[b], lo[b]
            he = self._height(lb, lob, max_level, 'eq', touched, min_level)
            hp = np.full(b.size, np.nan)
            for pole, m in (('np', lb > 0), ('sp', lb < 0)):
                if m.any():
                    hp[m] = self._height(lb[m], lob[m], max_level, pole, touched, min_level)
            w = (np.abs(lb) - a0) / (a1 - a0)
            out[b] = np.where(np.isfinite(he) & np.isfinite(hp), (1 - w) * he + w * hp,
                              np.where(np.isfinite(hp), hp, he))
        return out.reshape(shape)

    def _height(self, la, lo, max_level, zone, touched, min_level=None):
        n = la.size
        out = np.full(n, np.nan)
        zn = zone_name_for(la) if zone is None else np.full(n, zone)
        for z in ('sp', 'np', 'eq'):
            m = np.flatnonzero((zn == z) & np.isfinite(la) & np.isfinite(lo))
            if m.size == 0:
                continue
            if isinstance(max_level, dict) and z not in max_level:
                continue
            Z = ZONES[z]
            top = max_level.get(z) if isinstance(max_level, dict) else max_level
            bot = min_level.get(z) if isinstance(min_level, dict) else min_level
            u, v = Z.forward(la[m], lo[m])
            todo = np.ones(m.size, bool)
            for L in sorted((l for l in self.levels(z) if (top is None or l <= top) and (bot is None or l >= bot)),
                            reverse=True):
                if not todo.any():
                    break
                i = np.flatnonzero(todo)
                p = Z.pixel(L)
                c = (u[i] - Z.left) / p - 0.5
                r = (Z.top - v[i]) / p - 0.5
                c0 = np.floor(c).astype(np.int64); r0 = np.floor(r).astype(np.int64)
                a = c - c0; b = r - r0
                k = i.size
                rr = np.concatenate([r0, r0, r0 + 1, r0 + 1]); cc = np.concatenate([c0, c0 + 1, c0, c0 + 1])
                g = self._gather_height(z, L, rr, cc, touched)
                g00, g01, g10, g11 = g[:k], g[k:2 * k], g[2 * k:3 * k], g[3 * k:]
                h = ((1 - a) * (1 - b) * g00 + a * (1 - b) * g01 + (1 - a) * b * g10 + a * b * g11)
                ok = np.isfinite(h)
                if not ok.any():
                    continue
                out[m[i[ok]]] = h[ok]
                todo[i[ok]] = False
        return out

    def _gather_height(self, zone, level, rows, cols, touched=None):
        """Height band at global pixels (rows, cols) of a level; NaN where no tile or outside. Same values as
        `_gather(...)[0]`, without sorting: tiles are found through a dense per-level lookup table (a level has at most
        a few 10^4 tiles), the needed tiles are stacked once, and every pixel is one fancy index."""
        Z = ZONES[zone]
        T = Z.tile_px
        npx, npy = Z.n_pixels(level)
        ntx, nty = npx // T, npy // T
        rows = np.asarray(rows, dtype=np.int64); cols = np.asarray(cols, dtype=np.int64)
        if Z.kind == 'eq':
            cols = cols % npx
        out = np.full(rows.shape, np.nan, dtype=np.float32)
        ok = (rows >= 0) & (rows < npy) & (cols >= 0) & (cols < npx)
        have = self._tiles.get((zone, level))
        if not have or not ok.any():
            return out
        r = rows[ok]; c = cols[ok]
        key = (r // T) * ntx + (c // T)
        flag = np.zeros(ntx * nty, bool)
        flag[key] = True
        need = [int(q) for q in np.flatnonzero(flag) if (int(q) % ntx, int(q) // ntx) in have]
        if not need:
            return out
        lut = np.full(ntx * nty, -1, dtype=np.int64)
        lut[need] = np.arange(len(need))
        stack = np.empty((len(need), T, T), dtype=np.float32)
        for i, q in enumerate(need):
            stack[i] = self._load(zone, level, q % ntx, q // ntx)[0]
            if touched is not None:
                touched.add((zone, level, q % ntx, q // ntx))
        slot = lut[key]
        m = slot >= 0
        v = np.full(r.shape, np.nan, dtype=np.float32)
        v[m] = stack[slot[m], r[m] - (key[m] // ntx) * T, c[m] - (key[m] % ntx) * T]
        out[ok] = v
        return out

    def tile_max_height(self, zone, level, ix, iy):
        """nanmax of a tile's height band (memoised; NaN for an all-NaN tile). API addition (R1)."""
        memo = self.__dict__.setdefault('_tile_max', {})
        key = (zone, level, ix, iy)
        if key not in memo:
            a = self._load(zone, level, ix, iy)[0]
            memo[key] = float(np.nanmax(a)) if np.isfinite(a).any() else float('nan')
        return memo[key]

    def window(self, lat0, lon0, half_m, res_m=None, fill_coarser=False, name=None):
        """Square DEM of half-width half_m centred near (lat0, lon0).

        Polar zones: in the zone's stereographic grid (proj 'sp'/'np'), aligned to the level grid. eq zone: in a local
        oblique stereographic grid centred at (lat0, lon0) (proj 'local-stere', documented in the module docstring).
        res_m=None -> the native step of the finest level with data at the centre. Otherwise the finest level whose
        pixel is <= res_m is read and block-averaged (polar, integer ratio) or bilinearly sampled (never finer than the
        level). Pixels with no data at that level stay NaN unless fill_coarser=True (bilinear from coarser levels,
        counted in meta['filled_from_coarser_px'] and flagged in layers['filled'])."""
        zone = str(zone_name_for(lat0))
        Z = ZONES[zone]
        lv = self.levels(zone)
        if not lv:
            raise ValueError(f'no tiles in zone {zone}')
        if res_m is None:
            c = self.coverage(lat0, lon0)
            L = int(c['level'])
            if L < 0:
                raise ValueError(f'no data at ({lat0}, {lon0})')
            step = Z.pixel_m(L)
        else:
            cand = [l for l in lv if Z.pixel_m(l) <= res_m * (1 + 1e-9)]
            L = max(cand, key=lambda l: Z.pixel_m(l)) if cand else max(lv)
            step = max(float(res_m), Z.pixel_m(L))
        n = int(math.ceil(2 * half_m / step))
        meta = {'zone': zone, 'level': L, 'level_pixel_m': Z.pixel_m(L), 'res_m_requested': res_m,
                'label': LABEL, 'stack_root': str(self.root), 'crs_proj4': None}
        if Z.kind == 'polar':
            x0, y0 = Z.forward(lat0, lon0)
            p = Z.pixel(L)
            k = int(round(step / p))
            if abs(k * p - step) < 1e-6 * step:
                # aligned read of k x k level pixels per output pixel
                c0 = int(math.floor((float(x0) - half_m - Z.left) / step)) * k
                r0 = int(math.floor((Z.top - float(y0) - half_m) / step)) * k
                rr, cc = np.meshgrid(np.arange(r0, r0 + n * k), np.arange(c0, c0 + n * k), indexing='ij')
                g = self._gather(zone, L, rr, cc)
                lay = _block_reduce(g, k)
                x_left = Z.left + c0 * p; y_top = Z.top - r0 * p
            else:
                x_left = float(x0) - half_m; y_top = float(y0) + half_m
                xs = x_left + (np.arange(n) + 0.5) * step; ys = y_top - (np.arange(n) + 0.5) * step
                X, Y = np.meshgrid(xs, ys)
                lat, lon = Z.inverse(X, Y)
                lay = self._layers_at(lat, lon, [L])
            proj = zone
            meta['crs_proj4'] = Z.proj4
        else:
            x_left = -n * step / 2; y_top = n * step / 2
            xs = x_left + (np.arange(n) + 0.5) * step; ys = y_top - (np.arange(n) + 0.5) * step
            X, Y = np.meshgrid(xs, ys)
            lat, lon = oblique_stereo_inverse(X, Y, lat0, lon0)
            lay = self._layers_at(lat, lon, [L])
            proj = 'local-stere'
            meta['crs_proj4'] = f'+proj=stere +lat_0={lat0} +lon_0={lon0} +k=1 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs'
        meta['crs_wkt'] = _wkt(meta['crs_proj4'])
        H = lay['height'].astype(np.float64)
        filled = np.zeros(H.shape, bool)
        if fill_coarser and np.isnan(H).any():
            X, Y = np.meshgrid(x_left + (np.arange(H.shape[1]) + 0.5) * step, y_top - (np.arange(H.shape[0]) + 0.5) * step)
            lat, lon = (Z.inverse(X, Y) if proj != 'local-stere' else oblique_stereo_inverse(X, Y, lat0, lon0))
            q = self._query(lat, lon)
            filled = np.isnan(H) & np.isfinite(q['height'])
            H[filled] = q['height'][filled]
            for b in ('source_id', 'native_res_m', 'quality'):
                lay[b][filled] = q[b][filled]
        srcs = sorted(int(s) for s in np.unique(lay['source_id']) if s)
        res = lay['native_res_m'][np.isfinite(lay['native_res_m'])]
        meta.update({'source_ids': srcs, 'native_res_m_min': float(res.min()) if res.size else None,
                     'native_res_m_max': float(res.max()) if res.size else None,
                     'nan_fraction': float(np.isnan(H).mean()), 'filled_from_coarser_px': int(filled.sum())})
        layers = {'source_id': lay['source_id'].astype(np.uint8), 'native_res_m': lay['native_res_m'].astype(np.float32),
                  'quality': lay['quality'].astype(np.uint8), 'filled': filled}
        return ZoneDEM(H, x_left=float(x_left), y_top=float(y_top), step=float(step),
                       name=name or f'TerrainStack {zone} L{L} {step:g} m', meta=meta,
                       proj=proj, lat0=float(lat0), lon0=float(lon0), layers=layers)

    def _layers_at(self, lat, lon, levels):
        q = self._query(lat, lon, levels=levels)
        return {'height': q['height'], 'source_id': q['source_id'], 'native_res_m': q['native_res_m'],
                'quality': q['quality']}


def _wkt(proj4):
    try:
        import warnings
        from pyproj import CRS
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            return CRS.from_proj4(proj4).to_wkt()
    except Exception:            # pyproj missing: proj4 string is still in meta
        return None


def _block_reduce(g, k):
    """(4, n*k, n*k) level pixels -> output pixels. Height: mean if >= 50 % of the block is valid, else NaN.
    source_id/quality: value at the block's centre pixel; native_res_m: max over the block's valid pixels."""
    h = g[0]
    if k == 1:
        return {'height': h.astype(np.float64), 'source_id': g[1].astype(np.uint8), 'native_res_m': g[2].copy(),
                'quality': g[3].astype(np.uint8)}
    n0, n1 = h.shape[0] // k, h.shape[1] // k
    hb = h.reshape(n0, k, n1, k).astype(np.float64)
    valid = np.isfinite(hb).sum(axis=(1, 3))
    with np.errstate(invalid='ignore'):
        mean = np.nansum(hb, axis=(1, 3)) / np.maximum(valid, 1)
    mean[valid < 0.5 * k * k] = np.nan
    rb = np.where(np.isfinite(h), g[2], np.nan).reshape(n0, k, n1, k)
    with np.errstate(invalid='ignore'), _quiet():
        res = np.nanmax(rb, axis=(1, 3))
    c = k // 2
    return {'height': mean, 'source_id': g[1][c::k, c::k].astype(np.uint8), 'native_res_m': res,
            'quality': g[3][c::k, c::k].astype(np.uint8)}


class _quiet:
    def __enter__(self):
        import warnings
        self._w = warnings.catch_warnings(); self._w.__enter__()
        warnings.simplefilter('ignore', RuntimeWarning)

    def __exit__(self, *a):
        self._w.__exit__(*a)
