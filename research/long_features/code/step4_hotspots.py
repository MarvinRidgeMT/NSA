"""Information Hotspots pilot (PDF §5 #2): where would better elevation data most change the decision?

Score per 5 m DEM cell = expected number of Sun-state flip-hours (over the window) that would be removed if
that cell's height were known to 0.05 m instead of NASA's PGDA 78 'toterr' sigma. Uses the linearised
horizon from step 3 (controlling point + observer), no clones.

Test that can fail: in each of the 20 clone worlds, "measure" a set of 10 cells perfectly (copy the clone's
heights into the nominal map in a 3x3-pixel block) and re-run the FULL ray march. Count clone-hours where the
updated map still disagrees with that clone. Compare: top-10 hotspot cells vs 10 random controlling cells (3
draws) vs the 10 controlling cells nearest the lander vs nothing measured.
"""
import json, math, dataclasses
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
from polaris_batch import core, ext

D = Path("data/external"); W = Path("work"); HZ = W / "hz"
from sites import selected, merge_dump
import os
R = selected()
NOTEST = os.environ.get("NOTEST") == "1"
WIN = {"nov14d": (312, 312 + 337), "year": (312, 312 + 8761)}
SIGMA_NEW = 0.05
K = 10
BLOCK = 1  # half-width in pixels -> 3x3 block (15 m x 15 m)


def interp_bins(elev, az):
    n = len(elev); step = 360.0 / n
    a = np.mod(np.asarray(az) - step / 2, 360.0) / step
    i0 = np.floor(a).astype(int) % n; i1 = (i0 + 1) % n; f = a - np.floor(a)
    return elev[i0] * (1 - f) + elev[i1] * f


def dE_dh0(h0, h, d):
    th = np.asarray(d) / core.R_MOON
    r0, r = core.R_MOON + h0, core.R_MOON + np.asarray(h)
    a = r * np.cos(th) - r0; b = r * np.sin(th)
    return np.degrees(-b / (a * a + b * b))


def scores(key):
    site, lat, lon = R[key]
    near = core.Dem.open(core.site_files(site, D)["surf"][1])
    err = core.Dem.open(core.site_files(site, D)["toterr"][1])
    z = np.load(HZ / f"{key}_nominal_m1.npz")
    e = np.load(W / f"eph_{key}.npz")
    x0, y0 = near.to_grid.transform(np.array([lon]), np.array([lat]))
    c0, r0 = near.inv * (x0[0], y0[0]); obs_cell = (int(math.floor(r0 - 0.5 + 0.5)), int(math.floor(c0 - 0.5 + 0.5)))
    J1 = ext.dE_dh(z["h0"], z["hgt"], z["dist"]); J0 = dE_dh0(z["h0"], z["hgt"], z["dist"])
    s1 = np.where(z["in_near"], err.sample_xy(z["x"], z["y"]), 0.0)
    s0 = float(err.sample_xy(x0, y0)[0])
    col, row = near.inv * (z["x"], z["y"])
    cells = [(int(round(r - 0.5)), int(round(c - 0.5))) if n else None for r, c, n in zip(row, col, z["in_near"])]
    out = {}
    for wname, (a, b) in WIN.items():
        az = e["sun_az"][a:b]; el = e["sun_el"][a:b]
        m = el - interp_bins(z["elev"], az)
        ib = ext.nearest_bin(az)
        sig = np.sqrt((J1[ib] * s1[ib]) ** 2 + (J0[ib] * s0) ** 2)
        P = ext.norm_sf(np.abs(m) / np.maximum(sig, 1e-12))
        sig_ctrl = np.sqrt((J1[ib] * SIGMA_NEW) ** 2 + (J0[ib] * s0) ** 2)
        sig_obs = np.sqrt((J1[ib] * s1[ib]) ** 2 + (J0[ib] * SIGMA_NEW) ** 2)
        gain_ctrl = P - ext.norm_sf(np.abs(m) / np.maximum(sig_ctrl, 1e-12))
        gain_obs = P - ext.norm_sf(np.abs(m) / np.maximum(sig_obs, 1e-12))
        score = {}
        for t in range(len(m)):
            c = cells[ib[t]]
            if c is not None:
                score[c] = score.get(c, 0.0) + gain_ctrl[t]
        score_obs = float(gain_obs.sum())
        ranked = sorted(score.items(), key=lambda kv: -kv[1])
        rows = []
        for (r_, c_), v in ranked[:25]:
            x, y = near.inv.__invert__() * (c_ + 0.5, r_ + 0.5)
            dx, dy = x - x0[0], y - y0[0]
            rows.append({"row": r_, "col": c_, "x_m": round(x, 1), "y_m": round(y, 1),
                         "dist_from_lander_m": round(math.hypot(dx, dy), 1),
                         "toterr_m": round(float(err.z[r_, c_]), 3),
                         "expected_flip_hours_removed": round(v, 2)})
        out[wname] = {"expected_flip_hours_total": round(float(P.sum()), 2),
                      "observer_cell": {"row": obs_cell[0], "col": obs_cell[1], "toterr_m": round(s0, 3),
                                        "expected_flip_hours_removed": round(score_obs, 2)},
                      "n_cells_with_score": len(score), "top": rows,
                      "share_top10_pct": round(100 * sum(v for _, v in ranked[:10]) / max(sum(score.values()), 1e-9), 1),
                      "all_cells": [(rc[0], rc[1], v) for rc, v in ranked]}
    return out, obs_cell


