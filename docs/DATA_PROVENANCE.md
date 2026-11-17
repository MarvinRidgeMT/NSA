# Data provenance

Generated 14 November 2026. All scientific bundles remain explicitly `SOURCE_BASED_UNVALIDATED`.

## NASA terrain

The regional numerical terrain is a 401×401 crop at 80 m spacing from NASA PGDA product 90, `LDEM_80S_80MPP_ADJ.TIF`. It is read through GDAL HTTP range requests; the complete 181 MB COG is not stored, so the bundle records a hash of decoded crop values rather than claiming a full-file checksum.

| Site | Crop values SHA-256 |
|---|---|
| Connecting Ridge / Site01 | `d27c5aa679cd00ffee0a95ce36e0049b3189b477a6e14efb941eecac92d73b5d` |
| Shackleton Rim / Site04 | `e48bee96e517fe1e4d455a749d4f414e144be34c8a4639d536b8727cdc6383a4` |

The full Site01 PGDA product 78 files are retained under `app/data/source/pgda78/Site01/`:

| File role | SHA-256 |
|---|---|
| Nominal 5 m LDEM | `3ba7b97cb00a2bcf21189c3aeb535f65afc21207154ab9f0d43c5bdc1f7e747e` |
| Total-Z RMS layer | `cf2cf52f52d2aa51e60d058010d10b0ebfb1d3e920f5a2b9a46eb6c51054ab1c` |
| Clone 001 | `242de9e3da624a276864cc4fa7c499e96981c95fd27583565e68e92434faf05b` |
| Clone 002 | `97b2c05633e308c72eddfc5a337089836d80b5edb7469321976973f7eeb7dcad` |
| Clone 050 | `5819388022b1f32d50eab7bdd1c8d8446a9ddfcf88ba4693d24116f86ea02e37` |
| Clone 100 | `596dcdf341b411893e2994571685bd54f911bfb476855ca6ce8d8f0f5f676698` |

The clones are absolute deterministic elevation realizations supplied by the source product, not delta rasters and not assigned probabilities here.

## NASA global Moon model

Global navigation uses NASA SVS 14959's `Moon_NASA_LRO_8k_Topo_Small.glb`, credited to NASA's Goddard Space Flight Center. NASA describes it as an 8K color-map and height-map model derived from LRO data for web/AR/animation. The checked 81,505,784-byte asset has 2,021,340 vertices, 1,015,808 triangles and SHA-256 `c4b65fb4df622a37fd75366c2ed9bf9e163e41c0fde178b3b27e31b0173e6953`. The 13,799,876-byte color-only fallback has SHA-256 `12d3b0bb7fe214903f51447d1bc61710f442e92a11c703fcaca6d4e7ff8e67d4`. Both are visual assets and never supply numerical POLARIS elevations. Source: `https://svs.gsfc.nasa.gov/14959/`.

PGDA product 104's optional Site01 shape-from-shading archive was reviewed but not added to the runtime: its Connecting Ridge archive is approximately 2.2 GB and is not required by the current 5 m PGDA 78 plus 80 m PGDA 90 model. No product 104 result is claimed.

## NASA PGDA 69 visibility reference layer

The React viewer includes a separate reference map made from NASA PGDA product 69's 60 m average Sun and Earth visibility GeoTIFFs and the PGDA 78 ROI shapefiles for Sites 01, 04, 07 and 11. The two 2016 visibility rasters, PDS labels and four ROI archives were downloaded to `data/raw/pgda69/` and verified against eight pinned SHA-256 values by `tools/pgda69/build_layer.py` (56 MiB total). Generated runtime layers live under `web/public/layers/pgda69/`: 240 m/px whole-pole block means, native 60 m/px site crops, 17 ROI polygons and zonal statistics.

PGDA 69 values are 18.6-year, hourly surface-pixel averages using the 2016 60 m LOLA DEM. Sun/Earth are considered visible when any part of the relevant disc is unobscured. They are not the same quantity, time window, observer height or terrain version as POLARIS target-centre results, so the map is a reference/ranking layer and does not complete the independent validation gate.

