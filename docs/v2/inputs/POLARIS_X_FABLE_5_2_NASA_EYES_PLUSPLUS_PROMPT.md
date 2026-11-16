# POLARIS X — Fable 5.2 “NASA Eyes × 2” final production prompt

Copy everything below this line into a new Fable 5.2 coding session with the repository folder attached. Use high effort. This is an execution prompt, not a request for another plan or critique.

---

You are the principal engineer, scientific visualization director, lunar geospatial specialist, real-time graphics architect, Blender technical director, interaction designer, test owner, and release owner for POLARIS X. Continue the existing project in place and carry it from a strong scientific prototype to a public-facing lunar digital twin whose interaction quality exceeds NASA Eyes while retaining stricter evidence and uncertainty disclosure.

Your target is not “make it look like NASA.” Reverse-engineer the interaction principles of NASA’s best public tools, independently implement the useful patterns for this product, and surpass them in terrain fidelity, decision support, uncertainty explanation, provenance, accessibility, responsiveness, and reproducibility. Do not copy proprietary source code, scrape private APIs, use NASA insignia, imply endorsement, or imitate branding so closely that POLARIS X could be mistaken for an official NASA product.

## Execution behavior

This is an actual implementation request. Do not return only a plan, prompt, mockup, or list of recommendations. Inspect the repository, run the baseline, fix the current defects, implement the experience, inspect it in a real browser, run Blender, verify artifacts, update documentation, and build the final package.

Continue phase by phase without waiting for “continue” while safe in-scope work remains. A progress message is not a stopping point. If one item is blocked by a download or another writer, work on an independent phase and return to it later. Stop only for a genuine user decision, missing private authority, a paid service, or a destructive action that requires confirmation.

Give a concise update every few tool calls. If the client exposes an exact remaining-session percentage and it reaches 5%, finish or safely revert the current edit, run the smallest relevant verification, update the handoff and `docs/BUILD_STATUS.md`, and stop. If no exact percentage exists, do not guess.

Use at most three focused subagents concurrently. The main agent owns integration and acceptance. Useful optional specialties are:

1. `nasa-experience-auditor`: inspect NASA Eyes, Moon Trek, and Open MCT behavior and turn patterns into measurable POLARIS requirements without copying code.
2. `lunar-rendering-engineer`: multiscale terrain, shader/material work, WebGL profiling, camera grammar, Blender parity.
3. `scientific-contract-auditor`: coordinate frames, UTC/scenario synchronization, numerical-vs-visual separation, provenance, decision-language correctness.

Do not pause merely to create these skills if they do not exist.

## Repository, ownership, and safety

Expected repository:

`/Users/anishmeruva/Downloads/POLARIS-X5D-Blender-Codex`

Expected branch and base commit: `b-experience` at `8079924`, with a large intentionally dirty working tree containing user, Codex, and Claude work. Preserve it.

Before editing:

1. Read `AGENTS.md` completely.
2. Run `git status --short --branch` and record the state.
3. Read the latest sections of `docs/BUILD_STATUS.md`, `docs/DATA_PROVENANCE.md`, `docs/SCIENTIFIC_CONTRACT.md`, `docs/FRONTEND_SOURCE_OF_TRUTH.md`, `docs/RELEASE_READINESS.md`, `docs/RENDERING_VALIDATION.md`, `docs/PENUMBRA_FINAL_VISUAL_AUDIT.md`, and `web/docs/VIEWER_BUNDLE_CONTRACT.md` when present.
4. Inspect diffs and modification times for every shared file before editing. Confirm no concurrent writer is active.
5. Preserve uncommitted and untracked files. Never run `git reset`, `git restore`, `git checkout --`, `git clean`, destructive recursive deletion, broad repository-wide formatting, history rewriting, remote push, PR creation, or remote changes without explicit permission.
6. Do not modify unrelated projects or request paid services, credentials, or account creation.

`web/` is the primary product shell. `app/` is the legacy/direct-file viewer and regression/fallback path. Do not create a third frontend. Preserve `app/` unless an explicit compatibility fix is required; concentrate public product work in `web/`.

## Current verified checkpoint — use this only after checking the live files

The current project is far beyond the old “Connecting Ridge blank screen” build:

