"""Build a polaris-science-results-v1 for one site / window.

  python3 -m science.bundle --site site01 --start "2026-11-14 00:00" --days 14 --step-h 1 \
      --mast 2 --out data/bundles/site01_2026-11-14_14d.json --fixture data/bundles/fixtures/site01_ui_fixture_50.json

Everything numeric here derives from: LOLA LDEM 80 m (product 90), LOLA 5 m site tile
(product 78), and JPL Horizons responses archived under data/raw/horizons/.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np

from . import crossings as X
from . import frames
from . import horizons as H
from . import sites
from .skyline import compute_skyline

ROOT = Path(__file__).resolve().parents[1]
LABEL = 'SOURCE-BASED UNVALIDATED'
BODIES = {'sun': '10', 'earth': '399'}


def _git():
    try:
        rev = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain', '--', 'science'], cwd=ROOT, text=True).strip())
        return rev + ('-dirty' if dirty else '')
    except Exception:
        return 'unknown'


def _radius_deg(row):
    if row.get('ang_diam_arcsec'):
        return row['ang_diam_arcsec'] / 3600.0 / 2.0, 'horizons-ang-diam'
    return X.SUN_RADIUS_FALLBACK_DEG, 'fallback-0.2666deg'


def site_setup(site_id, mast_m, near=None, far=None):
    s = sites.SITES[site_id]
    far = far or sites.far_dem(site_id)
    near = near or sites.near_dem(site_id)
    x, y = frames.stereo_forward(s['lat'], s['lon'])
    h_near = float(near.sample(x, y)); h_far = float(far.sample(x, y))
    return s, near, far, x, y, h_near, h_far


def body_series(site_id, s, h_m, body, start, stop, step_h, sky, tag_suffix=''):
    tag = f'{site_id}_{body}_{start[:10].replace("-", "")}_{tag_suffix or "main"}'
    rows, src = H.ephemeris(BODIES[body], s['lat'], s['lon'], h_m, start, stop, f'{step_h} h', tag)
    for r in rows:
        r['radius_deg'], r['radius_source'] = _radius_deg(r)
        r['m'] = X.margins(r, sky)
    return rows, src


def refine_events(site_id, s, h_m, body, rows, sky, tol_s=0.5, tag_suffix=''):
    """Bisection on real Horizons evaluations for centre and both limbs."""
    events, raws = [], []
    for kind in ('center', 'upper_limb', 'lower_limb'):
        br = []
        for a, b in zip(rows[:-1], rows[1:]):
            if a['m'] is None or b['m'] is None:
                continue
            ga, gb = a['m']['g'][kind], b['m']['g'][kind]
            if (ga > 0) != (gb > 0):
                br.append((a['t'], b['t'], ga))
        if not br:
            continue
        it_box = {'k': 0}

        def f_batch(ts, kind=kind):
            it_box['k'] += 1
            rr, src = H.ephemeris_at(BODIES[body], s['lat'], s['lon'], h_m, ts,
                                     f'{site_id}_{body}_{kind}_bisect{tag_suffix}_it{it_box["k"]:02d}')
            raws.append(src)
            out = []
            for r in rr:
                r['radius_deg'], _ = _radius_deg(r)
                m = X.margins(r, sky)
                out.append(None if m is None else m['g'][kind])
            return out
        res, iters = X.bisect_many(f_batch, br, tol_s=tol_s)
        for (t, width), b in zip(res, br):
            rising = b[2] < 0
            label = {'center': ('center_rise', 'center_set'),
                     'upper_limb': ('first_light', 'last_light'),
                     'lower_limb': ('fully_visible', 'begins_occultation')}[kind][0 if rising else 1]
            # horizon flag at the crossing azimuth (from the nearest bracketing sample)
            near_row = min(rows, key=lambda r: abs(r['t'] - t))
            events.append({'body': body, 'kind': kind, 'event': label, 'direction': 'rise' if rising else 'set',
                           'utc': H.unix_to_iso(t), 't_unix': round(t, 3),
                           'bracket_width_s': round(width, 3), 'iterations': iters,
                           'horizon_flag': near_row['m']['horizon_flag'], 'label': LABEL})
    events.sort(key=lambda e: e['t_unix'])
    return events, raws


def visibility_intervals(rows, events, body, kind='center'):
    """Visible intervals of the body's centre/limb using refined crossing times."""
    t0, t1 = rows[0]['t'], rows[-1]['t']
    ev = [e for e in events if e['body'] == body and e['kind'] == kind]
    vis = rows[0]['m']['g'][kind] > 0
    cur = t0; out = []
    for e in ev:
        if vis:
            out.append((cur, e['t_unix']))
        vis = e['direction'] == 'rise'; cur = e['t_unix']
    if vis:
        out.append((cur, t1))
    return out


