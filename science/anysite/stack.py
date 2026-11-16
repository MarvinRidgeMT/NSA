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
import math

import numpy as np

from .. import dem as demmod
from .. import frames
from . import products as P


def _to_zone(lat, lon, entry):
    if entry['zone'] == 'sp':
        return frames.stereo_forward(lat, lon)
    t = _transformer(entry['crs_wkt'])
    return t.transform(np.asarray(lon, float), np.asarray(lat, float))


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
        self.meta = {'layers': [l.name for l in layers]}
        self.Z = layers[-1].Z
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

    # -- contract §5 -------------------------------------------------------------------------------------------
    def covering(self, lat, lon):
        """Products whose footprint contains (lat, lon) with a finite height there, in priority order."""
        out = []
        for e in self.entries:
            x, y = _to_zone(lat, lon, e)
            l, b, r, t = e['bounds']
            if not (l <= float(x) <= r and b <= float(y) <= t):
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
        e = self._pick(lat0, lon0, res_m, product)
        path, name, url = e['path'], e['name'], e['url']
        if member is not None:
            c = int(member.replace('clone', ''))
            if c not in e['clones']:
                raise KeyError(f'{member} not cached for {e["id"]}')
            path = e['clones'][c]; name = name.replace('nominal', f'clone{c:04d}'); url = e['clone_url'].format(c)
        x, y = _to_zone(lat0, lon0, e)
        d = _read(path, float(x), float(y), float(half_m), name)
        d.meta.update({'source_url': url, 'file_sha256': P.file_sha256(path), 'product_id': e['id'],
                       'product': e['product'], 'zone': e['zone'], 'native_res_m': e['res_m'],
                       'citation': e.get('citation')})
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
            r, c = ds.index(x, y)
            if not (0 <= r < ds.height and 0 <= c < ds.width):
                return float('nan')
            v = float(ds.read(1, window=((r, r + 1), (c, c + 1)))[0, 0])
            if ds.nodata is not None and not math.isnan(ds.nodata) and v == ds.nodata:
                return float('nan')
            return v if abs(v) <= 20000.0 else float('nan')


@functools.lru_cache(maxsize=3)   # a far window is ~420 MB (float64); keep near + far + one spare per process
def _read_cached(path, x, y, half_m):
    return demmod.read_window(path, x, y, half_m)


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