from functools import lru_cache


@lru_cache(4)
def _dem(p):
    return core.Dem.open(Path(p))


def _march(args):
    key, clone_n, block_cells, tag = args
    site, lat, lon = R[key]
    near = _dem(str(core.site_files(site, D)["surf"][1]))
    cd = core.Dem.open(core.clone_file(site, clone_n, D)[1])
    far = _dem(str(D / "pgda90/LDEM_80S_80MPP_ADJ.TIF"))
    zz = near.z.copy()
    for (r_, c_) in block_cells:
        zz[r_ - BLOCK:r_ + BLOCK + 1, c_ - BLOCK:c_ + BLOCK + 1] = cd.z[r_ - BLOCK:r_ + BLOCK + 1, c_ - BLOCK:c_ + BLOCK + 1]
    upd = dataclasses.replace(near, z=zz)
    nom = np.load(HZ / f"{key}_nominal_m1.npz")
    x0, y0 = near.to_grid.transform(np.array([lon]), np.array([lat]))
    c0, r0 = near.inv * (x0[0], y0[0]); obs = (int(math.floor(r0)), int(math.floor(c0)))
    z0 = float(upd.sample_xy(x0, y0)[0]); h0 = z0 + 1.0
    obs_changed = z0 != float(near.sample_xy(x0, y0)[0])
    az_all = nom["az"]
    if obs_changed:
        bins = np.arange(len(az_all))
    else:
        # only rays that pass within the modified blocks (plus one pixel of bilinear reach) can change
        fwd = ~near.inv; sel = np.zeros(len(az_all), bool)
        for r_, c_ in block_cells:
            x, y = fwd * (c_ + 0.5, r_ + 0.5)
            # local azimuth (clockwise from north) of the cell, via great-circle bearing in lon/lat
            lonc, latc = near.to_grid.transform(x, y, direction="INVERSE")
            p1, p2, dl = math.radians(lat), math.radians(latc), math.radians(lonc - lon)
            brg = math.degrees(math.atan2(math.sin(dl) * math.cos(p2), math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl))) % 360
            dist = math.hypot(x - x0[0], y - y0[0]); half = math.degrees(math.atan2((BLOCK + 1.5) * near.res * 1.42, max(dist, 1.0))) + 0.5
            dd = np.abs((az_all - brg + 180) % 360 - 180); sel |= dd <= half
        bins = np.where(sel)[0]
    elev = nom["elev"].copy()
    if len(bins):
        d = np.concatenate([np.arange(1.0, 25000.0, 1.0), np.arange(25000.0, 280001.0, far.res)])
        for s in range(0, len(bins), 40):
            bb = bins[s:s + 40]
            lo, la = core.destination(lon, lat, az_all[bb], d)
            x, y = upd.to_grid.transform(lo, la)
            hn = upd.sample_xy(x, y); h = np.where(np.isfinite(hn), hn, far.sample_xy(x, y))
            e = core.elevation_angle_deg(h0, h, d[None, :])
            elev[bb] = np.nanmax(np.where(np.isfinite(e), e, -np.inf), axis=1)
    return key, clone_n, tag, elev


