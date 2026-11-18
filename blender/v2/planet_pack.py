"""Inputs for the full-scale Mars and Mercury globes (project venv; Blender computes nothing). Like the Moon's globe pack:
heights on the same equal-angle cube-sphere nodes (cubesphere.py), the bundle's Sun and Earth directions, and for
Mercury the MDIS colour mosaic as an equirectangular texture.

    .venv/bin/python blender/v2/planet_pack.py [--n 256]

Sources (already downloaded, each with a manifest entry; nothing new is fetched):
  Mars     MOLA MEGDR 16 ppd global radius grid megr90n000eb.img (5760 x 2880, MSB int16, radius - 3 396 000 m, 0-360 E)
  Mercury  USGS MESSENGER global DEM 665 m v2 (23040 x 11520 int16, m above 2 439 400 m, -180..180 E)
           MDIS Basemap Enhanced Colour Mosaic 665 m (VISUAL: false-colour enhanced, not albedo)
Sun / Earth: the first sample of each world's solver bundle, topocentric az/el at the bundle site rotated to body-fixed
axes (site ENU -> body-fixed; Sun parallax across the planet is negligible for a whole-disc view).
Writes blender/output/v2/showcase/planets/<world>/{heights_n<n>.npy, colour.png (Mercury), pack.json}. Git-ignored.
Labels: heights SOURCE-BASED · UNVALIDATED; Mars uniform tint VISUAL; Mercury colour VISUAL (enhanced colour).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import struct
import sys
import zlib
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'blender'))
from v2 import cubesphere  # noqa: E402

PROD = Path('/Users/anishmeruva/Documents/ChatGPT/NSA/data/cache/v2/products') if not (ROOT / 'data' / 'cache').exists() else \
    ROOT / 'data' / 'cache' / 'v2' / 'products'
OUT = ROOT / 'blender' / 'output' / 'v2' / 'showcase' / 'planets'
WORLDS = {
    'mars': {'radius_m': 3_396_000.0, 'bundle': 'data/worlds/mars/mars_jezero_rim_2026-11-14_687d_mast1m.json.gz',
             'dem': 'mars_mola_megdr_016/meg016/megr90n000eb.img', 'dem_name': 'MOLA MEGDR 16 ppd radius (megr90n000eb)'},
    'mercury': {'radius_m': 2_439_400.0, 'bundle': 'data/worlds/mercury/mercury_prokofiev_rim_2026-11-14_176d_mast1m.json',
                'dem': 'mercury_usgs_dem_665m_v2/Mercury_Messenger_USGS_DEM_Global_665m_v2.tif',
                'dem_name': 'USGS MESSENGER global DEM 665 m v2',
                'colour': 'mercury_mdis_color_665m/Mercury_MESSENGER_MDIS_Basemap_EnhancedColor_Mosaic_Global_665m.tif'},
}


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def png(path, img):
    h, w, _ = img.shape
    raw = b''.join(b'\x00' + img[i].tobytes() for i in range(h))

    def ch(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) +
                           ch(b'IDAT', zlib.compress(raw, 6)) + ch(b'IEND', b''))


def equirect(world):
    """(heights m above the world radius, lon0_deg of column 0) as a full-globe equirect array, top row = 90 N."""
    p = PROD / WORLDS[world]['dem']
    if world == 'mars':
        a = np.fromfile(p, dtype='>i2').reshape(2880, 5760).astype(np.float32)
        return a, 0.0                                               # MEGDR: column 0 starts at 0 E, east-positive
    import rasterio
    from rasterio.enums import Resampling
    with rasterio.open(p) as d:
        a = d.read(1, out_shape=(5760, 11520), resampling=Resampling.average, masked=True).astype(np.float32)
        a = a.filled(np.nan) * float(d.scales[0]) + float(d.offsets[0])     # USGS DN x 0.5 m (raster scale tag)
        lon0 = lon_left(d)
    a = np.where(np.isfinite(a), a, np.nanmedian(a))                # the USGS DEM is gap-free; guard only
    return a, lon0


def lon_left(d):
    """East longitude of column 0's left edge from the CRS central meridian + geotransform (as science/worlds/grids.py)."""
    crs = d.crs.to_dict()
    if crs.get('proj') != 'eqc' or abs(d.bounds.right - d.bounds.left - 2 * math.pi * crs['R']) > 1e3:
        raise ValueError(f'not a global equirectangular grid: {crs}')
    return (crs.get('lon_0', 0.0) + math.degrees(d.bounds.left / crs['R'])) % 360.0


