"""decision6d.json: schema, traceability to the source cubes, reproducibility, role rules on a synthetic cube."""
import copy
import json

import numpy as np
import pytest

from science.cube import v2
from science.decision import build as B
from science.decision import questions as Q
from science.decision.core import analyse

SITES = B.SITES


def _cube(site):
    return json.loads((Q.CUBES / site / B.FILE).read_text())


def _qmeta(c):
    return json.loads(c['dims'][0]['note'])


@pytest.mark.parametrize('site', SITES)
def test_schema_v2_valid(site):
    c = _cube(site)
    assert c['schema'] == 'scenario-cube-v2' and c['world'] == 'moon'
    v2.validate_v2(c, full=True)
    assert c['dims'][0]['role'] == 'context'
    for k, b in c['derived'].items():
        for d in b['dims']:
            assert isinstance(d, dict) and d['role'] in v2.ROLES, k


@pytest.mark.parametrize('site', SITES)
def test_every_table_value_traces_to_its_source_cell(site):
    c = _cube(site)
    for m in _qmeta(c):
        if m['kind'] != 'cube':
            continue
        src, _ = Q.load(site, m['source_file'])
        sm = src['metrics'][m['metric']]
        blk = c['derived'][f'q__{m["id"]}__table']['metrics']
        n = 0
        for v, i in zip(blk['value']['values'], blk['source_flat_index']['values']):
            if i is None:
                continue
            assert v == pytest.approx(sm['values'][i] * sm.get('scale', 1), abs=1e-6)
            n += 1
        assert n > 0 or m['reduce'], m['id']


@pytest.mark.parametrize('site', SITES)
def test_source_cubes_unchanged_since_build(site):
    """decision6d records the SHA-256 of every input; the committed cube files must still match (never rewritten)."""
    c = _cube(site)
    for inp in c['provenance']['inputs']:
        if inp['path'].startswith('data/cubes/'):
            assert Q.sha256_of(Q.ROOT / inp['path']) == inp['sha256'], inp['path']


@pytest.mark.parametrize('site', SITES)
def test_question_blocks_reproduce(site):
    c = _cube(site)
    fresh = B.build(site)
    for k, b in c['derived'].items():
        if k.startswith('q__') and not k.startswith('q__landing'):
            assert fresh['derived'][k]['metrics'] == b['metrics'], k
    n_cube = sum(1 for m in _qmeta(c) if m['kind'] == 'cube')
    assert c['metrics']['robust_choice_index']['values'][:n_cube] == fresh['metrics']['robust_choice_index']['values'][:n_cube]


@pytest.mark.parametrize('site', SITES)
def test_summary_consistent_with_tables(site):
    c = _cube(site)
    for qi, m in enumerate(_qmeta(c)):
        t = c['derived'][f'q__{m["id"]}__table']
        nx, nl = len(t['dims'][0]['values']), len(t['dims'][1]['values'])
        a = np.array(t['metrics']['value']['values'], float).reshape(nx, nl)
        r = analyse(a, m['sense'], t['dims'][0].get('nominal_index', 0), t['dims'][1].get('nominal_index'))
        assert c['metrics']['robust_choice_index']['values'][qi] == r['robust_choice'], m['id']
        assert c['metrics']['nominal_choice_index']['values'][qi] == r['nominal_choice'], m['id']
        s = c['derived'][f'q__{m["id"]}__summary']['metrics']
        assert s['max_regret_nominal_choice']['values'][0] == pytest.approx(r['max_regret_nominal_choice'], abs=1e-5)


def test_no_probability_words():
    for site in SITES:
        txt = (Q.CUBES / site / B.FILE).read_text().lower()
        assert 'probability of success' not in txt
        assert 'not a probability' in txt


# ------------------------------------------------------------------ synthetic cube: role rules + planted optimum
def _synthetic():
    T = {'name': 'T', 'kind': 'uncertainty_terrain', 'role': 'uncertainty', 'values': ['nominal', 'c1', 'c2'],
         'units': '', 'label': 'map', 'nominal_index': 0}
    D = {'name': 'D_mast', 'kind': 'design', 'role': 'decision', 'values': [1.0, 2.0, 3.0], 'units': 'm', 'label': 'mast',
         'nominal_index': 0}
    R = {'name': 'R_x', 'kind': 'requirement', 'role': 'requirement', 'values': ['a', 'b'], 'units': '', 'label': 'req'}
    # value[T, D, R]; for R = 'a' the table is the planted one from test_core (robust D index 1, nominal-map choice 0)
    planted = np.array([[10, 6, 3], [1, 5, 7], [1, 4, 2]], float)
    vals = np.stack([planted, planted * 0 + 1], axis=-1)
    return {'schema': 'scenario-cube-v2', 'cube_id': 'syn', 'site_id': 'syn', 'world': 'moon', 'label': 'TEST',
            'generated_utc': 'x', 'dims': [T, D, R],
            'metrics': {'m': {'units': '%', 'label': 'measure', 'dtype': 'float64', 'values': vals.reshape(-1).tolist(),
                              'provenance': 'synthetic'}},
            'missing': {'encoding': 'sparse-flat-index', 'by_metric': {}},
            'provenance': {'inputs': [], 'command': '', 'code_commit': ''}}


def test_synthetic_cube_known_robust_optimum():
    c = _synthetic()
    v2.validate_v2(c)
    q = Q.Question('syn', 'x', 'm', 'max', ['T'], ['D_mast'], 'syn', fix={'R_x': 'a'})
    tb = Q.table(c, q)
    r = analyse(tb['values'], 'max', tb['nominal_x'], tb['nominal_l'])
    assert r['robust_choice'] == 1 and r['nominal_choice'] == 0
    assert r['max_regret_nominal_choice'] == 6 and r['mean_regret_nominal_choice'] == 3
    assert tb['l_labels'] == ['1 m', '2 m', '3 m'] and tb['x_labels'] == ['nominal', 'c1', 'c2']
    # agrees with the generic role-driven table of science/cube/v2.py
    dt_ = v2.decision_table(c, 'm', {'R_x': 0})
    assert np.allclose(dt_['values'], tb['values'])


def test_synthetic_cube_one_member_zero_regret():
    c = _synthetic()
    q = Q.Question('syn', 'x', 'm', 'max', ['T'], ['D_mast'], 'syn', fix={'R_x': 'a', 'T': 'c1'})
    q.x = []
    tb = Q.table(c, q)
    assert tb['values'].shape == (1, 3)
    r = analyse(tb['values'], 'max')
    assert r['max_regret_nominal_choice'] == 0 and r['voi'][0]['max_gain'] == 0


def test_requirement_axis_must_be_fixed_and_roles_enforced():
    c = _synthetic()
    with pytest.raises(v2.CubeV2Error):
        Q.table(c, Q.Question('syn', 'x', 'm', 'max', ['T'], ['D_mast'], 'syn'))
    with pytest.raises(v2.CubeV2Error):
        Q.table(c, Q.Question('syn', 'x', 'm', 'max', ['D_mast'], ['T'], 'syn', fix={'R_x': 0}))
    with pytest.raises(v2.CubeV2Error):
        Q.table(c, Q.Question('syn', 'x', 'm', 'max', ['T'], ['D_mast'], 'syn', reduce={'R_x': 'mean'}))
