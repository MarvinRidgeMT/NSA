# POLARIS X v2 — backlog merged from the two team prompts

Sources (line numbers are lines of these files as committed in eda168c):

- **E** = `docs/v2/inputs/POLARIS_X_FABLE_5_2_NASA_EYES_PLUSPLUS_PROMPT.md` ("NASA Eyes × 2"; has explicit P0/P1/P2 lists)
- **M** = `docs/v2/inputs/POLARIS_X_FABLE_5_2_MASTER_REBUILD_PROMPT.md` (master rebuild; "Defects that must be fixed" 1–12, no P labels)
- **V2** = `docs/v2/inputs/CLAUDE_CODE_PROMPT_6D_worlds_blender_v2.md` (wins on science and data rules; the team prompts win
  on UX detail)

Checked by session S1 on 16 Nov 2026 against branch `claude/v2-s1-6d-cube-0bb4aa` (= `feature/v2-whole-moon` eda168c +
S1 commits) by reading the code and tests. Status words: **open** (defect still present or required test missing),
**partial** (some of it is in the code, evidence given), **fixed** (evidence given), **not checked** (could not be
verified tonight; reason given). Nothing here was fixed tonight: S1 owns no file these items touch (`docs/v2/SPLIT.md`).
The shell's permission check failed repeatedly late in the session, so a few checks are file reads without a grep
sweep; those say so.

## 1. P0 / P1 defects (E lines 65–119, M lines 154–167)

