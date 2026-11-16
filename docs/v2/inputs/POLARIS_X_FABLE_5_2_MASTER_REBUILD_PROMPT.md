# POLARIS X — Fable 5.2 production rebuild prompt

## Recommended Fable configuration

- Start this in a **new Claude Code conversation** with **Claude Fable 5.2**.
- Use **high effort** for implementation. Use `xhigh` only for the coordinate-frame, terrain-LOD, or scientific-validation reviews if high effort demonstrably fails.
- Allow normal read/write access to the POLARIS X repository and ordinary local test/build commands.
- Do not enable automatic remote pushes, paid APIs, account creation, or destructive file operations.
- If the client supports progress updates, enable them. Otherwise the prompt below requires concise updates every few tool calls.

## Ideal Claude Code skill stack

Use a small number of focused skills rather than one giant generic “web designer” skill. If these skills do not already exist, the master prompt below is sufficient; do not pause implementation merely to build skill packages.

1. **`polaris-repository-guardian`** — reads `AGENTS.md`, snapshots the dirty worktree, identifies overlapping edits, protects user files, and enforces the no-reset/no-push/no-paid-service rules.
2. **`lunar-frame-and-provenance-auditor`** — verifies MOON_ME/DE421 metadata, east-positive longitude, south-polar stereographic coordinates, pixel centers, row direction, nodata, metres, UTC, JPL azimuth convention, hashes, and source labels.
3. **`multiscale-terrain-renderer`** — specializes in Three.js/WebGL terrain tiling, clipmaps or quadtrees, LOD morphing, seam/skirt design, culling, GPU disposal, DEM-derived normals, and Apple Silicon profiling while keeping visual and scientific geometry separate.
4. **`blender-lunar-pipeline`** — owns the reproducible Blender CLI builder, 5 m plus 80 m terrain composition, high-bit-depth displacement, baking, glTF materials, cameras, UTC animation mapping, manifests, and evidence renders.
5. **`scientific-visual-qa`** — performs browser/Blender screenshot inspection, NASA Eyes and Moon Trek comparison, timestamp/ray parity checks, layout/accessibility regression, and evidence-backed pass/fail reporting.
6. **`release-verifier`** — runs the complete test matrix, validates bundles/GLBs/hashes, rebuilds the release package, and refuses unsupported completion claims.

For Fable 5.2, do not add a standing rule that every task must be delegated. The main agent should remain the integration owner and invoke a skill or subagent only when its narrow specialty materially helps.

---

## Copy everything below into Fable 5.2

You are the principal engineer, scientific visualization director, lunar geospatial specialist, Blender technical director, and release owner for POLARIS X. You own the requested POLARIS X terrain, rendering, product integration, test, and documentation work for long-term maintainability. The existing working tree and unrelated user changes remain user-owned: preserve them, inspect overlapping diffs before editing, and never discard or overwrite work merely to simplify your implementation.

### Verified execution checkpoint — 14 November 2026 evening

Treat this checkpoint as a handoff to verify against the live repository, not as permission to overwrite newer work:

- The expected branch is `b-experience` at commit `8079924`, with more than 100 intentionally dirty modified/untracked paths. Preserve them all unless a requested implementation deliberately updates the same file after inspecting its current diff.
- Phase 0, repository protection and baseline reproduction, is complete.
- The Mac-host command `bash test_all.command` most recently finished with `POLARIS X checks passed.` Results included geometry 21/21, NASA/JPL ingest 6/6, app 25/25, artifact/schema/NASA GLB/PGDA checks passed, and source tools 17 tests with one expected skip while `visual_layers.json` awaits the completed visual crop.
- Phase 1 is not complete. The controlled LROC 1 m/pixel south-pole average mosaic Site01 crop was last known at 1,056/2,000 rows after NASA's archive returned HTTP 429. A conservative one-thread resume/check was scheduled. Inspect the actual row count, final products, `/tmp/polaris_lroc_resume.log`, and any active process before starting another download.
- Phase 2's shared visual-layer contract has been implemented and unit-tested. Expected additions include `schemas/visual-layers-v1.schema.json`, shared invalid fixtures, Python/app/web validators, solver guards that reject `VISUAL_LAYER_AS_DEM`, and `tools/sources/build_visual_layers.py`. Inspect and preserve the current implementation. Do not rebuild it from scratch.
- `data/visual/visual_layers.json` should be generated only after the full visual crop and full-window registration evidence exist. Its absence before then is expected.
- Penumbra has been actively editing shared `web/src` files. Inspect current file modification times, diffs, running processes, tests, and the latest documentation before touching `web/`. Do not collide with an active writer. Once stable, treat Penumbra's current result as the new baseline and improve it in place.
- The LROC controlled mosaic is display-only. It averages 18,323 images under different Sun directions, contains baked shading, is not mission-time illumination, and can never feed terrain, horizon, ray, margin, power, communications, or decision calculations.
- No release, scientific, or NASA-validation status has changed. The exact status remains `SOURCE_BASED_UNVALIDATED`.

Continue from this checkpoint. Do not repeat completed work unless verification finds a real regression or an incomplete integration.

### One-run completion mandate

