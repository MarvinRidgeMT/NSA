"""DEM clone sweep: how much does NASA's published terrain uncertainty change Sun/Earth visibility?

For each ROI, the terrain horizon is recomputed on the nominal PGDA 78 DEM and on N of its 100
published clones (complete alternative DEMs), for each mast height. JPL Horizons directions are
fetched once per ROI (a few metres of height change the Sun/Earth direction negligibly).

Example (third computer):
    python -m polaris_batch.clone_sweep --sites Site01,Site04 --clones 20 --masts 1,5,10 --workers 4

Near-field rays are sampled every --near-fine-step (default 1 m) out to --near-fine-m (default
1000 m), then every DEM pixel. A 5 m step everywhere is NOT converged for 1 m masts.

Interpretation: the spread across clones describes sensitivity to the sampled terrain alternatives.
It is NOT a calibrated mission-success probability.
"""
from __future__ import annotations

import argparse
import csv
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from . import common, core


def _job(task):
    roi, dem_id, dem_path, far_path, mast, n_az, eph_npz, fine_step, fine_m = task
    near = common.cached_dem(str(dem_path))
    far = common.cached_dem(str(far_path))
    hz = core.compute_horizon(roi["lon_deg_east"], roi["lat_deg"], near, far, mast_m=mast, n_az=n_az,
                              near_fine_step=fine_step, near_fine_m=fine_m)
    e = np.load(eph_npz)
    sun = {k: e[f"sun_{k}"] for k in ("az", "el", "ang_diam_arcsec")}
    earth = {k: e[f"earth_{k}"] for k in ("az", "el", "ang_diam_arcsec")}
    v = core.visibility(hz, sun, earth)
    sun_vis = sun["el"] > hz.at(sun["az"])
    run = best = 0
    for ok in sun_vis:
        run = 0 if ok else run + 1
        best = max(best, run)
    row = {"site": roi["site"], "roi": roi["roi"], "dem": dem_id, "mast_m": mast,
           **{k: round(val, 3) for k, val in v.items() if not k.startswith("_") and k != "n_steps"},
           "longest_sun_gap_steps": best,
           "n_steps": v["n_steps"], "horizon_complete_frac": round(float(hz.complete.mean()), 3),
           "max_horizon_deg": round(float(np.nanmax(hz.elev)), 3)}
    return row, (hz.to_json() if dem_id == "nominal" else None)


