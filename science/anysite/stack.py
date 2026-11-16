"""Terrain stack for the any-site solver.

`get_stack()` returns S3's `science.terrain.stack.TerrainStack` when it is importable and its index exists, otherwise
`LegacyStack`: the same three methods (`sample`, `window`, `coverage`; TERRAIN_STACK_CONTRACT.md §5) backed by the DEMs on
disk tonight (products.registry()). Windows are read with science.dem.read_window, unchanged (no resampling, nodata -> NaN,
|h| > 20 km -> NaN). Nothing is filled or upsampled.

compute_skyline samples DEMs at south-polar-stereographic grid coordinates. A window in another zone (north polar,
equirectangular) is wrapped by `SPView`, which converts those coordinates back to lat/lon (exact closed-form inverse) and
then into the product's own CRS (pyproj) before the bilinear sample. South-polar windows are passed through untouched, so
south-pole results are bit-identical to the existing solver.
"""
from __future__ import annotations

import functools
import json
import math

import numpy as np

from .. import dem as demmod
from .. import frames
from . import products as P


def _to_zone(lat, lon, entry):
    if entry['zone'] == 'sp':
        return frames.stereo_forward(lat, lon)
    if entry['zone'] == 'eq':
        lon0 = _eq_lon0(entry['crs_wkt'])
        lon = np.asarray(lon, float); lat = np.asarray(lat, float)
        x = frames.R_MOON_M * np.radians(((lon - lon0 + 180.0) % 360.0) - 180.0)
        y = frames.R_MOON_M * np.radians(lat)
        return (float(x), float(y)) if x.ndim == 0 else (x, y)
    t = _transformer(entry['crs_wkt'])
    return t.transform(np.asarray(lon, float), np.asarray(lat, float))


@functools.lru_cache(maxsize=16)
def _eq_lon0(wkt):
    import warnings
    from pyproj import CRS
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)       # to_dict goes through PROJ strings; parameters are kept
        p = CRS.from_wkt(wkt).to_dict()
    if p.get('proj') != 'eqc' or abs(p.get('R', frames.R_MOON_M) - frames.R_MOON_M) > 1 or p.get('lat_ts', 0) != 0:
        raise ValueError(f'unsupported equirectangular CRS {p}')
    return float(p.get('lon_0', 0.0))


def _eq_lon_left(e):
    """West edge of column 0, snapped to the product's exact 1/ppd grid (GDAL's bounds carry the rounded MAP_SCALE:
    -180.0005 deg instead of -180 for LOLA 128 ppd, a 0.06 px error if used directly)."""
    raw = _eq_lon0(e['crs_wkt']) + math.degrees(e['bounds'][0] / frames.R_MOON_M)
    return (round(raw * e['ppd']) / e['ppd']) % 360.0


def _is_global_eq(e):
    return e.get('zone') == 'eq' and e.get('ppd') and abs(e['width'] / e['ppd'] - 360.0) < 1e-6


EQ_MAX_PX = 60_000_000      # an equirectangular window above this is read from the next coarser resolution of the product


