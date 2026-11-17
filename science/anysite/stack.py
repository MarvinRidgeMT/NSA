"""Terrain stack for the any-site solver.

`get_stack()` returns `PyramidStack` (default since v2 round 2, R1): S3's merged whole-Moon pyramid
(`science.terrain.stack.TerrainStack`) supplies the nominal near field (finest level at the site, `LatLonView` for np /
eq `local-stere` windows) and the far field (`PyramidField`, sampled lazily across zones); the per-product adapter
`LegacyStack` supplies every uncertainty member (PGDA 78 clones, product disagreement). Rule and rationale:
docs/v2/PHASE_1_R1_PLAN.md. `POLARIS_ANYSITE_STACK=legacy` (or no pyramid index) gives `LegacyStack` alone.

`LegacyStack`: the contract methods (`sample`, `window`, `coverage`; TERRAIN_STACK_CONTRACT.md §5) backed by the product
files on disk. Windows are read with science.dem.read_window, unchanged (no resampling, nodata -> NaN, |h| > 20 km -> NaN).
Nothing is filled or upsampled.

compute_skyline samples DEMs at south-polar-stereographic grid coordinates. A window in another zone (north polar,
equirectangular) is wrapped by `SPView` / `LatLonView`, which convert those coordinates back to lat/lon (exact closed-form
inverse) and then into the window's own grid before the bilinear sample. South-polar windows are passed through
untouched, so south-pole results are bit-identical to the existing solver.
"""
from __future__ import annotations

import functools
from collections import OrderedDict
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
    if e.get('lon_left') is not None:                  # tile mosaic: from the labels' WESTERNMOST_LONGITUDE
        return float(e['lon_left']) % 360.0
    raw = _eq_lon0(e['crs_wkt']) + math.degrees(e['bounds'][0] / frames.R_MOON_M)
    return (round(raw * e['ppd']) / e['ppd']) % 360.0


def _lat_top(e):
    """Latitude of the top edge of row 0: +90 for a global product, the label MAXIMUM_LATITUDE for a tile mosaic."""
    return float(e.get('lat_top', 90.0))


def _lat_bot(e):
    return float(e.get('lat_bot', -90.0))


def _is_global_eq(e):
    return e.get('zone') == 'eq' and e.get('ppd') and abs(e['width'] / e['ppd'] - 360.0) < 1e-6


EQ_MAX_PX = 60_000_000      # an equirectangular window above this is read from the next coarser resolution of the product


class EqDEM:
    """Window of a global simple-cylindrical product (pixel-registered, row 0 at lat_top: +90 for a global grid, the top
    of the mosaic for a tiled product such as SLDEM2015 60 S - 60 N). Sampled at south-polar-stereo
    (x, y) like every DEM here: (x, y) -> lat/lon (exact) -> fractional (row, col) -> bilinear. Longitude wraps across the
    0/360 seam; a window touching a pole spans all longitudes (rays over the pole stay inside). Within the half pixel next
    to +-90 deg (inside the footprint of the first/last row) the row index is clamped: the sample lies inside that row's
    pixels, nothing is extrapolated beyond the product."""

    def __init__(self, Z, r0, c0, ppd, full_ring, n_rows_total, n_cols_total, lon_left, name, meta, lat_top=90.0):
        self.Z = Z; self.r0 = r0; self.c0 = c0; self.ppd = ppd; self.full_ring = full_ring
        self.H = n_rows_total; self.W = n_cols_total; self.lon_left = lon_left; self.lat_top = float(lat_top)
        self.step = frames.R_MOON_M * math.radians(1.0 / ppd)
        self.name = name; self.meta = meta
        lat_top = self.lat_top - r0 / ppd; lat_bot = self.lat_top - (r0 + Z.shape[0]) / ppd
        self.bounds = (lon_left + c0 / ppd, lat_bot, lon_left + (c0 + Z.shape[1]) / ppd, lat_top)   # degrees

    def sample(self, x, y):
        lat, lon = frames.stereo_inverse(x, y)
        lat = np.asarray(lat, float); lon = np.asarray(lon, float)
        r = (self.lat_top - lat) * self.ppd - 0.5 - self.r0
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
        h.update(json.dumps([self.r0, self.c0, self.ppd, self.full_ring, list(self.Z.shape)]
                            + ([self.lat_top] if self.lat_top != 90.0 else [])).encode())
        h.update(np.ascontiguousarray(self.Z, dtype=np.float32).tobytes())
        return h.hexdigest()

    def perturbed(self, field, name, meta):
        return EqDEM((self.Z.astype(np.float64) + field).astype(np.float32), self.r0, self.c0, self.ppd, self.full_ring,
                     self.H, self.W, self.lon_left, name, meta, self.lat_top)


