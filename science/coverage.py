"""A3 Coverage Gauge: how much of the decision-relevant skyline lies inside the 5 m clone tile.

The clones (PGDA 78) perturb only the near-field 5 m tile. A clone spread therefore says something
about an hour only when the terrain controlling the skyline at that hour's Sun/Earth azimuth came from
that tile ('near_5m'). Critical hours = hourly samples with |margin| < critical_threshold_deg
(default 1.0 deg, IMPLEMENTATION_PROMPT A3). covered_frac = share of critical hours whose controlling
sample is near_5m. Needs derived.attribution (A1) in the same bundle. SOURCE-BASED UNVALIDATED.
"""
from __future__ import annotations

LABEL = 'SOURCE-BASED UNVALIDATED'


def _bin_of(az, bins):
    return int(round((az % 360.0) / (360.0 / bins))) % bins


def coverage(attribution, samples, step_h=1.0, critical_threshold_deg=1.0, body='sun'):
    pb = attribution['per_bin']; src = pb['source']; n = len(src)
    ridges = attribution['ridges']
    crit = cov = 0; all_n = all_cov = 0; unc = set()
    for s in samples:
        x = s[body]
        if x.get('horizon_flag') == 'unknown':
            continue
        i = _bin_of(x['az_deg'], n)
        near = src[i] == 'near_5m'
        all_n += 1; all_cov += near
        if abs(x['margin_deg']) < critical_threshold_deg:
            crit += 1; cov += near
            r = pb['ridge_idx'][i]
            if not near and r is not None:
                unc.add(ridges[r]['id'])
    return {
        'body': body, 'critical_threshold_deg': critical_threshold_deg,
        'n_critical_h': crit * step_h,
        'covered_frac': None if crit == 0 else round(cov / crit, 4),
        'uncovered_ridges': sorted(unc, key=lambda r: int(r[1:])),
        'all_hours_covered_frac': None if all_n == 0 else round(all_cov / all_n, 4),
        'n_hours': all_n * step_h,
    }


def for_bundle(b, critical_threshold_deg=1.0):
    att = b['derived']['attribution']
    step = b['time']['step_h']
    sun = coverage(att, b['samples'], step, critical_threshold_deg, 'sun')
    earth = coverage(att, b['samples'], step, critical_threshold_deg, 'earth')
    return {
        'label': LABEL,
        # Top level = Sun (the IMPLEMENTATION_PROMPT A3 shape); Earth alongside.
        **{k: v for k, v in sun.items() if k != 'body'},
        'earth': {k: v for k, v in earth.items() if k != 'body'},
        'wording_rule': 'if covered_frac < 0.5, any "robust on every alternate map" claim must show covered_frac next to it',
        'method': {'critical': f'hourly samples with |margin_deg| < {critical_threshold_deg:g} deg',
                   'covered': "controlling skyline sample at the body's azimuth (nearest bin) came from the "
                              "near-field 5 m tile (derived.attribution.per_bin.source == 'near_5m')",
                   'all_hours_covered_frac': 'same test over all hourly samples (comparable to the batch coverage gauge)',
                   'uncovered_ridges': 'ridges (derived.attribution ids) controlling uncovered critical hours'},
    }


if __name__ == '__main__':
    import argparse, json
    from pathlib import Path
    ap = argparse.ArgumentParser(description='A3 Coverage Gauge (needs derived.attribution)')
    ap.add_argument('bundles', nargs='+'); ap.add_argument('--write', action='store_true')
    ap.add_argument('--threshold', type=float, default=1.0)
    a = ap.parse_args()
    for p in a.bundles:
        p = Path(p); b = json.loads(p.read_text())
        c = for_bundle(b, a.threshold)
        print(p.name, 'Sun', c['n_critical_h'], 'crit h, covered', c['covered_frac'], 'all', c['all_hours_covered_frac'],
              c['uncovered_ridges'], '| Earth', c['earth']['n_critical_h'], c['earth']['covered_frac'],
              c['earth']['all_hours_covered_frac'], c['earth']['uncovered_ridges'])
        if a.write:
            b['derived']['coverage'] = c
            p.write_text(json.dumps(b, indent=1))
