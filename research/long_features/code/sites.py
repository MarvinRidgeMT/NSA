R = {"Site04_ROI3": ("Site04", -89.78012, -156.32023, "Shackleton rim, Site04 RoI 3"),
     "Site01_ROI6": ("Site01", -89.47409, -137.3813, "Connecting Ridge, Site01 RoI 6"),
     "Site07_ROI1": ("Site07", -88.8063, 123.54887, "Peak near Shackleton, Site07 RoI 1"),
     "Site11_ROI4": ("Site11", -88.70606, -68.52994, "de Gerlache rim, Site11 RoI 4")}
NEW = ["Site07_ROI1", "Site11_ROI4"]
import os, json
def selected(n=3):
    keys = os.environ.get("SITES", ",".join(R)).split(",")
    return {k: R[k][:n] for k in keys}
def merge_dump(path, obj, **kw):
    """Update an existing JSON file instead of replacing it (top level, and one level down for dict values)."""
    try:
        old = json.load(open(path))
    except Exception:
        old = {}
    for k, v in obj.items():
        if isinstance(v, dict) and isinstance(old.get(k), dict) and k in ("measurement_test", "strategies"):
            old[k].update(v)
        else:
            old[k] = v
    json.dump(old, open(path, "w"), **kw)
