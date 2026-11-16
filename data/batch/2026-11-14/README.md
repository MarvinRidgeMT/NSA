# Spare-computer batch run, 14 Nov 2026 (polaris_batch, full mode + Certainty Height)

All numbers: SOURCE-BASED UNVALIDATED. NASA PGDA 78 (5 m LOLA tiles + 100 published clones), PGDA 90
(LDEM 80 m), PGDA 69 (18.6-yr average Sun / Earth visibility), JPL Horizons. Run by Claude in the cloud workspace
on Sid's behalf (the PC is the "spare computer"; the bash runner does not run natively on Windows).
Code used: `code/` (polaris_batch with the changes below). Tests: `python -m pytest -q code/tests` → 7/7.

## Changes to polaris_batch for this run (vs claude/POLARIS_BATCH_SOURCE.md as of 11:28 ET)
Made in parallel with the strategy/batch session's package **v2** (12:55 ET, `POLARIS_BATCH_SOURCE` + `_PART2`). Site04 ROI3
results are identical to v2's cloud run (claude/BATCH_RESULTS_CLOUD_2026-11-14.md). Difference: v2 also uses the 1 m step for
the PGDA 69 fine variant; this run used 5 m there. Full report: claude/BATCH_RESULTS_THIRD_2026-11-14.md.
> E1 (15 Nov 2026), Site04 RoI 3 1 m batch-v2 values quoted above (93.77 / 71.22 / 87.2–97.0): float32 heights, superseded by the float64 rerun (94.36 / 72.11 / 87.54–97.33).

1. **Converged near-field ray step.** `compute_horizon(..., near_fine_step, near_fine_m)`; the clone sweep
   uses 1 m out to 1 km, then the 5 m pixel (`--near-fine-step 1 --near-fine-m 1000`, the new defaults).
   At Site04 ROI3, 1 m mast, nominal DEM: 5 m step → 95.0 % Sun (the earlier BATCH_RUNS value), 1 m → 93.8 %.
   The PGDA 69 jobs keep the 5 m step (they compare 18.6-yr averages against a 60 m product).
2. **Download size check.** `core.download` now compares the bytes written with Content-Length. A truncated
   Site04 clone 0019 (11 MB of 41 MB) crashed the first sweep attempt; it was re-fetched and verified.
3. Clone sweep rows add `longest_sun_gap_steps` (longest run of hours with the Sun centre blocked).

## 1. Clone sweep: 11 ROIs (Site01, Site04) × nominal + 20 clones × masts 1, 5, 10 m (`clone_sweep/`)
Window 2026-11-14 00:00 → 11-28 00:00 UTC, 1 h (337 samples, both endpoints included). Sun = centre above skyline.
Verdict columns use illustrative thresholds (Sun ≥ 70 %, Sun+Earth ≥ 40 %), NOT mission requirements.

| ROI | 1 m mast: Sun % clones min–max (nominal) | 1 m: Sun+Earth % | 5 m: Sun % | 10 m: Sun % (Sun+Earth) |
|---|---|---|---|---|
| Site01 ROI6 | 100–100 (100) | 81.6 | 100 | 100 (81.6) |
| Site01 ROI1 | **61.1–100 (100)** | 61.1–81.9 | 100 | 100 (81.9) |
| Site01 ROI2–5, 7 | 100 | 70.3–81.9 | 100 | 100 |
| Site04 ROI1 | **51.9–69.4 (71.2)** | 4.7–36.5 | 100 | 100 (74.8–75.1) |
| Site04 ROI2 | **58.5–96.4 (80.4)** | 23.1–65.9 | 100 | 100 (76.6–77.7) |
| **Site04 ROI3** | **87.2–97.0 (93.8)** | **62.6–74.8 (71.2)** | **100** | **100 (78.9)** |
| Site04 ROI4 | 100 | 78.6 | 100 | 100 (78.6) |
> E1 (15 Nov 2026), Site04 RoI 3 1 m batch-v2 values quoted above (93.77 / 71.22 / 87.2–97.0): float32 heights, superseded by the float64 rerun (94.36 / 72.11 / 87.54–97.33).

## 2. Certainty Height (queue item 6b): masts 1–15 m × nominal + 20 clones (`certainty_height*/`)
Smallest mast at which the Sun centre is visible 100 % of the window on all 20 clones (same window).

| ROI | 1 m | 1.25 m | 1.5 m | 1.75 m | 2 m | 3–15 m | Certainty Height |
|---|---|---|---|---|---|---|---|
| Site04 ROI3 | 87.2–97.0 | 91.1–100 | 96.1–100 | **100** | 100 | 100 | **1.75 m** |
| Site01 ROI6 | 100 | — | — | — | 100 | 100 | ≤ 1 m |
> E1 (15 Nov 2026), Site04 RoI 3 1 m batch-v2 values quoted above (93.77 / 71.22 / 87.2–97.0): float32 heights, superseded by the float64 rerun (94.36 / 72.11 / 87.54–97.33).

