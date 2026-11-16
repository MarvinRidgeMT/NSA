# Performance report (Final Apex P10)

15 Nov 2026. Measurements on Anish's Mac were made by **session A**; Penumbra cites them here and did not re-measure, so as not to run a second, competing measurement on the same machine. The raw files are `web/docs/perf/mac-browser-pane-2026-11-15.json` and `web/docs/perf/mac-chrome-2026-11-15.json`. Penumbra's own numbers come from the cloud (Chrome with SwiftShader, a software GPU) and are only good for sizes and for spotting regressions, never for frame rates.

## Mac (Apple M5 Pro, ANGLE Metal), session A

| Measure | Browser pane (Chromium 156, dev server) | Headed Chrome 157 (`npm run perf:mac`, `vite preview`) |
|---|---|---|
| First contentful paint | 644 ms | — |
| Model visible (context pack loaded) | — | 1690 ms |
| Idle frame interval | mean 8.33 ms, p95 9.3, p99 9.4, max 9.4 (display-limited at 120 Hz) | mean 33.3 ms, p95 34.2 (capped at 30 Hz; see caveat) |
| Camera transition | to South-pole context: p50 8.3, p95 9.1, max 17.0 ms | to context: p95 33.8; to Approach: p95 33.7 ms |
| Time step | before the fix: first frame delayed 0.8–1.0 s; after `StableLine`: p95 9.2 ms, max 16.6 ms | p95 34.3 ms, no long tasks |
| Playback | one long task per sample (React render 52–57 ms) | p95 34.3 ms, no long tasks |
| JS heap | 70 MB after load, 108 MB after playback tests | 55 MB |
| Cast-shadow pass | spread over ~26 frames (8 of 201 rows per frame, double-buffered) | — |

**Caveats (session A's own, kept verbatim in the JSON):**
- In the embedded pane, any main-thread task longer than ~50 ms is followed by a ~1 s pause in frame production. A synthetic 52 ms task with no app involvement reproduced this, so the pauses belong to the pane, not to the scene.
- GPU time per frame was not measured directly (no timer queries); 8.3 ms is an upper bound set by the display.
- The headed-Chrome run reports a flat 33.3 ms in every phase. That pattern fits a 30 Hz frame-rate cap (for example macOS Low Power Mode, or an unfocused or occluded window) rather than a 33 ms workload. Penumbra has not confirmed the cause; the run should be repeated with the window focused and Low Power Mode off before quoting a Chrome frame rate.

## Correction to an earlier Penumbra claim

`docs/RENDERING_VALIDATION.md` (14 Nov, 22:46) states "shadow pass 1.08 ms mean … over 24 Sun positions". That number came from a micro-benchmark of the full-resolution cast-shadow pass run on its own. Inside the app, session A then observed a ~1 s GPU stall per sample with that single-frame pass. Session A replaced it at ~00:30 with a frame-spread pass on a 10 m grid. **The 1.08 ms figure does not describe the app and should not be quoted.** A correction note has been appended to RENDERING_VALIDATION.md.

## Build sizes (cloud build of the current tree, 15 Nov 01:40 EST)

| Asset | Size |
|---|---|
| `index-*.js` (app shell, charts, panels) | 421 kB (≈ 130 kB gzip) |
| `Scene3D-*.js` (three.js + scene, lazy) | 1,055 kB (≈ 290 kB gzip) |
| `index-*.css` | 99 kB |
| `bundles/` (11 listed bundles; the hero ROI export is 5.3 MB) | 24 MB |
| `context/` (terrain context packs, 4 sites, 3 levels) | 28 MB |
| `globe/` (NASA SVS Moon GLB, loaded only on "Moon") | 14 MB |
| Whole `dist/` | 71 MB |

Only the hero bundle, its context pack and the sidecars load at start; the globe, other bundles and other context packs load on demand.

## Not measured

- Clean GPU frame time on the Mac in focused, headed Chrome (see the caveat above).
- Memory over a long session, and the cost of switching between all eleven bundles.
- Mobile hardware.

No optimisation was made in this pass. The one measured problem, the per-step shader relink, was fixed by session A with `StableLine`. No quality mode was added, because none was needed for a measured problem.

## Change log
- 15 Nov 2026 01:45 EST (Penumbra session): created; cites session A's two perf files; corrects the 1.08 ms claim.
