"""Surrogate screener (sheet row 38). SURROGATE = a deliberately coarse horizon model used only to rank candidate cells;
every number shown as a result is re-checked with the full solver.

Screen: every 25 m cell within +-500 m of the RoI centre (41 x 41 = 1,681 cells), nominal PGDA 78 map, 1 m mast,
horizon with 180 azimuth bins, near-field step 5 m to 3 km, 80 m map beyond; Sun-centre % over 12 months (2-hourly).
Re-check: the surrogate's top 20 cells + 20 random cells with the full solver (720 bins, 1 m step to 25 km, 80 m to 280 km, hourly).
"""
import json, math, sys, time
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr
from polaris_batch import core
from build_data import transfer_azel, interp
from sites import R

D = Path("data/external"); W = Path("work")
YEAR = slice(312, 312 + 8761)


@lru_cache(2)
def dem(p):
    return core.Dem.open(Path(p))


def cell_job(a):
    key, i, dx, dy, mode = a
    site, lat, lon, _ = R[key]
    near = dem(str(core.site_files(site, D)["surf"][1])); far = dem(str(D / "pgda90/LDEM_80S_80MPP_ADJ.TIF"))
    x0, y0 = near.to_grid.transform(lon, lat)
    lo, la = near.to_grid.transform(x0 + dx, y0 + dy, direction="INVERSE"); lo, la = float(lo), float(la)
    if mode == "surrogate":
        hz = core.compute_horizon(lo, la, near, far, 1.0, n_az=180, near_step=5.0, near_max_m=3000.0, az_chunk=180)
        step = 2
    else:
        hz = core.compute_horizon(lo, la, near, far, 1.0, n_az=720, near_step=1.0)
        step = 1
    e = np.load(W / f"eph_{key}.npz")
    az, el = transfer_azel(e["sun_az"][YEAR][::step], e["sun_el"][YEAR][::step], lon, lat, lo, la)
    return key, i, dx, dy, mode, round(100 * float((el > interp(hz.elev, az)).mean()), 2)


def main(keys):
    out = json.load(open(W / "surrogate.json")) if (W / "surrogate.json").exists() else {}
    for key in keys:
        t0 = time.time()
        cells = [(dx, dy) for dx in range(-500, 501, 25) for dy in range(-500, 501, 25)]
        with ProcessPoolExecutor(2) as ex:
            sur = list(ex.map(cell_job, [(key, i, dx, dy, "surrogate") for i, (dx, dy) in enumerate(cells)], chunksize=16))
        sv = np.array([r[5] for r in sur]); ts = time.time() - t0
        order = np.argsort(-sv, kind="stable"); top = order[:20].tolist()
        rng = np.random.default_rng(7); rnd = rng.choice([i for i in range(len(cells)) if i not in top], 20, replace=False).tolist()
        t1 = time.time()
        with ProcessPoolExecutor(2) as ex:
            full = {r[1]: r[5] for r in ex.map(cell_job, [(key, i, cells[i][0], cells[i][1], "full") for i in top + rnd])}
        tf = time.time() - t1
        rs = [full[i] for i in rnd]; ss = [sv[i] for i in rnd]
        ft = [full[i] for i in top]
        best_full_checked = max(full.items(), key=lambda kv: kv[1])
        centre = cells.index((0, 0))
        out[key] = {
            "label": "SURROGATE screen + full-solver re-check",
            "grid": {"half_width_m": 500, "step_m": 25, "n": len(cells)},
            "surrogate_sun_12mo": [round(v, 1) for v in sv.tolist()],
            "cells": cells,
            "top20": [{"dx": cells[i][0], "dy": cells[i][1], "surrogate": float(sv[i]), "full": full[i]} for i in top],
            "random20": [{"dx": cells[i][0], "dy": cells[i][1], "surrogate": float(sv[i]), "full": full[i]} for i in rnd],
            "random_spearman": round(float(spearmanr(ss, rs).correlation), 3),
            "random_mae_pts": round(float(np.mean(np.abs(np.array(ss) - np.array(rs)))), 2),
            "random_bias_pts": round(float(np.mean(np.array(ss) - np.array(rs))), 2),
            "top20_full_min": min(ft), "top20_full_median": float(np.median(ft)), "random_full_median": float(np.median(rs)),
            "top20_beat_random_median": int(sum(v > np.median(rs) for v in ft)),
            "best_checked": {"dx": cells[best_full_checked[0]][0], "dy": cells[best_full_checked[0]][1], "full": best_full_checked[1]},
            "centre_surrogate": float(sv[centre]),
            "seconds": {"surrogate_total": round(ts, 1), "surrogate_per_cell": round(ts / len(cells), 3), "full_per_cell": round(tf / 40, 2)},
        }
        o = out[key]
        print(key, {k: v for k, v in o.items() if k not in ("surrogate_sun_12mo", "cells", "top20", "random20")}, flush=True)
        json.dump(out, open(W / "surrogate.json", "w"))


if __name__ == "__main__":
    main(sys.argv[1].split(",") if len(sys.argv) > 1 else list(R))
