#!/usr/bin/env python3
"""Pre-registered comparison of POLARIS Sun visibility with NASA SVS 4930 illumination frames.

Protocol (frozen first): docs/validation/SVS4930_PROTOCOL.md (SHA-256 in docs/validation/SVS4930_PROTOCOL.sha256).
Every threshold below is the protocol's value; the script refuses to run if the protocol file's hash differs.

Steps: (1) hash the frames; (2) find the pole pixel from the overlay crosshair; (3) fit rotation / mirror / scale by
correlating frame luminance with a Lambert cos-incidence image of the PGDA 90 DEM (DEM normals only; no horizon, no cast
shadow, no POLARIS solver output) for each frame's own sub-solar point; (4) project the three bundle sites into the frames;
(5) classify lit/shadow and compare with the bundles' sun.center_visible at the same UTC.
Usage: python tools/validation/svs4930_compare.py --frames tmp/svs4930 --dem tmp/svs4930/ldem_pole_240m.npy
"""
from __future__ import annotations
import argparse, hashlib, json, math, os, sys
from datetime import datetime, timedelta, timezone
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROTOCOL = os.path.join(ROOT, "docs", "validation", "SVS4930_PROTOCOL.md")
PROTOCOL_SHA = "1946a9c58b406de56d2e79624c31748db7db688cab68304cafefa4d613ef0038"
# --- frozen parameters (protocol) ---
FIRST, LAST = 3805, 3973
EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)
SHADOW_Y = 8.0
NEAR_CRITICAL_DEG = 0.5
MIN_SAMPLES, PASS_AGREEMENT = 20, 0.90
FIT_FRAMES = (3805, 3847, 3889, 3931, 3973)
BUNDLES = {"site04_roi3": "data/bundles/site04_roi3_2026-11-14_14d_mast1m.json",
           "site04_roi4": "data/bundles/site04_roi4_2026-11-14_14d_mast1m.json",
           "site01_roi6": "data/bundles/site01_roi6_2026-11-14_14d_mast1m.json"}
R_MOON = 1737400.0
DEM_HALF_M, DEM_N = 60000.0, 500          # tmp/svs4930/ldem_pole_240m.npy: PGDA 90 read at 240 m, x/y in [-60, 60] km, row 0 = north


def frame_utc(n: int) -> datetime:
    return EPOCH + timedelta(hours=2 * (n - 1))


def sha(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def luminance(rgb: np.ndarray) -> np.ndarray:
    return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]


def find_pole(rgb: np.ndarray):
    """Crosshair of the overlay: thin cyan-ish lines (G, B well above R). Returns (col, row) of the intersection."""
    r, g, b = (rgb[..., k].astype(float) for k in range(3))
    cyan = (g - r > 12) & (b - r > 12)
    col = int(np.argmax(cyan.sum(axis=0)))
    row = int(np.argmax(cyan.sum(axis=1)))
    return col, row, int(cyan.sum(axis=0)[col]), int(cyan.sum(axis=1)[row])


def stereo_xy(lat_deg: float, lon_e_deg: float):
    r = 2 * R_MOON * math.tan(math.radians(90 + lat_deg) / 2)
    return r * math.sin(math.radians(lon_e_deg)), r * math.cos(math.radians(lon_e_deg))


def lambert(dem: np.ndarray, sub_lat: float, sub_lon_e: float) -> np.ndarray:
    """cos-incidence for a Sun toward grid direction (sin L, cos L) at elevation -sub_lat (south pole approximation). No shadows."""
    s = 2 * DEM_HALF_M / (DEM_N - 1)
    dzdx = np.gradient(dem, s, axis=1)
    dzdy = -np.gradient(dem, s, axis=0)               # row 0 = north (largest y)
    n = np.sqrt(dzdx ** 2 + dzdy ** 2 + 1)
    el = math.radians(-sub_lat)
    L = math.radians(sub_lon_e)
    sx, sy, sz = math.cos(el) * math.sin(L), math.cos(el) * math.cos(L), math.sin(el)
    return np.clip((-dzdx * sx - dzdy * sy + sz) / n, 0, None)


def dem_points(step: int):
    c = np.linspace(-DEM_HALF_M, DEM_HALF_M, DEM_N)[::step]
    X, Y = np.meshgrid(c, c[::-1])                    # rows north->south
    return X, Y


def to_frame(x, y, pole, theta, scale, mirror):
    """Map metres -> frame (col,row): rotate by -theta, divide by scale (m/px), optional mirror, image v points down."""
    ct, st = math.cos(theta), math.sin(theta)
    u = (ct * x + st * y) / scale
    v = (-st * x + ct * y) / scale
    if mirror:
        u = -u
    return pole[0] + u, pole[1] - v


