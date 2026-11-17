"""Cesium terrain (quantized-mesh-1.0) display tiles from the science pyramid (prompt §2.2 display formats, R2 plan §5).

DISPLAY ONLY. Heights are the REAL pyramid (bilinear, area-averaged level whose pixel is closest to the vertex spacing
without being coarser); VISUAL relief never enters these tiles. Nothing here is read by science code.

Format: quantized-mesh-1.0 (https://github.com/CesiumGS/quantized-mesh), little-endian, gzip-compressed:
  header (88 B: tile centre ECEF, min/max height, bounding sphere, horizon occlusion point), vertex data (u, v, height
  in 0..32767, zig-zag delta coded), triangle indices (high-water-mark coded), west/south/east/north edge indices,
  extension 1 (oct-encoded per-vertex normals, requested with `extensions=octvertexnormals`).
Frame: the 1,737,400 m sphere (Cesium `Ellipsoid.MOON`), MOON_ME, east-positive; ECEF x toward 0 E, z north. Heights
metres above that sphere (as the pyramid). Tiling: Cesium GeographicTilingScheme / TMS (level 0 = 2 x 1 tiles of 180 deg,
y = 0 at the south), 65 x 65 vertex grid per tile (vertex spacing 180 / 2^z / 64 deg).

Levels [decision, budget]: global 0..GLOBAL_MAX (level 8 = 0.011 deg ~ 0.33 km vertex spacing), |lat| >= 80 deg to
POLAR_MAX (level 9 ~ 0.17 km). Output git-ignored: web/public/globe/terrain/ with layer.json (Cesium) + manifest.json.

    python -m tools.globe.qmesh build [--max-level 8] [--polar-max 9] [--workers 2]
    python -m tools.globe.qmesh check     # decode a sample, edge agreement, manifest numbers
"""
from __future__ import annotations

import argparse
import datetime as _dt
import gzip
import json
import math
import os
import struct
import sys
import time
from pathlib import Path

import numpy as np

from science.terrain import stack as S

R = S.R
REPO = Path(__file__).resolve().parents[2]
OUT = REPO / 'web' / 'public' / 'globe' / 'terrain'
N = 65                        # vertices per tile side
GLOBAL_MAX = 8
POLAR_MAX = 9
POLAR_LAT = 80.0
LABEL = 'SOURCE-BASED · UNVALIDATED (display mesh of the science pyramid; real terrain only, no VISUAL relief)'


# ------------------------------------------------------------------------------------------ tiling
def tile_rect(z, x, y):
    """(west, south, east, north) degrees of TMS geographic tile (z, x, y)."""
    d = 180.0 / 2 ** z
    return -180.0 + x * d, -90.0 + y * d, -180.0 + (x + 1) * d, -90.0 + (y + 1) * d


def tiles_at(z, polar_only=False):
    nx, ny = 2 ** (z + 1), 2 ** z
    out = []
    d = 180.0 / ny
    for y in range(ny):
        s, n = -90.0 + y * d, -90.0 + (y + 1) * d
        if polar_only and not (n > POLAR_LAT or s < -POLAR_LAT):
            continue
        out += [(x, y) for x in range(nx)]
    return out


def pyramid_levels_for(z):
    """Pyramid levels to sample for tile level z: every level up to the one whose pixel is closest to (not coarser
    than... the finest not finer than) the vertex spacing, so heights are area averages at about the mesh scale."""
    sp_m = R * math.radians(180.0 / 2 ** z / (N - 1))
    def lv(zone):
        Z = S.ZONES[zone]
        L = 0
        for k in range(S.MAX_LEVEL + 1):
            if Z.pixel_m(k) >= sp_m / 1.5:
                L = k
        return L
    return {'eq': lv('eq'), 'sp': lv('sp'), 'np': lv('np')}


# ------------------------------------------------------------------------------------------ geometry helpers
def ecef(lat, lon, h):
    la, lo = np.radians(lat), np.radians(lon)
    r = R + np.asarray(h, float)
    return np.stack([r * np.cos(la) * np.cos(lo), r * np.cos(la) * np.sin(lo), r * np.sin(la)], -1)