def summarize(rows, thresholds):
    out = []
    keys = sorted({(r["site"], r["roi"], r["mast_m"]) for r in rows})
    for site, roi, mast in keys:
        grp = [r for r in rows if (r["site"], r["roi"], r["mast_m"]) == (site, roi, mast)]
        nom = next((r for r in grp if r["dem"] == "nominal"), None)
        cl = [r for r in grp if r["dem"] != "nominal"]
        rec = {"site": site, "roi": roi, "mast_m": mast, "n_clones": len(cl)}
        for m in ("sun_centre_pct", "sun_disc_mean_pct", "earth_centre_pct", "earth_any_pct", "both_centre_pct",
                  "longest_sun_gap_steps"):
            vals = np.array([r[m] for r in cl]) if cl else np.array([np.nan])
            rec[f"{m}_nominal"] = nom[m] if nom else None
            for q, name in ((0, "min"), (10, "p10"), (50, "median"), (90, "p90"), (100, "max")):
                rec[f"{m}_{name}"] = round(float(np.nanpercentile(vals, q)), 3)
            rec[f"{m}_std"] = round(float(np.nanstd(vals)), 3)
        for m, thr in thresholds.items():
            ok = [r[m] >= thr for r in cl]
            rec[f"pass_{m}>={thr:g}"] = f"{sum(ok)}/{len(ok)}"
            rec[f"verdict_{m}"] = ("robust pass" if ok and all(ok) else "robust fail" if ok and not any(ok)
                                   else "MARGINAL (clones disagree)" if ok else "n/a")
        out.append(rec)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path("data/external"), help="download/cache root")
    ap.add_argument("--out", type=Path, default=Path("results/clone_sweep"))
    ap.add_argument("--roi-csv", type=Path, default=common.DEFAULT_ROIS)
    ap.add_argument("--sites", default="Site01,Site04")
    ap.add_argument("--rois", default=None, help="e.g. Site01:6,Site04:3 (overrides --sites)")
    ap.add_argument("--clones", type=int, default=20, help="number of clones, 1..100")
    ap.add_argument("--masts", default="1,5,10", help="observer heights above ground, m")
    ap.add_argument("--start", default="2026-11-14 00:00")
    ap.add_argument("--stop", default="2026-11-28 00:00")
    ap.add_argument("--step", default="1h")
    ap.add_argument("--n-az", type=int, default=720)
    ap.add_argument("--near-fine-step", type=float, default=1.0, help="ray step near the observer, m (0 = DEM pixel)")
    ap.add_argument("--near-fine-m", type=float, default=1000.0, help="distance covered by the fine step, m")
    ap.add_argument("--workers", type=int, default=max(1, min(4, (__import__("os").cpu_count() or 2) - 1)))
    ap.add_argument("--threshold", action="append", default=["sun_centre_pct=70", "both_centre_pct=40"],
                    help="metric=value pass threshold; repeatable")
    a = ap.parse_args(argv)
    assert 0 <= a.clones <= 100
    masts = [float(m) for m in a.masts.split(",")]
    thresholds = {k: float(v) for k, v in (t.split("=") for t in a.threshold)}
    rois = common.select_rois(a.roi_csv, a.sites, a.rois)
    if not rois:
        raise SystemExit("no ROIs selected")
    t0 = time.time()
    far = common.prepare_far(a.data)
    dems = {s: common.prepare_site(s, a.data, a.clones) for s in sorted({r["site"] for r in rois})}

    eph_dir = a.out / "ephemeris"; eph_dir.mkdir(parents=True, exist_ok=True)
    raw = {}
    tasks = []
    fine = (a.near_fine_step or None, a.near_fine_m if a.near_fine_step else 0.0)
    for r in rois:
        z0 = common.cached_dem(str(dems[r["site"]]["nominal"])).sample_lonlat(
            np.array([r["lon_deg_east"]]), np.array([r["lat_deg"]]))[0]
        print(f"[horizons] {r['site']} ROI{r['roi']} ground {z0:.1f} m", flush=True)
        sun = core.horizons_observer("10", r["lon_deg_east"], r["lat_deg"], float(z0), a.start, a.stop, a.step, a.data / "horizons_cache")
        earth = core.horizons_observer("399", r["lon_deg_east"], r["lat_deg"], float(z0), a.start, a.stop, a.step, a.data / "horizons_cache")
        npz = eph_dir / f"{r['site']}_ROI{r['roi']}.npz"
        np.savez(npz, **{f"sun_{k}": sun[k] for k in ("az", "el", "ang_diam_arcsec")},
                 **{f"earth_{k}": earth[k] for k in ("az", "el", "ang_diam_arcsec")})
        raw[f"{r['site']}_ROI{r['roi']}"] = {"sun": sun["raw"], "earth": earth["raw"], "first": sun["time"][0], "last": sun["time"][-1]}
        for dem_id, p in dems[r["site"]].items():
            for m in masts:
                tasks.append((r, dem_id, p, far, m, a.n_az, npz, *fine))
    print(f"[run] {len(tasks)} horizon+visibility jobs on {a.workers} workers", flush=True)

    rows, horizons = [], {}
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(_job, t) for t in sorted(tasks, key=lambda t: str(t[2]))]
        for i, f in enumerate(as_completed(futs), 1):
            row, hz = f.result()
            rows.append(row)
            if hz:
                horizons[f"{row['site']}_ROI{row['roi']}_mast{row['mast_m']:g}"] = hz
            if i % 10 == 0 or i == len(futs):
                print(f"[run] {i}/{len(futs)} done ({time.time() - t0:.0f} s)", flush=True)

    rows.sort(key=lambda r: (r["site"], r["roi"], r["mast_m"], r["dem"]))
    a.out.mkdir(parents=True, exist_ok=True)
    with open(a.out / "clone_sweep_runs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    summ = summarize(rows, thresholds)
    with open(a.out / "clone_sweep_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summ[0])); w.writeheader(); w.writerows(summ)
    common.write_json(a.out / "nominal_horizons.json", horizons)
    common.write_json(a.out / "manifest.json", common.run_manifest(a, {
        "runtime_s": round(time.time() - t0, 1), "horizons_raw": raw,
        "dem_files": {s: {k: str(p) for k, p in d.items()} for s, d in dems.items()},
        "far_dem": str(far),
        "note": "Clone spread = sensitivity to sampled terrain alternatives, not a mission probability. "
                "Thresholds are illustrative, not mission requirements."}))
    print("\n=== summary (sun centre %, clones min..max | nominal) ===")
    for s in summ:
        print(f"{s['site']} ROI{s['roi']} mast {s['mast_m']:>4g} m: "
              f"sun {s['sun_centre_pct_min']:.1f}..{s['sun_centre_pct_max']:.1f} | {s['sun_centre_pct_nominal']}  "
              f"both {s['both_centre_pct_min']:.1f}..{s['both_centre_pct_max']:.1f} | {s['both_centre_pct_nominal']}  "
              + "  ".join(f"{k[8:]}: {v}" for k, v in s.items() if k.startswith("verdict_")))
    print(f"\nwrote {a.out}/ in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
