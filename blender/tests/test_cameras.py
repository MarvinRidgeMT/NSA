import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v2 import cameras as C  # noqa: E402
from v2 import hapke  # noqa: E402


class Instruments(unittest.TestCase):
    def test_pixel_scale_matches_published(self):
        """Focal length + pitch reproduce each instrument's published pixel scale at its reference altitude (within 4 %)."""
        for name in ('lroc_nac', 'lroc_wac', 'shadowcam', 'kaguya_tc'):
            p = C.preset(name)
            got = C.pixel_scale_m(p, p['published_altitude_m'])
            self.assertAlmostEqual(got / p['published_pixel_scale_m'], 1.0, delta=0.04, msg=(name, got))

    def test_ifov_matches_kernel(self):
        for name in ('lroc_nac', 'shadowcam'):
            p = C.preset(name)
            self.assertAlmostEqual(C.ifov_from_optics(p) / p['ifov_rad'], 1.0, delta=0.02, msg=name)

    def test_unverified_values_are_flagged(self):
        self.assertIn('focal_mm', C.preset('kaguya_tc')['unverified'])

    def test_render_layout_caps_resolution_and_records_downscale(self):
        p = C.preset('lroc_nac')
        lay = C.render_layout(p, 512)
        self.assertEqual(max(lay['resolution']), 512)
        self.assertAlmostEqual(lay['downscale'], 5064 / 512, places=6)
        self.assertAlmostEqual(lay['effectiveIfovRad'], C.ifov_from_optics(p) * 5064 / 512, places=12)


class Exposure(unittest.TestCase):
    def test_iso12232_saturation_relation(self):
        # v = q L_v t S / (78 N^2): doubling t or S doubles v; doubling N quarters it
        a = C.exposure_scale(8, 1 / 250, 100)
        self.assertAlmostEqual(C.exposure_scale(8, 2 / 250, 100), 2 * a)
        self.assertAlmostEqual(C.exposure_scale(16, 1 / 250, 100), a / 4)
        self.assertAlmostEqual(a, 0.65 * 93 * (1 / 250) * 100 / (78 * 64))

    def test_calibrated_instruments_hit_the_target(self):
        L = hapke.reference_r(hapke.params(), 60, 0, 60) * 1361.0
        for name in ('lroc_nac', 'lroc_wac', 'kaguya_tc'):
            p = C.preset(name)
            v = L * 2 ** C.exposure_stops(p)
            self.assertAlmostEqual(v, C.CAL_TARGET, places=9, msg=name)

    def test_shadowcam_is_200x_nac_for_the_same_scene(self):
        nac, sc = C.preset('lroc_nac'), C.preset('shadowcam')
        self.assertAlmostEqual(2 ** C.exposure_stops(sc) / 2 ** C.exposure_stops(nac), 200.0, places=6)

    def test_surface_presets(self):
        eye = C.preset('eva_eye')
        self.assertEqual(eye['height_m'], 1.7)
        self.assertAlmostEqual(C.fov_deg(eye), math.degrees(2 * math.atan(18 / 50)), places=9)


if __name__ == '__main__':
    unittest.main()
