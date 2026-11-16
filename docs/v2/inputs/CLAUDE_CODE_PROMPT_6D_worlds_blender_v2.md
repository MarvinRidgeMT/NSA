# POLARIS X v2 — the ENTIRE Moon (rough terrain everywhere), 6D decision model, more worlds, Blender production pipeline, realism proven against thousands of real images
**Run in Claude Code with Claude Fable 5.2 selected.** Multi-week, multi-session job. This file replaces `CLAUDE_CODE_PROMPT_6D_worlds_blender.md`.

---------------------------------------------------------------------------------------------------
## 0. Ground rules (read all of this before touching anything)

### 0.1 Protect the hackathon submission
- The Space Apps submission closed 15 Nov 2026 23:59 ET. `submission/merged` is what judges see.
- First commands:
  ```
  git tag submission-2026-11-15 submission/merged
  git worktree add ../NSA-v2 -b feature/v2-whole-moon feature/5d-complete
  ```
  Work ONLY in `../NSA-v2`. Never commit to, rebase or force-push `submission/merged`, `codex/lab-integration` or `main`. No pushes unless Sid or Anish ask.
- At the end of every session, confirm `git log -1 submission-2026-11-15` is unchanged.

### 0.2 Build on what exists; don't restart
- `feature/5d-complete` holds 5D Phases 1–10: scenario cube, slope safety, visibility rule, DSN + LCRNS links, energy, dispersion, sensitivity, multi-asset, ±7 km LOD, design docs. Read `docs/5D_UPGRADES_STATUS.md`, `docs/SCENARIO_CUBE_CONTRACT.md` and `docs/BUILD_STATUS.md` there.
- Read the two untracked team prompts in the main checkout: `POLARIS_X_FABLE_5_2_MASTER_REBUILD_PROMPT.md` and `POLARIS_X_FABLE_5_2_NASA_EYES_PLUSPLUS_PROMPT.md`. Merge their still-open defects (P0/P1 lists) and UX rules into the backlog below. Where they conflict with this file, this file wins on science and data rules; they win on UX detail.
- Read project docs: `claude/LIMITS_AND_ERRORS_2026-11-15.md`, `claude/5D_MODEL_RESEARCH_2026-11-15.md`, `claude/DATA_AND_AI_SOURCES_2026-11-15.md`.

### 0.3 Two kinds of truth, never mixed
- **Science numbers** come only from the Python solver: NASA/JAXA DEMs + JPL Horizons/SPICE, float64 heights.
- **Pictures** (Blender, web) only *display* those numbers plus imagery. Their realism is *measured* in Phase 6, never assumed.
- **Labels on every on-screen value:**

  | Label | Applies to |
  |---|---|
  | SOURCE-BASED · UNVALIDATED | geometry |
  | ENGINEERING ASSUMPTION | energy, link |
  | MODEL | thermal |
  | VISUAL | synthetic sub-resolution roughness, boulders, textures |
  | AI-GENERATED | any AI output |

- "k of N maps is not a probability." Never combine counts across axes into a "probability of success".

### 0.4 Data rules
- Never commit rasters, meshes or images from NASA, JAXA, ISRO or CNSA. Use a cache root `$POLARIS_DATA` (default `data/cache/`, git-ignored; recommend an external SSD ≥ 2 TB).
- Every file gets a manifest entry: URL, SHA-256, licence, retrieval UTC, product version.
- Credit every source in `docs/DATA_PROVENANCE.md`. Use the exact acknowledgement each archive asks for (JAXA SELENE wording, CC-BY-4.0 SfS, ISRO PRADAN terms).
- Respect archive rate limits and terms. Download in resumable batches. Never scrape around a login or terms page.
- No secrets in code. No paid services without asking.

