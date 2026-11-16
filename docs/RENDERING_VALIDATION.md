# Rendering validation (14 Nov 2026, 19:45 EST)

What the Explore scene draws, and how far each element can be trusted. Display only: no rendering result feeds a number.

| Element | Source | Physically grounded? | Notes |
|---|---|---|---|
| Terrain mesh (REAL SURFACE) | Bundle DEM grid (`dem.values`, 401² × 5 m crop of PGDA 78, SHA in the bundle) | **Yes, geometry** — true scale, 1:1 vertical, metres; observer at the origin | Display decimation ≤ 401² (none for these crops). Normals by `computeVertexNormals`. Height ramp colour is display only (no albedo data). |
| Horizon panorama (HORIZON GEOMETRY) | Bundle `skyline` (720 bins) | **Angles yes, distances no** — every point at one radius so the elevation angle is exact | Shade encodes the controlling distance (light = near, dark = far). Explicitly not a terrain surface (chip + note). |
| Sun disc | Bundle Sun az/el at the current sample (`gridDirection`) | **Direction yes**; size not to scale | Placed far along the true direction, including below-horizon elevations. |
| Key light and shadows | Bundle Sun azimuth; elevation clamped ≥ 0.5° | **No — illustrative** | Shadows come from a 4096² shadow map over the 2 km crop, not from the solver's ray casts; terrain beyond the crop casts nothing. Stated in the scene note. |
| Sun/Earth rays | Bundle az/el; ray ends at the bundle's first-hit distance | Yes (geometry copied) | Earth ray dashed everywhere. |
| Ridge of Record line | Bundle `derived.attribution.per_bin.ctrl_dist_m` | Yes (positions copied) | Ridges beyond the crop are declared "not drawn". |
| Critical cells | Bundle `firstHit` positions | Yes | Constant screen size; terrain and mast true scale. |
| Story / landing renders (`public/penumbra/*.webp`) | Our offline renders of the real PGDA 78 Site04 DEM | Geometry yes; **lighting illustrative** | Sun at grid az 120°, el 1.5°, chosen for composition; captioned on every use (`public/penumbra/README.md`). |

## Checks done
- Coordinate convention unchanged: the scene uses the existing `toThree` / `gridDirection` / `basis` (contract §frame); no new transform.
- Sun disc and key light derive from the same `v.sun` as the instrument readout (same sample).
- Real-surface default: the ROI export's `site04_roi3` dataset; its ridge facts and margins match the results bundle (same a-science run); the
  Playwright test "ROI export with a real DEM" still passes (far ridge declared outside the crop, not drawn).
- Tone mapping ACES (three.js), exposure 1.05; no fog, no bloom, no atmosphere.

## Performance (measured, not estimated)
Mac (Apple M5 Pro, ANGLE Metal, Chrome in the Claude desktop browser pane, DPR 2, 1440 × 900 emulated), Explore on the 401² DEM with shadows,
during a Regional-terrain camera transition: 116 animation frames recorded in a 2.0 s window; mean frame interval 8.4 ms, p95 9.2 ms,
max 16.7 ms; JS heap 122 MB; first contentful paint 176 ms. The frame count (≈58/s) is lower than the 8.4 ms mean implies, so part of the
window had no frames (likely the pane's background throttling): read it as "no frame over 16.7 ms while running", not as a sustained 119 FPS.
GPU memory: NOT MEASURED (no API in the pane). Cloud screenshots use SwiftShader software GL and are not performance evidence.

## Lighting model (final visual pass, 14 Nov 2026, 21:10–23:00 EST) — DISPLAY ONLY
No visible/blocked state, margin or number comes from the renderer; geometry is the bundle DEM unchanged.
- Photometry: McEwen (1991) Lunar-Lambert, r = A [2 L(α) μ0/(μ0+μ) + (1−L(α)) μ0], L(α) = 1 − 0.019α + 2.42e-4α² − 1.46e-6α³; regolith albedo ~0.16 (linear RGB 0.172/0.160/0.146).
- Cast shadows on the 5 m crop: per-cell march toward the bundle Sun azimuth over the 5 m DEM, then the 80 m PGDA 90 context to its display reach, height drop t²/2R (R = 1737.4 km), soft edge ±0.266° (solar radius). Computed once per sample into a 401² texture. Outside the crop the context pack's horizon maps are used; beyond the context reach the bundle skyline sets a floor (unchanged).
- Scientific mode: true Sun elevation, no fill, fixed exposure 1.4. Display mode: Sun elevation shown at ≥ 0.5°, plus a relief fill (weak hillshade from the Sun azimuth at 35°, 0.10) standing in for light scattered by sunlit terrain. Both modes are named on screen.
- Tone mapping AgX, exposure 1.2. Sun disc 0.53° and Earth disc ~1.9° at their true bundle directions (Earth drawn above −1.2°).
- Measured on Anish's Mac (Apple M5 Pro, ANGLE Metal): shadow pass 1.08 ms mean, 1.0 ms median, 1.5 ms p95, 1.6 ms max over 24 Sun positions (20 ms on the first call, shader compile).

## Correction and Final Apex additions (15 Nov 2026, 01:50 EST, Penumbra session)

- **Correction.** The line above giving "shadow pass 1.08 ms mean … over 24 Sun positions" came from a micro-benchmark of the
  full-resolution cast-shadow pass run on its own. Inside the app, session A then observed a ~1 s GPU stall per sample with that
  single-frame pass and replaced it (~00:30) with a pass spread over frames on a 10 m grid (8 of 201 rows per frame, double-buffered).
  The 1.08 ms figure does not describe the app and should not be quoted. Current measurements: `docs/PERFORMANCE_REPORT.md`.
- **Science invariance (P3).** New browser test `final-apex.spec.ts` "light mode and surface layer never change a science value". At a
  Sun-blocked hour (sample 311) it checks that the Sun and Earth readouts, the clock and the mast instrument are identical:
  - in Display mode, across every enabled surface layer;
  - in Scientific mode, with the neutral and shadow layers.
  Passes in the cloud.
- **Shadow orientation without the GPU (P3).** New unit test `tests/unit/shadow-orientation.test.ts`. At the observer node it compares
  the context-pack horizon map (the display shadow input) with the bundle's solver skyline, using the bundle frame's local north/east
  vectors:
  - the best rotation is 0° (within one 5° step);
  - a mirrored azimuth convention fits worse;
  - a 180° flip fits worse by more than 0.5°;
  - median |display − solver| is 0.80°.
  The 0.80° residual comes from three things: the horizon is taken at a ground node rather than the 1 m mast, on a 10 m grid with 48 azimuths and a finite display reach. Session A's `skylineCrossCheck` in `context.json` records it too. This is display-consistency evidence only.
- **Not done:** a pixel-level check of the GPU shadow pass itself (the shader is session A's file).