def _complement(iv, t0, t1):
    gaps, cur = [], t0
    for a, b in iv:
        if a > cur:
            gaps.append((cur, a))
        cur = max(cur, b)
    if cur < t1:
        gaps.append((cur, t1))
    return gaps


def _intersect(a, b):
    out = []
    for x0, x1 in a:
        for y0, y1 in b:
            lo, hi = max(x0, y0), min(x1, y1)
            if hi > lo:
                out.append((lo, hi))
    return out


def metrics(rows_sun, rows_earth, events):
    t0, t1 = rows_sun[0]['t'], rows_sun[-1]['t']
    span = t1 - t0
    sv = visibility_intervals(rows_sun, events, 'sun')
    ev = visibility_intervals(rows_earth, events, 'earth')
    both = _intersect(sv, ev)
    dur = lambda iv: sum(b - a for a, b in iv)
    longest = lambda iv: max([b - a for a, b in iv], default=0.0)
    trap = lambda rows, key: float(np.trapezoid([r['m'][key] for r in rows], [r['t'] for r in rows]) / span)
    return {
        'label': LABEL,
        'window_utc': [H.unix_to_iso(t0), H.unix_to_iso(t1)],
        'sun_center_visible_pct': round(100 * dur(sv) / span, 3),
        'earth_center_visible_pct': round(100 * dur(ev) / span, 3),
        'sun_and_earth_center_visible_pct': round(100 * dur(both) / span, 3),
        'longest_sun_center_hidden_h': round(longest(_complement(sv, t0, t1)) / 3600, 4),
        'longest_earth_center_hidden_h': round(longest(_complement(ev, t0, t1)) / 3600, 4),
        'sun_disk_mean_visible_fraction': round(trap(rows_sun, 'disk_fraction'), 5),
        'earth_disk_mean_visible_fraction': round(trap(rows_earth, 'disk_fraction'), 5),
        'min_sun_margin_deg': round(min(r['m']['margin_deg'] for r in rows_sun), 5),
        'min_earth_margin_deg': round(min(r['m']['margin_deg'] for r in rows_earth), 5),
        'max_earth_margin_deg': round(max(r['m']['margin_deg'] for r in rows_earth), 5),
        # Fraction of the hourly Horizons samples with the centre above the skyline (includes both window
        # endpoints). This is the definition used by the standalone polaris_batch package, kept for comparison.
        'sun_center_visible_pct_hourly_samples': round(100 * np.mean([r['m']['margin_perp_deg'] > 0 for r in rows_sun]), 3),
        'earth_center_visible_pct_hourly_samples': round(100 * np.mean([r['m']['margin_perp_deg'] > 0 for r in rows_earth]), 3),
        'sun_and_earth_center_visible_pct_hourly_samples': round(100 * np.mean(
            [a['m']['margin_perp_deg'] > 0 and b['m']['margin_perp_deg'] > 0 for a, b in zip(rows_sun, rows_earth)]), 3),
        'method': {'visible_pct': 'centre-visibility intervals bounded by bisection-refined crossings (+-0.5 s) over the window',
                   'visible_pct_hourly_samples': 'share of hourly samples (both endpoints included) with centre above skyline',
                   'disk_mean': 'trapezoid over hourly Horizons samples of the visible-disk fraction',
                   'margins': 'el - skyline(az) at hourly samples'},
        'disclaimer': 'Local geometric visibility only: not certified illumination, power, or DSN link availability.',
    }


