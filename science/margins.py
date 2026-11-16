"""A4 margin series for the Margin Ribbon: per hourly sample, Sun/Earth centre margin (deg) on the
nominal DEM (copied from the bundle samples) and the min/max over the PGDA 78 clone DEMs.

Clone skylines: near field = clone k of the product-78 tile (Barker et al. 2021), observer ground
height re-sampled from that clone, far field = the same LDEM 80 m, same 1 m near ray step and 280 km
range as the nominal bundle. Ephemeris: the nominal bundle's Horizons az/el are reused for every
clone. Changing the observer height by the clone's height difference (cm to m) moves the Sun/Earth
direction by < 1e-8 deg (topocentric parallax of ~1 m at >= 384,000 km), far below the margins.
SOURCE-BASED UNVALIDATED.
"""
from __future__ import annotations

import hashlib

import numpy as np

from . import crossings as X
from . import frames, sites
from .skyline import compute_skyline

LABEL = 'SOURCE-BASED UNVALIDATED'


def clone_margins(b, clone, far):
    sid = b['site']['id']; s = sites.SITES[sid]
    near = sites.near_dem(sid, clone=clone)
    x, y = frames.stereo_forward(s['lat'], s['lon'])
    h = float(near.sample(x, y))
    sky = compute_skyline(s['lat'], s['lon'], h, b['site']['observer_mast_m'], near=near, far=far,
                          bins=b['skyline']['bins'], max_range_m=b['skyline']['max_range_m'],
                          step_m=b['skyline']['step_near_m'])
    out = {}
    for body in ('sun', 'earth'):
        m, vis = [], []
        for smp in b['samples']:
            r = smp[body]
            mm = X.margins({'az_deg': r['az_deg'], 'el_deg': r['el_deg'], 'radius_deg': r['radius_deg']}, sky)
            m.append(None if mm is None else round(mm['margin_deg'], 5))
            vis.append(None if mm is None else mm['margin_perp_deg'] > 0)
        out[body] = {'margin_deg': m, 'visible': vis}
    return {'clone': clone, 'ground_m': round(h, 3), 'near_sha256': near.meta.get('file_sha256'),
            'n_truncated_bins': sky['n_truncated'], **out}


def series(b, clones=range(1, 21), log=None):
    far = sites.far_dem(b['site']['id'])
    runs = []
    for c in clones:
        runs.append(clone_margins(b, c, far))
        if log:
            log(c)
    res = {'label': LABEL, 't_unix': [s['t_unix'] for s in b['samples']],
           'n_clones': len(runs), 'clone_ids': [r['clone'] for r in runs]}
    for body in ('sun', 'earth'):
        nom = [s[body]['margin_deg'] for s in b['samples']]
        M = np.array([[np.nan if v is None else v for v in r[body]['margin_deg']] for r in runs], dtype=float)
        res[f'{body}_margin_deg'] = nom
        res[f'{body}_margin_clone_min_deg'] = [None if np.isnan(v) else round(float(v), 5) for v in np.nanmin(M, axis=0)]
        res[f'{body}_margin_clone_max_deg'] = [None if np.isnan(v) else round(float(v), 5) for v in np.nanmax(M, axis=0)]
        pct = [round(100 * float(np.mean([v for v in r[body]['visible'] if v is not None])), 3) for r in runs]
        res[f'{body}_center_visible_pct_hourly_by_clone'] = pct
        res[f'{body}_n_clones_visible'] = [int(sum(bool(r[body]['visible'][i]) for r in runs)) for i in range(len(nom))]
    both = [round(100 * float(np.mean([bool(a) and bool(e) for a, e in zip(r['sun']['visible'], r['earth']['visible'])])), 3)
            for r in runs]
    res['sun_and_earth_center_visible_pct_hourly_by_clone'] = both
    res['clones'] = [{'clone': r['clone'], 'ground_m': r['ground_m'], 'near_sha256': r['near_sha256'],
                      'n_truncated_bins': r['n_truncated_bins']} for r in runs]
    res['method'] = {
        'nominal': 'bundle samples[].{sun,earth}.margin_deg (nominal DEM)',
        'clones': 'near field = PGDA 78 clone k, ground height from that clone, same far DEM / ray step / range as the bundle',
        'ephemeris': 'nominal Horizons az/el reused for every clone (observer-height parallax < 1e-8 deg)',
        'visible': 'centre visible = perpendicular margin > 0 (same test as the bundle); pct over hourly samples incl. both endpoints',
        'note': 'clone spread = N of N terrain models tested, not a probability; clones vary only the 5 m tile',
    }
    return res


if __name__ == '__main__':
    import argparse, json
    from pathlib import Path
    ap = argparse.ArgumentParser(description='A4 margin series with clone min/max')
    ap.add_argument('bundles', nargs='+'); ap.add_argument('--clones', type=int, default=20)
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    for p in a.bundles:
        p = Path(p); b = json.loads(p.read_text())
        r = series(b, range(1, a.clones + 1))
        sp = r['sun_center_visible_pct_hourly_by_clone']; bp = r['sun_and_earth_center_visible_pct_hourly_by_clone']
        print(p.name, 'Sun by clone', min(sp), '-', max(sp), '| Sun+Earth', min(bp), '-', max(bp), flush=True)
        if a.write:
            b.setdefault('derived', {})['margin_series'] = r
            p.write_text(json.dumps(b, indent=1))
