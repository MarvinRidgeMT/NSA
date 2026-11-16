"""Terrain levels, view-dependent tile selection and the stereographic-grid -> local-ENU transform. numpy, no bpy.
Unit-tested in blender/tests/test_terrain.py.

Levels (finest first) are rasters on the south-polar stereographic grid (+proj=stere +lat_0=-90 +k=1 +R=1737400), heights in
metres above the 1 737 400 m sphere (docs/v2/TERRAIN_STACK_CONTRACT.md §2). Tonight they are the solver's own cached DEMs:
  near  PGDA 78 5 m tile        data/cache/<site>_p78_p78.npy (+ .json: x_left, y_top, step; rows north -> south)
  far   PGDA 90 LDEM_80S 80 m    data/cache/<site>_ldem80_290km.npy (+ .json), +-290 km around the site
  committed fallback: the 80 m +-16 km crop inside app/data/polaris-source-site01-2026-11-14-v2.json (rows south -> north,
  origin relative to the site's projectedMeters) - the only terrain in git, used by the reproducibility test.
When S3's science/terrain/stack.py exists, `stack_level()` reads TerrainStack.window() instead (same Level shape).

Geometry: SOURCE-BASED · UNVALIDATED. NaN nodes are never filled: a cell with any NaN corner is not drawn.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

R_MOON_M = 1_737_400.0


@dataclass
class Level:
    name: str
    h: np.ndarray            # (ny, nx) heights, row 0 = SOUTH edge (y0), column 0 = WEST edge (x0)
    x0: float                # absolute grid x of column 0 (m)
    y0: float                # absolute grid y of row 0 (m)
    step: float              # node spacing (m)
    source: str = ''
    sha256: str = ''
    status: str = 'SOURCE-BASED · UNVALIDATED'
    info: dict = field(default_factory=dict)

    @property
    def shape(self):
        return self.h.shape

    def box(self):
        ny, nx = self.h.shape
        return (self.x0, self.x0 + (nx - 1) * self.step, self.y0, self.y0 + (ny - 1) * self.step)

    def describe(self):
        ny, nx = self.h.shape
        return {'name': self.name, 'nodes': [int(nx), int(ny)], 'stepM': self.step, 'boxGridM': [round(v, 3) for v in self.box()],
                'source': self.source, 'sha256': self.sha256, 'status': self.status, **self.info}


def file_sha256(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


def load_cache_level(npy, name, hash_file=True):
    """Solver cache raster (x_left, y_top, step; rows north -> south) -> Level with rows south -> north."""
    npy = Path(npy)
    meta = json.loads(npy.with_suffix('.json').read_text())
    a = np.load(npy, mmap_mode='r')
    ny, nx = a.shape
    step = float(meta['step'])
    h = np.ascontiguousarray(a[::-1, :], dtype=np.float64)
    m = meta.get('meta', {})
    return Level(name=name, h=h, x0=float(meta['x_left']), y0=float(meta['y_top']) - (ny - 1) * step, step=step,
                 source=m.get('source_url') or m.get('source_path') or meta.get('name', ''),
                 sha256=file_sha256(npy) if hash_file else '',
                 info={'product': meta.get('name'), 'sourceFileSha256': m.get('file_sha256'), 'cacheFile': str(npy.name),
                       'nodata': 'NaN (never filled)', 'nanNodes': int(np.isnan(h).sum())})


def load_bundle_v2_level(bundle_path, dataset_id, name='committed 80 m crop'):
    """The DEM crop stored in a science-bundle-v2 file (rows south -> north, origin relative to site projectedMeters)."""
    raw = Path(bundle_path).read_bytes()
    b = json.loads(raw)
    d = next(x for x in b['datasets'] if x['siteId'] == dataset_id)
    dem = d['dem']
    n = int(dem['n'])
    h = np.asarray(dem['values'], dtype=np.float64).reshape(n, n)
    site = d['site']['projectedMeters']
    return Level(name=name, h=h, x0=float(site['x']) + float(dem['originX']), y0=float(site['y']) + float(dem['originY']),
                 step=float(dem['spacing']), source=dem.get('source') or dem.get('layer', ''),
                 sha256=hashlib.sha256(raw).hexdigest(),
                 info={'bundleFile': Path(bundle_path).name, 'dataset': dataset_id, 'cropValuesSha256': dem.get('cropValuesSha256'),
                       'layer': dem.get('layer'), 'note': 'sha256 is of the whole bundle file'})


def stack_level(lat, lon, half_m, res_m):
    """S3 TerrainStack window, when science/terrain/stack.py exists. Returns (Level | None, reason)."""
    try:
        from science.terrain.stack import TerrainStack  # noqa: F401  (S3, not on this branch yet)
    except Exception as e:                              # pragma: no cover - depends on S3
        return None, f'science.terrain.stack not available ({type(e).__name__})'
    return None, 'TerrainStack present but not wired yet (contract §5 window() -> ArrayDEM)'


# ---------------------------------------------------------------- frames
def stereo_inverse(x, y):
    """Closed form, identical to science/frames.stereo_inverse: rho = 2R tan(pi/4 + lat/2), x = rho sin lon, y = rho cos lon."""
    rho = np.hypot(x, y)
    lat = 2.0 * np.arctan(rho / (2.0 * R_MOON_M)) - np.pi / 2.0
    lon = np.arctan2(x, y)
    return lat, lon


def stereo_forward(lat_deg, lon_deg):
    la, lo = math.radians(lat_deg), math.radians(lon_deg)
    rho = 2 * R_MOON_M * math.tan(math.pi / 4 + la / 2)
    return rho * math.sin(lo), rho * math.cos(lo)


class EnuFrame:
    """Local ENU at the observer ground point (lat0, lon0, h0): x east, y north, z up (radial)."""

    def __init__(self, lat_deg, lon_deg, h0):
        self.lat, self.lon, self.h0 = lat_deg, lon_deg, float(h0)
        la, lo = math.radians(lat_deg), math.radians(lon_deg)
        self.e = np.array([-math.sin(lo), math.cos(lo), 0.0])
        self.n = np.array([-math.sin(la) * math.cos(lo), -math.sin(la) * math.sin(lo), math.cos(la)])
        self.u = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
        self.P0 = (R_MOON_M + self.h0) * self.u
        self.M = np.stack([self.e, self.n, self.u])     # rows: ENU axes in Moon-fixed

    def from_grid(self, x, y, h):
        """Absolute stereographic grid (x, y) + height -> ENU (N, 3)."""
        lat, lon = stereo_inverse(np.asarray(x, float), np.asarray(y, float))
        r = R_MOON_M + np.asarray(h, float)
        P = np.stack([r * np.cos(lat) * np.cos(lon), r * np.cos(lat) * np.sin(lon), r * np.sin(lat)], axis=-1)
        return (P - self.P0) @ self.M.T

    def describe(self):
        return {'latDeg': self.lat, 'lonEastDeg': self.lon, 'groundHeightM': self.h0, 'axes': 'x east, y north, z up (site radius)',
                'transform': 'grid -> (lat, lon) closed-form inverse stereographic -> (R+h) u(lat, lon) Moon-fixed -> ENU at the observer'}


def sample_bilinear(level, x, y):
    """Height at absolute grid (x, y) by bilinear interpolation; NaN outside or next to NaN."""
    fx, fy = (x - level.x0) / level.step, (y - level.y0) / level.step
    ny, nx = level.h.shape
    if not (0 <= fx <= nx - 1 and 0 <= fy <= ny - 1):
        return float('nan')
    i, j = min(int(fx), nx - 2), min(int(fy), ny - 2)
    tx, ty = fx - i, fy - j
    q = level.h[j:j + 2, i:i + 2]
    return float((q[0, 0] * (1 - tx) + q[0, 1] * tx) * (1 - ty) + (q[1, 0] * (1 - tx) + q[1, 1] * tx) * ty)


# ---------------------------------------------------------------- view-dependent tiles
@dataclass
class View:
    """Camera in ENU: position, unit forward, horizontal/vertical half-FOV (rad), angular pixel size (rad)."""
    pos: tuple
    fwd: tuple
    half_h: float
    half_v: float
    pixel_rad: float
    sun_dir: tuple = (0.0, 0.0, 1.0)
    sun_radius_rad: float = math.radians(0.267)


def _in_frustum(view, c, radius):
    d = np.asarray(c) - np.asarray(view.pos)
    L = float(np.linalg.norm(d))
    if L <= radius:
        return True
    ang = math.acos(max(-1.0, min(1.0, float(np.dot(d, view.fwd)) / L)))
    half_diag = math.atan(math.hypot(math.tan(view.half_h), math.tan(view.half_v)))
    return ang - math.asin(min(1.0, radius / L)) <= half_diag


def _sun_side(view, c, observer=(0.0, 0.0, 0.0), wedge_deg=35.0):
    """True when the tile lies toward the Sun's azimuth (within +-wedge) from the observer: a possible shadow caster."""
    d = np.asarray(c, float) - np.asarray(observer, float)
    s = np.asarray(view.sun_dir, float)
    dh, sh = d[:2], s[:2]
    if np.linalg.norm(dh) < 1 or np.linalg.norm(sh) < 1e-9:
        return True
    cosang = float(np.dot(dh, sh) / (np.linalg.norm(dh) * np.linalg.norm(sh)))
    return cosang >= math.cos(math.radians(wedge_deg))