def sample_record(rs, re_):
    def b(r):
        m = r['m']
        return {'az_deg': r['az_deg'], 'el_deg': r['el_deg'], 'radius_deg': round(r['radius_deg'], 6),
                'radius_source': r['radius_source'], 'range_au': r.get('range_au'),
                'horizon_deg': round(m['horizon_deg'], 5), 'margin_deg': round(m['margin_deg'], 5),
                'center_visible': m['margin_perp_deg'] > 0, 'disk_fraction': round(m['disk_fraction'], 5),
                'horizon_flag': m['horizon_flag']}
    assert rs['utc'] == re_['utc']
    return {'utc': rs['utc'], 't_unix': rs['t'], 'sun': b(rs), 'earth': b(re_)}


def build(site_id, start, days, step_h, mast_m, near=None, far=None, events_on=True, tag_suffix='',
          h_override=None, lat_lon_override=None, skyline_override=None):
    s, near, far, x, y, h_near, h_far = site_setup(site_id, mast_m, near, far)
    s = dict(s)
    if sites.SITES[site_id].get('roi') is not None:
        # Raw-file tags must be unique per mast: bisection times depend on the skyline, so
        # a run at another mast would otherwise overwrite this run's archived responses.
        tag_suffix = f'm{mast_m:g}' + (f'_{tag_suffix}' if tag_suffix else '')
    if lat_lon_override:
        s['lat'], s['lon'] = lat_lon_override
        x, y = frames.stereo_forward(s['lat'], s['lon'])
        h_near = float(near.sample(x, y)); h_far = float(far.sample(x, y))
    h = h_override if h_override is not None else h_near
    step = sites.NEAR_RAY_STEP_M if sites.SITES[site_id].get('roi') is not None else None  # tile-centre bundles unchanged
    sky = skyline_override or compute_skyline(s['lat'], s['lon'], h, mast_m, near=near, far=far, bins=720,
                                              max_range_m=sites.MAX_RANGE_M, step_m=step)
    stop = (dt.datetime.fromisoformat(start) + dt.timedelta(days=days)).strftime('%Y-%m-%d %H:%M')
    rs, src_s = body_series(site_id, s, h, 'sun', start, stop, step_h, sky, tag_suffix)
    re_, src_e = body_series(site_id, s, h, 'earth', start, stop, step_h, sky, tag_suffix)
    events, raws = [], []
    if events_on:
        for body, rows in (('sun', rs), ('earth', re_)):
            e, r = refine_events(site_id, s, h, body, rows, sky, tag_suffix=tag_suffix)
            events += e; raws += r
        events.sort(key=lambda e: e['t_unix'])
    met = metrics(rs, re_, events)
    return {'s': s, 'x': x, 'y': y, 'h': h, 'h_near': h_near, 'h_far': h_far, 'sky': sky, 'rows_sun': rs,
            'rows_earth': re_, 'events': events, 'metrics': met, 'src': [src_s, src_e], 'raws': raws,
            'near': near, 'far': far, 'stop': stop}


