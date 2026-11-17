"""Mars terrain provider for the generic world solver: near/far layers for any site, heights above 3 396 000 m.

Priority along each ray (first layer with data wins): CTX 20 m (Jezero science mosaic) > MOLA MEGDR 128 ppd (cached tile
0-44 N 0-90 E) > MOLA MEGDR 16 ppd (global fill). Outside the CTX footprint the near field is MOLA itself.
Members (alternative products, not probabilities): 'mola_only' (no CTX), 'ctx_trn' (the independent TRN CTX DTM as near
field instead of the science mosaic; only where it holds the site).
"""
from __future__ import annotations

import math

from ..anysite import TerrainSet
from ..skyline import Layer
from . import dem as MD

STEP_DIV = 5.0
FINE_MAX_M = 12_500.0
FAR_STEP_M = 100.0


def _rec(name, pid, rel, step, crs, role, note=''):
    from ..mercury.site import _manifest_sha
    e = _manifest_sha(f'v2/products/{pid}/{rel}')
    return {'name': name, 'product_id': pid, 'local_path': f'v2/products/{pid}/{rel}', 'step_m': step, 'crs': crs,
            'role': role, 'source_url': e['url'] if e else None, 'file_sha256': e['sha256'] if e else None, 'note': note}


def _inscribed(d, fwd, lat, lon):
    x, y = fwd(lat, lon)
    l, b, r, t = d.bounds
    return max(0.0, min(float(x) - l, r - float(x), float(y) - b, t - float(y)) - d.step)


def provider(lat, lon, max_range_m, member=None):
    layers, recs = [], []
    if member != 'mola_only':
        which = 'trn' if member == 'ctx_trn' else 'sci'
        d, fwd, crs = MD.ctx(which)
        inside = math.isfinite(float(d.sample(*fwd(lat, lon))))
        if inside:
            pid, rel = MD.CTX_SCI if which == 'sci' else MD.CTX_TRN
            layers.append(Layer(d, fwd, 'near'))
            recs.append(_rec(d.name, pid, rel, d.step, crs, 'near', d.meta['datum_conversion']))
        elif member == 'ctx_trn':
            raise LookupError('the TRN CTX DTM does not hold this site')
    try:
        m128 = MD.mola_radius(128, lat, lon, max_range_m)
        layers.append(Layer(m128, m128.forward, 'far'))
        recs.append(_rec(m128.name, MD.MEG128, MD.TILE128['megr'] + '.img', m128.step, 'simple cylindrical 128 ppd', 'far',
                         'radius - 3 396 000 m'))
    except LookupError:
        m128 = None
    m16 = MD.mola_radius(16, lat, lon, max_range_m)
    layers.append(Layer(m16, m16.forward, 'far'))
    recs.append(_rec(m16.name, MD.MEG016, 'meg016/megr90n000eb.img', m16.step, 'simple cylindrical 16 ppd', 'global fill',
                     'radius - 3 396 000 m'))
    first = layers[0]
    near_cut = min(FINE_MAX_M, _inscribed(first.dem, first.forward, lat, lon)) if first.role == 'near' else FINE_MAX_M
    step_near = first.dem.step / STEP_DIV
    return TerrainSet(layers, step_near, near_cut, FAR_STEP_M, float('inf'), recs,
                      Layer(m128, m128.forward, 'far') if m128 is not None else layers[-1],
                      ' > '.join(r['name'] for r in recs))
