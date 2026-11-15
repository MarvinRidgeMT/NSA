# polaris_solver (API for the POLARIS X solver)

One JSON request in, one JSON result out. Same physics as `polaris_batch` v2 core (with the float64 height fix):
720 azimuth bins, 1 m ray step to 25 km on the NASA PGDA 78 5 m LOLA tile, PGDA 90 80 m to 280 km, spherical Moon,
JPL Horizons topocentric Sun/Earth (airless apparent). SOURCE-BASED, UNVALIDATED; geometric visibility only.

```bash
pip install numpy scipy pyproj rasterio pytest
export POLARIS_DATA=data/external          # cache for NASA files + raw Horizons responses (downloads on first use)
python -m polaris_solver request.json       # request: {"lat": -89.78012, "lon": -156.32023, "mast_m": 1, "clones": 20}
python -m polaris_solver --serve 8765        # POST /solve, GET / -> tool spec for an AI assistant
python -m polaris_solver --tool-spec
pytest -q tests                              # needs network the first time (NASA + JPL), then runs from cache
```

Result: `nominal` {sun_pct, sun_earth_pct, earth_pct, longest_dark_h}, `nominal_passes`, optional `clones` {ranges, pass_k_of_n,
verdict, note}, optional `hourly` margins, `provenance` (file SHA-256s, raw Horizons file hashes, method), `labels`.
"pass on k of N" counts NASA terrain clones tested; it is never a probability.
Tool spec (`TOOL_SPEC`) is ready for function calling; an assistant must quote numbers only from this result.
