"""ShadowCam (KPLO) camera model and catalogue v2 pieces: constants vs the cached USGS kernels, look geometry, kernel choice."""
import datetime as dt
import math
import re
import unittest

import numpy as np

from tools.validation.render_vs_real import shc_camera as C
from tools.validation.render_vs_real import shc_kernels as K


def _vals(txt, key):
    m = re.search(rf'{re.escape(key)}\s*=\s*\(?([^)\n]*)\)?', txt)
    return [float(x) for x in re.findall(r'[-+]?\d[\d.]*(?:[EeDd][-+]?\d+)?', m.group(1).replace('D', 'E'))]


class Constants(unittest.TestCase):
    @unittest.skipUnless((K.KDIR / 'kplo_shadowcam_v00.ti').exists(), 'KPLO IK not cached')
    def test_ik_and_iak_values(self):
        ik = (K.KDIR / 'kplo_shadowcam_v00.ti').read_text()
        self.assertAlmostEqual(_vals(ik, 'INS-155151_FOCAL_LENGTH')[0], C.IK['focal_mm'])
        self.assertEqual(_vals(ik, 'INS-155151_BORESIGHT_SAMPLE')[0], C.IK['boresight_sample'])
        self.assertEqual(_vals(ik, 'INS-155151_BORESIGHT_LINE')[0], C.IK['boresight_line'])
        self.assertAlmostEqual(_vals(ik, 'INS-155151_OD_K')[0], C.IK['od_k'])
        self.assertEqual(_vals(ik, 'INS-155151_TRANSY')[:3], [0.0, C.IK['pixel_mm'], 0.0])
        self.assertEqual(_vals(ik, 'INS-155151_TRANSX')[:3], [0.0, 0.0, C.IK['pixel_mm']])
        self.assertEqual(_vals(ik, 'INS-155151_PIXEL_SAMPLES')[0], C.IK['detector_samples'])
        iak = (K.KDIR / 'kplo_instrumentAddendum_v02.ti').read_text()
        for k in ('TDI_A_OFFSET', 'TDI_B_OFFSET', 'CONSTANT_TIME_OFFSET', 'ADDITIVE_LINE_ERROR', 'MULTIPLI_LINE_ERROR'):
            self.assertEqual(_vals(iak, f'INS-155151_{k}')[0], C.IAK[k])


class Look(unittest.TestCase):
    def cam(self, sfp=0):
        c = C.ShcCamera.__new__(C.ShcCamera)
        c.L = {'sample_first_pixel': sfp}
        return c

    def test_boresight_and_ifov(self):
        c = self.cam()
        v = c.look_cam(np.array([1558.0, 1559.0]))
        # along-track: line-scan detector line 0 vs boresight line 1 -> x = -0.012 mm (one pixel)
        self.assertAlmostEqual(v[0, 0] / v[0, 2], -0.012 / 699.275, places=9)
        self.assertAlmostEqual(v[0, 1], 0.0, places=12)
        ang = math.acos(float(v[0] @ v[1]))
        self.assertAlmostEqual(ang / C.IK['ifov_rad'], 1.0, places=2)

    def test_first_pixel_shifts_samples(self):
        a = self.cam(0).look_cam(np.array([100.0]))
        b = self.cam(72).look_cam(np.array([28.0]))
        np.testing.assert_allclose(a, b)


class Kernels(unittest.TestCase):
    def test_end_date_is_exclusive(self):
        listing = [['usgs_data/kplo/kernels/spk/kplo_d_20221231_20230103_v01.bsp', 10],
                   ['usgs_data/kplo/kernels/spk/kplo_d_20230101_20230104_v00.bsp', 20]]
        old = K.listing
        try:
            K.listing = lambda kind, refresh=False: listing
            best = K._covering('spk', dt.datetime(2023, 1, 3, 17, 58), dt.datetime(2023, 1, 3, 18, 1))
        finally:
            K.listing = old
        self.assertEqual(best[1].split('/')[-1], 'kplo_d_20230101_20230104_v00.bsp')


