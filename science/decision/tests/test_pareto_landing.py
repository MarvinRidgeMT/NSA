"""Pareto front and landing-search helpers; consistency of the stored blocks in decision6d.json."""
import json

import numpy as np
import pytest

from science.decision import build as B
from science.decision import landing as LD
from science.decision import questions as Q
from science.decision.pareto import AXES, pareto_front


def test_pareto_front_by_hand():
    pts = np.array([[1, 1], [2, 0], [0, 2], [0.5, 0.5], [2, 0]], float)     # max, max
    assert pareto_front(pts, ['max', 'max']).tolist() == [True, True, True, False, True]
    # flipping a sense flips which points survive
    assert pareto_front(pts, ['max', 'min']).tolist() == [False, True, False, False, True]


def test_pareto_single_point_and_identical_points():
    assert pareto_front(np.array([[3.0, 4.0]]), ['max', 'min']).tolist() == [True]
    assert pareto_front(np.ones((3, 2)), ['max', 'max']).all()


def test_lattice_within_radius_and_centred():
    for s in LD.SEARCHES:
        pts = LD.lattice(s['radius_m'], s['step_m'])
        assert (0, 0) in pts and len(pts) == len(set(pts))
        assert all(np.hypot(dx, dy) <= s['radius_m'] + 1e-9 for dx, dy in pts)
        assert all(abs(dx / s['step_m'] - round(dx / s['step_m'])) < 1e-9 for dx, _ in pts)
    assert len(LD.lattice(500, 50)) == 317


def test_pick_respects_separation_and_slope():
    rows = [{'dx': dx, 'dy': dy, 'dist_km': np.hypot(dx, dy) / 1000, 'slope_ok': (dx, dy) != (50, 0),
             'emulated_sun_pct': 100 - abs(dx) / 10 - abs(dy) / 7} for dx, dy in LD.lattice(500, 50)]
    p = LD.pick(rows, {'step_m': 50.0})
    assert p[0][1] == 'here' and (rows[p[0][0]]['dx'], rows[p[0][0]]['dy']) == (0, 0)
    top = [rows[i] for i, r in p if r == 'top']
    assert len(top) == LD.N_TOP and all(r['slope_ok'] for r in top)
    for a in top:
        for b in top:
            if a is not b:
                assert np.hypot(a['dx'] - b['dx'], a['dy'] - b['dy']) >= 100
    assert sum(r == 'random' for _, r in p) == LD.N_RANDOM


def _d6(site):
    return json.loads((Q.CUBES / site / B.FILE).read_text())


@pytest.mark.parametrize('site', B.SITES)
def test_stored_pareto_front_matches_stored_values(site):
    c = _d6(site)
    if 'pareto__positions' not in c['derived']:
        pytest.skip('Pareto run not in decision6d.json')
    m = c['derived']['pareto__positions']['metrics']
    keys = list(AXES)
    nom = np.stack([m[f'{k}_nominal']['values'] for k in keys], axis=1)
    worst = np.stack([m[f'{k}_min']['values'] if AXES[k]['sense'] == 'max' else m[f'{k}_max']['values'] for k in keys], axis=1)
    senses = [AXES[k]['sense'] for k in keys]
    assert pareto_front(nom, senses).tolist() == m['on_front_nominal']['values']
    assert pareto_front(worst, senses).tolist() == m['on_front_robust']['values']
    assert 'passes": true' in c['derived']['pareto__positions']['method']        # energy centre check
    # Sun / slope axes are copies of the committed cubes (centre cell, nominal map)
    pos, _ = Q.load(site, 'position_schedule.json.gz')
    centre = pos['dims'][1]['values'].index('0,0')
    sun = np.array(pos['metrics']['sun_pct']['values'], float).reshape(21, 81, -1)[0, centre].mean() * pos['metrics']['sun_pct']['scale']
    assert m['sun_12mo_nominal']['values'][centre] == pytest.approx(sun, abs=1e-4)
    saf, _ = Q.load(site, 'terrain_safety.json')
    assert m['slope_nominal']['values'][centre] == pytest.approx(saf['metrics']['landing_slope_100m']['values'][centre], abs=1e-4)


@pytest.mark.parametrize('site', B.SITES)
def test_stored_landing_blocks_consistent(site):
    c = _d6(site)
    keys = [k for k in c['derived'] if k.startswith('landing__') and k.endswith('__candidates')]
    if not keys:
        pytest.skip('landing run not in decision6d.json')
    for k in keys:
        m = c['derived'][k]['metrics']
        e, s, err = (m[x]['values'] for x in ('emulated_sun_pct', 'solver_sun_pct', 'recheck_error_pct'))
        assert np.allclose(np.array(e) - np.array(s), err, atol=1e-3)
        assert m['dx_m']['values'][0] == 0 and m['dy_m']['values'][0] == 0      # "here" is the reference
        assert all(sl <= LD.SLOPE_LIMIT for sl, top in zip(m['slope_100m_deg']['values'], m['is_top_pick']['values']) if top)
        sid = k.split('__')[1]
        r = float(sid[1:-2].replace('p', '.'))
        assert max(m['dist_km']['values']) <= r + 1e-9
        scr = c['derived'][f'landing__{sid}__screen']['metrics']
        own = np.array(m['in_this_search']['values'])
        assert scr['recheck_max_abs_pct']['values'][0] == pytest.approx(np.abs(np.array(err)[own]).max(), abs=1e-3)
        assert scr['n_rechecked']['values'][0] == own.sum()
        t = c['derived'][f'q__landing_{sid}__table']
        assert len(t['dims'][0]['values']) == 21 and len(t['dims'][1]['values']) == len(e)
        worst = np.array(t['metrics']['value']['values']).reshape(21, -1).min(axis=0)
        assert np.allclose(worst, m['solver_sun_pct_worst_T']['values'], atol=1e-4)


def test_larger_radius_never_answers_worse_than_smaller():
    for site in B.SITES:
        c = _d6(site)
        if 'q__landing_r2km__summary' not in c['derived']:
            pytest.skip('landing run not in decision6d.json')
        w = {r: c['derived'][f'q__landing_{r}__summary']['metrics']['robust_worst']['values'][0] for r in ('r0p5km', 'r2km')}
        assert w['r2km'] >= w['r0p5km'] - 1e-9, site
