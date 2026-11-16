"""Shared helpers for the batch runners: ROI selection, data preparation, per-process DEM cache."""
from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from . import core

PKG_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROIS = PKG_ROOT / "data" / "polaris_roi_sites.csv"


def select_rois(csv_path: Path, sites: str | None, rois: str | None) -> list[dict]:
    """sites='Site01,Site04'; rois='Site01:6,Site04:3' (overrides sites)."""
    allr = core.load_rois(csv_path)
    if rois:
        want = {(s, int(n)) for s, n in (x.split(":") for x in rois.split(","))}
        return [r for r in allr if (r["site"], r["roi"]) in want]
    if sites:
        want = set(sites.split(","))
        return [r for r in allr if r["site"] in want]
    return allr


def far_dem_path(data: Path) -> Path:
    return Path(data) / "pgda90" / "LDEM_80S_80MPP_ADJ.TIF"


def prepare_far(data: Path) -> Path:
    p = far_dem_path(data)
    print(f"[data] far-field LDEM 80 m -> {p}", flush=True)
    return core.download(core.PGDA90_80M, p)


def prepare_site(site: str, data: Path, clones: int = 0) -> dict:
    url, p = core.site_files(site, data)["surf"]
    print(f"[data] {site} nominal 5 m DEM", flush=True)
    core.download(url, p)
    out = {"nominal": p}
    for n in range(1, clones + 1):
        u, cp = core.clone_file(site, n, data)
        print(f"[data] {site} clone {n:04d}/{clones:04d}", flush=True)
        out[f"clone_{n:04d}"] = core.download(u, cp)
    return out


@lru_cache(maxsize=2)
def cached_dem(path: str) -> core.Dem:
    return core.Dem.open(Path(path))


def run_manifest(args, extra: dict | None = None) -> dict:
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "command": " ".join(sys.argv),
        "args": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
        "host": platform.node(), "python": sys.version.split()[0], "cpu_count": os.cpu_count(),
        "label": "SOURCE-BASED, UNVALIDATED unless the comparison below says otherwise",
        **(extra or {}),
    }


def write_json(path: Path, obj) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=1, default=float))
