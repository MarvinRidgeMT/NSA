"""Information Hotspots with the clones' own (correlated) height errors, via the 16-ridge linearised horizon (no ray marching).

Measure a set of cells = in each clone world, the map takes that clone's true heights inside a 3x3-pixel block around each
measured cell (and at the lander if its block is included); every other candidate keeps the nominal height. Count clone-hours
(20 clones x 12 months hourly) where the updated map's Sun state differs from the clone's own (linearised) state.
Calibration: the same counts for the strategies already tested with full ray marches (hotspots_report.json).
"""
import json, math, sys
from pathlib import Path
import numpy as np
from polaris_batch import core, ext
from build_data import interp
from sites import R

D = Path("data/external"); W = Path("work"); HZ = W / "hz"
YEAR = slice(312, 312 + 8761)
import os
_TR = os.environ.get("TRAIN", "1-20").split("-")
CL = [f"clone_{n:04d}" for n in range(int(_TR[0]), int(_TR[1]) + 1)]
NC = len(CL)


def dE_dh0(h0, h, d):
    th = np.asarray(d) / core.R_MOON; r0, r = core.R_MOON + h0, core.R_MOON + np.asarray(h)
    a = r * np.cos(th) - r0; b = r * np.sin(th)
    return np.degrees(-b / (a * a + b * b))


def run(key):
    site, lat, lon, _ = R[key]
    near = core.Dem.open(core.site_files(site, D)["surf"][1])
    z = np.load(HZ / f"{key}_nominal_m1.npz")
    e = np.load(W / f"eph_{key}.npz"); az, el = e["sun_az"][YEAR], e["sun_el"][YEAR]
    x0, y0 = near.to_grid.transform(lon, lat); c0, r0 = near.inv * (x0, y0)
    ob = (int(math.floor(r0)), int(math.floor(c0)))
    cx, cy, cn = z["cand_x"], z["cand_y"], z["cand_near"]
    col, row = near.inv * (cx, cy); pr = np.floor(row).astype(int); pc = np.floor(col).astype(int)
    hn = np.where(cn, near.sample_xy(cx, cy), 0.0); zn = float(near.sample_xy(np.array([x0]), np.array([y0]))[0])
    dh, dz = [], []
    for c in CL:
        cd = core.Dem.open(core.clone_file(site, int(c[-4:]), D)[1])
        dh.append(np.where(cn, cd.sample_xy(cx, cy) - hn, 0.0)); dz.append(float(cd.sample_xy(np.array([x0]), np.array([y0]))[0]) - zn)
    dh = np.array(dh); dz = np.array(dz)
    Jc = ext.dE_dh(z["h0"], z["cand_h"], z["cand_dist"]); J0 = dE_dh0(z["h0"], z["cand_h"], z["cand_dist"])
    base = z["cand_elev"]

    def states(mask_cand, lander):
        """mask_cand: bool (720,K) candidates whose height becomes the clone's; lander: whether ground height is the clone's."""
        out = []
        for i in range(NC):
            H = np.max(base + Jc * dh[i] * mask_cand + J0 * dz[i] * lander, axis=1)
            out.append(el > interp(H, az))
        return np.array(out)

    truth = states(np.ones_like(cn), 1.0)

    def wrong(cells, lander):
        m = np.zeros_like(cn)
        for (r_, c_) in cells:
            m |= (np.abs(pr - r_) <= 1) & (np.abs(pc - c_) <= 1) & cn
        lan = 1.0 if (lander or any(abs(r_ - ob[0]) <= 1 and abs(c_ - ob[1]) <= 1 for r_, c_ in cells)) else 0.0
        return int((states(m, lan) != truth).sum())

    hs = json.load(open(W / "hotspots_report.json"))
    calib = {}
    strat = hs.get("strategies", {}).get(key); test = hs.get("measurement_test", {}).get(key, {}).get("year")
    if strat and test:
        for tag in ("none", "observer_only", "hotspots_top10", "nearest10", "hotspots_top10+observer", "nearest10+observer"):
            cells = [tuple(c) for c in strat[tag]]
            calib[tag] = {"linearised": wrong(cells, False), "full_ray_march": test[tag]}
    # greedy plan on the clone-error model
    cand_cells = sorted({(int(a), int(b)) for a, b, n in zip(pr.ravel(), pc.ravel(), cn.ravel()) if n})
    # keep cells whose candidates are ever the controlling ridge during the year (others cannot matter to first order)
    ib = ext.nearest_bin(az); used = set()
    for b in np.unique(ib):
        for k in range(base.shape[1]):
            if cn[b, k] and base[b, k] > base[b, 0] - 2.0:
                used.add((int(pr[b, k]), int(pc[b, k])))
    pool = [c for c in cand_cells if c in used] + [ob]
    plan = [{"k": 0, "measured": "nothing", "clone_hours_wrong": wrong([], False)}]
    chosen = []
    for k in range(1, 11):
        best = None
        for c in pool:
            if c in chosen:
                continue
            v = wrong(chosen + [c], False)
            if best is None or v < best[0]:
                best = (v, c)
        chosen.append(best[1]); r_, c_ = best[1]
        xx, yy = (~near.inv) * (c_ + .5, r_ + .5)
        plan.append({"k": k, "cell_rc": [int(r_), int(c_)], "measured": "lander cell" if best[1] == ob else f"cell {round(xx - x0)},{round(yy - y0)} m",
                     "dist_m": round(math.hypot(xx - x0, yy - y0), 1), "clone_hours_wrong": best[0]})
        print(key, plan[-1], flush=True)
    toterr_top = [tuple(c) for c in strat["hotspots_top10"]] if strat else None
    overlap = len(set(chosen) & set(toterr_top + [ob])) if toterr_top else None
    rho = None
    return {"calibration": calib, "plan_clone_errors": plan, "pool_cells": len(pool),
            "overlap_with_toterr_top10_plus_lander": overlap,
            "note": "Clone-error (correlated) model via the 16-ridge linearised horizon; 'clone-hours wrong' = 20 clones x 8,761 h."}


if __name__ == "__main__":
    keys = sys.argv[1].split(",")
    FN = W / os.environ.get("OUT", "hot_corr.json")
    out = json.load(open(FN)) if FN.exists() else {}
    for k in keys:
        out[k] = run(k); print(k, out[k]["calibration"], flush=True)
        json.dump(out, open(FN, "w"), indent=1)
