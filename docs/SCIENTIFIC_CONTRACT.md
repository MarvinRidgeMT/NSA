# Scientific contract

## Coordinates and units

- Geographic input uses planetocentric latitude and east-positive longitude. Stored site longitudes may be negative and are normalized to east-positive `[0, 360)` for JPL requests.
- Regional and local rasters use an IAU Moon sphere with radius `1,737,400 m`, south-polar stereographic projection, and the source-declared `MOON_ME / DE421` frame.
- The local solver uses east/north/elevation axes in metres: `x=east`, `y=north`, `z=elevation`.
- Imported north-up GeoTIFF rows are explicitly flipped into the bundle's south-to-north row order. Pixel-center offsets are recorded.
- No vertical exaggeration is used by the scientific geometry. Presentation-only scaling must never feed calculations.

## Time and directions

- Time is UTC ISO-8601. The current source cases span `2026-11-14T14:00:00Z` through `2026-11-28T14:00:00Z` at 60-minute intervals.
- Azimuth is clockwise from local north: north `0°`, east `90°`.
- Sun and Earth angles are JPL Horizons airless apparent azimuth/elevation for a surface observer on body 301.
- Interpolation is permitted only inside source coverage. The engine rejects silent source-to-demo fallback outside that interval.

## Terrain visibility

Visibility means the target centre is above the maximum sampled finite-DEM skyline after exact spherical curvature drop. It does not model the angular solar disk, diffraction, radio link margin, DSN availability, power generation, thermal balance, dust or hazards.

The regional 80 m case has approximately a 15.96 km valid sampling radius. The 5 m Site01 layers cover approximately 1.0 km. Distant terrain outside those footprints can change the true horizon.

## Dimension five

Dimension five selects a named uncertainty or mission scenario. Current examples include NASA-published deterministic LDEM realizations, observer offsets, observer-height changes and bounded elevation perturbations. These are sensitivity cases, not calibrated probabilities.

## Status vocabulary

- `DEMO_ONLY`: synthetic terrain or analytic illustrative sky.
- `SOURCE_BASED_UNVALIDATED`: official input records and internal gates are present, but no independent science validation is complete.
- `VALIDATED_NASA_JPL`: reserved for a future release with recorded independent evidence. This project does not currently claim this status.

POLARIS X is research decision-support software, not flight software or a NASA endorsement.