def assemble(site_id, r, start, days, step_h, mast_m, command, scenarios=None):
    s, sky, near, far = r['s'], r['sky'], r['near'], r['far']
    sky_out = {k: sky[k] for k in ('bins', 'azimuth_deg', 'elevation_deg', 'status', 'range_limited', 'valid_reach_m',
                                   'critical', 'n_truncated', 'n_range_limited', 'max_range_m', 'near_cut_m',
                                   'step_near_m', 'step_far_m', 'n_samples_per_bin',
                                   'beyond_range_max_possible_elev_deg', 'beyond_range_reference_height_m',
                                   'flat_baseline', 'method')}
    sky_out['label'] = LABEL
    sky_out['dem_layers'] = [
        {'role': 'near', 'name': near.name, 'step_m': near.step, 'bounds_grid_m': list(near.bounds),
         'source_url': near.meta.get('source_url'), 'file_sha256': near.meta.get('file_sha256'),
         'array_sha256': near.digest()},
        {'role': 'far', 'name': far.name, 'step_m': far.step, 'bounds_grid_m': list(far.bounds),
         'source_url': far.meta.get('source_url'), 'transport': far.meta.get('transport'),
         'file_sha256': far.meta.get('file_sha256'), 'array_sha256': far.digest()}]
    man = {m['path']: m for m in json.loads((H.RAW_DIR / 'MANIFEST.json').read_text())}
    hraw = [dict(role=f'{b}-hourly', **_m(man, src['path'])) for b, src in zip(('sun', 'earth'), r['src'])]
    hraw += [dict(role='bisection', **_m(man, src['path'])) for src in r['raws']]
    from . import frame_tie
    bundle = {
        'schema': 'polaris-science-results-v1',
        'bundle_id': f'{site_id}_{start[:10]}_{days}d' + (f'_mast{mast_m:g}m' if s.get('roi') is not None else ''),
        'generated_utc': H.unix_to_iso(dt.datetime.now(dt.timezone.utc).timestamp()),
        'generator': {'code': 'science/ (POLARIS X a-science)', 'git_commit': _git(), 'command': command},
        'validation_status': validation_status(site_check(site_id, r)),
        'site': {'id': site_id, 'name': s['name'], 'lat_deg': s['lat'], 'lon_deg_east': s['lon'],
                 'height_m': round(r['h'], 3), 'height_source': 'bilinear sample of near-field DEM (product 78, 5 m) at site',
                 'height_far_dem_m': round(r['h_far'], 3), 'observer_mast_m': mast_m,
                 'observer_eye_height_m': round(r['h'] + mast_m, 3),
                 'grid_x_m': round(r['x'], 3), 'grid_y_m': round(r['y'], 3),
                 'slope_deg_5m_50m_baseline': round(site_slope(near, r['x'], r['y']), 3),
                 'coordinates_source': s.get('coordinates_source',
                                              'archived app SITES table (Mazarico et al. 2011 numbering); product-78 tile centre') + '; ' + LABEL},
        'frame': FRAME,
        'datum': {'reference_surface': 'sphere', 'radius_m': frames.R_MOON_M,
                  'heights': 'metres above the 1737.4 km reference sphere (LOLA LDEM convention)',
                  'horizons_site_alt_km': round(r['h'] / 1000, 6),
                  'horizons_center_radii_km': [1737.4, 1737.4, 1737.4]},
        'time': {'scale': 'UTC', 'start_utc': H.unix_to_iso(r['rows_sun'][0]['t']), 'stop_utc': H.unix_to_iso(r['rows_sun'][-1]['t']),
                 'step_h': step_h, 'n_samples': len(r['rows_sun']),
                 'no_extrapolation': 'samples and events are only at Horizons-evaluated times'},
        'skyline': sky_out,
        'samples': [sample_record(a, b) for a, b in zip(r['rows_sun'], r['rows_earth'])],
        'events': r['events'],
        'metrics': r['metrics'],
        'scenarios': scenarios or [],
        'provenance': {'sources': SOURCES + [
            {'id': 'p78-site', 'description': f'LOLA {site_id} 5 m LDEM (Barker et al. 2021), PGDA product 78',
             'url': near.meta.get('source_url'), 'sha256': near.meta.get('file_sha256')}],
            'horizons_raw': hraw},
        'limitations': LIMITATIONS,
    }
    if s.get('roi') is not None:  # ROI bundles carry the frame-tie bound computed from their own samples/events
        rep = frame_tie.check_bundle(bundle)
        for c in bundle['validation_status']['checks']:
            if c['id'] == 'me-frame-tie-de421-vs-horizons':
                c['status'], c['evidence'] = rep['status'], frame_tie.evidence(rep)
        bundle['frame']['body_fixed_frame'] = ('DEMs: MOON_ME (DE421) per PGDA README; Horizons: MEAN_ME high precision (DE441). '
                                               'Offset not applied; bounded by science/frame_tie.py (see validation_status).')
    return bundle