- `web/` has a full-screen React/TypeScript/R3F product with Story, Explore, Decision, and Evidence workspaces.
- It displays a NASA SVS global Moon, transitions to south-pole context, and shows a 401×401 5 m local DEM inside a 401×401 80 m regional context crop.
- Site01 can display a registered 2 km × 2 km, 1 m/pixel LROC controlled south-pole average mosaic. It covers about 78% of ROI6 and is correctly labeled `VISUAL`; it is never numerical authority or mission-time lighting.
- Site04 has no registered albedo and uses neutral regolith/display shading.
- Timeline, Sun/Earth rays, margin ribbon, ridge-of-record evidence, certainty-height scenarios, evaluated terrain realizations, coverage sidecars, source labels, and global Moon navigation exist.
- Blender 5.3 produced a full 401² Site04 ROI3 5 m mesh, 401² 80 m display context, `.blend`, `.glb`, manifest, and start/middle/end frames. GLB re-import passed.
- The Mac gate most recently passed geometry 25/25, ingest 6/6, app 25/25, source 18/18, terrain 7/7, web unit tests 89 pass/1 optional-data skip, and Playwright 52/52.
- Release status is still `SOURCE_BASED_UNVALIDATED`. Keep it that way unless real independent, frame-compatible validation is completed and documented.

The current release ZIP was rebuilt after its checksum sidecar. The current archive hash was observed as:

`68782a83966079979de26e38c87c9e1b358e0193c8595aa8ce135333a2d7769e`

The existing `.sha256` sidecar still contains an older hash. Recompute it only after all source, docs, tests, Blender artifacts, and packaging are final.

## Defects found in the live model — fix these before adding spectacle

Treat this list as a required regression backlog. Reproduce each item on the current source and add a test before or with its fix.

### P0 — decision-language contradiction

On Site01 ROI6 at the 1 m mast, Decision displays a minimum Sun visibility of 100.0% but says every realization “loses the Sun for part of the window.” `web/src/components/DecisionHero.tsx` currently emits that sentence unconditionally. Generate verdict language from actual values:

- if `min >= 100`, state that none of the evaluated realizations loses the Sun;
- if `min < 100 && max >= 100`, state that some lose it and some do not;
- if `max < 100`, state that all lose it;
- keep “evaluated realizations,” never probabilities.

Add unit and browser cases for all three branches. Search all Story, Guided Demo, Decision Card, tooltips, alt text, and print copy for the same logical contradiction.

### P0 — release integrity

The ZIP checksum sidecar is stale after repackaging. Change `package_release.command` so one successful command atomically creates the archive and matching `.sha256` sidecar, then verifies the pair from the sidecar directory with `shasum -a 256 -c`. Test ZIP integrity, required entries, forbidden transient entries, and checksum equality. Update stale documentation only after the final build.

### P1 — short-desktop and mobile composition

At approximately 1512×783, the global-Moon information card can collide with the camera/control strip. At 390 px, the current evidence screenshot has a clipped two-line site title and terrain/ray labels colliding with metadata. “No horizontal scroll” is insufficient.

Add explicit visual/layout gates at:

- 390×844 and 430×932 phones;
- 768×1024 tablet portrait;
- 1024×768 and 1366×768 short laptops;
- 1440×900, 1512×783, 1512×982, 1920×1080, and 2560×1440 desktops.

For every size require: no overlap, no clipped headings, no controls covering cards, no unreadable ray label pileups, no focus target hidden behind sticky UI, no horizontal document overflow, and a usable terrain viewport. Mobile must be a designed hierarchy, not the desktop layout squeezed into one column. Collapse secondary metrics and provenance into sheets/details; keep scene, one primary metric, clock, play/pause, site/scenario, and a single layer control immediately usable.

### P1 — deterministic Moon-to-terrain state

In a live review, a terrain camera button could become selected while the global Moon remained visible. Make the state machine explicit:

- `Moon` means globe overlay visible and no terrain camera button reports selected;
- selecting any terrain camera view closes the globe first, then performs the requested camera transition;
- `Enter terrain` always closes the globe and lands on the documented regional/context framing;
- switching site while the globe is open updates the marker and card without corrupting the next terrain camera;
- browser Back/Forward and deep links restore the correct mode.

