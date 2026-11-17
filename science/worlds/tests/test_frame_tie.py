"""Frame tie (T3): Horizons' body-fixed model for Mercury and Mars is identified from geocentric quantity 14 (sub-observer
point) against light-time-corrected vectors, independently of any DEM. Uses cached Horizons responses and the NAIF PCKs
($POLARIS_DATA/v2/products/{mercury,mars}_horizons, mars_naif_pck); skipped when absent."""
import os
import unittest

import numpy as np

from science.worlds import frame_tie as FT
from science.worlds import pck as PCK

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
PK = os.path.join(ROOT, 'data', 'cache', 'v2', 'products', 'mars_naif_pck')
K10, K11, KM = (os.path.join(PK, f) for f in ('pck00010.tpc', 'pck00011.tpc', 'pck00010_msgr_v23.tpc'))
WIN = ('2026-11-14', '2027-11-14', '5 d')


def _have(*p):
    return all(os.path.exists(x) for x in p)


@unittest.skipUnless(_have(K10, K11, KM), 'NAIF PCKs not cached (python -m science.worlds.mars.fetch --products mars_naif_pck)')
class PckEvaluator(unittest.TestCase):
    def test_constants_read(self):
        k = PCK.read_pck(K11)
        self.assertEqual(k['BODY499_PM'][:2], [176.049863, 350.891982443297])
        self.assertEqual(k['BODY199_PM'][:2], [329.5988, 6.1385108])
        self.assertEqual(PCK.read_pck(KM)['BODY199_PM'][:2], [329.5988, 6.1385108])     # MESSENGER = IAU 2015 values
        self.assertEqual(PCK.read_pck(K10)['BODY199_PM'][:2], [329.5469, 6.1385025])

    def test_rotation_matrix_pole(self):
        a, d, w = PCK.rotation(K11, 499, 2461400.5)
        M = PCK.icrf_to_body(a, d, w)
        self.assertTrue(np.allclose(M @ M.T, np.eye(3), atol=1e-12))
        pole = np.array([np.cos(np.radians(d)) * np.cos(np.radians(a)), np.cos(np.radians(d)) * np.sin(np.radians(a)),
                         np.sin(np.radians(d))])
        self.assertTrue(np.allclose(M @ pole, [0, 0, 1], atol=1e-12))

    def test_mars_effective_w0_matches_iau2000(self):
        # the 2015 model's long-period terms make its effective W0 ~176.63 (= the IAU 2000 value used by MOLA)
        off = FT.longitude_offset_deg(499, K10, K11, 2451545.0)
        self.assertLess(abs(off), 0.005, off)
        self.assertLess(FT.pole_difference_deg(499, K10, K11, 2451545.0), 0.001)


class HorizonsModel(unittest.TestCase):
    def _tie(self, naif, world, radii):
        cd = os.path.join(ROOT, 'data', 'cache', 'v2', 'products', f'{world}_horizons')
        if not _have(K10, K11):
            self.skipTest('PCKs not cached')
        try:
            return FT.tie(naif, True, {'iau2009': K10, 'iau2015': K11}, *WIN, cd, allow_network=False, radii_km=radii)
        except LookupError:
            self.skipTest('Horizons responses not cached')

    def test_mercury_horizons_is_iau2015(self):
        r = self._tie(199, 'mercury', (2440.53, 2440.53, 2438.26))
        self.assertEqual(r['horizons_model'], 'iau2015')
        self.assertLess(r['models']['iau2015']['max_abs_dlon_deg'], 1e-4)
        self.assertLess(r['models']['iau2015']['max_abs_dlat_deg'], 1e-4)
        self.assertGreater(r['models']['iau2009']['median_dlon_deg'], 0.1)       # 0.135 deg: the R6 worry, resolved

    def test_mars_horizons_is_iau2015(self):
        r = self._tie(499, 'mars', (3396.19, 3396.19, 3376.2))
        self.assertEqual(r['horizons_model'], 'iau2015')
        self.assertLess(r['models']['iau2015']['max_abs_dlon_deg'], 2e-4)
        self.assertGreater(r['models']['iau2009']['max_abs_dlon_deg'], 5 * r['models']['iau2015']['max_abs_dlon_deg'])

    def test_mla_to_horizons_offset_zero(self):
        if not _have(KM, K11):
            self.skipTest('PCKs not cached')
        for jd in (2455650.5, 2461400.5):          # MESSENGER orbit phase, and this window
            self.assertLess(abs(FT.longitude_offset_deg(199, KM, K11, jd)), 1e-9)


if __name__ == '__main__':
    unittest.main()