def plan_tiles(levels, frame, view, tile_cells=64, budget=2_500_000, k=2.0, near_keep_m=2000.0, all_around=False):
    """Choose, per tile of each level, whether to draw it and at what decimation (power of two).

    In the view frustum: spacing <= k * distance * pixel angle. Outside it, only tiles toward the Sun (possible shadow casters)
    or within `near_keep_m`: spacing <= distance * tan(Sun angular radius). Cells inside a finer level's box (inset by one coarse
    cell) are left to that level. If the vertex estimate exceeds `budget`, k doubles (recorded). `all_around` treats every
    tile as in view (skyline consistency check). Returns (tiles, report)."""
    for attempt in range(8):
        tiles, verts = [], 0
        for li, lv in enumerate(levels):
            ny, nx = lv.h.shape
            finer = [levels[j].box() for j in range(li)]
            for j0 in range(0, ny - 1, tile_cells):
                for i0 in range(0, nx - 1, tile_cells):
                    i1, j1 = min(i0 + tile_cells, nx - 1), min(j0 + tile_cells, ny - 1)
                    gx0, gx1 = lv.x0 + i0 * lv.step, lv.x0 + i1 * lv.step
                    gy0, gy1 = lv.y0 + j0 * lv.step, lv.y0 + j1 * lv.step
                    if any(b[0] + lv.step <= gx0 and gx1 <= b[1] - lv.step and b[2] + lv.step <= gy0 and gy1 <= b[3] - lv.step for b in finer):
                        continue                                          # fully covered by a finer level
                    sub = lv.h[j0:j1 + 1:max(1, (j1 - j0) // 4), i0:i1 + 1:max(1, (i1 - i0) // 4)]
                    if np.all(np.isnan(sub)):
                        continue
                    hm = float(np.nanmean(sub))
                    xs = np.array([gx0, gx1, gx0, gx1, (gx0 + gx1) / 2])
                    ys = np.array([gy0, gy0, gy1, gy1, (gy0 + gy1) / 2])
                    pts = frame.from_grid(xs, ys, np.full(5, hm))
                    c = pts[4]
                    radius = float(np.max(np.linalg.norm(pts[:4] - c, axis=1))) + float(np.nanmax(sub) - np.nanmin(sub)) / 2
                    dist = max(1.0, float(np.linalg.norm(c - np.asarray(view.pos))) - radius)
                    inside = all_around or _in_frustum(view, c, radius)
                    if inside:
                        need = k * dist * view.pixel_rad
                        role = 'view'
                    elif dist <= near_keep_m or _sun_side(view, c):
                        need = dist * math.tan(view.sun_radius_rad)
                        role = 'shadow-caster'
                    else:
                        continue
                    f = 1
                    while f * 2 <= tile_cells and lv.step * f * 2 <= need:
                        f *= 2
                    nvx = (i1 - i0) // f + 2
                    nvy = (j1 - j0) // f + 2
                    verts += nvx * nvy + 2 * (nvx + nvy)
                    tiles.append({'level': li, 'i0': i0, 'i1': i1, 'j0': j0, 'j1': j1, 'decim': f, 'role': role,
                                  'distM': round(dist, 1), 'spacingM': lv.step * f})
        if verts <= budget:
            break
        k *= 2.0
    report = {'tiles': len(tiles), 'vertexEstimate': int(verts), 'budget': budget, 'k': k, 'attempts': attempt + 1, 'allAround': all_around,
              'rule': 'view: spacing <= k * distance * pixel angle; shadow-caster (toward the Sun, or within near_keep_m): '
                      'spacing <= distance * tan(Sun angular radius); power-of-two decimation, never finer than native',
              'byLevel': {}}
    for li, lv in enumerate(levels):
        ts = [t for t in tiles if t['level'] == li]
        report['byLevel'][lv.name] = {'tiles': len(ts), 'view': sum(t['role'] == 'view' for t in ts),
                                      'shadowCaster': sum(t['role'] == 'shadow-caster' for t in ts),
                                      'spacingRangeM': [min((t['spacingM'] for t in ts), default=None), max((t['spacingM'] for t in ts), default=None)]}
    return tiles, report


def tile_mesh(level, t, frame, finer_boxes=(), skirt=True):
    """Vertices (N,3 ENU) and quad faces (M,4) for one planned tile. Cells inside a finer box or touching NaN are dropped.
    Skirts: each tile edge gets a strip dropped by 3 x spacing so LOD seams do not open cracks (VISUAL seam filler)."""
    f = t['decim']
    ii = list(range(t['i0'], t['i1'] + 1, f))
    jj = list(range(t['j0'], t['j1'] + 1, f))
    if ii[-1] != t['i1']:
        ii.append(t['i1'])
    if jj[-1] != t['j1']:
        jj.append(t['j1'])
    ii, jj = np.array(ii), np.array(jj)
    H = level.h[np.ix_(jj, ii)]
    gx = level.x0 + ii * level.step
    gy = level.y0 + jj * level.step
    GX, GY = np.meshgrid(gx, gy)
    nyv, nxv = H.shape
    V = frame.from_grid(GX.ravel(), GY.ravel(), np.nan_to_num(H.ravel(), nan=0.0))
    valid = ~np.isnan(H)
    q = (np.arange(nyv - 1)[:, None] * nxv + np.arange(nxv - 1)[None, :]).ravel()
    faces = np.stack([q, q + 1, q + nxv + 1, q + nxv], axis=1)
    ok = (valid[:-1, :-1] & valid[:-1, 1:] & valid[1:, :-1] & valid[1:, 1:]).ravel()
    cx = ((gx[:-1] + gx[1:]) / 2)[None, :].repeat(nyv - 1, 0).ravel()
    cy = ((gy[:-1] + gy[1:]) / 2)[:, None].repeat(nxv - 1, 1).ravel()
    for b in finer_boxes:
        ok &= ~((cx > b[0] + level.step) & (cx < b[1] - level.step) & (cy > b[2] + level.step) & (cy < b[3] - level.step))
    faces = faces[ok]
    dropped = int((~ok).sum())
    if skirt and len(faces):
        depth = 3.0 * level.step * f
        down = -frame.u @ frame.M.T            # ENU of the local "down" at the observer (approximately -z)
        edges = [np.arange(nxv), (nyv - 1) * nxv + np.arange(nxv)[::-1], np.arange(nyv)[::-1] * nxv, np.arange(nyv) * nxv + nxv - 1]
        extra_v, extra_f = [], []
        base = len(V)
        for e in edges:
            e = e[valid.ravel()[e]]
            if len(e) < 2:
                continue
            start = base + sum(len(x) for x in extra_v)
            n_e = len(e)
            # own copies of the edge vertices, so the skirt never bends the surface's smooth normals
            extra_v.append(np.vstack([V[e], V[e] + depth * down]))
            k = np.arange(n_e - 1)
            extra_f.append(np.stack([start + k, start + k + 1, start + n_e + k + 1, start + n_e + k], axis=1))
        if extra_v:
            V = np.vstack([V] + extra_v)
            faces = np.vstack([faces] + extra_f)
    return V, faces, dropped


def ground_height(levels, x, y):
    """Height at grid (x, y) from the finest level that covers it (NaN if none)."""
    for lv in levels:
        h = sample_bilinear(lv, x, y)
        if math.isfinite(h):
            return h, lv.name
    return float('nan'), None
