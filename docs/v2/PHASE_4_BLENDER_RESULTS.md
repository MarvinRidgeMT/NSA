# Phase 4 (prompt §5) — Blender v2 pipeline: results, decisions, limits

Session S5, 16 Nov 2026 02:30–~04:00 EST, branch `claude/v2-s5-blender-9fbc79` (from `feature/v2-whole-moon` eda168c). Plan:
`docs/v2/PHASE_4_BLENDER_PLAN.md`. Blender 5.3.0 (02f0899d78e3), Cycles CPU unless stated.

Labels used everywhere: terrain geometry **SOURCE-BASED · UNVALIDATED**; Hapke photometry, earthshine **MODEL**; stars
**VISUAL** (orientation MODEL); lander/mast/antenna/tower **ILLUSTRATIVE**. Renders are pictures of solver numbers; their
realism against real images is Phase 5's job and is **not** claimed here.

## 1. What exists

| Piece | File | Status |
|---|---|---|
| Scene builder `--world moon --lat --lon --utc --camera` | `blender/v2/build_scene.py`, wrapper `blender/v2/build.command` | done |
| Scene spec from the solver bundle (every number the scene uses) | `blender/v2/spec.py` | done |
| Sun/Earth/earthshine/star-frame maths | `blender/v2/astro.py` | done |
| Hapke regolith (one expression graph → Python value and Cycles nodes) | `blender/v2/hapke.py`, `hapke_nodes.py` | done |
| Camera presets + physical exposure | `blender/v2/cameras.py` | done (Kaguya TC optics partly unverified) |
| View-dependent terrain tiles + far ring in local ENU with curvature | `blender/v2/terrain.py` | done on the solver's DEMs; S3 pyramid adapter written, not yet usable (see §6) |
| Proof: manifest + `.blend`, glTF provenance test, headless rebuild vs reference | `blender/tests/run_all.py`, `glb_proof.py`, `test_glb_proof.py`, `reference/*.png` | done |
| Extra checks found two real bugs | `blender/tests/skyline_check.py`, `star_check.py` | done |
| Downloads (URL, SHA-256, licence) | `blender/v2/data_sources.json` | done |

Usage:
```
bash blender/v2/build.command --lat -89.47409 --lon -137.3813 --utc 2026-11-21T02:00Z --camera eva_eye --look-az 145 --look-el 2.5 --ev-comp 3
/Applications/Blender.app/Contents/MacOS/Blender -b --python-exit-code 1 -P blender/tests/run_all.py
python3 -m unittest discover -s blender -p 'test_*.py'
```
Every build writes `<tag>.blend`, `<tag>_spec.json`, `<tag>_manifest.json` (Blender version and build hash, SHA-256 of every
`blender/v2` script, of the bundle and of each terrain level, engine CYCLES, samples, seed, device, resolution, exposure, tile
plan, timings), `<tag>.png` and with `--glb` a Draco GLB whose `scenes[0].extras.polaris` names the builder and script hashes.

## 2. How each §5.2 item was done

**Frame.** Blender world = local ENU at the observer's ground point (x east, y north, z up along the site radius), 1 unit = 1 m.
Each DEM node goes grid → (lat, lon) (closed-form inverse stereographic, same as `science/frames.py`) → Moon-fixed
`(R+h)·u` → ENU, so curvature is exact (6 km drop at 145 km) and a Horizons az/el is used as is.

