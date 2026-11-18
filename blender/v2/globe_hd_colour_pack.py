"""Colour inputs for the HD globes (project venv). Writes into blender/output/v2/showcase/hd/<body>/ (git-ignored):

  earth/day_colour.png   16384 x 8192 equirect, column 0 at 180 W: NASA GIBS VIIRS NOAA-21 corrected-reflectance true
                         colour of 2026-11-16 (real clouds of that day), its gaps filled from NOAA-20 of the same day,
                         remaining gaps (polar night, not yet imaged) from Blue Marble Next Generation, November 2004.
                         earth/day_colour.json records the fraction of pixels from each source.
  mars/colour.json       the Viking colour mosaic's path and column-0 longitude (read from its CRS; used as is)
Labels: VISUAL. The clouds are those of 2026-11-16 (the newest complete day), not of the scene's timestamp
2026-11-21T02:00Z, which is in the future of the data.

    .venv/bin/python blender/v2/globe_hd_colour_pack.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PROD = ROOT / 'data' / 'cache' / 'v2' / 'products'
HD = ROOT / 'blender' / 'output' / 'v2' / 'showcase' / 'hd'
W, H = 16384, 8192


def read_rgb(p, shape=None):
    import rasterio
    from rasterio.enums import Resampling
    with rasterio.open(p) as d:
        out = (3, *shape) if shape else None
        return d.read([1, 2, 3], out_shape=out, resampling=Resampling.bilinear if shape else Resampling.nearest)


def png_rgb(path, img):
    import struct
    import zlib
    h, w, _ = img.shape

    def ch(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    c = zlib.compressobj(1)
    parts = [c.compress(b'\x00' + img[i].tobytes()) for i in range(h)] + [c.flush()]
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) +
                           ch(b'IDAT', b''.join(parts)) + ch(b'IEND', b''))


def earth():
    """Newest real imagery first: VIIRS NOAA-21 then NOAA-20 for 2026-11-16, then the same for 11-15 and 11-14 (real clouds of
    those days); Blue Marble November 2004 only where none of them has data (polar night)."""
    v = PROD / 'earth_viirs_truecolor_20261116'

    def missing(a):
        return a.astype(np.int32).sum(axis=0) < 12          # GIBS fills unimaged pixels with black
    out = None
    filled = None
    frac = {}
    for day in ('2026-11-16', '2026-11-15', '2026-11-14'):
        for sat in ('NOAA21', 'NOAA20'):
            p = v / f'VIIRS_{sat}_CorrectedReflectance_TrueColor.{day}.8192x4096.jpg'
            if not p.exists():
                continue
            a = read_rgb(p, (H, W))
            ok = ~missing(a)
            if out is None:
                out, filled = a.copy(), ok.copy()
                frac[f'VIIRS {sat} {day} (NASA GIBS)'] = float(ok.mean())
                continue
            take = ok & ~filled
            out[:, take] = a[:, take]
            filled |= take
            frac[f'VIIRS {sat} {day} (NASA GIBS)'] = float(take.mean())
    bm = read_rgb(PROD / 'earth_bmng_200411' / 'world.200411.3x21600x10800.jpg', (H, W))
    rest = ~filled
    out[:, rest] = bm[:, rest]
    frac['Blue Marble NG November 2004 (NASA Earth Observatory)'] = float(rest.mean())
    d = HD / 'earth'
    png_rgb(d / 'day_colour.png', np.ascontiguousarray(np.transpose(out, (1, 2, 0))))
    stats = {'width': W, 'height': H, 'lon0_deg': 180.0, 'sources': frac,
             'note': 'real clouds of 2026-11-14..16 (newest first), not of the scene timestamp; VISUAL'}
    (d / 'day_colour.json').write_text(json.dumps(stats, indent=1) + '\n')
    print('earth day colour', {k: round(x, 3) for k, x in frac.items()})


def mars():
    import rasterio
    p = PROD / 'mars_viking_color_925m' / 'Mars_Viking_ClrMosaic_global_925m.tif'
    with rasterio.open(p) as d:
        crs = d.crs.to_dict()
        R = crs.get('R') or crs.get('a') or 3_396_190.0
        lon0 = (crs.get('lon_0', 0.0) + math.degrees(d.bounds.left / R)) % 360.0
        info = {'path': str(p), 'width': d.width, 'height': d.height, 'count': d.count, 'lon0_deg': lon0, 'crs': crs,
                'note': 'USGS Viking MDIM colorized global mosaic 925 m; VISUAL'}
    (HD / 'mars' / 'colour.json').write_text(json.dumps(info, indent=1, default=str) + '\n')
    print('mars colour', info['width'], info['height'], 'lon0', round(lon0, 3))


if __name__ == '__main__':
    earth()
    if (PROD / 'mars_viking_color_925m' / 'Mars_Viking_ClrMosaic_global_925m.tif').exists():
        mars()
    else:
        print('mars colour: download not finished')