def _m(man, path):
    m = man[path]
    return {'path': path, 'sha256': m['sha256'], 'retrieved_utc': m['retrieved_utc']}


FRAME = {
    'body': 'Moon (NAIF 301)',
    'body_fixed_frame': 'DEMs: MOON_ME (DE421) per PGDA README; Horizons: MEAN_ME high precision. '
                        'DE421-ME vs DE44x-ME offset not applied: SOURCE-BASED UNVALIDATED.',
    'latitude': 'planetocentric (deg)', 'longitude': 'east-positive (deg, -180..180)',
    'grid_crs': '+proj=stere +lat_0=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +R=1737400 +units=m (read from LDEM COG header)',
    'grid_to_local': 'at longitude L: local north = (sin L, cos L), local east = (cos L, -sin L) in grid (x, y); grid_az = local_az + L',
    'local_enu': 'e = d/dlon, n = d/dlat, u = radial unit vector of the site',
    'azimuth': 'degrees clockwise from LOCAL north (0 N, 90 E); identical to JPL Horizons surface-observer azimuth',
    'elevation': 'degrees above the plane normal to the site radius vector; airless (no refraction)',
    'model_3d': 'P = (R + h) * [cos lat cos lon, cos lat sin lon, sin lat]; el = asin((P - P_obs).u / |P - P_obs|)',
}

SOURCES = [
    {'id': 'ldem-80m', 'description': 'LOLA LDEM_80S_80MPP_ADJ.TIF, 80 m/px south-polar mosaic, PGDA product 90',
     'url': frames.LDEM_URL, 'sha256': sites.LDEM_SHA256},
    {'id': 'jpl-horizons', 'description': 'JPL Horizons API, observer tables, CENTER=coord@301, QUANTITIES=4,13,20, APPARENT=AIRLESS',
     'url': H.API},
]

LIMITATIONS = [
    'Local geometric terrain visibility only; not certified illumination/power or DSN telecom availability.',
    'Single ray per 0.5 deg azimuth bin at the bin centre; sub-bin peaks can be missed.',
    'Near field 5 m to the inscribed radius of the product-78 tile, far field 80 m to max_range_m; DEM interpolation is bilinear.',
    'Skyline bins with status "truncated" are lower bounds; "range_limited" bins could be raised by terrain beyond max_range_m.',
    'Visible-disk fraction treats the local skyline as a straight line across the disk (slope from adjacent bins); no limb darkening.',
    'Horizons observer altitude uses DEM height without the mast (sub-mm parallax effect).',
    'DE421 MOON_ME (DEM) vs Horizons MEAN_ME (DE441) frame offset is not applied; ROI bundles bound its effect '
    '(<= 1.8e-5 deg, ~0.53 m, NAIF moon_de440_220930.tf) in validation_status.',
    'Tile-centre bundles (site01, site04) use archived app coordinates; ROI bundles use product-78 ROI centroids, '
    'and a centroid is a single representative point of a polygon, not a surveyed landing point.',
]


def site_slope(near, x, y, d=25.0):
    gx = (near.sample(x + d, y) - near.sample(x - d, y)) / (2 * d)
    gy = (near.sample(x, y + d) - near.sample(x, y - d)) / (2 * d)
    return float(np.degrees(np.arctan(np.hypot(gx, gy))))


def site_check(site_id, r):
    near = r['near']; l, b, rr, t = near.bounds
    cx, cy = (l + rr) / 2, (b + t) / 2
    off = math.hypot(r['x'] - cx, r['y'] - cy)
    slope = site_slope(near, r['x'], r['y'])
    ev = (f'Site coordinate is {off:.1f} m from the centre of the product-78 tile ({cx:.0f}, {cy:.0f}) m: the archived '
          f'app appears to use tile centres as sites. Local slope at the point (5 m DEM, 50 m baseline) = {slope:.1f} deg.')
    roi = sites.SITES[site_id].get('roi')
    if roi is not None:
        ev = (f'Site is the published product-78 ROI{roi} centroid ({sites.ROI_SOURCE}), {off:.1f} m from the tile '
              f'centre. Local slope at the point (5 m DEM, 50 m baseline) = {slope:.1f} deg.')
        return {'id': 'site-coordinate-source', 'status': 'fail' if slope > 15.0 else 'pass', 'evidence': ev}
    status = 'fail' if slope > 15.0 else 'not-run'
    if status == 'fail':
        ev += ' Slope > 15 deg: this point is not a plausible landing site; results describe the tile centre only.'
    return {'id': 'site-coordinate-source', 'status': status, 'evidence': ev}


