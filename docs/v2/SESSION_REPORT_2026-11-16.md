# POLARIS X v2 — session report, 16 Nov 2026 (overnight run, ~02:40–11:30 EST)

Integration branch `feature/v2-whole-moon` (worktree `../NSA-v2`), cut from `feature/5d-complete` (ae9f6d9). Six sessions
ran in parallel on their own branches; all six are merged. Nothing is pushed.

## Phases done or partial
| Session | § | Status |
|---|---|---|
| S1 6D model + cube v2 | §1 | done: `docs/v2/6D_MODEL.md` (XLRM), `scenario-cube-v2` with roles, v1→v2 migration (28 cubes, every value identical), slicer grouped "What we don't know" / "What we choose", `BACKLOG.md` (open P0: B1, B2) |
| S2 whole-Moon data | §2.1 | done for public no-login products: 105.93 GB, 172 files, re-hashed 172/172 |
| S3 global pyramid | §2.2–2.3, 2.5 | done, partial in places: 85,982 COG tiles for the whole Moon, seam/coverage/roughness QA; VISUAL relief polar only and 1.2–1.9× too strong (open) |
| S4 any-site solver | §2.4 | done on the per-product adapter (exact Site04 RoI 3 reproduction, 711 sites precomputed); merged-pyramid path opt-in, integration gaps listed below |
| S5 Blender v2 | §5 | partial: close-up builder + Blender-proof tests done; whole-Moon base mesh, pyramid tiles in Blender, WAC/NAC albedo, Mercury/Mars not done |
| S6 imagery | §6.1, 6.3 | orbital catalogue done, protocol pre-registered; render twins, scoring and surface imagery not started |
| §4 decision tools, §3 worlds, §6.2–6.5 scoring, §7 NASA-user features | — | not started (ordered after Phase 1) |

## Test results on the merged branch (b4ca107 + this report)
pytest `science/tests science/anysite tools` 580 passed, 2 skipped (LOD tiles not built in this worktree); Blender
`run_all.py` 11/11; Blender unit tests OK; vitest 147/147; build OK; Playwright 96 passed, 2 skipped, 2 failed = the
known artefacts (`cold-launch` hard-codes port 4173; final-apex P6 passes when run alone); traceability 541 scanned,
0 untraced.

## Coverage of the Moon by resolution class (real terrain, finest native resolution; `COVERAGE_SUMMARY.md`)
≤ 5 m 0.064 % · 5–20 m 0.90 % · 20–40 m 2.36 % · 40–80 m 96.54 % (SLDEM2015 86.5 %) · 160–320 m 0.14 % · none 0 %.

## Seam and roughness QA
- Seams: 20 product pairs + 2 zone seams pass (PGDA 78/PGDA 90 median 0.2–0.5 m, p99 1.2–3.3 m; LOLA polar rings
  p99 1.1–2.3 m after a 40-px edge trim; SLDEM2015/LOLA p99 22–41 m = intrinsic product disagreement). Tolerances were
  revised twice, each with a documented cause (`docs/v2/PYRAMID_QA.json`).
- Co-registration: LOLA-family |dz| ≤ 0.28 m.
- Roughness: displayed vs real RMS slope (15 m–2.56 km) 1.00–1.09 at the four PGDA 78 sites (pass); the added VISUAL
  sub-resolution relief is 1.2–1.9× the real residual (OPEN); Hurst exponent matches PGDA 70.
- Site04 RoI 3 skyline from the pyramid vs the committed bundle (S3's check): median 0.000°, p95 0.0045°.

## Render-vs-real
No scores yet (render twins not built). Catalogue: 7,298 orbital images (NAC 2,292, WAC 423, ShadowCam 2,760 with
suspect footprints, Kaguya TC 1,823), 2,124 held out; 113 NAC footprints contain the Site04 RoI 3 hero point. Protocol
SHA-256 bf85659d…, catalogue 4b941d61… (re-checked after merge: unchanged).

## Data downloaded
105.93 GB new in 172 files, all in `$POLARIS_DATA/v2/manifest.jsonl` and `docs/v2/DATA_MANIFEST.json`: SLDEM2015
512 ppd 45.30 GB; LOLA polar LDEMs 5–60 m 37.27; PGDA 67 slope/azimuth 10.61; LROC WAC 100 m 5.96; LOLA global LDEM
16/64/128 ppd 5.37; LOLA roughness 1.31; PGDA 70 0.11. Pyramid tiles 71 GB (derived, git-ignored). Disk free 285 GB.
Not downloaded: Chandrayaan-2 TMC-2 (ISRO PRADAN) and CNSA data (need accounts nobody approved); Kaguya TC DTMs, NAC
DTMs, SfS stream on demand. JAXA SELENE acknowledgement wording not verified (DARTS rejected scripted requests).

## Integration fixes made by the coordinator
- `science/anysite`: S3's `ZoneDEM.layers` (a dict of per-pixel bands) was read as a list of sub-DEMs, and its
  vectorised `coverage()` was serialised as arrays; both fixed.
- The any-site solver defaults to the per-product adapter. With the merged pyramid as default it lost the PGDA 78 clones
  and product members, its near field changed (12.5 km window vs the 5 m tile's 6.317 km) so Site04 RoI 3 no longer
  equalled the bundle, and eq-zone `local-stere` windows were not understood. The pyramid is opt-in
  (`POLARIS_ANYSITE_STACK=pyramid`) until that integration is done.

## What is NOT done
Pyramid as the solver's default terrain; VISUAL relief amplitude and the eq zone; crater/boulder populations (no cited
statistics yet); Earth-visibility global map; quantized-mesh / 3D Tiles; Blender whole-Moon mesh, pyramid tiles,
albedo; render twins and all render-vs-real scores; surface imagery; Artemis III regions (NASA publishes no
coordinates); §3 Mercury/Mars; §4 whole-Moon decision tools; §7 NASA-user features and gates; open backlog P0s B1/B2.

## Submission check
tag `submission-2026-11-15` → c5dce9f, tag `submission-final` → 8dde4f1, `submission/merged` → 62cc7b1, `main` →
8dde4f1: all unchanged since the start of this session. `feature/5d-complete` → ae9f6d9 (unchanged).
