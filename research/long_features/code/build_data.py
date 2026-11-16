"""Assemble every result into one JSON for the viewer page (work/viewer_data.json)."""
import base64, hashlib, json, math
from pathlib import Path
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from polaris_batch import core

D = Path("data/external"); W = Path("work"); J = W / "jobs"
from sites import R as _RALL
R = dict(_RALL)
_UNUSED = {"Site04_ROI3": ("Site04", -89.78012, -156.32023, "Shackleton rim, Site04 RoI 3"),
     "Site01_ROI6": ("Site01", -89.47409, -137.3813, "Connecting Ridge, Site01 RoI 6")}
L = 337
CLONES = [f"clone_{n:04d}" for n in range(1, 21)]


def interp(elev, az):
    n = len(elev); st = 360.0 / n
    a = np.mod(np.asarray(az) - st / 2, 360.0) / st
    i0 = np.floor(a).astype(int) % n; i1 = (i0 + 1) % n; f = a - np.floor(a)
    return elev[i0] * (1 - f) + elev[i1] * f


def longest(blk):
    run = np.zeros(blk.shape[:-1], np.int32); best = run.copy()
    for j in range(blk.shape[-1]):
        run = np.where(blk[..., j], run + 1, 0); best = np.maximum(best, run)
    return best


def b64(a, dt):
    return base64.b64encode(np.ascontiguousarray(a).astype(dt).tobytes()).decode()


def _enu(lon, lat):
    lam, phi = math.radians(lon), math.radians(lat)
    e = np.array([-math.sin(lam), math.cos(lam), 0.0])
    n = np.array([-math.sin(phi) * math.cos(lam), -math.sin(phi) * math.sin(lam), math.cos(phi)])
    u = np.array([math.cos(phi) * math.cos(lam), math.cos(phi) * math.sin(lam), math.sin(phi)])
    return e, n, u


def transfer_azel(az, el, lon_a, lat_a, lon_b, lat_b):
    """polaris_batch v2 core.transfer_azel (direction of a distant body re-expressed at a nearby site)."""
    ea, na, ua = _enu(lon_a, lat_a); eb, nb, ub = _enu(lon_b, lat_b)
    az, el = np.radians(az), np.radians(el)
    d = (np.cos(el) * np.sin(az))[:, None] * ea + (np.cos(el) * np.cos(az))[:, None] * na + np.sin(el)[:, None] * ua
    return np.degrees(np.arctan2(d @ eb, d @ nb)) % 360.0, np.degrees(np.arcsin(np.clip(d @ ub, -1, 1)))


def states(elev, e, sl):
    sun = e["sun_el"][sl] > interp(elev, e["sun_az"][sl])
    earth = e["earth_el"][sl] > interp(elev, e["earth_az"][sl])
    return sun, sun & earth


def win_metrics(sun, both, a, b):
    """windows of L samples starting at a..b-1 (indices into sun/both)."""
    ws = sliding_window_view(sun, L)[a:b]; wb = sliding_window_view(both, L)[a:b]
    return 100 * ws.mean(-1), 100 * wb.mean(-1), longest(~ws)


def sha(p):
    return core.sha256(Path(p))[:16]


