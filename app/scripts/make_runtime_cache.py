#!/usr/bin/env python3
"""Build the self-contained two-site runtime bundle with Site01 local layers."""

from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site01",
        default="app/data/polaris-source-site01-2026-11-14-v2.json",
    )
    parser.add_argument(
        "--two-site",
        default="app/data/polaris-source-two-site-2026-11-14-v2.json",
    )
    parser.add_argument(
        "--output",
        default="app/data/polaris-runtime-source-case.json",
    )
    args = parser.parse_args()
    site01 = json.loads(Path(args.site01).read_text(encoding="utf-8"))
    comparison = json.loads(Path(args.two_site).read_text(encoding="utf-8"))
    if site01.get("format") != "POLARIS-X5D-v2" or comparison.get("format") != "POLARIS-X5D-v2":
        raise ValueError("Both inputs must be POLARIS-X5D-v2 bundles")
    connecting = next(item for item in site01["datasets"] if item["siteId"] == "connecting")
    shackleton = next(item for item in comparison["datasets"] if item["siteId"] == "shackleton")
    output_bundle = copy.deepcopy(site01)
    output_bundle["sources"].update(comparison.get("sources", {}))
    output_bundle["datasets"] = [connecting, shackleton]
    output_bundle["contract"]["terrainGridAxes"] = {
        "x": "south-polar grid east meters",
        "y": "south-polar grid north meters",
        "z": "elevation meters",
    }
    output_bundle["contract"]["frameTransform"] = (
        "local ENU directions and offsets are rotated into the terrain grid using the explicit DEM basis"
    )
    for dataset in output_bundle["datasets"]:
        longitude = math.radians(dataset["site"]["longitudeEastDeg"])
        north = [math.sin(longitude), math.cos(longitude)]
        east = [math.cos(longitude), -math.sin(longitude)]
        layers = [dataset.get("dem"), dataset.get("localDem"), dataset.get("uncertainty", {}).get("totalZRms")]
        layers.extend(item.get("dem") for item in dataset.get("uncertainty", {}).get("clones", []))
        for dem in filter(None, layers):
            dem["horizontalAxes"] = "south-polar stereographic grid: x=grid east, y=grid north"
            dem["localNorthInGrid"] = north
            dem["localEastInGrid"] = east
    output_bundle["cacheProfile"] = {
        "name": "source-backed-two-site-runtime-with-site01-local-layers",
        "includes": [
            "Site01 5 m nominal terrain",
            "Site01 total-Z RMS terrain error",
            "Site01 PGDA clones 001, 002, 050 and 100",
            "Site01 and Site04 80 m regional terrain",
            "Site01 and Site04 JPL Horizons Sun/Earth records",
        ],
        "scientificStatus": output_bundle["validation"]["status"],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(output_bundle, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {output} ({output.stat().st_size / 1048576:.1f} MiB)")


if __name__ == "__main__":
    main()
