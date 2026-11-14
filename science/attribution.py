"""A1 Ridge of Record: which terrain controls the skyline, and which terrain costs Sun/Earth hours.

Input: a skyline computed with compute_skyline(..., with_gap=True) and the bundle's hourly samples.
Clustering: consecutive azimuth bins (circular) join one ridge when their controlling points are
within join_m of each other in the polar-stereographic grid (default 2 far-field cells = 160 m),
after allowing for the ray spacing D*dtheta at range D (without it, every ridge beyond ~18 km
would split into single bins because adjacent 0.5 deg rays are > 160 m apart there).
Hours: each hourly sample is attributed to the bin nearest the body's azimuth. A sample counts as
'loss' for a ridge when the body centre is below the terrain skyline there (center_visible false),
the same test the visibility metrics use. 'ctrl' counts every sample whose azimuth bin
belongs to the ridge. Hours = samples x step_h (hourly samples include both window endpoints).
All outputs are SOURCE-BASED UNVALIDATED.
"""
from __future__ import annotations

import math

import numpy as np

from . import frames

LABEL = 'SOURCE-BASED UNVALIDATED'


def _bin_of(az, bins):
    return int(round((az % 360.0) / (360.0 / bins))) % bins


def cluster(sky, join_m=160.0):
    """Return a list of bin-index lists (circular runs), one per ridge."""
    n = sky['bins']; crit = sky['critical']

    def linked(i, j):
        a, b = crit[i], crit[j]
        if a is None or b is None:
            return False
        # Adjacent rays diverge by D*dtheta at range D; that spacing is not a gap in the ridge.
        spacing = 0.5 * (a.get('distance_m', 0.0) + b.get('distance_m', 0.0)) * math.radians(360.0 / n)
        return math.hypot(a['grid_x_m'] - b['grid_x_m'], a['grid_y_m'] - b['grid_y_m']) <= join_m + spacing

    links = [linked(i, (i + 1) % n) for i in range(n)]
    if all(links):
        return [list(range(n))]
    start = (links.index(False) + 1) % n  # first bin after a break
    runs, cur = [], []
    for s in range(n):
        i = (start + s) % n
        if crit[i] is None:
            if cur:
                runs.append(cur); cur = []
            continue
        cur.append(i)
        if not links[i]:
            runs.append(cur); cur = []
    if cur:
        runs.append(cur)
    return runs


def attribute(sky, samples, step_h=1.0, obs_ground_m=None, join_m=160.0):
    if 'runner_up_gap_deg' not in sky:
        raise ValueError('skyline must be computed with with_gap=True')
    n = sky['bins']; w = 360.0 / n; crit = sky['critical']
    runs = cluster(sky, join_m)
    ridge_of = [None] * n
    for r, run in enumerate(runs):
        for i in run:
            ridge_of[i] = r
    acc = [{'sun_loss': 0, 'earth_loss': 0, 'sun_ctrl': 0, 'earth_ctrl': 0} for _ in runs]
    for s in samples:
        for body in ('sun', 'earth'):
            x = s[body]
            if x.get('horizon_flag') == 'unknown':
                continue
            r = ridge_of[_bin_of(x['az_deg'], n)]
            if r is None:
                continue
            acc[r][f'{body}_ctrl'] += 1
            if not x['center_visible']:
                acc[r][f'{body}_loss'] += 1
    ridges = []
    for r, run in enumerate(runs):
        pts = [crit[i] for i in run]
        gx = float(np.mean([p['grid_x_m'] for p in pts])); gy = float(np.mean([p['grid_y_m'] for p in pts]))
        clat, clon = frames.stereo_inverse(gx, gy)
        srcs = [sky['critical_source'][i] for i in run]
        src = srcs[0] if len(set(srcs)) == 1 else 'mixed'
        hmax = max(p['height_m'] for p in pts)
        gaps = [sky['runner_up_gap_deg'][i] for i in run if sky['runner_up_gap_deg'][i] is not None]
        a = acc[r]
        ridges.append({
            'centroid_lat': round(float(clat), 6), 'centroid_lon': round(float(clon), 6),
            'dist_km': round(float(np.mean([p['distance_m'] for p in pts])) / 1000, 4),
            'dist_range_km': [round(min(p['distance_m'] for p in pts) / 1000, 4), round(max(p['distance_m'] for p in pts) / 1000, 4)],
            'az_span_deg': [run[0] * w, run[-1] * w], 'n_bins': len(run),
            'height_m': round(hmax, 3),
            'relief_m': None if obs_ground_m is None else round(hmax - obs_ground_m, 3),
            'max_elev_deg': max(sky['elevation_deg'][i] for i in run),
            'min_gap_deg': None if not gaps else min(gaps),
            'source': src, 'source_counts': {k: srcs.count(k) for k in sorted(set(srcs))},
            'sun_loss_h': a['sun_loss'] * step_h, 'earth_loss_h': a['earth_loss'] * step_h,
            'ctrl_h': a['sun_ctrl'] * step_h, 'sun_ctrl_h': a['sun_ctrl'] * step_h, 'earth_ctrl_h': a['earth_ctrl'] * step_h,
            '_bins': run,
        })
    rel = [rd for rd in ridges if rd['sun_ctrl_h'] or rd['earth_ctrl_h']]
    rel.sort(key=lambda rd: (-(rd['sun_loss_h'] + rd['earth_loss_h']), -rd['ctrl_h'], -rd['earth_ctrl_h']))
    idx_of = {}
    for k, rd in enumerate(rel):
        rd['id'] = f'R{k + 1}'
        rd['of_record'] = bool(rd['sun_loss_h'] or rd['earth_loss_h'])
        for i in rd.pop('_bins'):
            idx_of[i] = k
    per_bin = {
        'ridge_idx': [idx_of.get(i) for i in range(n)],
        'ctrl_idx': sky['critical_index'],
        'ctrl_dist_m': [None if c is None else c['distance_m'] for c in crit],
        'gap_deg': sky['runner_up_gap_deg'],
        'source': sky['critical_source'],
    }
    return {
        'label': LABEL,
        'ridges': [{'id': rd['id'], **{k: v for k, v in rd.items() if k != 'id'}} for rd in rel],
        'per_bin': per_bin,
        'n_clusters_total': len(runs),
        'method': {
            'clustering': f'circular runs of adjacent bins whose controlling points are within {join_m:g} m (grid) '
                          'plus the ray spacing D*dtheta at their mean range D',
            'gap': f'controlling elevation minus best elevation among ray samples >= {sky["gap_sep_cells"]} DEM cells '
                   'away (cell of the DEM supplying the controlling sample)',
            'hours': f'hourly samples x {step_h:g} h; body azimuth -> nearest skyline bin; loss = centre not visible',
            'ctrl_idx': 'index of the controlling sample along the bin ray (skyline sample array)',
            'ridge_idx': 'index into ridges[] (null = bin in a cluster that never held the Sun or Earth in the window)',
            'source': "'near_5m' = controlling height from the near-field (product 78, 5 m) DEM, 'far_80m' = LDEM 80 m",
            'of_record': 'ridge caused at least one Sun or Earth loss sample',
        },
    }


