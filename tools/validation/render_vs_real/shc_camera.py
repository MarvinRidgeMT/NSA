"""KPLO ShadowCam push-broom camera model from the PDS4 label + ISIS cube header + KPLO SPICE, in MOON_ME.

Model = ISIS ShadowCamCamera / ShadowCamDistortionMap (DOI-USGS/ISIS3 isis/src/kplo/objs/ShadowCamCamera, merged
2026-04-27) with LineScanCameraDetectorMap, CameraDetectorMap and CameraFocalPlaneMap, and the IK kplo_shadowcam_v00.ti +
IAK kplo_instrumentAddendum_v02.ti (USGS public kernels; values copied below, a test compares them with the cached files):
  line rate   r = LineRate * (1 + MULTIPLI_LINE_ERROR) + ADDITIVE_LINE_ERROR          (IAK: 0, 0)
  et_start    = et(SCLK ExecutionSpacecraftTime) + StartTimeOffset + CONSTANT_TIME_OFFSET + TDI_<dir>_OFFSET * r
  et(line)    = et_start + r * (line - 0.5)                                          (ISIS line, 1-based)
  detector    sample_det = sample + SampleFirstPixel; line_det = 0 (line-scan detector line offset)
  focal (mm)  cs = sample_det - BORESIGHT_SAMPLE (1558), cl = line_det - BORESIGHT_LINE (1) = -1
              x = 0.012 * cl, y = 0.012 * cs                                         (TRANSX, TRANSY)
  undistorted y_u = y * (1 + OD_K * y^2), x_u = x                                    (OD_K = -1.741e-5)
  look        (x_u, y_u, FOCAL_LENGTH) in KPLO_SHC_A; attitude from the KPLO CK (frame -155000) via kplo_v06.tf
TDI direction B: ISIS's camera has no sample flip, ALE's driver flips the sample axis. Only direction A is modelled until
a dev image settles B (A8). Spacecraft: spkpos('KPLO', et, 'MOON_ME', 'NONE', 'MOON'); Sun: 'LT+S' as for the NAC.
Status: SOURCE-BASED · UNVALIDATED (checked against the label's ASU centre-pixel and sub-spacecraft points).
"""
from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from .common import spiceypy

IK = {'code': -155151, 'frame': 'KPLO_SHC_A', 'focal_mm': 699.275, 'boresight_sample': 1558.0, 'boresight_line': 1.0,
      'pixel_mm': 0.012, 'od_k': -1.741e-5, 'detector_samples': 3144, 'ifov_rad': 1.71606e-5}
IAK = {'TDI_A_OFFSET': 64.0, 'TDI_B_OFFSET': 64.0, 'CONSTANT_TIME_OFFSET': 0.0, 'ADDITIVE_LINE_ERROR': 0.0,
       'MULTIPLI_LINE_ERROR': 0.0}
SPACECRAFT_ID = -155
NS = {'pds': 'http://pds.nasa.gov/pds4/pds/v1', 'kplo': 'http://www.kari.re.kr/kpds/mission/kplo/v1',
      'geom': 'http://pds.nasa.gov/pds4/geom/v1'}
SOURCES = ['https://asc-isisdata.s3.us-west-2.amazonaws.com/usgs_data/kplo/kernels/ (IK, IAK, FK, SCLK, CK, SPK)',
           'https://github.com/DOI-USGS/ISIS3 isis/src/kplo/objs/ShadowCamCamera/ (camera, distortion map)',
           'https://github.com/DOI-USGS/ISIS3 isis/src/base/objs/{CameraDetectorMap,LineScanCameraDetectorMap,CameraFocalPlaneMap}/']


def _hex(s):
    return int(s.strip(), 16)