| # | Pri | Defect (source line) | Status | Evidence | Owner hint |
|---|---|---|---|---|---|
| B1 | P0 | Decision copy contradicts the numbers: "every realization loses the Sun" while min Sun = 100 % (E 69–78) | **partial** | `web/src/components/DecisionHero.tsx:88` and `:138` now branch on `sLow.max < 100` / `sLow.min < 100` (every one / some / none). Still open: (a) the sentence keeps "Meets … but none of them loses the Sun", so the "but" reads as a contradiction in the none-branch; (b) no unit or browser test for the three branches (no test under `web/tests/` matches the branch text); (c) the Story, Guide, Decision Card, alt-text and print-copy sweep the prompt asks for is not recorded | web UX |
| B2 | P0 | Release integrity: ZIP checksum sidecar stale after repackaging (E 80–82) | **open** | `package_release.command` writes the ZIP then only prints `shasum -a 256` to stdout (line 27); no `.sha256` sidecar is written and nothing runs `shasum -a 256 -c`; no test of archive entries | release |
| B3 | P1 | Short-desktop and mobile composition: globe card vs control strip at ~1512×783, clipped title and label pile-ups at 390 px (E 84–95) | **partial** | Gates exist only for some sizes: `final-apex.spec.ts:111` (390×844 overflow + title/light-tag overlap), `final-apex.spec.ts:123` (1024×768 sight labels vs instrument), `decision-evidence.spec.ts:32` (390×844, 820×1180 overflow only), `terrain-context.spec.ts` (1440×900, 1512×982, 390×844). No gate at 430×932, 768×1024, 1366×768, 1512×783, 1920×1080, 2560×1440; no clipped-heading or focus-behind-sticky-UI check; mobile is still the desktop layout in one column | web UX |
| B4 | P1 | Deterministic Moon ↔ terrain state machine (E 97–107) | **open** | Camera buttons report `aria-pressed={cam.view === c.id}` whether or not the globe overlay is open and their click only calls `cam.request(c.id)` (`web/src/App.tsx:559–562`); the globe closes only from its own Enter action (`web/src/three/Scene3D.tsx:800`) or the Moon toggle (`SurfaceLayer.tsx:96`). Globe mode is not in the deep link (`web/src/store/urlState.ts` serialises bundle, site, t, sc, cam, layer only), so Back/Forward cannot restore it. One existing test covers Moon → Enter terrain (`terrain-context.spec.ts:133`); none for Moon → camera view, site change while the globe is open, rapid clicks or reduced motion | web 3D |
| B5 | P1 | Console cleanliness: "Attempted to synchronously unmount a root while React was already rendering" (E 109–111) | **partial** | `decision-evidence.spec.ts:31` asserts no page errors across workspace switches; `ux-regressions.spec.ts:23` collects console errors but only fails on duplicate-key messages. No test requires zero console errors and zero React warnings through the full guided demo and site-switch sequence; the unmount warning was not reproduced tonight | web |
| B6 | P1 | Local terrain visual quality: Site04 neutral terrain and the Blender hero soft/patchy; slab/trench/island look at the local→regional cut (E 113–115; M 156–158) | **not checked** | Needs a visual review in the browser and Blender renders; S5 (Blender v2) and the render-vs-real phase own this. Not judged from code | S5, §6 |
| B7 | P2 | Only two fixed terrain levels (E 117–119; M 160, 5) | **partial** | 5D Phase 9.4 added a 5-level near-field quadtree (80/40/20/10/5 m, ±7 km) streamed by camera distance, opt-in (`docs/5D_UPGRADES_STATUS.md` row 9.4, `tools/terrain/build_lod_tiles.py`, the `LodTerrain` component). Still: opt-in only; no 80 m context beyond ±7 km while on; no cast shadows on the LOD layer; no verified intermediate PGDA 90 20 m product in the display. V2 §2 (whole-Moon pyramid, S3) supersedes this | S3 |
| B8 | M-4 | Terrain cast shadows disabled because of a rectangular shadow boundary (M 159) | **not checked** | `Scene3D.tsx:785` enables `shadows` on the Canvas; whether a regional shadow-only caster removed the boundary needs a visual check | web 3D |
| B9 | M-6 | ~1.28 M triangles / 421 MB heap (M 161) | **partial** | `docs/PERFORMANCE_REPORT.md` (Phase 9.4) reports p95 frame 4.4 ms worst phase with LOD on (headless Chrome, Metal, vsync off). Heap and triangle count after 20 site/layer/globe cycles not measured | web perf |
| B10 | M-7 | Continuous `preserveDrawingBuffer: true` (M 162) | **partial** | The `web/` Canvas does not set it (`web/src/three/Scene3D.tsx:788`: `antialias, logarithmicDepthBuffer, toneMapping, toneMappingExposure`). The legacy `app/` renderer was not re-checked tonight (no grep: shell unavailable) | app |
| B11 | M-8, M-9 | Blender v2 scene: 80 m DEM as 201×201 mesh, 5 m not the hero; `derivedOutputsPresent: false`, rays "not evaluated" (M 163–164) | **not checked** | E 55 reports a later Blender 5.3 build with a full 401² Site04 5 m mesh; ray derived outputs not verified here. V2 §5 (S5) rebuilds the Blender pipeline | S5 |
| B12 | M-10 | Global Moon must not be numerical terrain; NASA polar pinching disclosed (M 165) | **partial** | `GlobeButton` title says "NASA SVS global model, visual context only" (`SurfaceLayer.tsx:96`). The polar-pinching disclosure on screen was not located tonight | web |
| B13 | M-11 | Two products (React viewer and legacy viewer) (M 166) | **fixed (by policy)** | E 44 makes `web/` the product shell and `app/` the legacy/fallback path; V2 builds only on `web/` | — |
| B14 | M-12 | Release packaging / parity checks stale (M 167) | **open** | Same as B2; plus no Blender ↔ web parity check at three UTC samples on this branch (V2 §5.3 adds Blender-proof tests, S5) | release, S5 |
| B15 | E | Reduce the ~1.03 MB uncompressed `Scene3D` chunk (E 245) | **open** | `npm run build` on this branch: `dist/assets/Scene3D-*.js` 1,074.25 kB (301.49 kB gzip), larger than the 1.03 MB the prompt cites | web perf |

