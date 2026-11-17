"""LROC NAC push-broom camera model from the PDS4 CDR label + NAIF SPICE, in the site's local ENU frame.

Model = ISIS LroNarrowAngleCamera / LroNarrowAngleDistortionMap (public USGS source) with the NAIF IK lro_lroc_v20.ti and the
ISIS IAK lro_instrumentAddendum_v04.ti timing constants (values copied below; file in USGS ALE test data):
  line rate   = LINE_EXPOSURE_DURATION * (1 + 0.0045)                         (MULTIPLI_LINE_ERROR; ADDITIVE 0)
  et_start    = et(SCLK pre-roll count) + 1024 * line rate                     (ADDITIONAL_PREROLL; CONSTANT_TIME_OFFSET 0)
  et(line)    = et_start + rate * (line - 0.5)                                 (ISIS line, 1-based, pixel centre at integers)
  detector    = (sample - 1) * sum + sum / 2 + 0.5 + (first_pixel - 1)         (first_pixel = SampleFirstPixel + 1 = 1)
  focal y     = TRANSY * (detector - BORESIGHT_SAMPLE) mm  (NAC-L +0.007, NAC-R -0.007);  x = 0
  undistorted = y / (1 + OD_K * y^2)
  look (cam)  = (0, y_u, FOCAL_LENGTH);  frame LRO_LROCNAC[LR] (CK frame, lrolc temperature-corrected CK on LRO_SC_BUS)
Spacecraft position: spkpos('LRO', et, 'MOON_ME', 'NONE', 'MOON') (ISIS also applies a surface light-time correction:
~0.17 ms x 1.6 km/s ~ 0.3 m, ignored and stated). Sun: spkpos('SUN', et_mid, 'MOON_ME', 'LT+S', 'MOON').
Status: SOURCE-BASED · UNVALIDATED (checked against the label's own START/STOP times and the ODE centre point).
"""
from __future__ import annotations

import datetime as dt
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from .common import spiceypy

IK = {  # NAIF lro_lroc_v20.ti (+ ISIS IAK lro_instrumentAddendum_v04.ti)
    'LEFT': {'code': -85600, 'frame': 'LRO_LROCNACL', 'focal_mm': 699.62, 'boresight': 2548.0, 'transy': 7.0e-3, 'od_k': 1.81e-5},
    'RIGHT': {'code': -85610, 'frame': 'LRO_LROCNACR', 'focal_mm': 701.57, 'boresight': 2496.0, 'transy': -7.0e-3, 'od_k': 1.83e-5},
}
IAK = {'ADDITIONAL_PREROLL': 1024.0, 'MULTIPLI_LINE_ERROR': 0.0045, 'ADDITIVE_LINE_ERROR': 0.0, 'CONSTANT_TIME_OFFSET': 0.0}
SOURCES = ['https://naif.jpl.nasa.gov/pub/naif/pds/data/lro-l-spice-6-v1.0/lrosp_1000/data/ik/lro_lroc_v20.ti',
           'https://raw.githubusercontent.com/DOI-USGS/ale/main/tests/pytests/data/M103595705LE/lro_instrumentAddendum_v04.ti',
           'https://github.com/DOI-USGS/ISIS3 isis/src/lro/objs/LroNarrowAngleCamera/ (camera, distortion map)',
           'https://github.com/DOI-USGS/ISIS3 isis/src/base/objs/{CameraDetectorMap,LineScanCameraDetectorMap}/']
R_MOON_M = 1_737_400.0
NS = {'pds': 'http://pds.nasa.gov/pds4/pds/v1', 'lro': 'http://pds.nasa.gov/pds4/mission/lro/v1',
      'img': 'http://pds.nasa.gov/pds4/img/v1'}


