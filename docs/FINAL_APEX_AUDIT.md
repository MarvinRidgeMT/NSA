# Final Apex audit (15 Nov 2026)

Penumbra session, 00:33–~02:30 EST. Directive: "POLARIS X — FINAL APEX DIRECTIVE" (visual, scientific, interaction and release
stabilization of `web/`). Release status unchanged: **SOURCE-BASED · UNVALIDATED**. Nothing was committed, pushed, uploaded or
deployed. Session A was working in `web/` at the same time. Every write to the Mac was preceded by a hash check against the last
version Penumbra had read; session A's edits (URL state, StableLine, 20 m ring, perf script) were merged, never overwritten.

## Documents for this pass

| Directive name | Contents |
|---|---|
| `docs/FINAL_APEX_AUDIT.md` | this summary |
| `docs/COLD_START_AND_PARITY.md` | P1: cause of the cold-launch error, fixes, launch commands (extends PRODUCTION_PARITY.md) |
| `docs/GUIDED_DEMO_VERIFICATION.md` | P2 |
| `docs/SCIENTIFIC_RESULT_CONSISTENCY.md` | P8 (value-by-value, Site04 ROI3) |
| `docs/FINAL_VISUAL_QA.md` | P6 + P12 (five differences per page 13/16/17/18/19/20, extends PENUMBRA_FINAL_VISUAL_AUDIT.md) |
| `docs/PERFORMANCE_REPORT.md` | P10 (cites session A's Mac measurements; corrects Penumbra's 1.08 ms claim) |
| `docs/RENDERING_VALIDATION.md` | appended: correction, P3 invariance and orientation tests |
| `docs/RELEASE_READINESS.md`, `docs/BUILD_STATUS.md` | appended dated sections |

## Phase by phase

