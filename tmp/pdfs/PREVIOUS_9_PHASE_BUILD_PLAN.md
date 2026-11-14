# POLARIS X — Complete Codex Build Prompts

**Goal:** Transform the existing `POLARIS-X5D-Blender-Codex` project into a real-data-backed, interactive 5D lunar mission-resilience digital twin on an Apple Silicon MacBook. **5D means 3 spatial coordinates + UTC time + selectable scenario/uncertainty dimension; it does not mean five spatial dimensions.**

## Start here

1. Unzip `POLARIS-X5D-Blender-Codex-Mac.zip` into `~/Downloads/`, open the extracted `POLARIS-X5D-Blender-Codex` directory in **Codex**, and give Codex permission to edit files only inside that directory.
2. The repo already has `AGENTS.md`. **Do not run `/init` over it** or erase it. Attach the two POLARIS research PDFs to Codex if convenient, but the prompts below are self-contained.
3. Paste **Prompt 1 (Master)** first. Codex should implement in stages. If it stops or needs a tighter task, paste **Prompts 2–8 in order**. Paste Prompt 9 for a final independent audit.
4. Sources and constraints: NASA Space Apps *Lunar Landing Site Navigator* challenge; NASA PGDA products 78/90/104; JPL Horizons; NASA SVS lunar polar illumination; Cesium Moon. Do not treat unverified sources, synthetic assets, or AI art as science results.

---

## PROMPT 1 — MASTER: Build POLARIS X end-to-end

