"""Build deterministic, print-ready decision cards from science result bundles.

Every numeric value in the output is either wrapped with its exact bundle JSON
path or, for a signed margin, carries the two source paths in its arithmetic
formula. Optional evidence is omitted when the bundle does not carry it.

Run from the repository root::

    .venv/bin/python -m science.decision_card \
      data/bundles/site04_roi3_2026-11-14_14d_mast1m.json \
      data/bundles/site01_roi6_2026-11-14_14d_mast1m.json \
      --out-dir data/cards
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
from pathlib import Path
from typing import Any


SCHEMA = "polaris-decision-card-v1"


def _sourced(value: int | float | None, source_path: str) -> dict[str, Any]:
    return {"value": value, "source_path": source_path}


def _team_requirement(value: int | float, cli_flag: str) -> dict[str, Any]:
    return {
        "value": value,
        "source_type": "team requirement",
        "source": f"CLI {cli_flag}",
        "classification": "SCENARIO",
    }


def _margin(value: float, threshold: float, value_path: str, threshold_path: str) -> dict[str, Any]:
    return {
        "value": round(float(value) - float(threshold), 12),
        "formula": "nominal - threshold",
        "source_paths": {"nominal": value_path, "threshold": threshold_path},
    }


def _maximum_margin(value: float, threshold: float, value_path: str, threshold_flag: str) -> dict[str, Any]:
    return {
        "value": round(float(threshold) - float(value), 12),
        "formula": "threshold - nominal",
        "source_paths": {"nominal": value_path},
        "threshold_source": f"CLI {threshold_flag}",
    }


def _zero_slip(bundle: dict) -> tuple[dict, int]:
    points = bundle["derived"]["arrival_slip"]["points"]
    for index, point in enumerate(points):
        if point["slip_h"] == 0:
            return point, index
    raise ValueError("derived.arrival_slip has no 0 h point")


def _certainty_height(bundle: dict) -> dict[str, Any] | None:
    derived = bundle.get("derived", {})
    if isinstance(derived.get("certainty_height_m"), (int, float)):
        return _sourced(derived["certainty_height_m"], "derived.certainty_height_m")
    value = derived.get("certainty_height")
    if isinstance(value, dict):
        for key in ("value_m", "mast_m", "height_m"):
            if isinstance(value.get(key), (int, float)):
                return _sourced(value[key], f"derived.certainty_height.{key}")
    return None


def _coverage(bundle: dict, *, include_earth: bool) -> dict[str, Any] | None:
    block = bundle.get("derived", {}).get("coverage")
    if not isinstance(block, dict):
        return None
    result = {
        "sun_critical_covered_fraction": _sourced(
            block.get("covered_frac"), "derived.coverage.covered_frac"
        ),
        "sun_critical_hours": _sourced(block.get("n_critical_h"), "derived.coverage.n_critical_h"),
    }
    if include_earth and isinstance(block.get("earth"), dict):
        result.update(
            {
                "earth_critical_covered_fraction": _sourced(
                    block["earth"].get("covered_frac"), "derived.coverage.earth.covered_frac"
                ),
                "earth_critical_hours": _sourced(
                    block["earth"].get("n_critical_h"), "derived.coverage.earth.n_critical_h"
                ),
            }
        )
    return result


def build_card(
    bundle: dict,
    *,
    bundle_path: str,
    bundle_sha256: str,
    max_dark_h: int | float = 120,
) -> dict:
    if bundle.get("schema") != "polaris-science-results-v1":
        raise ValueError("decision cards require polaris-science-results-v1")
    if isinstance(max_dark_h, bool) or not isinstance(max_dark_h, (int, float)) or not math.isfinite(max_dark_h) or max_dark_h < 0:
        raise ValueError("max_dark_h must be a finite non-negative number")
    arrival = bundle.get("derived", {}).get("arrival_slip")
    if not isinstance(arrival, dict):
        raise ValueError("decision cards require derived.arrival_slip for bundle-carried thresholds")
    point, point_index = _zero_slip(bundle)
    p = f"derived.arrival_slip.points[{point_index}]"
    thresholds = arrival["thresholds"]
    threshold_base = "derived.arrival_slip.thresholds"

    def percentage_requirement(
        *,
        requirement_id: str,
        title: str,
        nominal_key: str,
        threshold_key: str,
        clone_min_key: str,
        clone_max_key: str,
        pass_key: str,
        include_earth_coverage: bool,
    ) -> dict:
        nominal_path = f"{p}.nominal.{nominal_key}"
        threshold_path = f"{threshold_base}.{threshold_key}"
        return {
            "result_id": f"decision-card-{bundle['site']['id']}-{requirement_id}",
            "label": "SOURCE-BASED / UNVALIDATED",
            "requirement_id": requirement_id,
            "title": title,
            "unit": "%",
            "comparison": ">=",
            "threshold": _sourced(thresholds[threshold_key], threshold_path),
            "nominal": _sourced(point["nominal"][nominal_key], nominal_path),
            "signed_margin": _margin(
                point["nominal"][nominal_key], thresholds[threshold_key], nominal_path, threshold_path
            ),
            "clone_range": {
                "min": _sourced(point["clones"][clone_min_key], f"{p}.clones.{clone_min_key}"),
                "max": _sourced(point["clones"][clone_max_key], f"{p}.clones.{clone_max_key}"),
            },
            "clone_pass": {
                "count": _sourced(point["clones"][pass_key], f"{p}.clones.{pass_key}"),
                "denominator": _sourced(
                    point["clones"]["pass_denominator"], f"{p}.clones.pass_denominator"
                ),
                "wording": "pass on k/N deterministic terrain clones; not a probability",
            },
            "coverage": _coverage(bundle, include_earth=include_earth_coverage),
        }

    requirements = [
        percentage_requirement(
            requirement_id="sun-centre",
            title="Sun-centre visible",
            nominal_key="sun_center_visible_pct",
            threshold_key="sun_center_visible_pct_min",
            clone_min_key="sun_center_visible_pct_min",
            clone_max_key="sun_center_visible_pct_max",
            pass_key="sun_pass_count",
            include_earth_coverage=False,
        ),
        percentage_requirement(
            requirement_id="sun-and-earth",
            title="Sun + Earth centres visible",
            nominal_key="sun_and_earth_center_visible_pct",
            threshold_key="sun_and_earth_center_visible_pct_min",
            clone_min_key="sun_and_earth_center_visible_pct_min",
            clone_max_key="sun_and_earth_center_visible_pct_max",
            pass_key="joint_pass_count",
            include_earth_coverage=True,
        ),
    ]

    gap = None
    if isinstance(bundle.get("metrics", {}).get("longest_sun_center_hidden_h"), (int, float)):
        value_path = "metrics.longest_sun_center_hidden_h"
        value = bundle["metrics"]["longest_sun_center_hidden_h"]
        gap = {
            "result_id": f"decision-card-{bundle['site']['id']}-longest-sun-gap",
            "label": "SOURCE-BASED / UNVALIDATED observation; SCENARIO team requirement",
            "requirement_id": "maximum-sun-darkness",
            "title": "Longest Sun-centre blocked stretch",
            "unit": "h",
            "comparison": "<=",
            "threshold": _team_requirement(max_dark_h, "--max-dark-h"),
            "nominal": _sourced(value, value_path),
            "signed_margin": _maximum_margin(value, max_dark_h, value_path, "--max-dark-h"),
            "pass": value <= max_dark_h,
            "clone_evidence": {
                "status": "nominal only; per-clone longest Sun-gap is not present in this bundle"
            },
            "coverage": _coverage(bundle, include_earth=False),
        }

    ridges = []
    attribution = bundle.get("derived", {}).get("attribution")
    if isinstance(attribution, dict):
        for index, ridge in enumerate(attribution.get("ridges", [])):
            if not ridge.get("of_record"):
                continue
            base = f"derived.attribution.ridges[{index}]"
            ridges.append(
                {
                    "result_id": f"decision-card-{bundle['site']['id']}-ridge-{ridge['id']}",
                    "label": attribution.get("label", "SOURCE-BASED UNVALIDATED"),
                    "ridge_id": ridge["id"],
                    "distance_range_km": {
                        "min": _sourced(ridge["dist_range_km"][0], f"{base}.dist_range_km[0]"),
                        "max": _sourced(ridge["dist_range_km"][1], f"{base}.dist_range_km[1]"),
                    },
                    "azimuth_span_deg": {
                        "min": _sourced(ridge["az_span_deg"][0], f"{base}.az_span_deg[0]"),
                        "max": _sourced(ridge["az_span_deg"][1], f"{base}.az_span_deg[1]"),
                    },
                    "height_m": _sourced(ridge["height_m"], f"{base}.height_m"),
                    "sun_loss_h": _sourced(ridge["sun_loss_h"], f"{base}.sun_loss_h"),
                }
            )

    site = bundle["site"]
    card = {
        "schema": SCHEMA,
        "result_id": f"decision-card-{site['id']}-{bundle['bundle_id']}",
        "labels": ["SOURCE-BASED", "UNVALIDATED"],
        "source": {
            "bundle_id": bundle["bundle_id"],
            "bundle_path": bundle_path,
            "bundle_sha256": bundle_sha256,
            "bundle_schema": bundle["schema"],
            "validation_status": bundle["validation_status"]["overall"],
            "generator": bundle.get("generator", {}),
        },
        "site": {
            "id": site["id"],
            "name": site["name"],
            "latitude_deg": _sourced(site["lat_deg"], "site.lat_deg"),
            "longitude_deg_east": _sourced(site["lon_deg_east"], "site.lon_deg_east"),
            "observer_mast_m": _sourced(site["observer_mast_m"], "site.observer_mast_m"),
        },
        "window": {
            "start_utc": bundle["time"]["start_utc"],
            "stop_utc": bundle["time"]["stop_utc"],
        },
        "requirements": requirements,
        "ridge_of_record": ridges,
        "data_versions": bundle.get("provenance", {}).get("sources", []),
        "disclaimer": bundle["metrics"].get("disclaimer"),
    }
    if gap is not None:
        card["longest_sun_blocked_requirement"] = gap
    certainty = _certainty_height(bundle)
    if certainty is not None:
        card["certainty_height_m"] = certainty
    return card


def _value(item: dict) -> int | float | None:
    return item["value"]


def _fmt(value: int | float | None, digits: int = 2) -> str:
    if value is None:
        return "not available"
    return f"{value:.{digits}f}" if isinstance(value, float) else str(value)


def _source_attr(item: dict) -> str:
    return html.escape(item["source_path"], quote=True)


def render_html(card: dict) -> str:
    site = card["site"]
    requirement_rows = []
    for row in card["requirements"]:
        coverage = row.get("coverage") or {}
        coverage_text = []
        for key, label in (
            ("sun_critical_covered_fraction", "Sun critical covered fraction"),
            ("earth_critical_covered_fraction", "Earth critical covered fraction"),
        ):
            if key in coverage:
                coverage_text.append(f"{label}: {_fmt(_value(coverage[key]), 4)}")
        clone_range = row["clone_range"]
        clone_pass = row["clone_pass"]
        requirement_rows.append(
            f"""<tr data-result-id="{html.escape(row['result_id'])}" data-label="{html.escape(row['label'])}">
