"""Offline tests for the source tools (no network). Run: python3 -m unittest discover -s tools/sources -p 'test_*.py' -v"""
import json, math, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import fetch_lroc_nac_crop as nac  # noqa: E402

S0, L0 = nac.EXPECT["SAMPLE_PROJECTION_OFFSET"], nac.EXPECT["LINE_PROJECTION_OFFSET"]


class NacPixelRule(unittest.TestCase):
    def test_tile_corners_match_label_extent(self):
        # tile P892S2250 is the 180-270 E quadrant: x in [-45488, 0], y in [-45488, 0], pole at the top-right corner
        self.assertEqual(nac.pixel_center_xy(1, 1, S0, L0), (-45487.5, -0.5))
        self.assertEqual(nac.pixel_center_xy(45488, 45488, S0, L0), (-0.5, -45487.5))

    def test_site01_window_is_2000_px_and_aligned_to_the_5m_grid(self):
        s1, s2, l1, l2 = nac.window_to_pixels(-12000, -10000, -13000, -11000, S0, L0)
        self.assertEqual((s2 - s1 + 1, l2 - l1 + 1), (2000, 2000))
        x_first, y_first = nac.pixel_center_xy(s1, l1, S0, L0)
        x_last, y_last = nac.pixel_center_xy(s2, l2, S0, L0)
        self.assertEqual((x_first - 0.5, x_last + 0.5, y_first + 0.5, y_last - 0.5), (-12000, -10000, -11000, -13000))

    def test_site01_reference_point_falls_inside_the_window_and_tile_quadrant(self):
        lat, lon_e, R = -89.4632, -137.49, 1737400.0
        r = 2 * R * math.tan(math.radians(90 + lat) / 2)
        x, y = r * math.sin(math.radians(lon_e)), r * math.cos(math.radians(lon_e))
        self.assertAlmostEqual(x, -10999.14, delta=0.05)   # same value as the bundle's site.projectedMeters
        self.assertAlmostEqual(y, -11999.26, delta=0.05)
        self.assertTrue(-12000 < x < -10000 and -13000 < y < -11000)
        self.assertTrue(180 <= (lon_e % 360) <= 270)

    def test_block_requests_cover_exactly_the_missing_rows(self):
        self.assertEqual(nac.missing_blocks([5, 6, 7, 9, 10, 20], 2), [(5, 2), (7, 1), (9, 2), (20, 1)])
        self.assertEqual(nac.missing_blocks(range(1286, 2000), 50)[0], (1286, 50))
        self.assertEqual(sum(c for _, c in nac.missing_blocks(range(1286, 2000), 50)), 714)
        s1, _s2, l1, _l2 = nac.window_to_pixels(-12000, -10000, -13000, -11000, S0, L0)
        rec = int(nac.EXPECT["RECORD_BYTES"])
        one = nac.block_byte_range(0, 1, l1, s1, 2000, rec, 1)
        self.assertEqual(one, (rec + (l1 - 1) * rec + (s1 - 1) * 4, rec + (l1 - 1) * rec + (s1 - 1) * 4 + 7999))   # same bytes as the per-row request
        start, end = nac.block_byte_range(10, 3, l1, s1, 2000, rec, 1)
        self.assertEqual(start, one[0] + 10 * rec)
        self.assertEqual(end - start + 1, 2 * rec + 8000)

    def test_label_parser_reads_values_with_units(self):
        text = "\n".join(f"    {k} = {json.dumps(v) if isinstance(v, str) else v} <X>" if not isinstance(v, str) else f"    {k} = \"{v}\"" for k, v in nac.EXPECT.items())
        self.assertEqual(nac.parse_label(text), nac.EXPECT)


class Registry(unittest.TestCase):
    def setUp(self):
        p = os.path.join(ROOT, "data", "source_registry.json")
        if not os.path.exists(p):
            self.skipTest("data/source_registry.json not generated")
        with open(p, encoding="utf-8") as f:
            self.reg = json.load(f)

    def test_status_and_roles(self):
        self.assertEqual(self.reg["releaseStatus"], "SOURCE_BASED_UNVALIDATED")
        roles = {s["id"]: s["role"] for s in self.reg["sources"]}
        self.assertEqual(roles["NASA_PGDA_78"], "numerical-authority")
        self.assertEqual(roles["JPL_HORIZONS"], "ephemeris-authority")
        for visual in ("NASA_SVS_14959", "LROC_NAC_POLE_SOUTH_CM_AVG"):
            self.assertEqual(roles[visual], "visual-context")
            src = next(s for s in self.reg["sources"] if s["id"] == visual)
            self.assertIs(src["numericalAuthority"], False)
        self.assertEqual(roles["NASA_PGDA_69"], "reference-layer")

    def test_no_hash_mismatch_and_every_local_file_hashed(self):
        self.assertEqual(self.reg["summary"]["hashMismatches"], [])
        for s in self.reg["sources"]:
            for f in s["files"]:
                self.assertTrue(f["present"]); self.assertEqual(len(f["sha256"]), 64)

    def test_remote_only_sources_do_not_claim_a_whole_file_hash(self):
        p90 = next(s for s in self.reg["sources"] if s["id"] == "NASA_PGDA_90")
        self.assertIsNone(p90["wholeFileSha256"])


if __name__ == "__main__":
    unittest.main()
