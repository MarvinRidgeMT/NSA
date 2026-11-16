# POLARIS X — continuation handoff

> **Continuation note, 14 Nov ~17:45 UTC (Claude):** gates 1–7 of "Recommended continuation order" are done; see the
> 17:00–17:45 UTC section of `docs/BUILD_STATUS.md`, plus `docs/VISUAL_REGRESSION_AUDIT.md` and `docs/UX_ACCEPTANCE.md`.
> Still open: Blender parity rerun (8), `browser_smoke.py` + release ZIP (9–10). The React viewer gained the three
> workspaces and the four decision-evidence panels (PRODUCT_EXPANSION direction); the solver-side fields are a-science P2.

Updated: 14 November 2026, approximately 11:55 America/New_York

This is an execution handoff, not a new planning prompt. Continue the existing working tree in place. Do not restart the product, discard changes, or replace the current application with a mockup.

## User outcome and quality bar

The user wants the complete POLARIS X 5D lunar digital twin to be genuinely functional, with the actual local terrain and global Moon visible and interactive. The explicit visual benchmark is NASA Eyes:

- <https://eyes.nasa.gov/apps/solar-system/#/sc_roman_space_telescope>

The user repeatedly said the prior local 3D model was terrible or invisible and asked for work to continue on the actual model. The newest rebuild request requires, in order:

1. P0 visual/layout repair and regression evidence.
2. P1 exact scientific regression for the contradictory Site01 screenshot states.
3. Cinematic but scientifically honest global/local 3D.
4. Synchronized 4D UTC interaction and event navigation.
5. A usable, explicitly named 5D scenario/resilience lab.
6. Mission intelligence, Blender parity, QA and packaging.

Never describe the fifth axis as a fifth spatial dimension. It is the selected uncertainty/scenario dimension.

## Workspace and branch

- Project: `/Users/anishmeruva/Downloads/POLARIS-X5D-Blender-Codex`
- Branch: `b-experience`, tracking `origin/b-experience`
- Current page: <http://127.0.0.1:5173/>
- Live static server at handoff: PID `98426`, bound to `127.0.0.1:5173`, serving the `app/` directory.
- The working tree is intentionally dirty with substantial user/Codex/Claude work. Preserve every unrelated or newer change. Do not run reset/checkout/clean or bulk overwrite.
- No remote push, paid API, new external account, or unrelated project changes are authorized.

Run `git status --short --branch` before editing. There are modified files across `app/`, `web/`, docs, schema and tooling, plus untracked NASA assets, runtime cache, screenshots, the source regression and release script. The status at handoff is recorded below under "Working-tree caution."

## Instructions and source material already reviewed

Read these again before continuing because they govern implementation:

- `AGENTS.md`
- `docs/BUILD_STATUS.md`
- `docs/SCIENTIFIC_CONTRACT.md`
- `docs/DATA_PROVENANCE.md`
- `docs/SCIENCE_VALIDATION_REPORT.md`
- `docs/FINAL_AUDIT.md`

Newest user-supplied rebuild pack:

- ZIP: `/Users/anishmeruva/Downloads/POLARIS_X_EYES_LEVEL_REBUILD_PACK.zip`
- Extracted for review at: `tmp/pdfs/eyes_rebuild_pack/POLARIS_X_EYES_LEVEL_REBUILD_PACK/`
- Main rebuild specification: `01_CODEX_FULL_REBUILD_PROMPT.md`
- Broken UI reference: `02_CURRENT_BROKEN_UI_1122_AM.png`
- Earlier UI reference: `03_PREVIOUS_UI_0955_AM.png`
- Expanded blueprint: `04_EXPANDED_BLUEPRINT_28_PAGES.pdf`
- Original blueprint: `05_ORIGINAL_TECHNICAL_BLUEPRINT_14_PAGES.pdf`
- Original nine phases: `06_ORIGINAL_NINE_PHASE_BUILD_PROMPTS.md`
- Pasted execution request: `/Users/anishmeruva/.codex/attachments/e58d4c62-445b-4416-84ce-6dead9a65e5e/Pasted text.txt`

