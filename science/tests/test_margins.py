"""A4 margin series tests (real ROI bundles)."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLES = sorted((ROOT / 'data/bundles').glob('site0*_roi*_mast*.json'))


class MarginSeries(unittest.TestCase):
    def test_sign_matches_visibility_flags(self):
        for p in BUNDLES:
            b = json.loads(p.read_text())
            ms = b.get('derived', {}).get('margin_series')
            if ms is None:
                self.skipTest('margin_series not yet written')
            with self.subTest(p.name):
                self.assertEqual(ms['label'], 'SOURCE-BASED UNVALIDATED')
                self.assertEqual(ms['t_unix'], [s['t_unix'] for s in b['samples']])
                for body in ('sun', 'earth'):
                    nom, lo, hi = ms[f'{body}_margin_deg'], ms[f'{body}_margin_clone_min_deg'], ms[f'{body}_margin_clone_max_deg']
                    nv = ms[f'{body}_n_clones_visible']; N = ms['n_clones']
                    for i, s in enumerate(b['samples']):
                        if nom[i] is not None and abs(nom[i]) > 1e-9:
                            self.assertEqual(nom[i] > 0, s[body]['center_visible'])
                        self.assertLessEqual(lo[i], hi[i])
                        if lo[i] > 0:
                            self.assertEqual(nv[i], N)
                        if hi[i] < 0:
                            self.assertEqual(nv[i], 0)

    def test_hourly_pct_consistent_with_counts(self):
        for p in BUNDLES:
            ms = json.loads(p.read_text()).get('derived', {}).get('margin_series')
            if ms is None:
                self.skipTest('margin_series not yet written')
            with self.subTest(p.name):
                n = len(ms['t_unix'])
                tot = sum(ms['sun_n_clones_visible'])
                self.assertAlmostEqual(tot / (n * ms['n_clones']) * 100,
                                       sum(ms['sun_center_visible_pct_hourly_by_clone']) / ms['n_clones'], places=2)

    def test_one_clone_reproduces(self):
        from science import sites
        from science.margins import clone_margins
        p = ROOT / 'data/bundles/site04_roi3_2026-11-14_14d_mast1m.json'
        if not (sites.CACHE / 'p78' / 'Site04_final_adj_5mpp_0001_err.tif').exists():
            self.skipTest('clone tile not cached')
        b = json.loads(p.read_text())
        ms = b['derived']['margin_series']
        r = clone_margins(b, 1, sites.far_dem('site04_roi3'))
        self.assertEqual(r['ground_m'], ms['clones'][0]['ground_m'])
        vis = 100 * sum(bool(v) for v in r['sun']['visible']) / len(r['sun']['visible'])
        self.assertAlmostEqual(vis, ms['sun_center_visible_pct_hourly_by_clone'][0], places=2)


if __name__ == '__main__':
    unittest.main()