class Label(unittest.TestCase):
    def test_parse_without_header(self):
        from tools.validation.render_vs_real.shc_catalogue import LABELS
        p = LABELS / 'M013114234SC.xml'
        if not p.exists():
            self.skipTest('dev label not cached')
        lab = C.parse_label(p.read_bytes())
        self.assertEqual((lab['lines'], lab['samples'], lab['tdi_direction']), (83968, 3072, 'A'))
        self.assertIsNone(lab['sample_first_pixel'])
        self.assertAlmostEqual(lab['line_rate_ms'], 1.20115)


if __name__ == '__main__':
    unittest.main()


class Frozen(unittest.TestCase):
    def test_held_out_run_freezes_every_shadowcam_module_it_executes(self):
        from pathlib import Path
        from tools.validation.render_vs_real import shc_heldout
        here = Path(shc_heldout.__file__).parent
        mods = {f'tools/validation/render_vs_real/{p.name}' for p in here.glob('shc_*.py')
                if p.name not in ('shc_report.py', 'shc_pipeline_test.py')}
        self.assertEqual(mods - set(shc_heldout.FROZEN_CODE), set())
        self.assertIn('tools/validation/render_vs_real/wac_twin.py', shc_heldout.FROZEN_CODE)

    def test_catalogue_v2_hash_is_pinned(self):
        from tools.validation.render_vs_real import shc_common
        from tools.validation.render_vs_real.common import sha256_file
        self.assertEqual(sha256_file(shc_common.CATALOGUE_V2), shc_common.CATALOGUE_V2_SHA256)


class Saturation(unittest.TestCase):
    """A10: directly sunlit ground saturates ShadowCam. Protocol §4.1 counts saturated window pixels as lit; the A8.5 dev
    pilot had dropped them from the window, which removed the lit class (dev: saturated 40 % of the window, predicted lit
    39 %, IoU(saturated, predicted lit) 0.91 unregistered)."""

    def test_saturated_blocks_count_as_lit(self):
        from tools.validation.render_vs_real import score as S
        from tools.validation.render_vs_real.shc_run import SATURATION_RULE, saturation_fill
        self.assertEqual(SATURATION_RULE, 'lit')
        rng = np.random.default_rng(0)
        val = np.exp(rng.normal(-3.0, 0.5, (60, 80)))       # scattered-light shadow, log-normal radiance
        val[:, :20] *= 0.2                                   # a darker strip inside the shadow (the A8.5 failure mode)
        sat = np.zeros(val.shape, bool)
        sat[:, 50:] = True                                   # directly sunlit -> saturated, no radiance
        inv = np.zeros(val.shape, bool)
        inv[0, :] = True
        val[sat | inv] = np.nan
        real = saturation_fill(val, inv, sat)
        window = ~inv & np.isfinite(real)
        self.assertTrue(window[1:, 50:].all(), 'saturated blocks must stay in the window')
        self.assertEqual(float(real[5, 60]), float(np.nanmax(val[~sat & ~inv])))
        ns = window & ~sat
        rn, _ = S.normalise(real, ns)
        obs, _ = S.observed_shadow(rn, window, sat)
        self.assertFalse(obs[:, 50:].any(), 'saturated pixels are lit')
        pred = np.zeros(val.shape, bool)
        pred[:, :50] = True
        a = S.agreement(pred, obs, window)
        self.assertAlmostEqual(a['iouLit'], 0.5, delta=0.05)    # Otsu still splits the dark strip from the rest of the shadow
        cm = S.agreement(pred, S.count_matched_shadow(rn, window, int((~pred & window).sum())), window)
        self.assertGreater(cm['iouShadow'], 0.99)

    def test_dropped_rule_still_available_for_the_registered_a85_pilot(self):
        from tools.validation.render_vs_real import shc_run
        self.assertIn('dropped', shc_run.load_real.__code__.co_consts)
