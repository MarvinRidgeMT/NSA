"""Mercury physics checks (prompt §3.2): Sun angular size over the eccentric orbit, the 3:2 spin-orbit resonance and the
~176-day solar day, and solar-conjunction flags for direct-to-Earth links.
"""
from __future__ import annotations

import math
from typing import Dict, List

import numpy as np

from ..base import AU_KM, ENGINEERING, R_SUN_KM
from .world import MERCURY, SEP_KA_BAND_DEG, SEP_SOURCE, SEP_X_BAND_DEG


def sun_angular_diameter_deg(r_au):
    """Full angular diameter of the Sun's disc from distance r (AU): 2 asin(R_sun / r)."""
    return np.degrees(2 * np.arcsin(R_SUN_KM / (np.asarray(r_au, float) * AU_KM)))


def analytic_sun_size_range(world=MERCURY) -> Dict[str, float]:
    q, Q = world.orbit.perihelion_au, world.orbit.aphelion_au
    return {'perihelion_au': q, 'aphelion_au': Q, 'max_diam_deg': float(sun_angular_diameter_deg(q)),
            'min_diam_deg': float(sun_angular_diameter_deg(Q)), 'ratio_max_min': float(sun_angular_diameter_deg(q) /
                                                                                       sun_angular_diameter_deg(Q)),
            'ratio_analytic_(1+e)/(1-e)': (1 + world.orbit.e) / (1 - world.orbit.e)}


def solar_day_days(rot_days, orb_days):
    """Synodic (solar) day for prograde rotation: 1 / (1/P_rot - 1/P_orb)."""
    return 1.0 / (1.0 / rot_days - 1.0 / orb_days)


def resonance(world=MERCURY) -> Dict[str, float]:
    p_rot = world.rotation.sidereal_period_days; p_orb = world.orbit.period_days
    return {'sidereal_rotation_days': p_rot, 'orbital_period_days': p_orb, 'orbit_over_rotation': p_orb / p_rot,
            'solar_day_days': solar_day_days(p_rot, p_orb), 'solar_day_over_orbit': solar_day_days(p_rot, p_orb) / p_orb}


def perihelion_times(t_unix, range_au):
    """Local minima of the Sun distance (Horizons samples), refined by a parabola through the 3 samples around each
    minimum (interpolation between real samples only). Returns unix times."""
    t = np.asarray(t_unix, float); r = np.asarray(range_au, float); out = []
    for k in range(1, len(r) - 1):
        if r[k] < r[k - 1] and r[k] <= r[k + 1]:
            y0, y1, y2 = r[k - 1], r[k], r[k + 1]; den = y0 - 2 * y1 + y2
            off = 0.5 * (y0 - y2) / den if den > 0 else 0.0
            out.append(float(t[k] + off * (t[k + 1] - t[k])))
    return out


def solar_day_from_azimuth(t_unix, az_deg, orbit_days):
    """Solar day from the Sun's azimuth at a near-polar site. The azimuth rate is not uniform (equation of centre, up to
    2e rad = 23.6 deg for Mercury, periodic with the orbit), so the first 360 deg crossing is NOT the solar day. Over
    exactly two orbital periods the periodic term cancels: T_solar = 360 * (2 P_orb) / delta_az(2 P_orb).
    delta_az at t0 + 2 P_orb is linearly interpolated between the two bracketing hourly samples."""
    t = np.asarray(t_unix, float); az = np.degrees(np.unwrap(np.radians(np.asarray(az_deg, float))))
    span = 2 * orbit_days * 86400.0
    t1 = t[0] + span
    if t1 > t[-1]:
        return None
    a1 = float(np.interp(t1, t, az))
    dz = abs(a1 - az[0])
    return {'solar_day_days': 360.0 * 2 * orbit_days / dz, 'delta_az_deg_over_2_orbits': dz,
            'orbit_days_used': orbit_days}


def conjunctions(rows: List[dict], threshold_deg=SEP_X_BAND_DEG) -> Dict[str, object]:
    """Flag samples with SEP < threshold. Kind: superior if Earth-Mercury distance > 1 AU (Mercury beyond the Sun; near
    conjunction delta is ~1.3-1.47 AU superior vs ~0.53-0.69 AU inferior, so 1 AU separates them unambiguously).
    Also lists every local SEP minimum (conjunction epoch on the sample grid)."""
    t = np.array([r['t'] for r in rows]); sep = np.array([r['sep_deg'] for r in rows]); dl = np.array([r['delta_au'] for r in rows])
    below = sep < threshold_deg
    kind = np.where(dl > 1.0, 'superior', 'inferior')
    spans = []
    i = 0
    while i < len(t):
        if below[i]:
            j = i
            while j + 1 < len(t) and below[j + 1]:
                j += 1
            spans.append({'start_utc': rows[i]['utc'], 'stop_utc': rows[j]['utc'], 'kind': str(kind[i]),
                          'min_sep_deg': round(float(sep[i:j + 1].min()), 4),
                          'duration_days_on_grid': round(float(t[j] - t[i]) / 86400.0, 4),
                          'counts_as_outage': bool(kind[i] == 'superior'),
                          'open_start': i == 0, 'open_end': j == len(t) - 1})
            i = j + 1
        else:
            i += 1
    minima = []
    for k in range(1, len(t) - 1):
        if sep[k] < sep[k - 1] and sep[k] <= sep[k + 1] and sep[k] < 30.0:
            minima.append({'utc': rows[k]['utc'], 't': float(t[k]), 'sep_deg': round(float(sep[k]), 4), 'kind': str(kind[k]),
                           'delta_au': round(float(dl[k]), 6)})
    outage = below & (kind == 'superior')
    return {'threshold_deg': threshold_deg, 'threshold_ka_band_deg': SEP_KA_BAND_DEG, 'source': SEP_SOURCE,
            'label': ENGINEERING, 'spans': spans, 'minima': minima, 'outage_flags': outage.tolist(),
            'inferior_flags': (below & (kind == 'inferior')).tolist(),
            'note': ('Outage = superior conjunction with SEP below the X-band threshold (coronal scintillation, module 106). '
                     'Inferior conjunctions below the threshold put the Sun near the ground antenna beam (noise, module 105): '
                     'flagged, not assessed, not counted as outage.')}
