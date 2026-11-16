# POLARIS X v2 — status (one row per phase; each session edits only its own row)

Integration branch `feature/v2-whole-moon`. Split: `docs/v2/SPLIT.md`. Started 16 Nov 2026 ~02:40 EST.

| Phase / session | Status | Tests | Results | Open items | Hours |
|---|---|---|---|---|---|
| S1 · §1 6D model + cube v2 + backlog | not started | — | — | — | — |
| S2 · §2.1 whole-Moon data inventory + downloads | not started | — | — | — | — |
| S3 · §2.2–2.3, 2.5 global pyramid, seams, coverage, roughness | **done, partial in places** (branch `claude/v2-s3-pyramid-b01622`): pyramid built for the whole Moon (sp/np/eq, 85,982 COG tiles, 71 GB, git-ignored); `science/terrain/stack.py` contract API; VISUAL relief polar only (100 tiles, sp 20 m around the pole) | `pytest tools/globe/tests science/tests`: 253 passed, 2 skipped | **Coverage (real terrain, finest native res):** ≤5 m 0.064 %, 5–20 m 0.90 %, 20–40 m 2.36 %, 40–80 m 96.54 % (SLDEM2015 86.5 %), 160–320 m 0.14 %, none 0 % (`docs/v2/COVERAGE_SUMMARY.md`). **Seams:** 20 product pairs + 2 zone seams pass (e.g. PGDA 78/PGDA 90 median 0.2–0.5 m, p99 1.2–3.3 m; LOLA polar rings p99 1.1–2.3 m after a 40-px edge trim; SLDEM/LOLA p99 22–41 m = intrinsic product disagreement); tolerances revised twice with documented causes. **Co-registration:** LOLA-family |dz| ≤ 0.28 m. **Roughness:** displayed/real RMS slope 15 m–2.56 km at 4 PGDA 78 sites 1.00–1.09 (pass); added sub-resolution relief 1.2–1.9× the real residual (open); Hurst matches PGDA 70 (0.93–0.98 vs 0.94–0.99). **Site04 RoI 3 skyline from the pyramid vs committed bundle:** median 0.000°, p95 0.0045°. **Analytics:** Moon median slope 5.1° (~1 km), 25.7 % > 10° | VISUAL eq zone; PGDA 70 as VISUAL parameter source; craters/boulders (no cited statistics); Earth-visibility map; quantized-mesh/3D Tiles; VISUAL amplitude 1.2–1.9× too strong | ~8.5 (02:25–10:55 EST, ~4 h of it paused) |
| S4 · §2.4 any-site solver | not started | — | — | — | — |
| S5 · §5 Blender v2 pipeline + proof tests | not started | — | — | — | — |
| S6 · §6.1, 6.3 imagery catalogue + pre-registered protocol | not started | — | — | — | — |
| §4 6D decision tools across the Moon | not started (after Phase 1) | — | — | — | — |
| §3 worlds: Mercury, Mars | not started (after Phase 1) | — | — | — | — |
| §6.2, 6.4–6.5 render twins + scoring | not started (after S5 + S6) | — | — | — | — |
| §7 NASA-user features + gates | not started | — | — | — | — |
