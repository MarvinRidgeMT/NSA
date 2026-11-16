"""The Moon as a `World`. It WRAPS the existing code; nothing on the Moon path is reimplemented:
  * frames, skyline, Horizons query: science.frames / science.skyline / science.horizons.build_params (byte-identical);
  * any-site solve: science.anysite.solve.solve (owned by R1; called, never edited).
The regression test science/worlds/tests/test_moon_world.py re-derives Site04 RoI 3 through this module.
"""
from __future__ import annotations

from .. import frames
from ..anysite import curvature
from .base import LABEL, CommsAsset, DemProduct, Orbit, RotationModel, World

MOON = World(
    name='moon', naif_id=301, horizons_center='coord@301', horizons_coord_type='GEODETIC', horizons_longitude='east',
    horizons_radii_km=(1737.4, 1737.4, 1737.4), radius_m=frames.R_MOON_M,
    shape='sphere R = 1 737 400 m (LOLA LDEM reference radius; Horizons body 301 radii are the same sphere)',
    rotation=RotationModel(
        269.9949, 0.0031, 66.5392, 0.0130, 38.3213, 13.17635815,
        'plus 13 periodic terms E1..E13 (IAU); the pipeline does not evaluate them: Horizons and the DEM frames do',
        'Archinal et al. (2018) Celest. Mech. Dyn. Astron. 130:22 (IAU WGCCRE 2015), Table 2'),
    body_fixed_frame='DEMs: MOON_ME (DE421) per PGDA/LOLA; Horizons coord@301: MEAN_ME high precision (DE441)',
    spice_kernels='not loaded by the pipeline; frame offset DE421 ME vs DE440 ME bounded in bundles (moon_de440_220930.tf)',
    orbit=Orbit(1.0, 0.0167, 365.256, 'Earth-Moon barycentre about the Sun (context only; not used by any check)'),
    relief_max_m=curvature.MOON_MAX_HEIGHT_M, relief_min_m=curvature.MOON_MIN_HEIGHT_M, relief_source=curvature.RELIEF_SOURCE,
    atmosphere='none',
    dem_stack=[DemProduct('pgda78', 'near', 5.0, 'south-polar sites', 'm above 1 737.4 km'),
               DemProduct('pgda90_80m', 'far', 80.0, '80-90 S', 'm above 1 737.4 km'),
               DemProduct('lola_ldem_polar', 'near', 5.0, 'both poles', 'km above 1 737.4 km (converted)'),
               DemProduct('sldem2015_512', 'global', 59.0, '60 S - 60 N', 'km above 1 737.4 km (converted)'),
               DemProduct('pyramid', 'global', 20.0, 'whole Moon (S3 pyramid, terrain stack contract)', 'm above 1 737.4 km')],
    comms=[CommsAsset('dsn-dte', 'direct-to-earth', True,
                      'Earth centre above the local terrain skyline (geometric line of sight only); DSN station '
                      'visibility and link budget are not modelled'),
           CommsAsset('lunar-relay', 'relay', False, 'no relay orbiter ephemerides wired (D_relay axis is a placeholder)')],
    default_requirements={
        'sun_center_pct_ge_70': {'value': 70, 'unit': '% of hourly samples', 'source': 'team requirement (science/certainty.py)'},
        'both_center_pct_ge_40': {'value': 40, 'unit': '% of hourly samples', 'source': 'team requirement (science/certainty.py)'},
        'sun_center_pct_eq_100': {'value': 100, 'unit': '% of hourly samples', 'source': 'polaris_batch definition'}},
)


def solve(lat, lon, **kw):
    """Any-site solve on the Moon: exactly science.anysite.solve.solve (same arguments, same bundle)."""
    from ..anysite.solve import solve as anysite_solve
    b = anysite_solve(lat, lon, **kw)
    return b


def world_block(bundle=None):
    return {'world': 'moon', 'label': LABEL, 'solver': 'science.anysite.solve (unchanged)'}
