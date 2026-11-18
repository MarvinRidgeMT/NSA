#!/usr/bin/env python3
"""Build the web copy of NASA PGDA product 69 that Simple mode's "Check a spot" (S13) looks values up in.

Inputs (NASA files, kept out of git):
  AVGVISIB_85S_060M_201608.TIF        18.6-year average Sun visibility, 60 m
  AVGVISIB_85S_060M_201608_EARTH.TIF  18.6-year average Earth visibility, 60 m
Both are int16, 5058 x 5058 cells of 60 m, polar stereographic "Moon2000_spole" (sphere R = 1 737 400 m, true scale at
the pole, central meridian 0), value x 4e-05 = fraction, nodata -32768.

Output (web/public/pgda69-spot/): a crop of CROP_PX x CROP_PX cells centred on the pole, cut into TILE_PX tiles.
Nothing is resampled, rescaled or rounded: every tile holds the original int16 values of its cells, Sun layer first and
Earth layer second, rows from the top (north-up in the grid, as in the TIF). To make the files smaller without losing
anything, each layer is stored as differences along each row (the first cell of a row as it is, every other cell minus
the cell to its left, wrapping in 16 bits), all the low bytes followed by all the high bytes, then gzip. Adding the
differences back up gives the original values exactly (scripts/test_pgda69_web.py checks every cell). The whole 85-90 S
map compresses to about 48 MB, so the web copy is a crop; the manifest says exactly which cells it holds and the page
tells a visitor when a point is on NASA's map but outside the copy.

The manifest also carries check points (the bundle's sites and seeded random points) whose cell and values were read
here from the TIFs with rasterio and pyproj. The page's own projection and decoder are tested against them
(web/tests/unit/spot-check.test.ts), and scripts/test_pgda69_web.py compares every shipped cell with the TIFs.

Run (needs rasterio, pyproj, numpy; e.g. tmp/pgda69-venv):
  tmp/pgda69-venv/bin/python scripts/build_pgda69_web.py [--src tmp/pgda69] [--out web/public/pgda69-spot]
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import math
import random
import shutil
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer

ROOT = Path(__file__).resolve().parent.parent
SUN_TIF = 'AVGVISIB_85S_060M_201608.TIF'
EARTH_TIF = 'AVGVISIB_85S_060M_201608_EARTH.TIF'
URL = 'https://pgda.gsfc.nasa.gov/data/MoonIllumination/'
BUNDLE = ROOT / 'data' / 'viewer' / 'polaris-x5d-roi-2026-11-14-v2.json'
CROP_PX = 2048  # cells per side of the web copy, centred on the pole
TILE_PX = 256
N_RANDOM_CHECKS = 240
SEED = 69


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def gz(raw: bytes) -> bytes:
    buf = io.BytesIO()
    # mtime 0 and no file name: the same input always gives the same bytes
    with gzip.GzipFile(fileobj=buf, mode='wb', compresslevel=9, mtime=0) as f:
        f.write(raw)
    return buf.getvalue()


def pack(layer: np.ndarray) -> bytes:
    """Row-wise differences (wrapping int16), low bytes then high bytes. Lossless."""
    a = layer.astype(np.int32)
    d = a.copy()
    d[:, 1:] = a[:, 1:] - a[:, :-1]
    b = d.astype('<i2').view(np.uint8).reshape(-1, 2)  # int32 -> int16 wraps, as the reader's sum does
    return b[:, 0].tobytes() + b[:, 1].tobytes()


def window(a: np.ndarray, row: int, col: int) -> list[int]:
    """Smallest and largest value of the 3 x 3 cells centred on (row, col)."""
    w = a[row - 1 : row + 2, col - 1 : col + 2]
    return [int(w.min()), int(w.max())]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--src', type=Path, default=ROOT / 'tmp' / 'pgda69')
    ap.add_argument('--out', type=Path, default=ROOT / 'web' / 'public' / 'pgda69-spot')
    args = ap.parse_args()

    with rasterio.open(args.src / SUN_TIF) as s, rasterio.open(args.src / EARTH_TIF) as e:
        for d in (s, e):
            assert d.dtypes == ('int16',), d.dtypes
            assert d.nodata == -32768, d.nodata
            assert d.scales == (4e-05,) and d.offsets == (0.0,), (d.scales, d.offsets)
        assert s.transform == e.transform and s.shape == e.shape and s.crs == e.crs
        t = s.transform
        assert t.a == 60 and t.e == -60 and t.b == 0 and t.d == 0, t
        wkt = s.crs.to_wkt()
        assert 'Polar_Stereographic' in wkt and '1737400' in wkt, wkt
        radius = 1737400.0
        cell = t.a
        x0_full, y0_full = t.c, t.f
        h, w = s.shape
        created = s.tags().get('PRODUCT_CREATION_TIME')
        sun = s.read(1)
        earth = e.read(1)
        to_xy = Transformer.from_crs(s.crs.geodetic_crs, s.crs, always_xy=True)
        nodata = int(s.nodata)
        scale = s.scales[0]

    assert h == w and (w - CROP_PX) % 2 == 0 and CROP_PX % TILE_PX == 0
    off = (w - CROP_PX) // 2
    csun = sun[off : off + CROP_PX, off : off + CROP_PX]
    cearth = earth[off : off + CROP_PX, off : off + CROP_PX]
    x0 = x0_full + off * cell  # left edge of the crop, m
    y0 = y0_full - off * cell  # top edge of the crop, m
    half = CROP_PX * cell / 2
    assert abs(x0 + half) < 1e-9 and abs(y0 - half) < 1e-9, 'crop is not centred on the pole'

    if args.out.exists():
        shutil.rmtree(args.out)
    (args.out / 'tiles').mkdir(parents=True)
    tiles = []
    total = 0
    n = CROP_PX // TILE_PX
    for tr in range(n):
        for tc in range(n):
            sl = (slice(tr * TILE_PX, (tr + 1) * TILE_PX), slice(tc * TILE_PX, (tc + 1) * TILE_PX))
            raw = pack(csun[sl]) + pack(cearth[sl])
            blob = gz(raw)
            name = f'tiles/r{tr}c{tc}.i16.gz'
            (args.out / name).write_bytes(blob)
            tiles.append({'r': tr, 'c': tc, 'file': name, 'bytes': len(blob), 'sha256': hashlib.sha256(blob).hexdigest()})
            total += len(blob)

    # ---- check points: cell and values read here from the full TIFs, with pyproj's projection ----
    def check(name: str, lat: float, lon: float) -> dict:
        x, y = to_xy.transform(lon, lat)
        col = math.floor((x - x0_full) / cell)
        row = math.floor((y0_full - y) / cell)
        return {
            'name': name,
            'lat': lat,
            'lonE': lon,
            'xM': x,
            'yM': y,
            'row': row,
            'col': col,
            'inCopy': bool(off <= row < off + CROP_PX and off <= col < off + CROP_PX),
            'sunRaw': int(sun[row, col]),
            'earthRaw': int(earth[row, col]),
            'sun3x3': window(sun, row, col),
            'earth3x3': window(earth, row, col),
        }

    checks = []
    bundle = json.loads(BUNDLE.read_text())
    for d in bundle['datasets']:
        site = d['site']
        c = check(site['name'], site['latitudePlanetocentricDeg'], site['longitudeEastDeg'])
        c['siteId'] = d['siteId']
        checks.append(c)
    rng = random.Random(SEED)
    edge_lat = -90 + math.degrees(2 * math.atan(half / (2 * radius)))  # latitude of the copy's inscribed circle
    while len(checks) < len(bundle['datasets']) + N_RANDOM_CHECKS:
        # even over the cap, a little past the copy's edge so some points fall outside it
        r = (half * 1.25) * math.sqrt(rng.random())
        lon = rng.uniform(-180, 180)
        lat = -90 + math.degrees(2 * math.atan(r / (2 * radius)))
        c = check(f'random {len(checks)}', lat, lon)
        if 1 <= c['row'] < h - 1 and 1 <= c['col'] < w - 1:
            checks.append(c)

    manifest = {
        'schema': 'POLARIS-X-pgda69-spot-v1',
        'kind': 'NASA_REFERENCE_PRODUCT',
        'product': 'NASA PGDA product 69: LOLA-derived average illumination and Earth visibility, south pole 85-90 S, 60 m',
        'citation': 'Mazarico, E., et al. (2011), Illumination conditions of the lunar polar regions using LOLA topography, Icarus, 211, 1066-1081, doi:10.1016/j.icarus.2010.10.030',
        'productCreationTime': created,
        # What the values mean, as the product's own PDS labels and NASA's product page state it (re-read 18 Nov 2026). The page
        # shows these words; they are a description of the source, not something computed here.
        # Sun: the label's title is "a map of the average illumination by the solar disc", its column description "average
        # solar disc visibility (DN up to 25000, scaling to 1)", and the product page "solar illumination, averaged over hourly
        # timesteps spanning 18.6 years" with the Sun treated as a finite disc (Mazarico et al. 2011): the long-term average
        # fraction of the solar disc in view. The label's longer sentence also says "percentage of timesteps where each pixel
        # was sunlit (by any fraction of the solar disc)"; the Earth label repeats that sentence word for word with "sunlit"
        # left in, so it reads as template text, and the product page states the any-part rule for the Earth only. The card
        # follows the title, the column and the page; 'labelConflict' keeps the other sentence on record.
        'meaning': {
            'sunShort': 'average share of the Sun’s disc in view',
            'earthShort': 'share of hours; counts as visible if any part of its disc shows',
            'basis': 'averaged over hourly steps spanning 18.6 years',
            'sun': 'Average fraction of the solar disc in view, over hourly timesteps spanning 18.6 years (one lunar nutation cycle): the label\'s "average illumination by the solar disc" and "average solar disc visibility".',
            'earth': 'Earth: visible if any part of its disc is not obscured (NASA notes this is slightly optimistic for radio links); the share of hourly timesteps over 18.6 years in which it was.',
            'labelConflict': 'Both labels\' longer DESCRIPTION also says the values "indicate the percentage of timesteps where each pixel was sunlit (by any fraction of the solar disc)" (Earth label: "of the Earth disc", "sunlit" kept). For the Sun this differs from the title, the column description and the product page; the card uses the latter.',
            'statedIn': [
                'https://pgda.gsfc.nasa.gov/products/69',
                'http://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_85S_060M_201608.LBL',
                'http://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_85S_060M_201608_EARTH.LBL',
            ],
        },
        'generatedBy': 'scripts/build_pgda69_web.py',
        'sources': [
            {'layer': 'sun', 'file': SUN_TIF, 'url': URL + SUN_TIF, 'sha256': sha256(args.src / SUN_TIF)},
            {'layer': 'earth', 'file': EARTH_TIF, 'url': URL + EARTH_TIF, 'sha256': sha256(args.src / EARTH_TIF)},
        ],
        'grid': {
            'crs': 'Moon2000_spole: polar stereographic, latitude of origin -90, central meridian 0, sphere',
            'radiusM': radius,
            'cellM': cell,
            'fullWidthPx': w,
            'fullHeightPx': h,
            'fullX0M': x0_full,
            'fullY0M': y0_full,
            'fullEdgeLatDeg': -85.0,
            'dtype': 'int16',
            'scale': scale,
            'offset': 0.0,
            'nodata': nodata,
        },
        'copy': {
            'note': 'A crop of the full map, centred on the pole. Original int16 values, nothing resampled.',
            'col0': off,
            'row0': off,
            'widthPx': CROP_PX,
            'heightPx': CROP_PX,
            'x0M': x0,
            'y0M': y0,
            'halfWidthM': half,
            'inscribedLatDeg': edge_lat,
            'tilePx': TILE_PX,
            'tileLayout': 'gzip of: Sun layer then Earth layer; each layer is tilePx x tilePx int16 cells, rows from the top (grid +y), stored as row-wise differences (first cell of a row as is, each other cell minus the cell to its left, wrapping in 16 bits), all low bytes then all high bytes',
            'encoding': 'rowdelta-bytesplit-gzip',
            'totalTileBytes': total,
        },
        'tiles': tiles,
        'checks': checks,
    }
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
    size = total + (args.out / 'manifest.json').stat().st_size
    print(f'{len(tiles)} tiles, {total / 1e6:.2f} MB of tiles, {size / 1e6:.2f} MB with the manifest -> {args.out}')
    print(f'copy: {CROP_PX} x {CROP_PX} cells, +/- {half / 1000:.2f} km, everything south of {edge_lat:.3f} deg')
    for c in checks[: len(bundle["datasets"])]:
        print(f"  {c['name']}: Sun {c['sunRaw'] * scale * 100:.1f} % ({c['sun3x3'][0] * scale * 100:.1f}-{c['sun3x3'][1] * scale * 100:.1f}), Earth {c['earthRaw'] * scale * 100:.1f} % ({c['earth3x3'][0] * scale * 100:.1f}-{c['earth3x3'][1] * scale * 100:.1f})")


if __name__ == '__main__':
    main()
