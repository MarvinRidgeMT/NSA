# Scenario cube contract (v1)

Schema: `schemas/scenario-cube-v1.schema.json`. Builder: `science/cube/build_cube.py`. Browser loader:
`web/src/bundle/scenarioCube.ts`. Label: **SOURCE-BASED · UNVALIDATED** (geometry). Branch `feature/5d-upgrades`.

The fifth axis of POLARIS X is a set of *named, typed scenario sub-axes*. It is never a spatial dimension and
never a probability. A cube replaces the old flat scenario list for the questions it covers; the old bundle
`scenarios` / `derived` blocks are untouched and still drive the existing panels.

## 1. Shape

A cube is one JSON object:

| field | meaning |
|---|---|
| `dims` | ordered list of axes. Each: `name`, `kind`, `values`, `units`, `label`, optional `value_labels`, `nominal_index`, `note` |
| `metrics` | name → `{units, label, dtype, values, provenance, scale?, decimals?}`; `values` is the N-d array flattened **row-major** over `dims` |
| `missing` | `{encoding: "sparse-flat-index", by_metric: {metric: [flat index …]}, reasons}`. A missing cell holds `null`. Nothing is filled silently |
| `derived` | robust-decision outputs (below), each a small cube whose `dims` are parent-dim names or new dims (e.g. `R`) |
| `provenance` | `inputs` (path, SHA-256, URL, note), `command`, `code_commit`, `solver` |
| `fixed` | axes held constant for the whole cube (e.g. `mast_m: 1`, `visibility_rule: centre`) |

Flat index of cell (i₀, i₁, …, iₙ₋₁) with sizes (n₀ … nₙ₋₁): `((i₀·n₁ + i₁)·n₂ + i₂)…`.

