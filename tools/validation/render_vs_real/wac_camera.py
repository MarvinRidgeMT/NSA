"""LROC WAC push-frame camera model (VIS 643 nm band of COLOR-mode CDRs) from the PDS4 label + NAIF SPICE, in the site's ENU.

Model = ISIS LroWideAngleCamera / PushFrameCameraDetectorMap / CameraDetectorMap / LroWideAngleCameraFocalPlaneMap /
LroWideAngleCameraDistortionMap (public USGS source) with the NAIF IK lro_lroc_v20.ti (values copied below; a test compares
them with the cached IK file). The CDR frame layout is that of ISIS lrowac2isis.

  CDR layout (COLOR mode)  each frame set = 78 lines x 704 samples: UV 321 (4), UV 360 (4), VIS 415, 566, 604, 643, 689
                           (14 each). The 643 nm framelet is lines 50-63 of every set. The "band image" used here stacks
                           those framelets: band row = 14 * k + j (k = frame set, 0-based; j = framelet line, 0-based).
  time of frame set k      et = et(SpacecraftClockStartCount) + exposure / 2 + k * interframe_delay
  detector                 sample_det = sample + 160 (COLOR_SAMPLE_OFFSET); line_det = 781 (FILTER_OFFSET) + framelet line,
                           framelet line = j + 1 at the pixel centre (ISIS 1-based, continuous)
  focal plane (mm)         cs = sample_det - (BORESIGHT_SAMPLE + 1), cl = line_det - (BORESIGHT_LINE + 1)
                           x = TRANSX . (1, cs, cl),  y = TRANSY . (1, cs, cl)
  undistorted              (x, y) * (1 + k1 r^2 + k2 r^4 + k3 r^6),  r^2 = x^2 + y^2   (OD_K, forward from distorted)
  look (camera)            (x_u, y_u, FOCAL_LENGTH) in LRO_LROCWAC_VIS (ISIS instrument rotation frame -85621; the CK
                           frame LRO_LROCWAC -85620 is in the lrolc CKs)
Spacecraft position: spkpos('LRO', et, 'MOON_ME', 'NONE', 'MOON'); Sun: spkpos('SUN', et_mid, 'MOON_ME', 'LT+S', 'MOON'), as
for the NAC (nac_camera.py). Light-time from the surface to the spacecraft (~0.2 ms) is ignored, as there.
Status: SOURCE-BASED · UNVALIDATED (checked against the label START/STOP times, the ODE centre point and, per image, by the
registration offset).
"""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from .common import spiceypy
from .nac_camera import NS, R_MOON_M, matrix_to_rotvec, me_to_latlon, rotvec_to_matrix, sphere_hit, stereo_xy

FILTER = {  # NAIF IK lro_lroc_v20.ti, LRO_LROCWAC_VIS_FILTER_4 (643 nm), code -85634; sample offset of INS-85621
    'code': -85634, 'band_nm': 643, 'frame': 'LRO_LROCWAC_VIS', 'focal_mm': 6.0308669,
    'boresight_sample': 509.5297, 'boresight_line': 775.7545, 'filter_offset': 781,
    'transx': (0.0, -0.000002600831484, -0.008999999624204), 'transy': (0.0, 0.008999999624204, -0.000002600831484),
    'od_k': (0.011310945216635900, 0.000144463288593614, 4.887542512911270e-6), 'color_sample_offset': 160,
    'pixel_pitch_mm': 0.009,
}
IFOV_RAD = FILTER['pixel_pitch_mm'] / FILTER['focal_mm']
SET_LINES = 78                      # COLOR frame set: 4 + 4 + 5 x 14
BAND_FIRST_LINE = 50                # 643 nm framelet: lines 50..63 of the set (lrowac2isis order UV1, UV2, 415, 566, 604, 643, 689)
FRAMELET = 14
SAMPLES = 704
BAND_LINES = {415: 8, 566: 22, 604: 36, 643: 50, 689: 64}   # first line of each VIS framelet in a set (for the band-order check)
SOURCES = ['https://naif.jpl.nasa.gov/pub/naif/pds/data/lro-l-spice-6-v1.0/lrosp_1000/data/ik/lro_lroc_v20.ti',
           'https://github.com/DOI-USGS/ISIS3 isis/src/lro/objs/LroWideAngleCamera/ (camera, focal plane, distortion maps)',
           'https://github.com/DOI-USGS/ISIS3 isis/src/lro/apps/lrowac2isis/lrowac2isis.cpp (frame-set layout)',
           'https://github.com/DOI-USGS/ISIS3 isis/src/base/objs/{CameraDetectorMap,PushFrameCameraDetectorMap}/']


