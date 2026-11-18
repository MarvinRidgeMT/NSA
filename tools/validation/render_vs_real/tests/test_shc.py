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
