"""Site table and DEM sources. Coordinates are the values carried in the archived
app (app/scripts/prepare_science.py SITES); their origin (Mazarico et al. 2011 site
numbering, per PGDA product 78 README) is SOURCE-BASED UNVALIDATED against an
independent site list."""
from pathlib import Path

import numpy as np

from . import dem as demmod
from . import frames

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data' / 'cache'

P78 = 'https://pgda.gsfc.nasa.gov/data/LOLA_5mpp'

SITES = {
    'site01': {'name': 'Connecting Ridge (Site01)', 'lat': -89.4632, 'lon': -137.4900,
               'p78': f'{P78}/Site01/Site01_final_adj_5mpp_surf.tif',
               'p78_err': f'{P78}/Site01/Site01_final_adj_5mpp_toterr.tif',
               'p78_clone': P78 + '/Site01/Clones/Site01_final_adj_5mpp_{:04d}_err.tif'},
    'site04': {'name': 'Shackleton Rim (Site04)', 'lat': -89.7668, 'lon': -171.8700,
               'p78': f'{P78}/Site04/Site04_final_adj_5mpp_surf.tif',
               'p78_err': f'{P78}/Site04/Site04_final_adj_5mpp_toterr.tif',
               'p78_clone': P78 + '/Site04/Clones/Site04_final_adj_5mpp_{:04d}_err.tif'},
}

# Real landing points: PGDA product 78 published ROI polygons (centroid of the polygon
# vertices; polar stereographic R=1737400, lat/lon on the sphere). The site01/site04
# entries above are the product-78 TILE CENTRES (Site04's centre is on a ~31.6 deg slope
# inside Shackleton) and are kept only so the earlier bundles stay reproducible.
ROI_SOURCE = ('PGDA product 78 ROI shapefile (Barker et al. 2021), polygon-vertex centroid, '
              'fetched 2026-11-14 (fetch_extra_nasa_data.sh, SHA-256 pinned)')
_ROIS = {
    'site01_roi6': ('site01', 6, -89.47409, -137.38130),
    'site04_roi3': ('site04', 3, -89.78012, -156.32023),
    'site04_roi4': ('site04', 4, -89.78480, -155.94606),
}
for _sid, (_tile, _n, _lat, _lon) in _ROIS.items():
    _base = SITES[_tile]
    SITES[_sid] = {**{k: v for k, v in _base.items() if k.startswith('p78')},
                   'name': f'{_base["name"].split(" (")[0]} ({_tile.capitalize()} ROI{_n})',
                   'lat': _lat, 'lon': _lon, 'tile': _tile, 'roi': _n,
                   'coordinates_source': ROI_SOURCE}

FAR_HALF_M = 290_000.0
# Near-field ray step for ROI bundles. The default (= DEM pixel, 5 m) is NOT converged for
# low masts: at Site04 ROI3, 1 m mast, Sun-centre visibility is 98.5 % at 5 m, 95.6 % at
# 2.5 m, 94.7 % at 1.25 m and 94.4 % at both 1.0 m and 0.5 m (14-28 Nov 2026, 1 h).
# 1 m is the converged value used for ROI bundles (~1.5x skyline cost).
NEAR_RAY_STEP_M = 1.0
MAX_RANGE_M = 280_000.0
LDEM_LOCAL = CACHE / 'ldem' / 'LDEM_80S_80MPP_ADJ.TIF'
LDEM_SHA256 = '82030dcbdd7c4bb0c7d858e9b4b293b9f2cda5a543ba31ec0f42784bd6beee5a'  # whole file, 2026-11-14
FAR_NAME = 'LOLA LDEM_80S_80MPP_ADJ (PGDA product 90), 80 m'


def _cached(key, loader):
    CACHE.mkdir(parents=True, exist_ok=True)
    npy, js = CACHE / f'{key}.npy', CACHE / f'{key}.json'
    import json
    if npy.exists() and js.exists():
        m = json.loads(js.read_text())
        d = demmod.ArrayDEM(np.load(npy), m['x_left'], m['y_top'], m['step'], m['name'], m['meta'])
        return d
    d = loader()
    np.save(npy, d.Z.astype('float32'))
    js.write_text(json.dumps({'x_left': d.x_left, 'y_top': d.y_top, 'step': d.step, 'name': d.name,
                              'meta': {k: v for k, v in d.meta.items() if k != 'crs_wkt'}}))
    d.Z = d.Z.astype('float32').astype('float64')  # identical to cached path
    return d


def far_dem(site_id, prefer_local=True):
    """Far field from the LDEM COG. Default transport is /vsicurl range reads; if the
    whole file has been downloaded to data/cache/ldem/ and its SHA-256 matches
    LDEM_SHA256 it is read locally instead (identical bytes; a 4125x4125 /vsicurl window
    was verified bit-identical to this file, max |diff| = 0.0 m)."""
    s = SITES[site_id]
    x, y = frames.stereo_forward(s['lat'], s['lon'])
    src, transport = frames.LDEM_VSI, 'vsicurl'
    if prefer_local and LDEM_LOCAL.exists():
        import hashlib
        if hashlib.sha256(LDEM_LOCAL.read_bytes()).hexdigest() == LDEM_SHA256:
            src, transport = str(LDEM_LOCAL), 'local-copy-sha256-verified'

    def load():
        d = demmod.read_window(src, x, y, FAR_HALF_M, name=FAR_NAME)
        d.meta.update({'source_url': frames.LDEM_URL, 'transport': transport, 'file_sha256': LDEM_SHA256})
        return d
    return _cached(f'{site_id}_ldem80_{int(FAR_HALF_M/1000)}km', load)


def download(url, dest):
    """Whole-file download with Content-Length check and SHA-256. Product-78 tiles are
    uncompressed strip TIFFs; proxied /vsicurl strip reads were observed to return
    corrupted rows (|z| ~ 1e34) in this environment, so near-field tiles are fetched whole."""
    import hashlib, requests
    dest = Path(dest); dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        r = requests.get(url, timeout=600); r.raise_for_status()
        n = int(r.headers.get('Content-Length', len(r.content)))
        if n != len(r.content):
            raise IOError(f'short read {len(r.content)} != {n} for {url}')
        dest.write_bytes(r.content)
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    return dest, sha


def near_dem(site_id, url_key='p78', clone=None):
    s = SITES[site_id]
    url = s['p78_clone'].format(clone) if clone is not None else s[url_key]
    x, y = frames.stereo_forward(s['lat'], s['lon'])
    tag = f'clone{clone:04d}' if clone is not None else url_key
    name = f'LOLA {site_id} 5 m (PGDA product 78) {tag}'

    def load():
        path, sha = download(url, CACHE / 'p78' / url.rsplit('/', 1)[-1])
        d = demmod.read_window(str(path), x, y, 9000.0, name=name)
        d.meta.update({'source_url': url, 'file_sha256': sha})
        return d
    return _cached(f'{site_id}_p78_{tag}', load)