## JPL ephemeris

JPL Horizons was queried for target 10 (Sun) and target 399 (Earth), observer centre `coord@301`, geodetic lunar coordinates, airless apparent angles, UTC and 60-minute steps. Each raw text response is retained under a bundle-specific directory in `app/data/raw/jpl/`. The query URL, parsed API version, requested/reported centre and raw-response SHA-256 are embedded beside the samples.

## Bundles

| Artifact | Content | SHA-256 |
|---|---|---|
| `polaris-source-site01-2026-11-14-v2.json` | Site01 regional + 5 m + RMS + four clones + JPL | `6a16ee59965e47afe54527c0b2bcdd90c6d40ba40a2423ca964e7da8e89a4fb6` |
| `polaris-source-two-site-2026-11-14-v2.json` | Site01 and Site04 regional + JPL | `b60129a0399e9dd58ab42e6fb7fe76c82355b2b823dbbf4f3fa80e3aa87658ee` |
| `polaris-offline-source-case.json` | Compact two-site startup cache | `11919cfbbd9d84e68dad02520dadfc95880dd3a40aabe16d9e60a8e48a1dfee3` |
| `polaris-runtime-source-case.json` | Full runtime: Site01 local layers plus two-site regional/JPL data and explicit local-to-grid bases | `713099a1623690fd761dcab8b3b2a0439e3f87f96cddd58d0d722fddc4e72062` |

The compact cache deliberately omits the 5 m nominal terrain, RMS layer and clones. The generated runtime cache includes them and is the default for localhost and direct-file launches.

## Reproduction

Install `requirements-science.txt`, then run `app/scripts/prepare_science.py --help`. The checked-in source bundles use the exact commands documented in `docs/BUILD_STATUS.md`. A future API response can be numerically equivalent but byte-different, so each run receives its own raw-response directory and hashes.

## Source registry (machine-readable)

`data/source_registry.json` (schema `polaris-source-registry-v1`) is generated by `tools/sources/build_source_registry.py`.
It lists every external source with its role, URL, credit, frame, projection, pixel scale and limitations, and hashes every
local source file. On 2026-11-14 19:26 EST all 12 hashes documented above matched the files on disk.
`python3 tools/sources/build_source_registry.py --check` verifies without rewriting the file.

## LROC NAC controlled south-pole average mosaic (visual context only)

| Field | Value |
|---|---|
| Product | LRO-L-LROC-5-RDR-V1.0, `NAC_POLE_SOUTH_CM_AVG_P892S2250` (Controlled 1 m/pixel South Pole Average Mosaic) |
| Page | https://data.lroc.im-ldi.com/lroc/view_rdr/NAC_POLE_SOUTH_CM_AVG |
| File | `…/LROLRC_2001/DATA/BDR/NAC_POLE/NAC_POLE_SOUTH_CM_AVG/NAC_POLE_SOUTH_CM_AVG_P892S2250.IMG`, 8,276,814,528 bytes, PDS3, 32-bit PC_REAL |
| Cite | Archinal et al. (2023), "Controlled High-Resolution LROC NAC Polar Mosaics", LPSC 54, abstract 2333 |
| Coverage | 88.5–90° S, 180–270° E; 45488 × 45488 px at 1 m |
| Projection | Polar stereographic, centre 90° S / 0° E, sphere 1737.4 km, east-positive, planetocentric |
| Pixel rule | x = (sample−1) − 45487.5, y = −0.5 − (line−1), pixel centres (label offsets, LROC Nov-2011 definition) |
| Control | ISIS jigsaw, 1,677,811 points, constrained by points tied to LOLA track data; projected on a LOLA-track polar DEM |
| Stored here | Only the Site01 window x −12000…−10000, y −13000…−11000 m (2000² px), fetched by byte range; no whole-file hash |
| Role | **Visual context only** (albedo/morphology texture). Never numerical. |

