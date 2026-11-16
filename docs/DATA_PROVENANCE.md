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
