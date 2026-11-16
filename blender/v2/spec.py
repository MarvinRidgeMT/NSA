"""Scene specification for blender/v2/build_scene.py: every number the Blender scene uses, resolved in pure Python from a
solver bundle (polaris-science-results-v1) and published constants. JSON-serialisable; unit-tested in test_spec.py.

The Blender script only turns this spec into objects. It never computes a direction, a size, a state or a metric.
"""
from __future__ import annotations

import glob
import hashlib
import json
import math
from pathlib import Path

from . import astro, cameras, hapke

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = 'polaris-blender-scene-spec-v1'
SITE_MATCH_TOLERANCE_M = 50.0

# Mirror of science/cube/build_assets.py LAYOUTS (grid metres from the bundle site; checked equal by test_spec.py).
# ILLUSTRATIVE shapes: cylinders, not a lander design.
ASSET_BODY = {'name': 'lander body', 'xy': (0.0, 0.0), 'r': 2.0, 'top': 4.0}
ASSET_LAYOUTS = {
    'single': {'array': ((0, 0), 1.0), 'antenna': ((0, 0), 1.0), 'bodies': []},
    'research': {'array': ((0, 0), 4.5), 'antenna': ((0, 5), 2.0), 'bodies': [ASSET_BODY]},
    'bad': {'array': ((0, 5), 1.0), 'antenna': ((0, -5), 2.0), 'bodies': [ASSET_BODY]},
    'tower': {'array': ((0, 10), 15.0), 'antenna': ((0, 10), 15.0),
              'bodies': [ASSET_BODY, {'name': 'tower', 'xy': (0.0, 10.0), 'r': 0.3, 'top': 15.0}]},
}

DEFAULT_ALTITUDE_M = {'lroc_nac': 50_000.0, 'lroc_wac': 50_000.0, 'shadowcam': 100_000.0, 'kaguya_tc': 100_000.0}


class SpecError(ValueError):
    pass


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def find_bundle(lat, lon, mast=None, bundles_glob=None):
    """Solver bundle whose site is within SITE_MATCH_TOLERANCE_M of (lat, lon) (grid distance). Prefers `mast` (m) when
    several bundles share the site, else the lowest mast. Fails with a clear message otherwise (any-site solving is S4's)."""
    from .terrain import stereo_forward
    x, y = stereo_forward(lat, lon)
    found = []
    for f in sorted(glob.glob(bundles_glob or str(ROOT / 'data' / 'bundles' / '*.json'))):
        try:
            b = json.loads(Path(f).read_text())
        except Exception:
            continue
        if b.get('schema') != 'polaris-science-results-v1':
            continue
        s = b['site']
        bx, by = stereo_forward(s['lat_deg'], s['lon_deg_east'])
        d = math.hypot(bx - x, by - y)
        if d <= SITE_MATCH_TOLERANCE_M:
            found.append((d, s.get('observer_mast_m', 0.0), f))
    if not found:
        raise SpecError(f'no solver bundle within {SITE_MATCH_TOLERANCE_M} m of ({lat}, {lon}). Run the any-site solver '
                        '(science/anysite, S4) for this point first; the scene builder never invents Sun/Earth geometry.')
    if mast is not None:
        m = [t for t in found if abs(t[1] - mast) < 1e-6]
        if not m:
            raise SpecError(f'bundles at this site have masts {sorted(t[1] for t in found)}, not {mast}')
        found = m
    found.sort(key=lambda t: (t[1], t[0]))
    return found[0][2], found[0][0]


def _body(s, key):
    b = s[key]
    return {'azDeg': b['az_deg'], 'elDeg': b['el_deg'], 'radiusDeg': b['radius_deg'], 'radiusSource': b.get('radius_source'),
            'rangeAu': b['range_au'], 'horizonDeg': b.get('horizon_deg'), 'marginDeg': b.get('margin_deg'),
            'centreVisible': b.get('center_visible'), 'discFraction': b.get('disk_fraction'), 'horizonFlag': b.get('horizon_flag'),
            'dirEnu': list(astro.enu_direction(b['az_deg'], b['el_deg']))}


def skyline_bin(b, az_deg):
    sk = b['skyline']
    n = sk['bins']
    k = int(round((az_deg % 360.0) / (360.0 / n))) % n
    return k, sk['elevation_deg'][k], (sk['critical'][k] or {}).get('distance_m')


