# Phase 4 (prompt §5) — Blender as the single scripted 3D production pipeline: plan

Session S5, branch `claude/v2-s5-blender-9fbc79` (cut from `feature/v2-whole-moon` at eda168c), 16 Nov 2026 from ~02:30 EST.
Written before coding (§0.5). Owns `blender/v2/**`, `blender/tests/**` and the glTF-proof test (`docs/v2/SPLIT.md`).

## 0. Rules this phase keeps
- Blender is read-only with respect to science. Every direction, angular size, range and visible/blocked state comes from a
  solver bundle (`polaris-science-results-v1`, JPL Horizons samples) or is computed in pure Python from those numbers in
  `blender/v2/*.py` (unit-tested outside Blender). Nothing is read back from a lamp.
- Labels: terrain geometry SOURCE-BASED · UNVALIDATED; synthetic relief / albedo variation / textures VISUAL; lander, mast,
  antenna, tower ILLUSTRATIVE; Hapke photometry MODEL (published parameters, not fitted here).
- `--utc` never interpolates: it must equal a bundle sample (or lie within half a step of one, which is then used and the
  offset recorded); outside the sampled span the build fails.
- No NASA raster, mesh or image is committed. Downloads go to `data/cache/v2/blender/…` with URL + SHA-256 in
  `blender/v2/data_sources.json`. Small reference PNGs of our own renders are committed (≤ 200 KB each).

## 1. Inputs available tonight
| Input | Where | Use |
|---|---|---|
| Solver bundles (Sun/Earth az, el, angular radius, range; skyline; per-sample states) | `data/bundles/*.json` (committed) | lighting, sky bodies, sight lines, skyline |
| Terrain context packs: 5 m display crop ±1 km, 5 m L1 ±4 km, 80 m regional ±16 km | `data/visual/terrain_context/<site>/` (bins git-ignored) | near / mid / regional levels |
| PGDA 90 LDEM 80 m windows ±290 km around each ROI | `data/cache/<site>_ldem80_290km.npy` (git-ignored) | far ring to the horizon |
| 80 m ±16 km crop inside the committed v2 bundle | `app/data/polaris-source-site01-2026-11-14-v2.json` | the only terrain that is committed: used by the reproducibility test |
| LROC WAC Hapke parameter map, 643 nm (PDS `WAC_HAPKEPARAMMAP_643NM`, 1.8 MB) | `data/cache/v2/blender/lroc_wac_hapkeparammap/` | regolith photometry parameters |
| NASA SVS 4851 Deep Star Maps 2020, `starmap_2020_4k.exr` (34.3 MB, ICRF) | `data/cache/v2/blender/svs4851/` | starfield |
| S3 global pyramid via `science/terrain/stack.py` | not yet on this branch | adapter `blender/v2/terrain.py::stack_levels()` switches to it when it exists |

## 2. Method
### 2.1 Frame
Blender world = local ENU at the observer's ground point: x east, y north, z up (radial), 1 unit = 1 m. Every DEM node
(south-polar stereographic grid, heights above the 1 737 400 m sphere) goes grid → (lat, lon) (closed-form inverse, same as
`science/frames.stereo_inverse`) → Moon-fixed `(R+h)·u(lat,lon)` → ENU at the observer. So the far ring curves away
correctly (≈ 6 km drop at 145 km) and a Horizons azimuth/elevation maps straight to `(sin az cos el, cos az cos el, sin el)`.

### 2.2 Terrain tiles + far ring (`terrain.py`, pure numpy)
Levels nest: L0 5 m (±1 km) ⊂ L1 5 m (±4 km) ⊂ L2 80 m (±16 km) ⊂ L3 80 m (±145 km). Each level is cut into tiles. For each tile
the needed node spacing is `distance × camera pixel angle × 2` inside the view frustum, and `distance × tan(Sun angular
radius)` outside it (shadow casters: simplified by no more than the solar penumbra). The tile is decimated by the largest power
of two whose spacing stays below that need and never finer than native. Cells covered by a finer level are dropped; tile edges get
short skirts so LOD seams don't open cracks. A vertex budget scales the factor up if exceeded. Selection, decimation and
coverage are recorded per tile in the manifest.

### 2.3 Lighting (`astro.py`)
- Sun: SUN lamp, `angle` = 2 × Horizons angular radius for that sample, direction from Horizons az/el, irradiance
  `1361 W m⁻² / r_au²` (TSIS-era total solar irradiance; Kopp & Lean 2011).
- Earth: sphere at a scaled distance with radius `D·tan(ρ_E)` (true angular size from Horizons), lit by the same Sun lamp, so its
  phase follows the true Sun–Earth geometry (parallax of the Sun over the Earth–Moon distance < 0.15°, stated). Phase angle and
  illuminated fraction are also computed from the Horizons Sun and Earth vectors (range + az/el) and recorded.
