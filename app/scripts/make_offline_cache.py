#!/usr/bin/env python3
"""Create a compact deterministic offline case from a full v2 source bundle."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("--output", default="app/data/polaris-offline-source-case.json")
    args = parser.parse_args()
    bundle = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if bundle.get("format") != "POLARIS-X5D-v2":
        raise ValueError("Expected a POLARIS-X5D-v2 source bundle")
    for dataset in bundle["datasets"]:
        dataset["localDem"] = None
        dataset["uncertainty"] = {
            "classification": "Optional PGDA 5 m layers omitted from compact offline cache",
            "totalZRms": None,
            "clones": [],
        }
    bundle["cacheProfile"] = {
        "name": "compact-offline-regional-source-case",
        "omits": ["5 m local DEM", "RMS error raster", "PGDA clones"],
        "scientificStatus": bundle["validation"]["status"],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bundle, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {output} ({output.stat().st_size / 1048576:.1f} MiB)")


if __name__ == "__main__":
    main()
