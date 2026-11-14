#!/usr/bin/env python3
"""Build the viewer's "South Pole map" layer from NASA PGDA product 69 + PGDA 78 site ROIs.

    python3 tools/pgda69/build_layer.py                # downloads (SHA-256 pinned) into data/raw/pgda69/
    python3 tools/pgda69/build_layer.py --raw-dir DIR  # use already-downloaded files

Outputs web/public/layers/pgda69/:
    pgda69.json                       metadata, provenance, ROI polygons + statistics, image index
    {sun,earth}_overview.png          85-90 S, 240 m/px (4x4 block mean of valid 60 m pixels)
    {sun,earth}_<Site>.png            6 km box around each site's ROIs at native 60 m/px

PNG encoding: 8-bit grey, value = round(fraction * 250) (0.4 % steps); 255 = no data.

This is NASA reference data, displayed. It is not a POLARIS computation:
  * Sun: fraction of hourly timesteps over 18.6 years in which ANY part of the solar disc was visible.
  * Earth: same for the Earth's disc (slightly optimistic for radio links).
  * Based on LOLA LDEM_85S_060M (2016 release). Mazarico et al. 2011, Icarus 211, 1066-1081,
    doi:10.1016/j.icarus.2010.10.030.
Requires: numpy, rasterio, pyshp, pillow.
"""
import argparse
import hashlib
import io
import json
import math
import tarfile
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
import rasterio.features
import shapefile
from PIL import Image

R_MOON = 1737400.0
ROOT = Path(__file__).resolve().parents[2]

FILES = {
    'AVGVISIB_85S_060M_201608.TIF': ('https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608.TIF',
                                     'ccf67d4f39e0a970c111196da7d6551ffcf50d075470b93067fb3904c0b05806'),
    'AVGVISIB_85S_060M_201608_EARTH.TIF': ('https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608_EARTH.TIF',
                                           'd71dc5adfff653e0e924e0a4cbf03795b996caa30b4ace3d5843a70a5ab2f3d2'),
    'AVGVISIB_85S_060M_201608.LBL': ('http://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_85S_060M_201608.LBL',
                                     '33decce957d5d4d9608557d8d969d1e1b94056a159b2563624ade4b528a0c917'),
    'AVGVISIB_85S_060M_201608_EARTH.LBL': ('http://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_85S_060M_201608_EARTH.LBL',
                                           '45a61697d779fdb9170bca2553f9e0188aeda1159811d3531c348df8f57f68bd'),
    'Site01_ROIs.tgz': ('https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site01/Site01_ROIs.tgz',
                        '40b961417a344ce0274aecbab522e171a22f658507d82e8fb4d7bc97526ffc4f'),
    'Site04_ROIs.tgz': ('https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site04/Site04_ROIs.tgz',
                        '8e8b788f9fdf6400f23fd36dad02138102bd1a905b4b71a5739a9a4fd8a0e07a'),
    'Site07_ROIs.tgz': ('https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site07/Site07_ROIs.tgz',
                        '694d85297c40133e91570f020e46f7fd0b25c14e94f0a7c5b6d001e8728bddbe'),
    'Site11_ROIs.tgz': ('https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site11/Site11_ROIs.tgz',
                        '6ec7a3110717f3d0b76abc49fe634580f2960f216372f835ae6a7d5797c4d278'),
}
SITES = {  # PGDA 78 site names (product page)
    'Site01': 'Connecting ridge',
    'Site04': 'Shackleton rim',
    'Site07': 'Peak near Shackleton',
    'Site11': 'de Gerlache rim',
}
CROP_M = 6000.0
OVERVIEW_BLOCK = 4
Q = 250.0
NODATA_Q = 255


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def fetch(raw):
    raw.mkdir(parents=True, exist_ok=True)
    for name, (url, want) in FILES.items():
        p = raw / name
        if not p.exists():
            print('download', url)
            with urllib.request.urlopen(url, timeout=300) as r:
                p.write_bytes(r.read())
        got = sha256(p)
        if got != want:
            raise SystemExit(f'SHA-256 mismatch for {name}: {got} != pinned {want}')


def xy_to_latlon(x, y):
    """South polar stereographic on a sphere, true scale at the pole (matches the GeoTIFF CRS)."""
    rho = math.hypot(x, y)
    lat = -90.0 + math.degrees(2 * math.atan(rho / (2 * R_MOON)))
    lon = math.degrees(math.atan2(x, y))
    return lat, lon


