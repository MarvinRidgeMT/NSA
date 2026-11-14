"""T4 tests: emitted bundles validate against science-bundle-v2 and obey the contract."""
import json
import unittest
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / 'schemas' / 'science-bundle-v2.schema.json').read_text())
BUNDLES = sorted((ROOT / 'data' / 'bundles').glob('*.json')) + sorted((ROOT / 'data' / 'bundles' / 'fixtures').glob('*.json'))


class BundleContract(unittest.TestCase):
    def test_bundles_exist(self):
        self.assertTrue(any(p.name.startswith('site01_2026-11-14_14d') for p in BUNDLES))
        self.assertTrue((ROOT / 'data/bundles/fixtures/site01_ui_fixture_50.json').exists())

    def test_schema_valid(self):
        jsonschema.Draft202012Validator.check_schema(SCHEMA)
        for p in BUNDLES:
            with self.subTest(p.name):
                jsonschema.validate(json.loads(p.read_text()), SCHEMA)

    def test_contract_invariants(self):
        for p in BUNDLES:
            b = json.loads(p.read_text())
            with self.subTest(p.name):
                sky = b['skyline']
                for e, st, c in zip(sky['elevation_deg'], sky['status'], sky['critical']):
                    self.assertEqual(e is None, c is None)       # no angle without a real critical sample
                    if st == 'complete':
                        self.assertIsNotNone(e)
                self.assertEqual(b['validation_status']['overall'], 'SOURCE-BASED UNVALIDATED')
                for s in b['samples']:
                    for body in ('sun', 'earth'):
                        x = s[body]
                        self.assertAlmostEqual(x['margin_deg'], x['el_deg'] - x['horizon_deg'], places=4)
                ts = [s['t_unix'] for s in b['samples']]
                self.assertEqual(ts, sorted(ts))
                for e in b['events']:
                    self.assertTrue(ts[0] <= e['t_unix'] <= ts[-1])  # no extrapolation
                    self.assertLessEqual(e['bracket_width_s'], 1.0)

    def test_fixture_is_exact_subset(self):
        full = json.loads((ROOT / 'data/bundles/site01_2026-11-14_14d.json').read_text())
        fx = json.loads((ROOT / 'data/bundles/fixtures/site01_ui_fixture_50.json').read_text())
        self.assertEqual(len(fx['samples']), 50)
        for i, s in zip(fx['fixture']['sample_indices'], fx['samples']):
            self.assertEqual(full['samples'][i], s)
        self.assertEqual(full['skyline'], fx['skyline'])



class NegativeCases(unittest.TestCase):
    def setUp(self):
        self.b = json.loads((ROOT / 'data/bundles/fixtures/site01_ui_fixture_50.json').read_text())

    def test_fabricated_status_rejected(self):
        self.b['skyline']['status'][0] = 'filled'
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(self.b, SCHEMA)

    def test_short_range_rejected(self):
        self.b['skyline']['max_range_m'] = 15000
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(self.b, SCHEMA)

    def test_unlabelled_metrics_rejected(self):
        self.b['metrics']['label'] = 'NASA'
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(self.b, SCHEMA)


if __name__ == '__main__':
    unittest.main()
