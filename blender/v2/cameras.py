"""Camera presets and physical exposure for the v2 Blender scene. Pure Python, unit-tested in blender/tests/test_cameras.py.

Instrument presets are frame-camera approximations of line-scan (pushbroom) instruments: the cross-track field is reproduced
with the published focal length, pixel pitch and pixel count; the along-track direction is rendered as a frame of the same
IFOV, i.e. one exposure for the whole strip with no spacecraft motion, no TDI and no jitter (line-scan approximation).
Grayscale = Rec.709 luminance of linear radiance, not the instruments' spectral bandpass.

Exposure (all presets): ISO 12232 saturation relation  v = q L_v t S / (78 N^2), q = 0.65, L_v = 93 lm/W * L (W m^-2 sr^-1),
so v = 1 at saturation. Blender film exposure = log2(q 93 t S / (78 N^2)) with the Standard view transform (linear -> sRGB) for
"eye"/"lander" and Raw (linear DN) for instruments. Instruments have no ISO: `equivalent_iso` is an ENGINEERING ASSUMPTION
chosen once per instrument (stated below) so sunlit highland at i = 60 deg sits near 40 % of full scale; ShadowCam's is the NAC's
x 200, from the published sensitivity ratio (">200x the LROC NAC").
"""
from __future__ import annotations

import math

from . import astro

Q_LENS = 0.65
K_SAT = 78.0

# ---------------------------------------------------------------- instrument presets (sources inline)
PRESETS = {
    'lroc_nac': {
        'kind': 'instrument', 'label': 'LROC NAC-L (frame approximation of a pushbroom line)',
        # NAIF lro_lroc_v20.ti: INS-85600_FOCAL_LENGTH = 699.62 (mm), INS-85600_PIXEL_PITCH = 7.0E-3 (mm),
        # INS-85600_PIXEL_SAMPLES = 5064, INS-85600_F/RATIO = 3.577, INS-85600_IFOV = 10.0054E-6;
        # lroc.im-ldi.com/about/specs: "0.5 meter per pixel (10 micro-radian IFOV)" at 50 km, "400-750 nm".
        'focal_mm': 699.62, 'pitch_mm': 7.0e-3, 'pixels': 5064, 'f_number': 3.577, 'ifov_rad': 10.0054e-6,
        'published_pixel_scale_m': 0.5, 'published_altitude_m': 50_000.0, 'band_nm': (400, 760),
        'exposure_s': 0.000338, 'equivalent_iso': 'calibrated',
        'sources': ['https://naif.jpl.nasa.gov/pub/naif/LRO/kernels/ik/lro_lroc_v20.ti', 'https://lroc.im-ldi.com/about/specs'],
    },
    'lroc_wac': {
        'kind': 'instrument', 'label': 'LROC WAC visible 643 nm band (frame camera, 1024 x 1024 detector)',
        # lro_lroc_v20.ti: 643 nm FOCAL_LENGTH 6.0308669 mm, PIXEL_PITCH 9.0E-3 mm, 1024 x 1024; f/5.052 (VIS);
        # specs page: "1.50 milli-radian, 75 meters/pixel (visible)" at 50 km; FOV 61 deg (visible colour).
        'focal_mm': 6.0308669, 'pitch_mm': 9.0e-3, 'pixels': 1024, 'lines': 1024, 'f_number': 5.052, 'ifov_rad': 1.4924e-3,
        'published_pixel_scale_m': 75.0, 'published_altitude_m': 50_000.0, 'band_nm': (632, 655),
        'exposure_s': 0.005, 'equivalent_iso': 'calibrated',
        'sources': ['https://naif.jpl.nasa.gov/pub/naif/LRO/kernels/ik/lro_lroc_v20.ti', 'https://lroc.im-ldi.com/about/specs'],
    },
    'shadowcam': {
        'kind': 'instrument', 'label': 'ShadowCam (KPLO/Danuri), frame approximation of the TDI line',
        # Robinson et al. 2023, J. Astron. Space Sci. 40(4), 149-171, doi:10.5140/JASS.2023.40.4.149, Table 2: focal length
        # 699.275 mm, f/3.6, 3,072 active pixels, IFOV (nadir) 17.16 urad, 1.7 m at 100 km, FOV 2.86 deg, 410-780 nm;
        # shadowcam.im-ldi.com/about: "Pixel Size 12 um", "Sensitivity >200x the LROC NAC".
        'focal_mm': 699.275, 'pitch_mm': 12.0e-3, 'pixels': 3072, 'f_number': 3.6, 'ifov_rad': 17.16e-6,
        'published_pixel_scale_m': 1.7, 'published_altitude_m': 100_000.0, 'band_nm': (410, 780),
        'exposure_s': 0.000338, 'equivalent_iso': 'nac_x200',
        'sources': ['https://doi.org/10.5140/JASS.2023.40.4.149', 'https://shadowcam.im-ldi.com/about'],
    },
    'kaguya_tc': {
        'kind': 'instrument', 'label': 'SELENE (Kaguya) Terrain Camera, nominal swath, frame approximation',
        # USGS STAC (stac.astrogeology.usgs.gov/docs/data/moon/kaguyatc): "detectors were both 4096 pixels wide but nominal
        # imaging used 3504 pixels", "10 m/pixel ground sampling distance" from 100 km, "single panchromatic band ... 0.43 to
        # 0.85 um", "~15 deg forward and backward". Focal length and pixel pitch were NOT found in a source reachable tonight:
        # pitch 7 um / focal 72.45 mm are UNVERIFIED values (from memory of Haruyama et al. 2008) that reproduce the published
        # 9.7-10 m/pixel at 100 km; flagged in the manifest.
        'focal_mm': 72.45, 'pitch_mm': 7.0e-3, 'pixels': 3504, 'f_number': 3.97, 'ifov_rad': 7.0e-3 / 72.45,
        'published_pixel_scale_m': 10.0, 'published_altitude_m': 100_000.0, 'band_nm': (430, 850),
        'exposure_s': 0.0013, 'equivalent_iso': 'calibrated', 'unverified': ['focal_mm', 'pitch_mm', 'f_number'],
        'sources': ['https://stac.astrogeology.usgs.gov/docs/data/moon/kaguyatc'],
    },
    'eva_eye': {
        'kind': 'surface', 'label': 'Human EVA eye height 1.7 m, 50 mm on 36 mm (39.6 deg horizontal)',
        'focal_mm': 50.0, 'sensor_mm': 36.0, 'f_number': 8.0, 'exposure_s': 1 / 250, 'iso': 100.0, 'height_m': 1.7,
        'view_transform': 'Standard',
    },
    'lander_cam': {
        'kind': 'surface', 'label': 'Lander deck camera 3.0 m above ground, 24 mm on 36 mm (73.7 deg), ILLUSTRATIVE mount',
        'focal_mm': 24.0, 'sensor_mm': 36.0, 'f_number': 8.0, 'exposure_s': 1 / 250, 'iso': 100.0, 'height_m': 3.0,
        'view_transform': 'Standard',
    },
}


