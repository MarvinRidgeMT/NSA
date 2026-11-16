import json
import unittest
from pathlib import Path

from science.stretch.flip_forecast import LABEL, comparison_row, confusion

ROOT = Path(__file__).resolve().parents[2]


class ConfusionMetrics(unittest.TestCase):
    def test_counts_precision_recall_and_traceability(self):
        result = comparison_row(
            site_id="site04_roi3",
            row_id="fixture",
            label="Fixture",
            predicted=[True, True, False, False],
            actual=[True, False, True, False],
        )
        self.assertEqual(result["label"], LABEL)
        self.assertEqual(result["result_id"], "flip-forecast-site04_roi3-m1-fixture")
        self.assertEqual(result["true_positive"], 1)
        self.assertEqual(result["false_positive"], 1)
        self.assertEqual(result["false_negative"], 1)
        self.assertEqual(result["true_negative"], 1)
        self.assertEqual(result["precision"], 0.5)
        self.assertEqual(result["recall"], 0.5)
        self.assertEqual(result["precision_display"], "50.0 %")

    def test_zero_denominators_remain_not_evaluable(self):
        result = confusion([False, False], [False, False])
        self.assertIsNone(result["precision"])
        self.assertIsNone(result["recall"])
        self.assertEqual(result["precision_display"], "not evaluable")
        self.assertEqual(result["recall_display"], "not evaluable")

    def test_inputs_must_align(self):
        with self.assertRaisesRegex(ValueError, "aligned"):
            confusion([True], [True, False])


class RealBundleContract(unittest.TestCase):
    def test_committed_blocks_are_complete_and_threshold_traceable(self):
        for site in ("site04_roi3", "site01_roi6"):
            path = ROOT / "data" / "stretch" / "flip_forecast" / f"{site}.json"
            if not path.exists():
                self.skipTest("generate data/stretch/flip_forecast sidecars first")
            block = json.loads(path.read_text())
            bundle_path = ROOT / "data" / "bundles" / f"{site}_2026-11-14_14d_mast1m.json"
            bundle = json.loads(bundle_path.read_text())
            self.assertEqual(block["label"], "PILOT")
            self.assertEqual(block["clone_count"], 20)
            self.assertEqual(block["sample_count"], len(bundle["samples"]))
            self.assertEqual(block["thresholds"], {
                "sun_center_visible_pct_min": bundle["derived"]["arrival_slip"]["thresholds"]["sun_center_visible_pct_min"],
                "sun_and_earth_center_visible_pct_min": bundle["derived"]["arrival_slip"]["thresholds"]["sun_and_earth_center_visible_pct_min"],
                "source_result_id": bundle["derived"]["arrival_slip"]["result_id"],
            })
            self.assertEqual(len(block["per_clone"]), 20)
            self.assertEqual(len(block["forecast_vs_actual"]), 4)
            self.assertEqual(len({row["result_id"] for row in block["forecast_vs_actual"]}), 4)
            for row in block["forecast_vs_actual"]:
                self.assertEqual(
                    row["case_count"],
                    row["true_positive"] + row["false_positive"] + row["false_negative"] + row["true_negative"],
                )

    def test_committed_site_comparisons_keep_nulls_and_known_counts(self):
        site04 = json.loads((ROOT / "data" / "stretch" / "flip_forecast" / "site04_roi3.json").read_text())
        rows04 = {row["row_id"]: row for row in site04["forecast_vs_actual"]}
        self.assertEqual(
            {key: rows04["sun-hourly"][key] for key in ("predicted_flips", "actual_flips", "true_positive", "false_positive", "false_negative")},
            {"predicted_flips": 241, "actual_flips": 243, "true_positive": 240, "false_positive": 1, "false_negative": 3},
        )
        self.assertEqual(rows04["earth-hourly"]["recall_display"], "62.2 %")
        self.assertIsNone(rows04["mission-thresholds"]["precision"])
        self.assertIsNone(rows04["mission-thresholds"]["recall"])

        site01 = json.loads((ROOT / "data" / "stretch" / "flip_forecast" / "site01_roi6.json").read_text())
        for row in site01["forecast_vs_actual"]:
            self.assertEqual(row["predicted_flips"], 0)
            self.assertEqual(row["actual_flips"], 0)
            self.assertEqual(row["precision_display"], "not evaluable")
            self.assertEqual(row["recall_display"], "not evaluable")


if __name__ == "__main__":
    unittest.main()