def sight_line(b, body, mast_m):
    """Ray from the mast top toward the body, with the bundle's own state; a blocked ray ends at the bundle skyline's critical
    point for that azimuth bin (horizontal distance / cos el). Nothing is recomputed."""
    k, sky_el, dist = skyline_bin(b, body['azDeg'])
    state = 'clear' if body['centreVisible'] else 'blocked'
    length = None
    if state == 'blocked' and dist:
        length = dist / max(math.cos(math.radians(body['elDeg'])), 1e-6)
    return {'state': state, 'skylineBin': k, 'skylineElDeg': sky_el, 'criticalDistanceM': dist, 'lengthM': length,
            'fromHeightM': mast_m, 'rule': 'bundle center_visible; blocked rays end at the bundle skyline critical point'}


def camera_pose(cam, look_az=None, look_el=None, sun=None, emission_deg=0.0, altitude_m=None, offset_enu=None):
    """Camera position and look direction in ENU. Surface cameras stand at the site (lander camera: 6 m off the site toward
    -look so the site is in frame); orbital instruments sit at `altitude_m` above the site, looking down at `emission_deg`
    off nadir toward look_az (+180 for the camera position)."""
    if cam['kind'] == 'surface':
        az = (sun['azDeg'] + 120.0) if look_az is None else look_az
        el = -1.0 if look_el is None else look_el
        d = astro.enu_direction(az, el)
        back = astro.enu_direction(az, 0.0)
        # EVA eye: 3 m behind the site so the mast and rays are in frame; lander camera: on the side of the ILLUSTRATIVE
        # lander body (r 2 m), 2.3 m out from the site centre toward the view, looking outward
        stand = -2.3 if cam['name'] == 'lander_cam' else 3.0
        pos = [-stand * back[0], -stand * back[1], cam['height_m']]
        if offset_enu:
            pos = [p + o for p, o in zip(pos, offset_enu)]
        return {'posEnu': pos, 'lookDir': list(d), 'lookAzDeg': az, 'lookElDeg': el,
                'standBackM': stand,
                'rule': 'default: Sun azimuth + 120 deg (Sun behind-left, lit slopes in view), 1 deg down' if look_az is None else 'user'}
    alt = altitude_m or DEFAULT_ALTITUDE_M.get(cam['name'], 50_000.0)
    az = 0.0 if look_az is None else look_az
    e = math.radians(emission_deg)
    ground_range = alt * math.tan(e)
    back = astro.enu_direction(az + 180.0, 0.0)
    pos = [ground_range * back[0], ground_range * back[1], alt]
    look = [-p for p in pos]
    n = math.sqrt(sum(v * v for v in look))
    return {'posEnu': pos, 'lookDir': [v / n for v in look], 'altitudeM': alt, 'emissionDeg': emission_deg, 'lookAzDeg': az,
            'slantRangeM': n, 'rule': 'orbital: above the site (flat-sphere approximation of the spacecraft position; no ephemeris)'}