def _hex_float(s):
    s = s.strip()
    if s.lower().startswith('0x'):
        return int(s, 16)
    raise ValueError(s)


def parse_label(xml_bytes):
    """Fields of an LROC WAC CDR PDS4 label needed by the camera model and the reader."""
    root = ET.fromstring(xml_bytes)

    def f(path):
        e = root.find(path, NS)
        return None if e is None else (e.text or '').strip()

    arr = root.find('.//pds:Array_2D_Image', NS)
    axes = {a.find('pds:axis_name', NS).text: int(a.find('pds:elements', NS).text) for a in arr.findall('pds:Axis_Array', NS)}
    sc = arr.find('pds:Special_Constants', NS)
    special = {c.tag.split('}')[1]: _hex_float(c.text) for c in sc} if sc is not None else {}
    out = {
        'product_id': Path(f('.//pds:File/pds:file_name')).stem,
        'file_name': f('.//pds:File/pds:file_name'),
        'file_size': int(f('.//pds:File/pds:file_size')),
        'md5': f('.//pds:File/pds:md5_checksum'),
        'start_utc': f('.//pds:Time_Coordinates/pds:start_date_time'),
        'stop_utc': f('.//pds:Time_Coordinates/pds:stop_date_time'),
        'sclk_start': f('.//lro:spacecraft_clock_start_count'),
        'exposure_ms': float(f('.//img:exposure_duration')),
        'interframe_ms': float(f('.//lro:interframe_delay')),
        'mode': f('.//lro:instrument_mode_id'),
        'nframes': int(f('.//lro:nframes')),
        'band_code': int(f('.//lro:band_code')),
        'data_offset': int(arr.find('pds:offset', NS).text),
        'lines': axes['Line'], 'samples': axes['Sample'],
        'data_type': arr.find('pds:Element_Array/pds:data_type', NS).text,
        'special_bits': special, 'product_version': f('.//lro:product_version_id'),
        'data_quality_id': f('.//lro:data_quality_id'),
    }
    if out['mode'] != 'COLOR' or out['band_code'] != 127:
        raise ValueError(f"WAC mode {out['mode']} band code {out['band_code']}: only COLOR / 127 is modelled")
    if out['data_type'] != 'IEEE754LSBSingle' or out['samples'] != SAMPLES:
        raise ValueError(f"unexpected array {out['data_type']} x {out['samples']} samples")
    if out['lines'] != out['nframes'] * SET_LINES:
        raise ValueError(f"lines {out['lines']} != nframes {out['nframes']} x {SET_LINES}")
    return out


