# Pre-registered illumination comparison: POLARIS X vs NASA SVS 4930 (frozen before any comparison)

Written 15 Nov 2026 00:30 EST by b-experience session A, before any POLARIS result was compared with any frame.
What had been seen at this point: the SVS 4930 web page, the frame directory listing, and two whole frames viewed for their
date overlay and layout (2026 frames 0001 and 3805). No site pixel had been sampled. This file is not edited after the
comparison starts; any later change is appended below a dated line and called a deviation.

## Reference product
- NASA Scientific Visualization Studio 4930, "Illumination at the Moon's South Pole, 2023 to 2030" (E. Wright, N. Petro;
  LOLA topography, JPL DE421; 2-hour steps; field south of about 88° S). https://svs.gsfc.nasa.gov/4930/
- Frames: `https://svs.gsfc.nasa.gov/vis/a000000/a004900/a004930/frames/1920x1080_16x9_30p/2026/sp_illum.NNNN.tif`,
  1920×1080 RGB. Frame N ↔ UTC 2026-01-01T00:00Z + 2 h × (N − 1). Checked on the overlay of frame 3805 ("14 Nov 2026 00:00 UT");
  the overlay of the last frame used will be checked too and the run stops if it disagrees.
- Window: frames 3805 … 3973 = 2026-11-14T00:00Z … 2026-11-28T00:00Z, 169 frames. SHA-256 of every frame is recorded.
- Independence: separate team, code and rendering. It shares the LOLA topography family and the DE421 ephemeris with POLARIS,
  so agreement tests the horizon, ephemeris, frame-transform and time handling, **not** the DEM itself.

## POLARIS side (frozen inputs)
a-science results bundles, 1 m mast: `data/bundles/site04_roi3_2026-11-14_14d_mast1m.json`,
`site04_roi4_…_mast1m.json`, `site01_roi6_…_mast1m.json` (SHA-256 recorded at run time). At each frame time the bundle sample
with the identical UTC is used (hourly bundle, even hours); no interpolation.
POLARIS state: `samples[k].sun.center_visible` (primary); `sun.disk_fraction > 0` (secondary, reported only).

## Geometry registration of the frames (illumination-independent of the solver under test)
- Pole = intersection of the overlay crosshair; image scale from the overlay latitude circle (taken as 88° S) checked against the
  fitted scale below.
- Rotation (which longitude is "up") and a scale refinement are fitted once by maximising the correlation between frame luminance
  and a Lambert cos-incidence image of the PGDA 90 80 m DEM (`app/data/polaris-source-two-site-2026-11-14-v2.json` crops are too
  small; the full LDEM 80 m region is read by HTTP range from PGDA 90) for the frame's own overlay sub-solar point. Only DEM normals
  are used: no horizon, no cast shadow, no POLARIS solver output. Fitted on frames 3805, 3847, 3889, 3931, 3973.
- Site pixel = projection of the bundle's site latitude/longitude through the fitted geometry (orthographic/stereographic differ by
  < 0.02 % at this latitude and are treated as equal).

## Classification and metric (fixed now)
- Luminance Y = 0.2126 R + 0.7152 G + 0.0722 B (0–255). A pixel is **shadow** if Y < 8, **lit** if Y ≥ 8.
- SVS state at a site = state of the site pixel. **Ambiguous** (excluded) if the 3×3 block around it contains both states.
- **Near-critical** (excluded) if |bundle `sun.margin_deg`| < 0.5° (covers the solar radius, the 1 m mast vs ground-level render,
  and the ~114 m frame pixel).
- Metric per site: agreement = matching samples / compared samples (after both exclusions). Also reported: the same without the
  near-critical exclusion, the 2×2 confusion matrix, and the excluded counts.

## Pass criterion (fixed now)
- **PASS** if, at every one of the three sites, at least 20 samples remain after exclusions and agreement ≥ 0.90.
- **FAIL** otherwise. An insufficient-sample outcome is reported as **INCONCLUSIVE**, not PASS.
- A PASS closes the "independent illumination comparison" gate **for these three sites, this window, the Sun, at the stated
  resolution**. It says nothing about Earth visibility, other sites, DEM accuracy, power or communications. Whether the release label
  changes from `SOURCE_BASED_UNVALIDATED` is a team decision (Sid and Anish); this run does not change it.

## Code
`tools/validation/svs4930_compare.py` (written after this file; its parameters must match the values above).
