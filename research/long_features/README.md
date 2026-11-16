# Long-feature research handoff

These are standalone research scripts and result JSON files. They are not imported by, or used to compute values in,
the POLARIS X app. The Decision Lab is a separately supplied static evidence viewer for these results.

Data sources:

- NASA PGDA products 78, 90 and 69.
- NASA/JPL Horizons.
- NASA GSFC shape-from-shading DEM: Bertone et al. (2026), Zenodo
  [doi:10.5281/zenodo.17954508](https://doi.org/10.5281/zenodo.17954508), CC-BY-4.0; attribution is required.
- LROC `WAC_POLE_ILL_TWI_SOUTH_100M` illumination map from the Planetary Data System (PDS).

Large NASA raster inputs are downloaded by `code/fetch.py` and are never committed to this repository.

Batch-2 research additions:

- `code/sites.py` centralizes the four reference-site coordinates and `SITES` selection; it supplies site mappings to the analysis scripts and a helper for merged JSON outputs.
- `code/step15_new_prep.py` takes the shared Site07/Site11 definitions plus the external PGDA/Horizons cache, downloads 20 clones per site, and writes yearly and 18.6-year ephemeris NPZ files plus `work/eph_meta.json`.
- `code/step17_surrogate.py` ranks a ±500 m, 25 m-grid candidate field with a coarse horizon and full-solver re-checks; it reads DEM/ephemeris caches and writes `work/surrogate.json`.
- `code/step18_hot_corr.py` uses nominal/clone horizons, correlated clone height errors and existing hotspot calibration to build a greedy measurement plan; it writes `work/hot_corr.json` (or `OUT`) for the selected sites/clones.
- `code/step18b_test.py` full-ray-marches the first five and ten correlated-error plan cells against all 20 clones and appends `full_ray_test` results to `work/hot_corr.json`.
- `code/step18c_oos.py` trains from `work/hot_corr_train.json` clones 1–10, full-ray tests strategies on unseen clones 11–20, and appends `out_of_sample` results to `work/hot_corr.json`.
- `code/run_new.sh` is the supplied cloud-workspace orchestration sequence for Site07/Site11; it consumes the prepared `work/` and external-data caches and runs the scripts that produce the new result JSON files.
