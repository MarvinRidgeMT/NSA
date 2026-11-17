# Phase 5 · R4 — render twins and scoring on the training (`dev`) split: plan

Session R4 of round 2, 16 Nov 2026 (started ~11:45 EST), branch `claude/v2-r4-render-vs-real-ab0c1a` (already contains 72e3430,
so no new branch was cut). Prompt §6.2, §6.4–6.5 of `docs/v2/inputs/CLAUDE_CODE_PROMPT_6D_worlds_blender_v2.md`. Protocol:
`docs/v2/RENDER_VS_REAL_PROTOCOL.md` (frozen, SHA-256 bf85659d…); catalogue `imagery/catalogue.csv.gz` (frozen, 4b941d61…).
Owned paths (`docs/v2/SPLIT_ROUND2.md`): `tools/imagery/**`, `tools/validation/render_vs_real/**`,
`docs/validation/RENDER_VS_REAL.md` (+ its gallery folder `docs/validation/render_vs_real/`), `web/src/components/RealVsModel*.tsx`.

"Training split" in the round-2 brief = `split = dev` in the frozen catalogue. **No held-out image is fetched, rendered, looked
at or scored.** A test fails if any held-out product id appears in any R4 output.

## 0. What already exists / what was checked before writing this

| Item | Finding (16 Nov 2026) |
|---|---|
| Eligible dev rows (protocol §2 metadata gates: not `footprint_suspect`, covers centre or overlap ≥ 0.25) | LROC NAC 522 rows / 495 images; WAC 925 rows; Kaguya TC 1,532; ShadowCam 97 (non-suspect) |
| LROC NAC CDR product | PDS4 label + PDS3 attached header; int16 "Scaled I/F" (× 3.05185e-5), special constants in the label; 2532 or 5064 samples; served by `pds.mcp.nasa.gov` with HTTP byte ranges (206 checked) |
| Geometry in labels | **None** in the CDR label (no sub-spacecraft point, no pointing). Line timing is: SCLK pre-roll count, exposure, summing |
| NAIF LRO SPICE (PDS, public) | SPK `lrorg_*` 6–15 MB per quarter; spacecraft CK `lrosc_*` 88–581 MB per ~10 days; LROC camera CK `lrolc_*` (temperature-corrected NAC orientation, frame `LRO_LROCNAC[LR]` is a CK frame) ~15 MB per month; IK `lro_lroc_v20.ti`, FK, SCLK, LSK, PCK, DE421 |
| NAC camera model | ISIS `LroNarrowAngleCamera` + `LroNarrowAngleDistortionMap` (read from the public ISIS source): detector sample = (s−1)·sum + sum/2 + 0.5 + (first−1); focal-plane y = ±0.007 mm × (det − BORESIGHT_SAMPLE); undistorted y = y / (1 + k1 y²); look = (x, y, f) in the NAC frame; line time = et0 + rate·(line − 0.5) with IAK pre-roll/line-rate corrections. The IAK values are checked against the label's own START/STOP times |
| spiceypy | not in the shared venv; installed with `pip --target` into the git-ignored `$POLARIS_DATA/v2/render_vs_real/pylib` (the shared venv is not touched) |
| Blender 5.3 | Cycles has `CUSTOM` (OSL) cameras → a true push-broom camera (per-line position and attitude), CPU only |
| Terrain at the four sites | PGDA 78 5 m tiles cover every site's 10 km square; LOLA LDEM_875S_5M (PDS) and PGDA 90 LDEM 80 m in the cache; S3 pyramid (equal to PGDA 78 at the sites at its 5 m level). SLDEM2015 stops at 60° S: **not applicable** at these sites |

## 1. Steps (one small validated step per commit)

1. **Selection** (`tools/validation/render_vs_real/select.py`): eligible dev NAC images → which `lrosc` CK window holds each →
   cluster sample of whole CK windows, in order of images per downloaded GB (a download-budget rule that never looks at image
   content or scores), until ~200 images; the strata of the sample are reported next to the eligible population.
   Committed: `results/selection.json` (ids, CK window, reason). Held-out guard test.
