# Science validation report

## Release decision

**Status: SOURCE-BASED BUT UNVALIDATED.** Official source identifiers, frame declarations, parser checks, raster orientation tests and numerical regression tests pass. Independent illumination validation has not been run, so this release does not claim validated lunar illumination, communications availability or mission readiness.

## Gates completed

| Gate | Result | Evidence |
|---|---|---|
| No synthetic substitution in source mode | PASS | Source pipeline raises on raster/API/parser failure; bundles retain explicit source status. |
| Projection implementation | PASS (internal) | Analytic south-polar formula agrees with `pyproj` IAU 30100→30135 for all four configured sites. |
| Longitude convention | PASS (internal) | Negative stored longitudes are converted to east-positive JPL request values; requested and reported centres match. |
| Raster orientation and pixel registration | PASS (internal) | Automated north-up row-flip test plus recorded source pixel, pixel-centre and observer offset. |
| JPL declarations/parser | PASS (internal) | Raw responses must declare Moon body 301, `MEAN_ME`, east-positive longitude, airless apparent angles, UTC, and exact azimuth/elevation columns. |
| Time monotonicity and coverage | PASS | Bundle and browser validators reject non-increasing or out-of-coverage ephemerides. |
| Curvature and obstruction | PASS (unit/regression) | Exact spherical tangent-plane curvature; synthetic ridge and first-blocking-cell tests. |
| Blender source export | PASS (artifact) | Nonempty `.blend`, GLB v2, manifest hashes and start/middle/end renders. |
| Browser source workflow | PASS (smoke) | Cached two-site bundle and full Site01 import were exercised in Chrome with no console/page errors. |

## Gates not completed

| Gate | Result | Consequence |
|---|---|---|
| Independent illumination comparison against an authoritative external product or observation | NOT RUN | Source output remains unvalidated. |
| Long-range horizon beyond the 32 km regional crop | NOT AVAILABLE | Distant ridges may be absent from visibility results. |
| Cross-alignment of Cesium visual tiles and numerical PGDA grids | NOT RUN | Cesium is visual context only. |
| Partial solar/Earth disk, thermal, power, link budget, navigation and hazard models | NOT IMPLEMENTED | Target-centre geometric visibility must not be interpreted as subsystem availability. |
| Flight qualification or agency review | NOT APPLICABLE | Research prototype only. |

## Numerical scope

Source cases use 401×401 terrain arrays. The regional layer is 80 m per pixel with about 15.96 km valid radius; Site01's local layers are 5 m per pixel with about 1.0 km valid radius. Time sampling is hourly over 14 days. Short events between samples can be missed. Terrain interpolation and horizon azimuth discretization add model error that is not yet bounded by an external truth set.

## Required next validation

Select an independently published, frame-compatible south-pole illumination product or observation; freeze its version and checksum; define matched sites and UTC samples; compare Sun visibility/clearance; record tolerances before viewing results; and publish discrepancies. Until that is complete, retain `SOURCE_BASED_UNVALIDATED` in code, UI, Blender metadata and reports.