### 0.5 Process for every phase
1. Write a plan into `docs/v2/PHASE_<n>_PLAN.md` (inputs, method, tests, acceptance) **before** coding.
2. Add tests that can fail. Keep all suites green: `npx vitest run`, `npx playwright test`, `python -m pytest -q`, Blender tests (`blender -b -P blender/tests/run_all.py`).
3. Append to `docs/BUILD_STATUS.md` (append only; never delete others' sections). Update `docs/v2/STATUS.md`: one row per phase with status, tests, results, open items, hours.
4. Commit in small logical commits.
5. Time boxes are guidance. If one runs out, leave the phase *working and labelled partial* and move on.

Never report an unbuilt feature as done.

---------------------------------------------------------------------------------------------------
## 1. The 6D model: definition, and why this 6th axis

### 1.1 Definition (write `docs/v2/6D_MODEL.md`)
| # | Axis | Role | Examples |
|---|---|---|---|
| 1–3 | East, North, Up (local ENU of the chosen world) | space | any point on the body |
| 4 | Time (UTC/TDB, frames documented) | time | mission window, launch calendar, 18.6-yr cycle |
| 5 | **Uncertainty X**: what we don't control | stress over it | T terrain realizations (PGDA clones, far-field members), M data product (LOLA, SLDEM2015, Kaguya TC, SfS, NAC DTM) |
| 6 | **Decision L**: what the mission controls | optimise over it | mast and asset heights, landing point, layout, relay use, battery, start date, arrival slip |

Requirements (team thresholds, slope limits) are filters on outcomes, not an axis. **World** (Moon, Mercury, Mars …) is a context selector, not an axis.

### 1.2 Why "Decision" is the right 6th dimension (put this reasoning in the doc)
- **The established framework.** This split is the standard frame of decision-making under deep uncertainty. RAND's XLRM separates exogenous uncertainties X (variables we have no control over) from policy levers L (the actions decision makers can take), with a model R linking them to measures M.
- **What it gives the user.** Separating the two is what makes these questions well-posed:
  - **robust choice:** the best L under the worst X;
  - **regret:** the loss from choosing L on the nominal map when the truth is another member of X;
  - **value of information:** which measurement shrinks X enough to change L.
  POLARIS's 5D cube already holds both, mixed in one axis. 6D separates them.
- **Alternatives considered and rejected:**

  | Candidate 6th axis | Why not |
  |---|---|
  | World/body | It is a different scenario, not a varying quantity inside one decision |
  | Requirements | These are stakeholder thresholds on outputs |
  | Data product | It belongs inside X (structural uncertainty) |
  | Observer type | It is a D value |

- **Migration.** Migrate `scenario-cube-v1` → `scenario-cube-v2` with `role: uncertainty | decision | requirement | context` on every axis. Keep v1 readable, with migration tests. The UI groups controls into "What we don't know" and "What we choose".

---------------------------------------------------------------------------------------------------
## 2. PHASE 1 (TOP PRIORITY): the ENTIRE Moon's terrain, rough terrain everywhere, not one small part
**Goal:** every point on the Moon has real terrain at the best resolution that exists, and the solver works anywhere, not only at the four south-pole sites.

### 2.1 What exists (verify each product's current version and page before downloading; record it in the manifest)
| Product | Coverage | Resolution | Use |
|---|---|---|---|
| **SLDEM2015** (LOLA + Kaguya TC, Barker et al. 2016) | ±60° latitude | 512 ppd (~59 m at equator), vertical ~3–4 m | Global backbone |
| **SLDEM2015 slope/azimuth** (PGDA 67) | pole to pole | up to 512 ppd | Slope layers, sanity checks |
| **LOLA gridded LDEM** (global, e.g. 64–256 ppd) and **LOLA polar LDEMs** (polar stereographic, finest available beyond ±60°) | global / poles | 118 m global; finer near poles | Fill beyond ±60°; global consistency |
| **PGDA 90** (20/40/80 m) and **PGDA 78** (5 m sites + clones) | south pole regions | 5–80 m | Polar high resolution (have) |
| **Kaguya TC DTMs**: JAXA SLDEM2013 / TC DTM MAP; USGS ASP TC DTMs | near-global | TC images ~10 m/pixel; USGS ASP DTMs posted at 35 m | Second independent global product (structural uncertainty M); detail where better than SLDEM |
| **LROC NAC DTMs** (PDS SDNDTM / ASPDTM) | hundreds of sites | ~2–5 m | Highest-resolution real terrain where available |
| **GSFC SfS** (Zenodo 10.5281/zenodo.17954508) | selected polar regions | 5 m (some finer) | Polar detail + structural uncertainty |
| **Chandrayaan-2 TMC-2 DEMs** (ISRO PRADAN) | partial | ~10 m class | Additional detail (registration needed; check terms) |
| **LOLA roughness: slope + Hurst exponent** (PGDA 70; LOLA RMHE) | global | 16 ppd maps; baselines ~17 m–2.7 km | Statistics for sub-resolution roughness (VISUAL only) |
| **LROC WAC global mosaic** (100 m), **NAC** imagery | global / local | 100 m / ~0.5–2 m | Albedo and texture |

Sizes to plan for (write the actual numbers into `docs/v2/DATA_BUDGET.md`):
- SLDEM2015 at 512 ppd over ±60° is about 1.1 × 10¹⁰ pixels (~22 GB int16).
- A global ~10 m Kaguya-class surface would be about 4 × 10¹¹ pixels (~0.8 TB). Stream it by tile, on demand; never mirror it whole.
- Keep the source ID and native resolution per pixel.

### 2.2 Build the global terrain pyramid (`tools/globe/`)
1. **One datum and frame.** Heights above the 1,737,400 m reference sphere, MOON_ME body-fixed frame (convert where products differ; test each conversion).
2. **Merge rules, by documented priority per location:**
   - NAC DTM > SfS (polar, where validated) > PGDA 78 5 m > Kaguya TC DTM (where its quality flag is good) > PGDA 90 > SLDEM2015 > LOLA polar LDEM > LOLA global LDEM.
   - Co-register each product to the LOLA geodetic frame (estimate and log the horizontal and vertical shifts).
   - Feather seams over a documented width.
   - Store per-tile layers: `height`, `source_id`, `native_res_m`, `quality`.
3. **Pyramid.** A cube-sphere or a quadtree per polar-stereographic + equirectangular zone, from global ~1 km down to each tile's native resolution, never upsampled beyond native. Formats: Cloud-Optimized GeoTIFF for science, quantized-mesh / 3D Tiles (or Cesium terrain) for display.
4. **Seam QA.** Report height jumps across product boundaries (median and 99th percentile), with a map. Tests fail if a seam exceeds the documented tolerance for that product pair.
5. **Coverage map.** Show globally which product and resolution backs each point. It goes in the UI as a layer, so users see where terrain is real-and-fine vs coarse.

### 2.3 Rough terrain everywhere: real where measured, statistical below that (and labelled)
- **Real roughness.** Everything at or above each product's native resolution comes from the data, as-is.
- **Below native resolution (display only, VISUAL):**
  - Add fractal micro-relief whose RMS-slope-vs-baseline matches the local LOLA roughness. The Hurst exponent is the slope of log RMS deviation against baseline; LOLA computed it from RMS slopes over baselines of 57 m to 2.7 km.
  - Use the local Hurst exponent and median slope maps to set the spectrum per tile. Add a small-crater population from published size-frequency distributions per terrain type (mare vs highland), and boulders from published NAC boulder statistics and Diviner rock abundance.
  - Seed deterministically by tile ID, so every render matches.
- **Science never sees synthetic relief.** A test must fail if the solver reads a VISUAL layer.
- **Roughness check.** Measure the RMS slope of the displayed surface at 17 m–2.7 km baselines and compare it with LOLA's maps per tile. Report the match (it should agree within the published spread).

### 2.4 Any-site solver (`science/anysite/`)
- **Input:** any lat/lon (+ mast height, window). The pipeline:
  1. picks the terrain stack;
  2. builds the near field at native resolution (to ≥ 25 km);
  3. builds the far field from the pyramid to the curvature limit for that world's relief (compute the limit; record it);
  4. computes the horizon mask (720+ bins);
  5. gets the Sun and Earth from Horizons;
  6. outputs the standard bundle with provenance.
- **Uncertainty.** Clones where PGDA provides them. Elsewhere, members from each product's documented accuracy (SLDEM2015 vertical ~3–4 m, LOLA track spacing), labelled "assumed error model". Product disagreement (M) is computed wherever ≥ 2 products overlap.
- **Performance.** ≤ 60 s for a new site on the Mac. Cache by site hash. Precompute: the 4 current sites, all Artemis III candidate regions (NASA's latest list), a 1° grid poleward of 80° at both poles, and the Apollo/Chang'e/Chandrayaan-3/IM-1/IM-2/Blue Ghost landing sites (useful for validation in Phase 6).
- **Tests:**
  - reproduce Site04 RoI 3: 94.36 % / 72.11 % / 19 h, clones 87.54–97.33 %;
  - at a site covered by both PGDA 78 and the merged pyramid, the masks agree within tolerance;
  - flat-sphere analytic test;
  - north-pole sanity run.

### 2.5 Global analytics (precomputed, display-only)
- Global maps at coarse resolution (e.g. 1 km; finer in polar regions):
  - slope;
  - roughness;
  - Earth-visibility fraction (libration-aware);
  - Sun-visibility fraction where a long-window computation is feasible (poles first; compare with PGDA 69).
- A **"query any point" panel**: click anywhere → a precomputed value, or "compute now" (runs the any-site solver locally through the solver API).

---------------------------------------------------------------------------------------------------
## 3. PHASE 2: World abstraction + more worlds (after Phase 1 is solid)

### 3.1 `science/worlds/`
Each `World` defines:
- radius and shape;
- the IAU rotation model, body-fixed frame and SPICE kernels;
- the Horizons ID and observer syntax;
- the DEM stack;
- the atmosphere model (none / Mars);
- default requirements;
- comms assets.

The Moon regression must be unchanged.

### 3.2 Mercury (airless; same physics; strong polar-ice story)
- **Data:** MESSENGER MLA polar DEMs, the USGS MDIS global DEM and mosaics (latest versions), and radar-bright polar deposits as an ice layer.
- **Physics to test:**
  - the Sun's angular size varies a lot over Mercury's eccentric orbit;
  - the 3:2 spin–orbit resonance gives a solar day of ~176 Earth days;
  - direct-to-Earth only, with solar-conjunction outages flagged.

### 3.3 Mars (different physics; label clearly)
- **Data:** MOLA global, HRSC + CTX DTMs, HiRISE DTMs (~1 m) at chosen sites.
- **Physics:**
  - geometry works the same, but power depends on atmospheric opacity (tau) and dust, so energy stays ENGINEERING ASSUMPTION with tau as an explicit input;
  - seasons via Ls;
  - comms via relay orbiters only after their ephemerides are wired.
- **Optional later:** Moon north pole (same pipeline), Ceres/Vesta (Dawn DEMs).

Every world gets the same Decision Card, cube, sensitivity and validation sections, or an explicit "not available for this world".

---------------------------------------------------------------------------------------------------
## 4. PHASE 3: 6D cube v2 + decision tools across the whole Moon
- Cube v2 (§1) for every precomputed site. Robust choice, regret and VoI over X × L.
- "Find the best landing point within R km of here" uses the emulator from 5D Phase 7 to screen and the full solver to re-check the top candidates (report the re-check error).
- Pareto view across Sun %, Earth/link %, slope, energy margin and distance to ice (M3/LAMP/Diviner layers), with ranges over X.
- Tests: synthetic cube with known robust optimum; regret = 0 when X has one member.

---------------------------------------------------------------------------------------------------
## 5. PHASE 4: Blender as the single 3D production pipeline, and proof that it really is Blender

### 5.1 What "everything in Blender" means here (be exact)
- **Every 3D asset, scene, material and cinematic render is generated by scripted Blender** (`blender --background --python …`), from the solver outputs and the terrain pyramid. No hand edits.
- **The interactive viewer stays web**, because NASA users need to click, query and slice. Its 3D content is **exported from Blender** (glTF 2.0 with Draco; 3D Tiles where Blender output is tiled). It keeps its own scientific overlays drawn from bundle data.
- **The whole Moon in Blender** is a multiresolution build, because no single scene can hold 10 m terrain for the whole body:
  - (a) a global base mesh (cube-sphere) displaced from the ~1 km pyramid level, with WAC albedo;
  - (b) view-dependent tile loading for any close-up: a script picks the tiles inside the camera frustum at the needed resolution, plus a ring of coarser tiles to the horizon;
  - (c) sub-resolution VISUAL relief via displacement or micro-displacement in Cycles.

### 5.2 Scene builder `blender/v2/build_scene.py --world moon --lat … --lon … --utc … --camera …`
- **Terrain:** tiles at the needed resolution + far ring. Albedo from WAC/NAC (MDIS for Mercury; HiRISE/CTX for Mars).
- **Lighting:**
  - Sun as a disc light, with the true angular size for that date's distance and the direction from SPICE/Horizons for that observer;
  - Earth (or the host planet) as a sphere of correct size and phase, lit by the Sun;
  - Earthshine as a secondary light scaled by Earth phase and albedo;
  - no atmosphere on airless worlds; a Mars sky model only for Mars (labelled MODEL).
- **Starfield:** from a NASA SVS deep-star map, exposure-correct (normally invisible in sunlit exposures; visible in shadowed or long exposures).
- **Assets:** lander, mast, antenna, tower from the multi-asset phase (ILLUSTRATIVE shapes unless real CAD is supplied). Sight-line rays and skylines from the bundle.
- **Regolith photometry:**
  - a Hapke-type BRDF implemented as an OSL/node shader, with parameters from published LROC WAC Hapke photometry (look up and cite; e.g. Sato et al. 2014's Hapke parameter maps of the Moon);
  - opposition surge and macroscopic roughness included;
  - separate published parameters for Mercury and Mars.
- **Cameras:**
  - instrument models for LROC NAC/WAC, ShadowCam, Kaguya TC, MDIS, HiRISE, CTX (focal length, pixel scale, line-scan approximation, response → grayscale);
  - human-eye EVA (1.7 m) and lander-camera presets;
  - physical exposure.

### 5.3 Blender proof (acceptance tests that fail if it isn't really Blender)
- Every scene has a `.blend` file plus a manifest: Blender version (`bpy.app.version_string`), script SHA-256, input file hashes, render engine (`CYCLES`), samples, device.
- Every web 3D asset is a glTF whose `asset.generator` field shows the Blender glTF exporter (Khronos glTF Blender I/O). A test reads every `.glb` in `web/public/` and fails otherwise, except for whitelisted non-terrain UI assets.
- `blender/tests/` rebuilds one scene headless from scratch and compares its render to a stored reference (tolerance-based), so the pipeline is reproducible.

---------------------------------------------------------------------------------------------------
## 6. PHASE 5: Realism proven against THOUSANDS of real images, for every world
Realism is measured, not claimed. This is also POLARIS's strongest validation: **predicted shadows against thousands of observed ones**.

### 6.1 Harvest (`tools/imagery/`)
- **Orbital Moon:** LROC NAC, WAC, ShadowCam (shadowed regions), Kaguya TC, Chandrayaan-2 OHRC (if terms allow).
  - Use PDS ODE REST footprint and metadata queries (time, incidence, emission, phase, spacecraft position, pixel scale) for every image covering each precomputed site and region.
  - Reuse the 687 GSFC orthorectified NAC images already used for regions 6/8/9.
- **Surface Moon (ground-level realism):**
  - Apollo surface photography (Hasselblad scans with documented positions and times);
  - Chang'e 3/4/5/6 lander and rover images (CNSA data release system, check terms);
  - Chandrayaan-3 Vikram/Pragyan (near the south pole; ISRO PRADAN);
  - commercial landers (IM-1, IM-2, Blue Ghost) where images and metadata are public.
- **Mercury:** MESSENGER MDIS NAC/WAC.
- **Mars:** HiRISE, CTX, HRSC orbital; Perseverance and Curiosity raw images (public APIs, with positions) for ground level.
- **Sampling.** Stratify into a few thousand images per world: solar azimuth and elevation bins, emission angle, season, terrain type, resolution. Keep 30 % held out for final scoring. Store metadata in a catalogue (`imagery/catalogue.parquet`). Download only what is scored.

### 6.2 Render twins
For each catalogue image, render the same view in Blender: same spacecraft or camera position and pointing, same UTC Sun/Earth geometry, same camera model and pixel scale. For surface images, reconstruct the camera pose from published metadata; where the pose is uncertain, solve it from horizon features and record the residual.

### 6.3 Scores (pre-register these in `docs/v2/RENDER_VS_REAL_PROTOCOL.md`, with hashes, BEFORE scoring)
- Shadow-mask IoU (fixed thresholding rule).
- Shadow-edge position error in metres (orbital) or pixels (surface).
- Skyline/horizon profile error (surface images).
- SSIM on non-saturated pixels.
- Radiometric histogram distance.
- Report per world, site, terrain product (LOLA vs SLDEM vs Kaguya vs SfS vs NAC DTM) and photometric model.

### 6.4 Rules
- Tune only physics-allowed parameters: photometric values within published ranges, exposure.
- **Never tune terrain to match pictures.** Score the held-out set once at the end.
- Failures are shown, never hidden.

### 6.5 Deliverables
- `docs/validation/RENDER_VS_REAL.md`: distributions, galleries (real | render | difference), worst cases, and the product comparison (which DEM predicts shadows best where).
- An in-app "Real vs model" viewer: pick a real image, see its render twin and the shadow-edge differences.
- Where an image covers the Site04 RoI 3 hero point, this finally provides its observation check.

---------------------------------------------------------------------------------------------------
## 7. PHASE 6: Make it genuinely useful to NASA users
- **Any-site query anywhere on the Moon**, then Mercury and Mars. Exports: CSV/JSON time series, GeoTIFF masks and maps, Decision Card PDF, provenance bundle, and a one-line reproduce command per number.
- **Solver API** generalised to worlds: OpenAPI docs, a local server, batch mode, and a tool-spec for AI planners.
- **Optional AI planner** (see `claude/DATA_AND_AI_SOURCES_2026-11-15.md`):
  - Gemini via Vertex AI, or Claude, tool-calling the solver;
  - a number-grounding check blocks any number not in that turn's tool results;
  - output labelled AI-GENERATED; keys server-side only.
- **Live context panel** (Horizons now, NOAA SWPC protons, DONKI), labelled LIVE · CONTEXT, never changing stored results.
- **Performance and quality gates** before any public link:
  - p95 frame ≤ 16 ms on the Mac at globe, region and 5 m levels;
  - cold start ≤ 5 s to the first globe frame;
  - the traceability scan covers every new number;
  - the label audit passes;
  - accessibility scan clean;
  - mobile layout checked.

---------------------------------------------------------------------------------------------------
## 8. Order of work and time boxes (multi-session)
| Order | Phase | Time box |
|---|---|---|
| 1 | 6D definition + cube v2 schema and migration (§1) | 2 days |
| 2 | **Whole-Moon terrain** (§2): global pyramid, coverage map, seam QA, roughness, any-site solver | 2–3 weeks |
| 3 | **Blender** global and close-up scene builder + Blender-proof tests (§5) | 2 weeks |
| 4 | **Render-vs-real** on the Moon, a few thousand images including surface photos (§6) | 2–3 weeks |
| 5 | 6D decision tools across the whole Moon (§4) | 1 week |
| 6 | Worlds abstraction → Mercury → Mars (§3), each with its own image validation | 2–4 weeks each |
| 7 | NASA-user features and gates (§7) | ongoing |

## 9. Session report (every session)
- Phases done or partial, with test results.
- New coverage: % of the Moon at each resolution class, with sources.
- Seam and roughness QA numbers.
- Render-vs-real scores so far (held-out where available).
- Data downloaded (GB) and its manifest status.
- What is NOT done.
- Confirmation that `submission/merged` and tag `submission-2026-11-15` are unchanged.