def for_bundle(path, write=False):
    """Recompute the bundle's skyline with the runner-up gap (same inputs), check it reproduces the
    stored skyline exactly, attribute the bundle's hourly samples, and optionally write
    bundle['derived']['attribution']."""
    import hashlib, json, subprocess
    from pathlib import Path
    from . import sites
    from .skyline import compute_skyline
    path = Path(path)
    b = json.loads(path.read_text())
    sid, site = b['site']['id'], b['site']
    if sites.SITES[sid].get('roi') is None:
        raise ValueError('attribution is emitted for ROI bundles only')
    near, far = sites.near_dem(sid), sites.far_dem(sid)
    s = sites.SITES[sid]
    x, y = frames.stereo_forward(s['lat'], s['lon'])
    h = float(near.sample(x, y))  # exactly as bundle.build (the bundle stores it rounded)
    if abs(h - site['height_m']) > 0.001:
        raise AssertionError(f'site height {h} vs bundle {site["height_m"]}')
    sky = compute_skyline(s['lat'], s['lon'], h, site['observer_mast_m'],
                          near=near, far=far, bins=b['skyline']['bins'], max_range_m=b['skyline']['max_range_m'],
                          step_m=b['skyline']['step_near_m'], with_gap=True)
    if sky['elevation_deg'] != b['skyline']['elevation_deg']:
        raise AssertionError('recomputed skyline differs from the stored one; rebuild the bundle first')
    att = attribute(sky, b['samples'], step_h=b['time']['step_h'], obs_ground_m=h,
                    join_m=2 * far.step)
    try:
        rev = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True,
                             cwd=Path(__file__).resolve().parents[1]).stdout.strip() or None
    except Exception:
        rev = None
    att['provenance'] = {'generator': 'science/attribution.py', 'git': rev,
                         'skyline_reproduced_exactly': True,
                         'near_dem_sha256': near.meta.get('file_sha256'), 'far_dem_sha256': far.meta.get('file_sha256'),
                         'join_m': 2 * far.step, 'gap_sep_cells': sky['gap_sep_cells']}
    if write:
        b.setdefault('derived', {})['attribution'] = att
        path.write_text(json.dumps(b, indent=1))
    return att


if __name__ == '__main__':
    import argparse, json
    ap = argparse.ArgumentParser(description='A1 Ridge of Record for ROI bundles')
    ap.add_argument('bundles', nargs='+'); ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    for p in a.bundles:
        att = for_bundle(p, write=a.write)
        print(p)
        for r in att['ridges'][:8]:
            print('  ', r['id'], 'record' if r['of_record'] else '      ', f"az {r['az_span_deg'][0]:.1f}->{r['az_span_deg'][1]:.1f}",
                  f"{r['dist_km']:.3f} km", f"relief {r['relief_m']:+.1f} m", r['source'],
                  f"sun loss {r['sun_loss_h']:g} h ctrl {r['ctrl_h']:g} h | earth loss {r['earth_loss_h']:g} h ctrl {r['earth_ctrl_h']:g} h",
                  f"gap {r['min_gap_deg']}")
