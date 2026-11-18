# Render-vs-real protocol — Amendment A10 (the held-out run for ShadowCam)

Written 18 Nov 2026 by the coordinating session (Claude), after the ShadowCam dev pilot and **before any held-out ShadowCam
image is fetched, rendered, displayed or scored**. Its SHA-256, and the SHA-256 of every ShadowCam code file the run
executes, are recorded in `docs/v2/PREREGISTRATION.md` (Entry 11) in the same commit. The NAC and WAC files the run imports
are already frozen (Entries 6 and 8). `shc_heldout.py` refuses to start if any registered hash differs.

**State at writing.**
- **Dev pilot as registered (A8.5):** complete, `docs/validation/RENDER_VS_REAL_SHC_DEV_A8.md` (commit c39c722). 149 rows
  scored (120 primary track, 29 secondary), 0 failed, 1 gated at geometry.
- **Dev pilot under the A10 saturation rule:** complete, `docs/validation/RENDER_VS_REAL_SHC_DEV.md` (same 149 rows,
  re-rendered and re-scored; commit d60ca16).
- **Held-out data so far:** catalogue metadata and 828 held-out PDS4 labels, read for the catalogue v2 footprints (A8;
  labels carry times, geometry and settings, no pixels). The ShadowCam download manifest
  (`$POLARIS_DATA/v2/imagery/shc/MANIFEST.jsonl`) lists no held-out cube header and no held-out image line.

## A10.1 Scope
- **Instrument:** ShadowCam (KPLO), CAL radiance, camera model and conventions as A8 and A9 (ISIS start time; TDI B
  without sample flip).
- **This is the single held-out run for ShadowCam.** After it, nothing in the ShadowCam pipeline may change without a new
  amendment that reports both the original and the changed numbers.

## A10.2 Rows
- **Considered:** every `split = heldout` row of catalogue v2 (SHA-256 pinned in Entry 9).
- **Eligible:** the protocol §2 gates on catalogue v2 (`shc_common.eligible`) leave 183 rows / 162 images; 54 of them are
  in the secondary-illumination track (Sun < −0.5° at the site). No sampling.
- **Gates:** then the A8 geometry gate (state-polynomial fit within 1 m / 0.1 binned pixel) and the §3.1 window minimum.
- **Accounting:** every row is reported as scored, gated (with its reason) or failed (with its reason).

## A10.3 The change after the dev pilot: saturated blocks count as lit (protocol §4.1 restored)
- **What A8.5 said:** "Special and saturated blocks leave the window." The wording came from the WAC amendment (A6), where
  saturation is rare.
- **What the frozen protocol says (§3, §4.1):** saturated pixels stay in the window and **count as lit**; the Otsu rule,
  the normalisation, SSIM and the histogram distances use the valid non-saturated pixels only.
- **Why it matters for ShadowCam:** ShadowCam is built to image ground in shadow by scattered light, about 200 times more
  sensitive than the NAC. **Directly sunlit ground saturates.** Dropping saturated blocks therefore removed nearly the
  whole lit class from the window. In the A8.5 pilot the render predicted shadow on 0.99 of what was left, and the fixed
  Otsu rule split scattered-light shadow into two classes (median IoU 0.67, edge 184 m; not met at any site).
- **Dev evidence that saturation is the lit class** (cached dev arrays, PGDA 78, unregistered, 120 primary rows):
  saturated blocks cover a median 40 % of the window against 39 % predicted lit; IoU(saturated, predicted lit) median
  0.91 (P10 0.81); IoU(non-saturated, predicted shadow) 0.95; IoU(saturated, flat-control lit) 0.25.
- **The change:** `shc_run.SATURATION_RULE = 'lit'`. A saturated block (any raw pixel of the b × b block carries the
  ISIS high-saturation code, and none is invalid) stays in the window and counts as lit. It has no radiance, so it takes
  the brightest valid non-saturated value of the window. That value reaches only the registration (NCC), the
  count-matched mask and the gallery; every metric that uses radiance excludes saturated pixels, as §4 prescribes.
  Regression test: `tests/test_shc.py::Saturation`.
- **Registration follows from it.** With saturated blocks in the window, their single fill value dominated the
  Sobel-gradient NCC (first dev try, kept as `results_shc/scores_a10_try1_regwindow.jsonl`: NCC median 0.10, offsets at
  the search bound). Registration therefore uses the window's non-saturated pixels only (`score.register` mask
  `window & ~saturated`), which restores the A8.5 behaviour (NCC median 0.605, offset median 30 m). Regression test:
  `tests/test_shc.py::SaturationRegistrationAndMask`.
- **What did not change:** the Otsu thresholding rule (never tuned, protocol §5), the camera model, grid, binning,
  registration radius, metrics, products, photometry and the claim rule.
- **Both rules are reported on held-out.** Each held-out row is rendered once and scored twice: under the A10 rule
  (`scores.jsonl`, the claim) and under the A8.5 rule (`scores_dropped.jsonl`, a sensitivity record, never the claim).
- **Partial blocks:** a block counts as saturated if any of its b² raw pixels is. This biases the observed lit class
  outward by at most one binned pixel (≈ 5 m) along sunlit edges. It is stated here, not corrected.

