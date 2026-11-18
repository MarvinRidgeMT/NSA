"""Terrain / albedo packs for the Blender v2 scenes. Runs in the PROJECT venv (Blender's Python has no rasterio), reads the S3
pyramid through science.terrain.stack (TERRAIN_STACK_CONTRACT.md §5) and the LROC WAC mosaic, writes plain npy + JSON that
blender/v2/build_scene.py and blender/v2/globe.py load. Nothing here changes a number: windows are what TerrainStack returns.

    .venv/bin/python blender/v2/pack.py site  --lat 26.13239 --lon 3.6333 [--near-half 25000] [--far-half 290000] [--skyline]
    .venv/bin/python blender/v2/pack.py globe [--faces 384,192] [--supersample 3] [--texture 1024]

Output root: $POLARIS_DATA/v2/blender/packs/ (git-ignored cache; default data/cache/v2/blender/packs). A site pack is named by a
hash of its request + the pyramid index, so a rebuilt pyramid gives a new pack.

Site pack levels (finest first; the scene builder draws the finer one wherever it has a node):
  near : stack.window(lat, lon, near_half, res=None -> native step at the site, fill_coarser=True)
  far  : stack.window(lat, lon, far_half, 80 m, fill_coarser=True); for the eq zone (local oblique stereographic grid, 7 250^2
         nodes) the same computation is done in row chunks (identical arithmetic to window(): oblique_stereo_inverse ->
         TerrainStack._query at the window's level, then the fill from coarser levels) to bound memory; a test checks equality.
Filled pixels (no data at that level; bilinear from a coarser level, as the contract allows with fill_coarser) are counted.
--skyline also writes the reference skyline of the pack: science.skyline.compute_skyline (the solver's function) on the same
two windows, with the solver's any-site settings (720 bins, ray step native/5, range 280 km). Windows in the 'local-stere' or
'np' grid are wrapped so compute_skyline can sample them at south-polar grid coordinates (frames.stereo_inverse ->
window.forward -> window.sample), the role SPView plays in science/anysite for product CRSs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent))

from v2 import cubesphere  # noqa: E402

WAC_MOSAIC = 'v2/products/lroc_wac_100m/Lunar_LRO_LROC-WAC_Mosaic_global_100m_June2013.tif'
WAC_CREDIT = ('LROC WAC global morphologic mosaic 100 m (June 2013): NASA/GSFC/Arizona State University (LROC SOC); '
              'distributed by USGS Astrogeology. Speyerer et al. 2011 (LPSC 42, 2387); Wagner et al. 2015 (LPSC 46, 1473).')
SOLVER_RANGE_M = 280_000.0       # science/anysite/solve.py BASE_RANGE_M (every existing bundle)
STEP_DIVISOR = 5.0               # science/anysite/solve.py: ray step = native / 5


def data_root():
    return Path(os.environ.get('POLARIS_DATA') or (ROOT / 'data' / 'cache'))


def packs_root():
    return data_root() / 'v2' / 'blender' / 'packs'


def sha256_file(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


def script_hashes():
    return {p.name: sha256_file(p) for p in sorted(HERE.glob('*.py'))}


def _save(dir_, name, a):
    p = dir_ / name
    np.save(p, a)
    return {'file': name, 'sha256': sha256_file(p), 'bytes': p.stat().st_size}


# ------------------------------------------------------------------------------------------------ site windows
def eq_window_chunked(stack, lat0, lon0, half_m, res_m, fill_coarser=True, rows_per_chunk=400):
    """TerrainStack.window() for the eq zone (proj 'local-stere'), computed in row chunks. Same arithmetic as window():
    n = ceil(2 half / step), x_left = -n step / 2, pixel centres -> oblique_stereo_inverse -> _query at level L; NaN filled
    from all levels when fill_coarser. Returns a ZoneDEM."""
    from science.terrain.stack import ZONES, ZoneDEM, oblique_stereo_inverse, LABEL
    Z = ZONES['eq']
    lv = stack.levels('eq')
    cand = [l for l in lv if Z.pixel_m(l) <= res_m * (1 + 1e-9)]
    L = max(cand, key=lambda l: Z.pixel_m(l)) if cand else max(lv)
    step = max(float(res_m), Z.pixel_m(L))
    n = int(math.ceil(2 * half_m / step))
    x_left, y_top = -n * step / 2, n * step / 2
    xs = x_left + (np.arange(n) + 0.5) * step
    H = np.full((n, n), np.nan)
    src = np.zeros((n, n), np.uint8)
    res = np.full((n, n), np.nan, np.float32)
    filled = np.zeros((n, n), bool)
    for r0 in range(0, n, rows_per_chunk):
        r1 = min(n, r0 + rows_per_chunk)
        ys = y_top - (np.arange(r0, r1) + 0.5) * step
        X, Y = np.meshgrid(xs, ys)
        lat, lon = oblique_stereo_inverse(X, Y, lat0, lon0)
        q = stack._query(lat, lon, levels=[L])
        h = q['height'].astype(np.float64)
        s, rr = q['source_id'], q['native_res_m']
        if fill_coarser and np.isnan(h).any():
            qa = stack._query(lat, lon)
            f = np.isnan(h) & np.isfinite(qa['height'])
            h[f] = qa['height'][f]; s = np.where(f, qa['source_id'], s); rr = np.where(f, qa['native_res_m'], rr)
            filled[r0:r1] = f
        H[r0:r1], src[r0:r1], res[r0:r1] = h, s, rr
    srcs = sorted(int(v) for v in np.unique(src) if v)
    rv = res[np.isfinite(res)]
    meta = {'zone': 'eq', 'level': L, 'level_pixel_m': Z.pixel_m(L), 'res_m_requested': res_m, 'label': LABEL,
            'stack_root': str(stack.root), 'source_ids': srcs, 'native_res_m_min': float(rv.min()) if rv.size else None,
            'native_res_m_max': float(rv.max()) if rv.size else None, 'nan_fraction': float(np.isnan(H).mean()),
            'filled_from_coarser_px': int(filled.sum()), 'computed': 'pack.eq_window_chunked (= TerrainStack.window, in row chunks)',
            'crs_proj4': f'+proj=stere +lat_0={lat0} +lon_0={lon0} +k=1 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs'}
    return ZoneDEM(H, x_left=float(x_left), y_top=float(y_top), step=float(step), name=f'TerrainStack eq L{L} {step:g} m',
                   meta=meta, proj='local-stere', lat0=float(lat0), lon0=float(lon0),
                   layers={'source_id': src, 'native_res_m': res, 'quality': np.zeros((n, n), np.uint8), 'filled': filled})


def stack_window(stack, lat, lon, half_m, res_m, fill_coarser=True):
    from science.terrain.stack import zone_name_for
    if str(zone_name_for(lat)) == 'eq' and res_m is not None:
        return eq_window_chunked(stack, lat, lon, half_m, res_m, fill_coarser)
    return stack.window(lat, lon, half_m, res_m, fill_coarser=fill_coarser)


class SouthGridView:
    """A window in any pyramid grid, sampled at south-polar stereographic (x, y) as science.skyline.compute_skyline does."""

    def __init__(self, dem):
        self.inner, self.Z, self.step, self.name, self.meta = dem, dem.Z, dem.step, dem.name, dem.meta

    def sample(self, x, y):
        from science import frames
        if getattr(self.inner, 'proj', 'sp') == 'sp':
            return self.inner.sample(x, y)
        lat, lon = frames.stereo_inverse(x, y)
        u, v = self.inner.forward(lat, lon)
        return self.inner.sample(u, v)

    def digest(self):
        return self.inner.digest()


def site_pack(lat, lon, near_half=None, far_half=290_000.0, far_res=80.0, mast_m=1.0, skyline=False, out_root=None, force=False,
              site_id=None, mid_half=None, mid_res=None):
    """mid_half / mid_res (optional): a third window between near and far (e.g. +-100 km at 20 m), for the large-area
    showcase scenes; absent from the pack request when not used, so existing pack ids are unchanged."""
    from science.terrain.stack import TerrainStack
    t0 = time.time()
    lat, lon = round(float(lat), 7), round((float(lon) + 180.0) % 360.0 - 180.0, 7)   # 1e-7 deg ~ 2 cm: float noise -> same pack
    stack = TerrainStack.open(max_tiles=512)
    index_sha = sha256_file(stack.root / 'index.json')
    cov = {k: (v.item() if hasattr(v, 'item') else v) for k, v in stack.coverage(lat, lon).items()}
    native = float(cov['native_res_m'])
    if near_half is None:
        near_half = min(25_000.0, 1600 * native)
    req = {'lat': lat, 'lon': lon, 'nearHalfM': near_half, 'nearRes': 'native', 'farHalfM': far_half, 'farResM': far_res,
           'fillCoarser': True, 'pyramidIndexSha256': index_sha, 'packVersion': 1}
    if mid_half:
        req.update(midHalfM=float(mid_half), midResM=float(mid_res or 20.0))
    pid = f'site_{lat:+.5f}_{lon:+.5f}_' + hashlib.sha256(json.dumps(req, sort_keys=True).encode()).hexdigest()[:12]   # label-free
    out = Path(out_root or packs_root()) / pid
    if (out / 'pack.json').exists() and not force and (not skyline or (out / 'skyline.json').exists()):
        return out, json.loads((out / 'pack.json').read_text())
    out.mkdir(parents=True, exist_ok=True)
    near = stack_window(stack, lat, lon, near_half, None)
    t_near = time.time() - t0
    mid = stack_window(stack, lat, lon, float(mid_half), float(mid_res or 20.0)) if mid_half else None
    far = stack_window(stack, lat, lon, far_half, far_res)
    t_far = time.time() - t0 - t_near
    levels = []
    for name, d in (('near', near), ('mid', mid), ('far', far)):
        if d is None:
            continue
        f = _save(out, f'{name}.npy', np.asarray(d.Z, dtype=np.float64))
        meta = {k: v for k, v in d.meta.items() if isinstance(v, (str, int, float, list, type(None))) and k != 'crs_wkt'}
        levels.append({'name': f'{name} (S3 pyramid {d.meta.get("zone")} L{d.meta.get("level")}, {d.step:g} m)', **f,
                       'x_left': d.x_left, 'y_top': d.y_top, 'step': d.step, 'shape': list(d.Z.shape), 'proj': d.proj,
                       'lat0': d.lat0, 'lon0': d.lon0, 'meta': meta, 'digest': d.digest(), 'source': 'science.terrain.stack.TerrainStack'})
    h_site = float(near.sample_latlon(lat, lon))
    pack = {'schema': 'polaris-blender-pack-v1', 'kind': 'site', 'id': pid, 'request': req, 'site': {'lat': lat, 'lon': lon, 'id': site_id},
            'coverageAtSite': cov, 'groundHeightM': h_site, 'levels': levels, 'stackRoot': str(stack.root),
            'label': 'SOURCE-BASED · UNVALIDATED (pyramid windows as TerrainStack returns them)',
            'createdUtc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'scriptsSha256': script_hashes(),
            'timingsS': {'near': round(t_near, 1), 'far': round(t_far, 1)}}
    if skyline:
        pack['skyline'] = reference_skyline(out, near, far, lat, lon, h_site, mast_m)
    (out / 'pack.json').write_text(json.dumps(pack, indent=1))
    return out, pack


def reference_skyline(out, near, far, lat, lon, h_site, mast_m):
    from science.skyline import compute_skyline
    t = time.time()
    sk = compute_skyline(lat, lon, h_site, mast_m, near=SouthGridView(near), far=SouthGridView(far), bins=720,
                         max_range_m=SOLVER_RANGE_M, step_m=near.step / STEP_DIVISOR,
                         near_range_m=0.5 * near.step * near.Z.shape[0] - 2 * near.step, far_step_m=far.step)
    rec = {'schema': 'polaris-pack-skyline-v1', 'bins': len(sk['elevation_deg']), 'azimuth_deg': sk['azimuth_deg'],
           'elevation_deg': sk['elevation_deg'], 'critical_distance_m': [(c or {}).get('distance_m') for c in sk['critical']],
           'status': sk.get('status'), 'mast_m': mast_m, 'ground_m': h_site, 'max_range_m': SOLVER_RANGE_M,
           'method': 'science.skyline.compute_skyline on this pack\'s near + far windows (solver any-site settings: ray step native/5, '
                     '280 km); windows wrapped by pack.SouthGridView', 'seconds': round(time.time() - t, 1),
           'label': 'reference for the Blender drawing check; not a solver bundle (the any-site solver does not yet read eq '
                    'pyramid windows)'}
    (out / 'skyline.json').write_text(json.dumps(rec))
    return {'file': 'skyline.json', 'sha256': sha256_file(out / 'skyline.json'), 'seconds': rec['seconds']}


# ------------------------------------------------------------------------------------------------ globe
def wac_equirect(width=8192, out_dir=None):
    """Area-average the 100 m WAC morphologic mosaic (109 164 x 54 582, uint8, strips) onto a width x width/2 equirectangular
    grid (lon -180..180, lat 90..-90, pixel-registered). Nodata 0 excluded. Cached as npy next to the packs."""
    import rasterio
    from rasterio.windows import Window
    src = data_root() / WAC_MOSAIC
    out_dir = Path(out_dir or packs_root())
    out_dir.mkdir(parents=True, exist_ok=True)
    cache = out_dir / f'wac_morph_equirect_{width}.npy'
    if cache.exists():
        return np.load(cache), cache
    with rasterio.open(src) as ds:
        W, H = ds.width, ds.height
        hgt = width // 2
        cb = np.round(np.arange(width + 1) * W / width).astype(int)
        rb = np.round(np.arange(hgt + 1) * H / hgt).astype(int)
        acc = np.zeros((hgt, width)); cnt = np.zeros((hgt, width))
        for k in range(hgt):
            a = ds.read(1, window=Window(0, rb[k], W, rb[k + 1] - rb[k])).astype(np.float64)
            v = (a > 0)
            acc[k] = np.add.reduceat(np.where(v, a, 0).sum(axis=0), cb[:-1])
            cnt[k] = np.add.reduceat(v.sum(axis=0), cb[:-1])
    img = np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan).astype(np.float32)
    np.save(cache, img)
    return img, cache


def sample_equirect(img, lat, lon):
    """Bilinear on a pixel-registered global equirect image (row 0 = 90 N edge), periodic in longitude."""
    hgt, wid = img.shape
    fx = (np.asarray(lon) + 180.0) / 360.0 * wid - 0.5
    fy = np.clip((90.0 - np.asarray(lat)) / 180.0 * hgt - 0.5, 0, hgt - 1.000001)
    x0 = np.floor(fx).astype(int); y0 = np.floor(fy).astype(int)
    tx, ty = fx - x0, fy - y0
    x0m, x1m = x0 % wid, (x0 + 1) % wid
    y1 = np.minimum(y0 + 1, hgt - 1)
    return ((img[y0, x0m] * (1 - tx) + img[y0, x1m] * tx) * (1 - ty) + (img[y1, x0m] * (1 - tx) + img[y1, x1m] * tx) * ty)


def globe_heights(stack, n, s=3, level=0, chunk=2_000_000):
    """(6, n+1, n+1) heights: mean over s x s sub-samples in each node's footprint of the pyramid at `level` (L0 ~ 1 km;
    eq<->polar blend as the contract's sample()). NaN sub-samples are excluded; a node with none is NaN."""
    A, B = cubesphere.node_params(n)
    oa, ob = cubesphere.supersample_params(n, s)
    out = np.full((6, n + 1, n + 1), np.nan)
    stats = {'subsamples': 0, 'nanSubsamples': 0}
    for f in range(6):
        acc = np.zeros(A.shape); cnt = np.zeros(A.shape)
        for da, db in zip(oa.ravel(), ob.ravel()):
            d = cubesphere.directions(f, A + da, B + db)
            la, lo = cubesphere.latlon_deg(d)
            h = np.empty(la.size)
            fl, fo = la.ravel(), lo.ravel()
            for c0 in range(0, fl.size, chunk):
                h[c0:c0 + chunk] = stack._query_blended(fl[c0:c0 + chunk], fo[c0:c0 + chunk], levels=[level])['height']
            h = h.reshape(A.shape)
            ok = np.isfinite(h)
            acc += np.where(ok, h, 0); cnt += ok
            stats['subsamples'] += h.size; stats['nanSubsamples'] += int((~ok).sum())
        out[f] = np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan)
    stats['nanNodes'] = int(np.isnan(out).sum())
    return out, stats