# ------------------------------------------------------------------------------------------------ label
def parse_label(xml_bytes):
    """Fields of an LROC NAC CDR PDS4 label needed by the camera model and the reader."""
    root = ET.fromstring(xml_bytes)

    def f(path):
        e = root.find(path, NS)
        return None if e is None else (e.text or '').strip()

    arr = root.find('.//pds:Array_2D_Image', NS)
    axes = {a.find('pds:axis_name', NS).text: int(a.find('pds:elements', NS).text) for a in arr.findall('pds:Axis_Array', NS)}
    sc = arr.find('pds:Special_Constants', NS)
    special = {c.tag.split('}')[1]: int(c.text) for c in sc} if sc is not None else {}
    el = arr.find('pds:Element_Array', NS)
    out = {
        'product_id': Path(f('.//pds:File/pds:file_name')).stem,
        'file_name': f('.//pds:File/pds:file_name'),
        'file_size': int(f('.//pds:File/pds:file_size')),
        'md5': f('.//pds:File/pds:md5_checksum'),
        'frame_id': f('.//lro:frame_id'),
        'start_utc': f('.//pds:Time_Coordinates/pds:start_date_time'),
        'stop_utc': f('.//pds:Time_Coordinates/pds:stop_date_time'),
        'sclk_preroll': f('.//lro:spacecraft_clock_preroll_count'),
        'line_exposure_ms': float(f('.//lro:line_exposure_duration')),
        'crosstrack_summing': int(f('.//img:crosstrack_summing') or 1),
        'data_offset': int(arr.find('pds:offset', NS).text),
        'lines': axes['Line'], 'samples': axes['Sample'],
        'data_type': el.find('pds:data_type', NS).text,
        'scaling_factor': float(el.find('pds:scaling_factor', NS).text),
        'value_offset': float(el.find('pds:value_offset', NS).text) if el.find('pds:value_offset', NS) is not None else 0.0,
        'special': special, 'product_version': f('.//lro:product_version_id'),
        'data_quality_id': f('.//lro:data_quality_id'),
    }
    if out['data_type'] != 'SignedLSB2':
        raise ValueError(f"unexpected data type {out['data_type']}")
    if out['frame_id'] not in IK:
        raise ValueError(f"unexpected NAC frame {out['frame_id']}")
    if out['samples'] * out['crosstrack_summing'] != 5064:
        raise ValueError(f"samples x summing = {out['samples']} x {out['crosstrack_summing']} != 5064 (SampleFirstPixel != 0?)")
    return out


