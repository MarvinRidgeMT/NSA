import json
import unittest
from pathlib import Path

from science.stretch.arrival_slip import LABEL, SLIP_HOURS, evaluate_slips

ROOT = Path(__file__).resolve().parents[2]


class ArrivalSlipAggregation(unittest.TestCase):
    def setUp(self):
        self.times = [hour * 3600.0 for hour in range(-72, 14 * 24 + 72 + 1)]
        n = len(self.times)
        self.nominal = {
            "sun": [index % 5 != 0 for index in range(n)],
            "both": [index % 3 != 0 for index in range(n)],
        }
        self.clones = {
            clone: {
                "sun": [index % (clone + 2) != 0 for index in range(n)],
                "both": [index % (clone + 3) != 0 for index in range(n)],
            }
            for clone in range(1, 21)
        }

    def points(self):
        return evaluate_slips(
            site_id="site04_roi3",
            bundle_id="fixture",
            times=self.times,
            nominal=self.nominal,
            clones=self.clones,
            base_start=0,
            base_stop=14 * 24 * 3600,
            step_h=1,
        )

    def test_grid_and_traceability(self):
        points = self.points()
        self.assertEqual([point["slip_h"] for point in points], list(SLIP_HOURS))
        self.assertEqual(len(points), 25)
        self.assertTrue(all(point["label"] == LABEL for point in points))
        self.assertEqual(len({point["result_id"] for point in points}), len(points))
        self.assertTrue(all(point["sample_count"] == 337 for point in points))

    def test_clone_ranges_and_pass_counts_are_derived(self):
        zero = next(point for point in self.points() if point["slip_h"] == 0)
        clone_sun = []
        clone_both = []
        indices = range(72, 72 + 337)
        for run in self.clones.values():
            clone_sun.append(round(100 * sum(run["sun"][index] for index in indices) / 337, 3))
            clone_both.append(round(100 * sum(run["both"][index] for index in indices) / 337, 3))
        self.assertEqual(zero["clones"]["sun_center_visible_pct_min"], min(clone_sun))
        self.assertEqual(zero["clones"]["sun_and_earth_center_visible_pct_max"], max(clone_both))
        self.assertEqual(
            zero["clones"]["joint_pass_count"],
            sum(sun >= 70 and both >= 40 for sun, both in zip(clone_sun, clone_both)),
        )
        self.assertEqual(zero["clones"]["pass_denominator"], 20)
        self.assertEqual(zero["clones"]["joint_pass_pct"], 100.0 * zero["clones"]["joint_pass_count"] / 20)
        expected_band = "all" if zero["clones"]["joint_pass_count"] == zero["clones"]["pass_denominator"] else "dropped"
        self.assertEqual(zero["clones"]["pass_band"], expected_band)

    def test_output_is_deterministic(self):
        self.assertEqual(self.points(), self.points())

    def test_missing_hour_is_rejected(self):
        times = self.times.copy()
        times.pop(80)
        nominal = {key: values[:80] + values[81:] for key, values in self.nominal.items()}
        clones = {
            clone: {key: values[:80] + values[81:] for key, values in run.items()}
            for clone, run in self.clones.items()
        }
        with self.assertRaisesRegex(ValueError, "missing"):
            evaluate_slips(
                site_id="site04_roi3",
                bundle_id="fixture",
                times=times,
                nominal=nominal,
                clones=clones,
                base_start=0,
                base_stop=14 * 24 * 3600,
                step_h=1,
            )


class Site04AcceptanceAnchor(unittest.TestCase):
    def test_zero_hour_nominal_is_exactly_94_362(self):
        path = ROOT / "data" / "bundles" / "site04_roi3_2026-11-14_14d_mast1m.json"
        bundle = json.loads(path.read_text())
        direct = round(100 * sum(sample["sun"]["center_visible"] for sample in bundle["samples"]) / len(bundle["samples"]), 3)
        zero = next(point for point in bundle["derived"]["arrival_slip"]["points"] if point["slip_h"] == 0)
        self.assertEqual(direct, bundle["metrics"]["sun_center_visible_pct_hourly_samples"])
        self.assertEqual(zero["nominal"]["sun_center_visible_pct"], direct)
        self.assertEqual(direct, 94.362)


if __name__ == "__main__":
    unittest.main()
