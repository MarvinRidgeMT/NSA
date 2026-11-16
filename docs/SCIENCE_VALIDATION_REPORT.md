# Science validation report

## Release decision

**Status: SOURCE-BASED BUT UNVALIDATED.** Official source identifiers, frame declarations, parser checks, raster orientation tests and numerical regression tests pass. A pre-registered comparison against NASA SVS 4930 frames has been run and passed its protocol, but every compared sample was lit in both products, so it has low discriminating power; independent illumination validation is therefore not complete, so this release does not claim validated lunar illumination, communications availability or mission readiness.

## Gates completed

| Gate | Result | Evidence |
|---|---|---|
| No synthetic substitution in source mode | PASS | Source pipeline raises on raster/API/parser failure; bundles retain explicit source status. |
| Projection implementation | PASS (internal) | Analytic south-polar formula agrees with `pyproj` IAU 30100→30135 for all four configured sites. |
| Longitude convention | PASS (internal) | Negative stored longitudes are converted to east-positive JPL request values; requested and reported centres match. |
| Raster orientation and pixel registration | PASS (internal) | Automated north-up row-flip test plus recorded source pixel, pixel-centre and observer offset. |
| Local azimuth to polar-grid rotation | PASS (internal) | JavaScript, TypeScript and Blender regressions verify Site01 local north/east against longitude-derived radial/tangential grid vectors; a synthetic local-east ridge test rejects the former naive grid-axis behavior. |
| JPL declarations/parser | PASS (internal) | Raw responses must declare Moon body 301, `MEAN_ME`, east-positive longitude, airless apparent angles, UTC, and exact azimuth/elevation columns. |
| Time monotonicity and coverage | PASS | Bundle and browser validators reject non-increasing or out-of-coverage ephemerides. |
| Curvature and obstruction | PASS (unit/regression) | Exact spherical tangent-plane curvature; synthetic ridge and first-blocking-cell tests. |
| Blender source export | PASS (artifact) | Nonempty `.blend`, GLB v2, manifest hashes and start/middle/end renders. |
| Browser source workflow | PASS (smoke) | Cached two-site bundle and full Site01 import were exercised in Chrome with no console/page errors. |
| Embedded global Moon artifact | PASS (artifact) | NASA SVS GLB v2 header, declared length and frozen SHA-256 are checked; this verifies the downloaded artifact, not numerical terrain accuracy. |
| Independent illumination comparison (NASA SVS 4930, pre-registered) | PASS per frozen protocol — low discriminating power | 169 frames × 3 sites, 331 compared samples, agreement 1.00 at every site, but all compared samples were lit in both products (no shadow case tested). `docs/validation/SVS4930_RESULT.md`. Release label unchanged. |
| PGDA 69 reference-map artifact | PASS (artifact) | Eight raw source hashes, 17 PGDA 78 ROI projections/statistics and ten generated layer PNGs are checked. The differing 18.6-year/disc-edge/surface-pixel definition prevents treating it as a matched validation result. |

## Gates not completed

| Gate | Result | Consequence |
|---|---|---|
| Discriminating illumination comparison (shadow cases, numerical product at matching resolution) | NOT RUN | The SVS 4930 gate above passed but tested only lit samples at ~113 m/px; source output remains unvalidated. |
| Long-range horizon beyond the 32 km regional crop | NOT AVAILABLE | Distant ridges may be absent from visibility results. |
| Cross-alignment of Cesium visual tiles and numerical PGDA grids | NOT RUN | Cesium is visual context only. |
| Partial solar/Earth disk, thermal, power, link budget, navigation and hazard models | NOT IMPLEMENTED | Target-centre geometric visibility must not be interpreted as subsystem availability. |
| Flight qualification or agency review | NOT APPLICABLE | Research prototype only. |

## P1 — the Site01 14:00 UTC Sun/Earth reversal, reproduced and explained

Two user screenshots of the same case disagreed: 09:55 ET showed **Sun BLOCKED / Earth VISIBLE**, 11:22 ET showed
**Sun VISIBLE / Earth BLOCKED**, at identical displayed angles. Frozen case (`app/tests/site01-source-regression.test.js`):

- Connecting Ridge / Site01, lat −89.4632°, lon −137.4900° E (= 222.5100° E), observer +2 m, 2026-11-14T14:00:00Z
- JPL Sun az 256.984524°, el +1.435750°; JPL Earth az 135.424493°, el −4.411757°

| Model | Sun skyline | Sun margin | Sun | Earth skyline | Earth margin | Earth |
|---|---:|---:|---|---:|---:|---|
| Corrected (local ENU rotated into the south-polar grid, 80 m regional crop) | −4.224789968° | +5.660539968° | visible | +1.126075677° | −5.537832677° | blocked |
| Legacy (local azimuth used as if it were a grid bearing) | +1.859482497° | −0.423732497° | blocked | −4.687672293° | +0.275915293° | visible |

The legacy row reproduces the 09:55 capture exactly; the corrected row reproduces 11:22. The reversal is therefore a
**physics/frame bug in the earlier build**, not a data change: at longitude L the local north direction in the polar
stereographic grid is (sin L, cos L), so grid_az = local_az + L (≈ −137.5° at Site01), and the old code tested terrain
roughly 137° away from the true target direction. Inputs were identical in both runs (hashes below). The corrected Earth
ray's first sampled hit is 70 m out with clearance −6.864675282 m; that is a discrete sample, not sub-cell ground truth.
Independent cross-check: the a-science solver (separate code, 720-bin skyline, 5 m near field) gives Sun +3.97° and
Earth −5.30° at the same instant — same signs and same states, different magnitudes because of the different DEM layers
and reach. Both remain `SOURCE_BASED_UNVALIDATED`.

Frozen provenance: Site01 bundle `6a16ee59965e47afe54527c0b2bcdd90c6d40ba40a2423ca964e7da8e89a4fb6`; regional crop values
`d27c5aa679cd00ffee0a95ce36e0049b3189b477a6e14efb941eecac92d73b5d`; PGDA 78 5 m source
`3ba7b97cb00a2bcf21189c3aeb535f65afc21207154ab9f0d43c5bdc1f7e747e`; Sun raw Horizons
`6346b02074c2711eec549045e219e58b24a8dd85f656c10253158749da7204be`; Earth raw Horizons
`65a2c8eeee12a23f43bac4d0f9d0d01ae9cdc881a483d1003abd6dbfa4db7c81`; runtime cache
`app/data/polaris-runtime-source-case.json` `713099a1623690fd761dcab8b3b2a0439e3f87f96cddd58d0d722fddc4e72062`.
Neither screenshot is used as a truth label; the test locks the corrected computation and the explanation of the legacy one.

## Numerical scope

Source cases use 401×401 terrain arrays. The regional layer is 80 m per pixel with about 15.96 km valid radius; Site01's local layers are 5 m per pixel with about 1.0 km valid radius. Time sampling is hourly over 14 days. Short events between samples can be missed. Terrain interpolation and horizon azimuth discretization add model error that is not yet bounded by an external truth set.

## Required next validation

Select an independently published, frame-compatible south-pole illumination product or observation; freeze its version and checksum; define matched sites and UTC samples; compare Sun visibility/clearance; record tolerances before viewing results; and publish discrepancies. Until that is complete, retain `SOURCE_BASED_UNVALIDATED` in code, UI, Blender metadata and reports.
