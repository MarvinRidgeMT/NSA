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
)


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
    if args.require_blender:
        validate_blender_outputs()
        print("Validated Blender/GLB files and manifest hashes")


if __name__ == "__main__":
    main()
