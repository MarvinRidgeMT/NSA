import json
import unittest
from pathlib import Path

import numpy as np

from science import frames, sites
from science.dem import ArrayDEM
from science.stretch.hotspots import LABEL, METHOD_ID, _candidate_bins, aggregate_scores

ROOT = Path(__file__).resolve().parents[2]


def candidate(tile_id, bin_index, distance_m, variance_deg2):
    return {
        "tile_id": tile_id,
        "bin": bin_index,
        "lat_deg": -89.78,
        "lon_deg_east": 203.68,
        "grid_x_m": 1.0,
        "grid_y_m": 2.0,
        "distance_m": distance_m,
        "clone_height_variance_m2": 4.0,
        "clone_relative_height_variance_m2": 4.0,
        "horizon_variance_deg2": variance_deg2,
    }


class HotspotAggregation(unittest.TestCase):
    def setUp(self):
        self.candidates = [candidate("near", 0, 100.0, 0.25), candidate("beyond", 1, 1001.0, 100.0)]
        self.samples = [
            {
                "sun": {"az_deg": 0.0, "margin_deg": 0.5, "horizon_flag": "complete"},
                "earth": {"az_deg": 180.0, "margin_deg": 0.25, "horizon_flag": "complete"},
            },
            {
                "sun": {"az_deg": 0.0, "margin_deg": 2.0, "horizon_flag": "complete"},
                "earth": {"az_deg": 180.0, "margin_deg": 0.25, "horizon_flag": "complete"},
            },
        ]

    def scores(self):
        return aggregate_scores(
            site_id="site04_roi3",
            candidates_by_bin=self.candidates,
            samples=self.samples,
            max_range_m=1000.0,
            critical_margin_deg=1.0,
            step_h=1.0,
        )

    def test_deterministic_and_traceable(self):
        self.assertEqual(self.scores(), self.scores())
        self.assertTrue(all(tile["label"] == LABEL for tile in self.scores()))
        self.assertTrue(all(tile["method"] == METHOD_ID for tile in self.scores()))
        self.assertEqual(len({tile["result_id"] for tile in self.scores()}), 2)

    def test_critical_hours_are_variance_weighted(self):
        near = next(tile for tile in self.scores() if tile["tile_id"] == "near")
        self.assertEqual(near["sun_score"], 0.25)
        self.assertEqual(near["earth_score"], 0.0)
        self.assertEqual(near["score"], 0.25)

    def test_beyond_horizon_distance_scores_zero(self):
        beyond = next(tile for tile in self.scores() if tile["tile_id"] == "beyond")
        self.assertEqual(beyond["score"], 0.0)
        self.assertEqual(beyond["sun_score"], 0.0)
        self.assertEqual(beyond["earth_score"], 0.0)
        self.assertEqual(beyond["display_band"], "zero")

    def test_clone_wide_vertical_shifts_cancel_in_relative_relief(self):
        site = sites.SITES["site04_roi3"]
        observer_x, observer_y = frames.stereo_forward(site["lat"], site["lon"])
        nominal = ArrayDEM(np.zeros((5, 5)), observer_x - 12.5, observer_y + 12.5, 5.0)
        clones = [
            ArrayDEM(np.full((5, 5), float(offset)), nominal.x_left, nominal.y_top, nominal.step)
            for offset in range(20)
        ]
        bundle = {
            "site": {"id": "site04_roi3"},
            "skyline": {
                "bins": 1,
                "critical": [
                    {
                        "distance_m": 5.0,
                        "grid_x_m": observer_x + 5.0,
                        "grid_y_m": observer_y,
                    }
                ],
                "elevation_deg": [0.0],
            },
            "derived": {"attribution": {"per_bin": {"source": ["near_5m"]}}},
        }
        result = _candidate_bins(bundle, nominal, clones)[0]
        self.assertIsNotNone(result)
        self.assertGreater(result["clone_height_variance_m2"], 0.0)
        self.assertEqual(result["clone_relative_height_variance_m2"], 0.0)
        self.assertEqual(result["horizon_variance_deg2"], 0.0)


class RealBundleContract(unittest.TestCase):
    def test_committed_blocks_are_ranked_and_labelled(self):
        for site in ("site04_roi3", "site01_roi6"):
            path = ROOT / "data" / "stretch" / "hotspots" / f"{site}.json"
            if not path.exists():
                self.skipTest("generate data/stretch/hotspots sidecars first")
            block = json.loads(path.read_text())
            self.assertEqual(block["label"], "PILOT")
            self.assertEqual(block["clone_count"], 20)
            self.assertEqual(len(block["top_tiles"]), 10)
            self.assertEqual(block["top_tiles"], block["tiles"][:10])
            self.assertEqual([tile["rank"] for tile in block["top_tiles"]], list(range(1, 11)))
            self.assertTrue(all(tile["score"] >= 0 for tile in block["tiles"]))
            self.assertEqual(
                block["zero_state_caption"] is not None,
                block["tiles_positive"] == 0,
            )


if __name__ == "__main__":
    unittest.main()
