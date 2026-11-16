"""PILOT information-hotspot ranking for the two 1 m reference bundles.

The implementation is deliberately deterministic and non-probabilistic.  It
uses the existing nominal skyline attribution to identify near-field
controlling ray samples.  At each sample location it measures height spread
relative to the observer ground across PGDA 78 clones 1-20, maps that spread
through the local skyline Jacobian, and sums the resulting horizon-angle variance over source-bundle
Sun/Earth samples inside the bundle's critical-margin band.

The score is a sensitivity ranking in deg^2 h, not a probability, formal value
of information, or calibrated risk estimate.  Far-field cells are outside the
clone ensemble and are not scored.  Any candidate beyond the finite horizon
distance is retained with score zero.

Reproducible command (run from the repository root)::

    .venv/bin/python -m science.stretch.hotspots \
      data/bundles/site04_roi3_2026-11-14_14d_mast1m.json \
      data/bundles/site01_roi6_2026-11-14_14d_mast1m.json \
      --write
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np

from science import frames, sites

ROOT = Path(__file__).resolve().parents[2]
LABEL = "PILOT"
METHOD_ID = "clone-jacobian-critical-margin-v1"
CLONE_IDS = tuple(range(1, 21))
TOP_K = 10


def _bundle_hash_without_hotspots(bundle: dict) -> str:
    value = copy.deepcopy(bundle)
    value.get("derived", {}).pop("hotspots", None)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _bin_of(azimuth_deg: float, bins: int) -> int:
    return int(round((azimuth_deg % 360.0) / (360.0 / bins))) % bins


def _tile_at(dem, grid_x_m: float, grid_y_m: float) -> tuple[int, int, float, float]:
    """Return containing pixel row/column and its centre in the DEM grid."""
    height, width = dem.Z.shape
    col = int(math.floor((grid_x_m - dem.x_left) / dem.step))
    row = int(math.floor((dem.y_top - grid_y_m) / dem.step))
    if not (0 <= row < height and 0 <= col < width):
        raise ValueError(f"controlling sample ({grid_x_m}, {grid_y_m}) is outside the near DEM")
    centre_x = dem.x_left + (col + 0.5) * dem.step
    centre_y = dem.y_top - (row + 0.5) * dem.step
    return row, col, centre_x, centre_y


def aggregate_scores(
    *,
    site_id: str,
    candidates_by_bin: list[dict | None],
    samples: list[dict],
    max_range_m: float,
    critical_margin_deg: float,
    step_h: float,
) -> list[dict]:
    """Aggregate precomputed per-bin horizon variances into ranked tiles.

    A target-hour contributes only when its nominal margin is inside the
    source-bundle critical band.  Candidates beyond ``max_range_m`` always
    remain at zero, even when a supplied sample would otherwise contribute.
    """
    bins = len(candidates_by_bin)
    tiles: dict[str, dict] = {}
    for candidate in candidates_by_bin:
        if candidate is None:
            continue
        tile_id = candidate["tile_id"]
        tile = tiles.setdefault(
            tile_id,
            {
                "tile_id": tile_id,
                "lat_deg": candidate["lat_deg"],
                "lon_deg_east": candidate["lon_deg_east"],
                "grid_x_m": candidate["grid_x_m"],
                "grid_y_m": candidate["grid_y_m"],
                "distance_m_min": candidate["distance_m"],
                "distance_m_max": candidate["distance_m"],
                "controlled_bins": set(),
                "clone_height_variance_m2_max": candidate["clone_height_variance_m2"],
                "clone_relative_height_variance_m2_max": candidate["clone_relative_height_variance_m2"],
                "horizon_variance_deg2_max": candidate["horizon_variance_deg2"],
                "sun_score": 0.0,
                "earth_score": 0.0,
                "sun_critical_h": 0.0,
                "earth_critical_h": 0.0,
            },
        )
        tile["distance_m_min"] = min(tile["distance_m_min"], candidate["distance_m"])
        tile["distance_m_max"] = max(tile["distance_m_max"], candidate["distance_m"])
        tile["controlled_bins"].add(candidate["bin"])
        tile["clone_height_variance_m2_max"] = max(
            tile["clone_height_variance_m2_max"], candidate["clone_height_variance_m2"]
        )
        tile["clone_relative_height_variance_m2_max"] = max(
            tile["clone_relative_height_variance_m2_max"], candidate["clone_relative_height_variance_m2"]
        )
        tile["horizon_variance_deg2_max"] = max(
            tile["horizon_variance_deg2_max"], candidate["horizon_variance_deg2"]
        )

    for sample in samples:
        for body in ("sun", "earth"):
            target = sample[body]
            if target.get("horizon_flag") == "unknown" or abs(target["margin_deg"]) >= critical_margin_deg:
                continue
            candidate = candidates_by_bin[_bin_of(target["az_deg"], bins)]
            if candidate is None:
                continue
            tile = tiles[candidate["tile_id"]]
            if candidate["distance_m"] > max_range_m:
                continue
            tile[f"{body}_score"] += candidate["horizon_variance_deg2"] * step_h
            tile[f"{body}_critical_h"] += step_h

    out = []
    for tile in tiles.values():
        sun_score = tile["sun_score"]
        earth_score = tile["earth_score"]
        score = sun_score + earth_score
        controlled_bins = sorted(tile["controlled_bins"])
        tile["controlled_bins"] = len(controlled_bins)
        tile["controlled_bin_indices"] = controlled_bins
        tile["score"] = round(score, 12)
        tile["sun_score"] = round(sun_score, 12)
        tile["earth_score"] = round(earth_score, 12)
        tile["display_band"] = "positive" if score > 0 else "zero"
        for key in (
            "lat_deg",
            "lon_deg_east",
            "grid_x_m",
            "grid_y_m",
            "distance_m_min",
            "distance_m_max",
            "clone_height_variance_m2_max",
            "clone_relative_height_variance_m2_max",
            "horizon_variance_deg2_max",
            "sun_critical_h",
            "earth_critical_h",
        ):
            tile[key] = round(float(tile[key]), 12)
        tile["method"] = METHOD_ID
        out.append(tile)
    out.sort(key=lambda tile: (-tile["score"], tile["tile_id"]))
    for rank, tile in enumerate(out, 1):
        tile["rank"] = rank
        tile["result_id"] = f"hotspot-{site_id}-m1-{tile['tile_id']}"
        tile["label"] = LABEL
    return out


def _candidate_bins(bundle: dict, nominal, clones: list) -> list[dict | None]:
    skyline = bundle["skyline"]
    attribution = bundle["derived"]["attribution"]
    sources = attribution["per_bin"]["source"]
    bins = skyline["bins"]
    if len(sources) != bins or len(skyline["critical"]) != bins:
        raise ValueError("attribution and skyline bins are not aligned")
    site = sites.SITES[bundle["site"]["id"]]
    observer_x, observer_y = frames.stereo_forward(site["lat"], site["lon"])
    observer_heights = np.asarray([float(clone.sample(observer_x, observer_y)) for clone in clones])
    if observer_heights.size != len(CLONE_IDS) or not np.isfinite(observer_heights).all():
        raise ValueError("clone observer heights are incomplete")
    candidates: list[dict | None] = [None] * bins
    for index, (source, critical, theta_deg) in enumerate(
        zip(sources, skyline["critical"], skyline["elevation_deg"])
    ):
        if source != "near_5m" or critical is None or theta_deg is None:
            continue
        distance_m = float(critical["distance_m"])
        if distance_m <= 0:
            continue
        grid_x_m = float(critical["grid_x_m"])
        grid_y_m = float(critical["grid_y_m"])
        row, col, centre_x, centre_y = _tile_at(nominal, grid_x_m, grid_y_m)
        heights = np.asarray([float(clone.sample(grid_x_m, grid_y_m)) for clone in clones])
        if heights.size != len(CLONE_IDS) or not np.isfinite(heights).all():
            continue
        height_variance_m2 = float(np.var(heights, ddof=0))
        relative_height_variance_m2 = float(np.var(heights - observer_heights, ddof=0))
        jacobian_deg_per_m = math.degrees(math.cos(math.radians(theta_deg)) ** 2 / distance_m)
        horizon_variance_deg2 = jacobian_deg_per_m**2 * relative_height_variance_m2
        lat_deg, lon_deg = frames.stereo_inverse(centre_x, centre_y)
        candidates[index] = {
            "bin": index,
            "tile_id": f"p78-r{row:04d}-c{col:04d}",
            "lat_deg": float(lat_deg),
            "lon_deg_east": float(lon_deg % 360.0),
            "grid_x_m": centre_x,
            "grid_y_m": centre_y,
            "distance_m": distance_m,
            "clone_height_variance_m2": height_variance_m2,
            "clone_relative_height_variance_m2": relative_height_variance_m2,
            "horizon_variance_deg2": horizon_variance_deg2,
        }
    return candidates


def build_block(bundle_path: Path, *, clone_ids: Iterable[int] = CLONE_IDS, top_k: int = TOP_K) -> dict:
    bundle_path = Path(bundle_path).resolve()
    bundle = json.loads(bundle_path.read_text())
    if bundle.get("schema") != "polaris-science-results-v1":
        raise ValueError(f"{bundle_path}: expected polaris-science-results-v1")
    site_id = bundle["site"]["id"]
    if site_id not in {"site04_roi3", "site01_roi6"}:
        raise ValueError(f"{bundle_path}: not a reference site")
    if bundle["site"]["observer_mast_m"] != 1:
        raise ValueError(f"{bundle_path}: hotspots PILOT requires the 1 m bundle")
    clone_ids = tuple(clone_ids)
    if clone_ids != CLONE_IDS:
        raise ValueError("hotspots PILOT requires exactly PGDA 78 clones 1-20")
    if top_k != TOP_K:
        raise ValueError(f"hotspots PILOT requires top_k={TOP_K}")
    if "attribution" not in bundle.get("derived", {}):
        raise ValueError("hotspots PILOT requires derived.attribution")
    coverage = bundle["derived"].get("coverage")
    if not coverage:
        raise ValueError("hotspots PILOT requires derived.coverage")
    critical_margin_deg = float(coverage["critical_threshold_deg"])
    if float(coverage["earth"]["critical_threshold_deg"]) != critical_margin_deg:
        raise ValueError("Sun and Earth critical-margin thresholds differ")

    nominal = sites.near_dem(site_id)
    clones = [sites.near_dem(site_id, clone=clone_id) for clone_id in clone_ids]
    shape = nominal.Z.shape
    for clone_id, clone in zip(clone_ids, clones):
        if clone.Z.shape != shape or clone.step != nominal.step or clone.bounds != nominal.bounds:
            raise ValueError(f"clone {clone_id} grid is not aligned with nominal")
    candidates = _candidate_bins(bundle, nominal, clones)
    tiles = aggregate_scores(
        site_id=site_id,
        candidates_by_bin=candidates,
        samples=bundle["samples"],
        max_range_m=float(bundle["skyline"]["max_range_m"]),
        critical_margin_deg=critical_margin_deg,
        step_h=float(bundle["time"]["step_h"]),
    )
    top_tiles = tiles[:top_k]
    if len(top_tiles) != top_k:
        raise ValueError(f"{site_id}: only {len(top_tiles)} scored tiles, expected at least {top_k}")

    tiles_positive = sum(tile["display_band"] == "positive" for tile in tiles)
    return {
        "result_id": f"hotspots-{site_id}-m1-20261114-pilot-v1",
        "label": LABEL,
        "validation_status": "SOURCE-BASED UNVALIDATED",
        "site_id": site_id,
        "input_bundle_id": bundle["bundle_id"],
        "observer_mast_m": bundle["site"]["observer_mast_m"],
        "clone_count": len(clones),
        "tile_step_m": nominal.step,
        "horizon_distance_m": float(bundle["skyline"]["max_range_m"]),
        "critical_margin_deg": critical_margin_deg,
        "score_unit": "deg^2 h",
        "tiles_evaluated": len(tiles),
        "tiles_positive": tiles_positive,
        "zero_state_caption": (
            "No clone-covered critical tile has a positive score in this bundle."
            if tiles_positive == 0
            else None
        ),
        "top_k": top_k,
        "top_tiles": top_tiles,
        "tiles": tiles,
        "method": {
            "id": METHOD_ID,
            "caption": "20-clone pixel-minus-observer relief variance mapped through the nominal skyline Jacobian and summed over bundle-defined near-horizon Sun/Earth target-hours.",
            "candidate": "nominal near-field 5 m skyline-controlling ray samples, grouped by containing PGDA 78 pixel",
            "dispersion": "population variance of paired controlling-pixel minus observer-ground relief across deterministic PGDA 78 clones 1-20; absolute pixel variance is retained as a diagnostic",
            "jacobian": "horizon variance = clone relative-height variance * (degrees(cos(theta)^2 / distance))^2",
            "score": "sum of horizon variance times sample step over Sun and Earth samples with |nominal margin| below derived.coverage.critical_threshold_deg",
            "coverage": "far-field controllers have no PGDA 78 clone support and are excluded; any candidate beyond skyline.max_range_m scores exactly zero",
            "limitation": "piecewise nominal-controller sensitivity only; controller switching and decision-flip precision/recall are deferred to the flip-forecast PILOT",
        },
        "provenance": {
            "input_bundle": {
                "path": bundle_path.relative_to(ROOT).as_posix(),
                "sha256_without_hotspots": _bundle_hash_without_hotspots(bundle),
            },
            "nominal_near_dem": {
                "file_sha256": nominal.meta.get("file_sha256"),
                "array_sha256": nominal.digest(),
            },
            "clones": [
                {
                    "clone_id": clone_id,
                    "file_sha256": clone.meta.get("file_sha256"),
                    "array_sha256": clone.digest(),
                }
                for clone_id, clone in zip(clone_ids, clones)
            ],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PILOT information-hotspot ranking")
    parser.add_argument("bundles", nargs="+", type=Path)
    parser.add_argument("--write", action="store_true", help="write derived.hotspots into each input bundle")
    args = parser.parse_args(argv)
    for bundle_path in args.bundles:
        block = build_block(bundle_path)
        sidecar = ROOT / "data" / "stretch" / "hotspots" / f"{block['site_id']}.json"
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(json.dumps(block, indent=1) + "\n")
        print(
            f"{block['site_id']}: {block['tiles_evaluated']} tiles, "
            f"{block['tiles_positive']} positive; top={block['top_tiles'][0]['tile_id']} "
            f"score={block['top_tiles'][0]['score']} {block['score_unit']}",
            flush=True,
        )
        print(f"wrote {sidecar.relative_to(ROOT)}", flush=True)
        if args.write:
            bundle = json.loads(bundle_path.read_text())
            bundle.setdefault("derived", {})["hotspots"] = block
            bundle_path.write_text(json.dumps(bundle, indent=1) + "\n")
            print(f"extended {bundle_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
