# Render vs real — Kaguya Terrain Camera (SELENE), held-out run (Amendment A13): stopped before completion

**SOURCE-BASED · UNVALIDATED · held-out run incomplete — no result and no claim.** Protocol
`docs/v2/RENDER_VS_REAL_PROTOCOL.md` (frozen) + amendments A1–A13 (hashes in `docs/v2/PREREGISTRATION.md`, Entry 14).

## What happened
- **Registered first:** A13 and the frozen TC code (Entry 14) at commit b083733, before any held-out file was listed.
  Selection at a5ecf27: 200 rows / 182 images, 50 per site, metadata only (`results_tc_heldout/selection.json`).
- **Downloads:** the project owner downloaded all 364 held-out files (182 labels + 182 images) by hand; none damaged.
- **Run:** started 19 Nov 00:27 UTC (18 Nov 19:27 EST) at a5ecf27, one start, hashes verified first
  (`results_tc_heldout/RUN_LOG.jsonl`).
- **Stopped by the project owner** on 18 Nov 2026 at about 21:10 EST, before completion. Logged as event
  `stopped_by_owner`. The run was not stopped because of anything in the scores; no score was looked at for the decision.

## Accounting at the stop
| state | rows |
|---|---|
| selected | 200 |
| geometry OK | 122 |
| gated at geometry (satellite moving direction +1, A12.2) | 5 |
| no geometry yet (files downloaded, never processed) | 73 |
| scored (PGDA 78 and controls, all products and photometry) | 66 (64 primary track, 2 secondary) |
| failed | 0 |

Scored rows by site: site04 24, site01 20, site07 12, site11 10.

## What this means
- **The A13 held-out run did not happen as registered.** The §8 claim needs every selected row (A13.2); 66 of 200 is not
  that sample, and the rows scored first are not a random subset of it (they follow download and render order).
- **No held-out metric is reported here, and none may be quoted.** The partial records
  (`results_tc_heldout/geometry.csv`, `scores.jsonl`) are committed as ids and numbers only, for the record; they are
  not a result. The A13.4 prediction is neither confirmed nor refuted.
- **Kaguya TC therefore has dev results only** (`docs/validation/RENDER_VS_REAL_TC_DEV.md`, labelled dev, not a claim).
- **Resuming:** the frozen code is unchanged, so `python -m tools.validation.render_vs_real.tc_heldout run` would resume
  the same registered run (scored rows are never re-scored) and the report would then disclose this stop and restart.
  Any change to the pipeline instead needs a new amendment.