## A10.4 What the dev pilot showed under the A10 rule, and the prediction stated before the run
**Claim rows under the A10 rule** (dev, `docs/validation/RENDER_VS_REAL_SHC_DEV.md`, PGDA 78, Hapke, registered,
120 primary-track rows):
- **The §8 claim is not met at any site.** Median shadow IoU 0.57–0.70, edge 118–182 m against a ~10 m limit. Restoring
  the lit class did not change this (A8.5: IoU 0.58–0.72, edge 136–214 m).
- **Why:** the fixed Otsu rule (protocol §5, not tuned) splits ShadowCam's scattered-light shadow, which is not dark.
  Observed shadow fraction median 0.41 against 0.63 predicted; Otsu threshold median log10 0.21, far above the −5 floor.
  The count-matched mask (A5.5), which does not use the threshold, gives shadow IoU 0.94 and lit IoU 0.91.

**Secondary analysis (new in A10; never the claim).** Directly sunlit ground saturates ShadowCam, so the saturation mask
is a threshold-free observed lit class. `shc_run.saturation_metrics` scores it in the same window and with the same
registration: IoU(saturated, predicted lit), IoU(non-saturated, predicted shadow), κ, and the edge distance between the
saturation boundary and the predicted shadow boundary (same `S.edge_errors`). The flat-sphere control is scored the same
way; a missing edge counts as worse than any distance. Dev result per site:

| site | n | IoU(sat, pred. lit) median (P10) | edge median m | limit m | beats flat control: lit IoU / edge |
|---|---|---|---|---|---|
| site04_roi3 | 21 | 0.904 (0.773) | 9.5 | 10.9 | 100 % / 100 % |
| site01_roi6 | 26 | 0.915 (0.840) | 6.6 | 10.9 | 100 % / 100 % |
| site07_roi1 | 56 | 0.943 (0.900) | 7.3 | 10.6 | 100 % / 100 % |
| site11_roi4 | 17 | 0.926 (0.853) | 6.9 | 9.7 | 94 % / 94 % |

Signed edge median 0.0 m; unmatched edge fraction median 0.01. site04 is the weakest (P90 edge 23 m; one row at 129 m
with 68 % of its edges unmatched).

**Prediction for the held-out run, written before any held-out pixel is seen** (PGDA 78, Hapke, registered, primary
track, every site with scored rows; the report checks each item and prints confirmed / NOT confirmed):
- **(a)** The §8 claim fails conditions 1 and 2 at every site, for every terrain product.
- **(b)** Count-matched shadow IoU median ≥ 0.90 over all primary rows.
- **(c1)** Secondary: median IoU(saturated, predicted lit) ≥ 0.85 at every site.
- **(c2)** Secondary: median saturation-edge distance ≤ the §8 edge limit (2 × the median binned pixel) at every site.
- **(c3)** Secondary: PGDA 78 beats the flat-sphere control on ≥ 80 % of rows, for lit IoU and for edge, at every site.

(b) and (c) are not claims; a confirmed (c) would not change the result of the claim. The held-out split has 129
primary-track rows (site01 38, site04 24, site07 49, site11 18), counted from catalogue metadata only.

## A10.5 The §8 claim (rule unchanged from A5.6)
- **Unit:** per site and per terrain product. Rows: registered, Hapke, primary track. Headline product PGDA 78 5 m.
- **Conditions:** (1) median shadow IoU ≥ 0.80; (2) median edge error ≤ 2 × the median binned analysis pixel (~5 m, so a
  limit near 10 m); (3) beats the flat-sphere control on ≥ 80 % of paired rows, for IoU and for edge error.
- **Secondary-track rows** never enter the claim. They are reported on SSIM and the histogram distances only (A8.5).
- **Not a claim:** the A10.4 saturation-mask analysis, count-matched IoU (A5.5), the A8.5-rule sensitivity scores, product and photometry comparisons, and
  every result on the secondary track.

## A10.6 Frozen parameters and code
- **Code:** the ShadowCam files listed in Entry 11, plus the NAC files of Entry 6 and the WAC files of Entry 8. Run by
  `python -m tools.validation.render_vs_real.shc_heldout all --workers 4 --threads 4`.
  - Outputs: `results_shc_heldout/` (ids and numbers) and `$POLARIS_DATA/v2/render_vs_real/shc_heldout/` (git-ignored).
  - Logging: start, stop and commit go to `results_shc_heldout/RUN_LOG.jsonl`.
  - A crash may be resumed; rows already scored are not re-scored.
- **Report:** `POLARIS_SHC_SPLIT=heldout python -m tools.validation.render_vs_real.shc_report` writes
  `docs/validation/RENDER_VS_REAL_SHC_HELDOUT.md`. The report script only formats; it is not frozen, and any change to it
  after the run is listed in the report's commit.
- **Imagery terms:** ShadowCam crops are never committed (git-ignored gallery); only ids and numbers are.

## A10.7 What a result would and would not mean
- A met claim at a site means the rendered direct-sunlight shadow geometry from LOLA terrain and SPICE matches what
  ShadowCam records as saturated (directly lit) versus unsaturated ground at about 5 m, for those images and that site.
- It does **not** validate the render's brightness inside shadows. The render has no secondary (scattered) illumination,
  so inside permanently or temporarily shadowed ground it is black while ShadowCam is not. SSIM and the histogram
  distances measure that gap; they are reported, not claimed.
- It does not certify illumination power, DSN or link availability, and it is not a probability.