Display value = stored value × `scale` (when present). Percentages are stored as **visible-sample counts** with
`scale = 100/337` (a 14-day window has 337 hourly samples, both ends included, the same definition as the
bundles' `*_hourly_samples` metrics), so they are exact and compress well.

## 2. Axis kinds

| kind | code | example | question on the Decision Card |
|---|---|---|---|
| `uncertainty_terrain` | T | nominal + PGDA 78 clones 1–20 | how sure? |
| `uncertainty_model` | M | LOLA 5 m / PGDA 90 20, 40, 80 m / SfS | do the data products agree? |
| `design` | D_* | `D_mast` 1–10 m, `D_pos` 81 cells | what fixes it? |
| `schedule` | S | 14-day window start, hourly or daily over 12 months | when? |
| `requirement` | R | threshold presets; later visibility rule, slope limits | against which requirement? |
| `site` | — | one file per site (browser payload ≤ 20 MB) | — |
| `target` | — | sun, earth_centre, DSN, relays (Phase 4) | who can we talk to? |

"k of N maps" counts clone maps; **it is not a probability**. Scenario counts are never combined across axes
into a probability of success.

## 3. Files (per site)

`data/cubes/<site>/` (copied to `web/public/cubes/<site>/` by `npm run sync-bundles`):

| file | dims | notes |
|---|---|---|
| `index.json` | — | lists cubes with bytes and SHA-256, plus the baseline round-trip check |
| `centre_mast_schedule.json.gz` | T(21) × D_mast(10) × S(8761 hourly starts) | site centre |
| `position_schedule.json.gz` | T(21) × D_pos(81) × S(366 daily starts) | mast 1 m |
| `products.json` | M(5) | copied from `research/long_features/results/lens_*.json`, `sfs_result.json` |
| `energy.json.gz` | T(21) × D_array(2) × D_mast(10) × S(366 daily starts) | Phase 5, label ENGINEERING ASSUMPTION; `science/energy/build_energy.py` |
| `terrain_safety.json` | T(21) × D_pos(81) | Phase 2 slope 5/25/100 m; derived `eva_region`, `safe_and_lit` (R_slope 10°/8°) |
| `visibility_rule.json.gz` | T(21) × R_vis(4) × D_mast(10) × S(366) | Phase 3; `half_disc` = `centre` under the straight-line horizon |
| `disc_fraction_hourly.json.gz` | T(21) × D_mast(10) × H(9097) | Phase 3 hourly visible disc fraction, per-mille, flat local horizon |
| `link.json.gz` | T(21) × D_mast(10) × target(10) × R_margin(3) × S(366) | Phase 4, ENGINEERING ASSUMPTION; derived `year_summary`, `model_sensitivity`, `nasa_sanity_check` |
| `dispersion.json` | R_slope(2) × D_dispersion(6) × k(22) | Phase 6 sample counts; "share of sampled landing outcomes", not a probability |
| `asset_layout.json`, `footprint.json`, `asset_heights.json` | T(21) × D_layout(4) / D_pad(5) / D_height(5) × S_window(2) | Phases 8, 9.1, 9.2; asset shapes ILLUSTRATIVE |
| `launch_calendar.json.gz` | D_mast(10) × R(3) × S_day(365) × S_slip(24) | Phase 9.3, re-indexing of `k_of_N` |
| `decision_summary.json` | — (`polaris-decision-summary-v1`) | Decision Card rows, one per sub-axis question, precomputed by `science/cube/build_summary.py` |

Browser files are gzip-compressed JSON (the loader checks the gzip magic bytes, so a server that already
decodes `Content-Encoding` also works). An optional analysis copy (NetCDF/Zarr) is not written yet; the
solver arrays can be regenerated from the cached skylines (`data/cache/cube_sky/`, git-ignored).

**No combinatorial blow-up:** only the joints above are stored. Position × mast × hourly start is not stored;
it can be computed in Python when a question needs it.

## 4. Derived (robust-decision) outputs — precomputed in Python, display-only in the browser

* `band_over_T`: min and max over the 21 maps of every metric, per D × S cell. Drawn as the range band.
* `k_of_N`: per requirement preset R × D × S, the number of clone maps (of 20) on which the cell passes all of
  R, and whether the nominal map passes.
* `regret`: per S, D* = argmax over D of nominal Sun+Earth %; regret_k = max_D m_k(D) − m_k(D*); reported as
  the max over k, plus the clone that gives it. Within this design set and these 20 maps only.
* `decision_changes`: per D, the share of starts where 0 < k < 20 under the team preset (the verdict depends on
  which map is true), and the flag at the 2026-11-14 start.

Requirement presets (R): `team` = Sun ≥ 70 %, Sun+Earth ≥ 40 % (team requirement, `web/src/bundle/requirements.ts`)
and longest Sun gap ≤ 120 h (research `all3`, `step12_more.py`); `strict` = 80 / 50 / 72 h; `loose` = 60 / 30 / 168 h.

## 5. Solver and assumptions

* Numerical authority is Python (`science/skyline.compute_skyline`, float64 heights). The cube builder uses a
  batched, bit-identical form (`science/cube/compute.multi_skyline`) that shares ray geometry and far-field
  samples across maps and masts at one position; `science/tests/test_cube.py` checks equality.
* Terrain: PGDA 78 5 m tile (nominal or clone k) to the tile's inscribed radius, PGDA 90 80 m beyond, to 280 km,
  720 azimuth bins, 1 m near-field ray step. Observer = near-DEM ground + mast.
* Ephemeris: JPL Horizons hourly 2026-11-14 00:00 → 2027-11-28 00:00 UTC (9097 samples), same query as the
  bundles; cached under `data/cache/cube_horizons/` with SHA-256. The first 337 samples equal the bundle samples
  exactly (test).
* Position offsets: grid metres in the polar stereographic frame (dx, dy ∈ −100…100, 25 m step). Ephemeris at an
  offset is the centre direction re-expressed in the offset site's local ENU; parallax over ≤ 142 m is
  < 2.2 × 10⁻⁵ ° for Earth and negligible for the Sun.
* Visibility: target centre above the skyline (perpendicular margin > 0), as the bundles. Gaps are runs of hidden
  hourly samples × 1 h; the bundles' bisection-refined gaps are kept in the bundles.
* Not power, not a DSN link, not a probability.

## 6. Baseline round-trip

`data/cubes/site04_roi3/index.json` → `baseline`: the cell (nominal, mast 1 m, start 2026-11-14 00:00) must equal the
bundle `site04_roi3_2026-11-14_14d_mast1m.json` hourly-sample metrics: Sun 94.362 %, Sun+Earth 72.107 %,
longest Sun gap 19 h (bundle bisected 19.44 h); clone range of Sun % 87.54–97.33 %. Enforced by
`science/tests/test_cube.py` and `web/tests/unit/scenarioCube.test.ts`.
