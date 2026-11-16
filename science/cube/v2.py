"""Scenario cube v2 (6D roles): v1 -> v2 migration, the exact inverse, and role-driven decision helpers.

Contract: `schemas/scenario-cube-v2.schema.json`, model: `docs/v2/6D_MODEL.md`.

v2 = v1 plus `role` on every axis (`uncertainty` X, `decision` L, `requirement` filter, `context` selector); `kind` is
kept. Migration never touches a value: `to_v1(migrate_v1_to_v2(c)) == c` for every committed cube (tested).

The role rule is deterministic: `ROLE_BY_KIND[kind]`, unless `(kind, name)` is in `ROLE_OVERRIDES`. Both tables are
embedded in the v2 schema (`x-role-by-kind`, `x-role-overrides`) and the tests check that this module, the schema and
`web/src/bundle/scenarioCubeV2.ts` agree.

The decision helpers (robust choice, regret, minimax regret, "would knowing X change L") are display-free Python. They
are deterministic and non-probabilistic: "min over X" is over the listed members only (e.g. nominal + 20 PGDA 78 clones),
which is a stress test over this scenario set, not a probability and not a worst case over all possible terrain.

CLI: `python -m science.cube.v2 --check [data/cubes]` migrates every cube in memory and checks the round trip and the
schema; `--out DIR` also writes the v2 files there (never into data/cubes).
"""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import sys
from itertools import product
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

V1 = 'scenario-cube-v1'
V2 = 'scenario-cube-v2'
ROLES = ('uncertainty', 'decision', 'requirement', 'context')

ROLE_BY_KIND: dict[str, str] = {
    'uncertainty_terrain': 'uncertainty',
    'uncertainty_model': 'uncertainty',
    'design': 'decision',
    'schedule': 'decision',  # window start date / launch day / arrival slip are levers in prompt §1.1
    'requirement': 'requirement',
    'site': 'context',
    'target': 'context',  # target mixes measures (Sun, Earth) with relay options; see 6D_MODEL.md §5
}

# (kind, name) -> (role, reason). Only axes whose v1 kind is too coarse for the 6D split.
ROLE_OVERRIDES: dict[tuple[str, str], tuple[str, str]] = {
    ('schedule', 'H'): ('context', 'hourly sample time coordinate (axis 4 itself), not a start date the mission chooses'),
    ('schedule', 'S_window'): ('context', 'evaluation horizon (14-day demo window vs 12 months), a question selector, not a lever'),
    ('uncertainty_terrain', 'k'): ('context', 'outcome bin (number of clone maps passing), a measure, not a member of the uncertainty set X'),
}

ROLE_RULE = 'role = ROLE_BY_KIND[kind] unless (kind, name) in ROLE_OVERRIDES (science/cube/v2.py)'
_DIM_KEYS_V2_ONLY = ('role', 'role_note')
_TOP_KEYS_V2_ONLY = ('world', 'migration')

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_V1 = ROOT / 'schemas' / 'scenario-cube-v1.schema.json'
SCHEMA_V2 = ROOT / 'schemas' / 'scenario-cube-v2.schema.json'


class CubeV2Error(ValueError):
    pass


# --------------------------------------------------------------------------------------------- roles + migration
def role_for(kind: str, name: str) -> tuple[str, str | None]:
    """(role, note). note is set only when an override applies."""
    if (kind, name) in ROLE_OVERRIDES:
        role, reason = ROLE_OVERRIDES[(kind, name)]
        return role, reason
    if kind not in ROLE_BY_KIND:
        raise CubeV2Error(f'no role for kind {kind!r} (dim {name!r})')
    return ROLE_BY_KIND[kind], None


def _with_role(dim: Mapping[str, Any]) -> dict:
    role, note = role_for(dim['kind'], dim['name'])
    out: dict[str, Any] = {}
    for k, v in dim.items():
        out[k] = copy.deepcopy(v)
        if k == 'kind':
            out['role'] = role
            if note:
                out['role_note'] = note
    return out


def _without_role(dim: Mapping[str, Any]) -> dict:
    return {k: copy.deepcopy(v) for k, v in dim.items() if k not in _DIM_KEYS_V2_ONLY}