def sample(img: np.ndarray, col, row):
    h, w = img.shape
    ci, ri = np.rint(col).astype(int), np.rint(row).astype(int)
    ok = (ci >= 0) & (ci < w) & (ri >= 0) & (ri < h)
    out = np.full(np.shape(col), np.nan)
    out[ok] = img[ri[ok], ci[ok]]
    return out


def fit(frames, dem, pole, overlay_mask):
    best = None
    for coarse in (True, False):
        step = 4 if coarse else 1
        X, Y = dem_points(step)
        dm = dem[::step, ::step]
        if coarse:
            thetas = np.radians(np.arange(0, 360, 2.0)); scales = np.arange(104, 126, 2.0); mirrors = (False, True)
        else:
            t0, s0, m0 = best[1], best[2], best[3]
            thetas = t0 + np.radians(np.arange(-2, 2.01, 0.25)); scales = s0 + np.arange(-2, 2.01, 0.25); mirrors = (m0,)
        shades = [lambert(dm if not coarse else dm, f["subLat"], f["subLon"]) if False else None for f in frames]
        shades = []
        for f in frames:
            full = lambert(dem, f["subLat"], f["subLon"])
            shades.append(full[::step, ::step])
        for m in mirrors:
            for th in thetas:
                for sc in scales:
                    c, r = to_frame(X, Y, pole, th, sc, m)
                    rs = []
                    for f, sh in zip(frames, shades):
                        y = sample(f["Y"], c, r)
                        msk = sample(overlay_mask, c, r)
                        ok = np.isfinite(y) & (msk == 0)
                        if ok.sum() < 500:
                            rs.append(-1); continue
                        a, b = y[ok], sh[ok]
                        if a.std() == 0 or b.std() == 0:
                            rs.append(-1); continue
                        rs.append(float(np.corrcoef(a, b)[0, 1]))
                    score = float(np.mean(rs))
                    if best is None or score > best[0]:
                        best = (score, float(th), float(sc), bool(m))
    return best


