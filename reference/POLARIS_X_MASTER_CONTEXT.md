# POLARIS X — Master Project Context for Claude Max and Claude Code

> **Read before giving recommendations or editing code.** This document is an onboarding summary grounded in two research/planning PDFs, the existing source archive, and the implementation instructions. It separates aspirations from verified functionality. It is not a NASA data product or a substitute for inspecting current local code.

## 1. Identity and purpose

**Project name:** POLARIS X (earlier concept: POLARIS — Lunar Landing Intelligence System).  
**Context:** NASA International Space Apps Challenge 2026, **Lunar Landing Site Navigator**.  
**Primary research concept:** a **lunar mission-resilience digital twin** that answers more than “where is sunlight?” It lets users investigate **which lunar surface location, mission start time and engineering assumptions remain workable when terrain and scheduling uncertainties change**, shows **which ridge or crater edge caused a visibility failure**, and explores **what small change could restore feasibility**.

**One-sentence pitch:** “POLARIS X turns NASA lunar maps and sky geometry into an explainable resilience test: it shows which site and date work, when they stop working under uncertainty, and which mission change could restore feasibility.”

**What this is:** A research and educational decision-support tool with interactive 3D lunar terrain, time-dependent geometry, scientifically auditable results, and 5D perturbation analysis. **It is not flight-certified software, an Artemis landing recommendation, a NASA endorsement, or a full spacecraft power / radio link system.**

**The distinctive contribution:** Ordinary lunar 3D globes, sun/shadow visualizations, site ranks, and simple date searches already exist. POLARIS X should demonstrate evidence-based **decision robustness** and, if time allows, **where improving terrain measurements would change a borderline decision** (sensitivity / approximate value of information). Never market an unimplemented proposed idea as a discovered scientific result.

## 2. Precisely what “5D” means

1. **East** (local ENU X; physical spatial coordinate, metres).
2. **North** (local ENU Y; physical spatial coordinate, metres).
3. **Up/elevation** (local ENU Z; metres, referenced to a documented lunar vertical datum).
4. **Time** (UTC astronomical / mission instant, exact selected date and range).
5. **Scenario / uncertainty axis** (select one NASA DEM error clone where available, nearby observer position, observer/antenna height, mission arrival slip, DEM resolution/horizon reach, and/or declared constraints).

The fifth dimension is a **discrete or sampled scenario space**, not a fifth physical dimension and not automatically a calibrated probability of mission success.

## 3. Main user experience / core demo

The user should be able to:

1. Open a high-quality global 3D Moon, zoom from globe to a south-pole region, and pick a documented candidate reference location.
2. Select a UTC start date and mission length (initial demonstration can use **14 Earth days**). Display source coordinates, dataset resolution and reference frame.
3. Scrub, seek, play or reverse a **single synchronized clock**. Show physically sourced Sun and Earth azimuth/elevation and terrain-relative sky paths. Camera lighting may be artistic, but all scientific rays and labels must follow validated input geometry.
4. See the local terrain horizon, times when the **Sun center** and **Earth center** are above it, simultaneous access intervals, longest modeled darkness and Earth blockage, and constraint margins.
5. Click a visibility failure to reveal the actual first blocking terrain sample, azimuth, elevation, time, distance, and 3D cross-section.
6. Compare the same mission window between **Connecting Ridge (Site01)** and **Shackleton Rim (Site04)**, later **Peak Near Shackleton (Site07)** and **de Gerlache Rim (Site11)** if data permits.
7. Switch the fifth-axis scenario (e.g., nearby observer offset, NASA published DEM clone) and watch computed results and feasibility rankings change or remain stable. Showing stability is a valid result; do not manufacture a rank reversal.
8. Try a legitimate repair: shift a mission date, move to a nearby location, raise the relevant observer/antenna height, change energy reserve for an explicitly modeled power scenario, or reduce duration. Recompute only physically affected quantities.
9. Open a source/provenance panel and export reproducible JSON/CSV describing inputs, source files, date range, assumptions, limitations, software versions and results.

