"""Visual-layer contract (polaris-visual-layers-v1): validation and the solver guard. Standard library only.

A visual layer is a display raster (albedo, morphology...). It is never numerical terrain:
`status` is "VISUAL", `numericalAuthority` is False, and DEM fields (values, spacing, n, verticalUnits...) are forbidden.
`reject_visual_layer(obj)` is the guard solvers call before reading a DEM.
The same rules are implemented in app/src/visual-layers.js and web/src/bundle/visualLayers.ts and are driven by the
shared cases in schemas/fixtures/visual-layers-cases.json.
"""
from __future__ import annotations
import re

SCHEMA_ID = "polaris-visual-layers-v1"
ROLES = ("albedo", "morphology", "hillshade", "reference-image")
DEM_FIELDS = ("values", "verticalUnits", "spacing", "n", "originX", "originY", "layer", "kind")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
_PATH = re.compile(r"^(?!/)(?!.*\.\.)[A-Za-z0-9_./-]+$")


class VisualLayerError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")


def validate_layer(layer: dict) -> dict:
    if not isinstance(layer, dict):
        raise VisualLayerError("LAYER", "layer must be an object")
    for f in DEM_FIELDS:
        if f in layer:
            raise VisualLayerError("DEM_FIELDS", f"visual layer must not carry the numerical DEM field '{f}'")
    if layer.get("status") != "VISUAL" or "VISUAL" not in str(layer.get("label", "")):
        raise VisualLayerError("VISUAL_STATUS", "status must be 'VISUAL' and the label must contain the word VISUAL")
    if layer.get("numericalAuthority") is not False:
        raise VisualLayerError("NUMERICAL_AUTHORITY", "numericalAuthority must be exactly false")
    if not isinstance(layer.get("id"), str) or not _ID.match(layer["id"]):
        raise VisualLayerError("ID", "id must be a stable lower-case slug")
    if layer.get("role") not in ROLES:
        raise VisualLayerError("ROLE", f"role must be one of {ROLES}")
    for k in ("title", "productId", "frame"):
        if not isinstance(layer.get(k), str) or len(layer[k]) < 3:
            raise VisualLayerError("FIELD", f"{k} missing")
    if not str(layer.get("sourceUrl", "")).startswith("https://"):
        raise VisualLayerError("FIELD", "sourceUrl must be https")
    p = layer.get("projection") or {}
    if p.get("units") != "m":
        raise VisualLayerError("UNITS", "projection.units must be 'm'")
    if p.get("type") != "south_polar_stereographic" or p.get("centreLatDeg") != -90 or p.get("centreLonEastDeg") != 0 or p.get("radiusM") != 1737400:
        raise VisualLayerError("PROJECTION", "only south polar stereographic, 90 S / 0 E, R = 1737400 m is accepted")
    a = layer.get("artifact") or {}
    if not isinstance(a.get("path"), str) or not _PATH.match(a["path"]):
        raise VisualLayerError("ARTIFACT", "artifact.path must be a repository-relative path")
    if not isinstance(a.get("sha256"), str) or not _HEX.match(a["sha256"]):
        raise VisualLayerError("HASH", "artifact.sha256 must be 64 lower-case hex characters")
    sh = layer.get("sourceHash") or {}
    if sh.get("kind") not in ("whole-file", "byte-range-window") or not isinstance(sh.get("sha256"), str) or not _HEX.match(sh["sha256"]):
        raise VisualLayerError("HASH", "sourceHash.sha256 must be 64 lower-case hex characters")
    if sh.get("wholeFileSha256") is not None and not _HEX.match(str(sh["wholeFileSha256"])):
        raise VisualLayerError("HASH", "sourceHash.wholeFileSha256 must be null or 64 hex characters")
    if not all(isinstance(a.get(k), int) and not isinstance(a.get(k), bool) and a[k] > 0 for k in ("width", "height")):
        raise VisualLayerError("ARTIFACT", "artifact width/height must be positive integers")
    px = layer.get("pixelSizeM")
    if not _num(px) or px <= 0:
        raise VisualLayerError("UNITS", "pixelSizeM must be a positive number of metres")
    b = layer.get("boundsM") or {}
    if not all(_num(b.get(k)) for k in ("xmin", "xmax", "ymin", "ymax")) or b.get("boundsAre") != "pixel-edges":
        raise VisualLayerError("BOUNDS", "boundsM needs xmin/xmax/ymin/ymax (pixel-edges)")
    if not (b["xmin"] < b["xmax"] and b["ymin"] < b["ymax"]):
        raise VisualLayerError("BOUNDS", "bounds are inverted")
    if abs((b["xmax"] - b["xmin"]) - a["width"] * px) > 1e-6 or abs((b["ymax"] - b["ymin"]) - a["height"] * px) > 1e-6:
        raise VisualLayerError("BOUNDS", "bounds do not equal artifact size x pixelSizeM")
    if layer.get("rowOrder") != "north-to-south":
        raise VisualLayerError("BOUNDS", "rowOrder must be north-to-south")
    r = layer.get("registration") or {}
    o = r.get("offsetM") or {}
    if r.get("status") != "display-alignment-evidence-only" or not _num(o.get("x")) or not _num(o.get("y")) or not r.get("method") or not r.get("against"):
        raise VisualLayerError("REGISTRATION", "registration needs method, against, offsetM and status 'display-alignment-evidence-only'")
    if not isinstance((layer.get("display") or {}).get("processing"), str):
        raise VisualLayerError("DISPLAY", "display.processing must describe the stretch")
    lim = layer.get("limitations")
    if not isinstance(lim, list) or not lim or not all(isinstance(x, str) and len(x) >= 8 for x in lim):
        raise VisualLayerError("LIMITATIONS", "at least one limitation is required")
    return layer


def validate_visual_layers(doc: dict) -> dict:
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA_ID:
        raise VisualLayerError("SCHEMA", f"schema must be {SCHEMA_ID}")
    if doc.get("releaseStatus") != "SOURCE_BASED_UNVALIDATED":
        raise VisualLayerError("RELEASE_STATUS", "releaseStatus must stay SOURCE_BASED_UNVALIDATED")
    layers = doc.get("layers")
    if not isinstance(layers, list):
        raise VisualLayerError("SCHEMA", "layers must be an array")
    seen = set()
    for layer in layers:
        validate_layer(layer)
        if layer["id"] in seen:
            raise VisualLayerError("DUPLICATE_ID", layer["id"])
        seen.add(layer["id"])
    return doc


def is_visual_layer(obj) -> bool:
    return isinstance(obj, dict) and (obj.get("status") == "VISUAL" or obj.get("numericalAuthority") is False
                                      or (isinstance(obj.get("artifact"), dict) and "values" not in obj))


def reject_visual_layer(obj):
    """Solver guard: raise if `obj` is (or is flagged as) a visual layer. Returns obj otherwise."""
    if is_visual_layer(obj):
        raise VisualLayerError("VISUAL_LAYER_AS_DEM", "a visual layer cannot be used as solver terrain (numericalAuthority is false)")
    return obj
