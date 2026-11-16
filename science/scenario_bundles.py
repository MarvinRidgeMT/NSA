"""5th-axis scenario bundles for the ROI landing points, each a FULL recomputation with the same method
as the baseline ROI bundle (science/bundle.py): skyline from the DEM, JPL Horizons hourly samples for the
scenario's own position/height, bisection-refined crossings on real Horizons evaluations, metrics.

Families (deterministic named alternatives, NOT a probability distribution):
  dem-clone        near field = PGDA 78 clone k (Barker et al. 2021). Three clones per site, chosen as the
                   lowest / middle / highest of the 20 clones by hourly Sun+Earth % (tie-break Sun %) from
                   the baseline bundle's derived.margin_series. "k of 20" is a count of terrain models.
  position-offset  observer moved +-100 m along LOCAL east / north (great circle), new DEM ground height.

  .venv/bin/python -m science.scenario_bundles --site site04_roi3 [--only dem-clone|position-offset]

Writes data/bundles/scenarios/<baseline bundle_id>__<tag>.json (polaris-science-results-v1 + `scenario`).
SOURCE-BASED UNVALIDATED.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys

from . import bundle as B
from . import frames, sites

OUT_DIR = B.ROOT / 'data' / 'bundles' / 'scenarios'
START, DAYS, STEP_H = '2026-11-14 00:00', 14, 1
OFFSETS = ((100, 0), (-100, 0), (0, 100), (0, -100))  # (east_m, north_m), local ENU
SELECTION_NOTE = ('selected from the 20 PGDA 78 clones as lowest / middle / highest hourly Sun+Earth % '
                  '(tie-break Sun %) in the baseline margin_series; a rank among 20 terrain models, not a percentile')


def base_bundle(sid, mast):
    p = B.ROOT / 'data' / 'bundles' / f'{sid}_2026-11-14_{DAYS}d_mast{mast:g}m.json'
    return p, json.loads(p.read_text())


def pick_clones(b):
    """Lowest / middle / highest clone by (Sun+Earth %, Sun %); always three distinct clone ids."""
    ms = b['derived']['margin_series']
    ids = ms['clone_ids']
    key = {c: (ms['sun_and_earth_center_visible_pct_hourly_by_clone'][i], ms['sun_center_visible_pct_hourly_by_clone'][i], c)
           for i, c in enumerate(ids)}
    order = sorted(ids, key=lambda c: key[c])
    picks = [('lowest', order[0]), ('middle', order[len(order) // 2]), ('highest', order[-1])]
    tie = key[order[0]][:2] == key[order[-1]][:2]
    return [(('all-tied' if tie else rank), c, {'sun_and_earth_pct_hourly': key[c][0], 'sun_pct_hourly': key[c][1],
                                                'all_20_tied_on_hourly_metrics': tie}) for rank, c in picks]


def specs(sid, b, only=None):
    out = []
    if only in (None, 'dem-clone'):
        for rank, c, ref in pick_clones(b):
            out.append({'family': 'dem-clone', 'tag': f'clone{c:03d}',
                        'parameters': {'clone': c, 'rank_of_20': rank, 'selection': SELECTION_NOTE, 'margin_series_hourly': ref},
                        'label': f'Terrain clone {c} (' + ('all 20 tie hourly' if rank == 'all-tied' else f'{rank} of 20') + ')',
                        'clone': c})
    if only in (None, 'position-offset'):
        for de, dn in OFFSETS:
            out.append({'family': 'position-offset', 'tag': f'pos_e{de:+d}_n{dn:+d}',
                        'parameters': {'east_m': de, 'north_m': dn, 'frame': 'local ENU at the ROI point'},
                        'label': f'Moved {abs(de or dn)} m {"east" if de > 0 else "west" if de < 0 else "north" if dn > 0 else "south"}',
                        'offset': (de, dn)})
    return out


def run(sid, spec, mast, log=print):
    s = sites.SITES[sid]
    kw = {}
    method = ''
    if spec['family'] == 'dem-clone':
        kw['near'] = sites.near_dem(sid, clone=spec['clone'])
        method = ('near field replaced by PGDA 78 clone k; observer ground height re-sampled from that clone; same far DEM, '
                  '1 m near ray step, 280 km range, Horizons queried at that height; crossings bisection-refined')
    else:
        de, dn = spec['offset']
        az = math.degrees(math.atan2(de, dn)) % 360
        kw['lat_lon_override'] = frames.destination(s['lat'], s['lon'], az, math.hypot(de, dn))
        method = ('observer moved along a great circle in local ENU; new ground height from the 5 m DEM; skyline, Horizons '
                  'samples (new lat/lon/height, so new local azimuths) and bisection-refined crossings all recomputed')
    r = B.build(sid, START, DAYS, STEP_H, mast, tag_suffix=spec['tag'], **kw)
    cmd = f'python3 -m science.scenario_bundles --site {sid} --mast {mast:g} ({spec["tag"]})'
    b = B.assemble(sid, r, START, DAYS, STEP_H, mast, cmd)
    b['bundle_id'] += f'__{spec["tag"]}'
    x0, y0 = frames.stereo_forward(s['lat'], s['lon'])
    b['scenario'] = {
        'family': spec['family'], 'tag': spec['tag'], 'label': spec['label'], 'parameters': spec['parameters'],
        'method': method, 'label_status': B.LABEL,
        'observer_offset_grid_m': [round(r['x'] - x0, 3), round(r['y'] - y0, 3)],
        'observer_lat_lon': [round(r['s']['lat'], 8), round(r['s']['lon'], 8)],
        'not_probability': 'deterministic named alternative; counts of terrain models are not probabilities',
    }
    if spec['family'] == 'dem-clone':
        b['scenario']['near_sha256'] = kw['near'].meta.get('file_sha256')
    log(sid, spec['tag'], {k: b['metrics'][k] for k in ('sun_center_visible_pct', 'earth_center_visible_pct',
                                                       'sun_and_earth_center_visible_pct', 'longest_sun_center_hidden_h')},
        'events', len(b['events']))
    return b


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--site', required=True, choices=[k for k, v in sites.SITES.items() if v.get('roi') is not None])
    p.add_argument('--mast', type=float, default=1.0)
    p.add_argument('--only', choices=['dem-clone', 'position-offset'])
    p.add_argument('--skip-existing', action='store_true')
    a = p.parse_args(argv)
    _, base = base_bundle(a.site, a.mast)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for spec in specs(a.site, base, a.only):
        out = OUT_DIR / f'{base["bundle_id"]}__{spec["tag"]}.json'
        if a.skip_existing and out.exists():
            print('skip', out.name, flush=True); continue
        b = run(a.site, spec, a.mast, log=lambda *x: print(*x, flush=True))
        out.write_text(json.dumps(b, indent=1))
        print('wrote', out.relative_to(B.ROOT), hashlib.sha256(out.read_bytes()).hexdigest(), flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
