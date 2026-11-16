# Prompt for Claude Code — POLARIS X: fix the remaining limits

Paste everything below the line into Claude Code, opened in `~/Downloads/POLARIS-X5D-Blender-Codex` on Anish's Mac.

---

You are working in the POLARIS X repo (branch `b-experience`, remote https://github.com/MarvinRidgeMT/NSA). It is a lunar south-pole
landing-site viewer: a React/Three.js web app in `web/`, Python science/terrain tools in `tools/`, Blender scripts in `blender/`.
Read `docs/FINAL_REPORT_SESSION_A_2026-11-15.md`, `docs/BUILD_STATUS.md` (last three sections), `docs/SCIENTIFIC_CONTRACT.md` and
`docs/validation/SITE01_SFS_OFFSET.md` first.

## Hard rules
- Never change science values, bundles (`data/viewer/*.json`, `web/public/bundles/*`), sidecars or solver inputs to make a picture look better.
  Visibility states, margins and rays come only from the bundles.
- Terrain context packs, SfS relief, LROC imagery, grain, boulders are DISPLAY ONLY and must stay labelled as such.
- Keep the release label `SOURCE_BASED_UNVALIDATED`. Do not claim NASA validation, flight readiness, power or DSN links.
- Never fabricate NASA data. Download only public NASA/PDS/Zenodo data, record URL + SHA-256 + licence in `docs/DATA_PROVENANCE.md`.
- Git: work on a new branch from `b-experience` (e.g. `limits-fix`); no force-push, reset, rebase, stash or clean; do not delete others' files.
  Commit messages end with your attribution lines. Do not commit files over 95 MB.
- Other Claude sessions may be editing. Before editing a file, check `git status`/`git log` and the project doc
  `claude/REBUILD_PHASES_2026-11-14.md` notes; do not overwrite uncommitted work you did not make.
- After each task: `cd web && npx tsc --noEmit && npx vitest run && npm run build && npx playwright test --workers=4` must stay green
  (currently Vitest 99/99, Playwright 79/79), and `python -m pytest tools/terrain blender` (Blender tests 31/31).
  Update `docs/BUILD_STATUS.md` with a dated section (EST) per task.

## Tasks (in priority order; stop and report after each)

### 1. Diamond pattern on the 20 m L1 ring (web)
Symptom: in the Overhead camera a faint diamond/lattice pattern shows on the L1 ring (±4 km, 401² at 20 m). Cause: the L1 shadow test reads
`mid_horizon_u8.bin`, which `tools/terrain/build_terrain_context.py` builds on a 201² subsample (`mm = mid.subsample(201)`), i.e. ~40 m horizon
cells bilinearly interpolated over 20 m geometry, at k=48 azimuths.
Fix options (pick by measurement): (a) build the mid horizon map at full 401² (check build time and the context pack size; keep under ~8 MB);
(b) increase azimuth count to 64–96 for the mid map only; (c) in `web/src/three/TerrainSurface.tsx` interpolate the horizon in angle space
across the two nearest azimuths and smooth with the existing `soft` width for level 1. Do not change the 5 m level behaviour.
Acceptance: before/after screenshots at Overhead and Regional views for Site01 ROI6 and Site04 ROI3 in `web/docs/screenshots/limits/`;
pattern gone at 1440×900; frame time on the Mac (`npm run perf:mac`) not worse than mean 8.33 ms / p95 9.1 ms by more than 10 %.
Rebuild packs with `python tools/terrain/build_terrain_context.py`, then copy them as the build does; record new SHA-256s.

### 2. 1.75 m Certainty Height hourly series (science pipeline, needs Sid/Anish OK before merging)
The ROI bundles only have `baseline` (1 m) and `mast10` scenarios. Add a `mast1p75` scenario computed by the **existing** solver with the same
inputs, method and float64 settings that produced the others (find the producer named in `derived.producer` in the bundle; do not write a new
solver). Store it as a new scenario in a NEW bundle version file (do not edit the v2 file in place), with its own SHA-256 and producer record.
Then: show 1.75 m in the web mast selector and add an `obstruction_mast1p75m` render in `blender/showcase.py` using the bundle ray state.
Acceptance: the 1 m and 10 m values in the new bundle are bit-identical to v2; a Vitest test proves it; Sid or Anish signs off in the PR.

### 3. Site01 +2 m SfS vs LOLA (validation, display)
(a) Download LOLA RDR shot points (PDS Geosciences Node, LOLA RDR query tool, public) within 1 km of the Site01 ROI6 site point
(projected coords in the ROI bundle `site.projectedMeters`; polar stereographic as in PGDA 78). Compare SfS and the PGDA 78 5 m LOLA DEM to the
shots: bias, rms, and the mean in 0–50 m / 50–250 m rings. Write `docs/validation/SITE01_SFS_OFFSET_RDR.md`. Do not change any reference.
(b) Prepare (do not merge without Sid/Anish) a display change: shift by the crop bias instead of the site-point value and blend SfS back to LOLA within
100 m of the observer, in both `tools/terrain/build_terrain_context.py` and `blender/bundle_v2.py`. Keep the mast foot on the bundle ground.

### 4. Terrain streaming and Blender ring
(a) Replace the fixed 3-level mesh set with a clipmap or quadtree LOD around the camera target in `TerrainSurface.tsx`, using the same packs; no
cracks between levels (skirts or stitched edges); test on the 390 px phone layout too. (b) Add the 20 m L1 ring to the Blender hero scene
(`blender/build_from_nasa_bundle.py`, `--mid-ring`), cut under the 5 m crop, labelled DISPLAY ONLY. Measure frame time before/after.

### 5. Accessibility (axe)
Fix: dangling `aria-controls="ws-sky"` on the error panel; focusable children inside chart SVG and the polar overlay (make the container focusable
once, children `tabindex=-1`/`aria-hidden` as appropriate); `<p>` inside `dl.three-heights` (use `dd`). Add an axe check to Playwright
(`@axe-core/playwright`, no paid service) that fails on serious/critical issues for Story, Explore, Decision, Evidence.

### 6. Ground-level Blender render polish
In `blender/showcase.py` the ground view still shows the Sun-ray and eye-marker objects large. Option: for the ground render only, scale the ray
cylinders' radius to 25 % and the eye sphere to 40 % (clear animation data on a copy first), or hide them and add a thin emissive line instead.
Re-run `SHOWCASE_ARGS="--samples 128" bash showcase_render.command` then `python tools/showcase/build_gallery.py`; check the images by eye.

## Final step
Push the branch (no force), verify with `git ls-remote origin refs/heads/limits-fix`, and open a PR into `b-experience` listing per task: what
changed, test counts, before/after screenshots, performance numbers, and anything that needs Sid/Anish sign-off.