**Visual principle:** NASA-inspired mission control, cinematic but credible lunar terrain as the hero, accessible charts and labels, low-angle lighting, sparse restrained amber/cyan/violet/red visual semantics, responsive performance. **Science first, then polish.** Do not turn this into a rotating gray sphere with decorative panels or an attractive dashboard with invented metrics.

## 4. Research PDFs — status and priority

**PRIMARY — `POLARIS_X_Expanded_Lunar_Mission_Blueprint.pdf` (28 pages; 12 Nov 2026).**
- Executive / mission vision: pp. 1–2.
- Prior work, scientific differentiation and research hypothesis: pp. 3, 6.
- Modules and live judge demo: pp. 4–5.
- NASA datasets, sites and frame cautions: pp. 7–9.
- Local horizon and Sun/Earth visibility equations: p. 10.
- Mission windows, constraints, uncertainty clones and perturbation tests: pp. 11–13.
- Robust optimization and regret: p. 14.
- Data-sensitivity / value-of-information concept: p. 15.
- Failure diagnosis and intervention semantics: p. 16.
- Simplified power vs communications caveats: p. 17.
- Scientific tests, code architecture, performance and priorities: pp. 19–22.
- Team split, execution timeline, presentation and risk register: pp. 23–26.
- Post-hackathon roadmap and sources: pp. 27–28.

**SECONDARY — `POLARIS_Lunar_Landing_Intelligence_Full_Breakdown.pdf` (14 pages; Nov 2026).**
- Initial idea and challenge alignment: pp. 1–3.
- Four intended app views and data-source roles: pp. 4–5.
- Terrain skyline mathematics and target visibility: pp. 6–7.
- Software stack and explicit test criteria: pp. 8–9.
- User experience and scoped feature priorities: pp. 10–11.
- Event build plan / roles / deliverables: pp. 12–14.

These two documents are planning/research references, not completed POLARIS scientific analyses. The expanded 28-page blueprint is the desired direction when the original 14-page proposal is less ambitious; the original's equations and dataset context still matter. Treat numerical examples or illustrations labeled hypothetical as such.

## 5. Core verified/public scientific input sources to use

**Official challenge:** https://www.spaceappschallenge.org/2026/challenges/lunar-landing-site-navigator/  
**NASA PGDA product 78:** https://pgda.gsfc.nasa.gov/products/78 — site-specific LOLA 5m lunar elevation, error products, and alternate DEM realizations/clones for selected polar study sites. Check exact files, datums and uncertainty meaning.  
**NASA PGDA product 90:** https://pgda.gsfc.nasa.gov/products/90 — regional south-pole topography products at coarser resolution, including cloud-optimized raster variants; important for **distant obstructions** beyond the local 5m crop.  
**NASA PGDA product 104:** https://pgda.gsfc.nasa.gov/products/104 — enhanced local lunar south-pole topography; validate source processing/coverage before mixing it with LOLA.  
**JPL Horizons docs/API:** https://ssd-api.jpl.nasa.gov/doc/horizons.html and https://ssd.jpl.nasa.gov/horizons/manual.html — surface observer directions for Sun (target 10) and Earth (target 399), with site/azimuth/time conventions explicitly verified.  
**NASA polar illumination references:** https://svs.gsfc.nasa.gov/5027/ and https://svs.gsfc.nasa.gov/4930 — useful limited cross-checks when time and georeferencing match.  
**Cesium Moon terrain:** https://cesium.com/platform/cesium-ion/content/cesium-moon/ and https://sandcastle.cesium.com/?id=moon — visual/global terrain infrastructure (suggested Cesium ion asset ID 2684829, subject to availability and current terms), NOT automatically the numerical science DEM.  
**NASA Moon visual assets:** https://svs.gsfc.nasa.gov/14959/ — web-friendly Moon models for context, NOT high-resolution measurement geometry.  
**NASA Moon Trek:** https://trek.nasa.gov/moon/ — map and comparison precedent.

**Do not use** `NASA-3d-model.txt` as a source of lunar DEM; that earlier link was to a Roman Space Telescope scene. Do not conflate a NASA-inspired render with source data.

## 6. Candidate polar locations

