"""Kaguya (SELENE) Terrain Camera push-broom model from the PDS3 Level 2B0 label + SELENE SPICE, in MOON_ME.

Model = ISIS KaguyaTcCamera / KaguyaTcCameraDistortionMap (DOI-USGS/ISIS3 isis/src/kaguya/objs/KaguyaTcCamera) with
LineScanCameraDetectorMap, CameraDetectorMap and CameraFocalPlaneMap, and the IK SEL_TC_V01.TI + ISIS IAK
kaguyaTcAddendum007.ti (USGS public kernels; values copied below, a test compares them with the cached files):
  et_start   = sct2e(-131, CORRECTED_SC_CLOCK_START_COUNT as ticks)       (kaguyatc2isis -> SpacecraftClockStartCount;
                                                                            getClockTime(clock, -1, clockTicks=true))
  rate       = CORRECTED_SAMPLING_INTERVAL / 1000                           (-> LineSamplingInterval)
  et(line)   = et_start + rate * (line - 0.5)                               (ISIS line, 1-based)
  detector   sample_det = (sample - 1) + FIRST_PIXEL_NUMBER                 (297 nominal, 1 full, 1172 half swath)
             line_det = 0 (line-scan detector)
  focal (mm) ds = sample_det - BORESIGHT_SAMPLE (2048), dl = line_det - BORESIGHT_LINE (0.5)
             x = -0.007 * dl, y = -0.007 * ds                              (TRANSX = (0,0,-0.007), TRANSY = (0,-0.007,0))
  undistort  r = |(x, y)|; x_u = x + (cx0 + bx) + cx1 r + cx2 r^2 + cx3 r^3; y_u likewise with cy, by
             (cx, cy = DISTORTION_COEF_X/Y; bx, by = the IK BORESIGHT x, y)
  look       (x_u, y_u, FOCAL_LENGTH) in LISM_TC<n>_HEAD (NaifCkCode -131350 / -131370); attitude from the SELENE CK
Spacecraft: spkpos('SELENE', et, 'MOON_ME', 'NONE', 'MOON') (IAK: LIGHTTIME_CORRECTION NONE); Sun: 'LT+S' as for the NAC.

Conventions not settled before any render (A11.4 pipeline test):
  start  'isis' (as above) or 'label' (CORRECTED_START_TIME UTC; 33 ms later than 'isis' on the one label checked, ~50 m)
  flip   sample axis reversed (sample_det = FIRST_PIXEL_NUMBER + samples - sample). ISIS ignores the label's
         SATELLITE_MOVING_DIRECTION and FIRST_DETECTOR_ELEM_POSITION; whether Level 2B0 lines are stored in detector order
         for both moving directions is not documented in the label.
Status: SOURCE-BASED · UNVALIDATED.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from .common import spiceypy

# IK SEL_TC_V01.TI (focal length, boresight vector, distortion) + IAK kaguyaTcAddendum007.ti (pixel pitch, detector origin)
IK = {
    'TC1': {'code': -131351, 'frame': 'LISM_TC1_HEAD', 'focal_mm': 72.45, 'boresight_xy': (-0.0725, 0.0214),
            'cx': (-9.6499e-4, 9.8441e-4, 8.5773e-6, -3.7438e-6), 'cy': (-1.3796e-3, 1.3502e-5, 2.7251e-6, -6.1938e-6)},
    'TC2': {'code': -131371, 'frame': 'LISM_TC2_HEAD', 'focal_mm': 72.63, 'boresight_xy': (-0.0474, 0.0126),
            'cx': (2.9786e-3, 7.7836e-5, 3.9265e-6, -4.4088e-6), 'cy': (9.2410e-4, -1.1994e-4, 2.9281e-5, -3.7239e-7)},
}
PIXEL_MM = 0.007
BORESIGHT_SAMPLE, BORESIGHT_LINE = 2048.0, 0.5
DETECTOR_SAMPLES = 4096
FIRST_PIXEL = {'FULL': 1, 'NOMINAL': 297, 'HALF': 1172}
SPACECRAFT_ID = -131
IFOV_RAD = PIXEL_MM / 72.45
SOURCES = ['https://asc-isisdata.s3.us-west-2.amazonaws.com/usgs_data/kaguya/kernels/ (IK, IAK, FK, SCLK, CK, SPK)',
           'https://github.com/DOI-USGS/ISIS3 isis/src/kaguya/objs/KaguyaTcCamera/ (camera, distortion map)',
           'https://github.com/DOI-USGS/ISIS3 isis/src/kaguya/apps/kaguyatc2isis/ (label translation)']


def _pds3(text):
    """Top-level KEY = VALUE pairs (first occurrence), units and quotes stripped; plus the IMAGE object."""
    out = {}
    for m in re.finditer(r'^\s*(\^?[A-Z0-9_]+)\s*=\s*(.+?)\s*$', text, re.M):
        out.setdefault(m.group(1), m.group(2))
    return out


def _num(v):
    return float(re.sub(r'[()"]|<[^>]*>', '', v).strip())


def _str(v):
    return v.strip().strip('"').strip()


def parse_label(text):
    top = _pds3(re.split(r'^\s*OBJECT\s*=', text, maxsplit=1, flags=re.M)[0])
    m = re.search(r'^\s*OBJECT\s*=\s*IMAGE\s*$(.*?)^\s*END_OBJECT\s*=\s*IMAGE\s*$', text, re.M | re.S)
    if not m:
        raise ValueError('no IMAGE object in label')
    img = _pds3(m.group(1))
    ptr = re.search(r'\(\s*"[^"]+"\s*,\s*(\d+)\s*<BYTES>\s*\)', top.get('^IMAGE', ''))
    if not ptr:
        raise ValueError(f"unexpected ^IMAGE pointer {top.get('^IMAGE')!r}")
    types = re.findall(r'"([^"]+)"', img['INVALID_TYPE'])
    vals = [int(v) for v in re.findall(r'-?\d+', img['INVALID_VALUE'])]
    out = {
        'product_id': Path(_str(top['FILE_NAME'])).stem,
        'instrument_id': _str(top['INSTRUMENT_ID']),
        'product_set': _str(top['PRODUCT_SET_ID']),
        'start_utc': _str(top['START_TIME']), 'stop_utc': _str(top['STOP_TIME']),
        'corrected_start_utc': _str(top['CORRECTED_START_TIME']), 'corrected_stop_utc': _str(top['CORRECTED_STOP_TIME']),
        'sclk_start': _num(top['CORRECTED_SC_CLOCK_START_COUNT']),
        'line_rate_ms': _num(top['CORRECTED_SAMPLING_INTERVAL']),
        'swath_mode': _str(top['SWATH_MODE_ID']),
        'first_pixel': int(_num(top['FIRST_PIXEL_NUMBER'])), 'last_pixel': int(_num(top['LAST_PIXEL_NUMBER'])),
        'moving_direction': int(_num(top['SATELLITE_MOVING_DIRECTION'])),
        'first_detector_elem': _str(top['FIRST_DETECTOR_ELEM_POSITION']),
        'first_sampled_line': _str(top['FIRST_SAMPLED_LINE_POSITION']),
        'exposure_mode': _str(top['EXPOSURE_MODE_ID']),
        'spice_metakernel': _str(top['SPICE_METAKERNEL_FILE_NAME']),
        'centre_lat': _num(top['SCENE_CENTER_LATITUDE']), 'centre_lon': _num(top['SCENE_CENTER_LONGITUDE']),
        'corners': {c: (_num(top[f'{c}_LATITUDE']), _num(top[f'{c}_LONGITUDE']))
                    for c in ('UPPER_LEFT', 'UPPER_RIGHT', 'LOWER_LEFT', 'LOWER_RIGHT')},
        'image_byte_offset': int(ptr.group(1)) - 1,
        'lines': int(_num(img['LINES'])), 'samples': int(_num(img['LINE_SAMPLES'])),
        'sample_type': _str(img['SAMPLE_TYPE']), 'sample_bits': int(_num(img['SAMPLE_BITS'])),
        'scaling_factor': _num(img['SCALING_FACTOR']), 'offset': _num(img['OFFSET']),
        'invalid_codes': dict(zip(types, vals)),
        'compression': _str(img.get('COMPRESSION_TYPE', '"N/A"')),
    }
    if out['instrument_id'] not in IK:
        raise ValueError(f"unexpected INSTRUMENT_ID {out['instrument_id']}")
    if out['sample_type'] != 'MSB_INTEGER' or out['sample_bits'] != 16:
        raise ValueError(f"unexpected sample format {out['sample_type']} / {out['sample_bits']}")
    if FIRST_PIXEL.get(out['swath_mode']) != out['first_pixel']:
        raise ValueError(f"swath {out['swath_mode']} with FIRST_PIXEL_NUMBER {out['first_pixel']} (ISIS: {FIRST_PIXEL})")
    # DCT-compressed products pad each line to a multiple of 8 samples (e.g. 3496 samples for detector 297..3788):
    # the padding follows the last detector pixel. ISIS uses FIRST_PIXEL_NUMBER only, so the model is unchanged.
    out['valid_samples'] = out['last_pixel'] - out['first_pixel'] + 1
    out['pad_samples'] = out['samples'] - out['valid_samples']
    if not 0 <= out['pad_samples'] < 8:
        raise ValueError(f"LINE_SAMPLES {out['samples']} vs detector span {out['valid_samples']}: not 0-7 padding samples")
    if 'SATURATION' not in out['invalid_codes']:
        raise ValueError('label has no SATURATION invalid code')
    return out


def look_cam(ik, first_pixel, samples, sample, flip=False):
    """Unit look vectors in LISM_TC<n>_HEAD for (fractional, 1-based) image samples. `samples` = the valid detector span
    (padding excluded); it only matters for the flipped axis."""
    s = np.asarray(sample, float)
    det = (first_pixel + samples - s) if flip else (s - 1.0 + first_pixel)
    y = -PIXEL_MM * (det - BORESIGHT_SAMPLE)
    x = np.full_like(y, -PIXEL_MM * (0.0 - BORESIGHT_LINE))
    r = np.hypot(x, y)
    cx, cy = ik['cx'], ik['cy']
    bx, by = ik['boresight_xy']
    xu = x + (cx[0] + bx) + cx[1] * r + cx[2] * r * r + cx[3] * r ** 3
    yu = y + (cy[0] + by) + cy[1] * r + cy[2] * r * r + cy[3] * r ** 3
    v = np.stack([xu, yu, np.full_like(yu, ik['focal_mm'])], axis=-1)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


class TcCamera:
    def __init__(self, label, kernels, start='isis', flip=False):
        self.L, self.start, self.flip = label, start, bool(flip)
        self.ik = IK[label['instrument_id']]
        self.sp = spiceypy()
        self.sp.kclear()
        for k in kernels:
            self.sp.furnsh(str(k))
        self.rate = label['line_rate_ms'] / 1000.0
        if start == 'isis':
            self.et0 = self.sp.sct2e(SPACECRAFT_ID, float(label['sclk_start']))
        elif start == 'label':
            self.et0 = self.sp.utc2et(label['corrected_start_utc'].replace('Z', ''))
        else:
            raise ValueError(start)
        self.ifov = PIXEL_MM / self.ik['focal_mm']

    def close(self):
        self.sp.kclear()

    def et(self, line):
        return self.et0 + self.rate * (np.asarray(line, float) - 0.5)

    def timing_check(self):
        s = self.sp
        start = s.utc2et(self.L['corrected_start_utc'].replace('Z', ''))
        stop = s.utc2et(self.L['corrected_stop_utc'].replace('Z', ''))
        return {'startDiffS': float(self.et0 - start), 'stopDiffS': float(self.et(self.L['lines'] + 0.5) - stop),
                'lineRateS': self.rate, 'labelSpanRateS': (stop - start) / self.L['lines']}

    def look_cam(self, sample):
        return look_cam(self.ik, self.L['first_pixel'], self.L['valid_samples'], sample, self.flip)

    def sc_pos_me(self, ets):
        return np.array([self.sp.spkpos('SELENE', float(e), 'MOON_ME', 'NONE', 'MOON')[0] for e in np.atleast_1d(ets)]) * 1000.0

    def cam_to_me(self, ets):
        return np.array([self.sp.pxform(self.ik['frame'], 'MOON_ME', float(e)) for e in np.atleast_1d(ets)])

    def sun_me(self, et):
        p, _lt = self.sp.spkpos('SUN', float(et), 'MOON_ME', 'LT+S', 'MOON')
        p = np.asarray(p) * 1000.0
        return p / np.linalg.norm(p), float(np.linalg.norm(p))

    def rays_me(self, lines, samples):
        lines, samples = np.broadcast_arrays(np.asarray(lines, float), np.asarray(samples, float))
        ets = self.et(lines.ravel())
        P = self.sc_pos_me(ets)
        R = self.cam_to_me(ets)
        return P, np.einsum('nij,nj->ni', R, self.look_cam(samples.ravel()))


def corner_check(cam, radius_m=1_737_400.0):
    """Model vs label corner and centre coordinates (JAXA's own geometry), on the sphere of the label's radius.
    Returns the great-circle distance in metres per point; a reported check, not a gate."""
    from .geometry import _gc
    from .nac_camera import me_to_latlon, sphere_hit
    L = cam.L
    ns = L['valid_samples']
    pts = {'UPPER_LEFT': (0.5, 0.5), 'UPPER_RIGHT': (0.5, ns + 0.5), 'LOWER_LEFT': (L['lines'] + 0.5, 0.5),
           'LOWER_RIGHT': (L['lines'] + 0.5, ns + 0.5), 'CENTER': (L['lines'] / 2 + 0.5, ns / 2 + 0.5)}
    ref = {**L['corners'], 'CENTER': (L['centre_lat'], L['centre_lon'])}
    P, d = cam.rays_me(np.array([v[0] for v in pts.values()]), np.array([v[1] for v in pts.values()]))
    lat, lon = me_to_latlon(sphere_hit(P, d, radius_m))
    return {k: radius_m * np.radians(_gc(lat[i], lon[i], *ref[k])) for i, k in enumerate(pts)}


def osl_source(cam, fit, l0, nl_render_lines, b, s0=1, ns_render=None):
    """OSL push-broom camera for Cycles (as shc_camera.osl_source) with the TC detector, distortion and optional flip.
    Raster v = 1 is the first cropped line; raster u = 0 is the left edge of sample s0 (the cropped sample window)."""
    L, ik = cam.L, cam.ik
    ns = (ns_render if ns_render is not None else L['samples'] // b) * b
    nl = nl_render_lines * b
    cp, cw, Rm = np.asarray(fit['posCoef']), np.asarray(fit['rotCoef']), np.asarray(fit['Rmid'])

    def poly(c, axis):
        terms = [f'{c[k, axis]:.10e}' for k in range(c.shape[0])]
        expr = terms[-1]
        for t in reversed(terms[:-1]):
            expr = f'({t} + tau * {expr})'
        return expr

    rm = [f'{v:.15e}' for v in Rm.ravel()]
    det = (f'{float(L["first_pixel"] + L["valid_samples"]):.4f} - s' if cam.flip else f's - 1.0 + {float(L["first_pixel"]):.4f}')
    cx, cy = ik['cx'], ik['cy']
    bx, by = ik['boresight_xy']
    return f'''// POLARIS X Kaguya TC push-broom camera for {L["product_id"]} (generated by tools/validation/render_vs_real/tc_camera.py)
shader camera(output point position = 0.0, output vector direction = 0.0, output color throughput = 1.0)
{{
  point r = camera_shader_raster_position();
  float s = {s0 - 0.5:.1f} + r[0] * {float(ns)};
  float line = {l0 - 0.5:.6f} + (1.0 - r[1]) * {float(nl)};
  float tau = (line - {fit["lmid"]:.6f}) / {fit["half"]:.6f};
  float det = {det};
  float y = {-PIXEL_MM:.6e} * (det - {BORESIGHT_SAMPLE:.4f});
  float x = {-PIXEL_MM * (0.0 - BORESIGHT_LINE):.6e};
  float rr = sqrt(x * x + y * y);
  float xu = x + ({cx[0] + bx:.8e}) + ({cx[1]:.8e}) * rr + ({cx[2]:.8e}) * rr * rr + ({cx[3]:.8e}) * rr * rr * rr;
  float yu = y + ({cy[0] + by:.8e}) + ({cy[1]:.8e}) * rr + ({cy[2]:.8e}) * rr * rr + ({cy[3]:.8e}) * rr * rr * rr;
  vector lc = normalize(vector(xu, yu, {ik["focal_mm"]:.6f}));
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