def oct_encode(n):
    """Oct-encode unit normals (..., 3) to two uint8 (Cesium AttributeCompression.octEncode, range 255)."""
    n = n / np.linalg.norm(n, axis=-1, keepdims=True)
    s = np.abs(n).sum(-1, keepdims=True)
    p = n[..., :2] / s
    neg = n[..., 2] < 0
    px, py = p[..., 0].copy(), p[..., 1].copy()
    qx = (1 - np.abs(py)) * np.where(px >= 0, 1.0, -1.0)
    qy = (1 - np.abs(px)) * np.where(py >= 0, 1.0, -1.0)
    px = np.where(neg, qx, px); py = np.where(neg, qy, py)
    to = lambda v: np.round((np.clip(v, -1, 1) * 0.5 + 0.5) * 255.0).astype(np.uint8)
    return np.stack([to(px), to(py)], -1)


def oct_decode(e):
    x = e[..., 0].astype(float) / 255.0 * 2 - 1; y = e[..., 1].astype(float) / 255.0 * 2 - 1
    z = 1 - np.abs(x) - np.abs(y)
    neg = z < 0
    xo = np.where(neg, (1 - np.abs(y)) * np.where(x >= 0, 1, -1), x)
    yo = np.where(neg, (1 - np.abs(x)) * np.where(y >= 0, 1, -1), y)
    v = np.stack([xo, yo, z], -1)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def zigzag(v):
    v = np.asarray(v, np.int64)
    return ((v << 1) ^ (v >> 63)).astype(np.uint16)


def unzigzag(u):
    u = np.asarray(u, np.int64)
    return (u >> 1) ^ (-(u & 1))


def hwm_encode(idx):
    out = np.empty(idx.size, np.int64)
    highest = 0
    for k, i in enumerate(idx.tolist()):
        c = highest - i
        out[k] = c
        if c == 0:
            highest += 1
    return out


def hwm_decode(code):
    out = np.empty(code.size, np.int64)
    highest = 0
    for k, c in enumerate(code.tolist()):
        out[k] = highest - c
        if c == 0:
            highest += 1
    return out


def occlusion_point(pos, centre):
    """Cesium EllipsoidalOccluder.computeHorizonCullingPointFromVertices on a sphere (scaled space = / R)."""
    p = pos / R
    dvec = centre / R
    dn = dvec / np.linalg.norm(dvec)
    mag2 = (p * p).sum(-1); mag = np.sqrt(mag2)
    d = p / mag[:, None]
    mag2 = np.maximum(1.0, mag2); mag = np.maximum(1.0, mag)
    cos_a = d @ dn
    sin_a = np.linalg.norm(np.cross(d, dn), axis=-1)
    cos_b = 1.0 / mag
    sin_b = np.sqrt(mag2 - 1.0) * cos_b
    den = cos_a * cos_b - sin_a * sin_b
    if np.any(den <= 0):
        return dn * 1e3 * R                               # no finite point: never occlusion-culled (conservative)
    return dn * float((1.0 / den).max()) * R


# ------------------------------------------------------------------------------------------ grid triangulation (fixed)
def _grid_topology():
    """Triangle indices of the N x N grid in an order that makes high-water-mark coding valid (vertices renumbered
    by first use) and the permutation from grid order to stored order."""
    g = np.arange(N * N).reshape(N, N)      # row j (south->north), column i (west->east)
    tris = []
    for j in range(N - 1):
        for i in range(N - 1):
            a, b, c, d = g[j, i], g[j, i + 1], g[j + 1, i], g[j + 1, i + 1]
            tris += [a, b, c, b, d, c]
    tris = np.array(tris)
    order = []
    seen = np.full(N * N, -1)
    for v in tris:
        if seen[v] < 0:
            seen[v] = len(order); order.append(v)
    order = np.array(order)
    return seen[tris], order, seen


TRIS, ORDER, NEWIDX = _grid_topology()
_TRI_CODE = hwm_encode(TRIS).astype(np.uint16)


