"""Phase 7 — sensitivity indices and position emulator. Each test can fail: known shares on synthetic
functions, exactness of the decomposition, GP/LOO identities, the committed file against a recomputation from
the committed cubes, and the emulator re-check against the full solver (skips when caches are absent)."""
import gzip
import json
from pathlib import Path

import numpy as np
import pytest

from science.cube import sensitivity as SE

ROOT = Path(__file__).resolve().parents[2]
CUBES = ROOT / 'data' / 'cubes'
SCHEMA = ROOT / 'schemas' / 'scenario-cube-v1.schema.json'
SITES = ('site04_roi3', 'site01_roi6')


def _load(site, name):
    p = CUBES / site / name
    if not p.exists():
        pytest.skip(f'{p} not built')
    raw = p.read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)


def _centred(rng, n, var):
    g = rng.normal(size=n)
    g -= g.mean()
    return g * np.sqrt(var / np.mean(g ** 2))


# ------------------------------------------------------------------ synthetic: known shares
@pytest.mark.parametrize('shares', [(0.6, 0.3, 0.1), (0.05, 0.9, 0.05), (1 / 3, 1 / 3, 1 / 3)])
def test_additive_function_recovers_known_shares(shares):
    """Y = a(x1) + b(x2) + c(x3) on an uneven 21 x 10 x 37 grid: first = total = Shapley = known share (within 2 %)."""
    rng = np.random.default_rng(7)
    a, b, c = (_centred(rng, n, v) for n, v in zip((21, 10, 37), shares))
    Y = 5.0 + a[:, None, None] + b[None, :, None] + c[None, None, :]
    r = SE.indices(Y, ['T', 'D', 'S'])
    for name, s in zip('TDS', shares):
        ax = r['axes'][name]
        for kind in ('first', 'total', 'shapley'):
            assert abs(ax[kind] - s) <= 0.02, (name, kind, ax[kind], s)
            assert ax[kind] == pytest.approx(s, abs=1e-9)          # exact on a full grid
    assert r['interaction_share'] == pytest.approx(0.0, abs=1e-12)


def test_pure_interaction_is_split_by_shapley():
    """Y = x1 * x2 + x3 with centred x: V12 = var1 var2, no first-order term for x1, x2; Shapley halves V12."""
    rng = np.random.default_rng(3)
    x1, x2, x3 = _centred(rng, 9, 1.0), _centred(rng, 8, 4.0), _centred(rng, 7, 2.0)
    Y = x1[:, None, None] * x2[None, :, None] + x3[None, None, :]
    r = SE.indices(Y, ['A', 'B', 'C'])
    V12, V3 = 1.0 * 4.0, 2.0
    V = V12 + V3
    assert r['variance'] == pytest.approx(V, rel=1e-12)
    assert r['axes']['A']['first'] == pytest.approx(0.0, abs=1e-12)
    assert r['axes']['A']['total'] == pytest.approx(V12 / V, abs=1e-12)
    assert r['axes']['A']['shapley'] == pytest.approx(V12 / V / 2, abs=1e-12)
    assert r['axes']['C']['first'] == pytest.approx(V3 / V, abs=1e-12)
    assert r['interactions']['A×B'] == pytest.approx(V12 / V, abs=1e-12)


def test_decomposition_exact_and_consistent_on_random_grid():
    rng = np.random.default_rng(11)
    Y = rng.normal(size=(5, 6, 4, 3)) ** 3
    r = SE.indices(Y, list('abcd'))
    assert r['closure'] == pytest.approx(1.0, abs=1e-12)
    assert sum(v['shapley'] for v in r['axes'].values()) == pytest.approx(1.0, abs=1e-12)
    for v in r['axes'].values():
        assert v['first'] - 1e-12 <= v['shapley'] <= v['total'] + 1e-12