```text
You are the principal engineer, scientific software architect, senior Blender technical artist, and QA lead for POLARIS X, a 5D lunar-surface mission-resilience digital twin for NASA Space Apps 2026. I want a REAL, WORKING Mac application, not mockups, diagrams, task lists, or an attractive spinning Moon.

WORKSPACE: You are running inside the extracted POLARIS-X5D-Blender-Codex directory on my Apple Silicon MacBook Pro. Confine all edits, installations, generated assets, and run artifacts to this project directory or its virtual environments. Do not modify ~/hackathon_agents, GitHub remotes, other users' machines, unrelated system settings, or my other projects. You may edit and test this local project without stopping for routine approvals. Ask only before paid services/credits, new account connections, pushing/committing to external remotes, or destructive operations outside the project. Do not claim to use tools you cannot access.

READ THESE FIRST:
- AGENTS.md and README.md at project root.
- app/README.md, app/package.json, app/src/{main.js,science.js,scene.js,pro.js,fallback.js,styles.css}.
- app/scripts/prepare_science.py and app/tests/*.test.js.
- blender/{build_lunar_science_scene.py,build_from_nasa_bundle.py,polaris_geometry.py,test_geometry.py}.
- Both POLARIS X research PDFs if present; otherwise proceed from the complete requirements below rather than blocking.
Run existing tests BEFORE changing anything, inspect commands and current file layout, and record a baseline report in docs/BUILD_STATUS.md.

THE PRODUCT:
- 3D: high-quality, freely explorable lunar globe; fluid zoom to real south-polar terrain, site markers, local DEM-derived mesh and observer instruments.
- 4D: a UTC mission clock with seek, play/pause, speed, exact date/time, timeline scrubber, sampling and synchronization. Any frame must produce the same scientifically determined Sun/Earth geometry, shadow visibility, horizon plot, and metrics.
- 5D: a selectable ensemble/scenario dimension with named NASA elevation-error clones where available, observer offsets, height, arrival-time shifts, DEM-resolution perturbations, and explicitly declared mission assumptions. Make it visually obvious which conclusion changes. Do not represent arbitrary scenario counts as calibrated probabilities.
- True horizon-aware Sun/Earth geometric visibility; first-blocking obstacle identification, skyline profile, azimuth/elevation, local ENU vectors, simultaneous access, interruption duration, and event times.
- Two-site comparison (start with Connecting Ridge / Site01 and Shackleton Rim / Site04) plus Peak Near Shackleton and de Gerlache Rim once the pipeline is sound.
- Transparent mission decisions: requirements, pass/fail, margin to failure, one recomputed repair (e.g. change date/position/mast height), robustness comparison and a reproducible JSON/CSV report.
- Physically honest solar power scenario only if assumptions are explicit; Sun visible is NOT guaranteed electric power; Earth visible is NOT a scheduled DSN/radio link.
- A credible professional UX: NASA-inspired mission control, readable scientific graphs and maps, accessibility, responsive layout, keyboard control, and high-frame-rate 3D rendering.

STACK AND MIGRATION:
- Keep the working legacy app and tests running. Build an orderly React + TypeScript + Vite UI (with CesiumJS lunar 3D Tiles asset 2684829 when authorized) rather than destroying the existing plain-JS implementation immediately. Retain a token-free local terrain/GLB fallback. Do NOT mistake Cesium's decorative Moon object for Cesium Moon's global lunar terrain.
- Use Python for geospatial data preparation (rasterio, NumPy, pyproj/GDAL only with validated lunar CRS conventions), JPL Horizons ingestion, and science-reference checks. Use a TypeScript science package or a documented versioned JSON contract so browser and Blender agree.
- Use Blender 4.5+/5.x bpy for locally editable scientifically referenced DEM meshes, georeferenced site markers, materials, cameras, animations, overlays, renders, GLB export. Blender is a visual/rendering tool, not the authority for astronomical computations.
- Keep astronomy/terrain numerical calculations separated from artistic materials, shadows, LLMs and generative models. A Blender Sun lamp must follow validated Sun direction, never produce it.
- Optionally use installed Codex, Claude Code, local Qwen, or modeling tools for review, but do not require them; do not use generative geometry as surveyed lunar terrain.

RESEARCH DATA AND RULES:
- NASA PGDA product 78 provides site-specific LOLA 5m LDEMs, height-error layers, and terrain clones; product 90 provides regional south-pole DEM coverage; product 104 may improve local relief when justified. Preserve file identifier, citation, license/attribution, georeference, vertical datum, selected coordinates, timestamps and checksums.
- JPL Horizons API provides lunar surface observer Sun/Earth ephemerides. Verify observer location conventions, azimuth orientation and timestamp scale. Record exact queries and raw responses. Check 0° azimuth = north, 90° = east after *explicitly validated* coordinate conversion, not by assumption. Avoid Earth/WGS84 defaults for the Moon.
- For the numerical horizon: use DEM elevations, observer height, and lunar curvature/3D Moon-centered geometry over an explicitly bounded range. Compute horizontal azimuth-to-horizon profile, first intersections, visibility fractions, longest uninterrupted darkness/Earth occultation, overlap intervals and event margins. Sample adaptively near threshold crossings; never report minute precision from hourly samples without refinement.
- Use exact reference sites only after verifying source coordinates; historical NASA PGDA reference points are NOT asserted current Artemis touchdown choices.
- Any missing/bad NASA data, contradictory reference frames, nodata, coverage gaps, failed JPL query, or unvalidated conversion MUST produce a visible error or 'unvalidated/unavailable' state. Never silently replace scientific data with synthetic terrain or approximate sky and still display a NASA/JPL badge.
- Demo-mode assets and values must say DEMONSTRATION / SYNTHETIC / NOT NASA. Use a persistent source provenance panel and status tags across every screen.
- Do not make flight-ready, certified safety, success-probability, DSN-contact, or NASA-endorsement claims.

IMPLEMENTATION PHASES:
A. Audit repo, dependencies, existing bugs, and Mac Blender/WebGL tools. Produce docs/ARCHITECTURE.md, docs/BUILD_STATUS.md, test baseline, acceptance checklist and a runnable plan.
B. Get and verify a real NASA DEM crop + JPL Sun/Earth tables for one south-pole site, then the second. Save provenance; prove coordinate mapping with explicit tests.
C. Build tested terrain horizon and timeline solver with flat-horizon comparison, crossing events, first hit, uncertainty scenarios, mission constraint evaluation and explainable repair.
D. Build/edit actual .blend scene from the SAME science bundle and timestamp: real DEM geometry, reference camera, line-of-sight objects, animated Sun/Earth directions, dark/sunlit terrain, named collections, GLB export, preview images and an export manifest. Verify start/mid/end frames.
E. Build React/TypeScript/Cesium Moon viewer with clock, selector, horizon graphs, scene/cross-section inspector, data-source inspector and stress-testing controls. Support fallback without Cesium credentials; preserve existing demo.
F. Integrate everything end-to-end with one canonical JSON schema, cache precomputed outputs for reliable offline demos, add tests and performance benchmarks, and produce a single Mac launch command.
G. Polish visual hierarchy, scientific interpretability, accessibility and demo/presentation material after the evidence pipeline passes.

QUALITY GATES (MANDATORY):
1) Existing npm and Python tests still pass; add tests for projection round-trip, longitude sign, pixel row direction/nodata, azimuth bearings, horizon wraparound, synthetic ridge, terrain clipping, lunar curvature, observer-height monotonicity, UTC coverage, interpolation across 359°→0°, event-crossing precision, 5D scenarios, cross-language agreement and data export provenance.
2) A real dataset and verified JPL record reach the dashboard and Blender for the same site/time with matching rays and calculated visibility status. If impossible due to data/network, report blocker and keep an honest demo instead of inventing measurements.
3) Scrubbing time changes all connected views; changing a scenario recomputes expected outputs and preserves immutable source input.
4) At least one failure can be traced to an actual elevation sample, named obstacle bearing, timestamp and numerical margin; one valid intervention is recomputed.
5) Browser UI tested with Playwright or comparable browser automation; Blender .blend opens and renders at start/mid/end; GLB loads; no console errors. Don't claim GPU testing if unavailable.
6) The app stays responsive, keyboard-operable, and accessible (WCAG 2.2 AA target) without marketing claims unsupported by measurements.

WORKING METHOD:
- Do not stop at analysis, plans, generated pseudocode, or disconnected prototypes. Implement and run tests as you proceed. First fix factual/scientific correctness, then visuals, then optional extras.
- Keep docs/BUILD_STATUS.md updated with completed gates, code paths, commands, tests executed, evidence paths, blockers and exact next tasks. Keep one stable run command and preserve testable intermediate states.
- Make reasonable engineering decisions autonomously when requirements are clear. If external credentials or NASA data cannot be fetched, complete all offline tests, demo path and integration seams. Explicitly report what is not verified.
- No extra live backends, collaborators, paid services, or GitHub push are needed now. Do not claim to have used other AI tools without actual access.

SUCCESS: I can open POLARIS X on my Mac, navigate detailed lunar terrain, choose a documented polar site and mission date, scrub UTC time, watch correctly synchronized Sun/Earth geometric visibility, inspect the exact blocking ridge, toggle a fifth-axis perturbation, see updated requirements and a genuine recalculated repair, and audit data lineage. I also receive an editable Blender scene, GLB, tests, exported reports, and explicit uncertainty and limitation statements.

START NOW: Read the repo, run baseline tests, identify the highest-priority real blocker, then implement the entire product in the phases above. Report what ran and what remains uncertain, not mere intentions. Follow local system permissions for all operations.
```

