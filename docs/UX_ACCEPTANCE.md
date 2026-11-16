# UX acceptance gates

Written 14 Nov 2026 ~17:40 UTC. Status values: VERIFIED WORKING (evidence listed), WORKING BUT UNVALIDATED, DEMO ONLY,
BLOCKED, NOT RUN. Two user interfaces exist: the main offline app (`app/`, modular JS + Three.js, served on :5173) and the
typed React viewer (`web/`, bundle reader). The product direction of 14 Nov (PRODUCT_EXPANSION) groups the work into three
workspaces — **Sky, Decision, Evidence** — which supersede the earlier Explore / Analyze / Resilience / Mission split; the
mapping is Explore→Sky, Analyze→Sky+Evidence, Resilience+Mission→Decision.

## Sky — what the observer sees

| Gate | app/ | web/ | Evidence |
|---|---|---|---|
| Real local terrain at true scale by default; relief exaggeration explicit and visual-only | VERIFIED WORKING | VERIFIED WORKING (1:1 DEM mesh; a-science bundles show the 720-bin panorama because they ship no DEM) | `browser_smoke.py` relief assertions; `web/tests/e2e/science-v2.spec.ts` |
| Sun/Earth rays at the bundle/solver az-el, clipped at the first hit, state label never from GPU shadows | VERIFIED WORKING | VERIFIED WORKING | `app/tests/site01-source-regression.test.js`; `web/tests/e2e/margins.spec.ts` |
| Camera presets: perspective, overhead, horizon, regional, obstruction close-up; eased flights; cancel with drag or Escape | VERIFIED WORKING (17:03 UTC) | partial: orbit controls + ridge-of-record fly-to only | live check 17:05 UTC (`activePreset`, `flight`, cancel toast) |
| Global Moon → local terrain transition | VERIFIED WORKING: two-stage cancelable flight (descend on the NASA SVS globe, swap to local from overhead, settle oblique) | not applicable (Cesium Moon optional, token at runtime) | live check: `modeDuring=globe`, `modeAfter=local`, `presetAfter=oblique` |
| Horizon chart / wheel with the bundle skyline and margins; truncated bins dashed; nulls as gaps | n/a (horizon canvas in the analysis deck) | VERIFIED WORKING | `web/tests/e2e/science-v2.spec.ts` |
| Margin ribbon: per-sample margins, near-zero band, unknown hatch, click/arrow seek, sign ↔ flag consistency | not implemented | VERIFIED WORKING | `web/tests/e2e/decision-evidence.spec.ts`, `tests/unit/evidence.test.ts` |
| Event navigation between visibility transitions, stating the bracketing samples and that no refinement is claimed | VERIFIED WORKING (`⇤ ⇥`, keys `[` `]`) | VERIFIED WORKING (bundle events, bisection-refined by the solver) | live check; `science-v2.spec.ts` "events jump the clock" |
| Time controls always reachable; one clock | VERIFIED WORKING | VERIFIED WORKING | `browser_smoke.py`; `web` keyboard spec |
| Frame time / memory measured, not assumed | VERIFIED WORKING: `getPerf()` → 8.3 ms mean, 8.9 ms p95, 1.28 M tris, 421 MB heap (Mac, Chrome, local mode) | NOT RUN | live check 17:05 UTC |

## Decision — does the configuration meet its requirements?

| Gate | app/ | web/ | Evidence |
|---|---|---|---|
| Requirements evaluated separately with margins and PASS/FAIL from the current scenario only | VERIFIED WORKING (Sun access, longest darkness, Earth access, longest blackout) | VERIFIED WORKING (bundle metrics with constraints when the bundle declares thresholds; a-science bundles declare none yet) | `app/tests/pro-science.test.js`; `margins.spec.ts` |
| Nominal vs perturbed comparison with the binding constraint and one recomputed repair | WORKING BUT UNVALIDATED (9 deterministic stress scenarios, recomputed) | VERIFIED WORKING for bundle content (22 scenarios, deltas, repair row, 3×3 offset grid) | `science-v2.spec.ts` "5D table" |
| Certainty height (mast sweep across realizations; min tested feasible vs agreement height) | not implemented | panel implemented and checked on the DEMO decision fixture (per-requirement k/N, agreed wording, < 50 % coverage caveat); **real data BLOCKED** on a-science A2 | `decision-evidence.spec.ts`; screenshot 14 |
| Coverage gauge (share of controlling terrain inside the clone footprint) | not implemented | panel implemented; **data BLOCKED** on `derived.coverage`; display tally from critical cells meanwhile, < 90 % triggers the qualification warning | `decision-evidence.spec.ts` |
| Team thresholds Sun ≥ 70 %, Sun+Earth ≥ 40 % (Anish ~13:50 EST) | — | VERIFIED WORKING: PASS/FAIL + margin when the bundle declares no limits, labelled as a team requirement | `tests/unit/decision-fixture.test.ts` |
| Two-site comparison | VERIFIED WORKING (four-site comparison cards) | per-bundle site selector | `app/tests/pro-science.test.js` |
| Changing one input affects only physically related outputs | WORKING BUT UNVALIDATED (battery/threshold inputs do not touch geometry; mast changes the observer) | n/a (viewer recomputes nothing) | code review of `app/src/science.js` |

## Evidence — why the numbers should or should not be trusted

