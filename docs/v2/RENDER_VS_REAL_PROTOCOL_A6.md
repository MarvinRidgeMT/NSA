# Render-vs-real protocol — Amendment A6 (LROC WAC: camera model, grid and dev pilot)

Written 17 Nov 2026 by the coordinating session (Claude), **before any LROC WAC score is computed**. Its SHA-256 is recorded in
`docs/v2/PREREGISTRATION.md` (Entry 7) in the same commit. Scope: the **dev** pilot for LROC WAC. The WAC held-out run needs
its own amendment (A7), which freezes the code and parameters after this pilot, as A5 did for the NAC.

**State at writing.**
- No WAC row has been scored, on any split. No held-out WAC image has been fetched, rendered or displayed.
- One dev image, M109971544CC (3 rows: site04_roi3, site01_roi6, site11_roi4), was used as the pipeline test: it was fetched,
  rendered, and its real and rendered crops were looked at side by side. No metric was computed on it. Protocol §1.4 allows
  up to 20 dev pipeline-test thumbnails.
- One label and frame set of a second dev product, C1094452178CC, were fetched to learn the file layout. It is a calibration
  sequence (PDS3 TARGET_NAME "CAL"). It is not in the pilot selection.

## A6.1 Scope
- **Instrument:** LROC WAC COLOR-mode CDR (`CDRWAC4`; every catalogue WAC row is COLOR mode, band code 127).
- **Band:** the VIS 643 nm band only (NAIF filter frame `LRO_LROCWAC_VIS_FILTER_4`, IK code −85634).
  - Why this band: it is the band of the Hapke parameters (LROC WAC 643 nm, `blender/v2/hapke.py`) that every render uses.
  - The band is fixed here, before any score. No other band is scored.

## A6.2 Rows (dev pilot)
- **Eligible:** dev WAC rows passing the protocol §2 metadata gates: 925 rows / 296 images (66 rows gated).
- **Selected** (`wac_select.py`, rule in its docstring): every eligible image for which all SPICE kernels the camera model
  needs were already in the local kernel cache, downloaded for the NAC pilots before this rule was written. That gives
  **464 rows / 141 images**.
  - This is cluster sampling by download cost, as A1.1. It never uses image content or scores.
  - The sample is concentrated in 2009–2011. Its strata are reported against the eligible population.

## A6.3 Camera model (`tools/validation/render_vs_real/wac_camera.py`)
- **Model:** ISIS LroWideAngleCamera, as implemented in the public USGS source, with the NAIF IK `lro_lroc_v20.ti`.
  - Frame-set layout: from `lrowac2isis`.
  - Frame time: et(set k) = et(SCLK start) + exposure/2 + k × interframe delay.
  - Detector: sample + 160; line = 781 + framelet line.
  - Focal plane: TRANSX/TRANSY. Radial distortion: OD_K (three terms), forward from the distorted position.
  - Look vector: in `LRO_LROCWAC_VIS`, with attitude from the lrolc CKs (frame −85620).
  - Orbit: A4 applies (GRGM900C where it covers the image, FDF otherwise, flagged).
- **Checks before registration** (no score involved):
  - The IK values equal the cached NAIF IK (test).
  - On the pipeline-test image:
    - Band order: the 415 → 689 nm framelets brighten in that order, the lunar red slope.
    - Model frame-set span equals the label START–STOP span.
    - The SPICE Sun direction matches the catalogue's Horizons value to 0.002°.
  - The Blender camera's surface hits agree with the Python model's rays to ≤ 0.0011 pixel (2,000 pixels per row, 3 rows).
- **Bug found and fixed before registration.** The first test render placed the scene wrongly. The camera shader had
  formed ephemeris time (~3 × 10⁸ s) in OSL's 32-bit floats. The time is now built from the frame index with constants
  computed in double precision, and a regression test forbids large literals. After the fix the render and the real image
  show the same ridge, framelet steps and craters.
- **Not yet checked independently:** the model's image centre is 1.9 km from the ODE centre point of the pipeline-test
  image. ODE's centre method for WAC is not documented here, so this is reported, not used as a gate. The registration
  offsets of the pilot are the per-row check.
- **Geometry gate** (A1.2 rule in WAC units): the state polynomials must reproduce SPICE to 1 m and 0.1 pixel
  (149 µrad). The A2 degree rule applies.

