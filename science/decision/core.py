"""6D decision tools on an X x L table: robust choice, regret, minimax regret, value of information.

docs/v2/PHASE_3_DECISION_PLAN.md §1, docs/v2/6D_MODEL.md §2. Display-free, deterministic, non-probabilistic.

`m[x, l]`: X = listed members of the uncertainty set (e.g. nominal PGDA 78 map + 20 error clones), L = decision options.
Every "worst" / "max" / "mean" is over the LISTED members only. A mean over members is an unweighted mean, not an
expectation: the clones carry no weights, so no expected value of information is computed. Counts such as "k of N
members" are counts, never probabilities, and are never combined across axes or questions.

Tie rules (stated in every output):
  nominal choice  best on the nominal member; ties -> the nominal option, then the lowest index
  robust choice   best worst-case; ties -> best on the nominal member, then the nominal option, then the lowest index
  resolved choice (VoI) best worst-case over the resolved subset; ties -> the unresolved robust choice, then as above
A choice "changes" only when the new option is strictly better on the resolved subset (gain > TOL), never by tie order.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Sequence

import numpy as np

TOL = 1e-9
TIE_RULES = {
    'nominal': 'best on the nominal member; ties -> the nominal option, then the lowest index',
    'robust': 'best worst-case over the listed members; ties -> best on the nominal member, then the nominal option, then the lowest index',
    'resolved': 'best worst-case over the resolved subset; ties -> the unresolved robust choice, then as for robust',
}


class DecisionError(ValueError):
    pass


def as_table(table) -> np.ndarray:
    a = np.array([[np.nan if v is None else v for v in row] for row in table], dtype=float) \
        if not isinstance(table, np.ndarray) else np.asarray(table, dtype=float)
    if a.ndim != 2 or a.shape[0] < 1 or a.shape[1] < 1:
        raise DecisionError(f'need a non-empty X x L table, got shape {a.shape}')
    if not np.isfinite(a).all():
        raise DecisionError('table has missing or non-finite cells; fix the slice or drop those members explicitly')
    return a


def sign(sense: str) -> float:
    if sense not in ('max', 'min'):
        raise DecisionError("sense must be 'max' (higher is better) or 'min' (lower is better)")
    return 1.0 if sense == 'max' else -1.0


def _pick(score: np.ndarray, *tiebreaks) -> int:
    """Index of the max of `score` (within TOL); remaining ties broken by each tiebreak array in turn (higher wins),
    then the lowest index."""
    cand = np.flatnonzero(score >= score.max() - TOL)
    for tb in tiebreaks:
        if cand.size == 1:
            break
        v = tb[cand]
        cand = cand[v >= v.max() - TOL]
    return int(cand.min())


def _onehot(n: int, i: int | None) -> np.ndarray:
    v = np.zeros(n)
    if i is not None:
        v[i] = 1.0
    return v


def regret_matrix(a: np.ndarray, sense: str) -> np.ndarray:
    """r[x, l] = best_l' m(x, l') - m(x, l) in the measure's units, sign-corrected so r >= 0."""
    s = sign(sense)
    u = s * a
    return u.max(axis=1, keepdims=True) - u


def worst(a: np.ndarray, sense: str) -> np.ndarray:
    """Worst value over X per option, in the measure's units."""
    s = sign(sense)
    return s * (s * a).min(axis=0)


def robust_index(a: np.ndarray, sense: str, nominal_x: int = 0, nominal_l: int | None = None,
                 prefer: int | None = None) -> int:
    s = sign(sense)
    w = (s * a).min(axis=0)
    tb = [_onehot(a.shape[1], prefer)] if prefer is not None else []
    return _pick(w, *tb, s * a[nominal_x], _onehot(a.shape[1], nominal_l))


def nominal_index(a: np.ndarray, sense: str, nominal_x: int = 0, nominal_l: int | None = None) -> int:
    s = sign(sense)
    return _pick(s * a[nominal_x], _onehot(a.shape[1], nominal_l))


@dataclass
class Axis:
    """One uncertainty axis of a product-structured X (rows are row-major over the axes in order)."""
    name: str
    size: int


def _axis_index(axes: Sequence[Axis], n_rows: int) -> np.ndarray:
    """(n_rows, n_axes) array: the value index of each axis for every X row."""
    sizes = [ax.size for ax in axes]
    if int(np.prod(sizes)) != n_rows:
        raise DecisionError(f'axes {sizes} do not multiply to {n_rows} X rows')
    return np.array(list(product(*[range(n) for n in sizes])), dtype=int).reshape(n_rows, len(axes))


