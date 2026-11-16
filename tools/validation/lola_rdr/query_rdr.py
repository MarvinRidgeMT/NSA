#!/usr/bin/env python3
"""Query LOLA RDR shots (PDS Geosciences ODE GDS REST) within +/-1 km of RoI centres.

Endpoint and parameters from the GDS REST Interface Manual
(https://oderest.rsl.wustl.edu/GDS_REST_V2.0.pdf, section 4.5):
    https://oderest.rsl.wustl.edu/livegds/?query=lolardr&results=u&output=JSON
        &minlat=..&maxlat=..&westernlon=..&easternlon=..   (lon east 0-360, planetocentric lat)
`results=u` returns URLs of "Simple Topography Per Row" CSVs (valid shots only, flag=0):
    Pt_Longitude, Pt_Latitude, Topography

Outputs
  data/cache/lola_rdr/<site>/*.csv + manifest.json   (git-ignored cache; manifest has query URLs)
  data/science_limits/lola_shots/<site>.json         (shot counts and nearest-shot distances only)

The +/-1 km box is in south-polar stereographic metres (sphere R = 1737.4 km) around the RoI
centre from the stored bundle. The lat/lon query box is the bounding box of that square, then shots
are clipped to the square. The 10-highest-lit-crest-cell comparison is NOT computed here (it needs
per-cell lit fraction from the solver); the JSON records it as not computed.

Usage:  python3 tools/validation/lola_rdr/query_rdr.py [--sites site04_roi3 site01_roi6]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ENDPOINT = "https://oderest.rsl.wustl.edu/livegds/"
R_M = 1737400.0
HALF_M = 1000.0
CELL_M = 5.0
TIMEOUT_S = 180

SITES = {
    "site04_roi3": "data/bundles/site04_roi3_2026-11-14_14d_mast1m.json",
    "site01_roi6": "data/bundles/site01_roi6_2026-11-14_14d_mast1m.json",
}


def ps_xy(lat_deg: float, lon_deg: float) -> tuple[float, float]:
    """South-polar stereographic (true scale at pole), x toward lon 90E, y toward lon 0."""
    colat = math.radians(90.0 + lat_deg)
    rho = 2.0 * R_M * math.tan(colat / 2.0)
    lon = math.radians(lon_deg)
    return rho * math.sin(lon), rho * math.cos(lon)


def ps_latlon(x: float, y: float) -> tuple[float, float]:
    rho = math.hypot(x, y)
    colat = 2.0 * math.atan(rho / (2.0 * R_M))
    return math.degrees(colat) - 90.0, math.degrees(math.atan2(x, y)) % 360.0


def query_box(cx: float, cy: float) -> dict:
    corners = [ps_latlon(cx + dx, cy + dy) for dx in (-HALF_M, 0, HALF_M) for dy in (-HALF_M, 0, HALF_M)]
    lats = [c[0] for c in corners]
    lons = sorted(c[1] for c in corners)
    # box does not contain the pole, so lon span is < 180; handle wrap across 0/360
    span = lons[-1] - lons[0]
    if span > 180:
        lons = sorted((l + 180) % 360 - 180 for l in lons)
    return {"minlat": min(lats) - 0.001, "maxlat": max(lats) + 0.001,
            "westernlon": lons[0] % 360 - 0.01, "easternlon": lons[-1] % 360 + 0.01}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "polaris-x-validation/0.1"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return r.read()


def nearest_dists(cells: list[tuple[float, float]], shots: list[tuple[float, float]]) -> list[float]:
    # bucket shots in 50 m bins; expand search ring until a hit is guaranteed
    B = 50.0
    grid: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for s in shots:
        grid.setdefault((int(s[0] // B), int(s[1] // B)), []).append(s)
    out = []
    for (x, y) in cells:
        bx, by = int(x // B), int(y // B)
        best = math.inf
        r = 0
        while True:
            for i in range(bx - r, bx + r + 1):
                for j in range(by - r, by + r + 1):
                    if max(abs(i - bx), abs(j - by)) != r:
                        continue
                    for s in grid.get((i, j), ()):
                        d = math.hypot(s[0] - x, s[1] - y)
                        if d < best:
                            best = d
            if best <= r * B or r > 60:
                break
            r += 1
        out.append(best)
    return out


def median(v: list[float]) -> float:
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def run_site(site: str, bundle_rel: str) -> None:
    b = json.loads((ROOT / bundle_rel).read_text())["site"]
    lat, lon = b["lat_deg"], b["lon_deg_east"] % 360.0
    cx, cy = ps_xy(lat, lon)
    box = query_box(cx, cy)
    params = {"query": "lolardr", "results": "u", "output": "JSON", **{k: f"{v:.6f}" for k, v in box.items()}}
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    cache = ROOT / "data/cache/lola_rdr" / site
    cache.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    meta = json.loads(fetch(url))["GDSResults"]
    files = meta.get("ResultFiles", {}).get("ResultFile", [])
    if isinstance(files, dict):
        files = [files]
    csv_urls = [f["URL"] for f in files if f.get("URL", "").lower().endswith(".csv")]
    shots = []
    for u in csv_urls:
        raw = fetch(u)
        (cache / Path(urllib.parse.urlparse(u).path).name).write_bytes(raw)
        rd = csv.reader(io.StringIO(raw.decode("utf-8", "replace")))
        next(rd, None)
        for row in rd:
            try:
                plon, plat = float(row[0]), float(row[1])
            except (ValueError, IndexError):
                continue
            x, y = ps_xy(plat, plon)
            if abs(x - cx) <= HALF_M and abs(y - cy) <= HALF_M:
                shots.append((x - cx, y - cy))
    (cache / "manifest.json").write_text(json.dumps({
        "site": site, "query_url": url, "csv_urls": csv_urls, "gds_status": meta.get("Status"),
        "gds_count_in_bbox": meta.get("Count"), "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_s": round(time.time() - t0, 1)}, indent=2))

    n = int(2 * HALF_M / CELL_M)
    counts = [[0] * n for _ in range(n)]
    for (x, y) in shots:
        i = min(n - 1, int((x + HALF_M) // CELL_M))
        j = min(n - 1, int((y + HALF_M) // CELL_M))
        counts[j][i] += 1
    flat = [c for r in counts for c in r]
    cells = [(-HALF_M + (i + 0.5) * CELL_M, -HALF_M + (j + 0.5) * CELL_M) for j in range(n) for i in range(n)]
    d = nearest_dists(cells, shots) if shots else []
    out = {
        "site": site,
        "status": "SOURCE-BASED UNVALIDATED: counts only, no conclusions",
        "centre": {"lat_deg": b["lat_deg"], "lon_deg_east": b["lon_deg_east"], "bundle": bundle_rel},
        "box": {"half_width_m": HALF_M, "projection": "south polar stereographic, sphere R=1737.4 km, frame of this script",
                "cell_m": CELL_M, "cells": n * n},
        "source": {"query_url": url, "product": "LOLA RDR via ODE GDS REST, results=u (valid shots, flag=0)"},
        "all_cells": {
            "shot_count": len(shots),
            "cells_with_ge1_shot": sum(1 for c in flat if c > 0),
            "max_shots_per_cell": max(flat) if flat else 0,
            "median_nearest_shot_m": round(median(d), 2) if d else None,
            "p90_nearest_shot_m": round(sorted(d)[int(0.9 * len(d))], 2) if d else None,
        },
        "top10_lit_crest_cells": {"computed": False,
                                  "reason": "needs per-5m-cell lit fraction from the solver; not wired tonight"},
    }
    dst = ROOT / "data/science_limits/lola_shots" / f"{site}.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, indent=2) + "\n")
    print(site, json.dumps(out["all_cells"]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", nargs="*", default=list(SITES))
    a = ap.parse_args()
    for s in a.sites:
        run_site(s, SITES[s])
    return 0


if __name__ == "__main__":
    sys.exit(main())