| Gate | app/ | web/ | Evidence |
|---|---|---|---|
| Ridge of record: controlling terrain for every blocked interval with distance, bearing, height, source | partial (first-hit distance and clearance per ray) | **VERIFIED WORKING on real data** (13:56 EST): a-science A1 `derived.attribution` (Site04 ROI3: R3 16 m bump 19 h Sun loss; R1 128 km Earth loss); critical-cell fallback for older bundles | `web/docs/screenshots/12-evidence-ridge-of-record-site04-roi3.png`; `decision-evidence.spec.ts` |
| Click a ridge → camera moves to it, horizon chart highlights the bin, clock seeks | OBSTRUCTION camera preset (first hit) | VERIFIED WORKING | `decision-evidence.spec.ts` |
| Provenance: file hashes, DEM layers, Horizons records, frame, gates, limitations | VERIFIED WORKING (`Inspect data`, report export) | VERIFIED WORKING (drawer + Evidence workspace) | keyboard spec (`bundle-sha`) |
| PGDA 69 reference map clearly separated from POLARIS results | n/a | VERIFIED WORKING | `polar-map.spec.ts` |
| Status always one of DEMO / SOURCE-BASED UNVALIDATED / VALIDATED, most cautious wins | VERIFIED WORKING | VERIFIED WORKING | `web/tests/unit/validate.test.ts` |

## Cross-cutting

| Gate | Status | Evidence |
|---|---|---|
| 1512×982 and 1920×1080: no clipped controls, no HUD overlap, no page scroll (app/) | VERIFIED WORKING | `docs/VISUAL_REGRESSION_AUDIT.md` |
| 390 px phone: no horizontal overflow (web/) | VERIFIED WORKING | `web` e2e "phone 390" screenshot |
| Keyboard-only run, Escape closes, focus visible (web/) | VERIFIED WORKING | `keyboard.spec.ts` |
| Reduced motion honoured (camera flights skipped) | VERIFIED WORKING (app/ and web/ check `prefers-reduced-motion`) | code; not screenshot-tested |
| WCAG 2.2 AA contrast / screen-reader pass | NOT RUN | — |
| First-use guided 60–90 s sequence | not implemented | — |
| Cesium Moon end-to-end with a real token | NOT RUN (no token; failure path tested) | `real-and-fallbacks.spec.ts` |

## Update 14:35 EST (web/ viewer)

| Gate | Status | Evidence |
|---|---|---|
| Sky: blocked target names its ridge of record with distance range, bearing, height vs site ground, hours, obstruction interval | VERIFIED WORKING on Site04 ROI3 (R3 Sun, R1 Earth) | `decision-evidence.spec.ts` (callout values == bundle) |
| Sky: ridge drawn on true-scale DEM from bundle per-bin points; far ridge declared outside the crop | VERIFIED WORKING (ROI export) | screenshot 15; `ridge-3d-outside` test |
| Viewer ridge lookups reproduce bundle per-ridge hours exactly (nearest-bin rule) | VERIFIED WORKING | `tests/unit/evidence.test.ts` |
| Decision: Certainty Height on real batch data, sampled heights only, three distinct heights, team-requirement label | VERIFIED WORKING (sidecar; A2 in bundles still pending) | `certainty-sidecar.test.ts`, screenshot 16 |
| No horizontal overflow at 390 / 820 px in any workspace; no page errors on tab switches | VERIFIED WORKING | `decision-evidence.spec.ts` workspaces test |
| Coverage Gauge / ribbon clone band on real A3/A4 | BLOCKED (`d14af8d` not pushed) | fallback + DEMO fixture only |
| FPS / memory of web/ on the Mac GPU | NOT RUN | — |
| Global Moon → site flight in web/ | ~~not implemented (exists in app/)~~ implemented 14 Nov 21:40 EST, see the rebuild pass below | `terrain-context.spec.ts` |

## Rebuild pass, 14 Nov 2026 (session A) — camera, layers, global Moon

| Item | State | Evidence |
|---|---|---|
| Global Moon → site → regional → local sequence in the React shell | WORKING (Moon → Enter terrain → South-pole context → Approach / Mast-eye / Ridge of Record / Overhead) | `terrain-context.spec.ts` "global Moon" test; screenshot `rebuild/global-moon-site-marker-1512x982.png` |
| Flight cancelable by pointer, wheel and Escape; cut under reduced motion | Implemented for the globe flight; terrain camera views already were (Penumbra) | code: `GlobalMoon.tsx` `Flight`; reduced-motion path not exercised by an automated test for the globe |
| Surface layer picker (keyboard reachable native select) with a source chip | WORKING | `terrain-context.spec.ts` layers test |
| Changing layer / opening the globe changes no instrument value | VERIFIED (automated) | same tests compare the instrument text before/after |
| Image layer offered only where a registered image covers ≥ 20 % of the crop | VERIFIED for "not covered" (Site04 ROI3: option disabled). Covered case (Site01 ROI6) waits for the LROC window | same spec (1 test skipped until `visual_layers.json` exists) |
| No overlap of camera row / picker with instrument or temporal bar at 1440×900; no sideways scroll at 390 px | VERIFIED (automated) | same spec |
| Deep link | `?bundle=` and `#sky|decision|evidence` only. Layer, camera, time and scenario are not in the URL yet | — |
| Mac GPU frame time with the context terrain (≈ 640K triangles + two 3D textures) | NOT MEASURED in this pass | Penumbra measured 8.4 ms mean on the crop-only scene before this change |


## Shareable link (15 Nov 2026)
- [x] A link restores bundle, site, UTC time, scenario, camera view and surface layer (`?bundle=&site=&t=&sc=&cam=&layer=`).
- [x] Changing time or camera updates the address bar without adding history entries; reload gives the same view.
- [x] A time outside the bundle is refused with "never extrapolates", not clamped silently.
Evidence: `web/tests/e2e/url-state.spec.ts` (3/3), `web/tests/unit/url-state.test.ts` (3/3).
