# Visual regression audit — P0 layout collapse of 14 Nov 2026

Written 14 Nov 2026 ~17:40 UTC (Claude, b-experience working tree). Evidence paths are relative to the repo root.

## Before / after evidence

| Role | File | Origin |
|---|---|---|
| **Before** (the regression) | `app/docs/visual-audit/before-user-capture-1122ET.png` | User's own Chrome capture of `localhost:5173/#`, 11:22 ET, copied unchanged from the rebuild pack (`02_CURRENT_BROKEN_UI_1122_AM.png`). |
| Earlier state, for the science comparison | `app/docs/visual-audit/previous-user-capture-0955ET.png` | User's capture at 09:55 ET (`03_PREVIOUS_UI_0955_AM.png`). Shows Sun BLOCKED / Earth VISIBLE at the same displayed angles: see `docs/SCIENCE_VALIDATION_REPORT.md` §P1. |
| **After**, automated | `app/docs/visual-audit/after-1512x982.png`, `after-1920x1080.png` | Written by `app/tests/browser_smoke.py --screenshot` (Chrome, exact viewports) after the fixes. A small lower-right toast from the relief-toggle test is visible; wait ≥ 5.3 s after restoring true scale for presentation captures. |
| After, inspected live | built-in browser pane at 1512×982 and 1920×1080, 17:00 UTC | No console errors, `scrollWidth/Height` equal the viewport, 36 styled buttons/selects, 0 native-styled controls, all off-screen controls belong to closed drawers (mission/analysis). |

The user screenshots are historical observations of the UI at those moments; they are not truth labels for either the
layout or the science.

## Defect table

