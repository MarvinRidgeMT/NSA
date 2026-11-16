# Scientific result consistency (Final Apex P8)

15 Nov 2026, Penumbra session. Scope: Site04 ROI3, ROI export bundle `polaris-x5d-roi-2026-11-14-v2.json`
(SHA-256 `5b93dd66c3177d6098531f1261d565b3089101bd58f4d9a38d8ffb617b9cf51f`). Batch values come from `web/public/certainty/sidecar.json`
and `coverage.json`, which are copies of the a-science batch files whose hashes are listed on the Evidence page.
Status: **SOURCE-BASED · UNVALIDATED**. This audit checks that the viewer shows the same number everywhere, with the right label.
It does not validate the science.

Method:
1. Each value was recomputed in Python directly from the bundle/sidecar JSON.
2. It was compared with the text the built app shows: `vite preview`, all `<details>` opened, `innerText` of Explore, Decision and Evidence.
3. The comparisons that matter most are pinned in browser tests: `final-apex.spec.ts`, `visual-final.spec.ts`, `apex.spec.ts` and `guided-demo.spec.ts`.

## Identity, time and conventions

| Quantity | Bundle / sidecar | Shown | Where | Agrees |
|---|---|---|---|---|
| Site point | −89.78012°, −156.32023° (ROI polygon centroid, not a surveyed touchdown point) | 89.78012° S · 156.32023° W, with the coordinate role on Evidence | stage title, Evidence record | yes |
| Masts | baseline 1 m, mast10 10 m (bundle); sampled 1, 1.25, 1.5, 1.75, 2, 3, 5, 7, 10, 15 m (batch) | same; chips only at sampled heights; "no bundle time series at 1.75 m" note | instrument, Decision | yes |
| Window | 337 samples, 60 min, 2026-11-14T00:00Z → 2026-11-28T00:00Z | "337 samples … (336 h, 336 intervals)" | time bar, Evidence record | yes |
| Azimuth convention | clockwise from local north (N=0, E=90); airless apparent target-centre az/el; UTC | stated in Evidence → Solver, schema and conventions | Evidence | yes |

**337 vs 336.** The 337 hourly samples bound 336 one-hour intervals. The viewer now states this once, next to sampling. Two kinds of number use these differently:
- **Per-sample tallies** (strips, failures list, ridge hours, the batch) count samples.
- **Bundle window metrics** (Sun 94.213 %, longest obstruction 19.44 h) are fractions or durations of the 336 h window, computed from refined crossing times (the bundle's scenario description says so).

Both are labelled, and neither is converted into the other.

## Values at specific samples

| Quantity | Bundle | Shown | Agrees |
|---|---|---|---|
| Sample 0, Sun | az 282.932°, el +1.606°, margin +3.386°, visible | 3D label "az 282.9° · el +1.61° · +3.39° vs skyline"; instrument "+3.39°, az 282.9° · el +1.61°" | yes (test P5) |
| Sample 0, Earth | az 155.086°, el −4.848°, margin −4.167°, blocked, skyline R1 at 127.7–129.6 km (80 m DEM) | "−4.17° vs skyline … skyline: R1, 127.7–129.6 km · beyond this crop" | yes (test P5) |
| Sample 311 (2026-11-26T23:00Z), Sun | blocked; horizon 1.41325°, margin −0.03998°, first hit 16 m; ridge R3 | blocked; margin −0.04°; R3 | yes (test P3 opens this sample by link) |

## Window results, 1 m mast

| Quantity | Value | Source label on screen | Agrees |
|---|---|---|---|
| Sun visible (window) | 94.213 % | BUNDLE | yes |
| Sun visible (samples) | 318 / 337 = 94.36 % (19 blocked) | per-sample strips / failures "19 samples" | yes |
| Sun visible, batch nominal | 93.8 % | BATCH SWEEP ("nominal 93.8 %") | yes |
| Bundle vs batch | 19 vs 21 blocked samples (2 knife-edge samples); (337 − 21)/337 = 93.77 % | explained in the Decision source legend and Certainty Height method note | yes |
| Earth visible | 77.699 % window; 75 blocked samples; longest Earth obstruction 74.93 h (one run) | BUNDLE | yes |
| Longest Sun obstruction | 19.44 h (window) = one run of 19 samples | metrics 19.4 h; failures "19 samples" | yes |
| Ridge attribution | R3: 19 Sun samples; R1: 41 and R2: 34 Earth samples; sums 19 and 75 equal the blocked tallies; 60 clusters | ridge list and Evidence table ("hourly bundle samples", "loss hours do not overlap") | yes |
> E1 (15 Nov 2026), Site04 RoI 3 1 m batch-v2 values quoted above (93.77 / 71.22 / 87.2–97.0): float32 heights, superseded by the float64 rerun (94.36 / 72.11 / 87.54–97.33).

## Certainty Height and coverage (batch sidecar)

| Quantity | Sidecar | Shown | Agrees |
|---|---|---|---|
| 1 m, Sun centre | 87.2–97.0 %, nominal 93.8 %, 20/20 pass ≥ 70 % | hero, card, instrument | yes |
| 1 m, Sun + Earth | 62.6–74.8 %, 20/20 pass ≥ 40 % | hero, card | yes |
| Lowest height meeting the team requirements on all 20 | 1 m (both pass counts "20/20") | "Meets the team requirements on all 20 · 1 m" | yes |
| Lowest with Sun 100 % on all 20 (Certainty Height) | `all_maps_100pct_sun_mast_m` = 1.75 m | "1.75 m" | yes |
| Agreement height (Sun spread ≤ 1 pt) | `agreement_mast_m` = 1.75 m | "Agreement height · 1.75 m"; "three different questions; here the last two fall on the same sampled height" | yes |
| 1.75 m, Sun + Earth | 78.0–78.6 % | hero | yes |
| Best Sun + Earth at any sampled mast | 78.9 % (10 m, 15 m) | "≤ 78.9 %" | yes |
| Coverage | Sun 34.1 %, Earth 58.5 % of window hours, at 1 m | next to the Certainty Height verdict, on the card (with the < 50 % warning), coverage gauge | yes |
> E1 (15 Nov 2026), Site04 RoI 3 1 m batch-v2 values quoted above (93.77 / 71.22 / 87.2–97.0): float32 heights, superseded by the float64 rerun (94.36 / 72.11 / 87.54–97.33).

## Wording rules checked

- Centre ≠ disc: "Centre-of-disk geometric visibility" next to the readouts; the PGDA 69 reference says "any part of the disc".
- Earth ≠ communications link; visibility ≠ power; agreement ≠ probability: each appears on Decision, the card and Evidence.
- No silent zeros: missing values show "—" or "not in bundle". The only zeros shown are real ones, e.g. longest Sun obstruction 0.0 h at 10 m.
- Status reads SOURCE-BASED · UNVALIDATED in the header, the card, Evidence and the footer. The one open gate is shown by name: `independent-illumination-comparison`, NOT_RUN.

## Not covered here

- Site01 ROI6 and Site04 ROI4 were not audited value by value; the same code paths serve them.
- No check of the science itself. Session A's SVS 4930 comparison (`docs/validation/SVS4930_RESULT.md`) is a separate, low-discriminating-power check and does not change the status.

## Change log
- 15 Nov 2026 01:40 EST (Penumbra session): created.
