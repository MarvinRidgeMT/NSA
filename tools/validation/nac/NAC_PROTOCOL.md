# POLARIS X — independent illumination comparison against LROC NAC images: frozen protocol

Written 15 Nov 2026 ~17:40 EST, before any comparison result was computed. The comparison script refuses to run if this
file's SHA-256 differs from the value recorded at freeze time. Author: Claude (Penumbra session). Status of POLARIS is not
changed by this test; changing it is a Sid/Anish decision.

## Question
Does the POLARIS illumination model — PGDA 78 5 m LOLA surface (site tile) + PGDA 90 80 m LOLA (beyond the tile), lunar
curvature, Sun centre from DE440 in MOON_ME with light time and stellar aberration, visible ⇔ Sun-centre elevation > terrain
horizon elevation along the Sun azimuth — predict where the ground is lit or in shadow in **observed** LROC NAC images?

## Reference (independent observation)
LROC NAC images orthorectified to the 5 m polar-stereographic lattice by NASA GSFC (Bertone et al. 2026, Zenodo
doi:10.5281/zenodo.17954508, CC-BY-4.0, region A3CLR22-6 "Connecting Ridge", files `LROC-NAC-maps/A306_GLDIMGP_005_<ID>.tif`;
acquisition time = `m_centerEphemerisTime` in `LROC-NAC-adjust/A306_GLDACAM_005_<ID>.json`). The images were used to build
the SfS DEM, **not** the LOLA DEMs POLARIS uses, so they are independent of the model's terrain input.
All 322 images in the region are used; none is chosen after seeing results.

## Test areas (fixed)
- **A, Site01 ROI6:** PGDA 78 Site01 tile; points on a 25 m grid within 1000 m of (−89.47409°, −137.3813°).
- **B, Site04 west:** PGDA 78 Site04 tile; points on a 25 m grid within 1500 m of Site04 ROI3 (−89.78012°, −156.32023°) that
  lie inside region 6 (x ≤ −3010 m). The Site04 ROI3 lander point itself and its 16 m rise are **outside** the image region,
  so this test does not observe them.

## Model (POLARIS definition, independent implementation in this check)
Point height = bilinear 5 m surface + 0.05 m. Ray along the Sun azimuth on a great circle; samples every 2.5 m while inside
the 5 m tile (from 5 m distance), then every 80 m on PGDA 90 to 200 km. Elevation angle with Moon-centred geometry,
R = 1737.4 km, float64 throughout. Horizon = max elevation along the ray. Margin = Sun-centre elevation − horizon.
Predicted **lit** if margin > 0, **shadow** if margin ≤ 0.

## Observation rule (fixed)
For each image, valid = finite DN > 0 inside the image. P90 = 90th percentile of valid DN within the test area.
Observed **lit** if DN ≥ 0.20·P90; **shadow** if DN ≤ 0.07·P90; otherwise ambiguous (excluded). A point is also excluded
if its 3×3-pixel neighbourhood (5 m pixels) contains both a lit and a shadow pixel (edge). An image enters an area only
if ≥ 200 valid points and P90 > 0.

## Exclusions (fixed, reported both ways)
Near-critical: |margin| < 0.5° (Sun disc radius 0.27° plus terrain error). Results are reported with and without it.

## Metrics
Confusion matrix (predicted × observed), agreement, balanced accuracy, Cohen's κ; observed-lit fraction in margin bins of
0.25°; the margin at which the observed-lit fraction crosses 50 % (logistic fit) = horizon offset in degrees.

## Pass rule (for this test only)
Per area: ≥ 200 observed-shadow points compared (excluding near-critical) **and** balanced accuracy ≥ 0.90 (excluding
near-critical) **and** |50 % crossing| ≤ 0.5°. PASS needs both areas. A PASS supports the model's terrain + geometry at the
5 m scale in these areas only; it does not validate the 1 m-mast results at the Site04 ROI3 lander, the 20-realization spread,
power or communications.
