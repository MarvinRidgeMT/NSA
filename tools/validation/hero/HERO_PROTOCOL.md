# POLARIS X — observation check at the Site04 RoI 3 lander point: pre-registered protocol (frozen, no data yet)

Written 15 Nov 2026 ~22:15 EST on branch `science/limits-2026-11-15`, **before any image covering the Site04 RoI 3 lander
point has been found or looked at** (none exists in the sources searched; see `data/science_limits/L6_hero_observation/`).
Its SHA-256 is recorded in `HERO_PROTOCOL.sha256`; any comparison script must refuse to run if the hash differs.
Author: Claude (science-limits session). Changing POLARIS's status label on the result is a Sid/Anish decision.

**Status: the hero point stays UNCHECKED.** This protocol is the plan for when a suitable observation appears. Results from
SfS region 6, regions 8/9 (NAC v2) or any other area are **not** a stand-in for this point.

## Target
- Lander point P0: PGDA 78 RoI 3 polygon-vertex centroid, −89.78012°, −156.32023° E (grid x −2677.834 m, y −6106.132 m,
  south polar stereographic R = 1 737 400 m).
- Controlling rise: the 5 m cell with lower-left corner (−2690, −6095) m, 15–17 m from P0, which controls 28 of the 31
  near-critical hours (|margin| ≤ 0.5°) in 14–28 Nov 2026 (L7 result).

## Qualifying observation (any one)
1. An LROC NAC image orthorectified to the 5 m polar-stereographic lattice by NASA GSFC (same product family as Bertone et
   al. 2026, Zenodo doi:10.5281/zenodo.17954508) whose footprint contains P0 and the rise, with finite DN > 0 at both; or
2. a raw LROC NAC EDR/CDR frame containing P0, with a published SPICE-based camera model, orthorectified by an
   **independent** party onto a DEM that is not PGDA 78 (to avoid circularity), with stated registration accuracy ≤ 10 m.
Each image needs its acquisition time (`m_centerEphemerisTime` or the PDS label `START_TIME`/`STOP_TIME` midpoint).

## Points (fixed now)
- **Set A (lander area):** every 5 m lattice point within 100 m of P0 that is inside the image with finite DN > 0.
- **Set B (point test):** P0 itself and the 8 lattice points within 7.5 m of P0.
- **Set C (shadow tip):** for each image with Sun-centre elevation (at P0) between −1° and +3°, the predicted shadow edge
  of the rise along the anti-Sun azimuth from the rise cell, 0–200 m.

## Model (frozen)
Point height = bilinear PGDA 78 Site04 5 m surface + 1.0 m (mast) for Set B, + 0.05 m for Sets A/C (ground);
great-circle rays, 1 m near step within the 5 m tile, PGDA 90 80 m far field to 280 km, 720 bins not used (one ray per
point along the Sun azimuth); Moon-centred elevation angles, R = 1737.4 km, **float64 heights**; Sun from JPL Horizons
(observer = point, `ANG-DIAM` for r☉) at the image time. Margin m = Sun-centre elevation − horizon; m⊥ as in
`science/crossings.py`. Predicted lit ⇔ m⊥ > 0 (primary); secondary rule (reported, not used for pass): full disc
m⊥ > +r☉ (L1 found the NAC v2 crossings at +0.31°/+0.45° ≈ 1.2–1.7 r☉).
Also run all 20 PGDA 78 clones; report k of 20 clones agreeing (not a probability).

## Observation rule (as NAC v2, absolute DN of the GSFC product)
Shadow if 0 < DN ≤ 0.0020; lit if DN ≥ 0.0040; otherwise ambiguous (excluded); 3×3 edge rule as in v1/v2. For a
non-GSFC product (qualifying observation 2) the thresholds are set **on a different area of the same image** before the
P0 pixels are read, and recorded with their own hash.

## Exclusions
Near-critical |m⊥| < 0.5° reported separately (with and without). Images with |registration error| > 10 m excluded.

## Metrics
Set A: confusion matrix, balanced accuracy, κ, 50 % crossing in 0.25° margin bins (v2 estimator).
Set B: per image, predicted vs observed state at P0 (majority of the 9 points, ties = ambiguous).
Set C: observed shadow-tip distance along the anti-Sun azimuth (first lit pixel after ≥ 3 consecutive shadow pixels) minus
predicted, in metres; and the implied rise height error Δh = Δtip · tan(Sun elevation).

## Pass rule
PASS requires all of: (A) ≥ 200 observed-shadow points excluding near-critical **and** balanced accuracy ≥ 0.90 **and**
|50 % crossing| ≤ 0.5°; (B) P0 state agrees in ≥ 80 % of non-ambiguous images, with ≥ 5 such images; (C) if ≥ 3
shadow-tip images exist, median |Δh| ≤ 0.56 m (the height change at the rise that flips the 70 % Sun verdict, L7).
Fewer qualifying images than these minima → INCOMPLETE, never PASS.

## Scope of a PASS
It would support the model's terrain and visibility classification at the lander point and its controlling rise for the
imaged epochs. It would not test the 20-clone spread as a probability, power, comms, or other epochs' geometry.