Add tests for Moon → Approach, Moon → Regional, Moon → site change → Enter terrain, rapid repeated clicks, reduced motion, and short-height layouts.

### P1 — console cleanliness

A live Vite session logged: “Attempted to synchronously unmount a root while React was already rendering.” Reproduce under dev and production builds. Determine whether it is HMR-only or a real Canvas/React transition. Do not suppress it. Make Story/Explore/workspace and globe transitions mount-safe, then require zero unexpected console errors and zero React warnings through the full guided-demo and site-switch sequence.

### P1 — local terrain visual quality

Site01 LROC texture is the strongest local view. Site04 neutral terrain and the Blender hero remain soft, patchy, and visibly less convincing. The local/regional transition and visual cut must not read as a slab, trench, island, or blurred rectangle. Improve material, normal reconstruction, tonal range, camera composition, and transition design without altering numerical elevations or implying imagery exists where it does not.

### P2 — only two fixed terrain levels

The current 5 m local plus 80 m regional arrangement is a useful milestone, not a NASA Eyes-class scale system. Implement a documented multiscale solution: preferably concentric clipmap/ring LOD or a quadtree with geomorphing, frustum culling, skirts/stitching, deterministic source selection, and disposal. Use a real selectively downloaded/cropped intermediate product where available, such as a PGDA 90 20 m product covering the site. Do not upsample 80 m data and market it as new 20 m detail. If an intermediate numerical product cannot be verified, retain a two-level scientific contract while improving only the visual transition and documenting the limitation.

## What “NASA Eyes × 2” means

Do not interpret “2×” as twice as many panels, animations, particles, labels, or decorative effects. It means twice the clarity and proof per interaction.

### Reverse-engineered NASA Eyes interaction grammar

The live NASA Eyes experience uses these product patterns:

- one full-viewport 3D world as the primary interface;
- a small breadcrumb/object identity at the top;
- object selection and focus rather than exposing raw data-file selectors as the main experience;
- a left contextual panel with `Info`, `Toolbox`, and `View Options` tabs;
- independent panels for description, related objects, compare size, distance measurement, camera mode, surface map, layer visibility, and texture quality;
- a compact right-side vertical tool rail for info/layers/zoom/light/fullscreen/settings;
- a persistent bottom time conductor with current date/time, live/fixed state, speed controls, slider, and direct time input;
- `Nearby`, `System`, and `Follow` camera concepts;
- flood, shadow, and natural lighting modes;
- guided Stories separate from free exploration;
- a searchable categorized object library;
- shareable links and embed code;
- the ability to hide UI and let the world fill the screen.

Adapt these principles, not their visual assets or code. For POLARIS X:

- object focus becomes site, observer, Sun, Earth, ridge of record, terrain layer, uncertainty realization, and mission window;
- camera scope becomes Moon, South Pole, regional terrain, local approach, mast-eye, ridge inspection, and overhead;
- Toolbox becomes distance/bearing, elevation profile, slope probe, line of sight, timestamp comparison, and source inspection;
- View Options becomes surface source, display/scientific lighting, labels, rays, uncertainty overlay, terrain LOD/debug, and UI visibility;
- Stories becomes a guided mission narrative driven entirely from current bundle values;
- Share produces a reproducible deep link containing bundle, site, scenario, UTC sample, camera, surface layer, light mode, and selected ridge.

### NASA Moon Trek patterns to surpass

Moon Trek combines 3D globe, global/north/south-pole projections, searchable data layers, layer stacking and opacity, metadata, screen capture, share links, distance, elevation profile, Sun angle, slope, line of sight, subsetting/download, and 3D-print output. POLARIS does not need every tool, but it must provide the mission-relevant subset with a cleaner workflow:

- a scale ladder from globe to south-pole map to local surface;
- searchable/selectable authoritative and visual layers with source, resolution, date, projection, coverage, hash, and role;
- distance/bearing measurement in the documented lunar frame;
- an elevation/slope profile whose values come only from the chosen numerical DEM;
- a line-of-sight/ridge probe tied to the same UTC/scenario contract;
- visual layer opacity/compare without changing calculations;
- copyable deep links and evidence screenshots;
- clearly separated “download source/derived evidence” actions.

