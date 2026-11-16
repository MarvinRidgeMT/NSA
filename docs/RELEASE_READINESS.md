# Release readiness (Penumbra Apex)

Date: 14 Nov 2026, 20:52 EST. Verdict: **ready for an internal demo; not externally published, pushed or submitted** (no authorization to do so). All results remain SOURCE-BASED · UNVALIDATED.

## Artifacts (Mac repo `tmp/`)
| Artifact | SHA-256 |
|---|---|
| `tmp/polaris_web_release_apex_20261114_2051.tgz` — web source + public data + tests + configs (20,055,132 bytes) | `49ec341f394641c4c8ae1b901583186a0d8dbce60cb35bc5903355cc057b9f1e` |
| `tmp/polaris_web_dist_apex_20261114_2051.tgz` — clean production build (`dist_apex_20261114_2051/`, 49 MB, 76 assets) | `2dcc12d9838e0dce699add86b884e21d9554c34fccde64be64cd09b58948fb55` |
Base commit (HEAD, working tree uncommitted): `80799247ebc01a0e333bf18fa39b4b70664f2376`. Nothing was committed or pushed.
Recovery copies taken before each overwrite: `tmp/web_before_penumbra_20261114_1906.tgz`, `tmp/web_before_apex_20261114_2010.tgz`, `tmp/web_before_apex_sync_2042.tgz`.

## Checks
| Check | Result |
|---|---|
| `tsc --noEmit` (Mac and cloud) | clean |
| Vitest | 89 pass, 1 skipped (11 files) |
| Playwright full suite | 41 / 41 (cloud, headless Chrome) — includes deep links, keyboard-only run, story/explore/decision/evidence, camera views under reduced motion, ribbon accessibility (summary + on-demand 337-row table), 1440 × 900 overlap check, fonts, invalid-bundle rejection, Cesium failure without persisting a token, WebGL-independent fallbacks |
| Visual audit, 22 screens incl. 1512, 1920, tablet, mobile | before/after in `web/docs/screenshots/penumbra/apex-*`; see PENUMBRA_FINAL_VISUAL_AUDIT.md |
| Dev vs preview parity (Mac browser) | match; see PRODUCTION_PARITY.md |
| Science labels | see SCIENCE_LABEL_AUDIT.md |

## Guided demo (5 scenes, header "Guided demo" or Story)
1. Lunar environment — Site04 ROI3, 2 km 5 m DEM crop, window, 1 m mast (approach camera).
2. Ridge of Record — clock set inside R3's run, bin highlighted, ribbon outline, Ridge camera.
3. Certainty Height — 1.75 m selected from the sidecar, outline mast, every realization keeps the Sun.
4. Coverage — 20/20 vs 34.1 %; R1 at ~128 km is outside every realization.
5. Decision — Decision page, card in view.
Every sentence is filled from the bundle and sidecars; Esc or Exit leaves at any time; Back/Next/dots navigate.

## Open items before any external release
- Independent validation of the solver (solver of record pending).
- GPU frame-rate measurement on the Mac.
- Camera-row layout at 1440 px now two lines (shared with session A's surface picker).
- Commit/push only on the team's instruction.

## Change log
| When (EST) | Who | Change |
|---|---|---|
| 2026-11-14 20:52 | Claude (Penumbra Apex session) | Created. |

## Final visual-quality pass — artifacts (14 Nov 2026, 22:46 EST)
| Artifact | Size | SHA-256 |
|---|---|---|
| `tmp/polaris_web_release_final_visual_20261114_2246.tgz` — web source + public data (incl. globe, context packs) + tests + configs | 34,655,772 B | `aac6696a4aba1c5735a1aa8f856e7b5ff62c9288f2e44d72376022174972bda3` |
| `tmp/polaris_web_dist_final_visual_20261114_2246.tgz` — clean production build (`dist_final_visual_20261114_2246/`) | 35,803,118 B | `2ea84821bb82f4dc6818f434511cc56061ad0ebbd44054705c78eeb635baab5a` |
The clean build reproduces the in-place `web/dist` asset names (`index-mtC7LE4E.js`). Earlier archives are kept unchanged (Apex 20:51, backups 19:06, 20:10, 20:42, 22:31).
Checks: tsc clean; Vitest 89 pass / 1 skip; Playwright 51 pass, 1 skipped by design, 0 failed of 52; dev = production screenshots at 1440 × 900 (pixel-identical); Mac preview DOM verified; shadow pass 1.1 ms on the M5 Pro. Not committed, pushed or published.
Still open: frame rate on the Mac GPU (needs the browser pane visible); an all-region results sidecar for the V3 page 18 region table; header density vs the board.

## Final Apex directive (15 Nov 2026, 02:25 EST, Penumbra session)
Status: **not release-ready yet**. Two things must happen first:
- the browser suite must pass on the Mac GPU (two time-limit failures in the cloud, below);
- session A's 02:15 work (shape-from-shading relief) must settle.

Release status: SOURCE-BASED · UNVALIDATED. Nothing committed, pushed or published.

| Check | Result |
|---|---|
| Unit (cloud) | 98 passed, 1 skipped (needs repo-root `data/bundles/site01_…14d.json`) |
| Browser (cloud, SwiftShader) | 75 passed; 2 failed on the 60 s limit, no assertion failed. `visual-final` 1440 × 900 passes alone (55 s). `terrain-context` layer test: ~12 s per layer switch here, same on the 01:12 tree; needs the Mac run. No skips. |
| Cold launch | fixed: IPv4 binding, per-failure messages, Retry, no substitution (`docs/COLD_START_AND_PARITY.md`) |
| Guided demo | deterministic, restores the user's state (`docs/GUIDED_DEMO_VERIFICATION.md`) |
| Science consistency | all audited Site04 ROI3 values agree (`docs/SCIENTIFIC_RESULT_CONSISTENCY.md`) |
| Visual QA | five differences per V3 page 13/16/17/18/19/20, defects fixed (`docs/FINAL_VISUAL_QA.md`) |
| Performance | session A's Mac numbers; Chrome 30 Hz cap unexplained (`docs/PERFORMANCE_REPORT.md`) |

Source snapshot (not a release): `tmp/polaris_web_source_final_apex_20261115_0220.tgz`, 91,016,371 B, SHA-256
`07c6d18ca559013eb79c6820db72d9c7a48474ddba8906f683cbe7ebaf9fda68`. All earlier archives are kept unchanged.

Launch: in `web/`, run `npm run build && npm run preview` → http://127.0.0.1:4173. If port 4173 is busy, stop the other server first (a Python `http.server` was holding it at 00:45).

Before release, on the Mac (Anish):
1. `cd web && npm run build && npx playwright test`
2. `bash test_all.command`
3. `bash package_release.command`, recording the SHA-256.

Summary: `docs/FINAL_APEX_AUDIT.md`.

## Final scientific validation and release directive (15 Nov 2026, 19:05 EST, Penumbra session)

Status: **RELEASE BLOCKED** (Mac test run not yet done; no package built). Full record: `docs/FINAL_APEX_AUDIT.md` § Final scientific validation. Independent illumination validation: `docs/validation/NAC_ILLUMINATION_RESULT.md` (v2 PASS on two new areas; does not observe Site04 ROI3). Certainty sidecar rebuilt from the float64 re-run (`73792233…2472`).

**20:15 EST update:** Mac Playwright 78/79 on the tree after the opening-site change. The guided-demo Play test fails on the Mac GPU; it passed before the change. ZIP `9fc88f15…` (19:32) is stale: it predates edits at 19:34 and 19:48. Still **RELEASE BLOCKED**. Details: FINAL_APEX_AUDIT.
