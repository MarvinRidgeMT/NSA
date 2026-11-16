"""Product descriptions and readers for the science pyramid (S3, reader side).

S2 owns what is downloaded (tools/globe/products.py, $POLARIS_DATA/v2/manifest.jsonl). This module only says how to
read a file into the pyramid's datum and frame: metres above the 1,737,400 m sphere, MOON_ME, east-positive
longitude -180..180. Each conversion is a small pure function with its own test (tools/globe/tests/test_globe_conversions.py):

  dn_to_value       DN * scale + offset                          (PDS IMG SCALING_FACTOR / OFFSET)
  km_to_m           value * 1000                                  (SLDEM2015 and LOLA *_FLOAT.IMG are in km)
  radius_to_height  value - 1,737,400                             (products that store radius)
  rebase_sphere     h' + R' - 1,737,400                           (heights above a different reference sphere)
  wrap_lon_360      lon mod 360 for 0..360 products               (sampling only; pixels are never shifted)
  pa_to_me          DE421 principal-axis -> mean-Earth rotation   (only for products that declare PA)

Readers sample a product at arbitrary (lat, lon) points for a target pixel size: the native grid is block-averaged by
the integer factor floor(target / native) (aligned to the product's own pixel grid, >= 50 % valid per block) and then
sampled bilinearly (NaN propagates). They never return values on a grid finer than the product's native posting.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np

R = 1_737_400.0
REPO = Path(__file__).resolve().parents[2]


def polaris_data():
    return Path(os.environ.get('POLARIS_DATA') or (REPO / 'data' / 'cache'))


# ------------------------------------------------------------------------------------------ conversions
def dn_to_value(dn, scale=1.0, offset=0.0):
    return np.asarray(dn, dtype=np.float64) * float(scale) + float(offset)


def km_to_m(v):
    return np.asarray(v, dtype=np.float64) * 1000.0


def radius_to_height(radius_m):
    return np.asarray(radius_m, dtype=np.float64) - R


def rebase_sphere(h_m, ref_radius_m):
    """Height above a sphere of radius ref_radius_m -> height above the 1,737,400 m sphere."""
    return np.asarray(h_m, dtype=np.float64) + (float(ref_radius_m) - R)


def wrap_lon_360(lon):
    return np.mod(np.asarray(lon, dtype=np.float64), 360.0)


def wrap_lon_180(lon):
    return (np.asarray(lon, dtype=np.float64) + 180.0) % 360.0 - 180.0


# DE421 PA -> ME rotation (Williams et al. 2008, "DE421 Lunar Orbit, Physical Librations, and Surface Coordinates",
# JPL IOM 335-JW,DB,WF-20080314-001): r_ME = Rx(-0.30") Ry(-78.56") Rz(-67.92") r_PA. SOURCE-BASED, not used by any
# product ingested so far (all are MOON_ME); kept so a PA product cannot be merged silently.
PA_TO_ME_ARCSEC = (67.92, 78.56, 0.30)


def _rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, s], [0, -s, c]])


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])


def pa_to_me_matrix():
    z, y, x = (math.radians(a / 3600.0) for a in PA_TO_ME_ARCSEC)
    return _rx(-x) @ _ry(-y) @ _rz(-z)


def pa_to_me(lat, lon, inverse=False):
    """Rotate planetocentric lat/lon (deg) from the PA to the ME frame (inverse=True: ME -> PA)."""
    M = pa_to_me_matrix()
    if inverse:
        M = M.T
    la = np.radians(np.asarray(lat, dtype=float)); lo = np.radians(np.asarray(lon, dtype=float))
    v = np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], axis=-1)
    w = v @ M.T
    return np.degrees(np.arcsin(np.clip(w[..., 2], -1, 1))), np.degrees(np.arctan2(w[..., 1], w[..., 0]))


# ------------------------------------------------------------------------------------------ product spec
@dataclass
class ProductSpec:
    product_id: str
    source_id: int                  # docs/v2/SOURCE_IDS.json; lower = higher merge priority (contract §6)
    path: str                       # absolute, or relative to $POLARIS_DATA
    native_res_m: float             # nominal posting (larger axis), metres
    units: str = 'm'                # 'm' | 'km'
    datum: str = 'height'           # 'height' (above ref_radius_m) | 'radius'
    ref_radius_m: float = R
    scale: float | None = None      # None -> from the file (GDAL scale), default 1
    offset: float | None = None     # None -> from the file (GDAL offset), default 0
    frame: str = 'ME'               # 'ME' | 'PA'
    nodata: float | None = None     # None -> from the file
    version: str = ''
    url: str = ''
    sha256: str = ''
    notes: str = ''
    coreg: dict = field(default_factory=dict)   # {'dx','dy' (product CRS units), 'dz' (m), 'applied': bool, ...}
    edge_trim_px: int = 0           # native pixels at the grid edge treated as no data (gridding boundary effects)

    @property
    def abspath(self):
        p = Path(self.path)
        return p if p.is_absolute() else polaris_data() / p

    @property
    def priority(self):
        # contract order equals source_id order; finer first within one source_id; product_id breaks ties
        # (e.g. two overlapping PGDA 78 tiles) so the merge does not depend on the order products are listed
        return (self.source_id, self.native_res_m, self.product_id)

    def to_json(self):
        d = asdict(self)
        d['path'] = str(self.path)
        return d


def convert_values(raw, spec, file_scale=1.0, file_offset=0.0):
    """Raw file values -> metres above the 1,737,400 m sphere (the order is fixed: DN -> units -> datum)."""
    s = spec.scale if spec.scale is not None else (file_scale if file_scale is not None else 1.0)
    o = spec.offset if spec.offset is not None else (file_offset if file_offset is not None else 0.0)
    v = dn_to_value(raw, s, o)
    if spec.units == 'km':
        v = km_to_m(v)
    elif spec.units != 'm':
        raise ValueError(f'unknown units {spec.units}')
    if spec.datum == 'radius':
        v = radius_to_height(v)
    elif spec.datum == 'height':
        v = rebase_sphere(v, spec.ref_radius_m)
    else:
        raise ValueError(f'unknown datum {spec.datum}')
    return v


# ------------------------------------------------------------------------------------------ reader
class ProductReader:
    """Point sampler for one product file at a target pixel size."""

    def __init__(self, spec: ProductSpec):
        import rasterio
        self.spec = spec
        self.ds = rasterio.open(spec.abspath)
        t = self.ds.transform
        if t.b or t.d:
            raise ValueError(f'{spec.product_id}: rotated grids unsupported')
        self.px_x, self.px_y = abs(t.a), abs(t.e)
        self.left, self.top = t.c, t.f
        self.h, self.w = self.ds.height, self.ds.width
        self.kind, self.params = classify_crs(self.ds.crs)
        self.crs_kind = self.kind
        self.file_scale = (self.ds.scales or [1.0])[0]
        self.file_offset = (self.ds.offsets or [0.0])[0]
        self.nodata = spec.nodata if spec.nodata is not None else self.ds.nodata
        if self.kind == 'eqc':
            # Re-express an equirectangular-metres grid (GDAL's view of PDS SIMPLE CYLINDRICAL) as an exact lon/lat
            # grid: GDAL derives the metre transform from a rounded MAP_SCALE (e.g. 236.901 m for 128 ppd), so the
            # degree grid is rebuilt from the pixel counts (global products: exactly 360 / width deg per pixel).
            if abs(self.params['lat_ts']) > 1e-9:
                raise ValueError('eqc with lat_ts != 0 unsupported')
            lon_left = self.params['lon_0'] + math.degrees(self.left / R)
            lon_right = self.params['lon_0'] + math.degrees((self.left + self.w * self.px_x) / R)
            lat_top = math.degrees(self.top / R)
            lat_bot = math.degrees((self.top - self.h * self.px_y) / R)
            if abs((lon_right - lon_left) - 360.0) < 0.01:
                lon_left = round(lon_left, 4); self.px_x = 360.0 / self.w
            else:
                self.px_x = (lon_right - lon_left) / self.w
            if abs(lat_top - 90.0) < 0.01 and abs(lat_bot + 90.0) < 0.01:
                lat_top = 90.0; self.px_y = 180.0 / self.h
            else:
                self.px_y = (lat_top - lat_bot) / self.h
            self.left, self.top, self.kind = lon_left, lat_top, 'lonlat'
        # longitude convention of lon/lat grids
        self.lon360 = False
        self.global_lon = False
        if self.kind == 'lonlat':
            lon_left = self.left
            lon_right = self.left + self.w * self.px_x
            self.lon360 = lon_right > 180.0 + 1e-6
            self.global_lon = abs((lon_right - lon_left) - 360.0) < 1e-6
        self._cache = {}

    def close(self):
        self.ds.close()

    # -- projection to the product grid
    def _x_to_lon(self, x):
        if self.kind == 'lonlat':
            return x
        return self.params['lon_0'] + np.degrees(np.asarray(x) / (R * math.cos(math.radians(self.params['lat_ts']))))

    def to_grid(self, lat, lon):
        lat = np.asarray(lat, dtype=float); lon = np.asarray(lon, dtype=float)
        if self.spec.frame == 'PA':
            lat, lon = pa_to_me(lat, lon, inverse=True)   # pyramid points are ME; the file is PA
        elif self.spec.frame != 'ME':
            raise ValueError(f'unknown frame {self.spec.frame}')
        k = self.kind
        if k == 'sp':
            rho = 2 * R * np.tan(np.pi / 4 + np.radians(lat) / 2)
            return rho * np.sin(np.radians(lon)), rho * np.cos(np.radians(lon))
        if k == 'np':
            rho = 2 * R * np.tan(np.pi / 4 - np.radians(lat) / 2)
            return rho * np.sin(np.radians(lon)), -rho * np.cos(np.radians(lon))
        if k == 'lonlat':
            # longitude into [left, left + 360): 0..360 and -180..180 products alike, never by shifting pixels
            return self.left + np.mod(lon - self.left, 360.0), lat
        raise ValueError(f'unsupported CRS kind {k}')

    def native_px_m(self):
        """Nominal native pixel (larger axis) in metres."""
        if self.kind == 'lonlat':
            return R * math.radians(max(self.px_x, self.px_y))
        return max(self.px_x, self.px_y)

    def native_res_at(self, lat):
        """Native horizontal resolution (m) at each point: polar grids divide by the stereographic scale; lon/lat grids
        report the latitude-direction posting (the larger axis)."""
        lat = np.asarray(lat, dtype=float)
        if self.kind in ('sp', 'np'):
            return self.native_px_m() * (1.0 + np.sin(np.radians(np.abs(lat)))) / 2.0
        if self.kind == 'lonlat':
            return np.full(lat.shape, R * math.radians(self.px_y))
        return np.full(lat.shape, self.px_y)

    # -- raw reads
    def read_block(self, r0, c0, nr, nc, k=1):
        """Converted heights for native rows r0..r0+nr, cols c0..c0+nc (clipped; NaN outside), block-averaged by k
        (blocks aligned to multiples of k in native pixel indices; caller passes aligned r0/c0/nr/nc)."""
        from rasterio.windows import Window
        out = np.full((nr // k, nc // k), np.nan)
        cc0, cc1 = max(0, c0), min(self.w, c0 + nc)
        if cc1 <= cc0:
            return out
        # native rows per strip: multiple of k, aligned to r0, <= ~32 M values (256 MB float64) per strip
        strip = max(1, min(2048, (1 << 25) // max(nc, 1)) // k) * k
        for a in range(r0, r0 + nr, strip):
            b = min(r0 + nr, a + strip)
            ra, rb = max(a, 0), min(b, self.h)
            buf = np.full((b - a, nc), np.nan)
            if rb > ra:
                raw = self.ds.read(1, window=Window(cc0, ra, cc1 - cc0, rb - ra)).astype(np.float64)
                if self.nodata is not None and not np.isnan(self.nodata):
                    raw[raw == self.nodata] = np.nan
                v = convert_values(raw, self.spec, self.file_scale, self.file_offset)
                v[np.abs(v) > 20000.0] = np.nan          # physical-range screen (science.dem.read_window)
                buf[ra - a:rb - a, cc0 - c0:cc1 - c0] = v
            out[(a - r0) // k:(b - r0) // k] = block_mean(buf, k) if k > 1 else buf
        return out

    def sample(self, lat, lon, target_px_m, fill_gaps=True):
        """Heights (m), quality flag (1 gap-filled, 2 native) and native res (m) at points, for a target pixel size.
        The product grid is block-averaged by k = floor(target / native) first; NaN outside the product."""
        lat = np.asarray(lat, dtype=float); lon = np.asarray(lon, dtype=float)
        x, y = self.to_grid(lat, lon)
        cg = self.spec.coreg or {}
        if cg.get('applied'):
            x = x + cg.get('dx', 0.0); y = y + cg.get('dy', 0.0)
        k = max(1, int(math.floor(target_px_m / self.native_px_m() * 1.0001)))
        c = (x - self.left) / self.px_x
        r = (self.top - y) / self.px_y
        fin = np.isfinite(c) & np.isfinite(r)
        H = np.full(lat.shape, np.nan); Q = np.zeros(lat.shape, np.uint8)
        if not fin.any():
            return H, Q, self.native_res_at(lat)
        # window in native pixels, aligned to k, padded for bilinear + gap fill
        pad = 3 * k
        cmin = int(math.floor(np.nanmin(c[fin]))) - pad; cmax = int(math.ceil(np.nanmax(c[fin]))) + pad
        rmin = int(math.floor(np.nanmin(r[fin]))) - pad; rmax = int(math.ceil(np.nanmax(r[fin]))) + pad
        rmin = max(rmin, -pad); rmax = min(rmax, self.h + pad)
        whole = False
        if self.global_lon and (cmax - cmin) >= self.w // 2:
            cmin, cmax, whole = 0, self.w, True          # polar cap from a global lon grid: read whole rows
        elif not self.global_lon:
            cmin = max(cmin, -pad); cmax = min(cmax, self.w + pad)
        if rmax <= rmin or cmax <= cmin:
            return H, Q, self.native_res_at(lat)
        rmin = (rmin // k) * k; cmin = (cmin // k) * k
        nr = ((rmax - rmin + k - 1) // k) * k; nc = ((cmax - cmin + k - 1) // k) * k
        if self.global_lon and not whole:
            G = self._read_wrapped(rmin, cmin, nr, nc, k)
        else:
            G = self.read_block(rmin, cmin, nr, nc, k)
        filled = np.zeros(G.shape, bool)
        if fill_gaps and np.isnan(G).any():
            G, filled = fill_small_gaps(G, max_px=2)
        # bilinear on block centres
        cb = (c - cmin) / k - 0.5; rb = (r - rmin) / k - 0.5
        if whole:
            nwb = self.w // k
            cb = np.mod(cb, nwb)
            G = np.concatenate([G[:, :nwb], G[:, :1]], axis=1)          # wrap column for bilinear
            filled = np.concatenate([filled[:, :nwb], filled[:, :1]], axis=1)
        hb, fb = bilinear_nan(G, rb, cb, filled)
        t = self.spec.edge_trim_px
        if t and not self.global_lon:
            hb = np.where((c >= t) & (c <= self.w - t) & (r >= t) & (r <= self.h - t), hb, np.nan)
        if cg.get('applied'):
            hb = hb - cg.get('dz', 0.0)
        H = hb
        Q = np.where(np.isfinite(hb), np.where(fb, 1, 2), 0).astype(np.uint8)
        return H, Q, self.native_res_at(lat)

    def _read_wrapped(self, r0, c0, nr, nc, k):
        cols = np.arange(c0, c0 + nc)
        if cols.min() >= 0 and cols.max() < self.w:
            return self.read_block(r0, c0, nr, nc, k)
        # split at the wrap
        parts = []
        a = c0
        while a < c0 + nc:
            base = a % self.w
            n = min(c0 + nc - a, self.w - base)
            parts.append(self.read_block(r0, base, nr, n, 1))
            a += n
        G = np.concatenate(parts, axis=1)
        return block_mean(G, k) if k > 1 else G

    # -- footprint
    def valid_rect(self):
        """(left, bottom, right, top) of the usable grid in its own units, after the edge trim."""
        t = self.spec.edge_trim_px
        return (self.left + t * self.px_x, self.top - (self.h - t) * self.px_y,
                self.left + (self.w - t) * self.px_x, self.top - t * self.px_y)

    def footprint_latlon(self, n=200):
        """Boundary of the valid grid as lat/lon points (grid edges after the edge trim; inner nodata not traced)."""
        l, b, r, t = self.valid_rect()
        xs = np.linspace(l, r, n)
        ys = np.linspace(t, b, n)
        X = np.concatenate([xs, np.full(n, xs[-1]), xs[::-1], np.full(n, xs[0])])
        Y = np.concatenate([np.full(n, ys[0]), ys, np.full(n, ys[-1]), ys[::-1]])
        return self.grid_to_latlon(X, Y)

    def grid_to_latlon(self, x, y):
        x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
        k = self.kind
        if k in ('sp', 'np'):
            rho = np.hypot(x, y); c = 2 * np.arctan(rho / (2 * R))
            if k == 'sp':
                lat, lon = np.degrees(c - np.pi / 2), np.degrees(np.arctan2(x, y))
            else:
                lat, lon = np.degrees(np.pi / 2 - c), np.degrees(np.arctan2(x, -y))
        elif k == 'lonlat':
            lat, lon = y, wrap_lon_180(x)
        else:
            lat = np.degrees(y / R); lon = wrap_lon_180(self._x_to_lon(x))
        if self.spec.frame == 'PA':
            lat, lon = pa_to_me(lat, lon)
        return lat, lon


def classify_crs(crs):
    """Return (kind, params) for a rasterio CRS: 'sp' / 'np' (polar stereographic on the 1,737,400 m sphere),
    'lonlat' (geographic on that sphere) or 'eqc' (equirectangular metres). Anything else raises."""
    from pyproj import CRS
    c = CRS.from_wkt(crs.to_wkt())
    ell = c.ellipsoid
    a = ell.semi_major_metre if ell else None
    b = ell.semi_minor_metre if ell else None
    if a is None or abs(a - R) > 1.0 or abs(b - R) > 1.0:
        raise ValueError(f'CRS is not the 1,737,400 m sphere (a={a}, b={b}); add an explicit datum conversion')
    if c.is_geographic:
        return 'lonlat', {}
    d = c.to_dict()
    proj = d.get('proj')
    if proj in ('stere', 'ups', 'sterea') or 'Polar_Stereographic' in c.to_wkt() or 'Polar Stereographic' in c.to_wkt():
        lat0 = d.get('lat_0')
        if lat0 is None:
            lat0 = -90.0 if '-90' in c.to_wkt() else 90.0
        if float(d.get('lon_0', 0.0)) != 0.0 or float(d.get('x_0', 0.0)) or float(d.get('y_0', 0.0)):
            raise ValueError(f'polar stereographic with lon_0/x_0/y_0 != 0 unsupported: {d}')
        k0 = float(d.get('k', d.get('k_0', 1.0)))
        if abs(k0 - 1.0) > 1e-12 or abs(abs(float(d.get('lat_ts', lat0))) - 90.0) > 1e-9:
            raise ValueError(f'polar stereographic not true-scale at the pole: {d}')
        return ('sp' if float(lat0) < 0 else 'np'), {}
    if proj == 'eqc':
        return 'eqc', {'lat_ts': float(d.get('lat_ts', 0.0)), 'lon_0': float(d.get('lon_0', 0.0))}
    raise ValueError(f'unsupported projection {proj}: {d}')


# ------------------------------------------------------------------------------------------ numerics
def block_mean(a, k, min_valid=0.5):
    n0, n1 = a.shape[0] // k, a.shape[1] // k
    b = a[:n0 * k, :n1 * k].reshape(n0, k, n1, k)
    valid = np.isfinite(b).sum(axis=(1, 3))
    s = np.nansum(b, axis=(1, 3))
    out = s / np.maximum(valid, 1)
    out[valid < min_valid * k * k] = np.nan
    return out


def bilinear_nan(G, r, c, flag=None):
    """Bilinear on pixel centres of G at fractional (row, col); NaN if any corner is NaN or out of range."""
    h, w = G.shape
    ok = np.isfinite(r) & np.isfinite(c) & (r >= 0) & (r <= h - 1) & (c >= 0) & (c <= w - 1)
    r = np.where(ok, r, 0.0); c = np.where(ok, c, 0.0)
    r0 = np.clip(np.floor(r).astype(np.int64), 0, max(h - 2, 0)); c0 = np.clip(np.floor(c).astype(np.int64), 0, max(w - 2, 0))
    r1 = np.minimum(r0 + 1, h - 1); c1 = np.minimum(c0 + 1, w - 1)
    a = c - c0; b = r - r0
    z = ((1 - a) * (1 - b) * G[r0, c0] + a * (1 - b) * G[r0, c1] + (1 - a) * b * G[r1, c0] + a * b * G[r1, c1])
    z = np.where(ok, z, np.nan)
    f = None
    if flag is not None:
        f = flag[r0, c0] | flag[r0, c1] | flag[r1, c0] | flag[r1, c1]
    return z, f


def fill_small_gaps(G, max_px=2):
    """Fill NaN holes whose bounding box is <= max_px x max_px pixels with the mean of their valid 8-neighbours
    (iterated). Larger holes stay NaN (contract: never filled). Returns (filled array, mask of filled pixels)."""
    from scipy import ndimage
    nan = np.isnan(G)
    if not nan.any():
        return G, np.zeros(G.shape, bool)
    lab, n = ndimage.label(nan, structure=np.ones((3, 3)))
    sl = ndimage.find_objects(lab)
    small = np.zeros(n + 1, bool)
    for i, s in enumerate(sl, start=1):
        if s is None:
            continue
        hh = s[0].stop - s[0].start; ww = s[1].stop - s[1].start
        touches = s[0].start == 0 or s[1].start == 0 or s[0].stop == G.shape[0] or s[1].stop == G.shape[1]
        small[i] = hh <= max_px and ww <= max_px and not touches
    target = small[lab]
    out = G.copy()
    todo = target.copy()
    for _ in range(max_px + 1):
        if not todo.any():
            break
        v = np.where(np.isnan(out), 0.0, out); m = np.isfinite(out).astype(float)
        k = np.ones((3, 3))
        s = ndimage.convolve(v, k, mode='constant'); c = ndimage.convolve(m, k, mode='constant')
        can = todo & (c > 0)
        out[can] = s[can] / c[can]
        todo &= ~can
    return out, target & np.isfinite(out)


def sha256_file(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


# ------------------------------------------------------------------------------------------ product registry
def local_products():
    """Products already on disk before S2's manifest (paths relative to the repo's data/ symlinks)."""
    ext = REPO / 'data' / 'external'
    out = []
    p90 = ext / 'pgda90' / 'LDEM_80S_80MPP_ADJ.TIF'
    if p90.exists():
        out.append(ProductSpec('pgda90_ldem_80s_80m', 5, str(p90), 80.0, version='LDEM_80S_80MPP_ADJ (PGDA 90)',
                               url='https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF',
                               sha256='82030dcbdd7c4bb0c7d858e9b4b293b9f2cda5a543ba31ec0f42784bd6beee5a',
                               notes='heights above 1737.4 km sphere (m), south polar stereographic, float32, NaN nodata'))
    for site in ('Site01', 'Site04', 'Site07', 'Site11', 'Site20', 'Site23'):
        for base in (ext / 'pgda78' / site, REPO / 'data' / 'cache' / 'p78'):
            f = base / f'{site}_final_adj_5mpp_surf.tif'
            if f.exists():
                out.append(ProductSpec(f'pgda78_{site.lower()}_5m', 3, str(f), 5.0,
                                       version=f'{site}_final_adj_5mpp_surf (PGDA 78, Barker et al. 2021)',
                                       url=f'https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/{site}/{site}_final_adj_5mpp_surf.tif',
                                       notes='heights above 1737.4 km sphere (m), south polar stereographic, float32'))
                break
    return out


def manifest_products(manifest=None):
    """Products announced in S2's $POLARIS_DATA/v2/manifest.jsonl that S3 knows how to read (see KNOWN_PRODUCTS).
    Unknown product ids are returned in the second list so they can be reported, never guessed."""
    manifest = Path(manifest) if manifest else polaris_data() / 'v2' / 'manifest.jsonl'
    if not manifest.exists():
        return [], []
    specs, unknown = [], []
    for line in manifest.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        lp = e.get('local_path', '')
        fn = Path(lp).name.upper()
        mk = KNOWN_PRODUCTS.get(e.get('product_id'))
        if mk is None:
            unknown.append(e.get('product_id'))
            continue
        try:
            spec = mk(e, fn)
        except ValueError as err:                 # label does not match the reader: report, never guess
            unknown.append(f"{e.get('product_id')}:{Path(lp).name} ({err})")
            continue
        if spec is not None:
            specs.append(spec)
    specs = _mosaic_tiled(specs)
    return specs, sorted(set(u for u in unknown if u))


# Products published as tiles of one grid are merged as ONE product through a GDAL VRT mosaic, so adjacent tiles
# are not feathered against each other and bilinear sampling across a tile boundary sees both sides.
TILED_PRODUCTS = {'sldem2015_512'}


def _mosaic_tiled(specs):
    out, groups = [], {}
    for s in specs:
        base = s.product_id.split('__')[0]
        if base in TILED_PRODUCTS:
            groups.setdefault(base, []).append(s)
        else:
            out.append(s)
    for base, ss in groups.items():
        vrt = polaris_data() / 'v2' / 'vrt' / f'{base}.vrt'           # outside the pyramid (atomic rebuilds swap it)
        write_vrt_mosaic([x.abspath for x in ss], vrt)
        s0 = ss[0]
        out.append(ProductSpec(base, s0.source_id, str(vrt), s0.native_res_m, units=s0.units, datum=s0.datum,
                               ref_radius_m=s0.ref_radius_m, scale=s0.scale, offset=s0.offset, frame=s0.frame,
                               version=f'{len(ss)} tiles: ' + s0.version, url=s0.url.rsplit('/', 1)[0] + '/',
                               sha256='; '.join(x.sha256[:12] for x in ss),
                               notes=f'VRT mosaic of {len(ss)} tiles ({vrt.name}); ' + s0.notes))
    return out


def write_vrt_mosaic(paths, out):
    """VRT mosaic of north-up rasters that share CRS and pixel size (each tile placed by its own geotransform)."""
    import rasterio
    from xml.sax.saxutils import escape
    out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    info = []
    for p in paths:
        with rasterio.open(p) as ds:
            info.append((str(p), ds.transform, ds.width, ds.height, ds.crs.to_wkt(), ds.nodata, ds.dtypes[0]))
    t0 = info[0][1]
    px, py = t0.a, -t0.e
    for _, t, *_ in info:
        if abs(t.a - px) > 1e-9 * abs(px) or abs(-t.e - py) > 1e-9 * abs(py):
            raise ValueError('tiles do not share a pixel size')
    left = min(t.c for _, t, *_ in info); top = max(t.f for _, t, *_ in info)
    right = max(t.c + w * px for _, t, w, *_ in info); bottom = min(t.f - h * py for _, t, _, h, *_ in info)
    W = int(round((right - left) / px)); H = int(round((top - bottom) / py))
    dt = {'float32': 'Float32', 'int16': 'Int16', 'uint16': 'UInt16', 'float64': 'Float64'}[info[0][6]]
    nod = info[0][5]
    src = []
    for p, t, w, h, *_ in info:
        xo = int(round((t.c - left) / px)); yo = int(round((top - t.f) / py))
        src.append(f'<SimpleSource><SourceFilename relativeToVRT="0">{escape(p)}</SourceFilename><SourceBand>1</SourceBand>'
                   f'<SrcRect xOff="0" yOff="0" xSize="{w}" ySize="{h}"/><DstRect xOff="{xo}" yOff="{yo}" xSize="{w}" ySize="{h}"/>'
                   f'</SimpleSource>')
    xml = (f'<VRTDataset rasterXSize="{W}" rasterYSize="{H}"><SRS>{escape(info[0][4])}</SRS>'
           f'<GeoTransform>{left!r}, {px!r}, 0, {top!r}, 0, {-py!r}</GeoTransform>'
           f'<VRTRasterBand dataType="{dt}" band="1">' + (f'<NoDataValue>{nod!r}</NoDataValue>' if nod is not None else '')
           + ''.join(src) + '</VRTRasterBand></VRTDataset>')
    out.write_text(xml)
    return out


def parse_pds3_label(path):
    """Flat KEY = value map of a PDS3 label (first occurrence wins; units in <..> and quotes stripped)."""
    import re
    out = {}
    for line in Path(path).read_text(errors='replace').splitlines():
        m = re.match(r'\s*\^?([A-Z_][A-Z0-9_:]*)\s*=\s*(.*?)\s*$', line)
        if not m:
            continue
        k, v = m.group(1), m.group(2)
        v = re.sub(r'<[^>]*>', '', v).strip().strip('"').strip("'").strip()
        out.setdefault(k, v)
    return out


def _f(v):
    return float(str(v).split()[0])


# Measured 16 Nov (S3): next to the square edge of the LOLA polar LDEMs the gridded surface departs from the
# neighbouring product (p99 |diff| by distance from the edge, 80N 20 m vs 75N 30 m: 52 m at 10 m, 25 m at 150 m, 6 m
# at 400 m, 1.7 m at 800 m = interior level; 75N 30 m: back to interior by 800-1200 m; 5 m and 10 m grids by ~150 m).
# A gridding boundary effect, scaling with the posting: the outer 40 native pixels are treated as no data.
LOLA_POLAR_EDGE_TRIM_PX = 40


def lola_pds_spec(entry, source_id_polar=7, source_id_global=8, id_sep='_'):
    """LOLA GDR LDEM *_FLOAT.IMG (PDS3 label next to it). Checks the label before accepting: PC_REAL km heights
    relative to 1737.4 km (DN * 1, the label's OFFSET 1737.4 is the radius of the reference sphere and is NOT added:
    we store height above that sphere), 1737.4 km sphere, MEAN EARTH/POLAR AXIS frame. Returns None if the file is
    incomplete (size differs from the manifest) or the label does not match."""
    lp = entry.get('local_path', '')
    if not lp.lower().endswith('.img') or 'quality' in Path(lp).name.lower():
        return None                               # labels, XML, and non-height layers (SLDEM data-quality map)
    img = polaris_data() / lp
    lbl = img.with_suffix('.lbl')
    if not lbl.exists():
        lbl = img.with_suffix('.LBL')
    if not img.exists() or not lbl.exists():
        return None
    if entry.get('bytes') is not None and img.stat().st_size != int(entry['bytes']):
        return None
    L = parse_pds3_label(lbl)
    problems = []
    if L.get('UNIT', '').upper() != 'KILOMETER':
        problems.append(f"UNIT {L.get('UNIT')}")
    if abs(_f(L.get('SCALING_FACTOR', '1')) - 1.0) > 1e-12:
        problems.append('SCALING_FACTOR')
    if abs(_f(L.get('OFFSET', '0')) - 1737.4) > 1e-9:
        problems.append(f"OFFSET {L.get('OFFSET')}")
    for ax in ('A_AXIS_RADIUS', 'B_AXIS_RADIUS', 'C_AXIS_RADIUS'):
        if abs(_f(L.get(ax, '0')) - 1737.4) > 1e-9:
            problems.append(ax)
    if 'MEAN EARTH' not in L.get('COORDINATE_SYSTEM_NAME', '').upper():
        problems.append(f"frame {L.get('COORDINATE_SYSTEM_NAME')}")
    if L.get('SAMPLE_TYPE', '').upper() not in ('PC_REAL',):
        problems.append(f"SAMPLE_TYPE {L.get('SAMPLE_TYPE')}")
    if problems:
        raise ValueError(f'{lbl}: label does not match the LOLA LDEM reader: {problems}')
    polar = 'POLAR' in L.get('MAP_PROJECTION_TYPE', '').upper()
    if polar:
        native = _f(L['MAP_SCALE'])
    else:
        native = R * math.radians(1.0 / _f(L['MAP_RESOLUTION']))
    pid = L.get('PRODUCT_ID', img.stem).lower()
    return ProductSpec(f"{entry['product_id']}{id_sep}{pid}", source_id_polar if polar else source_id_global, str(lbl), native,
                       units='km', datum='height', scale=1.0, offset=0.0, frame='ME',
                       edge_trim_px=LOLA_POLAR_EDGE_TRIM_PX if polar else 0,
                       version=f"{L.get('PRODUCT_ID')} {L.get('PRODUCT_VERSION_ID', '')} ({entry.get('product_version', '')})",
                       url=entry.get('url', ''), sha256=entry.get('sha256', ''),
                       notes=f"{L.get('MAP_PROJECTION_TYPE')}, {L.get('MINIMUM_LATITUDE')}..{L.get('MAXIMUM_LATITUDE')} deg, "
                             f"height km rel. 1737.4 km sphere, {L.get('COORDINATE_SYSTEM_NAME')}")


# product_id -> builder(entry, FILENAME) -> ProductSpec | None. Filled in as S2's products appear (their labels read
# first; nothing here is guessed from a file name alone without the label).
KNOWN_PRODUCTS = {
    'lola_ldem_global': lambda e, fn: lola_pds_spec(e),
    'lola_ldem_polar': lambda e, fn: lola_pds_spec(e),
    # SLDEM2015 512 ppd float tiles: same PDS3 layout (km rel. 1737.4 km, ME); merged as one VRT mosaic (source 6)
    'sldem2015_512': lambda e, fn: lola_pds_spec(e, source_id_global=6, id_sep='__'),
}


def all_products(manifest=None):
    """Local + manifest products, priority-sorted. Of the LOLA global LDEM only the finest complete file is kept
    (the coarser files are the same altimetry gridded coarser; block-averaging the finest gives the coarse levels)."""
    specs = local_products()
    m, _ = manifest_products(manifest)
    have = {s.product_id for s in specs}
    specs += [s for s in m if s.product_id not in have]
    glob_ = [s for s in specs if s.source_id == 8]
    if len(glob_) > 1:
        keep = min(glob_, key=lambda s: s.native_res_m)
        specs = [s for s in specs if s.source_id != 8 or s is keep]
    return sorted(specs, key=lambda s: s.priority)