# ------------------------------------------------------------------------------------------------ camera
class NacCamera:
    def __init__(self, label, kernels):
        self.L = label
        self.ik = IK[label['frame_id']]
        self.sp = spiceypy()
        self.sp.kclear()
        for k in kernels:
            self.sp.furnsh(str(k))
        rate = label['line_exposure_ms'] / 1000.0
        self.rate = rate * (1.0 + IAK['MULTIPLI_LINE_ERROR']) + IAK['ADDITIVE_LINE_ERROR']
        et_pre = self.sp.scs2e(-85, label['sclk_preroll'])
        self.et0 = et_pre + IAK['ADDITIONAL_PREROLL'] * self.rate + IAK['CONSTANT_TIME_OFFSET']
        self.csum = label['crosstrack_summing']

    def close(self):
        self.sp.kclear()

    # -- timing / detector
    def et(self, line):
        return self.et0 + self.rate * (np.asarray(line, float) - 0.5)

    def timing_check(self):
        """Model times of the first/last line edges vs the label START/STOP (independent of the IAK constants)."""
        s = self.sp
        start = s.utc2et(self.L['start_utc'].replace('Z', ''))
        stop = s.utc2et(self.L['stop_utc'].replace('Z', ''))
        return {'startDiffS': float(self.et0 - start), 'stopDiffS': float(self.et(self.L['lines'] + 0.5) - stop),
                'lineRateS': self.rate, 'labelSpanRateS': (stop - start) / self.L['lines']}

    def look_cam(self, sample):
        """Unit look vectors (N, 3) in the NAC frame for continuous ISIS sample coordinates."""
        s = np.asarray(sample, float)
        det = (s - 1.0) * self.csum + self.csum / 2.0 + 0.5
        y = self.ik['transy'] * (det - self.ik['boresight'])
        yu = y / (1.0 + self.ik['od_k'] * y * y)
        v = np.stack([np.zeros_like(yu), yu, np.full_like(yu, self.ik['focal_mm'])], axis=-1)
        return v / np.linalg.norm(v, axis=-1, keepdims=True)

    # -- SPICE states in MOON_ME (metres)
    def sc_pos_me(self, ets):
        return np.array([self.sp.spkpos('LRO', float(e), 'MOON_ME', 'NONE', 'MOON')[0] for e in np.atleast_1d(ets)]) * 1000.0

    def cam_to_me(self, ets):
        return np.array([self.sp.pxform(self.ik['frame'], 'MOON_ME', float(e)) for e in np.atleast_1d(ets)])

    def sun_me(self, et):
        p, _lt = self.sp.spkpos('SUN', float(et), 'MOON_ME', 'LT+S', 'MOON')
        p = np.asarray(p) * 1000.0
        return p / np.linalg.norm(p), float(np.linalg.norm(p))

    def rays_me(self, lines, samples):
        """Origins (N,3) and unit directions (N,3) in MOON_ME for paired (line, sample) arrays."""
        lines, samples = np.broadcast_arrays(np.asarray(lines, float), np.asarray(samples, float))
        ets = self.et(lines.ravel())
        P = self.sc_pos_me(ets)
        R = self.cam_to_me(ets)
        d = np.einsum('nij,nj->ni', R, self.look_cam(samples.ravel()))
        return P, d


# ------------------------------------------------------------------------------------------------ geometry helpers
def sphere_hit(P, d, radius):
    """First intersection of rays with a sphere centred at the Moon's centre (NaN if missed)."""
    b = np.einsum('ij,ij->i', P, d)
    c = np.einsum('ij,ij->i', P, P) - radius ** 2
    disc = b * b - c
    t = -b - np.sqrt(np.where(disc >= 0, disc, np.nan))
    return P + t[:, None] * d


def me_to_latlon(X):
    r = np.linalg.norm(X, axis=-1)
    return np.degrees(np.arcsin(X[..., 2] / r)), np.degrees(np.arctan2(X[..., 1], X[..., 0]))


def stereo_xy(lat, lon):
    la, lo = np.radians(lat), np.radians(lon)
    rho = 2 * R_MOON_M * np.tan(np.pi / 4 + la / 2)
    return rho * np.sin(lo), rho * np.cos(lo)


def enu_basis(lat, lon, h0):
    la, lo = math.radians(lat), math.radians(lon)
    e = np.array([-math.sin(lo), math.cos(lo), 0.0])
    n = np.array([-math.sin(la) * math.cos(lo), -math.sin(la) * math.sin(lo), math.cos(la)])
    u = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
    return np.stack([e, n, u]), (R_MOON_M + h0) * u


# ------------------------------------------------------------------------------------------------ rotation helpers
def rotvec_to_matrix(w):
    w = np.asarray(w, float)
    th = np.linalg.norm(w, axis=-1, keepdims=True)
    k = np.where(th > 1e-15, w / np.where(th > 1e-15, th, 1), 0)
    K = np.zeros(w.shape[:-1] + (3, 3))
    K[..., 0, 1], K[..., 0, 2], K[..., 1, 2] = -k[..., 2], k[..., 1], -k[..., 0]
    K[..., 1, 0], K[..., 2, 0], K[..., 2, 1] = k[..., 2], -k[..., 1], k[..., 0]
    th = th[..., None]
    return np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * (K @ K)