class EqDEM:
    """Window of a global simple-cylindrical product (pixel-registered, row 0 at +90). Sampled at south-polar-stereo
    (x, y) like every DEM here: (x, y) -> lat/lon (exact) -> fractional (row, col) -> bilinear. Longitude wraps across the
    0/360 seam; a window touching a pole spans all longitudes (rays over the pole stay inside). Within the half pixel next
    to +-90 deg (inside the footprint of the first/last row) the row index is clamped: the sample lies inside that row's
    pixels, nothing is extrapolated beyond the product."""

    def __init__(self, Z, r0, c0, ppd, full_ring, n_rows_total, n_cols_total, lon_left, name, meta):
        self.Z = Z; self.r0 = r0; self.c0 = c0; self.ppd = ppd; self.full_ring = full_ring
        self.H = n_rows_total; self.W = n_cols_total; self.lon_left = lon_left
        self.step = frames.R_MOON_M * math.radians(1.0 / ppd)
        self.name = name; self.meta = meta
        lat_top = 90.0 - r0 / ppd; lat_bot = 90.0 - (r0 + Z.shape[0]) / ppd
        self.bounds = (lon_left + c0 / ppd, lat_bot, lon_left + (c0 + Z.shape[1]) / ppd, lat_top)   # degrees

    def sample(self, x, y):
        lat, lon = frames.stereo_inverse(x, y)
        lat = np.asarray(lat, float); lon = np.asarray(lon, float)
        r = (90.0 - lat) * self.ppd - 0.5 - self.r0
        nr, nc = self.Z.shape
        if self.r0 == 0:
            r = np.where((r < 0) & (r >= -0.5), 0.0, r)
        if self.r0 + nr == self.H:
            r = np.where((r > nr - 1) & (r <= nr - 0.5), nr - 1.0, r)
        col = ((lon - self.lon_left) % 360.0) * self.ppd - 0.5          # 0..W-0.5 (global column, fractional)
        if self.full_ring:
            c = col % self.W
            ok = (r >= 0) & (r <= nr - 1)
            r0i = np.clip(np.floor(r).astype(int), 0, max(nr - 2, 0)); a_r = np.clip(r - r0i, 0, 1)
            c0i = np.floor(c).astype(int) % self.W; c1i = (c0i + 1) % self.W; a_c = c - np.floor(c)
        else:
            c = (col - self.c0) % self.W
            ok = (r >= 0) & (r <= nr - 1) & (c <= nc - 1)
            r0i = np.clip(np.floor(r).astype(int), 0, max(nr - 2, 0)); a_r = np.clip(r - r0i, 0, 1)
            c0i = np.clip(np.floor(c).astype(int), 0, nc - 2); c1i = c0i + 1; a_c = c - c0i
        r1i = np.minimum(r0i + 1, nr - 1)
        Z = self.Z
        z = ((1 - a_c) * (1 - a_r) * Z[r0i, c0i].astype(np.float64) + a_c * (1 - a_r) * Z[r0i, c1i]
             + (1 - a_c) * a_r * Z[r1i, c0i] + a_c * a_r * Z[r1i, c1i])
        return np.where(ok, z, np.nan)

    def digest(self):
        import hashlib
        h = hashlib.sha256()
        h.update(json.dumps([self.r0, self.c0, self.ppd, self.full_ring, list(self.Z.shape)]).encode())
        h.update(np.ascontiguousarray(self.Z, dtype=np.float32).tobytes())
        return h.hexdigest()

    def perturbed(self, field, name, meta):
        return EqDEM((self.Z.astype(np.float64) + field).astype(np.float32), self.r0, self.c0, self.ppd, self.full_ring,
                     self.H, self.W, self.lon_left, name, meta)


