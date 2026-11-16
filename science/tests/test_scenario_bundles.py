"""5th-axis scenario bundles (science/scenario_bundles.py) and their viewer export.

Skips the checks on built files when data/bundles/scenarios/ has not been generated on this machine."""
import hashlib
import json
import math
import unittest
from pathlib import Path

from science import frames, scenario_bundles as S, sites

ROOT = Path(__file__).resolve().parents[2]
SC = ROOT / 'data' / 'bundles' / 'scenarios'
VIEW = ROOT / 'data' / 'viewer' / 'polaris-x5d-roi-2026-11-14-v2.json'
ROIS = ('site01_roi6', 'site04_roi3', 'site04_roi4')


def built():
    return sorted(SC.glob('*__*.json')) if SC.exists() else []


class ScenarioSpecs(unittest.TestCase):
    def test_three_distinct_clones_and_four_offsets_per_roi(self):
        for sid in ROIS:
            _, b = S.base_bundle(sid, 1)
            sp = S.specs(sid, b)
            clones = [x['clone'] for x in sp if x['family'] == 'dem-clone']
            self.assertEqual(len(set(clones)), 3, sid)
            self.assertEqual(sorted(x['offset'] for x in sp if x['family'] == 'position-offset'),
                             sorted(S.OFFSETS))

    def test_clone_ranking_follows_margin_series(self):
        _, b = S.base_bundle('site04_roi3', 1)
        ms = b['derived']['margin_series']
        both = dict(zip(ms['clone_ids'], ms['sun_and_earth_center_visible_pct_hourly_by_clone']))
        (_, lo, _), (_, _, _), (_, hi, _) = S.pick_clones(b)
        self.assertEqual(both[lo], min(both.values()))
        self.assertEqual(both[hi], max(both.values()))

    def test_ties_are_labelled_not_ranked(self):
        _, b = S.base_bundle('site04_roi4', 1)  # every clone gives the same hourly Sun / Sun+Earth here
        self.assertTrue(all(rank == 'all-tied' for rank, _, _ in S.pick_clones(b)))


@unittest.skipUnless(built(), 'scenario bundles not generated (run python -m science.scenario_bundles)')
class BuiltScenarioBundles(unittest.TestCase):
    def test_each_bundle_is_a_full_recomputation_on_the_baseline_times(self):
        man = {m['path']: m for m in json.loads((ROOT / 'data/raw/horizons/MANIFEST.json').read_text())}
        for p in built():
            b = json.loads(p.read_text())
            base_id, tag = b['bundle_id'].split('__')
            base = json.loads((ROOT / 'data' / 'bundles' / f'{base_id}.json').read_text())
            self.assertEqual([x['utc'] for x in b['samples']], [x['utc'] for x in base['samples']], p.name)
            self.assertEqual(b['validation_status']['overall'], 'SOURCE-BASED UNVALIDATED')
            self.assertEqual(b['scenario']['tag'], tag)
            for body in ('sun', 'earth'):  # every hourly visibility change has a bisection-refined centre crossing
                vis = [x[body]['center_visible'] for x in b['samples']]
                flips = sum(a != c for a, c in zip(vis, vis[1:]))
                n_ev = sum(1 for e in b['events'] if e['body'] == body and e['kind'] == 'center')
                self.assertGreaterEqual(n_ev, flips, f'{p.name} {body}')
            for r in b['provenance']['horizons_raw']:  # every JPL response archived with its hash, and unique to this scenario
                self.assertIn(tag, r['path'], r['path'])
                f = ROOT / r['path']
                self.assertTrue(f.exists(), r['path'])
                self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(), r['sha256'])
                self.assertEqual(man[r['path']]['sha256'], r['sha256'])

    def test_position_offsets_move_100_m_in_local_enu(self):
        for p in built():
            b = json.loads(p.read_text()); sc = b['scenario']
            if sc['family'] != 'position-offset':
                continue
            s = sites.SITES[b['site']['id']]
            de, dn = sc['parameters']['east_m'], sc['parameters']['north_m']
            dx, dy = sc['observer_offset_grid_m']
            self.assertAlmostEqual(math.hypot(dx, dy), 100.0, delta=0.5)
            e, n = frames.grid_to_enu(dx, dy, s['lon'])
            self.assertAlmostEqual(float(e), de, delta=0.5); self.assertAlmostEqual(float(n), dn, delta=0.5)
            self.assertNotEqual(b['samples'][0]['sun']['az_deg'], None)

    def test_clone_bundles_match_the_independent_margin_series(self):
        """Clone k's hourly Sun % here must agree with science/margins.py, which reused the nominal ephemeris."""
        for p in built():
            b = json.loads(p.read_text()); sc = b['scenario']
            if sc['family'] != 'dem-clone':
                continue
            ref = sc['parameters']['margin_series_hourly']
            self.assertAlmostEqual(b['metrics']['sun_center_visible_pct_hourly_samples'], ref['sun_pct_hourly'], delta=0.31)
            self.assertAlmostEqual(b['metrics']['sun_and_earth_center_visible_pct_hourly_samples'],
                                   ref['sun_and_earth_pct_hourly'], delta=0.31)


@unittest.skipUnless(built() and VIEW.exists(), 'viewer export not built')
class ViewerExport(unittest.TestCase):
    def test_every_scenario_bundle_is_in_the_viewer_with_its_hash(self):
        v = json.loads(VIEW.read_text())
        rec = {s['sourceBundle']['file']: s for d in v['datasets'] for s in d['derived']['scenarios'] if s.get('sourceBundle')}
        for p in built():
            k = p.relative_to(ROOT).as_posix()
            self.assertIn(k, rec)
            self.assertEqual(rec[k]['sourceBundle']['sha256'], hashlib.sha256(p.read_bytes()).hexdigest())
            b = json.loads(p.read_text())
            self.assertEqual(rec[k]['samples']['sun']['visible'], [x['sun']['center_visible'] for x in b['samples']])
            got = {m['id']: m['value'] for m in rec[k]['metrics']}
            self.assertEqual(got['sun_fraction'], b['metrics']['sun_center_visible_pct'])
            if b['scenario']['family'] == 'position-offset':
                self.assertEqual([s['sun']['az'] for s in rec[k]['ephemeris']['samples']],
                                 [x['sun']['az_deg'] for x in b['samples']])


if __name__ == '__main__':
    unittest.main()
