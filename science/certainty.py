"""A2 Certainty Height: visibility vs mast height over the nominal DEM and PGDA 78 clones 1-20.

For each mast height, each DEM (nominal + clones) gets its own skyline (near field = that DEM,
ground height from it, same far LDEM / 1 m ray step / 280 km range as the bundle). The Sun/Earth
az/el are the bundle's hourly Horizons samples (observer-height parallax < 1e-8 deg, see margins.py).
Metric = share of hourly samples with the body centre visible (perpendicular margin > 0).
certainty_height_m[req] = smallest tested mast at which the nominal DEM and every clone meet the
requirement (null if none). Clone spread = N of N terrain models tested, not a probability.
SOURCE-BASED UNVALIDATED.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from . import crossings as X
from . import frames, sites
from .skyline import compute_skyline

LABEL = 'SOURCE-BASED UNVALIDATED'
MASTS = (1.0, 1.25, 1.5, 1.75, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0)   # same set as polaris_batch v2 `certainty`
REQUIREMENTS = {
    'sun_center_pct_eq_100': ('sun_center_pct', lambda v: v >= 100.0 - 1e-9),   # batch definition
    'sun_center_pct_ge_70': ('sun_center_pct', lambda v: v >= 70.0),            # IMPLEMENTATION_PROMPT default
    'both_center_pct_ge_40': ('both_center_pct', lambda v: v >= 40.0),          # IMPLEMENTATION_PROMPT default
}


def _pcts(b, sky):
    vs, ve = [], []
    for smp in b['samples']:
        out = []
        for body in ('sun', 'earth'):
            r = smp[body]
            m = X.margins({'az_deg': r['az_deg'], 'el_deg': r['el_deg'], 'radius_deg': r['radius_deg']}, sky)
            out.append(None if m is None else m['margin_perp_deg'] > 0)
        vs.append(out[0]); ve.append(out[1])
    ok = [i for i in range(len(vs)) if vs[i] is not None and ve[i] is not None]
    sun = 100 * np.mean([vs[i] for i in ok]); both = 100 * np.mean([vs[i] and ve[i] for i in ok])
    return round(float(sun), 3), round(float(both), 3)


def run(b, clones=range(1, 21), masts=MASTS, log=print):
    sid = b['site']['id']; s = sites.SITES[sid]
    far = sites.far_dem(sid)
    x, y = frames.stereo_forward(s['lat'], s['lon'])
    tags = ['nominal'] + list(clones)
    rows = {}
    for tag in tags:  # one near DEM in memory at a time
        near = sites.near_dem(sid) if tag == 'nominal' else sites.near_dem(sid, clone=tag)
        h = float(near.sample(x, y))
        for m in masts:
            sky = compute_skyline(s['lat'], s['lon'], h, m, near=near, far=far, bins=b['skyline']['bins'],
                                  max_range_m=b['skyline']['max_range_m'], step_m=b['skyline']['step_near_m'])
            rows[(tag, m)] = _pcts(b, sky)
        if log:
            log(sid, tag, time.strftime('%H:%M:%S'), flush=True)
        del near
    return rows, list(clones), list(masts)


def summarise(rows, clone_ids, masts, provenance):
    curve, ch = [], {}
    for m in masts:
        for metric, k in (('sun_center_pct', 0), ('both_center_pct', 1)):
            v = np.array([rows[(c, m)][k] for c in clone_ids])
            row = {'mast_m': m, 'metric': metric, 'nominal': rows[('nominal', m)][k],
                   'min': float(v.min()), 'p10': round(float(np.percentile(v, 10)), 3),
                   'median': round(float(np.median(v)), 3), 'p90': round(float(np.percentile(v, 90)), 3),
                   'max': float(v.max()), 'n_clones': len(clone_ids), 'by_clone': [float(x) for x in v]}
            for req, (rm, test) in REQUIREMENTS.items():
                if rm == metric:
                    k_pass = int(sum(test(x) for x in v))
                    row.setdefault('pass', {})[req] = f'{k_pass}/{len(v)}'
                    row.setdefault('nominal_pass', {})[req] = bool(test(row['nominal']))
            curve.append(row)
    for req, (rm, test) in REQUIREMENTS.items():
        ok = [m for m in masts
              if test(rows[('nominal', m)][0 if rm == 'sun_center_pct' else 1])
              and all(test(rows[(c, m)][0 if rm == 'sun_center_pct' else 1]) for c in clone_ids)]
        ch[req] = min(ok) if ok else None
    return {
        'label': LABEL, 'masts_m': masts, 'clone_ids': clone_ids, 'certainty_curve': curve,
        # Primary number (what the viewer's B3 reads): the batch definition, 100 % Sun on every DEM.
        'certainty_height_m': ch['sun_center_pct_eq_100'],
        'certainty_height_primary_requirement': 'sun_center_pct_eq_100',
        'certainty_height_by_requirement_m': ch,
        'requirements': {'sun_center_pct_eq_100': 'Sun centre visible in 100 % of hourly samples (polaris_batch definition)',
                         'sun_center_pct_ge_70': 'Sun centre visible >= 70 % (team requirement, Anish 14 Nov 13:50 ET)',
                         'both_center_pct_ge_40': 'Sun and Earth centres both visible >= 40 % (team requirement, Anish 14 Nov 13:50 ET)'},
        'method': {'dems': 'nominal PGDA 78 tile + clones (near field), LDEM 80 m far field, 1 m near ray step, 280 km',
                   'ephemeris': "the bundle's hourly Horizons samples (Sun/Earth az/el), reused for every mast and DEM",
                   'metric': 'share of hourly samples (both window endpoints included) with the centre visible',
                   'certainty_height': 'smallest tested mast where the nominal DEM and every clone meet the requirement; '
                                       'resolution is the tested mast grid',
                   'note': 'clone spread = N of N terrain models tested, not a probability; clones vary only the 5 m tile'},
        'provenance': provenance,
    }


BATCH_REFERENCE = {
    # Values quoted from project docs (not recomputed here): polaris_batch v2, 1 m near step, 20 clones.
    'site04_roi3': {'source': 'claude/BATCH_RESULTS_CLOUD_2026-11-14.md; claude/BATCH_RESULTS_THIRD_2026-11-14.md',
                    'certainty_height_m': 1.75,
                    'sun_center_pct_range': {'1.0': [87.2, 97.0], '1.25': [91.1, 100.0], '1.5': [96.1, 100.0]}},
    'site01_roi6': {'source': 'claude/BATCH_RESULTS_THIRD_2026-11-14.md',
                    'certainty_height_m': 1.0, 'note': 'reported as <= 1 m (100 % at every mast tested)'},
}


def write_into_bundles(sid, res, bundle_dir):
    out = dict(res); out['batch_reference'] = BATCH_REFERENCE.get(sid)
    out.setdefault('requirements', {}).update({
        'sun_center_pct_ge_70': 'Sun centre visible >= 70 % (team requirement, Anish 14 Nov 13:50 ET)',
        'both_center_pct_ge_40': 'Sun and Earth centres both visible >= 40 % (team requirement, Anish 14 Nov 13:50 ET)'})
    if isinstance(out.get('certainty_height_m'), dict):  # output of an earlier summarise(); same numbers
        ch = out.pop('certainty_height_m')
        out = {**{k: v for k, v in out.items() if k not in ('certainty_curve',)},
               'certainty_height_m': ch['sun_center_pct_eq_100'],
               'certainty_height_primary_requirement': 'sun_center_pct_eq_100',
               'certainty_height_by_requirement_m': ch, 'certainty_curve': res['certainty_curve']}
    for p in sorted(Path(bundle_dir).glob(f'{sid}_2026-11-14_14d_mast*.json')):
        b = json.loads(p.read_text())
        d = b.setdefault('derived', {})
        d['certainty'] = out
        # Flat aliases in the IMPLEMENTATION_PROMPT A2 names, for readers of the results bundle.
        d['certainty_curve'] = out['certainty_curve']; d['certainty_height_m'] = out['certainty_height_m']
        p.write_text(json.dumps(b, indent=1))
        print('wrote', p.name)


if __name__ == '__main__' and __import__('sys').argv[1:2] == ['--write']:
    import sys
    for f in sys.argv[2:]:
        res = json.loads(Path(f).read_text())
        sid = Path(f).stem
        write_into_bundles(sid, res, Path(__file__).resolve().parents[1] / 'data' / 'bundles')
    raise SystemExit

if __name__ == '__main__':
    import argparse, subprocess
    ap = argparse.ArgumentParser(description='A2 Certainty Height sweep')
    ap.add_argument('--bundle', required=True, help='ephemeris source bundle (any mast) for the site')
    ap.add_argument('--out', required=True); ap.add_argument('--clones', type=int, default=20)
    a = ap.parse_args()
    b = json.loads(Path(a.bundle).read_text())
    rows, cids, masts = run(b, range(1, a.clones + 1))
    rev = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
    res = summarise(rows, cids, masts, {'generator': 'science/certainty.py', 'git': rev,
                                        'ephemeris_bundle': b['bundle_id']})
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(json.dumps(res['certainty_height_m']))