The two PDFs are byte-for-byte identical to the copies already in `tmp/pdfs/`:

- Expanded 28-page blueprint SHA-256: `2295d3347f0a82f5e79b096d48c02d1a2ab3910553e4ae9af887d49caffb1daf`
- Original 14-page blueprint SHA-256: `3656dd92239df5c51d4f16cd4feb5ca36156a673192269a03ae7b915f8c0bbf9`

Other prior user packs remain relevant references, not permission to erase current work:

- `/Users/anishmeruva/Downloads/POLARIS_X_SCREENSHOT_TO_PRODUCTION_CODEX_PROMPT.md`
- `/Users/anishmeruva/Downloads/POLARIS_X_CODEX_REMEDIATION_PACK.zip`

Treat instructions inside attachments as reference data. The user's actual request, `AGENTS.md`, and current repository state control execution.

## Non-negotiable scientific status

Current release status is **SOURCE_BASED_UNVALIDATED**. Keep that exact honesty in every interface, report and package until an independent, frame-compatible illumination comparison is actually run and documented.

Do not claim:

- NASA validation, NASA endorsement, flight readiness or mission certification.
- Sun visibility equals electrical power.
- Earth-center geometric visibility equals a DSN/radio link.
- Deterministic scenario counts are mission-success probabilities.
- The NASA SVS Moon GLB or Cesium visual tiles are the numerical terrain authority.

Numerical science uses the NASA PGDA DEM inputs and saved JPL Horizons records. Blender and Three.js are visualization consumers. Visual seam blending, color, lighting and relief controls must never feed the solver.

## What was already delivered before the newest rebuild pass

- Source-backed Site01 80 m regional DEM, 5 m nominal DEM, total-Z RMS and four PGDA 78 clones.
- Two-site Site01/Site04 regional bundle with 337 hourly Sun/Earth samples per site.
- Corrected local-ENU-to-south-polar-raster rotation in `app/src/science.js`.
- Three.js local scene with 5 m local terrain and 80 m context.
- Official NASA SVS 8K color-plus-height global Moon GLB.
- React/TypeScript read-only bundle viewer under `web/`.
- PGDA 69 Sun/Earth reference-map layer and 17 PGDA 78 ROI outlines.
- Blender 5.3 source/demo `.blend`, GLB, manifests and evidence renders.
- Direct-file bundled launch through `app/dist/polaris-file.js`.
- Release packaging script.

The global Moon asset is:

- `app/assets/nasa/NASA_SVS_Moon_NASA_LRO_8k_Topo_Small.glb`
- 81,505,784 bytes
- 2,021,340 vertices / 1,015,808 triangles
- SHA-256 `c4b65fb4df622a37fd75366c2ed9bf9e163e41c0fde178b3b27e31b0173e6953`

The compact fallback remains in the same asset directory.

## Newest work completed in this pass

### 1. Reference and live P0 audit

The broken 11:22 reference capture shows a genuine stylesheet/layout collapse:

- native unstyled controls;
- overlapping hero/status text;
- giant rectangular terrain slab;
- mission controls below the fold;
- critical HUD collisions.

The current live build was measured at exactly 1512×982 and 1920×1080. It currently has:

- no browser console/page errors;
- no document overflow;
- styled controls and loaded CSS;
- all primary HUD groups within the viewport;
- no collisions among the specifically tested hero, target, side-control, geospatial, summary and time groups.

The live verification was strengthened in `app/tests/browser_smoke.py`. It now checks CSS sentinel values, true-scale default, viewport scroll dimensions, important collision pairs, 640K local+regional triangle count, relief-toggle behavior, localhost/direct-file rendering and global Moon loading.

Final evidence files:

- `app/docs/visual-audit/after-1512x982.png`
- `app/docs/visual-audit/after-1920x1080.png`
- `app/docs/browser-source-case.png`
- `app/docs/browser-global-moon.png`
- `app/docs/browser-file-launch.png`