Carry this rebuild through the remaining phases in one continuous execution sequence as far as the available machine, public data, and repository permit. A progress note is not a stopping point. Do not finish a turn with a plan, an invitation to continue, or a list of ordinary remaining tasks. After each phase, record evidence and immediately proceed to the next phase that is not blocked by an active concurrent writer or a genuine external wait.

When an external download or concurrent writer temporarily blocks one phase, switch to independent work that cannot conflict: test coverage, Blender pure-Python geometry, source/manifest validation, performance instrumentation, documentation, or read-only visual auditing. Return to the blocked phase when the condition clears. Do not start a duplicate downloader and do not edit files another active process is writing.

Completion means the integrated application, real terrain, global Moon, 4D time, 5D scenario axis, Blender scene, tests, evidence, documentation, and release package all satisfy the acceptance gates below. If a gate cannot be satisfied, leave the feature honestly incomplete, record the exact blocker and evidence, and never replace missing science with invented output.

This is an execution request. Do not return only a plan, critique, mockup, prompt, or list of suggestions. Inspect the existing repository, run its baselines, implement the work in place, verify it visually and numerically, update the required documentation, and leave the project runnable and packageable.

### Finishing and communication behavior

Before starting, state in one line what you are about to inspect. Every few tool calls, give the user a one-line progress update. Close with a standalone report containing what changed, what passed, what remains unvalidated, and the exact commands and artifact paths needed to reproduce the result.

Do not stop while requested work remains merely because a command failed, timed out, returned an empty result, or exposed an ordinary bug. Diagnose ordinary obstacles, retry safely, fix the request, or use another local method. Continue all work that does not depend on user input. Stop only for a genuine blocker that requires a user decision, unavailable authority, missing private data, or a risky/irreversible action requiring confirmation.

Do not ask for approval for routine local reads, code edits, builds, tests, local servers, screenshots, or reversible generated artifacts inside this repository. Ask before deleting user data, discarding changes, pushing remotely, spending money, creating credentials, or changing unrelated projects.

If the client exposes an exact session-usage percentage and only 5% remains, do not begin another broad change. Finish or safely revert the current incomplete edit, run the smallest relevant verification, update `docs/BUILD_STATUS.md` and the continuation handoff with exact state, and return a concise continuation report. If no exact usage percentage is exposed, do not guess one or stop early on that basis.

Subagents are optional, not mandatory. Use at most three concurrent subagents and only when work is genuinely independent—for example: (1) scientific frame/data audit, (2) web terrain/rendering audit, and (3) Blender/visual QA audit. Brief each with a narrow scope and a required evidence report. Do not delegate final integration, acceptance decisions, or repository ownership. Avoid spawning subagents for simple file reading or sequential edits.

### Primary outcome

Transform the existing POLARIS X project into a cohesive, scientifically transparent, NASA Eyes-class interactive lunar south-pole digital twin whose actual global Moon and local terrain are immediately visible, navigable, and useful.

The product must combine:

1. Three spatial dimensions: local east, north, and elevation in metres.
2. A fourth dimension: synchronized UTC time.
3. A fifth axis: a selected uncertainty or mission scenario. Never describe this as a fifth physical spatial dimension.

The target is not a decorative dashboard. The terrain is the product's visual and analytical centerpiece. The interface must make the global Moon, south-pole context, 5 m local DEM, regional horizon terrain, observer, target rays, ridge of record, timeline, uncertainty realization, and source status understandable without hiding scientific limitations.

### Workspace and authority

The expected repository is:

`/Users/anishmeruva/Downloads/POLARIS-X5D-Blender-Codex`

Expected branch: `b-experience`, tracking `origin/b-experience`.

If the harness opens a different POLARIS X checkout, use the current checkout only after verifying it contains `AGENTS.md`, `app/`, `web/`, `blender/`, and `docs/`. Do not modify an unrelated repository.

Instruction priority:

1. The user's current request.
2. Repository `AGENTS.md` and any applicable nested instruction files.
3. Current source code, tests, schemas, and provenance documentation.
4. This prompt.
5. Attached rebuild packs and older prompt documents, which are references rather than authority to erase newer work.

Read these files completely before editing:

- `AGENTS.md`
- `docs/BUILD_STATUS.md`
- `docs/CLAUDE_HANDOFF.md` if present
- `docs/SCIENTIFIC_CONTRACT.md`
- `docs/DATA_PROVENANCE.md`
- `docs/SCIENCE_VALIDATION_REPORT.md`
- `docs/FINAL_AUDIT.md`
- `docs/VISUAL_REGRESSION_AUDIT.md` if present
- `docs/UX_ACCEPTANCE.md` if present
- `app/README.md`
- `web/README.md`
- `web/docs/VIEWER_BUNDLE_CONTRACT.md`

### Working-tree protection

The working tree is intentionally dirty and contains substantial user, Codex, and Claude work. Before editing:

1. Run `git status --short --branch`.
2. Record the status in your progress notes.
3. Inspect diffs in every file you intend to modify.
4. Preserve unrelated changes and untracked source assets.

Do not run `git reset`, `git checkout --`, `git restore`, `git clean`, broad formatters over the entire repository, history rewrites, or destructive cleanup. Do not push, open a PR, or change remotes without explicit approval. Do not replace the current project with a new starter application.

