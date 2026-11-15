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
