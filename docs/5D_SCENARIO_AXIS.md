# 5D scenario axis, Sun/Earth sky model and terrain framing (15 Nov 2026)

Release status unchanged: **SOURCE-BASED UNVALIDATED**. The scenario axis is a set of named, deterministic alternatives,
not a probability distribution, and never a spatial dimension.

## 1. Terrain "too small": diagnosis (measured, not guessed)

| Level (web + Blender) | Source | Coverage | Spacing | Elevation range | Triangles |
|---|---|---|---|---|---|
| L0 near field | PGDA 78 5 m LOLA tile (bundle crop; SfS display surface where it exists) | 2.0 km × 2.0 km | 5 m | Site01 ROI6 315 m · Site04 ROI3 552 m · ROI4 565 m | 320,000 |
| L1 ring | 20 m block means of the same PGDA 78 tile | 8.0 km × 8.0 km | 20 m | Site01 1,071 m · Site04 2,468–2,480 m | 320,000 |
| L2 regional | PGDA 90 LDEM 80 m | 32 km × 32 km (display reach 14–16 km) | 80 m | Site01 4,559 m · Site04 4,827 m | 320,000 |

Source tiles: PGDA 78 Site01 / Site04 5 m tiles are 3200 × 3200 px = **16 km × 16 km**. The solver uses the full tile plus
the 80 m LDEM to 280 km; the display uses the three levels above.

Causes found:
1. **Camera framing** (main cause): the default Explore view (`approach`) and the `regional` view framed only the 2 km
   L0 crop, from 0.4–1.6 km away. The 32 km regional terrain with 4.6–4.8 km of relief (Shackleton crater) was only
   visible from the "South-pole context" view.
2. **No vertical exaggeration**: polar relief within 2 km is a few hundred metres over 2 km, so 1:1 looks flat.
3. **Sun/Earth discs inside the drawn terrain**: the discs were drawn 6 km out while terrain is drawn to ~16 km, so
   ridges beyond 6 km could not hide them.
4. Not causes: mesh scale (1 unit = 1 m), coordinate transforms (grid → three.js `(x, z, −y)`), datum (heights above
   the 1737.4 km sphere) and clipping (far plane 90 km) were all checked and correct.

Fixes (web, display only, `web/src/three/Scene3D.tsx`, `web/src/components/SurfaceLayer.tsx`, `web/src/store/ui.ts`):
- `Regional terrain` view now frames the 8 km ring (`H × 2.9` out, `H × 1.9` up) when the context pack is loaded.
- **Vertical exaggeration** select (1× physical, 2×, 3×, 5×, 10×; `data-testid="vertical-exaggeration"`) next to the
  Surface picker. It scales the drawn terrain, mast, rays and markers as **one group**, so every above/below relation
  between a sight line and terrain is preserved; Sun/Earth bodies use `skyBodyPosition` (tan(el) × k, azimuth
  unchanged, unit-tested). The mast-eye view is always 1×. A "vertical ×k · display only" tag shows in the scene.
  Bundle margins, visibility and metrics never change (checked in the browser: Sun −0.04° blocked at 1× and 5×).
- Sun/Earth discs are drawn beyond the drawn terrain (`1.4 × displayReachM`, ~20–22 km). When the bundle says a body is
  blocked it is drawn faint with a dashed "Sun/Earth direction · hidden by terrain (bundle)" label, never as visible.

Not done (time): a larger 5 m near field (the 16 km tile allows ±7 km at 5 m, but 48-azimuth horizon maps at that
size are ~120 MB per site); a clipmap/streaming LOD.

## 2. Fifth axis: recomputed scenarios with full time series

Before: real ROI bundles carried `baseline` and `mast10` only. Now each ROI site carries 9 scenarios
(`data/viewer/polaris-x5d-roi-2026-11-14-v2.json`):