def test_constant_axis_has_zero_share_and_missing_cell_refuses():
    rng = np.random.default_rng(5)
    Y = np.repeat(rng.normal(size=(6, 1, 5)), 4, axis=1)
    r = SE.indices(Y, ['T', 'D', 'S'])
    assert r['axes']['D']['total'] == pytest.approx(0.0, abs=1e-12)
    Y[0, 0, 0] = np.nan
    with pytest.raises(ValueError):
        SE.anova(Y)
    flat = SE.indices(np.full((3, 4), 100.0), ['T', 'D'])
    assert flat['no_spread'] and flat['axes']['T']['shapley'] is None


# ------------------------------------------------------------------ emulator pieces (no cache needed)
def test_gp_interpolates_and_loo_equals_refit():
    from science.cube.emulator import MultiGP
    rng = np.random.default_rng(2)
    X = np.array([(dx, dy) for dx in range(-100, 101, 25) for dy in range(-100, 101, 25)], float)
    Y = np.stack([np.sin(X[:, 0] / 40) + np.cos(X[:, 1] / 55), X[:, 0] * X[:, 1] / 1e4], axis=1) + 0.01 * rng.normal(size=(81, 2))
    g = MultiGP(X, Y, 40.0, 1e-8)
    assert np.allclose(g.predict(X), Y, atol=1e-5)
    loo = g.loo()
    for i in (0, 17, 40, 80):
        keep = np.arange(81) != i
        gi = MultiGP(X[keep], Y[keep], 40.0, 1e-8)
        # closed-form LOO uses the full-data constant mean; refit with that same mean to compare like with like
        gi.mu = g.mu; gi.alpha = gi.Kinv @ (Y[keep] - g.mu)
        assert np.allclose(gi.predict(X[i:i + 1])[0], loo[i], atol=1e-6)


def test_counts_daily_matches_cube_window_helper():
    from science.cube import compute as C, ephem_year as E
    from science.cube.emulator import counts_daily, DAILY
    rng = np.random.default_rng(9)
    f = rng.random((3, E.N_STARTS + E.WINDOW_H)) > 0.4
    for row in f:
        w = C.window_metrics(row, row, E.N_STARTS, E.WINDOW_H, DAILY)
        assert np.array_equal(counts_daily(row[None, :])[0], w['sun_n'])


def test_candidates_are_off_grid():
    from science.cube import compute as C
    from science.cube.emulator import candidate_lattice
    cands = candidate_lattice()
    assert len(cands) == 17 * 17 - 81
    assert not set(cands) & set(C.OFFSETS)
    assert all(-100 <= dx <= 100 and -100 <= dy <= 100 for dx, dy in cands)


# ------------------------------------------------------------------ committed file
@pytest.mark.parametrize('site', SITES)
def test_sensitivity_file_schema_and_index(site):
    jsonschema = pytest.importorskip('jsonschema')
    c = _load(site, 'sensitivity.json')
    jsonschema.validate(c, json.loads(SCHEMA.read_text()))
    assert c['label'] == 'SOURCE-BASED · UNVALIDATED'
    assert 'not a probability' in ' '.join(c['limitations'])
    assert 'share of spread within this scenario set' in c['derived']['sobol__centre__sun_pct']['caveat'].lower()
    idx = json.loads((CUBES / site / 'index.json').read_text())
    e = next(x for x in idx['cubes'] if x['file'] == 'sensitivity.json')
    from science.limits.common import sha256_file
    assert e['sha256'] == sha256_file(CUBES / site / 'sensitivity.json')
    if not (CUBES / site / 'energy.json.gz').exists():
        assert c['fixed']['energy_margin'] == 'not in bundle'


