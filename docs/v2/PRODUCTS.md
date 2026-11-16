# v2 terrain and imagery products: official pages, versions, files, terms (S2; prompt §2.1)

Verified 16 Nov 2026 (EST) by reading each archive's live directory listing. Byte counts are exact from those listings
and are re-checked with HEAD by `python -m tools.globe.fetch --check` (172/172 OK at 02:30 EST). The machine-readable
form is `tools/globe/products.py`, and each downloaded file is recorded in `$POLARIS_DATA/v2/manifest.jsonl`
(mirror: `docs/v2/DATA_MANIFEST.json`).

No product here is validated by POLARIS: these are SOURCE-BASED · UNVALIDATED inputs. Frames and datums are taken from
each product's PDS label. Every conversion into the contract frame (heights above 1,737,400 m, MOON_ME,
east-positive) belongs to S3 and needs its own test there.

Archive roots used:
- PDS Geosciences Node, LOLA RDR bundle `urn:nasa:pds:lro_lola_rdr` v1.0 (PDS3 volume LRO-L-LOLA-3-RDR-V1.0):
  `https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/`
- LOLA science-team node at MIT, linked from the PGDA product pages: `http://imbrium.mit.edu/` (plain HTTP only).
- USGS Astrogeology map-a-planet mosaics: `https://planetarymaps.usgs.gov/mosaic/`, which redirects to the public S3
  bucket `https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/`.

## Acknowledgement wording (use verbatim in credits)
| Key | Wording | Where it comes from |
|---|---|---|
| LOLA RDR (PDS) | Smith, D.E.; Neumann, G.A. (2023). *Lunar Reconnaissance Orbiter LOLA Processed Data (RDR) Bundle*, urn:nasa:pds:lro_lola_rdr v1.0. NASA Planetary Data System. https://doi.org/10.17189/tnyt-7007 | `bundle_lola_rdr.xml` `<Citation_Information>` (author_list, publication_year, doi) |
| SLDEM2015 (PGDA 54) | "If using this dataset, please cite the following paper: Barker, M. K., Mazarico, E., Neumann, G. A., Zuber, M. T., Haruyama, J., Smith, D. E. "A new lunar digital elevation model from the Lunar Orbiter Laser Altimeter and SELENE Terrain Camera," Icarus, Volume 273, p. 346-355. http://dx.doi.org/10.1016/j.icarus.2015.07.039" | https://pgda.gsfc.nasa.gov/products/54 |
| PGDA 67 slope/azimuth | "Please cite the Barker et al. (2016) reference below if you use these products in your scientific work." (Barker et al. 2016, Icarus 273, 346–355) | https://pgda.gsfc.nasa.gov/products/67 |
| PGDA 70 slopes/Hurst | "Please acknowledge Rosenburg et al. (2011) if you use these data products." Rosenburg, M. A., et al., "Global surface slopes and roughness of the Moon from the Lunar Orbiter Laser Altimeter", 2011, JGR, 116, E2 (E02001), doi:10.1029/2010JE003716 | https://pgda.gsfc.nasa.gov/products/70 |
| LROC WAC mosaic | NASA/GSFC/Arizona State University (the LROC credit line); producer "Arizona State University", data set `WAC_morphology_globe_June2013_100m`; distributed by USGS Astrogeology Science Center | USGS `.lbl` (Archive group) and the LROC credit convention |
| GSFC SfS | Bertone, S., McKenna, T. E., Barker, M. K., Mazarico, E., Beyer, R. A., Petro, N. (2025), Zenodo, doi:10.5281/zenodo.17954508; paper doi:10.3847/PSJ/ae5b70. CC-BY-4.0 (attribution required) | Zenodo record (recorded 15 Nov in `docs/DATA_PROVENANCE.md`) |

Licence for the NASA PDS, PGDA and USGS products: these are U.S. Government works with no copyright restriction in the
U.S. Each archive's citation request above is the condition we honour. The LOLA node's `EXTRAS/` README says those
products are "made available, but are unsupported by the LOLA Science Team" (this covers PGDA 70).

## Downloaded tonight (`status = download`)
### 1. `lola_ldem_global` — LOLA gridded global LDEM, float (source_id 8)
- Page: `…/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/` (PDS4 collection `data_gridded` v1.0, 2023).
- Version: LRO-L-LOLA-3-RDR-V1.0. File dates: `ldem_16_float.img` 2019-03-04, `ldem_64_float.img` 2019-03-04,
  `ldem_128_float.img` 2017-09-06.
- Files: `ldem_16_float.img` 66,355,200 B; `ldem_64_float.img` 1,061,683,200 B; `ldem_128_float.img` 4,246,732,800 B;
  each with its `.lbl` (PDS3) and `.xml` (PDS4) label.
