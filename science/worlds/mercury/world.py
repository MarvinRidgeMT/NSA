"""Mercury as a `World` (prompt §3.2): airless, same visibility physics as the Moon, 3:2 spin-orbit resonance, eccentric
orbit, direct-to-Earth communication only, solar conjunctions.

Horizons facts used here were read from a live response on 2026-11-16 (header of a coord@199 query):
  'Center pole/equ : IAU_MERCURY {West-longitude positive}', 'Center radii : 2440.53, 2440.53, 2438.26 km',
  'Input east-longitude as negative for IAU west-positive body #199' (an E-lon of 62.6 entered as -62.6 is echoed as
  W-lon 297.4). The site is therefore given as CYLINDRICAL (E-lon negative, Dxy, Dz in km) so that its radius is exactly
  R + h on the DEM datum sphere, and Horizons az/el (ellipsoid normal) are rotated to the sphere normal
  (World.horizons_azel_to_sphere; <= 0.008 deg at 86 N).
"""
from __future__ import annotations

from ..base import ENGINEERING, CommsAsset, DemProduct, Orbit, RotationModel, World


def _terrain(lat, lon, max_range_m, member=None):
    from .terrain import provider
    return provider(lat, lon, max_range_m, member)


FRAME_TIE = {'dem_pck': 'mars_naif_pck/pck00010_msgr_v23.tpc', 'horizons_pck': 'mars_naif_pck/pck00011.tpc',
             'dem_frame_source': 'MLA RDR SIS (messmla_2101/document/mla_rdrsis.txt): "The current release uses the file '
                                 'pck00010_msgr_v21.tpc"; v2.1-v2.3 differ only in commentary (kernel version log), the '
                                 'archived v2.3 is read.',
             'horizons_model_evidence': 'science/worlds/tests/test_frame_tie.py (geocentric quantity 14 vs LT-corrected '
                                        'vectors, 2026-11-14..2027-11-14, 5-day steps)',
             'offset_deg': 0.0}

R_MERCURY_M = 2_439_400.0          # IAU 2015 mean radius (Archinal et al. 2018); projection sphere of the MLA/USGS products
SEP_X_BAND_DEG = 2.3
SEP_KA_BAND_DEG = 1.0
SEP_SOURCE = ('DSN Telecommunications Link Design Handbook 810-005, module 106 "Solar Corona and Solar Wind Effects", '
              'Rev. B (30 Sep 2010), section 2.3: standard downlink BPSK link design and coding achieve X-band data return '
              'at SEP angles down to at least 2.3 deg, and Ka-band down to 1 deg. '
              'https://deepspace.jpl.nasa.gov/dsndocs/810-005/106/106B.pdf')

MERCURY = World(
    name='mercury', naif_id=199, horizons_center='coord@199', horizons_coord_type='CYLINDRICAL', horizons_longitude='west',
    horizons_radii_km=(2440.53, 2440.53, 2438.26), radius_m=R_MERCURY_M,
    shape=('sphere R = 2 439 400 m for heights and rays (IAU 2015 mean radius; the MLA/USGS map-projection sphere). '
           'Horizons uses an ellipsoid 2440.53/2440.53/2438.26 km; the site is passed in cylindrical coordinates so that '
           'its radius is exact. MLA hdem_75n_250m heights are relative to 2 440 000 m and are re-referenced (+600 m).'),
    rotation=RotationModel(
        281.0103, -0.0328, 61.4155, -0.0049, 329.5988, 6.1385108,
        'plus 88-day libration terms (amplitude 0.0107 deg, IAU) not evaluated by the pipeline',
        'Archinal et al. (2018) Celest. Mech. Dyn. Astron. 130:22 (IAU WGCCRE 2015), Table 2; W0 from Margot (2009)'),
    body_fixed_frame=('Horizons: IAU_MERCURY (west-positive; converted to east-positive) = the IAU 2015 model (pck00011: '
                      'W0 329.5988, Wdot 6.1385108 deg/d), identified by the T3 frame-tie test (Horizons quantity 14 '
                      'reproduced to 1e-6 deg; the IAU 2009 model is off by 0.135 deg). MLA GDR: MESSENGER PCK '
                      'pck00010_msgr_v21 (MLA RDR SIS), whose Mercury block (v2.0-2.3) has the same W0, Wdot and pole: '
                      'MLA -> Horizons longitude offset 0 (science/worlds/frame_tie.py).'),
    spice_kernels='not loaded; Horizons evaluates IAU_MERCURY (DE441)',
    orbit=Orbit(0.38709927, 0.20563593, 87.9691,
                'JPL "Keplerian elements for approximate positions of the major planets" (Standish), J2000 mean elements; '
                'sidereal period 87.9691 d'),
    relief_max_m=5_100.0, relief_min_m=-5_700.0,
    relief_source=('Measured 2026-11-16 on the downloaded products, heights above 2 439.4 km: USGS DEM 665 m v2 -5 382 to '
                   '+4 497 m (Becker et al. 2016, LPSC 47 #2959); MLA hdem_75n_250m -5 651 to +2 692 m. Bounds +5.1 / -5.7 km '
                   'include margin (checked in science/worlds/tests/test_mercury_data.py).'),
    atmosphere='none',
    dem_stack=[DemProduct('mercury_pgda85_prokofiev', 'near', 125.0, '83.5-87 N, 40-83 E', 'km (band 1), reference from ISIS label'),
               DemProduct('mercury_mla_gdr_v2', 'far', 250.0, '75-90 N', 'm above 2 440.0 km (re-referenced)'),
               DemProduct('mercury_mla_gdr_v1', 'far', 250.0, '45-90 N', 'm above the OFFSET in each label'),
               DemProduct('mercury_usgs_dem_665m_v2', 'global', 665.0, 'global', 'm (DN * 0.5) on the 2 439.4 km sphere'),
               DemProduct('mercury_pgda88_south_pole', 'near', 250.0, '75-90 S', 'm above 2 439.4 km'),
               DemProduct('mercury_pgda85_prokofiev:radar3b', 'ice', 125.0, 'Prokofiev only',
                          'Arecibo radar reflectance (Harmon et al. 2011) resampled by PGDA 85')],
    comms=[CommsAsset('dsn-dte', 'direct-to-earth', True,
                      'Earth centre above the local terrain skyline AND Sun-Earth-probe angle >= threshold at superior '
                      'conjunction. Inferior conjunctions below the threshold are flagged (Sun near the ground beam, '
                      'module 105 noise) but not assessed.',
                      {'sep_outage_x_band_deg': SEP_X_BAND_DEG, 'sep_outage_ka_band_deg': SEP_KA_BAND_DEG}, SEP_SOURCE,
                      ENGINEERING),
           CommsAsset('relay', 'relay', False, 'no Mercury relay exists; direct-to-Earth only')],
    default_requirements={
        'sun_center_pct_ge_70': {'value': 70, 'unit': '% of hourly samples', 'source': 'Moon team requirement, copied',
                                 'label': ENGINEERING + ' (no Mercury mission requirement exists)'},
        'both_center_pct_ge_40': {'value': 40, 'unit': '% of hourly samples', 'source': 'Moon team requirement, copied',
                                  'label': ENGINEERING + ' (no Mercury mission requirement exists)'},
        'sep_outage_threshold_deg': {'value': SEP_X_BAND_DEG, 'unit': 'deg', 'source': SEP_SOURCE, 'label': ENGINEERING}},
    terrain_provider=_terrain, frame_tie=FRAME_TIE,
)