def latlon_to_xy(lat, lon):
    rho = 2 * R_MOON * math.tan(math.radians(90.0 + lat) / 2)
    return rho * math.sin(math.radians(lon)), rho * math.cos(math.radians(lon))


def read_map(path):
    with rasterio.open(path) as d:
        crs = d.crs.to_proj4()
        if '+proj=stere' not in crs or '+lat_0=-90' not in crs or '+R=1737400' not in crs:
            raise SystemExit(f'{path}: unexpected CRS {crs}')
        if abs(d.transform.a - 60) > 1e-9 or abs(d.transform.e + 60) > 1e-9:
            raise SystemExit(f'{path}: unexpected pixel size {d.transform}')
        dn = d.read(1).astype(np.int32)
        valid = dn != int(d.nodata)
        frac = np.where(valid, dn * d.scales[0] + d.offsets[0], np.nan)
        return frac, d.transform, crs


def quantize(a):
    q = np.where(np.isnan(a), NODATA_Q, np.clip(np.rint(a * Q), 0, Q)).astype(np.uint8)
    return q


def png(arr, path):
    buf = io.BytesIO()
    Image.fromarray(arr, mode='L').save(buf, format='PNG', optimize=True)
    path.write_bytes(buf.getvalue())
    return len(buf.getvalue())