def value_of_information(a: np.ndarray, sense: str, robust: int, axes: Sequence[Axis] | None = None,
                         nominal_x: int = 0, nominal_l: int | None = None) -> list[dict]:
    """Non-probabilistic VoI. For each uncertainty axis A (and 'all' = every member resolved):

    for each value v of A, the robust choice over the members with A = v, L*(v) (ties -> the unresolved robust choice),
    gain(v) = worst_{A=v} m(., L*(v)) - worst_{A=v} m(., L*)  (>= 0, measure units, sign-corrected).
    Reported: k = number of values with gain > TOL (k of n values; not a probability), max gain, unweighted mean gain,
    and the per-value choices/gains.
    """
    s = sign(sense)
    nx = a.shape[0]
    axes = list(axes) if axes else [Axis('X', nx)]
    idx = _axis_index(axes, nx)
    groups: list[tuple[str, list[np.ndarray]]] = []
    for j, ax in enumerate(axes):
        groups.append((ax.name, [np.flatnonzero(idx[:, j] == v) for v in range(ax.size)]))
    if len(axes) > 1 or axes[0].name != 'all':
        groups.append(('all', [np.array([x]) for x in range(nx)]))
    out = []
    for name, subsets in groups:
        choices, gains = [], []
        for rows in subsets:
            sub = a[rows]
            nx_sub = int(np.flatnonzero(rows == nominal_x)[0]) if nominal_x in rows else 0
            c = robust_index(sub, sense, nx_sub, nominal_l, prefer=robust)
            g = float(s * (worst(sub[:, [c]], sense)[0] - worst(sub[:, [robust]], sense)[0]))
            g = max(g, 0.0)
            if g <= TOL:
                c, g = robust, 0.0
            choices.append(c); gains.append(g)
        gains_a = np.array(gains)
        out.append({'axis': name, 'n_values': len(subsets), 'k_values_choice_changes': int((gains_a > TOL).sum()),
                    'max_gain': float(gains_a.max()), 'mean_gain_unweighted': float(gains_a.mean()),
                    'choice_if_resolved': choices, 'gain_if_resolved': [float(g) for g in gains]})
    return out


def requirement_screen(a: np.ndarray, sense: str, threshold: float, order: Sequence[int] | None = None,
                       nominal_x: int = 0) -> dict:
    """For an ordered decision (e.g. mast height, cheapest first): the first option in `order` whose worst value over X
    meets `threshold` (>= for max, <= for min), and the first that meets it on the nominal member alone. A requirement is
    a filter on the measure, never optimised over."""
    s = sign(sense)
    order = list(range(a.shape[1])) if order is None else list(order)
    meets = (s * a) >= s * threshold - TOL                       # (X, L)
    all_ok = meets.all(axis=0)
    first = next((l for l in order if all_ok[l]), None)
    first_nom = next((l for l in order if meets[nominal_x, l]), None)
    return {'threshold': float(threshold), 'first_meeting_all': first, 'first_meeting_nominal': first_nom,
            'k_members_meeting': meets.sum(axis=0).astype(int).tolist(),
            'k_members_meeting_at_nominal_pick': None if first_nom is None else int(meets[:, first_nom].sum()),
            'n_members': int(a.shape[0])}


def analyse(table, sense: str = 'max', nominal_x: int = 0, nominal_l: int | None = None,
            axes: Sequence[Axis] | None = None, threshold: float | None = None,
            order: Sequence[int] | None = None) -> dict:
    """Everything the decision panels show for one X x L table."""
    a = as_table(table)
    nx, nl = a.shape
    if not 0 <= nominal_x < nx:
        raise DecisionError('nominal_x out of range')
    if nominal_l is not None and not 0 <= nominal_l < nl:
        raise DecisionError('nominal_l out of range')
    s = sign(sense)
    R = regret_matrix(a, sense)
    w = worst(a, sense)
    rob = robust_index(a, sense, nominal_x, nominal_l)
    nom = nominal_index(a, sense, nominal_x, nominal_l)
    max_reg = R.max(axis=0)
    mmr = _pick(-max_reg, s * w, s * a[nominal_x], _onehot(nl, nominal_l))
    tied = np.flatnonzero(s * w >= (s * w).max() - TOL)
    best_if_known = [robust_index(a[[x]], sense, 0, nominal_l, prefer=rob) for x in range(nx)]
    out = {
        'sense': sense, 'n_x': nx, 'n_l': nl, 'nominal_x': nominal_x, 'nominal_l': nominal_l,
        'robust_choice': rob, 'robust_worst': float(w[rob]), 'robust_tied': tied.astype(int).tolist(),
        'nominal_choice': nom, 'nominal_choice_worst': float(w[nom]), 'nominal_choice_nominal_value': float(a[nominal_x, nom]),
        'robust_equals_nominal': bool(rob == nom),
        'minimax_regret_choice': mmr, 'minimax_regret': float(max_reg[mmr]),
        'regret_of_nominal_choice': R[:, nom].tolist(),
        'max_regret_nominal_choice': float(R[:, nom].max()), 'mean_regret_nominal_choice': float(R[:, nom].mean()),
        'regret_of_robust_choice': R[:, rob].tolist(),
        'max_regret_robust_choice': float(R[:, rob].max()), 'mean_regret_robust_choice': float(R[:, rob].mean()),
        'worst_by_choice': w.tolist(), 'best_by_choice': (s * (s * a).max(axis=0)).tolist(),
        'nominal_by_choice': a[nominal_x].tolist(),
        'max_regret_by_choice': max_reg.tolist(), 'mean_regret_by_choice': R.mean(axis=0).tolist(),
        'best_if_known': best_if_known,
        'k_members_choice_changes': int((R[:, rob] > TOL).sum()),
        'voi': value_of_information(a, sense, rob, axes, nominal_x, nominal_l),
        'regret': R, 'values': a, 'tie_rules': TIE_RULES,
    }
    if threshold is not None:
        out['requirement'] = requirement_screen(a, sense, threshold, order, nominal_x)
    return out
