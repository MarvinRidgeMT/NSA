"""Phase 6 — landing dispersion. sigma -> 0 reproduces the point result; seed-fixed reproducibility; the default preset
really has its 99 % circle at 100 m; samples beyond the field are never counted as pass or fail."""
import json
from pathlib import Path

import numpy as np
import pytest

from science.cube import build_dispersion as BD

ROOT = Path(__file__).resolve().parents[2]


def _synthetic_field(seed=0):
    rng = np.random.default_rng(seed)
    n = len(BD.field_offsets())
    vis = rng.random((21, n)) < 0.7
    slope = rng.uniform(0, 15, (21, n))
    return vis, slope


def test_sigma_zero_reproduces_point_result():
    vis, slope = _synthetic_field()
    centre = BD.field_offsets().index((0, 0))
    idx = BD.assign(BD.samples({'kind': 'iso', 'sigma': 0.0}))
    assert np.all(idx == centre)
    k, nom, inside = BD.outcome(vis, slope, idx, 10.0)
    ok = vis & (slope < 10.0)
    assert np.all(k == ok[1:, centre].sum()) and np.all(nom == ok[0, centre]) and inside.all()


def test_seed_fixed_reproducibility():
    for d in BD.DISPERSIONS.values():
        assert np.array_equal(BD.samples(d), BD.samples(d))
    assert not np.array_equal(BD.samples(BD.DISPERSIONS['sigma25'], seed=1), BD.samples(BD.DISPERSIONS['sigma25'], seed=2))


def test_sigma99_preset_has_99pct_circle_at_100m():
    pts = BD.samples(BD.DISPERSIONS['sigma99_100m'], n=200_000)
    assert np.mean(np.hypot(pts[:, 0], pts[:, 1]) <= 100.0) == pytest.approx(0.99, abs=0.002)


def test_ellipse_axes():
    pts = BD.samples(BD.DISPERSIONS['ellipse_60x20_30deg'], n=200_000)
    cov = np.cov(pts.T)
    w, v = np.linalg.eigh(cov)
    assert np.sqrt(w[1]) == pytest.approx(60, rel=0.02) and np.sqrt(w[0]) == pytest.approx(20, rel=0.02)
    major = v[:, 1] * np.sign(v[1, 1])
    assert np.degrees(np.arctan2(major[0], major[1])) == pytest.approx(30, abs=1.0)


def test_outside_field_never_counted():
    vis, slope = _synthetic_field()
    pts = np.array([[0.0, 0.0], [400.0, 0.0], [0.0, -1000.0]])
    k, nom, inside = BD.outcome(vis, slope, BD.assign(pts), 10.0)
    assert inside.tolist() == [True, False, False] and k[1] == -1 and not nom[1:].any()


def test_built_cube_consistency():
    p = ROOT / 'data' / 'cubes' / 'site04_roi3' / 'dispersion.json'
    if not p.exists():
        pytest.skip('dispersion cube not built')
    c = json.loads(p.read_text())
    h = np.array(c['metrics']['samples']['values']).reshape(2, len(BD.DISPERSIONS), 22)
    assert np.all(h.sum(axis=2) == BD.N_SAMPLES)
    share = np.array(c['derived']['summary']['metrics']['share_pass_all_20_pct']['values']).reshape(2, -1)
    assert np.allclose(share, 100 * h[:, :, 20] / BD.N_SAMPLES, atol=1e-3)
    assert np.all(share[1] <= share[0] + 1e-9)         # stricter 8 deg slope limit never passes more
    assert 'not a probability' in ' '.join(c['limitations'])