CAL_TARGET = 0.4                 # fraction of full scale for the calibration scene below
CAL_GEOMETRY_DEG = (60.0, 0.0, 60.0)   # i, e, g: the LROC WAC normalisation geometry
SHADOWCAM_GAIN_VS_NAC = 200.0    # published: ">200x the LROC NAC" (lower bound used)


def calibrated_iso(p, hapke_params=None):
    """ENGINEERING ASSUMPTION: the ISO that puts Hapke regolith (643 nm SOUTH_60_70 parameters) at i=60, e=0, g=60 under a
    1 AU Sun at CAL_TARGET of full scale with this preset's f-number and exposure time."""
    from . import hapke
    hp = hapke_params or hapke.params()
    L = hapke.reference_r(hp, *CAL_GEOMETRY_DEG) * astro.TSI_W_M2
    return CAL_TARGET / (L * exposure_scale(p['f_number'], p['exposure_s'], 1.0))


def preset(name):
    if name not in PRESETS:
        raise KeyError(f'camera preset {name!r}; have {sorted(PRESETS)}')
    p = dict(PRESETS[name], name=name)
    if p.get('equivalent_iso') == 'calibrated':
        p['equivalent_iso'] = calibrated_iso(p)
        p['isoRule'] = f'calibrated: Hapke regolith at i,e,g = {CAL_GEOMETRY_DEG} deg, 1 AU -> {CAL_TARGET:.0%} full scale (ENGINEERING ASSUMPTION)'
    elif p.get('equivalent_iso') == 'nac_x200':
        nac = PRESETS['lroc_nac']
        p['equivalent_iso'] = calibrated_iso(nac) * SHADOWCAM_GAIN_VS_NAC * (p['f_number'] / nac['f_number']) ** 2 * (nac['exposure_s'] / p['exposure_s'])
        p['isoRule'] = 'LROC NAC calibrated ISO x 200 (published sensitivity ratio), corrected for f-number and line time: same scene -> 200x the NAC signal'
    return p


def ifov_from_optics(p):
    return p['pitch_mm'] / p['focal_mm']


def pixel_scale_m(p, range_m):
    """Ground pixel scale at nadir for a frame/pushbroom camera at `range_m`."""
    return ifov_from_optics(p) * range_m


def sensor_width_mm(p, pixels=None):
    return p.get('sensor_mm') or p['pitch_mm'] * (pixels or p['pixels'])


def fov_deg(p):
    return math.degrees(2 * math.atan(sensor_width_mm(p) / (2 * p['focal_mm'])))


def exposure_scale(f_number, t_s, iso):
    """Linear factor: scene radiance (W m^-2 sr^-1) -> fraction of saturation."""
    return Q_LENS * astro.LUMINOUS_EFFICACY_SUN * t_s * iso / (K_SAT * f_number * f_number)


def exposure_stops(p):
    iso = p.get('iso') or p.get('equivalent_iso')
    return math.log2(exposure_scale(p['f_number'], p['exposure_s'], iso))


def render_layout(p, max_px=512):
    """Rendered resolution (capped) and the effective IFOV after downscaling. Instruments keep their FOV; when the published
    pixel count exceeds `max_px` the render is coarser by the stated factor (recorded)."""
    if p['kind'] == 'instrument':
        nx = p['pixels']
        ny = p.get('lines') or nx                     # along-track: a square piece of the strip (frame approximation)
        scale = min(1.0, max_px / max(nx, ny))
        rx, ry = max(16, round(nx * scale)), max(16, round(ny * scale))
        return {'resolution': (rx, ry), 'downscale': nx / rx, 'effectiveIfovRad': ifov_from_optics(p) * nx / rx,
                'sensor_mm': sensor_width_mm(p), 'sensorFit': 'HORIZONTAL'}
    rx, ry = max_px, round(max_px * 9 / 16)
    return {'resolution': (rx, ry), 'downscale': 1.0, 'effectiveIfovRad': math.radians(fov_deg(p)) / rx,
            'sensor_mm': p['sensor_mm'], 'sensorFit': 'HORIZONTAL'}
