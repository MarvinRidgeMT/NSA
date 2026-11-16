# Visual QA — Penumbra V3 in `web/` (14 Nov 2026, 19:50 EST)

Screenshots: `web/docs/screenshots/penumbra/before/` (Mac built-in browser, 19:04, before any change) and `.../after/` (`mac-*` = Mac
GPU, Apple M5 Pro; `cloud-*` = headless Chrome + SwiftShader at exact sizes 1440×900, 1512×982, 1920×1080, 834×1112, 390×844).

## Before (19:04) — main problems seen
Dashboard of equal bordered cards on navy; the 3D view was one card among many (380–640 px tall); three rows of controls before any
content; teal accent used for selection, ridges and agreement alike; system font; ribbon and strips carried one `<title>` per sample;
the opening bundle was skyline-only, so the "terrain" was an elliptical silhouette; the built preview (4173) lagged the sources.

## Review loop (each round: screenshot → compare with the V3 board → five largest differences → fix)
| Round | Board | Largest differences found | Fixed |
|---|---|---|---|
| 1 | Explore (App) | scene not dominant; labels over terrain; controls crowding the header (label "SCENARIO" collided); 3D HTML tags above the instrument; ribbon scaled down and clipped | full-viewport stage, overlays in the sky, visually hidden select captions with titles, z-index above drei `Html`, compact full-width ribbon |
| 2 | Explore | bundle warning pushed the bar off-screen; ridge caption, scene note and camera list overlapped on the left; "R1" read "Rl" in the serif | warning inside the stage title; camera row moved above the temporal bar; scene note → "About this view" disclosure; ids in mono |
| 3 | Explore | terrain a thin strip at the bottom; sky navy; flat light | anti-Sun approach camera low over terrain, black sky, hard key light + shadows, Sun disc on the true Sun direction |
| 4 | Story | terrain only a sliver; chapter 03 heading inherited the uppercase label style | hero image raised; heading style isolated |
| 5 | Decision / Evidence | clock above the page title; wide ridge table clipped; wrapping mast labels | title first, clock under it; panels scroll horizontally; `nowrap` table headers |
| 6 | Responsive | mobile render caption over the kicker; compact ribbon unreadable on narrow screens; inspect heading crowded | caption moved to the bottom; full ribbon below 1024 px; heading stacks |
| 7 | Explore 1920×1080 | taller ribbon hid the camera row | ribbon viewBox follows pixel width (fixed height); camera row and bar stacked in one container |

## Automated layout checks (Playwright, `tests/e2e/penumbra.spec.ts`)
- 1440×900: instrument ∩ temporal bar = ∅; instrument ∩ title = ∅; camera row ∩ bar = ∅; camera row ∩ instrument = ∅; bar inside the viewport;
  ribbon wider than 1000 px; no horizontal page overflow.
- Fonts loaded (`document.fonts.check`) and numbers in JetBrains Mono.

## Remaining visual defects (known, not fixed in this pass)
1. Instrument text can be clipped at the bottom at 1440×900 when both Sun and Earth callouts show (it scrolls; a collapsible callout would be better).
2. The 3D "local N" tag can sit at the far left edge in some views.
3. Ridge caption (left) and the instrument callout (right) repeat the same ridge facts.
4. Bundle select label is long ("Connecting Ridge (Site01 ROI6) + …") because the export bundle lists three sites.
5. Panorama mode is honest but less cinematic than the real-surface mode by design.
6. No custom ⌘K / tooltip / dropdown components yet (see PENUMBRA_IMPLEMENTATION_STATUS).

## Compared with the V3 boards
Closest: Story (landing), Explore (stage + instrument + horizon bar), Decision card, colour/type system. Furthest: Sky board (Horizon Wheel not built),
Components board (several bespoke controls not built), Decision board's 11-region table (only 3 ROIs have bundles).