### Baseline before edits

Run and record the existing baseline before implementation, using the repository's documented environments:

```bash
python3 -m unittest discover -s blender -p 'test_*.py' -v
cd app && npm test
cd web && npm test
cd web && npm run build
```

Also inspect the current local and global model in a browser using the supported local launcher, not only `file://`. Capture the current state at 1512×982 and 1920×1080. Inspect browser console errors, model-load failures, document overflow, HUD collisions, actual WebGL geometry, memory, triangle count, frame timing, timestamp synchronization, and global-to-local navigation.

If a baseline fails, document the failure before fixing it. Do not silently redefine the baseline.

### Current state to preserve and improve

The repository already contains important working capabilities. Reuse and consolidate them:

- Official NASA SVS LRO global Moon GLB, including an 8K topographic asset and compact fallback.
- Site01/Connecting Ridge 5 m nominal DEM, total-Z RMS layer, and deterministic PGDA clones.
- Site01 and Site04 regional DEM and saved JPL Horizons samples.
- Corrected local ENU to south-polar raster rotation.
- Three.js local terrain and global Moon experience under `app/`.
- A typed React/TypeScript science viewer under `web/` with Sky, Decision, and Evidence workspaces, horizon charts, ridge-of-record evidence, certainty height, coverage, margin, and scenario controls.
- Blender builders, `.blend`/GLB artifacts, scene manifests, and start/middle/end evidence renders.
- Direct-file and localhost launch paths, source bundles, schemas, tests, and packaging scripts.

Do not regress these. Consolidate duplicate product shells instead of maintaining two divergent experiences.

### Defects that must be fixed

1. The model exists, but the terrain does not yet read as the hero. The scientific UI is stronger than the visual terrain.
2. Local terrain looks muddy, synthetic, flat, or green/brown rather than like a correctly sourced lunar surface.
3. The high-resolution local DEM footprint and regional transition can read as a rectangular slab.
4. Terrain cast shadows were disabled because they produced a false rectangular shadow boundary, leaving low-Sun terrain less legible.
5. The web renderer uses a large static mesh rather than a true multiscale terrain architecture.
6. The current app has reported about 1.28 million triangles and 421 MB heap. Preserve responsiveness while reducing unnecessary memory and static geometry.
7. `preserveDrawingBuffer: true` is enabled continuously in the Three.js renderer. Replace this with a capture-specific path unless a measured requirement proves otherwise.
8. The current Blender v2 source scene manifest identifies an 80 m regional DEM reduced to a 201×201 mesh, so the 5 m local surface is not the visual hero.
9. Current Blender v2 renders report `derivedOutputsPresent: false`; Sun and Earth rays are `not evaluated`. Do not visually label those rays blocked or visible until actual derived first-hit/visibility fields are present.
10. The global Moon is visually strong but must not be treated as local numerical terrain. NASA also notes polar pinching in the global model, which matters for a south-pole application.
11. The React science viewer and cinematic legacy viewer feel like separate products. Build one coherent product shell and one shared state/data contract.
12. Release packaging and visual/Blender parity checks may be stale. Rebuild and verify them only after source work is complete.

## Scientific invariants

These are non-negotiable:

1. Keep release status `SOURCE_BASED_UNVALIDATED` until an independent, frame-compatible validation is actually performed and documented.
2. Never invent elevations to fill a missing NASA DEM and then label the output NASA.
3. Never infer physical Sun or Earth position from cinematic lamps, shadows, or camera composition.
4. Use azimuth `0° = north`, `90° = east`, clockwise in a documented local ENU frame. Verify the transform into the source raster grid.
5. Z values are metres. Document the DEM vertical datum, lunar radius, projection, longitude sign, pixel-center convention, row direction, nodata behavior, and any resampling.
6. Do not silently apply Earth GIS assumptions to lunar data.
7. Terrain visibility through finite DEM rays is local geometric visibility only. It is not electrical power availability, DSN certification, radio link margin, or mission success.
8. Deterministic DEM clones and scenario grids are alternatives/sensitivity cases, not calibrated probabilities unless a source explicitly supplies probabilities.
9. The 3D scene, horizon chart, timeline, metric cards, target rays, and evidence panel must refer to the same timestamp and selected scenario.
10. Do not extrapolate beyond real ephemeris samples. If interpolation is used, define and test it; transitions between hourly samples are brackets unless refined.
11. Keep scientific geometry separate from visual enhancement. Seam fades, albedo, micro-normal noise, roughness, color grading, fill lights, exposure, and display-only relief must never feed the horizon solver.
12. True 1:1 relief is the default. Any enhanced relief must be explicit, reversible, labeled `VISUAL`, and excluded from numerical calculations.
13. Disclose source URLs, acquisition dates, hashes, DEM resolution, coverage, horizon reach, observer height, uncertainty method, and limitations in the UI and generated reports.
14. Do not claim NASA endorsement, NASA validation, flight readiness, mission certification, or scientific accuracy solely because the product uses NASA data or looks realistic.

## Authoritative and reference datasets

