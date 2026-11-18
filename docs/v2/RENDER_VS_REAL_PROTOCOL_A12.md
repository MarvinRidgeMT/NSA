# Render-vs-real protocol — Amendment A12 (Kaguya TC: pipeline-test outcome, before the dev pilot)

Written 18 Nov 2026 by the coordinating session (Claude), after the A11.4 pipeline test and **before any dev-pilot TC
row is scored**. Its SHA-256 and that of `results_tc/pipeline_test.json` are recorded in `docs/v2/PREREGISTRATION.md`
(Entry 13) in the same commit.

## A12.1 Pipeline test (A11.4)
- **Rows:** the 8 registered rows (4 TC1, 4 TC2), each under start `isis` / `label` × flip no / yes, rendered with
  PGDA 78 and Hapke, registered over ± 2,000 m. Every row and offset is in `results_tc/pipeline_test.json`.
- **7 rows readable.** The 8th (TC1W2B0_01_00895S894E3196, site11) failed: its downloaded `.img.gz` is truncated
  (A12.3). It is recorded as failed.

| row (camera, site) | no flip: offset, NCC | flip: offset, NCC | model vs JAXA label corners |
|---|---|---|---|
| 00968S893E2030 (TC1, site04) | 286 m, 0.76 | 826 m, 0.01 | 280 m |
| 00683S896E2170 (TC1, site01) | 249 m, 0.86 | 2,028 m, 0.27 | 243 m |
| 00925S894E1897 (TC1, site01) | 275 m, 0.75 | 2,821 m, 0.07 | 265 m |
| 00841S893E1579 (TC2, site04) | 228 m, 0.59 | 2,642 m, 0.16 | 298 m |
| 01223S897E0119 (TC2, site04) | 292 m, 0.66 | 2,548 m, 0.10 | 327 m |
| 01705S892E1887 (TC2, site01) | 232 m, 0.83 | 1,967 m, 0.19 | 298 m |
| 00823S899E0979 (TC2, site01) | 206 m, 0.85 | 2,478 m, 0.29 | 278 m |

Start `isis`. All 7 rows have satellite moving direction −1.

## A12.2 Decisions (A11.4 rule: adopt below 600 m and at least 2× better than the alternative)
- **Sample axis, moving direction −1: no flip (resolved).** Median 249 m against 2,478 m flipped.
- **Moving direction +1: not settled.** No pipeline-test row had it, so those rows are **gated** with that reason
  (`tc_geometry.FLIP_BY_DIRECTION`). All 19 dev labels downloaded so far are −1.
- **Start time: unresolved.** Medians 224 m (`label`) against 249 m (`isis`), so `isis` is kept as A11.4 says. The two
  conventions trade places from row to row.
- **Registration radius for the pilot:** max(150 m, 3 × 249 m) = **748 m** (`tc_run.REG_RADIUS_M`).
- **A systematic along-track offset.** On every row the real image sits 18–25 lines (≈ 200–290 m) along track from the
  model, close to where JAXA's own label geometry puts it (243–327 m from the model).
  - Its cause is not established. The label metakernels name JAXA's TC IK v4.01; the public IK is `SEL_TC_V01`.
  - The registration absorbs it. **Unregistered metrics will therefore be poor and are reported as such**; the §8
    claim uses registered rows, as for every instrument.
  - The registered offset is reported per row. The offset is a finding about the public camera model, not a fitted
    parameter: nothing is tuned to it.

## A12.3 Code changes since A11 (all found on real files before any dev-pilot score)
1. **DCT padding.** DCT-compressed products pad each line to a multiple of 8 samples after the last detector pixel
   (3,496 samples for detector 297–3788). The parser accepts 0–7 trailing padding samples; the ISIS model, which uses
   `FIRST_PIXEL_NUMBER` only, is unchanged.
2. **Attitude fit.** The SELENE CK interpolates linearly between quaternions about 2 s apart, and some windows carry
   small line-to-line wobbles. One polynomial over a ~13 s TC window often cannot meet the registered gate (1 m, 0.1
   pixel; A1.2/A2).
   - `tc_camera.fit_piecewise` tries one polynomial (degrees 3–11), then 2–16 equal line segments, each under the same
     gate. Seams on the checked row: 0 m in position, ≤ 3 µrad in attitude.
   - The OSL camera chooses the segment by line. **The gate is unchanged.**
3. **Sample crop.** The render and the image window are cropped to the samples whose rays reach the site square plus
   its margin (4.0 instead of 7.2 Mpx on the first row). No metric changes: other pixels never enter the analysis
   window.
4. **Downloads.** DARTS sometimes ends a transfer early without the client noticing. `tc_io` tests the whole gzip
   stream before accepting a file, and `tc_download_list --check` lists damaged files. One truncated copy had reached
   the cache; it was deleted and the removal recorded in the manifest.

## A12.4 Dev pilot
- **Unchanged from A11.5,** with the decisions above.
- **Rows** whose images are missing or damaged when the pilot runs are reported as failed with the reason, and scored
  in a resumed run once they are downloaded again; rows already scored are never re-scored.
- **Unchanged:** the Otsu rule, the metrics, the products, the photometry and the claim rule.