def matrix_to_rotvec(R):
    R = np.asarray(R, float)
    c = np.clip((np.trace(R, axis1=-2, axis2=-1) - 1) / 2, -1, 1)
    th = np.arccos(c)
    v = np.stack([R[..., 2, 1] - R[..., 1, 2], R[..., 0, 2] - R[..., 2, 0], R[..., 1, 0] - R[..., 0, 1]], axis=-1)
    s = np.sin(th)
    f = np.where(s > 1e-12, th / (2 * np.where(s > 1e-12, s, 1)), 0.5)
    return v * f[..., None]


# ------------------------------------------------------------------------------------------------ per-image geometry
def window_lines(cam, site_xy, half_m, h_lo, h_hi, margin_m, step=64):
    """1-based [l0, l1] of the image lines whose rays (5 samples across) hit the square site_xy +- (half + margin) on
    spheres R + h_lo and R + h_hi (brackets the terrain). None if no line does."""
    ns = cam.L['samples']
    lines = np.arange(1, cam.L['lines'] + 1, step, dtype=float)
    samples = np.array([0.5, ns / 4, ns / 2, 3 * ns / 4, ns + 0.5])
    LL, SS = np.meshgrid(lines, samples, indexing='ij')
    P, d = cam.rays_me(LL, SS)
    hit_any = np.zeros(len(lines), bool)
    for h in (h_lo, h_hi):
        X = sphere_hit(P, d, R_MOON_M + h)
        lat, lon = me_to_latlon(X)
        x, y = stereo_xy(lat, lon)
        inside = (np.abs(x - site_xy[0]) <= half_m + margin_m) & (np.abs(y - site_xy[1]) <= half_m + margin_m)
        hit_any |= inside.reshape(LL.shape).any(axis=1)
    if not hit_any.any():
        return None
    idx = np.flatnonzero(hit_any)
    l0 = max(1, int(lines[idx[0]]) - step)
    l1 = min(cam.L['lines'], int(lines[idx[-1]]) + step)
    return l0, l1


def fit_states(cam, l0, l1, M_enu, P0, degree=3, nodes=41, check=401):
    """Polynomials in tau (line l0-0.5 -> -1, l1+0.5 -> +1) of the spacecraft position (ENU, m) and of the rotation vector
    w(tau) with R_cam->enu(tau) = R_mid @ exp([w(tau)]x). Returns dict with coefficients and fit residuals."""
    la, lb = l0 - 0.5, l1 + 0.5
    lmid, half = (la + lb) / 2, (lb - la) / 2

    def states(lines):
        ets = cam.et(lines)
        P = (cam.sc_pos_me(ets) - P0) @ M_enu.T
        R = M_enu[None] @ cam.cam_to_me(ets)
        return P, R

    ln = lmid + half * np.cos(np.linspace(math.pi, 0, nodes))          # Chebyshev-Lobatto nodes
    tau = (ln - lmid) / half
    P, R = states(ln)
    R_mid = states(np.array([lmid]))[1][0]
    W = matrix_to_rotvec(np.einsum('ji,njk->nik', R_mid, R))
    V = np.vander(tau, degree + 1, increasing=True)
    cp = np.linalg.lstsq(V, P, rcond=None)[0]
    cw = np.linalg.lstsq(V, W, rcond=None)[0]
    lc = np.linspace(la, lb, check)
    tc = (lc - lmid) / half
    Pc, Rc = states(lc)
    Vc = np.vander(tc, degree + 1, increasing=True)
    pos_err = np.linalg.norm(Vc @ cp - Pc, axis=1)
    Rfit = R_mid[None] @ rotvec_to_matrix(Vc @ cw)
    ang = np.arccos(np.clip((np.trace(np.einsum('nji,njk->nik', Rfit, Rc), axis1=1, axis2=2) - 1) / 2, -1, 1))
    return {'lmid': lmid, 'half': half, 'degree': degree, 'posCoef': cp.tolist(), 'rotCoef': cw.tolist(), 'Rmid': R_mid.tolist(),
            'fitMaxPosErrM': float(pos_err.max()), 'fitMaxAngErrUrad': float(ang.max() * 1e6), 'checkLines': check}


