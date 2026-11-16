# 5D upgrades — status (branch `feature/5d-upgrades`, worktree `../NSA-5d`)

Prompt: `CLAUDE_CODE_PROMPT_5D_upgrades.md` (roadmap in `claude/5D_MODEL_RESEARCH_2026-11-15.md`). Started 15 Nov 2026 ~22:00 EST
at Anish's request, before the submission deadline, in a separate worktree so no other checkout was touched.

| Phase | Status | What was done | Tests | Results | Open items | Time |
|---|---|---|---|---|---|---|
| 1 Scenario cube | **done (UI partial)** | Schema + contract; `science/cube/` builder; 3 cubes per site + index; robust outputs (band over T, k of 20 × 3 R presets, regret, decision-changes); TS loader/validator/slicer; `CubeSlicer` on Decision page | `test_cube.py` (schema, round trip, baseline, 10-cell slices vs scalar recomputation, solver bit-identity, mast monotonicity, band/k/regret brute force, < 20 MB); vitest `scenarioCube.test.ts`; Playwright `cube-slicer.spec.ts` | Site04 RoI 3 baseline 94.36 % / 72.11 % / 19 h, clones 87.54–97.33 % (identical to bundle) | Small multiples site × mast; Decision Card rows per sub-axis; NetCDF/Zarr copy; Site07/11 and site04_roi4 (no local clone set) | ~2.5 h (half of it waiting on a CPU shared with another session's batch) |
| 2 Terrain safety | **done (UI partial)** | LSQ plane-fit slope at 5/25/100 m for nominal + 20 clones; per-cell median/max; landing (100 m) and EVA (25 m, 2 km region) metrics; R_slope axis 10° / 8°; safe-and-lit derived block; Barker comparison | `test_slope.py` (synthetic planes ±0.1°, flat = 0, NaN edges, Shackleton wall > 20°, RoI 3 < 10°) | see below | Map layer on position grid / polar map; Decision Card row; editable thresholds in UI (presets only now) | ~0.5 h |
| 3 Visibility rule | not started | — | — | — | Reuse L1 (any/centre/full) as R sub-axis | — |
| 4 Link targets (DSN, LCRNS) | not started | — | — | — | Station codes from Horizons docs; LCRNS states from NTRS 20250002698 | — |
| 5 Energy margin | **done (ENGINEERING ASSUMPTION)** | `science/energy/` P = S·A·η·f_disc·cos(inc), S = 1361 W/m² × (1 au/r)² from the cached Horizons year ephemeris, f_disc = Phase 3 hourly Sun disc fraction at the array top; array types VSAT-style tracking (cos el) and fixed vertical (auto azimuth = best year-mean on nominal 1 m: 264° Site04, 267° Site01); battery SoC simulation with YAML parameters (`science/energy/assumptions.yaml`, shown on screen); battery needed by vectorised bisection; `energy.json.gz` T(21) × D_array(2) × D_mast(10) × S(366 daily 14 d windows) + derived band over T, k of 20 at the YAML capacity, trade, needed-by-k; `EnergyTrade` panel (display only) | `test_energy.py` 16 (conservation on both ledgers, more battery → fewer hours below reserve and monotone feasibility, zero load, always lit closed form, always dark closed form, vectorised = scalar, antenna height bit-identical, schema + index, cube cells = fresh recomputation); vitest `energyCube.test.ts` | Battery needed, VSAT, nominal / worst of 20 (kWh). 2026-11-14 start: Site04 1 m 3.13 / 8.89, 5 m 0 / 0; Site01 1 m 0 / 0, 5 m 0 / 0. Every daily start over 12 months: Site04 1 m 71.0 / 73.7 (73.7 = zero-generation bound), 5 m 13.9 / 13.9; Site01 1 m 33.9 / 50.2, 5 m 20.2 / 21.6. Fixed vertical face: 29.2 (Site04) / 38.8 (Site01) at the demo start and 73.7 for some start at every mast (whole windows with the Sun behind the face) | Load, array and battery numbers are illustrative; no thermal derating, dust, degradation or lander self-shadowing; windows start at the initial SoC independently; Decision Card energy row not added | ~1 h |
| 6 Dispersion × terrain | not started | — | — | — | Reuse L9 and research `more.json` ellipse | — |
| 7 Sensitivity + emulator | not started | — | — | — | — | — |
| 8 Multi-asset layout | not started | — | — | — | — | — |
| 9 Detail upgrades | not started | — | — | — | — | — |
| 10 Design docs | not started | — | — | — | Needs Sid's and Anish's go-ahead | — |

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
```
Inputs that stay out of git: NASA rasters (`data/cache/`), Horizons responses (`data/cache/cube_horizons/`, SHA-256 in the cube provenance).