def _map_dims(cube: dict, fn) -> None:
    cube['dims'] = [fn(d) for d in cube['dims']]
    for blk in (cube.get('derived') or {}).values():
        blk['dims'] = [d if isinstance(d, str) else fn(d) for d in blk['dims']]


def migrate_v1_to_v2(cube: Mapping[str, Any], *, source_sha256: str | None = None) -> dict:
    """v1 -> v2. A v2 input is returned as a deep copy (idempotent). Values are deep-copied, never changed."""
    if cube.get('schema') == V2:
        return copy.deepcopy(dict(cube))
    if cube.get('schema') != V1:
        raise CubeV2Error(f'not a scenario cube: schema {cube.get("schema")!r}')
    out: dict[str, Any] = {}
    for k, v in cube.items():
        out[k] = V2 if k == 'schema' else copy.deepcopy(v)
        if k == 'site_id':
            out['world'] = 'moon'
    _map_dims(out, _with_role)
    mig: dict[str, Any] = {'from_schema': V1, 'tool': 'science/cube/v2.py migrate_v1_to_v2', 'role_rule': ROLE_RULE}
    if source_sha256:
        mig['source_sha256'] = source_sha256
    out['migration'] = mig
    return out


def to_v1(cube: Mapping[str, Any]) -> dict:
    """v2 -> v1 slicing view: drop role/role_note/world/migration. Exact inverse of migrate_v1_to_v2."""
    if cube.get('schema') == V1:
        return copy.deepcopy(dict(cube))
    if cube.get('schema') != V2:
        raise CubeV2Error(f'not a scenario cube: schema {cube.get("schema")!r}')
    out = {k: (V1 if k == 'schema' else copy.deepcopy(v)) for k, v in cube.items() if k not in _TOP_KEYS_V2_ONLY}
    _map_dims(out, _without_role)
    return out


def read_json_maybe_gzip(path: Path) -> tuple[Any, str]:
    raw = Path(path).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    return json.loads(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw), sha


def load_any(path: Path) -> dict:
    """Read a v1 or v2 cube file and return it as v2 (v1 is migrated in memory, with the file's SHA-256)."""
    c, sha = read_json_maybe_gzip(path)
    return migrate_v1_to_v2(c, source_sha256=sha)


def _skeleton(cube: Mapping[str, Any], keep: int) -> dict:
    """Copy with every metric `values` array cut to `keep` entries (shared references elsewhere; read-only use)."""
    def cut(ms):
        return {k: {**m, 'values': m['values'][:keep]} for k, m in ms.items()}
    out = dict(cube)
    out['metrics'] = cut(cube['metrics'])
    if 'derived' in cube:
        out['derived'] = {k: {**b, 'metrics': cut(b['metrics'])} for k, b in cube['derived'].items()}
    return out


def _value_ok(v: Any) -> bool:
    return v is None or isinstance(v, (bool, int, float))


def validate_v2(cube: Mapping[str, Any], *, full: bool = False) -> None:
    """JSON-schema check plus the rules a schema cannot state (array sizes).

    full=False validates the schema on a skeleton (metric arrays cut to 64 values) and type-checks every value in Python:
    the same constraints (`values` items are number | boolean | null), ~20x faster on the 1-2 M-cell cubes.
    """
    import jsonschema

    schema = json.loads(SCHEMA_V2.read_text())
    jsonschema.validate(cube if full else _skeleton(cube, 64), schema)
    n = 1
    for d in cube['dims']:
        n *= len(d['values'])
    for k, m in cube['metrics'].items():
        if len(m['values']) != n:
            raise CubeV2Error(f'metric {k} has {len(m["values"])} values, dims give {n}')
        if not full and not all(_value_ok(v) for v in m['values']):
            raise CubeV2Error(f'metric {k} has a value that is not number | boolean | null')
    parent = {d['name']: d for d in cube['dims']}
    for bk, b in (cube.get('derived') or {}).items():
        dn = 1
        for d in b['dims']:
            if isinstance(d, str) and d not in parent:
                raise CubeV2Error(f'derived {bk} refers to unknown dim {d}')
            dn *= len((parent[d] if isinstance(d, str) else d)['values'])
        for k, m in b['metrics'].items():
            if len(m['values']) != dn:
                raise CubeV2Error(f'derived {bk}.{k} has {len(m["values"])} values, dims give {dn}')
            if not full and not all(_value_ok(v) for v in m['values']):
                raise CubeV2Error(f'derived {bk}.{k} has a value that is not number | boolean | null')