### Open MCT patterns to surpass

Open MCT’s central principle is a single Time Conductor synchronizing multiple views around one time system. POLARIS already has one clock; make it unbreakable:

- one UTC sample selection drives the 3D scene, rays, margins, timeline, event list, charts, ridge highlight, Decision snapshot, and Evidence view;
- no component owns an independent hidden time;
- no extrapolation beyond samples;
- play rate, pause, previous/next event, direct UTC, and sample stepping are accessible by keyboard;
- selected scenario/realization is a separate fifth axis, never a fifth physical spatial dimension;
- deep links and exported reports capture both UTC and scenario.

## Product experience specification

### First 30 seconds

1. Load directly into a crisp global Moon with the selected south-pole site marker, minimal branding, source status, and one clear action: `Fly to site`.
2. `Fly to site` performs one continuous, interruptible global → south pole → regional → local camera journey. Reduced-motion mode uses meaningful cuts.
3. At the local surface, the terrain occupies at least 70% of the available visual attention. UI starts collapsed to the essentials.
4. The selected UTC and scenario are visible. Sun/Earth rays, state, and margins agree with the bundle at that sample.
5. A first-time user can answer “Where am I?”, “What time?”, “Which scenario?”, “Can I see the Sun/Earth?”, “What blocks it?”, and “How trustworthy is this?” without opening raw tables.

### Progressive disclosure

Use three depths:

- `Explore`: immersive 3D, time, scenario, primary visibility, selected obstruction.
- `Analyze`: surface/layer tools, profile, measurement, horizon, events, compare.
- `Evidence`: source registry, hashes, contracts, validation gates, limitations, downloadable machine-readable evidence.

Retain Story and Decision where they improve comprehension, but remove duplicated controls and competing narratives. Raw filenames belong in Evidence, provenance, or an advanced data chooser—not the default top bar.

### Camera and interaction quality

- Mouse/trackpad/touch orbit, pan, and zoom must feel stable at every scale.
- Camera transitions are interruptible and never cross terrain, clip through the Moon, or end inside a mesh.
- Named views are deterministic resets, not approximate suggestions.
- Focus a ridge, observer, ray, or site with a double-click/explicit action and provide `Back to previous view`.
- Labels use decluttering, priority, occlusion, collision avoidance, and edge pinning. Never stack opaque labels over the same feature.
- Add `Hide UI`, fullscreen, screenshot, copy link, and reset view.
- Preserve keyboard operation and a visible focus system.

## Rendering architecture

### Scale and geometry

- Global Moon: NASA SVS model, visual context only. Disclose polar pinching and never sample it for local science.
- South-pole/regional: real PGDA context products in their documented frame. Keep source role explicit.
- Local: full 401² 5 m DEM by default, one Blender/WebGL unit = one metre, vertical scale 1:1.
- Intermediate LOD: selectively crop a verified PGDA product if used. Record source, transform, resampling, decoded hash, nodata, and role.
- Use floating/local origins so precision is stable.
- Eliminate cracks with edge-compatible sampling, skirts or stitching, and geomorphing. No visible rectangular slab or shadow boundary.
- Numerical calculations continue using authoritative arrays under the existing scientific contract; rendering LOD never silently changes solver inputs.

### Surface material

- Site01: correctly register and map the controlled LROC NAC average mosaic. Preserve the `VISUAL` label, coverage percentage, product ID, registration evidence, baked-shading warning, and “not mission-time lighting.”
- Site04: seek a public registered LROC/PGDA image or PGDA 104 enhanced terrain only if coverage, projection, license/credit, and registration can be verified. Otherwise use neutral regolith with DEM-derived normals, slope/curvature tonal variation, physically plausible roughness, and restrained procedural micro-normal detail labeled visual-only.
- Never add procedural displacement to numerical geometry. Micro-detail may affect normals/roughness only.
- Surface modes: natural/registered image, neutral regolith, elevation, slope, normals, source coverage, uncertainty where numerically available, and display shadow model.
- Each mode must be a pure visual change unless explicitly identified as an analytical layer. Instruments must not change when switching display layers.

### Lighting and shadows

