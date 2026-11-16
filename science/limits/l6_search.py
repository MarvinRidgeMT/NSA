"""L6 — what observations exist at the Site04 RoI 3 lander point (search only, no pixels read).

Inputs are the committed metadata listings in data/science_limits/L6_hero_observation/ (PDS ODE
queries; Zenodo GSFC SfS archive DEM bounds read from GeoTIFF headers via /vsizip//vsicurl/;
region-6 NAC map bounds when that header scan has finished). This module only summarises them.
"""
from __future__ import annotations

import json
import math

import numpy as np

from .common import OUT_ROOT, write_result

D = OUT_ROOT / 'L6_hero_observation'
P0 = {'lat': -89.78012, 'lon_east': -156.32023, 'grid_x_m': -2677.834, 'grid_y_m': -6106.132}


def summarise():
    z = json.loads((D / 'zenodo_sfs_region_bounds.json').read_text())
    cdr = json.loads((D / 'ode_cdrnac_p0.json').read_text())
    dtm = json.loads((D / 'ode_nacdtm_p0.json').read_text())['product']
    inc = np.array([float(p['Incidence_angle']) for p in cdr['products'] if p.get('Incidence_angle')])
    years = {}
    for p in cdr['products']:
        years[p['UTC_start_time'][:4]] = years.get(p['UTC_start_time'][:4], 0) + 1
    contains = [r for r, v in z.items() if v['dist_to_hero_m'] == 0]
    nearest = min(z, key=lambda r: z[r]['dist_to_hero_m'])
    lon360 = P0['lon_east'] % 360
    dtm_contains = (float(dtm['Minimum_latitude']) <= P0['lat'] <= float(dtm['Maximum_latitude'])
                    and float(dtm['Westernmost_longitude']) <= lon360 <= float(dtm['Easternmost_longitude']))
    res = {
        'hero_point': P0,
        'gsfc_sfs_regions': {'n_regions': len(z), 'regions_containing_p0': contains,
                             'nearest_region': nearest, 'nearest_distance_m': z[nearest]['dist_to_hero_m']},
        'lroc_nac_cdr_frames_footprint_intersecting_p0_box': {
            'n': cdr['n'], 'years': dict(sorted(years.items())),
            'incidence_deg_quantiles_0_10_50_90_100': np.quantile(inc, [0, .1, .5, .9, 1]).round(2).tolist(),
            'n_sun_elev_proxy_between_-1_and_3_deg': int(np.sum(((90 - inc) >= -1) & ((90 - inc) <= 3))),
            'note': 'incidence at frame centre, not at P0; footprint intersection per ODE polygons; raw frames need orthorectification'},
        'lroc_nac_dtm': {'product': dtm['Product_name'], 'producer': dtm['Producer_id'], 'resolution_m': dtm['Map_resolution'],
                         'bbox_contains_p0': bool(dtm_contains), 'label': dtm['LabelURL']},
        'status': 'hero point UNCHECKED: no orthorectified observation covers it; raw NAC frames and one NAC stereo DTM exist',
    }
    r6 = D / 'region6_nacmap_bounds.json'
    if r6.exists():
        rows = json.loads(r6.read_text())
        ok = [x for x in rows if x[1]]
        res['gsfc_region6_nac_maps'] = {'n': len(rows), 'n_read': len(ok), 'n_containing_p0': sum(1 for x in ok if x[2] is True),
                                       'max_right_edge_x_m': max(x[1][2] for x in ok) if ok else None}
    return res


README = """# L6 — Observation check at the hero point (Site04 RoI 3 lander point)

**Label:** PILOT · SOURCE-BASED · UNVALIDATED. **The hero point stays UNCHECKED.**

**Question.** Is there any observation that covers the Site04 RoI 3 lander point (−89.78012°, −156.32023° E) and its
controlling rise 15–17 m away?

**Method (metadata only — no pixels read).** (1) Zenodo doi:10.5281/zenodo.17954508 (GSFC SfS + orthorectified NAC maps,
13 Artemis regions): central directories listed by HTTP range reads; each region's `GLDELEV_005.tif` bounds read from the
GeoTIFF header via `/vsizip//vsicurl/`; region 6 (nearest) NAC map bounds likewise. (2) PDS ODE REST (live2), footprint
intersection with a ~90 m box around the point, for LROC NAC CDRs (`CDRNAC4`), NAC DTMs (`SDNDTM`) and ROI mosaics.
`python -m science.limits.l6_search` summarises the committed listings.

**Result.**
- None of the 13 GSFC SfS regions contains the point. Nearest: region 6 "Connecting Ridge", whose extent ends **322 m**
  short (x = −3000 m vs −2677.8 m). So the GSFC orthorectified NAC product used by NAC v1/v2 does not cover it.
- PDS ODE lists **234 LROC NAC calibrated frames** (2009–2024, mostly 2010) whose footprints intersect the point's box,
  most with incidence 87–93° (Sun near the horizon). They are raw; using them needs orthorectification onto an
  independent DEM (base protocol, qualifying observation 2).
- PDS ODE lists **one LROC NAC stereo DTM**, `NAC_DTM_ESALL_SR12` (ASU, 2 m/px, Shackleton rim ESA lander site), whose
  extent contains the point. It can test the rise's height relative to the point (amendment A1, test T).

**Protocol.** `tools/validation/hero/HERO_PROTOCOL.md` (frozen, SHA-256 81d12824…) and `HERO_PROTOCOL_A1.md` (frozen before
any pixel, 9ab36bcc…). No result yet: running them needs the DTM and frame downloads, held until the submission is
pushed. Results from region 6, regions 8/9 or other areas are **not** used as a stand-in for this point.

**What it does not show.** Footprint intersection is ODE's polygon test; a frame may still have the point in shadow,
saturated or off the usable edge. Incidence is at the frame centre.
"""


def main():
    res = {'item': 'L6_hero_observation', **summarise()}
    inputs = [D / 'zenodo_sfs_region_bounds.json', D / 'ode_cdrnac_p0.json', D / 'ode_nacdtm_p0.json',
              OUT_ROOT.parent.parent / 'tools' / 'validation' / 'hero' / 'HERO_PROTOCOL.md',
              OUT_ROOT.parent.parent / 'tools' / 'validation' / 'hero' / 'HERO_PROTOCOL_A1.md']
    if (D / 'region6_nacmap_bounds.json').exists():
        inputs.append(D / 'region6_nacmap_bounds.json')
    write_result('L6_hero_observation', res, inputs, README)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