def _read_block(e, ds, r0, r1, gc, n, out):
    """Rows [r0, r1) x global columns [gc, gc + n) (no wrap) of an eq entry into `out`. A global product reads its own
    file (`ds`); a tile mosaic reads every tile overlapping the block (pixels no tile holds stay NaN)."""
    from rasterio.windows import Window
    if not e.get('tiles'):
        for rr in range(r0, r1, 2048):
            k = min(2048, r1 - rr)
            out[rr - r0:rr - r0 + k, :] = ds.read(1, window=Window(gc, rr, n, k))
        return
    import rasterio
    out[:] = np.nan
    for t in e['tiles']:
        a0 = max(r0, t['r_off']); a1 = min(r1, t['r_off'] + t['height'])
        b0 = max(gc, t['c_off']); b1 = min(gc + n, t['c_off'] + t['width'])
        if a0 >= a1 or b0 >= b1:
            continue
        with rasterio.open(t['path']) as tds:
            blk = tds.read(1, window=Window(b0 - t['c_off'], a0 - t['r_off'], b1 - b0, a1 - a0)).astype(np.float32)
            nod = tds.nodata
        if nod is not None and not math.isnan(nod):
            blk[blk == nod] = np.nan
        out[a0 - r0:a1 - r0, b0 - gc:b1 - gc] = blk
        e.setdefault('_tiles_read', set()).add(t['id'])


def _read_eq(e, lat0, lon0, half_m, name):
    import rasterio
    ppd = e['ppd'] or 1.0 / math.degrees(e['res_m'] / frames.R_MOON_M)
    H, W = e['height'], e['width']
    lon_left = _eq_lon_left(e)
    top = _lat_top(e)
    dlat = math.degrees(half_m / frames.R_MOON_M)
    lat_hi = min(90.0, lat0 + dlat); lat_lo = max(-90.0, lat0 - dlat)
    r0 = max(0, int(math.floor((top - lat_hi) * ppd)) - 1); r1 = min(H, int(math.ceil((top - lat_lo) * ppd)) + 2)
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
    e.pop('_tiles_read', None)
    with rasterio.open(e['path']) as ds:
        nod = ds.nodata
        col = 0
        while col < nc:
            gc = (c0 + col) % W; n = min(nc - col, W - gc)
            _read_block(e, ds, r0, r1, gc, n, Z[:, col:col + n])
            col += n
    bad = ~np.isfinite(Z)
    if nod is not None and not math.isnan(nod):
        bad |= Z == nod
    Z = (Z.astype(np.float64) * scale).astype(np.float32) if scale != 1.0 else Z
    bad |= np.abs(Z) > 20000.0
    Z[bad] = np.nan
    meta = {'source_path': e['path'], 'rows': [r0, r1], 'col_off': c0, 'n_cols': nc, 'full_ring': full, 'ppd': ppd,
            'unit_scale': scale, 'resampling': 'none', 'screened_px': int(bad.sum())}
    if e.get('tiles'):
        meta.update({'lat_top': top, 'tiles_read': sorted(e.pop('_tiles_read', set()))})
    return EqDEM(Z, r0, c0 % W if not full else 0, ppd, full, H, W, lon_left, name, meta, top)


