# What the viewer needs from science-bundle-v2

Status: **proposal from b-experience to the science branch. Additive only.** Nothing here changes an existing field in
`schemas/science-bundle-v2.schema.json` or `docs/SCIENTIFIC_CONTRACT.md`.

## Why

The viewer (`web/`) never computes a skyline, a visibility flag, a margin or a metric. The current Codex source cases
(`app/data/polaris-source-*-v2.json`) carry raw inputs only: DEM crops and JPL Horizons samples. With those the viewer can show
terrain, the clock and Sun/Earth angles, and it shows "not in bundle" everywhere a science result would go.

To show margins, strips, constraint results and failure cross-sections, each dataset needs one extra optional object:
`datasets[i].derived`.

## `datasets[i].derived`

```jsonc
{
  "producer": { "name": "science/…", "version": "…" },
  "status": "SOURCE_BASED_UNVALIDATED",          // same vocabulary as validation.status (+ DEMO_ONLY)
  "frame": {                                      // optional; if absent the viewer derives it from site longitude for DRAWING only
    "localNorthInGrid": [sinL, cosL],
    "localEastInGrid":  [cosL, -sinL]
  },
  "skylineBinDeg": 0.5,
  "scenarios": [                                  // first one = baseline
    {
      "id": "baseline", "label": "Baseline · 2 m mast", "kind": "baseline|mast_height|observer_offset|dem_realization|arrival_shift|elevation_perturbation|repair",
      "description": "…",
      "observer": { "xM": 0, "yM": 0, "groundM": 1946.2, "mastM": 2 },   // grid metres in the DEM crop's frame
      "skyline":  { "azimuthDeg": [...], "elevationDeg": [...], "reachM": [...], "coverage": ["full"|"truncated", ...] },
      "samples": {                                // arrays aligned 1:1 with ephemeris.samples
        "sun":   { "visible": [bool], "horizonElDeg": [num], "marginDeg": [num], "firstHitM": [num|null] },
        "earth": { "visible": [bool], "horizonElDeg": [num], "marginDeg": [num], "firstHitM": [num|null] },
        "both":  { "visible": [bool] }
      },
      "metrics": [
        { "id": "sun_fraction", "label": "Sun visible (centre)", "value": 81.17, "unit": "%",
          "constraint": { "op": ">=", "threshold": 60 }, "marginToLimit": 21.17, "pass": true }
      ],
      "failures": [                               // one per blocked interval (worst sample)
        { "id": "…", "target": "sun|earth", "sampleIndex": 12, "time": "…Z",
          "azimuthDeg": 257.0, "targetElDeg": 1.44, "horizonElDeg": 1.86, "marginDeg": -0.42, "blockedSamples": 5,
          "firstHit": { "distanceM": 140, "xM": …, "yM": …, "heightM": …, "cell": [ix, iy] },
          "profile": { "distanceM": [...], "terrainM": [...], "rayM": [...] } }   // curvature-corrected, as used by the solver
      ]
    }
  ]
}
```

Rules the viewer enforces (`web/src/bundle/validate.ts`): every array length matches the sample count, every number is finite,
times are strictly increasing UTC with a `Z`, azimuths are in `[0, 360)`. A bundle that breaks any rule is refused with a
specific message.

## Status shown on screen

The badge is the **most cautious** of: top-level `validation.status`, every dataset's `validation.status`, every
`derived.status`, `demo: true`, and any DEM whose `kind` is not `nasa`. Anything synthetic shows **DEMO**.

Note: the schema's `validation.status` enum lists `SOURCE_BASED_UNVALIDATED` and `VALIDATED_NASA_JPL` but not `DEMO_ONLY`,
although `SCIENTIFIC_CONTRACT.md` defines `DEMO_ONLY`. The DEMO fixture uses `DEMO_ONLY`; suggest adding it to the enum.

## The only numeric work the viewer does

- Binary-search a UTC time among `ephemeris.samples`; refuse anything outside `[first, last]`.
- Interpolate between the two bracketing samples: azimuth on the shortest arc (359° → 1° passes 0°), everything else linearly.
  Between samples the UI says "between samples"; visibility shows "transition" when the two samples disagree.
- Rotate local az/el into the DEM grid to **draw** rays (`web/src/bundle/frame.ts`). Never used for any result.

## Decision evidence A1–A4 — single version (T-ORG-02, 14 Nov 2026 13:56 EST)

Replaces both earlier copies (this tree's "Decision-evidence fields" proposal and the `integration` worktree's
"Decision evidence (A1–A4)" section). Rule: **what science/ actually emits wins**; this list records it, and where the
science branch has not emitted a block yet, it fixes the names the viewer reads. snake_case in JSON; the viewer camel-cases
on load and copies values, never computes them. Every block is optional; a missing block shows "not in bundle".

