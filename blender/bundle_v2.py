"""Pure-Python (no bpy) reader for science-bundle-v2 (POLARIS-X5D-v2), used by
blender/build_from_nasa_bundle.py. Unit-tested by blender/test_bundle_v2.py.

Blender is READ-ONLY with respect to science: it places geometry and lights from
bundle values. It never computes a skyline, a visibility flag, a margin or a metric.

Frames
------
DEM crops are on the south-polar stereographic GRID (x = grid east, y = grid north,
metres). JPL azimuths are LOCAL (clockwise from local north). At longitude L:
    local north in grid = ( sin L,  cos L )
    local east  in grid = ( cos L, -sin L )
A bundle may declare datasets[i].derived.frame.localNorthInGrid/localEastInGrid; that
wins. The rotation is used only to aim the lamp and draw rays.
"""
import hashlib
import json
import math
from pathlib import Path

FORMAT = 'POLARIS-X5D-v2'
STATUS_LABEL = {
    'DEMO_ONLY': 'DEMO',
    'SOURCE_BASED_UNVALIDATED': 'SOURCE-BASED UNVALIDATED',
    'VALIDATED_NASA_JPL': 'VALIDATED',
}


class BundleError(ValueError):
    pass


def load(path):
    """Return (bundle_dict, sha256_hex_of_bytes, byte_count). Refuses anything but v2."""
    raw = Path(path).expanduser().read_bytes()
    try:
        b = json.loads(raw)
    except json.JSONDecodeError as e:
        raise BundleError(f'{path}: not JSON ({e})')
    if b.get('format') != FORMAT:
        raise BundleError(f"{path}: format {b.get('format')!r} is not {FORMAT}")
    if not str(b.get('schemaVersion', '')).startswith('2.'):
        raise BundleError(f"{path}: schemaVersion {b.get('schemaVersion')!r} is not 2.x")
    if not b.get('datasets'):
        raise BundleError(f'{path}: no datasets')
    return b, hashlib.sha256(raw).hexdigest(), len(raw)


def display_status(b):
    """Most cautious label across the bundle; anything synthetic is DEMO."""
    raws = [b.get('validation', {}).get('status')]
    for d in b['datasets']:
        raws.append(d.get('validation', {}).get('status'))
        if d.get('derived'):
            raws.append(d['derived'].get('status'))
        if d.get('dem', {}).get('kind') != 'nasa':
            raws.append('DEMO_ONLY')
    if b.get('demo'):
        raws.append('DEMO_ONLY')
    if any(r == 'DEMO_ONLY' or r not in STATUS_LABEL for r in raws):
        return 'DEMO'
    if any(r == 'SOURCE_BASED_UNVALIDATED' for r in raws):
        return 'SOURCE-BASED UNVALIDATED'
    return 'VALIDATED'


def dataset(b, site_id=None):
    if site_id is None:
        return b['datasets'][0]
    for d in b['datasets']:
        if d['siteId'] == site_id:
            return d
    raise BundleError(f"no dataset for site {site_id!r}; have {[d['siteId'] for d in b['datasets']]}")


def check_dem(dem):
    n = dem['n']
    if len(dem['values']) != n * n:
        raise BundleError(f"DEM has {len(dem['values'])} values, expected {n * n}")
    if 'south-to-north' not in dem.get('rowOrder', ''):
        raise BundleError('DEM rowOrder must be south-to-north')
    if dem.get('verticalUnits') != 'meters':
        raise BundleError('DEM verticalUnits must be meters')
    for v in dem['values']:
        if not math.isfinite(v):
            raise BundleError('DEM contains non-finite values')


def basis(d):
    f = (d.get('derived') or {}).get('frame') or {}
    if f.get('localNorthInGrid') and f.get('localEastInGrid'):
        return tuple(f['localNorthInGrid']), tuple(f['localEastInGrid']), 'bundle'
    L = math.radians(d['site']['longitudeEastDeg'])
    return (math.sin(L), math.cos(L)), (math.cos(L), -math.sin(L)), 'derived-from-longitude'


def grid_direction(d, az_deg, el_deg):
    """Unit vector (x grid-east, y grid-north, z up) pointing TOWARD a target at local az/el."""
    north, east, _ = basis(d)
    a, e = math.radians(az_deg), math.radians(el_deg)
    h = math.cos(e)
    return (
        (math.sin(a) * east[0] + math.cos(a) * north[0]) * h,
        (math.sin(a) * east[1] + math.cos(a) * north[1]) * h,
        math.sin(e),
    )


def key_samples(d):
    """Start / mid / end sample indices of the ephemeris."""
    n = len(d['ephemeris']['samples'])
    if n < 2:
        raise BundleError('need at least 2 ephemeris samples')
    return {'start': 0, 'mid': n // 2, 'end': n - 1}


def scenario(d, scenario_id=None):
    der = d.get('derived')
    if not der:
        return None
    if scenario_id is None:
        return der['scenarios'][0]
    for s in der['scenarios']:
        if s['id'] == scenario_id:
            return s
    raise BundleError(f'no scenario {scenario_id!r}')


def observer(d, sc):
    """Observer in grid metres: from the scenario if present, else the DEM node nearest the crop centre (display only)."""
    if sc:
        o = sc['observer']
        return {'x': o['xM'], 'y': o['yM'], 'ground': o['groundM'], 'mast': o['mastM'], 'source': 'bundle scenario'}
    dem = d['dem']
    n = dem['n']
    i = min(n - 1, max(0, round(-dem['originX'] / dem['spacing'])))
    j = min(n - 1, max(0, round(-dem['originY'] / dem['spacing'])))
    return {'x': dem['originX'] + i * dem['spacing'], 'y': dem['originY'] + j * dem['spacing'],
            'ground': dem['values'][j * n + i], 'mast': 2.0, 'source': 'DEM node nearest crop centre (display only)'}


def ray_state(sc, target, k):
    """(state, first_hit_horizontal_m) from the bundle; ('not evaluated', None) without derived outputs."""
    if not sc:
        return 'not evaluated', None
    ser = sc['samples'][target]
    if ser['visible'][k]:
        return 'clear', None
    return 'blocked', ser['firstHitM'][k]


def png_pixel_sha256(path):
    """SHA-256 of a PNG's decompressed IDAT stream (the pixel rows).

    Unlike a whole-file hash it survives ancillary metadata chunks being added later
    (for example C2PA content-credential chunks inserted by file-transfer tools)."""
    import struct
    import zlib
    data = Path(path).read_bytes()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise BundleError(f'{path}: not a PNG')
    pos, idat = 8, []
    while pos < len(data):
        length, ctype = struct.unpack('>I4s', data[pos:pos + 8])
        if ctype == b'IDAT':
            idat.append(data[pos + 8:pos + 8 + length])
        pos += 12 + length
    return hashlib.sha256(zlib.decompress(b''.join(idat))).hexdigest()


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()