def _eq_px(e, lat0, half_m):
    ppd = e['ppd'] or 1.0 / math.degrees(e['res_m'] / frames.R_MOON_M)
    dlat = math.degrees(half_m / frames.R_MOON_M)
    lat_hi = min(90.0, lat0 + dlat); lat_lo = max(-90.0, lat0 - dlat)
    if e.get('tiles'):
        lat_hi = min(lat_hi, _lat_top(e)); lat_lo = max(lat_lo, _lat_bot(e))
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
        # ray step / cell size of the composite = its primary layer's (fill layers must not change the far step)
        self.layers = layers; self.step = layers[0].step
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
                if not _lat_bot(e) <= lat <= _lat_top(e):   # GDAL's rounded bounds miss x = -pi R (lon_0 - 180) by 4 m
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
        common = {'source_url': url, 'product_id': e['id'],
                  'product': e['product'], 'zone': e['zone'], 'native_res_m': e['res_m'], 'citation': e.get('citation')}
        if e['zone'] == 'eq' and e.get('ppd'):
            d = _read_eq_cached(e['id'], round(lat0, 7), round(lon0, 7), float(half_m), name)
            if e.get('tiles'):        # mosaic: one SHA-256 per tile actually read (the mosaic has no single file)
                by_id = {t['id']: t for t in e['tiles']}
                tl = [{'id': i, 'img': by_id[i]['img'], 'url': by_id[i]['url'], 'file_sha256': P.file_sha256(by_id[i]['img'])}
                      for i in d.meta.get('tiles_read', [])]
                common['tiles'] = tl
                common['file_sha256'] = __import__('hashlib').sha256(''.join(t['file_sha256'] for t in tl).encode()).hexdigest()
                common['file_sha256_note'] = 'SHA-256 of the concatenated per-tile SHA-256s (tiles listed in meta.tiles)'
            else:
                common['file_sha256'] = P.file_sha256(sha_path)
            d.meta.update(common)
            return d
        common['file_sha256'] = P.file_sha256(sha_path)
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
    def _tile_point(e, r, c):
        import rasterio
        if not (0 <= r < e['height'] and 0 <= c < e['width']):
            return float('nan')
        t = next((t for t in e['tiles'] if t['r_off'] <= r < t['r_off'] + t['height']
                  and t['c_off'] <= c < t['c_off'] + t['width']), None)
        if t is None:
            return float('nan')
        with rasterio.open(t['path']) as ds:
            v = float(ds.read(1, window=((r - t['r_off'], r - t['r_off'] + 1), (c - t['c_off'], c - t['c_off'] + 1)))[0, 0])
            if ds.nodata is not None and not math.isnan(ds.nodata) and v == ds.nodata:
                return float('nan')
        v *= e.get('unit_scale', 1.0)
        return v if abs(v) <= 20000.0 else float('nan')

    @staticmethod
    def _point(e, x, y):
        import rasterio
        with rasterio.open(e['path']) as ds:
            if e['zone'] == 'eq' and e.get('ppd'):
                # exact pixel-registered lat/lon grid (GDAL's geotransform uses the rounded label MAP_SCALE, which
                # drifts by up to ~0.06 px towards +-180 deg from the lon_0 of the CRS)
                lat = math.degrees(y / frames.R_MOON_M); lon = math.degrees(x / frames.R_MOON_M) + _eq_lon0(e['crs_wkt'])
                lon_left = _eq_lon_left(e)
                r = int(math.floor((_lat_top(e) - lat) * e['ppd'])); c = int(math.floor(((lon - lon_left) % 360.0) * e['ppd']))
                if e.get('tiles'):
                    return LegacyStack._tile_point(e, r, c)
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


# ------------------------------------------------------------------------------------------------ pyramid (R1)
FAR_MIN_RES_M = 75.0          # far level = finest pyramid level whose pixel is >= this (polar L4 = 80 m, eq L3 = 118 m)
NEAR_MAX_PX = 6000            # near window <= 6000 px per side (as the per-product path)
NEAR_HALF_M = 25_000.0
FINE_STEP_MAX_M = 12_500.0
FINE_NATIVE_TOL = 1.05        # a near pixel is "fine" if native_res_m <= 1.05 x the level pixel

# source_id (docs/v2/SOURCE_IDS.json) -> product family key of products.PRIORITY / ERROR_MODELS
SOURCE_FAMILY = {1: 'nac_dtm', 2: 'sfs', 3: 'pgda78', 4: 'kaguya_tc', 5: 'pgda90', 6: 'sldem2015',
                 7: 'lola_polar_ldem', 8: 'lola_global_ldem'}


def _source_names():
    try:
        d = json.loads((P.ROOT / 'docs' / 'v2' / 'SOURCE_IDS.json').read_text())
        return {int(k): v for k, v in d.items() if k.isdigit()}
    except Exception:
        return {}


