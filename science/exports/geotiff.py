"""GeoTIFF masks and maps from precomputed results (values copied, never resampled).

* `safety(site)`: the 9 x 9 position grid of `data/cubes/<site>/terrain_safety.json` (25 m step, south-polar
  stereographic grid metres around the site) -> one float64 GeoTIFF, one band per quantity. Pixel centre = cube
  position. Thresholds are ENGINEERING ASSUMPTIONS; k of N maps is not a probability.
* `global_grid()`: the 10 deg global grid of `data/anysite/precompute_summary.json` -> lon/lat GeoTIFF on the
  1 737.4 km sphere (pixel centre = grid point; no site -> nodata).
* `polar_points()`: the 1 deg polar grids are rings, not a lon/lat raster -> CSV points.

The outputs are NASA-derived rasters: they are written under data/exports/ (git-ignored).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from .. import frames, sites
from . import common as C

# IAU_2015 codes from the PROJ database; their proj4 equals the bundles' grid_crs (+proj=stere +lat_0=-90 ... +R=1737400)
# and the 1 737.4 km lon/lat sphere exactly (checked by test_exports).
STEREO_S = 'IAU_2015:30135'      # Moon (2015) - Sphere / Ocentric / South Polar
LONLAT = 'IAU_2015:30100'        # Moon (2015) - Sphere / Ocentric
PRECOMPUTE = C.ROOT / 'data' / 'anysite' / 'precompute_summary.json'
CUBES = C.ROOT / 'data' / 'cubes'
NODATA = float('nan')


def _write(path, bands, descs, transform, crs, tags, band_tags):
    import rasterio
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.stack(bands).astype('float64')
    with rasterio.open(path, 'w', driver='GTiff', width=arr.shape[2], height=arr.shape[1], count=arr.shape[0],
                       dtype='float64', crs=rasterio.crs.CRS.from_string(crs), transform=transform, nodata=NODATA,
                       compress='deflate') as ds:
        ds.write(arr)
        ds.update_tags(**{k: (v if isinstance(v, str) else json.dumps(v)) for k, v in tags.items()})
        for i, (d, bt) in enumerate(zip(descs, band_tags), start=1):
            ds.set_band_description(i, d)
            ds.update_tags(i, **{k: (v if isinstance(v, str) else json.dumps(v)) for k, v in bt.items()})
    return path


def site_xy(site):
    s = sites.SITES[site]
    return frames.stereo_forward(s['lat'], s['lon'])


def safety_layout(cube):
    """Offsets (dx, dy) of the D_pos axis -> (row, col) in a north-up raster. Row-major in the cube: dx outer, dy inner."""
    offs = [tuple(float(v) for v in s.split(',')) for s in cube['dims'][1]['values']]
    xs = sorted({o[0] for o in offs}); ys = sorted({o[1] for o in offs}, reverse=True)
    step = xs[1] - xs[0]
    assert all(abs((b - a) - step) < 1e-9 for a, b in zip(xs, xs[1:])), 'D_pos x offsets are not a regular grid'
    rc = [(ys.index(dy), xs.index(dx)) for dx, dy in offs]
    return offs, xs, ys, step, rc


def safety(site, out_dir):
    from rasterio.transform import from_origin
    p = CUBES / site / 'terrain_safety.json'
    cube = C.read_json(p); sha = C.sha256_file(p)
    offs, xs, ys, step, rc = safety_layout(cube)
    x0, y0 = site_xy(site)
    nP = len(offs); nr, nc = len(ys), len(xs)
    T = cube['dims'][0]['values']

    def grid(vals):
        g = np.full((nr, nc), NODATA)
        for k, (r, c) in enumerate(rc):
            v = vals[k]
            g[r, c] = NODATA if v is None else float(v)
        return g
    bands, descs, btags = [], [], []
    land = cube['metrics']['landing_slope_100m']
    for ti in (0,):
        vals = land['values'][ti * nP:(ti + 1) * nP]
        bands.append(grid(vals)); descs.append(f'landing_slope_100m_{T[ti]}')
        btags.append({'unit': land['units'], 'label': C.LABEL, 'json_path': f'metrics.landing_slope_100m.values[{ti}*{nP}+k]',
                      'source': land['provenance']})
    sl = cube['derived']['safe_and_lit']
    rdim = sl['dims'][0]
    for name, m in sl['metrics'].items():
        for ri, lim in enumerate(rdim['values']):
            vals = m['values'][ri * nP:(ri + 1) * nP]
            bands.append(grid([None if v is None else (1.0 if v is True else 0.0 if v is False else v) for v in vals]))
            descs.append(f'{name}_slope_lt_{lim:g}deg')
            btags.append({'unit': m.get('units', ''), 'label': f'{C.LABEL} · {C.ENGINEERING} threshold {lim:g} deg',
                          'json_path': f'derived.safe_and_lit.metrics.{name}.values[{ri}*{nP}+k]',
                          'description': m['label'], 'note': C.K_OF_N})
    tr = from_origin(x0 + xs[0] - step / 2, y0 + ys[0] + step / 2, step, step)
    tags = {'POLARIS_LABEL': C.LABEL, 'POLARIS_SOURCE_FILE': C.rel(p), 'POLARIS_SOURCE_SHA256': sha,
            'POLARIS_CUBE_ID': cube['cube_id'], 'POLARIS_RECOMPUTE': cube['provenance']['command'],
            'POLARIS_SITE': site, 'POLARIS_SITE_GRID_XY_M': [x0, y0],
            'POLARIS_PIXEL_INDEX': 'pixel (row, col) = cube D_pos k with dx -> col (west->east), dy -> row (north->south)',
            'POLARIS_NOTE': f'{C.K_OF_N}; thresholds are {C.ENGINEERING}; slopes from PGDA 78 5 m (NASA-derived: not committed)',
            'POLARIS_EXPORT': C.EXPORT_VERSION}
    out = _write(Path(out_dir) / f'{site}_terrain_safety.tif', bands, descs, tr, STEREO_S, tags, btags)
    return {'path': out, 'source': p, 'sha256': sha, 'bands': descs, 'cube': cube, 'layout': (offs, xs, ys, step, rc),
            'site_xy': (x0, y0)}


GRID_FIELDS = (('sun_pct', '% of hourly samples'), ('earth_pct', '% of hourly samples'),
               ('sun_earth_pct', '% of hourly samples'), ('longest_sun_gap_h', 'h'))


def global_grid(out_dir, summary_path=PRECOMPUTE):
    from rasterio.transform import from_origin
    d = C.read_json(summary_path); sha = C.sha256_file(summary_path)
    idx = {(round(s['lat'], 6), round(s['lon'], 6)): (i, s) for i, s in enumerate(d['sites'])
           if s['group'] == 'global_grid_10deg' and s['status'] == 'done'}
    lats = sorted({k[0] for k in idx}, reverse=True); lons = sorted({k[1] for k in idx})
    st = lons[1] - lons[0]
    bands = []
    for f, _ in GRID_FIELDS:
        g = np.full((len(lats), len(lons)), NODATA)
        for (la, lo), (_, s) in idx.items():
            v = s.get(f)
            g[lats.index(la), lons.index(lo)] = NODATA if v is None else float(v)
        bands.append(g)
    tr = from_origin(lons[0] - st / 2, lats[0] + st / 2, st, st)
    tags = {'POLARIS_LABEL': C.LABEL, 'POLARIS_SOURCE_FILE': C.rel(summary_path), 'POLARIS_SOURCE_SHA256': sha,
            'POLARIS_WINDOW': d.get('window'), 'POLARIS_RECOMPUTE': f'{C.PY} -m science.anysite.precompute',
            'POLARIS_PIXEL_INDEX': 'pixel centre = grid point (lat, lon); json_path sites[i] per pixel in POLARIS_SITE_INDEX',
            'POLARIS_SITE_INDEX': {f'{la},{lo}': i for (la, lo), (i, _) in idx.items()},
            'POLARIS_NOTE': 'one point per pixel; the value is the point solve, not a cell average', 'POLARIS_EXPORT': C.EXPORT_VERSION}
    btags = [{'unit': u, 'label': C.LABEL, 'json_path': f'sites[i].{f}'} for f, u in GRID_FIELDS]
    out = _write(Path(out_dir) / 'moon_global_10deg_precompute.tif', bands, [f for f, _ in GRID_FIELDS], tr, LONLAT, tags, btags)
    return {'path': out, 'source': Path(summary_path), 'sha256': sha, 'lats': lats, 'lons': lons, 'index': idx}


def polar_points(out_dir, summary_path=PRECOMPUTE):
    d = C.read_json(summary_path); sha = C.sha256_file(summary_path)
    out = Path(out_dir) / 'moon_polar_1deg_precompute.csv'; out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['json_index', 'id', 'group', 'lat_deg', 'lon_deg_east', 'site_hash'] + [k for k, _ in GRID_FIELDS])
        for i, s in enumerate(d['sites']):
            if s['group'] in ('south_grid_1deg', 'north_grid_1deg') and s['status'] == 'done':
                w.writerow([i, s['id'], s['group'], repr(float(s['lat'])), repr(float(s['lon'])), s.get('site_hash')]
                           + ['' if s.get(k) is None else repr(float(s[k])) for k, _ in GRID_FIELDS])
    return {'path': out, 'source': Path(summary_path), 'sha256': sha}