---

## PROMPT 2 — Forensic audit, migration and production architecture

```text
Continue POLARIS X from its current files, not from an empty template. Inspect AGENTS.md, root README, app/ source/tests/scripts, Blender scripts and the existing report outputs. Run `python3 -m unittest discover -s blender -p 'test_*.py' -v` and `cd app && npm test`, report actual exit codes. Check whether Blender CLI, Apple Silicon GPU/WebGL2, Node/npm, Python, pyproj/rasterio and a browser automation tool are available. Do not reinstall working tools just because they are present in a generic setup guide.

Identify confirmed bugs and architectural risks: the app is plain JS with a Python static server; source-mode JPL/DEM frame alignment is unvalidated; browser WebGL path needs live testing; 80m finite raster crop may miss distant ridge shadows; some terrain sources are synthetic. Search for numerical inconsistency between Python and JS, especially azimuth wrap, row orientation, projection, lunar curvature, observer height, scenario normalization and missing-sample fallback.

Implement a non-destructive path to a typed React/Vite UI while keeping legacy demo and tests runnable. Create docs/ARCHITECTURE.md, docs/SCIENTIFIC_CONTRACT.md (versioned input/output JSON), docs/DATA_PROVENANCE.md, docs/BUILD_STATUS.md and a precise feature acceptance checklist. Set up appropriate tests, lint/typechecks and dev launch commands. Avoid premature dependencies and no private tokens in frontend source or logs.

Deliver real code and passing tests for the architectural foundation, not just a migration plan. Do not delete the existing functioning interface until feature parity is demonstrated. Document the exact command to proceed.
```

