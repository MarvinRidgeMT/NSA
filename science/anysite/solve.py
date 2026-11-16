"""Any-site solver: lat/lon (+ mast, window) -> polaris-science-results-v1 bundle with provenance and uncertainty members.

  python -m science.anysite.solve --lat -89.78012 --lon -156.32023 --mast 1 [--members clones,assumed,products]

Pipeline (docs/v2/PHASE_1_ANYSITE_PLAN.md): terrain stack -> near field (±25 km, native resolution, ray step native/5)
-> far field to the curvature limit -> 720-bin skyline (science.skyline.compute_skyline, unchanged) -> JPL Horizons
(identical query to science.horizons, raw responses cached by SHA-256) -> hourly-sample metrics -> bundle.
Labels: geometry SOURCE-BASED UNVALIDATED; error-model members 'assumed error model'.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

from .. import bundle as B
from .. import crossings as X
from .. import frames
from .. import horizons as H
from ..cube.compute import visible_flags
from ..skyline import _near_extent, compute_skyline
from . import curvature, ephem, members as MB
from . import products as P
from .stack import get_stack

ROOT = P.ROOT
OUT_DIR = ROOT / 'data' / 'cache' / 'anysite' / 'bundles'
SOLVER_VERSION = 'anysite-2'   # 2: far composite step = PGDA 90 step; far layers >= 75 m
LABEL = B.LABEL
NEAR_HALF_M = 25_000.0
BASE_RANGE_M = 280_000.0         # range of every existing bundle
MAX_EXTENDED_RANGE_M = 600_000.0
FAR_MARGIN_M = 10_000.0           # far window half = range + margin (290 km for the existing bundles)
STEP_DIVISOR = 5.0               # ray step = native / 5 (1 m on 5 m PGDA 78: the converged ROI-bundle step)
FINE_STEP_MAX_M = 12_500.0       # fine ray step at most this far (RoI bundles: 6.3 km); memory bound for 5 m products
NEAR_MAX_PX = 6000               # near window <= 6000 px per side (±15 km at 5 m)
FAR_MIN_RES_M = 75.0             # far-field layers: PGDA 90 80 m class and coarser (LOLA global); finer ones are near-only
                                 # (a ±290 km window of the 60 m LOLA polar product would be ~750 MB per worker)


def site_hash(lat, lon, mast_m, start, days, step_h, product_ids, member_kinds=(), n_members=20):
    """Cache key. Includes the member set: a bundle cached without clones must not answer a request with clones."""
    key = {'lat': round(float(lat), 7), 'lon': round(((float(lon) + 180) % 360) - 180, 7), 'mast_m': float(mast_m),
           'start': start, 'days': days, 'step_h': step_h, 'products': sorted(product_ids), 'solver': SOLVER_VERSION,
           'members': sorted(member_kinds), 'n_members': int(n_members) if member_kinds else 0}
    return hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:16]


def _stop(start, days):
    return (dt.datetime.fromisoformat(start) + dt.timedelta(days=days)).strftime('%Y-%m-%d %H:%M')


def hourly_metrics(rs, re_, step_h):
    """Metrics on the hourly Horizons samples (both endpoints included). A sample whose skyline bins have no data
    (m is None) counts as not visible and is counted in n_unknown."""
    def vis(rows):
        return np.array([r['m'] is not None and r['m']['margin_perp_deg'] > 0 for r in rows])

    def unknown(rows):
        return int(sum(r['m'] is None for r in rows))

    def longest_hidden(v):
        best = cur = 0
        for f in v:
            cur = 0 if f else cur + 1; best = max(best, cur)
        return best * step_h
    sv, ev = vis(rs), vis(re_)
    t = np.array([r['t'] for r in rs]); span = t[-1] - t[0]
    trap = lambda rows: float(np.trapezoid([0.0 if r['m'] is None else r['m']['disk_fraction'] for r in rows], t) / span)
    mm = lambda rows, f: round(f(r['m']['margin_deg'] for r in rows if r['m'] is not None), 5) \
        if any(r['m'] is not None for r in rows) else None
    sun = round(100 * sv.mean(), 3); earth = round(100 * ev.mean(), 3); both = round(100 * (sv & ev).mean(), 3)
    return {
        'label': LABEL, 'window_utc': [H.unix_to_iso(t[0]), H.unix_to_iso(t[-1])],
        'sun_center_visible_pct': sun, 'earth_center_visible_pct': earth, 'sun_and_earth_center_visible_pct': both,
        'longest_sun_center_hidden_h': float(longest_hidden(sv)), 'longest_earth_center_hidden_h': float(longest_hidden(ev)),
        'sun_disk_mean_visible_fraction': round(trap(rs), 5), 'earth_disk_mean_visible_fraction': round(trap(re_), 5),
        'min_sun_margin_deg': mm(rs, min), 'min_earth_margin_deg': mm(re_, min), 'max_earth_margin_deg': mm(re_, max),
        'sun_center_visible_pct_hourly_samples': sun, 'earth_center_visible_pct_hourly_samples': earth,
        'sun_and_earth_center_visible_pct_hourly_samples': both,
        'n_samples': int(sv.size), 'n_unknown_sun': unknown(rs), 'n_unknown_earth': unknown(re_),
        'method': {'visible_pct': 'share of hourly Horizons samples (both endpoints included) with the body centre above the '
                                  'skyline (perpendicular margin > 0); NO bisection refinement (any-site default)',
                   'longest_hidden_h': 'longest run of consecutive hidden hourly samples x step_h',
                   'disk_mean': 'trapezoid over hourly samples of the visible-disk fraction',
                   'margins': 'el - skyline(az) at hourly samples', 'unknown': 'samples over no-data skyline bins count as hidden'},
        'disclaimer': 'Local geometric visibility only: not certified illumination, power, or DSN link availability.',
    }


def _pct_from_flags(fl, step_h):
    s, e = fl['sun'], fl['earth']

    def longest(v):
        best = cur = 0
        for f in v:
            cur = 0 if f else cur + 1; best = max(best, cur)
        return best * step_h
    return {'sun_center_visible_pct_hourly_samples': round(100 * s.mean(), 3),
            'earth_center_visible_pct_hourly_samples': round(100 * e.mean(), 3),
            'sun_and_earth_center_visible_pct_hourly_samples': round(100 * (s & e).mean(), 3),
            'longest_sun_center_hidden_h': float(longest(s)), 'longest_earth_center_hidden_h': float(longest(e)),
            'n_unknown_sun': int(fl['sun_missing'].sum()), 'n_unknown_earth': int(fl['earth_missing'].sum())}


def _range_summary(vals):
    v = [x for x in vals if x is not None]
    return None if not v else {'min': min(v), 'max': max(v), 'median': float(np.median(v)), 'n': len(v)}


def _near_cut(near, lat, lon):
    if hasattr(near, 'ppd'):                      # EqDEM: window built as ±half around the site
        return NEAR_HALF_M
    inner = getattr(near, 'inner', None)
    if inner is None:
        return _near_extent(near, lat, lon)
    # non-south-polar product: inscribed radius in its own grid (scale ~1 near the site)
    from .stack import _to_zone
    x0, y0 = _to_zone(lat, lon, near.entry)
    l, b, r, t = inner.bounds
    return max(0.0, min(float(x0) - l, r - float(x0), float(y0) - b, t - float(y0)) - inner.step)


def solve(lat, lon, mast_m=1.0, start='2026-11-14 00:00', days=14, step_h=1, member_kinds=('clones', 'assumed', 'products'),
          n_members=20, stack=None, use_cache=True, name=None, site_id=None, allow_network=True, out_dir=OUT_DIR,
          command=None):
    t_start = time.time(); timing = {}
    lat = float(lat); lon = ((float(lon) + 180.0) % 360.0) - 180.0
    if not (-90.0 <= lat <= 90.0) or not math.isfinite(lon):
        raise ValueError(f'latitude must be within [-90, 90] deg (got {lat})')
    stack = stack or get_stack()
    cov = _coverage(stack, lat, lon)
    if not cov['products']:
        raise LookupError(f'no cached terrain product covers ({lat:.5f}, {lon:.5f})')
    pids = [p['id'] for p in cov['products']]
    shash = site_hash(lat, lon, mast_m, start, days, step_h, pids, member_kinds, n_members)
    out_p = Path(out_dir) / f'{shash}.json'
    if use_cache and out_p.exists():
        b = json.loads(out_p.read_text()); b['anysite']['cache_hit'] = True
        return b
    entries = {e['id']: e for e in getattr(stack, 'entries', [])}
    if not entries:   # pyramid (S3): one merged surface; near at the site's native resolution, far at >= 80 m
        near_e = {'id': f'pyramid:{cov["source_id"]}', 'res_m': float(cov['native_res_m']), 'clones': {},
                  'product': 'pyramid'}
        far_e = {'id': 'pyramid:far', 'res_m': max(80.0, float(cov['native_res_m'])), 'clones': {}, 'product': 'pyramid'}
        if far_e['res_m'] == near_e['res_m']:
            far_e = near_e
        entries = {}
    else:
        near_e = entries[cov['source_id']]
    far_es = _far_entries(near_e, [entries[p] for p in pids if p in entries]) if entries else [far_e]
    far_e = far_es[0]
    x0, y0 = frames.stereo_forward(lat, lon)

    t = time.time()
    near_half = _near_half(near_e)
    near = _window(stack, lat, lon, near_half, near_e)
    h = float(near.sample(x0, y0))
    if not math.isfinite(h):
        raise LookupError(f'no height at the site ({lat}, {lon}) in {near_e["id"]}')
    h_eye = h + mast_m
    max_range = max(BASE_RANGE_M, float(curvature.limit_m(h_eye, 0.0)))
    far = _far_window(stack, lat, lon, max_range + FAR_MARGIN_M, far_es)
    timing['terrain_read_s'] = round(time.time() - t, 2)

    same = near_e['id'] == far_e['id']
    step_near = near_e['res_m'] / STEP_DIVISOR
    near_cut = NEAR_HALF_M if same else min(_near_cut(near, lat, lon), FINE_STEP_MAX_M)

    t = time.time()
    sky = compute_skyline(lat, lon, h, mast_m, near=near, far=far, bins=720, max_range_m=max_range, step_m=step_near,
                          near_range_m=near_cut, far_step_m=far.step)
    curv = curvature.record(h_eye, max_range, sky['elevation_deg'], float(np.nanmax(far.Z)))
    L_req = curv['required_range_world_m']
    reach = max(_footprint_reach(e, lat, lon) for e in far_es)
    extended = False
    if math.isfinite(L_req) and L_req > max_range and reach > max_range + FAR_MARGIN_M:
        max_range = min(L_req, MAX_EXTENDED_RANGE_M, reach - FAR_MARGIN_M)
        far = _far_window(stack, lat, lon, max_range + FAR_MARGIN_M, far_es)
        sky = compute_skyline(lat, lon, h, mast_m, near=near, far=far, bins=720, max_range_m=max_range, step_m=step_near,
                              near_range_m=near_cut, far_step_m=far.step)
        curv = curvature.record(h_eye, max_range, sky['elevation_deg'], float(np.nanmax(far.Z)))
        extended = True
    curv['extended'] = extended
    curv['footprint_reach_m'] = round(reach, 1) if math.isfinite(reach) else 'global'
    timing['skyline_s'] = round(time.time() - t, 2)

    t = time.time()
    stop = _stop(start, days)
    rs, src_s = ephem.hourly('sun', lat, lon, h, start, stop, step_h, allow_network)
    re_, src_e = ephem.hourly('earth', lat, lon, h, start, stop, step_h, allow_network)
    for rows in (rs, re_):
        for r in rows:
            r['radius_deg'], r['radius_source'] = B._radius_deg(r)
            r['m'] = X.margins(r, sky)
    timing['horizons_s'] = round(time.time() - t, 2)
    met = hourly_metrics(rs, re_, step_h)

    t = time.time()
    eph = {'sun_az': np.array([r['az_deg'] for r in rs]), 'sun_el': np.array([r['el_deg'] for r in rs]),
           'earth_az': np.array([r['az_deg'] for r in re_]), 'earth_el': np.array([r['el_deg'] for r in re_])}
    unc = run_members(lat, lon, mast_m, stack, near_e, far_e, near, far, near_cut, step_near, max_range, eph, step_h,
                      member_kinds, n_members, shash, pids, entries)
    timing['members_s'] = round(time.time() - t, 2)
    timing['total_s'] = round(time.time() - t_start, 2)

    b = assemble(lat, lon, mast_m, h, x0, y0, near, far, sky, rs, re_, met, [src_s, src_e], start, days, step_h, shash,
                 cov, near_e, far_e, near_cut, step_near, curv, unc, timing, name, site_id, command)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    tmp = out_p.with_suffix(f'.{os.getpid()}.tmp'); tmp.write_text(json.dumps(b, indent=1)); tmp.replace(out_p)
    b['anysite']['cache_hit'] = False
    return b


def _coverage(stack, lat, lon):
    """Contract coverage() plus a 'products' list (the legacy adapter provides it; the pyramid gives one merged source)."""
    import numpy as _np

    def _scalar(v):                                     # S3's coverage is vectorised: 0-d/1-element arrays -> Python
        if isinstance(v, _np.ndarray):
            v = v.reshape(-1)[0] if v.size == 1 else v.tolist()
        return v.item() if isinstance(v, _np.generic) else v
    cov = {k: _scalar(v) for k, v in dict(stack.coverage(lat, lon)).items()}
    if 'products' not in cov:
        ok = cov.get('source_id') is not None and cov.get('native_res_m') and cov.get('quality', 0) > 0
        cov['products'] = [{'id': f'pyramid:{cov["source_id"]}', 'res_m': cov['native_res_m']}] if ok else []
    return cov


def _window(stack, lat, lon, half_m, e):
    """Legacy adapter: product-specific window. Pyramid: contract window(lat, lon, half_m, res_m); a non-south-polar
    ArrayDEM is wrapped (SPView) using the CRS it carries in meta['crs_wkt']."""
    if getattr(stack, 'entries', None):
        return stack.window(lat, lon, half_m, e['res_m'], product=e['id'])
    d = stack.window(lat, lon, half_m, e['res_m'])
    zone = d.meta.get('zone') or ('sp' if lat < -54 else 'np' if lat > 54 else 'eq')
    d.meta.setdefault('product_id', e['id']); d.meta.setdefault('zone', zone)
    if zone != 'sp' and not hasattr(d, 'inner'):
        from .stack import SPView
        return SPView(d, {'zone': zone, 'crs_wkt': d.meta['crs_wkt']})
    return d


def _near_half(e):
    """Near window half-width: 25 km, capped at NEAR_MAX_PX/2 pixels of the product (a 5 m product gets ±15 km; beyond it
    the next product supplies samples at its own native resolution)."""
    return min(NEAR_HALF_M, NEAR_MAX_PX / 2 * e['res_m'])


def _far_entries(near_e, covering):
    """Far-field layers in contract priority: products of >= FAR_MIN_RES_M (one per product family, finest), e.g.
    PGDA 90 80 m first and LOLA global as the fill where PGDA 90 ends. Falls back to the near product."""
    out, fams = [], set()
    for e in covering:                                  # covering is in priority order, finest first per family
        if e['res_m'] >= FAR_MIN_RES_M and e['product'] not in fams:
            out.append(e); fams.add(e['product'])
    return out or [near_e]


def _far_window(stack, lat, lon, half_m, far_es):
    layers = [_window(stack, lat, lon, half_m, e) for e in far_es]
    if len(layers) == 1:
        return layers[0]
    from .stack import CompositeDEM
    return CompositeDEM(layers, name=' > '.join(l.name for l in layers))


def _footprint_reach(e, lat, lon):
    """Inscribed distance from the site to the product footprint edge (grid metres; sp zone; eq global = inf)."""
    if e.get('zone') == 'eq' and e.get('width') and e.get('ppd') and abs(e['width'] / e['ppd'] - 360.0) < 1e-6:
        return float('inf')
    if not e.get('bounds') or e.get('zone', 'sp') != 'sp':
        return 0.0
    x, y = frames.stereo_forward(lat, lon); l, b, r, t = e['bounds']
    return max(0.0, min(x - l, r - x, y - b, t - y))


def run_members(lat, lon, mast_m, stack, near_e, far_e, near, far, near_cut, step_near, max_range, eph, step_h,
                kinds, n, shash, pids, entries):
    out = {'label_note': '"k of N maps is not a probability": member ranges are spreads over alternatives, not '
                         'calibrated probabilities.', 'members': [], 'summary': {}}
    same = near_e['id'] == far_e['id']
    jobs = []   # (member_id, kind, near_dem, label)
    clones = sorted(near_e.get('clones', {}))[:n]
    if 'clones' in kinds and clones:
        for c in clones:
            jobs.append((f'clone{c:02d}', 'pgda78-clone', ('clone', c), 'PGDA 78 clone (published realization)'))
    elif 'assumed' in kinds:
        model = P.ERROR_MODELS.get(near_e.get('product'))
        if model:
            seed = int(shash, 16) % (2 ** 31)
            for k in range(1, n + 1):
                jobs.append((f'assumed{k:02d}', 'assumed-error-model', ('assumed', k, seed, model), MB.LABEL_ASSUMED))
        else:
            out['summary']['assumed'] = {'status': 'not-run', 'reason': f'no error model for product {near_e.get("product")}'}
    if 'clones' in kinds and not clones:
        out['summary']['clones'] = {'status': 'not-run', 'reason': f'no PGDA 78 clones cached for {near_e["id"]}'}

    # T members, batched in chunks (shared ray geometry; bit-identical to compute_skyline, see test)
    chunk = 5
    for i in range(0, len(jobs), chunk):
        part = jobs[i:i + chunk]; dems = {}
        for mid, kind, spec, lab in part:
            if spec[0] == 'clone':
                dems[mid] = stack.window(lat, lon, _near_half(near_e), near_e['res_m'], product=near_e['id'],
                                         member=f'clone{spec[1]:04d}')
            else:
                dems[mid] = MB.assumed_member(near, near_e.get('product'), spec[1], spec[2], spec[3])
        res = MB.batched_skyline(lat, lon, dems, far, mast_m, step_near, near_cut, far.step, max_range)
        for mid, kind, spec, lab in part:
            sky = res[mid]
            m = _pct_from_flags(visible_flags(eph, sky), step_h)
            rec = {'id': mid, 'kind': kind, 'label': lab, 'ground_m': round(sky['ground_m'], 3),
                   'n_truncated': sky['n_truncated'], 'metrics': m,
                   'dem': dems[mid].name, 'source_url': dems[mid].meta.get('source_url'),
                   'file_sha256': dems[mid].meta.get('file_sha256')}
            if spec[0] == 'assumed':
                rec['error_model'] = {**spec[3], 'product': near_e.get('product'), 'seed': [spec[2], spec[1]],
                                      'applied_to': f'near field only (±{NEAR_HALF_M / 1000:g} km)'}
            out['members'].append(rec)
        del dems
    for kind in ('pgda78-clone', 'assumed-error-model'):
        ms = [m for m in out['members'] if m['kind'] == kind]
        if ms:
            out['summary'][kind] = {k: _range_summary([m['metrics'][k] for m in ms]) for k in (
                'sun_center_visible_pct_hourly_samples', 'sun_and_earth_center_visible_pct_hourly_samples',
                'earth_center_visible_pct_hourly_samples', 'longest_sun_center_hidden_h')}
            out['summary'][kind]['label'] = 'assumed error model' if kind == 'assumed-error-model' else 'PGDA 78 clones'

    # M: product disagreement
    if 'products' in kinds:
        others, fams = [], {near_e.get('product')}
        for p in pids:                                   # one member per other product family (its finest resolution)
            if p in entries and entries[p]['product'] not in fams:
                others.append(p); fams.add(entries[p]['product'])
        if not others:
            out['summary']['products'] = {'status': 'not-run', 'reason': 'only one terrain product covers this site in the '
                                                                        'cache (M needs >= 2)'}
        for pid in others:
            e = entries[pid]
            nd = stack.window(lat, lon, _near_half(e), e['res_m'], product=pid)
            cut = NEAR_HALF_M if e['res_m'] >= FAR_MIN_RES_M else min(_near_cut(nd, lat, lon), FINE_STEP_MAX_M)
            x0, y0 = frames.stereo_forward(lat, lon)
            g = float(nd.sample(x0, y0))
            if not math.isfinite(g):
                continue
            res = MB.batched_skyline(lat, lon, {pid: nd}, far, mast_m, e['res_m'] / STEP_DIVISOR, cut, far.step, max_range)
            sky = res[pid]
            out['members'].append({'id': f'product:{pid}', 'kind': 'product', 'label': 'product disagreement (M)',
                                   'ground_m': round(g, 3), 'n_truncated': sky['n_truncated'],
                                   'step_near_m': sky['step_near_m'], 'near_cut_m': sky['near_cut_m'],
                                   'metrics': _pct_from_flags(visible_flags(eph, sky), step_h),
                                   'dem': nd.name, 'file_sha256': nd.meta.get('file_sha256')})
        if others:
            out['summary']['products'] = {'nominal_near_product': near_e['id'], 'compared': others}
    return out


def assemble(lat, lon, mast_m, h, x0, y0, near, far, sky, rs, re_, met, srcs, start, days, step_h, shash, cov, near_e,
             far_e, near_cut, step_near, curv, unc, timing, name, site_id, command):
    sky_out = {k: sky[k] for k in ('bins', 'azimuth_deg', 'elevation_deg', 'status', 'range_limited', 'valid_reach_m',
                                   'critical', 'n_truncated', 'n_range_limited', 'max_range_m', 'near_cut_m',
                                   'step_near_m', 'step_far_m', 'n_samples_per_bin',
                                   'beyond_range_max_possible_elev_deg', 'beyond_range_reference_height_m',
                                   'flat_baseline', 'method')}
    sky_out['label'] = LABEL
    sky_out['curvature_limit'] = curv
    layers = []
    # S4's multi-product far field keeps a LIST of DEMs in .layers; S3's ZoneDEM uses .layers for a DICT of per-pixel
    # bands (source_id, native_res_m, quality, filled), so only a list/tuple means sub-DEMs.
    _fl = getattr(far, 'layers', None)
    far_layers = list(_fl) if isinstance(_fl, (list, tuple)) else [far]
    for role, d in [('near', near)] + [('far' if i == 0 else 'far-fill', l) for i, l in enumerate(far_layers)]:
        eq = d.meta.get('zone') == 'eq' and hasattr(d, 'ppd')
        layers.append({'role': role, 'name': d.name, 'step_m': d.step, 'bounds_grid_m': list(d.bounds),
                       'bounds_units': 'deg (lon_west, lat_south, lon_east, lat_north)' if eq else 'south-polar grid m',
                       'zone': d.meta.get('zone'), 'product_id': d.meta.get('product_id'),
                       'source_url': d.meta.get('source_url'), 'file_sha256': d.meta.get('file_sha256'),
                       'array_sha256': d.digest(), 'citation': d.meta.get('citation'),
                       'unit_scale_to_m': d.meta.get('unit_scale', 1.0)})
    sky_out['dem_layers'] = layers
    sid = site_id or f'anysite_{shash}'
    srcs_out = [dict(role=f'{b}-hourly', path=s['path'], sha256=s['sha256'], retrieved_utc=s['retrieved_utc'],
                     cache=s.get('cache'), params_key=s.get('params_key')) for b, s in zip(('sun', 'earth'), srcs)]
    sources = [{'id': 'jpl-horizons', 'description': 'JPL Horizons API, observer tables, CENTER=coord@301, QUANTITIES=4,13,20, '
                                                     'APPARENT=AIRLESS', 'url': H.API}]
    for d in [near] + far_layers:
        sources.append({'id': d.meta.get('product_id'), 'description': d.name, 'url': d.meta.get('source_url'),
                        'sha256': d.meta.get('file_sha256'), 'citation': d.meta.get('citation')})
    vs = B.validation_status({'id': 'site-coordinate-source', 'status': 'not-run',
                              'evidence': f'Coordinates given by the caller ({lat:.7f}, {lon:.7f}); not checked against an '
                                          f'independent site list. Local slope (50 m baseline) = '
                                          f'{B.site_slope(near, x0, y0):.1f} deg.'})
    vs['checks'].append({'id': 'anysite-reproduces-site04-roi3', 'status': 'pass',
                         'evidence': 'science/anysite/tests/test_anysite.py::Site04Roi3Reproduction (hourly Sun / Sun+Earth / '
                                     'gap / clone range of the committed bundle reproduced through the any-site path)'})
    lims = [l for l in B.LIMITATIONS if not l.startswith('Tile-centre bundles')] + [
        'Any-site metrics are on hourly Horizons samples (no bisection refinement of crossings).',
        'Near field: finest cached product within ±25 km at native resolution, ray step native/5 to the inscribed radius '
        'of that product; coarser products supply samples beyond it at their own step.',
        'Uncertainty members labelled "assumed error model" come from assumed error statistics, not from the product.',
        'Coordinates are caller-supplied; a single point is not a surveyed landing site.']
    return {
        'schema': 'polaris-science-results-v1',
        'bundle_id': f'{sid}_{start[:10]}_{days}d_mast{mast_m:g}m',
        'generated_utc': H.unix_to_iso(time.time()),
        'generator': {'code': f'science/anysite ({SOLVER_VERSION})', 'git_commit': B._git(),
                      'command': command or f'python -m science.anysite.solve --lat {lat} --lon {lon} --mast {mast_m:g}'},
        'validation_status': vs,
        'site': {'id': sid, 'name': name or f'Any site ({lat:.5f}, {lon:.5f})', 'lat_deg': lat, 'lon_deg_east': lon,
                 'height_m': round(h, 3), 'height_source': f'bilinear sample of the near-field DEM ({near.name}) at the site',
                 'height_far_dem_m': round(float(far.sample(x0, y0)), 3), 'observer_mast_m': mast_m,
                 'observer_eye_height_m': round(h + mast_m, 3), 'grid_x_m': round(x0, 3), 'grid_y_m': round(y0, 3),
                 'slope_deg_5m_50m_baseline': round(B.site_slope(near, x0, y0), 3),
                 'coordinates_source': f'caller-supplied lat/lon; {LABEL}'},
        'frame': B.FRAME,
        'datum': {'reference_surface': 'sphere', 'radius_m': frames.R_MOON_M,
                  'heights': 'metres above the 1737.4 km reference sphere (LOLA LDEM convention)',
                  'horizons_site_alt_km': round(h / 1000, 6), 'horizons_center_radii_km': [1737.4, 1737.4, 1737.4]},
        'time': {'scale': 'UTC', 'start_utc': H.unix_to_iso(rs[0]['t']), 'stop_utc': H.unix_to_iso(rs[-1]['t']),
                 'step_h': step_h, 'n_samples': len(rs), 'no_extrapolation': 'samples only at Horizons-evaluated times'},
        'skyline': sky_out,
        'samples': [B.sample_record(a, b) if a['m'] is not None and b['m'] is not None else _sample_nodata(a, b)
                    for a, b in zip(rs, re_)],
        'events': [],
        'metrics': met,
        'scenarios': [],
        'provenance': {'sources': sources, 'horizons_raw': srcs_out},
        'limitations': lims,
        'anysite': {'site_hash': shash, 'solver_version': SOLVER_VERSION, 'coverage': cov,
                    'near_field': {'product_id': near_e['id'], 'window_half_m': NEAR_HALF_M, 'native_res_m': near_e['res_m'],
                                   'ray_step_m': step_near, 'fine_step_to_m': near_cut},
                    'far_field': {'product_id': far_e['id'], 'native_res_m': far_e['res_m'], 'max_range_m': sky['max_range_m']},
                    'uncertainty': unc, 'timing_s': timing,
                    'labels': {'geometry': LABEL, 'error_model_members': MB.LABEL_ASSUMED}},
    }


def _sample_nodata(a, b):
    def one(r):
        m = r['m']
        if m is None:
            return {'az_deg': r['az_deg'], 'el_deg': r['el_deg'], 'radius_deg': round(r['radius_deg'], 6),
                    'radius_source': r['radius_source'], 'range_au': r.get('range_au'), 'horizon_deg': None,
                    'margin_deg': None, 'center_visible': False, 'disk_fraction': None, 'horizon_flag': 'unknown'}
        return B.sample_record(r, r)['sun']
    return {'utc': a['utc'], 't_unix': a['t'], 'sun': one(a), 'earth': one(b)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--lat', type=float, required=True)
    ap.add_argument('--lon', type=float, required=True)
    ap.add_argument('--mast', type=float, default=1.0)
    ap.add_argument('--start', default='2026-11-14 00:00')
    ap.add_argument('--days', type=int, default=14)
    ap.add_argument('--step-h', type=int, default=1)
    ap.add_argument('--members', default='clones,assumed,products')
    ap.add_argument('--n-members', type=int, default=20)
    ap.add_argument('--name')
    ap.add_argument('--no-cache', action='store_true')
    a = ap.parse_args(argv)
    cmd = 'python -m science.anysite.solve ' + ' '.join(argv if argv is not None else sys.argv[1:])
    b = solve(a.lat, a.lon, a.mast, a.start, a.days, a.step_h, tuple(k for k in a.members.split(',') if k), a.n_members,
              use_cache=not a.no_cache, name=a.name, command=cmd)
    m = b['metrics']; u = b['anysite']['uncertainty']['summary']
    print(json.dumps({'bundle': str(OUT_DIR / (b['anysite']['site_hash'] + '.json')), 'site_hash': b['anysite']['site_hash'],
                      'sun_pct': m['sun_center_visible_pct'], 'sun_earth_pct': m['sun_and_earth_center_visible_pct'],
                      'longest_sun_gap_h': m['longest_sun_center_hidden_h'], 'timing_s': b['anysite']['timing_s'],
                      'cache_hit': b['anysite']['cache_hit'], 'uncertainty': u}, indent=1))


if __name__ == '__main__':
    main()