def encode(lat_grid, lon_grid, h, rect):
    """Bytes (uncompressed) of one tile from an N x N grid (row 0 = south) of heights h (m) and a (N+2)^2 apron grid
    for normals: h is (N+2, N+2) with a one-vertex apron."""
    w, s, e, n = rect
    hc = h[1:-1, 1:-1]
    hc = np.where(np.isfinite(hc), hc, 0.0)
    ha = np.where(np.isfinite(h), h, 0.0)
    hmin, hmax = float(hc.min()), float(hc.max())
    if hmax - hmin < 1e-3:
        hmax = hmin + 1e-3
    lat_c, lon_c = lat_grid[1:-1, 1:-1], lon_grid[1:-1, 1:-1]
    P = ecef(lat_c, lon_c, hc).reshape(-1, 3)
    clat, clon = 0.5 * (s + n), 0.5 * (w + e)
    centre = ecef(clat, clon, 0.5 * (hmin + hmax))
    bsc = P.mean(0)
    bsr = float(np.linalg.norm(P - bsc, axis=1).max())
    hop = occlusion_point(P, bsc)
    u = np.round(np.linspace(0, 32767, N)).astype(np.int64)
    U = np.broadcast_to(u[None, :], (N, N)).ravel()
    V = np.broadcast_to(u[:, None], (N, N)).ravel()
    Hq = np.round((hc.ravel() - hmin) / (hmax - hmin) * 32767).astype(np.int64)
    U, V, Hq = U[ORDER], V[ORDER], Hq[ORDER]
    enc = lambda a: zigzag(np.diff(np.concatenate([[0], a])))
    # normals from the apron grid (central differences in ECEF)
    PA = ecef(lat_grid, lon_grid, ha)
    nrm = np.cross(PA[1:-1, 2:] - PA[1:-1, :-2], PA[2:, 1:-1] - PA[:-2, 1:-1]).reshape(-1, 3)
    out = bytearray()
    out += struct.pack('<3d2f4d3d', *centre, hmin, hmax, *bsc, bsr, *hop)
    out += struct.pack('<I', N * N)
    out += enc(U).tobytes() + enc(V).tobytes() + enc(Hq).tobytes()
    out += struct.pack('<I', TRIS.size // 3) + _TRI_CODE.tobytes()
    g = np.arange(N * N).reshape(N, N)
    for edge in (g[:, 0], g[0, :], g[:, -1], g[-1, :]):            # west, south, east, north
        out += struct.pack('<I', edge.size) + NEWIDX[edge].astype(np.uint16).tobytes()
    nb = oct_encode(nrm[ORDER]).astype(np.uint8).tobytes()
    out += struct.pack('<BI', 1, len(nb)) + nb
    return bytes(out)


def decode(buf):
    """-> dict(header, u, v, h_m (real heights), tris, edges, normals) of one tile (uncompressed or gzip bytes)."""
    if buf[:2] == b'\x1f\x8b':
        buf = gzip.decompress(buf)
    hdr = struct.unpack_from('<3d2f4d3d', buf, 0)
    o = 88
    nv = struct.unpack_from('<I', buf, o)[0]; o += 4
    arr = lambda k: np.frombuffer(buf, '<u2', nv, o + 2 * k * nv)
    dec = lambda a: np.cumsum(unzigzag(a))
    u, v, hq = dec(arr(0)), dec(arr(1)), dec(arr(2)); o += 6 * nv
    nt = struct.unpack_from('<I', buf, o)[0]; o += 4
    code = np.frombuffer(buf, '<u2', 3 * nt, o).astype(np.int64); o += 6 * nt
    tris = hwm_decode(code).reshape(-1, 3)
    edges = []
    for _ in range(4):
        k = struct.unpack_from('<I', buf, o)[0]; o += 4
        edges.append(np.frombuffer(buf, '<u2', k, o).astype(np.int64)); o += 2 * k
    normals = None
    while o < len(buf):
        eid, ln = struct.unpack_from('<BI', buf, o); o += 5
        if eid == 1:
            normals = oct_decode(np.frombuffer(buf, np.uint8, 2 * nv, o).reshape(-1, 2))
        o += ln
    hmin, hmax = hdr[3], hdr[4]
    return {'centre': hdr[0:3], 'hmin': hmin, 'hmax': hmax, 'bsphere': hdr[5:9], 'hop': hdr[9:12], 'u': u, 'v': v,
            'h_m': hmin + hq / 32767.0 * (hmax - hmin), 'tris': tris, 'edges': edges, 'normals': normals}


# ------------------------------------------------------------------------------------------ build
def tile_heights(stack, z, x, y, levels=None):
    w, s, e, n = tile_rect(z, x, y)
    d = (e - w) / (N - 1)
    lon = w + (np.arange(-1, N + 1)) * d
    lat = s + (np.arange(-1, N + 1)) * ((n - s) / (N - 1))
    LA, LO = np.meshgrid(np.clip(lat, -90.0, 90.0), lon, indexing='ij')
    lv = levels or pyramid_levels_for(z)
    L = max(lv.values())
    q = stack._query_blended(LA, LO, levels=list(range(0, L + 1)))
    h = q['height']
    # use only levels up to each zone's chosen level (eq and polar pixels differ)
    for zone, Lz in lv.items():
        m = (q['zone'] == zone) & (q['level'] > Lz)
        if m.any():
            qq = stack._query_blended(LA[m], LO[m], levels=list(range(0, Lz + 1)))
            h[m] = qq['height']
    return LA, LO, h, (w, s, e, n)


def tile_path(z, x, y, root=None):
    return (Path(root) if root else OUT) / str(z) / str(x) / f'{y}.terrain'


def build_tile(stack, z, x, y, root=None):
    LA, LO, h, rect = tile_heights(stack, z, x, y)
    raw = encode(LA, LO, h, rect)
    p = tile_path(z, x, y, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f'.{os.getpid()}.tmp')
    tmp.write_bytes(gzip.compress(raw, compresslevel=6, mtime=0))
    os.replace(tmp, p)
    return p.stat().st_size, float(np.isfinite(h[1:-1, 1:-1]).mean())


def _worker(args):
    z, tiles, root = args
    stack = S.TerrainStack.open(max_tiles=512)
    tot = 0; nfin = []
    for x, y in tiles:
        p = tile_path(z, x, y, root)
        if p.exists():
            tot += p.stat().st_size; nfin.append(1.0); continue
        b, f = build_tile(stack, z, x, y, root)
        tot += b; nfin.append(f)
    return tot, len(tiles), float(np.mean(nfin)) if nfin else 1.0


def plan(max_level=GLOBAL_MAX, polar_max=POLAR_MAX):
    return [(z, tiles_at(z, polar_only=z > max_level)) for z in range(0, max(max_level, polar_max) + 1)]


def build(max_level=GLOBAL_MAX, polar_max=POLAR_MAX, workers=2, root=None, log=print):
    root = Path(root) if root else OUT
    t0 = time.time()
    levels = {}
    from multiprocessing import get_context
    for z, tiles in plan(max_level, polar_max):
        if workers > 1 and len(tiles) > 64:
            # contiguous chunks along x keep each worker's pyramid tiles cached
            k = max(1, len(tiles) // (workers * 16))
            chunks = [tiles[i:i + k] for i in range(0, len(tiles), k)]
            with get_context('spawn').Pool(workers) as pool:
                res = pool.map(_worker, [(z, c, str(root)) for c in chunks])
        else:
            res = [_worker((z, tiles, str(root)))]
        b = sum(r[0] for r in res); n = sum(r[1] for r in res)
        levels[z] = {'tiles': n, 'bytes': b, 'finite_fraction': round(float(np.mean([r[2] for r in res])), 6),
                     'vertex_spacing_deg': 180.0 / 2 ** z / (N - 1), 'pyramid_levels': pyramid_levels_for(z),
                     'extent': 'global' if z <= max_level else f'|lat| >= {POLAR_LAT} deg (tiles touching)'}
        log(f'level {z}: {n} tiles, {b / 1e6:.1f} MB, {time.time() - t0:.0f} s')
    write_layer_json(root, max_level, polar_max)
    man = {'schema': 'polaris-qmesh-manifest-v1', 'label': LABEL,
           'created_utc': _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
           'format': 'quantized-mesh-1.0 + octvertexnormals, gzip', 'ellipsoid': 'sphere R = 1737400 m (Cesium Ellipsoid.MOON)',
           'frame': 'MOON_ME, east-positive longitude; heights m above the sphere', 'tiling': 'geographic TMS, 2x1 at level 0',
           'vertices_per_tile': N * N, 'source': 'science pyramid $POLARIS_DATA/v2/pyramid (index.json); real terrain only',
           'levels': levels, 'total_bytes': sum(v['bytes'] for v in levels.values()),
           'total_tiles': sum(v['tiles'] for v in levels.values()),
           'cesium_usage': "CesiumTerrainProvider.fromUrl('<base>/globe/terrain', {ellipsoid: Ellipsoid.MOON, "
                           "requestVertexNormals: true}) on a Globe(Ellipsoid.MOON)"}
    (root / 'manifest.json').write_text(json.dumps(man, indent=1))
    return man


def write_layer_json(root, max_level, polar_max):
    avail = []
    for z in range(0, max(max_level, polar_max) + 1):
        nx, ny = 2 ** (z + 1), 2 ** z
        if z <= max_level:
            avail.append([{'startX': 0, 'startY': 0, 'endX': nx - 1, 'endY': ny - 1}])
        else:
            ys = sorted({y for _, y in tiles_at(z, polar_only=True)})
            runs = []
            for y in ys:
                if runs and y == runs[-1][1] + 1:
                    runs[-1][1] = y
                else:
                    runs.append([y, y])
            avail.append([{'startX': 0, 'startY': a, 'endX': nx - 1, 'endY': b} for a, b in runs])
    layer = {'tilejson': '2.1.0', 'name': 'POLARIS X Moon terrain (science pyramid, display)', 'version': '1.0.0',
             'scheme': 'tms', 'format': 'quantized-mesh-1.0', 'projection': 'EPSG:4326',
             'bounds': [-180, -90, 180, 90], 'minzoom': 0, 'maxzoom': max(max_level, polar_max),
             'tiles': ['{z}/{x}/{y}.terrain?v={version}'], 'extensions': ['octvertexnormals'], 'available': avail,
             'attribution': 'NASA LRO LOLA / SLDEM2015 / PGDA (via the POLARIS X science pyramid). ' + LABEL}
    Path(root).mkdir(parents=True, exist_ok=True)
    (Path(root) / 'layer.json').write_text(json.dumps(layer))


def check(root=None, n=40, log=print):
    """Decode a sample of built tiles: heights vs the pyramid, west/east and south/north edge agreement."""
    root = Path(root) if root else OUT
    man = json.loads((root / 'manifest.json').read_text())
    stack = S.TerrainStack.open()
    rng = np.random.default_rng(1)
    errs = []; edge = []
    for z in sorted(int(k) for k in man['levels']):
        files = list((root / str(z)).glob('*/*.terrain'))
        for f in rng.choice(files, size=min(n // 4 + 1, len(files)), replace=False):
            x, y = int(f.parent.name), int(f.stem)
            t = decode(f.read_bytes())
            LA, LO, h, rect = tile_heights(stack, z, x, y)
            g = np.full(N * N, np.nan); g[ORDER] = t['h_m']
            ref = h[1:-1, 1:-1].ravel()
            ok = np.isfinite(ref)
            errs.append(float(np.abs(g[ok] - ref[ok]).max()))
            nb = tile_path(z, (x + 1) % 2 ** (z + 1), y, root)
            if nb.exists():
                tn = decode(nb.read_bytes())
                gn = np.full(N * N, np.nan); gn[ORDER] = tn['h_m']
                edge.append(float(np.abs(g.reshape(N, N)[:, -1] - gn.reshape(N, N)[:, 0]).max()))
    out = {'tiles_checked': len(errs), 'max_abs_height_err_m': round(max(errs), 4),
           'max_abs_east_west_edge_diff_m': round(max(edge), 4) if edge else None,
           'total_tiles': man['total_tiles'], 'total_gb': round(man['total_bytes'] / 1e9, 3)}
    log(out)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.globe.qmesh')
    ap.add_argument('cmd', choices=['build', 'check'])
    ap.add_argument('--max-level', type=int, default=GLOBAL_MAX); ap.add_argument('--polar-max', type=int, default=POLAR_MAX)
    ap.add_argument('--workers', type=int, default=2); ap.add_argument('--root', default=None)
    a = ap.parse_args(argv)
    if a.cmd == 'build':
        m = build(a.max_level, a.polar_max, a.workers, a.root)
        print(json.dumps({k: m[k] for k in ('total_tiles', 'total_bytes')}))
    else:
        check(a.root)
    return 0


if __name__ == '__main__':
    sys.exit(main())