def _read_eq(e, lat0, lon0, half_m, name):
    import rasterio
    from rasterio.windows import Window
    ppd = e['ppd'] or 1.0 / math.degrees(e['res_m'] / frames.R_MOON_M)
    H, W = e['height'], e['width']
    lon_left = _eq_lon_left(e)
    dlat = math.degrees(half_m / frames.R_MOON_M)
    lat_hi = min(90.0, lat0 + dlat); lat_lo = max(-90.0, lat0 - dlat)
    r0 = max(0, int(math.floor((90.0 - lat_hi) * ppd)) - 1); r1 = min(H, int(math.ceil((90.0 - lat_lo) * ppd)) + 2)
    cosm = math.cos(math.radians(max(abs(lat_lo), abs(lat_hi))))
    full = lat_hi >= 90.0 - 1e-9 or lat_lo <= -90.0 + 1e-9 or cosm < 1e-6 or \
        math.degrees(half_m / (frames.R_MOON_M * cosm)) >= 179.0
    if full:
        c0, nc = 0, W
    else:
        dlon = math.degrees(half_m / (frames.R_MOON_M * cosm))
        c0 = int(math.floor((((lon0 - lon_left) % 360.0) - dlon) * ppd)) - 2
        nc = min(W, int(math.ceil(2 * dlon * ppd)) + 5)
    scale = e.get('unit_scale', 1.0)
    Z = np.empty((r1 - r0, nc), dtype=np.float32)
    with rasterio.open(e['path']) as ds:
        nod = ds.nodata
        col = 0
        while col < nc:
            gc = (c0 + col) % W; n = min(nc - col, W - gc)
            for rr in range(r0, r1, 2048):
                k = min(2048, r1 - rr)
                Z[rr - r0:rr - r0 + k, col:col + n] = ds.read(1, window=Window(gc, rr, n, k))
            col += n
    bad = ~np.isfinite(Z)
    if nod is not None and not math.isnan(nod):
        bad |= Z == nod
    Z = (Z.astype(np.float64) * scale).astype(np.float32) if scale != 1.0 else Z
    bad |= np.abs(Z) > 20000.0
    Z[bad] = np.nan
    meta = {'source_path': e['path'], 'rows': [r0, r1], 'col_off': c0, 'n_cols': nc, 'full_ring': full, 'ppd': ppd,
            'unit_scale': scale, 'resampling': 'none', 'screened_px': int(bad.sum())}
    return EqDEM(Z, r0, c0 % W if not full else 0, ppd, full, H, W, lon_left, name, meta)


def _eq_px(e, lat0, half_m):
    ppd = e['ppd'] or 1.0 / math.degrees(e['res_m'] / frames.R_MOON_M)
    dlat = math.degrees(half_m / frames.R_MOON_M)
    lat_hi = min(90.0, lat0 + dlat); lat_lo = max(-90.0, lat0 - dlat)
    cosm = math.cos(math.radians(max(abs(lat_lo), abs(lat_hi))))
    rows = (lat_hi - lat_lo) * ppd
    if lat_hi >= 90 - 1e-9 or lat_lo <= -90 + 1e-9 or cosm < 1e-6:
        return rows * e['width']
    return rows * min(e['width'], 2 * math.degrees(half_m / (frames.R_MOON_M * cosm)) * ppd)


@functools.lru_cache(maxsize=16)
def _transformer(wkt):
    from pyproj import CRS, Transformer
    crs = CRS.from_wkt(wkt)
    return Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True)


class SPView:
    """Adapter: an ArrayDEM in any CRS, sampled at south-polar-stereographic (x, y) as compute_skyline requires."""

    def __init__(self, dem, entry):
        self.inner = dem; self.entry = entry
        self.Z = dem.Z; self.step = dem.step; self.name = dem.name; self.meta = dem.meta
        self.bounds = dem.bounds

    def sample(self, x, y):
        lat, lon = frames.stereo_inverse(x, y)
        u, v = _to_zone(lat, lon, self.entry)
        return self.inner.sample(u, v)

    def digest(self):
        return self.inner.digest()


class CompositeDEM:
    """First finite sample among layers (priority order). Used when > 2 products cover a near field."""

    def __init__(self, layers, name=None):
        self.layers = layers; self.step = min(l.step for l in layers)
        self.name = name or ' > '.join(l.name for l in layers)
        self.meta = {'layers': [l.name for l in layers], **{k: v for k, v in layers[0].meta.items()
                                                             if k in ('product_id', 'product', 'zone')}}
        # compute_skyline only takes nanmax(Z) (beyond-range bound): the max over every layer
        self.Z = np.array([max(float(np.nanmax(l.Z)) for l in layers)])
        self.bounds = layers[0].bounds

    def sample(self, x, y):
        h = self.layers[0].sample(x, y)
        for l in self.layers[1:]:
            m = ~np.isfinite(h)
            if not m.any():
                break
            h = np.where(m, l.sample(x, y), h)
        return h

    def digest(self):
        import hashlib
        return hashlib.sha256(''.join(l.digest() for l in self.layers).encode()).hexdigest()


