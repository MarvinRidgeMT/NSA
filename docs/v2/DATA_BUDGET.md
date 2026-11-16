# v2 data budget (S2; prompt §2.1, §0.4)

All numbers come from the archives' own directory listings (read 16 Nov 2026) or from pixel arithmetic. Byte counts are
exact; GB = 10⁹ bytes. The disk had ~496 GB free on the internal drive when downloads started, and there is no external
SSD. Tonight's limits: ≤ 150 GB of new data, and ≥ 250 GB left free (enforced per file by `tools/globe/fetch.py`).

## Downloaded tonight (planned; the actual totals are in the "Result" section below)
| product_id | Grid (samples × lines) | Pixels | Type | Bytes on disk (uncompressed) | Compressed alternative on the archive |
|---|---|---|---|---|---|
| `lola_ldem_global` 16 ppd | 5,760 × 2,880 | 1.66 × 10⁷ | float32 | 66,355,200 | int16 `ldem_16.img` 33,177,600 |
| `lola_ldem_global` 64 ppd | 23,040 × 11,520 | 2.65 × 10⁸ | float32 | 1,061,683,200 | int16 530,841,600 |
| `lola_ldem_global` 128 ppd | 46,080 × 23,040 | 1.06 × 10⁹ | float32 | 4,246,732,800 | int16 2,123,366,400 |
| `lola_ldem_polar` 87.5° 5 m (×2 poles) | 30,336² | 9.20 × 10⁸ each | float32 | 3,681,091,584 each | int16 1,840,545,792 |
| `lola_ldem_polar` 85° 10 m (×2) | 30,336² | 9.20 × 10⁸ each | float32 | 3,681,091,584 each | int16 1,840,545,792 |
| `lola_ldem_polar` 80° 20 m (×2) | 30,400² | 9.24 × 10⁸ each | float32 | 3,696,640,000 each | int16 1,848,320,000 |
| `lola_ldem_polar` 75° 30 m (×2) | 30,496² | 9.30 × 10⁸ each | float32 | 3,720,024,064 each | int16 1,860,012,032 |
| `lola_ldem_polar` 60° 60 m (×2) | 31,040² | 9.63 × 10⁸ each | float32 | 3,853,926,400 each | int16 1,926,963,200 |
| `pgda70_roughness` (Hurst 8 ppd + 3 × MAS 16 ppd) | 2,880 × 1,440; 5,760 × 2,880 | 5.4 × 10⁷ | int16/float (see .LBL) | 107,828,078 | — |
| `lola_roughness_gdr` (LDRM/LDSM/LDRC cyl. + polar 75/85) | 16–32 ppd; polar 240 m / 40 m | 6.5 × 10⁸ | int16 | 1,308,516,800 | — |
| `pgda67_slope_azimuth_64` (slope + azimuth) | 23,040 × 11,520 ×2 | 5.3 × 10⁸ | float32 | 2,123,366,400 | GeoJPEG2000 copies |
| `sldem2015_512` (32 tiles of 45° × 30°) | 23,040 × 15,360 each | 1.13 × 10¹⁰ total | float32 | 45,298,483,200 (+ 172,800 quality map) | JPEG2000: 5,403,050,925 (32 tiles) |
| `lroc_wac_100m` | 109,164 × 54,582 | 5.96 × 10⁹ | uint8 | 5,959,263,751 | — |
| `pgda67_slope_azimuth_128` (optional) | 46,080 × 23,040 ×2 | 2.1 × 10⁹ | float32 | 8,493,465,600 | — |
| PDS labels (.lbl/.xml/.LBL/.md5) | | | text | < 2 MB | |
| **Planned total** | | **~3.9 × 10¹⁰ pixels** | | **105.93 GB** | |

Check against the prompt's estimate: SLDEM2015 at 512 ppd over ±60° has 184,320 × 61,440 = 1.13 × 10¹⁰ pixels, i.e.
22.6 GB as int16 (the prompt's "~22 GB") but **45.3 GB as the float32 product actually on PDS**. No official int16
512 ppd copy exists. The JPEG2000 tiles (5.4 GB) are about 8.4× smaller, but their compression has not been checked
here, so they are not used for science.

## Not downloaded: what they would cost
| Product | Size estimate | Why not tonight |
|---|---|---|
| PGDA 67 slope + azimuth 256 ppd global | 2 × 16,986,931,200 B = 34.0 GB | Not "modest"; slope can be derived from SLDEM2015 |
| PGDA 67 slope + azimuth 512 ppd tiles | 48 tiles × 1,415,577,600 B × 2 layers = 135.9 GB | Far over budget |
| LOLA global LDEM 256 ppd float | 4 × 4,246,732,800 B = 17.0 GB | SLDEM2015 is finer within ±60°, polar LDEMs are finer beyond |
| LOLA global LDEM 512 ppd (int16 tiles) / 1024 ppd (int16 tiles) | 16 × 1.06 GB = 17.0 GB / 144 × 0.94 GB = 135.9 GB | Mostly interpolation between LOLA tracks at low latitude; SLDEM2015 is the better 512 ppd surface |
| LOLA polar 45° 100 m float (×2) | 2 × 3,317,760,000 B = 6.6 GB | Covered by SLDEM2015 (±60°) + 60° 60 m polar |
| Kaguya TC global ~10 m class surface | ≈ 4 × 10¹¹ px ≈ 0.8 TB (int16) | Stream by tile on demand; never mirror whole (§2.1) |
| Kaguya TC ortho mosaic 4096 ppd (USGS JPEG2000) | 194,731,159,794 B = 194.7 GB | Imagery, over budget |
| LROC WAC GLD100 DTM 100 m (USGS) | 10,461,394,351 B = 10.5 GB | Not in the §2.1 list; possible independent DTM later |
| LROC NAC DTMs | ~0.1–2 GB per site, hundreds of sites | Per site on demand |
| GSFC SfS (Zenodo 17954508) | see `docs/v2/PRODUCTS.md` | Per region on demand |
| Chandrayaan-2 TMC-2, CNSA Chang'e | — | Need an account the user has not approved |

## Result (filled in at the end of the session)
See the S2 section of `docs/BUILD_STATUS.md` and `docs/v2/DATA_MANIFEST.json` (the totals block) for the bytes
actually downloaded and hashed tonight.