Site04 ROI3 Sun+Earth at 1.75 m: 78.0–78.6 %; at 10 m: 78.9 % on every clone.

## 3. Coverage Gauge (queue item 6c): does "every model" cover the terrain that matters? (`certainty_height/coverage_gauge.json`)
PGDA 78 clones vary only the 5 m tile; terrain beyond the tile's inscribed radius comes from the single 80 m LDEM.
Share of window hours whose Sun / Earth skyline-controlling cell lies inside the clone tile (nominal DEM, 1 m mast):

| ROI | tile inscribed radius | Sun | Earth |
|---|---|---|---|
| Site04 ROI3 | 6.3 km | 34.1 % | 58.5 % |
| Site01 ROI6 | 7.7 km | 11.0 % | 0.0 % |

At Site04 ROI3 every Sun-blocked hour (21 h at 1 m) is controlled by terrain 15–17 m away, inside the tile, so the
clone spread is meaningful for the blocking. At Site01 ROI6, "all clones agree" mostly reflects far terrain that the
clones do not change. Say "every NASA terrain model tested (5 m tile)", not "every possible terrain".

## 4. PGDA 69, 17 ROIs, 2026-01-01 → 2044-08-08 at 6 h, 1 m mast (`pgda69_rois/`)
| Variant | Sun ρ | Sun bias / RMS (pts) | Earth ρ | Earth bias / RMS (pts) | Best Sun ROI ours vs NASA |
|---|---|---|---|---|---|
| fine (5 m + 80 m) | 0.505 | +4.0 / 10.1 | 0.882 | +3.0 / 4.4 | Site01 ROI6 = Site01 ROI6 |
| coarse (80 m) | 0.488 | +5.0 / 10.9 | 0.887 | +3.2 / 4.6 | Site01 ROI6 = Site01 ROI6 |

Single-pixel ROI comparisons are noisy (PGDA 69 varies 14–75 % within 180 m on ridges); use the grid below.

## 5. PGDA 69 map grid: 4 sites × 21 × 21 PGDA 69 pixels (stride 120 m), same 18.6-yr window (`pgda69_grid/`)
| Site | Sun ρ fine (coarse) | Sun bias, median abs diff (pts) | Earth ρ fine (coarse) | Earth median abs diff |
|---|---|---|---|---|
| Site01 | 0.787 (0.765) | +0.5, 2.9 | 0.939 (0.930) | 0.07 |
| Site04 | 0.927 (0.927) | −2.4, 3.2 | 0.862 (0.871) | 1.39 |
| Site07 | 0.715 (0.705) | +0.1, 3.4 | 0.900 (0.895) | 0.81 |
| Site11 | 0.740 (0.732) | −2.4, 3.0 | 0.981 (0.980) | 0.03 |

Outliers: single PGDA 69 pixels near 0 % where POLARIS gives 30–50 % (visible as isolated black pixels in NASA's map in
`pgda69_grid_maps.png`). Hypothesis (unchecked): pits in the 2016 60 m DEM behind PGDA 69 that are not in PGDA 78/90.

## Independent reproductions
- claude/BATCH_RESULTS_CLOUD_2026-11-14.md (strategy session, package v2): Site04 ROI3 hero + Certainty Height identical.
- claude/BATCH_RESULTS_FULL_2026-11-14.md (second chat on this PC, 13:20 ET): v2 sweep for all 11 ROIs and the PGDA 69
  18.6-yr grid/ROI results identical to the tables above.
> E1 (15 Nov 2026), Site04 RoI 3 1 m batch-v2 values quoted above (93.77 / 71.22 / 87.2–97.0): float32 heights, superseded by the float64 rerun (94.36 / 72.11 / 87.54–97.33).

## Provenance
- `horizons_raw/`: the 22 raw JPL Horizons responses for the 14-day runs, with `MANIFEST.json` (SHA-256).
- The 210 raw responses for the 18.6-yr runs (71 MB) are not committed. Their file names and SHA-256 are in
  `pgda69_rois/summary.json` and `pgda69_grid/grid_summary.json`; a zip is on the PC at
  `data/cache/batch_horizons_raw_18p6yr.zip` (gitignored). Re-running the same command re-fetches identical queries.
- DEM files: paths in each `manifest.json`; all 40 clone files (Site01 + Site04, 0001–0020) were checked readable and complete (Content-Length).
- Commands: see `run.log` / `manifest.json` in each folder.
