"""E4 regression: Site04 RoI 4 all_hours_covered_frac = 0.0 is genuine (every reached azimuth is controlled outside the 5 m tile).

The generator (science.coverage.for_bundle) reproduces the committed value from the bundle's own attribution, and a
synthetic check confirms the denominator is all hours (not critical hours) and the numerator counts near_5m bins."""
import json
import unittest
from pathlib import Path

from science.coverage import _bin_of, coverage, for_bundle

ROOT = Path(__file__).resolve().parents[2]


class Roi4Coverage(unittest.TestCase):
    def test_reproduces_committed_value_and_cause(self):
        for mast in (1, 10):
            b = json.loads((ROOT / f'data/bundles/site04_roi4_2026-11-14_14d_mast{mast}m.json').read_text())
            c = for_bundle(b)
            self.assertEqual(c['all_hours_covered_frac'], b['derived']['coverage']['all_hours_covered_frac'])
            self.assertEqual(c['earth']['all_hours_covered_frac'], b['derived']['coverage']['earth']['all_hours_covered_frac'])
            self.assertEqual(c['all_hours_covered_frac'], 0.0)
            self.assertEqual(c['earth']['all_hours_covered_frac'], 0.0)
            src = b['derived']['attribution']['per_bin']['source']
            self.assertGreater(src.count('near_5m'), 0)  # the tile does control some bins ...
            for k in ('sun', 'earth'):  # ... but none the Sun or Earth reach in this window
                self.assertTrue(all(src[_bin_of(s[k]['az_deg'], len(src))] != 'near_5m' for s in b['samples']))

    def test_roi3_is_nonzero_with_same_generator(self):
        b = json.loads((ROOT / 'data/bundles/site04_roi3_2026-11-14_14d_mast1m.json').read_text())
        c = for_bundle(b)
        self.assertEqual((c['all_hours_covered_frac'], c['earth']['all_hours_covered_frac']), (0.3442, 0.6113))

    def test_denominator_is_all_hours(self):
        att = {'per_bin': {'source': ['near_5m', 'far_80m', 'far_80m', 'far_80m'], 'ridge_idx': [None] * 4}, 'ridges': []}
        mk = lambda az, m: {'sun': {'az_deg': az, 'margin_deg': m, 'horizon_flag': 'complete'}}
        samples = [mk(0, 5.0), mk(90, 5.0), mk(180, 0.1), mk(270, 5.0)]  # 1 of 4 hours near; the only critical hour is far
        c = coverage(att, samples, 1.0, 1.0, 'sun')
        self.assertEqual(c['all_hours_covered_frac'], 0.25)
        self.assertEqual(c['covered_frac'], 0.0)
        self.assertEqual(c['n_hours'], 4)


if __name__ == '__main__':
    unittest.main()