def globe_pack(face_ns=(384, 192), s=3, texture=1024, out_root=None, force=False):
    from science.terrain.stack import TerrainStack
    t0 = time.time()
    stack = TerrainStack.open(max_tiles=512)
    index_sha = sha256_file(stack.root / 'index.json')
    req = {'faces': list(face_ns), 'supersample': s, 'level': 0, 'texture': texture, 'pyramidIndexSha256': index_sha, 'packVersion': 1}
    pid = 'globe_' + hashlib.sha256(json.dumps(req, sort_keys=True).encode()).hexdigest()[:12]
    out = Path(out_root or packs_root()) / pid
    if (out / 'pack.json').exists() and not force:
        return out, json.loads((out / 'pack.json').read_text())
    out.mkdir(parents=True, exist_ok=True)
    meshes = []
    for n in face_ns:
        t = time.time()
        h, st = globe_heights(stack, n, s)
        f = _save(out, f'heights_{n}.npy', h)
        smax, smin = cubesphere.node_spacing_m(n)
        meshes.append({'n': n, **f, 'stats': st, 'nodeSpacingM': [round(smin, 1), round(smax, 1)], 'seconds': round(time.time() - t, 1),
                       'hMinM': float(np.nanmin(h)), 'hMaxM': float(np.nanmax(h))})
    t = time.time()
    eq, eq_path = wac_equirect(8192, out.parent)
    A, B = cubesphere.texel_params(texture)
    tex = np.zeros((6, texture, texture), np.uint8)
    for f in range(6):
        la, lo = cubesphere.latlon_deg(cubesphere.directions(f, A, B))
        v = sample_equirect(eq, la, lo)
        tex[f] = np.clip(np.nan_to_num(v, nan=0.0), 0, 255).round().astype(np.uint8)
    tf = _save(out, f'wac_faces_{texture}.npy', tex)
    pack = {'schema': 'polaris-blender-pack-v1', 'kind': 'globe', 'id': pid, 'request': req, 'meshes': meshes,
            'heightsRule': f'mean of {s}x{s} sub-samples per node footprint of pyramid level 0 (eq 947 m, polar 1280 m), '
                           'eq<->polar blend as TerrainStack.sample; NaN sub-samples excluded, never filled',
            'texture': {**tf, 'faces': 6, 'size': texture, 'source': WAC_MOSAIC, 'credit': WAC_CREDIT,
                        'intermediate': {'file': eq_path.name, 'grid': '8192 x 4096 equirect, area-averaged from 100 m, nodata excluded'},
                        'label': 'VISUAL base colour: WAC MORPHOLOGIC mosaic, topographic shading baked in; not an albedo for photometry'},
            'stackRoot': str(stack.root), 'label': 'SOURCE-BASED · UNVALIDATED heights (pyramid L0); texture VISUAL',
            'createdUtc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'scriptsSha256': script_hashes(),
            'timingsS': {'total': round(time.time() - t0, 1), 'texture': round(time.time() - t, 1)}}
    (out / 'pack.json').write_text(json.dumps(pack, indent=1))
    return out, pack


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('site')
    s.add_argument('--lat', type=float, required=True)
    s.add_argument('--lon', type=float, required=True)
    s.add_argument('--id', default=None)
    s.add_argument('--near-half', type=float, default=None)
    s.add_argument('--far-half', type=float, default=290_000.0)
    s.add_argument('--far-res', type=float, default=80.0)
    s.add_argument('--mid-half', type=float, default=None)
    s.add_argument('--mid-res', type=float, default=None)
    s.add_argument('--mast', type=float, default=1.0)
    s.add_argument('--skyline', action='store_true')
    s.add_argument('--force', action='store_true')
    g = sub.add_parser('globe')
    g.add_argument('--faces', default='384,192')
    g.add_argument('--supersample', type=int, default=3)
    g.add_argument('--texture', type=int, default=1024)
    g.add_argument('--force', action='store_true')
    a = p.parse_args(argv)
    if a.cmd == 'site':
        out, pk = site_pack(a.lat, a.lon, a.near_half, a.far_half, a.far_res, a.mast, a.skyline, force=a.force, site_id=a.id,
                            mid_half=a.mid_half, mid_res=a.mid_res)
    else:
        out, pk = globe_pack(tuple(int(v) for v in a.faces.split(',')), a.supersample, a.texture, force=a.force)
    print(json.dumps({'pack': str(out), 'id': pk['id'], 'timingsS': pk.get('timingsS')}))


if __name__ == '__main__':
    main()
