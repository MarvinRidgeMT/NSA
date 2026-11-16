# Science label audit (Penumbra Apex)

Date: 14 Nov 2026, EST. Scope: every user-visible sentence in `web/src` that states a result, a source or a limit.
Status of all numbers: **SOURCE-BASED · UNVALIDATED** (no independent validation of the solver yet).

## Verified against source data
| Claim on screen | Source | Value |
|---|---|---|
| Sun centre visible (bundle) | results bundle, repo solver, interval-based | 94.213 % (hourly 94.362 %) |
| Sun + Earth (bundle) | same | 71.912 % (hourly 72.107 %) |
| Sun-blocked hourly samples (bundle) | same, 2026-11-26T23:00 → 11-27T17:00 | **19**, contiguous, all attributed to R3 |
| Batch nominal at 1 m | batch sweep CSV (a-science 971df9a) | 93.769 % = 316/337 → **21** blocked hours |
| Longest Sun obstruction | bundle | 19.4434 h (time-weighted, interval crossings) |
| 1 m range across 20 realizations | certainty sidecar | Sun 87.24–97.03 %, Sun+Earth 62.61–74.78 %, pass 20/20 |
| Lowest sampled mast with Sun 100 % on all 20 | sidecar `all_maps_100pct_sun_mast_m` | 1.75 m (independently re-derived in VALIDATION_CHECKS) |
| Coverage | coverage sidecar | Sun 34.1 %, Earth 58.5 % of window hours (nominal DEM, 1 m) |
| R3 | bundle attribution | 12–169 m, az 78–144°, +1.563 m vs site ground, 5 m DEM, Sun 19 h |
| R1 | bundle attribution | 127.7–129.6 km, az 153–156°, +3232 m, 80 m DEM, Earth 41 h; never drawn in the 2 km crop |

19 vs 21: the bundle (repo solver) and the batch (separate solver) differ by two knife-edge hourly samples (A_SCIENCE_STATUS 13:06). The UI now labels every number `bundle` or `batch sweep` and says the two sample differently.

## Wording changes
| Before | After | Why |
|---|---|---|
| "NASA publishes 20 equally plausible versions of this terrain" | "NASA's PGDA 78 product includes alternate realizations of this terrain that reflect its elevation uncertainty; we evaluated 20 of them… They do not exhaust what the real ground could be." | "Equally plausible" is not a claim the product makes; agreement ≠ certainty. |
| "20 alternate NASA terrain maps" / "N maps tested" / "alternate maps" (Story, Decision Card, Certainty Height, Coverage, ridge notes, mast instrument) | "evaluated alternate (NASA) terrain realizations" / "realizations tested" | User brief wording. |
| "of Sun hours decided by terrain the maps vary" | "of window hours whose Sun horizon lies in the varied tile" | Coverage is over all window hours, not Sun hours. |
| "every hour without Sun is decided by a rise…" | "the bundle attributes every Sun-blocked hourly sample (19) to one rise…" | Names the quantity (hourly samples) and its source. |
| "19 h of Sun lost" | "19 Sun-blocked hourly samples attributed to it (bundle attribution, repo solver)" | Samples ≠ time-weighted hours. |
| Decision card: "keeps the Sun on all 20 tested maps" | "keeps the Sun centre in view on all 20 evaluated alternate terrain realizations"; "team requirement"; "agreement is not certainty" | Centre visibility, team (not NASA) requirement. |

## Distinctions kept on screen
- Geometric centre visibility ≠ power or communications (readouts, mast instrument, guide, decision card).
- Agreement across realizations ≠ certainty or probability (Certainty Height, Coverage, decision card).
- Team requirements (Sun ≥ 70 %, Sun+Earth ≥ 40 %) ≠ NASA standards.
- Imported ≠ validated: status badge and card footer "SOURCE-BASED · UNVALIDATED".
- Display-only items labelled: light clamp (on-screen tag), fill light, outline mast at heights with no bundle series, shadows on the context surface.
- No interpolation between sampled mast heights; the 128 km ridge is declared "beyond this 2 km DEM crop", never drawn.

## Change log
| When (EST) | Who | Change |
|---|---|---|
| 2026-11-14 20:52 | Claude (Penumbra Apex session) | Created. |

## Scenario cube slicer (5D upgrades Phase 1–2, 16 Nov 2026, branch feature/5d-upgrades)
Component `web/src/components/CubeSlicer.tsx`; every value is a slice of `data/cubes/<site>/*` (built by `science/cube/`).
The panel and card carry `data-source="scenario cube <cube_id>"` and `data-label="SOURCE-BASED · UNVALIDATED"`.

| Claim on screen | Source | Check |
|---|---|---|
| "{metric} · this cell" (e.g. 72.11 % at nominal, 1 m, 2026-11-14) | cube metric × declared scale (count/337) | equals bundle hourly-sample metric (test_cube round trip; Playwright cube-slicer) |
| "T · range over 21 maps" | `derived.band_over_T` min/max | brute-force min/max over T (test_cube) |
| "R · clone maps passing: k of 20 maps" | `derived.k_of_N` | recount from cube metrics (test_cube); wording never says probability |
| "D · regret if chosen on nominal" (pct pts) | `derived.regret` | brute-force argmax/max (test_cube) |
| "D · verdict depends on map: x % of starts" | `derived.decision_changes` | 0 < k < 20, team preset |
| Strip caption "solid = selected map · band = range over T · hatch = missing" | visual grammar | — |
| Requirement presets (team 70/40/120 h; strict 80/50/72 h; loose 60/30/168 h) | team requirement + research all3 gap limit; strict/loose are sensitivity presets | labelled as presets, not mission requirements |
| Products table, "not in source" | `products.json` missing mask with reason | Site04 SfS cell missing (tile coverage 25.8 %) |
| Terrain-safety values (slope °, safe-and-lit k) | `terrain_safety.json`; thresholds 10° / 8° / 20° are ENGINEERING ASSUMPTION | test_slope synthetic planes ±0.1° |

## Energy trade view (5D upgrades Phase 5, 16 Nov 2026, branch feature/5d-phase5-energy)
Component `web/src/components/EnergyTrade.tsx`; every value is a cell of `data/cubes/<site>/energy.json.gz` (built by `science/energy/`).
Panel `data-label="ENGINEERING ASSUMPTION · inputs SOURCE-BASED · UNVALIDATED"`, badge shows the cube label `ENGINEERING ASSUMPTION`.

| Claim on screen | Source | Check |
|---|---|---|
| Battery needed (kWh), demo start / every start, nominal / worst of 20 | `derived.trade` | equals parent-cube cells (test_energy, vitest energyCube) |
| "k of 20 maps where X kWh holds every start", "% of starts hold on all 20" | `derived.trade.k_ok_all`, `share_starts_ok_all20` | recount from hours_below_reserve; wording never says probability |
| Assumptions line (area, η, azimuth, battery, efficiencies, reserve, initial SoC, load) | cube `fixed`, copied from `science/energy/assumptions.yaml` | test_energy checks fixed = YAML |