def parse_label(xml_bytes, header_bytes=None):
    """PDS4 label fields + ISIS cube header (first 64 KiB of the .cub: SampleFirstPixel, TDIDirection, LineRate).
    Without the header (catalogue footprints), SampleFirstPixel is None and the format checks are skipped."""
    root = ET.fromstring(xml_bytes)

    def f(path):
        e = root.find(path, NS)
        return None if e is None else (e.text or '').strip()

    arr = root.find('.//pds:Array_2D_Image', NS)
    axes = {a.find('pds:axis_name', NS).text: int(a.find('pds:elements', NS).text) for a in arr.findall('pds:Axis_Array', NS)}
    sc = arr.find('pds:Special_Constants', NS)
    hdr = header_bytes.decode('latin-1').replace('\x00', '') if header_bytes else ''

    def h(key):
        m = re.search(rf'^\s*{key}\s*=\s*"?([^"\n<]+?)"?\s*(<[^>]*>)?\s*$', hdr, re.M)
        return m.group(1).strip() if m else None
    out = {
        'product_id': Path(f('.//pds:File/pds:file_name')).stem,
        'file_size': int(f('.//pds:File/pds:file_size')), 'md5': f('.//pds:File/pds:md5_checksum'),
        'start_utc': f('.//pds:Time_Coordinates/pds:start_date_time'),
        'stop_utc': f('.//pds:Time_Coordinates/pds:stop_date_time'),
        'exec_sclk': f('.//kplo:execution_spacecraft_time'),
        'start_time_offset_s': float(f('.//kplo:start_time_offset')),
        'line_rate_ms': float(f('.//kplo:line_rate_ms')),
        'tdi_direction': f('.//kplo:tdi_direction'),
        'data_offset': int(arr.find('pds:offset', NS).text),
        'lines': axes['Line'], 'samples': axes['Sample'],
        'data_type': arr.find('pds:Element_Array/pds:data_type', NS).text,
        'unit': arr.find('pds:Element_Array/pds:unit', NS).text,
        'special_bits': {c.tag.split('}')[1]: _hex(c.text) for c in sc} if sc is not None else {},
        'centre_lat': float(f('.//geom:Pixel_Intercept/geom:pixel_latitude')),
        'centre_lon': float(f('.//geom:Pixel_Intercept/geom:pixel_longitude')),
        'subsc_lat': float(f('.//geom:subspacecraft_latitude')), 'subsc_lon': float(f('.//geom:subspacecraft_longitude')),
        'geometry_utc': f('.//geom:geometry_reference_time_utc'),
        'sample_first_pixel': int(h('SampleFirstPixel')) if h('SampleFirstPixel') is not None else None,
        'header_tdi': h('TDIDirection'), 'header_line_rate_ms': float(h('LineRate')) if h('LineRate') else None,
        'header_format': h('Format'), 'header_start_byte': int(h('StartByte')) if h('StartByte') else None,
        'data_quality_id': f('.//kplo:data_quality_id'),
    }
    if out['data_type'] != 'IEEE754LSBSingle' or (header_bytes and out['header_format'] != 'BandSequential'):
        raise ValueError(f"unexpected array {out['data_type']} / {out['header_format']}")
    if out['header_tdi'] and out['header_tdi'] != out['tdi_direction']:
        raise ValueError(f"TDI direction label {out['tdi_direction']} != header {out['header_tdi']}")
    if out['samples'] + (out['sample_first_pixel'] or 0) > IK['detector_samples']:
        raise ValueError('samples + SampleFirstPixel exceed the 3144-sample detector')
    return out


