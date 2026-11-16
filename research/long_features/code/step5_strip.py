"""12-month window strip + arrival-slip sweep + season comparison (PDF §4 B7, B5, A9).

For every hourly mission start from 2026-11-14 00:00 to 2027-11-14 00:00 UTC (8,761 starts), a 14-day
mission (337 hourly samples, same definition as the demo window) at a 1 m mast: Sun-centre %, Sun+Earth-centre %,
longest Sun-centre gap (h), on the nominal PGDA 78 DEM and on 20 clones. Team thresholds Sun >= 70 %,
Sun+Earth >= 40 %; "pass on k/20 clones" is not a probability.
"""
import csv, json
from pathlib import Path
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

W = Path("work"); HZ = W / "hz"; OUT = W / "strip"; OUT.mkdir(exist_ok=True)
from sites import selected, merge_dump
KEYS = list(selected())
S0, NSTART, L = 312, 8761, 337
DEMS = ["nominal"] + [f"clone_{n:04d}" for n in range(1, 21)]
THR_SUN, THR_BOTH = 70.0, 40.0


def interp_bins(elev, az):
    n = len(elev); step = 360.0 / n
    a = np.mod(np.asarray(az) - step / 2, 360.0) / step
    i0 = np.floor(a).astype(int) % n; i1 = (i0 + 1) % n; f = a - np.floor(a)
    return elev[i0] * (1 - f) + elev[i1] * f


def longest_run(blocked_win):
    run = np.zeros(blocked_win.shape[0], np.int32); best = run.copy()
    for j in range(blocked_win.shape[1]):
        run = np.where(blocked_win[:, j], run + 1, 0); best = np.maximum(best, run)
    return best


