"""Build the science terrain pyramid (v2 Phase 1, S3). Plan: docs/v2/PHASE_1_PYRAMID_PLAN.md.

    python -m tools.globe.pyramid products                 # what would be merged (local files + S2 manifest)
    python -m tools.globe.pyramid coreg                    # estimate/log co-registration vs LOLA (coreg.json)
    python -m tools.globe.pyramid build --zones sp [--max-level 8] [--workers 4]
    python -m tools.globe.pyramid index                    # rescan tiles -> index.json

Output: $POLARIS_DATA/v2/pyramid/<zone>/<level>/<ix>_<iy>.tif (COG, 4 float32 bands height, source_id, native_res_m,
quality) + index.json. Zone/level/tile geometry lives in science/terrain/stack.py (shared with the reader).

Merge (contract §6): products sorted by priority (lower source_id first; finer first within one id). Lowest priority is
laid down first; each higher-priority product is laid over with weight w = clip(d / FEATHER_PX, 0, 1), d = distance in
level pixels from that product's own valid-data edge (computed on a tile padded by FEATHER_PX + 2, so tile edges are not
seams). Where nothing lies beneath, w = 1. A product contributes as a "fine" product at a level only if the level
pixel >= its native posting / 1.01 (never upsampled); coarser products may be blending partners inside a
fine product's feather band (bilinear on their own grid), and every pixel with zero total fine weight is NaN, so no
stored pixel is purely upsampled. native_res_m in a blend = the coarsest contributor (conservative).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from science.terrain import stack as S
from tools.globe import pyramid_products as PP

FEATHER_PX = 8
PAD_PX = FEATHER_PX + 2
LABEL = 'SOURCE-BASED · UNVALIDATED'


def pyramid_root():
    return PP.polaris_data() / 'v2' / 'pyramid'


def workers_default():
    try:
        n = int(os.environ.get('CUBE_WORKERS', '4'))
    except ValueError:
        n = 4
    return max(1, min(4, n))


# ------------------------------------------------------------------------------------------- planning
_READERS = {}


def reader(spec):
    r = _READERS.get(spec.product_id)
    if r is None or r.spec is not spec:
        r = PP.ProductReader(spec)
        _READERS[spec.product_id] = r
    return r


def product_zone_bbox(spec, zone):
    """Bounding box (left, bottom, right, top) of a product's footprint in a zone's grid, or None if disjoint."""
    Z = S.ZONES[zone]
    rd = reader(spec)
    lat, lon = rd.footprint_latlon(400)
    poles = set()
    if rd.kind in ('sp', 'np'):
        vl, vb, vr, vt = rd.valid_rect()
        inside = (vl <= 0.0 <= vr) and (vb <= 0.0 <= vt)
        if inside:
            poles.add(-90.0 if rd.kind == 'sp' else 90.0)
    elif rd.kind in ('lonlat', 'eqc') and rd.global_lon:
        if float(np.max(lat)) >= 89.99:
            poles.add(90.0)
        if float(np.min(lat)) <= -89.99:
            poles.add(-90.0)
    lat_lo, lat_hi = float(np.min(lat)), float(np.max(lat))
    for p_ in poles:
        lat_lo, lat_hi = min(lat_lo, p_), max(lat_hi, p_)
    if Z.kind == 'eq':
        lo, hi = max(lat_lo, -S.EQ_MAX_ABS_LAT), min(lat_hi, S.EQ_MAX_ABS_LAT)
        if hi <= lo:
            return None
        lons = PP.wrap_lon_180(lon)
        if poles or rd.global_lon or (lons.max() - lons.min()) > 180:
            return (-180.0, lo, 180.0, hi)
        return (float(lons.min()), lo, float(lons.max()), hi)
    # polar zone
    if zone == 'sp' and lat_lo > -S.POLAR_MIN_ABS_LAT:
        return None
    if zone == 'np' and lat_hi < S.POLAR_MIN_ABS_LAT:
        return None
    rho55 = 2 * S.R * math.tan(math.radians(90 - S.POLAR_MIN_ABS_LAT) / 2)
    if (-90.0 if zone == 'sp' else 90.0) in poles and rd.kind not in ('sp', 'np'):
        # cap from a lon/lat grid: the disc down to the product's edge latitude (or 55 deg)
        # the cap reaches the product's equator-side edge, but never beyond the zone limit (|lat| = 55)
        edge = min(lat_hi, -S.POLAR_MIN_ABS_LAT) if zone == 'sp' else max(lat_lo, S.POLAR_MIN_ABS_LAT)
        rho = 2 * S.R * math.tan(math.radians(90 - abs(edge)) / 2)
        return (-rho, -rho, rho, rho)
    if rd.kind == zone:
        b = rd.valid_rect()
    else:
        m = Z.in_zone(lat) if np.any(Z.in_zone(lat)) else np.ones(lat.shape, bool)
        x, y = Z.forward(lat[m], lon[m])
        b = (float(x.min()), float(y.min()), float(x.max()), float(y.max()))
    b = (max(b[0], -rho55), max(b[1], -rho55), min(b[2], rho55), min(b[3], rho55))
    return b if b[2] > b[0] and b[3] > b[1] else None


def tiles_for_bbox(zone, level, bbox):
    Z = S.ZONES[zone]
    s = Z.pixel(level) * Z.tile_px
    nx, ny = Z.n_tiles(level)
    l, b, r, t = bbox
    ix0 = max(0, int(math.floor((l - Z.left) / s))); ix1 = min(nx - 1, int(math.floor((r - Z.left) / s - 1e-12)))
    iy0 = max(0, int(math.floor((Z.top - t) / s))); iy1 = min(ny - 1, int(math.floor((Z.top - b) / s - 1e-12)))
    return [(ix, iy) for iy in range(iy0, iy1 + 1) for ix in range(ix0, ix1 + 1)]


def plan(zone, specs, max_level=S.MAX_LEVEL, bbox=None, min_level=0):
    """{level: {(ix, iy): [product_id, ...]}} — a tile is planned at a level only if a product fine enough for that
    level overlaps it; every overlapping product (fine or coarse partner) is listed for the tile."""
    Z = S.ZONES[zone]
    boxes = {}
    for sp in specs:
        bb = product_zone_bbox(sp, zone)
        if bb is not None:
            boxes[sp.product_id] = bb
    out = {}
    for L in range(min_level, max_level + 1):
        lvl = {}
        for sp in specs:
            if sp.product_id not in boxes:
                continue
            if reader(sp).native_px_m() > Z.pixel_m(L) * 1.01:
                continue
            bb = boxes[sp.product_id]
            if bbox is not None:
                bb = (max(bb[0], bbox[0]), max(bb[1], bbox[1]), min(bb[2], bbox[2]), min(bb[3], bbox[3]))
                if bb[2] <= bb[0] or bb[3] <= bb[1]:
                    continue
            for t in tiles_for_bbox(zone, L, bb):
                lvl.setdefault(t, set())
        byid = {s.product_id: s for s in specs}
        skipped = []
        for t in lvl:
            tb = Z.tile_bounds(L, *t)
            pad = PAD_PX * Z.pixel(L)
            tb = (tb[0] - pad, tb[1] - pad, tb[2] + pad, tb[3] + pad)
            for pid, bb in boxes.items():
                if bb[0] < tb[2] and bb[2] > tb[0] and bb[1] < tb[3] and bb[3] > tb[1]:
                    lvl[t].add(pid)
            # Suppressed tile: the highest-priority product that covers the whole padded tile is too coarse for this
            # level and nothing above it is fine -> the merge would be all NaN (it overlays everything with w = 1).
            # Only for rectangular footprints in the zone's own grid kind, where the bbox IS the footprint.
            for s in sorted((byid[p] for p in lvl[t]), key=lambda s: s.priority):
                fine = reader(s).native_px_m() <= Z.pixel_m(L) * 1.01
                if fine:
                    break
                bb = boxes[s.product_id]
                own = reader(s).kind == zone or (Z.kind == 'eq' and reader(s).kind == 'lonlat')
                if own and bb[0] <= tb[0] and bb[2] >= tb[2] and bb[1] <= tb[1] and bb[3] >= tb[3]:
                    skipped.append(t)
                    break
        for t in skipped:
            del lvl[t]
        # Prune reads: below the highest-priority product that covers the whole padded tile (rectangle in the zone's
        # own grid, or a global lon/lat grid in eq), nothing can show (it is laid over with w = 1 everywhere), so the
        # lower-priority products are not read for that tile. Same output, far fewer reads near the poles.
        for t, pids in lvl.items():
            tb = Z.tile_bounds(L, *t)
            pad = PAD_PX * Z.pixel(L)
            tb = (tb[0] - pad, tb[1] - pad, tb[2] + pad, tb[3] + pad)
            keep = []
            for s in sorted((byid[p] for p in pids), key=lambda s: s.priority):
                keep.append(s.product_id)
                bb = boxes[s.product_id]
                own = reader(s).kind == zone or (Z.kind == 'eq' and reader(s).kind == 'lonlat' and reader(s).global_lon)
                if own and bb[0] <= tb[0] and bb[2] >= tb[2] and bb[1] <= tb[1] and bb[3] >= tb[3]:
                    break
            lvl[t] = set(keep)
        if lvl:
            out[L] = {t: sorted(v) for t, v in lvl.items()}
    return out


# ------------------------------------------------------------------------------------------- merge
def feather_weight(valid, feather_px=FEATHER_PX):
    """w = clip(d / F, 0, 1), d = Euclidean distance (pixels) to the nearest invalid pixel; 1 everywhere if no edge."""
    from scipy import ndimage
    if valid.all():
        return np.ones(valid.shape)
    if not valid.any():
        return np.zeros(valid.shape)
    d = ndimage.distance_transform_edt(valid)
    return np.clip(d / float(feather_px), 0.0, 1.0)


def _priority_units(specs, zone, sampler):
    """Merge units, lowest priority first: single products, or groups of overlapping-capable products of EQUAL
    priority class (same source_id and native posting, e.g. adjacent PGDA 78 site tiles) whose footprints are
    rectangles in this zone's own grid. Yields (spec, members) with members = [] for a single product."""
    out = []
    groups = {}
    for s in specs:
        groups.setdefault((s.source_id, s.native_res_m), []).append(s)
    for key in sorted(groups, reverse=True):
        mem = sorted(groups[key], key=lambda s: s.priority)
        rect = sampler is None and len(mem) > 1 and all(reader(s).kind == zone for s in mem)
        if rect:
            out.append((mem[0], mem))
        else:
            out.extend((s, []) for s in sorted(mem, key=lambda s: s.priority, reverse=True))
    return out


