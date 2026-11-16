"""Consistency tests for the v2 terrain catalogue (no network). Run: python -m pytest -q tools/globe"""
import math
import re
import unittest

from tools.globe import products as P


class CatalogueTests(unittest.TestCase):
    def test_every_section_2_1_row_is_catalogued(self):
        need = {"sldem2015_512", "pgda67_slope_azimuth_64", "lola_ldem_global", "lola_ldem_polar", "pgda90_polar",
                "pgda78_sites", "kaguya_tc_dtm", "lroc_nac_dtm", "gsfc_sfs", "ch2_tmc2_dem", "pgda70_roughness",
                "lola_roughness_gdr", "lroc_wac_100m", "lroc_nac_images"}
        self.assertLessEqual(need, set(P.PRODUCTS))

    def test_account_gated_products_are_never_downloaded(self):
        plan = {p.product_id for p in P.download_plan()}
        for pid in ("ch2_tmc2_dem", "cnsa_change_dem"):
            p = P.get(pid)
            self.assertEqual(p.status, "not-downloaded")
            self.assertIn("needs an account the user has not approved", p.reason)
            self.assertNotIn(pid, plan)
            self.assertEqual(p.files, [])

    def test_not_downloaded_entries_say_why(self):
        for p in P.PRODUCTS.values():
            if p.status != "download":
                self.assertTrue(p.reason, p.product_id)

    def test_download_entries_have_licence_ack_version_and_files(self):
        for p in P.download_plan():
            self.assertTrue(p.files, p.product_id)
            for attr in ("licence", "acknowledgement", "product_version", "landing_page"):
                self.assertGreater(len(getattr(p, attr)), 10, (p.product_id, attr))

    def test_urls_are_public_archives_and_local_paths_unique(self):
        hosts = ("https://pds-geosciences.wustl.edu/", "http://imbrium.mit.edu/",
                 "https://asc-pds-services.s3.us-west-2.amazonaws.com/")
        seen = set()
        for p in P.download_plan():
            for f in p.files:
                self.assertTrue(f.url.startswith(hosts), f.url)
                self.assertNotRegex(f.url, r"[?&](token|key|sig|password)=", f.url)
                key = (p.product_id, f.relpath)
                self.assertNotIn(key, seen)
                seen.add(key)
                self.assertFalse(f.relpath.startswith(("/", "..")), f.relpath)

    def test_priority_order_matches_the_task(self):
        order = [p.product_id for p in P.download_plan()]
        self.assertLess(order.index("lola_ldem_global"), order.index("lola_ldem_polar"))
        self.assertLess(order.index("lola_ldem_polar"), order.index("pgda70_roughness"))
        self.assertLess(order.index("pgda70_roughness"), order.index("pgda67_slope_azimuth_64"))
        self.assertLess(order.index("pgda67_slope_azimuth_64"), order.index("sldem2015_512"))
        self.assertLess(order.index("sldem2015_512"), order.index("lroc_wac_100m"))

    def test_cylindrical_sizes_match_pixel_counts(self):
        # float32 simple cylindrical: (360 * ppd) samples x (lat span * ppd) lines x 4 bytes
        for p in (P.get("lola_ldem_global"), P.get("pgda67_slope_azimuth_64"), P.get("pgda67_slope_azimuth_128")):
            for f in p.files:
                m = re.search(r"(?:ldem_|SLDEM2015_)(\d+)_", f.url)
                if f.bytes and m:
                    ppd = int(m.group(1))
                    self.assertEqual(f.bytes, 360 * ppd * 180 * ppd * 4, f.url)
        for f in P.get("sldem2015_512").files:
            if f.url.endswith("_float.img") and "sldem2015_512_" in f.url:
                self.assertEqual(f.bytes, (45 * 512) * (30 * 512) * 4, f.url)

    def test_polar_sizes_are_square_and_match_ring_radius(self):
        R = 1737400.0
        for f in P.get("lola_ldem_polar").files:
            if not f.url.endswith("_float.img"):
                continue
            m = re.search(r"ldem_(\d+)([ns])_(\d+)m_float", f.url)
            ring = float(m.group(1)) / (10 if len(m.group(1)) == 3 else 1)   # "875" -> 87.5
            post = int(m.group(3))
            n = math.isqrt(f.bytes // 4)
            self.assertEqual(n * n * 4, f.bytes, f.url)
            # half-width of a polar stereographic grid reaching colatitude (90 - ring), true scale at the pole
            half = 2 * R * math.tan(math.radians(90 - ring) / 2)
            self.assertAlmostEqual(n * post / 2, half, delta=0.01 * half, msg=f.url)

    def test_budget_fits_tonight(self):
        total = sum(p.total_bytes for p in P.download_plan())
        self.assertLess(total, 150e9)


if __name__ == "__main__":
    unittest.main()