class WacCamera:
    """643 nm band image: rows 0 .. 14 * nframes - 1, samples 1..704 (ISIS, pixel centres at integers)."""

    def __init__(self, label, kernels):
        self.L = label
        self.F = FILTER
        self.sp = spiceypy()
        self.sp.kclear()
        for k in kernels:
            self.sp.furnsh(str(k))
        self.ifd = label['interframe_ms'] / 1000.0
        self.et0 = self.sp.scs2e(-85, label['sclk_start']) + label['exposure_ms'] / 1000.0 / 2.0
        self.nrows = label['nframes'] * FRAMELET

    def close(self):
        self.sp.kclear()

    # -- timing / detector
    def et_set(self, k):
        return self.et0 + self.ifd * np.asarray(k, float)

    @staticmethod
    def split_y(y):
        """Continuous band-image y (0 = top edge of row 0) -> (frame set k, framelet line in ISIS units, 0.5 .. 14.5)."""
        y = np.asarray(y, float)
        k = np.clip(np.floor(y / FRAMELET), 0, None)
        return k, y - FRAMELET * k + 0.5

    def timing_check(self):
        s = self.sp
        start = s.utc2et(self.L['start_utc'].replace('Z', ''))
        stop = s.utc2et(self.L['stop_utc'].replace('Z', ''))
        span = self.ifd * self.L['nframes']
        return {'startDiffS': float(self.et0 - start), 'labelSpanS': float(stop - start), 'modelSpanS': span,
                'interframeS': self.ifd}

    def look_cam(self, sample, fline):
        """Unit look vectors (N, 3) in LRO_LROCWAC_VIS for continuous ISIS sample and framelet line."""
        F = self.F
        s = np.asarray(sample, float)
        fl = np.asarray(fline, float)
        cs = (s + F['color_sample_offset']) - (F['boresight_sample'] + 1.0)
        cl = (F['filter_offset'] + fl) - (F['boresight_line'] + 1.0)
        tx, ty = F['transx'], F['transy']
        x = tx[0] + tx[1] * cs + tx[2] * cl
        y = ty[0] + ty[1] * cs + ty[2] * cl
        r2 = x * x + y * y
        k1, k2, k3 = F['od_k']
        dr = 1.0 + k1 * r2 + k2 * r2 * r2 + k3 * r2 * r2 * r2
        v = np.stack([x * dr, y * dr, np.full_like(x, F['focal_mm'])], axis=-1)
        return v / np.linalg.norm(v, axis=-1, keepdims=True)

    # -- SPICE states in MOON_ME (metres)
    def sc_pos_me(self, ets):
        return np.array([self.sp.spkpos('LRO', float(e), 'MOON_ME', 'NONE', 'MOON')[0] for e in np.atleast_1d(ets)]) * 1000.0

    def cam_to_me(self, ets):
        return np.array([self.sp.pxform(self.F['frame'], 'MOON_ME', float(e)) for e in np.atleast_1d(ets)])

    def sun_me(self, et):
        p, _lt = self.sp.spkpos('SUN', float(et), 'MOON_ME', 'LT+S', 'MOON')
        p = np.asarray(p) * 1000.0
        return p / np.linalg.norm(p), float(np.linalg.norm(p))

    def rays_me(self, y, samples):
        """Origins and unit directions in MOON_ME for paired continuous (band-image y, ISIS sample) arrays."""
        y, samples = np.broadcast_arrays(np.asarray(y, float), np.asarray(samples, float))
        k, fl = self.split_y(y.ravel())
        ks, inv = np.unique(k, return_inverse=True)
        ets = self.et_set(ks)
        P = self.sc_pos_me(ets)[inv]
        R = self.cam_to_me(ets)[inv]
        d = np.einsum('nij,nj->ni', R, self.look_cam(samples.ravel(), fl))
        return P, d


# ------------------------------------------------------------------------------------------------ per-image geometry
def window(cam, site_xy, half_m, h_lo, h_hi, margin_m, pad_px=3):
    """Band-image rows [r0, r1] (whole frame sets) and samples [s0, s1] (1-based, inclusive) whose rays hit the square
    site_xy +- (half + margin) on the spheres R + h_lo and R + h_hi (brackets the terrain). None if nothing does."""
    ks = np.arange(cam.L['nframes'])
    jj = np.array([0.0, 7.0, 13.999])
    ss = np.arange(0.5, SAMPLES + 1.0, 4.0)
    K, J, S = np.meshgrid(ks, jj, ss, indexing='ij')
    P, d = cam.rays_me(K * FRAMELET + J, S)
    hit = np.zeros(K.shape, bool)
    for h in (h_lo, h_hi):
        X = sphere_hit(P, d, R_MOON_M + h)
        lat, lon = me_to_latlon(X)
        x, y = stereo_xy(lat, lon)
        hit |= ((np.abs(x - site_xy[0]) <= half_m + margin_m) & (np.abs(y - site_xy[1]) <= half_m + margin_m)).reshape(K.shape)
    if not hit.any():
        return None
    kk = np.flatnonzero(hit.any(axis=(1, 2)))
    sidx = np.flatnonzero(hit.any(axis=(0, 1)))
    k0, k1 = max(0, int(kk[0]) - 1), min(cam.L['nframes'] - 1, int(kk[-1]) + 1)
    s0 = max(1, int(math.floor(ss[sidx[0]])) - 4 - pad_px)
    s1 = min(SAMPLES, int(math.ceil(ss[sidx[-1]])) + 4 + pad_px)
    return k0 * FRAMELET, (k1 + 1) * FRAMELET - 1, s0, s1


