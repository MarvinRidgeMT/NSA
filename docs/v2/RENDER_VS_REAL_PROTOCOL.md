# POLARIS X v2 — render-vs-real protocol (pre-registered)

Version 1.0, written 16 Nov 2026 by session S6 (Claude), **before any render twin exists and before any score is computed.**
Scope: prompt §6.3 and §6.4 (`docs/v2/inputs/CLAUDE_CODE_PROMPT_6D_worlds_blender_v2.md`). Plan: `docs/v2/PHASE_5_IMAGERY_PLAN.md`.

**Freezing.** This file's SHA-256 and the catalogue's SHA-256 are recorded in `docs/v2/PREREGISTRATION.md` in the commit after
this one. The file is never edited after that. Changes are made only by appending a dated amendment file
`docs/v2/RENDER_VS_REAL_PROTOCOL_A<n>.md`, whose own SHA-256 is added to `PREREGISTRATION.md` **before** any result that depends on it
is computed. The scoring script refuses to run if any recorded hash differs (the same pattern as `tools/validation/nac/`).

**What this measures.** How well a POLARIS render (Blender, §6.2) of a real image's geometry reproduces where shadows fall,
the skyline and the brightness distribution in that image. It tests the terrain product + Sun geometry + camera model + photometric
model chain. It does **not** test power, communications, thermal or any decision metric. Scores are labelled
SOURCE-BASED · UNVALIDATED until an independent party has repeated them.

---------------------------------------------------------------------------------------------------
## 1. Images and the split

1. **Catalogue.** `imagery/catalogue.csv.gz` (fallback for `catalogue.parquet`; columns in `imagery/catalogue.schema.json`), one row per
   image × site, built by `python -m tools.imagery.catalogue build`. Its SHA-256 is in `PREREGISTRATION.md`. Images added later go
   into a new, separately hashed catalogue version; they never change the frozen split.
2. **Split.** By image (product id), never by row. `split = heldout` or `dev` exactly as stored in the frozen catalogue
   (seed `polaris-x-v2-heldout-2026-11-16`, 30 %, systematic sampling over images sorted by (stratum, SHA-256(seed:product_id));
   rule in `tools/imagery/catalogue.py:assign_split`).
3. **prior_use.** The 687 GSFC orthorectified NAC images of the earlier NAC comparison (`tools/validation/nac/`) are always `dev`:
   region 6 images were used to choose thresholds there.
4. **Held-out images are not looked at** — no thumbnails, browse images, renders or scores — until the single final scoring run (§6).
   The ≤ 20 pipeline-test thumbnails are drawn from `dev` only.

## 2. Eligibility gates (fixed; applied from catalogue metadata only, never from image content or scores)

An image × site row is **scored** for the orbital metrics iff all hold:
- `footprint_suspect` is not `true`;
- `covers_site_centre = true` **or** `overlap_frac ≥ 0.25`;
- the calibrated product and the label fetch successfully, and the camera model (label + SPICE) resolves;
- the terrain product under test covers the whole analysis window (§3.1) at its native resolution.

Rows failing a gate are **counted and listed by reason** in the report, never silently dropped. Almost all ShadowCam rows in
catalogue v1 are `footprint_suspect` (ODE gives the browse-map extent, not the footprint), so they are not scored from v1. They
can enter scoring only through a new catalogue version whose footprint comes from the product itself (label corner coordinates
or the valid-data outline), built and hashed by an amendment **before** any ShadowCam image is rendered; their `split` is kept. ShadowCam images whose site-centre
Sun elevation is < −0.5° (secondary illumination only) are scored on SSIM and the histogram distance only, as a separate
"secondary-illumination" track; their shadow metrics are reported as not applicable. Surface images (when catalogued) follow §4.

## 3. Comparison geometry

### 3.1 Space
- **Orbital: image space.** The render twin is rendered in the real image's own camera geometry — same instrument camera model,
  spacecraft position and pointing from the product label and the NAIF SPICE kernels named in the label, same UTC (exposure
  mid-time per line for push-broom instruments), same pixel grid. No orthorectification is used for scoring, so the DEM under
  test never moves the observed pixels.
