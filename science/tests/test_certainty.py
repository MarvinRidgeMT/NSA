"""A2 Certainty Height tests (real ROI bundles)."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLES = sorted((ROOT / 'data/bundles').glob('site0*_roi*_mast*.json'))


def _blocks():
    out = []
    for p in BUNDLES:
        b = json.loads(p.read_text())
        if 'certainty' in b.get('derived', {}):
            out.append((p, b))
    return out


class CertaintyHeight(unittest.TestCase):
    def setUp(self):
        self.blocks = _blocks()
        if not self.blocks:
            self.skipTest('certainty not yet written')

    def test_monotonic_in_mast_on_each_dem(self):
        # raising the mast never lowers geometric Sun visibility on a fixed DEM
        for p, b in self.blocks:
            c = b['derived']['certainty']
            rows = [r for r in c['certainty_curve'] if r['metric'] == 'sun_center_pct']
            rows.sort(key=lambda r: r['mast_m'])
            with self.subTest(p.name):
                for a, z in zip(rows, rows[1:]):
                    self.assertGreaterEqual(z['nominal'] + 1e-9, a['nominal'])
                    for x, y in zip(a['by_clone'], z['by_clone']):
                        self.assertGreaterEqual(y + 1e-9, x)

    def test_matches_bundle_and_margin_series_at_bundle_mast(self):
        for p, b in self.blocks:
            c = b['derived']['certainty']; mast = b['site']['observer_mast_m']
            if mast not in c['masts_m']:
                continue
            with self.subTest(p.name):
                r = next(r for r in c['certainty_curve'] if r['mast_m'] == mast and r['metric'] == 'sun_center_pct')
                self.assertAlmostEqual(r['nominal'], b['metrics']['sun_center_visible_pct_hourly_samples'], places=2)
                ms = b['derived'].get('margin_series')
                if ms:
                    self.assertEqual(r['by_clone'], ms['sun_center_visible_pct_hourly_by_clone'])

    def test_certainty_height_definition(self):
        for p, b in self.blocks:
            c = b['derived']['certainty']; h = c['certainty_height_m']
            rows = {r['mast_m']: r for r in c['certainty_curve'] if r['metric'] == 'sun_center_pct'}
            with self.subTest(p.name):
                if h is None:
                    self.assertTrue(all(r['min'] < 100 or r['nominal'] < 100 for r in rows.values()))
                    continue
                self.assertEqual(rows[h]['min'], 100.0)
                self.assertEqual(rows[h]['nominal'], 100.0)
                for m, r in rows.items():
                    if m < h:
                        self.assertTrue(r['min'] < 100 or r['nominal'] < 100)


if __name__ == '__main__':
    unittest.main()
