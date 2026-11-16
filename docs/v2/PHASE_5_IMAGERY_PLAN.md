# Phase 5 (§6.1 + §6.3) — imagery catalogue and pre-registered render-vs-real protocol: plan

Session S6, 16 Nov 2026 (night run; the user is asleep, so every choice below is the conservative one and is written down).
Source prompt: `docs/v2/inputs/CLAUDE_CODE_PROMPT_6D_worlds_blender_v2.md` §0 and §6. Ownership: `docs/v2/SPLIT.md`
(S6 owns `tools/imagery/**`, `imagery/catalogue.*`, `docs/v2/RENDER_VS_REAL_PROTOCOL.md`; this plan, `IMAGERY_CATALOGUE.md`
and `PREREGISTRATION.md` are S6's new docs).

**In scope tonight:** §6.1 harvest of *metadata* (no bulk imagery), §6.3 protocol frozen with hashes.
**Not in scope tonight:** render twins (§6.2), any scoring, rules enforcement beyond writing them (§6.4), deliverables (§6.5),
Mercury and Mars imagery.

## 1. Inputs

| Input | Where | Notes |
|---|---|---|
| Four current sites | `research/long_features/code/sites.py` `R` (the Decision Lab's four sites, `docs/LONG_FEATURES_2026-11-15.md` §8) | Site04 RoI 3 (−89.78012, −156.32023), Site01 RoI 6 (−89.47409, −137.3813), Site07 RoI 1 (−88.8063, 123.54887), Site11 RoI 4 (−88.70606, −68.52994). Site04 RoI 3 and Site01 RoI 6 are also in `science/sites.py`. PGDA 78 ROI centroids, SOURCE-BASED · UNVALIDATED. |
| Metadata archive | PDS Geosciences Node Orbital Data Explorer (ODE) REST, `https://oderest.rsl.wustl.edu/live2/`, manual `ODE_REST_V2.1.pdf` (09/08/21) | Public, no account. Product types found by the `iipt` query on 16 Nov 2026 (below). |
| Solar geometry at each site | JPL Horizons API through `science/horizons.py` (`build_params`, `parse_text`), observer `coord@301`, airless apparent az/el of the Sun centre | Same convention as the solver: azimuth 0° = north, 90° = east, local ENU on the 1737.4 km sphere. One TLIST call per batch of image times, cached. |
| Prior NAC work | `tools/validation/nac/` (`nac_cams.json` 322 region 6, `nac8_imgs.json` 172 region 8, `nac9_cams.json` 193 region 9 = 687 GSFC orthorectified NAC images, Zenodo 10.5281/zenodo.17954508, CC-BY-4.0) | Reused as a join key: these product IDs are flagged `prior_use` and are never in the held-out set (region 6 tuned the v2 thresholds). |

ODE product types (iipt query, 16 Nov 2026): LRO LROC `CDRNAC4` (2,928,547 products), `CDRWAC4` (929,884), KPLO ShadowCam `CAL`
(39,518), SELENE (Kaguya) TC `TCWL2B` (stereo Level 2B0, 221,138) and `TCSL2B` (mono Level 2B0, 83,481). Calibrated (CDR/CAL/L2B0)
products are used rather than raw EDRs, because their labels carry the geometry fields. Chandrayaan-2 OHRC is **not** indexed by
ODE; it is distributed by ISRO PRADAN, which needs registration → not catalogued (no account created).

### Artemis III candidate regions
NASA's current list is the nine regions announced on 28 Oct 2024 (NASA news release "NASA Provides Update on Artemis III Moon
Landing Regions"), restated with no change in T. George, M. A. Rubio, S. J. Lawrence, P. Curell (NASA), *Artemis III site selection
update: down-selection from 13 to 9 candidate regions*, LPSC 57 (2026) abstract 1901: Peak near Cabeus B, Haworth, Malapert
Massif, Mons Mouton Plateau, Mons Mouton, Nobile Rim 1, Nobile Rim 2, de Gerlache Rim 2, Slater Plain. Neither source gives numeric
coordinates or region outlines (the abstract has only a map image). **Decision: do not invent boxes from a picture.** The regions
are listed in the catalogue doc but not queried tonight. They will be queried when an official outline file (or a NASA-published
coordinate table) is found and cited. Two of the four current sites sit in regions of the 2022 list (GSFC Zenodo regions 8 "Peak
Near Shackleton" and 9 "de Gerlache Rim"); this is not claimed to equal a 2024 region.

## 2. Method

### 2.1 Footprint query (`tools/imagery/ode.py`)
1. For each site, a 10 km × 10 km square (±5 km) centred on the site in the south-polar stereographic grid of `science/frames.py`
   (x = ρ sin λ, y = ρ cos λ, ρ = 2R tan(π/4 + φ/2), R = 1,737,400 m).
2. The square's boundary, densely sampled, gives its planetocentric lat/lon envelope (lon 0–360 E). If the pole is inside, the
   envelope is lat [−90, max], lon [0, 360]. If the lon range wraps 0/360 it is split into two queries.
3. ODE `query=product`, `loc=f` (bounding box intersects the product footprint), `results=c` first (count), then `results=mf`
   paged with `limit`/`offset` until the count is reached. Fetched total must equal the count, else the run stops.
4. Exact local filter: ODE's `Footprint_SP_geometry` (metres, south-polar stereographic) is clipped against the square
   (Sutherland–Hodgman, exact for a convex window). Kept if the overlap area > 0. Recorded: overlap fraction of the square,
   whether the footprint contains the site centre. A test checks ODE's SP frame against `frames.stereo_forward` on a fixture vertex.
5. Footprints are taken as ODE gives them. Some early NAC footprints come from the PDS index table and are visibly too large;
   rows whose footprint area exceeds 4× the instrument's nominal frame area are flagged `footprint_suspect` (not dropped).

### 2.2 Politeness and provenance
- Sequential requests only, ≥ 2.0 s between network requests to the same host, generic User-Agent, three retries with back-off.
- Every raw response is saved byte-for-byte under `data/cache/v2/imagery/ode/` (git-ignored; `data/cache/` is a symlink to the
  main checkout's cache) with a manifest line (URL, SHA-256, bytes, retrieval UTC). A cached response is never re-fetched.
- Horizons responses go to `data/cache/v2/imagery/horizons/` the same way.
- **No image downloads** except ≤ 20 ODE thumbnails (small PNG) for the pipeline test, cached under `data/cache/v2/imagery/thumbs/`,
  never committed.

### 2.3 Catalogue fields (one row per image × site overlap)
Product id, instrument, ODE product type, observation UTC (mid), start/stop UTC, emission / incidence / phase angle (ODE, at the
image centre), pixel scale (ODE `Map_resolution` / `Map_scale`; nominal value flagged if absent), centre lat/lon, footprint area,
overlap fraction, covers-centre flag, label URL, product page URL, data file URL and size, `footprint_suspect`, `prior_use`
(687 GSFC NAC images), and at the **site centre** from Horizons: Sun azimuth, Sun elevation, sub-solar latitude (derived from the
Sun direction at the site; it is the lunar "season" variable).

**Sub-spacecraft position:** ODE does not provide it for these products (checked on NAC, WAC, ShadowCam and TC rows). It is in the
PDS labels (LROC/ShadowCam PDS4 XML, TC PDS3 label). Fetching thousands of labels tonight would be a heavy load on the LROC and
JAXA servers; the catalogue stores the label URL and the label is fetched per image when that image is rendered (§6.2). Tonight the
label parser is tested on a few labels only. This is a known gap, not done.

### 2.4 Strata
| Axis | Bins |
|---|---|
| Sun azimuth at site (0° N, 90° E) | 8 × 45° (N, NE, E, SE, S, SW, W, NW centred on the compass point) |
| Sun elevation at site | < −0.5°, [−0.5, 0.5), [0.5, 1.5), [1.5, 2.5), ≥ 2.5° |
| Emission angle | [0, 5), [5, 15), [15, 30), ≥ 30° |
| Season (sub-solar latitude) | < −0.75°, [−0.75, 0.75), ≥ 0.75° |
| Terrain type | per site, from the site description (crater rim: Site04, Site11; ridge: Site01; massif peak: Site07). A site-level label, not a per-pixel classification. |
| Resolution | < 1 m/px, [1, 5), [5, 20), [20, 100), ≥ 100 m/px |

### 2.5 Held-out split
- Split by **image** (product id), never by row, so one image is never in both sets through two sites.
- Each image's primary row is its site with the largest overlap (ties: site order above). Its stratum is that row's stratum.
- Within each stratum, eligible images (not `prior_use`) are ranked by SHA-256 of `"polaris-x-v2-heldout-2026-11-16:" + product_id`;
  the first round-half-up(0.3 × n) are held out. `prior_use` images are always in the development set.
- The seed string is fixed in code and in the protocol. The split is a pure function of the catalogue; a test re-derives it.

### 2.6 Output format
The venv has no pyarrow, pandas, fastparquet, polars or duckdb. Installing into the shared venv while other sessions run is not a
conservative move. **Fallback: `imagery/catalogue.csv.gz`** (gzip mtime = 0, sorted rows, fixed column order, so the SHA-256 is
reproducible), with a JSON column dictionary `imagery/catalogue.schema.json`. A one-line converter to Parquet is left for when
pyarrow is installed. The ≤ 20-thumbnail pipeline test does not write into the catalogue.

### 2.7 Surface imagery
Catalogue only sources whose metadata is public and whose terms allow reuse, without any account:
- Apollo Hasselblad scans: NASA, public; per-frame times/positions are in the Apollo Lunar Surface Journal narratives, not in one
  machine-readable index → source recorded, frames not catalogued tonight.
- Chandrayaan-3 (ISRO PRADAN), Chang'e 3/4/5/6 (CNSA GRAS data release), IM-1, IM-2 (Intuitive Machines), Blue Ghost (Firefly):
  "needs registration / terms not checked" → skipped.
Recorded in `docs/v2/IMAGERY_CATALOGUE.md`.

## 3. Tests (`tools/imagery/tests/`, run with `python -m pytest tools/imagery -q`)
1. WKT parsing of POLYGON / MULTIPOLYGON / GEOMETRYCOLLECTION fixtures from real ODE responses.
2. ODE's SP frame equals `frames.stereo_forward` within 2 m at a recorded vertex (fails if the axes or radius differ).
3. Polygon clipping: known overlap areas (square in square, triangle, disjoint, concave L-shape).
4. Site box envelope contains the square; pole-inside case; 0/360 split case.
5. Pagination stops at the ODE count and raises on a short page; cache hit makes no network call (fake transport).
6. Product-row parsing of recorded NAC, WAC, ShadowCam and TC fixtures (angles, times, pixel scale, URLs).
7. Stratum binning edge cases (bin edges, azimuth wrap at 337.5°/22.5°).
8. Held-out split: deterministic, ~30 % per stratum, `prior_use` never held out, split by image.
9. Sub-solar latitude from (az, el) at a site: pole and equator closed-form cases.
10. Catalogue writer: same input → same bytes (SHA-256).

## 4. Acceptance (tonight)
- Tests green; existing suites not broken (S6 touches no shared code).
- Catalogue written with counts per instrument × site and per stratum in `docs/v2/IMAGERY_CATALOGUE.md`; held-out count stated.
- `docs/v2/RENDER_VS_REAL_PROTOCOL.md` committed **before any scoring** (none is run), then its SHA-256 and the catalogue's SHA-256
  in `docs/v2/PREREGISTRATION.md`.
- `docs/BUILD_STATUS.md` appended; S6 row in `docs/v2/STATUS.md` filled. Nothing unbuilt reported as done.
