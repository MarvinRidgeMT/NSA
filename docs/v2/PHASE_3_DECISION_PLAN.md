# POLARIS X v2 — Phase 3 plan: 6D decision tools (session R5, prompt §4)

Written before coding (16 Nov 2026, session R5, branch `claude/v2-r5-decision-04ba20`, cut from `feature/v2-whole-moon`
at 72e3430). Model: `docs/v2/6D_MODEL.md` (X = uncertainty, L = decision, requirements = filters, world/site = context).
Owns `science/decision/**`, additions to `science/cube/v2.py` and `web/src/bundle/scenarioCubeV2.ts`,
`web/src/components/Decision6D*.tsx`. Never changes a number in an existing cube file.

## 0. Rules carried into every output

- Every statement is **over the listed members of X** (nominal PGDA 78 map + 20 PGDA 78 error clones; for the landing
  search also the any-site solver's product members). "Worst case" = worst listed member, not a bound over all terrain.
- **k of N maps is not a probability.** Counts are never combined across axes or questions into a probability. No
  expected value of information is computed: the clones carry no weights. A plain mean over members is labelled
  "unweighted mean over the listed members (not an expectation)".
- Requirement and context axes are **fixed** before a question is asked (`science/cube/v2.decision_table` already
  refuses otherwise). Decision axes not optimised in a question are held at a stated value (e.g. start date = the
  2026-11-14 demo start).
- Labels: geometry SOURCE-BASED · UNVALIDATED; energy and link ENGINEERING ASSUMPTION. Every output records the source
  cube file, its SHA-256 and the fixed indices so the UI can show traceability.
- The browser only displays precomputed numbers (no science in TypeScript).

## 1. Core: robust choice, regret, value of information (`science/decision/core.py`)

Input: a table `m[x, l]` (X members × L options, from `v2.decision_table`) plus `sense` (max/min) and the nominal
X index. Outputs (all deterministic):

| Output | Definition |
|---|---|
| robust choice | `L* = argbest_l worst_x m(x,l)` (maximin; minimax for lower-is-better). Ties reported as the full tied set; the reported pick is the tied option that is best on the nominal member, then the nominal L, then the lowest index |
| nominal choice | `L_nom = argbest_l m(x_nom, l)` (same tie rule) |
| regret | `r(x,l) = best_l' m(x,l') − m(x,l)` (sign flipped for lower-is-better), ≥ 0. Reported for `L_nom` (the task's definition: choose on the nominal member, truth is another member) and for `L*`: max and unweighted mean over X |
| minimax-regret choice | `argmin_l max_x r(x,l)` (Savage) |
| VoI (per uncertainty axis A) | resolve A: for each value a, the robust choice over the remaining members `X|a`, `L*(a)`. Gain(a) = `worst_{X|a} m(·,L*(a)) − worst_{X|a} m(·,L*)` (≥ 0). Reported: values a where `L*(a) ≠ L*` (k of |A|, not a probability), max gain, unweighted mean gain. "Resolve all of X" (perfect information) is reported as its own row: gain(x) = regret of `L*` at x |
| requirement screen (ordered L only, e.g. mast) | smallest L whose worst-over-X value meets a threshold, and the same on the nominal member alone |

The existing helpers in `science/cube/v2.py` (`robust_choice`, `regret_table`, `minimax_regret_choice`,
`choice_changes_if_known`) stay as they are; the tests check the new module against them where tie rules coincide.

Tests (`science/decision/tests/`): synthetic cube with a planted robust optimum (different from the nominal optimum) →
robust choice, regret and VoI values known by hand; regret = 0 and VoI = 0 when X has one member; sense = min mirrors
sense = max on a negated table; two-axis X where resolving one axis changes the choice and the other does not;
requirement/context axes left free are refused; ties; missing cells refused.

## 2. Questions precomputed per site → `data/cubes/<site>/decision6d.json` (new file, `scenario-cube-v2`)

Questions (from existing cubes only; start date fixed at the 2026-11-14 demo start unless the question says 12-month):

| id | source cube | X | L | fixed | measure (sense) | label |
|---|---|---|---|---|---|---|
| mast_sun_earth | centre_mast_schedule | T | D_mast | S = demo start | Sun+Earth % (max) | geometry |
| mast_sun_gap | centre_mast_schedule | T | D_mast | S = demo start | longest Sun gap h (min) | geometry |
| pos_sun_earth | position_schedule | T | D_pos (81) | S = demo start | Sun+Earth % (max) | geometry |
| pos_sun_12mo | position_schedule | T | D_pos | mean over 366 daily starts | Sun % (max) | geometry |
| pos_slope | terrain_safety | T | D_pos | — | landing slope 100 m (min) | geometry |
| energy_battery | energy | T | D_array × D_mast | S = demo start | battery needed kWh (min) | ENGINEERING ASSUMPTION |
| link_dsn | link | T | D_mast | target = earth_dsn, R_margin = 0, S = demo start | link available % (max) | ENGINEERING ASSUMPTION |
| layout_power_link | asset_layout | T | D_layout | S_window = demo | power AND link % (max) | ENGINEERING ASSUMPTION |
| landing_r0p5km / landing_r2km | §3 below | members | candidates | 12 months | Sun % (max) | geometry |

File layout (fits the strict v2 schema without schema changes): parent dim `Q` (role context; one value per question)
with index/count metrics only (robust / nominal / minimax-regret choice index, |X|, |L|, size of the tied set, k of |X|
members where knowing the member changes the choice). Every value-bearing number sits in per-question derived blocks
with inline roled dims: `q__<id>__table` (X × L: value, regret), `q__<id>__by_choice` (L: worst, best, nominal value,
max and mean regret), `q__<id>__by_member` (X: best choice if known, regret of L_nom, regret of L*), `q__<id>__voi`
(uncertainty axes + "all": k changes, max gain, mean gain). Each block's `method`/`caveat` carries the source file,
SHA-256 and fixed indices. A test re-reads every source cell and checks it equals the stored table value.

## 3. "Best landing point within R km of here" (`science/decision/landing.py`)

Screen (emulator), then re-check (full solver), for R = 0.5 km and 2 km around both current sites.

- Candidates: a square lattice clipped to the disc of radius R (step 50 m for 0.5 km, 200 m for 2 km), centre included.
- Requirement filter: landing slope (100 m plane fit, `science/cube/slope.py` on the nominal PGDA 78 map) ≤ 10° (the
  committed `LANDING_LIMITS[0]`); candidates off the near DEM are dropped and counted.
- Screen: the Phase 7 emulator `science/cube/emulator.py` (coarse step17 skyline + GP correction over position).
  **The GP was trained on the ±100 m grid**; beyond it a GP reverts to its mean, so outside ±100 m the screen is the
  coarse surrogate plus a constant correction. That is stated in the output, and the re-check error is what measures it.
  Objective: 12-month share of hourly samples with the Sun centre visible (nominal map, 1 m mast).
- Re-check: top candidates (≥ 100 m apart; 6 per R) plus 2 random survivors, with the any-site solver
  (`science/anysite/solve.py`, 720 bins, native/5 ray step, its own Horizons query at the point) over the same 12-month
  hourly window, with its clone/product members where the terrain stack provides them. Reported: emulator − solver error
  per candidate, MAE, max |error|, Spearman rank correlation, whether the emulator's top pick is the solver's top pick.
- Result written as questions `landing_r0p5km` / `landing_r2km` in `decision6d.json`: X = the solver's members,
  L = re-checked candidates; robust choice over them. Candidate coordinates (lat/lon, ENU offset) are in the L labels.

## 4. Pareto view (`science/decision/pareto.py`)

Over the 81 positions of the ±100 m grid (the only L with all measures available per position):

| axis | sense | source | label |
|---|---|---|---|
| Sun % (12-month mean of window %) | max | position_schedule | SOURCE-BASED · UNVALIDATED |
| Earth centre visible % (12-month) — geometric line of sight; the link cube exists only at the centre | max | position_schedule | SOURCE-BASED · UNVALIDATED (geometry); ENGINEERING ASSUMPTION is not claimed for a geometric number |
| landing slope 100 m | min | terrain_safety | SOURCE-BASED · UNVALIDATED |
| energy margin = 10 kWh assumed battery − battery needed (kWh), worst 14-d window of 12 months | max | **new**: energy model (`science/energy/model.py`, same assumptions YAML) run on hourly Sun disc fractions at each position (cached full-solver skylines) | ENGINEERING ASSUMPTION |
| distance to ice | — | **not available**: no cited M3 / LAMP / Diviner layer is in `$POLARIS_DATA`; not downloaded in this phase | — |

Each axis is stored as nominal, min and max over T. Pareto sets: nominal-map front, and the "robust" front on the
worst-over-T value of every axis. Check: the energy recomputation at the centre (0, 0) equals the committed
`energy.json.gz` cell (vsat, mast 1 m) for every T. Stored as `pareto__*` derived blocks in `decision6d.json`.

## 5. UI (`web/src/components/Decision6D*.tsx`, display only)

On the Decision page, after the cube slicer: a question picker; "What we don't know" (X members) and "What we choose"
(L options) headings; robust choice, nominal choice and regret (max and unweighted mean), VoI per axis, the landing
search table (emulator vs solver, re-check error), and the Pareto table with ranges over X. Every value carries
`data-source`, `data-label` and `data-trace` (cube file + block + flat index) for `traceability.spec.ts`. Copy:
"k of N maps is not a probability"; no combined probability anywhere. Missing file → the panel says "not computed for
this site".

## 6. Acceptance

`python -m pytest science -q`; `cd web && npm run build && npx vitest run`; Playwright Decision specs + traceability on
port 4211; `docs/v2/STATUS.md` row "R5 · …"; `docs/BUILD_STATUS.md` appended. Not done items are listed, not hidden.
