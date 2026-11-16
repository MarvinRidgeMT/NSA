#!/usr/bin/env python3
"""Build DISPLAY-ONLY quadtree level-of-detail tiles of the near field (±7 km at 5 m) for the 3D view (5D Phase 9.4).

Source: the NASA PGDA product 78 5 m tile of the site, read through science.sites.near_dem(site) (the solver's own cached
copy under data/cache/, URL + SHA-256 in its metadata). Nothing is downloaded when the cache is present.

Lattice. Nodes are the source pixel centres. The centre node is the pixel centre nearest the site point; the covered area is
the 2800 x 2800 pixel square of nodes around it (2801 nodes a side, 14 000 m = ±7 000 m). The quadtree has LEVELS = 5 levels:
level l has 2^l x 2^l tiles, each TILE_CELLS = 175 cells (176 nodes) a side, node spacing 5 m * 2^(4 - l): 80, 40, 20, 10, 5 m.
Neighbouring tiles of one level share their edge nodes, so a level tiles the area exactly.

Heights. Level 4 (5 m) nodes are the source pixels, unchanged (float32 source -> float32 tile, bit-identical).
A coarser node is the mean of the source pixels in the (s + 1) x (s + 1) pixel box centred on it, s = spacing / 5 m
(a vertex-centred box average; coarse nodes sit on fine nodes, so shared edges agree exactly). Any non-finite or absent pixel
in the box -> NaN (no fill, no extrapolation). Each tile file also carries a one-node apron on every side (used only to
compute seamless shading normals); the apron lies outside the tile bounds and is computed by the same rule.

Output (git-ignored, NASA-derived): web/public/context/lod/<site>/manifest.json + L<l>_<ix>_<iy>.f32
  tile file: (176 + 2)^2 float32 little-endian, row-major, rows south-to-north (j), columns west-to-east (i) in grid x;
  ix west-to-east, iy south-to-north; coordinates in metres in the bundle grid axes (x toward 90 E, y toward 0 E) relative to
  the dataset site point (same frame as data/viewer bundles and tools/terrain/build_terrain_context.py).

VISUAL ONLY. The solver never reads these tiles; no visible/blocked state, margin or metric is computed from them.
Usage: python tools/terrain/build_lod_tiles.py [--only site04_roi3] [--out web/public/context/lod]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

SCHEMA = 'polaris-lod-tiles-v1'
SITES_DEFAULT = ('site04_roi3', 'site01_roi6')
HALF_M = 7000.0
PIXEL_M = 5.0
LEVELS = 5
TILE_CELLS = 175                       # 2^(LEVELS-1) * 175 = 2800 pixels = 14 000 m
APRON = 1
MAX_TILE_BYTES = 2 * 1024 * 1024
OUT_DEFAULT = os.path.join(ROOT, 'web', 'public', 'context', 'lod')


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def area_pixels() -> int:
    return TILE_CELLS * 2 ** (LEVELS - 1)


class BoxMean:
    """Means of square pixel boxes on a north-up raster Z (rows north->south) via summed-area tables.
    mean(r, c, h) = mean of Z[r-h : r+h+1, c-h : c+h+1]; NaN if the box leaves the raster or holds a non-finite pixel."""

    def __init__(self, Z: np.ndarray):
        Z = np.asarray(Z, dtype=np.float64)
        bad = ~np.isfinite(Z)
        self.h, self.w = Z.shape
        self.S = np.zeros((self.h + 1, self.w + 1))
        self.B = np.zeros((self.h + 1, self.w + 1))
        self.S[1:, 1:] = np.where(bad, 0.0, Z).cumsum(0).cumsum(1)
        self.B[1:, 1:] = bad.astype(np.float64).cumsum(0).cumsum(1)
        self.Z = Z

    def mean(self, r: np.ndarray, c: np.ndarray, half: int) -> np.ndarray:
        r = np.asarray(r); c = np.asarray(c)
        ok = (r - half >= 0) & (r + half < self.h) & (c - half >= 0) & (c + half < self.w)
        r0 = np.clip(r - half, 0, self.h); r1 = np.clip(r + half + 1, 0, self.h)
        c0 = np.clip(c - half, 0, self.w); c1 = np.clip(c + half + 1, 0, self.w)
        box = lambda T: T[r1, c1] - T[r0, c1] - T[r1, c0] + T[r0, c0]  # noqa: E731
        n = (2 * half + 1) ** 2
        s, b = box(self.S), box(self.B)
        out = s / n
        if half == 0:   # exact source value (no summed-area round-off)
            out = self.Z[np.clip(r, 0, self.h - 1), np.clip(c, 0, self.w - 1)]
        return np.where(ok & (b < 0.5), out, np.nan)


def lattice(dem, site_xy):
    """Source pixel (row, col) of the centre node and the site-relative position of that pixel centre."""
    cx = (site_xy[0] - dem.x_left) / dem.step - 0.5
    cy = (dem.y_top - site_xy[1]) / dem.step - 0.5
    c0, r0 = int(round(cx)), int(round(cy))
    x0 = dem.x_left + (c0 + 0.5) * dem.step - site_xy[0]
    y0 = dem.y_top - (r0 + 0.5) * dem.step - site_xy[1]
    return r0, c0, x0, y0


def tile_nodes(level: int):
    """Node offsets (in source pixels, from the area's south-west node) of every tile of a level, apron included."""
    s = 2 ** (LEVELS - 1 - level)
    k = np.arange(-APRON, TILE_CELLS + 1 + APRON)
    return s, k


def build_tiles(dem, site_xy, out_dir=None):
    """Cut the quadtree. Returns (manifest_partial, {file: bytes}). `dem` is an ArrayDEM (rows north->south, 5 m pixels)."""
    if abs(dem.step - PIXEL_M) > 1e-9:
        raise ValueError(f'expected {PIXEL_M} m pixels, got {dem.step}')
    r_c, c_c, x_c, y_c = lattice(dem, site_xy)
    half_px = area_pixels() // 2
    # south-west node of the area: pixel row increases southward
    r_sw, c_sw = r_c + half_px, c_c - half_px
    x_sw, y_sw = x_c - half_px * PIXEL_M, y_c - half_px * PIXEL_M
    bm = BoxMean(dem.Z)
    tiles, files = [], {}
    for level in range(LEVELS):
        s, k = tile_nodes(level)
        n_t = 2 ** level
        spacing = s * PIXEL_M
        for iy in range(n_t):
            for ix in range(n_t):
                # node (i, j) of this tile: pixel offset east = (ix*TILE_CELLS + i) * s, north = (iy*TILE_CELLS + j) * s
                ci = c_sw + (ix * TILE_CELLS + k) * s
                rj = r_sw - (iy * TILE_CELLS + k) * s
                R, C = np.meshgrid(rj, ci, indexing='ij')          # rows j (south->north), cols i (west->east)
                z = bm.mean(R, C, s // 2).astype('<f4')
                name = f'L{level}_{ix}_{iy}.f32'
                data = np.ascontiguousarray(z).tobytes()
                core = z[APRON:-APRON, APRON:-APRON]
                fin = core[np.isfinite(core)]
                xmin = x_sw + ix * TILE_CELLS * spacing
                ymin = y_sw + iy * TILE_CELLS * spacing
                tiles.append({'level': level, 'ix': ix, 'iy': iy, 'file': name, 'bytes': len(data), 'sha256': sha(data),
                              'bounds': {'xmin': round(xmin, 3), 'xmax': round(xmin + TILE_CELLS * spacing, 3),
                                         'ymin': round(ymin, 3), 'ymax': round(ymin + TILE_CELLS * spacing, 3)},
                              'zMin': round(float(fin.min()), 3) if fin.size else None,
                              'zMax': round(float(fin.max()), 3) if fin.size else None,
                              'nanNodes': int(core.size - fin.size)})
                files[name] = data
    levels = [{'level': l, 'spacingM': PIXEL_M * 2 ** (LEVELS - 1 - l), 'tilesPerSide': 2 ** l,
               'tileWidthM': TILE_CELLS * PIXEL_M * 2 ** (LEVELS - 1 - l),
               'boxPixels': 2 ** (LEVELS - 1 - l) + 1 if l < LEVELS - 1 else 1} for l in range(LEVELS)]
    area = {'xmin': round(x_sw, 3), 'xmax': round(x_sw + area_pixels() * PIXEL_M, 3),
            'ymin': round(y_sw, 3), 'ymax': round(y_sw + area_pixels() * PIXEL_M, 3),
            'centreNode': {'x': round(x_c, 3), 'y': round(y_c, 3), 'sourceRow': r_c, 'sourceCol': c_c},
            'southWestSourcePixel': {'row': r_sw, 'col': c_sw}}
    part = {'levels': levels, 'area': area, 'tiles': tiles,
            'tileGrid': {'cells': TILE_CELLS, 'nodes': TILE_CELLS + 1, 'apron': APRON, 'stored': TILE_CELLS + 1 + 2 * APRON,
                         'dtype': 'float32-le', 'layout': 'row-major (stored x stored); row j south-to-north, column i west-to-east; '
                                                          'node (i, j) of the tile core is stored at [(j + apron) * stored + (i + apron)]'}}
    return part, files


def build_site(site_id, out_root):
    sys.path.insert(0, ROOT)
    from science import frames, sites
    t0 = time.time()
    s = sites.SITES[site_id]
    x, y = frames.stereo_forward(s['lat'], s['lon'])
    site_xy = (round(x, 3), round(y, 3))     # the bundle site point (data/viewer: projectedMeters to 1 mm)
    dem = sites.near_dem(site_id)
    part, files = build_tiles(dem, site_xy)
    big = [t for t in part['tiles'] if t['bytes'] > MAX_TILE_BYTES]
    if big:
        raise SystemExit(f'{site_id}: {len(big)} tiles exceed {MAX_TILE_BYTES} bytes')
    d = os.path.join(out_root, site_id)
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        if f.endswith('.f32') and f not in files:
            os.remove(os.path.join(d, f))
    for name, data in files.items():
        with open(os.path.join(d, name), 'wb') as f:
            f.write(data)
    meta = dem.meta
    leaf = [t for t in part['tiles'] if t['level'] == LEVELS - 1]
    manifest = {
        'schema': SCHEMA, 'generatedUTC': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'status': 'VISUAL', 'numericalAuthority': False, 'label': 'NEAR FIELD 5 m LOD · DISPLAY ONLY',
        'releaseStatus': 'SOURCE_BASED_UNVALIDATED', 'datasetId': site_id, 'siteName': s['name'],
        'sitePointProjectedM': {'x': site_xy[0], 'y': site_xy[1]},
        'frame': 'bundle grid axes (x toward 90 E, y toward 0 E), metres, relative to the dataset site point; heights in metres above R = 1737400 m',
        'halfExtentM': HALF_M,
        'source': {'product': 'NASA PGDA product 78 LOLA 5 m tile (Barker et al. 2021), surface heights', 'url': meta.get('source_url'),
                   'sha256': meta.get('file_sha256'), 'pixelM': PIXEL_M, 'reader': 'science.sites.near_dem (data/cache, solver copy)',
                   'windowWidthPx': meta.get('window_width_px'), 'windowHeightPx': meta.get('window_height_px'),
                   'windowXLeft': dem.x_left, 'windowYTop': dem.y_top},
        **part,
        'rule': 'level 4 (5 m) node = source pixel (unchanged); coarser node = mean of the (s+1)x(s+1) source pixels centred on it, '
                's = spacing / 5 m; any non-finite or absent pixel -> NaN (no fill)',
        'nanFractionLeaf': round(sum(t['nanNodes'] for t in leaf) / (len(leaf) * (TILE_CELLS + 1) ** 2), 5),
        'totalBytes': sum(t['bytes'] for t in part['tiles']), 'maxTileBytes': max(t['bytes'] for t in part['tiles']),
        'limitations': [
            'Display only: the solver, its skylines and every number on screen come from the bundles, never from these tiles.',
            'Coarse levels are box means and smooth relief; the 5 m level is the source raster as published.',
            'Nodes outside the PGDA 78 tile are NaN and are not drawn (Site04 ROI3: the west edge of the ±7 km square lies beyond the tile).',
            'No cast shadows from these tiles; lighting on this layer is a display model.',
        ],
    }
    with open(os.path.join(d, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=1)
    print(f"{site_id}: {len(part['tiles'])} tiles, {manifest['totalBytes'] / 1e6:.1f} MB, max tile {manifest['maxTileBytes']} B, "
          f"leaf NaN fraction {manifest['nanFractionLeaf']}, {time.time() - t0:.1f} s -> {d}")
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--only')
    ap.add_argument('--out', default=OUT_DEFAULT)
    a = ap.parse_args()
    for site in SITES_DEFAULT:
        if a.only and a.only != site:
            continue
        build_site(site, a.out)


if __name__ == '__main__':
    main()
