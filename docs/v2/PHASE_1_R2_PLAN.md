# Phase 1 · R2 — finishing the whole-Moon pyramid (plan)

Session R2 of v2 round 2, 16 Nov 2026 ~12:00 EST, branch `claude/v2-r2-pyramid-finish-191208` (contains 72e3430, cut from
`feature/v2-whole-moon`). Scope: prompt §2.3 (VISUAL relief), §2.5 (global analytics maps), §2.2 display formats.
Owns `tools/globe/**`, `$POLARIS_DATA/v2/pyramid_visual`, analytics maps, git-ignored `web/public/globe/**` display
tiles. Does not edit `science/**` (R1). Written before coding (§0.5); decisions taken without the user are marked
**[decision]** with the reason. Budget: ≤ 60 GB new derived data, ≤ 4 processes.

## 1. VISUAL relief amplitude (open item from S3)
**Problem.** The S3 model sets the added relief from a power law fitted to the 80 m DEM's own structure function at
160–640 m and extrapolated below the posting, minus what bilinear interpolation already carries. At the PGDA 78 sites the
structure function there is dominated by regional tilt (H ≈ 0.95), so "law − carried" is a small difference of two large
numbers and the added relief comes out 1.2–1.9× the real sub-80 m residual.

**Fix [decision].** Take the amplitude from what LOLA measures *at the scale the relief is added*, not from an
extrapolation of the resolved DEM:
- **LOLA 5-spot roughness, LDRM_32_25 / _50 / _75** (LRO-L-LOLA-4-GDR-V1.0, already on disk from S2): per 1/32° bin,
  the 0.25/0.50/0.75 quantiles of the RMS residual height of the five spots of one laser shot after removing a plane
  (label: point-to-point baseline 25 m at the nominal 50 km altitude, corrected to that distance; instrument noise
  ≈ 0.15 m removed). A plane fit is blind to regional tilt, which is exactly the quantity the old fit got wrong.
- **Spectral shape:** Hurst exponent from PGDA 70 HE_8 (Rosenburg et al. 2011; fitted over 57 m–2.7 km), clipped to
  [0.5, 1.0]; self-fit H only where HE_8 has no value.
- **Synthesis:** same deterministic global-lattice octave noise (only wavelengths below 2× the local native posting),
  amplitude chosen so the emulated LOLA 5-spot roughness of *displayed = bilinear(real) + noise* equals the local
  LDRM median: σ_noise = √max(LDRM₅₀² − σ_base², 0) / g(H, octaves), where g is the 5-spot roughness of unit-amplitude
  noise, calibrated once by Monte Carlo with a fixed seed. Parameters are sampled per parameter cell (2.56 km polar,
  1/32° eq) and interpolated bilinearly, so tiles stay seamless.
- **Hard test** (`tools/globe/tests/test_globe_roughness.py`, skips only if the real pyramid or the LOLA maps are absent):
  at the four PGDA 78 sites and at ≥ 8 fixed windows elsewhere (both poles and the eq zone, mare and highland),
  VISUAL built at 5 m from the pyramid,
  (a) *implementation*: emulated 5-spot roughness of the displayed surface (median over shots in the window) lies inside
      the published spread = [median LDRM_32_25, median LDRM_32_75] over the LOLA bins of the window (this is in-sample
      by construction: it checks the synthesis hits its target);
  (b) *independent, real data*: at the PGDA 78 sites (VISUAL from the 80 m level only), displayed/real 5 m RMS slope
      at 15 m–2.56 km within [0.8, 1.25] and added/real sub-80 m residual RMS slope within [0.5, 1.5] (PGDA 78 is LOLA
      gridded to 5 m, so its residual is a lower bound on true roughness — reported, not tuned to);
  (c) PGDA 70 median absolute slope at 57 m is reported per site (regional 1/16° maps; no pass/fail).
  The test fails if any window fails (a) or any site fails (b).
  17 m is not a multiple of the 5 m post; baselines are 15, 20, 40 … 2560 m (as S3), stated as such.

## 2. VISUAL for the eq zone and the remaining polar tiles
- Generalise `visual_grid` to the eq zone (lat/lon grid; metric spacing R·dφ and R·cosφ·dλ; noise evaluated on a
  local metric coordinate so octaves are isotropic). **Deterministic seed by tile id**: the noise is a pure function of
  the global lattice and a fixed seed (S3 design), and each tile records `seed`, `zone/level/ix/iy` in its tags.