def _equal_priority_mosaic(members, zone, U, V, lat, lon, px_m, feather_px):
    """Equal-priority tiles: each point takes the tile whose centre is nearest (Voronoi on tile centres; d_i = minus
    the distance to centre i), blended softly across the bisector: w_i = exp((d_i - d_max) / (feather_px * px)).
    Replaces an arbitrary product-id order (16 Nov: Site01 overlapping Site04 ~320 m from Site04 RoI 3)."""
    hs, qs, rs, ws = [], [], [], []
    native = None
    for s in members:
        rd = reader(s)
        h, q, res = rd.sample(lat, lon, px_m)
        cx = rd.left + rd.w * rd.px_x / 2; cy = rd.top - rd.h * rd.px_y / 2
        d = -np.hypot(U - cx, V - cy)                 # nearer the tile centre = deeper inside it
        d = np.where(np.isfinite(h), d, -np.inf)
        hs.append(h); qs.append(q); rs.append(res); ws.append(d)
        native = rd.native_px_m()
    D = np.stack(ws)
    dmax = D.max(axis=0)
    have = np.isfinite(dmax)
    W = np.where(np.isfinite(D), np.exp(np.clip((D - np.where(have, dmax, 0)) / (feather_px * px_m), -50, 0)), 0.0)
    Hs = np.nan_to_num(np.stack(hs))
    sw = W.sum(axis=0)
    h = np.where(have, (W * Hs).sum(axis=0) / np.where(sw > 0, sw, 1), np.nan)
    k = np.argmax(D, axis=0)
    q = np.take_along_axis(np.stack(qs), k[None], 0)[0]
    res = np.take_along_axis(np.stack(rs), k[None], 0)[0]
    return h, q.astype(np.uint8), res, native