- `Scientific`: true bundle Sun direction/elevation, fixed documented exposure, no secret fill that could be read as illumination, and explicit limitations.
- `Display`: same azimuth and timestamp, clearly labeled relief fill/exposure aid, with no effect on any number.
- Avoid a rectangular shadow-map footprint. Prefer DEM-aware horizon/cast-shadow display methods with tested transitions.
- The visibility state always comes from the bundle/solver, never from rendered pixels or a lamp.

### Performance targets on the user’s Apple Silicon Mac

Measure, do not guess:

- 1512×982 DPR 2, active local terrain: median frame interval ≤16.7 ms and p95 ≤22 ms during orbit and camera transition;
- no repeated frame >50 ms during ordinary interaction after assets are loaded;
- stable heap and GPU resource counts after 20 site/layer/globe cycles; no monotonic leak;
- initial shell interactive within 2 s locally, first global Moon within 4 s, local terrain within 5 s on a warm local server;
- lazy-load the global model, terrain packs, LROC image, Evidence-heavy data, and optional Cesium;
- no continuous `preserveDrawingBuffer`; screenshots use an explicit render/read path;
- use frustum culling, LOD, typed arrays, memoized geometry, texture anisotropy chosen from capability, and explicit GPU disposal;
- consider KTX2, Meshopt, or Draco only when the build remains reproducible and visual/source hashes are documented;
- reduce the current ~1.03 MB uncompressed `Scene3D` chunk through sensible code splitting without fragmenting the architecture.

Record hardware, browser, DPR, resolution, scene, data set, frame timing method, heap, triangle count, draw calls if available, and limitations in `docs/RENDERING_VALIDATION.md`.

## Blender parity and cinematic evidence

Blender is the editable authoring/evidence artifact; WebGL is the product runtime.

- Keep CLI reproducibility through `rebuild_blender_hero.command`.
- Improve Site04’s material and composition without inventing image coverage.
- Use registered Site01 albedo in an additional Blender build if the UV/projection mapping can be reproduced and recorded.
- Preserve full local 401² mesh and regional context, 1:1 relief, named collections, UTC sample mapping, observer, Sun/Earth rays, and source labels.
- Remove the soft grey “clay island” look using calibrated exposure, better neutral regolith, DEM-derived normals, contact/long-shadow readability, and better cameras. Do not turn cinematic lamps into science.
- Produce global/context/approach/mast/ridge/overhead cameras plus start/middle/end UTC renders.
- Re-import every GLB into an empty Blender scene and record objects, meshes, vertices, polygons, materials, lights, animation state, and bounds.
- Verify start/middle/end image state against bundle values and web values at the same samples.

## Scientific invariants

1. Dimensions 1–3 are local east, north, elevation; dimension 4 is UTC; dimension 5 is selected uncertainty/mission scenario, not physical space.
2. Keep `SOURCE_BASED_UNVALIDATED` until independent validation actually passes.
3. Never invent missing NASA elevation or albedo and label it NASA.
4. Azimuth is 0° north, 90° east clockwise in documented local ENU, transformed into the source raster basis.
5. Z is metres. Record lunar radius/datum, MOON_ME/DE421 frame, east-positive longitude, projection, pixel-center convention, row direction, nodata, crop and resampling.
6. Finite-DEM geometric visibility is not power, thermal safety, DSN availability, link margin, or mission certification.
7. Deterministic clones/realizations are tested alternatives, not calibrated probabilities.
8. One timestamp and one scenario drive every numerical and visual readout.
9. Do not extrapolate outside ephemeris samples.
10. Visual layers, light aids, textures, micro-normals, seam fades and camera effects never enter numerical solvers.
11. Disclose source URL, acquisition date, product, resolution, coverage, hashes, horizon reach, observer height, uncertainty method, and limitations.
12. Do not claim NASA/JPL endorsement, validation, flight readiness, or accuracy from appearance.

## Required implementation sequence

### Phase 0 — protect and reproduce

Inspect state, active writers, existing servers, latest ZIP, checksum, artifacts, and docs. Run baseline tests before editing. Capture current screenshots at all target sizes and preserve them under a timestamped `before` folder.

### Phase 1 — correctness and release blockers

Fix the Decision copy branches, checksum generation, Moon/terrain state machine, console warning, and short-height/mobile collisions. Add regression tests first or with each fix. Run the focused tests after every small change.