- `ensure_visual_tile(zone, level, ix, iy)`: on-demand build (R3/Blender and the viewer can request any tile; a rebuild
  is byte-identical), plus a budgeted pre-build [decision; whole-Moon VISUAL at ≤ 15 m would be > 150 GB]:
  sp L6 (20 m) poleward of 80° S (PGDA 90 80 m native), np L7 (10 m) over 80–85° N where the LOLA 20 m LDEM is
  native (if time), eq L6 (2048 ppd ≈ 14.8 m) in ±20 km boxes around the any-site landing sites. Target ≤ 15 GB;
  GB written reported in `PYRAMID_QA.json` and STATUS.

## 3. Craters and boulders [decision: only with exact citations]
Add a small-crater or boulder population only if the size-frequency distribution can be cited to a paper, table and
values checked in this session. Also: the LOLA roughness the relief is calibrated to was measured on the real, cratered,
bouldered surface, so craters added on top double-count unless the noise is reduced by a published partition; boulders
(mostly < 5 m) are below every VISUAL pixel built here. If either condition is not met, they stay out and the reason is
written down.

## 4. Global analytics (§2.5, display-only, SOURCE-BASED · UNVALIDATED)
- **Geometry from Horizons** (one archived request per span; raw text kept under `$POLARIS_DATA/v2/analytics/horizons/`
  with SHA-256): observer Earth geocentre (500@399), target Moon (301), QUANTITIES 14 (sub-Earth point on the Moon,
  MOON_ME, 1737.4 km sphere), 15 (sub-solar point), 19 (Sun–Moon r), 20 (Earth–Moon Δ). Span 2026-01-01 → 2044-08-01
  (≥ 18.6 years, one nodal cycle) at 3 h. Check: topocentric az/el derived from these at two sites vs Horizons
  `coord@301` az/el (independent query path).
- **Earth-visibility fraction (libration-aware):** fraction of the samples in which any part of the Earth's disc is above
  the terrain horizon (also: disc centre), topocentric (parallax included). Horizon from rays on the pyramid
  (curvature included), only over the azimuth range the Earth visits from that point. Global map 0.125° from a 16 ppd
  mosaic of the pyramid (local obstructions < ~4 km are missed — stated); poles finer: 1 km polar stereographic grids
  poleward of 80° from the 80 m (≤ 20 km) and 320 m (beyond) levels.
- **Sun-visibility fraction, poles:** same method, full 360° horizons, 1 km grid poleward of 85°; compared with PGDA 69
  (Mazarico et al. 2011, AVGVISIB_85S_060M_201608 Sun and Earth, "any part of the disc", hourly over 18.6 years, LOLA
  LDEM_85S_060M), downloaded SHA-256-pinned as `tools/pgda69/build_layer.py` already does: median and p90 |Δ|,
  correlation, at the same points.
- Outputs: PNG + JSON under `web/public/globe/analytics/` (git-ignored); numbers in `PYRAMID_QA.json` "analytics_r2".
  The "query any point" panel is not in R2's scope (web/src belongs to others).

## 5. Display formats
- **Quantized-mesh 1.0 (Cesium terrain)** from the science pyramid (real heights only; VISUAL never in these tiles),
  geographic tiling scheme (2 × 1 root tiles), 65 × 65 vertex grids, heights above the 1,737,400 m sphere (Cesium
  `Ellipsoid.MOON` is that sphere), oct-encoded vertex normals extension, gzip, `layer.json` + `manifest.json` (source
  levels, tile counts, bytes, label). Global to level 7 (~0.02°), poles poleward of 80° deeper (level 9–10), sized to
  the budget [decision: measured after the first levels]. Under `web/public/globe/terrain/` (git-ignored).
  Tests: encoder/decoder round trip, edge-vertex agreement between neighbouring tiles, header bounding values.
- **Coverage layer, web-ready:** equirectangular 8-bit PNG (Cesium `SingleTileImageryProvider`-ready, plate carrée
  −180…180) + polar insets + legend JSON with class colours, from `tools.globe.coverage`.

## 6. Done means
`python -m pytest tools/globe science/tests -q` green; the VISUAL guard test kept; STATUS row "R2 · …";
BUILD_STATUS appended; QA numbers in `PYRAMID_QA.json`; small commits on this branch only; rasters/meshes never
committed; anything not built listed as not done.
