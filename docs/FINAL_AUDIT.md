# Final audit

Audit date: 14 November 2026

Release decision: **usable local research build; scientific output remains `SOURCE_BASED_UNVALIDATED`.**

## VERIFIED WORKING

| Feature | Evidence | Boundary |
|---|---|---|
| Source ingest and provenance | Three v2 bundles pass JSON Schema; recorded raw JPL hashes match retained responses; local PGDA 78 source hashes are recorded. | Confirms reproducibility and internal contract, not science truth. |
| Projection/raster/parser gates | 6 automated tests cover four site anchors/round trips, longitude sign, source row flip, header-driven parsing and declaration checks. | Internal checks are not an independent geodetic review. |
| Terrain obstruction engine | 9 Python and 15 JavaScript tests pass, including exact curvature, synthetic ridge, first-hit evidence, time bounds and scenarios. | Finite sampled terrain and point targets only. |
| Browser source workflow | Headless Chrome verifies visible WebGL terrain in localhost and direct-file modes, loads two source sites, imports the full Site01 bundle, exposes six terrain choices, recomputes a clone, exercises mission/analysis drawers and reports no page/console errors. | Cesium live token flow was not part of this smoke test. |
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
| Complete requested React/TypeScript stack | Existing local app is verified modular JavaScript; migration was not completed in this execution. |

## Test record

- Baseline before edits: 6 Python geometry tests and 13 JavaScript tests passed.
- Final automated suite: 9 geometry + 6 ingest + 15 JavaScript tests passed; Python compile, three bundle schemas and raw-response hashes passed.
- Browser: Chrome smoke passed with no captured errors in both localhost and direct `file://` launches; the rendered canvas was checked as nonempty.
- Blender: demo and source rebuilds completed; generated files and collection structure passed checks.
- One initial final verifier run failed because the new verifier assumed manifest assets were a list while the builder emits a dictionary. The verifier was corrected to support the actual contract, then rerun successfully. This was a test-harness defect, not an artifact hash failure.

## Top three remaining issues

1. Independent illumination validation is the mandatory science gate.
2. Horizon reach/resolution uncertainty must be quantified with wider coverage and all four source sites.
3. React/TypeScript migration should preserve the existing source contract and regression suite rather than changing numerical behavior.