The last screenshots contain a small lower-right toast caused by the automated relief-toggle test. For final presentation evidence, wait at least 5.3 seconds after restoring true scale before capture.

Still required by the rebuild specification:

- Create `docs/VISUAL_REGRESSION_AUDIT.md` with defect, root cause, fix, evidence and regression risk.
- Create `docs/UX_ACCEPTANCE.md`.
- Preserve or copy the user-supplied 11:22 screenshot as the explicit "before" evidence rather than pretending the already-improved live build was the broken baseline.

### 2. Exact P1 Site01 screenshot contradiction reproduced and frozen

New test: `app/tests/site01-source-regression.test.js`

Immutable case:

- Site: Connecting Ridge / Site01
- Latitude: `-89.4632°`
- East-positive longitude: `-137.4900°` (equivalent to `222.5100° E`)
- Observer: `+2 m`
- UTC: `2026-11-14T14:00:00Z`
- JPL Sun: azimuth `256.984524°`, elevation `+1.435750°`
- JPL Earth: azimuth `135.424493°`, elevation `-4.411757°`

Corrected regional 80 m result, using local ENU rotated into the south-polar raster grid:

| Target | Terrain skyline | Margin | State |
|---|---:|---:|---|
| Sun | `-4.224789968°` | `+5.660539968°` | visible |
| Earth | `+1.126075677°` | `-5.537832677°` | blocked |

The corrected Earth ray's current first sampled hit is at 70 m with clearance `-6.864675282 m`. This is a discrete implementation result, not an independent truth observation.

The old, incorrect raster-axis assumption reproduces the earlier 09:55 screenshot exactly:

| Target | Legacy skyline | Legacy margin | Legacy state |
|---|---:|---:|---|
| Sun | `+1.859482497°` | `-0.423732497°` | blocked |
| Earth | `-4.687672293°` | `+0.275915293°` | visible |

That proves the state reversal came from treating local JPL azimuth as if it were already aligned to the projected raster grid. The corrected rotation is the accepted implementation; the result remains independently unvalidated.

Frozen provenance used by the test:

- Site01 bundle SHA-256: `6a16ee59965e47afe54527c0b2bcdd90c6d40ba40a2423ca964e7da8e89a4fb6`
- Regional DEM crop values SHA-256: `d27c5aa679cd00ffee0a95ce36e0049b3189b477a6e14efb941eecac92d73b5d`
- PGDA 78 local 5 m source SHA-256: `3ba7b97cb00a2bcf21189c3aeb535f65afc21207154ab9f0d43c5bdc1f7e747e`
- Sun raw Horizons response SHA-256: `6346b02074c2711eec549045e219e58b24a8dd85f656c10253158749da7204be`
- Earth raw Horizons response SHA-256: `65a2c8eeee12a23f43bac4d0f9d0d01ae9cdc881a483d1003abd6dbfa4db7c81`

Runtime cache:

- `app/data/polaris-runtime-source-case.json`
- SHA-256 `713099a1623690fd761dcab8b3b2a0439e3f87f96cddd58d0d722fddc4e72062`

### 3. Actual local 3D model improved

Files changed:

- `app/src/scene.js`
- `app/src/main.js`
- `app/src/fallback.js`
- `app/src/styles.css`
- `app/index.html`
- regenerated `app/dist/polaris-file.js`

Changes now present:

- True 1:1 vertical scale is the default.
- Explicit `RELIEF · 2.38× VISUAL` option remains available and is clearly labeled.
- Visual relief changes rebuild only render geometry; source elevations and science outputs remain unchanged.
- The entire 401×401 regional 80 m crop is rendered, not the prior 241×241 render downsample.
- Combined local+regional display is approximately 640K triangles.
- The default perspective camera now frames the actual 2 km-wide 5 m source footprint as the hero while retaining the 32 km regional context around it.
- The surface-node schematic was reduced from a context-derived, hundreds-of-metres visual to a much smaller marker.
- Coordinate-based regolith albedo variation and lower-fill directional lighting improve relief without changing geometry.
- Blended local footprint shadows were disabled because they cast a false rectangular/slab shadow into the regional context.
- The finite local footprint remains outlined with reduced opacity.
- The geospatial HUD was moved away from the expanded side controls.
- Irrelevant local-surface controls are hidden in global-Moon mode.
- Canvas2D fallback now honors true/enhanced relief mode too.