## A6.4 Grid and the framelet rule
- **Native WAC pixels, no binning.** The A1.3 binning to 5 m does not apply: the WAC pixel is 56–290 m in the catalogue,
  median 73 m.
- **The image grid is the band image:** the 643 nm framelets (14 lines each) stacked in time order.
  - This is the product's own pixel grid; no orthorectification is done.
  - Consecutive framelets overlap on the ground by a few lines, so ground in an overlap is scored twice, once in each
    exposure.
- **Framelet rule:** every framelet is a separate exposure, so no neighbourhood operation may cross a seam.
  - Implementation: the 14-line strips are separated by 64 rows that never enter the analysis window. The gap rows repeat
    each strip's edge row, so they add no gradient. The frozen `run.metrics`, `score.register` and `score.shift` then run
    unchanged.
  - Consequences:
    - Shadow edges (§4.2) must lie ≥ 3 pixels inside their framelet: rows 4–11 of 14 (the §4.2 border rule, applied per
      exposure).
    - An edge is matched only within its own framelet. A gap of 64 rows is beyond the 50-pixel unmatched limit, so a
      cross-framelet match is counted as unmatched.
    - The 2-pixel edge band of §4.1, the SSIM windows (§4.4) and the registration's Sobel gradients stay inside a
      framelet.
    - Registration (§3.1): one rigid translation for all framelets of the row, as one pointing error per image. The
      shifted render is cut at each framelet's edge; rows that would receive another framelet's content leave the window.
  - Synthetic tests: identical images score IoU 1 and edge 0; a 2-line ground shift is recovered across seams within the
    0.25-pixel grid.
- **Analysis window:** §3.1 (render hit inside the site square, minus special pixels, minus 8 pixels at the crop borders).
  Special pixels are NULL, LRS, LIS and HRS/HIS from the label's float32 special constants. The A1.3 rule applies:
  saturated pixels leave the window.
- **Registration radius:** the A4.2 rule in WAC pixels.
  - GRGM900C rows: ± max(3 px, 3 × 20 m / pixel), which is 3 pixels at every WAC scale.
  - FDF rows: ± max(3 px, 400 m / pixel).
- **Ground offset:** the along- and across-Sun split is computed from the render's surface points inside one framelet
  near the crop centre.

## A6.5 Render, terrain and photometry — as for the NAC
- **Renderer:** `wac_twin.py` imports the frozen NAC twin (`blender_twin.py`) and differs only in the camera and in the
  view cone given to the tile planner, which is computed from the fitted WAC rays.
- **Settings and products:** render settings (A1.4), terrain products (A1.5, near and far levels) and photometric models
  (Hapke SOUTH_60_70 643 nm for every product; lunar-Lambert 0.5 and Lommel–Seeliger on PGDA 78) are unchanged.
- **Shadow pass:** one Sun-centre ray from each pixel's centre hit (§4.1).
  - Limitation: at 60–290 m a WAC pixel often contains both lit and shadowed ground. Its predicted class is that of the
    centre point, while its observed class comes from the pixel's mean brightness. This mixed-pixel effect is expected to
    lower IoU and raise edge error relative to the NAC. It is reported, not corrected.

## A6.6 Metrics and reporting (dev)
- **Metrics:** §4.1, §4.2, §4.4 and §4.5 as for the NAC, plus the A5.5 count-matched mask and the near-total-shadow stratum.
- **Edge error in metres:** each pixel's ground size is range × IFOV (1.4923 mrad).
- **Claim rule (dry run only):** the A5.6 rule is applied to the dev records as a code check. The analysis pixel there is
  the native WAC pixel. The result is not a claim.
- **Report:** `docs/validation/RENDER_VS_REAL_WAC_DEV.md`, labelled dev only.
  - Thumbnails are crops of NASA images and are not committed.

## A6.7 What may change before the held-out amendment (A7)
- **May change** (protocol §5 limits only): photometric model choice and parameters within the published ranges, and
  render sampling. Every such change is stated in A7 with the dev numbers that motivated it.
- **May not change:** the camera model, grid, framelet rule, window, gates, metrics and thresholding rule. A bug in them may
  be fixed only through a dated amendment that reports both numbers.