- Not fetched: the int16 `img/ldem_{4,16,64,128}.img` (the same grids quantised to 0.5 m); the 256 ppd float (4 files
  × 4.25 GB); 512 ppd int16 (16 files × 1.06 GB); 1024 ppd int16 (144 files × 0.94 GB).

### 2. `lola_ldem_polar` — LOLA polar stereographic LDEMs, float (source_id 7)
- Page: `…/data/lola_gdr/polar/float_img/`. North files are dated 2016-08-31 and south files 2017-06-02.
- Files: the finest post of each ring, both poles. Each is 4-byte float, square, polar stereographic on the
  1,737,400 m sphere:

  | ring | post | file (s / n) | bytes each | samples² |
  |---|---|---|---|---|
  | ≥ 87.5° | 5 m | `ldem_875{s,n}_5m_float.img` | 3,681,091,584 | 30,336² |
  | ≥ 85° | 10 m | `ldem_85{s,n}_10m_float.img` | 3,681,091,584 | 30,336² |
  | ≥ 80° | 20 m | `ldem_80{s,n}_20m_float.img` | 3,696,640,000 | 30,400² |
  | ≥ 75° | 30 m | `ldem_75{s,n}_30m_float.img` | 3,720,024,064 | 30,496² |
  | ≥ 60° | 60 m | `ldem_60{s,n}_60m_float.img` | 3,853,926,400 | 31,040² |
- Not fetched: the coarser posts of the same rings, `ldem_45{s,n}_{100,200,400}m`, and the int16 copies.
- Note: south of 80° S, PGDA 90 (20/40/80 m, already in the cache) is newer and outranks this product in the merge
  order.

### 3a. `pgda70_roughness` — PGDA 70 "Lunar slopes and Hurst exponent" (M. K. Barker)
- Page: https://pgda.gsfc.nasa.gov/products/70. Its download link goes to `http://imbrium.mit.edu/EXTRAS/FRACTAL/`.
- Version: files dated 2011-05-16, from LOLA Laser 1 and 2 data through mission phase LRO_NO_13.
- Files: `IMG/HE_8.IMG` 8,294,400 B (Hurst exponent, 8 ppd; fitted from 57 m to the breakover point, ≤ 2.7 km);
  `IMG/MAS_57M_16.IMG`, `IMG/MAS_225M_16.IMG`, `IMG/MAS_560M_16.IMG`, 33,177,600 B each (median absolute along-track
  slope, degrees, 16 ppd); each with its `.LBL`; plus `README_FRACTAL.TXT`.
- Use: statistics for VISUAL sub-resolution roughness (§2.3). These files are never science heights.

### 3b. `lola_roughness_gdr` — LOLA gridded roughness / slope (read as the prompt's "LOLA RMHE")
- No product named "RMHE" exists on the LOLA node. The matching archived products are the LOLA GDR RMS-height
  roughness maps `LDRM_*`, the slope maps `LDSM_*` and the roughness counts `LDRC_*`.
- Cylindrical (`…/lola_gdr/cylindrical/img/`):
  - `ldrm_16.img` (2012-06-08, roughness in metres, int16 × 0.001);
  - `ldsm_16.img` (2012-06-08, bidirectional slope at a 240 m baseline, degrees, int16 × 0.0015 + 45);
  - `ldrm_32_n.img`, `ldrm_32_25.img`, `ldrm_32_50.img`, `ldrm_32_75.img` (2019-09-03; roughness and its 0.25/0.5/0.75
    quantiles at 32 ppd);
  - `ldrc_32.img` (count).
  The 16 ppd files are 33,177,600 B and the 32 ppd files 132,710,400 B.
- Polar (`…/lola_gdr/polar/img/`): `ldrm_75{s,n}_240m`, `ldsm_75{s,n}_240m` (29,062,688 B each);
  `ldrm_85{s,n}_40m`, `ldsm_85{s,n}_40m` (115,034,112 B each).
- The labels say the slope baseline "may vary from 30 to 120 meters" with spacecraft altitude.

### 4. `pgda67_slope_azimuth_64` — PGDA 67 slope and azimuth from SLDEM2015 (E. Mazarico)
- Page: https://pgda.gsfc.nasa.gov/products/67. Data: `http://imbrium.mit.edu/DATA/SLDEM2015_SLOPE/` and `…/SLDEM2015_AZIMUTH/`.
- Version: files dated 2017-07-10, labels 2018-07-11. Coverage is pole to pole.
- Files: `GLOBAL/FLOAT_IMG/SLDEM2015_64_SL_90S_90N_000_360.IMG` and `…_64_AZ_…IMG`, 1,061,683,200 B each, with
  their `.LBL`s.
