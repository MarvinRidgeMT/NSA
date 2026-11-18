"""Kaguya TC camera model, label parsing, pixel decoding, kernel choice and the dev guard (A11 pieces).

The labels here are synthetic (the keys and layout of a Level 2B0 label, made-up values); no JAXA file is in git."""
import re
import unittest

import numpy as np

from tools.validation.render_vs_real import tc_camera as C
from tools.validation.render_vs_real import tc_io as IO
from tools.validation.render_vs_real import tc_kernels as K


def _vals(txt, key):
    m = re.search(rf'{re.escape(key)}\s*=\s*\(([^)]*)\)', txt, re.S)
    return [float(x) for x in re.findall(r'[-+]?\d[\d.]*(?:[Ee][-+]?\d+)?', m.group(1))]


def synthetic_label(swath='NOMINAL', first=297, samples=3208, lines=40, inst='TC1'):
    return f'''PDS_VERSION_ID                       = "PDS3"
/*** FILE FORMAT ***/
FILE_NAME                            = "TC1S2B0_01_00000S000E0000.img"
^IMAGE                               = ("TC1S2B0_01_00000S000E0000.img", 1 <BYTES>)
PRODUCT_SET_ID                       = "TC_s_Level2B0"
INSTRUMENT_ID                        = "{inst}"
START_TIME                           = 2008-11-06T07:23:24.464295
STOP_TIME                            = 2008-11-06T07:23:54.719795
SPICE_METAKERNEL_FILE_NAME           = "RGC_INF_TCv401IK_MIv200IK_SPv105IK_RISE100i_05_LongCK_D_V02_de421_110706.mk"
SENSOR_DESCRIPTION                   = "Imagery type:Pushbroom. OBJECTS in a comment must not split the label."
EXPOSURE_MODE_ID                     = "LONG"
CORRECTED_SC_CLOCK_START_COUNT       =  909991394.119896 <s>
CORRECTED_START_TIME                 = 2008-11-06T07:23:24.460691
CORRECTED_STOP_TIME                  = 2008-11-06T07:23:54.718032
CORRECTED_SAMPLING_INTERVAL          = (6.499966 <ms>)
UPPER_LEFT_LATITUDE                  = -88.471668 <deg>
UPPER_LEFT_LONGITUDE                 = 251.813762 <deg>
UPPER_RIGHT_LATITUDE                 = -88.503569 <deg>
UPPER_RIGHT_LONGITUDE                = 215.469645 <deg>
LOWER_LEFT_LATITUDE                  = -89.462945 <deg>
LOWER_LEFT_LONGITUDE                 = 334.619607 <deg>
LOWER_RIGHT_LATITUDE                 = -89.559117 <deg>
LOWER_RIGHT_LONGITUDE                = 126.099420 <deg>
SCENE_CENTER_LATITUDE                = -89.340487 <deg>
SCENE_CENTER_LONGITUDE               = 236.139058 <deg>
SATELLITE_MOVING_DIRECTION           = -1
FIRST_SAMPLED_LINE_POSITION          = "UPPERMOST"
FIRST_DETECTOR_ELEM_POSITION         = "LEFT"
SWATH_MODE_ID                        = "{swath}"
FIRST_PIXEL_NUMBER                   = {first}
LAST_PIXEL_NUMBER                    = {first + samples - 1}
/*** DESCRIPTION OF OBJECTS CONTAINED IN THE FILE ***/
OBJECT                               = IMAGE
    COMPRESSION_TYPE                 = "N/A"
    LINES                            = {lines}
    LINE_SAMPLES                     = {samples}
    SAMPLE_TYPE                      = MSB_INTEGER
    SAMPLE_BITS                      = 16
    SCALING_FACTOR                   = 1.30000e-02
    OFFSET                           = 0.00000e+00
    INVALID_TYPE                     = ("SATURATION" , "MINUS" , "DUMMY_DEFECT" , "OTHER")
    INVALID_VALUE                    = (-20000 , -21000 , -22000 , -23000)
END_OBJECT                           = IMAGE
OBJECT                               = PROCESSING_PARAMETERS
    LINES                            = 99
END_OBJECT                           = PROCESSING_PARAMETERS
END
'''