<th>{html.escape(row['title'])}</th>
<td data-source="{_source_attr(row['threshold'])}">{row['comparison']} {_fmt(_value(row['threshold']))} {row['unit']}</td>
<td data-source="{_source_attr(row['nominal'])}">{_fmt(_value(row['nominal']))} {row['unit']}</td>
<td data-source="{html.escape(' + '.join(row['signed_margin']['source_paths'].values()), quote=True)}">{_fmt(row['signed_margin']['value'])} {row['unit']}</td>
<td data-source="{_source_attr(clone_range['min'])} + {_source_attr(clone_range['max'])}">{_fmt(_value(clone_range['min']))}–{_fmt(_value(clone_range['max']))} {row['unit']}</td>
<td data-source="{_source_attr(clone_pass['count'])} + {_source_attr(clone_pass['denominator'])}">pass on {_fmt(_value(clone_pass['count']), 0)}/{_fmt(_value(clone_pass['denominator']), 0)} clones<br><small>{html.escape('; '.join(coverage_text))}</small></td>
</tr>"""
        )

    gap_html = ""
    if "longest_sun_blocked_requirement" in card:
        gap = card["longest_sun_blocked_requirement"]
        verdict = "PASS" if gap["pass"] else "FAIL"
        verdict_class = "pass" if gap["pass"] else "fail"
        gap_html = f"""<section><h2>Longest blocked stretch</h2>