| Phase | Result |
|---|---|
| P0 preserve | Archives verified (22:46 release `aac6696a…`, dist `2ea84821…`; Anish's ZIP `63455169…`). Recovery copy `tmp/web_before_final_apex_0040.tgz`. Notices in REBUILD_PHASES. |
| P1 cold launch | **Fixed.** Causes: IPv6-only dev server binding plus a stale Python server on 127.0.0.1:4173, and silent bootstrap failures. Now IPv4 loopback binding, a specific message per failure, Retry, no substitution. 6 browser + 4 unit tests. |
| P2 guided demo | **Deterministic.** Each scene sets the full state; Exit/Esc/Finish restore the user's state; Play/Pause; Evidence link; focus handling. 4 browser tests (fresh, after site/mast switch, play/pause, reduced motion). |
| P3 renderer | Science invariance across light modes × surface layers: test passes. Horizon-map orientation vs solver skyline: unit test, best rotation 0°. LROC layer labels: product, m/px, coverage, "not mission-time lighting"; offered only where registered (not at Site04 ROI3). **Not done:** a pixel check of the GPU shadow pass (session A's file). |
| P4 cameras | **Reset view** button added. Global Moon is labelled "visual context, not numerical terrain; display lighting, not the Sun at the bundle time", and hands off with "Enter terrain →". Camera eases: existing 1.4 s, interruptible, instant under reduced motion. |
| P5 rays/ridges | 3D labels show azimuth, elevation, margin, state and controlling ridge; R1 (128 km) is "beyond this crop", never drawn inside. Consecutive ridge selections, then Return, restore the original sample and camera (test). Unchanged and still open: a terrain cross-section view. |
| P6 composition | Selectors no longer squeezed at 1440–1699 px; labels avoid the instrument; mobile overlays fixed; bottom tab bar under 640 px. Six sizes checked. |
| P7 Decision | Three heights shown separately (1 m / 1.75 m / 1.75 m) from the sidecar; coverage with the < 50 % warning beside the conclusion and on the card; card shows the 1.75 m result; "not a guarantee of power, comms or mission success". |
| P8 consistency | All audited values agree (see SCIENTIFIC_RESULT_CONSISTENCY). 337 samples / 336 intervals stated on Evidence. |
| P9 Sky/Evidence | Horizon wheel (whole-window Sun/Earth tracks, blocked samples, skyline, linear elevation scale). Evidence: five-line pipeline, "Not validated yet", dataset record with files and checksums, solver/schema/conventions, gates, assumptions, reproduction, raw-data links. |
| P10 performance | Cited from session A (pane: idle p95 9.3 ms; the per-step relink stall fixed). The headed-Chrome 30 Hz cap is unexplained and needs a rerun. No optimisation by Penumbra. |
| P11 accessibility | Tests: skip link, keyboard to the demo, focus in and out of the demo, Esc; WebGL-off fallback shows all values. New controls have labels; the scene text is announced. **Not done:** an automated WCAG contrast scan. |
| P12 art direction | Five differences per page; fixes listed in FINAL_VISUAL_QA; self-scored. |
| P13 tests | See below. No test removed; no assertion loosened. One existing test (`apex` Certainty Height selector) got a longer time limit only, with the reason in the code. |
| P14 release | **Not packaged as a release.** Session A was still changing `web/` at 02:15 (shape-from-shading relief), and the critical browser checks have not been run on the Mac GPU. A source snapshot was made instead: `tmp/polaris_web_source_final_apex_20261115_0220.tgz`, 91,016,371 B, SHA-256 `07c6d18ca559013eb79c6820db72d9c7a48474ddba8906f683cbe7ebaf9fda68` (web/ without node_modules and dist). All earlier archives are kept. The release ZIP is built by Anish's `package_release.command` after both sessions finish. |

## Tests (cloud, Chrome + SwiftShader, `vite preview` on 127.0.0.1:4173)

- Unit (Vitest): **98 passed, 1 skipped** (14 files). The skip is `scienceV2` "full Site01 a-science bundle". It needs `data/bundles/site01_2026-11-14_14d.json` at the repo root, which is not in the cloud copy; it runs on the Mac.
- Browser (Playwright, full run 01:39–02:08 EST, 77 tests in 14 files): **75 passed, 2 failed, both on the 60 s time limit, not on an assertion**:
  - `visual-final` "Explorer at 1440 × 900 …": passes when re-run alone (55.1 s).
  - `terrain-context` "surface layers are display only …" (session A's test): under SwiftShader each surface-layer switch takes 10–13 s, and it does the same on the 01:12 tree, before Penumbra's later edits. Seven layers therefore exceed 60 s. It needs the Mac GPU run, or session A's decision on a longer limit (Penumbra did not edit session A's test).
  - Previously skipped tests: none skipped in this run.
- The directive's 25 named checks map to tests as follows:

| Check | Test |
|---|---|
| cold launch, missing index, missing bundle, invalid schema, direct URL, refresh recovery, parity | `cold-launch.spec.ts` |
| demo fresh, demo after switch, reduced motion | `guided-demo.spec.ts` |
| light toggle / LROC layer invariance | `final-apex` P3 |
| ridge back | `final-apex` P5 and `apex` Ridge of Record |
| card export | `final-apex` P13 print |
| coverage warning | `final-apex` P7 and `visual-final` |
| provenance | `final-apex` P8/P9 |
| responsive | `final-apex` P6, `terrain-context` phone, `decision-evidence` widths |
| WebGL fallback | `final-apex` P11 |
| time boundaries | `final-apex` P13 |
| site and mast switching | `guided-demo` #2, `apex` Certainty Height |
| ROI export | `decision-evidence` "real ROI viewer export" |
| Global Moon | `terrain-context` globe test (session A) |
| ribbon seek | `decision-evidence` margin ribbon |

  **Fullscreen exit** has no test: the app has no fullscreen mode.
- LROC skip: `terrain-context.spec.ts` skipped its LROC test when `visual_layers.json` had no Site01 layer. The file now has one in `public/visual/`, so the test runs.

## Not done / open

- GPU shadow-pass pixel test.
- Clean headed-Chrome frame rate on the Mac.
- Automated contrast scan.
- Eleven-region decision view and per-map dots: these need an all-region batch sidecar.
- Terrain cross-section view.
- Mac-side reruns: `test_all.command`, Playwright, `perf:mac`, Blender, `package_release.command`.
- The independent illumination validation (science gate) is still NOT_RUN.

## Final scientific validation and release directive (15 Nov 2026, 17:17–19:05 EST, Penumbra session)

### Source state
- Branch `b-experience`, HEAD `8079924`; 75 tracked files changed, nothing committed.
- Recovery snapshot (17:25): `tmp/recovery_final_validation_20261115_1725.tgz`, 277,736,285 B, SHA-256 `9101488695ce8e43353216bd3746f10cc4e908006bf360c8e6a989ba8f1b8191`; `git status` in `tmp/git_status_20261115_1725.txt`.
- Changed after the snapshot (checked by diff against it):
  - session A, 17:42: the "NAC relief" toggle moved to the surface chip (`web/src/styles.css`, `web/src/components/SurfaceLayer.tsx`, `web/tests/e2e/sfs-relief.spec.ts`);
  - the Site01 ROI6 Blender rebuild, 17:54 (`blender/output/POLARIS_X_site01_roi6_bundlev2.*`);
  - `web/public/*`: rewritten by a 17:49 build with identical content except the `generated` time in `bundles/index.json`.

  These are taken into the tested tree.
- This pass changed:
  - `tools/certainty/build_certainty_sidecar.py`: new `--what`, `--solver-note` and `--repo-branch` options. With no options it reproduces the old sidecar byte for byte (SHA-256 `64c747bd…`, checked on the Mac).
  - `web/public/certainty/sidecar.json`: rebuilt from the float64 re-run, SHA-256 `73792233b0c052f6afd42dd06c6ee4dd054034c55c103e29540f6db49eee2472`. The old file is in `tmp/before_float64_fix/`.

  New files: `data/batch/2026-11-15_float64_rerun/`, `docs/validation/NAC_ILLUMINATION_RESULT.md` and `tools/validation/nac/`. `data/batch/2026-11-14/` is untouched.

### Independent validation (Phase 4): `docs/validation/NAC_ILLUMINATION_RESULT.md`
- Method: observed LROC NAC images (NASA GSFC orthorectified, Zenodo 10.5281/zenodo.17954508) against the model's lit/shadow prediction at ground points. Protocols and the pass rule were frozen by SHA-256 before each run.
- **v1, region 6 (Site01 ROI6, Site04 west): NOT PASS.** The relative-brightness rule labelled scattered light as "lit". This verdict is kept.
- **v2 + amendment A1, confirmatory, regions 8 and 9 (new terrain): PASS in both areas.**
  - Site07 ROI1: 49 images, 114,883 points. Balanced accuracy 0.976 (excluding |margin| < 0.5°), κ 0.950, 50 % crossing +0.315°.
  - Site11 ROI1: 42 images, 109,015 points. Balanced accuracy 0.983, κ 0.964, crossing +0.445°.
- Both crossings are positive, with D close to the 0.5° limit. The model errs slightly towards "lit".
- **Not observed:** the Site04 ROI3 lander point and its rise, the 1 m mast, the clone spread, Earth visibility, and the 2026 window.
- The bundle's `validation` gate is not changed: that is the science owners' decision.

### Site04 ROI3 claims (Phase 5)
- **Defect:** the 14 Nov batch sweep held terrain heights in float32. A replica of it reproduces the published summary to ≤ 0.001 points in float32. In float64:
  - Site01 ROI6: identical to the original.
  - Site04 ROI3: masts 1–1.75 m change by up to 1.8 points; 2 m and above are identical.
  - Viewer sidecar values before → after:

    | Mast | Sun nominal | Sun range | Sun+Earth nominal | Sun+Earth range |
    |---|---|---|---|---|
    | 1 m | 93.769 → **94.362** | 87.24–97.033 → **87.537–97.329** | 71.217 → **72.107** | 62.611–74.777 → **64.392–74.481** |
    | 1.25 m | unchanged | min 91.098 → 91.395 | unchanged | 68.249–78.042 → 68.546–78.338 |
    | 1.5 m | unchanged | min 96.142 → 96.439 | unchanged | min 73.887 → 74.184 |
    | 1.75 m | unchanged | unchanged | unchanged | p10 78.042 → 78.309 |
  - The 1 m nominal now equals the repo bundle sample for sample (Sun 318/337, Sun+Earth 243/337). The old note in the sidecar ("2 knife-edge hourly samples") was wrong and is replaced.
- **Unchanged and verified:**
  - Certainty Height for the team requirements: 1 m (20/20 pass, Sun ≥ 70 % and Sun+Earth ≥ 40 %).
    - No requirement fails at any sampled mast.
    - The tightest is Sun at 1 m: worst map 87.537 % against 70 % (+17.5 points). Sun+Earth at 1 m: 64.392 % against 40 % (+24.4 points).
  - 100 % Sun on all 20 maps, and Sun spread ≤ 1 point: both from 1.75 m.
    - First failing mast below that: 1.5 m. Worst map 96.439 % (3.56 points short of 100); spread 3.56 points against the 1-point tolerance.
  - Coverage: Sun 34.1 %, Earth 58.5 %, identical in float32 and float64.
  - 337 samples / 336 intervals.
  - Tile SHA-256 values equal the bundle's `dem.sourceSha256`.
- **Coverage qualifier stays:** only 34.1 % of the window's Sun horizon is set by terrain that the realizations vary. The 1.75 m conclusion covers that share, not the rest.

### Tests
- **Cloud** (Chrome + SwiftShader, after syncing the Mac tree with the new sidecar):
  - Vitest: 95 passed, 4 skipped (Site01 science bundle not in the cloud).
  - Playwright, 79 tests: 66 passed, 13 failed (12 timeouts, 1 guided-demo text check). This ran in parallel with the NAC comparison.
  - The 13 re-run alone: 6 pass, 7 fail. All 7 involve heavy 3D work: SfS relief, layer switches, the guided demo, the ROI export, URL state, the Explorer layout.
  - The two tests tried with the original sidecar fail the same way, so the change did not cause them.
  - None of this counts as a pass. The Mac GPU run decides.
- **Accessibility** (axe-core 4.14, WCAG 2.0/2.1 A+AA, 8 views, one-off script `tools/validation/a11y/axe_scan.mjs`): 0 colour-contrast violations among elements axe can decide. Text over the 3D canvas or translucent panels was left undecided (22–1,834 nodes per view), so contrast there is **not** automatically verified. Violations found (not fixed in this pass):
  - `aria-valid-attr-value` (critical): `#tab-sky` `aria-controls="ws-sky"` when the error panel replaces the workspace;
  - `nested-interactive` (serious): focusable children inside the chart `svg` and `.polar-overlay`;
  - `definition-list` (serious): `<p>` directly inside `dl.three-heights`.
- **Mac:** `tmp/final_validation_mac.command` covers `test_all`, Vitest with the Site01 bundle, build, Playwright full plus failed-only re-run, `perf:mac` and Blender. **Not yet run (19:05).**

### Release status (19:05)
**RELEASE BLOCKED** until the Mac run passes. Then at best **SOURCE-BASED · UNVALIDATED**: the NAC comparison supports the method on other terrain but does not observe the Site04 ROI3 result. No package was built, and nothing was committed, pushed or published.

### Mac results from Anish's Terminal log (recorded 15 Nov 20:15 EST, Penumbra session)
Source: the Terminal log pasted at 20:09. `tmp/final_validation_mac.command` was **not** used.

**Environment:** Apple M5 Pro, ANGLE Metal; Chrome 157.0.8103.78; Blender 5.3.0.

**Playwright** (`--workers=4`, 79 tests):

| Time (EST) | Tree | Result |
|---|---|---|
| ~17:50 | before the opening-site change | 77/79; 2 layout failures at 390 px (`final-apex` P6, `terrain-context` phone). |
| ~17:52 | same | **79/79** passed. |
| ~19:25 | after session A's opening-site change (Sid 18:15; `App.tsx`/`Header.tsx` 18:51) | 75/79. Failures: guided-demo "Play advances" (still 1/5 after 15 s), `terrain-context` image layer and global Moon (default site now Site01), `visual-final` sight lines (Earth margin of the other site). |
| ~19:40 | after `siteDefaults.ts` 19:34 | **78/79.** Failure: guided-demo "Play advances", still 1/5 after 15 s on the Mac GPU. |

- That test passed in every Mac run before the opening-site change, so this is a regression, not a slow renderer.
- At 19:48, session A raised its limit from 15 s to 25 s, citing SwiftShader. That reason does not cover the Mac failure. Until a Mac run shows the cause is fixed, this is **not counted as a pass**.

**Blender:** Site01 ROI6 (17:05, 17:19, 17:54) and Site04 ROI3 (17:11) rebuilt; GLB re-import PASS each time.

**Release ZIP:** `dist/POLARIS-X5D-SourceBuild-Mac.zip`, 374,647,391 B, 19:32, SHA-256 `9fc88f1599f6e5fbf1485b085564056ec62dcba4847099c29861121d022050ee`.
- Contains the float64 sidecar (`73792233…`).
- **Stale:** it predates `siteDefaults.ts` (19:34) and the `guided-demo.spec.ts` edit (19:48).
- Earlier ZIPs: `8b66e332…` (17:56, before the opening-site change), `634551…`, `68782a…`, `0a7c4044…`, `ae12105e…`.

**Not in the log for the current tree:** `test_all.command`, Vitest (with the Site01 bundle), `perf:mac`. The perf JSONs in the log are from 01:22–01:45 EST, on battery at 12–13 %, capped at 30 fps.

**Status: still RELEASE BLOCKED.** Next: on the current tree, run `bash tmp/final_validation_mac.command`, then `package_release.command`, then re-check the SHA-256.

## Change log
- 15 Nov 2026 02:10 EST (Penumbra session): created.
- 15 Nov 2026 19:05 EST (Penumbra session): final scientific validation section added (NAC validation, float64 re-run, axe scan, status).
- 15 Nov 2026 20:15 EST (Penumbra session): Mac results from Anish's Terminal log recorded; status unchanged (RELEASE BLOCKED).