class Constants(unittest.TestCase):
    @unittest.skipUnless((K.KDIR / 'SEL_TC_V01.TI').exists() and (K.KDIR / 'kaguyaTcAddendum007.ti').exists(),
                         'SELENE IK / IAK not cached')
    def test_ik_and_iak_values(self):
        ik = (K.KDIR / 'SEL_TC_V01.TI').read_text()
        iak = (K.KDIR / 'kaguyaTcAddendum007.ti').read_text()
        for name, d in C.IK.items():
            code = d['code']
            self.assertAlmostEqual(_vals(ik, f'INS{code}_FOCAL_LENGTH')[0], d['focal_mm'])
            self.assertEqual(tuple(_vals(ik, f'INS{code}_DISTORTION_COEF_X')), d['cx'])
            self.assertEqual(tuple(_vals(ik, f'INS{code}_DISTORTION_COEF_Y')), d['cy'])
            self.assertEqual(tuple(_vals(ik, f'INS{code}_BORESIGHT ')[:2]), d['boresight_xy'])
            self.assertEqual(float(re.search(rf'INS{code}_BORESIGHT_SAMPLE\s*=\s*(\S+)', iak).group(1)), C.BORESIGHT_SAMPLE)
            self.assertEqual(float(re.search(rf'INS{code}_BORESIGHT_LINE\s*=\s*(\S+)', iak).group(1)), C.BORESIGHT_LINE)
            self.assertEqual(float(re.search(rf'INS{code}_PIXEL_PITCH\s*=\s*(\S+)', iak).group(1)), C.PIXEL_MM)
            self.assertEqual(_vals(iak, f'INS{code}_TRANSX'), [0.0, 0.0, -C.PIXEL_MM])
            self.assertEqual(_vals(iak, f'INS{code}_TRANSY'), [0.0, -C.PIXEL_MM, 0.0])
        fk = (K.KDIR / 'SEL_V01.TF').read_text()
        self.assertIn("FRAME_LISM_TC1_HEAD       =  -131350", fk)
        self.assertIn("FRAME_LISM_TC2_HEAD       =  -131370", fk)


class Label(unittest.TestCase):
    def test_parse(self):
        L = C.parse_label(synthetic_label())
        self.assertEqual(L['product_id'], 'TC1S2B0_01_00000S000E0000')
        self.assertEqual((L['lines'], L['samples'], L['first_pixel']), (40, 3208, 297))
        self.assertEqual(L['image_byte_offset'], 0)
        self.assertEqual(L['invalid_codes'], {'SATURATION': -20000, 'MINUS': -21000, 'DUMMY_DEFECT': -22000, 'OTHER': -23000})
        self.assertAlmostEqual(L['line_rate_ms'], 6.499966)
        self.assertAlmostEqual(L['sclk_start'], 909991394.119896)
        self.assertEqual(L['moving_direction'], -1)
        self.assertEqual(K.rise_solution(L['spice_metakernel']), 'RISE100i_05')

    def test_dct_padding(self):
        """DCT products pad lines to a multiple of 8 samples after the last detector pixel (seen on a dev stereo label:
        3496 samples for detector 297..3788)."""
        lab = synthetic_label().replace('LINE_SAMPLES                     = 3208', 'LINE_SAMPLES                     = 3212')
        L = C.parse_label(lab)
        self.assertEqual((L['samples'], L['valid_samples'], L['pad_samples']), (3212, 3208, 4))
        with self.assertRaises(ValueError):
            C.parse_label(synthetic_label().replace('LINE_SAMPLES                     = 3208', 'LINE_SAMPLES                     = 3216'))

    def test_swath_first_pixel_must_match_isis(self):
        with self.assertRaises(ValueError):
            C.parse_label(synthetic_label(swath='FULL', first=297))
        C.parse_label(synthetic_label(swath='FULL', first=1, samples=4096))


class Look(unittest.TestCase):
    ik = C.IK['TC1']

    def test_centre_is_near_the_ik_boresight(self):
        v = C.look_cam(self.ik, 297, 3208, 2048 - 297 + 1)       # detector sample 2048 = the IAK boresight sample
        b = np.array([*self.ik['boresight_xy'], self.ik['focal_mm']])
        ang = np.arccos(np.clip(v @ (b / np.linalg.norm(b)), -1, 1))
        self.assertLess(float(ang), 3 * C.IFOV_RAD)

    def test_ifov(self):
        v = C.look_cam(self.ik, 297, 3208, np.array([1700.0, 1701.0]))
        self.assertAlmostEqual(float(np.arccos(v[0] @ v[1])) / (C.PIXEL_MM / self.ik['focal_mm']), 1.0, delta=0.01)

    def test_flip_reverses_the_sample_axis(self):
        s = np.array([1.0, 500.5, 3208.0])
        a = C.look_cam(self.ik, 297, 3208, s, flip=True)
        b = C.look_cam(self.ik, 297, 3208, 3208 + 1 - s)
        np.testing.assert_allclose(a, b, atol=1e-15)

    def test_samples_run_along_minus_y(self):
        v = C.look_cam(self.ik, 297, 3208, np.array([1.0, 3208.0]))
        self.assertGreater(v[0, 1], v[1, 1])                       # y = -0.007 (det - 2048): first sample has +y


