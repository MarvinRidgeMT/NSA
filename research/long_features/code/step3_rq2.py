"""RQ2 pilot: Jacobian of the Sun margin w.r.t. terrain height, finite-difference test, flip forecast.

Truth = the 20 PGDA 78 clones run through the full ray march (work/hz/*.npz).
Forecasts never run a ray march on a clone:
  A  linearised clone forecast: nominal horizon + Jacobian x (clone height - nominal height) at the
     controlling point, the runner-up ridge and the observer (3 pixel lookups per azimuth bin per clone).
  B  error-map forecast: nominal horizon + PGDA 78 'toterr' sigma at the same points, no clones at all.
"""
import json, math, sys
from pathlib import Path
import numpy as np
from polaris_batch import core, ext

D = Path("data/external"); W = Path("work"); HZ = W / "hz"
R = {"Site04_ROI3": ("Site04", -89.78012, -156.32023), "Site01_ROI6": ("Site01", -89.47409, -137.3813)}
CLONES = [f"clone_{n:04d}" for n in range(1, 21)]
WIN = {"nov14d": (312, 312 + 337),        # 2026-11-14 00:00 .. 11-28 00:00, 337 hourly samples (demo window)
       "year": (312, 312 + 8761)}         # 2026-11-14 00:00 .. 2027-11-14 00:00, 8761 hourly samples


def load_hx(key, dem_id):
    z = np.load(HZ / f"{key}_{dem_id}_m1.npz")
    return ext.HorizonX(**{k: (z[k] if z[k].shape else float(z[k])) for k in z.files})


def interp_bins(hx_like_elev, az_deg):
    n = len(hx_like_elev); step = 360.0 / n
    a = np.mod(np.asarray(az_deg) - step / 2, 360.0) / step
    i0 = np.floor(a).astype(int) % n; i1 = (i0 + 1) % n; f = a - np.floor(a)
    return hx_like_elev[i0] * (1 - f) + hx_like_elev[i1] * f


def dE_dh0(h0, h, d):
    th = np.asarray(d) / core.R_MOON
    r0, r = core.R_MOON + h0, core.R_MOON + np.asarray(h)
    a = r * np.cos(th) - r0; b = r * np.sin(th)
    return np.degrees(-b / (a * a + b * b))


def prf(pred, truth):
    tp = int(np.sum(pred & truth)); fp = int(np.sum(pred & ~truth)); fn = int(np.sum(~pred & truth))
    return {"tp": tp, "fp": fp, "fn": fn, "tn": int(np.sum(~pred & ~truth)),
            "recall": round(tp / (tp + fn), 3) if tp + fn else None,
            "precision": round(tp / (tp + fp), 3) if tp + fp else None}


def single_az_horizon(lon0, lat0, near_z, near, far, az, h0, near_step=1.0):
    """One-azimuth ray march on a (possibly modified) near-DEM array; same sampling as compute_horizon_x."""
    d = np.concatenate([np.arange(near_step, 25000.0, near_step), np.arange(25000.0, 280001.0, far.res)])
    lon, lat = core.destination(lon0, lat0, np.array([az]), d)
    x, y = near.to_grid.transform(lon, lat)
    saved = near.z; near.z = near_z
    try:
        hn = near.sample_xy(x, y)
    finally:
        near.z = saved
    h = np.where(np.isfinite(hn), hn, far.sample_xy(x, y))
    e = core.elevation_angle_deg(h0, h, d[None, :])
    return float(np.nanmax(e))


