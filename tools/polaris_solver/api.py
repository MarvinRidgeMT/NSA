from __future__ import annotations

import hashlib, json, math, os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import core

VERSION = "0.1.0"
DATA = Path(os.environ.get("POLARIS_DATA", "data/external"))
SITES = ("Site01", "Site04", "Site07", "Site11")
LABELS = ["SOURCE-BASED", "UNVALIDATED", "geometric visibility only"]

REQUEST_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["lat", "lon"],
    "properties": {
        "lat": {"type": "number", "minimum": -90, "maximum": -88.0, "description": "planetocentric latitude, deg"},
        "lon": {"type": "number", "minimum": -180, "maximum": 360, "description": "east longitude, deg"},
        "mast_m": {"type": "number", "minimum": 0.1, "maximum": 50, "default": 1.0},
        "start": {"type": "string", "default": "2026-11-14 00:00", "description": "UTC, 'YYYY-MM-DD HH:MM'"},
        "stop": {"type": "string", "default": "2026-11-28 00:00"},
        "step": {"type": "string", "enum": ["1h", "2h", "6h"], "default": "1h"},
        "clones": {"type": "integer", "minimum": 0, "maximum": 100, "default": 0},
        "thresholds": {"type": "object", "properties": {"sun_pct": {"type": "number", "default": 70},
                                                          "sun_earth_pct": {"type": "number", "default": 40},
                                                          "longest_dark_h": {"type": "number", "default": 120}}},
        "return_hourly": {"type": "boolean", "default": False},
    },
}

TOOL_SPEC = {
    "name": "polaris_solve",
    "description": ("Compute geometric Sun-centre and Earth-centre visibility for a point near the lunar south pole (88-90 S) on NASA "
                    "LOLA terrain, optionally across NASA's terrain clones. Returns percentages, the longest Sun-blocked stretch, "
                    "and 'pass on k of N terrain maps'. k of N is a count, not a probability. Not power or comms availability."),
    "input_schema": REQUEST_SCHEMA,
}


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


@lru_cache(8)
def _dem(path: str) -> core.Dem:
    return core.Dem.open(Path(path))


def _site_for(lat: float, lon: float) -> str:
    for s in SITES:
        _, p = core.site_files(s, DATA)["surf"]
        core.download(*core.site_files(s, DATA)["surf"])
        d = _dem(str(p))
        if np.isfinite(d.sample_lonlat(np.array([lon]), np.array([lat]))[0]):
            # require 500 m margin inside the tile so nearby terrain is on the 5 m map
            x, y = d.to_grid.transform(lon, lat)
            col, row = d.inv * (x, y)
            if 100 <= col <= d.z.shape[1] - 100 and 100 <= row <= d.z.shape[0] - 100:
                return s
    raise ValueError("point is not inside a PGDA 78 5 m tile (Sites 01, 04, 07, 11)")


def _interp(elev, az):
    n = len(elev); st = 360.0 / n
    a = np.mod(np.asarray(az) - st / 2, 360.0) / st
    i0 = np.floor(a).astype(int) % n; i1 = (i0 + 1) % n; f = a - np.floor(a)
    return elev[i0] * (1 - f) + elev[i1] * f


def _longest(b):
    best = run = 0
    for v in b:
        run = run + 1 if v else 0
        best = max(best, run)
    return int(best)


def solve(req: dict) -> dict:
    req = dict(req)
    for k, v in REQUEST_SCHEMA["properties"].items():
        if "default" in v:
            req.setdefault(k, v["default"])
    thr = {"sun_pct": 70.0, "sun_earth_pct": 40.0, "longest_dark_h": 120.0, **(req.get("thresholds") or {})}
    lat, lon, mast = float(req["lat"]), float(req["lon"]), float(req["mast_m"])
    if not (-90 <= lat <= -88):
        raise ValueError("lat must be between -90 and -88")
    site = _site_for(lat, lon)
    far_p = core.download(core.PGDA90_80M, DATA / "pgda90" / "LDEM_80S_80MPP_ADJ.TIF")
    nom_p = core.site_files(site, DATA)["surf"][1]
    near, far = _dem(str(nom_p)), _dem(str(far_p))
    z0 = float(near.sample_lonlat(np.array([lon]), np.array([lat]))[0])
    sun = core.horizons_observer("10", lon, lat, z0, req["start"], req["stop"], req["step"], DATA / "horizons_cache")
    earth = core.horizons_observer("399", lon, lat, z0, req["start"], req["stop"], req["step"], DATA / "horizons_cache")
    step_h = {"1h": 1, "2h": 2, "6h": 6}[req["step"]]

    def run(dem: core.Dem):
        hz = core.compute_horizon(lon, lat, dem, far, mast, near_step=1.0)
        hs = _interp(hz.elev, sun["az"]); he = _interp(hz.elev, earth["az"])
        s = sun["el"] > hs; e = earth["el"] > he
        return {"sun_pct": round(100 * float(s.mean()), 2), "sun_earth_pct": round(100 * float((s & e).mean()), 2),
                "earth_pct": round(100 * float(e.mean()), 2), "longest_dark_h": _longest(~s) * step_h,
                "max_horizon_deg": round(float(np.nanmax(hz.elev)), 3)}, (sun["el"] - hs)

    nominal, margin = run(near)
    passes = lambda r: (r["sun_pct"] >= thr["sun_pct"] and r["sun_earth_pct"] >= thr["sun_earth_pct"]
                        and r["longest_dark_h"] <= thr["longest_dark_h"])
    out = {"request": req, "site_tile": site, "ground_height_m": round(z0, 2), "observer_height_m": round(z0 + mast, 2),
           "n_samples": int(len(sun["el"])), "nominal": nominal, "nominal_passes": passes(nominal), "thresholds": thr}
    if req["clones"]:
        cl = []
        for n in range(1, int(req["clones"]) + 1):
            p = core.download(*core.clone_file(site, n, DATA))
            cl.append(run(_dem(str(p)))[0])
        k = sum(passes(r) for r in cl)
        out["clones"] = {"n": len(cl), **{m: [min(r[m] for r in cl), max(r[m] for r in cl)] for m in ("sun_pct", "sun_earth_pct", "longest_dark_h")},
                         "pass_k_of_n": f"{k}/{len(cl)}",
                         "verdict": "robust pass" if k == len(cl) else "robust fail" if k == 0 else "MARGINAL (terrain maps disagree)",
                         "note": "k/N counts NASA PGDA 78 terrain clones tested (5 m tile only); it is not a probability."}
    if req["return_hourly"]:
        out["hourly"] = {"time": sun["time"], "sun_margin_deg": np.round(margin, 4).tolist()}
    out["provenance"] = {"solver": f"polaris_solver {VERSION}", "dem": {"file": nom_p.name, "sha256": _sha(nom_p)},
                         "far_dem": {"file": far_p.name, "sha256": _sha(far_p)},
                         "horizons_raw": sun["raw"] + earth["raw"], "computed_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "method": "720 azimuth bins; 1 m ray step to 25 km, 80 m to 280 km; spherical Moon R=1737400 m; float64 heights"}
    out["labels"] = LABELS
    return out
