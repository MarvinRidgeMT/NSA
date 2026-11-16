# Guided demo: verification (Final Apex P2)

15 Nov 2026, Penumbra session. Code: `web/src/components/Guide.tsx`. Tests: `web/tests/e2e/guided-demo.spec.ts` (4) and
`web/tests/e2e/apex.spec.ts` "guided demo" (1). Status of the product is unchanged: **SOURCE-BASED · UNVALIDATED**.

## What the demo is

Five scenes on the Site04 ROI3 dataset of the ROI export bundle. Every sentence is filled from the loaded bundle and the two
sidecars; nothing is pre-recorded, and a missing value shows "—".

| # | Scene | Route | Scenario / mast shown | Sample (exact) | Camera |
|---|---|---|---|---|---|
| 1 | The lunar environment (arrival) | Explore | baseline · 1 m | 0 (2026-11-14T00:00Z) | Approach |
| 2 | Ridge of Record | Explore | baseline · 1 m | middle of the first Sun-blocked run attributed to the Sun ridge of record (R3) | Ridge of Record |
| 3 | Certainty Height (1 m vs 1.75 m) | Explore | mast chip 1.75 m; series stays the 1 m bundle series (no bundle series at 1.75 m, stated on screen) | same sample as scene 2 | Mast-eye |
| 4 | Coverage | Explore | baseline · 1 m | 0 | Regional terrain |
| 5 | The decision | Decision | baseline · 1 m | 0 | (unchanged) |

The Certainty Height scene is shown at the same blocked hour as the Ridge of Record scene, so the 1 m vs 1.75 m comparison is made at the moment the 1 m mast loses the Sun.

## Determinism

- Each scene sets its whole state: route, scenario, mast pick, exact sample index, ridge selection, ribbon outline, camera view, and pauses playback. Nothing carries over from what the user was doing before, or from the previous scene.
- If the current dataset is not Site04 ROI3, the demo switches to it, or loads the ROI export from `bundles/index.json` if needed, before running a scene.
- A scene runs once its data is present: bundle, dataset and, for scene 3, the Certainty Height sidecar.

## Leaving no trace

- Opening the demo captures the route, bundle, dataset, scenario, time, ridge selection, failure selection, mast pick, ribbon run, return target and camera view.
- **Exit**, **Esc** and **Finish** restore all of these exactly. If the demo loaded a different bundle, the previous one is reloaded from the bundle folder.
  - One limit: a bundle opened from a local file cannot be re-read without asking the user again. In that case the hero bundle stays, and the rest of the state is restored around it.
- **Open the evidence** on the last scene ends the demo on the Evidence workspace and deliberately keeps the demo's dataset.
- Focus moves to the scene title on open and back to the "Guided demo" button on close. The scene text is announced (`aria-live="polite"`).

## Controls

Next / Back / scene dots; **Play / Pause** advances one scene every 12 s (manual stepping is the default); Exit; Esc.
Under `prefers-reduced-motion` the camera cuts instead of easing (existing CameraRig rule), and the Decision scroll is instant.

## Verified (cloud, Chrome + SwiftShader, `vite preview` on 127.0.0.1:4173)

| Check | Test | Result |
|---|---|---|
| Fresh launch: five scenes reach the expected route and camera; scene 2 and 3 share the blocked hour; stepping Back reproduces each scene's full state (URL, UTC, site, scenario, camera, mast) | guided-demo #1 | pass |
| After the user switches site (Site01 ROI6), scenario (10 m) and workspace (Decision), scenes 1–2 are identical to a fresh launch; Esc restores that site, scenario, time and route, and focus returns | guided-demo #2 | pass |
| Play advances, Pause holds for ≥ 13 s; "Open the evidence" lands on Evidence with the demo's site | guided-demo #3 | pass |
| Reduced motion: all five scenes and Exit | guided-demo #4 | pass |
| Scene text values equal the sidecars (Certainty Height, coverage, pass counts) | apex "guided demo" | pass |

Not verified: a timed run-through on the Mac with a GPU (the scene transitions are camera eases of ~1.4 s; SwiftShader is too slow to judge pacing).

## Change log
- 15 Nov 2026 01:34 EST (Penumbra session): created.