## 2. UX rules (team prompts win on UX detail)

| # | Rule (source line) | Status | Evidence |
|---|---|---|---|
| U1 | One full-viewport 3D world as the primary interface; terrain first, time second, analysis on demand (E 129, M 291) | partial | Sky workspace with stage; Decision and Evidence are separate workspaces (`#sky`, `#decision`, `#evidence`). Not a single full-canvas shell with contextual panels |
| U2 | Contextual left panel `Info / Toolbox / View Options`; compact right tool rail (E 132–134, 147–148) | open | No such panel set found in `web/src/components/` (file list read tonight) |
| U3 | Persistent bottom time conductor: date/time, live/fixed state, speed, slider, direct input (E 135; M 411–412) | partial | `web/src/components/TimeBar.tsx`: UTC output, prev/next sample, play/pause, slider, ISO input, coverage. No speed control (fixed 400 ms per sample, line 23), no live/fixed state, no previous/next transition button in the bar |
| U4 | One UTC sample drives scene, rays, margins, timeline, events, charts, ridge, Decision, Evidence; no hidden component clock; no extrapolation (E 167–174; M 335, 409–416) | partial | Single store `usePolaris` (`utcMs`, `setTime` refuses out-of-range times, `urlState.ts:85` "not extrapolated"). The cube slicer has its own S index (start date, a decision axis, not the clock) — documented in `docs/v2/6D_MODEL.md` as L, not time. No test sweeps every view after play/seek/event/deep-link restore |
| U5 | Exact sample vs interpolation vs bracketed event shown (M 413) | fixed | `TimeBar.tsx:36` shows "between samples i–j" vs "sample n / N" |
| U6 | Share: deep link with bundle, site, scenario, UTC, camera, layer, light mode, selected ridge, workspace (E 150, 293) | partial | `web/src/store/urlState.ts` carries bundle, site, t, sc, cam, layer and the workspace hash; missing light mode, selected ridge, globe mode; no copy-link button located tonight |
| U7 | Hide UI, fullscreen, screenshot, copy link, reset view (E 141, 203) | partial | Focus mode hides panels (`HeadingTape.tsx:99`, key F); reset view `cam-reset` (`App.tsx` camera row). Fullscreen, screenshot and copy-link controls not located tonight |
| U8 | Camera grammar: named deterministic views, interruptible, never through terrain, Back to previous view, focus on double-click (E 196–204; M 394–407) | partial | `web/src/store/camera.ts` named views with request/nonce, instant under `prefers-reduced-motion`; no "Back to previous view" or double-click focus located |
| U9 | Label decluttering with priority, occlusion, collision avoidance, bounded overlap (E 202, 341) | partial | `ux-regressions.spec.ts` "South Pole map labels do not overlap"; `final-apex.spec.ts:123` sight labels vs instrument. No general declutter test |
| U10 | Progressive disclosure: Explore / Analyze / Evidence; raw filenames only in Evidence/advanced chooser (E 186–194) | open | The data-file selector (`bundle-select`) is in the main top area (`final-apex.spec.ts:111` checks its width on the stage) |
| U11 | Moon Trek subset: scale ladder, searchable layers with metadata, distance/bearing, elevation/slope profile, line-of-sight probe, layer opacity/compare, evidence downloads (E 152–163) | open | Surface layer chooser exists (`SurfaceLayer.tsx`); no distance, profile or probe tools located tonight |
| U12 | First 30 s: crisp globe, one `Fly to site`, continuous interruptible journey, terrain ≥ 70 % of attention (E 178–184) | partial | Globe overlay + `globe-enter` lands on the regional framing (`Scene3D.tsx:799–801`, `terrain-context.spec.ts:133`). The app opens on Story/Sky, not on the globe; no single continuous flight |
| U13 | Full keyboard access, visible focus, reduced motion, contrast, text alternatives (M 476–484; E 172, 204) | partial | `web/tests/e2e/keyboard.spec.ts`, `final-apex.spec.ts:183` (skip link, tabs, guided demo, Esc); reduced motion in `camera.ts`. Cube slicer controls are labelled (`aria-label={d.label}`) and now grouped in `<fieldset>`/`<legend>`; no automated axe scan |
| U14 | Responsive layouts at the listed sizes, mobile as a designed hierarchy (E 88–95; M 483) | partial | see B3 |
| U15 | Performance targets: median ≤ 16.7 ms, p95 ≤ 22 ms at 1512×982 DPR 2; shell ≤ 2 s, globe ≤ 4 s, terrain ≤ 5 s; stable heap after 20 cycles (E 233–245). V2 §7 sets p95 ≤ 16 ms, cold start ≤ 5 s to the first globe frame | partial | `docs/PERFORMANCE_REPORT.md` p95 4.4 ms (headless, vsync off). Native Chrome on the Mac, DPR 2, load-time and leak checks not recorded on this branch. V2 thresholds win where stricter (science/data rule is not involved; both are UX gates, so the stricter one is kept) |
| U16 | Every sentence value-conditional and tested at 0 %, 100 %, missing sidecar, no DEM, no attribution, metrics-only (E 305) | open | See B1; no edge-case copy tests located |
| U17 | Display layers change no instrument number; LROC cannot enter a DEM/solver path (E 337–338; M 183, 344) | partial | `terrain-context.spec.ts:146` asserts the globe never changes the instrument text; visual-layer guards `VISUAL_LAYER_AS_DEM` exist per M 38 (not re-checked tonight) |