def block_mean(a, k):
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    b = a[:h, :w].reshape(h // k, k, w // k, k)
    with np.errstate(invalid='ignore'):
        return np.nanmean(b, axis=(1, 3))


def rois(raw):
    out = []
    for site in SITES:
        with tarfile.open(raw / f'{site}_ROIs.tgz') as t:
            mem = {Path(m.name).suffix: t.extractfile(m).read() for m in t.getmembers() if m.isfile()}
        r = shapefile.Reader(shp=io.BytesIO(mem['.shp']), shx=io.BytesIO(mem['.shx']), dbf=io.BytesIO(mem['.dbf']))
        prj = mem['.prj'].decode()
        if 'Stereographic_South_Pole' not in prj or '1737400' not in prj:
            raise SystemExit(f'{site}: unexpected ROI projection')
        for k, (shp, rec) in enumerate(zip(r.shapes(), r.records()), start=1):
            ring = [(float(x), float(y)) for x, y in shp.points]
            # polygon area centroid (shoelace)
            a = cx = cy = 0.0
            for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
                c = x0 * y1 - x1 * y0
                a += c
                cx += (x0 + x1) * c
                cy += (y0 + y1) * c
            a *= 0.5
            cx, cy = cx / (6 * a), cy / (6 * a)
            lat, lon = xy_to_latlon(cx, cy)
            out.append({'site': site, 'siteName': SITES[site], 'roi': k, 'id': f'{site}-ROI{k}',
                        'centroidXY': [round(cx, 2), round(cy, 2)], 'lat': round(lat, 5), 'lonE': round(lon, 5),
                        'areaM2': round(abs(a), 1),
                        'ring': [[round(x, 2), round(y, 2)] for x, y in ring]})
    return out


def zonal(frac, transform, ring):
    mask = rasterio.features.geometry_mask([{'type': 'Polygon', 'coordinates': [ring]}], out_shape=frac.shape,
                                           transform=transform, invert=True, all_touched=True)
    v = frac[mask]
    v = v[~np.isnan(v)]
    return {'n60mPixels': int(v.size), 'mean': round(float(v.mean()) * 100, 2), 'min': round(float(v.min()) * 100, 2),
            'max': round(float(v.max()) * 100, 2)} if v.size else {'n60mPixels': 0}


def at_point(frac, transform, x, y):
    col, row = ~transform * (x, y)
    r, c = int(math.floor(row)), int(math.floor(col))
    v = frac[r, c]
    return None if np.isnan(v) else round(float(v) * 100, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw-dir', default=str(ROOT / 'data' / 'raw' / 'pgda69'))
    ap.add_argument('--out', default=str(ROOT / 'web' / 'public' / 'layers' / 'pgda69'))
    cfg = ap.parse_args()
    raw, out = Path(cfg.raw_dir), Path(cfg.out)
    fetch(raw)
    out.mkdir(parents=True, exist_ok=True)

    layers = {}
    for key, name in (('sun', 'AVGVISIB_85S_060M_201608.TIF'), ('earth', 'AVGVISIB_85S_060M_201608_EARTH.TIF')):
        frac, tr, crs = read_map(raw / name)
        layers[key] = (frac, tr)
    tr = layers['sun'][1]
    if layers['earth'][1] != tr:
        raise SystemExit('Sun and Earth maps are on different grids')

    roi_list = rois(raw)
    for r in roi_list:
        r['sun'] = zonal(layers['sun'][0], tr, r['ring'])
        r['earth'] = zonal(layers['earth'][0], tr, r['ring'])
        r['sunAtCentroid'] = at_point(layers['sun'][0], tr, *r['centroidXY'])
        r['earthAtCentroid'] = at_point(layers['earth'][0], tr, *r['centroidXY'])

    images = {'overview': {}, 'sites': {}}
    x0, y0, px = tr.c, tr.f, tr.a  # upper-left corner, pixel size
    n = layers['sun'][0].shape[0]
    k = OVERVIEW_BLOCK
    m = n // k
    for key, (frac, _) in layers.items():
        png(quantize(block_mean(frac, k)), out / f'{key}_overview.png')
        images['overview'][key] = {'file': f'{key}_overview.png'}
    images['overview'].update({'width': m, 'height': m, 'pixelM': px * k, 'x0': x0, 'y0': y0, 'resample': f'{k}x{k} block mean of valid 60 m pixels'})

    for site in SITES:
        pts = np.array([p for r in roi_list if r['site'] == site for p in r['ring']])
        cx, cy = pts[:, 0].mean(), pts[:, 1].mean()
        half = CROP_M / 2
        c0 = int(math.floor((cx - half - x0) / px))
        r0 = int(math.floor((y0 - (cy + half)) / px))
        w = int(round(CROP_M / px))
        c0, r0 = max(0, min(n - w, c0)), max(0, min(n - w, r0))
        entry = {'width': w, 'height': w, 'pixelM': px, 'x0': x0 + c0 * px, 'y0': y0 - r0 * px, 'resample': 'native 60 m'}
        for key, (frac, _) in layers.items():
            png(quantize(frac[r0:r0 + w, c0:c0 + w]), out / f'{key}_{site}.png')
            entry[key] = {'file': f'{key}_{site}.png'}
        images['sites'][site] = entry

    meta = {
        'schema': 'POLARIS-X-layer-pgda69-v1',
        'kind': 'NASA_REFERENCE_PRODUCT',
        'title': 'NASA PGDA 69: average Sun and Earth visibility, 85-90 S',
        'product': 'https://pgda.gsfc.nasa.gov/products/69',
        'roiProduct': 'https://pgda.gsfc.nasa.gov/products/78',
        'citation': 'Mazarico, E., et al. (2011), Illumination conditions of the lunar polar regions using LOLA topography, Icarus, 211, 1066-1081, doi:10.1016/j.icarus.2010.10.030',
        'meaning': {
            'sun': 'Fraction of hourly timesteps over 18.6 years (one lunar nutation cycle) in which any part of the solar disc was visible from the surface pixel.',
            'earth': 'Same for the Earth: visible if any part of its disc is unobscured (slightly optimistic for radio links).',
        },
        'basis': 'LOLA LDEM_85S_060M (2016 release), surface pixel (no mast), 60 m/px',
        'notAPolarisComputation': True,
        'caveats': [
            '18.6-year average at the surface: not a specific mission window, not a mast height.',
            'Single 60 m pixels can vary strongly on ridges; compare regions and rankings, not one pixel.',
            'Visible means any part of the disc, not the centre (POLARIS bundles report centre visibility).',
            'Isolated very dark 60 m pixels appear in places; a POLARIS comparison suggests pits in the older 2016 60 m DEM (hypothesis, not checked).',
        ],
        'crs': '+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400 +units=m (same grid axes as POLARIS DEM crops)',
        'encoding': {'scale': 1 / Q, 'nodata': NODATA_Q, 'note': 'grey value / 250 = fraction (0.4 % steps); 255 = no data'},
        'sources': [{'file': f, 'url': u, 'sha256': h} for f, (u, h) in FILES.items()],
        'images': images,
        'rois': roi_list,
        'generatedBy': 'tools/pgda69/build_layer.py',
    }
    (out / 'pgda69.json').write_text(json.dumps(meta, separators=(',', ':')))
    print('wrote', out)
    for r in roi_list:
        print(f"{r['id']:13s} lat {r['lat']:.5f} lon {r['lonE']:.5f}  Sun mean {r['sun'].get('mean')} (centroid {r['sunAtCentroid']})  Earth mean {r['earth'].get('mean')} (centroid {r['earthAtCentroid']})")


if __name__ == '__main__':
    main()