def dim_roles(cube: Mapping[str, Any]) -> dict[str, str]:
    """name -> role for the parent dims (v1 input gets the migration rule)."""
    if cube.get('schema') == V2:
        return {d['name']: d['role'] for d in cube['dims']}
    return {d['name']: role_for(d['kind'], d['name'])[0] for d in cube['dims']}


# --------------------------------------------------------------------------------------------- decision helpers
def _flat(sizes: Sequence[int], idx: Sequence[int]) -> int:
    i = 0
    for n, k in zip(sizes, idx):
        i = i * n + k
    return i


def decision_table(cube: Mapping[str, Any], metric: str, at: Mapping[str, int] | None = None,
                   *, scaled: bool = True) -> dict:
    """Collapse a cube metric to an X x L table using the axis roles.

    X = product of the uncertainty axes not fixed in `at`; L = product of the decision axes not fixed in `at`.
    Requirement and context axes must be fixed in `at` (a requirement is a filter, a context is a selector: neither is
    optimised or stressed over). Returns {'x_labels', 'l_labels', 'x_dims', 'l_dims', 'values'} with values[x][l]
    (None for a missing cell). No arithmetic beyond stored x scale.
    """
    at = dict(at or {})
    roles = dim_roles(cube)
    dims = cube['dims']
    for k in at:
        if k not in roles:
            raise CubeV2Error(f'unknown dim {k!r}')
    free = [d for d in dims if d['name'] not in at]
    bad = [d['name'] for d in free if roles[d['name']] in ('requirement', 'context')]
    if bad:
        raise CubeV2Error(f'requirement/context axes must be fixed, not stressed or optimised over: {bad}')
    xd = [d for d in free if roles[d['name']] == 'uncertainty']
    ld = [d for d in free if roles[d['name']] == 'decision']
    m = cube['metrics'][metric]
    scale = m.get('scale', 1) if scaled else 1
    sizes = [len(d['values']) for d in dims]

    def lab(ds, combo):
        return tuple((d.get('value_labels') or d['values'])[i] for d, i in zip(ds, combo))

    xs = list(product(*[range(len(d['values'])) for d in xd])) or [()]
    ls = list(product(*[range(len(d['values'])) for d in ld])) or [()]
    vals = []
    for xc in xs:
        row = []
        for lc in ls:
            pos = dict(at)
            pos.update({d['name']: i for d, i in zip(xd, xc)})
            pos.update({d['name']: i for d, i in zip(ld, lc)})
            v = m['values'][_flat(sizes, [pos[d['name']] for d in dims])]
            row.append(None if v is None else v * scale)
        vals.append(row)
    return {'x_dims': [d['name'] for d in xd], 'l_dims': [d['name'] for d in ld],
            'x_labels': [lab(xd, c) for c in xs], 'l_labels': [lab(ld, c) for c in ls], 'values': vals}


def _sign(sense: str) -> int:
    if sense not in ('max', 'min'):
        raise CubeV2Error("sense must be 'max' (higher is better) or 'min' (lower is better)")
    return 1 if sense == 'max' else -1


def _check(table: Sequence[Sequence[float | None]]) -> None:
    if not table or not table[0]:
        raise CubeV2Error('empty X x L table')
    w = len(table[0])
    if any(len(r) != w for r in table):
        raise CubeV2Error('ragged X x L table')
    if any(v is None for r in table for v in r):
        raise CubeV2Error('table has missing cells; fix the slice or drop those members explicitly')