def main():
    summary = {}
    for key in KEYS:
        e = np.load(W / f"eph_{key}.npz")
        times = e["time"]
        sl = slice(S0, S0 + NSTART + L - 1)
        saz, sel, eaz, eel = e["sun_az"][sl], e["sun_el"][sl], e["earth_az"][sl], e["earth_el"][sl]
        res = {}
        for dem in DEMS:
            z = np.load(HZ / f"{key}_{dem}_m1.npz")
            sun = sel > interp_bins(z["elev"], saz)
            earth = eel > interp_bins(z["elev"], eaz)
            both = sun & earth
            ws = sliding_window_view(sun, L); wb = sliding_window_view(both, L)
            res[dem] = {"sun": 100 * ws.mean(1), "both": 100 * wb.mean(1), "gap": longest_run(~ws)}
        starts = times[S0:S0 + NSTART]
        cl = {m: np.array([res[d][m] for d in DEMS[1:]]) for m in ("sun", "both", "gap")}
        nom = res["nominal"]
        pass_sun = (cl["sun"] >= THR_SUN).sum(0); pass_both = (cl["both"] >= THR_BOTH).sum(0)
        with open(OUT / f"strip_{key}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["start_utc", "sun_nom_pct", "sun_clone_min", "sun_clone_max", "both_nom_pct", "both_clone_min",
                        "both_clone_max", "longest_sun_gap_nom_h", "longest_sun_gap_clone_max_h", "pass_sun70_k_of_20", "pass_both40_k_of_20"])
            for i in range(NSTART):
                w.writerow([starts[i], round(nom["sun"][i], 2), round(cl["sun"][:, i].min(), 2), round(cl["sun"][:, i].max(), 2),
                            round(nom["both"][i], 2), round(cl["both"][:, i].min(), 2), round(cl["both"][:, i].max(), 2),
                            int(nom["gap"][i]), int(cl["gap"][:, i].max()), int(pass_sun[i]), int(pass_both[i])])
        # arrival slip relative to the demo start (index 0 = 2026-11-14 00:00)
        slips = {}
        for h in (-12, 12, 24, 48, 72, 7 * 24, 14 * 24, 30 * 24, 91 * 24, 182 * 24, 365 * 24):
            if 0 <= h < NSTART:
                slips[f"{h:+d}h"] = {"start": str(starts[h]), "sun_nom": round(nom["sun"][h], 2),
                                     "sun_clones": [round(cl["sun"][:, h].min(), 2), round(cl["sun"][:, h].max(), 2)],
                                     "both_nom": round(nom["both"][h], 2), "gap_nom_h": int(nom["gap"][h]),
                                     "gap_clone_max_h": int(cl["gap"][:, h].max())}
        # sensitivity of the demo start: largest change within +-1, +-3, +-7 days (starts before 11-14 use the ephemeris back to 11-01)
        months = {}
        for i, s in enumerate(starts):
            mk = s[:8]
            months.setdefault(mk, []).append(i)
        season = {}
        for mk, idx in months.items():
            idx = np.array(idx)
            season[mk] = {"n_starts": len(idx),
                          "sun_nom_mean": round(float(nom["sun"][idx].mean()), 1), "sun_nom_min": round(float(nom["sun"][idx].min()), 1),
                          "sun_nom_max": round(float(nom["sun"][idx].max()), 1),
                          "sun_clone_min": round(float(cl["sun"][:, idx].min()), 1),
                          "both_nom_mean": round(float(nom["both"][idx].mean()), 1),
                          "gap_nom_max_h": int(nom["gap"][idx].max()), "gap_clone_max_h": int(cl["gap"][:, idx].max()),
                          "starts_all20_pass_sun70_pct": round(100 * float((pass_sun[idx] == 20).mean()), 1),
                          "starts_all20_pass_both40_pct": round(100 * float((pass_both[idx] == 20).mean()), 1)}
        best = int(np.argmax(cl["sun"].min(0))); worst = int(np.argmin(cl["sun"].min(0)))
        summary[key] = {
            "n_starts": NSTART, "first_start": str(starts[0]), "last_start": str(starts[-1]),
            "year_hourly_sun_nom_pct": None,
            "starts_pass_sun70_all20_pct": round(100 * float((pass_sun == 20).mean()), 1),
            "starts_pass_sun70_none_pct": round(100 * float((pass_sun == 0).mean()), 1),
            "starts_marginal_sun70_pct": round(100 * float(((pass_sun > 0) & (pass_sun < 20)).mean()), 1),
            "starts_pass_both40_all20_pct": round(100 * float((pass_both == 20).mean()), 1),
            "starts_marginal_both40_pct": round(100 * float(((pass_both > 0) & (pass_both < 20)).mean()), 1),
            "best_start_by_worst_clone": {"start": str(starts[best]), "sun_clone_min": round(float(cl["sun"][:, best].min()), 2), "sun_nom": round(float(nom["sun"][best]), 2)},
            "worst_start_by_worst_clone": {"start": str(starts[worst]), "sun_clone_min": round(float(cl["sun"][:, worst].min()), 2), "sun_nom": round(float(nom["sun"][worst]), 2)},
            "max_longest_gap_nom_h": int(nom["gap"].max()), "max_longest_gap_clone_h": int(cl["gap"].max()),
            "starts_gap_le_120h_all20_pct": round(100 * float((cl["gap"].max(0) <= 120).mean()), 1),
            "slip": slips, "season": season}
        sun_all = sel > interp_bins(np.load(HZ / f"{key}_nominal_m1.npz")["elev"], saz)
        summary[key]["year_hourly_sun_nom_pct"] = round(100 * float(sun_all[:NSTART].mean()), 2)
        np.savez(OUT / f"strip_{key}.npz", starts=starts, **{f"nom_{m}": nom[m] for m in nom}, **{f"cl_{m}": cl[m] for m in cl},
                 pass_sun=pass_sun, pass_both=pass_both)
        print(key, json.dumps({k: v for k, v in summary[key].items() if k not in ("season",)}, indent=1))
        for mk, v in season.items():
            print("  ", mk, v)
    merge_dump(OUT / "strip_summary.json", summary, indent=1)


if __name__ == "__main__":
    main()
