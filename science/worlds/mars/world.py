"""Mars as a `World` (prompt §3.3). Different physics, clearly labelled:
  * geometry: the same method as the Moon/Mercury (terrain rays on the MOLA reference sphere, Horizons Sun/Earth);
  * atmosphere: present. Horizons is queried AIRLESS (no refraction): at ~6 mbar the refractivity of CO2 is
    (n - 1) ~ 4.5e-4 x (6.1/1013) x (273/210) ~ 3.5e-6, ~1/80 of Earth's, so horizon refraction ~ 35'/80 ~ 0.4' ~ 0.007 deg
    (estimate; no Mars refraction model is shipped). Seasons via Ls (science/worlds/mars/seasons.py);
  * energy depends on the atmospheric optical depth tau, so it is an ENGINEERING ASSUMPTION with tau an explicit input
    (science/worlds/mars/energy.py; direct beam only, no sky/diffuse MODEL is shipped);
  * comms: direct-to-Earth geometry + the SEP outage rule; relay orbiters NOT AVAILABLE (no ephemerides wired).

Horizons facts (read from a live coord@499 response header, recorded in each bundle's horizons_raw.center_site_header):
IAU_MARS {West-longitude positive}, radii 3396.19 / 3396.19 / 3376.20 km; east longitude entered negative; the site is
passed CYLINDRICAL so its radius is exactly R + h on the MOLA sphere. Horizons' rotation model = IAU 2015 (pck00011,
frame-tie test); MOLA MEGDR coordinates use IAU 2000 (label) = the pck00010 Mars block; the -0.003 deg longitude offset
between the two is applied to the Horizons site longitude (World.horizons_lon_offset_deg) and reported.
"""
from __future__ import annotations

from ..base import ENGINEERING, CommsAsset, DemProduct, Orbit, RotationModel, World
from ..mercury.world import SEP_KA_BAND_DEG, SEP_SOURCE, SEP_X_BAND_DEG

R_MOLA_M = 3_396_000.0          # MOLA MEGDR reference sphere (label OFFSET; radius files are radius - 3 396 000 m)


def _terrain(lat, lon, max_range_m, member=None):
    from .terrain import provider
    return provider(lat, lon, max_range_m, member)


FRAME_TIE = {'dem_pck': 'mars_naif_pck/pck00010.tpc', 'horizons_pck': 'mars_naif_pck/pck00011.tpc',
             'dem_frame_source': 'MOLA MEGDR labels: "Map coordinates use the IAU2000 reference system" (Seidelmann et al. '
                                 '2002: W0 176.630, Wdot 350.89198226, pole 317.68143/52.88650, unchanged in the IAU 2009 '
                                 'report = NAIF pck00010 BODY499). CTX DEMs are aligned to HRSC, itself tied to MOLA.',
             'horizons_model_evidence': 'science/worlds/tests/test_frame_tie.py (quantity 14 reproduced by pck00011 to '
                                        '5e-5 deg; pck00010 off by 0.0024 deg median)',
             'offset_note': 'W_IAU2000(t) - W_IAU2015(t) = -0.0032 to -0.0035 deg over 2026-2027 (~180 m at 18 N); pole '
                            'difference 0.0006 deg (~36 m), not applied'}

