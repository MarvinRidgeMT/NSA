"""`World`: everything that changes when POLARIS X moves from the Moon to another airless (or not) body (prompt §3.1).

The world is a CONTEXT SELECTOR, not a scenario axis: one bundle belongs to one world; cube axes are unchanged.

Fields: radius/shape, IAU rotation model + body-fixed frame (+ SPICE kernel note), Horizons ID and observer syntax,
DEM stack, atmosphere, default requirements, comms assets, orbit (for physics checks), relief bounds (curvature limit),
availability. Labels: geometry SOURCE-BASED UNVALIDATED; requirements / comms thresholds ENGINEERING ASSUMPTION unless
a source is given.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from .geometry import Sphere

LABEL = 'SOURCE-BASED UNVALIDATED'
ENGINEERING = 'ENGINEERING ASSUMPTION'
AU_KM = 149_597_870.7
R_SUN_KM = 695_700.0                 # IAU 2015 Resolution B3 nominal solar radius (Horizons IAU_SUN radii)


@dataclass(frozen=True)
class RotationModel:
    """IAU WGCCRE pole and prime meridian: alpha0, delta0 (deg, ICRF, J2000 + rate per century), W = W0 + Wdot d."""
    alpha0_deg: float
    alpha0_rate_deg_per_cy: float
    delta0_deg: float
    delta0_rate_deg_per_cy: float
    W0_deg: float
    Wdot_deg_per_day: float
    periodic_terms: str
    source: str

    @property
    def sidereal_period_days(self) -> float:
        return 360.0 / self.Wdot_deg_per_day


@dataclass(frozen=True)
class Orbit:
    """Heliocentric mean orbit (for physics checks only; ephemerides always come from Horizons)."""
    a_au: float
    e: float
    period_days: float
    source: str

    @property
    def perihelion_au(self) -> float:
        return self.a_au * (1 - self.e)

    @property
    def aphelion_au(self) -> float:
        return self.a_au * (1 + self.e)


@dataclass(frozen=True)
class CommsAsset:
    id: str
    kind: str                         # 'direct-to-earth' | 'relay'
    wired: bool                       # ephemerides / geometry available in the pipeline
    description: str
    thresholds: Dict[str, float] = field(default_factory=dict)
    source: str = ''
    label: str = ENGINEERING


@dataclass(frozen=True)
class DemProduct:
    product_id: str
    role: str                         # 'near' | 'far' | 'global' | 'ice' | 'visual'
    resolution_m: float
    coverage: str
    datum: str
    note: str = ''


@dataclass
class World:
    name: str
    naif_id: int
    horizons_center: str              # e.g. 'coord@301'
    horizons_coord_type: str          # 'GEODETIC' (Moon: sphere radii, the existing query) | 'CYLINDRICAL'
    horizons_longitude: str           # 'east' | 'west' (west-positive bodies: Horizons wants east longitude entered negative)
    horizons_radii_km: Tuple[float, float, float]
    radius_m: float                   # reference sphere for heights, rays and the skyline
    shape: str
    rotation: RotationModel
    body_fixed_frame: str
    spice_kernels: str
    orbit: Orbit
    relief_max_m: float               # highest point above radius_m (curvature limit)
    relief_min_m: float
    relief_source: str
    atmosphere: str                   # 'none' | 'mars'
    dem_stack: List[DemProduct]
    comms: List[CommsAsset]
    default_requirements: Dict[str, dict]
    available: bool = True
    availability_note: str = ''
    terrain_provider: Optional[Callable] = field(default=None, repr=False, compare=False)
    # frame tie DEM frame -> Horizons frame: {'dem_pck', 'horizons_pck' (product-relative paths), 'evidence', ...}
    frame_tie: Optional[dict] = None
    atmosphere_note: str = ''

    def horizons_lon_offset_deg(self, jd_tdb) -> float:
        """East-longitude offset to add to a DEM-frame longitude to get the Horizons-frame longitude at jd (W_dem - W_h,
        science/worlds/frame_tie.py). 0 when no tie is declared (Moon: not used; its query is the existing one)."""
        if not self.frame_tie:
            return 0.0
        import os
        from . import frame_tie as FT
        base = os.environ.get('POLARIS_DATA') or os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'cache')
        pk = lambda rel: os.path.abspath(os.path.join(base, 'v2', 'products', rel))
        a, b = pk(self.frame_tie['dem_pck']), pk(self.frame_tie['horizons_pck'])
        if not (os.path.exists(a) and os.path.exists(b)):
            raise FileNotFoundError(f'{self.name}: frame-tie kernels not cached ({a}, {b}); run python -m '
                                    f'science.worlds.mars.fetch --products mars_naif_pck')
        return FT.longitude_offset_deg(self.naif_id, a, b, jd_tdb)

    @property
    def sphere(self) -> Sphere:
        return Sphere(self.radius_m)

    # ------------------------------------------------------------------------------------------------ Horizons
    def site_coord(self, lat, lon, height_m) -> str:
        """SITE_COORD string. GEODETIC keeps the Moon's existing format byte for byte; CYLINDRICAL puts the site exactly at
        radius (radius_m + height_m) on the planetocentric latitude, independent of Horizons' ellipsoid."""
        lon_e = lon % 360
        lon_in = lon_e if self.horizons_longitude == 'east' else -lon_e
        if self.horizons_coord_type == 'GEODETIC':
            return f"'{lon_in:.7f},{lat:.7f},{height_m / 1000.0:.6f}'"
        r_km = (self.radius_m + height_m) / 1000.0
        la = math.radians(lat)
        return f"'{lon_in:.7f},{r_km * math.cos(la):.6f},{r_km * math.sin(la):.6f}'"

    def horizons_params(self, target, lat, lon, height_m, start=None, stop=None, step=None, tlist=None,
                        quantities='4,13,20'):
        from .. import horizons as H
        p = H.build_params(target, lat, lon, height_m, start, stop, step, tlist)
        if self.name == 'moon' and quantities == '4,13,20':
            return p                       # the existing Moon query, unchanged
        p['CENTER'] = f"'{self.horizons_center}'"
        p['COORD_TYPE'] = self.horizons_coord_type
        p['SITE_COORD'] = self.site_coord(lat, lon, height_m)
        p['QUANTITIES'] = f"'{quantities}'"
        return p

    # ------------------------------------------------------------------------------------------------ frame tie
    def geodetic_latitude_deg(self, lat, height_m, with_height=False):
        """Geodetic latitude (and height) on Horizons' ellipsoid (a = b, c) of the point at planetocentric lat and radius
        R + h. Standard fixed-point iteration; converges to < 1e-12 rad here (flattening ~1e-3)."""
        a, _, c = (x * 1000.0 for x in self.horizons_radii_km)
        r = self.radius_m + height_m; la = math.radians(lat)
        if abs(a - c) < 1e-9:
            return (float(lat), r - a) if with_height else float(lat)
        p, z = r * math.cos(la), r * math.sin(la)
        e2 = 1 - (c / a) ** 2
        phi = math.atan2(z, p * (1 - e2)); hh = 0.0
        for _ in range(20):
            N = a / math.sqrt(1 - e2 * math.sin(phi) ** 2)
            hh = p / math.cos(phi) - N
            phi = math.atan2(z, p * (1 - e2 * N / (N + hh)))
        return (math.degrees(phi), hh) if with_height else math.degrees(phi)

    def horizons_azel_to_sphere(self, az_deg, el_deg, lat, lon, height_m):
        """Horizons topocentric az/el refer to the ellipsoid (geodetic) normal; the skyline uses the sphere normal.
        Rotate the direction about the local east axis by (geodetic - planetocentric latitude). Zero for a sphere."""
        phi_d = self.geodetic_latitude_deg(lat, height_m)
        if phi_d == lat:
            return np.asarray(az_deg, float), np.asarray(el_deg, float), 0.0
        az = np.radians(np.asarray(az_deg, float)); el = np.radians(np.asarray(el_deg, float))
        # direction in the geodetic ENU frame
        e_, n_, u_ = np.cos(el) * np.sin(az), np.cos(el) * np.cos(az), np.sin(el)
        d = math.radians(phi_d - lat)                          # tilt of the geodetic normal toward the pole
        # u_g = cos d u_c + sin d n_c ; n_g = cos d n_c - sin d u_c  =>  project v = e_ e + n_ n_g + u_ u_g on (n_c, u_c)
        n_c = math.cos(d) * n_ + math.sin(d) * u_
        u_c = -math.sin(d) * n_ + math.cos(d) * u_
        el_c = np.degrees(np.arcsin(np.clip(u_c, -1, 1)))
        az_c = np.degrees(np.arctan2(e_, n_c)) % 360.0
        return az_c, el_c, phi_d - lat

    # ------------------------------------------------------------------------------------------------ summary
    def summary(self) -> dict:
        return {
            'name': self.name, 'naif_id': self.naif_id, 'available': self.available, 'availability_note': self.availability_note,
            'reference_sphere_m': self.radius_m, 'shape': self.shape, 'horizons_center': self.horizons_center,
            'horizons_coord_type': self.horizons_coord_type, 'horizons_longitude_input': self.horizons_longitude,
            'horizons_radii_km': list(self.horizons_radii_km), 'body_fixed_frame': self.body_fixed_frame,
            'spice_kernels': self.spice_kernels,
            'rotation': {'alpha0_deg': self.rotation.alpha0_deg, 'delta0_deg': self.rotation.delta0_deg,
                         'W0_deg': self.rotation.W0_deg, 'Wdot_deg_per_day': self.rotation.Wdot_deg_per_day,
                         'sidereal_period_days': round(self.rotation.sidereal_period_days, 6),
                         'periodic_terms': self.rotation.periodic_terms, 'source': self.rotation.source},
            'orbit': {'a_au': self.orbit.a_au, 'e': self.orbit.e, 'period_days': self.orbit.period_days,
                      'source': self.orbit.source},
            'relief_m': [self.relief_min_m, self.relief_max_m], 'relief_source': self.relief_source,
            'atmosphere': self.atmosphere,
            'dem_stack': [vars(p) for p in self.dem_stack],
            'comms': [vars(c) for c in self.comms],
            'default_requirements': self.default_requirements,
            'frame_tie': self.frame_tie, 'atmosphere_note': self.atmosphere_note,
            'context_note': 'The world is a context selector, not a scenario axis.',
        }