| Family | Scenarios | How computed |
|---|---|---|
| baseline / mast height | 1 m, 10 m | unchanged (byte-identical to the previous export) |
| `dem-clone` | 3 of the 20 NASA PGDA 78 clones: lowest / middle / highest by hourly Sun+Earth % in `derived.margin_series` | near field replaced by clone k; ground height from the clone; skyline, JPL Horizons at that height, bisection-refined crossings |
| `position-offset` | ±100 m local east / north | great-circle move in local ENU; new DEM ground height, skyline, **new JPL Horizons samples** (local azimuths differ near the pole) and refined crossings |

Where all 20 clones tie on hourly metrics (Site01 ROI6, Site04 ROI4) the picks are labelled "all 20 tie", not ranked.
Each scenario bundle is `data/bundles/scenarios/<baseline>__<tag>.json` with every Horizons response archived in
`data/raw/horizons/` and hashed in `MANIFEST.json`. Build: `.venv/bin/python -m science.scenario_bundles --site <roi>`;
export: `science/viewer.py` (adds `metric.delta` = scenario − baseline).

Site04 ROI3 (14–28 Nov 2026, centre visibility, 1 m mast):

| Scenario | Sun % | Earth % | Both % | Longest Sun gap |
|---|---|---|---|---|
| baseline | 94.2 | 77.7 | 71.9 | 19.4 h |
| clone 3 / 7 / 19 | 88.8 / 90.7 / 97.2 | 75.7 / 77.2 / 77.3 | 64.5 / 67.9 / 74.5 | 37.7 / 31.3 / 9.4 h |
| moved 100 m N / S / E / W | 71.3 / 69.8 / **0.0** / 72.6 | 69.1 / 54.0 / **0.0** / 43.8 | 53.5 / 23.7 / 0.0 / 16.4 | 52.6 / 101.5 / 336 / 92.2 h |

100 m east the ground is 8.6 m lower on a ~10° slope; that point's lowest skyline (2.77°) is above the Sun's highest
elevation (1.61°), so the Sun is never visible. Checked against the DEM heights and the skyline, not a solver fault.
Clone results agree with the independent `science/margins.py` clone series within 0.05 points (hourly method).

Web: `web/src/store/view.ts` `withScenarioGeometry` swaps in an offset scenario's own JPL samples and local basis
(refuses mismatched times); the 5D table (Decision workspace) shows all families with deltas and the offset grid;
the metrics source tag names the clone or offset. Blender `bundle_v2.with_scenario_geometry` applies the same rule.

## 3. Blender Sun/Earth sky model

`blender/sky_model.py` (pure Python, `blender/test_sky_model.py`) + `build_from_nasa_bundle.py`:
- **True sky shell** (radius ≥ 20 km, beyond the drawn terrain): the bundle skyline, the 14-day Sun and Earth paths
  coloured by the bundle visible flag (gold/blue = clear, dark = blocked), and Sun/Earth bodies at true directions and
  true angular size (Sun 0.2666°, Earth 0.95° nominal; the viewer bundle carries no per-sample radii). Earth is lit by
  the bundle Sun lamp, so it shows a phase. Distances are not to scale.
- **Sky chart** (overview only, elevation ×5, labelled "NOT TO SCALE"): every same-point 5th-axis skyline (baseline,
  mast, clones), the true 0° horizontal, and the Sun/Earth paths and markers.
- **Mast-eye renders** (`eye_sun_start`, `eye_sun_transition`, `eye_earth_frame…`): camera at the observer's eye, true
  angles. In the Site04 ROI3 Earth view the bundle skyline lies on the drawn ridge line.
- Sky objects never cast shadows or light the terrain; they are not exported to the GLB (GLB parity checks unchanged).
- Run: `bash rebuild_blender_hero.command site04_roi3` (or `site01_roi6`); `--no-sky` and `--chart-exaggeration` options.

## Limitations
- Visibility = target **centre** above a finite-DEM skyline, hourly samples with bisection-refined crossings; not power,
  not a DSN link.
- Clone counts are counts of NASA terrain models, not probabilities. Only 3 of 20 clones are carried as full series.
- With `--surface sfs` the drawn 5 m terrain is the NASA GSFC SfS display surface where it exists; the solver used LOLA.
  At a 1 m mast, a metre of near-field difference moves the apparent horizon by degrees, so eye-level views can differ.
