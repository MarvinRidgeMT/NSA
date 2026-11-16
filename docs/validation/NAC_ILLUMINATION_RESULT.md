# POLARIS X — independent illumination comparison against LROC NAC images: result

Run 15 Nov 2026, 17:20–18:30 EST, by Claude (Penumbra session) in a cloud workspace. Scripts, protocols and hashes are in
`tools/validation/nac/`. POLARIS's status label is not changed by this document; that is Sid's and Anish's decision.

## Verdict
- **Protocol v1 (region 6: Site01 ROI6 area A, Site04 west area B): NOT PASS.** It stands as recorded.
- **Protocol v2 + amendment A1, confirmatory, on new terrain (region 8: Site07 ROI1 area C; region 9: Site11 ROI1 area D): PASS in both areas.**
- **Not tested by either:** the Site04 ROI3 lander point and its 16 m rise. The 1 m mast, the 20-realization spread, the
  14-day window and power or communications are not tested either. No observed product here covers the Site04 ROI3 point.

## Reference data (independent of the model's inputs)
- **Images:** LROC NAC images orthorectified by NASA GSFC onto the 5 m polar-stereographic lattice. Source: Bertone et al. 2026,
  shape-from-shading DEMs and NAC maps, Zenodo doi:10.5281/zenodo.17954508, CC-BY-4.0, `LROC-NAC-maps/A30x_GLDIMGP_005_<ID>.tif`.
  - Region 6 (Connecting Ridge): 322 images, 2009-07-05 to 2011-12-21.
  - Region 8 (Peak Near Shackleton): 172 images.
  - Region 9 (de Gerlache Rim): 193 images.

  These images built the GSFC SfS DEMs, not the LOLA DEMs that POLARIS uses.
- **Image times:**
  - Regions 6 and 9: `LROC-NAC-adjust/*.json` `m_centerEphemerisTime` (ET, TDB seconds).
  - Region 8: the archive has no camera files, so amendment A1 was frozen before any region 8 image was downloaded. It takes ET from the product ID by a linear fit to the 515 region 6 + 9 camera files (max residual 8.95 s). A fit to region 6 alone predicts region 9 to within 8.49 s; 9 s moves the Sun by ≤ 0.0013°.
- **Model terrain:**
  - PGDA 78 5 m tiles: Site07 SHA-256 `38aaee10…2091f8`, Site11 `58f3372c…6e5`, Site01 `3ba7b97c…7e747e` (= bundle `dem.sourceSha256`), Site04 `38ff70db…ce758` (= bundle).
  - PGDA 90 80 m far field `82030dcb…beee5a`.
- **Ephemeris:** NAIF `de440s.bsp`, `moon_pa_de440_200625.bpc`, `moon_de440_250416.tf`, `pck00011.tpc`, `naif0012.tls`; frame `MOON_ME`, aberration `LT+S`.
  - The camera files' own Sun positions agree with this to a median of 0.0029° and a maximum of 0.0042° (322 region 6 images).
  - The `MOON_PA` frame would differ by 0.024°.

## Method (both protocols)
Each area is a set of points on a 25 m grid within 1000 m of a POLARIS ROI centre (v1 area B: 1500 m, x ≤ −3010 m, the part of
Site04 inside the SfS coverage). For every image covering ≥ 200 points:

1. Point height = bilinear PGDA 78 + 0.05 m.
2. The Sun azimuth and elevation come from SPICE at the image's ET.
3. Horizon = the maximum Moon-centred elevation angle along the great circle in the Sun's azimuth: 2.5 m steps on the 5 m tile, then 80 m steps on PGDA 90 out to 200 km, in float64.
4. **Predicted lit ⇔ Sun-centre elevation − horizon (the margin) > 0.**

Observed classes come from the image pixel at the point, with a 3×3 edge exclusion:
- v1: relative to each image's 90th-percentile brightness.
- v2: absolute DN thresholds, shadow ≤ 0.0020 and lit ≥ 0.0040, chosen on region 6.

Metrics:
- Agreement, balanced accuracy and Cohen's κ, all with and without near-critical points (|margin| < 0.5°).
- The 50 % crossing: the margin at which the observed-lit fraction first reaches 0.5, interpolated between 0.25° bins.

Pass rule (fixed before the run): ≥ 200 observed-shadow points, balanced accuracy ≥ 0.90 and |crossing| ≤ 0.5°, in both areas.

