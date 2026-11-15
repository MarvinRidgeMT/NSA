"""Two-lander complementarity, landing-ellipse dispersion, measurement planner (pilots). Nominal PGDA 78 maps, 1 m mast."""
import json, math
from pathlib import Path
import numpy as np
from polaris_batch import core, ext
from build_data import transfer_azel, interp, longest

D = Path("data/external"); W = Path("work"); J = W / "jobs"
R = {"Site04_ROI3": ("Site04", -89.78012, -156.32023), "Site01_ROI6": ("Site01", -89.47409, -137.3813)}
DEMO = slice(312, 312 + 337); YEAR = slice(312, 312 + 8761)
out = {}
for key, (site, lat, lon) in R.items():
    e = np.load(W / f"eph_{key}.npz")
    near = core.Dem.open(core.site_files(site, D)["surf"][1])
    x0, y0 = near.to_grid.transform(lon, lat)
    pts = []
    for dx in range(-100, 101, 25):
        for dy in range(-100, 101, 25):
            f = W / f"hz/{key}_nominal_m1.npz" if dx == 0 and dy == 0 else J / f"pos_{key}_nominal_x{dx}_y{dy}.npz"
            lo, la = near.to_grid.transform(x0 + dx, y0 + dy, direction="INVERSE")
            sa, se = transfer_azel(e["sun_az"], e["sun_el"], lon, lat, float(lo), float(la))
            ea, ee = transfer_azel(e["earth_az"], e["earth_el"], lon, lat, float(lo), float(la))
            el = np.load(f)["elev"]
            sun = se > interp(el, sa); earth = ee > interp(el, ea)
            pts.append({"dx": dx, "dy": dy, "sun": sun, "both": sun & earth})
    n = len(pts)
    # ---------------- A. two-lander complementarity (12 months, hourly)
    S = np.array([p["sun"][YEAR] for p in pts]); B = np.array([p["both"][YEAR] for p in pts])
    single = S.mean(1)
    best_single = int(np.argmax(single))
    res = []
    for i in range(n):
        for j in range(i + 1, n):
            sep = math.hypot(pts[i]["dx"] - pts[j]["dx"], pts[i]["dy"] - pts[j]["dy"])
            either = S[i] | S[j]
            res.append((float(either.mean()), int(longest((~either)[None, :])[0]), float((B[i] | B[j]).mean()), i, j, sep))
    res.sort(key=lambda r: (-r[0], r[1]))
    def pr(r):
        i, j = r[3], r[4]
        return {"a": [pts[i]["dx"], pts[i]["dy"]], "b": [pts[j]["dx"], pts[j]["dy"]], "sep_m": round(r[5], 1),
                "sun_either_pct": round(100 * r[0], 2), "longest_both_dark_h": r[1], "sun_earth_either_pct": round(100 * r[2], 2)}
    bs = S[best_single]
    comp = {"best_single": {"at": [pts[best_single]["dx"], pts[best_single]["dy"]], "sun_pct": round(100 * float(single[best_single]), 2),
                            "longest_dark_h": int(longest((~bs)[None, :])[0])},
            "centre_single": {"sun_pct": round(100 * float(single[40]), 2), "longest_dark_h": int(longest((~S[40])[None, :])[0])},
            "best_pairs": [pr(r) for r in res[:5]],
            "best_pair_with_centre": pr(next(r for r in res if 40 in (r[3], r[4]))),
            "best_pair_sep_ge_100m": pr(next(r for r in res if r[5] >= 100))}
    # ---------------- B. landing ellipse (isotropic Gaussian scatter about the RoI centroid; grid-weighted)
    thr = lambda p: (p["sun"][DEMO].mean() >= .70) and (p["both"][DEMO].mean() >= .40) and (longest((~p["sun"][DEMO])[None, :])[0] <= 120)
    ok = np.array([thr(p) for p in pts]); sun_d = np.array([p["sun"][DEMO].mean() for p in pts])
    sun_y = np.array([p["sun"][YEAR].mean() for p in pts])
    ell = {}
    for sig in (10, 25, 50, 100):
        w = np.array([math.exp(-(p["dx"] ** 2 + p["dy"] ** 2) / (2 * sig ** 2)) for p in pts]); w /= w.sum()
        ell[f"sigma_{sig}m"] = {"share_passing_all3_pct": round(100 * float((w * ok).sum()), 1),
                                "expected_sun_demo_pct": round(100 * float((w * sun_d).sum()), 2),
                                "expected_sun_12mo_pct": round(100 * float((w * sun_y).sum()), 2),
                                "worst_point_within_2sigma_sun_demo_pct": round(100 * float(min(sun_d[i] for i, p in enumerate(pts) if math.hypot(p["dx"], p["dy"]) <= 2 * sig)), 2)}
    # ---------------- C. measurement planner (greedy, toterr model as in Information Hotspots; 12 months)
    err = core.Dem.open(core.site_files(site, D)["toterr"][1])
    z = np.load(W / f"hz/{key}_nominal_m1.npz")
    J1 = ext.dE_dh(z["h0"], z["hgt"], z["dist"])
    th = z["dist"] / core.R_MOON; r0_, r_ = core.R_MOON + z["h0"], core.R_MOON + z["hgt"]
    a_ = r_ * np.cos(th) - r0_; b_ = r_ * np.sin(th); J0 = np.degrees(-b_ / (a_ * a_ + b_ * b_))
    s1 = np.where(z["in_near"], err.sample_xy(z["x"], z["y"]), 0.0); s0 = float(err.sample_xy(np.array([x0]), np.array([y0]))[0])
    col, row = near.inv * (z["x"], z["y"])
    cell = np.array([(int(round(r - .5)) * 10000 + int(round(c - .5))) if nn else -1 for r, c, nn in zip(row, col, z["in_near"])])
    az, el = e["sun_az"][YEAR], e["sun_el"][YEAR]; ib = ext.nearest_bin(az); m = np.abs(el - interp(z["elev"], az))
    sig_c = s1[ib].copy(); sig_o = s0; SIG_NEW = 0.05
    def expected(sc, so):
        s = np.sqrt((J1[ib] * sc) ** 2 + (J0[ib] * so) ** 2)
        return float(ext.norm_sf(m / np.maximum(s, 1e-12)).sum())
    plan = [{"k": 0, "measured": "nothing", "expected_flip_h": round(expected(sig_c, sig_o), 1)}]
    measured = set(); cand = set(cell[ib][cell[ib] >= 0].tolist()) | {"lander"}
    for k in range(1, 16):
        best = None
        for c in cand - measured:
            sc = sig_c if c == "lander" else np.where(cell[ib] == c, SIG_NEW, sig_c)
            so = SIG_NEW if c == "lander" else sig_o
            v = expected(sc, so)
            if best is None or v < best[0]:
                best = (v, c, sc, so)
        v, c, sig_c, sig_o = best; measured.add(c)
        if c == "lander":
            lab, dist = "lander cell", 0.0
        else:
            rr, cc = divmod(c, 10000); xx, yy = (~near.inv) * (cc + .5, rr + .5); lab = f"cell {round(xx - x0)},{round(yy - y0)} m"; dist = math.hypot(xx - x0, yy - y0)
        plan.append({"k": k, "measured": lab, "dist_m": round(dist, 1), "expected_flip_h": round(v, 1)})
    hs = json.load(open(W / "hotspots_report.json"))["measurement_test"][key]["year"]
    out[key] = {"complementarity": comp, "ellipse": ell, "planner": plan,
                "planner_check": {"tested_nothing": hs["none"], "tested_lander_only": hs["observer_only"], "tested_top10_plus_lander": hs["hotspots_top10+observer"],
                                  "note": "Tested = clone-hours still wrong after a full ray march (20 clones, 12 months); expected = toterr model flip-hours (not the same unit)."}}
    print(key, json.dumps({k: v for k, v in out[key].items() if k != "planner"}, indent=0)[:2500])
    for p in plan: print("   ", p)
json.dump(out, open(W / "more.json", "w"), indent=1)