def main():
    far = core.Dem.open(D / "pgda90/LDEM_80S_80MPP_ADJ.TIF")
    report = {}
    for key, (site, lat, lon) in R.items():
        print(f"\n===== {key}", flush=True)
        near = core.Dem.open(core.site_files(site, D)["surf"][1])
        err = core.Dem.open(core.site_files(site, D)["toterr"][1])
        nom = load_hx(key, "nominal")
        e = np.load(W / f"eph_{key}.npz")
        sun_az_all, sun_el_all = e["sun_az"], e["sun_el"]
        # ---- nominal and clone states over the year (truth)
        Hn = interp_bins(nom.elev, sun_az_all)
        m0 = sun_el_all - Hn
        st0 = m0 > 0
        clone_hx = {c: load_hx(key, c) for c in CLONES}
        stc = np.array([sun_el_all > interp_bins(clone_hx[c].elev, sun_az_all) for c in CLONES])  # (20, T)
        # ---- heights at controlling points in each clone (pixel lookups, no ray march)
        pts = {"p1": (nom.x, nom.y, nom.in_near), "p2": (nom.x2, nom.y2, nom.in_near2)}
        x0, y0 = near.to_grid.transform(np.array([lon]), np.array([lat]))
        hnom = {k: np.where(v[2], near.sample_xy(v[0], v[1]), np.nan) for k, v in pts.items()}
        z0n = float(near.sample_xy(x0, y0)[0])
        dh = {k: [] for k in pts}; dz0 = []; dhc = []
        cx, cy, cn = nom.cand_x, nom.cand_y, nom.cand_near
        hc_nom = np.where(cn, near.sample_xy(cx, cy), 0.0)
        for c in CLONES:
            cd = core.Dem.open(core.clone_file(site, int(c[-4:]), D)[1])
            for k, v in pts.items():
                dh[k].append(np.where(v[2], cd.sample_xy(v[0], v[1]) - hnom[k], 0.0))
            dz0.append(float(cd.sample_xy(x0, y0)[0]) - z0n)
            dhc.append(np.where(cn, cd.sample_xy(cx, cy) - hc_nom, 0.0))
            del cd
        dh = {k: np.array(v) for k, v in dh.items()}; dz0 = np.array(dz0); dhc = np.array(dhc)
        Jc = ext.dE_dh(nom.h0, nom.cand_h, nom.cand_dist); J0c = dE_dh0(nom.h0, nom.cand_h, nom.cand_dist)
        # Jacobians (deg per m): controlling point, runner-up, observer (per bin, for each point)
        J1, J2 = nom.jac, nom.jac2
        J01 = dE_dh0(nom.h0, nom.hgt, nom.dist)
        h2 = nom.elev2  # runner-up elevation already in deg
        # observer derivative for runner-up: use its own distance; height not stored -> invert E2 for h2
        th2 = nom.dist2 / core.R_MOON
        r2 = (core.R_MOON + nom.h0) / (np.cos(th2) - np.sin(th2) * np.tan(np.radians(nom.elev2)))
        J02 = dE_dh0(nom.h0, r2 - core.R_MOON, nom.dist2)

        # ---------------- finite-difference test (PDF RQ2 'finite-difference test')
        fd = []
        used_bins = np.unique(ext.nearest_bin(sun_az_all[WIN["nov14d"][0]:WIN["nov14d"][1]]))
        rng = np.random.default_rng(0)
        test_bins = [b for b in used_bins if nom.in_near[b]]
        test_bins = sorted(rng.choice(test_bins, size=min(12, len(test_bins)), replace=False).tolist())
        inv = near.inv
        for b in test_bins:
            col, row = inv * (nom.x[b], nom.y[b])
            r_i, c_i = int(math.floor(row - 0.5)), int(math.floor(col - 0.5))
            for delta in (0.25, 1.0):
                z = near.z.copy(); z[r_i - 1:r_i + 3, c_i - 1:c_i + 3] += delta   # 4x4 block: bilinear value at the point rises by delta
                Hfd = single_az_horizon(lon, lat, z, near, far, nom.az[b], nom.h0)
                fd.append({"bin": int(b), "az": float(nom.az[b]), "dist_m": float(nom.dist[b]), "delta_m": delta,
                           "dH_fd_deg": Hfd - float(nom.elev[b]), "dH_lin_deg": float(J1[b] * delta)})
            # observer
            for delta in (0.25,):
                Hfd = single_az_horizon(lon, lat, near.z, near, far, nom.az[b], nom.h0 + delta)
                fd.append({"bin": int(b), "az": float(nom.az[b]), "dist_m": float(nom.dist[b]), "delta_m": delta, "observer": True,
                           "dH_fd_deg": Hfd - float(nom.elev[b]), "dH_lin_deg": float(J01[b] * delta)})
        rel = [abs(r["dH_fd_deg"] - r["dH_lin_deg"]) / max(abs(r["dH_lin_deg"]), 1e-9) for r in fd]
        print("finite-difference: median rel err %.3g, max %.3g over %d tests" % (np.median(rel), np.max(rel), len(rel)))

        # ---------------- forecast A: linearised per-clone horizons
        Hlin = []
        for i in range(len(CLONES)):
            a1 = nom.elev + J1 * dh["p1"][i] + J01 * dz0[i]
            a2 = nom.elev2 + J2 * dh["p2"][i] + J02 * dz0[i]
            Hlin.append(np.maximum(a1, a2))
        stA = np.array([sun_el_all > interp_bins(h, sun_az_all) for h in Hlin])
        HlinK = [np.max(nom.cand_elev + Jc * dhc[i] + J0c * dz0[i], axis=1) for i in range(len(CLONES))]
        stK = np.array([sun_el_all > interp_bins(h, sun_az_all) for h in HlinK])

        # ---------------- forecast B: toterr only (no clones)
        s1 = np.where(nom.in_near, err.sample_xy(nom.x, nom.y), 0.0)
        s2 = np.where(nom.in_near2, err.sample_xy(nom.x2, nom.y2), 0.0)
        s0 = float(err.sample_xy(x0, y0)[0])
        out_site = {"toterr_observer_m": s0, "clone_dz0_m": {"mean": float(dz0.mean()), "std": float(dz0.std())},
                    "finite_difference": {"n": len(fd), "median_rel_err": float(np.median(rel)), "max_rel_err": float(np.max(rel)), "cases": fd}}
        # empirical vs toterr sigma at controlling points (sanity of error model)
        mask = nom.in_near
        emp = dh["p1"].std(axis=0)
        out_site["sigma_check"] = {"toterr_median_m": float(np.median(s1[mask])), "clone_std_median_m": float(np.median(emp[mask])),
                                   "ratio_median": float(np.median(emp[mask] / s1[mask]))}
        # correlation between observer and controlling-point clone errors (bins on the tile)
        rho = np.array([np.corrcoef(dh["p1"][:, b], dz0)[0, 1] for b in np.where(mask)[0]])
        out_site["rho_obs_ctrl_median"] = float(np.nanmedian(rho))
        for wname, (a, b) in WIN.items():
            sl = slice(a, b)
            truth_any = (stc[:, sl] != st0[sl]).any(axis=0)
            truth_cell = (stc[:, sl] != st0[sl])
            ib = ext.nearest_bin(sun_az_all[sl])
            res = {"n_samples": int(b - a), "sun_centre_nominal_pct": round(100 * st0[sl].mean(), 3),
                   "sun_centre_clones_pct": [round(100 * v, 3) for v in stc[:, sl].mean(axis=1)],
                   "truth_flip_hours_any_clone": int(truth_any.sum())}
            # A
            predA_cell = stA[:, sl] != st0[sl]
            res["A_linearised"] = {"per_clone_sample": prf(predA_cell.ravel(), truth_cell.ravel()),
                                   "any_clone": prf(predA_cell.any(axis=0), truth_any),
                                   "state_agreement_pct": round(100 * float((stA[:, sl] == stc[:, sl]).mean()), 4),
                                   "sun_pct_abs_err_max": round(float(np.max(np.abs(100 * stA[:, sl].mean(1) - 100 * stc[:, sl].mean(1)))), 3)}
            predK_cell = stK[:, sl] != st0[sl]
            res["A16_linearised_16_ridges"] = {"per_clone_sample": prf(predK_cell.ravel(), truth_cell.ravel()),
                                   "any_clone": prf(predK_cell.any(axis=0), truth_any),
                                   "state_agreement_pct": round(100 * float((stK[:, sl] == stc[:, sl]).mean()), 4),
                                   "sun_pct_abs_err_max": round(float(np.max(np.abs(100 * stK[:, sl].mean(1) - 100 * stc[:, sl].mean(1)))), 3),
                                   "sun_pct_pred_clone_range": [round(100 * float(stK[:, sl].mean(1).min()), 2), round(100 * float(stK[:, sl].mean(1).max()), 2)]}
            # B
            mabs = np.abs(m0[sl])
            for rho_name, rho_v in (("rho0", 0.0), ("rho_emp", out_site["rho_obs_ctrl_median"])):
                sig1 = np.sqrt((J1[ib] * s1[ib]) ** 2 + (J01[ib] * s0) ** 2 + 2 * rho_v * J1[ib] * J01[ib] * s1[ib] * s0)
                sig2 = np.sqrt((J2[ib] * s2[ib]) ** 2 + (J02[ib] * s0) ** 2)
                # runner-up only matters when it is close to the margin
                sig = np.where(np.abs(sun_el_all[sl] - nom.elev2[ib]) < np.abs(m0[sl]) + 3 * sig2, np.maximum(sig1, sig2), sig1)
                p = ext.norm_sf(mabs / np.maximum(sig, 1e-12))
                p_any = 1 - (1 - p) ** 20
                rows = {}
                for thr in (0.1, 0.25, 0.5):
                    rows[f"p_any>={thr}"] = prf(p_any >= thr, truth_any)
                # calibration: expected vs observed flipped clone-hours
                rows["expected_flip_clone_hours"] = round(float((20 * p).sum()), 1)
                rows["observed_flip_clone_hours"] = int(truth_cell.sum())
                res[f"B_toterr_{rho_name}"] = rows
            report_key = f"{key}/{wname}"
            report[report_key] = res
            print(wname, json.dumps({k: v for k, v in res.items() if k != "sun_centre_clones_pct"}, indent=None)[:1500])
        report[key] = out_site
        np.savez(W / f"rq2_{key}.npz", m0=m0, st0=st0, stc=stc, stA=stA, stK=stK, J1=J1, J01=J01, J2=J2, J02=J02,
                 s1=s1, s2=s2, s0=s0, dz0=dz0, dh1=dh["p1"], dh2=dh["p2"])
    json.dump(report, open(W / "rq2_report.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