def robust_choice(table: Sequence[Sequence[float]], sense: str = 'max') -> dict:
    """Maximin over the listed X members: L* = argbest_L worst_X m(x, L). Ties -> lowest index."""
    _check(table)
    s = _sign(sense)
    worst = [min(s * table[x][l] for x in range(len(table))) * s for l in range(len(table[0]))]
    best = max(range(len(worst)), key=lambda l: (s * worst[l], -l))
    return {'choice': best, 'worst_by_choice': worst, 'worst_at_choice': worst[best]}


def nominal_choice(table: Sequence[Sequence[float]], nominal_x: int = 0, sense: str = 'max') -> int:
    _check(table)
    s = _sign(sense)
    row = table[nominal_x]
    return max(range(len(row)), key=lambda l: (s * row[l], -l))


def regret_table(table: Sequence[Sequence[float]], choice: int, sense: str = 'max') -> list[float]:
    """Per X member: best achievable under that member minus what `choice` gives (>= 0, in metric units)."""
    _check(table)
    s = _sign(sense)
    return [s * (max(s * v for v in row) * s - row[choice]) for row in table]


def minimax_regret_choice(table: Sequence[Sequence[float]], sense: str = 'max') -> dict:
    """L minimising the maximum regret over the listed X members (Savage). Ties -> lowest index."""
    _check(table)
    mr = [max(regret_table(table, l, sense)) for l in range(len(table[0]))]
    best = min(range(len(mr)), key=lambda l: (mr[l], l))
    return {'choice': best, 'max_regret_by_choice': mr, 'max_regret_at_choice': mr[best]}


def choice_changes_if_known(table: Sequence[Sequence[float]], reference_choice: int, sense: str = 'max') -> dict:
    """Non-probabilistic value-of-information screen: for each X member, would knowing it is true change L?

    Returns the members where the best L differs from `reference_choice` and the regret avoided there. Counting these
    members ("k of N members") is not a probability.
    """
    _check(table)
    s = _sign(sense)
    best = [max(range(len(r)), key=lambda l: (s * r[l], -l)) for r in table]
    reg = regret_table(table, reference_choice, sense)
    changes = [x for x, b in enumerate(best) if reg[x] > 0 and b != reference_choice]
    return {'best_if_known': best, 'changes_at': changes, 'regret_avoided': [reg[x] for x in changes]}


# --------------------------------------------------------------------------------------------- CLI
def iter_cube_files(root: Path) -> Iterable[Path]:
    for p in sorted(Path(root).glob('*/*')):
        if p.name.endswith(('.json', '.json.gz')):
            yield p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('root', nargs='?', default=str(ROOT / 'data' / 'cubes'))
    ap.add_argument('--check', action='store_true', help='round-trip and schema check (default action)')
    ap.add_argument('--out', help='write migrated v2 files here (not into data/cubes)')
    a = ap.parse_args(argv)
    root = Path(a.root)
    out = Path(a.out) if a.out else None
    if out and out.resolve().is_relative_to((ROOT / 'data' / 'cubes').resolve()):
        ap.error('--out must not be inside data/cubes (committed v1 cubes stay as they are)')
    n = 0
    for p in iter_cube_files(root):
        c, sha = read_json_maybe_gzip(p)
        if not isinstance(c, dict) or c.get('schema') != V1:
            continue
        v2 = migrate_v1_to_v2(c, source_sha256=sha)
        validate_v2(v2)
        if to_v1(v2) != c:
            print(f'ROUND TRIP FAILED {p}', file=sys.stderr)
            return 1
        roles = ', '.join(f'{d["name"]}={d["role"]}' for d in v2['dims'])
        print(f'ok {p.relative_to(root)}  [{roles}]')
        if out:
            dst = out / p.relative_to(root)
            dst.parent.mkdir(parents=True, exist_ok=True)
            data = json.dumps(v2, separators=(',', ':'), ensure_ascii=False).encode()
            dst.write_bytes(gzip.compress(data, mtime=0) if p.name.endswith('.gz') else data)
        n += 1
    print(f'{n} v1 cubes migrated; round trip identical; v2 schema valid')
    return 0 if n else 1


if __name__ == '__main__':
    raise SystemExit(main())