class LatLonView:
    """A ZoneDEM whose proj is not 'sp' (np stereographic, eq 'local-stere'), sampled at compute_skyline's south-polar
    stereographic (x, y): exact closed-form inverse to lat/lon, then the window's own forward projection, then bilinear on
    its grid. (`SPView` does the same for per-product rasters through a CRS WKT; a pyramid window carries its projection.)"""

    def __init__(self, zd):
        self.inner = zd
        self.Z = zd.Z; self.step = zd.step; self.name = zd.name; self.meta = zd.meta; self.bounds = zd.bounds
        self.layers = getattr(zd, 'layers', {})

    def sample(self, x, y):
        lat, lon = frames.stereo_inverse(x, y)
        return self.inner.sample_latlon(lat, lon)

    def digest(self):
        return self.inner.digest()

    def rewrap(self, zd):
        return LatLonView(zd)


def view(zd):
    """compute_skyline-ready view of a pyramid window: 'sp' windows unchanged (bit-identical), others wrapped."""
    return zd if getattr(zd, 'proj', 'sp') == 'sp' else LatLonView(zd)


class PyramidField:
    """Far field: the merged pyramid sampled lazily at the ray points (no dense window), across zones, at the far level
    of each zone ({'sp': 4, 'np': 4, 'eq': 3}), coarser levels filling gaps. A dense +-290 km window is 7250^2 px and
    cannot cross the eq/polar switch; this samples exactly what the rays need.

    Z (compute_skyline / curvature use only nanmax(Z), the beyond-range reference height) = the maximum over the
    far-level tiles the rays read (a tile-granular upper bound of the far-level heights within the ray disc; the per-product
    path used the max of its +-290 km square window)."""

    CHUNK = 1_000_000

    def __init__(self, pyr, lat0, lon0, half_m, levels, step, name=None, min_levels=None, bounded=False):
        self.pyr = pyr; self.lat0 = float(lat0); self.lon0 = float(lon0); self.half = float(half_m)
        self.levels = dict(levels); self.step = float(step); self.min_levels = min_levels
        self.bounded = bounded      # True: NaN outside the +-half square of the oblique stereographic frame (near field)
        self.touched = set()
        self.name = name or f'pyramid far field (levels {self.levels}, ray step {self.step:g} m, +-{self.half / 1000:g} km)'
        self.bounds = (-self.half, -self.half, self.half, self.half)
        self.bounds_units = 'oblique stereographic m about the site'
        self.meta = {'zone': 'multi', 'product_id': 'pyramid:far', 'label': 'SOURCE-BASED · UNVALIDATED',
                     'levels': self.levels, 'stack_root': str(pyr.root)}
        self._zmax = None

    def sample(self, x, y):
        """Memoised on the exact bytes of (x, y): the nominal skyline and every member batch with the same ray geometry
        (clone chunks) ask for identical points."""
        import hashlib
        x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
        key = (x.shape, hashlib.blake2b(np.ascontiguousarray(x).tobytes() + np.ascontiguousarray(y).tobytes(),
                                        digest_size=16).hexdigest())
        memo = self.__dict__.setdefault('_memo', OrderedDict())
        if key in memo:
            memo.move_to_end(key)
            return memo[key].copy()
        h = np.empty(x.shape)
        xf, yf, hf = x.reshape(-1), y.reshape(-1), h.reshape(-1)
        for i in range(0, xf.size, self.CHUNK):          # bounded memory (4 corners x int64 indices per point)
            lat, lon = frames.stereo_inverse(xf[i:i + self.CHUNK], yf[i:i + self.CHUNK])
            v = self.pyr.sample_height(lat, lon, max_level=self.levels, touched=self.touched, min_level=self.min_levels)
            if self.bounded:
                from ..terrain.stack import oblique_stereo_forward
                xo, yo = oblique_stereo_forward(lat, lon, self.lat0, self.lon0)
                v = np.where((np.abs(xo) <= self.half) & (np.abs(yo) <= self.half), v, np.nan)
            hf[i:i + self.CHUNK] = v
        memo[key] = h
        while len(memo) > 2:
            memo.popitem(last=False)
        return h.copy()

    @property
    def Z(self):
        """compute_skyline and curvature.record read only nanmax(Z) (beyond-range reference height), after sampling the
        rays. Z = the maximum height of the far-level tiles the 720 rays read (fixed at first access); if accessed before
        any sampling, of the tiles covering the window square."""
        if self._zmax is None:
            cover = set(self.touched)
            if not cover:
                from ..terrain.stack import oblique_stereo_inverse
                span = min(ZONE.pixel_m(L) * ZONE.tile_px for ZONE, L in
                           ((self.pyr.zones[z], l) for z, l in self.levels.items()))
                n = int(math.ceil(2 * self.half / (span / 4))) + 1
                g = np.linspace(-self.half, self.half, n)
                X, Y = np.meshgrid(g, g)
                la, lo = oblique_stereo_inverse(X, Y, self.lat0, self.lon0)
                self.pyr.sample_height(la, lo, max_level=self.levels, touched=cover)
                self.meta['zmax_from'] = 'tiles covering the window square'
            else:
                self.meta['zmax_from'] = 'tiles read by the rays'
            vals = [self.pyr.tile_max_height(*t) for t in cover]
            vals = [v for v in vals if math.isfinite(v)]
            self._zmax = np.array([max(vals) if vals else np.nan])
            self.meta['zmax_tiles'] = len(cover)
        return self._zmax

    def tiles(self):
        return sorted(self.touched)

    def digest(self):
        import hashlib
        idx = _tile_sha(self.pyr)
        h = hashlib.sha256(json.dumps({'levels': self.levels, 'step': self.step, 'half': self.half}, sort_keys=True).encode())
        for t in self.tiles():
            h.update(f'{t}:{idx.get(t)}'.encode())
        return h.hexdigest()


