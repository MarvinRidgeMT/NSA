import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from science.decision_card import build_card, write_card


ROOT = Path(__file__).resolve().parents[2]
SITE04 = ROOT / "data" / "bundles" / "site04_roi3_2026-11-14_14d_mast1m.json"


def resolve_path(value, path):
    current = value
    for part in path.replace("]", "").split("."):
        bits = part.split("[")
        current = current[bits[0]]
        for index in bits[1:]:
            current = current[int(index)]
    return current


class DecisionCardTests(unittest.TestCase):
    def test_regeneration_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            a = write_card(SITE04, Path(first))
            b = write_card(SITE04, Path(second))
            self.assertEqual(a[0].read_bytes(), b[0].read_bytes())
            self.assertEqual(a[1].read_bytes(), b[1].read_bytes())
            self.assertNotIn("<script", a[1].read_text().lower())

    def test_numeric_sources_and_margins_trace_to_bundle(self):
        raw = SITE04.read_bytes()
        bundle = json.loads(raw)
        card = build_card(
            bundle,
            bundle_path="data/bundles/site04_roi3_2026-11-14_14d_mast1m.json",
            bundle_sha256=hashlib.sha256(raw).hexdigest(),
        )

        def visit(value):
            if isinstance(value, dict):
                if "source_path" in value and "value" in value:
                    self.assertEqual(value["value"], resolve_path(bundle, value["source_path"]))
                    return
                if value.get("source_type") == "team requirement" and "value" in value:
                    self.assertEqual(value["value"], 120)
                    self.assertEqual(value["source"], "CLI --max-dark-h")
                    self.assertEqual(value["classification"], "SCENARIO")
                    return
                if value.get("formula") == "nominal - threshold":
                    nominal = resolve_path(bundle, value["source_paths"]["nominal"])
                    threshold = resolve_path(bundle, value["source_paths"]["threshold"])
                    self.assertEqual(value["value"], round(nominal - threshold, 12))
                    return
                if value.get("formula") == "threshold - nominal":
                    nominal = resolve_path(bundle, value["source_paths"]["nominal"])
                    threshold = card["longest_sun_blocked_requirement"]["threshold"]["value"]
                    self.assertEqual(value["value"], round(threshold - nominal, 12))
                    self.assertEqual(value["threshold_source"], "CLI --max-dark-h")
                    return
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                self.fail(f"untraced numeric value in decision card: {value!r}")

        visit(card)

    def test_missing_optional_fields_are_omitted(self):
        raw = SITE04.read_bytes()
        bundle = json.loads(raw)
        bundle["derived"].pop("attribution")
        bundle["derived"].pop("coverage")
        bundle["metrics"].pop("longest_sun_center_hidden_h")
        for key in ("certainty", "certainty_curve", "certainty_height_m"):
            bundle["derived"].pop(key, None)
        card = build_card(bundle, bundle_path=SITE04.name, bundle_sha256=hashlib.sha256(raw).hexdigest())
        self.assertEqual(card["ridge_of_record"], [])
        self.assertNotIn("longest_sun_blocked_requirement", card)
        self.assertNotIn("certainty_height_m", card)
        self.assertTrue(all(row["coverage"] is None for row in card["requirements"]))

    def test_site04_crosscheck_uses_exact_bundle_values(self):
        raw = SITE04.read_bytes()
        bundle = json.loads(raw)
        card = build_card(bundle, bundle_path=SITE04.name, bundle_sha256=hashlib.sha256(raw).hexdigest())
        rows = {row["requirement_id"]: row for row in card["requirements"]}
        sun = rows["sun-centre"]
        both = rows["sun-and-earth"]
        self.assertEqual(sun["nominal"]["value"], 94.362)
        self.assertEqual((sun["clone_range"]["min"]["value"], sun["clone_range"]["max"]["value"]), (87.537, 97.329))
        self.assertEqual(both["nominal"]["value"], 72.107)
        self.assertEqual((both["clone_range"]["min"]["value"], both["clone_range"]["max"]["value"]), (64.392, 74.481))
        darkness = card["longest_sun_blocked_requirement"]
        self.assertEqual(darkness["nominal"]["value"], 19.4434)
        self.assertEqual(darkness["threshold"]["value"], 120)
        self.assertEqual(darkness["signed_margin"]["value"], 100.5566)
        self.assertTrue(darkness["pass"])
        self.assertIn("nominal only", darkness["clone_evidence"]["status"])
        # A2 Certainty Height (science/certainty.py, ported from a-science 0252b36): nominal + 20 clones all at 100 % Sun centre.
        self.assertEqual(card["certainty_height_m"], {"value": 1.75, "source_path": "derived.certainty_height_m"})

    def test_max_darkness_is_an_explicit_team_requirement(self):
        raw = SITE04.read_bytes()
        bundle = json.loads(raw)
        card = build_card(
            bundle,
            bundle_path=SITE04.name,
            bundle_sha256=hashlib.sha256(raw).hexdigest(),
            max_dark_h=10,
        )
        darkness = card["longest_sun_blocked_requirement"]
        self.assertEqual(darkness["threshold"]["value"], 10)
        self.assertEqual(darkness["threshold"]["source_type"], "team requirement")
        self.assertEqual(darkness["signed_margin"]["value"], -9.4434)
        self.assertFalse(darkness["pass"])


if __name__ == "__main__":
    unittest.main()
