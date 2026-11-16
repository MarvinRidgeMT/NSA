# POLARIS X v2 — status (one row per phase; each session edits only its own row)

Integration branch `feature/v2-whole-moon`. Split: `docs/v2/SPLIT.md`. Started 16 Nov 2026 ~02:40 EST.

| Phase / session | Status | Tests | Results | Open items | Hours |
|---|---|---|---|---|---|
| S1 · §1 6D model + cube v2 + backlog | not started | — | — | — | — |
| S2 · §2.1 whole-Moon data inventory + downloads | not started | — | — | — | — |
| S3 · §2.2–2.3, 2.5 global pyramid, seams, coverage, roughness | not started | — | — | — | — |
| S4 · §2.4 any-site solver | working, partial (legacy terrain adapter; pyramid not yet wired) — branch `claude/v2-s4-anysite-fef161` | `science/anysite/tests` 21 pass, 2 skip (north-polar DEM not cached; S3 `science.terrain.stack` not present); `science/tests` 194 pass, 2 skip | Site04 RoI 3 via lat/lon only: Sun 94.362 %, Sun+Earth 72.107 %, longest hourly Sun gap 19 h, 20 clones 87.537–97.329 %, skyline identical to the committed bundle; Site01 RoI 6 100 % / 81.602 % (= bundle). New-site wall time 10–18 s with 20 members (4 sites in parallel), 7 s nominal + 20 assumed members on PGDA 90. Curvature limit at RoI 3: 265 km needed for +10 786 m relief (< 280 km used). Precompute: 4 current sites, IM-1, IM-2, south 1° grid (see `data/anysite/precompute_summary.json`) | pyramid agreement test waits for S3; north-pole run waits for a north-polar LDEM (S2); Artemis III regions have no published coordinates; 13 landing sites need SLDEM2015/LOLA global; PGDA 90 ERR layer not cached (σ assumed); no bisection-refined events | ~3.5 |
| S5 · §5 Blender v2 pipeline + proof tests | not started | — | — | — | — |
| S6 · §6.1, 6.3 imagery catalogue + pre-registered protocol | not started | — | — | — | — |
| §4 6D decision tools across the Moon | not started (after Phase 1) | — | — | — | — |
| §3 worlds: Mercury, Mars | not started (after Phase 1) | — | — | — | — |
| §6.2, 6.4–6.5 render twins + scoring | not started (after S5 + S6) | — | — | — | — |
| §7 NASA-user features + gates | not started | — | — | — | — |
