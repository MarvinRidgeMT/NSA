# POLARIS X — 5D lunar model overhaul, Blender integration, GitHub push: final report (session A)

15 Nov 2026, ~21:40 EST. Release status unchanged: **SOURCE-BASED · UNVALIDATED**. No science value, bundle, sidecar or solver input
was changed by this work. Repo: https://github.com/MarvinRidgeMT/NSA, branch `b-experience`.

## Pushes (verified with `git ls-remote` in Anish's Terminal)
| Commit | What | Remote check |
|---|---|---|
| `2445253` | Checkpoint: web viewer, Blender scenes, validation (463 files, ~304 MB) | `24452534…  refs/heads/b-experience` = HEAD |
| `68621ac`, `ce03658` | Blender showcase v2, gallery, Site01 SfS offset analysis (+ concurrent Penumbra files) | `ce036581…  refs/heads/b-experience` = HEAD |
| this report | Final-state record (docs only) | see the push output pasted in chat |

No force-push, rebase, reset or stash. Excluded on purpose: the rebuilt `app/dist/polaris-file.js` (121 MB, over GitHub's 100 MB limit; the
committed copy is kept) and the 81 MB NASA SVS 8K Moon GLB (re-downloadable, SHA-checked by `test_all`).

## Deployment
- **Hosted copy (private, claude.ai artifact):** https://claude.ai/artifact/PkR5bSAVdAZuUNK4xAPu8J — **v6**, built from `ce03658` with
  `vite build --base ./`; includes the Blender gallery at `showcase/index.html`. Checked in headless Chromium: Explore opens on Connecting Ridge
  (Site01 ROI6) with NAC relief on, Decision on Shackleton Rim (Site04 ROI3), 0 failed requests, gallery page loads. It is private (owner shares it).
- **Local:** `open_web_viewer.command` / `.bat` (serves `web/dist` on 127.0.0.1:8765). Release ZIP `236c57cc…d6ae` (Penumbra's validated RC).
- **Public deployment:** none. The repo must be public for judging (Sid/Anish).

## What improved
**Terrain (web 5D viewer)**
- NASA GSFC shape-from-shading relief (Zenodo 10.5281/zenodo.17954508, CC-BY-4.0) as the 5 m display surface: 100 % of Site01, ~34 % of Site04;
  feathered into LOLA over 200 m; same constant shift on all levels so the mast meets the bundle ground.
- Three terrain levels: 5 m crop, 20 m L1 ring (±4 km), 80 m regional; fast typed-array meshes with analytic normals.
- Horizon-map shadows on every level, soft penumbra width per level (fixes the dotted mid-distance artifact in the regional view).
- Synthetic sub-5 m grain as gradient noise on the shading normal (Display mode only; labelled).
- Explore opens on Site01 ROI6; story, Decision, Evidence and the guided demo on Site04 ROI3 (`store/siteDefaults.ts`).

**Blender**
- `blender/build_from_nasa_bundle.py` / `bundle_v2.py`: SfS display surface, L1 ring, 80 m context, black sky, regolith material, low cross-lit hero.
- `blender/showcase.py` + `showcase_render.command`: regolith v2; synthetic boulder field (Geometry Nodes, Poisson, slope-weighted, ≤0.9 m,
  150 m clear of the observer, labelled VISUAL); Cycles on METAL; aerial, 1.7 m ground and low-Sun renders; 1 m vs 10 m obstruction pair at the
  bundle transition hour (states from the bundle); Draco web GLBs (~0.93 MB each, no boulders); manifest with SHA-256 of every render.
- Render review → v2 fixes: ground view no longer looks into the Sun; Site04 grey sky forced black; obstruction framing and marker size.

**Website integration**
- `web/public/showcase/` gallery (WebP + captions with bundle UTC, Sun az/el, ray states, "synthetic" note), linked from Evidence → Raw data.
  The interactive viewer is unchanged and remains the main experience.

**Science checks (unchanged label)**
- Site01 +1.97 m SfS−LOLA at the site point: analysed in `docs/validation/SITE01_SFS_OFFSET.md` — a local ~2 m, ~100 m-wide rise (crop bias +0.24 m,
  no tilt); no reference changed.
- Penumbra's gate (for context): SVS 4930 PASS (low power); NAC v1 NOT PASS (region 6), v2 PASS (Site07/Site11 ROI1); Site04 ROI3 not observed.

## Tests and performance
- Mac Playwright **79/79** (2.1 min, 21:1x EST, before `ce03658`); Vitest 99/99; Blender unit tests 31/31; `tsc` clean.
  Note: Playwright uses SwiftShader (software GL) on the Mac too.
- Chrome on the M5 Pro (Metal, AC power, Penumbra 20:18): frame mean 8.33 ms, p95 ≤ 9.1 ms, 0 long tasks.
- Blender showcase on METAL at 128 spp, 1920×1080: ~7 s per render; boulders 14,515 (Site01) / 43,592 (Site04).

## Files (main)
`blender/showcase.py`, `showcase_render.command`, `tools/showcase/build_gallery.py`, `web/public/showcase/*`,
`web/src/three/TerrainSurface.tsx`, `web/src/store/siteDefaults.ts`, `web/src/components/{SurfaceLayer,EvidenceRecord,Header}.tsx`,
`web/src/App.tsx`, `web/src/styles.css`, `tools/terrain/build_terrain_context.py`, `blender/{build_from_nasa_bundle,bundle_v2}.py`,
`open_web_viewer.command/.bat`, `docs/validation/SITE01_SFS_OFFSET.md`, `docs/BUILD_STATUS.md`, this report.
Renders: `blender/output/POLARIS_X_<site>_bundlev2_showcase_*.png`, `_showcase.blend`, `_web.glb`, `_showcase_manifest.json`.

## Known limits (honest)
1. Faint diamond pattern on the 20 m L1 ring in overhead view (horizon map too coarse for that ring).
2. No 1.75 m Certainty Height hourly series in the bundles, so the obstruction pair compares 1 m and 10 m only.
3. Site01 +2 m local SfS/LOLA difference unresolved (needs LOLA RDR shots or NAC stereo); the constant display shift leaves the far SfS surface
   ~1.7 m below LOLA on average (display only).
4. No streaming clipmap/quadtree; the 20 m ring is not in Blender.
5. Accessibility defects from axe not fixed (dangling `aria-controls="ws-sky"`, focusable children in chart SVG/polar overlay, `<p>` in `dl.three-heights`).
6. Synthetic boulders/micro-relief are presentation; they are never science inputs.
7. Validation status stays SOURCE-BASED · UNVALIDATED (Sid/Anish decision).

The harder items have a ready prompt: `docs/NEXT_WORK_PROMPT_CLAUDE_CODE.md`.
