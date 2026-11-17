"""Mars seasons via the areocentric solar longitude Ls.

Ls from UTC with the Allison & McEwen (2000) algorithm as used by NASA GISS Mars24 (Planet. Space Sci. 48, 215-235;
https://www.giss.nasa.gov/tools/mars24/help/algorithm.html, steps A-B):
    dt_J2000 = JD_TT - 2451545.0                                         (TT = UTC + 69.184 s since 2017)
    M        = 19.3871 + 0.52402073 dt                                   mean anomaly (deg)
    alpha_FMS= 270.3871 + 0.524038496 dt                                 fictitious mean sun
    PBS      = sum_i A_i cos(0.985626 dt / tau_i + phi_i)                planetary perturbations
    nu - M   = (10.691 + 3.0e-7 dt) sin M + 0.623 sin 2M + 0.050 sin 3M + 0.005 sin 4M + 0.0005 sin 5M + PBS
    Ls       = alpha_FMS + (nu - M)
Independent check (tests): sin(lat_subsolar) = sin(epsilon) sin(Ls) with epsilon = 25.19 deg, against the sub-solar
latitude JPL Horizons computes from its own ephemeris and the IAU pole (planetocentric).
Seasons (northern hemisphere): Ls 0-90 spring, 90-180 summer, 180-270 autumn, 270-360 winter; perihelion at Ls ~251.
"""
from __future__ import annotations

import numpy as np

TT_MINUS_UTC_S = 69.184            # 37 leap seconds + 32.184 s (valid from 2017-01-01; no leap second announced since)
OBLIQUITY_DEG = 25.19              # Mars obliquity (Allison & McEwen 2000, Mars24)
_A = (0.0071, 0.0057, 0.0039, 0.0037, 0.0021, 0.0020, 0.0018)
_TAU = (2.2353, 2.7543, 1.1177, 15.7866, 2.1354, 2.4694, 32.8493)
_PHI = (49.409, 168.173, 191.837, 21.736, 15.704, 95.528, 49.095)
SOURCE = 'Allison, M., McEwen, M. (2000), Planet. Space Sci. 48, 215-235 (Mars24 algorithm, NASA GISS)'
SEASONS = ('northern spring (Ls 0-90)', 'northern summer (Ls 90-180)', 'northern autumn (Ls 180-270)',
           'northern winter (Ls 270-360)')


def ls_deg(t_unix, tt_minus_utc_s=TT_MINUS_UTC_S):
    t = np.asarray(t_unix, float)
    jd_tt = t / 86400.0 + 2440587.5 + tt_minus_utc_s / 86400.0
    dt = jd_tt - 2451545.0
    M = np.radians(19.3871 + 0.52402073 * dt)
    a_fms = 270.3871 + 0.524038496 * dt
    pbs = sum(A * np.cos(np.radians(0.985626 * dt / tau + phi)) for A, tau, phi in zip(_A, _TAU, _PHI))
    eoc = ((10.691 + 3.0e-7 * dt) * np.sin(M) + 0.623 * np.sin(2 * M) + 0.050 * np.sin(3 * M) + 0.005 * np.sin(4 * M)
           + 0.0005 * np.sin(5 * M) + pbs)
    return (a_fms + eoc) % 360.0


def subsolar_lat_deg(ls):
    return np.degrees(np.arcsin(np.sin(np.radians(OBLIQUITY_DEG)) * np.sin(np.radians(ls))))


def season_index(ls):
    return (np.asarray(ls, float) // 90.0).astype(int) % 4
