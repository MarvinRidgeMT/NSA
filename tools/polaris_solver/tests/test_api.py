import json, numpy as np, pytest
from polaris_solver import solve, TOOL_SPEC
from polaris_solver import core

def test_float64_heights():
    assert (core.R_MOON + np.zeros(1, np.float64)).dtype == np.float64

def test_site04_roi3_demo_window():
    r = solve({"lat": -89.78012, "lon": -156.32023, "mast_m": 1.0})
    assert r["site_tile"] == "Site04"
    assert r["nominal"]["sun_pct"] == pytest.approx(94.36, abs=0.01)
    assert r["nominal"]["sun_earth_pct"] == pytest.approx(72.11, abs=0.01)
    assert r["nominal"]["longest_dark_h"] == 19
    assert "UNVALIDATED" in r["labels"]

def test_clones_and_labels():
    r = solve({"lat": -89.78012, "lon": -156.32023, "clones": 3})
    assert r["clones"]["n"] == 3 and "/" in r["clones"]["pass_k_of_n"]
    assert "not a probability" in r["clones"]["note"]

def test_outside_tiles():
    with pytest.raises(ValueError):
        solve({"lat": -88.2, "lon": 10.0})

def test_tool_spec_is_json():
    json.dumps(TOOL_SPEC); assert TOOL_SPEC["input_schema"]["required"] == ["lat", "lon"]