| # | Observed at 11:22 | Suspected root cause | Confirmed root cause | Fix | Evidence | Remaining risk |
|---|---|---|---|---|---|---|
| 1 | Header buttons `?`, `CAPTURE`, `FULLSCREEN`, `EXPORT REPORT` rendered as native white controls; `SURFACE LAYER` select and `TARGET RAYS` checkbox unstyled. | `app/src/styles.css` not applied: every symptom in the capture (native widgets, HUD text in document flow, no fixed top bar, controls below the canvas) is what the markup looks like with the stylesheet missing. | Not reproducible from the current tree: `app/index.html` links `./src/styles.css` and the live server serves it (sentinel checks pass). The capture coincides with Codex's concurrent rewrite of `styles.css` and `index.html` (both show uncommitted edits in this working tree), so the collapse is attributed to an intermediate state of those files served mid-edit, not to a defect that still exists. The exact intermediate bytes were not preserved. | Codex's finished `styles.css` / `index.html`; the smoke test now fails if the stylesheet is not applied (`body.overflow == hidden`, `.topbar.position == fixed`, active camera button has a background colour). | `app/tests/browser_smoke.py::assert_visual_contract`; live DOM check (0 native-styled controls). | A future half-written stylesheet would again show this way. Guard: the smoke test runs in `test_all.command`; run it before every capture. |
| 2 | `ACTIVE STUDY REGION`, Sun/Earth labels, `Connecting Ridge`, coordinates, metadata, `NE`, `SCALE 5 KM`, node label, camera buttons and layer controls stacked and overlapped at the top-left. | Same as #1: absolutely positioned HUD groups fell into normal flow. | Same as #1. | HUD groups are `position:absolute` inside `#sceneHost`; the geospatial HUD moved away from the side controls; collision pairs are asserted. | `VISUAL_PAIRS` in `browser_smoke.py` (hero/target, hero/legend, target/observer, side-controls/geospatial, side-controls/tool-rail, summary/time, summary/geospatial, time/geospatial) at 1512×982 and 1920×1080. | Pairs not in the list can still collide at widths < 1120 px; the responsive rules exist but are only spot-checked. |
| 3 | A dark rectangular DEM slab with a hard polygon edge; muddy, featureless lighting; no sense of global or regional context. | Default camera framed the 32 km regional crop instead of the 2 km 5 m footprint; local shadow caster produced a false rectangular shadow; render decimation of the 80 m layer. | Confirmed by reading `app/src/scene.js` (`fitRadius`, shadow setup, `maxResolution`). | Codex: true 1:1 relief default with an explicit `RELIEF ×2.38 · VISUAL` option, full 401² regional render (~640K triangles), hero camera on the 5 m footprint, blended footprint shadow disabled, albedo variation and lower fill light. Claude (17:03 UTC): footprint outline opacity 0.26 → 0.18, a `REGIONAL` context camera, an `OBSTRUCTION` close-up camera, eased camera flights. | `after-1512x982.png`; `HUD 5 M + 80 M LOD · 640K TRIANGLES`; measured on the Mac in Chrome: 8.3 ms mean / 8.9 ms p95 frame, 1.28 M triangles drawn, 17 draw calls, 421 MB JS heap (`window.__POLARIS_SCENE__.getPerf()`). | The finite crop edge is still visible when zoomed out; it is styled as a dataset boundary, not hidden. Not a NASA-Eyes-level terrain presentation yet. |
| 4 | Weak framing: no obvious north, scale, observer height, camera altitude, coverage extent or Sun/Earth direction. | HUD text present but unpositioned (#1) plus a regional default camera (#3). | Same. | Compass + scale + coverage HUD, observer HUD, Sun/Earth rays with first-hit marker, 5 camera presets. | After captures; obstruction preset verified to land on the Earth ray's 70 m first hit. | Camera altitude/distance readout is not shown numerically. |
| 5 | `MISSION`, `ANALYSIS`, `DRIFT` as plain inline buttons below the viewer; scenario configuration below the fold; no visible timeline. | Same as #1 (the tool rail and the fixed time console lost their positioning). | Same as #1. | Tool rail is a fixed right-edge rail; the time console is fixed at the bottom with play, ±1 h, and (new) previous/next visibility-transition buttons `⇤ ⇥` (keys `[` `]`), which state the bracketing hour and that the crossing time is not refined. | Live check: `#timeScrub`, `#playBtn`, `#prevEvent`, `#nextEvent` inside the viewport at both sizes; event jump verified (Earth clears between 2026-11-18 20:00 and 21:00 UTC on the 14-day window). | None known. |
| 6 | Tiger graphic with a `SPATIAL` label at bottom-right. | Browser extension or macOS overlay. | **Not emitted by the repo**: `grep -ri tiger app/src app/index.html` finds nothing; the only `spatial` match is the `.geospatial-hud` class; the live DOM has no such element. | None (third-party UI; not removed, not misattributed). | Live DOM id list. | None. |
| 7 | `SOURCE-BASED · UNVALIDATED` shown next to NASA-looking numbers with no nearby explanation. | Information design, not a CSS failure. | Confirmed. | Status badge in the header, `SOURCE DATA · UNVALIDATED` pill over the scene, the mission summary names the binding constraint, `?` opens the method/assumptions modal, `Inspect data` opens the method/data modal; the React viewer additionally has the Evidence workspace (ridge of record, provenance, limitations). | After captures; `web/docs/screenshots/10-evidence-ridge-of-record.png`. | The main app still shows numbers before the explanation; a first-use guided sequence is not implemented. |

## Automated regression proof

`cd app && ../.venv/bin/python tests/browser_smoke.py --screenshot` (Chrome on the Mac): PASS on 14 Nov per
`docs/CLAUDE_HANDOFF.md`; it asserts the stylesheet sentinels, viewport scroll size, the collision pairs above, the
true-scale default, both viewports, the global Moon load and the direct-file launch, and fails on any console/page error.
It was **not rerun by Claude after the 17:03 UTC camera/event changes** (the Cowork VM has no Chrome); the equivalent checks
were done live in the desktop app's browser pane (see "After, inspected live"). Rerun it before packaging.

## Follow-up, 13:00 EST

| # | Observed | Root cause | Fix | Evidence |
|---|---|---|---|---|
| 8 | At ≤ 760 px the scene-legend pills became ~160 px tall empty boxes over the terrain. | `.scene-legend` had both `top` (base) and `bottom` (narrow rule); wrapped flex lines stretched to fill. | `top:auto`, `align-content/align-items:flex-start`, first three pills only. | Live DOM check at 698 px: pill height 23 px. |
| 9 | OBSTRUCTION close-up hid the terrain behind schematic markers. | Marker sizes are tuned for the km-scale default view. | 0.12× markers / 0.25× rays in that preset only (visual). | Live screenshot, 1512×982. |

## Rebuild pass, 14 Nov 2026 20:00–22:00 EST (b-experience session A; React viewer `web/` unless noted)

| # | Defect (master rebuild prompt) | Root cause | Fix | Evidence | Residual risk |
|---|---|---|---|---|---|
| R1 | Local terrain reads as a floating rectangular slab in black space | Only the 2 km 5 m crop was drawn | Terrain context pack: the 80 m PGDA 90 crop (±16 km) drawn at true scale around the crop, cut out under it, skirt on the crop edge | `web/docs/screenshots/rebuild/explore-approach-regolith-1512x982.png`, `explore-context-regolith-1512x982.png`, `explore-context-coverage-1512x982.png` | 5 m → 80 m is a 16:1 step with no intermediate ring; visible as a resolution change at the crop edge in close views |
| R2 | Shadows disabled or cut at a rectangle (shadow-map frustum = crop) | 4096² shadow map covered only the crop; terrain outside cast nothing | No shadow map with a pack. Horizon maps (48 azimuths) of the displayed crops + the bundle skyline for farther terrain decide where the Sun is below the local horizon; penumbra one solar radius wide | `explore-context-shadow-1512x982.png` (the model alone), `explore-context-regolith-sample7-1512x982.png` | Display model, not the solver: surface points, finite crops, 8-bit angles. Stated on screen and in the scene note |
| R3 | Terrain colour muddy / green-brown; no statement of what the colour is | Height-ramp vertex colours | Neutral regolith grey with a soft-knee response at grazing light; chip names the layer and its source; debug layers for elevation (10 m contours), slope, normals, coverage, shadow | `explore-context-elevation-…`, `-slope-…`, `-coverage-…` | Registered photo layer exists only for Site01 once its download completes; Site04 has none |
| R4 | `preserveDrawingBuffer: true` permanently on | Convenience for captures | Off in `web/` (both canvases) and in `app/` (`scene.js`); app capture and smoke test render then read in the same task | cloud check: context attribute `preserveDrawingBuffer` false, capture 1.46 MB PNG | Mac `browser_smoke.py` not re-run after the change |
| R5 | Global Moon missing from the React shell | Lived only in `app/` | "Moon" in the camera row: NASA SVS 14959 compact GLB (hash-pinned), site marker, cancelable flight, "Enter terrain" arrives on the South-pole context framing | `global-moon-site-marker-1512x982.png` | Compact colour model only (13.8 MB); the 8K topographic model stays in `app/`. Longitude origin of the model not verified against its texture |
| R6 | 390 px page scrolled sideways | Header right group (Guided demo + status + Provenance) wider than the phone | wraps at ≤ 760 px | `explore-mobile-390.png`; `terrain-context.spec.ts` phone test | — |

All captures above are from headless Chrome with software GL (SwiftShader) in the cloud, at 1512×982 unless named.
They prove layout and that the scene draws; they are **not** Mac GPU evidence and not performance evidence.


## Time-step hitch, 15 Nov 2026 (session A)
Symptom: ~1 s freeze on every time step on the Mac. Cause: drei `<Line>` rebuilt its material when points changed, so ANGLE Metal
relinked 2 programs and the line made 70 buffer allocations per step. Fix: `web/src/three/StableLine.tsx` keeps one Line2 for the
component's life and rewrites its buffers. Measured in the Mac browser pane: 0 links and 0 allocations per step; frame p95 9.2 ms.
Evidence: `web/docs/perf/mac-browser-pane-2026-11-15.json`.