- **Analysis window:** the pixels whose ray hits the terrain inside the site's 10 km × 10 km square (render-side intersection),
  minus ISIS special pixels (NULL, LRS, LIS, HRS, HIS) in the real image, minus 8 px at the image borders.
- **Registration (pointing error only).** One rigid 2-D translation per image, no rotation or scale, searched on a 0.25 px grid
  within ± max(3 px, 3 × the documented pointing uncertainty / pixel scale) by maximising normalised cross-correlation of the
  Sobel gradient magnitude of the real image and the render. The offset is recorded. **Every metric is reported both registered
  and unregistered**; the registered value is the headline.
- **Surface: camera space** with the camera pose from published metadata; where the pose is uncertain it is solved from horizon
  features (§6.2 of the prompt) on the **dev** images of that camera only, and the residual is recorded and reported per image.

### 3.2 Radiometry
- Real image: the calibrated product (LROC CDR I/F, ShadowCam CAL, Kaguya TC Level 2B0 values as archived). No stretching.
- Render: linear radiance → I/F-equivalent with the Sun irradiance at the image's solar distance.
- **Exposure normalisation (the one allowed per-image gain):** each image (real and render separately) is divided by its own
  median over the valid non-saturated window pixels.
- **Saturated pixels:** ISIS HRS/HIS special pixels, values at or above the saturation code in the product's SIS, and, where the
  SIS gives no code, values ≥ the 99.9th percentile of the window. **Non-saturated** = valid and not saturated.

## 4. Metrics (all per image × site × terrain product × photometric model)

### 4.1 Shadow-mask IoU (fixed thresholding rule)
- **Predicted shadow mask:** from the render's direct-Sun shadow pass: a pixel is shadow iff the ray from its surface point to
  the **Sun centre** is blocked by terrain or the local incidence angle ≥ 90°. (Same definition as the solver's lit test,
  margin ≤ 0.) Not thresholded from rendered brightness.
- **Observed shadow mask — fixed rule:** on the valid non-saturated window pixels, take v = log10(max(I/F, 1e-5)) after
  exposure normalisation; build a 256-bin histogram between the 0.5th and 99.5th percentiles of v; the threshold is **Otsu's**
  threshold on that histogram; shadow iff v ≤ threshold. Saturated pixels count as lit. No manual adjustment, no per-instrument
  constant.
- **IoU** = |P ∩ O| / |P ∪ O| over the window, shadow as the positive class. Also reported: lit-class IoU, balanced accuracy,
  Cohen's κ, and IoU excluding a 2 px band around the predicted shadow edges.
- A **weak-bimodality flag** is recorded when Otsu's between-class variance is < 0.5 of the total variance of v; flagged images
  stay in every aggregate and are also reported separately.
- Secondary (sensitivity only, never headline): the same Otsu rule applied to the rendered image instead of the shadow pass.

### 4.2 Shadow-edge position error
- Edge pixels: shadow pixels with a 4-neighbour of the other class, inside the window and ≥ 3 px from window borders.
- For each predicted edge pixel, the distance to the nearest observed edge pixel (exact Euclidean distance transform), and the
  reverse; the symmetric set is pooled.
- **Orbital: metres**, each pixel's distance times the render's ground sample distance at that pixel. **Surface: pixels.**
- Per image: median and 90th percentile. Distances > 50 px are "unmatched" and reported as a fraction, not averaged in.
- Signed variant (orbital, sunward positive): the predicted edge shifted toward the Sun is positive. Reported to show bias.

### 4.3 Skyline / horizon profile error (surface images)
- Render skyline: per image column, the lowest row whose ray misses the terrain (exact, from geometry).
- Observed skyline: in the upper half of the image, Otsu threshold on log10 intensity; sky = the below-threshold component
  connected to the top edge; skyline row = the lowest sky row per column.
- Columns where the observed contrast across the skyline is < 3 × the image noise (dark terrain against black sky) are
  **ambiguous**: excluded from the error and counted.
- Error per column = |row_obs − row_render| px, converted to elevation angle with the camera IFOV. Per image: median, P90, RMS,
  ambiguous-column fraction.

