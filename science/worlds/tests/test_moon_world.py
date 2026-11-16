"""Moon regression through the world API: Site04 RoI 3 must be unchanged (94.36 % / 72.11 % / 19 h; 20 PGDA 78 clones
87.54-97.33 %). Also: the Moon world's Horizons query is the existing one byte for byte, and the world registry."""
import json
import unittest
from pathlib import Path

from science import frames
from science import horizons as H
from science.anysite import products as P
from science.worlds import WORLDS, get_world

ROOT = Path(__file__).resolve().parents[3]
ROI3 = (-89.78012, -156.32023)
BUNDLE_ROI3 = ROOT / 'data' / 'bundles' / 'site04_roi3_2026-11-14_14d_mast1m.json'


class MoonWorldDefinition(unittest.TestCase):
    def test_registry(self):
        self.assertEqual(WORLDS, ('moon', 'mercury', 'mars'))
        self.assertTrue(get_world('moon').available and get_world('mercury').available)
        mars = get_world('mars')
        self.assertFalse(mars.available)
        self.assertIn('not started', mars.availability_note)

    def test_moon_world_wraps_existing_constants(self):
        m = get_world('moon')
        self.assertEqual(m.radius_m, frames.R_MOON_M)
        self.assertEqual(m.horizons_radii_km, (1737.4, 1737.4, 1737.4))
        self.assertEqual(m.atmosphere, 'none')
        self.assertEqual(m.geodetic_latitude_deg(-89.78, 1500.0), -89.78)

    def test_moon_horizons_query_identical_to_committed_archive(self):
        """The world-built query equals the parameters of the committed raw Site04 RoI 3 Sun response."""
        b = json.loads(BUNDLE_ROI3.read_text())
        p = get_world('moon').horizons_params('10', ROI3[0], ROI3[1], b['site']['height_m'], '2026-11-14 00:00',
                                              '2026-11-28 00:00', '1 h')
        self.assertEqual(p, H.build_params('10', ROI3[0], ROI3[1], b['site']['height_m'], '2026-11-14 00:00',
                                           '2026-11-28 00:00', '1 h'))
        man = json.loads((H.RAW_DIR / 'MANIFEST.json').read_text())
        hit = [m for m in man if m['path'].endswith('site04_roi3_sun_20261114_m1.txt')]
        self.assertTrue(hit)
        self.assertEqual(hit[0]['params'], {k: v for k, v in p.items() if k != 'TLIST'})


@unittest.skipUnless(P.pgda90_file() is not None and P.pgda78_tile('Site04') is not None
                     and P.pgda78_tile('Site04', 20) is not None, 'Site04 tile, its 20 clones or PGDA 90 not cached')
class MoonRegressionThroughWorldAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        moon = get_world('moon')
        from science.worlds import moon as moon_mod
        cls.world = moon
        cls.b = moon_mod.solve(*ROI3, mast_m=1.0, member_kinds=('clones',), n_members=20, use_cache=False,
                               allow_network=False, out_dir=ROOT / 'data' / 'cache' / 'anysite' / 'test_bundles_worlds')

    def test_nominal(self):
        m = self.b['metrics']
        self.assertEqual(round(m['sun_center_visible_pct_hourly_samples'], 2), 94.36)
        self.assertEqual(round(m['sun_and_earth_center_visible_pct_hourly_samples'], 2), 72.11)
        self.assertEqual(m['longest_sun_center_hidden_h'], 19.0)

    def test_clones(self):
        s = self.b['anysite']['uncertainty']['summary']['pgda78-clone']['sun_center_visible_pct_hourly_samples']
        self.assertEqual(s['n'], 20)
        self.assertEqual(round(s['min'], 2), 87.54)
        self.assertEqual(round(s['max'], 2), 97.33)

    def test_skyline_equals_committed_bundle(self):
        ref = json.loads(BUNDLE_ROI3.read_text())['skyline']
        d = [abs(a - b) for a, b in zip(self.b['skyline']['elevation_deg'], ref['elevation_deg'])]
        self.assertLessEqual(max(d), 1e-5)
