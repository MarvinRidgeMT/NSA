# Phase 1 data plan: whole-Moon terrain inputs (S2; prompt §2.1 and §0.4)

Session S2, branch `claude/v2-s2-data-5d5689` (cut from `feature/v2-whole-moon` at eda168c), 16 Nov 2026 from 02:20 EST.
The user is asleep and cannot answer, so every choice below is the conservative one and is written down.

## Inputs
- Prompt §2.1 product table and §0.4 data rules (`docs/v2/inputs/CLAUDE_CODE_PROMPT_6D_worlds_blender_v2.md`).
- `docs/v2/TERRAIN_STACK_CONTRACT.md`: raw downloads go to `$POLARIS_DATA/v2/products/<product_id>/`, one manifest line
  per file in `$POLARIS_DATA/v2/manifest.jsonl`, committed mirror `docs/v2/DATA_MANIFEST.json`.
- Products already in the cache are not downloaded again: PGDA 78 5 m tiles and clones (`data/cache/p78`,
  `data/external/pgda78`), PGDA 90 LDEM_80S 80 m (`data/external/pgda90`), JPL Horizons responses.

## Method
1. **Verify before downloading.** For each §2.1 product, find the official page and archive directory, then read the
   live directory listing for exact file names and byte counts. Record version, licence and the acknowledgement text
   the archive asks for (`docs/v2/PRODUCTS.md`). `tools/globe/fetch.py --check` sends one HEAD per file and fails
   on any size mismatch.
2. **Catalogue in code.** `tools/globe/products.py` lists every §2.1 product. Downloadable ones have exact URLs and
   sizes. The rest are entries with `status="not-downloaded"` and a reason.
3. **Polite, resumable fetch.** `tools/globe/fetch.py` downloads one file at a time with ≥ 1 s between requests and a
   16 MiB/s cap. It retries 429/5xx and network errors with exponential backoff (honouring Retry-After) and resumes
   with HTTP Range into `<file>.part`. If the server ignores the Range it restarts from zero; it never appends blindly.
   When a file finishes, the fetcher checks its size against the server and the catalogue, hashes it (SHA-256),
   checks the USGS `.md5` sidecar where one exists, renames the file into place, and appends one manifest line
   (contract keys plus `catalogue_bytes`, `resumed_from`, `landing_page`, and `archive_md5` where one exists).
4. **Budget guards.** Before each file the fetcher stops if this run's new data would exceed **150 GB**, or if free
   space on the cache volume would drop below **250 GB**. Free space was ~496 GB at the start, and there is no
   external SSD.
5. **Only public, no-login sources.** No accounts are created, and nothing is fetched behind a login or terms page.
   ISRO PRADAN and CNSA are recorded as "not downloaded: needs an account the user has not approved".

## Download order tonight (stop at the budget)
| # | product_id | What | Files | Size |
|---|---|---|---|---|
| 1 | `lola_ldem_global` | LOLA LDEM 16/64/128 ppd float (PDS) | 3 + labels | 5.37 GB |
| 2 | `lola_ldem_polar` | LOLA polar stereographic LDEM, finest post per ring, both poles: 5 m ≥87.5°, 10 m ≥85°, 20 m ≥80°, 30 m ≥75°, 60 m ≥60° (float) | 10 + labels | 37.27 GB |
| 3 | `pgda70_roughness` | PGDA 70 median absolute slope 57/225/560 m + Hurst exponent | 4 + labels | 0.11 GB |
| 3 | `lola_roughness_gdr` | LOLA gridded roughness (LDRM), slope (LDSM), roughness count (LDRC): cylindrical + polar | 15 + labels | 1.31 GB |
| 4 | `pgda67_slope_azimuth_64` | PGDA 67 SLDEM2015 slope + azimuth, 64 ppd global | 2 + labels | 2.12 GB |
| 5 | `sldem2015_512` | SLDEM2015 512 ppd float tiles (32) + data-quality map | 33 + labels | 45.30 GB |
| 6 | `lroc_wac_100m` | LROC WAC global morphologic mosaic 100 m (USGS GeoTIFF, md5-checked) | 1 + labels | 5.96 GB |
| 7 | `pgda67_slope_azimuth_128` | optional: PGDA 67 slope + azimuth 128 ppd | 2 + labels | 8.49 GB |
| | | **total** | | **105.9 GB** |

