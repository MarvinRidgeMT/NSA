"""Phase 4b — LCRNS reference-constellation relays: propagation and topocentric visibility at a site.

ENGINEERING ASSUMPTION — reference constellation, not an operational schedule.

Source of initial states: NASA "LCRNS Reference Constellation 3.1" white paper (Ryden & Volle, GSFC, 3 Apr 2025,
NTRS 20250002698), Table 2: Moon-centred ICRF Cartesian states of SV-1..SV-5 at 2027-03-01 00:00:00.000 UTC (km, km/s).
Table 1 (Keplerian, Moon Principal Axis frame) is used as a frame consistency check.

Propagation (the prompt's fallback; NASA recommends GRGM-900c 25x25 + 6 point masses + SRP, not available offline):
Moon point mass + J2 (about the Moon's mean spin axis) + Earth and Sun third bodies, DOP853, rtol 1e-11.
Earth and Sun positions relative to the Moon: JPL Horizons geometric vectors (CENTER 500@301, ICRF), hourly, cubic
Hermite interpolation. Time is treated as uniform UTC (the constant 69 s UTC-TDB offset is ignored; no leap second
falls in the window).

Site frame: per hour, the rotation ICRF -> local ENU at the site is the least-squares (Wahba/SVD) fit between the
Horizons apparent az/el and the Horizons apparent topocentric ICRF directions of the Sun, Earth, Mars and Jupiter
(no lunar orientation model is assumed). Validated independently on LRO (Horizons az/el vs our transform of the
Horizons LRO vector) and by predicting a body left out of the fit.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np

from .. import horizons as H
from . import ephem_year as E

ROOT = Path(__file__).resolve().parents[2]
RAW = E.RAW
EPOCH_UTC = '2027-03-01T00:00:00Z'
R_MOON_KM = 1737.4
MU_MOON = 4902.800066          # km^3/s^2 (GRAIL-era lunar GM)
J2_MOON = 2.0330e-4            # unnormalised C20 magnitude, approximate (ENGINEERING ASSUMPTION)
R_J2 = 1738.0                  # km, reference radius of the GRAIL gravity models
MU_EARTH = 398600.4418
MU_SUN = 1.32712440018e11
FIT_BODIES = {'sun': '10', 'earth': '399', 'mars': '499', 'jupiter': '599'}
PAPER = {
    'source': 'NASA LCRNS Reference Constellation 3.1 white paper (Ryden & Volle, NASA GSFC, 3 Apr 2025), NTRS 20250002698, Table 2',
    'url': 'https://ntrs.nasa.gov/citations/20250002698',
    'epoch_utc': EPOCH_UTC, 'frame': 'Moon-centred ICRF', 'units': 'km, km/s',
    'states': {
        'SV-1': [-198.931445, 386.023132, 3458.355412, -1.539867, 0.022243, -0.091059],
        'SV-2': [1089.980598, -2260.918271, -18984.562823, 0.280301, -0.004049, 0.016575],
        'SV-3': [9187.665852, -260.470721, -8543.222759, 0.273629, 0.417588, -0.313828],
        'SV-4': [6484.019002, 14329.883921, -7966.345594, -0.258433, 0.033951, 0.235264],
        'SV-5': [-5074.242314, 14473.022751, -8638.530033, -0.229931, -0.026926, -0.264381],
    },
    # Table 1, Moon Principal Axis frame (deg, km): SMA ECC INC RAAN AOP TA
    'kepler_pa': {
        'SV-1': [11315.936501, 0.691982, 59.373229, 321.019197, 92.494031, 0.0],
        'SV-2': [11317.948675, 0.691982, 58.951732, 320.997768, 92.505016, 180.0],
        'SV-3': [11305.413654, 0.691982, 52.733096, 81.148790, 92.062891, 140.049207],
        'SV-4': [11326.302154, 0.691982, 52.513419, 81.138818, 92.068945, 195.992393],
        'SV-5': [11307.882863, 0.691982, 56.310396, 204.889626, 85.444071, 164.007607],
    },
    'recommended_model': 'DE421; GRGM-900c 25x25; point masses Sun, Venus, Earth, Mars, Jupiter, Saturn; spherical SRP Cr 1.8, 850 kg, 1 m^2',
}


# ------------------------------------------------------------------ Horizons
def _base(start=E.START, stop=E.STOP, step='1 h'):
    return {'format': 'text', 'OBJ_DATA': 'NO', 'MAKE_EPHEM': 'YES', 'CSV_FORMAT': 'YES', 'TIME_TYPE': 'UT',
            'START_TIME': f"'{start}'", 'STOP_TIME': f"'{stop}'", 'STEP_SIZE': f"'{step}'"}


def _fetch(params, tag):
    p = RAW / f'{tag}.txt'
    if p.exists():
        return p.read_text(), hashlib.sha256(p.read_bytes()).hexdigest()
    text, sha, _ = H.fetch(params, tag, raw_dir=RAW)
    return text, sha


def parse_vectors(text):
    lines = text.splitlines()
    i0 = lines.index('$$SOE'); i1 = lines.index('$$EOE')
    t, v = [], []
    for l in lines[i0 + 1:i1]:
        f = [x.strip() for x in l.split(',')]
        t.append(H.iso_to_unix(H._iso(f[1].replace('A.D. ', ''))))
        v.append([float(x) for x in f[2:8]])
    return np.array(t), np.array(v)


def vectors(target, center, site=None, corr='NONE', start=E.START, stop=E.STOP, step='1 h', tag=None):
    p = _base(start, stop, step)
    p.update({'COMMAND': f"'{target}'", 'EPHEM_TYPE': 'VECTORS', 'VEC_TABLE': "'2'", 'VEC_CORR': f"'{corr}'",
              'REF_SYSTEM': "'ICRF'", 'REF_PLANE': "'FRAME'", 'OUT_UNITS': "'KM-S'"})
    if site is not None:
        lat, lon, h_m = site
        p.update({'CENTER': "'coord@301'", 'COORD_TYPE': 'GEODETIC', 'SITE_COORD': f"'{lon % 360:.7f},{lat:.7f},{h_m / 1000.0:.6f}'"})
    else:
        p['CENTER'] = f"'{center}'"
    text, sha = _fetch(p, tag)
    t, v = parse_vectors(text)
    return t, v, {'path': f'data/cache/cube_horizons/{tag}.txt', 'sha256': sha, 'url': H.API}


def azel(target, site, start=E.START, stop=E.STOP, step='1 h', tag=None):
    lat, lon, h_m = site
    p = H.build_params(target, lat, lon, h_m, start, stop, step)
    text, sha = _fetch(p, tag)
    rows = H.parse_text(text)
    t = np.array([H.iso_to_unix(r['utc']) for r in rows])
    return t, np.array([r['az_deg'] for r in rows]), np.array([r['el_deg'] for r in rows]), \
        {'path': f'data/cache/cube_horizons/{tag}.txt', 'sha256': sha, 'url': H.API}


# ------------------------------------------------------------------ frame
def enu_from_azel(az, el):
    a = np.radians(az); e = np.radians(el)
    return np.stack([np.cos(e) * np.sin(a), np.cos(e) * np.cos(a), np.sin(e)], axis=-1)


def azel_from_enu(v):
    v = v / np.linalg.norm(v, axis=-1, keepdims=True)
    return np.degrees(np.arctan2(v[..., 0], v[..., 1])) % 360.0, np.degrees(np.arcsin(np.clip(v[..., 2], -1, 1)))


def wahba(b_enu, r_icrf):
    """b_enu, r_icrf: (n_bodies, T, 3) unit vectors. Returns R (T,3,3) with b = R r (ICRF -> ENU)."""
    B = np.einsum('kti,ktj->tij', b_enu, r_icrf)
    U, _, Vt = np.linalg.svd(B)
    d = np.linalg.det(U) * np.linalg.det(Vt)
    D = np.zeros_like(B); D[:, 0, 0] = 1; D[:, 1, 1] = 1; D[:, 2, 2] = d
    return U @ D @ Vt


def site_frame(site_id, site, eph, bodies=FIT_BODIES):
    """Hourly rotation ICRF -> ENU (T,3,3) and provenance. eph supplies the Sun/Earth az/el already cached."""
    b, r, prov = [], [], []
    for name, code in bodies.items():
        if name in ('sun', 'earth'):
            az, el = eph[f'{name}_az'], eph[f'{name}_el']
        else:
            t, az, el, pa = azel(code, site, tag=f'{site_id}_{name}_azel_year_20261114'); prov.append(pa)
            assert np.array_equal(t, eph['t'])
        t, v, pv = vectors(code, None, site=site, corr='LT+S', tag=f'{site_id}_{name}_topovec_year_20261114'); prov.append(pv)
        assert np.array_equal(t, eph['t']), name
        b.append(enu_from_azel(az, el)); r.append(v[:, :3] / np.linalg.norm(v[:, :3], axis=1, keepdims=True))
    return wahba(np.array(b), np.array(r)), prov


# ------------------------------------------------------------------ propagation
class Hermite:
    def __init__(self, t, pv):
        self.t, self.p, self.v = t, pv[:, :3], pv[:, 3:]

    def __call__(self, tq):
        i = int(np.clip(np.searchsorted(self.t, tq) - 1, 0, self.t.size - 2))
        h = self.t[i + 1] - self.t[i]; s = (tq - self.t[i]) / h
        h00 = 2 * s ** 3 - 3 * s ** 2 + 1; h10 = s ** 3 - 2 * s ** 2 + s; h01 = -2 * s ** 3 + 3 * s ** 2; h11 = s ** 3 - s ** 2
        return h00 * self.p[i] + h10 * h * self.v[i] + h01 * self.p[i + 1] + h11 * h * self.v[i + 1]


class PoleInterp:
    def __init__(self, t, pole):
        self.t, self.pole = t, pole

    def __call__(self, tq):
        p = np.array([np.interp(tq, self.t, self.pole[:, k]) for k in range(3)])
        return p / np.linalg.norm(p)


def accel(t, y, earth, sun, pole, j2=J2_MOON):
    r = y[:3]; rn = np.linalg.norm(r)
    a = -MU_MOON * r / rn ** 3
    if j2:
        k = pole(t); z = r @ k
        f = 1.5 * j2 * MU_MOON * R_J2 ** 2 / rn ** 5
        a = a + f * ((5 * z * z / rn ** 2 - 1) * r - 2 * z * k)
    for mu, body in ((MU_EARTH, earth), (MU_SUN, sun)):
        if body is None:
            continue
        rb = body(t); d = rb - r
        a = a + mu * (d / np.linalg.norm(d) ** 3 - rb / np.linalg.norm(rb) ** 3)
    return np.concatenate([y[3:], a])


def propagate(state0, t0, t_out, earth, sun, pole, j2=J2_MOON, rtol=1e-11):
    """Integrate forward and backward from t0 to every time in t_out (sorted). Returns (len(t_out), 6)."""
    from scipy.integrate import solve_ivp
    f = lambda t, y: accel(t, y, earth, sun, pole, j2)
    out = np.zeros((t_out.size, 6))
    fw = t_out >= t0
    for mask, rev in ((fw, False), (~fw, True)):
        tt = t_out[mask][::-1] if rev else t_out[mask]
        if not tt.size:
            continue
        sol = solve_ivp(f, (t0, tt[-1]), np.asarray(state0, float), method='DOP853', t_eval=tt, rtol=rtol, atol=1e-9)
        if not sol.success:
            raise RuntimeError(sol.message)
        out[mask] = sol.y.T[::-1] if rev else sol.y.T
    return out


def kepler(state, mu=MU_MOON):
    r = np.asarray(state[:3]); v = np.asarray(state[3:])
    h = np.cross(r, v); n = np.cross([0, 0, 1.0], h)
    e = ((v @ v - mu / np.linalg.norm(r)) * r - (r @ v) * v) / mu
    a = 1 / (2 / np.linalg.norm(r) - v @ v / mu)
    inc = math.degrees(math.acos(h[2] / np.linalg.norm(h)))
    raan = math.degrees(math.atan2(n[1], n[0])) % 360
    aop = math.degrees(math.acos(np.clip(n @ e / (np.linalg.norm(n) * np.linalg.norm(e)), -1, 1)))
    if e[2] < 0:
        aop = 360 - aop
    return {'sma': a, 'ecc': float(np.linalg.norm(e)), 'inc': inc, 'raan': raan, 'aop': aop}


# ------------------------------------------------------------------ geometry at the site
def occulted_by_moon(p_from, p_to, radius=R_MOON_KM):
    """True where the segment p_from -> p_to passes inside the lunar sphere (Moon-centred coords)."""
    d = p_to - p_from
    s = np.clip(-np.einsum('ij,ij->i', p_from, d) / np.einsum('ij,ij->i', d, d), 0, 1)
    closest = p_from + s[:, None] * d
    return np.linalg.norm(closest, axis=1) < radius


def relay_azel(R, r_site, r_relay):
    """R: (T,3,3) ICRF->ENU; r_site, r_relay: (T,3) Moon-centred ICRF km. Returns az, el, range km."""
    d = r_relay - r_site
    enu = np.einsum('tij,tj->ti', R, d)
    az, el = azel_from_enu(enu)
    return az, el, np.linalg.norm(d, axis=1)
