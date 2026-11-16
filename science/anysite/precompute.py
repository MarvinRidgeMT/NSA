"""Precompute the any-site list (science/anysite/precompute_sites.json) for everything the cached data supports.

  python -m science.anysite.precompute [--groups current_sites,landing_sites,south_grid_1deg] [--workers 4]

Terrain: get_stack() (the merged whole-Moon pyramid since R1; POLARIS_ANYSITE_STACK=legacy for the per-product adapter).

Sites with no covering product, or without coordinates, are recorded as 'needs data' / 'needs coordinates' with the reason.
Writes the committed summary data/anysite/precompute_summary.json (metrics, timings, hashes; no rasters). Full bundles stay
in data/cache/anysite/bundles/<site_hash>.json (git-ignored, reproducible).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
import traceback
from multiprocessing import Pool
from pathlib import Path

from . import products as P

LIST = Path(__file__).with_name('precompute_sites.json')
SUMMARY = P.ROOT / 'data' / 'anysite' / 'precompute_summary.json'


def grid_points(hemisphere='south'):
    sgn = -1 if hemisphere == 'south' else 1
    pts = [{'id': f'{hemisphere[0]}grid_pole', 'name': f'{hemisphere} pole', 'lat': sgn * 90.0 + (1e-6 if sgn < 0 else -1e-6),
            'lon': 0.0}]
    for a in range(80, 90):
        n = max(1, round(360 * math.cos(math.radians(a))))
        for k in range(n):
            lon = ((k * 360.0 / n) + 180) % 360 - 180
            pts.append({'id': f'{hemisphere[0]}grid_{a}_{k:03d}', 'name': f'{a} {hemisphere[0].upper()}, {lon:.2f} E',
                        'lat': sgn * float(a), 'lon': round(lon, 6)})
    return pts


def grid_global(step=10, max_abs_lat=70):
    pts = []
    for la in range(-max_abs_lat, max_abs_lat + 1, step):
        for lo in range(-180, 180, step):
            pts.append({'id': f'ggrid_{la:+03d}_{lo:+04d}', 'name': f'{abs(la)} {"N" if la >= 0 else "S"}, {lo} E',
                        'lat': float(la), 'lon': float(lo)})
    return pts


def sites(groups):
    spec = json.loads(LIST.read_text())
    out = []
    for g in spec['groups']:
        if g['id'] not in groups:
            continue
        pts = g.get('sites') or (grid_points('south') if g['id'] == 'south_grid_1deg' else
                                 grid_points('north') if g['id'] == 'north_grid_1deg' else
                                 grid_global() if g['id'] == 'global_grid_10deg' else [])
        out += [{**p, 'group': g['id']} for p in pts]
    return out


def _members_for(group):
    return ('clones', 'assumed', 'products') if group in ('current_sites', 'landing_sites') else ()


def run_one(p):
    from .solve import solve
    from .stack import get_stack
    rec = {'id': p['id'], 'name': p['name'], 'group': p['group'], 'lat': p['lat'], 'lon': p['lon']}
    if p['lat'] is None:
        rec.update(status='needs coordinates', reason='no official coordinates published (see precompute_sites.json)')
        return rec
    st = get_stack()
    if getattr(st, 'kind', None) == 'pyramid':
        if st.coverage(p['lat'], p['lon'])['window']['level'] < 0:
            rec.update(status='needs data', reason='no pyramid level has data at this point')
            return rec
    elif not st.covering(p['lat'], p['lon']):
        rec.update(status='needs data', reason='no cached terrain product covers this point')
        return rec
    t = time.time()
    try:
        b = solve(p['lat'], p['lon'], 1.0, member_kinds=_members_for(p['group']), stack=st, name=p['name'],
                  command=f'python -m science.anysite.precompute (site {p["id"]})')
    except Exception as exc:  # recorded, never hidden
        rec.update(status='error', reason=f'{type(exc).__name__}: {exc}', trace=traceback.format_exc()[-600:])
        return rec
    m = b['metrics']; a = b['anysite']; sky = b['skyline']
    rec.update(status='done', site_hash=a['site_hash'], wall_s=round(time.time() - t, 2), cache_hit=a['cache_hit'],
               terrain=a.get('terrain'), near_cut_m=round(sky['near_cut_m'], 1),
               near_level=(a['near_field'].get('pyramid') or {}).get('level'),
               near_zone=(a['near_field'].get('pyramid') or {}).get('zone'),
               timing_s=a['timing_s'], near_product=a['near_field']['product_id'], far_product=a['far_field']['product_id'],
               ground_m=b['site']['height_m'], slope_deg=b['site']['slope_deg_5m_50m_baseline'],
               sun_pct=m['sun_center_visible_pct_hourly_samples'], earth_pct=m['earth_center_visible_pct_hourly_samples'],
               sun_earth_pct=m['sun_and_earth_center_visible_pct_hourly_samples'],
               longest_sun_gap_h=m['longest_sun_center_hidden_h'], n_unknown_sun=m['n_unknown_sun'],
               n_truncated_bins=sky['n_truncated'], max_range_m=sky['max_range_m'],
               required_range_world_m=sky['curvature_limit']['required_range_world_m'],
               n_range_limited_world=sky['curvature_limit']['n_range_limited_world'],
               uncertainty={k: v for k, v in a['uncertainty']['summary'].items()},
               horizons_raw=[h['sha256'] for h in b['provenance']['horizons_raw']])
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--groups', default='current_sites,landing_sites,south_grid_1deg,artemis3_regions,north_grid_1deg,'
                                        'global_grid_10deg')
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--limit', type=int)
    ap.add_argument('--fresh', action='store_true', help='drop the previous summary rows (new solver version)')
    a = ap.parse_args(argv)
    workers = min(4, a.workers)                  # other sessions share the CPU
    todo = sites(a.groups.split(','))
    if a.limit:
        todo = todo[:a.limit]
    old = {}
    if SUMMARY.exists() and not a.fresh:
        old = {r['id']: r for r in json.loads(SUMMARY.read_text()).get('sites', [])}
    t0 = time.time(); res = []
    with Pool(workers) as pool:
        for r in pool.imap_unordered(run_one, todo):
            res.append(r); old[r['id']] = r
            print(r['id'], r['status'], r.get('wall_s', ''), r.get('sun_pct', ''), r.get('reason', ''), flush=True)
            if len(res) % 10 == 0:
                _write(old)
    _write(old, wall=time.time() - t0, workers=workers)


def _timing_by_group(rows):
    out = {}
    for g in sorted({r['group'] for r in rows}):
        w = sorted(r['wall_s'] for r in rows if r['group'] == g and r['status'] == 'done' and not r.get('cache_hit'))
        if w:
            out[g] = {'n': len(w), 'min': w[0], 'median': w[len(w) // 2], 'p95': w[min(len(w) - 1, int(0.95 * len(w)))],
                      'max': w[-1], 'n_over_60s': sum(x > 60 for x in w)}
    return out


def _write(by_id, wall=None, workers=None):
    rows = sorted(by_id.values(), key=lambda r: (r['group'], r['id']))
    stat = {}
    for r in rows:
        stat.setdefault(r['group'], {}).setdefault(r['status'], 0)
        stat[r['group']][r['status']] += 1
    done = [r for r in rows if r['status'] == 'done' and not r.get('cache_hit')]
    out = {'schema': 'polaris-anysite-precompute-summary-v1', 'label': 'SOURCE-BASED UNVALIDATED',
           'window': '2026-11-14 00:00 UTC + 14 d, hourly; mast 1 m', 'counts': stat,
           'new_site_wall_s': None if not done else {'min': min(r['wall_s'] for r in done),
                                                     'median': sorted(r['wall_s'] for r in done)[len(done) // 2],
                                                     'max': max(r['wall_s'] for r in done), 'n': len(done)},
           'note': 'wall_s per site was measured with up to 4 sites in parallel (shared CPU with other sessions).',
           'terrain': 'merged whole-Moon pyramid (nominal) + per-product members (docs/v2/PHASE_1_R1_PLAN.md)',
           'timing_by_group': _timing_by_group(rows),
           'sites': rows}
    if wall is not None:
        out['last_run'] = {'wall_s': round(wall, 1), 'workers': workers,
                           'products_registered_at_end': [e['id'] for e in P.registry()],
                           'note': 'a site records its own near/far terrain (bundle dem_layers, pyramid tiles + index SHA-256)'}
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    tmp = SUMMARY.with_suffix(f'.{os.getpid()}.tmp'); tmp.write_text(json.dumps(out, indent=1)); tmp.replace(SUMMARY)


if __name__ == '__main__':
    main()