def main():
    out = {"sites": {}, "generated": "2026-11-15 EST, Claude cloud session (long-feature pilots)"}
    for key, (site, lat, lon, name) in R.items():
        e = np.load(W / f"eph_{key}.npz"); t = e["time"]
        s = {"name": name, "lat": lat, "lon": lon, "z0": float(np.load(W / f"hz/{key}_nominal_m1.npz")["z0"])}
        # ---- strip (starts 2026-11-14 00:00 .. 2027-11-14 00:00) from step5
        z = np.load(W / f"strip/strip_{key}.npz")
        n = len(z["starts"])
        s["strip"] = {"t0": str(z["starts"][0]), "n": n,
                      "nom_sun": np.round(z["nom_sun"], 1).tolist(), "nom_both": np.round(z["nom_both"], 1).tolist(),
                      "nom_gap": z["nom_gap"].astype(int).tolist(),
                      "cl_sun": b64(np.round(z["cl_sun"] * 100), np.uint16), "cl_both": b64(np.round(z["cl_both"] * 100), np.uint16),
                      "cl_gap": b64(z["cl_gap"], np.uint16)}
        # ---- demo window + slip (starts 2026-11-07 .. 11-21), per clone
        i0 = 312 - 168; ns = 337
        sl = slice(i0, i0 + ns + L - 1)
        dems = ["nominal"] + CLONES
        res = {}
        for d in dems:
            sun, both = states(np.load(W / f"hz/{key}_{d}_m1.npz")["elev"], e, sl)
            res[d] = win_metrics(sun, both, 0, ns)
        s["slip"] = {"h0": -168, "t0": str(t[i0]),
                     "nom": [np.round(res["nominal"][k], 2).tolist() if k < 2 else res["nominal"][k].astype(int).tolist() for k in range(3)],
                     "cl": [[np.round(res[d][k], 2).tolist() if k < 2 else res[d][k].astype(int).tolist() for d in CLONES] for k in range(3)]}
        j = 168
        s["demo"] = {"start": str(t[312]), "end": str(t[312 + 336]),
                     "nom": {"sun": round(float(res["nominal"][0][j]), 2), "both": round(float(res["nominal"][1][j]), 2), "gap": int(res["nominal"][2][j])},
                     "cl": {"sun": [round(float(res[d][0][j]), 2) for d in CLONES], "both": [round(float(res[d][1][j]), 2) for d in CLONES],
                            "gap": [int(res[d][2][j]) for d in CLONES]}}
        # ---- masts (demo window + 12 months, Sun and Sun+Earth), nominal + clones
        masts = [1.0, 1.25, 1.5, 1.75, 2.0, 3.0, 5.0, 10.0]
        mrec = {"masts": masts, "demo_sun": [], "demo_both": [], "year_sun": [], "year_gapmax": []}
        sy = slice(312, 312 + 8761 + L - 1)
        ok = True
        for m in masts:
            row_d, row_b, row_y, row_g = [], [], [], []
            for d in dems:
                f = W / f"hz/{key}_{d}_m1.npz" if m == 1.0 else J / f"mast_{key}_{d}_m{m:g}.npz"
                if not f.exists():
                    ok = False; break
                el = np.load(f)["elev"]
                sun, both = states(el, e, slice(312, 312 + L))
                row_d.append(round(100 * float(sun.mean()), 2)); row_b.append(round(100 * float(both.mean()), 2))
                suny, _ = states(el, e, slice(312, 312 + 8761))
                row_y.append(round(100 * float(suny.mean()), 2))
                sunw, _ = states(el, e, sy)
                row_g.append(int(longest(~sliding_window_view(sunw, L)).max()))
            if not ok:
                break
            mrec["demo_sun"].append(row_d); mrec["demo_both"].append(row_b); mrec["year_sun"].append(row_y); mrec["year_gapmax"].append(row_g)
        if ok:
            s["masts"] = mrec
        # ---- position grid (1 m mast), demo window + 12 months
        near = core.Dem.open(core.site_files(site, D)["surf"][1])
        x0, y0 = near.to_grid.transform(lon, lat)
        cells = []
        for dx in range(-100, 101, 25):
            for dy in range(-100, 101, 25):
                f = J / f"pos_{key}_nominal_x{dx}_y{dy}.npz"
                if dx == 0 and dy == 0:
                    f = W / f"hz/{key}_nominal_m1.npz"
                if not f.exists():
                    continue
                lo, la = near.to_grid.transform(x0 + dx, y0 + dy, direction="INVERSE")
                ee = {}
                for b in ("sun", "earth"):
                    ee[f"{b}_az"], ee[f"{b}_el"] = transfer_azel(e[f"{b}_az"], e[f"{b}_el"], lon, lat, float(lo), float(la))
                rec = {"dx": dx, "dy": dy}
                def m_for(elev):
                    sd, bd = states(elev, ee, slice(312, 312 + L)); sy_, by_ = states(elev, ee, slice(312, 312 + 8761))
                    return 100 * sd.mean(), 100 * bd.mean(), 100 * sy_.mean(), int(longest(~sd[None, :])[0])
                a = m_for(np.load(f)["elev"])
                rec.update(sun=round(a[0], 2), both=round(a[1], 2), year=round(a[2], 2), gap=a[3])
                if abs(dx) <= 25 and abs(dy) <= 25:
                    cf = [(W / f"hz/{key}_{c}_m1.npz") if (dx == 0 and dy == 0) else J / f"pos_{key}_{c}_x{dx}_y{dy}.npz" for c in CLONES]
                    cf = [p for p in cf if p.exists()]
                    if len(cf) >= 10:
                        cv = [m_for(np.load(p)["elev"]) for p in cf]
                        rec["cl_sun"] = [round(v[0], 2) for v in cv]; rec["cl_both"] = [round(v[1], 2) for v in cv]
                        rec["cl_year"] = [round(v[2], 2) for v in cv]; rec["cl_gap"] = [v[3] for v in cv]
                rec["dz_m"] = round(float(near.sample_xy(np.array([x0 + dx]), np.array([y0 + dy]))[0]) - s["z0"], 2)
                cells.append(rec)
        s["pos"] = cells
        # ---- sky, replay, hotspots, rq2
        s["sky"] = json.load(open(W / "sky.json"))[key]
        s["replay"] = json.load(open(W / "replay.json"))[key]
        hs = json.load(open(W / "hotspots_report.json"))
        hy = hs[key]["year"]
        c0 = hy["observer_cell"]
        s["hot"] = {"total": hy["expected_flip_hours_total"], "lander": c0["expected_flip_hours_removed"], "lander_toterr": c0["toterr_m"],
                    "top": [{"dx": r["x_m"] - x0, "dy": r["y_m"] - y0, "d": r["dist_from_lander_m"], "v": r["expected_flip_hours_removed"],
                             "err": r["toterr_m"]} for r in hy["top"]],
                    "test": hs.get("measurement_test", {}).get(key)}
        rq = json.load(open(W / "rq2_report.json"))
        s["rq2"] = {w: {k: rq[f"{key}/{w}"][k] for k in ("truth_flip_hours_any_clone", "A16_linearised_16_ridges", "A_linearised", "B_toterr_rho0")}
                    for w in ("nov14d", "year")}
        s["rq2"]["fd"] = {k: rq[key]["finite_difference"][k] for k in ("n", "median_rel_err")}
        sm = json.load(open(W / "strip/strip_summary.json"))[key]
        s["season"] = sm["season"]
        for nm, fn in (("more", "more.json"), ("asset", "asset.json"), ("sfs", "sfs_result.json"), ("sur", "surrogate.json"), ("hotc", "hot_corr.json")):
            if (W / fn).exists():
                s[nm] = json.load(open(W / fn)).get(key)
        lens = W / f"lens_{key}.json"
        if lens.exists():
            s["lens"] = json.load(open(lens))
        out["sites"][key] = s
        print(key, "ok", "masts" in s, len(cells))
    if (W / "wac_result.json").exists():
        out["wac"] = json.load(open(W / "wac_result.json"))
    if (W / "barker_result.json").exists():
        out["barker"] = json.load(open(W / "barker_result.json"))
    hfiles = [D / "pgda90/LDEM_80S_80MPP_ADJ.TIF", D / "pgda78/Site04/Site04_final_adj_5mpp_surf.tif",
              D / "pgda78/Site01/Site01_final_adj_5mpp_surf.tif"]
    out["inputs"] = [{"file": p.name, "sha256_16": sha(p)} for p in hfiles]
    out["inputs"] += [{"file": r["file"], "sha256_16": r["sha256"][:16]} for k, m in json.load(open(W / "eph_meta.json")).items()
                      for b in m["raw"].values() for r in b]
    def clean(o):
        if isinstance(o, float):
            return None if not math.isfinite(o) else o
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [clean(v) for v in o]
        return o
    json.dump(clean(out), open(W / "viewer_data.json", "w"), separators=(",", ":"), allow_nan=False)
    print("bytes", (W / "viewer_data.json").stat().st_size)


if __name__ == "__main__":
    main()
