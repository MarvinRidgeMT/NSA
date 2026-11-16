"""Phase 7 — "which axis matters": exact variance decomposition over the full factorial of a scenario cube.

For a metric Y stored on a full grid (every combination of the cube's axes), each axis level is given equal
weight and the functional ANOVA (Hoeffding / Sobol) decomposition is computed exactly on the grid:

    Y = f0 + sum_i f_i(x_i) + sum_{i<j} f_ij(x_i, x_j) + ...,      V = sum_u V_u,  V_u = mean(f_u^2)

with f_u obtained from the marginal means by Moebius inclusion-exclusion. Reported per axis i:

    first-order share  S_i  = V_i / V                       (spread explained by i alone)
    total share        ST_i = sum_{u contains i} V_u / V    (i alone plus every interaction it takes part in)
    Shapley share      Sh_i = sum_{u contains i} V_u / (|u| V)   (interactions split equally; sums to 1)

This is the discrete-uniform Sobol decomposition, so it is exact (no Monte Carlo) and the Shapley effects
follow in closed form because the grid axes are independent by construction (Owen 2014; Song, Nelson &
Staum 2016). The T axis holds the nominal map and 20 PGDA 78 error clones: they are SAMPLES, so every index
is the "share of spread within this scenario set", not a population variance share and not a probability.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np

CAVEAT = ('Share of spread within this scenario set: every axis level is weighted equally and the 20 terrain clones '
          'are samples (deterministic PGDA 78 error realizations), so the indices describe this grid, not the '
          'population of possible terrains. Not a probability; not a ranking of physical importance outside '
          'the ranges on the axes.')
METHOD = ('Exact functional ANOVA (Sobol / Hoeffding) on the full factorial grid of the cube, equal weight per axis '
          'level: V_u from Moebius inclusion-exclusion of marginal means; first-order S_i = V_i/V, total '
          'ST_i = sum over u containing i of V_u/V, Shapley Sh_i = sum over u containing i of V_u/(|u| V). '
          'science/cube/sensitivity.py.')


def anova(Y):
    """Exact ANOVA of an n-d array on its full grid. Returns (V_total, {axes tuple: V_u}).

    Raises ValueError on non-finite cells: a missing cell breaks the full factorial and is never filled."""
    Y = np.asarray(Y, dtype=np.float64)
    if not np.isfinite(Y).all():
        raise ValueError('non-finite cells: the full-factorial decomposition needs every cell')
    k = Y.ndim
    axes = tuple(range(k))
    # marginal mean over the complement of u, kept broadcastable
    means = {}
    for r in range(k + 1):
        for u in combinations(axes, r):
            comp = tuple(a for a in axes if a not in u)
            means[u] = Y.mean(axis=comp, keepdims=True) if comp else Y
    effects, V = {}, {}
    for r in range(1, k + 1):
        for u in combinations(axes, r):
            g = np.zeros((1,) * k)
            for rr in range(r + 1):
                for v in combinations(u, rr):
                    g = g + ((-1) ** (r - rr)) * means[v]
            effects[u] = g
            V[u] = float(np.mean(g ** 2))
    Vt = float(np.mean((Y - Y.mean()) ** 2))
    return Vt, V


def indices(Y, names):
    """First-order, total and Shapley shares per named axis, plus the interaction shares (|u| >= 2)."""
    Vt, V = anova(Y)
    k = len(names)
    out = {'variance': Vt, 'sd': float(np.sqrt(Vt)), 'mean': float(np.mean(Y)), 'axes': {}}
    if Vt <= 1e-12 * max(1.0, float(np.mean(Y)) ** 2):
        # no spread: every cell has the same value, so shares are undefined (None), never 0 %
        out['no_spread'] = True
        for n in names:
            out['axes'][n] = {'first': None, 'total': None, 'shapley': None}
        out['interactions'] = {}
        out['interaction_share'] = None
        out['closure'] = None
        return out
    out['no_spread'] = False
    for i, n in enumerate(names):
        first = V[(i,)] / Vt
        total = sum(v for u, v in V.items() if i in u) / Vt
        shap = sum(v / len(u) for u, v in V.items() if i in u) / Vt
        out['axes'][n] = {'first': first, 'total': total, 'shapley': shap}
    out['interactions'] = {'×'.join(names[a] for a in u): v / Vt for u, v in V.items() if len(u) >= 2}
    out['interaction_share'] = float(sum(out['interactions'].values()))
    out['closure'] = float(sum(V.values()) / Vt)          # == 1 to rounding: the decomposition is exact
    assert k == Y.ndim
    return out


def cube_array(cube, metric):
    """Metric of a scenario-cube-v1 dict as an n-d display-unit array (stored x scale); None -> NaN."""
    m = cube['metrics'][metric]
    shape = tuple(len(d['values']) for d in cube['dims'])
    a = np.array([np.nan if v is None else float(v) for v in m['values']], dtype=np.float64).reshape(shape)
    return a * m.get('scale', 1.0)