### Phase 2 — NASA-class interaction shell

Implement the minimal full-screen world shell, object-focused contextual panel, compact tool rail, one time conductor, hide-UI/fullscreen/share/reset, and progressive disclosure. Preserve the strongest Story/Decision/Evidence work instead of rewriting blindly.

### Phase 3 — global-to-local journey and deep links

Build deterministic scale transitions and shareable state containing bundle, dataset/site, scenario, UTC sample, camera, layer, light mode, selected ridge, and workspace. Test refresh, Back/Forward, invalid state, and no silent bundle substitution.

### Phase 4 — multiscale terrain and materials

Implement verified LOD/ring architecture or document why an intermediate source is unavailable. Eliminate seams/slabs, improve normal/material quality, preserve Site01 LROC honesty, and produce a credible Site04 neutral surface.

### Phase 5 — analytical toolbox

Add mission-relevant Moon Trek-style measurement/profile/slope/line-of-sight/source tools tied to the existing contract. Do not duplicate solver science in the renderer. Every tool has tests, units, frame, source and exportable evidence.

### Phase 6 — 4D/5D and narrative polish

Make time/scenario synchronization, playback, events, uncertainty comparison, guided scenes, and decisions unbreakable. Ensure every sentence is value-conditional and tested at edge cases such as 0%, 100%, missing sidecar, no DEM, no attribution, and metrics-only scenarios.

### Phase 7 — Blender parity

Rebuild, inspect, improve, re-import GLBs, compare three UTC frames, and document the gap between cinematic display and numerical authority.

### Phase 8 — performance, accessibility and adversarial QA

Profile native Chrome on the Mac, not only SwiftShader. Test keyboard, reduced motion, contrast, focus, screen-reader summaries, touch, mobile hierarchy, DPR 1/2, WebGL failure, slow asset loading, missing context/albedo/global model, corrupt bundle, deep link, rapid site/scenario switching, and repeated resource cycles.

### Phase 9 — release

Run the complete matrix, regenerate evidence, update docs, build ZIP plus checksum atomically, test ZIP integrity and contents, and leave exact launch commands. Do not commit or push unless asked.

## Required test and visual matrix

At minimum run:

```bash
bash test_all.command
cd web && npm install && npm run typecheck && npm test && npm run build && npx playwright test
cd ../app && ../.venv/bin/python tests/browser_smoke.py --screenshot
cd .. && bash rebuild_blender_hero.command
bash package_release.command
```

Add tests that specifically assert:

- Decision language agrees with min/max values at 100%, mixed and all-loss cases;
- Moon mode cannot coexist with a selected terrain camera;
- every camera and `Enter terrain` closes the globe correctly;
- one clock drives scene/readouts/charts/evidence after play, seek, event and deep-link restore;
- display layers change no instrument number;
- LROC cannot enter a DEM/solver path;
- short-desktop and phone bounding boxes do not intersect;
- headings and labels are not clipped at target sizes;
- label collision/decluttering has bounded overlap;
- zero unexpected console errors/warnings in production;
- resource counts stabilize after repeated transitions;
- package checksum matches and required/forbidden archive entries are enforced.

Do not weaken tests to make them pass. Fix the product.

## Acceptance gate: “2× NASA standard”

Do not call the work complete unless all are true:

1. A first-time user sees the Moon and can reach real local terrain without instructions.
2. The global-to-local transition is smooth, interruptible, deterministic, and reduced-motion safe.
3. The actual terrain is the visual hero at all target sizes.
4. Site01 registered imagery looks photographic without being misrepresented as mission-time lighting.
5. Site04 looks credible without pretending to have imagery it lacks.
6. No slab, trench, crack, floating crop, rectangular shadow boundary, texture seam, or obvious LOD pop is visible in accepted views.
7. Time and scenario are synchronized everywhere; deep links reproduce the exact state.
8. Decision prose is numerically self-consistent at all edge cases.
9. Moon Trek-style mission tools expose frame, units, source and evidence.
10. UI can be hidden so the 3D world fills the screen; analytical UI returns without losing state.
11. Desktop, short-laptop, tablet and phone layouts are visually composed, not merely overflow-free.
12. Native-Mac performance meets the measured targets or any miss is explicitly documented with evidence and the best safe optimization completed.
13. Blender and web agree on bundle values at start/middle/end and GLB re-import passes.
14. All tests pass except an explicitly justified optional-data skip; no unexpected console errors remain.
15. Final ZIP and checksum verify, docs match the final tree, and no transient/private/paid-service data is packaged.
16. Status remains scientifically honest and no NASA endorsement is implied.

