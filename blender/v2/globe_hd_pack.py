"""Inputs for the high-detail, full-scale globes (Moon, Mars, Mercury, Earth) and the Sun / Earth-Moon system scene.
Project venv; Blender computes nothing.

    .venv/bin/python blender/v2/globe_hd_pack.py [--bodies moon,mars,mercury,earth] [--n 384]

Per body, in blender/output/v2/showcase/hd/<body>/ (git-ignored):
  height.png      the global height map, equirectangular 23040 x 11520 (Earth 21600 x 10800), heights in metres above the
                  body's reference sphere packed as q = round((h - hmin) / (hmax - hmin) * 65535), R = q >> 8, G = q & 255
                  (8-bit RGB PNG; sampled with "Closest" in Blender so the two bytes are never interpolated apart)
  base_n<n>.npy   heights at the cube-sphere nodes (the viewport mesh); the render displaces by (map - base)
  meta.json       radius, hmin/hmax, column-0 longitude, sources and SHA-256, the Sun/Earth/Moon directions
Sources (local, each with its manifest; nothing is fetched here):
  Moon     LOLA LDEM_64 float (64 ppd, km above 1737.4 km)                              ~0.47 km/px
  Mars     MOLA MEGDR 128 ppd radius tiles (16; 2x2 block mean -> 64 ppd; 88-90 deg from 16 ppd), - 3 396 000 m  ~0.93 km/px
  Mercury  USGS MESSENGER DEM 665 m v2 (DN x 0.5 m above 2 439.4 km)                    ~0.67 km/px
  Earth    NOAA ETOPO 2022 v1 60 arc-second surface elevation (m above the geoid, placed on a 6 371 km sphere)  ~1.85 km/px
Geometry at UTC (default 2026-11-21T02:00Z) from NAIF SPICE (de421, pck00010, moon_pa_de421, moon_080317.tf):
  Sun and Earth/Moon directions in each body-fixed frame (IAU_EARTH, MOON_ME, IAU_MARS, IAU_MERCURY), and for the
  Earth-Moon system: Moon and Sun positions in J2000 relative to Earth plus the rotations IAU_EARTH->J2000, MOON_ME->J2000.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'blender'))
from v2 import cubesphere  # noqa: E402

DATA = ROOT / 'data' / 'cache' / 'v2'
PROD = DATA / 'products'
SPICE = DATA / 'render_vs_real' / 'spice'
PYLIB = DATA / 'render_vs_real' / 'pylib'
OUT = ROOT / 'blender' / 'output' / 'v2' / 'showcase' / 'hd'
R = {'moon': 1_737_400.0, 'mars': 3_396_000.0, 'mercury': 2_439_400.0, 'earth': 6_371_000.0, 'sun': 695_700_000.0}
FRAME = {'moon': 'MOON_ME', 'mars': 'IAU_MARS', 'mercury': 'IAU_MERCURY', 'earth': 'IAU_EARTH'}
NAIF = {'moon': 'MOON', 'mars': 'MARS BARYCENTER', 'mercury': 'MERCURY', 'earth': 'EARTH', 'sun': 'SUN'}


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def png_rgb(path, img, level=1):
    h, w, _ = img.shape

    def ch(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    comp = zlib.compressobj(level)
    parts = [comp.compress(b'\x00' + img[i].tobytes()) for i in range(h)]
    parts.append(comp.flush())
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) +
                           ch(b'IDAT', b''.join(parts)) + ch(b'IEND', b''))


def moon():
    """SLDEM2015 (LOLA + Kaguya TC, 512 ppd, +-60 deg; 8x8 block mean -> 64 ppd) where it exists, LOLA LDEM_64 poleward.
    SLDEM2015 removes most of the north-south interpolation streaks between LOLA tracks at low latitudes."""
    p = PROD / 'lola_ldem_global/data/lola_gdr/cylindrical/float_img/ldem_64_float.img'
    a = np.fromfile(p, dtype='<f4').reshape(11520, 23040) * 1000.0
    files = [str(p.relative_to(DATA))]
    td = PROD / 'sldem2015_512/data/sldem2015/tiles/float_img'
    import re
    for t in sorted(td.glob('sldem2015_512_*_float.img')):
        m = re.match(r'sldem2015_512_(\d\d)([ns])_(\d\d)([ns])_(\d{3})_(\d{3})_float\.img', t.name)
        la0 = int(m.group(1)) * (1 if m.group(2) == 'n' else -1)
        la1 = int(m.group(3)) * (1 if m.group(4) == 'n' else -1)
        top, lo0 = max(la0, la1), int(m.group(5))
        x = np.memmap(t, dtype='<f4', mode='r').reshape(15360, 23040)
        blk = np.asarray(x).reshape(1920, 8, 2880, 8).mean(axis=(1, 3)) * 1000.0
        r0, c0 = (90 - top) * 64, lo0 * 64
        ok = np.isfinite(blk) & (blk > -20000) & (blk < 20000)
        sub = a[r0:r0 + 1920, c0:c0 + 2880]
        sub[ok] = blk[ok]
        files.append(str(t.relative_to(DATA)))
    return a, 0.0, files, 'SLDEM2015 512 ppd (8x8 mean -> 64 ppd) within +-60 deg, LOLA LDEM_64 poleward (m above 1737.4 km)'


def mars():
    d = PROD / 'mars_mola_megdr_128_global'
    out = np.full((11520, 23040), np.nan, np.float32)
    files = []
    for bi, lat in enumerate(('88n', '44n', '00n', '44s')):
        for li, lon in enumerate(('000', '090', '180', '270')):
            p = d / f'megr{lat}{lon}hb.img'
            t = np.fromfile(p, dtype='>i2').reshape(5632, 11520).astype(np.float32)
            t = t.reshape(2816, 2, 5760, 2).mean(axis=(1, 3))
            r0 = 128 + bi * 2816                       # 64 ppd rows: 90-88 N are rows 0..127
            out[r0:r0 + 2816, li * 5760:(li + 1) * 5760] = t
            files.append(str(p.relative_to(DATA)))
    g16 = np.fromfile(PROD / 'mars_mola_megdr_016/meg016/megr90n000eb.img', dtype='>i2').reshape(2880, 5760).astype(np.float32)
    up = np.repeat(np.repeat(g16, 4, 0), 4, 1)          # 16 -> 64 ppd for the polar caps beyond the 128 ppd tiles
    hole = ~np.isfinite(out)
    out[hole] = up[hole]
    files.append('products/mars_mola_megdr_016/meg016/megr90n000eb.img')
    return out, 0.0, files, 'MOLA MEGDR 128 ppd radius tiles (2x2 mean -> 64 ppd; |lat| > 88 from 16 ppd), m above 3 396 km'


def mercury():
    import rasterio
    p = PROD / 'mercury_usgs_dem_665m_v2/Mercury_Messenger_USGS_DEM_Global_665m_v2.tif'
    with rasterio.open(p) as d:
        a = d.read(1, masked=True).astype(np.float32)
        a = a.filled(np.nan) * float(d.scales[0]) + float(d.offsets[0])
        crs = d.crs.to_dict()
        lon0 = (crs.get('lon_0', 0.0) + np.degrees(d.bounds.left / crs['R'])) % 360.0
    a = np.where(np.isfinite(a), a, np.nanmedian(a))
    return a, float(lon0), [str(p.relative_to(DATA))], 'USGS MESSENGER DEM 665 m v2 (DN x 0.5 m above 2 439.4 km)'


def earth():
    sys.path.append(str(PYLIB))
    import h5py
    p = PROD / 'earth_etopo2022_60s/ETOPO_2022_v1_60s_N90W180_surface.nc'
    with h5py.File(p, 'r') as f:
        z = f['z'][...].astype(np.float32)
        lat = f['lat'][...]
        lon = f['lon'][...]
    if lat[0] < lat[-1]:
        z = z[::-1]                                     # top row = north
    lon0 = float(lon[0]) - 0.5 * float(lon[1] - lon[0])
    return z, lon0 % 360.0, [str(p.relative_to(DATA))], 'NOAA ETOPO 2022 v1 60 arc-second surface (m above the geoid; on a 6 371 km sphere)'


def sample(a, lon0, la, lo):
    h, w = a.shape
    row = (90.0 - la) / 180.0 * h - 0.5
    col = ((lo - lon0) % 360.0) / 360.0 * w - 0.5
    ap = np.concatenate([a[:, -1:], a, a[:, :1]], axis=1)
    return ndimage.map_coordinates(ap, [np.clip(row, 0, h - 1), col + 1], order=1, mode='nearest')


def geometry(utc):
    sys.path.append(str(PYLIB))
    import spiceypy as sp
    sp.kclear()
    for k in ('naif0012.tls', 'pck00010.tpc', 'moon_pa_de421_1900_2050.bpc', 'moon_080317.tf', 'moon_assoc_me.tf', 'de421.bsp'):
        sp.furnsh(str(SPICE / k))
    et = sp.utc2et(utc.replace('Z', ''))

    def unit(v):
        v = np.asarray(v, float)
        return (v / np.linalg.norm(v)).tolist()
    out = {'utc': utc, 'kernels': ['naif0012.tls', 'pck00010.tpc', 'moon_pa_de421_1900_2050.bpc', 'moon_080317.tf',
                                   'moon_assoc_me.tf', 'de421.bsp']}
    for body, frame in FRAME.items():
        s, _ = sp.spkpos('SUN', et, frame, 'LT+S', NAIF[body])
        e, _ = sp.spkpos('EARTH', et, frame, 'LT+S', NAIF[body]) if body != 'earth' else sp.spkpos('MOON', et, frame, 'LT+S', 'EARTH')
        out[body] = {'sun': unit(s), 'sunRangeKm': float(np.linalg.norm(s)), 'viewer': unit(e),
                     'viewerName': 'Earth' if body != 'earth' else 'Moon'}
    m, _ = sp.spkpos('MOON', et, 'J2000', 'LT+S', 'EARTH')
    s, _ = sp.spkpos('SUN', et, 'J2000', 'LT+S', 'EARTH')
    out['system'] = {'frame': 'J2000, Earth-centred, km', 'moonPosKm': list(map(float, m)), 'sunPosKm': list(map(float, s)),
                     'earthToJ2000': np.asarray(sp.pxform('IAU_EARTH', 'J2000', et)).tolist(),
                     'moonToJ2000': np.asarray(sp.pxform('MOON_ME', 'J2000', et)).tolist(),
                     'sunToJ2000': np.asarray(sp.pxform('IAU_SUN', 'J2000', et)).tolist()}
    sp.kclear()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--bodies', default='moon,mars,mercury,earth')
    ap.add_argument('--n', type=int, default=384)
    ap.add_argument('--utc', default='2026-11-21T02:00Z')
    a = ap.parse_args(argv)
    geo = geometry(a.utc)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'geometry.json').write_text(json.dumps(geo, indent=1) + '\n')
    for body in a.bodies.split(','):
        arr, lon0, files, desc = {'moon': moon, 'mars': mars, 'mercury': mercury, 'earth': earth}[body]()
        d = OUT / body
        d.mkdir(parents=True, exist_ok=True)
        hmin, hmax = float(np.nanmin(arr)), float(np.nanmax(arr))
        q = np.round((np.nan_to_num(arr, nan=hmin) - hmin) / (hmax - hmin) * 65535).astype(np.uint32)
        rgb = np.zeros(arr.shape + (3,), np.uint8)
        rgb[..., 0] = q >> 8
        rgb[..., 1] = q & 255
        png_rgb(d / 'height.png', rgb)
        A, B = cubesphere.node_params(a.n)
        base = np.empty((6, a.n + 1, a.n + 1), np.float32)
        for f in range(6):
            la, lo = cubesphere.latlon_deg(cubesphere.directions(f, A, B))
            base[f] = sample(arr, lon0, la, lo)
        np.save(d / f'base_n{a.n}.npy', base)
        meta = {'body': body, 'radius_m': R[body], 'height_png': 'height.png', 'width': int(arr.shape[1]), 'height': int(arr.shape[0]),
                'hmin_m': hmin, 'hmax_m': hmax, 'lon0_deg': lon0, 'quant_m': (hmax - hmin) / 65535, 'source': desc,
                'files': [{'path': f, 'sha256': sha(DATA / f)} for f in files], 'base': f'base_n{a.n}.npy', 'n': a.n,
                'px_km_equator': 2 * np.pi * R[body] / 1e3 / arr.shape[1], 'geometry': geo[body]}
        (d / 'meta.json').write_text(json.dumps(meta, indent=1) + '\n')
        print(body, arr.shape, f'h {hmin:.0f}..{hmax:.0f} m', f"px {meta['px_km_equator']:.2f} km", flush=True)


if __name__ == '__main__':
    main()
