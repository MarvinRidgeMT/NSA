"""LROC WAC pipeline (A6): camera constants, model geometry, frame-set layout, specials, OSL precision, strip-aware scoring.

No WAC image is needed except where a test says it is skipped without the local cache."""
import json
import math
import re
import unittest
from pathlib import Path

import numpy as np

from tools.validation.render_vs_real import wac_camera as W
from tools.validation.render_vs_real import wac_common as WC
from tools.validation.render_vs_real.common import HeldOutError, SPICE_DIR, read_catalogue

IK_FILE = SPICE_DIR / 'lro_lroc_v20.ti'


class Camera(unittest.TestCase):
    def cam(self):
        c = W.WacCamera.__new__(W.WacCamera)
        c.F = W.FILTER
        return c

    @unittest.skipUnless(IK_FILE.exists(), 'NAIF IK not cached')
    def test_constants_match_the_naif_ik(self):
        txt = IK_FILE.read_text()

        def vals(key):
            m = re.search(rf'{re.escape(key)}\s*=\s*\(?([^)\n]*(?:\n\s+[-+0-9.Ee][^)\n]*)*)\)?', txt)
            return [float(x.replace('D', 'E')) for x in re.findall(r'[-+]?\d[\d.]*(?:[EeDd][-+]?\d+)?', m.group(1))]
        F = W.FILTER
        self.assertAlmostEqual(vals('INS-85634_FOCAL_LENGTH')[0], F['focal_mm'], places=7)
        self.assertAlmostEqual(vals('INS-85634_BORESIGHT_SAMPLE')[0], F['boresight_sample'], places=4)
        self.assertAlmostEqual(vals('INS-85634_BORESIGHT_LINE')[0], F['boresight_line'], places=4)
        self.assertEqual(vals('INS-85634_FILTER_OFFSET')[0], F['filter_offset'])
        self.assertEqual(vals('INS-85634_FILTER_BANDCENTER')[0], F['band_nm'])
        self.assertEqual(vals('INS-85621_COLOR_SAMPLE_OFFSET')[0], F['color_sample_offset'])
        for key, mine in (('INS-85634_OD_K', F['od_k']), ('INS-85634_TRANSX', F['transx']), ('INS-85634_TRANSY', F['transy'])):
            np.testing.assert_allclose(vals(key)[:3], mine, rtol=1e-12, atol=1e-15)

    def test_boresight_pixel_looks_along_z_and_ifov(self):
        c = self.cam()
        F = W.FILTER
        s_bore = F['boresight_sample'] + 1.0 - F['color_sample_offset']
        fl_bore = F['boresight_line'] + 1.0 - F['filter_offset']
        v = c.look_cam(np.array([s_bore]), np.array([fl_bore]))[0]
        np.testing.assert_allclose(v, [0, 0, 1], atol=1e-6)
        a, b = c.look_cam(np.array([s_bore, s_bore + 1]), np.array([fl_bore, fl_bore]))
        self.assertAlmostEqual(math.acos(float(a @ b)) / W.IFOV_RAD, 1.0, places=2)
        # samples map to focal-plane +y, lines to -x (TRANSX/TRANSY), and distortion grows outward
        e = c.look_cam(np.array([1.0, 704.0]), np.array([7.0, 7.0]))
        self.assertLess(e[0, 1], 0)
        self.assertGreater(e[1, 1], 0)

    def test_framelet_split(self):
        k, fl = W.WacCamera.split_y(np.array([0.0, 0.5, 13.999, 14.0, 27.5]))
        np.testing.assert_array_equal(k, [0, 0, 0, 1, 1])
        np.testing.assert_allclose(fl, [0.5, 1.0, 14.499, 0.5, 14.0])

    def test_band_layout_and_specials(self):
        raw = np.zeros((2, W.SET_LINES, W.SAMPLES), np.uint32)
        for k in range(2):
            for line in range(W.SET_LINES):
                raw[k, line] = np.float32(k * 100 + line).view(np.uint32)
        b = W.band_from_sets(raw)
        self.assertEqual(b.shape, (28, 704))
        np.testing.assert_array_equal(b.view(np.float32)[:, 0], [50 + j for j in range(14)] + [150 + j for j in range(14)])
        self.assertEqual(sorted(W.BAND_LINES.values()), [8, 22, 36, 50, 64])
        sp = {'missing_constant': 0xFF7FFFFB, 'high_instrument_saturation': 0xFF7FFFFE,
              'high_representation_saturation': 0xFF7FFFFF, 'low_instrument_saturation': 0xFF7FFFFD,
              'low_representation_saturation': 0xFF7FFFFC, 'valid_minimum': 0xFF7FFFFA}
        bits = np.array([0xFF7FFFFB, 0xFF7FFFFE, 0xFF7FFFFF, 0xFF7FFFFD, np.float32(0.02).view(np.uint32)], np.uint32)
        inv, high = W.classify_bits(bits, sp)
        np.testing.assert_array_equal(inv, [True, False, False, True, False])
        np.testing.assert_array_equal(high, [False, True, True, False, False])

    def test_osl_has_no_large_float_literals(self):
        """OSL floats are 32-bit: an ephemeris time literal (~1e8 s) would lose ~10 s (the bug found on the first render)."""
        c = self.cam()
        c.L = {'product_id': 'TEST'}
        fit = {'posCoef': [[1e4, 2e4, 4e4], [10, 20, 30], [0.1, 0.2, 0.3], [0, 0, 0]], 'rotCoef': [[0, 0, 0]] * 4,
               'Rmid': np.eye(3).tolist(), 'et0': 3.0e8, 'etMid': 3.0e8 + 6.0, 'half': 5.0, 'ifd': 0.5}
        src = W.osl_source(c, fit, 6006, 322, 449, 240)
        nums = [abs(float(x)) for x in re.findall(r'(?<![\w.])[-+]?\d+\.\d*(?:e[-+]?\d+)?', src)]
        self.assertLess(max(nums), 1e6)
        self.assertNotIn('300000000', src)