class PerturbedField:
    """Assumed-error-model member of a lazily sampled near field: nominal heights + a smooth error field defined on the
    near window's grid (bilinear; the field's correlation length is >= 50 m, so interpolating it changes nothing)."""

    def __init__(self, base, field_view, name, meta):
        self.base = base; self.field = field_view; self.name = name; self.meta = meta
        self.step = base.step; self.bounds = base.bounds; self.bounds_units = base.bounds_units
        self.Z = base.Z

    def sample(self, x, y):
        return self.base.sample(x, y) + self.field.sample(x, y)

    def digest(self):
        import hashlib
        return hashlib.sha256((self.base.digest() + self.field.digest()).encode()).hexdigest()


_TILE_SHA = {}


def _tile_sha(pyr):
    key = id(pyr.index)
    if key not in _TILE_SHA:
        _TILE_SHA.clear()
        _TILE_SHA[key] = {(t['zone'], int(t['level']), int(t['ix']), int(t['iy'])): t.get('sha256')
                          for t in pyr.index.get('tiles', [])}
    return _TILE_SHA[key]


@functools.lru_cache(maxsize=4)
def _index_sha256(path, size, mtime_ns):
    import hashlib
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(1 << 22):
            h.update(chunk)
    return h.hexdigest()


def index_sha256(pyr):
    p = pyr.root / 'index.json'
    if not p.exists():
        return None
    st = p.stat()
    return _index_sha256(str(p), st.st_size, st.st_mtime_ns)


def fine_radius_m(zd, lat, lon, tol=FINE_NATIVE_TOL):
    """Near-field rule (PHASE_1_R1_PLAN.md §2): ground distance from the site to the nearest pixel centre of the window
    that is not 'fine' (non-finite height, or native_res_m > tol x level pixel), or to the window edge. Grid metres are
    divided by the zone's point scale at the site (polar stereographic k = 2/(1+sin|lat|); oblique stereographic k = 1 at
    its centre) to give ground metres."""
    x0, y0 = zd.forward(lat, lon)
    x0 = float(x0); y0 = float(y0)
    H, W = zd.Z.shape
    l, b, r, t = zd.bounds
    d = min(x0 - l, r - x0, y0 - b, t - y0)
    p = zd.meta.get('level_pixel_m', zd.step)
    bad = ~np.isfinite(zd.Z)
    nr = getattr(zd, 'layers', {}).get('native_res_m')
    if nr is not None:
        with np.errstate(invalid='ignore'):
            bad |= ~(nr <= tol * p)
    xs = zd.x_left + (np.arange(W) + 0.5) * zd.step - x0
    for r0 in range(0, H, 512):                          # row blocks: bounded memory
        blk = bad[r0:r0 + 512]
        if not blk.any():
            continue
        ys = zd.y_top - (np.arange(r0, r0 + blk.shape[0]) + 0.5) * zd.step - y0
        d2 = np.where(blk, xs[None, :] ** 2 + ys[:, None] ** 2, np.inf)
        d = min(d, float(np.sqrt(d2.min())))
    k = 1.0 if zd.proj == 'local-stere' else 2.0 / (1.0 + math.sin(math.radians(abs(lat))))
    return max(0.0, d) / k


