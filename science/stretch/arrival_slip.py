"""Arrival-slip sweep for the two 1 m reference-site science bundles.

This PILOT shifts the fixed 14-day mission window from -72 h to +72 h in 6 h
steps.  JPL Horizons is queried once for the extended hourly interval at each
site.  The established terrain solver then evaluates the nominal PGDA 78 map
and clones 1-20.  The browser only displays the resulting bundle block.

Reproducible command (run from the repository root)::

    .venv/bin/python -m science.stretch.arrival_slip \
      data/bundles/site04_roi3_2026-11-14_14d_mast1m.json \
      data/bundles/site01_roi6_2026-11-14_14d_mast1m.json \
      --write

Local geometric terrain visibility only.  It is not certified illumination,
power availability, or DSN telecommunications availability.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import time
from pathlib import Path
from typing import Callable, Iterable

from science import crossings
from science import frames
from science import horizons
from science import sites
from science.bundle import _radius_deg
from science.skyline import compute_skyline

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "stretch" / "arrival_slip" / "horizons"
LABEL = "PILOT"
SLIP_HOURS = tuple(range(-72, 73, 6))
SUN_THRESHOLD_PCT = 70.0
SUN_EARTH_THRESHOLD_PCT = 40.0
CLONE_IDS = tuple(range(1, 21))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bundle_hash_without_arrival_slip(bundle: dict) -> str:
    value = copy.deepcopy(bundle)
    derived = value.get("derived", {})
    derived.pop("arrival_slip", None)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _pct(flags: Iterable[bool]) -> float:
    values = list(flags)
    if not values:
        raise ValueError("visibility percentage needs at least one sample")
    if any(type(value) is not bool for value in values):
        raise ValueError("visibility flags must be booleans")
    return round(100.0 * sum(values) / len(values), 3)


def _exact_window_indices(times: list[float], start: float, stop: float, step_s: float) -> list[int]:
    by_time = {round(value, 3): index for index, value in enumerate(times)}
    count = int(round((stop - start) / step_s)) + 1
    expected = [round(start + index * step_s, 3) for index in range(count)]
    missing = [value for value in expected if value not in by_time]
    if missing:
        raise ValueError(f"extended ephemeris is missing {len(missing)} required sample(s), first={missing[0]}")
    return [by_time[value] for value in expected]


def evaluate_slips(
    *,
    site_id: str,
    bundle_id: str,
    times: list[float],
    nominal: dict[str, list[bool]],
    clones: dict[int, dict[str, list[bool]]],
    base_start: float,
    base_stop: float,
    step_h: float,
    slips_h: Iterable[int] = SLIP_HOURS,
    sun_threshold_pct: float = SUN_THRESHOLD_PCT,
    sun_earth_threshold_pct: float = SUN_EARTH_THRESHOLD_PCT,
) -> list[dict]:
    """Aggregate solver visibility flags into exact shifted-window results.

    ``nominal`` and every clone contain ``sun`` and ``both`` boolean arrays
    aligned with ``times``.  No interpolation or extrapolation is allowed.
    """
    if sorted(clones) != list(clones):
        clones = dict(sorted(clones.items()))
    lengths = {len(times), *(len(run[key]) for run in [nominal, *clones.values()] for key in ("sun", "both"))}
    if lengths != {len(times)}:
        raise ValueError(f"terrain runs are not aligned with ephemeris: lengths={sorted(lengths)}")
    step_s = step_h * 3600.0
    points = []
    for slip_h in slips_h:
        start = base_start + slip_h * 3600.0
        stop = base_stop + slip_h * 3600.0
        indices = _exact_window_indices(times, start, stop, step_s)

        def metrics(run: dict[str, list[bool]]) -> tuple[float, float]:
            return _pct(run["sun"][index] for index in indices), _pct(run["both"][index] for index in indices)

        nominal_sun, nominal_both = metrics(nominal)
        clone_metrics = {clone_id: metrics(run) for clone_id, run in clones.items()}
        clone_sun = [value[0] for value in clone_metrics.values()]
        clone_both = [value[1] for value in clone_metrics.values()]
        sun_pass_count = sum(value >= sun_threshold_pct for value in clone_sun)
        both_pass_count = sum(value >= sun_earth_threshold_pct for value in clone_both)
        joint_pass_count = sum(
            sun >= sun_threshold_pct and both >= sun_earth_threshold_pct for sun, both in clone_metrics.values()
        )
        sign = "p" if slip_h > 0 else "m"
        encoded = f"{sign}{abs(slip_h):03d}" if slip_h != 0 else "000"
        points.append(
            {
                "result_id": f"arrival-slip-{site_id}-m1-{encoded}h",
                "label": LABEL,
                "slip_h": slip_h,
                "window_start_utc": horizons.unix_to_iso(start),
                "window_stop_utc": horizons.unix_to_iso(stop),
                "sample_count": len(indices),
                "nominal": {
                    "sun_center_visible_pct": nominal_sun,
                    "sun_and_earth_center_visible_pct": nominal_both,
                    "sun_pass": nominal_sun >= sun_threshold_pct,
                    "sun_and_earth_pass": nominal_both >= sun_earth_threshold_pct,
                    "joint_pass": nominal_sun >= sun_threshold_pct and nominal_both >= sun_earth_threshold_pct,
                },
                "clones": {
                    "count": len(clone_metrics),
                    "sun_center_visible_pct_min": min(clone_sun),
                    "sun_center_visible_pct_max": max(clone_sun),
                    "sun_and_earth_center_visible_pct_min": min(clone_both),
                    "sun_and_earth_center_visible_pct_max": max(clone_both),
                    "sun_pass_count": sun_pass_count,
                    "sun_and_earth_pass_count": both_pass_count,
                    "joint_pass_count": joint_pass_count,
                    "pass_denominator": len(clone_metrics),
                    "joint_pass_pct": round(100.0 * joint_pass_count / len(clone_metrics), 3),
                    "pass_band": "all" if joint_pass_count == len(clone_metrics) else "dropped",
                },
            }
        )
    return points


def _load_or_fetch(target: str, bundle: dict, start: float, stop: float, raw_dir: Path) -> tuple[list[dict], dict]:
    site = bundle["site"]
    start_text = dt.datetime.fromtimestamp(start, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    stop_text = dt.datetime.fromtimestamp(stop, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    body = "sun" if target == "10" else "earth"
    start_tag = dt.datetime.fromtimestamp(start, dt.timezone.utc).strftime("%Y%m%d")
    stop_tag = dt.datetime.fromtimestamp(stop, dt.timezone.utc).strftime("%Y%m%d")
    tag = f'{site["id"]}_{body}_arrival_slip_{start_tag}_{stop_tag}_1h'
    params = horizons.build_params(
        target,
        site["lat_deg"],
        site["lon_deg_east"],
        site["height_m"],
        start=start_text,
        stop=stop_text,
        step="1 h",
    )
    path = raw_dir / f"{tag}.txt"
    if path.exists():
        text = path.read_text()
        sha = _sha256(path)
    else:
        text, sha, _ = horizons.fetch(params, tag, raw_dir=raw_dir)
    rows = horizons.parse_text(text)
    for row in rows:
        row["t"] = horizons.iso_to_unix(row["utc"])
        row["radius_deg"], row["radius_source"] = _radius_deg(row)
    expected_count = int(round((stop - start) / 3600.0)) + 1
    if len(rows) != expected_count:
        raise ValueError(f"{site['id']} {body}: Horizons returned {len(rows)} rows, expected {expected_count}")
    return rows, {"body": body, "path": path.relative_to(ROOT).as_posix(), "sha256": sha}


def _visibility(rows_sun: list[dict], rows_earth: list[dict], sky: dict) -> dict[str, list[bool]]:
    sun, earth = [], []
    for row_sun, row_earth in zip(rows_sun, rows_earth):
        if row_sun["t"] != row_earth["t"]:
            raise ValueError("Sun and Earth ephemeris rows are not aligned")
        ms = crossings.margins(row_sun, sky)
        me = crossings.margins(row_earth, sky)
        if ms is None or me is None:
            raise ValueError(f"unknown skyline margin at {row_sun['utc']}")
        sun.append(ms["margin_perp_deg"] > 0)
        earth.append(me["margin_perp_deg"] > 0)
    return {"sun": sun, "both": [a and b for a, b in zip(sun, earth)]}


def _terrain_run(bundle: dict, near, far, rows_sun: list[dict], rows_earth: list[dict]) -> tuple[dict, dict]:
    site_id = bundle["site"]["id"]
    site = sites.SITES[site_id]
    x, y = frames.stereo_forward(site["lat"], site["lon"])
    ground_m = float(near.sample(x, y))
    sky = compute_skyline(
        site["lat"],
        site["lon"],
        ground_m,
        bundle["site"]["observer_mast_m"],
        near=near,
        far=far,
        bins=bundle["skyline"]["bins"],
        max_range_m=bundle["skyline"]["max_range_m"],
        step_m=bundle["skyline"]["step_near_m"],
    )
    provenance = {
        "ground_m": round(ground_m, 3),
        "near_sha256": near.meta.get("file_sha256"),
        "near_array_sha256": near.digest(),
        "far_array_sha256": far.digest(),
        "n_truncated_bins": sky["n_truncated"],
    }
    return _visibility(rows_sun, rows_earth, sky), {"skyline": sky, **provenance}


def build_block(
    bundle_path: Path,
    *,
    clone_ids: Iterable[int] = CLONE_IDS,
    sun_threshold_pct: float = SUN_THRESHOLD_PCT,
    sun_earth_threshold_pct: float = SUN_EARTH_THRESHOLD_PCT,
    progress: Callable[[str], None] | None = None,
) -> dict:
    bundle_path = Path(bundle_path).resolve()
    bundle = json.loads(bundle_path.read_text())
    if bundle.get("schema") != "polaris-science-results-v1":
        raise ValueError(f"{bundle_path}: expected polaris-science-results-v1")
    if bundle["site"]["id"] not in {"site04_roi3", "site01_roi6"}:
        raise ValueError(f"{bundle_path}: not a reference site")
    if bundle["site"]["observer_mast_m"] != 1:
        raise ValueError(f"{bundle_path}: arrival-slip MVP requires the 1 m bundle")
    if bundle["time"]["step_h"] != 1:
        raise ValueError(f"{bundle_path}: arrival-slip MVP requires hourly source samples")

    clone_ids = tuple(clone_ids)
    if clone_ids != CLONE_IDS:
        raise ValueError("arrival-slip PILOT requires exactly PGDA 78 clones 1-20")
    base_start = horizons.iso_to_unix(bundle["time"]["start_utc"])
    base_stop = horizons.iso_to_unix(bundle["time"]["stop_utc"])
    ext_start = base_start + min(SLIP_HOURS) * 3600.0
    ext_stop = base_stop + max(SLIP_HOURS) * 3600.0
    rows_sun, src_sun = _load_or_fetch("10", bundle, ext_start, ext_stop, RAW_DIR)
    rows_earth, src_earth = _load_or_fetch("399", bundle, ext_start, ext_stop, RAW_DIR)
    times = [row["t"] for row in rows_sun]

    site_id = bundle["site"]["id"]
    far = sites.far_dem(site_id)
    started = time.monotonic()
    nominal, nominal_meta = _terrain_run(bundle, sites.near_dem(site_id), far, rows_sun, rows_earth)
    if nominal_meta["skyline"]["elevation_deg"] != bundle["skyline"]["elevation_deg"]:
        raise ValueError(f"{site_id}: recomputed nominal skyline does not reproduce the input bundle")
    if progress:
        progress(f"{site_id}: nominal terrain complete ({time.monotonic() - started:.1f} s)")

    clone_runs: dict[int, dict[str, list[bool]]] = {}
    clone_meta = []
    for position, clone_id in enumerate(clone_ids, 1):
        run, meta = _terrain_run(bundle, sites.near_dem(site_id, clone=clone_id), far, rows_sun, rows_earth)
        clone_runs[clone_id] = run
        clone_meta.append({"clone_id": clone_id, **{key: value for key, value in meta.items() if key != "skyline"}})
        if progress:
            progress(
                f"{site_id}: clone {clone_id} complete ({position}/{len(clone_ids)}, "
                f"{time.monotonic() - started:.1f} s elapsed)"
            )

    points = evaluate_slips(
        site_id=site_id,
        bundle_id=bundle["bundle_id"],
        times=times,
        nominal=nominal,
        clones=clone_runs,
        base_start=base_start,
        base_stop=base_stop,
        step_h=bundle["time"]["step_h"],
        sun_threshold_pct=sun_threshold_pct,
        sun_earth_threshold_pct=sun_earth_threshold_pct,
    )
    zero = next(point for point in points if point["slip_h"] == 0)
    expected = bundle["metrics"]["sun_center_visible_pct_hourly_samples"]
    if zero["nominal"]["sun_center_visible_pct"] != expected:
        raise ValueError(
            f"{site_id}: 0 h nominal Sun {zero['nominal']['sun_center_visible_pct']} != bundle {expected}"
        )
    if site_id == "site04_roi3" and expected != 94.362:
        raise ValueError(f"{site_id}: acceptance anchor changed: expected bundle value 94.362, got {expected}")

    return {
        "result_id": f"arrival-slip-{site_id}-m1-20261114-pilot-v1",
        "label": LABEL,
        "validation_status": "SOURCE-BASED UNVALIDATED",
        "site_id": site_id,
        "input_bundle_id": bundle["bundle_id"],
        "observer_mast_m": bundle["site"]["observer_mast_m"],
        "thresholds": {
            "sun_center_visible_pct_min": sun_threshold_pct,
            "sun_and_earth_center_visible_pct_min": sun_earth_threshold_pct,
            "joint_rule": "a clone passes only when both thresholds pass",
        },
        "slip_hours": list(SLIP_HOURS),
        "points": points,
        "method": {
            "mission_window": "fixed input-bundle duration shifted in 6 h increments; both endpoints included",
            "visibility_percentage": "share of hourly JPL Horizons samples with target centre above the terrain skyline",
            "terrain": "nominal PGDA 78 5 m tile and clones 1-20; same LDEM 80 m far field, 1 m near ray step, and 280 km reach as input bundle",
            "ephemeris": "one extended JPL Horizons hourly series per body and site; no interpolation or extrapolation",
            "uncertainty": "clone min-max and k/N are deterministic alternatives, not probabilities",
            "limitation": "local geometric visibility only; not certified illumination/power or DSN telecommunications availability",
        },
        "provenance": {
            "input_bundle": {
                "path": bundle_path.relative_to(ROOT).as_posix(),
                "sha256_without_arrival_slip": _bundle_hash_without_arrival_slip(bundle),
            },
            "horizons_raw": [src_sun, src_earth],
            "nominal_terrain": {key: value for key, value in nominal_meta.items() if key != "skyline"},
            "clones": clone_meta,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PILOT arrival-slip sweep (-72 h..+72 h, 6 h step)")
    parser.add_argument("bundles", nargs="+", type=Path)
    parser.add_argument("--sun-threshold", type=float, default=SUN_THRESHOLD_PCT)
    parser.add_argument("--sun-earth-threshold", type=float, default=SUN_EARTH_THRESHOLD_PCT)
    parser.add_argument("--write", action="store_true", help="write derived.arrival_slip into each input bundle")
    args = parser.parse_args(argv)
    for bundle_path in args.bundles:
        block = build_block(
            bundle_path,
            clone_ids=CLONE_IDS,
            sun_threshold_pct=args.sun_threshold,
            sun_earth_threshold_pct=args.sun_earth_threshold,
            progress=lambda message: print(message, flush=True),
        )
        sidecar = ROOT / "data" / "stretch" / "arrival_slip" / f"{block['site_id']}.json"
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(json.dumps(block, indent=1) + "\n")
        print(f"wrote {sidecar.relative_to(ROOT)}", flush=True)
        if args.write:
            bundle = json.loads(bundle_path.read_text())
            bundle.setdefault("derived", {})["arrival_slip"] = block
            bundle_path.write_text(json.dumps(bundle, indent=1) + "\n")
            print(f"extended {bundle_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
