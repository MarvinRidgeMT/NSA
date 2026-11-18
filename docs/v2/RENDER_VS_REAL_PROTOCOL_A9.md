# Render-vs-real protocol — Amendment A9 (ShadowCam: outcome of the A8.4 pipeline test)

Written 17 Nov 2026 by the coordinating session (Claude), after the A8.4 pipeline test and **before any ShadowCam dev-pilot
row is scored**. Registered in `docs/v2/PREREGISTRATION.md` (Entry 10).

## A9.1 Pipeline test
- **Data:** 6 dev rows: 3 TDI A (site04_roi3, site07_roi1, site11_roi4) and 3 TDI B (site04_roi3, site01_roi6 ×2), all with
  the Sun ≥ −0.5°.
- **Method:** PGDA 78 with Hapke, one rigid registration over ± 2,000 m. Every number is in
  `tools/validation/render_vs_real/results_shc/pipeline_test.json`.

| question | convention | median offset (n) | per-row offsets m | NCC |
|---|---|---|---|---|
| start time | `isis` (SCLK ExecutionSpacecraftTime + StartTimeOffset) | 21.3 m (3, TDI A) | 13.5, 21.3, 22.2 | 0.53–0.64 |
| start time | `label` (start_date_time) | 94.4 m (3, TDI A) | 57.3, 94.4, 136.9 | 0.53–0.64 |
| TDI B sample axis | no flip (ISIS camera) | 33.3 m (3) | 33.3, 18.0, 40.9 | 0.47–0.67 |
| TDI B sample axis | flipped (ALE driver) | 1,860.6 m (3) | 1,860.6, 1,332.5, 2,059.7 | 0.11–0.27 |

## A9.2 Decisions (the A8.4 rule, applied as written)
- **TDI B: resolved, no flip.** The no-flip median (33 m) is below 150 m and the flipped median (1,861 m) is above
  600 m.
  - TDI-B rows enter the pilot with the ISIS camera unchanged.
  - The ALE driver's sample flip disagrees with these images. That is reported here as a finding, not acted on.
- **Start time: not resolved by the rule, so the `isis` convention is kept, as A8.4 prescribes.**
  - `isis` is better on 5 of 6 rows (21 m against 94 m, TDI A), but the `label` median does not exceed 600 m, so the rule
    calls it unresolved.
  - Both conventions lie inside the registration search of ± max(3 binned px, 150 m), so the registered metrics do not
    depend on the choice. The unregistered ones can, and are reported as such.
- **No other parameter changes.** Everything else is as A8.5.

## A9.3 Use of the test
- **Not scores:** the test renders are not dev-pilot scores and enter no aggregate.
- **Overlap with the pilot:** the 6 rows may also be in the pilot sample. If so, they are scored there through the normal
  pipeline like every other row.
