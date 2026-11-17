# Render-vs-real protocol — Amendment A1 (dev-split pilot implementation, LROC NAC)

Written 16 Nov 2026 by session R4 (Claude) **before any render-vs-real score is computed**. Its SHA-256 is recorded in
`docs/v2/PREREGISTRATION.md` (Entry 2) in the same commit. It does not edit `RENDER_VS_REAL_PROTOCOL.md` (v1.0, frozen); it
fixes choices that v1.0 leaves open, for the LROC NAC pilot on the **dev** split. State at writing: one dev image
(M162485477LC, site04_roi3) has been rendered and looked at side by side with its real window to debug the camera
(orientation, clipping, terrain tiles); no metric has been computed on any image. Nothing here was chosen from a score.

## A1.1 Images (dev only)
- Instrument LROC NAC (CDRNAC4). Rows: `split = dev`, protocol §2 metadata gates. Sampling: whole NAIF `lrosc` CK windows in
  order of eligible images per CK megabyte (download budget), ties by SHA-256(`polaris-x-v2-r4-dev-sample-2026-11-16`:window),
  to ~200 images (`tools/validation/render_vs_real/select.py`). Cluster sampling; the sample's strata are reported.
- Held-out images are never fetched, rendered or scored; every stage calls `common.assert_dev`.

## A1.2 Camera model and geometry (§3.1 "camera model resolves")
- ISIS LroNarrowAngleCamera model with NAIF IK `lro_lroc_v20.ti` and ISIS IAK v04 timing (pre-roll 1024 lines, line-rate factor
  1.0045); NAIF PDS kernels `lrosc` (spacecraft CK), `lrolc` (LROC temperature-corrected CK), `lrorg` (SPK), DE421, MOON_ME
  (`moon_080317.tf`, `moon_pa_de421_1900_2050.bpc`). No light-time correction of the spacecraft position (~0.3 m).
- Per image × site, spacecraft position (local ENU at the site centre) and attitude are fitted over the cropped lines with
  cubic polynomials (position; rotation vector about the mid-crop attitude); the fit error is recorded and the row fails the
  camera gate if the position error exceeds 1 m or the angle error exceeds 0.1 binned pixel.
- Sun direction: SPICE `LT+S`, topocentric at the site centre, at the mid-crop time; constant over the crop. Sun angular
  diameter from its distance (R☉ = 695,700 km); irradiance 1361 W m⁻² / r_AU².

## A1.3 Pixel grid (§3.1 "same pixel grid")
- Only the image lines whose rays reach the site square ± (1 km + relief × tan(emission + 2°)) are fetched and scored.
- **Binning:** the real image is binned b × b with b = max(1, round(5 m / ODE pixel scale)), blocks aligned to the crop's
  first line and the image's first sample; the render is made on that binned grid (each render pixel integrates its binned
  footprint: BOX filter 1 px, uniform raster sampling). A binned pixel is a special pixel if any member is NULL/LRS/LIS/HRS/HIS.
- **Saturation:** the LROC CDR flags saturation with the HRS/HIS special constants, which is taken as the SIS's saturation
  code; special pixels leave the window (§3.1), so the 99.9th-percentile fallback is not used for LROC NAC.
- Border exclusion: 8 binned pixels on every side of the cropped window.

## A1.4 Render (§3.2, §4.1)
- Blender 5.3.0 Cycles CPU, OSL custom push-broom camera (per-line position/attitude polynomials); scene from the
  `blender/v2` builder (terrain levels and view-dependent tiles, ENU with curvature, Hapke material). Beauty: 32 samples,
  4 bounces, no denoising, seed 0, Sun lamp with the true angular diameter, black sky, no earthshine.
- Shadow pass (§4.1): white diffuse, **flat shading** (facet normals), Sun lamp angle 0 (Sun centre), direct light only,
  1 sample per pixel, filter width 0.01 px (pixel-centre ray). Lit iff the pass is > 0.
- Render I/F = π L / E☉. **Normalisation fallback:** if the render's median over the valid non-saturated window pixels is
  not > 0 (more than half the window received no light path), the render is divided by the real image's median instead
  (both are I/F), and the row is flagged `renderMedianZero`.

## A1.5 Terrain products and photometry (§5, §7)
- Products: PGDA 78 5 m site tile; LOLA LDEM_875S_5M; PGDA 90 LDEM_80S 80 m (protocol's LDEM control); flat-horizon control
  (1,737,400 m sphere, no terrain anywhere). Near level: one box per site (PGDA 78 tile ∩ site centre ± 8 km), same for every
  product; far level for every non-flat product: PGDA 90 80 m, ± 290 km. SLDEM2015 does not reach these latitudes; Kaguya TC
  DTM, GSFC SfS and NAC DTMs are not in hand; the S3 pyramid equals PGDA 78 there and is not rendered separately.
- Photometry: Hapke (SOUTH_60_70 parameters of the LROC WAC 643 nm map, as in `blender/v2/hapke.py`) for every product.
  On PGDA 78 only, two alternatives are also scored: lunar-Lambert L = 0.5 and Lommel–Seeliger (L = 1). Shadow metrics do
  not depend on photometry; SSIM, histogram distance and registration do. No photometric parameter is fitted in this pilot.

## A1.6 Metrics details (§4)
- Window membership uses the render's own surface points (per product).
- Otsu: 256 bins over [P0.5, P99.5] of v; values outside that range are not binned; the threshold is the upper edge of the
  last shadow-class bin; weak bimodality uses the histogram's between-class and total variance.
- IoU edge band: 2 px = two 3 × 3 dilations of the predicted edge pixels.
- Edge pixels: a 4-neighbour of the other class that is itself in the window; interior = window eroded 3 × (3 × 3).
- GSD at a pixel = slant range (render surface point to the spacecraft at that line) × 10.0054 µrad × summing × b.
  Signed edge error: (predicted edge point − nearest observed edge pixel's render surface point) · horizontal Sun unit
  vector, metres, matched pixels only.
- SSIM: local moments Gaussian-weighted over valid pixels only (weights renormalised); a window counts if ≥ 90 % of its
  11 × 11 box is valid non-saturated in both images (the same mask is used for both); dynamic range from the real image.
- Registration: Sobel gradient magnitude of the exposure-normalised linear I/F, masked by the analysis window. Pointing
  uncertainty used for the search radius: **σ = 50 m** (an engineering value, not a citation; LRO NAC geolocation is generally
  reported at tens of metres) → ± max(3, 150 m / binned GSD) px. Integer offsets by FFT masked NCC, then the exact 0.25 px grid
  within ± 1 px of the best integer offset. A row whose best offset sits on the search boundary is flagged `atBound` and kept.
- Bootstrap (§7): 10,000 resamples of images, seed `polaris-x-v2-boot`, numpy default_rng(SHA-256(seed) as int).

## A1.7 Reporting
- All numbers are labelled dev pilot, SOURCE-BASED · UNVALIDATED. The §8 claim rule needs the held-out run; no claim of it
  is made from these numbers.
