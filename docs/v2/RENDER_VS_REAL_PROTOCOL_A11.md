# Render-vs-real protocol — Amendment A11 (Kaguya TC: camera model, conventions test, dev pilot plan)

Written 18 Nov 2026 by the coordinating session (Claude), **before any Kaguya TC image is rendered, displayed or
scored**. Its SHA-256, and those of `tc_select.py` and the selection it wrote, are recorded in `docs/v2/PREREGISTRATION.md`
(Entry 12) in the same commit. The TC code is not frozen here (as A8 did not freeze the ShadowCam code); A13 freezes it
before the held-out run.

**State at writing.**
- No Kaguya TC image has been rendered, displayed or scored on any split.
- One dev Level 2B0 label (TC1S2B0_01_04808S893E2361) was read for the camera model and the label-corner check (A11.4).
  No held-out TC label or image has been read.
- The project owner is downloading the 288 dev files of `results_tc/download_dev.txt` (144 images) into the incoming
  folder (A11.7). The first files were opened only to check that they are gzip and PDS3 labels.
- The SELENE kernels come from the USGS public ISIS data bucket (`usgs_data/kaguya/kernels/`), recorded in
  `$POLARIS_DATA/v2/render_vs_real/spice_selene/MANIFEST.jsonl`.

## A11.1 Rows (protocol §2; no new catalogue)
- **Catalogue:** the frozen v1 catalogue. TC footprints there come from the PDS label corner coordinates (ODE "Footprint
  from PDS Label"); none is flagged `footprint_suspect`. So TC needs no catalogue version of its own, unlike ShadowCam
  (A8).
- **Products:** Level 2B0 stereo (`Kaguya_TC_stereo`, TC1/TC2 "W") and mono (`Kaguya_TC_mono`, "S") form one instrument
  here. Reports split them out.
- **Eligible (protocol §2 gates, `tc_common.eligible`):** dev 1,532 rows; held-out 645 rows (628 stereo, 17 mono).
- **Secondary-illumination track:** rows with the Sun below −0.5° at the site are scored on SSIM and the histogram
  distances only, as for ShadowCam (A8.5).

## A11.2 Camera model (`tc_camera.py`)
- **Source:** ISIS KaguyaTcCamera and KaguyaTcCameraDistortionMap, plus the kaguyatc2isis label translation,
  re-implemented with these kernels:
  - IK `SEL_TC_V01.TI`, ISIS IAK `kaguyaTcAddendum007.ti`, FK `SEL_V01.TF` and SCLK `SEL_M_V01.TSC`;
  - attitude: the whole-mission definitive CK `SEL_M_ALL_D_V02.BC`.
- **Formulas:** the module docstring. In short:
  - start = SCLK(`CORRECTED_SC_CLOCK_START_COUNT`), taken as ticks;
  - line rate = `CORRECTED_SAMPLING_INTERVAL`;
  - detector sample = image sample − 1 + `FIRST_PIXEL_NUMBER` (297 nominal, 1 full, 1172 half; the parser refuses a
    mismatch);
  - focal-plane maps and the radial polynomial distortion as in the IK and IAK;
  - look vector in `LISM_TC1_HEAD` / `LISM_TC2_HEAD`.
- **Pixels:** radiance = DN × `SCALING_FACTOR`. The label's `SATURATION` code marks saturated pixels; `MINUS`,
  `DUMMY_DEFECT` and `OTHER` mark invalid pixels.
- **Tests:** `tests/test_tc.py`. Constants match the cached kernels. The model is also checked for the boresight
  direction, the IFOV, the flip symmetry, label parsing, the pixel codes, the orbit choice and the dev guard.

## A11.3 Orbit
- **Headline: the RISE solution named in each label's SPICE metakernel**, as protocol §3.1 requires:
  - `RISE100i_05` → `SEL_M_071020_081226_SGMI_05.BSP`;
  - `RISE100h_02` → `SEL_M_071020_090610_SGMH_02.BSP`.
  - A label naming any other solution is gated.
- **Comparison only:** the GRGM900C + altimetry solution (`SELMAINGRGM900CL660DIRALT2008103020090610.bsp`). It covers
  only 30 Oct 2008 – 10 Jun 2009, about 10 % of the eligible rows, so it cannot be the headline.
- A gap in the SPK or CK over a row's image interval gates that row, with the reason.

## A11.4 Conventions not settled before any render, and the pipeline test that settles them
1. **Start time.** The `isis` convention (SCLK ticks) and the label's `CORRECTED_START_TIME` differ by 33 ms on the one
   label checked, about 50 m along track.
2. **Sample axis.** ISIS ignores `SATELLITE_MOVING_DIRECTION` and `FIRST_DETECTOR_ELEM_POSITION`. Whether Level 2B0
   lines are stored in detector order for both moving directions is not stated.
**What the one label already shows** (metadata only, `results_tc/label_check.json`; TC1, nominal swath, moving
direction −1):
- **No flip.** Without the flip, the modelled corners lie 202–220 m from JAXA's. With it, they lie about 28.6 km away,
  because the left and right corners swap.
- **Start time.** `isis` is 50 m closer than `label` (209 m against 259 m at the upper-left corner).
- **A near-rigid offset of about 200 m along track remains** (−193 to −208 m, plus 59–81 m across track). That is about
  22 lines, about 0.13° of pitch, or about 130 ms.
  - Its cause is unknown. The label's metakernel names JAXA's IK version 4.01, while the public IK is `SEL_TC_V01`.
  - The GRGM900C orbit changes the corners by 11 m.
  - Whether the real image sits on the model or on JAXA's geometry is what the pipeline test's registration measures.

One label covers one camera and one moving direction, so the pipeline test below still decides.

3. **Label-corner check (reported, not a gate).** For every geometry row, the distance from the modelled image corners
   and centre to the label's corners and centre (JAXA's own geometry), as A8 did with ASU's centre pixel.