---

## PROMPT 3 — Real NASA DEM + JPL Horizons ingestion and validation

```text
Implement the scientifically defensible NASA/JPL input pipeline for POLARIS X. Start with Connecting Ridge (NASA PGDA Site01), then Shackleton Rim (Site04) after Site01 passes tests. The scientific source of truth is public NASA PGDA LDEM GeoTIFF / metadata and JPL Horizons observer ephemerides; this is NOT Cesium screen terrain nor AI-generated regolith.

Inspect and refactor `app/scripts/prepare_science.py`, the raster coordinate transform and its Horizons CSV parser; don't assume it already works correctly. Use NASA PGDA product 78 for 5m site-specific data/error/clones when practical and product 90 80m regional data for distant horizon terrain. Save/download small cached crops, not an entire multi-GB DEM by default. If data requires user download, print precise source URLs and expected filenames and implement local import and validation; never insert invented heights to satisfy the pipeline.

Validate and record the Moon-specific horizontal and vertical reference systems, coordinate units and longitude sign. NASA PGDA 5m rasters use south-polar stereographic projected meters, MOON_ME / DE421 as documented; verify applicability to each chosen source. Use source metadata and rigorously tested lunar coordinate transformations, NOT an unverified Earth/WGS84 CRS default. Check at least one known site geolocation both ways and one known raster pixel, pixel-center offsets, north/south orientation, nodata coverage and observer elevation convention.

For JPL Horizons, use the official API and saved raw query/response, lunar observer site coordinates and explicitly chosen `TIME_TYPE` and apparent angular quantities. Verify exact query options and returned column structure against official docs; avoid brittle regex parsing that assumes exactly two numbers without checking the header, flags and CSV layout. Query Sun (10) and Earth (399) for identical UTC mission intervals, parse time/az/el, reject gaps and out-of-range requests, align samples and verify against a known independent Horizons case. Validate local ENU azimuth (north=0°, east=90°) and handling of near-polar coordinate basis. Match source frame conventions before claiming computed visibility.

Output a documented canonical `science-bundle-v2` (or compatible additive schema) containing site coordinates, DEM array/cell resolution/mask, frame/datum, valid coverage radius, Sun and Earth ephemeris with UTC, data hashes, raw query metadata, source publication URLs, preprocessing version and validation status. Add a command for building cache files, offline reuse and a machine-readable validation report. Run synthetic coordinate/bearing tests, then at least one true source input end-to-end. If reference alignment is unresolved, show 'SOURCE-BASED BUT UNVALIDATED' and a meaningful specific failure rather than green-checking it.
```

---

## PROMPT 4 — Full 4D visibility and 5D mission-resilience physics

