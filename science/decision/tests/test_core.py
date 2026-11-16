"""Decision core on synthetic tables with hand-computed answers (docs/v2/PHASE_3_DECISION_PLAN.md §1)."""
import numpy as np
import pytest

from science.cube import v2
from science.decision.core import Axis, DecisionError, analyse, requirement_screen

# rows = X members (x0 nominal), columns = L options. Robust optimum planted at L1, nominal optimum at L0.
T3 = [[10, 6, 3],
      [1, 5, 7],
      [1, 4, 2]]


def test_planted_robust_optimum():
    r = analyse(T3, 'max')
    assert r['robust_choice'] == 1 and r['robust_worst'] == 4
    assert r['nominal_choice'] == 0 and not r['robust_equals_nominal']
    assert r['worst_by_choice'] == [1, 4, 2]


def test_regret_of_nominal_choice_by_hand():
    r = analyse(T3, 'max')
    assert r['regret_of_nominal_choice'] == [0, 6, 3]
    assert r['max_regret_nominal_choice'] == 6 and r['mean_regret_nominal_choice'] == 3
    assert r['regret_of_robust_choice'] == [4, 2, 0]
    assert r['minimax_regret_choice'] == 1 and r['minimax_regret'] == 4
    assert r['max_regret_by_choice'] == [6, 4, 7]
    assert (r['regret'] >= 0).all()


def test_perfect_information_by_hand():
    r = analyse(T3, 'max')
    allv = next(v for v in r['voi'] if v['axis'] == 'all')
    assert allv['choice_if_resolved'] == [0, 2, 1]
    assert allv['gain_if_resolved'] == [4, 2, 0]
    assert allv['k_values_choice_changes'] == 2 and allv['max_gain'] == 4 and allv['mean_gain_unweighted'] == 2
    assert r['k_members_choice_changes'] == 2
    assert r['best_if_known'] == [0, 2, 1]


def test_one_member_means_zero_regret_and_zero_voi():
    for row in ([3, 9, 9, 1], [5.0], [2, 2]):
        for sense in ('max', 'min'):
            r = analyse([row], sense)
            assert r['max_regret_nominal_choice'] == 0 and r['max_regret_robust_choice'] == 0
            assert r['mean_regret_nominal_choice'] == 0
            assert r['robust_choice'] == r['nominal_choice']
            assert all(v['max_gain'] == 0 and v['k_values_choice_changes'] == 0 for v in r['voi'])


def test_min_sense_mirrors_max():
    a = np.array(T3, float)
    rmax, rmin = analyse(a, 'max'), analyse(-a, 'min')
    for k in ('robust_choice', 'nominal_choice', 'minimax_regret_choice', 'best_if_known'):
        assert rmax[k] == rmin[k]
    assert rmin['robust_worst'] == -4
    assert rmax['regret_of_nominal_choice'] == rmin['regret_of_nominal_choice']


def test_two_axis_voi_resolving_one_axis_changes_choice():
    # X = A(2) x B(2), row-major: a0b0, a0b1, a1b0, a1b1. L0 is great when a = 0, bad when a = 1; L1 is steady.
    t = [[9, 5], [8, 5], [1, 5], [2, 5]]
    r = analyse(t, 'max', axes=[Axis('A', 2), Axis('B', 2)])
    assert r['robust_choice'] == 1
    voi = {v['axis']: v for v in r['voi']}
    assert voi['A']['choice_if_resolved'] == [0, 1] and voi['A']['gain_if_resolved'] == [3, 0]
    assert voi['A']['k_values_choice_changes'] == 1 and voi['A']['n_values'] == 2
    assert voi['B']['k_values_choice_changes'] == 0 and voi['B']['max_gain'] == 0
    assert voi['all']['max_gain'] == 4  # a0b0: 9 - 5


def test_ties_do_not_count_as_changes_and_prefer_nominal_option():
    t = [[5, 5, 5], [5, 5, 5]]
    r = analyse(t, 'max', nominal_l=2)
    assert r['robust_choice'] == 2 and r['nominal_choice'] == 2 and r['robust_tied'] == [0, 1, 2]
    assert r['k_members_choice_changes'] == 0
    r0 = analyse(t, 'max')
    assert r0['robust_choice'] == 0


def test_robust_tie_broken_by_nominal_member():
    t = [[3, 7], [2, 2]]          # worst = [2, 2] tie; L1 better on the nominal member
    assert analyse(t, 'max')['robust_choice'] == 1


def test_agrees_with_cube_v2_helpers_without_ties():
    rng = np.random.default_rng(7)
    for _ in range(50):
        a = rng.normal(size=(rng.integers(1, 8), rng.integers(1, 9)))
        for sense in ('max', 'min'):
            r = analyse(a, sense)
            assert r['robust_choice'] == v2.robust_choice(a.tolist(), sense)['choice']
            assert r['minimax_regret_choice'] == v2.minimax_regret_choice(a.tolist(), sense)['choice']
            assert np.allclose(r['regret_of_nominal_choice'],
                               v2.regret_table(a.tolist(), v2.nominal_choice(a.tolist(), 0, sense), sense))


def test_requirement_screen_ordered_lever():
    # mast-like: value rises with the option; member 2 is the hardest
    t = [[40, 50, 60, 70], [45, 55, 65, 75], [30, 38, 41, 60]]
    s = requirement_screen(np.array(t, float), 'max', 40.0)
    assert s['first_meeting_nominal'] == 0 and s['first_meeting_all'] == 2
    assert s['k_members_meeting'] == [2, 2, 3, 3] and s['k_members_meeting_at_nominal_pick'] == 2
    g = requirement_screen(np.array(t, float), 'min', 39.0)
    assert g['first_meeting_all'] is None and g['first_meeting_nominal'] is None


def test_refuses_missing_and_bad_input():
    with pytest.raises(DecisionError):
        analyse([[1, None]])
    with pytest.raises(DecisionError):
        analyse([[1, 2]], 'best')
    with pytest.raises(DecisionError):
        analyse([[1, 2], [3, 4]], axes=[Axis('A', 3)])
    with pytest.raises(DecisionError):
        analyse([[]])
