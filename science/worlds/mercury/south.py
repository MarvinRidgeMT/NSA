"""One Mercury SOUTH-polar site end to end (R6 open item), through the generic world solver (science/worlds/anysite.py).

  python -m science.worlds.mercury.south [--offline]

Site rule (fixed in docs/v2/PHASE_6_T3_PLAN.md §3 before the run): the PGDA 88 250 m pixel with the highest height among
pixels within 2 deg of the south pole (lat <= -88) whose PGDA 88 slope is < 15 deg; ties -> nearest the pole. Not chosen
by its Sun visibility. Window: one solar day (176 d = 2 Mercury years) from 2026-11-14, hourly; metrics also for the first
Mercury year. Terrain: PGDA 88 SfS 250 m to the 75 S edge, USGS 665 m beyond (curvature limit with relief +5.1 km).
Members: USGS 665 m alone, PGDA 88 gap-filled. Ice: PGDA 88 PSR mask (permanent shadow in the producer's illumination
model; not a radar-bright ice map: none is public for the south pole, R6).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

from ..anysite import member_metrics, solve as world_solve
from ..base import ENGINEERING, LABEL
from ..geometry import PolarStereo
from . import dem as MD
from . import terrain as T
from .world import MERCURY

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / 'data' / 'worlds' / 'mercury'
START = '2026-11-14 00:00'
DAYS = 176
YEAR_D = 88
MAST_M = 1.0
RULE = {'region': 'lat <= -88 (within 2 deg of the south pole)', 'max_slope_deg': 15.0,
        'pick': 'highest PGDA 88 height (unfilled DEM)', 'ties': 'nearest the pole',
        'fixed_before_run': '2026-11-17 (docs/v2/PHASE_6_T3_PLAN.md §3)'}
MEMBERS = ('usgs_665m', 'pgda88_filled')


def select_site():
    import rasterio
    with rasterio.open(MD.path(T.P88, T.P88_DEM)) as ds:
        Z = ds.read(1).astype(np.float64); t = ds.transform
    with rasterio.open(MD.path(T.P88, 'HSLP_75S250M_ref2439p4km.tif')) as ds:
        S = ds.read(1).astype(np.float64); S[S == ds.nodata] = np.nan
        if ds.transform != t or S.shape != Z.shape:
            raise ValueError('PGDA 88 DEM and slope grids differ')
    h, w = Z.shape
    xs = t.c + (np.arange(w) + 0.5) * t.a; ys = t.f - (np.arange(h) + 0.5) * t.a
    X, Y = np.meshgrid(xs, ys)
    lat, lon = PolarStereo(MERCURY.radius_m, 'south').inverse(X, Y)
    cand = (lat <= -88.0) & np.isfinite(Z) & np.isfinite(S) & (S < RULE['max_slope_deg'])
    score = np.where(cand, Z, -np.inf)
    best = score.max()
    ii = np.argwhere(score == best)
    k = ii[np.argmin(lat[ii[:, 0], ii[:, 1]])]          # ties: nearest the south pole = most negative latitude
    r, c = int(k[0]), int(k[1])
    return {'lat_deg': round(float(lat[r, c]), 7), 'lon_deg_east': round(float(lon[r, c]), 7), 'pixel_row_col': [r, c],
            'grid_x_m': float(xs[c]), 'grid_y_m': float(ys[r]), 'pgda88_height_m': round(float(Z[r, c]), 3),
            'pgda88_slope_deg': round(float(S[r, c]), 3), 'n_candidates': int(cand.sum()), 'rule': RULE}


def psr(site):
    import rasterio
    with rasterio.open(MD.path(T.P88, 'HDEM_75S250M_mask.tif')) as ds:
        M = ds.read(1); t = ds.transform; crs = ds.crs.to_dict()
    pr = PolarStereo(float(crs['R']), 'south')
    x, y = pr.forward(site['lat_deg'], site['lon_deg_east'])
    c = int((x - t.c) / t.a); r = int((t.f - y) / t.a)
    h, w = M.shape
    xs = t.c + (np.arange(w) + 0.5) * t.a; ys = t.f - (np.arange(h) + 0.5) * t.a
    ii = np.argwhere(M == 1)
    near = None
    if ii.size:
        dd = np.hypot(xs[ii[:, 1]] - x, ys[ii[:, 0]] - y); j = int(np.argmin(dd))
        la, lo = pr.inverse(xs[ii[j, 1]], ys[ii[j, 0]])
        near = {'grid_distance_km': round(float(dd[j]) / 1000, 3), 'lat_deg': round(float(la), 5), 'lon_deg_east': round(float(lo), 5)}
    return {'layer': 'PGDA 88 HDEM_75S250M_mask.tif (PSR mask, 1 = permanently shadowed in the producer\'s model; grid on '
                     f'+R={crs["R"]:.0f})', 'value_at_site': int(M[r, c]) if 0 <= r < h and 0 <= c < w else None,
            'nearest_psr_pixel': near, 'psr_fraction_of_mask_grid': round(float((M == 1).mean()), 5),
            'label': 'SOURCE-BASED (published layer); a PSR is a cold-trap candidate, not detected ice',
            'radar_bright_layer': 'not available (no public georeferenced south-polar radar map; R6 search)'}


def build(allow_network=True, out_dir=OUT_DIR, command=None):
    site = select_site()
    lat, lon = site['lat_deg'], site['lon_deg_east']
    b = world_solve('mercury', lat, lon, MAST_M, START, DAYS, 1, allow_network, members=MEMBERS, write=False,
                    name='Mercury south pole, rule-selected high point (PGDA 88)', site_id='mercury_south_pole_high',
                    command=command or 'python -m science.worlds.mercury.south')
    ctx = b.pop('_context')
    rs, re_, sky = ctx['rs'], ctx['re'], ctx['sky']
    n_year = YEAR_D * 24 + 1
    y1, _, _ = member_metrics(sky, rs[:n_year], re_[:n_year], 1)
    flat_y1 = {'sun_center_visible_pct': round(100 * float(np.mean([r['el_deg'] > 0 for r in rs[:n_year]])), 3),
               'earth_center_visible_pct': round(100 * float(np.mean([r['el_deg'] > 0 for r in re_[:n_year]])), 3)}
    sweep = []
    from ..anysite import terrain_and_skyline
    for mast in (1.0, 10.0, 50.0, 100.0):
        _, _, skm, _, _ = terrain_and_skyline(MERCURY, lat, lon, mast)
        mm, _, _ = member_metrics(skm, rs, re_, 1)
        sweep.append({'mast_m': mast, 'solar_day': mm})
    b['site'].update({'selection': site, 'coordinates_source': f'rule-selected; {LABEL}'})
    b['metrics']['window_label'] = 'one solar day (176 d = 2 Mercury years)'
    b['metrics']['mercury_year_1'] = y1
    b['world'].update({'flat_horizon_control_mercury_year_1': flat_y1, 'mast_sweep': sweep, 'ice': psr(site),
                       'requirements_check': [
                           {'requirement': rid, 'threshold': thr, 'nominal': b['metrics'][key], 'pass': b['metrics'][key] >= thr,
                            'threshold_source': MERCURY.default_requirements[rid]}
                           for rid, key, thr in (('sun_center_pct_ge_70', 'sun_center_visible_pct', 70),
                                                 ('both_center_pct_ge_40', 'sun_and_earth_center_visible_pct', 40))]})
    b['validation_status']['checks'] = [
        {'id': 'generic-world-path-reproduces-prokofiev', 'status': 'pass',
         'evidence': 'science/worlds/tests/test_world_anysite.py (skyline and metrics = the R6 bundle)'},
        {'id': 'pgda88-orientation-datum-vs-usgs', 'status': 'pass', 'evidence': 'science/worlds/tests/test_mercury_south.py'},
        {'id': 'mla-horizons-prime-meridian-tie', 'status': 'pass', 'evidence': 'science/worlds/tests/test_frame_tie.py'},
        {'id': 'independent-illumination-comparison', 'status': 'not-run',
         'evidence': 'PGDA 88 publishes a PSR mask, not a Sun-visibility series'}]
    b['limitations'] += ['PGDA 88 SfS DEM 250 m: shape-from-shading on MDIS NAC images adjusted to MLA; its own accuracy '
                         'statement is in the Zenodo record (not re-derived here).',
                         'The site is a rule-selected high point, not a surveyed landing site.']
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{b['bundle_id']}.json"
    from ..anysite import _np
    p.write_text(json.dumps(b, separators=(',', ':'), allow_nan=False, default=_np))
    return b, p


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--offline', action='store_true')
    a = ap.parse_args(argv)
    b, p = build(not a.offline, command='python -m science.worlds.mercury.south ' + ' '.join(argv or sys.argv[1:]))
    m = b['metrics']; w = b['world']
    print(json.dumps({'bundle': str(p), 'site': {k: b['site'][k] for k in ('lat_deg', 'lon_deg_east', 'height_m')},
                      'sun_pct': m['sun_center_visible_pct'], 'earth_pct': m['earth_center_visible_pct'],
                      'sun_earth_pct': m['sun_and_earth_center_visible_pct'], 'gap_h': m['longest_sun_center_hidden_h'],
                      'year1': m['mercury_year_1'], 'flat': w['flat_horizon_control'], 'dte': w['comms'].get('dte_available_pct'),
                      'members': w['uncertainty']['summary'], 'sweep': w['mast_sweep'], 'ice': w['ice'],
                      'range': b['skyline']['curvature_limit'], 'n_trunc': b['skyline']['n_truncated'],
                      'timing': w['timing_s']}, indent=1, default=str))


if __name__ == '__main__':
    main()