## 3. Where the team prompts conflict with V2 (V2 wins on science and data)

| Topic | Team prompt | V2 rule kept |
|---|---|---|
| Dimension 5 | "selected uncertainty/mission scenario" (M 76, E 264) | 5 = uncertainty X only; mission choices are 6 = decision L; requirements are filters, world is a context selector (`docs/v2/6D_MODEL.md`) |
| Release label | `SOURCE_BASED_UNVALIDATED` (M 173, E 265) | Same meaning; V2 on-screen labels "SOURCE-BASED · UNVALIDATED" (geometry), "ENGINEERING ASSUMPTION" (energy, link), "MODEL" (thermal), "VISUAL", "AI-GENERATED" |
| Scope | south pole, Site01/Site04 (M 70, E 50–56) | whole Moon, then Mercury and Mars (V2 §2–3) |
| Data | download PGDA/LROC crops into the repo tree (M 504) | never commit NASA/JAXA/ISRO/CNSA rasters; cache under `$POLARIS_DATA`, manifest with URL, SHA-256, licence, retrieval UTC, version (V2 §0.4) |
| Blender role | "authoring/evidence artifact; WebGL is the product runtime" (E 251) | Blender is the single 3D production pipeline with proof tests (V2 §5); pictures only display solver numbers |
| Realism | compare against NASA Eyes / Moon Trek screenshots (M 608) | realism is measured against thousands of real images with a pre-registered protocol (V2 §6) |
| Performance | p95 ≤ 22 ms (E 237) | p95 ≤ 16 ms, cold start ≤ 5 s (V2 §7) — stricter one kept |
| Git | "Do not commit or push unless asked" (E 317) | small logical commits on the session branch, never push (V2 §0.1, §0.5) |

## 4. Suggested order (after the v2 Phase 1 merges)

1. B1 (copy branches + tests), B2/B14 (atomic ZIP + sidecar + `shasum -c` test) — small, P0.
2. B4 (globe/camera state machine + deep-link `globe` flag + tests), B5 (zero-console-error sweep).
3. B3/U14 layout gates at every listed size.
4. U3/U6/U7 time conductor speed and events, share link completeness, hide-UI/fullscreen/screenshot.
5. B15/U15 code splitting and native-Mac performance record.