```text
Implement the core POLARIS X numerical science module, independent of UI and Blender. Its inputs are a validated source-bundle DEM, observer ENU point/height, timestamped JPL Sun/Earth directions, and named scenario configuration. Outputs must be deterministic and reproducible, with complete units and source provenance.

Compute a 360° or higher-resolution local skyline by azimuth from DEM radial samples; include a documented lunar-curvature/3D vector correction, adaptive spatial sampling, strict nodata/coverage behavior and critical blocking terrain cell IDs. For each JPL sample, determine Sun-center and Earth-center geometric visibility, target-minus-horizon angular margin, first obstruction point/distance, both-visible interval and critical crossing times. Handle azimuth wraparound, UTC leaps/timezones, interpolated angles on a circle, near-grazing events, and avoid reporting unearned event precision. Explicitly test center-only visibility vs optional solar/terrestrial disk approximations.

Compute Sun-visible time/fraction, Earth-center visible time/fraction, overlapping time, longest continuous shadow, longest Earth obstruction, longest joint window and constraint margins. Compare each with the flat ideal horizon baseline. Add a transparent engineering scenario with Sun direction, panel normal/incidence, assumed generation, battery Wh, constant/scheduled loads, charge/discharge efficiency and reserve thresholds; make clear it is NOT a validated flight power system. Antenna-height changes recalculate Earth line-of-sight, not magically improve panel sunlight.

Implement fifth-axis scenarios: (1) NASA PGDA error/clone rasters with recorded subset and ensemble spread, when present; (2) reproducible 3x3 or 5x5 observer-position offsets; (3) ±12/24h arrival shifts; (4) observer height 1m/5m; (5) DEM resolution/horizon reach; (6) requirements thresholds. Distinguish measured uncertainty, deterministic stress grids, and assumptions. Fractions of selected cases are NOT mission-success probabilities. Compare nominal versus conservative feasible decisions, binding requirement, ranking stability, optional Pareto frontier and regret only with defined compatible units.

Implement one real counterfactual recovery: select a failed constraint and recompute feasible changes in site, time or observer height (and battery capacity only when modeling battery reserve) while maintaining cause/effect. Report 'no feasible repair within search range' if appropriate. Implement a credible uncertainty-hotspot prototype by tracing skyline-forming DEM cells; call it a sensitivity map, not formal Bayesian value of information.

Create unit tests for a flat surface, one ridge at a known bearing, height monotonicity, Moon curvature, azimuth bins, first-hit logic, time/circular interpolation, scene/time synchronization, window edge detection, source coverage, clone spread, 5D scenario behavior and recovery-specific metric changes. Cross-check at least one complete result against a separately implemented reference or saved NASA/JPL observation. Export results as versioned JSON + optional CSV with run seed/assumptions/hash/time window.
```

---

## PROMPT 5 — Blender 5.x lunar digital twin: real geometry, animation, export

```text
Build the highest-quality EDITABLE Blender component of POLARIS X from the canonical verified science bundle. You are responsible for an actual .blend scene plus exportable GLB, not screenshots or a generated image. Use existing `blender/build_lunar_science_scene.py` and geometry helpers as a starting point. Prefer pure bpy with Blender 4.5+/5.x compatibility. Run via the installed Blender executable on this Mac, discovered rather than hardcoded if its path differs.

Create logical collections: NASA_DEM_TERRAIN, GLOBAL_CONTEXT, LANDING_SITE_MARKERS, OBSERVER_AND_MAST, SUN_GEOMETRY, EARTH_GEOMETRY, RAYS_AND_OBSTRUCTIONS, HORIZON_WHEEL, 5D_SCENARIOS, SCIENTIFIC_LABELS, CAMERAS, LIGHTS, METADATA. Local scientific mesh is in meters in a consistent east/north/up frame; make mesh scale, origin, datum and source raster explicit in object custom properties. Preserve geometry in detail where it affects the visible scientific silhouette, but supply a lower-poly LOD for real-time GLB. Do NOT apply arbitrary vertical exaggeration to the actual solver mesh; any visual exaggeration must be an independently labeled toggle and the scientific ray must still use the unexaggerated mesh.

Produce a coherent NASA-style visual: plausible gray regolith with subtle roughness/noise and crater relief, low-angle hard solar shading derived from the science direction, restrained outlines/markers, an observer mast, unobtrusive terrain elevation tint, blocking ridge highlights, Sun/Earth directional gizmos and skyline plot. Use procedural materials and modest render costs. No fake atmosphere, invented water/ice, random science percentages or made-up crater coordinates. The global visual Moon can come from Cesium in the browser; Blender's local terrain is the scientifically referenced closeup. Optional AI-designed decorative equipment must be labeled visual-only.

Animation: key the solar light and direction gizmo from actual imported JPL samples over a user-chosen 14-day mission window; Earth reference line simultaneously updates. At each sample align the visible ray with the selected site; shorten the line at the first computed obstruction and highlight the obstructing ridge/cell. Sunset/sunrise shading and 5D stress markers must correspond to the canonical scenario/timestamp data. If runtime keyframes are interpolated between samples, document the interpolation and do not imply finer astrophysical fidelity. Make camera presets: overhead, 3/4 orbital, observer horizon, obstruction closeup, extreme ridge closeup. Add named controls in scene custom properties, not fragile object names only.

Provide scripts to build, inspect, render three sample frames, save `.blend`, export `.glb` using glTF-compatible material channels, save thumbnails and write a `scene_manifest.json` containing source DEM/ephemeris IDs, frame-to-UTC mapping, local coordinate origin, units, asset hash, validation status, and Blender version. Test the imported GLB orientation/size and camera framing; verify visual rays match numerical visibility at start, midpoint and end. If Blender is missing, give install verification steps and keep the runnable scripts complete without claiming an executed render. Synthetic demo mode must remain separately labeled and executable.
```

