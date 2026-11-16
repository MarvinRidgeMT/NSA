#!/usr/bin/env python3
"""Build display-only terrain context packs: regional DEM placement + horizon maps for shading.

For each dataset with a 5 m local crop, writes data/visual/terrain_context/<datasetId>/:
  context.json          metadata (polaris-terrain-context-v1; status VISUAL; numericalAuthority false)
  regional_f32.bin      the 80 m PGDA 90 crop already stored in the two-site source bundle, little-endian float32,
                        rows south-to-north, unchanged values (its float64 crop hash is re-verified here)
  local_horizon_u8.bin  horizon map of the local crop, (K, m, m) uint8, m = 201 (every 2nd node = 10 m)
  regional_horizon_u8.bin  horizon map of the regional crop, (K, m, m) uint8, m = 201 (every 2nd node = 160 m)
Angles: uint8 q -> degrees = q * 0.05 - 3 (clipped to -3 .. +9.75).

Inputs (nothing is downloaded): data/viewer/polaris-x5d-roi-2026-11-14-v2.json (ROI datasets, 5 m crops),
app/data/polaris-source-site01-2026-11-14-v2.json (Site01 site-centre 5 m crop), and
app/data/polaris-source-two-site-2026-11-14-v2.json (Site01 + Site04 80 m regional crops).

VISUAL ONLY: finite crops, ground points, K azimuths, nearest-cell marching. The solver's skyline (full 5 m tile +
80 m to 280 km, observer on a mast) is the numerical authority; this never feeds it. A cross-check against the
bundle skyline at the observer is printed and stored as display-consistency evidence, not validation.
Usage: python tools/terrain/build_terrain_context.py [--only site04_roi3] [--k 48]
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time
from datetime import datetime, timezone
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import terrain_context as tc  # noqa: E402

OUT = os.path.join(ROOT, "data", "visual", "terrain_context")
LOCAL_LIFT_M, REGIONAL_LIFT_M = 0.5, 4.0   # display shadow bias (see terrain_context.horizon_map)
MID_N, MID_BLOCK = 401, 4          # L1: 401 x 401 nodes at 20 m (4 x 4 block means of the 5 m display surface), about +-4 km.
# (801 x 801 at 10 m was tried on 15 Nov: 640k vertices made the scene too slow to start on software GL and crashed test pages.)
MID_LIFT_M = 1.5
TILE_FOR = {"site01": "app/data/source/pgda78/Site01/Site01_final_adj_5mpp_surf.tif", "connecting": "app/data/source/pgda78/Site01/Site01_final_adj_5mpp_surf.tif",
            "site04": "app/data/source/pgda78/Site04/Site04_final_adj_5mpp_surf.tif"}
TILE_SHA = {"app/data/source/pgda78/Site01/Site01_final_adj_5mpp_surf.tif": "3ba7b97cb00a2bcf21189c3aeb535f65afc21207154ab9f0d43c5bdc1f7e747e",
            "app/data/source/pgda78/Site04/Site04_final_adj_5mpp_surf.tif": "38ff70dbdf2f066c2cfa94a646c3a59d653ce7f6b4528b15fc1b43ee397ce758"}
REGIONAL_FOR = {"site01": "connecting", "connecting": "connecting", "site04": "shackleton", "shackleton": "shackleton"}


# NASA GSFC shape-from-shading (SfS) elevation for Artemis III candidate region 6 "Connecting Ridge" (Bertone et al.,
# Zenodo 10.5281/zenodo.17954508, CC-BY-4.0; paper 10.3847/PSJ/ae5b70). LOLA-controlled, refined with LROC NAC images; 5 m grid
# on the same south-polar stereographic lattice as PGDA 78. DISPLAY ONLY here: it replaces the LOLA crop in the picture, never in
# the solver. pixelSha256 is of the decoded float32 raster (the file container was rewritten in transfer; pixels are identical
# to the Zenodo file, whose own SHA-256 is c914e52b...ddd0 inside A3CLR22_6_Connecting_Ridge.zip, md5 0ad982cf42319a300f2a2cff69d39322).
SFS = {"file": "app/data/source/gsfc_sfs_a3clr22/A306_GLDELEV_005.tif",
       "pixelSha256": "8d7a4a2036d73555da50e682b9385e3ed96b3e66d628b50af88ae9d9aa66134c",
       "left": -19000.0, "right": -3000.0, "bottom": -20000.0, "top": -4000.0, "px": 5.0, "featherM": 200.0,
       "product": "NASA GSFC SfS elevation A306_GLDELEV_005 (Artemis III candidate region 6, Connecting Ridge), 5 m",
       "citation": "Bertone, S., McKenna, T. E., Barker, M. K., Mazarico, E., Beyer, R. A., Petro, N. (2025), Zenodo, doi:10.5281/zenodo.17954508",
       "doi": "10.5281/zenodo.17954508", "licence": "CC-BY-4.0"}
_sfs_cache = {}


def sfs_raster():
    """The SfS elevation raster (north-up float64) or None when the file is absent. Pixel hash is verified."""
    if "a" not in _sfs_cache:
        path = os.path.join(ROOT, SFS["file"])
        if not os.path.exists(path):
            _sfs_cache["a"] = None
        else:
            import rasterio
            with rasterio.open(path) as d:
                a = d.read(1)
                b = d.bounds
                if (b.left, b.right, b.bottom, b.top) != (SFS["left"], SFS["right"], SFS["bottom"], SFS["top"]) or d.res[0] != SFS["px"]:
                    raise SystemExit(f"{SFS['file']}: unexpected bounds or pixel size")
                nod = d.nodata
            if hashlib.sha256(np.ascontiguousarray(a, dtype="<f4").tobytes()).hexdigest() != SFS["pixelSha256"]:
                raise SystemExit(f"{SFS['file']}: pixel SHA-256 differs from the documented value")
            a = a.astype("f8")
            if nod is not None:
                a[a == nod] = np.nan
            _sfs_cache["a"] = a
    return _sfs_cache["a"]


def sfs_weight(X, Y, feather=None):
    """Blend weight of the SfS surface at absolute polar-stereographic metres: 0 outside its footprint, rising linearly to 1
    `feather` metres inside the edge (so the display surface joins the LOLA surface without a step)."""
    f = SFS["featherM"] if feather is None else feather
    d = np.minimum(np.minimum(X - SFS["left"], SFS["right"] - X), np.minimum(Y - SFS["bottom"], SFS["top"] - Y))
    return np.clip(d / f, 0.0, 1.0)


def sfs_blend(lola, X, Y):
    """Display heights = (1 - w) LOLA + w SfS at nodes (X, Y) (absolute metres, any shape). SfS is sampled bilinearly (exact
    when the node is a pixel centre). Returns (display, w). Without the SfS file or coverage: (lola, zeros)."""
    a = sfs_raster()
    w = sfs_weight(X, Y) if a is not None else np.zeros(np.shape(lola))
    if a is None or not (w > 0).any():
        return np.array(lola, dtype="f8"), np.zeros(np.shape(lola))
    c = (X - (SFS["left"] + SFS["px"] / 2)) / SFS["px"]
    rr = ((SFS["top"] - SFS["px"] / 2) - Y) / SFS["px"]
    c0 = np.clip(np.floor(c).astype(int), 0, a.shape[1] - 2); r0 = np.clip(np.floor(rr).astype(int), 0, a.shape[0] - 2)
    fc = np.clip(c - c0, 0, 1); fr = np.clip(rr - r0, 0, 1)
    z = (a[r0, c0] * (1 - fc) * (1 - fr) + a[r0, c0 + 1] * fc * (1 - fr) + a[r0 + 1, c0] * (1 - fc) * fr + a[r0 + 1, c0 + 1] * fc * fr)
    w = np.where(np.isfinite(z), w, 0.0)
    return np.where(w > 0, (1 - w) * np.asarray(lola, dtype="f8") + w * np.where(np.isfinite(z), z, 0.0), np.asarray(lola, dtype="f8")), w


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return json.load(f)


def grid_of(dem) -> tc.Grid:
    return tc.Grid(dem["values"], dem["n"], dem["spacing"], dem["originX"], dem["originY"])


def crop_hash(dem) -> str:
    return sha(np.asarray(dem["values"], dtype="<f8").tobytes())


def skyline_check(ds, local: tc.Grid, regional: tc.Grid):
    """Display-consistency evidence: horizon at the scenario observer (on its mast) marched over the DISPLAYED crops
    with the same rule as the map, compared bin by bin with the bundle's solver skyline. Not a validation."""
    derived = ds.get("derived") or {}
    sc = (derived.get("scenarios") or [None])[0]
    if not sc or "skyline" not in sc or "observer" not in sc:
        return None
    sk, ob = sc["skyline"], sc["observer"]
    az, el = np.asarray(sk["azimuthDeg"], dtype=float), np.asarray(sk["elevationDeg"], dtype=float)
    fr = derived.get("frame") or {}
    lon = np.radians(ds["site"]["longitudeEastDeg"])
    north = fr.get("localNorthInGrid") or (np.sin(lon), np.cos(lon))
    east = fr.get("localEastInGrid") or (np.cos(lon), -np.sin(lon))
    A = np.radians(az)
    gx, gy = np.sin(A) * east[0] + np.cos(A) * north[0], np.sin(A) * east[1] + np.cos(A) * north[1]
    z0, _ = local.sample_nearest(np.array([ob["xM"]]), np.array([ob["yM"]]))
    z0 = float(z0[0]) + float(ob.get("mastM") or 0)
    best = np.full(az.shape, -np.inf)
    for d in list(np.arange(local.s, 1200 + 1e-9, local.s)) + list(np.arange(1200 + regional.s, 20000 + 1e-9, regional.s)):
        px, py = ob["xM"] + d * gx, ob["yM"] + d * gy
        z, ok = (local.sample_nearest(px, py) if d <= 1200 else (np.full(az.shape, np.nan), np.zeros(az.shape, bool)))
        zf, okf = regional.sample_nearest(px, py)
        z = np.where(ok, z, zf); ok = ok | okf
        t = (z - z0 - d * d / (2 * tc.MOON_RADIUS_M)) / d
        best = np.where(ok, np.maximum(best, t), best)
    mine = np.degrees(np.arctan(best))
    good = np.isfinite(mine) & np.isfinite(el)
    diff = mine[good] - el[good]
    return {"comparedBins": int(good.sum()), "observerMastM": ob.get("mastM"),
            "displayMinusSolverDeg": {"median": round(float(np.median(diff)), 3), "p05": round(float(np.percentile(diff, 5)), 3),
                                      "p95": round(float(np.percentile(diff, 95)), 3)},
            "fractionWithin0p25Deg": round(float(np.mean(np.abs(diff) <= 0.25)), 3),
            "fractionDisplayLower": round(float(np.mean(diff < -0.25)), 3),
            "note": "display march = nearest-cell, 5 m crop to 1.2 km then 80 m crop to 20 km; solver = full 5 m tile + 80 m to 280 km. "
                    "Where the display is lower, the controlling terrain is outside the displayed crops. Display-consistency evidence only."}