def sample(a, lon0, la, lo):
    h, w = a.shape
    row = (90.0 - la) / 180.0 * h - 0.5
    col = ((lo - lon0) % 360.0) / 360.0 * w - 0.5
    ap = np.concatenate([a[:, -1:], a, a[:, :1]], axis=1)          # wrap in longitude
    return ndimage.map_coordinates(ap, [np.clip(row, 0, h - 1), col + 1], order=1, mode='nearest')


def sky(world):
    p = ROOT / WORLDS[world]['bundle']
    b = json.loads(gzip.decompress(p.read_bytes()) if p.suffix == '.gz' else p.read_text())
    s, site = b['samples'][0], b['site']
    la, lo = math.radians(site['lat_deg']), math.radians(site['lon_deg_east'])
    E = np.array([-math.sin(lo), math.cos(lo), 0.0])
    N = np.array([-math.sin(la) * math.cos(lo), -math.sin(la) * math.sin(lo), math.cos(la)])
    U = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
    out = {'utc': s['utc'], 'site': site.get('id'), 'bundle': WORLDS[world]['bundle'], 'bundleSha256': sha(p)}
    for body in ('sun', 'earth'):
        az, el = math.radians(s[body]['az_deg']), math.radians(s[body]['el_deg'])
        v = math.cos(el) * math.sin(az) * E + math.cos(el) * math.cos(az) * N + math.sin(el) * U
        out[body] = (v / np.linalg.norm(v)).tolist()
        out[body + 'RangeAu'] = s[body]['range_au']
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=256)
    a = ap.parse_args(argv)
    for world, cfg in WORLDS.items():
        d = OUT / world
        d.mkdir(parents=True, exist_ok=True)
        arr, lon0 = equirect(world)
        A, B = cubesphere.node_params(a.n)
        H = np.empty((6, a.n + 1, a.n + 1), np.float32)
        for f in range(6):
            la, lo = cubesphere.latlon_deg(cubesphere.directions(f, A, B))
            H[f] = sample(arr, lon0, la, lo)
        np.save(d / f'heights_n{a.n}.npy', H)
        meta = {'world': world, 'radius_m': cfg['radius_m'], 'n': a.n, 'heights': f'heights_n{a.n}.npy',
                'heightRangeM': [float(H.min()), float(H.max())], 'dem': cfg['dem_name'], 'demLon0': lon0,
                'demFile': cfg['dem'], 'demSha256': sha(PROD / cfg['dem']), 'sky': sky(world),
                'nodeSpacingKm': [x / 1e3 for x in cubesphere.node_spacing_m(a.n, cfg['radius_m'])]}
        if 'colour' in cfg:
            import rasterio
            from rasterio.enums import Resampling
            with rasterio.open(PROD / cfg['colour']) as src:
                rgb = src.read(out_shape=(3, 2048, 4096), resampling=Resampling.average)
                c_lon0 = lon_left(src)
            png(d / 'colour.png', np.ascontiguousarray(np.transpose(rgb, (1, 2, 0)).astype(np.uint8)))
            meta.update(colour='colour.png', colourLon0=c_lon0, colourFile=cfg['colour'], colourSha256=sha(PROD / cfg['colour']))
        (d / 'pack.json').write_text(json.dumps(meta, indent=1) + '\n')
        print(world, 'heights', meta['heightRangeM'], 'node spacing km', [round(x, 1) for x in meta['nodeSpacingKm']])


if __name__ == '__main__':
    main()