def merge_tile(zone, level, ix, iy, specs, feather_px=FEATHER_PX, pad=PAD_PX, sampler=None):
    """Merged (4, T, T) float32 array for one tile, or None if it holds no fine pixel. `sampler(spec, lat, lon,
    target_px_m) -> (h, q, res)` defaults to the product readers (tests pass synthetic samplers)."""
    Z = S.ZONES[zone]
    U, V = Z.pixel_centres(level, ix, iy, pad)
    lat, lon = Z.inverse(U, V)
    inzone = Z.in_zone(lat)
    px_m = Z.pixel_m(level)
    shape = U.shape
    H = np.full(shape, np.nan); FW = np.zeros(shape); RES = np.full(shape, np.nan)
    SRC = np.zeros(shape, np.uint8); Q = np.zeros(shape, np.uint8)
    contributed = []
    for sp, members in _priority_units(specs, zone, sampler):           # lowest priority first
        if members:
            h, q, res, native = _equal_priority_mosaic(members, zone, U, V, lat, lon, px_m, feather_px)
        elif sampler is None:
            rd = reader(sp)
            h, q, res = rd.sample(lat, lon, px_m)
            native = rd.native_px_m()
        else:
            h, q, res, native = sampler(sp, lat, lon, px_m)
        v = np.isfinite(h) & inzone
        if not v.any():
            continue
        contributed.append(sp.product_id)
        fine = 1.0 if native <= px_m * 1.01 else 0.0
        if (sp.coreg or {}).get('estimated'):
            q = np.where(q == 2, 3, q).astype(np.uint8)
        base = np.isfinite(H)
        w = np.where(base, feather_weight(v, feather_px), 1.0)
        w = np.where(v, w, 0.0)
        Hn = np.where(base, H, 0.0)
        H = np.where(v, w * np.where(v, h, 0.0) + (1 - w) * Hn, H)
        FW = np.where(v, w * fine + (1 - w) * FW, FW)
        blend = v & base & (w < 1.0)
        RES = np.where(blend, np.fmax(res, RES), np.where(v, res, RES))
        dom = v & (w >= 0.5)
        SRC = np.where(dom, sp.source_id, SRC).astype(np.uint8)
        Q = np.where(dom, q, Q).astype(np.uint8)
    keep = (FW > 1e-9) & inzone & np.isfinite(H)
    if not keep.any():
        return None, contributed
    H = np.where(keep, H, np.nan); RES = np.where(keep, RES, np.nan)
    SRC = np.where(keep, SRC, 0); Q = np.where(keep, Q, 0)
    sl = (slice(pad, pad + Z.tile_px), slice(pad, pad + Z.tile_px))
    out = np.stack([H[sl], SRC[sl], RES[sl], Q[sl]]).astype(np.float32)
    if not np.isfinite(out[0]).any():
        return None, contributed
    return out, contributed


