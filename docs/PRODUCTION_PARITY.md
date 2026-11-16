# Production parity (Penumbra Apex)

Date: 14 Nov 2026, 20:44–20:52 EST. Machine: Anish's Mac (repo `~/Downloads/POLARIS-X5D-Blender-Codex`).

## Build
- `web/dist` rebuilt with `npx vite build --emptyOutDir=false` (the Mac VM cannot delete files, so old hashed assets remain in `dist/assets`; `index.html` references only the new ones: `index-DSD9sRbZ.js`, `index-8OameGDJ.css`).
- Clean, reproducible build into a new folder: `npx vite build --outDir ../tmp/dist_apex_20261114_2051` → same asset names (`index-DSD9sRbZ.js`, `index-8OameGDJ.css`): content hashes match the in-place build.
- `dist` was never edited by hand.

## Dev (5174) vs preview (4173) on the Mac built-in browser
| Check | Dev `localhost:5174/#sky` | Preview `127.0.0.1:4173/#sky` |
|---|---|---|
| Bundle loaded | ROI export, Shackleton Rim (Site04 ROI3) | same |
| Mast instrument | chips 1…15 m, 87.2–97.0 %, nominal 93.8 %, 20/20 | same |
| Light tag | "Light: display · Sun 1.61°" | same |
| Ridges of record | R3 (Sun 19 h), R1 (Earth 41 h, 127.7–129.6 km), R2 (Earth 34 h) | same |
| Guided demo button, surface-layer picker | present | present |
| Load errors | none | none |
> E1 (15 Nov 2026), Site04 RoI 3 1 m batch-v2 values quoted above (93.77 / 71.22 / 87.2–97.0): float32 heights, superseded by the float64 rerun (94.36 / 72.11 / 87.54–97.33).
Note: the browser had cached the old `index.html` on 4173; a cache-bypassing reload served the new build (server confirmed by fetching `/index.html` with `cache: no-store`).

## Not checked
- Frame rate on the Mac GPU (browser pane hidden; rAF throttled).
- Playwright on the Mac (no browser in the VM); the full suite ran in the cloud copy of the same merged tree.

## Change log
| When (EST) | Who | Change |
|---|---|---|
| 2026-11-14 20:52 | Claude (Penumbra Apex session) | Created. |

## Final visual pass (14 Nov 2026, 22:31–22:40 EST)
- Mac: `tsc` clean, `vite build --emptyOutDir=false` OK (`index-mtC7LE4E.js`, `Scene3D-CAoAiKG4.js`). Recovery copy before the sync: `tmp/web_before_final_visual_2231.tgz`.
- Preview 4173 on the Mac (built-in browser, Apple M5 Pro): DOM ready 96 ms, load 97 ms, JS heap 53 MB; bundle 5.2 MB in 12 ms; context pack loaded; light line, Earth sight label ("−4.17° vs skyline · skyline: R1, 127.7–129.6 km · beyond this crop"), mast panel and a 32 px control row as expected. Dev 5174 shows the same DOM values.
- The built-in browser pane was hidden, so it rendered no animation frames (0 in 3 s): frame-rate and on-Mac screenshots were not possible. Screenshot parity was checked instead on the same merged tree in the cloud: dev vs production at 1440 × 900, Explore and Decision, 0 % of pixels differ (max difference 0).