The pipeline test then runs on dev rows only:
- **Rows:** `tc_select.py`, seed `polaris-x-v2-kaguya-tc-dev-2026-11-18`. The first 4 eligible dev rows of each camera
  (TC1, TC2) with the Sun at or above −0.5°.
- **Renders:** each row is rendered (PGDA 78, Hapke) under start `isis` / `label` × flip no / yes.
- **Decision rule (A8.4 adapted to TC):**
  - Each render is registered against the real image over ± 2,000 m.
  - For each question, the option whose median |offset| over the rows is smaller is adopted, provided it is below 600 m
    and the other option's median is at least twice as large.
  - Why not A8.4's thresholds (adopt below 150 m, other above 600 m): the label check already shows about 200 m between
    the model and JAXA's geometry, so a correct option could miss 150 m.
  - The flip is decided per moving direction (+1, −1). A direction it cannot settle is gated; an unsettled start time
    keeps `isis`, and the result is reported.
- **Registration radius for the pilot:** ± max(3 px, 3 × the median |offset| of the adopted conventions), at least
  150 m.
- **Record:** the outcome goes into A12, registered before any dev-pilot score. Scores from the test are not used for
  anything else.

## A11.5 Dev pilot (after A12)
- **Rows:** the first 150 eligible dev rows in the seeded order: 144 images, 12 rows on the secondary track.
- **Grid:** TC pixels are about 8–10 m, so b = round(5 m / pixel) gives 1 (no binning). The §8 edge limit is therefore
  about 2 × 9 m.
- **Saturation:** saturated pixels stay in the window and count as lit (protocol §4.1, as restored by A10). Registration
  uses non-saturated pixels.
- **Render, terrain and photometry:** as A8.5, with the TC OSL camera (`tc_camera.osl_source`). Hapke 643 nm parameters
  are applied to TC's 430–850 nm band, an approximation stated as such.
- **Report:** `docs/validation/RENDER_VS_REAL_TC_DEV.md`, labelled dev only. Stereo and mono rows, TC1 and TC2, and the
  orbit comparison are shown separately.

## A11.6 Held-out run (A13, later)
- **Rows:** 645 eligible held-out rows are more than one run can render in reasonable time (about 1.5 min per row). A13
  will fix a stratified, seeded sample of about 200 rows before any held-out label or image is read. NAC's held-out run
  (A5) was also a sample.
- **Before the run:** A13 freezes the TC code and states its prediction.

## A11.7 Image source
- **Labels and images:** JAXA DARTS (`data.darts.isas.jaxa.jp/pub/pds3/sln-l-tc-3-*-level2b0-v1.0/`, public, no
  account).
- **Problem:** on 18 Nov 2026 DARTS answered the pipeline's requests with a "Request Rejected" page. Nothing was
  fetched, and nothing was done to get around the refusal. The project owner decides how to obtain the files.
- **Decision (18 Nov 2026):** the project owner downloads the files from DARTS by hand.
  - The pipeline fetches nothing from DARTS.
  - `tc_download_list.py` writes the dev URL list (144 images, 288 files, about 908 MB).
  - The owner places the files in `$POLARIS_DATA/v2/imagery/tc/incoming/`.
  - `tc_io` checks each file (the product's PDS3 label; gzip), copies it into the cache and records it in the manifest
    (source URL, bytes, SHA-256, time).
  - Held-out files are listed only after A13 fixes the held-out sample.
- **Constraint:** every file gets a manifest entry, and no JAXA image is committed.
