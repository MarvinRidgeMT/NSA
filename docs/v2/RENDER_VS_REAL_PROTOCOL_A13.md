# Render-vs-real protocol — Amendment A13 (the held-out run for Kaguya TC)

Written 18 Nov 2026 by the coordinating session (Claude), after the Kaguya TC dev pilot and **before any held-out TC
label or image is listed for download, fetched, read, rendered, displayed or scored**. Its SHA-256, and the SHA-256 of
every TC code file the run executes, are recorded in `docs/v2/PREREGISTRATION.md` (Entry 14) in the same commit. The NAC
and WAC files the run imports are already frozen (Entries 6 and 8); `tc_select.py` is frozen in Entry 12.
`tc_heldout.py` refuses to start if any registered hash differs.

**State at writing.**
- **Dev pilot (A11.5, A12):** complete, `docs/validation/RENDER_VS_REAL_TC_DEV.md` (commit c1536d6). All 150 selected rows have
  geometry: 141 scored (137 primary track, 4 secondary), 9 gated (satellite moving direction +1, A12.2), 0 failed.
- **No TC code that renders or scores changed after A12** (Entry 13, commit 5196723). Since then only the drivers were
  added: `tc_pilot.py` (follows the owner's downloads), `tc_download_list.py` (list for either split), `tc_heldout.py`
  (this run), and the report script `tc_report.py` (formatting only, not frozen).
- **Held-out data so far:** catalogue metadata only. The TC download manifest (`$POLARIS_DATA/v2/imagery/tc/MANIFEST.jsonl`,
  440 records) and the TC cache hold no held-out product; no held-out URL list has been written.

## A13.1 Scope
- **Instrument:** Kaguya TC Level 2B0, stereo and mono, as one instrument (A11.1). Camera model, kernels and orbit as
  A11; conventions as A12: ISIS start time; no sample flip for moving direction −1; direction +1 gated; registration
  radius 747.6 m (`tc_run.REG_RADIUS_M`).
- **This is the single held-out run for Kaguya TC.** After it, nothing in the TC pipeline may change without a new
  amendment that reports both the original and the changed numbers.

## A13.2 Rows (the stratified sample A11.6 announced)
- **Considered:** every `split = heldout` TC row of the frozen v1 catalogue. The protocol §2 gates (`tc_common.eligible`)
  leave 645 rows / 436 images: site04 208, site07 173, site01 170, site11 94; 628 stereo, 17 mono; 60 rows on the
  secondary track. (Counts from catalogue metadata only.)
- **Sample:** stratified by site with **equal allocation**: per site, the first 50 eligible rows in
  SHA-256(`polaris-x-v2-kaguya-tc-heldout-2026-11-18`:product_id:site) order, 200 rows in all
  (`tc_heldout.select`, `PER_SITE = 50`). Why equal: the §8 claim is decided per site, and proportional allocation would
  give site11 only about 29 rows. The sample uses metadata only; `results_tc_heldout/selection.json` records it.
- **Then:** the A11/A12 geometry gates (orbit and attitude coverage, moving direction, the 1 m / 0.1 px fit gate) and
  the §3.1 window minimum. On dev, 9 of 150 rows (6 %) were gated for moving direction +1.
- **Accounting:** every row is reported as scored, gated (with its reason), failed (with its reason) or not downloaded.

## A13.3 Downloads
- DARTS rejects this pipeline's requests (A11.7), so the project owner downloads the held-out files by hand.
  `tc_heldout list` writes `results_tc_heldout/download_heldout.txt` and prints a fetch-until-valid command (gzip tested,
  refetched up to six times). `tc_heldout check` lists damaged or missing files.
- The run (`tc_heldout run`) scores rows as their files arrive and is resumable; rows already scored are never re-scored.
  Rows still missing when the owner stops downloading are reported as not downloaded, never silently dropped.
- Every file gets a manifest entry; no JAXA image is committed.

## A13.4 What the dev pilot showed, and the prediction stated before the run
**Dev, PGDA 78, Hapke, registered, 137 primary-track rows** (`docs/validation/RENDER_VS_REAL_TC_DEV.md`):
- **§8 dry run met at all four sites** for PGDA 78 and for LOLA LDEM_875S 5 m. Median shadow IoU 0.955–0.983; median
  edge 10.0–10.8 m against limits of 19.3–20.8 m. Beats the flat control: IoU 88.6–100 %, edge 94.3–100 %. site04 is the
  weakest on the control condition (39/44 rows for IoU).
- **PGDA 90 80 m** meets IoU and the control condition but **fails the edge condition at every site** (median 29–38 m).
- **Registration:** offset median 249 m (P90 318 m). Lines (dy, along track) median 22.2 px ≈ 223 m, as A12.2 found.
  NCC median 0.77; 4 rows at the search bound. **Unregistered** shadow IoU median 0.89 and edge 54 m (42–68 m per site, against limits near 20 m): the claim depends
  on the registration absorbing the systematic offset of the public camera model (A12.2).
- **The Otsu floor on low-Sun rows.** 19 rows have the fixed Otsu threshold at the −5 floor of log10 normalised radiance,
  17 of them in the el[−0.5°, 0.5°) bin. There, only pixels at the floor count as observed shadow; median Otsu shadow
  IoU in that bin is 0.27, while the count-matched IoU (A5.5) is 0.97. Geometry is right; the threshold rule (never tuned)
  is what fails. These rows (21 % of primary rows) pull no site median below 0.95.
- **Mono products (6 rows)** register about 1.1 km off (at or near the search bound) with NCC about 0.4: their geometry
  is not modelled as well as the stereo products'. Their cause is not established. They stay in the claim (A11.1).
- **GRGM900C orbit** covers 11 dev rows; comparison only (dev report §7.1).

**Prediction for the held-out run, written before any held-out file is listed** (PGDA 78, Hapke, registered, primary
track, headline orbit; the report checks each item and prints confirmed / NOT confirmed):
- **(a)** The §8 claim is **met at every site** with scored rows for PGDA 78 5 m.
- **(b)** The §8 claim is met at every site for LOLA LDEM_875S 5 m; for PGDA 90 80 m it fails condition 2 (edge) at
  every site.
- **(c)** Count-matched shadow IoU median ≥ 0.95 over all primary rows.
- **(d)** The along-track registration offset (dy) median lies between 18 and 26 lines over all primary stereo rows.
- **(e)** In the el[−0.5°, 0.5°) bin, the Otsu shadow IoU median is below 0.50 while the count-matched shadow IoU median
  is at least 0.90.
- **(f)** Unregistered PGDA 78 rows do **not** meet condition 2 (edge) at any site.

(c)–(f) are not claims. The prediction most at risk is (a) at site04 through condition 3 (88.6 % on dev, limit 80 %).

## A13.5 The §8 claim (rule unchanged from A5.6)
- **Unit:** per site and per terrain product. Rows: registered, Hapke, primary track, headline orbit (the RISE solution
  named in the label). Headline product PGDA 78 5 m.
- **Conditions:** (1) median shadow IoU ≥ 0.80; (2) median edge error ≤ 2 × the median analysis pixel (TC is unbinned,
  about 10 m, so a limit near 20 m); (3) beats the flat-sphere control on ≥ 80 % of paired rows, for IoU and for edge.
- **Never in the claim:** secondary-track rows (SSIM and histogram distances only), the GRGM900C comparison, count-matched
  IoU, unregistered scores, product and photometry comparisons, and the descriptive camera and product-type splits.

## A13.6 Frozen parameters and code
- **Code:** the TC files listed in Entry 14 (`tc_camera`, `tc_kernels`, `tc_common`, `tc_io`, `tc_geometry`, `tc_run`,
  `tc_pilot`, `tc_download_list`, `tc_heldout`), `tc_select.py` (Entry 12), and the NAC and WAC files of Entries 6 and 8.
- **Stages:** `python -m tools.validation.render_vs_real.tc_heldout select`, then `list` (the owner downloads), then
  `run --workers 4 --threads 4` (follows the downloads), `check` for damaged files, and `orbit` (the GRGM900C comparison,
  A11.3; comparison only).
  - Outputs: `results_tc_heldout/` (ids and numbers) and `$POLARIS_DATA/v2/render_vs_real/tc_heldout/` (git-ignored).
  - Logging: start, stop and commit go to `results_tc_heldout/RUN_LOG.jsonl`.
- **Report:** `POLARIS_TC_SPLIT=heldout python -m tools.validation.render_vs_real.tc_report` writes
  `docs/validation/RENDER_VS_REAL_TC_HELDOUT.md`. The report script only formats and checks the A13.4 items; it is not
  frozen, and any change to it after the run is listed in the report's commit.

## A13.7 What a result would and would not mean
- A met claim at a site means: after one rigid shift per image (median about 250 m, mostly along track), the
  direct-sunlight shadow geometry rendered from LOLA terrain and SPICE matches what TC recorded, to about one 10 m pixel,
  for those images and that site.
- It does **not** mean that the public camera model locates TC images to 10 m. Without the shift they are about 250 m
  off, a systematic offset whose cause is not established (A12.2); unregistered scores are reported beside the claim.
- It does not certify illumination power, DSN or link availability, and it is not a probability.
