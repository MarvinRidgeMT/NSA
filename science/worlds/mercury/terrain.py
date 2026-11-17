"""Mercury terrain provider for the generic world solver (science/worlds/anysite.py): near/far layers for any site.

Priority (first layer with data wins along each ray, as near-before-far on the Moon):
  north of 75 N : PGDA 85 Prokofiev 125 m (inside its box) > MLA GDR v2 250 m (75-90 N) > USGS 665 m (global fill)
  south of 75 S : PGDA 88 SfS 250 m (75-90 S, unfilled = nominal) > USGS 665 m (global fill)
  elsewhere     : USGS MESSENGER global DEM 665 m (Becker et al. 2016)
Heights in metres above 2 439 400 m. Datums: MLA v2 +600 m re-reference (dem.py), PGDA 85 km on 2 440 km (dem.py),
PGDA 88 m on 2 439.4 km (file name; tested against USGS: tests/test_mercury_south.py), USGS DN x 0.5 m on 2 439.4 km.
Members (alternative products, not probabilities): 'usgs_665m' (USGS alone), 'pgda88_filled' (the producer's gap-filled
DEM), 'mla_v2_only' (north, MLA v2 alone).
"""
from __future__ import annotations

import math

from ..anysite import TerrainSet
from ..geometry import PolarStereo
from ..grids import read_geotiff
from ..skyline import Layer
from . import dem as MD
from .world import MERCURY

USGS = ('mercury_usgs_dem_665m_v2', 'Mercury_Messenger_USGS_DEM_Global_665m_v2.tif')
P88 = 'mercury_pgda88_south_pole'
P88_DEM = 'HDEM_75S250M_ref2439p4km.tif'
P88_FILLED = 'HDEM_75S250M_ref2439p4km_filled.tif'
CAP_DEG = 75.0
STEP_DIV = 5.0
FINE_MAX_M = 12_500.0


def _deg(m):
    return math.degrees(m / MERCURY.radius_m)


def _rec(name, product_id, rel, step, crs, role, note=''):
    from .site import _manifest_sha
    e = _manifest_sha(f'v2/products/{product_id}/{rel}')
    return {'name': name, 'product_id': product_id, 'local_path': f'v2/products/{product_id}/{rel}', 'step_m': step,
            'crs': crs, 'role': role, 'source_url': e['url'] if e else None, 'file_sha256': e['sha256'] if e else None,
            'note': note}


def usgs_layer(lat, max_range_m):
    d = _deg(max_range_m) + 1.0
    g, fwd, crs = read_geotiff(MD.path(*USGS), 'USGS MESSENGER DEM 665 m v2', MERCURY.radius_m,
                               (-180, max(-90.0, lat - d), 180, min(90.0, lat + d)))
    return Layer(g, fwd, 'far'), _rec(g.name, USGS[0], USGS[1], g.step, crs, 'global fill',
                                      'DN x 0.5 m on the 2 439.4 km sphere; simple cylindrical 64 ppd')


def pgda88_layer(filled=False):
    rel = P88_FILLED if filled else P88_DEM
    d, fwd, crs = read_geotiff(MD.path(P88, rel), f'PGDA 88 south-polar SfS DEM 250 m{" (filled)" if filled else ""}',
                               MERCURY.radius_m)
    return Layer(d, fwd, 'near'), _rec(d.name, P88, rel, d.step, crs, 'near/far',
                                       'm above 2 439.4 km (file name; checked against USGS)')


def _inscribed_polar(dem, fwd, lat, lon):
    x, y = fwd(lat, lon)
    l, b, r, t = dem.bounds
    return max(0.0, min(x - l, r - x, y - b, t - y) - dem.step)


def provider(lat, lon, max_range_m, member=None):
    usgs, r_usgs = usgs_layer(lat, max_range_m)
    if member == 'usgs_665m':
        return TerrainSet([usgs], usgs.dem.step / STEP_DIV, max_range_m, usgs.dem.step, float('inf'), [r_usgs], usgs,
                          'member: USGS 665 m alone')
    if lat <= -CAP_DEG:
        near, r_near = pgda88_layer(filled=(member == 'pgda88_filled'))
        cap_reach = MERCURY.radius_m * math.radians(-CAP_DEG - lat) if lat > -90 else float('inf')
        near_cut = min(FINE_MAX_M, _inscribed_polar(near.dem, near.forward, lat, lon))
        return TerrainSet([near, usgs], near.dem.step / STEP_DIV, near_cut, near.dem.step, float('inf'), [r_near, r_usgs],
                          near, f'PGDA 88 to the 75 S edge (~{cap_reach / 1000:.0f} km), USGS 665 m beyond')
    if lat >= CAP_DEG:
        x, y = PolarStereo(2_439_400.0, 'north').forward(lat, lon)
        half = max_range_m + 20_000.0
        mla = MD.mla_v2((x - half, x + half, y - half, y + half))
        r_mla = _rec(mla.dem.name, MD.MLA_V2[0], MD.MLA_V2[1], mla.dem.step, mla.proj.proj4(), 'far',
                     'm above 2 440.0 km in the file, re-referenced to 2 439.4 km')
        layers, recs = [], []
        if member != 'mla_v2_only':
            try:
                p85 = MD.prokofiev('dem')
                if math.isfinite(float(p85.dem.sample(*p85.proj.forward(lat, lon)))):
                    layers.append(Layer(p85.dem, p85.proj.forward, 'near'))
                    recs.append(_rec(p85.dem.name, MD.P85, MD.P85_DEM, p85.dem.step, p85.proj.proj4(), 'near',
                                     'km on 2 440 km, re-referenced'))
            except FileNotFoundError:
                pass
        layers += [Layer(mla.dem, mla.proj.forward, 'far'), usgs]; recs += [r_mla, r_usgs]
        first = layers[0]
        near_cut = min(FINE_MAX_M, _inscribed_polar(first.dem, first.forward, lat, lon))
        return TerrainSet(layers, first.dem.step / STEP_DIV, near_cut, 125.0 if len(layers) == 3 else mla.dem.step,
                          float('inf'), recs, layers[-2], 'north polar stack')
    return TerrainSet([usgs], usgs.dem.step / STEP_DIV, max_range_m, usgs.dem.step, float('inf'), [r_usgs], usgs,
                      'USGS 665 m global (no finer public DEM outside the polar caps)')
