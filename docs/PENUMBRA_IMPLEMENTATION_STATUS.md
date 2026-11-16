# Penumbra V3 — implementation status in `web/` (14 Nov 2026, 19:45 EST)

Design source: Penumbra V3 canvas (https://claude.ai/artifact/EQC1bBz4fprgon2wf8WDCz; project note `claude/DESIGN_V3_2026-11-14.md`).
Scope: presentation layer only. **No change** to the science core, solver, bundles, schemas, ephemerides, coordinates, requirements or
`web/docs/VIEWER_BUNDLE_CONTRACT.md`. The viewer still computes no skyline, visibility or metric. Everything stays SOURCE-BASED · UNVALIDATED.

## Done
| Area | What was built | Where |
|---|---|---|
| Tokens | Penumbra palette as CSS custom properties (void → raised, bone/ash/dust, solar = Sun, earth = Earth, alarm = blocked/failed with a word, selenite = geometry). Old variable names mapped onto them so every existing panel inherits the system. Teal retired. | `src/styles.css` |
| Type | Instrument Serif (story, page titles only), Inter Tight (UI), JetBrains Mono (every number, coordinate, timestamp; tabular numerals). Self-hosted via `@fontsource/*` (OFL 1.1). Ridge ids moved to mono (serif "1" read as "l"). | `src/main.tsx`, `package.json` |
| Global shell | One-row top bar: identity, breadcrumb, data/site/scenario selects, workspace tabs (Explore · Decision · Evidence; same `role=tab` keyboard model and test ids), status badge, Provenance. | `src/components/Header.tsx` |
| Story (landing) | Hero render, editorial chapters 01–05, receipts, footer with data credits, "not affiliated with NASA" and AI disclosure. Opens first at `/` (no hash, no `?bundle=`); skippable; "Open the explorer" → Explore. **Every number is read at runtime** from the certainty sidecar, the coverage sidecar and the loaded bundle; missing source → "—". Renders captioned as illustrative lighting. | `src/components/Story.tsx`, `public/penumbra/` |
| Explore (immersive stage) | Full-viewport stage; title in the black sky; geometry-mode chip (REAL SURFACE · 401² × 5 m DEM vs HORIZON GEOMETRY · angular panorama, not a terrain mesh); floating instrument (Sun/Earth readouts, Ridge of Record callouts, links); temporal instrument (clock + full-width margin ribbon); camera row; "About this view" disclosure; inspectors below the stage (horizon chart, strips, events, failures, Cesium). | `src/App.tsx` |
| Real surface by default | With no `?bundle=`, Explore opens the ROI export's Site04 ROI3 dataset (real PGDA 78 5 m DEM crop, 401²) instead of the skyline-only results bundle. The results bundle remains selectable and is shown as Horizon Geometry Mode. | `src/App.tsx` |
| Scene look | Black sky, ACES tone mapping, one hard key light from the bundle's Sun azimuth with cast shadows (4096² map), near-zero fill, neutral regolith height ramp, Sun disc on the bundle's true Sun direction. Light elevation shown ≥ 0.5° so terrain stays readable — stated in the scene note (display only). | `src/three/Scene3D.tsx` |
| Camera | Named views: Approach, Regional terrain, Mast-eye, Ridge of Record, Overhead (DEM); Approach, Mast-eye, Ridge of Record, Overhead, Horizon inspection (panorama). 1.4 s camera ease, log-distance blend, any pointer/wheel input interrupts, reduced motion cuts, nothing moves unless asked. | `src/three/CameraRig.tsx`, `src/store/camera.ts` |
| Coverage | Batch Coverage Gauge as two rings (Sun solid, Earth) with definition, source path, SHA-256 and status, above the bundle's per-sample tally; < 50 % caveat also fires on it. | `src/components/CoverageGauge.tsx`, `src/bundle/coverageSidecar.ts`, `public/certainty/coverage.json`, `tools/certainty/build_coverage_sidecar.py` |
| Decision card | Paper print palette, statement + 1 m ranges + per-requirement pass counts copied as "k/N" (no joint count inferred), coverage line, sources; Print/save PDF prints the card alone. | `src/components/DecisionCard.tsx` |
| Margin ribbon a11y | Per-sample `<title>` nodes removed from the ribbon and strips (674 + 1011 nodes); one summary label ("Sun blocked in n of 337 bundle samples; …"); on-demand sample table (rendered only when opened; row click seeks). Compact full-width ribbon on the stage keeps unscaled text at any width. | `src/components/MarginRibbon.tsx`, `src/components/VisibilityStrips.tsx` |
| Responsive | ≥1440 desktop; 1024–1439 laptop; 640–1023 tablet (scene on top, instrument and temporal bar stacked below, 44 px targets); <640 mobile. | `src/styles.css` |
| Motion | Duration tokens 120/200/320 ms; 1.4 s camera; no animated counters; `prefers-reduced-motion` removes transitions and camera moves. | `src/styles.css`, `CameraRig.tsx` |

## Numbers verified before display (sources, not typed in)
Site04 ROI3 (certainty sidecar ← `data/batch/2026-11-14/certainty_height{,_fine}/clone_sweep_summary.csv`, a-science `971df9a`):
1 m Sun 87.24–97.03 % (nominal 93.769), Sun+Earth 62.61–74.78 %; Sun 100 % on all 20 maps first at the sampled 1.75 m
> E1 (15 Nov 2026), Site04 RoI 3 1 m batch-v2 values quoted above (93.77 / 71.22 / 87.2–97.0): float32 heights, superseded by the float64 rerun (94.36 / 72.11 / 87.54–97.33).
(`all_maps_100pct_sun_mast_m`); team-requirement pass counts 20/20. Sun+Earth at 1.5 m 73.9–78.6 % and 1.75 m 78.0–78.6 % **are** in the sidecar
(the V3 board had marked them PENDING). Coverage (← `coverage_gauge.json`): Sun 34.1 %, Earth 58.5 % of window hours, nominal DEM, 1 m mast.
Ridge facts come from the bundle's `derived.attribution`.

## Not done (honest list)
- Command search (⌘K), custom tooltip component, custom dropdown and slider components: the native selects/range are restyled, not replaced.
- Mast-height control **in the instrument**: mast changes still go through the Scenario select (bundles with mast scenarios) and the Certainty Height panel.
- Sky board's Horizon Wheel (zenith view) not built; the existing unrolled Horizon chart is restyled.
- A Decision table of all 11 regions: only 3 ROIs ship bundles; the batch-only regions are not shown.
- Global Moon → site flight in `web/` (exists in `app/` only).
- Ridge geometry for the panorama mode stays angular (by design); far ridges beyond the 2 km DEM crop are declared, not drawn.
- `app/` (5173) untouched.

## Changed files (this pass; none committed)
Modified: `web/src/styles.css` (rewritten), `web/src/App.tsx`, `web/src/main.tsx`, `web/src/components/Header.tsx`, `CoverageGauge.tsx`, `MarginRibbon.tsx`,
`VisibilityStrips.tsx`, `web/src/three/Scene3D.tsx`, `HorizonDome.tsx`, `web/package.json`, `web/package-lock.json`.
New: `web/src/components/Story.tsx`, `DecisionCard.tsx`, `web/src/three/CameraRig.tsx`, `web/src/store/camera.ts`, `web/src/bundle/coverageSidecar.ts`,
`web/public/penumbra/{hero,wall,app,map}.webp + README.md`, `web/public/certainty/coverage.json`, `tools/certainty/build_coverage_sidecar.py`,
`web/tests/e2e/penumbra.spec.ts`, `docs/FRONTEND_SOURCE_OF_TRUTH.md`, `docs/PENUMBRA_IMPLEMENTATION_STATUS.md`, `docs/VISUAL_QA.md`,
`docs/RENDERING_VALIDATION.md`, `web/docs/screenshots/penumbra/{before,after}/*`. Appended: `docs/BUILD_STATUS.md`.
Rollback: `tmp/web_before_penumbra_20261114_1906.tgz`.

## Gates (evidence in VISUAL_QA.md and BUILD_STATUS.md)
| Gate | Status |
|---|---|
| 1 Source of truth | **Met** — `docs/FRONTEND_SOURCE_OF_TRUTH.md` |
| 2 Penumbra foundation | **Mostly met** — tokens, type, shell, layout, restyled components; ⌘K/tooltip/custom controls not built |
| 3 Scientific presentation | **Mostly met** — Ridge of Record, Coverage, Certainty Height, Margin Ribbon read real sources; Horizon Wheel and in-instrument mast control not built |
| 4 Immersive experience | **Mostly met** — real DEM mesh by default with honest labels; panorama labelled as such; shadows illustrative |
| 5 Motion and navigation | **Partly met** — named views, interruptible eased camera, reduced-motion cut; terrain-clipping not checked for every view and site |
| 6 Visual QA | **Met for this pass** — screenshots at 5 sizes reviewed; remaining defects listed in VISUAL_QA.md |
| 7 Release | **Partly met** — build passes, `web/dist` rebuilt, Vitest 56 + 1 skip; Playwright 29 pass / 6 fail (the same 6 fail before this pass; see BUILD_STATUS) |

## Apex pass update (14 Nov 2026, 20:55 EST)
Supersedes the gate lines above where they differ:
- Gate 3: in-instrument mast control **built** (MastInstrument, sampled heights only); Ridge of Record inspect/return built. Horizon Wheel still not built.
- Gate 5: mast-eye camera fixed (eye at the mast top); camera Return added; terrain clipping still not checked for every site.
- Gate 7: Playwright **41/41** (6 previous failures resolved: 5 real deep-link bug, 1 stale test — BROWSER_TEST_RECONCILIATION.md); Vitest 89 + 1 skip; release artifacts with SHA-256 in RELEASE_READINESS.md.
- Lighting: display ≥ 0.5° vs true Sun elevation toggle, stated on screen.
- Guided 5-scene demo. Details: PENUMBRA_FINAL_VISUAL_AUDIT.md, SCIENCE_LABEL_AUDIT.md, PRODUCTION_PARITY.md.