class Pixels(unittest.TestCase):
    def test_decode_codes_and_scale(self):
        L = C.parse_label(synthetic_label(lines=2, samples=3208))
        dn = np.zeros((2, 3208), dtype='>i2')
        dn[0, :4] = [100, -20000, -21000, -23000]
        v, inv, sat, _h = IO.decode(L, dn.tobytes())
        self.assertAlmostEqual(v[0, 0], 1.3)
        self.assertTrue(sat[0, 1] and not inv[0, 1] and np.isnan(v[0, 1]))
        self.assertTrue(inv[0, 2] and inv[0, 3] and not sat[0, 2])
        self.assertEqual(int(inv.sum() + sat.sum()), 3)

    def test_short_file_refused(self):
        L = C.parse_label(synthetic_label(lines=2))
        with self.assertRaises(RuntimeError):
            IO.decode(L, b'\x00' * 100)


class Incoming(unittest.TestCase):
    """Files the project owner downloads into incoming/ are checked, copied into the cache and recorded."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmp = Path(tempfile.mkdtemp())
        self.saved = (IO.TC_DIR, IO.INCOMING)
        IO.TC_DIR, IO.INCOMING = self.tmp, self.tmp / 'incoming'
        (self.tmp / 'incoming' / 'sub').mkdir(parents=True)
        from tools.validation.render_vs_real.tc_common import tc_rows
        self.pid = next(r['product_id'] for r in tc_rows() if r['split'] == 'dev')

    def tearDown(self):
        import shutil
        IO.TC_DIR, IO.INCOMING = self.saved
        shutil.rmtree(self.tmp)

    def test_missing_file_says_where_to_put_it(self):
        with self.assertRaises(FileNotFoundError) as cm:
            IO.label(self.pid, 'https://example.invalid/x.lbl')
        self.assertIn('incoming', str(cm.exception))

    def test_label_checked_copied_and_recorded(self):
        (self.tmp / 'incoming' / 'sub' / f'{self.pid}.lbl').write_text(f'PDS_VERSION_ID = "PDS3"\nFILE_NAME = "{self.pid}.img"\n')
        self.assertIn(self.pid, IO.label(self.pid, 'u'))
        self.assertTrue((self.tmp / 'labels' / f'{self.pid}.lbl').exists())
        import json
        rec = json.loads((self.tmp / 'MANIFEST.jsonl').read_text().splitlines()[-1])
        self.assertEqual((rec['kind'], rec['product_id'], rec['url']), ('label', self.pid, 'u'))
        self.assertEqual(len(rec['sha256']), 64)

    def test_wrong_label_and_non_gzip_image_refused(self):
        (self.tmp / 'incoming' / f'{self.pid}.lbl').write_text('<html>Request Rejected</html>')
        (self.tmp / 'incoming' / f'{self.pid}.img.gz').write_bytes(b'not gzip')
        with self.assertRaises(RuntimeError):
            IO.label(self.pid, 'u')
        with self.assertRaises(RuntimeError):
            IO.image_gz(self.pid, 'u')


class Kernels(unittest.TestCase):
    def test_orbit_choice(self):
        self.assertEqual(K.spk_key({'spice_metakernel': 'X_RISE100h_02_Y.mk'}, 'label')[0], K.RISE_SPK['RISE100h_02'])
        self.assertIsNone(K.spk_key({'spice_metakernel': 'X_RISE200z_09_Y.mk'}, 'label')[0])
        self.assertEqual(K.spk_key({}, 'grgm900c')[0], K.GRGM900C_SPK)
        path, rec = K.kernels_for({'spice_metakernel': 'nothing'}, 'label', fetch_missing=False)
        self.assertIsNone(path)
        self.assertIn('error', rec)


class Guard(unittest.TestCase):
    def test_heldout_tc_id_refused_in_dev(self):
        from tools.validation.render_vs_real.common import HeldOutError
        from tools.validation.render_vs_real.tc_common import guard, tc_rows
        held = next(r['product_id'] for r in tc_rows() if r['split'] == 'heldout')
        with self.assertRaises(HeldOutError):
            guard([held])


class PipelineDecision(unittest.TestCase):
    def test_rule(self):
        from tools.validation.render_vs_real.tc_pipeline_test import decide
        self.assertEqual(decide({False: (200, 4), True: (1900, 4)}), (False, True))     # the expected no-flip case
        self.assertEqual(decide({'isis': (200, 8), 'label': (250, 8)}), (None, False))  # too close: unresolved
        self.assertEqual(decide({False: (700, 4), True: (1900, 4)}), (None, False))     # best above 600 m
        self.assertEqual(decide({False: (200, 4), True: (float('nan'), 0)}), (None, False))


if __name__ == '__main__':
    unittest.main()