Limitations: the mosaic averages 18,323 images taken 2009–2013 under many Sun directions; per its label it does not
represent any realistic lighting condition, and the shading is baked in. It must not be shown as illumination at a mission
time, used to infer elevation, or fed to any calculation. The units of the averaged pixel value are not stated in the label
read here, so the 8-bit display copy uses a documented linear percentile stretch and is labelled VISUAL.

Registration check against the PGDA 78 Site01 5 m DEM (north half of the window so far): best image shift x −5.7 m,
y −0.3 m, peak normalised cross-correlation 0.39 (0.37 at zero shift). Method and numbers:
`tools/sources/check_nac_dem_registration.py`, `data/visual/lroc_nac_pole_south_cm_avg/*_registration.json`.
~~The download is incomplete (1056 of 2000 rows).~~ **Complete, 14 Nov 22:04 EST** (2000 × 2000). Full-window registration: image
shift x −6.01 m, y +1.15 m, peak NCC 0.416 (0.374 at zero shift), 160,000 5 m pixels; display-alignment evidence only.
Hashes: raw float32 window `35ef3b5805cdee4e43f3a8d23066a165d3f4bce8aceafbeb74005e759d4be991`; display PNG
`8ff9a6248a2614838b20aa361c12c7ede0f871aaa6200a4b06ab3105687ef5e4`; float32 GeoTIFF (git-ignored copy)
`e2cee071d519dcbe3b10896b7b81065859097cd6c6fa3751b25958c5937db3c1`. Display stretch 0.0224–0.4409 (0.5–99.5 percentile).
Fetched in three sessions (1,056 + 230 + 714 rows); the last used 15 requests of 50 rows (`--block-rows 50`).

## Visual layers file

`data/visual/visual_layers.json` (schema `polaris-visual-layers-v1`) is the only place visual-raster metadata is stored
for the apps. It is generated by `tools/sources/build_visual_layers.py` and contains a layer only when its window is
fully downloaded **and** has a full-window registration result. ~~As of 19:50 EST it had not been written.~~ **Written 14 Nov 22:05 EST** with one layer,
`lroc-nac-avg-site01-center-2km` (`LROC NAC AVG · VISUAL`): 100 % of the Site01 site-centre crop, 78 % of the Site01 ROI6 crop;
Site04 has no registered image. See `docs/SCIENTIFIC_CONTRACT.md` § Scientific terrain versus visual layers.

## Terrain context packs (display only)

| Pack | Local 5 m crop (bundle) | Regional 80 m crop | Files |
|---|---|---|---|
| `site04_roi3` | ROI export `site04_roi3` (`cropValuesSha256` `7914bea1…`, re-verified) | two-site bundle `shackleton` (PGDA 90, source crop hash `e48bee96…`) | `context.json`, `regional_f32.bin`, `local_horizon_u8.bin`, `regional_horizon_u8.bin` |
| `site04_roi4` | ROI export `site04_roi4` (`77f1ca1b…`, re-verified) | same | same |
| `site01_roi6` | ROI export `site01_roi6` (`a04929aa…`, re-verified) | two-site bundle `connecting` (source crop hash `d27c5aa6…`) | same |
| `connecting` | Site01 source bundle `localDem` (`dce1fc20…`; not re-derivable, values stored rounded) | same | same |

Built by `tools/terrain/build_terrain_context.py` from files already in the repository (no download). Every output
file's SHA-256 is in its `context.json` and in `data/source_registry.json` → `derived.displayOnly`. The viewer loads a
pack only when `local.cropValuesSha256` equals the DEM crop it is drawing, and verifies the file hashes in the browser.
Role: rendering only. See `docs/SCIENTIFIC_CONTRACT.md` § Terrain context packs.


## Added 15 Nov 2026
- **PGDA 78 Site04 5 m tile** `app/data/source/pgda78/Site04/Site04_final_adj_5mpp_surf.tif`, SHA-256 matches the source registry
  (`38ff70db…`); bounds x −9000…7000 m, y −15000…1000 m. Used only to build the display-only L1 ring.