---

## PROMPT 6 — React/TypeScript + Cesium Moon interactive 5D mission control

```text
Build the polished browser application that uses the same canonical science bundle as Blender. First inspect and preserve the working legacy app; move incrementally to React + TypeScript + Vite with typed components and tests, not a blind rewrite. Make the scientific data/scene/time state a single source of truth.

Use CesiumJS for global lunar navigation with Cesium Moon (ion asset 2684829), applying `Cesium.Ellipsoid.default = Cesium.Ellipsoid.MOON` before constructing the viewer; disable inappropriate terrestrial globe imagery/geocoder and choose lunar-compatible view settings per official Cesium Moon sample. Cesium ion access token must be supplied at runtime from a local environment or in-session input; never hardcode/publish it. Catch 401/network/tileset errors and retain a clearly labeled local NASA-derived Blender GLB/DEM visual fallback. Make world-to-local ENU mapping to the Blender GLB explicit and tested; do not imply Cesium rendered polygons and NASA 5m numerical DEM pixels are identical.

Interface: (A) left navigation with site list, optional location coordinates and source mode, (B) center navigable lunar globe/local terrain with orbit/zoom/pan/horizon camera, legend and ray overlays, (C) right scientific inspector with point/timestamp coordinates, Sun/Earth azimuth/elevation, terrain skyline angle, blocking ridge cross-section, NASA source and confidence/coverage, (D) bottom synchronized time scrubber + 4D visibility strips, (E) 5D uncertainty/scenario controls and robust site comparison. Include both individual site mode and side-by-side site A/B time-matched comparisons.

Make the signature live experiment: select Connecting Ridge vs Shackleton Rim -> choose identical mission window -> scrub time -> click an actual obstruction -> draw the corresponding terrain azimuth cross section and source cell -> toggle a labeled NASA DEM clone or landing-position offset -> recalculate sunlight/Earth visibility and mission constraints -> show whether the selected plan remains feasible -> try one recomputed repair -> open an auditable source/provenance report. Never replace missing science outputs with random charts.

Aesthetics: premium NASA-style mission control with careful hierarchy, spacious typography, subtle color: sunlight amber, Earth cyan, uncertainty violet and failure red. Render text legibly, keep terrain as hero, avoid clutter and giant empty cards. Add responsive behavior and graceful WebGL failure, reduced motion, keyboard access, visible focus, ARIA labels, semantic tables, screen-reader timeline description, skip link, Escape key behavior, and meaningful accessible status updates. Avoid layout thrash and unnecessary re-render of Cesium every React state change.

Support a `DEMO` mode requiring no token or network, a `SOURCE-BASED UNVALIDATED` mode and a `VALIDATED NASA/JPL` mode only when verification gates truly pass. Provide a visible source badge with exact supporting metadata, cache a deterministic offline scenario, implement JSON/CSV report export and a 90-second demo preset. Add Playwright (or equivalent) checks for site choice, seek/play, cross-section, scenario toggle, error states, keyboard behavior, source badges and screenshots. Profile actual frame rate on the Mac's GPU rather than promising 60fps without measurement.
```

