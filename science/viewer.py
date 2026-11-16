"""Export polaris-science-results-v1 results as a POLARIS-X5D-v2 viewer bundle with the additive
`datasets[i].derived` block (web/docs/VIEWER_BUNDLE_CONTRACT.md on b-experience).

Nothing here recomputes a result shown in the bundle's metrics: skyline, horizon,
margins and visibility flags are copied from the science bundles. The only new
geometry is per-failure ray profiles and first-hit distances, computed with the same
DEMs, great-circle rays and Moon-fixed 3D elevation model as science/skyline.py.

  python -m science.viewer --out data/viewer/polaris-x5d-roi-2026-11-14-v2.json \
      --dataset site01_roi6:1,10 --dataset site04_roi3:1,10 --dataset site04_roi4:1,10
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from . import frames, sites
from .bundle import ROOT, _git
from .skyline import _distances, _near_extent

STATUS = 'SOURCE_BASED_UNVALIDATED'
CROP_N = 401  # 401 x 401 px of the 5 m product-78 tile = 2 km square


def _bundle(sid, mast, start='2026-11-14', days=14):
    p = ROOT / 'data' / 'bundles' / f'{sid}_{start}_{days}d_mast{mast:g}m.json'
    return p, json.loads(p.read_text())


def dem_crop(near, x0, y0, n=CROP_N):
    """n x n crop of the near DEM on its own pixel centres, rows south-to-north, coords relative to the site."""
    c = int(math.floor((x0 - near.x_left) / near.step)); r = int(math.floor((near.y_top - y0) / near.step))
    h = n // 2
    Z = near.Z[r - h:r + h + 1, c - h:c + h + 1]
    if Z.shape != (n, n) or not np.isfinite(Z).all():
        raise ValueError('crop leaves the tile or contains nodata')
    vals = np.round(Z[::-1].astype(float), 3)  # flip: row 0 = south
    ox = near.x_left + (c - h + 0.5) * near.step - x0
    oy = near.y_top - (r + h + 0.5) * near.step - y0
    return vals, ox, oy


def ray_profile(s, eye_h, az, near, far, step_near):
    d = _distances(step_near, _near_extent(near, s['lat'], s['lon']), far.step, sites.MAX_RANGE_M)
    la, lo = frames.destination(s['lat'], s['lon'], np.full(1, az), d[None, :])
    la, lo = la[0], lo[0]
    x, y = frames.stereo_forward(la, lo)
    h = near.sample(x, y); m = ~np.isfinite(h); h[m] = far.sample(x[m], y[m])
    P0 = frames.moon_fixed(s['lat'], s['lon'], eye_h); up = frames.up_vector(s['lat'], s['lon'])
    P = (frames.R_MOON_M + np.nan_to_num(h))[:, None] * frames.unit(la, lo)
    v = P - P0; vu = v @ up; hor = np.linalg.norm(v - vu[:, None] * up, axis=1)
    el = np.degrees(np.arctan2(vu, hor))
    ok = np.isfinite(h)
    return {'d': d[ok], 'x': x[ok], 'y': y[ok], 'h': h[ok], 'hor': hor[ok], 'z_tangent': eye_h + vu[ok], 'el': el[ok]}


def first_hit(pr, target_el):
    k = np.nonzero(pr['el'] > target_el)[0]
    return None if k.size == 0 else int(k[0])


def scenario(sid, mast, b, near, far, ox, oy, n, baseline=False):
    s = sites.SITES[sid]; x0, y0 = b['site']['grid_x_m'], b['site']['grid_y_m']
    eye = b['site']['observer_eye_height_m']; step = b['skyline']['step_near_m']
    S = b['samples']
    series, failures = {}, []
    cache = {}

    def prof(az):
        k = round(az, 6)
        if k not in cache:
            cache[k] = ray_profile(s, eye, az, near, far, step)
        return cache[k]

    for tgt in ('sun', 'earth'):
        vis = [x[tgt]['center_visible'] for x in S]
        hits = []
        for x, v in zip(S, vis):
            if v:
                hits.append(None); continue
            pr = prof(x[tgt]['az_deg']); k = first_hit(pr, x[tgt]['el_deg'])
            hits.append(None if k is None else round(float(pr['d'][k]), 1))
        series[tgt] = {'visible': vis, 'horizonElDeg': [x[tgt]['horizon_deg'] for x in S],
                       'marginDeg': [x[tgt]['margin_deg'] for x in S], 'firstHitM': hits}
        k = 0
        while k < len(vis):
            if vis[k]:
                k += 1; continue
            j = k
            while j < len(vis) and not vis[j]:
                j += 1
            w = min(range(k, j), key=lambda q: S[q][tgt]['margin_deg'])
            az, el = S[w][tgt]['az_deg'], S[w][tgt]['el_deg']
            pr = prof(az); fh = first_hit(pr, el); top = int(np.argmax(pr['el']))
            end = max(top, fh or 0)
            lim = np.searchsorted(pr['d'], pr['d'][end] * 1.5 + 50.0)
            idx = np.unique(np.concatenate([np.linspace(0, max(lim - 1, 1), 300).round().astype(int), [top] + ([fh] if fh is not None else [])]))
            idx = idx[idx < len(pr['d'])]
            hit = None
            if fh is not None:
                gx, gy = float(pr['x'][fh] - x0), float(pr['y'][fh] - y0)
                hit = {'distanceM': round(float(pr['d'][fh]), 1), 'xM': round(gx, 2), 'yM': round(gy, 2),
                       'heightM': round(float(pr['h'][fh]), 3),
                       'cell': [int(round((gx - ox) / near.step)), int(round((gy - oy) / near.step))]}
            failures.append({
                'id': f'{sid}-m{mast:g}-{tgt}-{w:03d}', 'target': tgt, 'sampleIndex': w, 'time': S[w]['utc'],
                'azimuthDeg': az, 'targetElDeg': el, 'horizonElDeg': S[w][tgt]['horizon_deg'],
                'marginDeg': S[w][tgt]['margin_deg'], 'blockedSamples': j - k, 'firstHit': hit,
                'profile': {'distanceM': [round(float(v), 2) for v in pr['hor'][idx]],
                            'terrainM': [round(float(v), 3) for v in pr['z_tangent'][idx]],
                            'rayM': [round(float(eye + hd * math.tan(math.radians(el))), 3) for hd in pr['hor'][idx]]},
                'note': 'profile in the observer tangent frame (3D, curvature included); exact-azimuth ray, so it can differ '
                        'slightly from the 0.5 deg skyline interpolation; firstHit null if this ray clears the target'})
            k = j
    both = [a and c for a, c in zip(series['sun']['visible'], series['earth']['visible'])]
    m = b['metrics']
    met = [
        {'id': 'sun_fraction', 'label': 'Sun visible (centre)', 'value': m['sun_center_visible_pct'], 'unit': '%'},
        {'id': 'earth_fraction', 'label': 'Earth visible (centre)', 'value': m['earth_center_visible_pct'], 'unit': '%'},
        {'id': 'both_fraction', 'label': 'Sun and Earth together', 'value': m['sun_and_earth_center_visible_pct'], 'unit': '%'},
        {'id': 'longest_dark', 'label': 'Longest Sun obstruction', 'value': m['longest_sun_center_hidden_h'], 'unit': 'h'},
        {'id': 'longest_blackout', 'label': 'Longest Earth obstruction', 'value': m['longest_earth_center_hidden_h'], 'unit': 'h'},
        {'id': 'min_sun_margin', 'label': 'Minimum Sun margin', 'value': m['min_sun_margin_deg'], 'unit': 'deg'},
    ]
    sk = b['skyline']
    return {
        'id': 'baseline' if baseline else f'mast{mast:g}', 'label': f'ROI point · {mast:g} m mast',
        'kind': 'baseline' if baseline else 'mast_height',
        'description': (f'{b["bundle_id"]}: solver outputs copied from the science bundle '
                        f'(sha256 {hashlib.sha256(json.dumps(b, sort_keys=True).encode()).hexdigest()[:16]}…). '
                        'Metrics use bisection-refined crossing intervals; strips show the hourly samples.'),
        'observer': {'xM': 0.0, 'yM': 0.0, 'groundM': b['site']['height_m'], 'mastM': mast},
        'attribution': b.get('derived', {}).get('attribution'),  # A1 Ridge of Record (science/attribution.py)
        'coverage': b.get('derived', {}).get('coverage'),  # A3 Coverage Gauge (science/coverage.py)
        'margin_series': b.get('derived', {}).get('margin_series'),  # A4 nominal + clone min/max margins (science/margins.py)
        'skyline': {'azimuthDeg': sk['azimuth_deg'], 'elevationDeg': sk['elevation_deg'], 'reachM': sk['valid_reach_m'],
                    'coverage': ['full' if st == 'complete' else 'truncated' for st in sk['status']]},
        'samples': {'sun': series['sun'], 'earth': series['earth'], 'both': {'visible': both}},
        'metrics': met, 'failures': failures,
    }


def dataset(sid, masts):
    s = sites.SITES[sid]
    paths, bs = zip(*[_bundle(sid, m) for m in masts])
    b0 = bs[0]
    for b in bs[1:]:
        assert [x['utc'] for x in b['samples']] == [x['utc'] for x in b0['samples']], 'samples must align'
        assert [x['sun']['az_deg'] for x in b['samples']] == [x['sun']['az_deg'] for x in b0['samples']]
    near, far = sites.near_dem(sid), sites.far_dem(sid)
    x0, y0 = b0['site']['grid_x_m'], b0['site']['grid_y_m']
    vals, ox, oy = dem_crop(near, x0, y0)
    L = math.radians(s['lon'])
    gates = [{'gate': c['id'], 'status': c['status'].upper().replace('-', '_'), 'evidence': c['evidence']}
             for c in b0['validation_status']['checks']]
    hraw = [r for r in b0['provenance']['horizons_raw'] if r['role'].endswith('hourly')]
    return {
        'siteId': sid,
        'site': {'id': sid, 'name': s['name'], 'code': f'{s["tile"].capitalize()} ROI{s["roi"]}',
                 'latitudePlanetocentricDeg': s['lat'], 'longitudeEastDeg': s['lon'],
                 'projectedMeters': {'x': x0, 'y': y0},
                 'coordinateRole': 'PGDA product 78 published ROI polygon centroid; not a surveyed touchdown point'},
        'dem': {'kind': 'nasa', 'layer': 'local_5m_crop', 'siteId': sid, 'n': CROP_N, 'spacing': near.step,
                'originX': round(ox, 3), 'originY': round(oy, 3), 'values': vals.ravel().tolist(),
                'source': near.meta['source_url'], 'sourceSha256': near.meta['file_sha256'],
                'cropValuesSha256': hashlib.sha256(np.ascontiguousarray(vals, dtype='<f8').tobytes()).hexdigest(),
                'verticalUnits': 'meters', 'frame': 'MOON_ME / DE421',
                'crsConvention': 'IAU Moon sphere R=1737400 m; south polar stereographic; x/y relative to the site grid point',
                'rowOrder': 'south-to-north after explicit source flip',
                'validCoverageRadiusM': round((CROP_N // 2) * near.step, 1),
                'note': 'display crop only; the solver skyline uses the full 5 m tile plus LDEM 80 m to 280 km'},
        'ephemeris': {'kind': 'jpl-horizons-observer-ephemeris', 'source': 'NASA/JPL Horizons API',
                      'sourceUrl': 'https://ssd.jpl.nasa.gov/api/horizons.api', 'frame': 'MEAN_ME (high precision), DE441',
                      'longitudeConvention': 'east-positive', 'azimuthConvention': 'clockwise from local north: N=0, E=90',
                      'angleType': 'airless apparent target-centre azimuth/elevation', 'timeScale': 'UTC', 'sampling': '60 min',
                      'records': [{'target': r['role'].split('-')[0], 'rawFile': r['path'], 'sha256': r['sha256'],
                                   'retrievedUTC': r['retrieved_utc']} for r in hraw],
                      'samples': [{'time': x['utc'], 'sun': {'az': x['sun']['az_deg'], 'el': x['sun']['el_deg']},
                                   'earth': {'az': x['earth']['az_deg'], 'el': x['earth']['el_deg']}} for x in b0['samples']]},
        'validation': {'status': STATUS, 'gates': gates},
        'derived': {
            'producer': {'name': 'science/viewer.py (POLARIS X a-science)', 'version': _git()},
            'status': STATUS,
            'frame': {'localNorthInGrid': [math.sin(L), math.cos(L)], 'localEastInGrid': [math.cos(L), -math.sin(L)],
                      'note': 'south-polar stereographic grid at the site longitude; same basis as science/frames.py'},
            'skylineBinDeg': 360.0 / b0['skyline']['bins'],
            'sourceBundles': [{'file': p.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                              for p in paths],
            'scenarios': [scenario(sid, m, b, near, far, ox, oy, CROP_N, baseline=(i == 0)) for i, (m, b) in enumerate(zip(masts, bs))],
            # A1: the baseline (first-mast) scenario's attribution; every scenario also carries its own.
            'attribution': None if b0.get('derived', {}).get('attribution') is None else
            {**b0['derived']['attribution'], 'scenarioId': 'baseline', 'mast_m': masts[0]},
            # A2 Certainty Height (science/certainty.py): per site, the same block in every mast bundle.
            'certainty_curve': (b0.get('derived', {}).get('certainty') or {}).get('certainty_curve'),
            'certainty_height_m': (b0.get('derived', {}).get('certainty') or {}).get('certainty_height_m'),
            'certainty': b0.get('derived', {}).get('certainty'),
            # A3: same convention (baseline scenario; every scenario carries its own).
            'coverage': None if b0.get('derived', {}).get('coverage') is None else
            {**b0['derived']['coverage'], 'scenarioId': 'baseline', 'mast_m': masts[0]},
        },
    }


def build(specs):
    ds = [dataset(sid, masts) for sid, masts in specs]
    return {
        'format': 'POLARIS-X5D-v2', 'schemaVersion': '2.1.0',
        'generatedUTC': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'producer': {'name': 'science/viewer.py (POLARIS X a-science)', 'version': _git()},
        'validation': {'status': STATUS, 'reason': 'NASA/JPL inputs, solver outputs SOURCE-BASED UNVALIDATED '
                       '(PGDA 69 grid comparison at Site01 is a consistency check, not a validation of these ROI numbers)',
                       'gates': [{'gate': 'flight_or_mission_certification', 'status': 'NOT_APPLICABLE',
                                  'evidence': 'Research prototype only'}]},
        'sources': {'NASA_PGDA_78': 'https://pgda.gsfc.nasa.gov/products/78', 'NASA_PGDA_90': 'https://pgda.gsfc.nasa.gov/products/90',
                    'regionalDem': 'https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF',
                    'JPL_Horizons': 'https://ssd.jpl.nasa.gov/api/horizons.api'},
        'contract': {'localAxes': {'x': 'grid east metres relative to site', 'y': 'grid north metres relative to site', 'z': 'elevation metres'},
                     'time': 'UTC ISO-8601', 'scenarioAxis': 'named deterministic case; never a spatial dimension or probability',
                     'visibility': 'target centre above finite-DEM terrain skyline; no DSN/power guarantee',
                     'constraints': 'no mission thresholds set: metrics carry no PASS/FAIL until the team defines them'},
        'datasets': ds,
    }


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    p.add_argument('--dataset', action='append', required=True, help='site_id:mast1,mast2 (first mast = baseline)')
    a = p.parse_args(argv)
    specs = [(d.split(':')[0], [float(m) for m in d.split(':')[1].split(',')]) for d in a.dataset]
    out = ROOT / a.out; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(specs), separators=(',', ':')))
    print('wrote', out, out.stat().st_size, hashlib.sha256(out.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
