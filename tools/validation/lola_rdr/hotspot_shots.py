#!/usr/bin/env python3
"""Nearest LOLA RDR shot distance at the stored hotspot top-10 tiles vs all 5 m cells.

Reads cached CSVs from query_rdr.py (data/cache/lola_rdr/<site>/) and data/stretch/hotspots/<site>.json.
Hotspot tiles are ranked by clone-jacobian critical-margin score, NOT by lit fraction; this is the
closest per-tile product stored in the repo. Adds a "top10_hotspot_tiles" block to
data/science_limits/lola_shots/<site>.json. Numbers only, no conclusions.
"""
import csv, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from query_rdr import ROOT, ps_xy, nearest_dists, median, HALF_M

for site in ("site04_roi3", "site01_roi6"):
    out_p = ROOT / "data/science_limits/lola_shots" / f"{site}.json"
    out = json.loads(out_p.read_text())
    shots = []
    for f in sorted((ROOT / "data/cache/lola_rdr" / site).glob("*.csv")):
        rd = csv.reader(f.open()); next(rd, None)
        for r in rd:
            try: shots.append(ps_xy(float(r[1]), float(r[0])))
            except (ValueError, IndexError): pass
    hs = json.loads((ROOT / "data/stretch/hotspots" / f"{site}.json").read_text())
    top = hs["top_tiles"][:10]
    pts = [(t["grid_x_m"], t["grid_y_m"]) for t in top]
    cx, cy = ps_xy(out["centre"]["lat_deg"], out["centre"]["lon_deg_east"])
    inside = [abs(x - cx) <= HALF_M and abs(y - cy) <= HALF_M for x, y in pts]
    d = nearest_dists(pts, shots)
    out["top10_hotspot_tiles"] = {
        "source": f"data/stretch/hotspots/{site}.json ({hs['result_id']}, ranked by clone-jacobian critical-margin score, not lit fraction)",
        "n_tiles": len(top), "all_inside_box": all(inside),
        "median_nearest_shot_m": round(median(d), 2),
        "max_nearest_shot_m": round(max(d), 2),
        "per_tile": [{"tile_id": t["tile_id"], "rank": t["rank"], "nearest_shot_m": round(v, 2)} for t, v in zip(top, d)],
    }
    out["top10_lit_crest_cells"]["reason"] = ("no per-5m-cell lit-fraction grid is stored in the repo; "
        "see top10_hotspot_tiles for the closest stored per-tile product")
    out_p.write_text(json.dumps(out, indent=2) + "\n")
    print(site, {k: v for k, v in out["top10_hotspot_tiles"].items() if k != "per_tile"} | {"all_cells_median": out["all_cells"]["median_nearest_shot_m"]})