**Where the viewer reads them** (both supported; the results bundle is primary):
1. `polaris-science-results-v1` (one site × mast per file, `data/bundles/*.json`): top-level `derived.{attribution,
   coverage, certainty_curve, certainty_height_m, requirements, margin_series}`. Primary because it is what science/ writes
   first and it carries the full hourly samples the ribbon and the ridge seek use.
2. POLARIS-X5D-v2 export (`data/viewer/*.json`, `science/viewer.py`): `datasets[i].derived.<same keys>`.

| Block | Field | Type / unit | Source of truth |
|---|---|---|---|
| A1 `attribution` | `label` | status string | emitted (a-science `13d23d4`) |
| | `method` | object of strings (`clustering`, `gap`, `hours`, `ctrl_idx`, `ridge_idx`, `source`, `of_record`) or string | emitted |
| | `ridges[]`: `id`, `centroid_lat`, `centroid_lon` (deg), `dist_km`, `dist_range_km` [min,max] (km), `az_span_deg` [a,b] (deg, clockwise; end < start wraps through north), `n_bins`, `height_m`, `relief_m` (m), `max_elev_deg`, `min_gap_deg` (deg, runner-up gap), `source` ∈ {`near_5m`,`far_80m`}, `source_counts`, `sun_loss_h`, `earth_loss_h`, `ctrl_h`, `sun_ctrl_h`, `earth_ctrl_h` (h, hourly samples × 1 h), `of_record` (bool) | numbers as stated | emitted |
| | `per_bin`: `ridge_idx` (index into `ridges[]` or null), `ctrl_idx`, `ctrl_dist_m` (m), `gap_deg`, `source` — one per skyline bin | arrays of length `skyline.bins` | emitted. (`integration`'s `ridge_id` strings are also read.) |
| | optional: `scenario_id` (default baseline), `centroid_x_m`/`centroid_y_m` (grid m, for 3D) | | `integration` proposal, read if present |
| A2 `certainty_curve` | rows `{mast_m, metric, nominal, min, p10, median, p90, max, n_clones, pass:"k/N"}`; metrics `sun_centre_pct`, `both_centre_pct` | % ; `pass` k ≤ N = n_clones | IMPLEMENTATION_PROMPT A2 (not emitted yet) |
| | `certainty_height_m` | `{metric: m or null}` (null = no tested mast passes on every map) | A2 |
| | `requirements` | `[{metric, label, op: ">="|"<=", threshold, unit}]` | A2; team values below |
| | `certainty_note` | string, e.g. "3 heights only" (fallback) | `integration` proposal |
| A3 `coverage` | `critical_threshold_deg` (deg), `n_critical_h` (h), `covered_frac` (0–1), `uncovered_ridges` [ids]; optional per-target `sun`/`earth` objects with the same three numeric keys | | A3 + a-science computes Sun and Earth (local `d14af8d`): **its emitted names win**; viewer reads both forms |
| A4 `margin_series` (alias `margins`) | `scenario_id`, `sun_margin_deg`, `earth_margin_deg`, `sun_clone_min_deg`, `sun_clone_max_deg`, `earth_clone_min_deg`, `earth_clone_max_deg` (deg, one per hourly sample), `n_clones`, optional `clone_ids`, `sun_truncated`/`earth_truncated` (bool per sample) | | a-science name `margin_series` (local `d14af8d`); field names from the viewer contract until the push shows otherwise |

**Team requirements** (Anish, 14 Nov ~13:50 EST): `sun_centre_pct >= 70`, `both_centre_pct >= 40`. Used for PASS/FAIL only
when a bundle declares none (`web/src/bundle/requirements.ts`), labelled as a team requirement on screen.

**Checks** (`validate.ts`, refuse with a specific message): `source` ∈ {near_5m, far_80m}; `per_bin.ridge_id` names a listed
ridge; `pass` = "k/N" with k ≤ N = `n_clones`; min ≤ median ≤ max; 0 ≤ `covered_frac` ≤ 1; every A4 array has one value per
sample. Shown as warnings, never fixed: a margin sign that disagrees with the visibility flag.

**Display rules:** ridges of record first, then by loss hours; per-requirement pass counts are shown separately (a joint
"passes all" count is never derived from marginal counts); wording "passes on k/N alternate terrain maps tested", never a
probability; if coverage < 50 % every such line carries "the maps cover only X % of the terrain that controls this result";
the clone band is drawn only under the scenario named by `margin_series.scenario_id`.

**Lookup rules the viewer applies (14 Nov 14:30 EST; unit-tested against the real Site04 ROI3 bundle):**
- Skyline bins are **centred** on i·(360/bins)°. A body azimuth maps to the **nearest** bin, as `science/attribution.py` does
  (`method.hours`). An earlier floor rule put 4 of 75 Earth-loss hours on the wrong ridge; with nearest, per-ridge loss hours
  recomputed from `samples` + `per_bin.ridge_idx` equal `sun_loss_h` / `earth_loss_h` exactly.
- Loss hours are hourly samples × 1 h and are **disjoint**: each blocked hour belongs to one ridge, and per-target sums equal the
  number of blocked samples (Site04 ROI3 1 m: Sun 19 = 19; Earth 41 + 34 = 75).
- "Height vs site ground" on screen is `relief_m` (ridge `height_m` − site `height_m`); `height_m` itself is a DEM height above
  the reference radius and is only shown in a tooltip.
- `attribution.scenario_id` / `scenarioId` (export; default baseline) is honoured: ridges are never shown under another
  scenario's series.
- 3D: the ridge line is drawn from `per_bin.ctrl_dist_m` along each bin azimuth, placed on the DEM crop for display; points
  outside the crop are not drawn and the caption says so.

**Certainty Height sidecar (interim, until A2 is in the bundles):** `web/public/certainty/sidecar.json`, format
`polaris-certainty-sidecar-v1`, written by `tools/certainty/build_certainty_sidecar.py` from
`data/batch/2026-11-14/certainty_height*/clone_sweep_summary.csv` (a-science `971df9a`; CSV SHA-256 recorded inside). Keys per
site id (`site04_roi3`, `site01_roi6`): `sampled_masts_m`, `certainty_curve` (A2 rows), `certainty_height_m`, `agreement_mast_m`
(Sun spread ≤ `agreement_tolerance_p` = 1.0 pt), `all_maps_100pct_sun_mast_m`. A bundle's own `derived.certainty_curve` always
wins. The batch is a separate solver from the repo bundles (2 knife-edge samples apart at 1 m); the panel says so.

**Open check (14:35 EST):** a-science reports A3/A4 on GitHub (`d7b5463`) and A2 locally (`4bb48b5`: `derived.certainty` + flat
`derived.certainty_curve`, `derived.certainty_height_m`). Not yet fetched into the viewer's clone, so not yet verified here: the exact
A3/A4/A2 key names, and whether `certainty_height_m` means "every map meets the team requirements" or "Sun 100 % on every map"
(a-science's 1.75 m is the latter). Until verified, a bundle-supplied certainty height is labelled "as the bundle defines it".

**Differences between the two earlier copies (resolved here):** `integration` used `ridge_id` per bin and `margins`;
science/ emits `ridge_idx` and names A4 `margin_series` → both read. `integration` had `requirements`, `certainty_note`,
`centroid_x_m/y_m`, `scenario_id` → kept. This tree had `margin_range`, `near_zero_margin_deg` and a nested
`{sun,earth,footprint}` coverage → kept only as read-compatible; not requested from science/. This tree's 90 % coverage
warning → replaced by the prompt's 50 % rule.

## Stretch PILOT: arrival-slip strip

When a `polaris-science-results-v1` bundle carries `derived.arrival_slip`, the viewer adapter copies it to
`dataset.derived.arrivalSlip` without changing a value. The Decision area may render its `points[]` as a strip and exact
traceability table. Thresholds, slip values, nominal percentages, clone min/max, k/N, result IDs and `PILOT` labels all
come from the bundle. The browser does not recompute a visibility percentage, threshold outcome, clone count or colour
percentage.

## Stretch PILOT: information-hotspot overlay

When `derived.hotspots` is present, the adapter copies it to `dataset.derived.hotspots` unchanged. The Evidence map
may offer a `Where better data matters` toggle and plot the bundle's pre-ranked `top_tiles[]`. Marker rank, tile ID,
latitude/longitude, score, score unit, method caption, result ID and `PILOT` label all come from the bundle. The browser
performs only map-coordinate projection and in-frame filtering; it does not recompute variance, a skyline Jacobian,
coverage, ranking, score or display band. A zero-positive-tile bundle must show the bundle-provided zero-state caption
rather than imply that clone agreement covers the far-field skyline.

## Stretch PILOT: flip-forecast table

When `derived.flip_forecast` is present, the adapter copies it to `dataset.derived.flipForecast` unchanged. The
Decision area renders only a compact `Forecast vs actual` table from `forecast_vs_actual[]`; it is not a headline
metric. Case counts, predicted and actual flip counts, TP/FP/FN, precision and recall display strings, method text,
result IDs and `PILOT` labels all come directly from the bundle. In particular, `not evaluable` remains visible when
the bundle's precision or recall is null. The browser does not calculate a confusion matrix, percentage, threshold
outcome or replacement skyline controller.

## Known science issue seen while building this (for the science branch)

`app/src/science.js` (`horizonProfile`, line ~39) still steps rays along `(sin az, cos az)` in the polar-stereographic **grid**.
JPL azimuths are **local**. At Site01 (L = −137.49°) local north points along grid bearing ≈ 222.5°, so terrain tests are
rotated by roughly the site longitude. The Site01 "Sun 0 % / Earth 100 %" result in the legacy app should be treated as
suspect until this is fixed and regression-tested (ridge due local-east must block az 90°, not az 270°).

## Visual layers (`polaris-visual-layers-v1`) — display only, separate from bundles (14 Nov 2026, rebuild Phase 2)

Visual rasters (for example the LROC NAC average mosaic over Site01) are **not** part of any science bundle. They are
described in one file, `data/visual/visual_layers.json`, schema `schemas/visual-layers-v1.schema.json`, generated by
`tools/sources/build_visual_layers.py` from completed, registered windows only.

Per layer: `id`, `role` (albedo | morphology | hillshade | reference-image), `title`, `label` (contains `VISUAL`, e.g.
`LROC NAC AVG · VISUAL`), `status: "VISUAL"`, `numericalAuthority: false`, `productId`, `sourceUrl`, `artifact`
{path, sha256, width, height, format}, `sourceHash` {kind, sha256, wholeFileSha256|null}, `pixelSizeM`, `projection`
(south polar stereographic, 90° S / 0° E, R 1737400 m, units m), `frame`, `boundsM` (pixel edges, +x toward 90° E,
+y toward 0° E), `rowOrder: "north-to-south"`, `registration` {method, against, offsetM, peakNcc,
status: "display-alignment-evidence-only", appliedShiftM}, `display` {processing, stretchLow, stretchHigh}, `limitations[]`.

Viewer side: `web/src/bundle/visualLayers.ts` has the types, `validateVisualLayers`, `assertNumericalDem` (throws
`VISUAL_LAYER_AS_DEM`) and `layerCoverageOnCrop` (how much of a DEM crop a layer covers; 0 means do not drape).
The viewer must show the layer's `label` whenever it is active, keep geometry from the bundle's DEM, and keep lighting
and visible/blocked states from the bundle's samples. Not yet wired into `App.tsx` / `Scene3D.tsx` (waiting for the
texture download to complete and for the Penumbra edits to those files to finish).

## Terrain context packs (`polaris-terrain-context-v1`) — display only (14 Nov 2026, rebuild Phase 4/5)

`npm run sync-bundles` copies `../data/visual/terrain_context/<datasetId>/` to `public/context/<datasetId>/` and
`../data/visual/visual_layers.json` (+ its images) to `public/visual/`. Neither is a science input.

`src/bundle/terrainContext.ts` loads `context/<siteId>/context.json` when a dataset with a DEM opens. The pack is used
only if `status` is `VISUAL`, `numericalAuthority` is `false`, `local.cropValuesSha256` equals `dataset.dem.cropValuesSha256`,
the three binaries have the sizes the metadata implies, and (where WebCrypto exists) their SHA-256 values match.
Otherwise the scene falls back to the crop-only rendering, unchanged.

With a pack, `src/three/TerrainSurface.tsx` draws L0 (the bundle's 5 m crop, full resolution, true scale), L2 (the 80 m
regional crop, true scale, cut out under L0) and a skirt on L0's edge (visual seam). One shader lights both from the
bundle's Sun direction and darkens terrain whose horizon (horizon map, or the bundle skyline for terrain beyond the
crops) is above the Sun's true elevation at the current sample. Surface layers (`src/store/surface.ts`): neutral
regolith, registered image (only where a `visual_layers.json` layer covers ≥ 20 % of the crop), elevation, slope,
normals, source coverage, Sun-shadow model. The chip `surface-layer-label` always names the layer and its source.
The viewer still computes no skyline, visibility, margin or metric.


## Context pack `mid` (optional, 15 Nov 2026)
`context.json` may add `mid {file, sha256, n, spacingM, originX, originY, product, source}` and `horizon.mid` (same shape as
`horizon.local`). The loader checks sizes and SHA-256; packs without `mid` load as before. Display only.

## URL parameters
`bundle`, `site`, `t` (ISO 8601 ending `Z`), `sc`, `cam` (camera view id), `layer` (surface layer id). Unknown values are ignored;
a time outside the bundle's samples is refused.
