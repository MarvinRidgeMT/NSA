"""L10 (part) — Certainty Height on a fine mast grid at Site04 RoI 3.

Certainty Height (A2 definition, science/certainty.py on a-science): the lowest mast at which the
Sun centre is visible in 100 % of hourly samples of 14-28 Nov 2026 on EVERY map (nominal PGDA 78
+ clones 1-20). Here masts 1.0-3.0 m in 0.25 m steps, same skyline settings as the bundles
(720 bins, 1 m near step, PGDA 90 far field to 280 km), observer ground re-sampled per map.
Check: it must reproduce the published 1.75 m.
"""
from __future__ import annotations

import numpy as np

from . import skylines as S
from .common import load_bundle, write_result
from .l1_disc import hourly_terms

SITE = 'site04_roi3'
MASTS = [round(1.0 + 0.25 * k, 2) for k in range(5)]  # 1.0-2.0 m tonight (time box); 2.25-3.0 open


def run(clones=range(1, 21)):
    b = load_bundle(SITE)
    series = {}
    for m in MASTS:
        row = {}
        for name, c in [('nominal', None)] + [(f'clone{c:02d}', c) for c in clones]:
            sky = S.skyline(SITE, clone=c, mast_m=m)
            t = hourly_terms(b, sky)
            s = t['sun']['mp'] > 0; e = t['earth']['mp'] > 0
            row[name] = {'sun_pct': round(100 * float(s.mean()), 3), 'sun_earth_pct': round(100 * float((s & e).mean()), 3)}
        sp = [v['sun_pct'] for v in row.values()]
        series[f'{m:.2f}'] = {'maps': row, 'min_sun_pct': min(sp), 'max_sun_pct': max(sp),
                              'n_maps_100pct': int(sum(x >= 100.0 for x in sp)), 'n_maps': len(sp)}
        print(m, min(sp), max(sp), series[f'{m:.2f}']['n_maps_100pct'], flush=True)
    ch = next((float(k) for k, v in series.items() if v['n_maps_100pct'] == v['n_maps']), None)
    return {'item': 'certainty_fine', 'site': SITE, 'masts_m': MASTS, 'definition':
            'lowest mast with Sun-centre visible in 100 % of hourly samples on every map (nominal + 20 clones)',
            'certainty_height_m': ch, 'published_certainty_height_m': 1.75, 'reproduces_published': ch == 1.75,
            'series': series, 'n_clones_used': len(list(clones)),
            'note': 'PGDA 78 publishes 100 clones; this run uses the 20 cached locally. k of N maps is not a probability.'}


README = """# Certainty Height, fine mast series (L10 part 2)

**Label:** PILOT · SOURCE-BASED · UNVALIDATED. Geometric visibility only.

**Question.** At Site04 RoI 3, how does visibility grow between 1.0 and 3.0 m masts in 0.25 m steps, and does the fine
grid reproduce the published Certainty Height of 1.75 m?

**Method.** `python -m science.limits.l10_certainty_fine`. Masts 1.00–2.00 m in 0.25 m steps (2.25–3.00 m not run: time box) × 21 maps (nominal + PGDA 78
clones 1–20). The skyline settings match the bundles. Sun-centre perpendicular margin > 0 on the 337 hourly samples of
14–28 Nov 2026. Certainty Height = the lowest mast that is 100 % on every map.

**Result.** `result.json` → `certainty_height_m`, plus a per-mast series (min/max Sun % over maps, number of maps at 100 %).
The series is written so that a future bundle can carry it.

**What it does not show.** It uses 20 of the 100 public clones. A Certainty Height that is a k-of-N statement over 21 maps
is not a probability. Hourly samples only (L2 shows continuous timing moves Sun % by ≤ 0.26 pt).
"""


def main():
    res = run()
    from .common import BUNDLES
    write_result('certainty_fine', res, [BUNDLES[SITE]], README)
    print('certainty height', res['certainty_height_m'])


if __name__ == '__main__':
    main()