def build_spec(lat, lon, utc, camera='eva_eye', bundle=None, mast=None, look_az=None, look_el=None, emission_deg=0.0,
               altitude_m=None, layout='research', hapke_region='SOUTH_60_70', resolution=512, samples=32, seed=0,
               device='CPU', terrain='cache', overlays=None, stars=True):
    if bundle is None:
        bundle, dmatch = find_bundle(lat, lon, mast)
    else:
        dmatch = None
    bpath = Path(bundle).resolve()
    b = json.loads(bpath.read_text())
    if b.get('schema') != 'polaris-science-results-v1':
        raise SpecError(f'{bpath.name}: schema {b.get("schema")!r} is not polaris-science-results-v1')
    k, off = astro.pick_sample(b['samples'], utc)
    s = b['samples'][k]
    site = b['site']
    sun, earth = _body(s, 'sun'), _body(s, 'earth')
    sun['irradianceWm2'] = astro.solar_irradiance(sun['rangeAu'])
    sun['discAngleDeg'] = astro.sun_disc_angle_deg(sun['radiusDeg'])
    sun['lampOn'] = (sun['discFraction'] or 0) > 0 or sun['elDeg'] > -sun['radiusDeg']
    ph = astro.earth_phase(sun['azDeg'], sun['elDeg'], sun['rangeAu'], earth['azDeg'], earth['elDeg'], earth['rangeAu'])
    earth.update(ph)
    earth['earthshineIrradianceWm2'] = astro.earthshine_irradiance(ph['sunEarthRangeAu'], ph['phaseAngleDeg'], earth['radiusDeg'])
    earth['earthshineRule'] = (f'E_sun(at Earth) x p({astro.EARTH_GEOMETRIC_ALBEDO}) x Lambert-sphere phase(alpha) x sin^2(angular radius); '
                               'MODEL, not data')
    earth['lampOn'] = earth['elDeg'] > -earth['radiusDeg']
    dominant = 'sun' if sun['lampOn'] else ('earth' if earth['lampOn'] else 'none')
    M, check = astro.icrf_to_enu(astro.parse_utc(s['utc']), site['lat_deg'], site['lon_deg_east'], sun['azDeg'], sun['elDeg'])
    cam = cameras.preset(camera)
    pose = camera_pose(cam, look_az, look_el, sun, emission_deg, altitude_m)
    layout_cfg = ASSET_LAYOUTS[layout]
    hp = hapke.params(hapke_region)
    if overlays is None:
        overlays = cam['kind'] == 'surface'
    mast_m = float(site.get('observer_mast_m') or 1.0)
    spec = {
        'schema': SCHEMA,
        'world': 'moon',
        'request': {'lat': lat, 'lon': lon, 'utc': utc, 'camera': camera},
        'bundle': {'file': str(bpath.relative_to(ROOT)) if bpath.is_relative_to(ROOT) else str(bpath), 'sha256': sha256_file(bpath),
                   'bundleId': b.get('bundle_id'), 'validation': (b.get('validation_status') or {}).get('overall'),
                   'siteMatchDistanceM': dmatch, 'generator': b.get('generator')},
        'site': {'id': site['id'], 'name': site.get('name'), 'latDeg': site['lat_deg'], 'lonEastDeg': site['lon_deg_east'],
                 'gridXM': site.get('grid_x_m'), 'gridYM': site.get('grid_y_m'), 'heightM': site.get('height_m'),
                 'heightSource': site.get('height_source'), 'mastM': mast_m},
        'sample': {'index': k, 'utc': s['utc'], 'requestOffsetS': off, 'rule': 'exact bundle sample (or nearest within half a step); no interpolation'},
        'sun': sun, 'earth': earth, 'dominantLight': dominant,
        'sightLines': {'sun': sight_line(b, sun, mast_m), 'earth': sight_line(b, earth, mast_m)},
        'skyline': {'bins': b['skyline']['bins'], 'azimuthDeg': b['skyline']['azimuth_deg'], 'elevationDeg': b['skyline']['elevation_deg'],
                    'criticalDistanceM': [(c or {}).get('distance_m') for c in b['skyline']['critical']], 'fromHeightM': mast_m,
                    'label': b['skyline'].get('label'), 'method': b['skyline'].get('method')},
        'stars': {'enabled': bool(stars), 'icrfToEnu': [list(r) for r in M], 'check': check,
                  'rule': 'TRIAD: Moon pole (IAU 2009, matched exactly) + Sun (almanac ICRF vs Horizons az/el) for the roll'},
        'photometry': {'model': 'Hapke 2012 (IMSA + SHOE + roughness), Sato et al. 2014 LROC WAC form', 'band': '643 nm',
                       'region': hapke_region, 'params': hp, 'fixed': hapke.FIXED, 'pdsProduct': hapke.PDS_URL,
                       'pdsSha256': hapke.PDS_SHA256, 'label': 'MODEL'},
        'camera': {**{k_: v for k_, v in cam.items() if k_ != 'sources'}, 'sources': cam.get('sources', []), 'pose': pose,
                   'layout': cameras.render_layout(cam, resolution), 'exposureStops': cameras.exposure_stops(cam)},
        'assets': {'layout': layout, 'config': layout_cfg, 'label': 'ILLUSTRATIVE asset shapes (cylinders), not a lander design',
                   'source': 'science/cube/build_assets.py LAYOUTS (positions in grid metres from the site)'},
        'overlays': bool(overlays),
        'render': {'engine': 'CYCLES', 'samples': int(samples), 'seed': int(seed), 'device': device},
        'terrain': {'source': terrain},
        'labels': {'geometry': 'SOURCE-BASED · UNVALIDATED', 'relief': 'VISUAL', 'assets': 'ILLUSTRATIVE', 'photometry': 'MODEL',
                   'earthshine': 'MODEL', 'stars': 'VISUAL (orientation MODEL, brightness MODEL)'},
    }
    return spec


def grid_offset_to_enu(dx, dy, lon_deg):
    """Grid-metre offset at longitude L -> (east, north): east = (cos L, -sin L), north = (sin L, cos L) (science/frames)."""
    L = math.radians(lon_deg)
    return dx * math.cos(L) - dy * math.sin(L), dx * math.sin(L) + dy * math.cos(L)