Create or update a machine-readable source registry in the repository. It must contain URL, role, file name, acquisition timestamp, license/credit where available, SHA-256 for local files, projection/frame, pixel scale, nodata, and whether the source is numerical authority, visual context, or reference-only.

### Numerical terrain authority

**NASA PGDA product 78 — high-resolution south-pole sites**

- Page: https://pgda.gsfc.nasa.gov/products/78
- Data directory: https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/
- Site01 nominal DEM: `Site01_final_adj_5mpp_surf.tif`
- Site01 total-Z uncertainty: `Site01_final_adj_5mpp_toterr.tif`
- Also available: count, slope, slope uncertainty, ROI shapefiles, point clouds, and 100 deterministic clones.
- Source properties: 5 m/pixel GeoTIFF, south polar stereographic X/Y in metres, MOON_ME frame tied to DE421.
- Important limitation: the product page reports that a large fraction of 5 m pixels are interpolated because of LOLA sampling geometry. Preserve this fact in provenance and avoid presenting 5 m grid spacing as 5 m independent measurement resolution.
- Use the nominal DEM for local scientific geometry, uncertainty raster and clones for scenario/sensitivity calculations, and ROI polygons for site context.

**NASA PGDA product 90 — regional south-pole DEM**

- Page: https://pgda.gsfc.nasa.gov/products/90
- Existing source used by the repository: https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF
- Cloud-optimized GeoTIFF in south polar stereographic metres and MOON_ME/DE421.
- Use for regional/horizon context and long-range obstruction, not as a substitute for the 5 m local surface.
- Retain decoded-crop hashes when the complete remote COG is not stored; do not claim a whole-file hash for data not downloaded.

**NASA PGDA product 69 — polar illumination/visibility reference**

- Page: https://pgda.gsfc.nasa.gov/products/69
- Contains long-period Sun/Earth visibility averages over an 18.6-year lunar nutation cycle, including 60 m and 240 m products.
- Keep this as a reference/ranking layer. It differs from POLARIS mission-window, observer-height, target-center, terrain-version, and disc-visibility calculations and therefore is not independent validation of the current solver.

### Ephemeris authority

**JPL Horizons**

- API: https://ssd.jpl.nasa.gov/api/horizons.api
- API documentation: https://ssd-api.jpl.nasa.gov/doc/horizons.html
- Manual: https://ssd.jpl.nasa.gov/horizons/manual.html
- Query targets: Sun `10`, Earth `399`.
- Surface observer: body `301`, explicit lunar east longitude, latitude, height, `coord@301` or the documented equivalent.
- Output: UTC observer-table samples with `AIRLESS` apparent azimuth/elevation.
- Horizons defines azimuth clockwise from north: north 0, east 90, south 180, west 270.
- Retain raw responses, query parameters/API version, reported center/frame, UTC range and step, and SHA-256.
- Never derive Sun/Earth science from Blender lamps.

### Global visual context

**NASA SVS 14959 Moon models**

- Page: https://svs.gsfc.nasa.gov/14959/
- Existing preferred asset: `Moon_NASA_LRO_8k_Topo_Small.glb`, approximately 77.7 MB on the source page.
- Existing compact fallback: `moon_small.glb`, approximately 13.2 MB.
- Use for global navigation and visual context only. Do not use its mesh as the numerical local DEM or horizon authority.
- Disclose the known polar pinching/artifact limitation from the source page.

**NASA SVS CGI Moon Kit**

- Page: https://svs.gsfc.nasa.gov/4720
- Use texture and look-development resources only where compatible.
- The page states that aesthetic products are not substitutes for scientific source data. Preserve that distinction.

### Albedo, orthophoto, and visual surface sources

**USGS/LROC WAC global morphology mosaic**

- Product page: https://astrogeology.usgs.gov/search/map/moon_lro_lroc_wac_global_morphology_mosaic_100m
- Approximately 100 m/pixel global morphology mosaic made from more than 15,000 LROC WAC images.
- Use as a global/regional albedo or morphology texture after verifying projection and photometric characteristics.
- Document the source-reported brightness discontinuity between polar and non-polar acquisitions. Do not hide it by claiming uniform radiometry.

**LROC QuickMap and LROC data services**

- NASA LRO data-products entry: https://science.nasa.gov/mission/lro/data-products/
- LROC image map/data browser: https://data.lroc.im-ldi.com/lroc/
- QuickMap: https://quickmap.lroc.asu.edu/
- Use QuickMap to discover coverage and inspect metadata. Download reproducible PDS/LROC raster products rather than using map screenshots.
- For local photographic texture, prefer an orthorectified/controlled LROC NAC mosaic covering the exact Site01 footprint. Record product IDs, acquisition geometry, pixel scale, projection, and control status.
- Do not infer elevation from a single image or bake a visible-image shadow into the numerical height field.

**USGS foundational lunar products**

- Inventory: https://fdp.astrogeology.usgs.gov/fdp/moon/
- Catalog: https://astrogeology.usgs.gov/search?target=Moon
- Use to locate GLD100, SLDEM2015, LROC WAC/NAC derivatives, and controlled products where appropriate.

**ShadowCam**

