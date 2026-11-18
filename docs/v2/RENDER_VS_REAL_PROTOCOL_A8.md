# Render-vs-real protocol — Amendment A8 (ShadowCam: catalogue v2, camera model, dev pilot plan)

Written 17 Nov 2026 by the coordinating session (Claude), **before any ShadowCam image is rendered**. Its SHA-256 and the
SHA-256 of catalogue v2 are recorded in `docs/v2/PREREGISTRATION.md` (Entry 9) in the same commit.

**State at writing.**
- **No ShadowCam image has been rendered or scored**, on any split.
- **Pixels touched so far:** one dev cube's 64 KiB ISIS header was read. One 50 MB byte range of the same dev cube was
  downloaded only to measure the archive's speed; it was discarded unread.
- **Held-out data used:** catalogue metadata and the PDS4 labels, which carry times, geometry and instrument settings
  but no image pixels.

## A8.1 Why a new catalogue (protocol §2)
- The frozen catalogue v1 takes ShadowCam footprints from ODE's browse-map extent. So 4,680 of 4,815 rows are
  `footprint_suspect`, and the 135 others still carry the browse-map shape (median width 94 km against a 5.4 km swath).
- Protocol §2 lets ShadowCam enter scoring only through a new catalogue version whose footprint comes from the product.
  This amendment builds and hashes it.

## A8.2 Catalogue v2 (`imagery/catalogue_shadowcam_v2.csv.gz`, SHA-256 in Entry 9)
- **Rows:** exactly the 4,815 ShadowCam image × site rows of v1. Every column and every split is kept. No row is added.
- **Recomputed with v1's own definitions:** footprint, area, width, `overlap_frac`, `covers_site_centre` and
  `footprint_suspect` (`tools/imagery/ode.py` `site_filter`: the 10 km × 10 km south-polar stereographic square).
- **Footprint:** the image outline from the camera model (A8.3) on the 1737.4 km sphere. It uses only the PDS4 label and
  the KPLO SPICE kernels; no pixel is read.
- **Builder:** `tools/validation/render_vs_real/shc_catalogue.py` (commit given in Entry 9).
- **Result:** All 4,815 rows resolve: 0 `footprint_suspect`; all CK/SPK coverage present. Camera-model swath widths ~3.6-5.5 km (nominal 3,072 x ~1.75 m = 5.4 km), against ODE's ~94 km. Rows passing the §2 gates: **dev 423 (378 images; 111 secondary track; TDI A 189, B 234)**, **held-out 183 (162 images; 54 secondary; A 85, B 98)**. 26 rows cover a site under some conventions but not all and are therefore not eligible; 21 rows reach overlap 0.25 only under some convention.

## A8.3 Camera model and the conventions not yet settled
- **Model:** `shc_camera.py`, ISIS ShadowCamCamera re-implemented with the USGS public KPLO kernels (IK
  `kplo_shadowcam_v00.ti`, IAK v02, FK v06, the newest SCLK, and the shortest covering CK and SPK).
- **Independent check, on one dev label:** at the label's reference time, the modelled sub-spacecraft point is 0.5 m from
  ASU's and the centre pixel is 51 m from ASU's.
- **Not settled before any render:**
  1. **Start time.** ISIS gives SCLK(ExecutionSpacecraftTime) + StartTimeOffset. The label's `start_date_time` is 0.78 s
     later on the checked image, because the label's ExecutionTime is a whole-second value.
  2. **Sample axis for TDI direction B.** ISIS has no flip; the ALE driver flips it.
  3. **SampleFirstPixel**, which only the cube header carries.
- **In catalogue v2** a row covers a site only if it does under all 8 combinations (`overlap_frac` = the minimum,
  `covers_site_centre` = all). The maximum overlap and the number of combinations covering are kept as columns.

## A8.4 Pipeline test: deciding 1 and 2 on dev, by a rule fixed here
- **Rows:** `shc_select.py`, seed `polaris-x-v2-shadowcam-dev-2026-11-17`. The first 3 eligible dev rows of each TDI
  direction with the Sun at or above −0.5° at the site.
- **Renders:** each row is rendered (PGDA 78, Hapke) under the start conventions `isis` and `label`; TDI-B rows also
  under both sample axes.
- **Decision rule:**
  - Register each render against the real image over ± 2,000 m (an extended search used only for this test).
  - The convention whose median |offset| over the rows is smaller is adopted, provided it is below 150 m and the other's
    is above 600 m.
  - Otherwise the question is unresolved and those rows are **gated** (TDI B), or the `isis` convention is kept and the
    result reported (start time).
- **Record:** the outcome goes into A9, registered before any dev-pilot score.
- **Scores from the test are not used for anything else, and are reported as such.**

## A8.5 Dev pilot (after A9)
- **Rows:** the first 150 eligible dev rows in the seeded order (`shc_select.py`). Rows in the protocol §2
  secondary-illumination track (Sun < −0.5° at the site) are kept and scored on SSIM and the histogram distances only;
  their shadow metrics are reported as not applicable.
- **Grid:** binned to the 5 m terrain posting (b = round(5 m / pixel scale), as A1.3). Special and saturated blocks leave
  the window.
- **Real image:** CAL radiance. The per-image median normalisation (§3.2) makes its scale irrelevant.
- **Render:** the frozen NAC/WAC settings (A1.4), through `wac_twin.py` with the ShadowCam OSL camera
  (`shc_camera.osl_source`).
- **Terrain and photometry:** terrain products as A1.5; photometry as A1.5 (Hapke 643 nm parameters; ShadowCam's band
  is 450–750 nm, so the parameters are an approximation, stated as such).
- **Registration:** ± max(3 binned px, 150 m) (3 × 50 m, from the 51 m label check).
- **Gates:** geometry A1.2/A2 (1 m, 0.1 binned pixel); window §3.1.
- **Report:** `docs/validation/RENDER_VS_REAL_SHC_DEV.md`, labelled dev only.

## A8.6 What follows
The held-out amendment (A10) freezes the code and parameters after the dev pilot, as A5 and A7 did, and states its
prediction before the held-out run.
