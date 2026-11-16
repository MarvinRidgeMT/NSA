"""Sun / Earth / star geometry for the v2 Blender scene. Pure Python (math only), unit-tested in blender/tests/test_astro.py.

Everything here is computed from JPL Horizons numbers carried by a solver bundle (az, el, angular radius, range per sample)
or from published constants. Nothing is read back from a Blender lamp.

Frame: local ENU at the observer, x east, y north, z up (the site radius vector); azimuth clockwise from local north
(JPL Horizons surface-observer convention, docs/SCIENCE_RESULTS_CONTRACT.md).
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

AU_M = 149_597_870_700.0
TSI_W_M2 = 1361.0             # total solar irradiance at 1 AU (Kopp & Lean 2011, GRL 38, L01706)
EARTH_GEOMETRIC_ALBEDO = 0.367  # Allen's Astrophysical Quantities (4th ed., 2000), Earth geometric albedo, visual
LUMINOUS_EFFICACY_SUN = 93.0    # lm/W for the extraterrestrial solar spectrum (1361 W/m^2 -> ~127 klux)
R_MOON_M = 1_737_400.0
R_EARTH_EQ_M = 6_378_137.0


def enu_direction(az_deg, el_deg):
    """Unit vector toward local az/el in ENU (x east, y north, z up)."""
    a, e = math.radians(az_deg), math.radians(el_deg)
    return (math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e))


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _norm(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _norm(a)
    return tuple(x / n for x in a)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def angle_deg(a, b):
    c = max(-1.0, min(1.0, _dot(_unit(a), _unit(b))))
    return math.degrees(math.acos(c))


def solar_irradiance(range_au):
    """W/m^2 at the observer for a Sun at `range_au`."""
    return TSI_W_M2 / (range_au * range_au)


def earth_phase(sun_az, sun_el, sun_range_au, earth_az, earth_el, earth_range_au):
    """Earth's phase as seen by the observer, from the Horizons Sun and Earth vectors (topocentric).

    Returns dict: phaseAngleDeg (Sun-Earth-observer), illuminatedFraction (1 + cos a)/2, elongationDeg (Sun-observer-Earth),
    sunEarthRangeAu. Positions are the Horizons apparent (light-time corrected, airless) directions; the light-time
    difference between the two bodies is ignored (error << 0.01 deg in the phase angle)."""
    S = tuple(sun_range_au * c for c in enu_direction(sun_az, sun_el))
    E = tuple(earth_range_au * c for c in enu_direction(earth_az, earth_el))
    to_sun = _sub(S, E)
    to_obs = tuple(-c for c in E)
    a = angle_deg(to_sun, to_obs)
    return {'phaseAngleDeg': a, 'illuminatedFraction': (1 + math.cos(math.radians(a))) / 2,
            'elongationDeg': angle_deg(S, E), 'sunEarthRangeAu': _norm(to_sun)}


def lambert_sphere_phase(alpha_deg):
    """Phase function of a Lambert sphere, normalised to 1 at alpha = 0 (Russell 1916)."""
    a = math.radians(alpha_deg)
    return (math.sin(a) + (math.pi - a) * math.cos(a)) / math.pi


def earthshine_irradiance(sun_earth_range_au, phase_angle_deg, earth_angular_radius_deg, albedo=EARTH_GEOMETRIC_ALBEDO):
    """Irradiance (W/m^2, normal to the Earth direction) of sunlight reflected by Earth: E_sun(at Earth) * p * Phi_L(a) * sin^2(rho).

    MODEL: a Lambert sphere of geometric albedo p. The real Earth (clouds, oceans) departs from this by tens of percent."""
    return solar_irradiance(sun_earth_range_au) * albedo * lambert_sphere_phase(phase_angle_deg) * math.sin(math.radians(earth_angular_radius_deg)) ** 2


def sun_disc_angle_deg(radius_deg):
    """Blender SUN lamp `angle` is the full angular diameter of the disc."""
    return 2.0 * radius_deg


def parse_utc(s):
    s = s.strip().replace('Z', '+00:00')
    if 'T' not in s:
        s = s.replace(' ', 'T')
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class SampleError(ValueError):
    pass


def pick_sample(samples, utc, key='utc'):
    """Index of the bundle sample at `utc`. Exact match, or the nearest sample if within half a step (offset recorded).
    Never interpolates and never extrapolates: a time outside the sampled span is an error."""
    t = parse_utc(utc).timestamp()
    ts = [parse_utc(s[key]).timestamp() for s in samples]
    if not ts:
        raise SampleError('bundle has no samples')
    step = (ts[-1] - ts[0]) / max(1, len(ts) - 1)
    if t < ts[0] - step / 2 or t > ts[-1] + step / 2:
        raise SampleError(f'{utc} is outside the bundle samples {samples[0][key]} .. {samples[-1][key]} (no extrapolation)')
    k = min(range(len(ts)), key=lambda i: abs(ts[i] - t))
    off = t - ts[k]
    if abs(off) > step / 2 + 1e-6:
        raise SampleError(f'{utc} is {off:.0f} s from the nearest sample (more than half a step)')
    return k, off


# ---------------------------------------------------------------- ICRF -> local ENU (starfield orientation only)
def julian_date(dt):
    return dt.timestamp() / 86400.0 + 2440587.5


def sun_icrf_unit(dt):
    """Geocentric Sun direction in ICRF/J2000 equatorial axes (Astronomical Almanac low-precision formula, ~0.01 deg),
    with the ecliptic longitude of date moved to J2000 by the general precession (1.396971 deg / century)."""
    jd = julian_date(dt)
    n = jd - 2451545.0
    L = 280.460 + 0.9856474 * n
    g = math.radians(357.528 + 0.9856003 * n)
    lam = L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)
    lam -= 1.396971 * (n / 36525.0)          # equinox of date -> J2000 (dominant term)
    eps = math.radians(23.4392911)           # J2000 obliquity
    lr = math.radians(lam)
    return _unit((math.cos(lr), math.cos(eps) * math.sin(lr), math.sin(eps) * math.sin(lr)))


def moon_pole_icrf(dt):
    """IAU WGCCRE 2009 Moon north pole (Archinal et al. 2011, Celest Mech Dyn Astr 109, 101; Table 2), main periodic terms.
    Returns (unit vector, alpha0_deg, delta0_deg). d = days from J2000 (UTC used for TDB: 69 s error, negligible here)."""
    d = julian_date(dt) - 2451545.0
    T = d / 36525.0
    E = {1: 125.045 - 0.0529921 * d, 2: 250.089 - 0.1059842 * d, 3: 260.008 + 13.0120009 * d, 4: 176.625 + 13.3407154 * d,
         6: 311.589 + 26.4057084 * d, 7: 134.963 + 13.0649930 * d, 10: 15.134 - 0.1589763 * d, 13: 25.053 + 12.9590088 * d}
    s = {k: math.sin(math.radians(v)) for k, v in E.items()}
    c = {k: math.cos(math.radians(v)) for k, v in E.items()}
    a0 = (269.9949 + 0.0031 * T - 3.8787 * s[1] - 0.1204 * s[2] + 0.0700 * s[3] - 0.0172 * s[4] + 0.0072 * s[6]
          - 0.0052 * s[10] + 0.0043 * s[13])
    d0 = (66.5392 + 0.0130 * T + 1.5419 * c[1] + 0.0239 * c[2] - 0.0278 * c[3] + 0.0068 * c[4] - 0.0029 * c[6]
          + 0.0009 * c[7] + 0.0008 * c[10] - 0.0009 * c[13])
    ar, dr = math.radians(a0), math.radians(d0)
    return (math.cos(dr) * math.cos(ar), math.cos(dr) * math.sin(ar), math.sin(dr)), a0, d0


def moon_pole_enu(lat_deg, lon_deg):
    """Moon-fixed +Z (north pole) expressed in local ENU at (lat, lon): (0, cos lat, sin lat)."""
    la = math.radians(lat_deg)
    return (0.0, math.cos(la), math.sin(la))


def triad(v1_a, v2_a, v1_b, v2_b):
    """Rotation matrix M (rows) with M @ a = b for the TRIAD pair (v1 exact, v2 used for the roll)."""
    def frame(v1, v2):
        t1 = _unit(v1)
        t2 = _unit(_cross(v1, v2))
        t3 = _cross(t1, t2)
        return (t1, t2, t3)
    A, B = frame(v1_a, v2_a), frame(v1_b, v2_b)
    # M = sum_k B_k (outer) A_k
    return tuple(tuple(sum(B[k][i] * A[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def matvec(M, v):
    return tuple(sum(M[i][j] * v[j] for j in range(3)) for i in range(3))


def icrf_to_enu(dt, lat_deg, lon_deg, sun_az, sun_el):
    """Rotation ICRF -> local ENU from two directions known in both frames: the Moon's pole (IAU 2009 in ICRF; geometry in
    ENU) is matched exactly, the Sun (low-precision ICRF; Horizons az/el in ENU) fixes the roll. Used ONLY to orient the
    starfield. Returns (M, check) where check is the Sun-pole angle in each frame: their difference measures the combined
    error of the two models and of the Horizons direction (expected < 0.2 deg: the Sun's parallax over the Earth-Moon
    distance is <= 0.15 deg and the low-precision Sun is ~0.01 deg)."""
    p_icrf, a0, d0 = moon_pole_icrf(dt)
    s_icrf = sun_icrf_unit(dt)
    p_enu = moon_pole_enu(lat_deg, lon_deg)
    s_enu = enu_direction(sun_az, sun_el)
    M = triad(p_icrf, s_icrf, p_enu, s_enu)
    check = {'sunPoleAngleIcrfDeg': angle_deg(s_icrf, p_icrf), 'sunPoleAngleEnuDeg': angle_deg(s_enu, p_enu),
             'poleAlpha0Deg': a0, 'poleDelta0Deg': d0}
    check['differenceDeg'] = abs(check['sunPoleAngleIcrfDeg'] - check['sunPoleAngleEnuDeg'])
    return M, check


def radec_unit(ra_deg, dec_deg):
    a, d = math.radians(ra_deg), math.radians(dec_deg)
    return (math.cos(d) * math.cos(a), math.cos(d) * math.sin(a), math.sin(d))


def star_irradiance_w_m2(v_mag):
    """Irradiance of a star of visual magnitude V: 2.54e-6 lux at V = 0 (Allen 2000), converted with the solar luminous
    efficacy (stars are not solar-spectrum: MODEL, tens of percent)."""
    return 2.54e-6 * 10 ** (-0.4 * v_mag) / LUMINOUS_EFFICACY_SUN
