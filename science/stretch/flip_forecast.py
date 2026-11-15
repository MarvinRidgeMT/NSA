"""PILOT nominal-controller finite-difference flip forecast.

For each PGDA 78 clone, this module keeps the nominal skyline-controlling
sample fixed in every azimuth bin.  It samples the clone terrain at that same
location and at the observer, evaluates the finite difference in the exact
Moon-fixed elevation geometry, and applies that delta to the stored nominal
skyline.  It never searches for a new controller in the forecast.

The forecast is compared with full clone skylines from the existing solver.
Precision and recall are reported for hourly Sun, Earth, Sun+Earth visibility
flips and for the bundle-carried mission thresholds.  Null metrics remain null
when there are no predicted or actual positives; they are never replaced with
an invented perfect score.

Reproducible command (run from the repository root)::

    .venv/bin/python -m science.stretch.flip_forecast \
      data/bundles/site04_roi3_2026-11-14_14d_mast1m.json \
      data/bundles/site01_roi6_2026-11-14_14d_mast1m.json \
      --write
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Callable, Iterable

import numpy as np

from science import crossings, frames, sites
from science.margins import clone_margins

ROOT = Path(__file__).resolve().parents[2]
LABEL = "PILOT"
METHOD_ID = "nominal-controller-clone-secant-v1"
CLONE_IDS = tuple(range(1, 21))


def _bundle_hash_without_flip_forecast(bundle: dict) -> str:
    value = copy.deepcopy(bundle)
    value.get("derived", {}).pop("flip_forecast", None)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _pct(flags: Iterable[bool]) -> float:
    values = list(flags)
    if not values:
        raise ValueError("percentage needs at least one sample")
    return round(100.0 * sum(values) / len(values), 3)


def confusion(predicted: Iterable[bool], actual: Iterable[bool]) -> dict:
    predicted = list(predicted)
    actual = list(actual)
    if len(predicted) != len(actual) or not predicted:
        raise ValueError("predicted and actual labels must be non-empty and aligned")
    tp = sum(p and a for p, a in zip(predicted, actual))
    fp = sum(p and not a for p, a in zip(predicted, actual))
    fn = sum(not p and a for p, a in zip(predicted, actual))
    tn = len(predicted) - tp - fp - fn
    precision = None if tp + fp == 0 else round(tp / (tp + fp), 6)
    recall = None if tp + fn == 0 else round(tp / (tp + fn), 6)
    if precision is None and recall is None:
        note = "not evaluable: no predicted or actual flips"
    elif precision is None:
        note = "precision not evaluable: no predicted flips"
    elif recall is None:
        note = "recall not evaluable: no actual flips"
    else:
        note = "evaluable"
    return {
        "case_count": len(predicted),
        "predicted_flips": sum(predicted),
        "actual_flips": sum(actual),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "precision": precision,
        "recall": recall,
        "precision_display": "not evaluable" if precision is None else f"{100 * precision:.1f} %",
        "recall_display": "not evaluable" if recall is None else f"{100 * recall:.1f} %",
        "note": note,
    }


def comparison_row(*, site_id: str, row_id: str, label: str, predicted: Iterable[bool], actual: Iterable[bool]) -> dict:
    return {
        "result_id": f"flip-forecast-{site_id}-m1-{row_id}",
        "label": LABEL,
        "row_id": row_id,
        "scope": label,
        **confusion(predicted, actual),
    }


def _fixed_controller_skyline(bundle: dict, nominal, clone) -> tuple[dict, dict]:
    """Forecast one clone skyline without an argmax/controller search."""
    site = sites.SITES[bundle["site"]["id"]]
    observer_x, observer_y = frames.stereo_forward(site["lat"], site["lon"])
    nominal_ground = float(nominal.sample(observer_x, observer_y))
    clone_ground = float(clone.sample(observer_x, observer_y))
    if not np.isfinite(nominal_ground) or not np.isfinite(clone_ground):
        raise ValueError("observer ground is missing in nominal or clone DEM")
    mast_m = float(bundle["site"]["observer_mast_m"])
    observer_nominal = frames.moon_fixed(site["lat"], site["lon"], nominal_ground + mast_m)
    observer_clone = frames.moon_fixed(site["lat"], site["lon"], clone_ground + mast_m)
    up = frames.up_vector(site["lat"], site["lon"])
    sources = bundle["derived"]["attribution"]["per_bin"]["source"]
    critical = bundle["skyline"]["critical"]
    stored = bundle["skyline"]["elevation_deg"]
    if len(sources) != len(critical) or len(critical) != len(stored):
        raise ValueError("skyline attribution arrays are not aligned")

    predicted = []
    sensitivities = []
    near_bins = far_bins = 0
    for source, cell, stored_theta in zip(sources, critical, stored):
        if cell is None or stored_theta is None:
            predicted.append(None)
            continue
        lat = float(cell["lat_deg"])
        lon = float(cell["lon_deg"])
        if source == "near_5m":
            grid_x = float(cell["grid_x_m"])
            grid_y = float(cell["grid_y_m"])
            nominal_height = float(nominal.sample(grid_x, grid_y))
            clone_height = float(clone.sample(grid_x, grid_y))
            near_bins += 1
        else:
            nominal_height = clone_height = float(cell["height_m"])
            far_bins += 1
        if not np.isfinite(nominal_height) or not np.isfinite(clone_height):
            raise ValueError("nominal-controller height is missing")
        unit = frames.unit(lat, lon)
        point_nominal = (frames.R_MOON_M + nominal_height) * unit
        point_clone = (frames.R_MOON_M + clone_height) * unit
        theta_nominal_fixed = float(frames.elevation_angle_deg(observer_nominal, up, point_nominal))
        theta_clone_fixed = float(frames.elevation_angle_deg(observer_clone, up, point_clone))
        delta_theta = theta_clone_fixed - theta_nominal_fixed
        predicted.append(float(stored_theta) + delta_theta)
        delta_relief = (clone_height - clone_ground) - (nominal_height - nominal_ground)
        if abs(delta_relief) > 1e-12:
            sensitivities.append(delta_theta / delta_relief)

    return (
        {
            "bins": bundle["skyline"]["bins"],
            "elevation_deg": predicted,
            "status": bundle["skyline"]["status"],
        },
        {
            "nominal_ground_m": nominal_ground,
            "clone_ground_m": clone_ground,
            "near_controller_bins": near_bins,
            "far_controller_bins": far_bins,
            "finite_difference_pairs": len(sensitivities),
            "sensitivity_deg_per_m_min": None if not sensitivities else round(min(sensitivities), 12),
            "sensitivity_deg_per_m_max": None if not sensitivities else round(max(sensitivities), 12),
        },
    )


def _forecast_visibility(bundle: dict, skyline: dict) -> dict[str, list[bool]]:
    out = {"sun": [], "earth": []}
    for sample in bundle["samples"]:
        for body in ("sun", "earth"):
            margin = crossings.margins(sample[body], skyline)
            if margin is None:
                raise ValueError(f"forecast skyline is unknown at {sample['utc']} {body}")
            out[body].append(margin["margin_perp_deg"] > 0)
    out["both"] = [sun and earth for sun, earth in zip(out["sun"], out["earth"])]
    return out


def build_block(
    bundle_path: Path,
    *,
    clone_ids: Iterable[int] = CLONE_IDS,
    progress: Callable[[str], None] | None = None,
) -> dict:
    bundle_path = Path(bundle_path).resolve()
    bundle = json.loads(bundle_path.read_text())
    if bundle.get("schema") != "polaris-science-results-v1":
        raise ValueError(f"{bundle_path}: expected polaris-science-results-v1")
    site_id = bundle["site"]["id"]
    if site_id not in {"site04_roi3", "site01_roi6"}:
        raise ValueError(f"{bundle_path}: not a reference site")
    if bundle["site"]["observer_mast_m"] != 1:
        raise ValueError(f"{bundle_path}: flip forecast requires the 1 m bundle")
    clone_ids = tuple(clone_ids)
    if clone_ids != CLONE_IDS:
        raise ValueError("flip-forecast PILOT requires exactly PGDA 78 clones 1-20")
    for required in ("attribution", "margin_series", "arrival_slip"):
        if required not in bundle.get("derived", {}):
            raise ValueError(f"flip-forecast PILOT requires derived.{required}")

    thresholds = bundle["derived"]["arrival_slip"]["thresholds"]
    sun_threshold = float(thresholds["sun_center_visible_pct_min"])
    both_threshold = float(thresholds["sun_and_earth_center_visible_pct_min"])
    margin_series = bundle["derived"]["margin_series"]
    if margin_series["clone_ids"] != list(clone_ids):
        raise ValueError("margin_series clone IDs do not match clones 1-20")

    nominal = sites.near_dem(site_id)
    far = sites.far_dem(site_id)
    nominal_visible = {
        "sun": [bool(sample["sun"]["center_visible"]) for sample in bundle["samples"]],
        "earth": [bool(sample["earth"]["center_visible"]) for sample in bundle["samples"]],
    }
    nominal_visible["both"] = [
        sun and earth for sun, earth in zip(nominal_visible["sun"], nominal_visible["earth"])
    ]
    nominal_sun_pct = float(bundle["metrics"]["sun_center_visible_pct_hourly_samples"])
    nominal_both_pct = float(bundle["metrics"]["sun_and_earth_center_visible_pct_hourly_samples"])
    nominal_mission_pass = nominal_sun_pct >= sun_threshold and nominal_both_pct >= both_threshold

    forecast_flips = {"sun": [], "earth": [], "both": [], "mission": []}
    actual_flips = {"sun": [], "earth": [], "both": [], "mission": []}
    per_clone = []
    provenance_clones = []
    for position, clone_id in enumerate(clone_ids, 1):
        clone = sites.near_dem(site_id, clone=clone_id)
        forecast_skyline, diagnostics = _fixed_controller_skyline(bundle, nominal, clone)
        predicted = _forecast_visibility(bundle, forecast_skyline)
        actual_run = clone_margins(bundle, clone_id, far)
        actual = {
            "sun": [bool(value) for value in actual_run["sun"]["visible"]],
            "earth": [bool(value) for value in actual_run["earth"]["visible"]],
        }
        actual["both"] = [sun and earth for sun, earth in zip(actual["sun"], actual["earth"])]

        predicted_sun_pct = _pct(predicted["sun"])
        predicted_both_pct = _pct(predicted["both"])
        actual_sun_pct = _pct(actual["sun"])
        actual_both_pct = _pct(actual["both"])
        expected_sun_pct = margin_series["sun_center_visible_pct_hourly_by_clone"][clone_id - 1]
        expected_both_pct = margin_series["sun_and_earth_center_visible_pct_hourly_by_clone"][clone_id - 1]
        if actual_sun_pct != expected_sun_pct or actual_both_pct != expected_both_pct:
            raise ValueError(
                f"{site_id} clone {clone_id}: actual solver no longer reproduces margin_series "
                f"({actual_sun_pct}, {actual_both_pct}) != ({expected_sun_pct}, {expected_both_pct})"
            )
        predicted_mission_pass = predicted_sun_pct >= sun_threshold and predicted_both_pct >= both_threshold
        actual_mission_pass = actual_sun_pct >= sun_threshold and actual_both_pct >= both_threshold

        hourly_predicted = {}
        hourly_actual = {}
        for scope in ("sun", "earth", "both"):
            p = [value != nominal for value, nominal in zip(predicted[scope], nominal_visible[scope])]
            a = [value != nominal for value, nominal in zip(actual[scope], nominal_visible[scope])]
            forecast_flips[scope].extend(p)
            actual_flips[scope].extend(a)
            hourly_predicted[scope] = sum(p)
            hourly_actual[scope] = sum(a)
        predicted_mission_flip = predicted_mission_pass != nominal_mission_pass
        actual_mission_flip = actual_mission_pass != nominal_mission_pass
        forecast_flips["mission"].append(predicted_mission_flip)
        actual_flips["mission"].append(actual_mission_flip)

        per_clone.append(
            {
                "result_id": f"flip-forecast-{site_id}-m1-clone-{clone_id:02d}",
                "label": LABEL,
                "clone_id": clone_id,
                "predicted": {
                    "sun_center_visible_pct": predicted_sun_pct,
                    "sun_and_earth_center_visible_pct": predicted_both_pct,
                    "mission_pass": predicted_mission_pass,
                    "mission_flip": predicted_mission_flip,
                    "sun_hourly_flips": hourly_predicted["sun"],
                    "earth_hourly_flips": hourly_predicted["earth"],
                    "sun_and_earth_hourly_flips": hourly_predicted["both"],
                },
                "actual": {
                    "sun_center_visible_pct": actual_sun_pct,
                    "sun_and_earth_center_visible_pct": actual_both_pct,
                    "mission_pass": actual_mission_pass,
                    "mission_flip": actual_mission_flip,
                    "sun_hourly_flips": hourly_actual["sun"],
                    "earth_hourly_flips": hourly_actual["earth"],
                    "sun_and_earth_hourly_flips": hourly_actual["both"],
                },
                "finite_difference": diagnostics,
            }
        )
        provenance_clones.append(
            {
                "clone_id": clone_id,
                "file_sha256": clone.meta.get("file_sha256"),
                "array_sha256": clone.digest(),
            }
        )
        if progress:
            progress(f"{site_id}: clone {clone_id} forecast + actual complete ({position}/20)")

    rows = [
        comparison_row(
            site_id=site_id,
            row_id="sun-hourly",
            label="Hourly Sun-centre visibility",
            predicted=forecast_flips["sun"],
            actual=actual_flips["sun"],
        ),
        comparison_row(
            site_id=site_id,
            row_id="earth-hourly",
            label="Hourly Earth-centre visibility",
            predicted=forecast_flips["earth"],
            actual=actual_flips["earth"],
        ),
        comparison_row(
            site_id=site_id,
            row_id="both-hourly",
            label="Hourly Sun+Earth visibility",
            predicted=forecast_flips["both"],
            actual=actual_flips["both"],
        ),
        comparison_row(
            site_id=site_id,
            row_id="mission-thresholds",
            label="Mission threshold pass/fail by clone",
            predicted=forecast_flips["mission"],
            actual=actual_flips["mission"],
        ),
    ]
    ridge_ids = [ridge["id"] for ridge in bundle["derived"]["attribution"]["ridges"] if ridge["of_record"]]
    return {
        "result_id": f"flip-forecast-{site_id}-m1-20261114-pilot-v1",
        "label": LABEL,
        "validation_status": "SOURCE-BASED UNVALIDATED",
        "site_id": site_id,
        "input_bundle_id": bundle["bundle_id"],
        "observer_mast_m": bundle["site"]["observer_mast_m"],
        "clone_count": len(clone_ids),
        "sample_count": len(bundle["samples"]),
        "thresholds": {
            "sun_center_visible_pct_min": sun_threshold,
            "sun_and_earth_center_visible_pct_min": both_threshold,
            "source_result_id": bundle["derived"]["arrival_slip"]["result_id"],
        },
        "nominal": {
            "sun_center_visible_pct": nominal_sun_pct,
            "sun_and_earth_center_visible_pct": nominal_both_pct,
            "mission_pass": nominal_mission_pass,
        },
        "ridge_ids_considered": ridge_ids,
        "forecast_vs_actual": rows,
        "per_clone": per_clone,
        "method": {
            "id": METHOD_ID,
            "caption": "Nominal skyline controllers are held fixed; each clone's cell-minus-observer relief change gives a Moon-fixed finite-difference horizon shift, then full clone skylines provide actual flips.",
            "forecast": "no clone argmax search: stored nominal skyline plus the fixed-controller elevation delta at each azimuth bin",
            "actual": "existing science.margins.clone_margins solver: complete skyline recomputation for every clone",
            "hourly_flip": "predicted or actual target-centre visibility differs from the nominal bundle at the same UTC sample",
            "mission_flip": "predicted or actual clone pass/fail differs from nominal under the bundle-carried Sun and Sun+Earth percentage thresholds",
            "metrics": "precision = TP/(TP+FP), recall = TP/(TP+FN); null and displayed as not evaluable when the denominator is zero",
            "limitation": "fixed nominal controllers cannot model argmax switching; PGDA 78 clones vary only the near tile and are deterministic alternatives, not probabilities",
        },
        "provenance": {
            "input_bundle": {
                "path": bundle_path.relative_to(ROOT).as_posix(),
                "sha256_without_flip_forecast": _bundle_hash_without_flip_forecast(bundle),
            },
            "nominal_near_dem": {
                "file_sha256": nominal.meta.get("file_sha256"),
                "array_sha256": nominal.digest(),
            },
            "far_dem": {
                "file_sha256": far.meta.get("file_sha256"),
                "array_sha256": far.digest(),
            },
            "clones": provenance_clones,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PILOT nominal-controller clone flip forecast")
    parser.add_argument("bundles", nargs="+", type=Path)
    parser.add_argument("--write", action="store_true", help="write derived.flip_forecast into each input bundle")
    args = parser.parse_args(argv)
    for bundle_path in args.bundles:
        block = build_block(bundle_path, progress=lambda message: print(message, flush=True))
        sidecar = ROOT / "data" / "stretch" / "flip_forecast" / f"{block['site_id']}.json"
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(json.dumps(block, indent=1) + "\n")
        print(f"wrote {sidecar.relative_to(ROOT)}", flush=True)
        if args.write:
            bundle = json.loads(bundle_path.read_text())
            bundle.setdefault("derived", {})["flip_forecast"] = block
            bundle_path.write_text(json.dumps(bundle, indent=1) + "\n")
            print(f"extended {bundle_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
