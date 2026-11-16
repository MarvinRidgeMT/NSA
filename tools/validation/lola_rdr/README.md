# LOLA RDR shot density near RoI centres

```bash
python3 tools/validation/lola_rdr/query_rdr.py            # both sites, ~20 s each, synchronous ODE GDS REST
```

- Endpoint: `https://oderest.rsl.wustl.edu/livegds/?query=lolardr&results=u&output=JSON&minlat&maxlat&westernlon&easternlon` (GDS REST manual §4.5). `results=u` = simple topography CSV, valid shots only (flag=0).
- Box: ±1 km square around the bundle RoI centre in south-polar stereographic (R = 1737.4 km, matches the bundle `grid_x_m/grid_y_m`); 5 m cells.
- Raw CSVs + `manifest.json` (query URL, CSV URL, fetch time) go to `data/cache/lola_rdr/<site>/` (git-ignored).
- Numbers go to `data/science_limits/lola_shots/<site>.json`: shot count, cells with ≥1 shot, median / p90 nearest-shot distance over all 160 000 cells.
- **Not computed:** the 10 highest-lit crest cells vs all cells. That needs per-cell lit fraction from the solver; the JSON says `"computed": false`.
- No conclusions are drawn from these numbers here.