- Earthshine: second SUN lamp from the Earth direction, `angle` = Earth angular diameter, irradiance
  `E_sun · p · Φ_L(α) · sin² ρ_E` with Earth geometric albedo p = 0.367 (Lambert-sphere phase function Φ_L). MODEL, not data.
- No atmosphere: world background black for the camera; no ambient fill (v1 had a dim fill; v2 removes it).
- Stars: SVS 4851 equirectangular map (ICRF/J2000) on the world, rotated from ICRF to local ENU with the IAU 2009 Moon pole
  and W (the mean-Earth frame difference is < 0.03°, stated); scaled by the same physical exposure as the terrain so stars vanish
  in sunlit exposures and appear in long ones. The map's pixel values are linear but uncalibrated (SVS gives no flux units): the
  scale is set so a Vega-like star reaches its expected irradiance, and that calibration is labelled MODEL.

### 2.4 Regolith photometry (`hapke.py`, node shader)
Hapke (2012) IMSA model as used for LROC WAC by Sato et al. (2014): double-lobed Henyey–Greenstein phase function (b, c),
shadow-hiding opposition effect (B_S0, h_S), coherent backscatter off (B_C0 = 0), macroscopic roughness θ̄ = 23.657°,
K = 1, H-function in Hapke's (2002) approximation. Parameters: medians of the PDS 643 nm map over 60–70° S (the map stops at
70° S; the sites are at ~89.5° S), plus the global median for comparison; the decode, statistic and file SHA-256 are recorded.
Cycles has no custom BSDF on Metal (OSL runs on CPU only and has no light vector), so the shader computes the Hapke radiance
factor `r(i,e,g)` for the dominant light (Sun, or Earth when the Sun is down) from the lamp direction passed in as a shader
constant, and sets a Diffuse BSDF colour to `π r / μ0`. Cycles then reproduces `L = r · E` with its own cast shadows. Error
sources (documented, and the first one measured by a test): node math vs the Python reference; earthshine and multiple
scattering evaluated with the dominant light's geometry.

### 2.5 Cameras + exposure (`cameras.py`)
LROC NAC / WAC (VIS), ShadowCam, Kaguya TC: focal length, pixel pitch, pixel count, f-number from the instrument kernels /
team pages; rendered as a frame camera with the same IFOV (line-scan approximation: one exposure for the whole strip, no
along-track motion), grayscale = Rec.709 luminance of linear radiance (not the instruments' spectral bandpass). Human EVA eye
(1.7 m above ground, 50 mm full-frame equivalent) and a lander camera. Physical exposure from N, t and ISO via the ISO 12232
saturation relation, with 93 lm/W for the solar spectrum. Pixel scale vs the published value is checked by a test.

### 2.6 Assets and overlays
Lander, mast, antenna, tower as ILLUSTRATIVE primitives at the observer (named and labelled). Sun / Earth sight-line rays from
the mast top with bundle state and first-hit distance; skyline ring from the bundle's 720 bins at true angles.

### 2.7 Proof (§5.3)
- Every build writes `<tag>.blend` + `<tag>_manifest.json`: `bpy.app.version_string`, SHA-256 of every `blender/v2` script,
  SHA-256 of every input file, engine `CYCLES`, samples, device, seed, resolution, exposure, render times.
- `blender/tests/test_glb_proof.py`: every `.glb` under `web/public/` must name the Khronos glTF Blender I/O exporter in
  `asset.generator`. Ours must additionally carry `asset.extras.polaris` (manifest SHA) that only `build_scene.py` writes.
  Whitelist with a reason per entry. The NASA SVS globe (`web/public/globe/NASA_SVS_moon_small.glb`) passes the generator
  check because NASA GSFC exported it from Blender, but it is not ours: it is whitelisted as third-party, pinned to its SHA-256.
- `blender/tests/run_all.py` (`blender -b -P …`): runs the pure tests inside Blender's Python, rebuilds the reference scene from
  committed inputs only (site01 bundle + committed 80 m crop), compares the render with `blender/tests/reference/*.png`
  (mean |Δ| and 99th percentile tolerance), and renders a flat Hapke plane whose pixel radiance must match the Python Hapke
  value within 2 %.

## 3. Acceptance
`blender -b -P blender/tests/run_all.py` green; `python3 -m unittest discover -s blender -p 'test_*.py'` green; science pytest and
web vitest unchanged; test renders ≤ 512 px and low samples; one hero render per current site (site01_roi6, site04_roi3).

## 4. Out of scope tonight (stated, not hidden)
Global cube-sphere base mesh from the ~1 km pyramid (needs S3); 3D Tiles; WAC/NAC albedo textures; Mercury/Mars parameters and
MDIS/HiRISE/CTX presets; re-exporting the web viewer's terrain through Blender (web components belong to other sessions).