class PyramidStack:
    """Default any-site terrain (R1): S3's merged pyramid for the nominal near and far fields, the per-product adapter
    (`products`, a LegacyStack) for every uncertainty member (PGDA 78 clones, product disagreement). The pyramid answers
    "best merged terrain here"; the members answer "what if". Contract API (sample/window/coverage) is the pyramid's."""
    kind = 'pyramid'

    def __init__(self, pyramid=None, products=None):
        if pyramid is None:
            from ..terrain.stack import TerrainStack
            pyramid = TerrainStack.open(max_tiles=400)   # ~1.7 GB: far disc (~200 L4 tiles) + near (~80) + members
        self.pyramid = pyramid
        self._products = products
        self.entries = []          # the per-product code path keys on .entries; members use .products

    @property
    def products(self):
        if self._products is None:
            self._products = LegacyStack()
        return self._products

    # ---- contract API (pyramid)
    def sample(self, lat, lon):
        return self.pyramid.sample(lat, lon)

    def window(self, lat0, lon0, half_m, res_m=None):
        return view(self.pyramid.window(lat0, lon0, half_m, res_m))

    def coverage(self, lat, lon):
        """Contract coverage (scalars) + the window zone/level the solver reads + 'products' = per-product entries
        covering the point (members)."""
        from ..terrain.stack import zone_name_for
        c = {k: _scalar(v) for k, v in self.pyramid.coverage(lat, lon).items()}
        zone = str(zone_name_for(lat))
        w = {k: _scalar(v) for k, v in self.pyramid.coverage(lat, lon, zone=zone).items()}
        c['window'] = {'zone': zone, 'level': int(w['level']), 'source_id': int(w['source_id']),
                       'native_res_m': None if not np.isfinite(w['native_res_m']) else float(w['native_res_m']),
                       'quality': int(w['quality'])}
        c['source_name'] = _source_names().get(int(c['source_id'] or 0))
        c['family'] = SOURCE_FAMILY.get(int(w['source_id']))
        c['pyramid_index_sha256'] = index_sha256(self.pyramid)
        try:
            cov = self.products.coverage(lat, lon)['products']
        except Exception:                                  # no per-product data on this machine: pyramid alone
            cov = []
        c['products'] = cov
        return c

    # ---- solver helpers
    def far_levels(self):
        return {z: self.far_level(z) for z in ('sp', 'np', 'eq') if self.pyramid.levels(z)}

    def far_level(self, zone):
        Z = self.pyramid.zones[zone]
        ok = [L for L in self.pyramid.levels(zone) if Z.pixel_m(L) >= FAR_MIN_RES_M / 1.0001]
        return max(ok) if ok else min(self.pyramid.levels(zone))

    def near_field(self, lat, lon, cov=None):
        """(near view, info): window at the finest level with data at the site in the window zone; near cut by the rule."""
        cov = cov or self.coverage(lat, lon)
        zone, L = cov['window']['zone'], cov['window']['level']
        if L < 0:
            raise LookupError(f'no pyramid data at ({lat}, {lon}) in zone {zone}')
        Z = self.pyramid.zones[zone]
        p = Z.pixel_m(L)
        Lf = self.far_level(zone)
        half = min(NEAR_HALF_M, NEAR_MAX_PX / 2 * p)
        zd = self.pyramid.window(lat, lon, half, p, name=f'pyramid {zone} L{L} {p:g} m (near)')
        cap = FINE_STEP_MAX_M if L > Lf else NEAR_HALF_M
        d_fine = fine_radius_m(zd, lat, lon)
        near_cut = max(0.0, min(d_fine - math.sqrt(2.0) * p, cap))
        zd.meta.update({'product_id': f'pyramid:{zone}/L{L}', 'pyramid_index_sha256': cov['pyramid_index_sha256']})
        if zd.proj == 'local-stere':
            # The eq window is a bilinear resample onto an oblique stereographic grid; sampling it again would
            # interpolate twice. The near field instead samples the pyramid's own lon/lat grid at exactly level L
            # (one bilinear, no coarser fill, eq zone only); the window serves the near-cut rule and provenance.
            nf = PyramidField(self.pyramid, lat, lon, half, {zone: L}, p, min_levels={zone: L}, bounded=True,
                              name=f'pyramid {zone} L{L} {p:g} m (near, native lon/lat grid)')
            nf.meta.update({k: v for k, v in zd.meta.items() if k not in ('zone',)})
            nf.meta.update({'zone': zone, 'level': L, 'window_proj': 'local-stere'})
            nf.window = zd
            nf._zmax = np.array([np.nanmax(zd.Z)]) if np.isfinite(zd.Z).any() else np.array([np.nan])
            return nf, {**info_base(zd), **self._info(zone, L, p, half, Lf, d_fine, near_cut, cap)}
        return view(zd), {**info_base(zd), **self._info(zone, L, p, half, Lf, d_fine, near_cut, cap)}

    @staticmethod
    def _info(zone, L, p, half, Lf, d_fine, near_cut, cap):
        return {'zone': zone, 'level': L, 'pixel_m': p, 'half_m': half, 'far_level': Lf, 'd_fine_m': round(d_fine, 3),
                'near_cut_m': near_cut, 'cap_m': cap,
                'rule': 'near_cut = min(d_fine - sqrt(2) * pixel, cap); d_fine = ground distance from the site to the '
                        'nearest window pixel that is NaN or has native_res_m > 1.05 x the level pixel (or the window '
                        'edge); cap 12.5 km if the near level is finer than the far level, else 25 km '
                        '(docs/v2/PHASE_1_R1_PLAN.md §2)'}

    def far_field(self, lat, lon, half_m):
        lv = self.far_levels()
        from ..terrain.stack import zone_name_for
        z = str(zone_name_for(lat))
        step = self.pyramid.zones[z].pixel_m(lv[z])
        return PyramidField(self.pyramid, lat, lon, half_m, lv, step)

    def tiles_of_window(self, zd):
        """(zone, level, ix, iy) of the pyramid tiles a window's pixels lie in (every 8th pixel + last row/col)."""
        if isinstance(zd, PyramidField):
            return zd.tiles() or self.tiles_of_window(zd.window)
        inner = getattr(zd, 'inner', zd)
        H, W = inner.Z.shape
        ri = np.unique(np.r_[np.arange(0, H, 8), H - 1]); ci = np.unique(np.r_[np.arange(0, W, 8), W - 1])
        X, Y = np.meshgrid(inner.x_left + (ci + 0.5) * inner.step, inner.y_top - (ri + 0.5) * inner.step)
        la, lo = inner.inverse(X, Y)
        L = int(inner.meta['level'])
        out = set()
        self.pyramid.sample_height(la, lo, max_level={inner.meta['zone']: L}, touched=out)
        return sorted(t for t in out if t[1] == L)


