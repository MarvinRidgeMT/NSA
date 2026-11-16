"""PDS Geosciences Node Orbital Data Explorer (ODE) REST footprint + metadata queries.

Manual: https://oderest.rsl.wustl.edu/ODE_REST_V2.1.pdf (09/08/21). Public, no account.
Query: query=product, target=moon, an IIPT set (ihid/iid/pt), a planetocentric 0-360 E bounding
box with loc=f (box intersects the product footprint), results=c for the count, then
results=mpf (metadata + PDS ids + files) paged with limit/offset, order=oba. Every product is then
filtered exactly against the site's 10 km stereographic square using ODE's
Footprint_SP_geometry (south-polar stereographic metres, the science/frames.py frame).

Run (sequential, >= 2 s between requests, raw responses cached with SHA-256):
    .venv/bin/python -m tools.imagery.ode harvest [--sites site04_roi3,...] [--products LROC_NAC,...]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import geometry as geo
from .http_cache import CACHE_ROOT, PoliteCache, canonical_url
from .sites import BOX_HALF_M, SITE_ORDER, SITES

ODE_BASE = 'https://oderest.rsl.wustl.edu/live2/'
PAGE_LIMIT = 200

# label -> (ihid, iid, pt, nominal pixel scale m/px used only when ODE has none, its source)
PRODUCTS = {
    'LROC_NAC': ('LRO', 'LROC', 'CDRNAC4', None, None),
    'LROC_WAC': ('LRO', 'LROC', 'CDRWAC4', None, None),
    'ShadowCam': ('KPLO', 'ShadowCam', 'CAL', None, None),
    'Kaguya_TC_stereo': ('SLN', 'TC', 'TCWL2B', 10.0, 'nominal TC 10 m/px at 100 km (Haruyama et al. 2008)'),
    'Kaguya_TC_mono': ('SLN', 'TC', 'TCSL2B', 10.0, 'nominal TC 10 m/px at 100 km (Haruyama et al. 2008)'),
}
# Cross-track samples, used only for the footprint_suspect strip-width test (upper values, so the test
# flags only footprints far too wide): NAC 5064 (LROC SIS); WAC 1024 (monochrome frame width; colour
# frames are 704); ShadowCam 3072 (<elements> in the M013371158SC PDS4 label); Kaguya TC 4096 (CCD
# length; the archived swath is narrower).
SWATH_SAMPLES = {'LROC_NAC': 5064, 'LROC_WAC': 1024, 'ShadowCam': 3072, 'Kaguya_TC_stereo': 4096, 'Kaguya_TC_mono': 4096}


class ODEError(RuntimeError):
    pass


def base_params(label, minlat, maxlat, west, east):
    ihid, iid, pt = PRODUCTS[label][:3]
    return {'query': 'product', 'output': 'JSON', 'target': 'moon', 'ihid': ihid, 'iid': iid, 'pt': pt,
            'minlat': f'{minlat:.6f}', 'maxlat': f'{maxlat:.6f}', 'westernlon': f'{west:.6f}',
            'easternlon': f'{east:.6f}', 'loc': 'f'}


def _results(body):
    d = json.loads(body.decode('utf-8'))
    r = d.get('ODEResults')
    if r is None:
        raise ODEError('no ODEResults in response')
    status = str(r.get('Status', 'Success'))
    if status.upper() not in ('SUCCESS', ''):
        raise ODEError(f'ODE status {status}: {r.get("Error", "")}')
    return r


def count(cache, params):
    p = dict(params, results='c')
    body, sha, path, _ = cache.get(canonical_url(ODE_BASE, p))
    r = _results(body)
    if 'Count' not in r:
        raise ODEError(f'no Count in response {path}')
    return int(r['Count']), {'url': canonical_url(ODE_BASE, p), 'sha256': sha}


def products_page(body):
    r = _results(body)
    prods = r.get('Products')
    if not isinstance(prods, dict):  # "No Products Found" string
        return []
    p = prods.get('Product', [])
    return p if isinstance(p, list) else [p]


def fetch_all(cache, params, limit=PAGE_LIMIT):
    """All products for one query: count first, then pages until the count is reached."""
    n, cmeta = count(cache, params)
    out, sources = [], [cmeta]
    offset = 0
    while n > 0:  # page until a short page; ODE's paged list can differ from its count by a repeat
        # m = metadata, p = PDS identifiers (pdsid, ihid, iid, pt: absent without 'p'), f = files
        p = dict(params, results='mpf', limit=str(limit), offset=str(offset), order='oba')
        url = canonical_url(ODE_BASE, p)
        body, sha, _, _ = cache.get(url)
        page = products_page(body)
        sources.append({'url': url, 'sha256': sha})
        out.extend(page)
        if len(page) < limit:
            break
        offset += limit
        if offset > n + 10 * limit:
            raise ODEError(f'paging ran past count {n}: {url}')
    # ODE pages can repeat a product across a page boundary (ties in the ordering); the run is
    # accepted only if the UNIQUE products equal ODE's count, so nothing can be silently skipped.
    uniq, seen = [], set()
    if any(not p.get('pdsid') for p in out):
        raise ODEError('product without pdsid (results must include p)')
    for p in out:
        if p.get('pdsid') not in seen:
            seen.add(p.get('pdsid'))
            uniq.append(p)
    if len(uniq) != n:
        raise ODEError(f'fetched {len(uniq)} unique products ({len(out)} rows), ODE count {n}')
    sources[0]['page_rows'], sources[0]['duplicates_dropped'] = len(out), len(out) - len(uniq)
    return uniq, sources


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def canonical_product_id(pdsid):
    s = str(pdsid)
    for pre in ('nac.', 'wac.'):
        if s.lower().startswith(pre):
            s = s[len(pre):]
    return s.upper()


def parse_product(p, label):
    """ODE product dict -> flat metadata row (no site-dependent fields)."""
    nominal, nominal_src = PRODUCTS[label][3], PRODUCTS[label][4]
    files = (p.get('Product_files') or {}).get('Product_file', [])
    files = files if isinstance(files, list) else [files]
    data = next((f for f in files if str(f.get('Type', '')).lower() == 'product'), files[0] if files else {})
    scale = _f(p.get('Map_resolution'))
    scale_src = 'ODE Map_resolution'
    if scale is not None and scale <= 0:  # ODE reports 0.0 for some WAC products: missing, not zero
        scale = None
    if scale is None:
        scale, scale_src = _f(p.get('Map_scale')), 'ODE Map_scale'
        if scale is not None and scale <= 0:
            scale = None
    if scale is None and nominal is not None:
        scale, scale_src = nominal, nominal_src
    if scale is None:
        scale_src = None
    return {
        'product_id': canonical_product_id(p.get('pdsid')),
        'ode_pdsid': p.get('pdsid'),
        'instrument': label,
        'ode_ihid': p.get('ihid'), 'ode_iid': p.get('iid'), 'ode_pt': p.get('pt'),
        'obs_utc': p.get('Observation_time'),
        'utc_start': p.get('UTC_start_time'), 'utc_stop': p.get('UTC_stop_time'),
        'emission_deg': _f(p.get('Emission_angle')),
        'incidence_deg': _f(p.get('Incidence_angle')),
        'phase_deg': _f(p.get('Phase_angle')),
        'pixel_scale_m': scale, 'pixel_scale_source': scale_src,
        'center_lat': _f(p.get('Center_latitude')), 'center_lon': _f(p.get('Center_longitude')),
        'footprint_source': p.get('Footprint_souce'),  # sic: ODE's field name
        'label_url': p.get('LabelURL'), 'product_page_url': p.get('ProductURL'),
        'external_url': p.get('External_url'),
        'data_file_url': data.get('URL'), 'data_file_kbytes': _f(data.get('KBytes')),
        'orbit': p.get('Start_orbit_number'),
        'sp_wkt': p.get('Footprint_SP_geometry'),
    }


def footprint_width_check(instrument, polys, area_m2, pixel_scale_m):
    """Strip-width test. Every catalogued instrument images a strip, so area / length ~ swath width.
    length = the footprint's bounding-box diagonal (>= true length, so the estimate errs low).
    suspect iff the estimated width > 3 x nominal swath (samples x pixel scale). Returns
    (width_km, suspect); suspect is None when the pixel scale is unknown."""
    diag = geo.bbox_diag(polys)
    width = area_m2 / diag if diag > 0 else 0.0
    if not pixel_scale_m:
        return width / 1e3, None
    swath = SWATH_SAMPLES[instrument] * pixel_scale_m
    return width / 1e3, bool(width > 3.0 * swath)


def site_filter(row, site_id, half_m=BOX_HALF_M):
    """Exact overlap of the footprint with the site square; returns site row or None."""
    s = SITES[site_id]
    rect, (cx, cy) = geo.site_square(s['lat'], s['lon'], half_m)
    polys = geo.parse_wkt_polygons(row.get('sp_wkt'))
    if not polys:
        return None
    ov = geo.overlap_area_rect(polys, *rect)
    if ov <= 0.0:
        return None
    area = sum(geo.polygon_area(pp) for pp in polys)
    width_km, suspect = footprint_width_check(row['instrument'], polys, area, row.get('pixel_scale_m'))
    out = {k: v for k, v in row.items() if k != 'sp_wkt'}
    out.update({'site': site_id, 'terrain': s['terrain'],
                'footprint_area_km2': area / 1e6,
                'footprint_width_km': width_km,
                'overlap_frac': ov / ((2 * half_m) ** 2),
                'covers_site_centre': geo.point_in_polys(cx, cy, polys),
                'footprint_suspect': suspect})
    return out


def harvest_site(cache, site_id, label, half_m=BOX_HALF_M):
    s = SITES[site_id]
    rect, _ = geo.site_square(s['lat'], s['lon'], half_m)
    minlat, maxlat, lon_ranges = geo.square_envelope(rect)
    seen, rows, sources, n_candidates = set(), [], [], 0
    for west, east in lon_ranges:
        prods, src = fetch_all(cache, base_params(label, minlat, maxlat, west, east))
        sources += src
        for p in prods:
            r = parse_product(p, label)
            if r['ode_pdsid'] in seen:
                continue
            seen.add(r['ode_pdsid'])
            n_candidates += 1
            sr = site_filter(r, site_id, half_m)
            if sr is not None:
                rows.append(sr)
    meta = {'site': site_id, 'instrument': label, 'bbox': {'minlat': minlat, 'maxlat': maxlat,
            'lon_ranges': lon_ranges}, 'ode_candidates': n_candidates, 'kept': len(rows), 'sources': sources}
    return rows, meta


def harvest(sites=None, labels=None, cache=None, out_dir=None, log=print):
    cache = cache or PoliteCache(CACHE_ROOT / 'ode', min_interval_s=2.0)
    out_dir = Path(out_dir or CACHE_ROOT / 'harvest')
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = []
    for site_id in sites or SITE_ORDER:
        for label in labels or PRODUCTS:
            rows, meta = harvest_site(cache, site_id, label)
            (out_dir / f'{site_id}__{label}.json').write_text(json.dumps({'meta': meta, 'rows': rows}, indent=0))
            summary.append({k: meta[k] for k in ('site', 'instrument', 'ode_candidates', 'kept')})
            log(f'{site_id:12s} {label:17s} ODE candidates {meta["ode_candidates"]:6d}  kept {len(rows):6d}  '
                f'(net {cache.network_calls}, cached {cache.cache_hits})')
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    h = sub.add_parser('harvest')
    h.add_argument('--sites', default=','.join(SITE_ORDER))
    h.add_argument('--products', default=','.join(PRODUCTS))
    a = ap.parse_args(argv)
    if a.cmd == 'harvest':
        s = harvest(a.sites.split(','), a.products.split(','))
        print(json.dumps(s, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
