"""World registry: get_world('moon' | 'mercury' | 'mars')."""
from __future__ import annotations

from .base import World


def _mars():
    from .base import Orbit, RotationModel
    return World(
        name='mars', naif_id=499, horizons_center='coord@499', horizons_coord_type='GEODETIC', horizons_longitude='west',
        horizons_radii_km=(3396.19, 3396.19, 3376.2), radius_m=3_389_500.0, shape='not wired',
        rotation=RotationModel(317.269202, -0.10927547, 54.432516, -0.05827105, 176.049863, 350.891982443297,
                               'periodic terms not evaluated', 'Archinal et al. (2018), Table 2'),
        body_fixed_frame='IAU_MARS', spice_kernels='not loaded', orbit=Orbit(1.52371034, 0.09339410, 686.980, 'JPL approx.'),
        relief_max_m=21_900.0, relief_min_m=-8_200.0, relief_source='MOLA (approx.)', atmosphere='mars',
        dem_stack=[], comms=[], default_requirements={}, available=False,
        availability_note=('Mars (prompt §3.3) is not started: it needs atmospheric opacity (tau) as an explicit input for '
                           'any energy number, seasons via Ls, and relay-orbiter ephemerides before any comms number. '
                           'R6 stops at Mercury by instruction.'))


def get_world(name: str) -> World:
    n = name.lower()
    if n == 'moon':
        from .moon import MOON
        return MOON
    if n == 'mercury':
        from .mercury.world import MERCURY
        return MERCURY
    if n == 'mars':
        return _mars()
    raise KeyError(f'unknown world {name!r}')


WORLDS = ('moon', 'mercury', 'mars')
