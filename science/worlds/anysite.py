"""Any-site solver for a world other than the Moon: the `world=` branch of `science.anysite.solve.solve`.

Same method as the Moon solver, every world-dependent number taken from the `World`:
  terrain (world.terrain_provider: near/far layers, each sampled in its own projection) -> site height -> curvature
  limit with the world's radius and relief bound (range extended to L_req where the terrain reaches) -> 720-bin skyline
  (science.worlds.skyline.layered_skyline = science.skyline.compute_skyline's algorithm, proven equal with the Moon's
  parameters) -> JPL Horizons Sun/Earth from the world's surface (world.horizons_params, frame tie, ellipsoid -> sphere
  az/el) -> hourly-sample metrics (science.anysite.solve.hourly_metrics, unchanged) -> flat-horizon control -> product
  members (alternative terrain, not probabilities) -> direct-to-Earth with the SEP outage rule -> bundle
  (polaris-science-results-v1 core keys + a `world` block).

The Moon never comes here: `science.anysite.solve.solve(world=None | 'moon')` runs the existing Moon code unchanged.
Labels: geometry SOURCE-BASED UNVALIDATED; requirements / comms threshold ENGINEERING ASSUMPTION.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

import numpy as np

from .. import bundle as B
from .. import crossings as X
from .. import horizons as H
from ..anysite import curvature
from ..anysite.solve import hourly_metrics
from . import ephem as WE
from .base import ENGINEERING, LABEL
from .skyline import Layer, layered_skyline

ROOT = Path(__file__).resolve().parents[2]
SOLVER_VERSION = 'world-anysite-1'
MAX_EXTENDED_RANGE_M = 600_000.0
BINS = 720


@dataclass
class TerrainSet:
    """What a world's terrain provider returns for a site: layers in priority order (first with data wins), ray steps,
    the near cut, how far the data reach (inscribed distance), and a provenance record per layer."""
    layers: List[Layer]
    step_near_m: float
    near_cut_m: float
    step_far_m: Optional[float]
    reach_m: float
    records: List[dict] = field(default_factory=list)
    beyond: Optional[Layer] = None
    note: str = ''

    def height(self, lat, lon):
        for L in self.layers:
            v = float(L.dem.sample(*L.forward(lat, lon)))
            if math.isfinite(v):
                return v, L.dem.name
        return float('nan'), None


def _stop(start, days):
    return (dt.datetime.fromisoformat(start) + dt.timedelta(days=days)).strftime('%Y-%m-%d %H:%M')


def skyline_for(world, ts: TerrainSet, lat, lon, h, mast_m, max_range_m):
    return layered_skyline(world.sphere, lat, lon, h, mast_m, ts.layers, bins=BINS, max_range_m=max_range_m,
                           step_near_m=ts.step_near_m, near_cut_m=min(ts.near_cut_m, max_range_m),
                           step_far_m=ts.step_far_m, beyond_reference=ts.beyond)


def curvature_record(world, h_eye, max_range, sky):
    e = np.array([np.nan if v is None else v for v in sky['elevation_deg']], float)
    ok = e[np.isfinite(e)]
    L_req = float(np.nanmax(curvature.limit_m(h_eye, ok, world.relief_max_m, world.radius_m))) if ok.size else float('nan')
    bound = float(curvature.elevation_deg(h_eye, world.relief_max_m, max_range, world.radius_m))
    return {'formula': 'theta_max(e) = acos((R + h_eye) cos e / (R + H)) - e ; L = R theta_max ; L_req = max over bins L(e_bin)',
            'R_m': world.radius_m, 'h_eye_m': round(h_eye, 3), 'H_world_max_m': world.relief_max_m,
            'relief_source': world.relief_source, 'required_range_world_m': round(L_req, 1), 'max_range_m': round(max_range, 1),
            'beyond_range_world_bound_elev_deg': round(bound, 5),
            'n_range_limited_world': int(sum(bool(np.isfinite(v) and v < bound) for v in e)),
            'note': 'Bins below beyond_range_world_bound_elev_deg could still be raised by terrain <= H_world_max_m beyond '
                    'max_range_m (world-wide bound; a conservative flag, not a detected obstruction).'}


def terrain_and_skyline(world, lat, lon, mast_m, member=None, provider=None):
    """(ts, h, sky, curv, max_range). Range: the e = 0 curvature limit, extended to L_req (all bins) where the data reach,
    capped at MAX_EXTENDED_RANGE_M."""
    provider = provider or world.terrain_provider
    if provider is None:
        raise LookupError(f'{world.name}: no terrain provider')
    probe = provider(lat, lon, 50_000.0, member)
    h, src = probe.height(lat, lon)
    if not math.isfinite(h):
        raise LookupError(f'{world.name}: no terrain height at ({lat}, {lon})')
    h_eye = h + mast_m
    base = float(curvature.limit_m(h_eye, 0.0, world.relief_max_m, world.radius_m))
    ts = provider(lat, lon, base, member)
    rng = min(base, ts.reach_m, MAX_EXTENDED_RANGE_M)
    sky = skyline_for(world, ts, lat, lon, h, mast_m, rng)
    curv = curvature_record(world, h_eye, rng, sky)
    curv['limit_e0_world_m'] = round(base, 1)
    L_req = curv['required_range_world_m']
    if math.isfinite(L_req) and L_req > rng + 1.0 and ts.reach_m > rng + 1.0 and rng < MAX_EXTENDED_RANGE_M:
        rng2 = min(L_req, ts.reach_m, MAX_EXTENDED_RANGE_M)
        ts = provider(lat, lon, rng2, member)
        sky = skyline_for(world, ts, lat, lon, h, mast_m, rng2)
        curv = curvature_record(world, h_eye, rng2, sky)
        curv.update({'limit_e0_world_m': round(base, 1), 'extended_from_m': round(rng, 1)})
        rng = rng2
    curv['footprint_reach_m'] = round(ts.reach_m, 1) if math.isfinite(ts.reach_m) else 'global'
    curv['capped_by'] = ('footprint' if rng >= ts.reach_m - 1.0 else 'max_extended_range' if rng >= MAX_EXTENDED_RANGE_M - 1.0
                         else 'L_req')
    return ts, h, sky, curv, rng


def _vis(rows, sky):
    out = []
    for r in rows:
        m = X.margins(r, sky)
        out.append(m is not None and m['margin_perp_deg'] > 0)
    return np.array(out)


def _longest(v, step_h):
    best = cur = 0
    for f in v:
        cur = 0 if f else cur + 1; best = max(best, cur)
    return best * step_h


def member_metrics(sky, rs, re_, step_h):
    sv, ev = _vis(rs, sky), _vis(re_, sky)
    return {'sun_center_visible_pct_hourly_samples': round(100 * sv.mean(), 3),
            'earth_center_visible_pct_hourly_samples': round(100 * ev.mean(), 3),
            'sun_and_earth_center_visible_pct_hourly_samples': round(100 * (sv & ev).mean(), 3),
            'longest_sun_center_hidden_h': float(_longest(sv, step_h))}, sv, ev


def solve(world, lat, lon, mast_m=1.0, start='2026-11-14 00:00', days=14, step_h=1, allow_network=True,
          members=(), horizons_lon_offset_deg=None, out_dir=None, use_cache=True, name=None, site_id=None, command=None,
          provider=None, write=True, extra=None):
    """Bundle for (lat, lon) on `world` (a World or its name). members: ids understood by the world's terrain provider
    (product members). Returns the bundle; `bundle['_context']` (not serialised) holds rows and skylines for callers that
    add world-specific sections (Mercury / Mars site scripts)."""
    if isinstance(world, str):
        from .registry import get_world
        world = get_world(world)
    if not world.available:
        raise LookupError(f'{world.name}: {world.availability_note}')
    t0 = time.time(); timing = {}
    lat = float(lat); lon = ((float(lon) + 180.0) % 360.0) - 180.0
    if not -90.0 <= lat <= 90.0:
        raise ValueError(f'latitude must be within [-90, 90] deg (got {lat})')
    out_dir = Path(out_dir or ROOT / 'data' / 'cache' / 'anysite' / 'worlds' / world.name)
    key = hashlib.sha256(json.dumps({'world': world.name, 'lat': round(lat, 7), 'lon': round(lon, 7), 'mast': mast_m,
                                     'start': start, 'days': days, 'step_h': step_h, 'members': sorted(members),
                                     'offset': horizons_lon_offset_deg, 'solver': SOLVER_VERSION},
                                    sort_keys=True).encode()).hexdigest()[:16]
    out_p = out_dir / f'{key}.json'
    if use_cache and write and out_p.exists() and extra is None:
        b = json.loads(out_p.read_text()); b['world']['cache_hit'] = True
        return b

    t = time.time()
    ts, h, sky, curv, rng = terrain_and_skyline(world, lat, lon, mast_m, None, provider)
    timing['skyline_s'] = round(time.time() - t, 2)
    stop = _stop(start, days)
    if horizons_lon_offset_deg is None:
        jd_mid = H.unix_to_jd((H.iso_to_unix(start.replace(' ', 'T') + ':00Z') + H.iso_to_unix(stop.replace(' ', 'T') + ':00Z')) / 2)
        horizons_lon_offset_deg = world.horizons_lon_offset_deg(jd_mid)
    t = time.time()
    rs, src_s = WE.site_series(world, 'sun', lat, lon, h, start, stop, f'{step_h} h', allow_network, horizons_lon_offset_deg)
    re_, src_e = WE.site_series(world, 'earth', lat, lon, h, start, stop, f'{step_h} h', allow_network, horizons_lon_offset_deg)
    timing['horizons_s'] = round(time.time() - t, 2)
    for rows in (rs, re_):
        for r in rows:
            r['radius_deg'], r['radius_source'] = B._radius_deg(r)
            r['m'] = X.margins(r, sky)
    met = hourly_metrics(rs, re_, step_h)
    flat = {'definition': 'Flat-horizon control: skyline 0 deg in every direction (no terrain), same Horizons samples',
            'sun_center_visible_pct': round(100 * float(np.mean([r['el_deg'] > 0 for r in rs])), 3),
            'earth_center_visible_pct': round(100 * float(np.mean([r['el_deg'] > 0 for r in re_])), 3),
            'sun_max_elevation_deg': round(max(r['el_deg'] for r in rs), 4),
            'earth_max_elevation_deg': round(max(r['el_deg'] for r in re_), 4)}

    t = time.time()
    mem = []
    for mid in members:
        try:
            tsm, hm, skm, cvm, _ = terrain_and_skyline(world, lat, lon, mast_m, mid, provider)
        except LookupError as exc:
            mem.append({'id': mid, 'status': 'not available', 'reason': str(exc)})
            continue
        mm, _, _ = member_metrics(skm, rs, re_, step_h)
        mem.append({'id': mid, 'kind': 'product', 'layers': [r.get('name') for r in tsm.records], 'ground_m': round(hm, 3),
                    'n_truncated': skm['n_truncated'], 'max_range_m': cvm['max_range_m'], 'metrics': mm})
    timing['members_s'] = round(time.time() - t, 2)
    ok = [m for m in mem if 'metrics' in m]
    unc = {'label_note': '"k of N maps is not a probability": members are alternative terrain products, not calibrated '
                         'probabilities.', 'members': mem,
           'summary': {k: {'min': min(m['metrics'][k] for m in ok), 'max': max(m['metrics'][k] for m in ok), 'n': len(ok)}
                       for k in ('sun_center_visible_pct_hourly_samples', 'sun_and_earth_center_visible_pct_hourly_samples')}
           if ok else {}}

    comms = dte(world, rs, re_, sky, start, stop, step_h, allow_network)
    timing['total_s'] = round(time.time() - t0, 2)
    b = assemble(world, lat, lon, mast_m, h, ts, sky, curv, rs, re_, met, flat, unc, comms, [src_s, src_e] + comms.pop('_src', []),
                 start, days, step_h, timing, name, site_id, command, horizons_lon_offset_deg, key)
    if extra:
        b['world'].update(extra)
    b['_context'] = {'rs': rs, 're': re_, 'sky': sky, 'ts': ts, 'h': h, 'range': rng}
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps({k: v for k, v in b.items() if k != '_context'}, separators=(',', ':'), allow_nan=False,
                                    default=_np))
    return b


def _np(o):
    if isinstance(o, np.generic):
        return o.item()
    raise TypeError(f'{type(o).__name__} is not JSON serializable')


def dte(world, rs, re_, sky, start, stop, step_h, allow_network):
    asset = next((c for c in world.comms if c.kind == 'direct-to-earth' and c.wired), None)
    relays = [{'id': c.id, 'status': 'not available for this world' if not c.wired else 'wired', 'description': c.description}
              for c in world.comms if c.kind == 'relay']
    if asset is None:
        return {'status': 'not available for this world', 'relays': relays}
    ev = _vis(re_, sky)
    out = {'asset': asset.id, 'label': asset.label, 'relays': relays,
           'definition': 'Earth centre above the terrain skyline (hourly sample) AND not in a superior-conjunction outage '
                         '(geocentric SEP < threshold)', 'earth_visible_pct': round(100 * float(ev.mean()), 3)}
    thr = asset.thresholds.get('sep_outage_x_band_deg')
    if thr is None:
        out['dte_available_pct'] = out['earth_visible_pct']
        out['conjunctions'] = 'no SEP rule for this world'
        return out
    from .mercury.physics import conjunctions
    sep_rows, src = WE.geocentric_sep(world, start, stop, f'{step_h} h', allow_network)
    if [r['utc'] for r in sep_rows] != [r['utc'] for r in re_]:
        raise ValueError('SEP grid differs from the site grid')
    conj = conjunctions(sep_rows, thr)
    outage = np.array(conj['outage_flags'])
    ok = ev & ~outage
    out.update({'dte_available_pct': round(100 * float(ok.mean()), 3), 'longest_dte_gap_h': float(_longest(ok, step_h)),
                'hours_lost_to_conjunction_while_earth_visible': int(np.sum(ev & outage)) * step_h,
                'conjunctions': {k: v for k, v in conj.items() if not k.endswith('_flags')},
                'threshold_source': asset.source,
                'not_modelled': 'DSN station elevation and scheduling, link budget, Sun-in-beam noise at inferior conjunction, '
                                'antenna pointing; any atmosphere effect on the link.', '_src': [src],
                '_outage_flags': outage})
    return out


def _sample(a, b):
    def one(r):
        m = r['m']
        base = {'az_deg': round(r['az_deg'], 6), 'el_deg': round(r['el_deg'], 6), 'radius_deg': round(r['radius_deg'], 6),
                'radius_source': r['radius_source'], 'range_au': r.get('range_au'), 'el_horizons_deg': r['el_horizons_deg']}
        if m is None:
            return {**base, 'horizon_deg': None, 'margin_deg': None, 'center_visible': False, 'disk_fraction': None,
                    'horizon_flag': 'unknown'}
        return {**base, 'horizon_deg': round(m['horizon_deg'], 5), 'margin_deg': round(m['margin_deg'], 5),
                'center_visible': m['margin_perp_deg'] > 0, 'disk_fraction': round(m['disk_fraction'], 5),
                'horizon_flag': m['horizon_flag']}
    return {'utc': a['utc'], 't_unix': a['t'], 'sun': one(a), 'earth': one(b)}


def assemble(world, lat, lon, mast_m, h, ts, sky, curv, rs, re_, met, flat, unc, comms, srcs, start, days, step_h, timing,
             name, site_id, command, lon_off, key):
    sid = site_id or f'{world.name}_{lat:+.4f}_{lon:+.4f}'
    sky_out = {k: sky[k] for k in sky if k != 'layers'}
    sky_out.update({'label': LABEL, 'curvature_limit': curv, 'dem_layers': ts.records, 'terrain_note': ts.note})
    hz = [{'role': role, **{k: s.get(k) for k in ('path', 'sha256', 'retrieved_utc', 'cache', 'params_key',
                                                   'center_site_header', 'horizons_lon_offset_deg')}}
          for role, s in zip(('sun-hourly', 'earth-hourly', 'geocentric-sep-hourly'), srcs)]
    comms.pop('_outage_flags', None)
    lims = ['Local geometric terrain visibility only; not certified illumination/power or DSN telecom availability.',
            f'Single ray per {360 / BINS:g} deg azimuth bin at the bin centre; sub-bin peaks can be missed.',
            'Hourly samples, no bisection refinement of crossings.',
            'Horizons az/el (ellipsoid normal) rotated to the sphere normal used by the skyline.',
            'Product members are alternative terrain products, not calibrated probabilities.',
            'Requirements copied from the Moon team as ENGINEERING ASSUMPTIONS unless the world states its own.']
    if world.atmosphere != 'none':
        lims.append('Atmosphere: Horizons APPARENT=AIRLESS (no refraction; see world.atmosphere_note for the estimate).')
    return {
        'schema': 'polaris-science-results-v1',
        'bundle_id': f"{sid}_{start[:10]}_{days:g}d_mast{mast_m:g}m",
        'generated_utc': H.unix_to_iso(time.time()),
        'generator': {'code': f'science/worlds/anysite.py ({SOLVER_VERSION})', 'git_commit': B._git(),
                      'command': command or f'python -m science.anysite.solve --world {world.name} --lat {lat} --lon {lon} '
                                            f'--mast {mast_m:g} --start "{start}" --days {days:g}', 'cache_key': key},
        'validation_status': {'overall': LABEL, 'checks': []},
        'site': {'id': sid, 'name': name or sid, 'lat_deg': lat, 'lon_deg_east': lon, 'height_m': round(h, 3),
                 'height_source': f'bilinear sample of {ts.height(lat, lon)[1]}', 'observer_mast_m': mast_m,
                 'observer_eye_height_m': round(h + mast_m, 3), 'coordinates_source': 'user input'},
        'frame': {'body': f'{world.name.capitalize()} (NAIF {world.naif_id})', 'body_fixed_frame': world.body_fixed_frame,
                  'latitude': 'planetocentric (deg)', 'longitude': 'east-positive (deg, -180..180)',
                  'horizons_longitude_offset_deg': lon_off,
                  'model_3d': f'P = (R + h) [cos lat cos lon, cos lat sin lon, sin lat], R = {world.radius_m:.0f} m',
                  'azimuth': 'degrees clockwise from LOCAL north (0 N, 90 E)',
                  'elevation': 'degrees above the plane normal to the site radius vector (sphere normal)'},
        'datum': {'reference_surface': 'sphere', 'radius_m': world.radius_m, 'heights': f'metres above the {world.radius_m:.0f} m '
                  'reference sphere', 'horizons_site': world.horizons_coord_type,
                  'horizons_center_radii_km': list(world.horizons_radii_km)},
        'time': {'scale': 'UTC', 'start_utc': H.unix_to_iso(rs[0]['t']), 'stop_utc': H.unix_to_iso(rs[-1]['t']), 'step_h': step_h,
                 'n_samples': len(rs), 'no_extrapolation': 'samples only at Horizons-evaluated times'},
        'skyline': sky_out,
        'samples': [_sample(a, b_) for a, b_ in zip(rs, re_)],
        'events': [],
        'metrics': met,
        'scenarios': [],
        'provenance': {'sources': [{'id': 'jpl-horizons', 'url': H.API,
                                    'description': f'JPL Horizons observer tables CENTER={world.horizons_center} '
                                                   f'({world.horizons_coord_type} site), QUANTITIES=4,13,20, APPARENT=AIRLESS'}]
                       + [{'id': r.get('product_id'), 'url': r.get('source_url'), 'sha256': r.get('file_sha256'),
                           'citation': r.get('citation')} for r in ts.records],
                       'horizons_raw': hz},
        'limitations': lims,
        'world': {**world.summary(), 'comms': comms, 'flat_horizon_control': flat, 'uncertainty': unc, 'timing_s': timing,
                  'sections': {
                      'decision_card': {'status': 'not available for this world',
                                        'reason': 'science.decision_card needs derived.arrival_slip with clone DEM members; '
                                                  'no clone DEMs exist for this world'},
                      'cube': {'status': 'not available for this world',
                               'reason': 'the 6D cube needs clone (T) members and mast/schedule grids'},
                      'sensitivity': {'status': 'not available for this world', 'reason': 'needs the cube'},
                      'validation': {'status': 'partial', 'see': 'validation_status'}}},
    }