The original concept PDF cites historical NASA research-region reference positions (verify coordinates against the original source and dataset before computing):

| Study point | Latitude (deg) | Longitude (deg) | Role |
|---|---:|---:|---|
| Site01 — Connecting Ridge | -89.4632 | -137.4900 | Initial primary test site |
| Site04 — Shackleton Rim | -89.7668 | -171.8700 | Initial comparison |
| Site07 — Peak Near Shackleton | -88.8110 | +123.6901 | Later extension |
| Site11 — de Gerlache Rim | -88.6834 | -67.9321 | Later extension |

These are **study references**, not asserted 2026 officially selected Artemis III touchdown locations. Negative longitude vs 0–360 sign conventions require explicit checking.

## 7. Scientific non-negotiables

**Coordinate rigor:** Do not use Earth/WGS84 defaults for lunar terrain. Check the exact projected lunar polar stereographic CRS, its radius/reference frame (e.g., MOON_ME/DE421 where documented), pixel centers, row direction, horizontal/vertical units, longitude sign and JPL lunar observer height convention. Prove lat/lon ↔ raster XY roundtrip with a known landmark and recorded tolerance. ENU bearings must be explicitly verified: local north 0°, east 90°, mindful of near-polar orientation.

**Terrain horizon:** For each azimuth, compute the highest apparent angle of sampled lunar surface along the ray, accounting for observer height, finite raster coverage and lunar curvature / Moon-centered 3D geometry at relevant ranges. Record the ray extent and samples responsible for the skyline. Do not silently assume a flat horizon or complete line-of-sight when DEM coverage is missing.

A basic decision at time t (Sun or Earth center) compares its apparent elevation with the sampled terrain skyline at its azimuth. Near crossings, numerical tolerance and finer time sampling matter. A point-Sun center test is not equivalent to visible solar-disk fraction. Earth-center above terrain is not proof of antenna pointing, link budget or scheduled DSN availability.

**Timeline metrics:** Sun fraction; Earth-center fraction; joint visibility fraction; longest uninterrupted darkness; longest Earth-blocked interval; joint continuous windows; event timestamps with stated precision; angular clearance / margins; time/date range and cadence.

**Constraints:** Evaluate hard mission requirements independently (e.g. minimum solar-visibility fraction, maximum blackout duration, maximum darkness duration). Avoid a single opaque score that allows power to cancel a critical communications failure. When a repair changes one physical variable, recompute the correct effect and leave unrelated variables unchanged.

**Uncertainty:** Use NASA DEM error maps/clones where practical, or explicitly named deterministic position/time/height/resolution stress tests. The spread over selected clones or nine offsets **is NOT calibrated mission success probability**. Do not assume ensemble members are independent or that a clone percentile equals actual statistical confidence without source methodology.

**Advanced extension:** Trace the skyline-forming ridge/cells that drive a borderline decision and cross-reference elevation-error layers to produce a **decision-sensitivity hotspot**. Do not label a simple hotspot “formal Bayesian expected value of information” unless justified with a probabilistic prior and observation-error model.

**Provenance:** Site, time scale, sample step, elevation raster ID/crop, coordinate/datum reference, JPL query text and raw response/checksums, versions, scenario parameters, numerical tolerances, failure labels and output source badges must remain traceable.

## 8. Target full software architecture

**Local Mac target:** Apple Silicon MacBook Pro (user-described M5 Pro), arm64; observed tools Homebrew 6.0.19, Node 26.4.0, npm 11.17.0, Python 3.14.5, Apple Git 2.50.1. Blender 4.5+ or 5.x needed locally. Python 3.12/3.13 isolated venv may be easier for geospatial library wheel support; do not replace the global Python or alter unrelated setups.

**Front-end:** TypeScript + React + Vite, CesiumJS Moon globe, local Blender GLB/DEM option when no token or internet, timeline/horizon charts, science inspector, comparative mission view, accessible and responsive UI. Separate visual tileset from numerical elevation source. Maintain one UTC/scenario state across views.