**Terrain.** The solver's own cached rasters: PGDA 78 5 m tile (16 km square) and PGDA 90 LDEM_80S 80 m (±290 km). Tiles of 64
cells; per tile a power-of-two decimation so spacing ≤ k × distance × camera pixel angle in view, and ≤ distance × tan(Sun
radius) for out-of-view tiles toward the Sun (shadow casters: simplified no more than the solar penumbra); other out-of-view
tiles are dropped. Vertex budget 2.5 M doubles k when exceeded (heroes ran at k = 8, orbital views at k = 2; recorded). 5 m tiles
within 150 m of the observer are bilinearly densified to 1 m (the solver's interpolation rule, no new data). NaN never filled;
cells under a finer level dropped; separate-vertex skirts hide LOD cracks.

**Sun.** SUN lamp, `angle` = 2 × Horizons angular radius of that sample (`radius_source: horizons-ang-diam`), direction =
Horizons az/el, irradiance 1361 W m⁻² / r_au² (Kopp & Lean 2011). A camera-only emissive disc of the true angular size and
mean photospheric radiance E/(π sin²ρ) is placed at 1000 km for views that include the Sun.

**Earth.** Sphere at 1000 km with radius 1000 km × tan(ρ_Earth) (true angular size from Horizons), Lambert albedo 0.55
(geometric albedo 0.367), lit by the same Sun lamp, so its phase follows the true Sun direction (solar parallax over the
Earth–Moon distance ≤ 0.15°). The phase angle and illuminated fraction are also computed from the Horizons Sun and Earth vectors
and recorded; over 14–28 Nov 2026 they follow the lunar calendar (new Earth on 24 Nov = full Moon; tested). No eclipse shadows.

**Earthshine.** Second SUN lamp from the Earth direction, `angle` = Earth's angular diameter, irradiance
E_sun · 0.367 · Φ_Lambert(α) · sin²ρ_Earth (MODEL): 0.087 W m⁻² at 52° phase (14 Nov) down to 0.0026 W m⁻² near new Earth.

**No atmosphere.** Black world for camera rays, no ambient fill (v1's dim fill is gone).

**Stars.** NASA SVS 4851 `starmap_2020_4k.exr` (34.3 MB, ICRF, SHA-256 in `data_sources.json`, cached, not committed),
rotated ICRF → ENU by TRIAD: the Moon's pole (IAU 2009, Archinal et al. 2011, main periodic terms) matched exactly, the Sun
(Astronomical Almanac low-precision, precessed to J2000) vs the Horizons Sun for the roll. Independent check: the Sun–pole angle
from Horizons equals the IAU/almanac one to 0.001–0.012° at all sampled times. The SVS map is display-scaled (bright stars clip
at 1.0, no flux units), so brightness is VISUAL: pixel 1.0 = a V = 1 star in one map pixel. With physical exposure stars vanish in
sunlit views and appear at +11…+16 EV.

**Assets and overlays.** Layouts mirror `science/cube/build_assets.py` LAYOUTS exactly (tested): lander body r 2 m × 4 m,
array, antenna (dish aimed at the bundle Earth direction), 15 m tower; the observer mast is the bundle mast. Sight-line rays from
the mast top carry the bundle state; blocked rays end at the bundle skyline's critical point; bodies below the mathematical
horizon get no ray. The bundle's 720-bin skyline is drawn at true angles (0.97 × critical distance, ~0.02° wide).

**Cameras.** Frame approximations of line-scan instruments (no motion, TDI or distortion), grayscale = Rec.709 luminance in
Raw 16-bit PNG:

| preset | focal mm | pitch µm | pixels | f/ | pixel scale (computed / published) | source |
|---|---|---|---|---|---|---|
| lroc_nac | 699.62 | 7 | 5064 | 3.577 | 0.500 m / 0.5 m at 50 km | NAIF `lro_lroc_v20.ti`, LROC specs page |
| lroc_wac (643 nm) | 6.0309 | 9 | 1024² | 5.052 | 74.6 m / 75 m at 50 km | same (no distortion model: 75° FOV vs 92° published mono) |
| shadowcam | 699.275 | 12 | 3072 | 3.6 | 1.716 m / 1.7 m at 100 km | Robinson et al. 2023 JASS Table 2; ShadowCam site |
| kaguya_tc | 72.45 | 7 | 3504 | 3.97 | 9.66 m / 10 m at 100 km | USGS STAC (pixels, GSD, band); **focal/pitch/f-number UNVERIFIED** |
| eva_eye | 50 on 36 mm | – | – | 8 | 1/250 s ISO 100, eye 1.7 m | – |
| lander_cam | 24 on 36 mm | – | – | 8 | 1/250 s ISO 100, 3 m on the lander side | ILLUSTRATIVE mount |

Exposure: ISO 12232 saturation relation v = 0.65 · 93 lm/W · L · t · S / (78 N²). Instruments have no ISO, so an "equivalent
ISO" is an ENGINEERING ASSUMPTION: Hapke regolith at i = g = 60°, e = 0 under a 1 AU Sun reaches 40 % of full scale;
ShadowCam = NAC × 200 (published ">200× the LROC NAC"). `--ev-comp` adds a stated compensation (heroes: +3 EV for a 1° Sun).

## 3. Regolith photometry

Hapke (2012) IMSA with shadow-hiding opposition, double-lobed Henyey–Greenstein (c > 0 back-scattering), macroscopic roughness
(Hapke 1984 S, μ0e, μe), H-function in Hapke's (2002) approximation, K = 1, B_C0 = 0: the form the LROC WAC parameter maps were
derived with (Sato, Robinson, Hapke, Denevi & Boyd 2014, JGR Planets 119, 1775–1805, doi:10.1002/2013JE004580).

Parameters are read from the published map itself, PDS `WAC_HAPKEPARAMMAP_643NM` (LROLRC_2001, v1.1; README: "Bc0 fixed at 0.0,
hc fixed at 1.0, theta fixed at 23.657, phi fixed at 1.0"). The map covers 70° N–70° S; the sites are at 89.5° S, so the
scene uses the median of the ten southernmost lines (60–70° S):

| set | w | b | c | B_S0 | h_S | θ̄ |
|---|---|---|---|---|---|---|
| SOUTH_60_70 (used) | 0.4215 | 0.1907 | 0.8394 | 1.5505 | 0.0155 | 23.657° |
| GLOBAL median (comparison) | 0.3955 | 0.2279 | 0.4242 | 1.6595 | 0.0505 | 23.657° |

I/F at i = g = 30°, e = 0 is 0.100 (SOUTH) and 0.098 (GLOBAL); at the LROC normalisation geometry (i = g = 60°, e = 0) 0.051.
**Not done:** the paper's own tables and equation numbers could not be read (publisher and ResearchGate refused automated
access); the values above come from the archived map, not the paper text, and the phase-function sign convention is Hapke
(2012)'s, consistent with c > 0 in the map. A PDS label quirk is recorded: the image starts at byte 5760, not the 1440 the PDS4
`.xml` states.

**OSL vs nodes.** OSL is compiled into this Blender but Cycles runs OSL only on CPU (not Metal), and a closure-based renderer
gives a shader no light vector anyway. So the shader evaluates r(i, e, g) for the **dominant light** (the bundle Sun, or Earth when
the Sun is down) passed as a constant direction, and sets a Diffuse BSDF colour to π r / μ0 (cap 4); Cycles then returns
L = r E with its own cast shadows. 176 Math nodes; works on CPU and GPU.

Measured error of the node implementation: flat-plane Cycles renders at six (i, e, g) geometries equal the independent
Python implementation to **1.3 × 10⁻⁶ relative** (`photometry_check.py`, in `run_all.py`). Expression graph vs straight-line
reference: < 10⁻⁹ over 4000 random geometries.

Approximations (documented, not removed):
- Light from any other direction is shaded with the dominant light's geometry. For earthshine falling on ground the Sun also
  lights, the colour used is 0.4–1.8 × the correct one in the cases computed (e.g. 1.78 at 5° depression looking 33° off the
  Sun's azimuth; 0.39 looking away from it); earthshine is ~10⁻⁴ of sunlight there, so this matters only in Sun shadow.
- Facets facing away from the dominant light (cos i < 0.01) get the Lambert-equivalent colour π r / μ0 at i = g = 60°, e = 0
  (0.103) so they still reflect scattered light and earthshine. This replaced a bug where such facets were black (§5).
- No VISUAL micro-relief is added on the Hapke material: θ̄ already models sub-resolution roughness; adding bump would count it twice.

## 4. Proof that it is Blender (§5.3)

`blender -b --python-exit-code 1 -P blender/tests/run_all.py` — **11/11 checks pass, ~18 s**:
1. 60 unit tests under Blender's Python (102 under `python3 -m unittest discover -s blender`, including the v1 tests).
2. Hapke nodes vs Python: max relative error 1.3 × 10⁻⁶.
3. Two scenes rebuilt **from scratch, committed inputs only** (site01 bundle + the 80 m crop in git; no cache, no stars) and compared
   with stored references (`ref_site01_eva_eye.png` 14 KB, `ref_site01_wac15km.png` 25 KB): mean |Δ| 0.000/255, p99 0.00/255
   (tolerance 2/255 and 16/255).
4. Negative control: the same eye-level scene 72 h later differs by mean 17.5/255, p99 155/255 → fails the tolerance, as it must.
   When the overlay drawing changed, the reference test failed (mean 3.3/255, p99 126/255) until the reference was deliberately regenerated.
5. Manifest + `.blend`: Blender version, script and input hashes, CYCLES, samples, device; the reopened `.blend` carries the
   same provenance in `scene['polaris']`.
6. Skyline consistency (needs the solver DEM cache): the drawn terrain, ray-cast by Blender from the mast top in the bundle's 720
   azimuths, reproduces the solver skyline. site01_roi6: median |Δ| **0.0014°**, p95 0.021°, max 0.063° (far bins p95 0.010°).
   site04_roi3: median 0.0027°, p95 0.032°, max 0.23° (near bins with the skyline point < 100 m away carry most of it).
7. Starfield orientation (needs the SVS map): long exposures aimed at the predicted LMC and SMC directions find them 0.16° and
   0.69° from the frame centre. The pre-fix mapping gives 17.4° and 8.2° and fails.
8. glTF provenance over `web/public/`: every `.glb`/`.gltf` must have `asset.generator` = Khronos glTF Blender I/O **and**
   `scenes[].extras.polaris.builder = blender/v2/build_scene.py`, unless whitelisted with a reason and a pinned SHA-256 (a changed
   file loses its exemption). Rule self-tests cover a three.js generator, a Blender file without provenance, ours, and a changed
   whitelisted file. A real `--glb` export from `build_scene.py` passes.

**Decision on the NASA SVS globe** (`web/public/globe/NASA_SVS_moon_small.glb`): its generator already reads
"Khronos glTF Blender I/O v5.0.21" because NASA GSFC made it in Blender, so a generator-only test would pass it without proving
anything about POLARIS. It is **whitelisted as third-party** (SHA-256 12d3b0bb…e67d4 pinned): a VISUAL whole-Moon navigation
globe, never terrain for a calculation. Re-exporting it here would only relabel NASA's mesh. It should be replaced by the v2
global base mesh built by `build_scene.py` from S3's pyramid (not done tonight).

## 5. Bugs found by the checks and fixed tonight

| Bug | Found by | Effect | Fix |
|---|---|---|---|
| Solver cache `x_left`/`y_top` are pixel **edges**; the loader used them as node centres | skyline check (median 0.0095°, p95 0.195°, max 0.46°) | terrain shifted 2.5 m (5 m level) and 40 m (80 m level) | pixel-centre convention + regression test against `science.dem.ArrayDEM.sample`; skyline median now 0.0014° |
| Starfield rotated 180° in RA (texture vector flipped) | star check (the Crux Milky Way where the Magellanic Clouds belong) | wrong sky | ICRF vector passed unflipped; star check 0.16° / 0.69° |
| Facets facing away from the dominant light reflected nothing | ShadowCam render with the Sun blocked | black back slopes even under scattered light/earthshine | Lambert-equivalent Hapke colour below cos i = 0.01 + test |
| Overlay rays for a body below the horizon drawn underground in front of the eye | first EVA render | black frame | no ray for bodies below the mathematical horizon |
| Skirts shared the surface's edge vertices | first EVA render | bright grid lines along tile edges | skirts get their own vertices + test |
| Near-observer densification applied to an 80 m level (×80) | `run_all` time (204 s) and reference diff | 26 M vertices | only levels with native ≤ 10 m |

## 6. Renders (all small; outputs in `blender/output/v2/final/`, git-ignored; copies in `docs/v2/phase4/`)

| Render | Resolution, samples | Terrain verts | Build + render (s) |
|---|---|---|---|
| hero site01_roi6, EVA eye, 2026-11-21T02Z (Sun 1.0°, Earth 4.1° at 16 %), +3 EV | 960×540, 64, denoised | 2.29 M | 3.7 + 2.9 |
| hero site04_roi3, same time and setup | 960×540, 64, denoised | 2.16 M | 4.4 + 2.9 |
| site01_roi6 LROC NAC / WAC from 50 km | 384², 32 | 0.68 M / 0.65 M | ~2.5 + 0.8 each |
| site04_roi3 Kaguya TC from 100 km (Shackleton in frame) | 384², 32 | 0.55 M | 2.5 + 0.8 |
| site04_roi3 ShadowCam at 2026-11-27T08Z (Sun blocked at the site) | 384², 32 | 0.59 M | 2.4 + 0.9 |
| site01_roi6 lander camera, +3 EV | 512×288, 32 | 2.52 M | 3.6 + 0.8 |
| site01_roi6 long-exposure sky (+14 EV, LMC/SMC) | 512×288, 16 | 2.19 M | 2.9 + 0.3 |

The ShadowCam frame shows sunlit ground saturated (as at ×200 NAC sensitivity) and the shadowed side near zero (~10⁻⁵ of full
scale, earthshine level): there the shadow falls across nearly flat ground under a 1.4° Sun, which scatters almost nothing into
it. This was checked with a plain Lambert material (same result), so it is geometry, not the shader. PSR views lit by steep sunlit
walls need many more samples than the 32 used.

## 7. Not done (stated, not hidden)

- **S3 pyramid:** `terrain.stack_levels()` / `--terrain stack` follow the contract and are tested on an `ArrayDEM` stand-in, but
  `science.terrain` is not on this branch and the pyramid directory was empty at 03:30 EST. Not run end to end.
- **Global cube-sphere base mesh** of the whole Moon (§5.1a), **3D Tiles**, and replacing the SVS globe: not started (they need S3).
- **Albedo from WAC/NAC:** no albedo texture; the Hapke map stops at 70° S and NAC mosaics carry baked-in shadows. Regolith is
  uniform 60–70° S Hapke.
- **Mercury/Mars** photometry and MDIS/HiRISE/CTX presets: not started (§3 comes later).
- **Kaguya TC** focal length, pixel pitch and f-number are unverified (they reproduce the published 10 m/px; flagged in the preset).
- **WAC distortion** not modelled (frame camera gives 75° instead of the published 92° mono FOV).
- **Sato et al. (2014) tables** not read (paywall/robots); parameters come from the archived map, which is the paper's product.
- **Web viewer**: no web asset was replaced; web 3D components belong to other sessions.
- Orbital cameras sit above the site with a chosen emission angle, not at a spacecraft ephemeris position.
- Overlays are drawn from the mast top; other viewpoints show parallax on nearby skyline bins.