class LegacyStack:
    """Contract-shaped adapter over the existing DEMs (PGDA 78 tiles + clones, PGDA 90 80 m, S2 products if present)."""
    kind = 'legacy-adapter'

    def __init__(self, entries=None):
        self.entries = entries if entries is not None else P.registry()
        for e in self.entries:
            _ENTRIES[e['id']] = e

    def window_entry(self, lat0, lon0, half_m, e):
        """The entry actually read for a window: an equirectangular window larger than EQ_MAX_PX pixels is read from the
        next coarser resolution of the same product (recorded in the bundle's dem_layers)."""
        if e['zone'] != 'eq' or _eq_px(e, lat0, half_m) <= EQ_MAX_PX:
            return e
        sib = sorted([s for s in self.entries if s['product'] == e['product'] and s['zone'] == 'eq'
                      and s['res_m'] > e['res_m'] and s.get('ppd')], key=lambda s: s['res_m'])
        for s in sib:
            if _eq_px(s, lat0, half_m) <= EQ_MAX_PX:
                return s
        return sib[-1] if sib else e

    # -- contract §5 -------------------------------------------------------------------------------------------
    def covering(self, lat, lon):
        """Products whose footprint contains (lat, lon) with a finite height there, in priority order."""
        out = []
        for e in self.entries:
            x, y = _to_zone(lat, lon, e)
            l, b, r, t = e['bounds']
            if _is_global_eq(e):
                if not -90.0 <= lat <= 90.0:      # GDAL's rounded bounds miss x = -pi R (lon_0 - 180) by 4 m
                    continue
            elif not (l <= float(x) <= r and b <= float(y) <= t):
                continue
            if np.isfinite(self._point(e, float(x), float(y))):
                out.append(e)
        return out

    def sample(self, lat, lon):
        """Vectorised (h, source_id, native_res_m) from the finest covering product (bilinear; NaN outside)."""
        lat = np.atleast_1d(np.asarray(lat, float)); lon = np.atleast_1d(np.asarray(lon, float))
        h = np.full(lat.shape, np.nan); src = np.full(lat.shape, '', dtype=object); res = np.full(lat.shape, np.nan)
        for i, (la, lo) in enumerate(zip(lat.ravel(), lon.ravel())):
            cov = self.covering(la, lo)
            if cov:
                e = cov[0]; x, y = _to_zone(la, lo, e)
                h.flat[i] = self._point(e, float(x), float(y)); src.flat[i] = e['id']; res.flat[i] = e['res_m']
        return h, src, res

    def coverage(self, lat, lon):
        cov = self.covering(lat, lon)
        if not cov:
            return {'source_id': None, 'native_res_m': None, 'quality': 0, 'level': None, 'products': []}
        return {'source_id': cov[0]['id'], 'native_res_m': cov[0]['res_m'], 'quality': 2, 'level': 'native',
                'products': [{'id': e['id'], 'product': e['product'], 'res_m': e['res_m'], 'zone': e['zone'],
                              'n_clones_cached': len(e['clones'])} for e in cov]}

    def window(self, lat0, lon0, half_m, res_m=None, product=None, member=None):
        """ArrayDEM (or SPView for non-south-polar zones) centred on (lat0, lon0), half-width half_m in the product's grid.
        product: registry id; default = the covering product whose native resolution is closest to res_m without being
        coarser than needed (never upsampled). member: None (nominal) or 'clone0001'.. (PGDA 78 clones)."""
        e = self.window_entry(lat0, lon0, half_m, self._pick(lat0, lon0, res_m, product))
        path, name, url = e['path'], e['name'], e['url']
        if member is not None:
            c = int(member.replace('clone', ''))
            if c not in e['clones']:
                raise KeyError(f'{member} not cached for {e["id"]}')
            path = e['clones'][c]; name = name.replace('nominal', f'clone{c:04d}'); url = e['clone_url'].format(c)
        sha_path = path[:-4] + '.img' if str(path).endswith('.lbl') else path
        common = {'source_url': url, 'file_sha256': P.file_sha256(sha_path), 'product_id': e['id'],
                  'product': e['product'], 'zone': e['zone'], 'native_res_m': e['res_m'], 'citation': e.get('citation')}
        if e['zone'] == 'eq' and e.get('ppd'):
            d = _read_eq_cached(e['id'], round(lat0, 7), round(lon0, 7), float(half_m), name)
            d.meta.update(common)
            return d
        x, y = _to_zone(lat0, lon0, e)
        d = _read(path, float(x), float(y), float(half_m), name)
        s = e.get('unit_scale', 1.0)
        if s != 1.0:
            Z = d.Z * s
            Z[np.abs(Z) > 20000.0] = np.nan
            d = demmod.ArrayDEM(Z, d.x_left, d.y_top, d.step, d.name, {**d.meta, 'unit_scale': s})
        d.meta.update(common)
        return d if e['zone'] == 'sp' else SPView(d, e)

    # -- helpers -----------------------------------------------------------------------------------------------
    def entry(self, pid):
        return next(e for e in self.entries if e['id'] == pid)

    def _pick(self, lat, lon, res_m, product):
        if product is not None:
            return self.entry(product)
        cov = self.covering(lat, lon)
        if not cov:
            raise LookupError(f'no terrain product covers ({lat}, {lon})')
        if res_m is None:
            return cov[0]
        ok = [e for e in cov if e['res_m'] <= res_m * 1.0001]
        return max(ok, key=lambda e: (e['res_m'], -e['priority'])) if ok else min(cov, key=lambda e: e['res_m'])

    @staticmethod
    def _point(e, x, y):
        import rasterio
        with rasterio.open(e['path']) as ds:
            if e['zone'] == 'eq' and e.get('ppd'):
                # exact pixel-registered lat/lon grid (GDAL's geotransform uses the rounded label MAP_SCALE, which
                # drifts by up to ~0.06 px towards +-180 deg from the lon_0 of the CRS)
                lat = math.degrees(y / frames.R_MOON_M); lon = math.degrees(x / frames.R_MOON_M) + _eq_lon0(e['crs_wkt'])
                lon_left = _eq_lon_left(e)
                r = int(math.floor((90.0 - lat) * e['ppd'])); c = int(math.floor(((lon - lon_left) % 360.0) * e['ppd']))
            else:
                r, c = ds.index(x, y)
            if not (0 <= r < ds.height and 0 <= c < ds.width):
                return float('nan')
            v = float(ds.read(1, window=((r, r + 1), (c, c + 1)))[0, 0])
            if ds.nodata is not None and not math.isnan(ds.nodata) and v == ds.nodata:
                return float('nan')
            v *= e.get('unit_scale', 1.0)
            return v if abs(v) <= 20000.0 else float('nan')


@functools.lru_cache(maxsize=3)   # a far window is ~420 MB (float64); keep near + far + one spare per process
def _read_cached(path, x, y, half_m):
    return demmod.read_window(path, x, y, half_m)


_ENTRIES = {}


@functools.lru_cache(maxsize=2)
def _read_eq_cached(pid, lat0, lon0, half_m, name):
    return _read_eq(_ENTRIES[pid], lat0, lon0, half_m, name)


def _read(path, x, y, half_m, name):
    d = _read_cached(str(path), round(x, 6), round(y, 6), half_m)
    return demmod.ArrayDEM(d.Z, d.x_left, d.y_top, d.step, name, dict(d.meta))


def get_stack(prefer_pyramid=True):
    """S3's TerrainStack if available (and it has an index), else the legacy adapter."""
    if prefer_pyramid:
        try:
            from ..terrain.stack import TerrainStack  # noqa: F401  (S3, may not exist yet)
            st = TerrainStack.open()
            st.kind = 'pyramid'
            return st
        except Exception:
            pass
    return LegacyStack()
