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


def with_scenario_geometry(d, sc):
    """Position-offset scenarios carry their own JPL samples (same UTC times) and local-ENU basis. Return the dataset with
    those swapped in, exactly like the web viewer (web/src/store/view.ts withScenarioGeometry); unchanged otherwise."""
    if not sc:
        return d
    out = d
    e = sc.get('ephemeris')
    if e and [s['time'] for s in e['samples']] == [s['time'] for s in d['ephemeris']['samples']]:
        out = dict(out, ephemeris=dict(out['ephemeris'], samples=e['samples']))
    f = sc.get('frame')
    if f and f.get('localNorthInGrid') and f.get('localEastInGrid') and out.get('derived'):
        out = dict(out, derived=dict(out['derived'], frame=f))
    return out


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


CONTEXT_CUT_DROP_M = 40.0


def context_regional_dem(context_dir, local_dem, cut_box=None):
    """Display-only regional context for the Blender scene, from a terrain context pack
    (tools/terrain/build_terrain_context.py). Returns (dem_like, info) or (None, reason).

    The pack must be VISUAL / numericalAuthority false and built for exactly this local DEM crop (crop hash). The
    returned grid is the pack's 80 m PGDA 90 crop in the same site-relative grid frame as the bundle DEM, with ONE
    presentation change: nodes strictly inside the local 5 m footprint (inset by one regional cell) are lowered by
    CONTEXT_CUT_DROP_M so the two surfaces never coincide in a render. That cut is visual, is counted in `info`, and
    the grid is never used for any calculation.
    """
    from array import array
    d = Path(context_dir)
    meta_path = d / 'context.json'
    if not meta_path.is_file():
        return None, 'no context pack'
    meta = json.loads(meta_path.read_text())
    if meta.get('schema') != 'polaris-terrain-context-v1' or meta.get('status') != 'VISUAL' or meta.get('numericalAuthority') is not False:
        return None, 'context pack is not a VISUAL polaris-terrain-context-v1 pack'
    if meta.get('local', {}).get('cropValuesSha256') != local_dem.get('cropValuesSha256'):
        return None, 'context pack was built for a different DEM crop'
    r = meta['regional']
    raw = (d / r['file']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != r['sha256']:
        return None, 'regional file hash differs from context.json'
    n = int(r['n'])
    vals = array('f')
    vals.frombytes(raw)
    if sys_is_big_endian():
        vals.byteswap()
    if len(vals) != n * n:
        return None, 'regional file size mismatch'
    values = list(vals)
    s, ox, oy = float(r['spacingM']), float(r['originX']), float(r['originY'])
    ln, ls = int(local_dem['n']), float(local_dem['spacing'])
    x0, y0 = float(local_dem['originX']) + s, float(local_dem['originY']) + s
    x1, y1 = float(local_dem['originX']) + (ln - 1) * ls - s, float(local_dem['originY']) + (ln - 1) * ls - s
    if cut_box is not None:                      # cut under a finer level that encloses the local crop (the L1 ring)
        x0, x1, y0, y1 = cut_box[0] + s, cut_box[1] - s, cut_box[2] + s, cut_box[3] - s
    cut = 0
    for j in range(n):
        y = oy + j * s
        if not (y0 < y < y1):
            continue
        for i in range(n):
            x = ox + i * s
            if x0 < x < x1:
                values[j * n + i] -= CONTEXT_CUT_DROP_M
                cut += 1
    dem_like = {'kind': 'nasa', 'layer': 'regional_80m_context_DISPLAY_ONLY', 'n': n, 'spacing': s, 'originX': ox, 'originY': oy, 'values': values}
    info = {'product': r.get('product'), 'source': r.get('source'), 'n': n, 'spacingM': s, 'sha256': r['sha256'],
            'sourceCropValuesSha256': r.get('sourceCropValuesSha256'), 'nodesLoweredInsideLocalFootprint': cut,
            'visualCutDropM': CONTEXT_CUT_DROP_M, 'status': 'VISUAL', 'numericalAuthority': False,
            'role': 'display context around the 5 m crop; never used for any calculation'}
    return dem_like, info


def _pack_meta(context_dir, local_dem):
    d = Path(context_dir)
    meta_path = d / 'context.json'
    if not meta_path.is_file():
        return None, None, 'no context pack'
    meta = json.loads(meta_path.read_text())
    if meta.get('schema') != 'polaris-terrain-context-v1' or meta.get('status') != 'VISUAL' or meta.get('numericalAuthority') is not False:
        return None, None, 'context pack is not a VISUAL polaris-terrain-context-v1 pack'
    if meta.get('local', {}).get('cropValuesSha256') != local_dem.get('cropValuesSha256'):
        return None, None, 'context pack was built for a different DEM crop'
    return d, meta, None


def _read_f32(path, sha, count):
    from array import array
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        return None, 'file hash differs from context.json'
    vals = array('f')
    vals.frombytes(raw)
    if sys_is_big_endian():
        vals.byteswap()
    if len(vals) != count:
        return None, 'file size mismatch'
    return list(vals), None


def context_display_surface(context_dir, local_dem):
    """DISPLAY surface for the 5 m crop from a context pack (`localDisplay`): NASA GSFC shape-from-shading heights blended into
    the LOLA crop (tools/terrain/build_terrain_context.py). Same nodes as the bundle crop. Returns (values, info) or (None, reason).
    Never used for any calculation: rays, states and margins stay the bundle's."""
    d, meta, why = _pack_meta(context_dir, local_dem)
    if why:
        return None, why
    ld = meta.get('localDisplay')
    if not ld:
        return None, 'pack has no display surface (no SfS coverage at this site)'
    n = int(local_dem['n'])
    if int(ld['n']) != n:
        return None, 'display surface grid differs from the bundle crop'
    vals, why = _read_f32(d / ld['file'], ld['sha256'], n * n)
    if why:
        return None, why
    info = {k: ld.get(k) for k in ('product', 'citation', 'doi', 'licence', 'sha256', 'coverageFraction', 'fullWeightFraction', 'minusSolverCropM', 'rule')}
    info.update(status='VISUAL', numericalAuthority=False, role='display surface of the 5 m crop; the bundle crop is what rays and states use')
    return vals, info


def display_shift(local_dem, display_values, obs):
    """Constant added to every displayed level so the display surface meets the bundle ground at the observer's cell (the
    mast and rays stand on bundle heights). Same rule as the web viewer (TerrainSurface.tsx)."""
    n, s = int(local_dem['n']), float(local_dem['spacing'])
    i = min(n - 1, max(0, round((obs['x'] - float(local_dem['originX'])) / s)))
    j = min(n - 1, max(0, round((obs['y'] - float(local_dem['originY'])) / s)))
    return float(local_dem['values'][j * n + i]) - float(display_values[j * n + i])


def context_mid_dem(context_dir, local_dem):
    """L1 ring of a context pack (`mid`, full 5 m since 15 Nov 22:00, earlier packs 20 m; about +-4 km), as a dem-like grid, with nodes strictly inside the local 5 m
    footprint (inset one L1 cell) lowered by CONTEXT_CUT_DROP_M so the two surfaces never coincide. Returns (dem_like, info,
    box) where box = (xmin, xmax, ymin, ymax) of the ring, or (None, reason, None)."""
    d, meta, why = _pack_meta(context_dir, local_dem)
    if why:
        return None, why, None
    m = meta.get('mid')
    if not m:
        return None, 'pack has no L1 ring', None
    n, s, ox, oy = int(m['n']), float(m['spacingM']), float(m['originX']), float(m['originY'])
    vals, why = _read_f32(d / m['file'], m['sha256'], n * n)
    if why:
        return None, why, None
    ln, ls = int(local_dem['n']), float(local_dem['spacing'])
    x0, y0 = float(local_dem['originX']) + s, float(local_dem['originY']) + s
    x1, y1 = float(local_dem['originX']) + (ln - 1) * ls - s, float(local_dem['originY']) + (ln - 1) * ls - s
    cut = 0
    for j in range(n):
        y = oy + j * s
        if not (y0 < y < y1):
            continue
        for i in range(n):
            if x0 < ox + i * s < x1:
                vals[j * n + i] -= CONTEXT_CUT_DROP_M
                cut += 1
    dem_like = {'kind': 'nasa', 'layer': f'L1_{s:g}m_ring_DISPLAY_ONLY', 'n': n, 'spacing': s, 'originX': ox, 'originY': oy, 'values': vals}
    info = {'product': m.get('product'), 'n': n, 'spacingM': s, 'sha256': m['sha256'], 'sfsFraction': m.get('sfsFraction'),
            'nodesLoweredInsideLocalFootprint': cut, 'visualCutDropM': CONTEXT_CUT_DROP_M, 'status': 'VISUAL', 'numericalAuthority': False}
    return dem_like, info, (ox, ox + (n - 1) * s, oy, oy + (n - 1) * s)


def sys_is_big_endian():
    import sys
    return sys.byteorder == 'big'


def transition_sample(sc, target='sun'):
    """First sample index at which the bundle's visible flag for `target` changes (the sample AFTER the change), else None.

    Purely a lookup in derived outputs; the transition itself lies between sample k-1 and k (hourly bracket, not refined)."""
    if not sc:
        return None
    vis = sc['samples'][target]['visible']
    for k in range(1, len(vis)):
        if bool(vis[k]) != bool(vis[k - 1]):
            return k
    return None


def key_samples_with_transition(d, sc):
    """start / mid / end plus `transition` (first Sun change, else first Earth change) when the bundle has one."""
    keys = key_samples(d)
    for t in ('sun', 'earth'):
        k = transition_sample(sc, t)
        if k is not None:
            keys['transition'] = k
            keys['transitionTarget'] = t
            break
    return keys