Choices, and why:
- **Float rather than int16 LDEMs.** The int16 products are quantised to 0.5 m. The float copies are the same grids
  without that step, and the budget allows them (+18.6 GB for the polar set).
- **Polar: only the finest post of each ring.** The coarser posts of the same ring are a strict subset of the
  information. The 45° 100 m product is skipped because SLDEM2015 covers ±60° better.
- **PGDA 67: 64 ppd only, plus optional 128 ppd.** The 512 ppd slope and azimuth tiles are 68 GB each, which is not
  "modest". Slope can be recomputed from SLDEM2015 by S3 where needed.
- **SLDEM2015 from the PDS float tiles (45.3 GB, the archive of record).** The ~22 GB int16 figure in the prompt is an
  estimate for a 2-byte copy; no such official int16 file exists on PDS. The 5.47 GB JPEG2000 tiles are another
  encoding of the same data; their compression is not checked here, so they are not used for science.
- **"LOLA RMHE".** No product of that exact name was found on the LOLA node. It is read as the LOLA gridded RMS-height
  roughness maps (`LDRM_*`), fetched together with the matching slope maps (`LDSM_*`) and roughness-count maps
  (`LDRC_*`). PGDA 70 is the slope/Hurst product (MIT `EXTRAS/FRACTAL`).
- **WAC from USGS Astrogeology.** The LROC PDS pages are JavaScript-rendered and have no plain index to fetch from.
  USGS distributes the same June 2013 ASU mosaic as one GeoTIFF with an MD5 sidecar. It is VISUAL only.

Not downloaded tonight (see `docs/v2/PRODUCTS.md`): Kaguya TC DTMs (JAXA / USGS ASP; ~0.8 TB class, stream per tile),
LROC NAC DTMs (per site), GSFC SfS (per region), LROC NAC images (S6), Chandrayaan-2 TMC-2 (ISRO PRADAN, needs an
account), CNSA Chang'e (needs an account).

## Tests
- `tools/globe/test_fetch.py` runs against a local HTTP server and covers:
  - resume after an interruption (Range header sent, bytes appended, SHA-256 equals the payload's);
  - server-dropped connections retried and resumed;
  - Range ignored → restart, not append;
  - a corrupt partial file exposed by the hash;
  - 503 retried and 404 not retried;
  - catalogue size mismatch rejected;
  - manifest lines carry every contract key, and a re-run is idempotent;
  - archive MD5 mismatch rejected;
  - budget stops before any byte is fetched;
  - throttle spacing and bandwidth cap.
- `tools/globe/test_products.py` checks that the catalogue is consistent: every §2.1 row present, unique local paths,
  HTTPS/HTTP public URLs only, sizes match the documented pixel counts, `not-downloaded` entries carry a reason, and
  account-gated products are never in the download plan.

## Acceptance
- Tests green: `python -m pytest -q tools/globe science/tests`.
- Every downloaded file has a manifest line whose SHA-256 matches the file. `docs/v2/DATA_MANIFEST.json` is regenerated
  with `python -m tools.globe.fetch --mirror docs/v2/DATA_MANIFEST.json`.
- `docs/v2/PRODUCTS.md`, `docs/v2/DATA_BUDGET.md` and the appended `docs/DATA_PROVENANCE.md` section are written;
  `docs/BUILD_STATUS.md` is appended; the S2 row of `docs/v2/STATUS.md` is filled.
- No rasters are committed, nothing is pushed, and no commits go to protected branches.

Reproduce: `python -m tools.globe.fetch --check` and then `python -m tools.globe.fetch`. Re-runs skip complete files and
resume partial ones.