def eval_states(fit, lines):
    tau = (np.asarray(lines, float) - fit['lmid']) / fit['half']
    V = np.vander(np.atleast_1d(tau), fit['degree'] + 1, increasing=True)
    P = V @ np.asarray(fit['posCoef'])
    R = np.asarray(fit['Rmid'])[None] @ rotvec_to_matrix(V @ np.asarray(fit['rotCoef']))
    return P, R


def fitted_rays_enu(cam, fit, lines, samples):
    """The rays the OSL camera evaluates (same formulas, float64): origins and unit directions in ENU."""
    lines, samples = np.broadcast_arrays(np.asarray(lines, float), np.asarray(samples, float))
    P, R = eval_states(fit, lines.ravel())
    d = np.einsum('nij,nj->ni', R, cam.look_cam(samples.ravel()))
    return P, d


def osl_source(cam, fit, l0, nl_render_lines, b):
    """OSL push-broom camera for Cycles (CUSTOM camera, camera object at the identity). Raster (u, v): v = 1 is the first
    cropped line (image top). Cycles camera space = world with z flipped (checked by a test render, see tests)."""
    ik, L = cam.ik, cam.L
    ns = L['samples']
    nl = nl_render_lines * b
    cp, cw, Rm = np.asarray(fit['posCoef']), np.asarray(fit['rotCoef']), np.asarray(fit['Rmid'])

    def poly(c, axis):
        terms = [f'{c[k, axis]:.10e}' for k in range(c.shape[0])]
        expr = terms[-1]
        for t in reversed(terms[:-1]):
            expr = f'({t} + tau * {expr})'
        return expr

    rm = [f'{v:.15e}' for v in Rm.ravel()]
    return f'''// POLARIS X R4 push-broom camera for {L["product_id"]} (generated by tools/validation/render_vs_real/nac_camera.py)
shader camera(output point position = 0.0, output vector direction = 0.0, output color throughput = 1.0)
{{
  point r = camera_shader_raster_position();
  float s = 0.5 + r[0] * {float(ns)};
  float line = {l0 - 0.5:.6f} + (1.0 - r[1]) * {float(nl)};
  float tau = (line - {fit["lmid"]:.6f}) / {fit["half"]:.6f};
  float det = (s - 1.0) * {float(cam.csum)} + {cam.csum / 2.0 + 0.5};
  float y = {ik["transy"]:.6e} * (det - {ik["boresight"]:.4f});
  y = y / (1.0 + {ik["od_k"]:.6e} * y * y);
  vector lc = normalize(vector(0.0, y, {ik["focal_mm"]:.6f}));
  vector w = vector({poly(cw, 0)}, {poly(cw, 1)}, {poly(cw, 2)});
  float th = length(w);
  vector lr = lc;
  if (th > 1e-15) {{
    vector k = w / th;
    lr = lc * cos(th) + cross(k, lc) * sin(th) + k * dot(k, lc) * (1.0 - cos(th));
  }}
  vector d = vector({rm[0]} * lr[0] + {rm[1]} * lr[1] + {rm[2]} * lr[2],
                    {rm[3]} * lr[0] + {rm[4]} * lr[1] + {rm[5]} * lr[2],
                    {rm[6]} * lr[0] + {rm[7]} * lr[1] + {rm[8]} * lr[2]);
  point p = point({poly(cp, 0)}, {poly(cp, 1)}, {poly(cp, 2)});
  position = point(p[0], p[1], -p[2]);
  direction = normalize(vector(d[0], d[1], -d[2]));
}}
'''


def utc(s):
    return dt.datetime.fromisoformat(s.replace('Z', '')).replace(tzinfo=None)
