import unittest

from planner import grounding_check

RESULTS = [{"site": "site04_roi3", "sun_center_visible_pct": 94.362, "clones": {"count": 20, "pass": 18}},
           "window 2026-11-14 to 2026-11-28"]


class GroundingCheck(unittest.TestCase):
    def test_all_numbers_grounded(self):
        ok, bad = grounding_check("Site04 RoI 3: Sun visible 94.362% on 18 of 20 maps.", RESULTS)
        # a free-standing "3" (RoI 3) is a number too and must be in the results; "Site04" is an identifier
        self.assertFalse(ok)
        self.assertEqual(bad, ["3"])
        ok, bad = grounding_check("Sun visible 94.362% on 18 of 20 maps.", RESULTS)
        self.assertTrue(ok, bad)

    def test_invented_number_rejected(self):
        ok, bad = grounding_check("Sun visible about 95% on 18 of 20 maps.", RESULTS)
        self.assertFalse(ok)
        self.assertEqual(bad, ["95"])

    def test_rounding_is_not_grounding(self):
        ok, bad = grounding_check("Sun visible 94.4% of the time.", RESULTS)
        self.assertFalse(ok)
        self.assertEqual(bad, ["94.4"])


if __name__ == "__main__":
    unittest.main()
