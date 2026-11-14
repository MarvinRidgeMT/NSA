#!/usr/bin/env python3
"""Build a source-preserving NASA PGDA + JPL Horizons POLARIS X bundle.

The output is deliberately labelled SOURCE-BASED BUT UNVALIDATED until an
independent illumination comparison is recorded. It never substitutes a
synthetic DEM or approximate ephemeris when a source request fails.

Examples:
  .venv/bin/python app/scripts/prepare_science.py --sites connecting
  .venv/bin/python app/scripts/prepare_science.py --sites connecting \
    --local-dem-file app/data/source/pgda78/Site01/Site01_final_adj_5mpp_surf.tif \
    --error-file app/data/source/pgda78/Site01/Site01_final_adj_5mpp_toterr.tif \
    --clone-file 001=app/data/source/pgda78/Site01/Clones/Site01_final_adj_5mpp_0001_err.tif
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import re
import sys
from pathlib import Path


R = 1_737_400.0
BUNDLE_FORMAT = "POLARIS-X5D-v2"
BUNDLE_SCHEMA_VERSION = "2.0.0"
REGIONAL_DEM_URL = "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF"
PGDA_78_URL = "https://pgda.gsfc.nasa.gov/products/78"
PGDA_90_URL = "https://pgda.gsfc.nasa.gov/products/90"
HORIZONS_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
HORIZONS_MANUAL_URL = "https://ssd.jpl.nasa.gov/horizons/manual.html"

SITES = {
    "connecting": (-89.4632, -137.4900, "Connecting Ridge / Site01", "Site01"),
    "shackleton": (-89.7668, -171.8700, "Shackleton Rim / Site04", "Site04"),
    "peak": (-88.8110, 123.6901, "Peak Near Shackleton / Site07", "Site07"),
    "gerlache": (-88.6834, -67.9321, "de Gerlache Rim / Site11", "Site11"),
}

# Regression anchors for the prototype's documented PGDA reference points.
# They are not asserted touchdown coordinates.
EXPECTED_PROJECTED_M = {
    "connecting": (-11_000.0, -12_000.0),
    "shackleton": (-1_000.0, -7_000.0),
    "peak": (30_000.0, -20_000.0),
    "gerlache": (-37_000.0, 15_000.0),
}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def xy_from_latlon(lat: float, lon: float) -> tuple[float, float]:
    """Spherical south-polar stereographic, east-positive longitude."""
    rho = 2 * R * math.tan(math.pi / 4 + math.radians(lat) / 2)
    return rho * math.sin(math.radians(lon)), rho * math.cos(math.radians(lon))


def latlon_from_xy(x: float, y: float) -> tuple[float, float]:
    rho = math.hypot(x, y)
    lat = math.degrees(2 * math.atan2(rho, 2 * R) - math.pi / 2)
    lon = math.degrees(math.atan2(x, y))
    return lat, lon


def projection_validation(site_id: str) -> dict:
    lat, lon, _, _ = SITES[site_id]
    x, y = xy_from_latlon(lat, lon)
    expected_x, expected_y = EXPECTED_PROJECTED_M[site_id]
    round_lat, round_lon = latlon_from_xy(x, y)
    lon_error = ((round_lon - lon + 180) % 360) - 180
    projected_error = math.hypot(x - expected_x, y - expected_y)
    # Published coordinates are rounded to four decimals, so the independent
    # whole-kilometre projected anchors are checked to a two-metre tolerance.
    passed = projected_error < 2.0 and abs(round_lat - lat) < 1e-10 and abs(lon_error) < 1e-10
    return {
        "gate": "moon_projection_and_longitude",
        "status": "PASS" if passed else "FAIL",
        "siteId": site_id,
        "input": {"latitudePlanetocentricDeg": lat, "longitudeEastDeg": lon},
        "projectedMeters": {"x": x, "y": y},
        "expectedProjectedMeters": {"x": expected_x, "y": expected_y},
        "projectedErrorMeters": projected_error,
        "roundTripErrorDegrees": {"latitude": round_lat - lat, "longitude": lon_error},
        "basis": "IAU Moon sphere R=1737400 m; south polar stereographic; east-positive longitude",
    }


def _source_path(source: str | Path) -> str:
    source = str(source)
    return source if not source.startswith("http") else "/vsicurl/" + source


def read_raster_crop(source: str | Path, site_id: str, n: int, layer: str) -> dict:
    import numpy as np
    import rasterio
    from rasterio.windows import Window

    lat, lon, _, _ = SITES[site_id]
    observer_x, observer_y = xy_from_latlon(lat, lon)
    source_string = str(source)
    path = _source_path(source)
    if source_string.startswith("http"):
        print(f"Opening source raster with GDAL HTTP range requests: {source_string}", flush=True)
    env = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF",
        "GDAL_HTTP_MAX_RETRY": "3",
        "GDAL_HTTP_RETRY_DELAY": "1",
    }
    with rasterio.Env(**env):
        with rasterio.open(path) as dataset:
            transform = dataset.transform
            if not (
                transform.a > 0
                and transform.e < 0
                and abs(abs(transform.a) - abs(transform.e)) < 1e-6
                and abs(transform.b) < 1e-12
                and abs(transform.d) < 1e-12
            ):
                raise ValueError("Expected an unrotated, square-pixel north-up south-polar raster")
            row, column = dataset.index(observer_x, observer_y)
            half = n // 2
            start_row, start_column = row - half, column - half
            window = Window(start_column, start_row, n, n)
            if (
                start_column < 0
                or start_row < 0
                or start_column + n > dataset.width
                or start_row + n > dataset.height
            ):
                raise ValueError(f"{layer} crop does not fully cover {site_id}")
            raster = dataset.read(1, window=window, masked=True).astype("float64")
            mask = np.ma.getmaskarray(raster) | ~np.isfinite(np.asarray(raster))
            if np.any(mask):
                raise ValueError(f"{layer} crop has {int(np.count_nonzero(mask))} nodata pixels")

            # GeoTIFF rows increase southward. Flip to the canonical contract:
            # values[row*n+col], row 0 is south and +Y is north.
            values = np.flipud(np.asarray(raster)).copy()
            southwest_row = start_row + n - 1
            southwest_column = start_column
            southwest_x, southwest_y = rasterio.transform.xy(
                transform, southwest_row, southwest_column, offset="center"
            )
            center_source_x, center_source_y = rasterio.transform.xy(
                transform, row, column, offset="center"
            )
            spacing = float(abs(transform.a))
            local_origin_x = float(southwest_x - observer_x)
            local_origin_y = float(southwest_y - observer_y)
            coverage_radius = min(
                -local_origin_x,
                -local_origin_y,
                local_origin_x + (n - 1) * spacing,
                local_origin_y + (n - 1) * spacing,
            )
            local_path = Path(source_string).expanduser()
            checksum = sha256_file(local_path) if local_path.is_file() else None
            crop_checksum = hashlib.sha256(values.astype('<f8', copy=False).tobytes()).hexdigest()
            nodata = dataset.nodata
            return {
                "kind": "nasa",
                "layer": layer,
                "siteId": site_id,
                "latitudePlanetocentricDeg": lat,
                "longitudeEastDeg": lon,
                "n": n,
                "spacing": spacing,
                "originX": local_origin_x,
                "originY": local_origin_y,
                "values": values.flatten().round(4).tolist(),
                "source": source_string,
                "sourceSha256": checksum,
                "sourceChecksumStatus": "complete local file" if checksum else "remote COG not downloaded in full",
                "cropValuesSha256": crop_checksum,
                "verticalUnits": "meters",
                "frame": "MOON_ME / DE421",
                "crsConvention": "IAU Moon sphere R=1737400 m; ocentric south polar stereographic",
                "rowOrder": "south-to-north after explicit source flip",
                "validCoverageRadiusM": coverage_radius,
                "metadata": {
                    "width": dataset.width,
                    "height": dataset.height,
                    "dtype": dataset.dtypes[0],
                    "nodata": None if nodata is None or (isinstance(nodata, float) and math.isnan(nodata)) else nodata,
                    "crsWkt": str(dataset.crs),
                    "transform": [float(value) for value in list(transform)[:6]],
                    "sourceObserverPixel": {"row": int(row), "column": int(column)},
                    "sourceObserverPixelCenterMeters": {"x": center_source_x, "y": center_source_y},
                    "observerOffsetFromPixelCenterMeters": {
                        "east": observer_x - center_source_x,
                        "north": observer_y - center_source_y,
                    },
                    "cropSizePixels": n,
                    "pixelRegistration": "GeoTIFF pixel centers; PGDA 78 documents GMT pixel-registered convention",
                },
            }


def read_dem(dem_file: str | Path | None, site_id: str, n: int) -> dict:
    """Backward-compatible regional DEM entry point used by older callers."""
    return read_raster_crop(dem_file or REGIONAL_DEM_URL, site_id, n, "regional_horizon_dem")


def _header_before_soe(content: str) -> list[str]:
    before = content.split("$$SOE", 1)[0]
    candidates = [line for line in before.splitlines() if "Date__(" in line and "Azi_" in line and "Elev_" in line]
    if not candidates:
        raise ValueError("Horizons response does not declare Date/Azimuth/Elevation CSV columns")
    return next(csv.reader([candidates[-1]]))


def parse_csv_response(content: str) -> list[dict]:
    if "$$SOE" not in content or "$$EOE" not in content:
        raise ValueError("Horizons response lacks ephemeris markers. Response opening:\n" + content[:1000])
    headers = [value.strip() for value in _header_before_soe(content)]
    try:
        az_index = next(i for i, value in enumerate(headers) if value.startswith("Azi_"))
        el_index = next(i for i, value in enumerate(headers) if value.startswith("Elev_"))
    except StopIteration as exc:
        raise ValueError(f"Horizons CSV columns are not recognizable: {headers}") from exc
    if "(a-app)" not in headers[az_index] or "(a-app)" not in headers[el_index]:
        raise ValueError("Expected airless apparent azimuth/elevation columns")

    body = content.split("$$SOE", 1)[1].split("$$EOE", 1)[0]
    samples = []
    for row in csv.reader(body.splitlines()):
        if not row or not row[0].strip():
            continue
        if max(az_index, el_index) >= len(row):
            raise ValueError(f"Truncated Horizons CSV row: {row}")
        stamp = row[0].strip()
        parsed = None
        for pattern in ("%Y-%b-%d %H:%M:%S", "%Y-%b-%d %H:%M"):
            try:
                parsed = dt.datetime.strptime(stamp, pattern)
                break
            except ValueError:
                pass
        if parsed is None:
            raise ValueError(f"Unrecognized Horizons UTC timestamp: {stamp}")
        try:
            azimuth = float(row[az_index])
            elevation = float(row[el_index])
        except ValueError as exc:
            raise ValueError(f"Non-numeric Horizons azimuth/elevation row: {row}") from exc
        if not (0 <= azimuth <= 360 and -90 <= elevation <= 90):
            raise ValueError("Horizons azimuth/elevation is outside its physical domain")
        samples.append({
            "time": parsed.replace(tzinfo=dt.timezone.utc).isoformat().replace("+00:00", "Z"),
            "az": azimuth,
            "el": elevation,
        })
    if len(samples) < 2:
        raise ValueError("Not enough numeric JPL rows to interpolate")
    if any(samples[index]["time"] >= samples[index + 1]["time"] for index in range(len(samples) - 1)):
        raise ValueError("Horizons timestamps are not strictly increasing")
    return samples


def validate_horizons_response(content: str, site_id: str) -> dict:
    lat, lon, _, _ = SITES[site_id]
    required = [
        "Center pole/equ : MEAN_ME",
        "East-longitude positive",
        "Atmos refraction: NO (AIRLESS)",
        "Date__(UT)__",
        "Azi_(a-app)",
        "Elev_(a-app)",
    ]
    missing = [value for value in required if value not in content]
    center = re.search(r"Center geodetic\s*:\s*([-+0-9.]+),\s*([-+0-9.]+),", content)
    if not center:
        missing.append("Center geodetic metadata")
        center_lon = center_lat = math.nan
    else:
        center_lon, center_lat = map(float, center.groups())
    expected_lon = lon % 360
    coordinate_error = max(abs(center_lat - lat), abs(center_lon - expected_lon))
    passed = not missing and coordinate_error < 1e-6
    version = re.search(r"API VERSION:\s*([^\s]+)", content)
    return {
        "status": "PASS" if passed else "FAIL",
        "siteId": site_id,
        "apiVersion": version.group(1) if version else "not-declared",
        "missingDeclarations": missing,
        "reportedCenter": {"longitudeEastDeg": center_lon, "latitudeDeg": center_lat},
        "requestedCenter": {"longitudeEastDeg": expected_lon, "latitudeDeg": lat},
        "maximumCoordinateErrorDeg": coordinate_error,
        "azimuthConvention": "north=0 degrees, east=90 degrees; checked against JPL Horizons manual",
    }


def _query_params(command: str, site_id: str, start: dt.datetime, stop: dt.datetime, step_minutes: int) -> dict:
    lat, lon, _, _ = SITES[site_id]
    return {
        "format": "text",
        "COMMAND": f"'{command}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'coord@301'",
        "COORD_TYPE": "'GEODETIC'",
        "SITE_COORD": f"'{(lon % 360):.7f},{lat:.7f},0'",
        "START_TIME": f"'{start.strftime('%Y-%m-%d %H:%M:%S')}'",
        "STOP_TIME": f"'{stop.strftime('%Y-%m-%d %H:%M:%S')}'",
        "STEP_SIZE": f"'{step_minutes} min'",
        "QUANTITIES": "'4'",
        "CSV_FORMAT": "'YES'",
        "TIME_TYPE": "'UT'",
        "TIME_DIGITS": "'SECONDS'",
        "TIME_ZONE": "'+00:00'",
        "ANG_FORMAT": "'DEG'",
        "APPARENT": "'AIRLESS'",
    }


def get_ephemeris(
    site_id: str,
    start: str,
    days: float,
    step_h: float = 1,
    raw_dir: str | Path | None = None,
) -> dict:
    import requests

    start_time = dt.datetime.fromisoformat(start.replace("Z", "+00:00"))
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=dt.timezone.utc)
    start_time = start_time.astimezone(dt.timezone.utc)
    stop_time = start_time + dt.timedelta(days=days)
    step_minutes = int(round(step_h * 60))
    if step_minutes < 1:
        raise ValueError("Ephemeris step must be at least one minute")
    raw_path = Path(raw_dir) if raw_dir else None
    if raw_path:
        raw_path.mkdir(parents=True, exist_ok=True)

    result = {}
    records = []
    for name, command in (("sun", "10"), ("earth", "399")):
        params = _query_params(command, site_id, start_time, stop_time, step_minutes)
        print(f"Querying JPL Horizons {name} for {site_id}...", flush=True)
        response = requests.get(HORIZONS_URL, params=params, timeout=90)
        response.raise_for_status()
        validation = validate_horizons_response(response.text, site_id)
        if validation["status"] != "PASS":
            raise ValueError(f"Horizons metadata validation failed for {name}: {validation}")
        result[name] = parse_csv_response(response.text)
        filename = None
        if raw_path:
            filename = raw_path / f"{site_id}-{name}-{start_time.strftime('%Y%m%dT%H%M%SZ')}.txt"
            filename.write_text(response.text, encoding="utf-8")
        records.append({
            "target": name,
            "command": command,
            "queryUrl": response.url,
            "responseSha256": sha256_text(response.text),
            "rawResponsePath": str(filename) if filename else None,
            "validation": validation,
        })

    sun_by_time = {row["time"]: row for row in result["sun"]}
    earth_by_time = {row["time"]: row for row in result["earth"]}
    if sun_by_time.keys() != earth_by_time.keys():
        missing_sun = sorted(earth_by_time.keys() - sun_by_time.keys())
        missing_earth = sorted(sun_by_time.keys() - earth_by_time.keys())
        raise ValueError(f"Sun/Earth timestamp mismatch: missing sun={missing_sun}, missing earth={missing_earth}")
    rows = [{
        "time": timestamp,
        "sun": {"az": sun_by_time[timestamp]["az"], "el": sun_by_time[timestamp]["el"]},
        "earth": {"az": earth_by_time[timestamp]["az"], "el": earth_by_time[timestamp]["el"]},
    } for timestamp in sorted(sun_by_time)]
    return {
        "kind": "jpl-horizons-observer-ephemeris",
        "source": "NASA/JPL Horizons API",
        "sourceUrl": HORIZONS_URL,
        "manualUrl": HORIZONS_MANUAL_URL,
        "observerCenter": "coord@301 (Moon), geodetic/planetocentric on a spherical Moon",
        "frame": "MEAN_ME / DE421 as declared by Horizons output",
        "longitudeConvention": "east-positive",
        "azimuthConvention": "clockwise from north: N=0, E=90, S=180, W=270",
        "angleType": "airless apparent target-center azimuth/elevation",
        "timeScale": "UTC",
        "sampling": f"{step_minutes} min",
        "records": records,
        "samples": rows,
    }


def _parse_clone_argument(value: str) -> tuple[str, str]:
    if "=" in value:
        identifier, path = value.split("=", 1)
    else:
        path = value
        match = re.search(r"_(\d{4})_err", Path(path).name)
        identifier = match.group(1) if match else Path(path).stem
    return identifier, path


def _gate(name: str, status: str, evidence: str) -> dict:
    return {"gate": name, "status": status, "evidence": evidence}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sites", nargs="+", choices=list(SITES), default=["connecting"])
    parser.add_argument("--dem-file", help="Optional local PGDA product 90 regional DEM; defaults to official COG")
    parser.add_argument("--local-dem-file", help="Optional PGDA product 78 5 m site LDEM")
    parser.add_argument("--error-file", help="Optional PGDA product 78 total-Z RMS error raster")
    parser.add_argument("--clone-file", action="append", default=[], help="Optional ID=path PGDA clone; repeatable")
    parser.add_argument("--pixels", type=int, default=401, help="Odd regional crop dimension (default 401 ~=32 km)")
    parser.add_argument("--local-pixels", type=int, default=401, help="Odd local 5 m crop dimension (default 401 ~=2 km)")
    parser.add_argument("--start", default="2026-11-14T14:00:00Z")
    parser.add_argument("--days", type=float, default=14)
    parser.add_argument("--step-minutes", type=int, default=60)
    parser.add_argument("--output", default="app/data/nasa-jpl-science-bundle-v2.json")
    parser.add_argument("--raw-dir", help="Raw JPL response directory; defaults beside output")
    args = parser.parse_args()

    for label, value in (("--pixels", args.pixels), ("--local-pixels", args.local_pixels)):
        if value < 51 or value > 1201 or value % 2 != 1:
            parser.error(f"{label} must be odd between 51 and 1201")
    if not (0 < args.days <= 90):
        parser.error("--days must be greater than 0 and at most 90")
    if not (1 <= args.step_minutes <= 1440):
        parser.error("--step-minutes must be 1-1440")
    if (args.local_dem_file or args.error_file or args.clone_file) and len(args.sites) != 1:
        parser.error("Local 5 m/error/clone files currently require exactly one --sites value")

    output = Path(args.output)
    raw_dir = Path(args.raw_dir) if args.raw_dir else output.parent / "raw" / "jpl"
    datasets = []
    global_gates = [
        _gate("official_source_identifiers", "PASS", "PGDA products 78/90 and JPL Horizons URLs recorded"),
        _gate("independent_illumination_comparison", "NOT_RUN", "NASA SVS/reference observation comparison not yet executed"),
        _gate("flight_or_mission_certification", "NOT_APPLICABLE", "Research prototype only"),
    ]

    clone_specs = [_parse_clone_argument(value) for value in args.clone_file]
    for site_id in args.sites:
        projection = projection_validation(site_id)
        if projection["status"] != "PASS":
            raise ValueError(f"Projection regression failed: {projection}")
        regional = read_raster_crop(args.dem_file or REGIONAL_DEM_URL, site_id, args.pixels, "regional_horizon_dem")
        local = read_raster_crop(args.local_dem_file, site_id, args.local_pixels, "local_5m_dem") if args.local_dem_file else None
        error = read_raster_crop(args.error_file, site_id, args.local_pixels, "total_z_rms_error") if args.error_file else None
        clones = [{
            "id": identifier,
            "dem": read_raster_crop(path, site_id, args.local_pixels, f"pgda_clone_{identifier}"),
        } for identifier, path in clone_specs]
        ephemeris = get_ephemeris(site_id, args.start, args.days, args.step_minutes / 60, raw_dir)
        lat, lon, name, code = SITES[site_id]
        dataset_gates = [projection]
        dataset_gates.append(_gate(
            "regional_dem_orientation_and_nodata",
            "PASS",
            f"{regional['n']}x{regional['n']} crop; rows flipped to +Y north; no masked/nonfinite pixels",
        ))
        dataset_gates.append(_gate(
            "jpl_response_metadata_and_columns",
            "PASS",
            "MEAN_ME, east-positive longitude, UTC, AIRLESS and apparent AZ/EL columns verified in both raw responses",
        ))
        dataset_gates.append(_gate(
            "local_5m_uncertainty_inputs",
            "PASS" if local and error and clones else "NOT_RUN",
            f"local={bool(local)}, rms_error={bool(error)}, clone_ids={[item['id'] for item in clones]}",
        ))
        datasets.append({
            "siteId": site_id,
            "site": {
                "id": site_id,
                "name": name,
                "code": code,
                "latitudePlanetocentricDeg": lat,
                "longitudeEastDeg": lon,
                "projectedMeters": projection["projectedMeters"],
                "coordinateRole": "PGDA reference location used by this prototype; not asserted touchdown coordinates",
            },
            # Legacy field retained so the existing browser remains usable.
            "dem": regional,
            "localDem": local,
            "uncertainty": {
                "classification": "NASA published RMS layer and deterministic LDEM realizations; not probabilities",
                "totalZRms": error,
                "clones": clones,
            },
            "ephemeris": ephemeris,
            "validation": {"status": "SOURCE_BASED_UNVALIDATED", "gates": dataset_gates},
        })

    bundle = {
        "format": BUNDLE_FORMAT,
        "schemaVersion": BUNDLE_SCHEMA_VERSION,
        "generatedUTC": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "producer": {"name": "POLARIS X source pipeline", "version": "2.0.0"},
        "validation": {
            "status": "SOURCE_BASED_UNVALIDATED",
            "reason": "Official sources and coordinate/parser gates pass; no independent illumination result has been completed",
            "gates": global_gates,
        },
        "sources": {
            "NASA_PGDA_78": PGDA_78_URL,
            "NASA_PGDA_90": PGDA_90_URL,
            "regionalDem": args.dem_file or REGIONAL_DEM_URL,
            "JPL_Horizons": HORIZONS_URL,
        },
        "contract": {
            "localAxes": {"x": "east meters", "y": "north meters", "z": "elevation meters"},
            "time": "UTC ISO-8601",
            "scenarioAxis": "named deterministic uncertainty/assumption case; never a spatial dimension or probability",
            "visibility": "target center above finite-DEM terrain horizon; no DSN/power guarantee",
        },
        "datasets": datasets,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bundle, separators=(",", ":")), encoding="utf-8")
    report = output.with_suffix(".validation.json")
    report.write_text(json.dumps({
        "bundle": str(output),
        "bundleSha256": sha256_file(output),
        "validation": bundle["validation"],
        "datasets": [{"siteId": item["siteId"], "validation": item["validation"]} for item in datasets],
    }, indent=2), encoding="utf-8")
    print(f"Wrote {output} ({output.stat().st_size / 1048576:.1f} MiB)")
    print(f"Wrote {report}")
    print("STATUS: SOURCE-BASED BUT UNVALIDATED - independent illumination comparison remains NOT_RUN")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\nDATA PREPARATION FAILED:", str(exc), file=sys.stderr)
        print("No synthetic replacement was generated.", file=sys.stderr)
        sys.exit(1)
