# POLARIS X v2 — status (one row per phase; each session edits only its own row)

Integration branch `feature/v2-whole-moon`. Split: `docs/v2/SPLIT.md`. Started 16 Nov 2026 ~02:40 EST.

| Phase / session | Status | Tests | Results | Open items | Hours |
|---|---|---|---|---|---|
| S1 · §1 6D model + cube v2 + backlog | not started | — | — | — | — |
| S2 · §2.1 whole-Moon data inventory + downloads | not started | — | — | — | — |
| S3 · §2.2–2.3, 2.5 global pyramid, seams, coverage, roughness | not started | — | — | — | — |
| S4 · §2.4 any-site solver | not started | — | — | — | — |
| S5 · §5 Blender v2 pipeline + proof tests | **partial (close-up builder + proof done; global base mesh / S3 pyramid / albedo not done)** — branch `claude/v2-s5-blender-9fbc79` | `blender -b -P blender/tests/run_all.py` 11/11; `python3 -m unittest discover -s blender` 102 OK; science pytest 194 passed 2 skipped; vitest 141/141 | `blender/v2/build_scene.py --world moon --lat --lon --utc --camera` (Sun disc from Horizons angular radius, Earth phase + earthshine MODEL, SVS 4851 stars, Hapke 2012 nodes with LROC WAC 643 nm map params, NAC/WAC/ShadowCam/Kaguya TC/EVA/lander presets, physical exposure); Hapke nodes = Python to 1.3e-6; rebuild = reference bit-identical; drawn terrain vs solver skyline median 0.0014 deg (site01_roi6); 3 bugs found by the checks and fixed (half-pixel DEM shift, 180 deg star RA, black backlit facets) | S3 pyramid adapter untested end to end; cube-sphere global mesh, 3D Tiles, WAC/NAC albedo, Mercury/Mars, SVS globe replacement; Kaguya TC optics unverified; see `docs/v2/PHASE_4_BLENDER_RESULTS.md` §7 | ~1.5 |
| S6 · §6.1, 6.3 imagery catalogue + pre-registered protocol | not started | — | — | — | — |
| §4 6D decision tools across the Moon | not started (after Phase 1) | — | — | — | — |
| §3 worlds: Mercury, Mars | not started (after Phase 1) | — | — | — | — |
| §6.2, 6.4–6.5 render twins + scoring | not started (after S5 + S6) | — | — | — | — |
| §7 NASA-user features + gates | not started | — | — | — | — |