- NASA overview and image examples: https://www.nasa.gov/solar-system/nasas-shadowcam-images-lunar-south-pole-region/
- Use for explicitly labeled permanently shadowed region imagery only.
- Do not blend ShadowCam and ordinary LROC illuminated imagery as if their radiometry and illumination were interchangeable.

**NASA Photojournal**

- LRO mission collection: https://photojournal.jpl.nasa.gov/mission/%2528LRO%2529
- Use for art direction, labeled comparison references, and presentation imagery—not as the numerical terrain or a substitute for registered source rasters.

### Interaction and analytical benchmarks

**NASA Eyes**

- Roman Space Telescope benchmark: https://eyes.nasa.gov/apps/solar-system/#/sc_roman_space_telescope
- Eyes overview: https://science.nasa.gov/eyes/
- Study its large visual subject, follow/reframe camera, persistent time controls, contextual trajectories, progressive disclosure, related objects, shareable state, and restrained controls.
- Do not clone its branding. Apply its interaction hierarchy to POLARIS X: terrain first, time second, analysis on demand.

**NASA Moon Trek**

- Application: https://trek.nasa.gov/moon/
- Use as the benchmark for layer metadata, north/south-pole projections, distance, elevation profiles, Sun angle, slope, lighting, line of sight, NAC search, subsetting, downloads, and visible source attribution.

### Video and workflow references

Review these before selecting the terrain architecture. Treat videos as workflow references; official data documentation and repository contracts remain authoritative.

1. NASA Lunar Terrain Visualization in Unreal Engine 5 — Unreal Fest 2022  
   https://www.youtube.com/watch?v=VISq_V4W6LU  
   Focus on the comparison of Landscape, Nanite, and clipmap approaches; virtual shadowing; ground-to-distance transitions; and why a multiscale system is required.

2. Make the Moon in Blender Using Real NASA Scan Data  
   https://www.youtube.com/watch?v=pXZ4aOXc9h0  
   Focus on high-bit-depth height preparation, LROC color alignment, and displacement. Do not copy any projection or GIMP step without verifying that it preserves numerical values and georegistration.

3. Blender displacement documentation  
   https://docs.blender.org/manual/en/latest/render/materials/components/displacement.html  
   Use true displacement for large measured relief, bump/normal detail for fine visual structure, 16/32-bit maps, and adaptive subdivision where appropriate.

4. Blender glTF export documentation  
   https://docs.blender.org/manual/en/latest/addons/scene_gltf2.html  
   Bake tangent-space normals and glTF-compatible material channels. Verify exported GLB materials in the target web renderer.

## Target product architecture

### One application shell

Use the typed React/TypeScript viewer as the long-term product shell unless repository evidence proves a lower-risk consolidation path. Port or wrap the stronger legacy Three.js global/local scene into that shell instead of replacing it with a weaker mock scene. Keep one shared store for:

- current site and ROI;
- UTC timestamp/sample index;
- Sun/Earth source sample and interpolated display state;
- scenario/DEM realization;
- observer east/north/height;
- true/enhanced display relief;
- selected ridge/horizon bin;
- camera mode and transition state;
- layer visibility;
- source status and limitations.

Charts, metrics, target rays, event navigation, and 3D must subscribe to the same state. Add tests proving this.

### Scientific mesh and visual shell

Maintain two explicit concepts:

1. **Scientific terrain** — source DEM values in metres, exact grid/frame metadata, used by horizons, rays, observer placement, evidence, and numerical tests.
2. **Visual terrain representation** — LOD meshes, seam morphing, albedo, DEM-derived normals, roughness, micro-normal detail, shadows, atmosphere-free color grading, and optional visual relief.

The visual shell may improve appearance but cannot alter scientific samples or obstruction results. Make this separation visible in code types, bundle schemas, tests, UI labels, and manifests.

### Multiscale terrain

Replace the monolithic static local/regional mesh with a measured, tested multiscale system. A suitable starting design is:

- L0: full-detail 5 m Site01 terrain around the observer and ridge of record.
- L1: intermediate/downsampled transition ring generated deterministically from source terrain.
- L2: 80 m regional horizon/context terrain.
- Optional L3: global Moon visual context only.

Implement a clipmap, quadtree, tiled geometry, or an equivalently justified LOD system. Requirements:

- no visible cracks, holes, z-fighting, rectangular slab edge, or sudden height pop at the normal cameras;
- stable local-to-regional coordinate transform;
- deterministic resampling with documented pixel-center rules;
- skirts or geomorphing only as visual seam treatments, excluded from science;
- frustum culling and disposal of unused GPU resources;
- no full-mesh rebuild for every time-slider update;
- no change in observer or ridge scientific height when visual LOD changes;
- regression tests for tile boundaries and frame transforms.

Compare at least two implementation options against the current code, then implement the simplest one that satisfies the acceptance gates. Do not introduce Cesium ion or another paid service. If CesiumJS is already optional, keep it optional and offline-capable.

### Surface appearance

Build a source-aware lunar material stack:

