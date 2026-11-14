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

## JPL ephemeris

JPL Horizons was queried for target 10 (Sun) and target 399 (Earth), observer centre `coord@301`, geodetic lunar coordinates, airless apparent angles, UTC and 60-minute steps. Each raw text response is retained under a bundle-specific directory in `app/data/raw/jpl/`. The query URL, parsed API version, requested/reported centre and raw-response SHA-256 are embedded beside the samples.

## Bundles

| Artifact | Content | SHA-256 |
|---|---|---|
| `polaris-source-site01-2026-11-14-v2.json` | Site01 regional + 5 m + RMS + four clones + JPL | `6a16ee59965e47afe54527c0b2bcdd90c6d40ba40a2423ca964e7da8e89a4fb6` |
| `polaris-source-two-site-2026-11-14-v2.json` | Site01 and Site04 regional + JPL | `b60129a0399e9dd58ab42e6fb7fe76c82355b2b823dbbf4f3fa80e3aa87658ee` |
| `polaris-offline-source-case.json` | Compact two-site startup cache | `11919cfbbd9d84e68dad02520dadfc95880dd3a40aabe16d9e60a8e48a1dfee3` |

The compact cache deliberately omits the 5 m nominal terrain, RMS layer and clones. Import the full Site01 bundle in the app to select those realizations.

## Reproduction

Install `requirements-science.txt`, then run `app/scripts/prepare_science.py --help`. The checked-in source bundles use the exact commands documented in `docs/BUILD_STATUS.md`. A future API response can be numerically equivalent but byte-different, so each run receives its own raw-response directory and hashes.
