# POLARIS X v2 — status (one row per phase; each session edits only its own row)

Integration branch `feature/v2-whole-moon`. Split: `docs/v2/SPLIT.md`. Started 16 Nov 2026 ~02:40 EST.

| Phase / session | Status | Tests | Results | Open items | Hours |
|---|---|---|---|---|---|
| S1 · §1 6D model + cube v2 + backlog | not started | — | — | — | — |
| S2 · §2.1 whole-Moon data inventory + downloads | not started | — | — | — | — |
| S3 · §2.2–2.3, 2.5 global pyramid, seams, coverage, roughness | not started | — | — | — | — |
| S4 · §2.4 any-site solver | not started | — | — | — | — |
| S5 · §5 Blender v2 pipeline + proof tests | not started | — | — | — | — |
| S6 · §6.1, 6.3 imagery catalogue + pre-registered protocol | §6.1 orbital metadata done (partial: no surface images); §6.3 protocol pre-registered | `pytest tools/imagery` 33 passed; science/tests + tools 245 passed, 2 skipped | 7,298 images / 11,726 image×site rows. Unique images: NAC 2,292, WAC 423, ShadowCam 2,760 (footprints suspect), TC stereo 1,748, TC mono 75. Rows by site (04 RoI3 / 01 RoI6 / 07 RoI1 / 11 RoI4): NAC 528/514/742/765, WAC 420/391/331/272, ShadowCam 252/789/1580/2194, TC stereo 880/790/720/448, TC mono 35/22/41/12. **Held out 2,124** images (seed polaris-x-v2-heldout-2026-11-16). 113 NAC footprints contain the Site04 RoI 3 hero point. Protocol SHA-256 bf85659d…, catalogue 4b941d61… (`docs/v2/PREREGISTRATION.md`) | render twins + scoring; sub-spacecraft position per image; true ShadowCam footprints; surface imagery (Apollo parse; others need registration); Artemis III 2024 regions (no official coordinates); Parquet once pyarrow is installed | ~1.2 |
| §4 6D decision tools across the Moon | not started (after Phase 1) | — | — | — | — |
| §3 worlds: Mercury, Mars | not started (after Phase 1) | — | — | — | — |
| §6.2, 6.4–6.5 render twins + scoring | not started (after S5 + S6) | — | — | — | — |
| §7 NASA-user features + gates | not started | — | — | — | — |