- registered WAC or controlled NAC albedo where available;
- DEM-derived normals or slope normals, generated from the same source grid and tagged as derived data;
- physically plausible, mostly diffuse, high-roughness regolith response;
- subtle deterministic micro-normal/roughness detail allowed only as `VISUAL` and never as displacement in the science mesh;
- exposure and color grading that preserve near-black shadows without crushing every detail;
- no Earth-like atmosphere, blue haze, vegetation colors, glossy wetness, or procedural craters presented as source terrain;
- no baked image shadows used as current-time illumination truth.

Add a debug layer switch among `albedo`, `elevation`, `slope`, `normal`, `source coverage`, and `uncertainty`. Display product ID and resolution for the active layer.

### Shadows and lighting

Restore convincing low-Sun polar shadows without reintroducing a rectangular footprint shadow:

- Sun direction must come from the current JPL sample/state.
- Build a larger regional shadow-only terrain caster or another tested method whose boundary lies outside the hero view.
- Consider cascaded/dynamic shadows or contact shadows only if measured and stable on Apple Silicon.
- Keep low-level fill or earthshine as a clearly cinematic/display parameter; it must not imply illumination availability.
- Add a debug visualization for Sun direction and shadow-frustum coverage.
- Test start/middle/end timestamps and at least one visible-to-blocked transition.
- The scene timestamp, Sun lamp direction, horizon state, and chart must agree.

### Global-to-local camera experience

Create a camera-led narrative comparable in clarity to NASA Eyes:

1. Global Moon with south-pole site marker.
2. Smooth, cancelable flight to the south-pole region.
3. Regional camera showing DEM coverage and selected ROI.
4. Local oblique terrain hero camera.
5. Observer-level horizon camera.
6. Ridge-of-record camera positioned so the obstruction is spatially understandable.

Camera transitions must be cancelable by pointer input and Escape, honor reduced-motion preferences, preserve user orientation where reasonable, avoid clipping through terrain, and not reset unnecessarily when switching product workspaces.

Keep the global Moon visually detailed but label it visual context. Do not let dense object labels overwhelm the viewport. Use progressive disclosure and stable selected-object highlighting.

### 4D UTC interaction

- Keep a persistent timeline available in all primary workspaces.
- Provide play/pause, UTC display, sample step, speed, start/end, and previous/next transition.
- Show when a value is an exact sample, an interpolation, or a bracketed event.
- Do not extrapolate outside source samples.
- Synchronize Sun/Earth directions, rays, horizon chart, metric cards, mission window, Blender frame mapping, and exported report.
- Deep-link or serialize current site, timestamp, scenario, camera, and selected evidence where practical.

### 5D scenario and uncertainty axis

The fifth axis is selected uncertainty/mission scenario. Provide explicit choices such as:

- nominal DEM;
- total-Z uncertainty display;
- individual source-provided deterministic clones;
- observer position/height perturbations;
- operational requirement thresholds;
- deterministic stress cases.

Recompute relevant results when the scenario changes. Do not relabel clone frequency or pass counts as probability. Show scenario ID, changed inputs, source, and whether the result is calculated or merely visualized.

### Evidence and decision workspaces

Preserve and strengthen the existing Sky, Decision, and Evidence concepts:

- Keep ridge-of-record evidence linked to its horizon bin and 3D camera.
- Explain whether an obstruction lies in the 5 m local DEM or 80 m regional DEM.
- Show source coverage, first-hit distance, terrain height versus site, target elevation, horizon elevation, and margin.
- If terrain lies beyond the displayed crop, say so; never draw invented terrain.
- Keep certainty-height and coverage displays tied to recomputed, source-backed data.
- Let Moon Trek-style layer metadata and downloads coexist with the cinematic viewport without covering the model by default.

## Blender production rebuild

Update the Blender builder rather than hand-editing only a `.blend` file.

Requirements:

1. Blender CLI build remains reproducible on Blender 4.5+/5.x.
2. Use `bpy` only inside Blender's Python; keep geometry/frame mathematics in pure Python where testable.
3. Build the 5 m Site01 local terrain as the hero scientific mesh and the 80 m regional terrain as surrounding context.
4. Keep vertical scale 1.0 by default. Any cinematic exaggeration must be a labeled render option and excluded from coordinates/metrics.
5. Use real source displacement values. Use 16/32-bit maps where maps are part of the pipeline.
6. Add registered albedo where an appropriate controlled product is available; otherwise use a neutral procedural visual material clearly labeled as unsourced color, without altering geometry.
7. Use true measured displacement for major relief and baked tangent-space normals/roughness for web export detail.
8. Improve composition: black space, deliberate low-Sun key, restrained fill, readable observer scale, terrain-centered framing, and camera paths that reveal relief.
9. Avoid broad gray world fill, pasted-on rays, oversized props, or a distant camera that makes metre-scale ridges invisible.
10. Include editable named collections for scientific terrain, visual terrain, observer, rays, annotations, lights, and cameras.
11. Consume derived first-hit/visibility fields from the bundle. If absent, render rays as `NOT EVALUATED`, not blocked/visible.
12. Map animation frame to exact UTC/sample index and include that mapping in the manifest.
13. Export nonempty `.blend` and `.glb` files and verify the GLB reimports with expected bounding box, materials, nodes, and units.
14. Render and inspect start, middle, end, and at least one transition frame. Compare ray state, target elevation, horizon state, and Sun direction against the web app for the same UTC.