def write_tile(path, arr, zone, level, ix, iy, sources):
    import rasterio
    from rasterio.transform import from_origin
    from rasterio.crs import CRS
    Z = S.ZONES[zone]
    l, b, r, t = Z.tile_bounds(level, ix, iy)
    p = Z.pixel(level)
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp.tif')
    blk = 256 if Z.tile_px % 256 == 0 else 240
    prof = dict(driver='COG', width=Z.tile_px, height=Z.tile_px, count=4, dtype='float32',
                crs=CRS.from_proj4(Z.proj4), transform=from_origin(l, t, p, p), nodata=float('nan'),
                compress='DEFLATE', predictor=3, blocksize=blk, overviews='NONE', BIGTIFF='NO')
    with rasterio.open(tmp, 'w', **prof) as ds:
        ds.write(arr)
        for i, n in enumerate(S.BANDS, start=1):
            ds.set_band_description(i, n)
        ds.update_tags(label=LABEL, zone=zone, level=str(level), ix=str(ix), iy=str(iy),
                       sources=','.join(str(s) for s in sources),
                       contract='docs/v2/TERRAIN_STACK_CONTRACT.md',
                       bands='height(m above 1737400 m sphere, NaN=no data),source_id(uint8 as float32),'
                             'native_res_m,quality(uint8 as float32: 0 none,1 gap<=2px,2 native,3 native+coreg)')
    os.replace(tmp, path)


def _build_batch(args):
    zone, level, tiles, specs_json, root = args
    specs = [PP.ProductSpec(**d) for d in specs_json]
    byid = {s.product_id: s for s in specs}
    done = []
    for (ix, iy), pids in tiles:
        arr, contributed = merge_tile(zone, level, ix, iy, [byid[p] for p in pids])
        path = S.tile_path(root, zone, level, ix, iy)
        if arr is None:
            if path.exists():
                path.unlink()
            continue
        srcs = sorted(int(s) for s in np.unique(arr[1]) if s > 0)
        write_tile(path, arr, zone, level, ix, iy, srcs)
        done.append((ix, iy))
    return zone, level, done


