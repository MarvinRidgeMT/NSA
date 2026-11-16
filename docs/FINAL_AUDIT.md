# Final audit

Audit date: 14 November 2026

Release decision: **usable local research build; scientific output remains `SOURCE_BASED_UNVALIDATED`.**

## VERIFIED WORKING

| Feature | Evidence | Boundary |
|---|---|---|
| Source ingest and provenance | Four v2 bundles pass JSON Schema; recorded raw JPL hashes match retained responses; local PGDA 78 source hashes are recorded. | Confirms reproducibility and internal contract, not science truth. |
| Projection/raster/parser gates | 6 automated tests cover four site anchors/round trips, longitude sign, source row flip, header-driven parsing and declaration checks. | Internal checks are not an independent geodetic review. |
| Terrain obstruction engine | 21 Python geometry/Blender and 18 JavaScript tests pass, including exact curvature, local-to-grid azimuth rotation, rotated synthetic ridge, first-hit evidence, time bounds and scenarios. | Finite sampled terrain and point targets only. |
| Browser source workflow | Headless Chrome verifies visible local and global Three.js models in localhost and direct-file modes, loads two source sites, imports the full Site01 bundle, exposes six terrain choices, recomputes a clone, exercises mission/analysis drawers and reports no page/console errors. | Cesium live token flow was not part of this smoke test. |
| Global Moon model | Embedded NASA SVS 8K LRO color-plus-height GLB is visible offline at 2.02M vertices / 1.02M triangles; both topographic and compact fallback GLB lengths/hashes pass. | Global asset is orientation context, not the numerical elevation authority. |
| React/TypeScript bundle viewer | 26 passing unit tests, production TypeScript/Vite build, and 11 passing Chrome end-to-end tests. | Source bundles currently lack the optional derived margins/metrics block, so the viewer refuses to invent them. |
| PGDA 69 south-pole reference map | Eight pinned raw-source hashes, 17 ROI tests, generated-image checks, two inspected screenshots and keyboard zoom/layer E2E coverage. | 18.6-year surface/disc-edge averages are a different quantity from the POLARIS mission-window centre-visibility result; no direct validation claim. |
| Blender artifact pipeline | Blender 5.3 rebuilds demo/source scenes; source `.blend` reopens with 25 objects, five cameras and all required collections. | Presentation scene is not the numerical authority. |
| GLB and manifests | Both GLBs are valid version 2 containers; file lengths and manifest SHA-256 values match. | GLB materials/animation portability depends on viewer support. |
| Evidence renders | Start/middle/end PNGs exist for demo and source scenes and were visually inspected. | Attractive renders do not validate illumination. |

## WORKING BUT UNVALIDATED

| Feature | Evidence | Limitation |
|---|---|---|
| NASA/JPL Site01 and Site04 cases | Official PGDA raster inputs and raw Horizons response text are retained with source URLs and checksums. | No independent illumination truth-set comparison has been executed. |
| Source-based Sun/Earth visibility | JPL airless apparent target-centre angles are compared to local terrain skylines. | No angular disk, diffraction, radio link, power or thermal model. |
| 5D terrain realizations | Site01 nominal 5 m terrain, total-Z RMS evidence and four deterministic source clones are selectable. | The clones are not assigned probabilities; 5D is a scenario axis. |
| Four-site comparison | Two cards are source-backed and two are explicitly demo-labelled. | Site07/Site11 source inputs and Site04 high-resolution layers remain absent. |
| Regional/local horizon results | Regional reach is about 15.96 km; local reach is about 1.0 km. | Terrain outside each crop can alter the real horizon. |

## DEMO ONLY

| Feature | Scope |
|---|---|
| Peak Near Shackleton (Site07) and de Gerlache Rim (Site11) | Synthetic terrain and analytic illustrative sky until source datasets are generated. |
| `run_blender.command --demo` | Deliberately synthetic control geometry, clearly labelled in scene and metadata. |
| Stress-test feasibility labels | Deterministic threshold experiments, not mission success probabilities. |

## BLOCKED

| Requirement | Blocker |
|---|---|
| Claiming validated lunar illumination | Requires an independently selected, frozen, frame-compatible truth set and documented acceptance tolerances. |
| Global/certified horizon | Requires wider or global terrain, resolution studies and external validation beyond the supplied regional/local crops. |
| Flight, power, thermal or telecommunications certification | Requires subsystem models, requirements, authoritative operational data and expert review outside this prototype. |
| Derived real-site metrics in the React viewer | Requires a versioned `datasets[i].derived` science-bundle block; the viewer intentionally does not recompute or invent it. |