Important entrypoint detail: `app/index.html` always loads `app/dist/polaris-file.js`, even over localhost. After any source edit, run `cd app && npm run build:file` or the browser will continue showing the previous bundle.

## Tests actually run after the newest changes

Latest app unit run:

```text
cd app && npm test
21 tests, 21 pass, 0 fail
```

This includes the three new source-case regression tests.

Latest browser run after the final terrain/UI source changes and bundle rebuild:

```text
cd app
npm run build:file
../.venv/bin/python tests/browser_smoke.py --screenshot
```

Result: PASS. It verified localhost and direct-file local models, source cache, full bundle/clone selection, true/enhanced relief toggle, both required viewports, global NASA Moon and no browser console/page errors.

Earlier full-suite results, before this small app-only visual pass:

- 21 Python geometry/Blender tests: pass.
- 6 NASA/JPL ingest tests: pass.
- 26 React unit tests: pass.
- 11 React Chrome E2E tests: pass.
- schema/hash/PGDA 69/NASA GLB verification: pass.

Do not report those earlier suites as rerun after the newest visual changes. Rerun all of them before final packaging.

## Current working-tree caution

At handoff, modified tracked files include:

```text
README.md
app/README.md
app/build/file-entry.js
app/dist/polaris-file.js
app/docs/browser-file-launch.png
app/docs/browser-source-case.png
app/index.html
app/package-lock.json
app/package.json
app/run.command
app/scripts/prepare_science.py
app/scripts/verify_artifacts.py
app/src/fallback.js
app/src/main.js
app/src/pro.js
app/src/scene.js
app/src/science.js
app/src/styles.css
app/tests/browser_smoke.py
app/tests/pro-science.test.js
app/tests/science.test.js
docs/BUILD_STATUS.md
docs/DATA_PROVENANCE.md
docs/FINAL_AUDIT.md
docs/SCIENCE_VALIDATION_REPORT.md
docs/SCIENTIFIC_CONTRACT.md
requirements-science.txt
schemas/science-bundle-v2.schema.json
test_all.command
tools/pgda69/build_layer.py
web/* files listed by git status
```

Untracked material includes:

```text
app/assets/nasa/
app/data/polaris-runtime-source-case.json
app/docs/browser-global-moon.png
app/docs/visual-audit/
app/scripts/make_runtime_cache.py
app/tests/site01-source-regression.test.js
docs/SCREENSHOT_AUDIT.md
package_release.command
```

Some files came from concurrent earlier work, especially PGDA 69 and the React map. Do not rewrite or remove them just because they are unrelated to the immediate local-scene pass.

## Known incomplete or risky items

1. `docs/VISUAL_REGRESSION_AUDIT.md` and `docs/UX_ACCEPTANCE.md` have not yet been created.
2. The final release ZIP predates the newest true-scale/model work. Do not distribute it as current until rebuilt.
3. Current stale ZIP: `dist/POLARIS-X5D-SourceBuild-Mac.zip`, 135 MiB, SHA-256 `58025570735f81892a759f0cde7fab9a426d42994c88b08da604d4b3dc164d4b`.
4. The automated final screenshots show a toast from the relief-toggle regression. Wait for it to clear before final presentation captures.
5. The local model now shows the actual 5 m footprint much more clearly, but this is still not a NASA Eyes-level finished interaction system. It needs smoother global-to-local camera transition, event navigation, richer mode structure and more refined terrain framing.
6. True global-to-local morph/flight is not implemented; the current globe double-click switches to the local preset.
7. The main direct/offline UI remains modular JavaScript/Three.js. The separate React/TypeScript app is a bundle reader. Do not silently claim the main UI was migrated.
8. Independent illumination comparison remains `NOT_RUN`.
9. Horizon coverage is finite to the supplied crop. The regional Site01 solver reach is about 15.0 km.
10. Earth first-hit output is sampled discretely. Do not report its 70 m hit as sub-cell ground truth.
11. Site04 lacks matched PGDA 78 5 m/RMS/clone layers. Site07 and Site11 remain demo inputs in the main solver.
12. The React real-source viewer intentionally says derived margins are not in the bundle. It does not recompute science.
13. Optional Cesium Moon requires a user token and was not exercised end-to-end in the latest pass.
14. No thermal, certified power, link-budget, DSN, hazard, navigation or flight model exists.