2. **Geometry** (`spice_kernels.py`, `nac_camera.py`): resumable kernel download with SHA-256 manifest
   (`$POLARIS_DATA/v2/render_vs_real/spice/`); per image: line times, spacecraft position (MOON_ME), NAC pointing, detector
   model, image lines crossing the site square, polynomial fit of position/attitude over those lines (fit residual recorded),
   Sun direction (DE421, LT+S, at the site centre at the window mid-time). Checks: label START/STOP vs ISIS timing; SPICE Sun vs the
   catalogue's Horizons az/el; SPICE footprint centre vs ODE centre lat/lon. Committed: `results/geometry.csv` (+ sources).
3. **Download** (`fetch.py`): only the image lines that cross the site square (+1 km margin), by HTTP range, resumable,
   SHA-256 of every block in `$POLARIS_DATA/v2/imagery/nac_windows/manifest.jsonl` (never committed). Polite: one connection,
   pauses between requests, back-off on errors. Budget: ≤ 40 GB new data in total for R4 (kernels + image windows).
4. **Render twins** (`blender_twin.py` run inside Blender + `pushbroom.osl`): v2 builder pieces (`blender/v2/terrain.py` levels,
   tiles and ENU frame; `hapke_nodes.py` Hapke material; Sun lamp with the true angular size and irradiance). Camera = OSL
   push-broom with the per-line state polynomials. Two renders per image × terrain product: **beauty** (Hapke, Sun disc,
   bounces) and **geometry** (Sun angle 0 = Sun centre, direct only, flat shading, 1 sample, tiny filter → lit/shadow by the
   protocol's definition; AOVs: surface position, normal). Products: PGDA 78 5 m, LOLA LDEM_875S_5M, PGDA 90 80 m, flat
   sphere (control); far field LDEM 80 m out to ±290 km for every non-flat product. ≤ 4 Blender processes at a time.
5. **Scoring** (`score.py`, `register.py`): exactly §3–§4 of the protocol (analysis window, exposure normalisation, saturated
   pixels, Otsu observed mask, IoU + lit IoU + balanced accuracy + κ + edge-band IoU, weak-bimodality flag, edge error in metres
   with unmatched fraction and signed variant, SSIM 11×11 σ 1.5 with the ≥ 90 % validity rule, Wasserstein-1 + JSD), registered
   and unregistered. Unit tests on synthetic images with known answers.
6. **Report** (`report.py` → `docs/validation/RENDER_VS_REAL.md`): distributions per site × product, paired differences vs the
   flat control with bootstrap 95 % intervals (seed `polaris-x-v2-boot`), gallery (12 per instrument, seed
   `polaris-x-v2-gallery`) and worst 10 %, every gated/failed row with its reason, registration offsets, Site04 RoI 3 hero point.
7. If time allows: WAC, more NAC CK windows, `web/src/components/RealVsModel.tsx` (display only).

## 2. Decisions that the frozen protocol leaves open → **Amendment A1** before any score

The protocol is not edited. Implementation choices it does not fix are written to `docs/v2/RENDER_VS_REAL_PROTOCOL_A1.md`,
whose SHA-256 is appended to `docs/v2/PREREGISTRATION.md` (Entry 2) **before any score is computed**. They are:
pixel binning to the terrain resolution (render on the binned image grid), border exclusion on the line-cropped window, the
registration search implementation (FFT masked NCC at integer px, then the exact 0.25 px grid near the peak), the pointing
uncertainty used for the search radius, the GSD definition, the terrain product list and far field, the renderer settings,
the photometric model(s), and the dev-only cluster sampling. Anything tuned later on dev gets A2, never an edit.

## 3. Rules kept

- Terrain is a reported factor, never tuned. Sun, times, camera model, shadow definition, threshold rule, windows, gates and
  metrics are as frozen. Exposure: only the per-image median normalisation.
- No NASA image or derived full-resolution crop is committed; gallery thumbnails only if the LROC archive's terms permit
  (checked and quoted in the report), small and credited "NASA/GSFC/Arizona State University".
- Labels: every score **SOURCE-BASED · UNVALIDATED, dev split, not the held-out headline**. No claim of the §8 claim rule can be
  made from dev numbers; the report says so.
- Every gated or failed image is listed with its reason.
