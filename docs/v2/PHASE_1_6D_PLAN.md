# Phase 1 (§1 of the v2 prompt) — the 6D model and scenario cube v2: plan

Session S1, branch `claude/v2-s1-6d-cube-0bb4aa` (worktree of the same name, cut from `feature/v2-whole-moon` eda168c;
already a descendant, so no separate `v2-s1-6d-cube` branch was created).
Written before any code (prompt §0.5 step 1). Owner files per `docs/v2/SPLIT.md`.

## Inputs

| input | used for |
|---|---|
| `docs/v2/inputs/CLAUDE_CODE_PROMPT_6D_worlds_blender_v2.md` §0, §1, §4 | axis table, XLRM reasoning, rejected alternatives, migration rule, §4 tests (known robust optimum; regret = 0 when X has one member) |
| `schemas/scenario-cube-v1.schema.json`, `docs/SCENARIO_CUBE_CONTRACT.md` | the v1 contract v2 must extend without changing any value |
| `data/cubes/site04_roi3/*`, `data/cubes/site01_roi6/*` (14 `scenario-cube-v1` cubes per site, 28 total) | migration round-trip test corpus |
| `science/cube/*.py`, `web/src/bundle/scenarioCube.ts`, `web/src/components/CubeSlicer.tsx` | existing loader/slicer that must keep working |
| `docs/v2/inputs/POLARIS_X_FABLE_5_2_MASTER_REBUILD_PROMPT.md`, `…_NASA_EYES_PLUSPLUS_PROMPT.md` | backlog (task 5) |

No downloads, no new data. The committed cubes stay `scenario-cube-v1` files (they are not S1-owned and the browser index
lists them); v2 is produced by migration in memory (and optionally written to a scratch directory by the CLI).

## Method

1. **Model doc** `docs/v2/6D_MODEL.md`: axis table (1–3 ENU, 4 time, 5 uncertainty X, 6 decision L), requirements as
   filters, world as a context selector; XLRM reasoning; what it enables (robust choice, regret, value of information,
   all non-probabilistic); rejected alternatives; mapping of every existing 5D cube axis to a role.
2. **Schema** `schemas/scenario-cube-v2.schema.json`: v1 unchanged plus `role ∈ {uncertainty, decision, requirement,
   context}` required on every dim (including inline dims of `derived` blocks); `kind` kept with the same enum; optional
   `role_note`, top-level optional `world` and `migration` (source schema, source SHA-256, tool). The deterministic role
   table is embedded in the schema as `x-role-by-kind` / `x-role-overrides` so Python and TS can be tested against one
   source.
3. **Role rule** (deterministic): role from `kind`, except a short explicit `(kind, name)` override list for axes whose
   v1 kind is too coarse (the hourly time coordinate `H`, the outcome-count bin `k`, the evaluation-horizon selector
   `S_window`). Every override carries a reason that the migration writes to `role_note`.
4. **Python** `science/cube/v2.py`: `migrate_v1_to_v2`, `to_v1` (exact inverse), `load_any` (v1 or v2 file → v2 dict),
   `validate_v2`, plus small display-free decision helpers over an X × L table built from roles: `robust_choice`
   (max over L of min over X), `regret_table` (loss of the nominal pick under each X member), `minimax_regret_choice`,
   `choice_changes_if_known` (non-probabilistic value-of-information screen). CLI `python -m science.cube.v2 --check`.
5. **TS** `web/src/bundle/scenarioCubeV2.ts`: reads v1 and v2, returns the existing v1 slicing view with `role` on every
   dim and `source_schema`; same role table and overrides as Python; `migrateV1toV2` / `toV1` mirrors. No science in the
   browser: roles only group controls.
6. **UI** `CubeSlicer`: controls grouped into "What we don't know" (uncertainty), "What we choose" (decision),
   "Requirement (filter)" and "Context" groups. Every existing `data-testid` kept; the `R` preset control of `k_of_N`
   moves into the requirement group with the same test id.
7. **Backlog** `docs/v2/BACKLOG.md`: every still-open P0/P1 defect and UX rule from the two team prompts with its source
   line, checked against the current code (open / fixed with evidence). v2 prompt wins on science/data; team prompts on
   UX detail.

## Tests (each can fail)

Python `science/tests/test_cube_v2.py`:
- every committed v1 cube migrates; `to_v1(migrate(c)) == c` exactly; every metric/derived/missing/provenance value
  identical; dims identical apart from the added `role`/`role_note`;
- every migrated cube validates against the v2 schema; every committed cube still validates against v1;
- the v2 schema rejects a dim without `role`, a bad role, and a v1 `schema` constant;
- the Python role table equals the schema's `x-role-by-kind` / `x-role-overrides`;
- migration is deterministic (same input → byte-identical JSON) and idempotent on v2 input;
- synthetic X × L cube with a known robust optimum (`robust_choice` finds it, nominal pick differs);
- regret = 0 everywhere when X has one member; minimax-regret on a hand-checked 3 × 3 table;
- role-driven table builder refuses an unfixed requirement/context axis.

Vitest `web/tests/unit/scenarioCubeV2.test.ts`:
- every committed cube (`data/cubes/`) read as v1 gets the same roles the schema table gives; a v2 object (built by
  `migrateV1toV2`) reads to the same slicing view with every cell identical; `toV1(migrateV1toV2(c))` deep-equals `c`;
- TS role table equals the schema's embedded table; bad role and missing role rejected.

Playwright: `cube-slicer.spec.ts` (unchanged test ids + a new assertion on the two groups), `cube-views.spec.ts`,
`traceability.spec.ts`, with `POLARIS_PLAYWRIGHT_PORT=4201`.

## Acceptance

- `python -m pytest science/tests -q` green; `cd web && npm run build && npx vitest run` green; the three Playwright specs
  green on port 4201.
- No committed cube value changes (`git diff --stat data/` empty).
- `docs/BUILD_STATUS.md` appended; S1 row in `docs/v2/STATUS.md` filled; small commits on this branch only; nothing pushed.

## Out of scope tonight (Phase 3, §4)

Robust choice / regret / VoI *panels* across the whole Moon, Pareto view, "best landing point within R km". The Python
helpers here are the tested core those panels will call; no new derived blocks are written into the committed cubes.
