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

## Known science issue seen while building this (for the science branch)

`app/src/science.js` (`horizonProfile`, line ~39) still steps rays along `(sin az, cos az)` in the polar-stereographic **grid**.
JPL azimuths are **local**. At Site01 (L = −137.49°) local north points along grid bearing ≈ 222.5°, so terrain tests are
rotated by roughly the site longitude. The Site01 "Sun 0 % / Earth 100 %" result in the legacy app should be treated as
suspect until this is fixed and regression-tested (ridge due local-east must block az 90°, not az 270°).