MARS = World(
    name='mars', naif_id=499, horizons_center='coord@499', horizons_coord_type='CYLINDRICAL', horizons_longitude='west',
    horizons_radii_km=(3396.19, 3396.19, 3376.20), radius_m=R_MOLA_M,
    shape=('sphere R = 3 396 000 m for heights and rays (MOLA MEGDR reference radius). Horizons uses the IAU ellipsoid '
           '3396.19/3396.19/3376.20 km; the site is passed in cylindrical coordinates so its radius is exact. Mars is '
           'oblate (f = 0.0059): geodetic - planetocentric latitude ~0.24 deg at 18 N, handled by the az/el frame tie.'),
    rotation=RotationModel(
        317.269202, -0.10927547, 54.432516, -0.05827105, 176.049863, 350.891982443297,
        'plus periodic terms (largest 0.419 deg in alpha0, 1.591 deg in delta0, 0.585 deg in W, period ~7e5 yr) '
        'evaluated from NAIF pck00011 by science/worlds/pck.py for the frame tie',
        'Archinal et al. (2018) Celest. Mech. Dyn. Astron. 130:22 (IAU WGCCRE 2015), Table 2 (Kuchynka et al. 2014)'),
    body_fixed_frame=('Horizons: IAU_MARS (west-positive; converted to east-positive), IAU 2015 model. DEMs: MOLA MEGDR '
                      'IAU 2000 planetocentric east-positive; longitude tie applied (frame_tie)'),
    spice_kernels='not loaded; NAIF text PCKs pck00010/pck00011 read by science/worlds/pck.py for the tie only',
    orbit=Orbit(1.52371034, 0.09339410, 686.980,
                'JPL "Keplerian elements for approximate positions of the major planets" (Standish), J2000 mean elements; '
                'sidereal period 686.980 d'),
    relief_max_m=21_500.0, relief_min_m=-23_400.0,
    relief_source=('Measured 2026-11-17 on MOLA MEGDR radius (megr) grids, radius - 3 396 000 m: 16 ppd max +21 280 m '
                   '(Olympus Mons, 17.34 N 226.97 E), min -23 170 m (76.97 N: the oblate figure, not a basin); 4 ppd '
                   '+21 241 / -22 931 m. Bounds +21.5 / -23.4 km include margin (science/worlds/tests/test_mars.py).'),
    atmosphere='mars',
    atmosphere_note=('CO2 atmosphere ~6 mbar: horizon refraction estimated ~0.007 deg (not applied; Horizons AIRLESS). Dust '
                     'opacity tau 0.3 (clear) to > 5 (global storms) controls surface irradiance; tau is an explicit input '
                     'of the energy section (ENGINEERING ASSUMPTION). No sky-brightness MODEL is shipped.'),
    dem_stack=[DemProduct('mars_ctx_jezero_sci_20m', 'near', 20.0, 'Jezero crater 77.0-78.6 E, 17.6-19.3 N',
                          'm above the MOLA areoid (tested) -> + areoid radius (MOLA 16 ppd) - 3 396 000 m'),
               DemProduct('mars_ctx_jezero_trn_20m', 'near', 20.0, 'Mars 2020 landing ellipse region',
                          'm above the MOLA areoid (tested)'),
               DemProduct('mars_mola_megdr_128_44n000', 'far', 463.0, '0-44 N, 0-90 E', 'radius - 3 396 000 m'),
               DemProduct('mars_mola_megdr_016', 'global', 3705.0, 'global', 'radius - 3 396 000 m')],
    comms=[CommsAsset('dsn-dte', 'direct-to-earth', True,
                      'Earth centre above the local terrain skyline AND Sun-Earth-probe angle >= threshold (solar '
                      'conjunction outage). Atmospheric attenuation of the link is not modelled.',
                      {'sep_outage_x_band_deg': SEP_X_BAND_DEG, 'sep_outage_ka_band_deg': SEP_KA_BAND_DEG}, SEP_SOURCE,
                      ENGINEERING),
           CommsAsset('relay-mro', 'relay', False, 'Mars Reconnaissance Orbiter (UHF relay): ephemeris not wired'),
           CommsAsset('relay-maven', 'relay', False, 'MAVEN (UHF relay): ephemeris not wired'),
           CommsAsset('relay-tgo', 'relay', False, 'ExoMars Trace Gas Orbiter (UHF relay): ephemeris not wired'),
           CommsAsset('relay-mex', 'relay', False, 'Mars Express (UHF relay): ephemeris not wired')],
    default_requirements={
        'sun_center_pct_ge_70': {'value': 70, 'unit': '% of hourly samples', 'source': 'Moon team requirement, copied',
                                 'label': ENGINEERING + ' (no Mars mission requirement in this repo)'},
        'both_center_pct_ge_40': {'value': 40, 'unit': '% of hourly samples', 'source': 'Moon team requirement, copied',
                                  'label': ENGINEERING + ' (no Mars mission requirement in this repo)'},
        'sep_outage_threshold_deg': {'value': SEP_X_BAND_DEG, 'unit': 'deg', 'source': SEP_SOURCE, 'label': ENGINEERING}},
    terrain_provider=_terrain, frame_tie=FRAME_TIE,
)