- **Terrain context L1 (`mid`)**: `mid_f32.bin` 401² float32 at 20 m (4×4 block means of the 5 m tile, aligned to its pixel
  lattice, ±4 km around the site) and `mid_horizon_u8.bin` (201² at 40 m, 48 azimuths); hashes in each `context.json`.
  VISUAL, `numericalAuthority: false`; never used by the solver.
- **NASA SVS 4930 frames 3805–3973** (https://svs.gsfc.nasa.gov/4930/), 169 TIFFs, used only for the comparison in
  `docs/validation/SVS4930_RESULT.md`; every frame SHA-256 is in `data/validation/svs4930/svs4930_comparison.json`.
  Frames are kept in `tmp/svs4930/` (git-ignored), not shipped.

## NASA GSFC shape-from-shading elevation (display only, added 15 Nov 2026)
- Product: `A306_GLDELEV_005.tif`, Artemis III candidate region 6 "Connecting Ridge" (x −19000…−3000 m, y −20000…−4000 m, 5 m, 3200²,
  `+proj=stere +lat_0=-90 +lon_0=0 +R=1737400`). Bertone, S., McKenna, T. E., Barker, M. K., Mazarico, E., Beyer, R. A., Petro, N. (2025),
  Zenodo, doi:10.5281/zenodo.17954508; paper doi:10.3847/PSJ/ae5b70. Licence CC-BY-4.0 (attribution required).
- From `A3CLR22_6_Connecting_Ridge.zip` (2,206,485,514 bytes, md5 `0ad982cf42319a300f2a2cff69d39322`); file SHA-256 in the zip
  `c914e52bf1e46c08b9c409d6ebd6a3605ad33756373571138b8d473dadaeddd0`. The copy in `app/data/source/gsfc_sfs_a3clr22/` was rewritten in transfer
  (container differs); its decoded float32 pixels are identical: pixel SHA-256 `8d7a4a2036d73555da50e682b9385e3ed96b3e66d628b50af88ae9d9aa66134c`
  (checked by the pack builder).
- Role: display surface of the 5 m crop and the L1 ring in `web/` and Blender. Never read by the solver.

## v2 whole-Moon terrain inputs (S2, added 16 Nov 2026)
Downloaded by `tools/globe/fetch.py` from the catalogue `tools/globe/products.py` into `$POLARIS_DATA/v2/products/<product_id>/`
(git-ignored). Each file has one line in `$POLARIS_DATA/v2/manifest.jsonl` with URL, SHA-256, bytes, licence, acknowledgement,
retrieval UTC and product version; the committed mirror is `docs/v2/DATA_MANIFEST.json`. Details, versions and exact file
lists: `docs/v2/PRODUCTS.md`; sizes: `docs/v2/DATA_BUDGET.md`. All of these are SOURCE-BASED · UNVALIDATED inputs; frames and datums
are converted (with tests) by the pyramid code, not here.

| product_id | Source and credit (use this wording) |
|---|---|
| `lola_ldem_global`, `lola_ldem_polar`, `lola_roughness_gdr` | NASA PDS Geosciences Node. Smith, D.E.; Neumann, G.A. (2023). Lunar Reconnaissance Orbiter LOLA Processed Data (RDR) Bundle, urn:nasa:pds:lro_lola_rdr v1.0. NASA Planetary Data System. https://doi.org/10.17189/tnyt-7007 |
| `sldem2015_512` | NASA PDS Geosciences Node (LOLA bundle, sldem2015 collection); PGDA product 54. Cite: Barker, M. K., Mazarico, E., Neumann, G. A., Zuber, M. T., Haruyama, J., Smith, D. E. "A new lunar digital elevation model from the Lunar Orbiter Laser Altimeter and SELENE Terrain Camera," Icarus, Volume 273, p. 346-355. http://dx.doi.org/10.1016/j.icarus.2015.07.039 |
| `pgda67_slope_azimuth_64` (and `_128` if fetched) | NASA PGDA product 67 (E. Mazarico), files on the LOLA node at MIT. Cite Barker et al. (2016), as above |
| `pgda70_roughness` | NASA PGDA product 70 (M. K. Barker), files on the LOLA node at MIT (EXTRAS, unsupported by the LOLA Science Team). "Please acknowledge Rosenburg et al. (2011) if you use these data products": Rosenburg, M. A., et al., Global surface slopes and roughness of the Moon from the Lunar Orbiter Laser Altimeter, JGR 116, E02001 (2011), doi:10.1029/2010JE003716 |
| `lroc_wac_100m` | LROC WAC global morphologic mosaic 100 m, June 2013: NASA/GSFC/Arizona State University; distributed by USGS Astrogeology Science Center (MD5 sidecar verified). VISUAL only |

Not downloaded: Chandrayaan-2 TMC-2 (ISRO PRADAN) and CNSA Chang'e DEMs need an account the user has not approved; Kaguya TC DTMs,
LROC NAC DTMs and further SfS regions are per-tile/per-site products to stream on demand (see `docs/v2/PRODUCTS.md`).

## Mercury inputs (R6, added 16 Nov 2026)
Downloaded by `python -m science.worlds.mercury.fetch` (the S2 fetcher `tools/globe/fetch.py` on the Mercury catalogue
`science/worlds/mercury/products.py`) into `$POLARIS_DATA/v2/products/mercury_*/` (git-ignored). Each file has one line in
`$POLARIS_DATA/v2/manifest.jsonl` (URL, SHA-256, bytes, licence, acknowledgement, retrieval UTC, product version). All
public, no login. SOURCE-BASED · UNVALIDATED inputs; datum conversions and their tests: `science/worlds/mercury/dem.py`,
`science/worlds/tests/test_mercury_data.py`; findings: `docs/v2/PHASE_6_WORLDS_RESULTS.md` §2.

| product_id | Source and credit (use this wording) |
|---|---|
| `mercury_mla_gdr_v2`, `mercury_mla_gdr_v1` | MESSENGER Mercury Laser Altimeter gridded data records, PDS data sets MESS-E/V/H-MLA-4-GDR-V2.0 and -V1.0 (MESSENGER MLA team, D. E. Smith, NASA GSFC), NASA PDS Geosciences Node. Zuber, M. T., et al. (2012), Topography of the northern hemisphere of Mercury from MESSENGER laser altimetry, Science 336, 217–220. MESSENGER: NASA/JHU APL/Carnegie Institution of Washington |
| `mercury_usgs_dem_665m_v2` | USGS Astrogeology Science Center. Becker, K. J., et al. (2016), First global digital elevation model of Mercury, LPSC XLVII, abstract 2959 (MD5 sidecar verified) |
| `mercury_mdis_bdr_166m`, `mercury_mdis_color_665m`, `mercury_mdis_polar_250m` | MESSENGER MDIS basemaps (NASA/JHU APL/Carnegie Institution of Washington); Denevi, B. W., et al. (2018), Space Sci. Rev. 214, 2; distributed by USGS Astrogeology (MD5 sidecars verified). VISUAL only |
| `mercury_pgda85_prokofiev` | NASA GSFC PGDA product 85. "Please cite": Barker, M. K., Chabot, N. L., Mazarico, E., Siegler, M., Martinez-Camacho, J. M., Hamill, C., Bertone, S. (2022), New Constraints on the Volatile Deposit in Mercury's North Polar Crater, Prokofiev, PSJ 3, 188. Its radar layer derives from Arecibo data of Harmon, J. K., Slade, M. A., Rice, M. S. (2011), Icarus 211, 37–50. The posted `.cub` stack is truncated at the source; the per-layer ZIP is used |
| `mercury_pgda88_south_pole` | NASA GSFC PGDA product 88; Bertone, S., Mazarico, E., Barker, M. K., Siegler, M. A., Martinez Camacho, J. M., Hamill, C. D., Glatzenberg, A. K., Chabot, N. L. (2026), Supplementary material to: Highly resolved topography and illumination at Mercury south pole from MESSENGER MDIS-NAC, v1.1.0, Zenodo, https://doi.org/10.5281/zenodo.19740142, CC-BY-4.0 |
| `mercury_mla_radr_v4` | NASA GSFC PGDA product 64 (G. A. Neumann). "Please cite": Deutsch, A. N., Neumann, G. A., Head, J. W. (2017), GRL 44 |
| `mercury_horizons` | JPL Horizons API (DE441) responses, cached by query SHA-256 with sidecars; SHA-256 of each response in the Mercury bundle |

Not downloaded: MDIS LOI 166 m (duplicate VISUAL use); a georeferenced global/south-polar radar-bright map (none public found;
figures such as PIA16514 are not data and were not digitised). Comms threshold source: DSN Telecommunications Link Design
Handbook 810-005, module 106 Rev. B (2010), §2.3.

## Mars inputs and NAIF kernels (T3, added 17 Nov 2026)
Downloaded by `python -m science.worlds.mars.fetch` (the S2 fetcher on the catalogue `science/worlds/mars/products.py`) into
`$POLARIS_DATA/v2/products/mars_*/` (git-ignored): **0.533 GB, 28 files**, each with one line (URL, SHA-256, bytes, licence,
acknowledgement, retrieval UTC) in `$POLARIS_DATA/v2/manifest.jsonl`. All public, no login. SOURCE-BASED · UNVALIDATED
inputs; datum tests in `science/worlds/tests/test_mars.py`; findings in `docs/v2/PHASE_6_T3_RESULTS.md` §4.

| product_id | Source and credit (use this wording) |
|---|---|
| `mars_mola_megdr_004`, `mars_mola_megdr_016`, `mars_mola_megdr_128_44n000` | Smith, D. E., Neumann, G., Arvidson, R. E., Guinness, E. A., Slavney, S. (2003), Mars Global Surveyor Laser Altimeter Mission Experiment Gridded Data Record, MGS-M-MOLA-5-MEGDR-L3-V1.0, NASA Planetary Data System (PDS Geosciences Node, mgsl_300x). Smith, D. E., et al. (2001), JGR 106(E10), 23689–23722. Radius files = radius − 3 396 000 m; IAU 2000 planetocentric coordinates |
| `mars_ctx_jezero_sci_20m` | Mars 2020 Science Investigation CTX DEM mosaic (urn:nasa:pds:mars2020_ctx_basemap_2021), JPL/USGS Astrogeology; cite Mangold, N., et al. (2021), Science 374, 711–717, doi:10.1126/science.abl4051. CTX: NASA/JPL/MSSS. Heights are MOLA-areoid heights (tested; the XML prose names the 3 396 190 m sphere) |
| `mars_ctx_jezero_trn_20m` | Fergason, R. L., et al. (2020), Mars 2020 Terrain Relative Navigation flight product generation, LPSC 51 #2020; USGS Astrogeology, doi:10.5066/P906QQT8. CTX: NASA/JPL/MSSS |
| `mars_naif_pck` | NAIF generic PCKs pck00010.tpc and pck00011.tpc (JPL/NASA, public); MESSENGER pck00010_msgr_v23.tpc (PDS NAIF node, mess-e_v_h-spice-6-v1.0). Rotation models: Archinal et al. (2011, 2018), Celest. Mech. Dyn. Astron. 109:101 and 130:22; Seidelmann et al. (2002) for the IAU 2000 Mars model MOLA uses |
| `mars_horizons`, `mercury_horizons` | JPL Horizons API (DE441) responses, cached by query SHA-256 with sidecars; SHA-256 of each response in the bundles |

Site coordinates: USGS Gazetteer of Planetary Nomenclature, Jezero (feature 14300, MDIM 2.1), retrieved 2026-11-17. Ls:
Allison & McEwen (2000), PSS 48, 215 (Mars24). Solar constant 1361 W/m² (Kopp & Lean 2011). Comms threshold: DSN 810-005
module 106 Rev. B §2.3. Not downloaded: HiRISE 1 m TRN tiles (0.76 GB, landing ellipse only), the other 15 MOLA 128 ppd
tiles (4.9 GB), HRSC DTMs, relay-orbiter ephemerides (not wired).