Protocol SHA-256:
- v1: `688b54d2…76ca60`.
- v2: `833adb90c41f697b07cd987e91850ac02e4e6542fda7c971606f2ea7ee8be49f`.
- A1: `62a497b8238fef8399170d6caabadbb5a0ff78deb30624132b2b0d820eb5eab2`.

The comparison scripts refuse to run if a hash differs.

## Results
| Area | Images (dates) | Points | Excl. near-critical: agreement / bal. acc. / κ | Shadow recall / lit recall | 50 % crossing | Verdict |
|---|---|---|---|---|---|---|
| A Site01 ROI6 (v1) | 105 | 265,379 | 0.919 / 0.918 / 0.838 | 0.975 / – | −1.53° (logistic) | NOT PASS |
| B Site04 west (v1) | 28 | 54,587 | 0.799 / 0.858 / 0.484 | 0.942 / – | −17.4° (logistic) | NOT PASS |
| **C Site07 ROI1 (v2)** | 49 (2009-08-26 to 2012-11-21) | 114,883 | **0.975 / 0.976 / 0.950** | 0.955 / 0.998 | **+0.315°** | **PASS** |
| **D Site11 ROI1 (v2)** | 42 (2009-07-20 to 2013-04-20) | 109,015 | **0.982 / 0.983 / 0.964** | 0.970 / 0.996 | **+0.445°** | **PASS** |

v2 detail:
- With near-critical points included, balanced accuracy is 0.960 (C) and 0.967 (D).
- Observed-shadow points compared: 57,074 (C) and 56,728 (D).
- Terrain-cast shadow (Sun above the local horizontal but below the terrain horizon): 47,675 of 62,976 shadow points in C, 24,624 of 59,839 in D. Restricted to the Sun above the horizontal, balanced accuracy is 0.977 and 0.985.
- Per-image agreement: minimum 0.914 (C) and 0.924 (D). No image is below 0.8.
- Sun elevation range: −0.95° to +2.76° (C) and −1.33° to +2.77° (D).

Why v1 failed: whole images that the model predicts dark were labelled "lit", because v1's thresholds scale with each image's own
brightness. Their brightest pixels are scattered light at 1–10 % of a sunlit image. This was found after v1's verdict, which is kept.
v2 fixed only the observation rule and the crossing estimator, then was applied once to the unseen regions.

## Discrepancies and limits
- **Both crossings are positive** (+0.32° and +0.45°). The observed-lit fraction reaches 50 % only when the model's Sun centre is a third to half a degree above the horizon. The Sun's disc is 0.27° in radius, so a pixel at margin 0 sees half a disc; reaching the absolute "lit" brightness needs more. Area D's +0.445° is close to the 0.5° limit. There, bins from −0.125° to +0.375° stay at a 35–37 % lit plateau before jumping to 89 %. A ~0.3–0.45° bias against the model's horizon (terrain or Sun-disc effect) cannot be excluded at this resolution.
- **Lit recall is higher than shadow recall** (0.996–0.998 vs 0.955–0.970), so the model errs slightly towards "lit". This matches the positive crossing.
- **Scale:** ground-level points (+0.05 m) at 25 m spacing, sampled at 5 m pixels. Not the 1 m mast, not the 1 m near-ray step of the bundles.
- **Coverage:** 2009–2013 images at Sun elevations of −1.3° to +2.8°, not the 2026-11-14 to 2026-11-28 window. Image dates are those NAC happened to observe; points are not independent (neighbouring points and repeated images are correlated).
- **Not observed:** the Site04 ROI3 lander point, its 16 m rise, Earth visibility, the clone (realization) spread.
- The NAC images are an observation, not a model. Their orthorectification used GSFC's SfS terrain, so a few metres of registration error near steep slopes is possible. It would act against agreement, not for it.

## What this supports
The terrain (PGDA 78/90), Sun geometry, horizon method and visibility rule reproduce observed sunlit and shadowed ground in
two south-polar areas that were not used to tune anything. The agreement is ≥ 0.975 away from the critical margin, and the shadow edge falls within half a degree. It does not show that the Site04 ROI3 numbers in the viewer are right.

## Change log
| When (EST) | Change |
|---|---|
| 15 Nov 2026 18:35 | Created (v1 NOT PASS on region 6; v2 + A1 PASS on regions 8 and 9). |