@pytest.mark.parametrize('site', SITES)
def test_sensitivity_file_equals_recomputation_from_cubes(site):
    from science.cube.build_sensitivity import METRICS, SOURCES, decompose
    c = _load(site, 'sensitivity.json')
    for src, file, demo, _t in SOURCES:
        cube = _load(site, file)
        for metric, _l in METRICS:
            names, r = decompose(cube, metric, demo)
            blk = c['derived'][f'sobol__{src}__{metric}']['metrics']
            assert c['fixed'][f'axes__{src}'] == ','.join(names)
            assert blk['no_spread']['values'][0] is r['no_spread']
            if r['no_spread']:                                  # every cell equal: shares are null, never 0 %
                assert all(blk[f'{k}_pct__{a}']['values'][0] is None for a in names for k in ('first', 'total', 'shapley'))
                continue
            for a in names:
                for kind in ('first', 'total', 'shapley'):
                    assert blk[f'{kind}_pct__{a}']['values'][0] == pytest.approx(100 * r['axes'][a][kind], abs=1e-5)
            assert sum(blk[f'shapley_pct__{a}']['values'][0] for a in names) == pytest.approx(100, abs=1e-3)
            assert blk['closure']['values'][0] == pytest.approx(1.0, abs=1e-9)


def test_site04_baseline_cell_feeds_the_decomposition():
    """The decomposed array is the committed cube: Site04 RoI 3 nominal / 1 m / demo start = 94.36 % / 72.11 % / 19 h."""
    c = _load('site04_roi3', 'centre_mast_schedule.json.gz')
    assert SE.cube_array(c, 'sun_pct')[0, 0, 0] == pytest.approx(94.362, abs=1e-3)
    assert SE.cube_array(c, 'sun_earth_pct')[0, 0, 0] == pytest.approx(72.107, abs=1e-3)
    assert SE.cube_array(c, 'sun_gap_h')[0, 0, 0] == 19
    clones = SE.cube_array(c, 'sun_pct')[1:, 0, 0]
    assert clones.min() == pytest.approx(87.54, abs=0.01) and clones.max() == pytest.approx(97.33, abs=0.01)


@pytest.mark.parametrize('site', SITES)
def test_emulator_recheck_passes(site):
    """Committed re-check meets the target (rho >= 0.99), top picks beat the random checks, and every
    candidate is off the 81-cell grid."""
    from science.cube import compute as C
    c = _load(site, 'sensitivity.json')
    k = c['derived']['emulator_check']['metrics']
    assert k['spearman_objective']['values'][0] >= 0.99
    assert k['passes_target']['values'][0] is True
    assert k['spearman_cell_sun_pct']['values'][0] >= 0.99
    full = c['metrics']['full_sun_12mo']['values']; top = c['metrics']['is_top_pick']['values']
    med_random = float(np.median([f for f, t in zip(full, top) if not t]))
    assert min(f for f, t in zip(full, top) if t) > med_random
    offs = {tuple(float(x) for x in v.split(',')) for v in c['dims'][0]['values']}
    assert not offs & {(float(a), float(b)) for a, b in C.OFFSETS}


@pytest.mark.parametrize('site', SITES)
def test_emulator_recheck_reproduces_from_cache(site):
    """Re-run the re-check from the cached skylines; it must reproduce the committed numbers."""
    from science.cube import compute as C, emulator as EM
    c = _load(site, 'sensitivity.json')
    need = [C.SKY / f'{C.sky_key(site, "nominal", 1.0, *EM._norm(*map(float, v.split(","))))}.json' for v in c['dims'][0]['values']]
    if not all(p.exists() for p in need) or not (EM.WORK / f'{site}_proposal.json').exists():
        pytest.skip('skyline / emulator caches absent')
    rc = EM.recheck(site)
    assert [round(r['full_sun_12mo'], 4) for r in rc['rows']] == c['metrics']['full_sun_12mo']['values']
    assert [round(r['emulated_sun_12mo'], 4) for r in rc['rows']] == pytest.approx(c['metrics']['emulated_sun_12mo']['values'], abs=1e-6)
    assert rc['objective_sun_12mo']['spearman'] == pytest.approx(c['derived']['emulator_check']['metrics']['spearman_objective']['values'][0], abs=1e-6)