def info_base(zd):
    return {'window_proj': zd.proj, 'window_nan_fraction': zd.meta.get('nan_fraction'),
            'window_source_ids': zd.meta.get('source_ids')}


def _scalar(v):
    if isinstance(v, np.ndarray):
        v = v.reshape(-1)[0] if v.size == 1 else v.tolist()
    return v.item() if isinstance(v, np.generic) else v


_DEFAULT = {}


def get_stack(prefer_pyramid=None):
    """Default: `PyramidStack` (S3's merged whole-Moon pyramid for the nominal terrain + the per-product adapter for
    members). The per-product adapter alone (`LegacyStack`) when prefer_pyramid=False, POLARIS_ANYSITE_STACK=legacy, or
    no pyramid index on disk. One instance per process and choice (tile cache and index are reused across sites).

    History: round 1 kept the adapter as default because the pyramid path lost clones/product members, changed the near
    field and could not read eq windows; R1 (round 2) resolved the three (docs/v2/PHASE_1_R1_PLAN.md)."""
    import os
    if prefer_pyramid is None:
        prefer_pyramid = os.environ.get('POLARIS_ANYSITE_STACK', 'pyramid').lower() != 'legacy'
    key = 'pyramid' if prefer_pyramid else 'legacy'
    if key in _DEFAULT:
        return _DEFAULT[key]
    st = None
    if prefer_pyramid:
        try:
            st = PyramidStack()
        except FileNotFoundError:
            st = None
    if st is None:
        key = 'legacy'
        st = _DEFAULT.get('legacy') or LegacyStack()
    _DEFAULT[key] = st
    return st
