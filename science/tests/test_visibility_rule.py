"""Phase 3 — visibility rule R_vis. Orderings that must hold, analytic disc fractions, and identity with the
existing (centre) numbers and with science-limits L1."""
import gzip
import json
import math
from pathlib import Path

import numpy as np
import pytest

from science import crossings as X
from science.cube.build_visibility import RULES, disc_fraction_flat, rule_flags

ROOT = Path(__file__).resolve().parents[2]
CUBES = ROOT / 'data' / 'cubes'


def _load(site, name):
    p = CUBES / site / name
    if not p.exists():
        pytest.skip(f'{p} not built')
    raw = p.read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)


def test_analytic_fractions_on_synthetic_flat_horizon():
    r = 0.27
    assert disc_fraction_flat(0.0, r) == pytest.approx(0.5, abs=1e-12)
    assert disc_fraction_flat(r, r) == pytest.approx(1.0) and disc_fraction_flat(2 * r, r) == pytest.approx(1.0)
    assert disc_fraction_flat(-r, r) == pytest.approx(0.0) and disc_fraction_flat(-5 * r, r) == pytest.approx(0.0)
    # centre r/2 above the horizon: segment below has area r^2 (acos(1/2) - (1/2) sqrt(3)/2)
    seg = math.acos(0.5) - 0.5 * math.sqrt(0.75)
    assert disc_fraction_flat(r / 2, r) == pytest.approx(1 - seg / math.pi, abs=1e-12)
    # symmetry f(m) + f(-m) = 1, and equality with the scalar bundle function
    for m in np.linspace(-0.3, 0.3, 61):
        assert disc_fraction_flat(m, r) + disc_fraction_flat(-m, r) == pytest.approx(1.0, abs=1e-12)
        assert disc_fraction_flat(m, r) == pytest.approx(X.disk_fraction_visible(m, r, 0.0), abs=1e-12)


def test_rule_flags_ordering_synthetic():
    mp = np.linspace(-1, 1, 2001); r = np.full_like(mp, 0.27)
    a, c, h, f = (rule_flags(mp, r, k) for k in RULES)
    assert np.all(a >= c) and np.all(c >= f) and np.array_equal(c, h)


@pytest.mark.parametrize('site', ['site04_roi3', 'site01_roi6'])
def test_any_ge_centre_ge_full_everywhere(site):
    c = _load(site, 'visibility_rule.json.gz')
    sizes = [len(d['values']) for d in c['dims']]
    for k in ('sun_pct', 'earth_pct', 'sun_earth_pct'):
        v = np.array(c['metrics'][k]['values']).reshape(sizes)
        assert np.all(v[:, 0] >= v[:, 1]) and np.all(v[:, 1] >= v[:, 3]), k
        assert np.array_equal(v[:, 1], v[:, 2]), 'half_disc must equal centre under the straight-line horizon'
    g = np.array(c['metrics']['sun_gap_h']['values']).reshape(sizes)
    assert np.all(g[:, 0] <= g[:, 1]) and np.all(g[:, 1] <= g[:, 3])


@pytest.mark.parametrize('site', ['site04_roi3', 'site01_roi6'])
def test_centre_rule_equals_existing_cube(site):
    """Default stays centre: the centre slice equals the centre_mast_schedule cube at the daily starts."""
    v = _load(site, 'visibility_rule.json.gz'); c = _load(site, 'centre_mast_schedule.json.gz')
    sv = [len(d['values']) for d in v['dims']]; sc = [len(d['values']) for d in c['dims']]
    for k in ('sun_pct', 'sun_earth_pct', 'earth_pct', 'sun_gap_h', 'earth_gap_h'):
        a = np.array(v['metrics'][k]['values']).reshape(sv)[:, 1]          # T, D_mast, S_daily
        b = np.array(c['metrics'][k]['values']).reshape(sc)[:, :, ::24]    # T, D_mast, S_hourly -> daily
        assert np.array_equal(a, b), k


def test_reproduces_science_limits_l1():
    p = ROOT / 'data' / 'science_limits' / 'L1_disc_visibility' / 'result.json'
    if not p.exists():
        pytest.skip('L1 not generated')
    l1 = json.loads(p.read_text())['sites']['site04_roi3']
    v = _load('site04_roi3', 'visibility_rule.json.gz')
    sv = [len(d['values']) for d in v['dims']]
    sun = np.array(v['metrics']['sun_pct']['values']).reshape(sv) * 100 / 337
    for k, name in ((0, 'any'), (1, 'centre'), (3, 'full')):
        assert round(sun[0, k, 0, 0], 3) == pytest.approx(l1['nominal'][name]['sun_pct'], abs=1e-3)
        for cid, blk in l1['clones'].items():
            t = int(''.join(ch for ch in str(cid) if ch.isdigit()))
            assert round(sun[t, k, 0, 0], 3) == pytest.approx(blk[name]['sun_pct'], abs=1e-3), (name, cid)


def test_hourly_fraction_consistent_with_rules():
    h = _load('site04_roi3', 'disc_fraction_hourly.json.gz')
    v = _load('site04_roi3', 'visibility_rule.json.gz')
    sh = [len(d['values']) for d in h['dims']]
    f = np.array(h['metrics']['sun_fraction']['values']).reshape(sh)[0, 0]      # nominal, 1 m, all hours
    assert f.min() >= 0 and f.max() <= 1000
    # window mean of the hourly fraction equals the stored disc mean (rounding to 0.001)
    mean0 = np.array(v['metrics']['sun_disc_mean']['values'])[0] / 1000
    assert f[:337].mean() / 1000 == pytest.approx(mean0, abs=1.5e-3)
