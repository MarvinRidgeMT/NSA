"""ROI bundles: real PGDA 78 ROI coordinates, converged ray step, provenance integrity,
frame-tie bound, and the cross-check against the standalone polaris_batch results
(claude/BATCH_RUNS_2026-11-14.md, 14-28 Nov 2026 at 1 h)."""
import hashlib
import json
import unittest
from pathlib import Path

from science import frame_tie, sites

ROOT = Path(__file__).resolve().parents[2]
BUNDLES = ROOT / 'data' / 'bundles'
RAW = ROOT / 'data' / 'raw' / 'horizons'

# PGDA product 78 ROI centroids (claude/DATA_AND_RULES_2026-11-14.md)
ROI_TABLE = {'site01_roi6': (-89.47409, -137.38130), 'site04_roi3': (-89.78012, -156.32023),
             'site04_roi4': (-89.78480, -155.94606)}


def load(sid, mast):
    return json.loads((BUNDLES / f'{sid}_2026-11-14_14d_mast{mast}m.json').read_text())


class RoiSites(unittest.TestCase):
    def test_coordinates_match_published_rois(self):
        for sid, (lat, lon) in ROI_TABLE.items():
            s = sites.SITES[sid]
            self.assertEqual((s['lat'], s['lon']), (lat, lon))
            self.assertEqual(s['p78'], sites.SITES[s['tile']]['p78'])  # same product-78 tile

    def test_bundles_use_roi_point_and_converged_step(self):
        for sid in ROI_TABLE:
            for mast in (1, 10):
                b = load(sid, mast)
                with self.subTest(f'{sid} {mast} m'):
                    self.assertEqual(b['bundle_id'], f'{sid}_2026-11-14_14d_mast{mast}m')
                    self.assertEqual((b['site']['lat_deg'], b['site']['lon_deg_east']), ROI_TABLE[sid])
                    self.assertEqual(b['site']['observer_mast_m'], mast)
                    self.assertEqual(b['skyline']['step_near_m'], sites.NEAR_RAY_STEP_M)
                    self.assertLess(b['site']['slope_deg_5m_50m_baseline'], 15.0)
                    chk = {c['id']: c for c in b['validation_status']['checks']}
                    self.assertEqual(chk['site-coordinate-source']['status'], 'pass')
                    self.assertEqual(chk['me-frame-tie-de421-vs-horizons']['status'], 'pass')


class Provenance(unittest.TestCase):
    def test_every_referenced_raw_file_exists_with_its_sha256(self):
        """Catches raw-file overwrites (e.g. two mast runs sharing a Horizons tag)."""
        for p in sorted(BUNDLES.glob('site0*_roi*_mast*.json')):
            b = json.loads(p.read_text())
            for r in b['provenance']['horizons_raw']:
                with self.subTest(f'{p.name} {r["path"]}'):
                    f = ROOT / r['path']
                    self.assertTrue(f.exists())
                    self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(), r['sha256'])

    def test_raw_tags_unique_per_mast(self):
        a = {r['path'] for r in load('site04_roi3', 1)['provenance']['horizons_raw'] if r['role'] == 'bisection'}
        b = {r['path'] for r in load('site04_roi3', 10)['provenance']['horizons_raw'] if r['role'] == 'bisection'}
        self.assertFalse(a & b)


class BatchCrossCheck(unittest.TestCase):
    """polaris_batch counts hourly samples; compare with the *_hourly_samples metrics."""
    def test_site01_roi6(self):
        for mast in (1, 10):
            m = load('site01_roi6', mast)['metrics']
            self.assertEqual(m['sun_center_visible_pct'], 100.0)
            self.assertAlmostEqual(m['sun_and_earth_center_visible_pct_hourly_samples'], 81.6, delta=0.05)

    def test_site04_roi3_10m(self):
        m = load('site04_roi3', 10)['metrics']
        self.assertEqual(m['sun_center_visible_pct'], 100.0)
        self.assertAlmostEqual(m['sun_and_earth_center_visible_pct_hourly_samples'], 78.9, delta=0.35)  # <= 1 sample

    def test_site04_roi3_1m_inside_batch_clone_range(self):
        m = load('site04_roi3', 1)['metrics']
        self.assertGreaterEqual(m['sun_center_visible_pct_hourly_samples'], 87.8)
        self.assertLessEqual(m['sun_center_visible_pct_hourly_samples'], 96.4)
        self.assertGreaterEqual(m['sun_and_earth_center_visible_pct_hourly_samples'], 62.6)
        self.assertLessEqual(m['sun_and_earth_center_visible_pct_hourly_samples'], 73.6)


class FrameTie(unittest.TestCase):
    def test_bound_value(self):
        dang, dpos = frame_tie.bound_deg()
        self.assertAlmostEqual(dang, 1.7595e-5, delta=1e-8)
        self.assertAlmostEqual(dpos, 0.5336, delta=1e-3)

    def test_flip_and_time_shift_logic(self):
        mk = lambda t, ms, me: {'t_unix': t, 'sun': {'margin_deg': ms}, 'earth': {'margin_deg': me}}
        b = {'bundle_id': 'synthetic', 'samples': [mk(0, -0.05, 1.0), mk(3600, 0.05, 1e-6), mk(7200, 0.1, 1.0)],
             'events': [{'kind': 'center', 'body': 'sun', 'event': 'center_rise', 'utc': 'x', 't_unix': 1800.0}]}
        r = frame_tie.check_bundle(b)
        self.assertEqual(r['earth_samples_within_bound'], 1)
        self.assertEqual(r['sun_samples_within_bound'], 0)
        self.assertAlmostEqual(r['center_events'][0]['time_shift_bound_s'], 1.7595e-5 / 0.1 * 3600, delta=0.01)


if __name__ == '__main__':
    unittest.main()