def build(zones=('sp',), max_level=S.MAX_LEVEL, workers=None, root=None, specs=None, bbox=None, log=print,
          atomic=False, min_level=0):
    """Build tiles for `zones` (all levels <= max_level) and rewrite index.json. atomic=True builds the WHOLE pyramid
    into <root>.staging and swaps it in at the end, so readers never see a half-built pyramid (zones not listed are
    not carried over: pass every zone)."""
    root = Path(root) if root else pyramid_root()
    if atomic:
        import shutil
        stage = root.with_name(root.name + '.staging')
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir(parents=True)
        if (root / 'coreg.json').exists():
            shutil.copy2(root / 'coreg.json', stage / 'coreg.json')
        n = build(zones, max_level, workers, stage, specs, bbox, log, atomic=False, min_level=min_level)
        old = root.with_name(root.name + '.old')
        if old.exists():
            shutil.rmtree(old)
        if root.exists():
            os.replace(root, old)
        os.replace(stage, root)
        shutil.rmtree(old, ignore_errors=True)
        return n
    specs = specs if specs is not None else PP.all_products()
    coreg = load_coreg(root)
    for s in specs:
        if s.product_id in coreg:
            s.coreg = coreg[s.product_id]
    workers = workers or workers_default()
    sj = [s.to_json() for s in specs]
    jobs = []
    for zone in zones:
        pl = plan(zone, specs, max_level=max_level, bbox=bbox, min_level=min_level)
        for L, tiles in sorted(pl.items()):
            items = sorted(tiles.items())
            log(f'{zone} L{L} ({S.ZONES[zone].pixel_m(L):g} m): {len(items)} tiles planned')
            nb = max(1, min(len(items), workers * 4))
            for i in range(nb):
                chunk = items[i::nb]
                if chunk:
                    jobs.append((zone, L, chunk, sj, str(root)))
    n = 0
    if workers == 1:
        for j in jobs:
            n += len(_build_batch(j)[2])
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for z, L, done in ex.map(_build_batch, jobs):
                n += len(done)
    log(f'wrote {n} tiles')
    write_index(root, specs)
    return n


# ------------------------------------------------------------------------------------------- index
def load_coreg(root):
    p = Path(root) / 'coreg.json'
    if not p.exists():
        return {}
    return {k: v for k, v in json.loads(p.read_text()).get('products', {}).items()}


def _tile_entry(args):
    zone, L, ix, iy, path, rel = args
    import rasterio
    Z = S.ZONES[zone]
    with rasterio.open(path) as ds:
        tags = ds.tags()
        h = ds.read(1)
    st = os.stat(path)
    return {'zone': zone, 'level': L, 'ix': ix, 'iy': iy, 'path': rel, 'bounds': list(Z.tile_bounds(L, ix, iy)),
            'pixel': Z.pixel(L), 'sources': [int(v) for v in tags.get('sources', '').split(',') if v],
            'valid_frac': round(float(np.isfinite(h).mean()), 6), 'sha256': PP.sha256_file(path),
            'bytes': st.st_size, 'mtime_ns': st.st_mtime_ns}


