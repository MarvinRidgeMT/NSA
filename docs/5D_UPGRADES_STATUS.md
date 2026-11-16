# 5D upgrades — status (integration branch `feature/5d-complete`, worktree `../NSA-5d`)

Branches: Phases 1–4, 8, 9.1–9.3 and 10 were committed on `feature/5d-upgrades`; `feature/5d-complete` was cut from its tip
(75f470e) at Anish's request and holds all later commits and the merges of the per-phase session branches
(Phase 5 `feature/5d-phase5-energy` 7383446; Phase 9.4 `5d-phase9-lod` 3eaac54; Phase 7 pending). The alternative Phase 5 branch `5d-phase5-energy`
(e1e27b0) is not merged. Nothing is pushed.

Prompt: `CLAUDE_CODE_PROMPT_5D_upgrades.md` (roadmap in `claude/5D_MODEL_RESEARCH_2026-11-15.md`). Started 15 Nov 2026 ~22:00 EST
at Anish's request, before the submission deadline, in a separate worktree so no other checkout was touched.

| Phase | Status | What was done | Tests | Results | Open items | Time |
|---|---|---|---|---|---|---|
| 1 Scenario cube | **done (UI partial)** | Schema + contract; `science/cube/` builder; 3 cubes per site + index; robust outputs (band over T, k of 20 × 3 R presets, regret, decision-changes); TS loader/validator/slicer; `CubeSlicer` on Decision page | `test_cube.py` (schema, round trip, baseline, 10-cell slices vs scalar recomputation, solver bit-identity, mast monotonicity, band/k/regret brute force, < 20 MB); vitest `scenarioCube.test.ts`; Playwright `cube-slicer.spec.ts` | Site04 RoI 3 baseline 94.36 % / 72.11 % / 19 h, clones 87.54–97.33 % (identical to bundle) | Small multiples site × mast; NetCDF/Zarr copy; Site07/11 and site04_roi4 (no local clone set). Decision Card rows per sub-axis: done (`decision_summary.json`) | ~2.5 h (half of it waiting on a CPU shared with another session's batch) |
| 2 Terrain safety | **done (UI partial)** | LSQ plane-fit slope at 5/25/100 m for nominal + 20 clones; per-cell median/max; landing (100 m) and EVA (25 m, 2 km region) metrics; R_slope axis 10° / 8°; safe-and-lit derived block; Barker comparison | `test_slope.py` (synthetic planes ±0.1°, flat = 0, NaN edges, Shackleton wall > 20°, RoI 3 < 10°) | see below | Safe-and-lit grid panel and Decision Card row: done. Polar-map layer not done; thresholds are presets (10°/8°), not free-text | ~0.5 h |
| 3 Visibility rule | **done** | R_vis {any_limb, centre, half_disc, full_disc} cube (T × R_vis × D_mast × daily S); hourly visible disc fraction (flat local horizon) | `test_visibility_rule.py` 8 (orderings everywhere, analytic segment fractions, centre slice = existing cube, L1 identity for nominal + 20 clones) | Site04 RoI 3 nominal 1 m: any 97.03 %, centre 94.36 %, full 92.29 %; `half_disc` = `centre` by construction (straight-line horizon) | Curved-horizon disc model | ~0.3 h |
| 4 Link targets (DSN, LCRNS) | **done (ENGINEERING ASSUMPTION)** | DSN DSS-14/25/63/56/43/35 resolved by Horizons, Moon ≥ 10°; LCRNS Reference Constellation 3.1 (NTRS 20250002698) 5 relays propagated (point mass + J2 + Earth + Sun); hourly site frame fitted from Horizons; link cube T × D_mast × target(10) × margin{0,2,5°} × daily S + year summary, model sensitivity, NASA sanity block | `test_link.py` 8 (relay never reduces availability, margin monotone, DSN gate, LRO check < 0.05°, leave-one-out, paper Table 1 ↔ 2 through J2000 frame, occultation) | 12 months, 1 m, nominal: DTE+DSN 50.5 / 52.1 %, + best relay 91.4 / 91.6 %, + best pair 98.14 % (DSN-limited). LRO check 0.0003° max | NASA's GRGM-900c 25×25 force model not available offline; one-relay line of sight 88–89 % at 5° vs NASA 80–86 % | ~1.2 h |
| 5 Energy margin | **done (ENGINEERING ASSUMPTION)** | `science/energy/` P = S·A·η·f_disc·cos(inc), S = 1361 W/m² × (1 au/r)² from the cached Horizons year ephemeris, f_disc = Phase 3 hourly Sun disc fraction at the array top; array types VSAT-style tracking (cos el) and fixed vertical (auto azimuth = best year-mean on nominal 1 m: 264° Site04, 267° Site01); battery SoC simulation with YAML parameters (`science/energy/assumptions.yaml`, shown on screen); battery needed by vectorised bisection; `energy.json.gz` T(21) × D_array(2) × D_mast(10) × S(366 daily 14 d windows) + derived band over T, k of 20 at the YAML capacity, trade, needed-by-k; `EnergyTrade` panel (display only) | `test_energy.py` 16 (conservation on both ledgers, more battery → fewer hours below reserve and monotone feasibility, zero load, always lit closed form, always dark closed form, vectorised = scalar, antenna height bit-identical, schema + index, cube cells = fresh recomputation); vitest `energyCube.test.ts` | Battery needed, VSAT, nominal / worst of 20 (kWh). 2026-11-14 start: Site04 1 m 3.13 / 8.89, 5 m 0 / 0; Site01 1 m 0 / 0, 5 m 0 / 0. Every daily start over 12 months: Site04 1 m 71.0 / 73.7 (73.7 = zero-generation bound), 5 m 13.9 / 13.9; Site01 1 m 33.9 / 50.2, 5 m 20.2 / 21.6. Fixed vertical face: 29.2 (Site04) / 38.8 (Site01) at the demo start and 73.7 for some start at every mast (whole windows with the Sun behind the face) | Load, array and battery numbers are illustrative; no thermal derating, dust, degradation or lander self-shadowing; windows start at the initial SoC independently. Decision Card energy row: added at integration (worst-of-20 battery for every start) | ~1 h (separate session) |
| 6 Dispersion × terrain | **done, provisional field** | Monte Carlo N = 2000 per dispersion (σ99 preset 32.9 m, σ 10/25/50/100 m, 60×20 m ellipse), fixed seed; pass = team visibility AND 100 m slope < limit on each of 20 maps; nearest 25 m cell | `test_dispersion.py` 6 (σ → 0 = point, seed reproducibility, 99 % circle, ellipse axes, outside-field handling, cube consistency) | Share of sampled landing outcomes passing on all 20 maps (10°): Site04 σ99 56.6 %, σ10 90.3 %, σ25 65.7 %; Site01 σ99 80.9 %, σ10 100 %, σ25 89.9 % | Built on ±100 m (σ50: 4 %, σ100: 44.5 % of samples outside, reported); ±200 m field computing; 25 m cells instead of 5–10 m | ~0.5 h + compute |
| 7 Sensitivity + emulator | **in progress (separate session)** | variance decomposition over the cubes; emulator + full-solver re-check | — | — | merge pending | — |
| 8 Multi-asset layout | **done (ILLUSTRATIVE shapes)** | Layouts single / research / bad / 15 m tower; cylinder self-shadowing on each asset's own terrain skyline; joint power + link | `test_assets.py` (antenna behind lander → 0 % Earth on all maps; single layout = point cubes) | 12-month power AND link, nominal: single 39.1 / 45.3 %, research 44.5 / 47.1 %, tower 45.1 / 49.1 % | Layout editor in the UI (presets only) | ~0.4 h |
| 9 Detail upgrades | **done (9.4 in its own row)** | 9.1 9 m pad footprint (centre + corners, worst/best); 9.2 heights 1.0/1.7/2.0/4.5/15 m; 9.3 launch calendar (365 dates × 24 slip hours, k of 20) | `test_assets.py` (pad centre = point, taller never sees less Sun), `test_cube_views.py` (calendar re-index identity), Playwright `cube-views.spec.ts` | Site04 pad 12-month Sun worst/best corner 63.7 / 78.5 %; heights 12-month Sun 73.8 (1 m) → 87.7 % (15 m); days with an all-20 start hour (1 m): 62 / 154 of 365 | — | ~0.5 h |
| 9.4 Near field ±7 km at 5 m (LOD display) | **done** (branch `5d-phase9-lod`) | `tools/terrain/build_lod_tiles.py` cuts the PGDA 78 5 m tile (via `science.sites.near_dem`) into a 5-level quadtree (80/40/20/10/5 m, 175-cell tiles, 127 KB each, 341 per site) around site04_roi3 and site01_roi6 → git-ignored `web/public/context/lod/<site>/` with a manifest (source URL, SHA-256, level, bounds, per-tile SHA-256); `LodTerrain` streams tiles by camera distance through Web Workers; opt-in toggle “Near field ±7 km · 5 m” (or `?lod=1`) with the on-screen statement “display only · solver numbers unchanged, never computed from these tiles” | `science/tests/test_lod_tiles.py` (8: exact tiling per level, 5 m nodes bit-identical to the source, coarse = box mean, shared edges, NaN never filled, ≤ 2 MB, built tiles vs solver DEM and vs the bundle's 5 m crop within 1 mm); vitest `lodTiles.test.ts` (9: level per distance, no gaps/overlaps incl. while streaming, ≤ 2 MB, validator); Playwright `lod-near-field.spec.ts` (2) | p95 frame 4.4 ms worst phase with the layer on (headless Chrome, Metal, M5 Pro, vsync off; `docs/PERFORMANCE_REPORT.md`); Site04 RoI 3: 4.8 % of the ±7 km square lies west of the PGDA 78 tile and is not drawn | Full-run measurement in the visible Claude pane (pane was hidden this session); no cast shadows on the LOD layer; no 80 m context beyond ±7 km while it is on | ~1.5 h |
| 10 Design docs | **done (docs only)** | `docs/design/THERMAL_MODEL.md`, `docs/design/TRAVERSE_PLANNER.md` | — | — | Implementation needs Sid's and Anish's go-ahead | ~0.2 h |

## Headline numbers so far (SOURCE-BASED · UNVALIDATED; k of N is not a probability)

| | Site04 RoI 3 | Site01 RoI 6 |
|---|---|---|
| Starts (of 8761 hourly) passing team R on all 20 maps, 1 m / 5 m / 10 m mast | 15.8 % / 48.0 % / 48.9 % | 39.9 % / 50.6 % / 55.4 % |
| Worst-map longest Sun gap over all starts, 1 m / 5 m / 10 m | 337 h / 69 h / 68 h | 252 h / 112 h / 102 h |
| Share of starts where the verdict depends on the map (1 m) | 24.2 % | 6.3 % |
| Position regret on Sun+Earth (daily starts): median / max | 0.00 / 40.4 pct pts | 9.2 / 89.0 pct pts |
| Positions (of 81) whose demo-start verdict depends on the map | 12 | 16 |
| Landing slope < 10° on all 20 maps | 54 / 81 cells | 73 / 81 cells |
| Safe (< 10°) and lit on all 20 maps, demo window | 29 / 81 cells | 39 / 81 cells |
| EVA region (2 km) with 25 m slope < 20° | 56.3 % | 97.9 % |
| Slope clone spread (median std) at 5 m baseline vs Barker 1.5–2.5° | 1.26° | 1.73° |

Notes
- Many starts fail team R on every map because Sun+Earth ≥ 40 % needs Earth above the horizon, which it is for only part of each month.
- Site01's 89-point maximum regret is a knife-edge, not a bug: at the 2027-01-10 start the nominal-best cell (−50, −25) keeps
  Sun+Earth at 99 % on the nominal map but 10 % on clone 17, while the cell 25 m away keeps 99 %.
- The M-axis cube uses the research SfS result only where `sfs_meta.json` reports full tile coverage (Site01). Site04's SfS
  coverage is 25.8 % of the tile, so its SfS cell is marked missing with that reason.
- Cross-check: the cube's 12-month mean nominal Sun % at 1 m is 73.65 % (Site04) and 85.17 % (Site01); the research strip gives
  73.82 % and 85.1 % (straight hourly mean rather than window mean).

## Reproduce
```
python -m science.cube.compute site04_roi3 site01_roi6     # skylines -> data/cache/cube_sky (CUBE_WORKERS, default 6)
python -m science.cube.build_cube site04_roi3 site01_roi6  # cubes -> data/cubes/<site>/
python -m science.cube.build_safety site04_roi3 site01_roi6
python -m science.cube.build_visibility; python -m science.cube.build_link; python -m science.cube.build_calendar
python -m science.cube.compute site04_roi3 site01_roi6 --points "0,0,1.7,4.5,15;0,5,1,2;0,-5,2;0,10,15;4.5,4.5,1;4.5,-4.5,1;-4.5,4.5,1;-4.5,-4.5,1"
python -m science.cube.build_assets
python -m science.cube.compute site04_roi3 site01_roi6 --grid 200 25; DISPERSION_HALF_M=200 python -m science.cube.build_dispersion
python -m science.energy.build_energy; python -m science.cube.build_summary   # summary last
```
Inputs that stay out of git: NASA rasters (`data/cache/`), Horizons responses (`data/cache/cube_horizons/`, SHA-256 in the cube provenance).