<div data-result-id="{html.escape(gap['result_id'])}">
<p data-label="SCENARIO" data-source="{html.escape(gap['threshold']['source'], quote=True)}">Team requirement: longest Sun-centre blocked stretch {gap['comparison']} <strong>{_fmt(_value(gap['threshold']))} h</strong>.</p>
<p data-label="SOURCE-BASED / UNVALIDATED" data-source="{_source_attr(gap['nominal'])}">Bundle nominal: <strong>{_fmt(_value(gap['nominal']), 4)} h</strong> · headroom {_fmt(gap['signed_margin']['value'], 4)} h · <strong class="{verdict_class}">{verdict}</strong>.</p>
<p class="foot">{html.escape(gap['clone_evidence']['status'])}.</p>
</div></section>"""

    certainty_html = ""
    if "certainty_height_m" in card:
        certainty = card["certainty_height_m"]
        certainty_html = (
            f'<p data-source="{_source_attr(certainty)}">Certainty height: '
            f'<strong>{_fmt(_value(certainty))} m</strong></p>'
        )

    ridge_rows = "".join(
        f"""<tr data-result-id="{html.escape(ridge['result_id'])}" data-label="{html.escape(ridge['label'])}">
<th>{html.escape(ridge['ridge_id'])}</th>
<td data-source="{_source_attr(ridge['distance_range_km']['min'])} + {_source_attr(ridge['distance_range_km']['max'])}">{_fmt(_value(ridge['distance_range_km']['min']), 3)}–{_fmt(_value(ridge['distance_range_km']['max']), 3)} km</td>
<td data-source="{_source_attr(ridge['azimuth_span_deg']['min'])} + {_source_attr(ridge['azimuth_span_deg']['max'])}">{_fmt(_value(ridge['azimuth_span_deg']['min']), 2)}–{_fmt(_value(ridge['azimuth_span_deg']['max']), 2)}°</td>
<td data-source="{_source_attr(ridge['height_m'])}">{_fmt(_value(ridge['height_m']), 3)} m</td>
<td data-source="{_source_attr(ridge['sun_loss_h'])}">{_fmt(_value(ridge['sun_loss_h']), 2)} h</td>
</tr>"""
        for ridge in card["ridge_of_record"]
    )
    source_rows = "".join(
        f"<li><strong>{html.escape(source.get('id', 'source'))}</strong>: {html.escape(source.get('description', ''))}"
        f"{(' · SHA-256 ' + html.escape(source['sha256'])) if source.get('sha256') else ''}</li>"
        for source in card["data_versions"]
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>POLARIS X Decision Card — {html.escape(site['name'])}</title>
<style>
:root{{font-family:Inter,system-ui,sans-serif;color:#152032;background:#fff}}body{{margin:0;padding:24px}}
.card{{max-width:1050px;margin:auto;border:2px solid #26384f;padding:22px;display:grid;gap:18px}}
header{{display:grid;grid-template-columns:1fr auto;gap:16px;border-bottom:2px solid #26384f;padding-bottom:14px}}
h1,h2,p{{margin:0}}h1{{font-size:25px}}h2{{font-size:16px;margin-bottom:8px}}.labels{{font-weight:800;color:#7d3d00}}
.facts{{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}}.fact{{border:1px solid #aeb8c4;padding:9px}}
.fact span,small{{display:block;color:#526173;font-size:11px}}table{{width:100%;border-collapse:collapse;font-size:12px}}
th,td{{border:1px solid #aeb8c4;padding:7px;text-align:left;vertical-align:top}}thead th{{background:#e9eef4}}
code{{font-size:10px;overflow-wrap:anywhere}}ul{{margin:0;padding-left:18px;font-size:11px}}.foot{{font-size:11px;color:#526173}}.pass{{color:#146c43}}.fail{{color:#a42424}}
@media print{{@page{{size:landscape;margin:10mm}}body{{padding:0}}.card{{border:1px solid #000;max-width:none;break-inside:avoid}}}}
</style></head><body><main class="card" data-result-id="{html.escape(card['result_id'])}" data-label="SOURCE-BASED / UNVALIDATED">
<header><div><h1>POLARIS X Decision Card</h1><p>{html.escape(site['name'])} · {html.escape(site['id'])}</p></div><div class="labels">SOURCE-BASED · UNVALIDATED</div></header>
<section class="facts">
<div class="fact" data-source="{_source_attr(site['latitude_deg'])}"><span>Latitude</span>{_fmt(_value(site['latitude_deg']), 5)}°</div>
<div class="fact" data-source="{_source_attr(site['longitude_deg_east'])}"><span>Longitude east</span>{_fmt(_value(site['longitude_deg_east']), 5)}°</div>
<div class="fact" data-source="{_source_attr(site['observer_mast_m'])}"><span>Observer mast</span>{_fmt(_value(site['observer_mast_m']))} m</div>
<div class="fact"><span>UTC window</span>{html.escape(card['window']['start_utc'])}<br>{html.escape(card['window']['stop_utc'])}</div>
<div class="fact"><span>Bundle</span><code>{html.escape(card['source']['bundle_id'])}</code></div>
<div class="fact"><span>Bundle SHA-256</span><code>{html.escape(card['source']['bundle_sha256'])}</code></div>
</section>
<section><h2>Requirements</h2><table><thead><tr><th>Requirement</th><th>Threshold</th><th>Nominal</th><th>Signed margin</th><th>Clone min–max</th><th>Deterministic clone result + coverage</th></tr></thead><tbody>{''.join(requirement_rows)}</tbody></table></section>
{gap_html}{certainty_html}
<section><h2>Ridges of record</h2><table><thead><tr><th>Ridge</th><th>Distance range</th><th>Azimuth span</th><th>Height</th><th>Sun-loss</th></tr></thead><tbody>{ridge_rows}</tbody></table></section>
<section><h2>Data versions</h2><ul>{source_rows}</ul></section>
<p class="foot">{html.escape(card.get('disclaimer') or '')} Clone k/N is not a probability. Source bundle: {html.escape(card['source']['bundle_path'])}.</p>
</main></body></html>
"""


def write_card(bundle_path: Path, out_dir: Path, *, max_dark_h: int | float = 120) -> tuple[Path, Path]:
    raw = bundle_path.read_bytes()
    bundle = json.loads(raw)
    try:
        source_path = bundle_path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        source_path = bundle_path.name
    card = build_card(
        bundle,
        bundle_path=source_path,
        bundle_sha256=hashlib.sha256(raw).hexdigest(),
        max_dark_h=max_dark_h,
    )
    target = out_dir / bundle["site"]["id"]
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "decision_card.json"
    html_path = target / "decision_card.html"
    json_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    html_path.write_text(render_html(card))
    return json_path, html_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build deterministic POLARIS X decision cards")
    parser.add_argument("bundles", nargs="+", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("data/cards"))
    parser.add_argument(
        "--max-dark-h",
        type=float,
        default=120,
        help="team requirement for maximum longest Sun-centre blocked stretch (default: 120 h)",
    )
    args = parser.parse_args(argv)
    if len(args.bundles) > 2:
        parser.error("pass one or two bundles")
    for bundle_path in args.bundles:
        json_path, html_path = write_card(bundle_path, args.out_dir, max_dark_h=args.max_dark_h)
        print(f"wrote {json_path} and {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
