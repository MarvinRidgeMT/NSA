"""Scenario cube v2 (6D roles, docs/v2/6D_MODEL.md). Every test can fail:
- every committed v1 cube migrates with every value identical and the exact inverse restores it byte for byte;
- the v2 schema accepts the migrated cubes and rejects missing/bad roles;
- the role table in Python equals the one embedded in the schema;
- decision helpers: known robust optimum on a synthetic cube, regret = 0 when X has one member, hand-checked minimax regret.
"""
import copy
import json
from pathlib import Path

import pytest

from science.cube import v2

ROOT = Path(__file__).resolve().parents[2]
CUBES = ROOT / 'data' / 'cubes'
SCHEMA_V1 = json.loads((ROOT / 'schemas' / 'scenario-cube-v1.schema.json').read_text())
SCHEMA_V2 = json.loads((ROOT / 'schemas' / 'scenario-cube-v2.schema.json').read_text())

FILES = [p for p in v2.iter_cube_files(CUBES)]
CUBE_FILES = [p for p in FILES if v2.read_json_maybe_gzip(p)[0].get('schema') == v2.V1]


def _id(p):
    return f'{p.parent.name}/{p.name}'


def test_corpus_is_the_committed_5d_cubes():
    # 14 scenario-cube-v1 files per site (index.json and decision_summary.json are other schemas)
    assert len(CUBE_FILES) == 28, [_id(p) for p in CUBE_FILES]


@pytest.fixture(scope='module', params=CUBE_FILES, ids=_id)
def pair(request):
    c, sha = v2.read_json_maybe_gzip(request.param)
    return c, v2.migrate_v1_to_v2(c, source_sha256=sha), sha


def test_round_trip_identical(pair):
    c, m, _ = pair
    assert v2.to_v1(m) == c
    # and through JSON text, as a file would be stored
    assert v2.to_v1(json.loads(json.dumps(m))) == c


def test_every_value_identical(pair):
    c, m, _ = pair
    for k in c:
        if k == 'schema':
            continue
        if k == 'dims':
            continue
        if k == 'derived':
            for bk, b in c['derived'].items():
                assert m['derived'][bk]['metrics'] == b['metrics'], bk
                assert m['derived'][bk]['method'] == b['method']
            continue
        assert m[k] == c[k], k
    for d1, d2 in zip(c['dims'], m['dims'], strict=True):
        assert {k: v for k, v in d2.items() if k not in ('role', 'role_note')} == d1
        assert list(d2)[: list(d2).index('role')] == list(d1)[: list(d1).index('kind') + 1], 'role sits right after kind'


def test_every_dim_has_a_role_from_the_rule(pair):
    _, m, _ = pair
    dims = list(m['dims']) + [d for b in (m.get('derived') or {}).values() for d in b['dims'] if isinstance(d, dict)]
    for d in dims:
        assert d['role'] in v2.ROLES
        role, note = v2.role_for(d['kind'], d['name'])
        assert d['role'] == role
        assert d.get('role_note') == note


def test_migration_metadata(pair):
    c, m, sha = pair
    assert m['schema'] == 'scenario-cube-v2' and m['world'] == 'moon'
    assert m['migration'] == {'from_schema': 'scenario-cube-v1', 'tool': 'science/cube/v2.py migrate_v1_to_v2',
                              'role_rule': v2.ROLE_RULE, 'source_sha256': sha}


def test_migrated_cube_validates_against_v2(pair):
    _, m, _ = pair
    v2.validate_v2(m)


def test_committed_cube_still_validates_against_v1(pair):
    jsonschema = pytest.importorskip('jsonschema')
    c, _, _ = pair
    jsonschema.validate(v2._skeleton(c, 64), SCHEMA_V1)


def test_migration_deterministic_and_idempotent(pair):
    c, m, sha = pair
    again = v2.migrate_v1_to_v2(copy.deepcopy(c), source_sha256=sha)
    assert json.dumps(again, sort_keys=False) == json.dumps(m, sort_keys=False)
    assert v2.migrate_v1_to_v2(m) == m


def test_full_schema_validation_on_small_cubes():
    jsonschema = pytest.importorskip('jsonschema')
    small = [p for p in CUBE_FILES if p.stat().st_size < 20_000]
    assert small
    for p in small:
        v2.validate_v2(v2.load_any(p), full=True)
        jsonschema.validate(v2.read_json_maybe_gzip(p)[0], SCHEMA_V1)