**Data/science:** Python + NumPy/rasterio for NASA DEM preprocessing and horizon calculations or a carefully tested shared typed science library. JPL Horizons ingestion with saved raw inputs/outputs. A stable versioned `science-bundle` JSON contract bridges Python, Blender and browser. Precompute/cache cases and save provenance for an offline demo. Scientific uncertainties and numerical tests are first-class outputs.

**Blender:** editable `.blend` scene built from the same canonical science bundle, local DEM mesh with metres/ENU/datum, named collections, observer and mast, Sun/Earth direction controls and line-of-sight markers, keyed scene from verified time samples, illumination setup corresponding to science data, three-plus useful cameras, `.glb` export and `scene_manifest.json`. Artistic procedural regolith materials can be detailed, but cannot change actual DEM height used in calculations.

**Quality:** Python unit tests; JS/TS tests; independent geometry/ephemeris checks; accessibility; browser E2E (Playwright), WebGL2/Cesium error states; Blender background render and GLB verification; Apple Silicon performance checks; clear user-visible source state.

**Out of scope until the core works:** full DSN links, detailed thermal/hazard model, guaranteed lander battery/power predictions, autonomous route planning, generative-AI-based numeric physics, large feature proliferation. Claude/LLMs may code or explain valid results but must never invent sky angles or “source-verified” terrain.

## 9. Current project snapshot (NOT current Codex progress)

**Existing archive:** `POLARIS-X5D-Blender-Codex-Mac.zip` (from earlier iteration). Repository root `POLARIS-X5D-Blender-Codex` and the following major paths:

```
AGENTS.md
README.md
run_blender.command
app/
  index.html
  package.json
  run.command
  src/main.js
  src/science.js
  src/scene.js
  src/pro.js
  src/fallback.js
  src/styles.css
  scripts/prepare_science.py
  tests/science.test.js
  tests/pro-science.test.js
  assets/ILLUSTRATIVE_terrain_preview.glb
  blender/build_lunar_scene.py
  docs/TOOLCHAIN.md
blender/
  build_lunar_science_scene.py
  build_from_nasa_bundle.py
  polaris_geometry.py
  test_geometry.py
```

**Working in this archived snapshot:** plain-JavaScript static web app with WebGL2 local terrain and fallback, 4 demonstration site choices, timeline and approximate sky, scene rays and cross-section, 9 deterministic test scenarios, 3D and report export, optional Cesium integration path, Python source-prep script and Blender builder. These **demonstration outputs use synthetic terrain/approximate sky** until a source bundle is fetched and independently aligned/validated. The app is **not yet** production React/TypeScript, a validated global lunar terrain/ephemeris solver, or an end-to-end NASA-verified 5D digital twin.

**Tests re-run against the archival ZIP during handoff preparation:** `cd app && npm test` — **13/13 passed**; `python3 -m unittest discover -s blender -p 'test_*.py' -v` — **6/6 passed**. These are **unit-level synthetic/demo tests, not proof of NASA alignment**. No local GPU browser run, real Cesium token session, complete JPL reference cross-check or full NASA DEM audit was performed in this handoff.

**Hosted Blender preview from previous iteration:** `https://higgsfield.ai/3d-jutsu/393826d4-72b2-468b-8def-820509cccdc4` — editable **synthetic** terrain + scientific-looking controls. Its existence does **not** mean NASA source terrain and verified ephemeris were loaded. The source archive contains a Blender script, not necessarily the same `.blend` file as the hosted scene.

**Important concurrency/history:** A Codex execution task was initiated from the 9-phase instructions. Its **current completion state is unknown** in this document. Claude MUST inspect the live local repo and any `docs/BUILD_STATUS.md` and test artifacts before deciding what remains, and should NOT assert Codex succeeded, failed, or is still running without seeing evidence. When Codex and Claude may both write to the same folder, coordinate ownership or work in a separate directory/worktree with an explicit integration plan.

## 10. Nine-phase instruction pack (separate accompanying file)

`POLARIS_X_FULL_CODEX_PROMPTS.md` is an implementation specification, not a generated report. The phases are: master requirements; audit/migration; NASA/JPL ingestion and validation; time-dependent terrain/uncertainty physics; Blender DEM scene and animation; React/Cesium UI; integration/QA; cinematic/scientific UX polish; final adversarial audit.

