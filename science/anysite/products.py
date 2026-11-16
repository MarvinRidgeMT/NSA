"""Terrain products the any-site solver can use tonight (adapter side of TERRAIN_STACK_CONTRACT.md §5).

Each product: id, zone ('sp' south-polar stereographic, 'np' north-polar stereographic, 'eq' equirectangular), native
resolution, merge priority (contract §6, lower = preferred), files on disk, published source URL, and the error model the
uncertainty axis uses where no PGDA clones exist. Error-model numbers are labelled "assumed error model" in every output.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / 'data' / 'cache'
EXTERNAL = ROOT / 'data' / 'external'
POLARIS_DATA = Path(os.environ.get('POLARIS_DATA', str(CACHE)))
P78_URL = 'https://pgda.gsfc.nasa.gov/data/LOLA_5mpp'

# Contract §6 merge priority (index = rank).
PRIORITY = ['nac_dtm', 'sfs', 'pgda78', 'kaguya_tc', 'pgda90', 'sldem2015', 'lola_polar_ldem', 'lola_global_ldem']

# Assumed error models (σ = 1-sigma vertical error, corr_m = correlation length of the error field). These are NOT product
# statements unless 'basis' says so; every member built from them is labelled 'assumed error model'.
ERROR_MODELS = {
    'pgda78': {'sigma_m': 0.40, 'corr_m': 50.0,
               'basis': 'PGDA product 78 page: median RMS Z error ~0.30-0.50 m within the RoIs (midpoint used); '
                        'correlation length 50 m assumed (10 px). Used only where the tile has no clones cached.'},
    'pgda90': {'sigma_m': 1.0, 'corr_m': 400.0,
               'basis': 'PGDA product 90 page states no accuracy number; it distributes LDEM_80S_80MPP_ADJ_ERR.TIF, not '
                        'cached tonight. sigma 1 m (LOLA radial orbit-accuracy class) and 400 m (5 px) correlation are '
                        'assumptions to be replaced by the ERR layer.'},
    'sldem2015': {'sigma_m': 3.5, 'corr_m': 1000.0,
                  'basis': 'SLDEM2015 vertical accuracy ~3-4 m (Barker et al. 2016, Icarus 273, 346); correlation length '
                           '~1 km assumed from LOLA cross-track spacing at low latitude.'},
    'lola_global_ldem': {'sigma_m': 5.0, 'corr_m': 2000.0,
                         'basis': 'assumed: gridded LOLA between tracks at low latitude (no product statement used).'},
}

PGDA78_SITES = ('Site01', 'Site04', 'Site07', 'Site11')


def _first(paths):
    for p in paths:
        if p and Path(p).exists():
            return Path(p)
    return None


def pgda78_tile(site, clone=None):
    if clone is None:
        name = f'{site}_final_adj_5mpp_surf.tif'
        return _first([EXTERNAL / 'pgda78' / site / name, CACHE / 'p78' / name])
    name = f'{site}_final_adj_5mpp_{clone:04d}_err.tif'
    return _first([CACHE / 'p78' / name, EXTERNAL / 'pgda78' / site / 'Clones' / name])


def pgda90_file():
    return _first([CACHE / 'ldem' / 'LDEM_80S_80MPP_ADJ.TIF', EXTERNAL / 'pgda90' / 'LDEM_80S_80MPP_ADJ.TIF'])


def file_sha256(path):
    """SHA-256 of a whole file, memoised on (path, size, mtime) in data/cache/anysite/sha_cache.json."""
    path = Path(path); st = path.stat()
    memo_p = CACHE / 'anysite' / 'sha_cache.json'
    key = f'{path.resolve()}|{st.st_size}|{int(st.st_mtime)}'
    try:
        memo = json.loads(memo_p.read_text())
    except Exception:
        memo = {}
    if key in memo:
        return memo[key]
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(1 << 22):
            h.update(chunk)
    memo[key] = h.hexdigest()
    try:
        memo_p.parent.mkdir(parents=True, exist_ok=True)
        tmp = memo_p.with_suffix(f'.{os.getpid()}.tmp'); tmp.write_text(json.dumps(memo)); tmp.replace(memo_p)
    except Exception:
        pass
    return memo[key]


def _tif_info(path):
    import rasterio
    with rasterio.open(path) as ds:
        b = ds.bounds
        return {'bounds': (b.left, b.bottom, b.right, b.top), 'res_m': abs(ds.transform.a), 'crs_wkt': ds.crs.to_wkt(),
                'proj4': ds.crs.to_proj4()}


def _zone_of(proj4):
    p = proj4.replace(' ', '')
    if '+proj=stere' in p and '+lat_0=-90' in p:
        return 'sp'
    if '+proj=stere' in p and '+lat_0=90' in p:
        return 'np'
    if '+proj=eqc' in p or '+proj=longlat' in p:
        return 'eq'
    return None


def registry():
    """All products found on disk. Each entry: dict(id, product, zone, res_m, priority, path, bounds, url, members)."""
    out = []
    for site in PGDA78_SITES:
        p = pgda78_tile(site)
        if p is None:
            continue
        info = _tif_info(p)
        clones = {c: pgda78_tile(site, c) for c in range(1, 101)}
        clones = {c: q for c, q in clones.items() if q is not None}
        out.append({'id': f'pgda78_{site}', 'product': 'pgda78', 'zone': 'sp', 'res_m': info['res_m'],
                    'priority': PRIORITY.index('pgda78'), 'path': str(p), 'bounds': info['bounds'],
                    'name': f'LOLA {site} 5 m (PGDA product 78) nominal',
                    'url': f'{P78_URL}/{site}/{p.name}', 'clones': {c: str(q) for c, q in clones.items()},
                    'clone_url': P78_URL + f'/{site}/Clones/{site}_final_adj_5mpp_{{:04d}}_err.tif',
                    'citation': 'Barker et al. 2021, PSS 203, 105119; PGDA product 78'})
    p = pgda90_file()
    if p is not None:
        info = _tif_info(p)
        out.append({'id': 'pgda90_80m', 'product': 'pgda90', 'zone': 'sp', 'res_m': info['res_m'],
                    'priority': PRIORITY.index('pgda90'), 'path': str(p), 'bounds': info['bounds'],
                    'name': 'LOLA LDEM_80S_80MPP_ADJ (PGDA product 90), 80 m',
                    'url': 'https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF', 'clones': {},
                    'citation': 'Barker et al. 2023, PSJ 4, 183 (doi:10.3847/PSJ/acf3e1); PGDA product 90'})
    # Any further product S2 has downloaded under $POLARIS_DATA/v2/products/<product_id>/ (GeoTIFF only; zone from CRS).
    for f in sorted(glob.glob(str(POLARIS_DATA / 'v2' / 'products' / '*' / '**' / '*.[tT][iI][fF]'), recursive=True)):
        pid = Path(f).relative_to(POLARIS_DATA / 'v2' / 'products').parts[0]
        prod = next((k for k in PRIORITY if k in pid.lower().replace('-', '_')), None)
        if prod is None or prod in ('pgda78', 'pgda90') or any(w in Path(f).name.lower() for w in ('err', 'slope', 'hurst')):
            continue
        try:
            info = _tif_info(f)
        except Exception:
            continue
        zone = _zone_of(info['proj4'])
        if zone is None:
            continue
        out.append({'id': f'{pid}:{Path(f).stem}', 'product': prod, 'zone': zone, 'res_m': info['res_m'],
                    'priority': PRIORITY.index(prod), 'path': f, 'bounds': info['bounds'], 'name': f'{pid} {Path(f).name}',
                    'url': None, 'clones': {}, 'crs_wkt': info['crs_wkt'], 'citation': f'see docs/v2/DATA_MANIFEST.json ({pid})'})
    out.sort(key=lambda e: (e['priority'], e['res_m']))
    return out
