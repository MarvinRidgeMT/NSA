"""Mars relay geometry (science/worlds/mars/relays.py): pass logic, no extrapolation, the committed file reproduces."""
import json
import unittest

import numpy as np

from science.worlds.mars import relays as R

FILE = R.OUT_DIR / 'mars_jezero_rim_relays_2026-11-14_16d.json'


class PassLogic(unittest.TestCase):
    def test_passes_gaps_and_window_edges(self):
        vis = np.array([1, 1, 0, 0, 0, 1, 1, 1, 0, 1], bool)
        t = np.arange(len(vis)) * 60.0
        el = np.arange(len(vis), dtype=float)
        ps = R.passes(t, vis, el, np.full(len(vis), 500.0))
        self.assertEqual([p['duration_min'] for p in ps], [2, 3, 1])
        self.assertEqual([p['truncated_by_window'] for p in ps], [True, False, True])
        self.assertEqual(ps[1]['max_el_deg'], 7.0)
        self.assertEqual(R.longest_gap_min(vis), 3)
        s = R.summarise(t, vis, el, np.full(len(vis), 500.0), 1.0)
        self.assertEqual((s['n_passes'], s['n_passes_complete']), (3, 1))
        self.assertEqual(s['pass_duration_min']['median'], 3.0)


class CommittedFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads(FILE.read_text())

    def test_labels_window_and_status(self):
        d = self.d
        self.assertIn('not relay availability', d['label'])
        self.assertEqual((d['window_utc']['start'], d['window_utc']['stop'], d['window_utc']['step']),
                         (R.START, R.STOP, R.STEP))
        by = {o['id']: o for o in d['orbiters']}
        self.assertEqual(set(by), {r[0] for r in R.ORBITERS})
        for o in by.values():
            if o['status'] == 'computed':
                self.assertEqual(o['n_samples'], 16 * 1440 + 1)
                self.assertEqual(o['independent_check']['status'], 'pass')
                ev = R.TRAJECTORY_READING[o['id']]['evidence']
                self.assertTrue(any(ev in l for l in o['horizons_trajectory_notes']['lines']), (o['id'], ev))
                t = o['terrain']
                self.assertLessEqual(t['visible_pct_minute_samples'], o['flat_horizon_control']['visible_pct_minute_samples'])
            else:
                self.assertIn('no ephemeris', o['reason'].lower())        # never extrapolated

    def test_rebuilds_offline_from_cached_horizons(self):
        try:
            out, _ = R.build(allow_network=False, out_dir=_Tmp.path())
        except LookupError:
            self.skipTest('Horizons responses not cached (git-ignored)')
        out = json.loads(json.dumps(out))
        # Horizons' "no ephemeris" answers are not cached, so offline those orbiters fail with a cache miss instead;
        # only their status is compared.
        def strip(x):
            return {**{k: v for k, v in x.items() if k not in ('generator', 'orbiters')},
                    'orbiters': [o if o['status'] == 'computed' else {'id': o['id'], 'status': o['status']}
                                 for o in x['orbiters']]}
        self.assertEqual(strip(out), strip(self.d))


class _Tmp:
    _d = None

    @classmethod
    def path(cls):
        import tempfile
        if cls._d is None:
            cls._d = tempfile.mkdtemp()
        return cls._d


if __name__ == '__main__':
    unittest.main()