def fit_states(cam, k0, k1, M_enu, P0, degree=3, nodes=41, check=401):
    """Polynomials in tau (et of set k0 -> -1, of set k1 -> +1) of the spacecraft position (ENU, m) and of the rotation
    vector w(tau), R_cam->enu(tau) = R_mid @ exp([w]x), as nac_camera.fit_states but in time. Checked at `check` times and
    at every frame-set time in [k0, k1]."""
    ea, eb = float(cam.et_set(k0)), float(cam.et_set(k1))
    emid, half = (ea + eb) / 2, max((eb - ea) / 2, 1e-3)

    def states(ets):
        P = (cam.sc_pos_me(ets) - P0) @ M_enu.T
        R = M_enu[None] @ cam.cam_to_me(ets)
        return P, R

    en = emid + half * np.cos(np.linspace(math.pi, 0, nodes))
    tau = (en - emid) / half
    P, R = states(en)
    R_mid = states(np.array([emid]))[1][0]
    W = matrix_to_rotvec(np.einsum('ji,njk->nik', R_mid, R))
    V = np.vander(tau, degree + 1, increasing=True)
    cp = np.linalg.lstsq(V, P, rcond=None)[0]
    cw = np.linalg.lstsq(V, W, rcond=None)[0]
    ec = np.concatenate([np.linspace(ea, eb, check), cam.et_set(np.arange(k0, k1 + 1))])
    tc = (ec - emid) / half
    Pc, Rc = states(ec)
    Vc = np.vander(tc, degree + 1, increasing=True)
    pos_err = np.linalg.norm(Vc @ cp - Pc, axis=1)
    Rfit = R_mid[None] @ rotvec_to_matrix(Vc @ cw)
    ang = np.arccos(np.clip((np.trace(np.einsum('nji,njk->nik', Rfit, Rc), axis1=1, axis2=2) - 1) / 2, -1, 1))
    return {'etMid': emid, 'half': half, 'et0': cam.et0, 'ifd': cam.ifd, 'degree': degree, 'posCoef': cp.tolist(),
            'rotCoef': cw.tolist(), 'Rmid': R_mid.tolist(), 'fitMaxPosErrM': float(pos_err.max()),
            'fitMaxAngErrUrad': float(ang.max() * 1e6), 'checkTimes': int(len(ec))}


def eval_states(fit, ets):
    tau = (np.asarray(ets, float) - fit['etMid']) / fit['half']
    V = np.vander(np.atleast_1d(tau), fit['degree'] + 1, increasing=True)
    P = V @ np.asarray(fit['posCoef'])
    R = np.asarray(fit['Rmid'])[None] @ rotvec_to_matrix(V @ np.asarray(fit['rotCoef']))
    return P, R


def fitted_rays_enu(cam, fit, y, samples):
    """The rays the OSL camera evaluates (same formulas, float64): origins and unit directions in ENU."""
    y, samples = np.broadcast_arrays(np.asarray(y, float), np.asarray(samples, float))
    k, fl = cam.split_y(y.ravel())
    P, R = eval_states(fit, fit['et0'] + fit['ifd'] * k)
    d = np.einsum('nij,nj->ni', R, cam.look_cam(samples.ravel(), fl))
    return P, d


