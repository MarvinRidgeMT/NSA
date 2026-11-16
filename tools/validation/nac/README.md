# LROC NAC illumination comparison (15 Nov 2026)

Result: `docs/validation/NAC_ILLUMINATION_RESULT.md`. Author: Claude (Penumbra session). Python 3, numpy, scipy, rasterio,
spiceypy, remotezip.

Data, not in the repo (about 2.6 GB), fetched into the folder the scripts run from:
- `pgda78/Site01|Site04|Site07|Site11_final_adj_5mpp_surf.tif` and `pgda90/LDEM_80S_80MPP_ADJ.TIF` (NASA PGDA products 78 and 90);
- `spice/` NAIF kernels listed in the result doc;
- `nac/` (region 6), `nac8/` and `nac9/` images from Zenodo 10.5281/zenodo.17954508, downloaded by `dl89.py` and `dl8.py`.
  The region 6 image list and times are in `nac_cams.json`.

Order:
1. v1: `nac_compare.py` → `nac_analyze.py` (`nac_summary.json`).
2. v2: `nac_compare_v2.py` → `nac_v2_analyze.py` (`nac_v2_summary.json`).

Each compare script checks its protocol `.md` against the `.sha256` frozen beside it and refuses to run on a mismatch.
`dl89.py` writes a `sun` field from the camera file with a wrong slice. Nothing uses it: the Sun is computed from ET with SPICE.