---

## PROMPT 7 — Tight integration, performance, scientific audit, accessibility

```text
Now connect all completed POLARIS X components into ONE RUNNABLE PRODUCT. Do not add new unrelated features. From a clean checkout/extracted folder, the documented run command should start the local UI, load a deterministic cached science case, permit importing a real NASA/JPL bundle, and open the corresponding Blender scene. Keep Node and Blender commands reproducible and do not require a paid service for local basic operation.

Enforce one versioned data contract across Python bundle preparation, TypeScript science engine, Blender scene manifest and React UI. Build schema validators/migration adapters for legacy `POLARIS-X5D-v1`. For every displayed timestamp, test that the sky angles, horizon height, visible/blocked result, ray length and overlay colors agree across browser, JSON report and Blender. A full science-mode scenario must reject missing georeference, insufficient DEM coverage, nonfinite values, source-time mismatch, and out-of-domain user controls explicitly.

Measure/optimize: terrain cropped windows/multi-scale skyline cache, GLB LOD and streaming, cached JPL timestamps, worker-side perturbation analysis, request cancellation, timeline seeking latency, memory footprint, render time, scene load time and CPU/GPU usage on Apple Silicon. Focus on responsive interaction before effects; expose low/medium/high visual quality modes without changing the numerical result.

Run: full JS/TS tests; Python tests; source validation cases; Blender background build and still renders at three frames; GLB load and orientation test; browser end-to-end automation, screenshot review and console log scan; accessibility checks for WCAG 2.2 AA; responsive checks at laptop and phone widths; offline test and invalid Cesium token fallback. Report PASS/FAIL/NOT-RUN with actual evidence and do not infer success from source inspection alone.

Write an accurate README with all commands, installed versions, required environment variables, data links, GPU/browser requirements, license/attributions, AI-use disclosures, validation limitations and troubleshooting. Include docs/SCIENCE_VALIDATION_REPORT.md and docs/BUILD_STATUS.md. Make final outputs: runnable app, editable .blend, .glb, cached demonstration science outputs, screenshots, machine-readable method/report and tests. Only claim NASA-validated status after independent comparison genuinely passes.
```

---

## PROMPT 8 — Major visual refinement without compromising science

```text
POLARIS X is functional; elevate its visual and interaction quality dramatically while keeping numerical outputs bit-for-bit consistent for identical inputs. Act as a high-end scientific visualization director and senior UX engineer.

Review screen recordings and screenshots in actual browser render mode, not just HTML and CSS. Audit the camera defaults, crater/ridge silhouette, lit-vs-dark terrain, antialiasing, terrain normal orientation, regolith material variation, label occlusion, legend clarity, framerate, contrast, hero scene size, panel density, docking and tooltip behavior. Prioritize the three judge-facing interactions: (1) global Moon zoom to a named real south-pole location, (2) time scrub through a shadow/horizon crossing with the target and obstruction highlighted, (3) uncertainty toggle with live side-by-side scientific decision comparison.

Upgrade Blender material/rim/LOD/multiresolution terrain and scene cameras, but preserve sampled DEM heights, ENU geometry and directional ephemeris as the scientific truth. Add purposeful motion, camera interpolation, interactive cross-section pick and snapshot/export controls, but never use cinematic material shadows as a substitute for the tested visibility solver. Treat AI/Tripo-generated objects only as non-scientific visual props, and do not use paid APIs without approval.

Use a clearly labeled graphic language: real calculations solid strokes, uncertain interval bands translucent, missing coverage hatched, illustrative graphics dotted. Export an attractive but truthful 90-second demo capture preset and a clean seven-slide screenshot set if allowed under verified current NASA Space Apps submission rules. All demo captions must match actual results. Rerun regression tests and browser screenshot comparison after every visual refactor.
```

---

## PROMPT 9 — Final independent review, fixes, and honest completion report