- The page warns that the pixel size is the slope baseline, so 64 ppd and 512 ppd slopes differ systematically.
- Catalogued, not fetched: 128 ppd (4,246,732,800 B per layer; queued as optional priority 7); 256 ppd
  (16,986,931,200 B per layer); 256 ppd tiles (12); 512 ppd tiles (48 × 1,415,577,600 B per layer).

### 5. `sldem2015_512` — SLDEM2015 512 ppd (source_id 6)
- Page: https://pgda.gsfc.nasa.gov/products/54 (M. K. Barker). It links the MIT copy `http://imbrium.mit.edu/DATA/SLDEM2015/`.
  Files are fetched from the PDS Geosciences copy, the archive of record: `…/lrolol_1xxx/data/sldem2015/tiles/float_img/`.
- Version: SLDEM2015 (Barker et al. 2016). Tiles dated 2015-07-14, labels 2015-08-10.
- Files: 32 tiles `sldem2015_512_{00n_30n,30n_60n,30s_00s,60s_30s}_{000_045,…,315_360}_float.img`, each
  1,415,577,600 B (23,040 × 15,360 float32), each with its `.lbl`; plus `global/float_img/sldem2015_data_quality_float.img`
  (172,800 B).
- Not fetched: the JPEG2000 tiles (32 × ~0.16–0.19 GB), the 256 ppd float tiles (6 × 1.89 GB), and the 128 ppd global
  float (2,831,155,200 B).

### 6. `lroc_wac_100m` — LROC WAC global morphologic mosaic, 100 m
- Page: USGS Astrogeology "Moon LRO LROC WAC Global Morphology Mosaic 100m" (map-a-planet mosaic directory).
- Version: `WAC_morphology_globe_June2013_100m` (ASU, June 2013); USGS copy dated 2022-11-08.
- Files: `Lunar_LRO_LROC-WAC_Mosaic_global_100m_June2013.tif` 5,959,263,751 B (109,164 × 54,582, uint8, simple
  cylindrical, 303.2333 ppd, longitude −180…180, sphere 1,737,400 m). The MD5 sidecar (`9f4774ad7fea0eeb4ba3c06e585844a1`)
  is verified at download. Also fetched: `.lbl`, `_pds3.lbl`, `.cub.xml`.
- Use: albedo/texture, VISUAL only.

### 7 (optional). `pgda67_slope_azimuth_128` — PGDA 67 128 ppd global slope + azimuth, 2 × 4,246,732,800 B.

## Already in the cache (`status = have`)
- **PGDA 90** LOLA south polar 20/40/80 m (`LDEM_80S_80MPP_ADJ.TIF`): see `docs/DATA_PROVENANCE.md` § NASA terrain.
- **PGDA 78** 5 m site tiles and 20+ clones per site: `data/cache/p78`, `data/external/pgda78`, `app/data/source/pgda78`.

## Not downloaded (`status = not-downloaded`)
| Product | Official page | Why not | Notes |
|---|---|---|---|
| Kaguya TC DTMs: JAXA SLDEM2013 / TC DTM MAP | JAXA DARTS SELENE archive, https://darts.isas.jaxa.jp/planet/pdap/selene/ | A ~10 m-class global surface is ≈ 4 × 10¹¹ px ≈ 0.8 TB; §2.1 says stream it per tile and never mirror it | JAXA SELENE acknowledgement wording: see § JAXA below |
| USGS ASP Kaguya TC DTMs | USGS Astrogeology | Per-tile, on demand | — |
| LROC NAC DTMs (SDNDTM / ASPDTM) | https://wms.lroc.asu.edu/lroc/rdr_product_select | Hundreds of sites at ~0.1–2 GB each; per site on demand (S4/S6) | Credit NASA/GSFC/Arizona State University |
| GSFC SfS polar DEMs | https://doi.org/10.5281/zenodo.17954508 | Per region on demand (e.g. A3CLR22 region 6 zip is 2,206,485,514 B); one region already used for display | CC-BY-4.0 |
| LROC NAC images | https://wms.lroc.asu.edu/lroc | S6 imagery catalogue (`tools/imagery`) | — |
| Chandrayaan-2 TMC-2 DEMs | ISRO ISSDC PRADAN, https://pradan.issdc.gov.in/ | **not downloaded: needs an account the user has not approved** | No account was created and no terms were accepted |
| CNSA Chang'e DEMs | CNSA/NAOC Lunar and Planetary Data Release System, https://moon.bao.ac.cn/ | **not downloaded: needs an account the user has not approved** | No account was created |
