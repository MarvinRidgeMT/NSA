"""Frame tie: which rotation model does JPL Horizons use for a body, and how far is a DEM's body-fixed frame from it?

Method (independent of any DEM and of the topocentric tables used by the solver):
  1. Horizons, observer = geocentre (500@399), TIME_TYPE=TT (observer tables allow UT/TT only; TT - TDB < 2 ms): quantity 14 = apparent sub-observer point (planetodetic;
     for a body with a = b the longitude is the planetocentric one; west-positive bodies report W-longitude).
  2. Horizons VECTORS, target wrt geocentre, VEC_CORR='LT+S' (light time + stellar aberration = the apparent direction),
     VEC_TABLE=3 (LT column), ICRF, same TDB grid.
  3. For each candidate text PCK: orientation at t - LT (the light-emission time), body-fixed direction of
     -(apparent target vector) -> sub-observer east longitude / latitude. The residual vs (1) identifies Horizons' model.
  4. The DEM's frame is the model its producers name (MLA: pck00010_msgr_v21, RDR SIS; MOLA MEGDR: "IAU2000"); the
     longitude offset of that frame from Horizons' at epoch t is W_dem(t) - W_horizons(t) (same pole to the stated
     tolerance), reported and applied as a sensitivity, never silently.
"""
from __future__ import annotations

import math
import os

import numpy as np

from ..anysite.ephem import fetch_cached, params_key
from . import pck as PCK

C_KM_S = 299_792.458


def _base(command, center, start, stop, step, time_type='TDB'):
    return {'format': 'text', 'COMMAND': f"'{command}'", 'OBJ_DATA': 'NO', 'MAKE_EPHEM': 'YES', 'CENTER': f"'{center}'",
            'START_TIME': f"'{start}'", 'STOP_TIME': f"'{stop}'", 'STEP_SIZE': f"'{step}'", 'CSV_FORMAT': 'YES',
            'TIME_TYPE': time_type}


def _rows(text):
    lines = text.splitlines()
    soe = lines.index('$$SOE'); eoe = lines.index('$$EOE')
    return lines[soe + 1:eoe], lines[:soe]


def horizons_sub_observer(naif, start, stop, step, cache_dir, allow_network=True):
    # observer tables accept only UT or TT; TT - TDB < 2 ms (rotation error < 1e-5 deg even for Mars)
    p = {**_base(str(naif), '500@399', start, stop, step, 'TT'), 'EPHEM_TYPE': 'OBSERVER', 'QUANTITIES': "'14,20'",
         'ANG_FORMAT': 'DEG', 'EXTRA_PREC': 'YES', 'CAL_FORMAT': 'JD', 'APPARENT': 'AIRLESS'}
    body, src = fetch_cached(p, cache_dir=cache_dir, allow_network=allow_network)
    text = body.decode()
    rows, head = _rows(text)
    hdr = next(l for l in reversed(head) if 'Date_' in l)
    names = [h.strip() for h in hdr.split(',')]
    i_lon = next(i for i, n in enumerate(names) if n.startswith('ObsSub-LON'))
    i_lat = next(i for i, n in enumerate(names) if n.startswith('ObsSub-LAT'))
    out = []
    for l in rows:
        f = [x.strip() for x in l.split(',')]
        out.append((float(f[0]), float(f[i_lon]), float(f[i_lat])))
    pole = next((l.split(':', 1)[1].strip() for l in head if l.startswith('Target pole/equ')), None)
    src.update({'params_key': params_key(p), 'target_pole_equ': pole})
    return np.array(out), src


def horizons_vectors(naif, start, stop, step, cache_dir, allow_network=True, corr='LT+S'):
    p = {**_base(str(naif), '500@399', start, stop, step), 'EPHEM_TYPE': 'VECTORS', 'VEC_TABLE': "'3'",
         'VEC_CORR': f"'{corr}'", 'REF_SYSTEM': "'ICRF'", 'REF_PLANE': "'FRAME'", 'OUT_UNITS': "'KM-S'",
         'VEC_LABELS': 'NO'}
    body, src = fetch_cached(p, cache_dir=cache_dir, allow_network=allow_network)
    rows, _ = _rows(body.decode())
    out = []
    for l in rows:
        f = [x.strip() for x in l.split(',') if x.strip()]
        # JDTDB, Calendar, X, Y, Z, VX, VY, VZ, LT, RG, RR
        out.append([float(f[0])] + [float(v) for v in f[2:9]])
    src['params_key'] = params_key(p)
    return np.array(out), src


