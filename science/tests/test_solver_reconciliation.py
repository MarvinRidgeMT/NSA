"""E2: the documented bundle-vs-batch differences stay within the tolerances stated in docs/SOLVER_RECONCILIATION.md."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('solver_reconciliation', ROOT / 'tools/validation/solver_reconciliation.py')
sr = importlib.util.module_from_spec(spec); spec.loader.exec_module(sr)


class SolverReconciliation(unittest.TestCase):
    def setUp(self):
        self.d = sr.build()

    def test_differences_within_stated_tolerance(self):
        for sid, rows in self.d['sites'].items():
            for k, tol in sr.TOL.items():
                with self.subTest(site=sid, metric=k):
                    self.assertLessEqual(abs(rows[k]['bundle'] - rows[k]['batch']), tol + 1e-9)

    def test_known_values(self):
        s4 = self.d['sites']['site04_roi3']
        self.assertAlmostEqual(s4['sun_pct']['bundle'], 94.362, places=3)
        self.assertAlmostEqual(s4['both_pct']['batch'], 72.107, places=3)
        self.assertEqual([round(x, 2) for x in s4['clone_range']['batch']], [87.54, 97.33])
        self.assertEqual(s4['longest_gap_h']['bundle'], 19)
        self.assertEqual((s4['coverage_sun_pct']['bundle'], s4['coverage_earth_pct']['bundle']), (34.42, 61.13))
        s1 = self.d['sites']['site01_roi6']
        self.assertEqual((s1['coverage_sun_pct']['bundle'], s1['coverage_sun_pct']['batch']), (9.5, 11.0))

    def test_committed_outputs_are_current(self):
        j = json.dumps(self.d, indent=1, ensure_ascii=False) + '\n'
        self.assertEqual((ROOT / sr.OUT_JSON).read_text(), j, 're-run tools/validation/solver_reconciliation.py')
        self.assertEqual((ROOT / sr.OUT_MD).read_text(), sr.markdown(self.d), 're-run tools/validation/solver_reconciliation.py')


if __name__ == '__main__':
    unittest.main()
