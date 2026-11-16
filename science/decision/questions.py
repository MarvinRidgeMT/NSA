"""Decision questions over the committed cubes: X x L tables cut by axis role (docs/v2/PHASE_3_DECISION_PLAN.md §2).

A question names a source cube, a measure and its sense, the uncertainty axes (X), the decision axes (L), and how every
other axis is held: `fix` (index; required for requirement and context axes, allowed for a decision axis that the
question does not optimise) or `reduce` (an unweighted mean over a decision axis, used only to define a 12-month
measure as the mean of the 14-day window measure over daily start dates). Values are read, scaled by the stored
`scale`, and never otherwise changed. Each cell keeps its source flat index for traceability.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np

from ..cube import v2

ROOT = Path(__file__).resolve().parents[2]
CUBES = ROOT / 'data' / 'cubes'
GEOMETRY = 'SOURCE-BASED · UNVALIDATED'
ENGINEERING = 'ENGINEERING ASSUMPTION'


@dataclass
class Question:
    id: str
    file: str
    metric: str
    sense: str
    x: list[str]
    l: list[str]
    text: str
    label: str = GEOMETRY
    fix: dict[str, Any] = field(default_factory=dict)       # dim -> index or value
    reduce: dict[str, str] = field(default_factory=dict)    # dim -> 'mean'
    threshold: float | None = None
    threshold_text: str | None = None
    ordered: bool = False                                   # L has a natural cheapest-first order (mast height)
    measure: str | None = None                              # display name of the measure (defaults to the metric label)


QUESTIONS = [
    Question('mast_sun_earth', 'centre_mast_schedule.json.gz', 'sun_earth_pct', 'max', ['T'], ['D_mast'],
             'Which mast height keeps Sun and Earth in view together (14-day demo window)?', fix={'S': 0},
             threshold=40.0, threshold_text='Team requirement: Sun+Earth ≥ 40 %', ordered=True),
    Question('mast_sun_gap', 'centre_mast_schedule.json.gz', 'sun_gap_h', 'min', ['T'], ['D_mast'],
             'Which mast height keeps the longest Sun gap short (14-day demo window)?', fix={'S': 0},
             threshold=120.0, threshold_text='Team requirement: longest Sun gap ≤ 120 h', ordered=True),
    Question('pos_sun_earth', 'position_schedule.json.gz', 'sun_earth_pct', 'max', ['T'], ['D_pos'],
             'Where in the ±100 m square should the 1 m mast stand (Sun+Earth, 14-day demo window)?', fix={'S': 0},
             threshold=40.0, threshold_text='Team requirement: Sun+Earth ≥ 40 %'),
    Question('pos_sun_12mo', 'position_schedule.json.gz', 'sun_pct', 'max', ['T'], ['D_pos'],
             'Where in the ±100 m square is the Sun in view most over 12 months (1 m mast)?', reduce={'S': 'mean'},
             measure='Sun centre visible, mean of the 14-day window % over 366 daily starts'),
    Question('pos_slope', 'terrain_safety.json', 'landing_slope_100m', 'min', ['T'], ['D_pos'],
             'Where in the ±100 m square is the ground flattest for landing?',
             threshold=10.0, threshold_text='Landing slope limit ≤ 10° (100 m plane fit)'),
    Question('energy_battery', 'energy.json.gz', 'battery_needed_kwh', 'min', ['T'], ['D_array', 'D_mast'],
             'Which array and mast need the smallest battery (14-day demo window)?', label=ENGINEERING, fix={'S': 0},
             threshold=10.0, threshold_text='Assumed battery: 10 kWh usable (science/energy/assumptions.yaml)'),
    Question('link_dsn', 'link.json.gz', 'available_pct', 'max', ['T'], ['D_mast'],
             'Which mast height keeps the direct-to-Earth DSN link up (14-day demo window)?', label=ENGINEERING,
             fix={'S': 0, 'target': 'earth_dsn', 'R_margin': 0.0}, ordered=True),
    Question('layout_power_link', 'asset_layout.json', 'power_and_link_pct', 'max', ['T'], ['D_layout'],
             'Which asset layout gives power and link in the same hour (14-day demo window)?', label=ENGINEERING,
             fix={'S_window': 'demo_14d'}),
]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


_CACHE: dict[Path, tuple[dict, str]] = {}


def load(site: str, file: str) -> tuple[dict, str]:
    p = CUBES / site / file
    if p not in _CACHE:
        c, sha = v2.read_json_maybe_gzip(p)
        _CACHE[p] = (v2.migrate_v1_to_v2(c, source_sha256=sha), sha)
    return _CACHE[p]


def _index(dim: dict, v) -> int:
    """A fixed axis is given by value (e.g. 'earth_dsn', 0.0) or, when the value is not on the axis, by index
    (S = 0 is the first start date, 2026-11-14)."""
    if v in dim['values']:
        return dim['values'].index(v)
    if isinstance(v, int) and not isinstance(v, bool) and 0 <= v < len(dim['values']):
        return v
    raise v2.CubeV2Error(f'{dim["name"]}: no value {v!r}')


def table(cube: dict, q: Question) -> dict:
    """X x L table for one question with labels and source flat indices (None when the cell is a reduction)."""
    dims = cube['dims']
    names = [d['name'] for d in dims]
    roles = v2.dim_roles(cube)
    for n in q.x:
        if roles[n] != 'uncertainty':
            raise v2.CubeV2Error(f'{q.id}: X axis {n} has role {roles[n]}')
    for n in q.l:
        if roles[n] != 'decision':
            raise v2.CubeV2Error(f'{q.id}: L axis {n} has role {roles[n]}')
    for n in names:
        if n in q.x or n in q.l:
            continue
        if n in q.reduce:
            if roles[n] != 'decision':
                raise v2.CubeV2Error(f'{q.id}: only a decision axis may be averaged into a measure, not {n} ({roles[n]})')
        elif n not in q.fix:
            raise v2.CubeV2Error(f'{q.id}: axis {n} ({roles[n]}) must be fixed or listed in X or L')
    fixed = {n: _index(dims[names.index(n)], v) for n, v in q.fix.items()}
    m = cube['metrics'][q.metric]
    scale = m.get('scale', 1.0)
    sizes = [len(d['values']) for d in dims]
    vals = np.array([np.nan if v is None else v for v in m['values']], dtype=float).reshape(sizes) * scale
    flat = np.arange(int(np.prod(sizes))).reshape(sizes)
    # order axes X..., L..., reduce..., then index fixed
    sel = tuple(fixed[n] if n in fixed else slice(None) for n in names)
    free = [n for n in names if n not in fixed]
    v = vals[sel]; f = flat[sel]
    order = [free.index(n) for n in q.x + q.l + list(q.reduce)]
    v = np.transpose(v, order); f = np.transpose(f, order)
    nx = int(np.prod([sizes[names.index(n)] for n in q.x])); nl = int(np.prod([sizes[names.index(n)] for n in q.l]))
    if q.reduce:
        if not np.isfinite(v).all():
            raise v2.CubeV2Error(f'{q.id}: missing cells inside a reduction')
        v = v.reshape(nx, nl, -1).mean(axis=-1)
        src = [[None] * nl for _ in range(nx)]
    else:
        v = v.reshape(nx, nl)
        src = f.reshape(nx, nl).astype(int).tolist()

    def labels(ns):
        ds = [dims[names.index(n)] for n in ns]
        out = []
        for combo in product(*[range(len(d['values'])) for d in ds]):
            parts = []
            for d, i in zip(ds, combo):
                lab = (d.get('value_labels') or [None] * len(d['values']))[i]
                val = d['values'][i]
                if lab is None:
                    lab = f'{val:g} {d.get("units", "")}'.strip() if isinstance(val, (int, float)) else str(val)
                parts.append(lab)
            out.append(' · '.join(parts))
        return out

    def nominal(ns):
        ds = [dims[names.index(n)] for n in ns]
        idx = 0
        for d in ds:
            idx = idx * len(d['values']) + int(d.get('nominal_index', 0))
        return idx

    return {'values': v, 'source_flat_index': src, 'x_labels': labels(q.x), 'l_labels': labels(q.l),
            'x_dims': [dims[names.index(n)] for n in q.x], 'l_dims': [dims[names.index(n)] for n in q.l],
            'nominal_x': nominal(q.x), 'nominal_l': nominal(q.l), 'fixed': fixed,
            'fixed_labels': {n: str((dims[names.index(n)].get('value_labels') or dims[names.index(n)]['values'])[i])
                             for n, i in fixed.items()},
            'metric_label': q.measure or m['label'], 'units': m['units'] or '',
            'decimals': m.get('decimals', 2)}