def overlay_parse_ok(path_png):  # placeholder kept for clarity: overlay text is checked by eye and recorded in the report
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frames", required=True); ap.add_argument("--dem", required=True)
    ap.add_argument("--subsolar", required=True, help="JSON {frame: [lat, lonE]} read from the overlays of the fit frames")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "validation", "svs4930"))
    a = ap.parse_args()
    if sha(PROTOCOL) != PROTOCOL_SHA:
        sys.exit("protocol file changed since it was frozen: refusing")
    subsolar = {int(k): v for k, v in json.load(open(a.subsolar)).items()}
    paths = {n: os.path.join(a.frames, f"sp_illum.{n:04d}.tif") for n in range(FIRST, LAST + 1)}
    missing = [n for n, p in paths.items() if not os.path.exists(p)]
    if missing:
        sys.exit(f"missing frames: {missing[:5]}…")
    hashes = {n: sha(p) for n, p in paths.items()}
    rgb0 = np.asarray(Image.open(paths[FIRST]).convert("RGB"))
    h, w, _ = rgb0.shape
    pc, pr, nc, nr = find_pole(rgb0)
    # overlay mask: text block bottom-right, title/logo top-right, crosshair and circle pixels (excluded from the fit)
    mask = np.zeros((h, w), np.uint8)
    mask[int(h * 0.62):, int(w * 0.68):] = 1
    mask[:int(h * 0.30), int(w * 0.68):] = 1
    r, g, b = (rgb0[..., k].astype(float) for k in range(3))
    mask[(g - r > 12) & (b - r > 12)] = 1
    dem = np.load(a.dem)
    fit_frames = []
    for n in FIT_FRAMES:
        rgb = np.asarray(Image.open(paths[n]).convert("RGB")).astype(float)
        fit_frames.append({"n": n, "Y": luminance(rgb), "subLat": subsolar[n][0], "subLon": subsolar[n][1]})
    score, theta, scale, mirror = fit(fit_frames, dem, (pc, pr), mask)
    sites = {}
    for sid, rel in BUNDLES.items():
        bpath = os.path.join(ROOT, rel)
        b = json.load(open(bpath))
        x, y = stereo_xy(b["site"]["lat_deg"], b["site"]["lon_deg_east"])
        c, rr = to_frame(np.array([x]), np.array([y]), (pc, pr), theta, scale, mirror)
        sites[sid] = {"bundle": rel, "bundleSha256": sha(bpath), "latDeg": b["site"]["lat_deg"], "lonEastDeg": b["site"]["lon_deg_east"],
                      "xyM": [round(x, 1), round(y, 1)], "framePx": [float(c[0]), float(rr[0])], "samples": {s["utc"][:19]: s for s in b["samples"]}}
    rows = []
    for n in range(FIRST, LAST + 1):
        t = frame_utc(n).strftime("%Y-%m-%dT%H:%M:%S")
        Y = luminance(np.asarray(Image.open(paths[n]).convert("RGB")).astype(float))
        for sid, s in sites.items():
            ci, ri = int(round(s["framePx"][0])), int(round(s["framePx"][1]))
            block = Y[ri - 1:ri + 2, ci - 1:ci + 2]
            lit_c = bool(Y[ri, ci] >= SHADOW_Y)
            states = set((block >= SHADOW_Y).ravel().tolist())
            smp = s["samples"].get(t)
            if smp is None:
                sys.exit(f"bundle {sid} has no sample at {t}")
            sun = smp["sun"]
            rows.append({"frame": n, "utc": t + "Z", "site": sid, "svsY": round(float(Y[ri, ci]), 1), "svsLit": lit_c,
                         "ambiguous": len(states) > 1, "polarisCentreVisible": bool(sun["center_visible"]),
                         "polarisDiskFraction": sun.get("disk_fraction"), "marginDeg": sun["margin_deg"],
                         "nearCritical": abs(sun["margin_deg"]) < NEAR_CRITICAL_DEG})
    summary, verdict = {}, "PASS"
    for sid in sites:
        rs = [r for r in rows if r["site"] == sid]
        comp = [r for r in rs if not r["ambiguous"] and not r["nearCritical"]]
        agree = [r for r in comp if r["svsLit"] == r["polarisCentreVisible"]]
        allc = [r for r in rs if not r["ambiguous"]]
        cm = {k: sum(1 for r in comp if (r["svsLit"], r["polarisCentreVisible"]) == v) for k, v in
              {"bothLit": (True, True), "bothShadow": (False, False), "svsLitPolarisBlocked": (True, False), "svsShadowPolarisVisible": (False, True)}.items()}
        sec = [r for r in comp if r["svsLit"] == ((r["polarisDiskFraction"] or 0) > 0)]
        summary[sid] = {"frames": len(rs), "ambiguous": sum(r["ambiguous"] for r in rs), "nearCritical": sum(r["nearCritical"] for r in rs),
                        "compared": len(comp), "agreement": round(len(agree) / len(comp), 4) if comp else None,
                        "confusion": cm, "agreementWithoutNearCriticalExclusion": round(sum(r["svsLit"] == r["polarisCentreVisible"] for r in allc) / len(allc), 4) if allc else None,
                        "secondaryDiskFractionAgreement": round(len(sec) / len(comp), 4) if comp else None}
        if len(comp) < MIN_SAMPLES:
            verdict = "INCONCLUSIVE" if verdict == "PASS" else verdict
        elif len(agree) / len(comp) < PASS_AGREEMENT:
            verdict = "FAIL"
    os.makedirs(a.out, exist_ok=True)
    report = {"schema": "polaris-validation-svs4930-v1", "generatedUTC": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "protocol": {"file": "docs/validation/SVS4930_PROTOCOL.md", "sha256": PROTOCOL_SHA},
              "reference": {"product": "NASA SVS 4930", "url": "https://svs.gsfc.nasa.gov/4930/", "frames": [FIRST, LAST],
                            "frameSha256": {str(k): v for k, v in hashes.items()}},
              "registration": {"poleCrosshairPx": [pc, pr], "crosshairPixelCounts": [nc, nr], "rotationDeg": round(math.degrees(theta) % 360, 3),
                               "scaleMPerPx": round(scale, 3), "mirrored": mirror, "meanCorrelation": round(score, 4), "fitFrames": list(FIT_FRAMES),
                               "subsolarFromOverlay": {str(k): v for k, v in subsolar.items()}},
              "sites": {k: {kk: vv for kk, vv in v.items() if kk != "samples"} for k, v in sites.items()},
              "parameters": {"shadowLuminance": SHADOW_Y, "nearCriticalDeg": NEAR_CRITICAL_DEG, "minSamples": MIN_SAMPLES, "passAgreement": PASS_AGREEMENT},
              "summary": summary, "verdict": verdict, "rows": rows}
    with open(os.path.join(a.out, "svs4930_comparison.json"), "w") as f:
        json.dump(report, f, indent=1)
    print(json.dumps({k: report[k] for k in ("registration", "summary", "verdict")}, indent=1))
    print("sites px:", {k: v["framePx"] for k, v in sites.items()})


if __name__ == "__main__":
    main()