## Test record

- Baseline before edits: 6 Python geometry tests and 13 JavaScript tests passed.
- Final core suite: 21 geometry/Blender + 6 ingest + 18 JavaScript tests passed; Python compile, four bundle schemas, raw-response hashes and the NASA GLB hash passed.
- Browser: Chrome smoke passed with no captured errors in both localhost and direct `file://` launches; local and global canvases were checked as nonempty.
- React/TypeScript viewer: all 26 unit tests, the production build and all 11 Chrome end-to-end tests passed; `npm audit` reports zero known dependency vulnerabilities.
- Blender: demo and source rebuilds completed; generated files and collection structure passed checks.
- One initial final verifier run failed because the new verifier assumed manifest assets were a list while the builder emits a dictionary. The verifier was corrected to support the actual contract, then rerun successfully. This was a test-harness defect, not an artifact hash failure.

## Top three remaining issues

1. Independent illumination validation is the mandatory science gate.
2. Horizon reach/resolution uncertainty must be quantified with wider coverage and all four source sites.
3. Publish the additive derived-output bundle contract so the React viewer can display real-site margins without becoming a second numerical authority.

## State after the rebuild pass of 14 Nov 2026 (evening)

Status: **SOURCE_BASED_UNVALIDATED**. No independent illumination validation was performed.

- React viewer (`web/`): 5 m crop inside the 80 m regional crop, display-model shadows, registered LROC image on Site01,
  surface debug layers, global Moon. Unit tests 90/90; cloud Playwright passes (session A: 49/49 before Penumbra's last
  merge; Penumbra: 51 passed / 1 skipped after it). Not run on the Mac host: Playwright, GPU timing.
- Legacy viewer (`app/`): unchanged in function; solver guard against visual layers; `preserveDrawingBuffer` off. Tests 25/25.
  `browser_smoke.py` not re-run on the Mac.
- Blender: builder extended (regional context, hero command) and unit-tested (25/25) but **not run**; existing `.blend`,
  GLB and renders in `blender/output/` are the earlier builds.
- Interim archive: `dist/POLARIS-X5D-SourceBuild-Mac-20261114-2255.zip`, SHA-256
  `d4179023879c0bc9752dd1ead05065286051e9a84d171b70d263a4e23d76474e` (see `docs/BUILD_STATUS.md`).

Remaining risks, in order: (1) no independent validation; (2) Mac-host checks and the Blender rebuild not run after these
edits; (3) 3D shadows are a display model and can differ from the bundle's visible/blocked state away from the observer;
(4) two terrain levels only (5 m, 80 m); (5) the React viewer and `app/` are still two front ends.

### Update, 15 Nov 2026 00:05 EST
Final archive: `dist/POLARIS-X5D-SourceBuild-Mac.zip`, 275,232,626 bytes, SHA-256
`634551699b661ccf0bc49cf64c47408977d55da3c8b0951684e4102fe63c6f77` (supersedes the 22:55 interim archive). Since the section
above: `test_all.command` passed on the Mac, web Playwright 52/52 on the Mac, `browser_smoke.py` passed, and the Blender hero
scene (Site04 ROI3, 401² 5 m crop, derived ray states, 80 m display context) was built with Blender 5.3.0. Risks (1), (3), (4),
(5) above still stand; risk (2) is reduced to: GPU frame time not measured, no Blender transition frame or GLB re-import.


### Update, 15 Nov 2026 01:05 EST
The five open items from 00:05 were worked: StableLine removes the per-step shader relink (Mac pane p95 9.2 ms); Blender gains a
transition render and a GLB re-import check (needs a Mac rerun); `web/` has a 20 m middle terrain level; time, scenario, camera and
layer are in the URL; a pre-registered NASA SVS 4930 comparison passed its protocol but only on lit samples (low discriminating
power). Status stays **SOURCE_BASED_UNVALIDATED**. The release ZIP must be rebuilt after the Mac rerun. Details: BUILD_STATUS.md.

### Update, 15 Nov 2026 01:30 EST
All Mac steps from 01:05 ran: Playwright 65/65 across two runs, Chrome perf recorded (30 fps cap, no dropped frames), Blender
transition render + GLB re-import PASS, release ZIP `0a7c4044…c134` (304,866,066 bytes). Status **SOURCE_BASED_UNVALIDATED**.