Update the scene manifest with source hashes, units, frame basis, DEM layers, vertical exaggeration, derived-output availability, active scenario, ray states, render hashes, Blender version, and limitations.

## Performance and engineering requirements

- Optimize for Apple Silicon without hiding scientific data.
- Measure rather than guess: first model-visible time, bundle load time, frame mean/p95, visible triangles, draw calls, GPU resource count where available, JS heap where available, and screenshot dimensions.
- Preserve the current smooth experience; do not accept a visually richer result that becomes unusable.
- Prefer LOD/culling/resource disposal over lowering source quality globally.
- Disable continuous `preserveDrawingBuffer`; implement capture using a render target, one-frame toggle if safe, or another tested screenshot path.
- Avoid unnecessary React rerenders and full geometry rebuilds on time-only changes.
- Dispose geometries, materials, textures, controls, listeners, and animation frames on teardown.
- Keep direct-file mode only if it can remain reliable without duplicating the whole product architecture. Localhost is the primary supported scientific mode.

## Accessibility and interaction quality

- Full keyboard access to workspaces, playback, event navigation, camera presets, layer controls, and dialogs.
- Visible focus states and semantic labels.
- Reduced-motion support.
- Sufficient contrast without losing lunar shadow detail.
- Text alternatives/source descriptions for important visual evidence.
- Responsive layouts at 1512×982, 1920×1080, and 390 px mobile width.
- No page overflow, native unstyled controls, HUD collisions, or model controls hidden below the fold.

## Required implementation phases

Execute these phases in order. Keep `docs/BUILD_STATUS.md` updated after each completed phase with commands, evidence, and unresolved limitations.

### Phase 0 — Protect and reproduce

- Read instructions and handoff documents.
- Record git state and baselines.
- Launch both existing viewers and capture before evidence.
- Confirm actual asset/model load paths and current data contracts.
- Identify overlapping uncommitted changes before editing.

### Phase 1 — Data/source registry and texture feasibility

- Inventory all existing PGDA, LROC, SVS, JPL, ShadowCam, and derived artifacts.
- Verify hashes and metadata.
- Determine whether an orthorectified LROC NAC/WAC product actually covers the Site01 hero footprint.
- If a suitable registered texture is unavailable, do not fabricate one. Implement neutral scientific shading and document the missing visual dataset.
- Add reproducible download/preparation scripts only for freely accessible public sources. Cache files locally and avoid redownloading unchanged assets.

### Phase 2 — Shared scientific/render contract

- Define typed contracts for grid/frame, terrain layers, visual layers, UTC, scenarios, ray results, and source status.
- Separate scientific values from presentation parameters.
- Add schema and unit tests for transforms, pixel indexing, nodata, sampling, first-hit state, timestamp mapping, and scenario selection.

### Phase 3 — Unified application shell

- Choose and document the consolidation route.
- Integrate the stronger global/local Three.js experience into the React scientific shell or justify an equivalent lower-risk design.
- Remove or isolate duplicated state and duplicated scene logic.
- Preserve direct-file launch if practical, but do not let it dictate a duplicated architecture.

### Phase 4 — Multiscale terrain and seam removal

- Implement tested clipmap/quadtree/tiled LOD.
- Make the 5 m terrain visibly dominant near the site.
- Blend into the 80 m regional context without a slab or false elevation.
- Add coverage/debug layers and seam regression tests.

### Phase 5 — Lunar material, shadows, and lighting

- Register source albedo if available.
- Add DEM-derived normals and visual-only roughness/micro-normal detail.
- Restore scientifically directed, visually credible shadows using context coverage that avoids rectangular boundaries.
- Verify three timestamps and a transition.

### Phase 6 — Camera-led experience and workspaces

- Implement global-to-local flight and six camera modes.
- Preserve user control and reduced-motion behavior.
- Make the model the default focal point; move deep analysis into progressive panels.
- Keep evidence selection synchronized with camera and charts.

### Phase 7 — 4D and 5D completion

- Finish synchronized UTC playback/event navigation.
- Finish scenario recomputation, provenance, and clear non-probabilistic labeling.
- Add serialized/deep-link state where feasible.

### Phase 8 — Blender parity

- Rebuild with local 5 m hero plus regional context.
- Add materials/cameras/lighting and derived ray states.
- Export, reimport, render, inspect, and compare against web UTC states.

### Phase 9 — QA, performance, accessibility, and packaging

- Run all unit, integration, browser, visual, Blender, schema, artifact, and packaging checks.
- Capture final evidence at required viewport sizes and start/middle/end times.
- Rebuild the release archive and record SHA-256 only after all source and generated assets are final.
- Update documentation and limitations.

## Required regression tests

At minimum, preserve/add tests for:

1. Site01 local ENU to raster-grid rotation and east-positive longitude.
2. Known Site01 timestamp reproducing the corrected Sun/Earth state.
3. Flat-horizon control versus terrain-aware horizon.
4. Nodata, crop boundary, row orientation, pixel-center indexing, and vertical units.
5. LOD tile edges: no scientific height change and no visible crack at deterministic camera points.
6. True relief versus visual enhanced relief: numerical outputs unchanged.
7. Timestamp synchronization across scene, chart, cards, event navigation, and exported report.
8. No extrapolation beyond JPL sample range.
9. Scenario/clone change recomputes data and keeps non-probabilistic wording.
10. Blender frame-to-UTC mapping and ray state parity.
11. GLB existence, nonzero size, units/bounds, material/texture references, and reimport.
12. Global Moon and local terrain actually render in localhost and supported direct-file modes.
13. No browser page errors during global/local flight, workspace switches, playback, relief changes, and evidence selection.
14. No layout collisions or document overflow at required viewports.
15. Keyboard and reduced-motion behavior.

Run the repository's complete commands, including as applicable:

```bash
python3 -m unittest discover -s blender -p 'test_*.py' -v
cd app && npm test
cd app && npm run build:file
cd web && npm test
cd web && npm run build
bash test_all.command
```

Run the documented browser smoke/E2E commands and the real Blender CLI commands. Do not claim a test passed if it was skipped, unavailable, or inferred from code inspection.

## Visual acceptance gates

The rebuild is not visually complete unless all are evidenced with screenshots:

- The global NASA Moon is visible within the initial experience and supports smooth navigation.
- The selected south-pole site is spatially understandable on the globe.
- The local 5 m terrain is unmistakably present and is the hero in the local view.
- The default local view does not look like a floating rectangular slab.
- Low-Sun relief is legible through correct directional lighting and shadows.
- Surface color reads as lunar regolith and identifies whether albedo is source-backed or neutral visual shading.
- True-scale and enhanced-relief states are clearly distinguishable and labeled.
- Observer, rays, ridge evidence, and terrain scale are mutually understandable.
- The React workspaces do not replace or obscure the model by default.
- Global/local flight, camera presets, timeline, scenario selection, layer controls, and evidence navigation function without console errors.
- Mobile layout remains usable even if full scientific interaction is desktop-first.

Compare final captures against NASA Eyes for hierarchy and navigation, not for branding. Compare analytical tools against Moon Trek for discoverability, metadata, and source transparency.

## Scientific acceptance gates

- All rendered metrics are marked `DEMO` or source-backed with explicit unvalidated status.
- Local and regional source frames, projections, resolutions, datums, hashes, and coverage are documented.
- Web and Blender use the same source timestamp and scenario for parity evidence.
- Rays with missing derived results remain `NOT EVALUATED`.
- First-hit distances and ridge states are generated from solver output, not visual ray intersections alone.
- Visual albedo/normal/shadow improvements do not change the science bundle or numerical tests.
- PGDA 69 remains a separate reference layer, not claimed validation.
- No mission certification, power prediction, or DSN availability claim is introduced.

## Required evidence artifacts

Create or refresh these without deleting useful prior evidence:

- before/after screenshots at 1512×982 and 1920×1080;
- mobile screenshot at 390 px width;
- global Moon screenshot;
- regional/local/observer/ridge camera screenshots;
- source coverage, albedo, elevation, slope, uncertainty, and seam-debug screenshots;
- start/middle/end and transition screenshots with visible UTC;
- Blender start/middle/end/transition renders;
- performance JSON or Markdown report with hardware/browser/build metadata;
- updated Blender scene manifest and bundle contract;
- final package SHA-256 and contents verification.

Store screenshots in existing documentation directories and use deterministic names. Do not overwrite unrelated reference images.

## Documentation deliverables

Update:

- `docs/BUILD_STATUS.md` — phase status, commands, evidence, actual pass/fail/skip state.
- `docs/DATA_PROVENANCE.md` — every new source, product ID, URL, hash, frame, resolution, role, and limitation.
- `docs/SCIENTIFIC_CONTRACT.md` — scientific versus visual layer contract and shared UTC/scenario semantics.
- `docs/SCIENCE_VALIDATION_REPORT.md` — only validation actually performed.
- `docs/VISUAL_REGRESSION_AUDIT.md` — defect, root cause, fix, evidence, residual risk.
- `docs/UX_ACCEPTANCE.md` — camera, controls, accessibility, responsive behavior.
- `docs/FINAL_AUDIT.md` — reproducible final state and remaining risks.
- application READMEs and Blender/run instructions.

If the release remains unvalidated, put `SOURCE_BASED_UNVALIDATED` prominently in the final report and application provenance surface.

## Final response format

When implementation and verification are complete, report:

1. The user-visible result first.
2. Major architecture and terrain changes.
3. Data added or intentionally not added, with sources and hashes.
4. Scientific changes and remaining unvalidated claims.
5. Tests/builds/renders with exact pass/fail/skip counts.
6. Performance measurements and comparison to baseline.
7. Clickable paths to screenshots, `.blend`, GLB, manifests, reports, and release archive.
8. Any remaining blocker that truly requires user action.

Do not use vague claims such as “NASA accurate,” “fully validated,” “production ready,” or “all tests pass” without direct evidence. Review the actual diff and generated artifacts before writing the summary, because the summary must include material changes even if they were made during debugging.

Begin now: inspect instructions and git state, run baseline tests, open both current viewers, capture the actual model, and then implement the phases in order.