# ------------------------------------------------------------------ schema rules
def _tiny():
    return v2.migrate_v1_to_v2({
        'schema': 'scenario-cube-v1', 'cube_id': 'x', 'site_id': 'x', 'label': 'DEMO', 'generated_utc': 'x',
        'dims': [{'name': 'T', 'kind': 'uncertainty_terrain', 'values': ['a', 'b'], 'units': '', 'label': 'T'},
                 {'name': 'D_mast', 'kind': 'design', 'values': [1, 2, 3], 'units': 'm', 'label': 'mast'}],
        'metrics': {'v': {'units': '%', 'label': 'v', 'dtype': 'int32', 'values': [1, 2, 3, 4, 5, 6], 'provenance': 'synthetic'}},
        'missing': {'encoding': 'sparse-flat-index', 'by_metric': {}},
        'provenance': {'inputs': [], 'command': 'x', 'code_commit': 'x'}})


def test_schema_rejects_missing_or_bad_role_and_v1_constant():
    jsonschema = pytest.importorskip('jsonschema')
    ok = _tiny()
    jsonschema.validate(ok, SCHEMA_V2)
    no_role = copy.deepcopy(ok)
    del no_role['dims'][0]['role']
    bad_role = copy.deepcopy(ok)
    bad_role['dims'][1]['role'] = 'world'
    v1_const = copy.deepcopy(ok)
    v1_const['schema'] = 'scenario-cube-v1'
    inline = copy.deepcopy(ok)
    inline['derived'] = {'k': {'dims': [{'name': 'R', 'kind': 'requirement', 'values': [0], 'units': '', 'label': 'R'}],
                               'metrics': {}, 'method': 'x'}}
    for bad in (no_role, bad_role, v1_const, inline):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, SCHEMA_V2)
    # v1 schema rejects a v2 cube (roles are not v1)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(ok, SCHEMA_V1)


def test_role_table_matches_schema():
    assert SCHEMA_V2['x-role-by-kind'] == v2.ROLE_BY_KIND
    assert {(o['kind'], o['name']): (o['role'], o['reason']) for o in SCHEMA_V2['x-role-overrides']} == v2.ROLE_OVERRIDES
    assert set(SCHEMA_V2['x-role-by-kind']) == set(SCHEMA_V1['$defs']['dim']['properties']['kind']['enum'])
    assert SCHEMA_V2['$defs']['dim']['properties']['kind'] == SCHEMA_V1['$defs']['dim']['properties']['kind']
    assert SCHEMA_V2['$defs']['role']['enum'] == list(v2.ROLES)


def test_unknown_kind_and_schema_refused():
    with pytest.raises(v2.CubeV2Error):
        v2.role_for('world', 'W')
    with pytest.raises(v2.CubeV2Error):
        v2.migrate_v1_to_v2({'schema': 'scenario-cube-v0'})
    with pytest.raises(v2.CubeV2Error):
        v2.to_v1({'schema': 'polaris-decision-summary-v1'})


def test_validate_catches_wrong_sizes():
    bad = _tiny()
    bad['metrics']['v']['values'].pop()
    with pytest.raises(v2.CubeV2Error):
        v2.validate_v2(bad)


# ------------------------------------------------------------------ decision helpers
def _synthetic_xl():
    """X(3 members, nominal first) x L(3 choices) Sun+Earth %. Nominal favours L0; L1 is best in the worst case.

        L0  L1  L2
    x0  90  80  60     nominal: pick L0
    x1  40  75  70     worst row for L0
    x2  85  78  65
    worst: L0 40, L1 75, L2 60 -> robust optimum L1 (75)
    """
    return [[90, 80, 60], [40, 75, 70], [85, 78, 65]]


def test_known_robust_optimum_differs_from_nominal_pick():
    t = _synthetic_xl()
    assert v2.nominal_choice(t) == 0
    r = v2.robust_choice(t)
    assert r['choice'] == 1 and r['worst_by_choice'] == [40, 75, 60] and r['worst_at_choice'] == 75
    assert v2.regret_table(t, 0) == [0, 35, 0]
    assert v2.regret_table(t, 1) == [10, 0, 7]
    mm = v2.minimax_regret_choice(t)
    assert mm['max_regret_by_choice'] == [35, 10, 30] and mm['choice'] == 1
    voi = v2.choice_changes_if_known(t, reference_choice=0)
    assert voi['best_if_known'] == [0, 1, 0] and voi['changes_at'] == [1] and voi['regret_avoided'] == [35]