def osl_source(cam, fit, r0, nrows, s0, ncols):
    """OSL push-frame camera for Cycles (CUSTOM camera at the identity). Raster (u, v): v = 1 is band row r0 (top), u = 0 the
    left edge of sample s0. Each output row lies inside one framelet, so a pixel never mixes frame times."""
    F, L = cam.F, cam.L
    cp, cw, Rm = np.asarray(fit['posCoef']), np.asarray(fit['rotCoef']), np.asarray(fit['Rmid'])

    def poly(c, axis):
        terms = [f'{c[k, axis]:.10e}' for k in range(c.shape[0])]
        expr = terms[-1]
        for t in reversed(terms[:-1]):
            expr = f'({t} + tau * {expr})'
        return expr

    rm = [f'{v:.15e}' for v in Rm.ravel()]
    tx, ty, k = F['transx'], F['transy'], F['od_k']
    return f'''// POLARIS X WAC push-frame camera for {L["product_id"]} 643 nm (generated by tools/validation/render_vs_real/wac_camera.py)
shader camera(output point position = 0.0, output vector direction = 0.0, output color throughput = 1.0)
{{
  point r = camera_shader_raster_position();
  float s = {s0 - 0.5:.6f} + r[0] * {float(ncols)};
  float y = {float(r0):.6f} + (1.0 - r[1]) * {float(nrows)};
  float k = floor(y / {float(FRAMELET)});
  if (k < 0.0) k = 0.0;
  float fl = y - {float(FRAMELET)} * k + 0.5;
  // OSL floats are 32-bit: et (~1e8 s) would lose ~10 s, so tau is formed from k with constants computed in double
  float tau = {(fit["et0"] - fit["etMid"]) / fit["half"]:.12e} + {fit["ifd"] / fit["half"]:.12e} * k;
  float cs = (s + {float(F["color_sample_offset"])}) - {F["boresight_sample"] + 1.0:.6f};
  float cl = ({float(F["filter_offset"])} + fl) - {F["boresight_line"] + 1.0:.6f};
  float x = {tx[0]:.15e} + {tx[1]:.15e} * cs + {tx[2]:.15e} * cl;
  float yy = {ty[0]:.15e} + {ty[1]:.15e} * cs + {ty[2]:.15e} * cl;
  float r2 = x * x + yy * yy;
  float dr = 1.0 + {k[0]:.15e} * r2 + {k[1]:.15e} * r2 * r2 + {k[2]:.15e} * r2 * r2 * r2;
  vector lc = normalize(vector(x * dr, yy * dr, {F["focal_mm"]:.7f}));
  vector w = vector({poly(cw, 0)}, {poly(cw, 1)}, {poly(cw, 2)});
  float th = length(w);
  vector lr = lc;
  if (th > 1e-15) {{
    vector kk = w / th;
    lr = lc * cos(th) + cross(kk, lc) * sin(th) + kk * dot(kk, lc) * (1.0 - cos(th));
  }}
  vector d = vector({rm[0]} * lr[0] + {rm[1]} * lr[1] + {rm[2]} * lr[2],
                    {rm[3]} * lr[0] + {rm[4]} * lr[1] + {rm[5]} * lr[2],
                    {rm[6]} * lr[0] + {rm[7]} * lr[1] + {rm[8]} * lr[2]);
  point p = point({poly(cp, 0)}, {poly(cp, 1)}, {poly(cp, 2)});
  position = point(p[0], p[1], -p[2]);
  direction = normalize(vector(d[0], d[1], -d[2]));
}}
'''


# ------------------------------------------------------------------------------------------------ real image
def classify_bits(bits, special):
    """(invalid, high-saturated) masks from the raw float32 bit patterns and the label's special constants."""
    sp = {k: np.uint32(v) for k, v in special.items()}
    high = (bits == sp.get('high_instrument_saturation', 0xFF7FFFFE)) | (bits == sp.get('high_representation_saturation', 0xFF7FFFFF))
    vals = bits.view(np.float32)
    invalid = ~np.isfinite(vals) | ((vals < -1e30) & ~high)     # NULL, LRS, LIS and any other special (all ~ -3.4e38)
    return invalid, high


def band_from_sets(raw_sets, first_line=BAND_FIRST_LINE):
    """(nsets, 78, 704) uint32 -> (nsets * 14, 704) uint32 of one VIS band."""
    return raw_sets[:, first_line:first_line + FRAMELET, :].reshape(-1, raw_sets.shape[2])
