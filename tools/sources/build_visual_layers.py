#!/usr/bin/env python3
"""Build data/visual/visual_layers.json (polaris-visual-layers-v1) from completed LROC NAC windows.

One layer per `<name>_manifest.json` in data/visual/lroc_nac_pole_south_cm_avg/ that also has a full-window
`<name>_registration.json` (tools/sources/check_nac_dem_registration.py). A window without both is skipped and named:
an incomplete download or an unmeasured registration never becomes a layer. The file is the single place app/ and
web/ read visual-layer metadata from; nothing is copied into numerical bundles.
Usage: python tools/sources/build_visual_layers.py [--check]
"""
from __future__ import annotations
import glob, hashlib, json, os, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import visual_layers as vl  # noqa: E402

NAC_DIR = "data/visual/lroc_nac_pole_south_cm_avg"
OUT = os.path.join(ROOT, "data", "visual", "visual_layers.json")


def sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def nac_layer(manifest_path: str):
    name = os.path.basename(manifest_path)[: -len("_manifest.json")]
    reg_path = os.path.join(os.path.dirname(manifest_path), name + "_registration.json")
    if not os.path.exists(reg_path):
        return None, f"{name}: no full-window registration file ({os.path.basename(reg_path)})"
    with open(manifest_path, encoding="utf-8") as f:
        m = json.load(f)
    with open(reg_path, encoding="utf-8") as f:
        r = json.load(f)
    w = m["window"]
    if r.get("rowsUsed1m") != w["height"]:
        return None, f"{name}: registration used {r.get('rowsUsed1m')} of {w['height']} rows (not the full window)"
    png_rel = f"{NAC_DIR}/{m['display8bit']['file']}"
    png = os.path.join(ROOT, png_rel)
    digest = sha256(png)
    if digest != m["display8bit"]["sha256"]:
        return None, f"{name}: display PNG hash differs from its manifest"
    layer = {
        "id": "lroc-nac-avg-" + name.replace("_", "-"),
        "role": "albedo",
        "title": m["product"]["title"] + " (window)",
        "label": "LROC NAC AVG · VISUAL",
        "status": "VISUAL",
        "numericalAuthority": False,
        "productId": m["product"]["productId"],
        "sourceUrl": m["product"]["url"],
        "productPage": m["product"]["productPage"],
        "cite": m["product"]["cite"],
        "siteId": "connecting" if name.startswith("site01") else name.split("_")[0],
        "artifact": {"path": png_rel, "sha256": digest, "width": w["width"], "height": w["height"], "format": "png-8bit-gray",
                     "bytes": os.path.getsize(png), "noDataValue": 0},
        "sourceHash": {"kind": "byte-range-window", "sha256": m["rawWindowSha256"], "wholeFileSha256": None,
                       "note": "hash of the little-endian float32 window bytes; the 8.28 GB tile was not downloaded in full"},
        "pixelSizeM": m["projection"]["pixelScaleM"],
        "projection": {"type": "south_polar_stereographic", "centreLatDeg": -90, "centreLonEastDeg": 0, "radiusM": 1737400, "units": "m",
                       "axes": "+x toward 90 E, +y toward 0 E (same as PGDA 78/90)"},
        "frame": "controlled to LOLA track data (ISIS jigsaw); planetocentric, east-positive; frame name not stated in the label",
        "boundsM": {"xmin": w["xminM"], "xmax": w["xmaxM"], "ymin": w["yminM"], "ymax": w["ymaxM"], "boundsAre": "pixel-edges"},
        "rowOrder": "north-to-south",
        "registration": {"method": r["method"], "against": "NASA PGDA 78 Site01 5 m DEM (" + os.path.basename(r.get("dem", "Site01_final_adj_5mpp_surf.tif")) + ")",
                         "offsetM": {"x": r["imageShiftRelativeToDemM"]["x"], "y": r["imageShiftRelativeToDemM"]["y"]},
                         "peakNcc": r["peakNcc"], "nccAtZeroShift": r["nccAtZeroShift"], "comparedPixels": r["comparedPixels5m"],
                         "appliedShiftM": {"x": 0, "y": 0}, "status": "display-alignment-evidence-only",
                         "evidencePath": f"{NAC_DIR}/{name}_registration.json"},
        "display": {"processing": m["display8bit"]["stretch"], "stretchLow": m["display8bit"]["p0_5"], "stretchHigh": m["display8bit"]["p99_5"]},
        "limitations": m["limitations"] + ["Covers only its bounds; outside them the renderer must show neutral shading, never invented imagery."],
    }
    return vl.validate_layer(layer), None


def main() -> None:
    layers, skipped = [], []
    for mp in sorted(glob.glob(os.path.join(ROOT, NAC_DIR, "*_manifest.json"))):
        layer, why = nac_layer(mp)
        (layers.append(layer) if layer else skipped.append(why))
    partial = [os.path.basename(p) for p in glob.glob(os.path.join(ROOT, NAC_DIR, "*.partial"))]
    doc = {"schema": vl.SCHEMA_ID, "generatedUTC": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "releaseStatus": "SOURCE_BASED_UNVALIDATED",
           "note": "Display-only rasters. Never numerical terrain; never mission-time illumination. Generated by tools/sources/build_visual_layers.py.",
           "layers": layers}
    vl.validate_visual_layers(doc)
    print(json.dumps({"layers": [l["id"] for l in layers], "skipped": skipped, "downloadsInProgress": partial}, indent=1))
    if "--check" in sys.argv:
        if os.path.exists(OUT):
            with open(OUT, encoding="utf-8") as f:
                on_disk = json.load(f)
            vl.validate_visual_layers(on_disk)
            if [l for l in on_disk["layers"]] != layers:
                print("data/visual/visual_layers.json is stale: rebuild it"); sys.exit(1)
        elif layers:
            print("data/visual/visual_layers.json missing"); sys.exit(1)
        return
    if not layers and not os.path.exists(OUT):
        print("no completed window yet: nothing written")
        return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
