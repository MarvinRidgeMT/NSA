#!/usr/bin/env python3
"""Validate generated POLARIS X bundles and optional Blender artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas" / "science-bundle-v2.schema.json"
BUNDLES = (
    ROOT / "app" / "data" / "polaris-source-site01-2026-11-14-v2.json",
    ROOT / "app" / "data" / "polaris-source-two-site-2026-11-14-v2.json",
    ROOT / "app" / "data" / "polaris-offline-source-case.json",
    ROOT / "app" / "data" / "polaris-runtime-source-case.json",
)

NASA_MOON = ROOT / "app" / "assets" / "nasa" / "NASA_SVS_moon_small.glb"
NASA_MOON_SHA256 = "12d3b0bb7fe214903f51447d1bc61710f442e92a11c703fcaca6d4e7ff8e67d4"
NASA_MOON_TOPO = ROOT / "app" / "assets" / "nasa" / "NASA_SVS_Moon_NASA_LRO_8k_Topo_Small.glb"
NASA_MOON_TOPO_SHA256 = "c4b65fb4df622a37fd75366c2ed9bf9e163e41c0fde178b3b27e31b0173e6953"
PGDA69_DIR = ROOT / "web" / "public" / "layers" / "pgda69"
PGDA69_META = PGDA69_DIR / "pgda69.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_bundle(path: Path, validator: Draft202012Validator) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = sorted(validator.iter_errors(data), key=lambda error: list(error.path))
    if errors:
        joined = "\n".join(f"{list(error.path)}: {error.message}" for error in errors)
        raise ValueError(f"{path.name} failed schema validation:\n{joined}")
    if data["validation"]["status"] != "SOURCE_BASED_UNVALIDATED":
        raise ValueError(f"{path.name} must retain the explicit unvalidated status")
    if not data["datasets"]:
        raise ValueError(f"{path.name} has no datasets")
    for dataset in data["datasets"]:
        for record in dataset["ephemeris"]["records"]:
            raw = ROOT / record["rawResponsePath"]
            if raw.exists() and sha256(raw) != record["responseSha256"]:
                raise ValueError(f"Raw JPL hash mismatch: {raw}")
    return data


def validate_glb(path: Path) -> None:
    with path.open("rb") as handle:
        header = handle.read(12)
    if len(header) != 12:
        raise ValueError(f"Truncated GLB: {path}")
    magic, version, declared_length = struct.unpack("<4sII", header)
    if magic != b"glTF" or version != 2:
        raise ValueError(f"Invalid GLB v2 header: {path}")
    if declared_length != path.stat().st_size:
        raise ValueError(f"GLB declared length mismatch: {path}")


def validate_pgda69_layer() -> None:
    data = json.loads(PGDA69_META.read_text(encoding="utf-8"))
    if data.get("schema") != "POLARIS-X-layer-pgda69-v1":
        raise ValueError("Unexpected PGDA 69 layer schema")
    if data.get("kind") != "NASA_REFERENCE_PRODUCT" or not data.get("notAPolarisComputation"):
        raise ValueError("PGDA 69 layer must remain labelled as a displayed NASA reference product")
    if len(data.get("rois", [])) != 17:
        raise ValueError("PGDA 69 layer must contain the 17 declared PGDA 78 ROIs")
    raw_dir = ROOT / "data" / "raw" / "pgda69"
    for source in data.get("sources", []):
        path = raw_dir / source["file"]
        if path.exists() and sha256(path) != source["sha256"]:
            raise ValueError(f"PGDA 69 raw-source hash mismatch: {path}")
    images = [data["images"]["overview"]]
    images.extend(data["images"]["sites"].values())
    for image in images:
        for key in ("sun", "earth"):
            item = image[key]
            path = PGDA69_DIR / item["file"]
            if not path.is_file():
                raise ValueError(f"PGDA 69 generated-image mismatch: {path}")
            if item.get("bytes") is not None and path.stat().st_size != item["bytes"]:
                raise ValueError(f"PGDA 69 generated-image size mismatch: {path}")
            if path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
                raise ValueError(f"PGDA 69 generated image is not PNG: {path}")


def validate_blender_outputs() -> None:
    output = ROOT / "blender" / "output"
    for stem in ("POLARIS_X_connecting_DEMO", "POLARIS_X_connecting_science"):
        blend = output / f"{stem}.blend"
        glb = output / f"{stem}.glb"
        manifest_path = output / f"{stem}_scene_manifest.json"
        for path in (blend, glb, manifest_path):
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"Missing or empty Blender artifact: {path}")
        validate_glb(glb)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assets = manifest["assets"]
        if isinstance(assets, dict):
            indexed = {Path(item["path"]).name: item for item in assets.values()}
        else:
            indexed = {Path(item["path"]).name: item for item in assets}
        for path in (blend, glb):
            item = indexed.get(path.name)
            if item is None or item["sha256"] != sha256(path):
                raise ValueError(f"Manifest hash mismatch: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-blender", action="store_true")
    args = parser.parse_args()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    loaded = [validate_bundle(path, validator) for path in BUNDLES]
    site_counts = [len(bundle["datasets"]) for bundle in loaded]
    print(f"Validated {len(loaded)} v2 bundles; dataset counts: {site_counts}")
    validate_glb(NASA_MOON)
    if sha256(NASA_MOON) != NASA_MOON_SHA256:
        raise ValueError("NASA SVS global Moon asset hash mismatch")
    validate_glb(NASA_MOON_TOPO)
    if sha256(NASA_MOON_TOPO) != NASA_MOON_TOPO_SHA256:
        raise ValueError("NASA SVS topographic Moon asset hash mismatch")
    print("Validated NASA SVS compact and 8K topographic Moon GLB headers and SHA-256 values")
    validate_pgda69_layer()
    print("Validated NASA PGDA 69 reference layer, 17 ROIs, images and available raw hashes")
    if args.require_blender:
        validate_blender_outputs()
        print("Validated Blender/GLB files and manifest hashes")


if __name__ == "__main__":
    main()