```text
Act as an independent adversarial reviewer of the completed POLARIS X repo. Do not trust your earlier descriptions. Inspect code, actual generated outputs, data files, render previews, UI screenshots, saved API queries, tests and environment. Find numerical mistakes, invalid NASA source claims, frame/coordinate mismatches, synthetic fallbacks hidden in real mode, Cesium token leaks, race conditions on time scrubs, visual/physics mismatches, accessibility failures, performance bottlenecks and broken packaging. If you can fix a problem within the project, implement the fix and add a regression test.

Test at least: signed east/west longitude; Moon-specific polar stereographic projection; correct pixel row order and source datum; JPL UTC and output column interpretation; az=0 north/90 east; 359->0 angular interpolation; inverse terrain ray; curvature sign; observer-height monotonicity; Sun-center vs visible disk labeling; night shadows; fixed reference site coordinates; finite DEM reach; true offline coverage; 9-scenario counts and robust ranking; changing a battery affects only modeled reserve, not geometric sunrise; raising antenna affects only applicable Earth LOS; same timestamp across Blender, chart, 3D markers and source report.

Produce a final `docs/FINAL_AUDIT.md` with a table of feature / implementation status / evidence / known limitation. Use only four statuses: VERIFIED WORKING, WORKING BUT UNVALIDATED, DEMO ONLY, and BLOCKED. Provide exact commands and output paths for running locally on my Mac. Do not say 'fully NASA accurate' or 'ready for flight' if the ephemeris/frame/illumination checks are incomplete. Do not claim any unrun test passed. Report the three highest-priority remaining tasks and stop only after packaging the best functioning deliverable available.
```

---

## Useful official documentation (hand Codex these URLs)

- NASA Space Apps challenge: https://www.spaceappschallenge.org/2026/challenges/lunar-landing-site-navigator/
- NASA PGDA 5m LOLA / DEM clones: https://pgda.gsfc.nasa.gov/products/78
- NASA PGDA 80m/20m regional topography: https://pgda.gsfc.nasa.gov/products/90
- NASA PGDA enhanced local south-pole DEM: https://pgda.gsfc.nasa.gov/products/104
- JPL Horizons API: https://ssd-api.jpl.nasa.gov/doc/horizons.html
- JPL Horizons manual: https://ssd.jpl.nasa.gov/horizons/manual.html
- Cesium Moon official code and coverage: https://cesium.com/platform/cesium-ion/content/cesium-moon/
- Cesium Moon Sandcastle example: https://sandcastle.cesium.com/?id=moon
- NASA SVS 2025–2028 polar illumination: https://svs.gsfc.nasa.gov/5027/
- NASA SVS Moon web 3D assets: https://svs.gsfc.nasa.gov/14959/
- NASA PGDA projects may have data limitations and require downloads; don't invent a source file URL.

## If Codex stops midway, paste this continuation prompt

```text
Continue the existing POLARIS X implementation from `docs/BUILD_STATUS.md`. Inspect all changes and rerun relevant tests. Do not start from scratch and do not repeat completed steps. Finish the earliest incomplete scientifically required gate, then continue through the remaining phases, keeping tests green and documenting blockers. Make actual code changes, build runnable artifacts, and show verification evidence. If a paid API, missing token, external account or remote file blocks only one feature, implement and test its offline adapter and continue with the other work. Never substitute synthetic results for unavailable verified NASA/JPL data. Do not change unrelated files or push anything without approval.
```

## Mac commands

```bash
cd ~/Downloads/POLARIS-X5D-Blender-Codex
python3 -m unittest discover -s blender -p 'test_*.py' -v
cd app && npm test && cd ..
bash run_blender.command --demo
cd app && bash run.command
# Codex CLI, only if installed:
cd ~/Downloads/POLARIS-X5D-Blender-Codex && codex
```

**Competition compliance reminder:** NASA Space Apps 2026 states the project submission window opens Nov 14 at 9:00 AM local time and closes Nov 15 at 11:59 PM. Observe official team implementation/eligibility and AI-disclosure instructions, and do not describe pre-event work as newly created during the official event if that is inaccurate.
