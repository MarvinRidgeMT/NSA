# POLARIS X v2 — status (one row per phase; each session edits only its own row)

Integration branch `feature/v2-whole-moon`. Split: `docs/v2/SPLIT.md`. Started 16 Nov 2026 ~02:40 EST.

| Phase / session | Status | Tests | Results | Open items | Hours |
|---|---|---|---|---|---|
| S1 · §1 6D model + cube v2 + backlog | not started | — | — | — | — |
| S2 · §2.1 whole-Moon data inventory + downloads | not started | — | — | — | — |
| S3 · §2.2–2.3, 2.5 global pyramid, seams, coverage, roughness | not started | — | — | — | — |
| S4 · §2.4 any-site solver | working, partial (legacy terrain adapter incl. S2's LOLA PDS LDEMs; S3 pyramid not yet available, shim tested) — branch `claude/v2-s4-anysite-fef161` | `science/anysite/tests` 30 pass, 1 skip (S3 pyramid absent); `science/tests` 194 pass, 2 skip (LOD tiles not built here) | Site04 RoI 3 via lat/lon only: Sun 94.362 %, Sun+Earth 72.107 %, longest hourly Sun gap 19 h, 20 clones 87.537–97.329 %, skyline identical to the committed bundle; Site01 RoI 6 100 % / 81.602 % (= bundle). M at RoI 3: PGDA 90 100 %, LOLA 5 m 65.3 %, LOLA 128 ppd 59.9 % Sun. Timing: 711 sites in 300 s (4 workers), median 1.4 s nominal; RoI 3 with 20 clones + 3 products 16.5 s; worst 26 s. Curvature limit RoI 3: 265 km for +10 786 m relief (< 280 km used). Precompute done: 4 sites, 15 landing sites, ≈1° grids poleward of 80° at both poles (0 errors, 0 truncated bins) → `data/anysite/precompute_summary.json` | pyramid-agreement test waits for S3; Artemis III regions have no published coordinates (not run); no bisection-refined events (hourly metrics); PGDA 90 ERR layer not cached (σ assumed); no error model for LOLA polar LDEMs; rerun precompute after S2's downloads finish | ~1.0 |
| S5 · §5 Blender v2 pipeline + proof tests | not started | — | — | — | — |
| S6 · §6.1, 6.3 imagery catalogue + pre-registered protocol | not started | — | — | — | — |
| §4 6D decision tools across the Moon | not started (after Phase 1) | — | — | — | — |
| §3 worlds: Mercury, Mars | not started (after Phase 1) | — | — | — | — |
| §6.2, 6.4–6.5 render twins + scoring | not started (after S5 + S6) | — | — | — | — |
| §7 NASA-user features + gates | not started | — | — | — | — |