def planetodetic_lat(lat_c_deg, radii_km):
    """Geodetic latitude of the surface point at planetocentric latitude lat_c on the ellipsoid (a = b, c):
    tan(phi_d) = (a / c)^2 tan(phi_c)."""
    a, _, c = radii_km
    return np.degrees(np.arctan((a / c) ** 2 * np.tan(np.radians(lat_c_deg))))


def tie(naif, west_positive, pcks: dict, start, stop, step, cache_dir, allow_network=True, radii_km=None, corr='LT'):
    """Residuals (deg) of Horizons' sub-observer point vs each candidate PCK. pcks: {label: path}. corr: aberration
    correction of the vector table ('LT' = light time only; 'LT+S' adds stellar aberration). radii_km: Horizons body
    radii, to compare latitudes as planetodetic (quantity 14 reports planetodetic latitude)."""
    so, src_o = horizons_sub_observer(naif, start, stop, step, cache_dir, allow_network)
    vec, src_v = horizons_vectors(naif, start, stop, step, cache_dir, allow_network, corr)
    if not np.allclose(so[:, 0], vec[:, 0], atol=1e-6):
        raise ValueError('sub-observer and vector grids differ')
    jd = vec[:, 0]; lt_d = vec[:, 7] / 86400.0
    v_obs = -vec[:, 1:4]                                     # target centre -> observer (apparent direction reversed)
    h_lon_e = (-so[:, 1]) % 360.0 if west_positive else so[:, 1] % 360.0
    out = {'vector_correction': corr, 'latitude_compared': 'planetodetic' if radii_km else 'planetocentric', 'n': int(len(jd)), 'jd_tdb': [float(jd[0]), float(jd[-1])], 'horizons_target_pole_equ': src_o.get('target_pole_equ'),
           'models': {}, 'raw': [{k: s.get(k) for k in ('path', 'sha256', 'retrieved_utc', 'params_key')} for s in (src_o, src_v)]}
    for name, path in pcks.items():
        lat, lon = PCK.sub_point(path, naif, jd - lt_d, v_obs)
        if radii_km is not None:
            lat = planetodetic_lat(lat, radii_km)
        dlon = (lon - h_lon_e + 180.0) % 360.0 - 180.0
        dlat = lat - so[:, 2]
        out['models'][name] = {'pck': os.path.basename(path), 'median_dlon_deg': round(float(np.median(dlon)), 6),
                               'max_abs_dlon_deg': round(float(np.max(np.abs(dlon))), 6),
                               'median_dlat_deg': round(float(np.median(dlat)), 6),
                               'max_abs_dlat_deg': round(float(np.max(np.abs(dlat))), 6)}
    best = min(out['models'], key=lambda m: out['models'][m]['max_abs_dlon_deg'])
    out['horizons_model'] = best
    return out


def longitude_offset_deg(naif, pck_dem, pck_horizons, jd_tdb):
    """W_dem - W_horizons at jd (deg): a point at DEM east longitude L sits at Horizons east longitude L + offset (pole
    difference not included; report it separately with pole_difference_deg)."""
    _, _, w_d = PCK.rotation(pck_dem, naif, jd_tdb)
    _, _, w_h = PCK.rotation(pck_horizons, naif, jd_tdb)
    return float((w_d - w_h + 180.0) % 360.0 - 180.0)


def pole_difference_deg(naif, pck_a, pck_b, jd_tdb):
    a1, d1, _ = PCK.rotation(pck_a, naif, jd_tdb)
    a2, d2, _ = PCK.rotation(pck_b, naif, jd_tdb)
    u = lambda a, d: np.array([math.cos(math.radians(d)) * math.cos(math.radians(a)),
                               math.cos(math.radians(d)) * math.sin(math.radians(a)), math.sin(math.radians(d))])
    return float(math.degrees(math.acos(min(1.0, float(u(float(a1), float(d1)) @ u(float(a2), float(d2)))))))
