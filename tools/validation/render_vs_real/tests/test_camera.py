"""NAC camera model: label parsing, detector mapping, rotation helpers, and (when the kernels are cached) the fitted
per-line states against direct SPICE."""
import json
from pathlib import Path

import numpy as np
import pytest

from tools.validation.render_vs_real import nac_camera as C
from tools.validation.render_vs_real.common import SPICE_DIR, WORK

FIX = Path(__file__).parent / 'fixtures' / 'M162485477LC.xml'


def test_parse_label():
    L = C.parse_label(FIX.read_bytes())
    assert L['frame_id'] == 'LEFT' and L['crosstrack_summing'] == 2 and L['samples'] == 2532 and L['lines'] == 52224
    assert L['data_offset'] == 5064 and L['special']['missing_constant'] == -32768
    assert L['scaling_factor'] == pytest.approx(3.05185094759972e-05)


class _Cam(C.NacCamera):
    def __init__(self, label):          # no SPICE: detector mapping only
        self.L, self.ik, self.csum = label, C.IK[label['frame_id']], label['crosstrack_summing']


def test_detector_mapping_boresight_and_distortion():
    L = C.parse_label(FIX.read_bytes())
    cam = _Cam(L)
    # summed sample s whose detector coordinate is the boresight (2548): (s-1)*2 + 1.5 = 2548 -> s = 1274.25
    v = cam.look_cam(np.array([1274.25]))[0]
    assert abs(v[1]) < 1e-12 and v[2] == pytest.approx(1.0)
    # edge: 5064-pixel detector, y = 0.007*(5064.5-2548) mm; distortion shrinks it by 1/(1+k y^2)
    y = 0.007 * (5064.0 - 2548.0)
    yu = y / (1 + 1.81e-5 * y * y)
    v = cam.look_cam(np.array([2532.0 + 0.25]))[0]
    assert v[1] / v[2] == pytest.approx(yu / 699.62, rel=1e-9)
    # NAC-R mirrors the sample axis
    R = dict(L, frame_id='RIGHT')
    assert _Cam(R).look_cam(np.array([10.0]))[0][1] > 0 > cam.look_cam(np.array([10.0]))[0][1]


def test_rotvec_roundtrip():
    w = np.array([[1e-3, -2e-3, 5e-4], [0.3, 0.1, -0.2]])
    assert np.allclose(C.matrix_to_rotvec(C.rotvec_to_matrix(w)), w, atol=1e-12)


def test_fitted_states_match_spice_when_kernels_are_cached():
    g = WORK / 'geometry' / 'M162485477LC__site04_roi3.json'
    if not g.exists() or not (SPICE_DIR / 'lrosc_2011162_2011165_v01.bc').exists():
        pytest.skip('SPICE kernels / geometry not cached in this checkout')
    G = json.loads(g.read_text())
    kern = [SPICE_DIR / k for k in G['kernels'].split()]
    cam = C.NacCamera(G['label'], kern)
    try:
        M, P0 = C.enu_basis(G['enu']['lat'], G['enu']['lon'], G['enu']['h0'])
        lines = np.linspace(G['l0'], G['l1'], 7)
        samples = np.array([1, 600, 1266, 2000, 2532], float)
        LL, SS = np.meshgrid(lines, samples, indexing='ij')
        P, d = cam.rays_me(LL, SS)
        Pf, df = C.fitted_rays_enu(cam, G['fit'], LL, SS)
        assert np.abs((P - P0) @ M.T - Pf).max() < 0.05
        ang = np.arccos(np.clip(np.einsum('ij,ij->i', d @ M.T, df), -1, 1))
        assert ang.max() < 5e-6
        tc = cam.timing_check()
        assert abs(tc['startDiffS']) < 2e-3 and abs(tc['lineRateS'] / tc['labelSpanRateS'] - 1) < 1e-5
    finally:
        cam.close()