class Guard(unittest.TestCase):
    def test_dev_guard_refuses_held_out_ids_and_paths_are_separate(self):
        rows = read_catalogue()
        held = next(r['product_id'] for r in rows if r['split'] == 'heldout' and r['instrument'] == 'LROC_WAC')
        dev = next(r['product_id'] for r in rows if r['split'] == 'dev' and r['instrument'] == 'LROC_WAC')
        WC.guard([dev], rows)
        with self.assertRaises(HeldOutError):
            WC.guard([held], rows)
        self.assertEqual(WC.WAC_RESULTS.name, 'results_wac')
        self.assertNotEqual(WC.WAC_WORK.name, 'render_vs_real')


class StripScoring(unittest.TestCase):
    """A6.4: synthetic push-frame scene; neighbourhood operations never cross a framelet seam."""

    def scene(self, shift_rows):
        rng = np.random.default_rng(1)
        ground = np.zeros((400, 120))
        yy, xx = np.mgrid[0:400, 0:120]
        ground += 0.02 + 0.01 * rng.random(ground.shape)
        ground[(xx + 0.6 * yy) % 70 < 30] = 1e-5                     # diagonal shadow bands
        n = 20
        band = np.stack([ground[12 * k + shift_rows: 12 * k + shift_rows + 14] for k in range(n)]).reshape(n * 14, 120)
        return band

    def run_score(self, real, rend):
        from tools.validation.render_vs_real import wac_run as R
        H, Wd = real.shape
        G = {'product_id': 'TEST', 'site': 'site04_roi3', 'sunDistM': R.AU, 'sunEnu': [0.0, 1.0, 0.02], 'render_h': H,
             'orbit': 'grgm900c'}
        pos = np.stack(np.meshgrid(np.arange(Wd) * 60.0, -np.arange(H) * 60.0), -1)
        pos = np.concatenate([pos, np.zeros((H, Wd, 1))], -1).astype(np.float32)
        Rp = {'hit': np.ones((H, Wd), bool), 'lit': rend > 1e-3, 'pos': pos}
        E = R.TSI / 1.0
        beauty = rend * E / math.pi
        old = R.row_context, R.square_and_gsd
        try:
            R.row_context = lambda G: (np.eye(3), np.zeros(3), np.zeros((H, 3)))
            R.square_and_gsd = lambda G, Rp, M, P0, Psc: (np.ones((H, Wd), bool), np.full((H, Wd), 60.0))
            recs = R.score_row(G, [('pgda78_5m', 'hapke', Rp, beauty)], real, np.zeros_like(real, bool),
                               np.zeros_like(real, bool))
        finally:
            R.row_context, R.square_and_gsd = old
        return {r['registered']: r for r in recs}

    def test_identical_images_score_perfectly(self):
        b = self.scene(0)
        r = self.run_score(b, b)
        self.assertEqual(r[True]['status'], 'scored')
        self.assertAlmostEqual(r[False]['iouShadow'], 1.0)
        self.assertEqual(r[False]['edgeMedianM'], 0.0)
        self.assertEqual((r[True]['regDyPx'], r[True]['regDxPx']), (0.0, 0.0))

    def test_a_ground_shift_is_recovered_inside_framelets(self):
        real, rend = self.scene(2), self.scene(0)
        r = self.run_score(real, rend)
        self.assertAlmostEqual(r[True]['regDyPx'], -2.0, delta=0.26)
        self.assertAlmostEqual(r[True]['regDxPx'], 0.0, delta=0.26)
        self.assertGreater(r[True]['iouShadow'], r[False]['iouShadow'])
        self.assertGreater(r[True]['iouShadow'], 0.97)

    def test_pad_unpad_roundtrip(self):
        from tools.validation.render_vs_real.wac_run import GAP_ROWS, pad_strips, unpad
        a = np.arange(28 * 3, dtype=float).reshape(28, 3)
        p = pad_strips(a)
        self.assertEqual(p.shape[0], 2 * (14 + GAP_ROWS))
        np.testing.assert_array_equal(unpad(p), a)
        np.testing.assert_array_equal(p[GAP_ROWS // 2 - 1], a[0])      # edge fill, no step at the strip border


if __name__ == '__main__':
    unittest.main()