def mid_grid(tile_rel, site_xy):
    """L1 grid: 4 x 4 block means of the 5 m display surface (PGDA 78 tile, SfS-blended where available), 401 x 401 nodes at 20 m around the site (site-relative metres,
    rows south-to-north). A node whose 16 source pixels are not all finite is NaN (no fill). Deterministic: blocks are aligned
    to the tile's own pixel lattice (block b spans pixel edges left + 20 b .. left + 20 (b + 1)); node = block centre."""
    import rasterio
    path = os.path.join(ROOT, tile_rel)
    with open(path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    if digest != TILE_SHA[tile_rel]:
        raise SystemExit(f"{tile_rel}: SHA-256 {digest} differs from the documented value")
    with rasterio.open(path) as d:
        left, top, px = d.bounds.left, d.bounds.top, d.res[0]
        span = MID_BLOCK * px
        bx0 = int(round((site_xy[0] - (MID_N - 1) / 2 * span - left - span / 2) / span))
        by0 = int(round((top - (site_xy[1] + (MID_N - 1) / 2 * span) - span / 2) / span))   # northmost block row
        if bx0 < 0 or by0 < 0 or (bx0 + MID_N) * MID_BLOCK > d.width or (by0 + MID_N) * MID_BLOCK > d.height:
            raise SystemExit(f"{tile_rel}: L1 window not inside the tile")
        from rasterio.windows import Window
        a = d.read(1, window=Window(bx0 * MID_BLOCK, by0 * MID_BLOCK, MID_N * MID_BLOCK, MID_N * MID_BLOCK)).astype("f8")
    if d.nodata is not None:
        a[a == d.nodata] = np.nan
    npx = MID_N * MID_BLOCK
    PX = left + (bx0 * MID_BLOCK + np.arange(npx) + 0.5) * px
    PY = top - (by0 * MID_BLOCK + np.arange(npx) + 0.5) * px
    a, wsfs = sfs_blend(a, *np.meshgrid(PX, PY))
    blocks = a.reshape(MID_N, MID_BLOCK, MID_N, MID_BLOCK)
    mean = blocks.mean(axis=(1, 3))                     # NaN where any of the 16 pixels is NaN
    mean = mean[::-1]                                   # north-up -> rows south-to-north
    x0 = left + bx0 * span + span / 2 - site_xy[0]
    y0 = top - (by0 + MID_N) * span + span / 2 - site_xy[1]
    info = {"n": MID_N, "spacingM": span, "originX": round(x0, 3), "originY": round(y0, 3), "source": tile_rel, "sourceSha256": digest,
            "blockPixels": MID_BLOCK, "nanNodes": int(np.isnan(mean).sum()),
            "product": "NASA PGDA 78 5 m tile" + (" blended with the NASA GSFC SfS surface where it exists" if (wsfs > 0).any() else "") + ", 4 x 4 block means (20 m)",
            "sfsFraction": round(float((wsfs > 0).mean()), 4), "sfsFullWeightFraction": round(float((wsfs >= 1).mean()), 4),
            "rule": "5 m display height = (1 - w) LOLA + w SfS (w feathered over 200 m at the SfS edge); node = mean of the 4 x 4 pixels of its block; any non-finite pixel -> NaN (no fill); blocks on the tile pixel lattice"}
    return tc.Grid(mean.ravel(), MID_N, span, x0, y0), info


def build(ds_id, ds, local_dem, regional_ds, k_az):
    t0 = time.time()
    local = grid_of(local_dem)
    reg_src = regional_ds["dem"]
    # a-science exports hash the stored values, so they re-verify. The Codex source bundles hash the unrounded crop but
    # store values rounded to 0.1 mm, so their hash cannot be reproduced from the JSON: record that instead of pretending.
    verify = lambda dem: ("re-verified from stored values" if crop_hash(dem) == dem["cropValuesSha256"]  # noqa: E731
                          else "not reproducible from the bundle: values are stored rounded to 1e-4 m, the hash is of the unrounded crop")
    reg_verify, local_verify = verify(reg_src), verify(local_dem)
    site, rsite = ds["site"]["projectedMeters"], regional_ds["site"]["projectedMeters"]
    regional = tc.rebase(grid_of(reg_src), (rsite["x"], rsite["y"]), (site["x"], site["y"]))
    mid, mid_info = mid_grid(TILE_FOR[ds_id.split("_")[0]], (site["x"], site["y"]))
    near_mid = tc.Grid(np.where(np.isnan(mid.z), np.nan, mid.z).ravel(), mid.n, mid.s, mid.x0, mid.y0)
    # display surface of the 5 m crop: SfS where it exists (feathered into LOLA), same nodes as the bundle crop
    gx = site["x"] + local.x0 + np.arange(local.n) * local.s
    gy = site["y"] + local.y0 + np.arange(local.n) * local.s
    GX, GY = np.meshgrid(gx, gy)
    disp_z, disp_w = sfs_blend(local.z, GX, GY)
    has_sfs = bool((disp_w > 0).any())
    lattice = float(np.abs(((gx - (SFS["left"] + SFS["px"] / 2)) / SFS["px"]) - np.rint((gx - (SFS["left"] + SFS["px"] / 2)) / SFS["px"])).max())
    solver_local = local
    if has_sfs:
        local = tc.Grid(disp_z, local.n, local.s, local.x0, local.y0)      # horizon maps below shade the DISPLAYED surface
    lm, rm, mm = local.subsample(201), regional.subsample(201), mid.subsample(201)
    # local map: 5 m crop to 1.2 km, then L1 (20 m) out to its edge (~4 km), then the 80 m crop to 20 km
    local_h = tc.horizon_map(lm, k_az, local, near_mid, near_step=local.s, near_reach=1200.0, far_step=mid.s, far_reach=4000.0, lift_m=LOCAL_LIFT_M)
    beyond = tc.horizon_map(lm, k_az, None, regional, near_step=0, near_reach=0, far_step=regional.s, far_reach=20000.0, lift_m=LOCAL_LIFT_M)
    local_h = np.maximum(local_h, beyond)
    mid_h = np.maximum(tc.horizon_map(mm, k_az, near_mid, None, near_step=mid.s, near_reach=4000.0, far_step=0, far_reach=0, lift_m=MID_LIFT_M),
                       tc.horizon_map(mm, k_az, None, regional, near_step=0, near_reach=0, far_step=regional.s, far_reach=20000.0, lift_m=MID_LIFT_M))
    reg_h = tc.horizon_map(rm, k_az, None, regional, near_step=0, near_reach=0, far_step=regional.s, far_reach=20000.0, lift_m=REGIONAL_LIFT_M)
    d = os.path.join(OUT, ds_id)
    os.makedirs(d, exist_ok=True)
    files = {"regional_f32.bin": regional.z.astype("<f4").tobytes(), "local_horizon_u8.bin": tc.encode_deg(local_h).tobytes(),
             "regional_horizon_u8.bin": tc.encode_deg(reg_h).tobytes(), "mid_f32.bin": mid.z.astype("<f4").tobytes(),
             "mid_horizon_u8.bin": tc.encode_deg(mid_h).tobytes()}
    if has_sfs:
        files["local_display_f32.bin"] = disp_z.astype("<f4").tobytes()
        dd = (disp_z - solver_local.z)[disp_w > 0]
        display_meta = {"file": "local_display_f32.bin", "sha256": sha(files["local_display_f32.bin"]), "n": local.n, "spacingM": local.s,
                        "dtype": "float32-le", "rowOrder": "south-to-north", "product": SFS["product"], "citation": SFS["citation"], "doi": SFS["doi"],
                        "licence": SFS["licence"], "source": SFS["file"], "sourcePixelSha256": SFS["pixelSha256"],
                        "coverageFraction": round(float((disp_w > 0).mean()), 4), "fullWeightFraction": round(float((disp_w >= 1).mean()), 4),
                        "featherM": SFS["featherM"], "latticeOffsetPx": round(lattice, 4),
                        "minusSolverCropM": {"rms": round(float(np.sqrt((dd ** 2).mean())), 3), "mean": round(float(dd.mean()), 3), "maxAbs": round(float(np.abs(dd).max()), 3),
                                             "atSitePoint": round(float(tc.Grid(disp_z - solver_local.z, local.n, local.s, local.x0, local.y0).sample_nearest(np.array([0.0]), np.array([0.0]))[0][0]), 3)},
                        "rule": "display height = (1 - w) LOLA crop + w SfS, w = clip(distance inside the SfS footprint / 200 m, 0, 1); nodes are the bundle crop nodes",
                        "role": "DISPLAY surface only. The solver, margins, ray hits and every number use the LOLA crop in the bundle, not this."}
    stale = os.path.join(d, "local_display_f32.bin")
    if not has_sfs and os.path.exists(stale):
        os.replace(stale, stale + ".stale")
    for name, data in files.items():
        with open(os.path.join(d, name), "wb") as f:
            f.write(data)
    meta = {
        "schema": "polaris-terrain-context-v1", "generatedUTC": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "VISUAL", "numericalAuthority": False, "label": "TERRAIN CONTEXT · VISUAL", "releaseStatus": "SOURCE_BASED_UNVALIDATED",
        "datasetId": ds_id, "siteName": ds["site"]["name"],
        "displayReachM": round(float(min(-regional.x0, -regional.y0, regional.x0 + (regional.n - 1) * regional.s, regional.y0 + (regional.n - 1) * regional.s)), 1),
        "frame": "bundle grid axes (x toward 90 E, y toward 0 E), metres, relative to the dataset site point; rows south-to-north",
        "local": {"n": local.n, "spacingM": local.s, "originX": local.x0, "originY": local.y0, "cropValuesSha256": local_dem["cropValuesSha256"],
                  "cropHashCheck": local_verify, "storedValuesSha256": crop_hash(local_dem), "source": local_dem["source"], "note": "matches dataset.dem of the bundle; values are NOT copied here"},
        "regional": {"file": "regional_f32.bin", "sha256": sha(files["regional_f32.bin"]), "n": regional.n, "spacingM": regional.s,
                     "originX": regional.x0, "originY": regional.y0, "dtype": "float32-le", "rowOrder": "south-to-north",
                     "source": reg_src["source"], "sourceCropValuesSha256": reg_src["cropValuesSha256"], "cropHashCheck": reg_verify,
                     "storedValuesSha256": crop_hash(reg_src), "sourceBundle": "app/data/polaris-source-two-site-2026-11-14-v2.json",
                     "sourceDataset": regional_ds["siteId"], "product": "NASA PGDA 90 LDEM_80S_80MPP_ADJ (80 m)", "verticalUnits": "metres",
                     "role": "display context around the 5 m crop; the solver reads its own copy, never this file"},
        "mid": dict(mid_info, file="mid_f32.bin", sha256=sha(files["mid_f32.bin"]), dtype="float32-le", rowOrder="south-to-north",
                    role="L1 display terrain between the 5 m crop and the 80 m crop; the solver never reads it"),
        **({"localDisplay": display_meta} if has_sfs else {}),
        "horizon": {
            "encoding": {"dtype": "uint8", "degrees": "q * 0.05 - 3", "minDeg": tc.ENC_MIN_DEG, "stepDeg": tc.ENC_STEP_DEG, "maxDeg": tc.ENC_MIN_DEG + 255 * tc.ENC_STEP_DEG},
            "azimuths": k_az, "azimuthRule": "index k -> grid angle 360*k/K degrees from +y toward +x; direction (sin, cos)",
            "layout": "(K, m, m): index = (k*m + j)*m + i, j south-to-north",
            "local": {"file": "local_horizon_u8.bin", "sha256": sha(files["local_horizon_u8.bin"]), "m": lm.n, "spacingM": lm.s, "originX": lm.x0, "originY": lm.y0,
                      "march": "5 m steps to 1200 m on the 5 m crop (80 m regional where the crop ends), then 80 m steps to 20 km on the regional crop"},
            "mid": {"file": "mid_horizon_u8.bin", "sha256": sha(files["mid_horizon_u8.bin"]), "m": mm.n, "spacingM": mm.s, "originX": mm.x0, "originY": mm.y0,
                    "march": "20 m steps to 4 km on L1, max with 80 m steps to 20 km on the regional crop"},
            "regional": {"file": "regional_horizon_u8.bin", "sha256": sha(files["regional_horizon_u8.bin"]), "m": rm.n, "spacingM": rm.s, "originX": rm.x0, "originY": rm.y0,
                         "march": "80 m steps to 20 km on the regional crop"},
            "model": "surface points lifted by a display shadow bias, nearest-cell sampling, curvature d^2/2R with R = 1737400 m, finite crops",
            "shadowBiasLiftM": {"local": LOCAL_LIFT_M, "mid": MID_LIFT_M, "regional": REGIONAL_LIFT_M},
        },
        "skylineCrossCheck": skyline_check(ds, solver_local, regional),
        "limitations": [
            "Display shading only: shadows come from the displayed crops (about 16 km), not from the solver's 280 km horizon.",
            "Terrain beyond the regional crop casts nothing, so points near its edge are under-shadowed.",
            "Never an input to visible/blocked states, margins or metrics; those come from the bundle.",
            "8-bit angles (0.05 deg), K azimuths with linear interpolation, 10 m / 160 m node spacing.",
        ],
    }
    with open(os.path.join(d, "context.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    print(f"{ds_id}: L1 {mid_info['n']}x{mid_info['n']} @ {mid_info['spacingM']} m, NaN nodes {mid_info['nanNodes']}, SfS {mid_info['sfsFraction']};", end=" ")
    if has_sfs:
        print(f"SfS display crop: coverage {display_meta['coverageFraction']}, minus LOLA {display_meta['minusSolverCropM']};", end=" ")
    print(f"{ds_id}: {time.time() - t0:.0f} s; local horizon {local_h.min():.2f}..{local_h.max():.2f} deg; check {json.dumps(meta['skylineCrossCheck'])}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only"); ap.add_argument("--k", type=int, default=48)
    a = ap.parse_args()
    two = {d["siteId"]: d for d in load("app/data/polaris-source-two-site-2026-11-14-v2.json")["datasets"]}
    jobs = []
    roi = load("data/viewer/polaris-x5d-roi-2026-11-14-v2.json")
    for ds in roi["datasets"]:
        jobs.append((ds["siteId"], ds, ds["dem"], two[REGIONAL_FOR[ds["siteId"].split("_")[0]]]))
    s1 = load("app/data/polaris-source-site01-2026-11-14-v2.json")["datasets"][0]
    jobs.append(("connecting", s1, s1["localDem"], two["connecting"]))
    for ds_id, ds, local_dem, reg in jobs:
        if a.only and a.only != ds_id:
            continue
        build(ds_id, ds, local_dem, reg, a.k)


if __name__ == "__main__":
    main()
