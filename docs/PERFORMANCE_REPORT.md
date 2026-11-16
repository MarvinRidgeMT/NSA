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

## 5D Phase 9.4: near-field LOD terrain (±7 km at 5 m), 16 Nov 2026 ~01:20 EST (Claude, branch `5d-phase9-lod`)

**Budget:** p95 frame time ≤ 16 ms. **Result: met.** The worst phase has p95 = 4.4 ms with the layer on. The page is Site04 RoI 3 with `?lod=1`: 76–79 quadtree tiles drawn, finest level 5 m, about 4.7 M triangles.

**Method.** `cd web && npm run build && node scripts/perf_mac.mjs --lod --headless --uncapped` runs Chrome 157 on the Mac's GPU: ANGLE Metal on an Apple M5 Pro. The viewport is 1512 × 982 CSS px at 2×, so the canvas is 3024 × 1852. The phases are idle, the camera views (context, regional, overhead, approach), 10 time steps and 8 s of playback, plus a 6 s orbit drag made with real mouse input, during which tiles keep streaming.

`--uncapped` turns vsync and the frame-rate limit off, so a requestAnimationFrame interval is the real frame cost. With vsync on, every interval reads 16.7 ms whatever the load; that run is kept as `mac-chrome-lod-2026-11-16.json` and shows p95 16.7–16.8 ms in every phase. `--headless` keeps the Metal GPU and puts no window on screen. A headed run was tried three times, and each time the Chrome window closed mid-run with no crash or page error, so the window is assumed to have been closed by someone at the Mac.

The script changes are additive: `--lod`, `--headless`, `--uncapped`, and a `pageErrors` field in the output. The default run is unchanged.

| Phase (rAF interval, ms) | LOD on: p50 / p95 / p99 | LOD off (existing scene, Site01 RoI 6): p50 / p95 / p99 |
|---|---|---|
| Idle | 2.4 / 4.0 / 5.3 | 2.5 / 4.2 / 7.5 |
| Camera → South-pole context | 1.1 / 3.8 / 8.8 | 1.3 / 3.8 / 6.3 |
| Camera → Regional | 1.5 / 3.9 / 9.5 | 2.3 / 4.4 / 9.5 |
| Camera → Overhead | 0.9 / 3.4 / 5.8 | 1.6 / 4.8 / 12.4 |
| Camera → Approach | 1.2 / 3.7 / 13.0 | 1.9 / 4.5 / 8.9 |
| Time steps (worst of 10 × 0.5 s) | p95 5.2, max 35.0, no long tasks | p95 934 (one 938 ms long task) |
| Playback 8 s | 2.6 / 4.4 / 7.8 | 2.6 / 4.6 / 11.0 |
| Orbit drag 6 s (tiles streaming) | 1.4 / 4.4 / 11.6 | — |
| JS heap after the run | 118 MB | 75 MB |

Raw files are in `web/docs/perf/`:
- `mac-chrome-lod-headless-uncapped-2026-11-16.json`;
- `mac-chrome-headless-uncapped-2026-11-16.json` (LOD off);
- `mac-chrome-lod-2026-11-16.json` (vsync-capped).

The first one or two frames of a run can take 0.1–0.8 s in both modes (warm-up). This is the `max` column in the JSON, and it is not the LOD layer's cost.

**Claude desktop app pane.** The pane run is the same page, measured in-page with `web/scripts/perf_lod_pane.js`; the record is `web/docs/perf/lod-pane-2026-11-16.json`. Idle at Approach and at Mast-eye gave p95 9.2–9.3 ms at 120 Hz, which is display-limited, with 76–88 tiles drawn.

The rest of that run is **not** a valid frame-time measurement. The session was not open in any window, so the pane was hidden and the page ran as a background page. A probe in the same tab later got 0 animation frames in 3 s, and the run's ~1 s intervals are throttling, not frame cost. A full pane run should be repeated with the pane on screen.

**What made it fit.** The first build turned tile heights into meshes on the main thread. In the pane, the queue drained at about 3 tiles/s and starved frames. The fix:
- tiles are fetched and checked (size and SHA-256), and their mesh arrays (positions, normals, index, bounding sphere) are built in 2 Web Workers (`web/src/three/lodWorker.ts`, `lodMesh.ts`);
- the render loop only wraps finished tiles in a `BufferGeometry`, at most 8 per frame and within a 2 ms budget (the first cap of 2 per frame made streaming take ~21 s under software GL, against ~9 s now);
- the JS copies are dropped after the GPU upload;
- the cache holds at most 160 tiles, about 1.1 MB of GPU buffers each for a 5 m tile.

**Not measured:** GPU memory directly; the pane with the layer on and the pane visible over a full run; low-end GPUs.
