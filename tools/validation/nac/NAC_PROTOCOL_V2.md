# POLARIS X — LROC NAC illumination comparison, protocol v2 (confirmatory): frozen

Written 15 Nov 2026 ~18:10 EST, **before any region 8 or region 9 image was downloaded or looked at**. The comparison script
refuses to run if this file's SHA-256 differs from the value recorded at freeze time. Author: Claude (Penumbra session).
POLARIS's status label is not changed by this test; that is a Sid/Anish decision.

## Why a v2
Protocol v1 (`NAC_PROTOCOL.md`, SHA-256 `688b54d2…76ca60`) was run on SfS region 6 (Site01 ROI6 area, Site04 west area) and,
by its own rule, did **not pass**. The cause was found afterwards: v1's observation rule set thresholds relative to each
image's 90th-percentile brightness, so images in which the whole area lies in shadow (P90 = 1–10 % of a lit image's P90,
i.e. scattered light) were labelled "lit". v1's result stands as recorded. v2 changes only the observation rule and
the crossing estimator. Its thresholds were chosen on the **region 6 data (training)**; v2 is applied to **new terrain (test)**
in two other SfS regions with their own PGDA 78 tiles.

## Reference (independent observation)
LROC NAC images orthorectified by NASA GSFC to the 5 m lattice (Bertone et al. 2026, Zenodo doi:10.5281/zenodo.17954508,
CC-BY-4.0): region A3CLR22-8 "Peak Near Shackleton" and A3CLR22-9 "de Gerlache Rim", all images in `LROC-NAC-maps/`, times from
`LROC-NAC-adjust/*.json` `m_centerEphemerisTime`. These images built the SfS DEMs, not the LOLA DEMs POLARIS uses.

## Test areas (fixed)
- **C, Site07 ROI1:** PGDA 78 Site07 tile; points on a 25 m grid within 1000 m of (−88.8063°, 123.54887°).
- **D, Site11 ROI1:** PGDA 78 Site11 tile; points on a 25 m grid within 1000 m of (−88.66821°, −68.38199°).

## Model (unchanged from v1)
Point height = bilinear PGDA 78 5 m surface + 0.05 m; great-circle ray along the Sun azimuth, 2.5 m steps in the 5 m tile
(from 5 m distance), 80 m steps on PGDA 90 to 200 km; Moon-centred elevation angles, R = 1737.4 km, float64; Sun centre
from DE440 (de440s), frame MOON_ME (MOON_ME_DE440_ME421), LT+S. Margin = Sun-centre elevation − horizon; predicted lit ⇔ margin > 0.

## Observation rule (v2, absolute brightness of the GSFC orthorectified product)
Observed **shadow** if 0 < DN ≤ 0.0020; observed **lit** if DN ≥ 0.0040; otherwise ambiguous (excluded). 3×3-pixel edge
rule as in v1 (a point whose 3×3 neighbourhood holds both a lit and a shadow pixel is excluded). An image enters an area if
≥ 200 of the area's points have finite DN > 0.

## Exclusions
Near-critical |margin| < 0.5°; results reported with and without.

## Metrics
Confusion matrix, agreement, balanced accuracy, Cohen's κ; observed-lit fraction in 0.25° margin bins; the 50 % crossing =
margin at which the observed-lit fraction first reaches 0.5, by linear interpolation between adjacent bin centres
(replaces v1's logistic fit, which a constant floor distorted).

## Pass rule
Per area: ≥ 200 observed-shadow points compared (excluding near-critical) **and** balanced accuracy ≥ 0.90 (excluding
near-critical) **and** |50 % crossing| ≤ 0.5°. PASS needs both C and D. If one region's download fails, the test is reported
as incomplete, not as a pass.

## Scope of a PASS
It supports the model's terrain (PGDA 78/90) + Sun geometry + horizon method + visibility classification at the 5 m,
ground-level scale in these areas. It does **not** observe the Site04 ROI3 lander point or its 16 m rise, does not test a
1 m mast, the 20-realization spread, power or communications.
