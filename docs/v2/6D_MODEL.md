# POLARIS X v2 — the 6D model

Source: `docs/v2/inputs/CLAUDE_CODE_PROMPT_6D_worlds_blender_v2.md` §1 (definition and reasoning), §4 (decision tools).
Contract: `schemas/scenario-cube-v2.schema.json`. Code: `science/cube/v2.py` (migration, decision helpers),
`web/src/bundle/scenarioCubeV2.ts` (reader), `web/src/components/CubeSlicer.tsx` (grouped controls).
Plan: `docs/v2/PHASE_1_6D_PLAN.md`. Status: **built and tested for the two precomputed sites; decision panels across the
whole Moon (§4) not started.**

Labels stay as in v1: geometry SOURCE-BASED · UNVALIDATED; energy and link ENGINEERING ASSUMPTION; thermal MODEL;
synthetic relief VISUAL; AI output AI-GENERATED. **k of N maps is not a probability**, and counts are never combined
across axes into a "probability of success".

## 1. Axes

| # | Axis | Role | Examples in POLARIS X |
|---|---|---|---|
| 1–3 | East, North, Up (local ENU of the chosen world; metres) | space | any point on the body; azimuth 0° = north, 90° = east |
| 4 | Time (UTC; Horizons samples, TDB where SPICE is used; frames documented per bundle) | time | hourly ephemeris samples, mission window, launch calendar, 18.6-yr cycle |
| 5 | **Uncertainty X**: what we do not control | stress over it | T terrain realizations (PGDA 78 nominal + 20 clones; later far-field members), M data product (LOLA 5 m, PGDA 90 20/40/80 m, SfS; later SLDEM2015, Kaguya TC, NAC DTM) |
| 6 | **Decision L**: what the mission controls | optimise over it | mast and asset heights, landing point / position, layout, array type, relay use, battery, start date, arrival slip |

Not axes:

- **Requirements R** (team thresholds, slope limits, visibility rule, elevation margin) are **filters on outcomes**.
  A cube may still store them as a dimension so every preset is precomputed, but they carry `role: requirement`, are
  always fixed to one preset when a decision question is asked, and are never optimised or stressed over.
- **World** (Moon, Mercury, Mars …) is a **context selector**: it picks a different scenario (different ephemeris,
  frames, physics), not a varying quantity inside one decision. v2 cubes carry it as the top-level `world` field.
- Other **context** selectors (`role: context`): the site, which measure or link target is shown, the evaluation
  horizon, and the time coordinate itself when a cube stores raw samples rather than start dates.

Dimension 5 is never called a physical spatial dimension, and neither is 6.

## 2. Why "Decision" is the right 6th dimension

**The established framework.** Separating what we do not control from what we choose is the standard frame of
decision-making under deep uncertainty. RAND's XLRM framework (Lempert, Popper and Bankes, *Shaping the Next One Hundred
Years*, RAND MR-1626, 2003; citation not re-checked online tonight) names four parts:

| XLRM | meaning | POLARIS X |
|---|---|---|
| **X** exogenous uncertainties | factors decision makers do not control | terrain realization T, data product M (axis 5) |
| **L** policy levers | actions decision makers can take | mast, position, layout, array, relay use, schedule (axis 6) |
| **R** relationships (model) | how X and L map to outcomes | the Python solver: `science/skyline.py`, `science/cube/compute.py`, energy, link, dispersion builders |
| **M** measures | how outcomes are judged | Sun %, Sun+Earth %, longest Sun gap, slope, battery needed, link availability; judged against the requirements R |