def test_lower_is_better_sense():
    gap_h = [[10, 20], [100, 30]]  # longest Sun gap: lower is better
    assert v2.nominal_choice(gap_h, sense='min') == 0
    assert v2.robust_choice(gap_h, sense='min')['choice'] == 1
    assert v2.regret_table(gap_h, 0, sense='min') == [0, 70]


@pytest.mark.parametrize('row', [[3.0, 9.0, 1.0], [5, 5, 5], [0.0]])
def test_regret_zero_when_X_has_one_member(row):
    t = [row]
    c = v2.nominal_choice(t)
    assert v2.regret_table(t, c) == [0]
    assert v2.minimax_regret_choice(t)['max_regret_at_choice'] == 0
    assert v2.robust_choice(t)['choice'] == c
    assert v2.choice_changes_if_known(t, c)['changes_at'] == []


def test_missing_cells_refused():
    with pytest.raises(v2.CubeV2Error):
        v2.robust_choice([[1, None]])


def _role_cube():
    """T(2) x D_mast(3) x R(2) x S(2); value = 100 T + 10 D + 5 R + S (hand-checkable)."""
    vals = [100 * t + 10 * d + 5 * r + s for t in range(2) for d in range(3) for r in range(2) for s in range(2)]
    return v2.migrate_v1_to_v2({
        'schema': 'scenario-cube-v1', 'cube_id': 'x', 'site_id': 'x', 'label': 'DEMO', 'generated_utc': 'x',
        'dims': [{'name': 'T', 'kind': 'uncertainty_terrain', 'values': ['nominal', 'c1'], 'units': '', 'label': 'T'},
                 {'name': 'D_mast', 'kind': 'design', 'values': [1, 2, 3], 'units': 'm', 'label': 'mast'},
                 {'name': 'R', 'kind': 'requirement', 'values': ['team', 'strict'], 'units': '', 'label': 'R'},
                 {'name': 'S', 'kind': 'schedule', 'values': [0, 1], 'units': 'h', 'label': 'S'}],
        'metrics': {'v': {'units': '%', 'label': 'v', 'dtype': 'int32', 'values': vals, 'provenance': 's', 'scale': 0.5}},
        'missing': {'encoding': 'sparse-flat-index', 'by_metric': {}},
        'provenance': {'inputs': [], 'command': 'x', 'code_commit': 'x'}})


def test_decision_table_uses_roles():
    c = _role_cube()
    t = v2.decision_table(c, 'v', {'R': 1, 'S': 0})
    assert t['x_dims'] == ['T'] and t['l_dims'] == ['D_mast']
    assert t['values'] == [[2.5, 7.5, 12.5], [52.5, 57.5, 62.5]]
    assert v2.robust_choice(t['values'])['choice'] == 2
    both = v2.decision_table(c, 'v', {'R': 0})  # S is a decision too: L = D_mast x S
    assert both['l_dims'] == ['D_mast', 'S'] and len(both['l_labels']) == 6
    with pytest.raises(v2.CubeV2Error, match='requirement'):
        v2.decision_table(c, 'v', {'S': 0})  # R left free: a requirement is a filter, not an axis to optimise


def test_decision_table_on_committed_cube_matches_cells():
    p = CUBES / 'site04_roi3' / 'centre_mast_schedule.json.gz'
    c = v2.load_any(p)
    t = v2.decision_table(c, 'sun_earth_pct', {'S': 0})
    assert t['x_dims'] == ['T'] and t['l_dims'] == ['D_mast'] and len(t['values']) == 21
    m = c['metrics']['sun_earth_pct']
    # nominal, 1 m, 2026-11-14 00:00: the documented baseline 72.107 % (SCENARIO_CUBE_CONTRACT §6)
    assert t['values'][0][0] == pytest.approx(72.107, abs=5e-3)
    assert t['values'][7][4] == m['values'][(7 * 10 + 4) * 8761 + 0] * m['scale']


def test_cli_check_and_out_guard(tmp_path, capsys):
    small = tmp_path / 'cubes' / 'site04_roi3'
    small.mkdir(parents=True)
    (small / 'products.json').write_bytes((CUBES / 'site04_roi3' / 'products.json').read_bytes())
    out = tmp_path / 'v2'
    assert v2.main([str(tmp_path / 'cubes'), '--out', str(out)]) == 0
    written = json.loads((out / 'site04_roi3' / 'products.json').read_text())
    assert written['schema'] == 'scenario-cube-v2' and v2.to_v1(written) == json.loads((small / 'products.json').read_text())
    with pytest.raises(SystemExit):
        v2.main([str(tmp_path / 'cubes'), '--out', str(CUBES / 'v2')])