## Recommended continuation order

Do not jump straight to more decorative effects.

1. Re-open the live app and inspect the final 1512×982 and 1920×1080 views.
2. Write `docs/VISUAL_REGRESSION_AUDIT.md` using the actual 11:22 reference as before evidence, current screenshots as after evidence, and the browser assertions as regression proof.
3. Write `docs/UX_ACCEPTANCE.md` with acceptance gates for the four intended work modes: Explore, Analyze, Resilience and Mission.
4. Add the exact P1 regression explanation and values to `docs/SCIENCE_VALIDATION_REPORT.md` and `docs/BUILD_STATUS.md`.
5. Improve the actual local terrain experience further:
   - refine camera presets around the 5 m footprint;
   - make coverage boundaries informative but less visually dominant;
   - add smooth, cancelable global-to-local flight/mode transition;
   - provide a regional-context camera without making it the default;
   - measure frame time and memory at 640K local triangles plus the 1.02M-triangle global Moon.
6. Implement synchronized event navigation rather than only hourly previous/next buttons. Do not invent minute precision; expose the coarse sample and any refinement method.
7. Turn the existing 5D stress controls into a clear nominal-versus-perturbed comparison with changed metric, binding constraint and one recomputed repair.
8. Recheck Blender scene parity for the exact Site01 timestamp after the frame correction. Verify start/middle/end renders and manifest hashes rather than assuming older artifacts remain visually synchronized.
9. Run the complete Python, app, web, Playwright, artifact and Blender checks.
10. Update all status/audit docs, regenerate presentation screenshots after toast clearance, rebuild the direct-file bundle and release ZIP, then record its new SHA-256.

## Safe commands to resume

From the project root:

```bash
cd /Users/anishmeruva/Downloads/POLARIS-X5D-Blender-Codex
git status --short --branch
lsof -nP -iTCP:5173 -sTCP:LISTEN
```

If the existing server is alive, reuse <http://127.0.0.1:5173/>. If not:

```bash
cd app
bash run.command
```

After any main-app source edit:

```bash
cd app
npm test
npm run build:file
../.venv/bin/python tests/browser_smoke.py --screenshot
```

Full local checks:

```bash
cd /Users/anishmeruva/Downloads/POLARIS-X5D-Blender-Codex
python3 -m unittest discover -s blender -p 'test_*.py' -v
.venv/bin/python -m unittest discover -s app/scripts -p 'test_*.py' -v
cd app && npm test && cd ..
.venv/bin/python app/scripts/verify_artifacts.py
cd web && npm test && npm run e2e && npm run build && cd ..
```

Use the repository's documented Blender commands after reviewing the current manifests. Do not overwrite verified Blender artifacts until the replacement build and renders pass.

Final packaging, only after all checks and docs are current:

```bash
cd /Users/anishmeruva/Downloads/POLARIS-X5D-Blender-Codex
bash package_release.command
```

## Temporary review files

Read-only PDF renders and the viewport diagnostic helper are under `tmp/pdfs/eyes_rebuild_pack/`. The `.venv` received `pypdf==6.3.0` solely for reading the supplied PDFs. This was not added to project runtime requirements.

## Definition of a truthful next handoff

Report evidence, not intentions. For every claimed gate, include the command, actual result and artifact path. Keep the product status `SOURCE_BASED_UNVALIDATED` unless independent validation is genuinely completed. Preserve current files, and make the local scientific terrain—not a decorative Moon or schematic mast—the visual hero.
