# Scientific contract

## Coordinates and units

- Geographic input uses planetocentric latitude and east-positive longitude. Stored site longitudes may be negative and are normalized to east-positive `[0, 360)` for JPL requests.
- Regional and local rasters use an IAU Moon sphere with radius `1,737,400 m`, south-polar stereographic projection, and the source-declared `MOON_ME / DE421` frame.
- User offsets and JPL azimuths use local east/north/up (ENU) axes in metres. Imported DEM arrays remain in their south-polar stereographic map grid (`x=grid east`, `y=grid north`); the solver rotates local ENU into that grid with the declared basis or site longitude before sampling.
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

## Scientific terrain versus visual layers (rebuild Phase 2, 14 Nov 2026)

Two kinds of raster exist and they never mix.

| | Scientific terrain | Visual layer |
|---|---|---|
| Examples | PGDA 78 5 m DEM, RMS layer, clones; PGDA 90 80 m DEM | LROC NAC average mosaic window; future albedo/hillshade images |
| Carries | elevation `values` in metres, `spacing`, `n`, origin, frame, crop hash | an image `artifact` (path, hash, size), bounds, registration, display stretch |
| Lives in | science bundles (`dem`, `localDem`, `uncertainty.*`) | `data/visual/visual_layers.json` (`polaris-visual-layers-v1`) only |
| `numericalAuthority` | implied true | always the literal `false`; `status` is `VISUAL`; label contains `VISUAL` |
| Used by | horizons, rays, observer height, margins, metrics, evidence | the renderer's surface colour only |

Rules:

1. A visual layer never contains `values`, `spacing`, `n`, `originX`, `originY`, `verticalUnits`, `layer` or `kind`. The
   schema (`schemas/visual-layers-v1.schema.json`) and all three validators reject it if it does.
2. Solvers refuse visual layers. `blender/polaris_geometry.py` (`validate_dem`, `terrain_horizon`, `trace_visibility`) and
   `app/src/science.js` (`horizonProfile`, `terrainRayProfile`) call a guard that raises `VISUAL_LAYER_AS_DEM` for any object
   flagged `status: VISUAL`, `numericalAuthority: false`, or shaped like a layer (an `artifact` and no `values`).
3. A visual layer is never mission-time illumination. The LROC average mosaic has shading from many Sun directions baked
   in; the current Sun direction, shadows, rays and visible/blocked states always come from JPL samples and the solver.
4. Registration numbers on a layer are **display-alignment evidence only** (`registration.status`), not validation.
   `appliedShiftM` records any shift the renderer applies; it is zero unless stated.
5. Outside a layer's bounds the renderer shows neutral shading. It never extends, mirrors or synthesises imagery.
6. Time, scenario and terrain semantics are unchanged: UTC sample index and scenario ID select numerical results; the
   active visual layer is a separate, independent display state and must not change any number.
7. One source of metadata: app and web both read `visual_layers.json`. Layer metadata is not copied into bundles.

Validators (same rules, one shared case file `schemas/fixtures/visual-layers-cases.json`, 20 invalid cases + guard cases):
`tools/sources/visual_layers.py`, `app/src/visual-layers.js`, `web/src/bundle/visualLayers.ts`.

## Terrain context packs: display-only surroundings and shadows (rebuild Phase 4/5, 14 Nov 2026)

`data/visual/terrain_context/<datasetId>/` (`polaris-terrain-context-v1`, built by `tools/terrain/build_terrain_context.py`)
lets the React viewer and Blender draw the 5 m crop inside its 80 m surroundings and shade it from the bundle's Sun
direction. It is **VISUAL, numericalAuthority false**, and follows the visual-layer rules above.

- `regional_f32.bin`: display copy of the PGDA 90 80 m crop from the two-site source bundle (unchanged values), placed
  by a pure translation between the two site points in projected metres. The solver never reads this copy.
- `*_horizon_u8.bin`: horizon maps. For each terrain node and each of 48 grid azimuths, the elevation angle of the highest
  **displayed** terrain in that direction (5 m crop to 1.2 km, then the 80 m crop to 20 km), with lunar curvature.
  Encoding: degrees = q × 0.05 − 3. Points are lifted 0.5 m (local) / 4 m (regional) as a shadow bias.
- Shading rule in the viewer: direct light is on where Sun elevation (true value from the bundle sample) exceeds
  max(horizon map, far horizon), with a penumbra one solar radius (0.266°) wide. The **far horizon** is the bundle's
  skyline elevation in the Sun's azimuth bin when `derived.attribution.per_bin.ctrl_dist_m` says the controlling terrain
  is beyond the displayed crops; when the bundle does not say, nothing is assumed.
- What it is not: it is not the solver. It uses finite crops, surface points instead of the mast, 48 azimuths and 8-bit
  angles. Visible/blocked states, margins, first-hit distances and every metric still come from the bundle only.
  Changing the surface layer or the lighting never changes a number (tested in `web/tests/e2e/terrain-context.spec.ts`).
- Display-consistency evidence (not validation), stored in each `context.json` → `skylineCrossCheck`: horizon at the
  observer on its mast, marched over the displayed crops, minus the bundle skyline over 720 bins. Median −0.02° (Site01
  ROI6), −0.03° (Site04 ROI3), −0.59° (Site04 ROI4); 51–61 % of bins within 0.25° at the first two; where the display is
  lower (38–60 % of bins) the controlling terrain lies outside the displayed crops, which is what the far-horizon rule covers.
- The Codex source bundles store DEM values rounded to 0.1 mm while their `cropValuesSha256` is of the unrounded crop,
  so that hash cannot be re-derived from the JSON. Each pack records this (`cropHashCheck`) and adds the hash of the
  stored values. The a-science ROI export's crop hashes do re-verify.


## Terrain context L1 (15 Nov 2026)
Context packs may carry an optional `mid` grid: 20 m block means of the PGDA 78 5 m tile (±4 km), plus its horizon map. It is drawn
between the 5 m crop and the 80 m regional crop and used by the display shadow march. Same rules as the rest of the pack: VISUAL,
`numericalAuthority: false`, never sets a visible/blocked state, never feeds the solver. Packs without `mid` still load.

## Display surface versus solver surface (15 Nov 2026)
Where a context pack has `localDisplay`, the viewer and Blender draw the NASA GSFC shape-from-shading surface (blended into LOLA at its edge,
shifted by one constant to meet the bundle ground at the observer). The solver, rays, first hits, margins and states use the bundle's LOLA
crop. The two differ by ~1–1.2 m rms (up to 8.6 m), so a drawn ray can graze or clear the drawn ground differently from the bundle state; the
bundle state is the result. The toggle "NAC relief" (web) and `--surface lola` (Blender) show the solver surface.