The 5D cube already held both X and L, mixed in one "scenario" axis with sub-kinds. 6D gives each sub-axis an explicit
role so the questions below are well-posed and the code can refuse ill-posed ones (for example, "optimise over the
requirement preset" or "take the worst case over link targets").

**What it gives the user.** All three are deterministic statements over the listed members of X, not probabilities:

- **Robust choice**: the L with the best worst-case measure over the listed X members (maximin). In v1 terms: the mast
  height whose *worst* of the 21 maps is best. `science/cube/v2.robust_choice`.
- **Regret**: the loss from choosing L on the nominal map when the truth is another member of X:
  `regret(x) = best_L m(x, L) − m(x, L_nominal)` (sign flipped for lower-is-better measures). The minimax-regret choice
  minimises the largest such loss. `regret_table`, `minimax_regret_choice`. The v1 cubes already store a per-start
  regret block (`derived.regret`); v2 makes the same computation generic over any X × L pair.
- **Value of information**: which measurement shrinks X enough to change L. The non-probabilistic screen implemented
  now is "for each X member, would knowing it is the truth change the choice, and by how much": `choice_changes_if_known`.
  An expected value of information needs weights over X, which the clones do not supply; it is not computed.

**Alternatives considered and rejected.**

| Candidate 6th axis | Why not |
|---|---|
| World / body | A different scenario (ephemeris, frames, physics), not a varying quantity inside one decision; it is a context selector |
| Requirements | Stakeholder thresholds on outputs; they filter M, they are not stressed or optimised over |
| Data product | Structural uncertainty: it belongs inside X |
| Observer type (lander, rover, crew, antenna) | It is a decision value (a height or asset in L), not a new axis |
| Probability / risk | The clones are deterministic alternates without calibrated weights; k of N is a count, not a probability |
| A second time axis (window start vs sample time) | Start date is a lever (L); sample time is axis 4 itself |

## 3. Role rule (deterministic) and the v1 → v2 migration

`role = x-role-by-kind[kind]`, unless `(kind, name)` is listed in `x-role-overrides`. Both tables live in the v2 schema;
`science/cube/v2.py` and `web/src/bundle/scenarioCubeV2.ts` hold copies that the tests compare to the schema.

| v1 `kind` | v2 `role` | reason |
|---|---|---|
| `uncertainty_terrain` | uncertainty | T: terrain realizations we do not control |
| `uncertainty_model` | uncertainty | M: data product / model choice is structural uncertainty |
| `design` | decision | D_*: hardware and placement levers |
| `schedule` | decision | S: window start date, launch day and arrival slip are levers in prompt §1.1 |
| `requirement` | requirement | R_*: thresholds are filters on outcomes |
| `site` | context | one file per site; site choice across files is a context selector |
| `target` | context | the link-target axis mixes measures (Sun, Earth centre, Earth limb) with relay options; see §5 |

Overrides (each written to the dim's `role_note` by the migration):

| kind | name | role | reason |
|---|---|---|---|
| schedule | `H` | context | hourly sample time coordinate (axis 4 itself), not a start date the mission chooses |
| schedule | `S_window` | context | evaluation horizon (14-day demo window vs 12 months), a question selector, not a lever |
| uncertainty_terrain | `k` | context | outcome bin (number of clone maps passing), a measure, not a member of the uncertainty set X |

Migration (`migrate_v1_to_v2`): `schema` → `scenario-cube-v2`; `role` (and `role_note` when an override applies)
inserted right after `kind` on every parent dim and every inline derived dim; top-level `world: "moon"` (every v1 cube is
lunar) and `migration: {from_schema, tool, role_rule, source_sha256}`. Nothing else changes: values, `value_labels`,
`nominal_index`, metrics, missing masks, derived blocks, provenance, limitations. `to_v1` is the exact inverse.
v1 stays readable everywhere: the committed cubes in `data/cubes/` remain v1 files and the browser reads both versions.

Tested (`science/tests/test_cube_v2.py`, `web/tests/unit/scenarioCubeV2.test.ts`): all 28 committed cubes migrate with
every value identical and `to_v1(migrate(c)) == c` (also through JSON text); migrated cubes validate against the v2
schema and the originals still validate against v1; the schema rejects a missing role, a bad role, an un-roled inline
derived dim and the v1 constant; migration is deterministic and idempotent; the role tables agree across Python, TS and
the schema.

## 4. Every existing 5D cube axis and its role

Both sites (`site04_roi3`, `site01_roi6`) have the same 14 cube files.

| cube file | axes → role | notes |
|---|---|---|
| `centre_mast_schedule.json.gz` | T X · D_mast L · S L | derived `k_of_N` adds R (requirement); `regret` and `decision_changes` are the v1 robust outputs |
| `position_schedule.json.gz` | T X · D_pos L · S L | same derived blocks over position |
| `products.json` | M X | single-axis product comparison table |
| `terrain_safety.json` | T X · D_pos L | derived `safe_and_lit` adds R_slope (requirement) |
| `visibility_rule.json.gz` | T X · R_vis requirement · D_mast L · S L | the visibility rule is a requirement on what counts as "visible" |
| `disc_fraction_hourly.json.gz` | T X · D_mast L · H context | H is the time coordinate (override) |
| `link.json.gz` | T X · D_mast L · target context · R_margin requirement · S L | derived `model_sensitivity` adds `model` (uncertainty_model → X) and `link` (target → context) |
| `energy.json.gz` | T X · D_array L · D_mast L · S L | ENGINEERING ASSUMPTION; derived `needed_by_k` adds K (requirement) |
| `dispersion.json` | R_slope requirement · D_dispersion L · k context | k is an outcome bin (override); "share of sampled landing outcomes", not a probability |
| `asset_layout.json` | T X · D_layout L · S_window context | asset shapes ILLUSTRATIVE |
| `footprint.json` | T X · D_pad L · S_window context | |
| `asset_heights.json` | T X · D_height L · S_window context | |
| `launch_calendar.json.gz` | D_mast L · R requirement · S_day L · S_slip L | arrival slip is a lever per prompt §1.1; see §5 |
| `sensitivity.json` | D_cand L | emulator candidates; Sobol blocks have no dims |

## 5. Choices made tonight (and their alternatives)

- **`target` → context, not decision.** The prompt lists "relay use" as a lever. The stored `target` axis, however, lists
  `sun` and `earth_centre` next to relays and relay pairs, so a robust choice over it would "choose the Sun over the
  Earth". Treating it as a context (which measure/link to look at) is the safe default. A future cube should split it
  into a measure selector plus a `D_relay` decision axis (none, one relay, pair).
- **`S_slip` (arrival slip) → decision**, following prompt §1.1. One could argue slip is exogenous (X). In the launch
  calendar the slip hour is what the plan tolerates, so it is kept as L; a cube that models *unplanned* slip should mark
  that axis `uncertainty` explicitly (v2 allows any role per axis; only the migration is fixed by kind).
- **No new derived blocks were written into the committed cubes.** The decision helpers run in Python on demand; the
  v1 `regret` / `decision_changes` blocks stay what the UI shows.
- **The browser holds every cube in the v1 slicing shape plus `role` per dim and `source_schema`.** This keeps every
  existing slicing helper and test unchanged.

## 6. UI

`CubeSlicer` groups the controls by role: **What we don't know** (uncertainty X: "not under mission control · stress over
these"), **What we choose** (decision L: "mission levers · compare choices across these"), **Requirement** (filter on
outcomes; includes the `k_of_N` preset control) and **Context** (selector). The metric (measure M) stays first. Every
existing `data-testid` is unchanged; the groups have `cube-group-<role>` test ids (`web/tests/e2e/cube-slicer-roles.spec.ts`).

## 7. Not done

- Cube v2 for every precomputed site across the whole Moon, robust choice / regret / VoI panels, the Pareto view and
  "best landing point within R km" (prompt §4, Phase 3).
- A `D_relay` decision axis split out of `target`.
- Weighted (probabilistic) value of information: needs weights over X that the PGDA clones do not provide.