def main():
    rep = {}; strategies = {}
    for key in R:
        sc, obs = scores(key)
        rep[key] = {w: {k: v for k, v in s.items() if k != "all_cells"} for w, s in sc.items()}
        print(key, json.dumps({w: {k: v for k, v in s.items() if k not in ("all_cells", "top")} for w, s in sc.items()}))
        for r in sc["year"]["top"][:10]:
            print("  ", r)
        cells_all = [(r, c) for r, c, v in sc["year"]["all_cells"] if v > 1e-6]
        top = [(r, c) for r, c, _ in sc["year"]["all_cells"][:K]]
        rng = np.random.default_rng(42)
        rand = [[cells_all[i] for i in rng.choice(len(cells_all), K, replace=False)] for _ in range(3)]
        # nearest-to-lander heuristic among controlling cells
        near_sorted = sorted(cells_all, key=lambda rc: (rc[0] - obs[0]) ** 2 + (rc[1] - obs[1]) ** 2)
        nearest = near_sorted[:K]
        strategies[key] = {"none": [], "hotspots_top10": top, "random_a": rand[0], "random_b": rand[1], "random_c": rand[2],
                           "nearest10": nearest, "observer_only": [obs], "hotspots_top10+observer": top + [obs],
                           "random_a+observer": rand[0] + [obs], "random_b+observer": rand[1] + [obs], "random_c+observer": rand[2] + [obs],
                           "nearest10+observer": nearest + [obs]}
    jobs = [] if NOTEST else [(k, n, cells, tag) for k, st in strategies.items() for tag, cells in st.items() for n in range(1, 21)]
    print(f"{len(jobs)} full ray marches", flush=True)
    res = {}
    with ProcessPoolExecutor(2) as ex:
        for i, (k, n, tag, elev) in enumerate(ex.map(_march, jobs), 1):
            res[(k, n, tag)] = elev
            if i % 20 == 0:
                print(i, flush=True)
    test = {}
    for key in ([] if NOTEST else R):
        e = np.load(W / f"eph_{key}.npz")
        test[key] = {}
        for wname, (a, b) in WIN.items():
            az = e["sun_az"][a:b]; el = e["sun_el"][a:b]
            truth = np.array([el > interp_bins(np.load(HZ / f"{key}_clone_{n:04d}_m1.npz")["elev"], az) for n in range(1, 21)])
            row = {}
            for tag in strategies[key]:
                est = np.array([el > interp_bins(res[(key, n, tag)], az) for n in range(1, 21)])
                row[tag] = int((est != truth).sum())
            test[key][wname] = row
        print(key, test[key])
    rep["measurement_test"] = test
    rep["strategies"] = {k: {t: [list(map(int, c)) for c in v] for t, v in s.items()} for k, s in strategies.items()}
    rep["notes"] = {"sigma_new_m": SIGMA_NEW, "block_px": 2 * BLOCK + 1, "K": K,
                    "metric": "clone-hours (20 clones x hourly samples) where the updated map's Sun-centre state differs from that clone's"}
    merge_dump(W / "hotspots_report.json", rep, indent=1, default=float)


if __name__ == "__main__":
    main()
