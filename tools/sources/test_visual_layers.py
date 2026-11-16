"""Contract tests for visual layers, driven by schemas/fixtures/visual-layers-cases.json (no network)."""
import copy, json, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "blender"))
import visual_layers as vl  # noqa: E402

with open(os.path.join(ROOT, "schemas", "fixtures", "visual-layers-cases.json"), encoding="utf-8") as _f:
    CASES = json.load(_f)
with open(os.path.join(ROOT, "schemas", "visual-layers-v1.schema.json"), encoding="utf-8") as _f:
    SCHEMA = json.load(_f)


def mutate(case):
    doc = copy.deepcopy(CASES["valid"])
    for path, value in case.get("set", {}).items():
        *parents, leaf = path.split(".")
        node = doc
        for p in parents:
            node = node[int(p)] if isinstance(node, list) else node[p]
        node[leaf] = value
    for path in case.get("delete", []):
        *parents, leaf = path.split(".")
        node = doc
        for p in parents:
            node = node[int(p)] if isinstance(node, list) else node[p]
        del node[leaf]
    if "duplicateLayer" in case:
        doc["layers"].append(copy.deepcopy(doc["layers"][case["duplicateLayer"]]))
    return doc


class Contract(unittest.TestCase):
    def test_valid_fixture_passes(self):
        vl.validate_visual_layers(copy.deepcopy(CASES["valid"]))

    def test_every_invalid_case_is_rejected_with_its_code(self):
        self.assertGreaterEqual(len(CASES["invalid"]), 15)
        for case in CASES["invalid"]:
            with self.subTest(case["name"]):
                with self.assertRaises(vl.VisualLayerError) as cm:
                    vl.validate_visual_layers(mutate(case))
                self.assertEqual(cm.exception.code, case["code"])

    def test_json_schema_agrees_when_jsonschema_is_installed(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema not installed in this interpreter")
        v = Draft202012Validator(SCHEMA)
        self.assertEqual(list(v.iter_errors(CASES["valid"])), [])
        cross_field = {"bounds do not match artifact size x pixel size", "inverted bounds", "duplicate ids"}  # not expressible in JSON Schema
        for case in CASES["invalid"]:
            if case["name"] in cross_field:
                continue
            with self.subTest(case["name"]):
                self.assertTrue(list(v.iter_errors(mutate(case))), "schema accepted an invalid document")


class SolverGuard(unittest.TestCase):
    def objects(self, key):
        for c in CASES["solverGuard"][key]:
            yield c["name"], (copy.deepcopy(CASES["valid"]["layers"][c["useLayer"]]) if "useLayer" in c else copy.deepcopy(c["object"]))

    def test_guard_rejects_visual_layers(self):
        for name, obj in self.objects("rejected"):
            with self.subTest(name):
                with self.assertRaises(vl.VisualLayerError):
                    vl.reject_visual_layer(obj)

    def test_guard_accepts_numerical_dem(self):
        for name, obj in self.objects("accepted"):
            with self.subTest(name):
                self.assertIs(vl.reject_visual_layer(obj), obj)

    def test_python_solver_refuses_a_visual_layer(self):
        import polaris_geometry as g
        for name, obj in self.objects("rejected"):
            with self.subTest(name):
                with self.assertRaises(ValueError):
                    g.validate_dem(obj)
                with self.assertRaises(ValueError):
                    g.terrain_horizon(obj, 0.0, 0.0, 2.0, 90.0)
                with self.assertRaises(ValueError):
                    g.trace_visibility(obj, 0.0, 0.0, 2.0, 90.0, 1.0)

    def test_python_solver_still_accepts_a_numerical_dem(self):
        import polaris_geometry as g
        for name, obj in self.objects("accepted"):
            with self.subTest(name):
                self.assertEqual(g.validate_dem(obj), 3)


class GeneratedFile(unittest.TestCase):
    def test_generated_visual_layers_file_is_valid_and_matches_disk(self):
        p = os.path.join(ROOT, "data", "visual", "visual_layers.json")
        if not os.path.exists(p):
            self.skipTest("data/visual/visual_layers.json not generated yet (texture download incomplete)")
        import hashlib
        with open(p, encoding="utf-8") as f:
            doc = json.load(f)
        vl.validate_visual_layers(doc)
        for layer in doc["layers"]:
            art = os.path.join(ROOT, layer["artifact"]["path"])
            self.assertTrue(os.path.exists(art), art)
            with open(art, "rb") as f:
                self.assertEqual(hashlib.sha256(f.read()).hexdigest(), layer["artifact"]["sha256"])


class Generator(unittest.TestCase):
    """build_visual_layers.nac_layer on a synthetic window in a temp tree (no network, no real imagery)."""

    def make(self, rows_used):
        import hashlib, tempfile
        import build_visual_layers as b
        root = tempfile.mkdtemp(prefix="polaris_vl_")
        d = os.path.join(root, b.NAC_DIR)
        os.makedirs(d)
        png = os.path.join(d, "site01_fixture_1m_8bit.png")
        with open(png, "wb") as f:
            f.write(b"FIXTURE-NOT-AN-IMAGE")
        manifest = {
            "product": {"title": "Controlled 1 m/pixel South Pole Average Mosaic", "productId": "NAC_POLE_SOUTH_CM_AVG_P892S2250",
                        "url": "https://pds.lroc.im-ldi.com/x.IMG", "productPage": "https://data.lroc.im-ldi.com/lroc/view_rdr/NAC_POLE_SOUTH_CM_AVG", "cite": "fixture"},
            "projection": {"pixelScaleM": 1.0},
            "window": {"xminM": -12000.0, "xmaxM": -10000.0, "yminM": -13000.0, "ymaxM": -11000.0, "width": 2000, "height": 2000},
            "rawWindowSha256": "a" * 64,
            "display8bit": {"file": "site01_fixture_1m_8bit.png", "sha256": hashlib.sha256(b"FIXTURE-NOT-AN-IMAGE").hexdigest(),
                            "stretch": "linear percentile stretch", "p0_5": 0.02, "p99_5": 0.3},
            "limitations": ["Average of many NAC images under different Sun directions."],
        }
        with open(os.path.join(d, "site01_fixture_manifest.json"), "w") as f:
            json.dump(manifest, f)
        reg = {"peakNcc": 0.4, "nccAtZeroShift": 0.37, "imageShiftRelativeToDemM": {"x": -5.7, "y": -0.3}, "comparedPixels5m": 160000,
               "rowsUsed1m": rows_used, "method": "fixture method", "dem": "app/data/source/pgda78/Site01/Site01_final_adj_5mpp_surf.tif"}
        with open(os.path.join(d, "site01_fixture_registration.json"), "w") as f:
            json.dump(reg, f)
        old = b.ROOT
        b.ROOT = root
        try:
            return b.nac_layer(os.path.join(d, "site01_fixture_manifest.json"))
        finally:
            b.ROOT = old

    def test_complete_window_becomes_a_valid_visual_layer(self):
        layer, why = self.make(2000)
        self.assertIsNone(why)
        vl.validate_layer(layer)
        self.assertEqual(layer["label"], "LROC NAC AVG · VISUAL")
        self.assertIs(layer["numericalAuthority"], False)
        self.assertEqual(layer["registration"]["offsetM"], {"x": -5.7, "y": -0.3})
        self.assertEqual(layer["registration"]["appliedShiftM"], {"x": 0, "y": 0})
        self.assertIsNone(layer["sourceHash"]["wholeFileSha256"])

    def test_partial_registration_never_becomes_a_layer(self):
        layer, why = self.make(1055)
        self.assertIsNone(layer)
        self.assertIn("not the full window", why)


if __name__ == "__main__":
    unittest.main()