class ShcCamera:
    def __init__(self, label, kernels, start='isis', flip=None):
        """start: 'isis' (SCLK ExecutionSpacecraftTime + StartTimeOffset) or 'label' (label start_date_time); both + TDI offset.
        flip: sample-axis flip (ALE convention for TDI B). None = no flip for A; B requires an explicit choice (A8/A9)."""
        if label['sample_first_pixel'] is None:
            raise ValueError('the cube header (SampleFirstPixel) is required for rendering')
        if flip is None:
            if label['tdi_direction'] != 'A':
                raise NotImplementedError(f"TDI direction {label['tdi_direction']}: the sample flip must be chosen explicitly")
            flip = False
        self.flip, self.start = bool(flip), start
        self.L = label
        self.sp = spiceypy()
        self.sp.kclear()
        for k in kernels:
            self.sp.furnsh(str(k))
        self.rate = label['line_rate_ms'] / 1000.0 * (1.0 + IAK['MULTIPLI_LINE_ERROR']) + IAK['ADDITIVE_LINE_ERROR']
        if start == 'isis':
            t_start = self.sp.scs2e(SPACECRAFT_ID, label['exec_sclk']) + label['start_time_offset_s']
        elif start == 'label':
            t_start = self.sp.utc2et(label['start_utc'].replace('Z', ''))
        else:
            raise ValueError(start)
        self.et0 = t_start + IAK['CONSTANT_TIME_OFFSET'] + IAK[f"TDI_{label['tdi_direction']}_OFFSET"] * self.rate
        self.ifov = IK['ifov_rad']

    def close(self):
        self.sp.kclear()

    def et(self, line):
        return self.et0 + self.rate * (np.asarray(line, float) - 0.5)

    def timing_check(self):
        s = self.sp
        start = s.utc2et(self.L['start_utc'].replace('Z', ''))
        stop = s.utc2et(self.L['stop_utc'].replace('Z', ''))
        return {'startDiffS': float(self.et0 - start), 'stopDiffS': float(self.et(self.L['lines'] + 0.5) - stop),
                'lineRateS': self.rate, 'labelSpanRateS': (stop - start) / self.L['lines']}

    def look_cam(self, sample):
        s = np.asarray(sample, float)
        det = (s - 1.0) + 1.0 + self.L['sample_first_pixel']             # (sample-1)*sum + sum/2 + 0.5 + (first-1), sum 1
        y = IK['pixel_mm'] * (det - IK['boresight_sample']) * (-1.0 if getattr(self, 'flip', False) else 1.0)
        x = np.full_like(y, IK['pixel_mm'] * (0.0 - IK['boresight_line']))
        yu = y * (1.0 + IK['od_k'] * y * y)
        v = np.stack([x, yu, np.full_like(yu, IK['focal_mm'])], axis=-1)
        return v / np.linalg.norm(v, axis=-1, keepdims=True)

    def sc_pos_me(self, ets):
        return np.array([self.sp.spkpos('KPLO', float(e), 'MOON_ME', 'NONE', 'MOON')[0] for e in np.atleast_1d(ets)]) * 1000.0

    def cam_to_me(self, ets):
        return np.array([self.sp.pxform(IK['frame'], 'MOON_ME', float(e)) for e in np.atleast_1d(ets)])

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


def footprint(cam, radius_m, n_along=64, n_across=8):
    """Image outline on the sphere of `radius_m`: (lat, lon) arrays of the boundary pixels, in order around the image."""
    from .nac_camera import me_to_latlon, sphere_hit
    L = cam.L
    ls = np.linspace(0.5, L['lines'] + 0.5, n_along)
    ss = np.linspace(0.5, L['samples'] + 0.5, n_across)
    edge = ([(l, ss[0]) for l in ls] + [(ls[-1], s) for s in ss[1:]] + [(l, ss[-1]) for l in ls[::-1][1:]] +
            [(ls[0], s) for s in ss[::-1][1:]])
    P, d = cam.rays_me(np.array([e[0] for e in edge]), np.array([e[1] for e in edge]))
    X = sphere_hit(P, d, radius_m)
    return me_to_latlon(X)


def osl_source(cam, fit, l0, nl_render_lines, b):
    """OSL push-broom camera for Cycles, as nac_camera.osl_source but with the ShadowCam detector, along-track offset,
    distortion y_u = y (1 + k y^2) and optional sample flip. Raster v = 1 is the first cropped line."""
    L = cam.L
    ns = L['samples'] // b * b
    nl = nl_render_lines * b
    cp, cw, Rm = np.asarray(fit['posCoef']), np.asarray(fit['rotCoef']), np.asarray(fit['Rmid'])

    def poly(c, axis):
        terms = [f'{c[k, axis]:.10e}' for k in range(c.shape[0])]
        expr = terms[-1]
        for t in reversed(terms[:-1]):
            expr = f'({t} + tau * {expr})'
        return expr

    rm = [f'{v:.15e}' for v in Rm.ravel()]
    sgn = -1.0 if cam.flip else 1.0
    return f'''// POLARIS X ShadowCam push-broom camera for {L["product_id"]} (generated by tools/validation/render_vs_real/shc_camera.py)
shader camera(output point position = 0.0, output vector direction = 0.0, output color throughput = 1.0)
{{
  point r = camera_shader_raster_position();
  float s = 0.5 + r[0] * {float(ns)};
  float line = {l0 - 0.5:.6f} + (1.0 - r[1]) * {float(nl)};
  float tau = (line - {fit["lmid"]:.6f}) / {fit["half"]:.6f};
  float det = s + {float(L["sample_first_pixel"])};
  float y = {sgn * IK["pixel_mm"]:.6e} * (det - {IK["boresight_sample"]:.4f});
  float x = {IK["pixel_mm"] * (0.0 - IK["boresight_line"]):.6e};
  y = y * (1.0 + {IK["od_k"]:.6e} * y * y);
  vector lc = normalize(vector(x, y, {IK["focal_mm"]:.6f}));
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