## Authoritative references and what to learn from them

Use these as public references and cite them in the project docs. Verify live behavior before relying on it.

- NASA Eyes on the Solar System: https://eyes.nasa.gov/apps/solar-system/ — full-canvas world, object focus, camera scopes, view options, lighting modes, time conductor, stories, share/embed, UI hiding.
- JPL’s Eyes overview: https://www.jpl.nasa.gov/news/explore-the-solar-system-with-nasas-new-and-improved-3d-eyes/ — direct manipulation, perspective/lighting control, guided journeys, past/present/future mission time.
- NASA Moon Trek: https://trek.nasa.gov/moon/ and https://trek.nasa.gov/moon/jpl/config/textAbout.html — globe/polar projections, searchable layers, metadata, blending, measurement, profiles, Sun angle, slope, line of sight, subsetting and downloads.
- NASA Open MCT: https://github.com/nasa/openmct and https://github.com/nasa/openmct/blob/master/API.md — single time conductor, UTC systems, fixed/realtime modes, synchronized data views, plots/tables/layouts.
- NASA SVS Moon models: https://svs.gsfc.nasa.gov/14959/ — web-ready LRO global models and explicit polar artifact disclosure.
- NASA SVS CGI Moon Kit: https://svs.gsfc.nasa.gov/4720 — LRO color/elevation assets for rendering with credits and bit-depth options.
- NASA PGDA 78: https://pgda.gsfc.nasa.gov/products/78 — 5 m south-pole DEMs, uncertainty, slopes, counts, clones, ROIs and the ~90% interpolation limitation.
- NASA PGDA 90: https://pgda.gsfc.nasa.gov/products/90 — regional south-pole COG products and potential verified intermediate/regional LOD sources.
- NASA PGDA 104: https://pgda.gsfc.nasa.gov/products/104 — shape-from-shading-enhanced selected south-pole terrain; use only if site coverage, frame and role are verified.
- JPL Horizons API: https://ssd-api.jpl.nasa.gov/doc/horizons.html and https://ssd.jpl.nasa.gov/horizons/manual.html — ephemeris authority and observer/frame conventions.
- LROC controlled south-pole average mosaic: https://data.lroc.im-ldi.com/lroc/view_rdr/NAC_POLE_SOUTH_CM_AVG — visual albedo source with baked multi-image lighting limitation.

Do not treat a reference product as independent validation merely because NASA published it. Compare frame, epoch, observer height, target definition, terrain version and metric before any validation claim.

## Required documentation and final response

Update:

- `docs/BUILD_STATUS.md`
- `docs/DATA_PROVENANCE.md`
- `docs/SCIENTIFIC_CONTRACT.md`
- `docs/RENDERING_VALIDATION.md`
- `docs/UX_ACCEPTANCE.md`
- `docs/FINAL_AUDIT.md`
- `docs/RELEASE_READINESS.md`
- `web/docs/VIEWER_BUNDLE_CONTRACT.md` when the state/deep-link contract changes

Record exact commands, hardware, browser, resolutions, data files, hashes, pass/fail counts, screenshots, limitations, and remaining unvalidated claims. Distinguish tests from scientific validation.

Your final response must lead with the achieved outcome and include:

1. what visibly changed;
2. which live defects were fixed and their regression tests;
3. data sources added or deliberately rejected and why;
4. performance measurements;
5. complete test results;
6. Blender/GLB artifact paths and checks;
7. release ZIP path, byte size and matching SHA-256 sidecar;
8. exact launch command;
9. remaining scientific and visual limitations;
10. confirmation that nothing was reset, committed or pushed unless the user explicitly authorized it.

Do not say “NASA accurate,” “validated,” “flight ready,” “finished,” or “2× NASA” unless every corresponding evidence gate above actually passes. Build the strongest honest product the current sources support.
