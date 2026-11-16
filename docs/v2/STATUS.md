# POLARIS X v2 — status (one row per phase; each session edits only its own row)

Integration branch `feature/v2-whole-moon`. Split: `docs/v2/SPLIT.md`. Started 16 Nov 2026 ~02:40 EST.

| Phase / session | Status | Tests | Results | Open items | Hours |
|---|---|---|---|---|---|
| S1 · §1 6D model + cube v2 + backlog | **done** (§1); §4 decision panels not started | pytest science/tests 405 passed, 2 skipped (LOD tiles not built in this worktree), incl. new `test_cube_v2.py` 211; vitest 147/147; build OK; Playwright cube-slicer, cube-slicer-roles, cube-views, traceability 8/8 on :4201 (541 scanned, 0 failed) | `scenario-cube-v2` schema + `science/cube/v2.py` + `scenarioCubeV2.ts`; all 28 committed cubes migrate with every value identical; slicer grouped "What we don't know" / "What we choose"; `6D_MODEL.md`, `BACKLOG.md` (P0 open: B1 copy tests, B2 ZIP checksum) | `D_relay` split of `target`; robust/regret/VoI panels (§4); backlog fixes belong to web/release owners | ~1.3 |
| S2 · §2.1 whole-Moon data inventory + downloads | not started | — | — | — | — |
| S3 · §2.2–2.3, 2.5 global pyramid, seams, coverage, roughness | not started | — | — | — | — |
| S4 · §2.4 any-site solver | not started | — | — | — | — |
| S5 · §5 Blender v2 pipeline + proof tests | not started | — | — | — | — |
| S6 · §6.1, 6.3 imagery catalogue + pre-registered protocol | not started | — | — | — | — |
| §4 6D decision tools across the Moon | not started (after Phase 1) | — | — | — | — |
| §3 worlds: Mercury, Mars | not started (after Phase 1) | — | — | — | — |
| §6.2, 6.4–6.5 render twins + scoring | not started (after S5 + S6) | — | — | — | — |
| §7 NASA-user features + gates | not started | — | — | — | — |