Claude should use its complete requirements, but **critically inspect the actual code and source documentation rather than parroting the tasks**. If the source documents disagree, identify the disagreement and its consequence explicitly. Do not silently treat a proposed feature as completed.

## 11. What to prioritize next / phased definition of done

**P0 science truth:** A named verified NASA DEM crop for a single documented point, matching JPL Sun/Earth directions over a bounded UTC interval; validated CRS/frame, pixel indexing and source provenance. Produce an actual terrain-aware skyline and an independent test against a flat horizon or reference illumination. Fail visibly on missing coverage or frame contradiction.

**P0 shared model and visual:** One same-site/time scientific bundle drives a local Blender mesh, interactive browser terrain, Sun/Earth line of sight, failure marker and horizon chart. The visual should not contradict the numerical outcome. A deterministic offline cached validated case should continue working when remote sites fail.

**P1 decision experiment:** Compare two sites over identical times; compute robust constraints under a named 5D perturbation subset; diagnose one failed constraint and recompute a physically valid repair. Record source and uncertainty limitations.

**P1 delivery and reliability:** React/TypeScript/Cesium and fallback, browser and Blender tests, clear UI/source badges, accessible controls, local Mac launcher, versioned JSON/CSV export, performance evidence and complete instructions.

**P2 stretch:** NASA DEM clone ensemble, rank stability / fragility map, data-sensitivity hotspot, more science overlays, robust optimization / Pareto outputs, premium cinematics, careful comparison with prior work.

**Demo target:** 90 seconds: globe to documented location; site A vs B over one UTC interval; drag time and reveal genuine ridge blockage; switch one uncertainty scenario and observe the margin change; apply a recomputed repair; show provenance and validation. If only a smaller verified scope is possible, prefer it over an elaborate fake scene.

## 12. Rules for Claude Max / Claude Code

- When in **Claude chat/Projects**, you may analyze the uploaded files and produce precise code suggestions, but **do not claim to have edited, run or opened the user's Mac**.
- When in **Claude Code** with the actual local project open, run test baselines before changes; preserve existing files; make real commits or edits locally only according to user permissions; verify output; maintain `docs/BUILD_STATUS.md` and report accurate blockers. Do not push GitHub or incur paid API charges without explicit approval.
- Do not create a second disconnected lunar app in a new folder if the existing working app can be migrated. Do not destroy `AGENTS.md`, Blender builders, tests or cached scientific artifacts.
- All numeric sources must be real and reproducible, or conspicuously marked `DEMO / SYNTHETIC / UNVALIDATED`.
- Cite exact PDFs, pages, source URLs and actual code paths for important technical assertions. Keep ideas from source, your inferences and external research separately identified.
- Preserve scientific confidence labels and actual time/space ranges on exports, screenshots and any judge-facing demo.
- Follow current competition submission rules, verify eligibility/AI disclosures, and do not conceal the date or authorship of pre-event work.

## 13. Links worth sharing verbatim with Claude

- Official lunar challenge: https://www.spaceappschallenge.org/2026/challenges/lunar-landing-site-navigator/
- NASA PGDA source family: https://pgda.gsfc.nasa.gov/products/78 ; https://pgda.gsfc.nasa.gov/products/90 ; https://pgda.gsfc.nasa.gov/products/104
- JPL Horizons: https://ssd-api.jpl.nasa.gov/doc/horizons.html ; https://ssd.jpl.nasa.gov/horizons/manual.html
- NASA polar illumination reference: https://svs.gsfc.nasa.gov/5027/
- Cesium Moon: https://cesium.com/platform/cesium-ion/content/cesium-moon/
- Hosted synthetic Blender scene (for visual context only): https://higgsfield.ai/3d-jutsu/393826d4-72b2-468b-8def-820509cccdc4

**Final instruction to any AI:** Build a truthful, reproducible scientific tool that happens to be visually exceptional, not an exceptional visualization masquerading as scientific evidence.