def validation_status(site_chk=None):
    return {'overall': LABEL,
            'checks': [
                {'id': 'grid-enu-rotation', 'status': 'pass', 'evidence': 'science/tests/test_frames.py GridEnuRotation, RidgeRegression'},
                {'id': 'crs-roundtrip-1mm', 'status': 'pass', 'evidence': 'science/tests/test_frames.py CogRoundTrip (pyproj, COG CRS)'},
                {'id': 'horizons-parse-by-header', 'status': 'pass', 'evidence': 'science/tests/test_horizons.py ParseByHeader'},
                {'id': 'raw-archive-sha256', 'status': 'pass', 'evidence': 'science/tests/test_horizons.py ArchivedRaw'},
                {'id': 'ldem-vsicurl-vs-wholefile', 'status': 'pass', 'evidence': '4125x4125 window bit-identical (BUILD_STATUS T2)'},
                {'id': 'independent-illumination-comparison', 'status': 'not-run',
                 'evidence': 'No comparison yet against published Site01/Site04 illumination (e.g. Barker et al. 2021, Mazarico et al. 2011).'},
                {'id': 'me-frame-tie-de421-vs-horizons', 'status': 'not-run', 'evidence': ''},
            ] + ([site_chk] if site_chk else [{'id': 'site-coordinate-source', 'status': 'not-run', 'evidence': ''}])}


def fixture_from(bundle, n=50):
    idx = sorted(set(int(round(i)) for i in np.linspace(0, len(bundle['samples']) - 1, n)))
    f = dict(bundle)
    f['bundle_id'] = bundle['bundle_id'] + f'_fixture{len(idx)}'
    f['samples'] = [bundle['samples'][i] for i in idx]
    f['fixture'] = {'of_bundle': bundle['bundle_id'], 'sample_indices': idx,
                    'note': 'UI fixture: evenly spaced subset of the real bundle samples (irregular step). '
                            'Skyline, events, metrics are copied unchanged from the full bundle.'}
    return f


def main(argv=None):
    import sys
    p = argparse.ArgumentParser()
    p.add_argument('--site', default='site01', choices=list(sites.SITES))
    p.add_argument('--start', default='2026-11-14 00:00')
    p.add_argument('--days', type=int, default=14)
    p.add_argument('--step-h', type=int, default=1)
    p.add_argument('--mast', type=float, default=2.0)
    p.add_argument('--out', required=True)
    p.add_argument('--fixture')
    p.add_argument('--scenarios', action='store_true')
    a = p.parse_args(argv)
    cmd = 'python3 -m science.bundle ' + ' '.join(argv if argv is not None else sys.argv[1:])
    r = build(a.site, a.start, a.days, a.step_h, a.mast)
    scen = []
    if a.scenarios:
        from .scenarios import run_all
        scen = run_all(a.site, r, a.start, a.days, a.step_h, a.mast)
    b = assemble(a.site, r, a.start, a.days, a.step_h, a.mast, cmd, scen)
    out = ROOT / a.out; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(b, indent=1))
    print('wrote', out, hashlib.sha256(out.read_bytes()).hexdigest())
    if a.fixture:
        fx = ROOT / a.fixture; fx.parent.mkdir(parents=True, exist_ok=True)
        fx.write_text(json.dumps(fixture_from(b), indent=1))
        print('wrote', fx, hashlib.sha256(fx.read_bytes()).hexdigest())
    print(json.dumps(b['metrics'], indent=1))
    print('events:', len(b['events']))


if __name__ == '__main__':
    main()