def write_index(root, specs=None, workers=None):
    """Rescan tiles -> index.json. Incremental: an entry from the previous index is reused when the file's size and
    mtime_ns are unchanged; new/changed tiles are hashed in a process pool (<= 4 workers)."""
    root = Path(root)
    prev = {}
    if (root / 'index.json').exists():
        try:
            prev = json.loads((root / 'index.json').read_text())
        except json.JSONDecodeError:
            prev = {}
    old = {t['path']: t for t in prev.get('tiles', []) if 'mtime_ns' in t}
    tiles, todo = [], []
    for zone in ('sp', 'np', 'eq'):
        zd = root / zone
        if not zd.exists():
            continue
        for ld in sorted(zd.iterdir(), key=lambda p: p.name):
            if not ld.is_dir() or not ld.name.isdigit():
                continue
            L = int(ld.name)
            for f in sorted(ld.glob('*_*.tif')):
                if f.name.endswith('.tmp.tif'):
                    continue
                ix, iy = (int(v) for v in f.stem.split('_'))
                rel = f'{zone}/{L}/{f.name}'
                o = old.get(rel)
                st = f.stat()
                if o is not None and o.get('bytes') == st.st_size and o.get('mtime_ns') == st.st_mtime_ns:
                    tiles.append(o)
                else:
                    todo.append((zone, L, ix, iy, str(f), rel))
    w = workers or workers_default()
    if todo:
        if w > 1 and len(todo) > 64:
            with ProcessPoolExecutor(max_workers=w) as ex:
                tiles += list(ex.map(_tile_entry, todo, chunksize=64))
        else:
            tiles += [_tile_entry(a) for a in todo]
    tiles.sort(key=lambda t: (t['zone'], t['level'], t['iy'], t['ix']))
    zones = {}
    for zone, Z in S.ZONES.items():
        zones[zone] = {'kind': Z.kind, 'crs_proj4': Z.proj4, 'extent_lbrt': [Z.left, Z.bottom, Z.right, Z.top],
                       'tile_px': Z.tile_px, 'grid_units': 'deg' if Z.kind == 'eq' else 'm',
                       'levels': {str(L): {'pixel': Z.pixel(L), 'pixel_m': Z.pixel_m(L), 'n_tiles': list(Z.n_tiles(L))}
                                  for L in range(S.MAX_LEVEL + 1)}}
    idx = {
        'contract': 'docs/v2/TERRAIN_STACK_CONTRACT.md', 'plan': 'docs/v2/PHASE_1_PYRAMID_PLAN.md',
        'label': LABEL, 'created_utc': _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'datum': 'metres above the 1,737,400 m sphere, MOON_ME, east-positive longitude',
        'bands': list(S.BANDS), 'band_dtype_on_disk': 'float32 (source_id, quality are exact integers; cast to uint8)',
        'feather_px': FEATHER_PX, 'zone_switch_abs_lat': S.ZONE_SWITCH_ABS_LAT,
        'zones': zones,
        'products': [s.to_json() for s in specs] if specs is not None else prev.get('products', []),
        'tiles': tiles,
    }
    tmp = root / 'index.json.tmp'
    tmp.write_text(json.dumps(idx, indent=1))
    os.replace(tmp, root / 'index.json')          # readers never see a half-written index
    return idx


# ------------------------------------------------------------------------------------------- CLI
def _parse_bbox(s):
    if not s:
        return None
    return tuple(float(v) for v in s.split(','))


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.globe.pyramid')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('products')
    b = sub.add_parser('build')
    b.add_argument('--zones', default='sp')
    b.add_argument('--max-level', type=int, default=S.MAX_LEVEL)
    b.add_argument('--min-level', type=int, default=0)
    b.add_argument('--workers', type=int, default=None)
    b.add_argument('--root', default=None)
    b.add_argument('--bbox', default=None, help='zone-grid bbox left,bottom,right,top')
    b.add_argument('--atomic', action='store_true', help='build into <root>.staging and swap in at the end')
    sub.add_parser('index').add_argument('--root', default=None)
    c = sub.add_parser('coreg')
    c.add_argument('--root', default=None)
    a = ap.parse_args(argv)
    if a.cmd == 'products':
        specs = PP.all_products()
        _, unknown = PP.manifest_products()
        for s in specs:
            rd = reader(s)
            print(f'{s.source_id:2d} {s.product_id:32s} {rd.kind:6s} {rd.native_px_m():8.2f} m  {s.abspath}')
        if unknown:
            print('manifest products not yet readable by S3:', ', '.join(unknown))
        return 0
    if a.cmd == 'build':
        build(zones=tuple(a.zones.split(',')), max_level=a.max_level, workers=a.workers, root=a.root,
              bbox=_parse_bbox(a.bbox), atomic=a.atomic, min_level=a.min_level)
        return 0
    if a.cmd == 'index':
        write_index(Path(a.root) if a.root else pyramid_root())
        return 0
    if a.cmd == 'coreg':
        from tools.globe import pyramid_coreg
        pyramid_coreg.main(Path(a.root) if a.root else pyramid_root())
        return 0
    return 1


if __name__ == '__main__':
    sys.exit(main())