### 4.4 SSIM on non-saturated pixels
- Both images exposure-normalised (§3.2); SSIM with an 11 × 11 Gaussian window, σ = 1.5, K1 = 0.01, K2 = 0.03, dynamic range
  L = the real image's 99.5th percentile minus its 0.5th percentile over the window.
- Mean SSIM over windows whose centre pixel is valid non-saturated and whose window is ≥ 90 % valid non-saturated, in both images.

### 4.5 Radiometric histogram distance
- Headline: **Wasserstein-1** distance between the distributions of log10(exposure-normalised I/F), clipped to [−3, 1], over the
  valid non-saturated window pixels of the real image and the render.
- Secondary: Jensen–Shannon divergence (base 2) on 64 fixed bins over [−3, 1].

## 5. What may and may not be tuned (§6.4)

| May be tuned (dev split only) | Range |
|---|---|
| Photometric model choice | Lommel–Seeliger, lunar-Lambert (McEwen 1991), Hapke (as parameterised for LROC WAC by Sato et al. 2014) |
| Photometric parameters | lunar-Lambert L ∈ [0, 1]; Hapke parameters within the ranges of the published Sato et al. (2014) per-band maps; regional albedo from a published map only |
| Exposure | the one per-image median normalisation of §3.2 (it is not fitted) |
| Render sampling | samples, bounces and denoising, fixed per instrument before the held-out run |

**Never tuned:** terrain (no height edits, smoothing, offsets, resampling choices made after looking at scores), Sun or Earth
geometry, image times, camera models, the shadow definition, thresholding rule, windows, gates or metrics. A terrain product is
a *factor that is reported*, not a knob: every product that covers a window is rendered and scored, and the products are compared
on the same images. Parameters are frozen in an amendment (with hash) before the held-out run.

## 6. The held-out run

- Run **once**, at the end, by a script whose SHA-256, frozen parameters and terrain-product list are in an amendment recorded in
  `PREREGISTRATION.md` before it starts.
- Re-runs only for a crash or a bug that is documented in a new amendment; then **both** the original and the corrected numbers
  are reported.
- Every held-out row appears in the result: scored, gated (with reason) or failed (with reason).

## 7. Reporting breakdown

Per world → site → instrument → terrain product (LOLA PGDA 78 5 m, LOLA LDEM 80 m, SLDEM2015, Kaguya TC DTM, GSFC SfS where it
exists, NAC DTM where it exists) → photometric model, and per stratum axis (Sun azimuth, Sun elevation, emission, season,
terrain type, resolution):
- n, median, IQR, P10 and P90 of every metric, dev and held-out **separately** (held-out is the headline);
- controls: a **flat-horizon control** (smooth sphere: no terrain shadows) and the LDEM 80 m product, scored on the same images;
  every product is reported as a difference from the control, paired per image;
- paired product comparisons on the same images: per-image differences, their median and a bootstrap 95 % interval
  (10,000 resamples of images, seed `polaris-x-v2-boot`); descriptive, not a hypothesis test;
- galleries (real | render | difference | edge overlay) for: a fixed random sample of 12 per instrument (seed
  `polaris-x-v2-gallery`), and the **worst 10 %** by shadow IoU per instrument; failures shown, never hidden;
- every gated or failed row with its reason;
- registration offsets and their distribution; the weak-bimodality subset separately.

## 8. Claim rule (what the report may say)

- "Renders reproduce observed shadow placement at <site>/<instrument>" only if, on the **held-out** set, registered median shadow IoU
  ≥ 0.80 **and** median shadow-edge error ≤ 2 × the median pixel scale **and** both beat the flat-horizon control on ≥ 80 % of paired
  images. Otherwise the report says which condition failed, with the numbers.
- No sentence may combine scores across instruments, sites or products into one "accuracy". No score is described as a probability.
- A good score validates render geometry only; it does not certify illumination power, DSN or link availability.
- Site04 RoI 3: if any catalogued image covers that point, its scores are reported individually (it is the hero point with no
  observation check so far); if none does, the report says so.
