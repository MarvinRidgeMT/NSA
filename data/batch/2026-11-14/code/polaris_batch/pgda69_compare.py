"""Long-window validation: POLARIS average Sun/Earth visibility vs NASA PGDA product 69.

PGDA 69 (Mazarico et al. 2011) gives 18.6-year average solar illumination (fraction of the solar
disc visible) and Earth visibility (any part of the disc visible), from a 60 m LOLA DEM. We run
our pipeline over a long window at all 17 published PGDA 78 ROIs and compare.

Two terrain variants are run so resolution effects can be separated from pipeline errors:
  - fine:   5 m PGDA 78 near field + 80 m PGDA 90 far field (what POLARIS uses)
  - coarse: 80 m PGDA 90 only (closest to the 60 m DEM behind PGDA 69)
Agreement is judged on rank order (Spearman) and bias, not on exact equality.

Example (third computer, full 18.6-year cycle at 6 h):
    python -m polaris_batch.pgda69_compare --workers 4
Dense map check (recommended validation; hundreds of points per site):
    python -m polaris_batch.pgda69_compare --grid Site01,Site04,Site07,Site11 --grid-n 21 --workers 4
Quick check:
    python -m polaris_batch.pgda69_compare --rois Site01:6,Site04:3 --stop "2027-01-01 00:00" --step 12h
"""
from __future__ import annotations

import argparse
import csv
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from . import common, core


def _job(task):
    roi, variant, near_path, far_path, mast, n_az, eph_npz = task
    far = common.cached_dem(str(far_path))
    near = common.cached_dem(str(near_path)) if near_path else far
    hz = core.compute_horizon(roi["lon_deg_east"], roi["lat_deg"], near, far, mast_m=mast, n_az=n_az)
    e = np.load(eph_npz)
    sun = {k: e[f"sun_{k}"] for k in ("az", "el", "ang_diam_arcsec")}
    earth = {k: e[f"earth_{k}"] for k in ("az", "el", "ang_diam_arcsec")}
    v = core.visibility(hz, sun, earth)
    return {"site": roi["site"], "roi": roi["roi"], "variant": variant, "mast_m": mast,
            "ours_sun_disc_pct": round(v["sun_disc_mean_pct"], 2), "pgda69_sun_pct": roi["avg_sun_pct_18p6yr"],
            "diff_sun": round(v["sun_disc_mean_pct"] - roi["avg_sun_pct_18p6yr"], 2),
            "ours_earth_any_pct": round(v["earth_any_pct"], 2), "pgda69_earth_pct": roi["avg_earth_pct_18p6yr"],
            "diff_earth": round(v["earth_any_pct"] - roi["avg_earth_pct_18p6yr"], 2),
            "ours_sun_centre_pct": round(v["sun_centre_pct"], 2), "n_steps": v["n_steps"],
            "horizon_complete_frac": round(float(hz.complete.mean()), 3)}


def stats(rows, variant):
    g = [r for r in rows if r["variant"] == variant]
    out = {"variant": variant, "n_rois": len(g)}
    for body in ("sun", "earth"):
        d = np.array([r[f"diff_{body}"] for r in g])
        okey = "ours_sun_disc_pct" if body == "sun" else "ours_earth_any_pct"
        ours = [r[okey] for r in g]
        ref = [r[f"pgda69_{body}_pct"] for r in g]
        rho = spearmanr(ours, ref).statistic if len(g) >= 3 else float("nan")
        bo = max(g, key=lambda r: r[okey]); br = max(g, key=lambda r: r[f"pgda69_{body}_pct"])
        out[body] = {"mean_bias_pct_pts": round(float(d.mean()), 2), "rms_pct_pts": round(float(np.sqrt((d ** 2).mean())), 2),
                     "max_abs_pct_pts": round(float(np.abs(d).max()), 2), "spearman_rho": round(float(rho), 3),
                     "best_roi_ours": f"{bo['site']}_ROI{bo['roi']}", "best_roi_pgda69": f"{br['site']}_ROI{br['roi']}"}
    return out


def plot(rows, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    fig, axs = plt.subplots(1, 2, figsize=(10, 4.6))
    for ax, body, o, ref in ((axs[0], "Sun (disc fraction)", "ours_sun_disc_pct", "pgda69_sun_pct"),
                             (axs[1], "Earth (any part visible)", "ours_earth_any_pct", "pgda69_earth_pct")):
        for variant, mk in (("fine", "o"), ("coarse", "s")):
            g = [r for r in rows if r["variant"] == variant]
            if g:
                ax.scatter([r[ref] for r in g], [r[o] for r in g], marker=mk, label=variant, alpha=0.8)
        lo = min(min(r[ref], r[o]) for r in rows) - 3; hi = max(max(r[ref], r[o]) for r in rows) + 3
        ax.plot([lo, hi], [lo, hi], "k--", lw=0.8); ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
        ax.set_xlabel("NASA PGDA 69 average, %"); ax.set_ylabel("POLARIS average, %"); ax.set_title(body); ax.legend()
    fig.suptitle("POLARIS vs NASA PGDA 69 at PGDA 78 ROIs")
    fig.tight_layout(); fig.savefig(path, dpi=140); plt.close(fig)


# --------------------------------------------------------------------------- grid mode
PGDA69_URL = "https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608{sfx}.TIF"


def _grid_job(task):
    pt, variant, near_path, far_path, mast, n_az, eph_npz, anchor = task
    far = common.cached_dem(str(far_path))
    near = common.cached_dem(str(near_path)) if near_path else far
    try:
        hz = core.compute_horizon(pt["lon"], pt["lat"], near, far, mast_m=mast, n_az=n_az)
    except ValueError:
        return None
    e = np.load(eph_npz)
    bodies = {}
    for b in ("sun", "earth"):
        az, el = core.transfer_azel(e[f"{b}_az"], e[f"{b}_el"], anchor[0], anchor[1], pt["lon"], pt["lat"])
        bodies[b] = {"az": az, "el": el, "ang_diam_arcsec": e[f"{b}_ang_diam_arcsec"]}
    v = core.visibility(hz, bodies["sun"], bodies["earth"])
    return {**pt, "variant": variant, "ours_sun_disc_pct": round(v["sun_disc_mean_pct"], 2),
            "ours_earth_any_pct": round(v["earth_any_pct"], 2),
            "diff_sun": round(v["sun_disc_mean_pct"] - pt["pgda69_sun_pct"], 2),
            "diff_earth": round(v["earth_any_pct"] - pt["pgda69_earth_pct"], 2)}


def pyproj_tr(crs, inverse=False):
    import pyproj
    return (pyproj.Transformer.from_crs(crs, core.LONLAT, always_xy=True) if inverse
            else pyproj.Transformer.from_crs(core.LONLAT, crs, always_xy=True))


def run_grid(a, rois):
    import rasterio
    t0 = time.time()
    far = common.prepare_far(a.data)
    ref = {}
    for key, sfx in (("sun", ""), ("earth", "_EARTH")):
        p = a.data / "pgda69" / f"AVGVISIB_85S_060M_201608{sfx}.TIF"
        core.download(PGDA69_URL.format(sfx=sfx), p)
        ref[key] = rasterio.open(p)
    rows, tasks = [], []
    eph_dir = a.out / "ephemeris"; eph_dir.mkdir(parents=True, exist_ok=True)
    raw = {}
    for site in a.grid.split(","):
        nominal = common.prepare_site(site, a.data, 0)["nominal"]
        sr = [r for r in rois if r["site"] == site] or [r for r in core.load_rois(a.roi_csv) if r["site"] == site]
        tr = pyproj_tr(ref["sun"].crs)
        xs, ys = tr.transform([r["lon_deg_east"] for r in sr], [r["lat_deg"] for r in sr])
        cx, cy = float(np.mean(xs)), float(np.mean(ys))
        # snap the grid to PGDA 69 pixel centres so the reference is sampled exactly
        r0, c0 = ref["sun"].index(cx, cy)
        half = a.grid_n // 2
        inv = pyproj_tr(ref["sun"].crs, inverse=True)
        alon, alat = inv.transform(cx, cy)
        z0 = common.cached_dem(str(nominal)).sample_lonlat(np.array([alon]), np.array([alat]))[0]
        print(f"[horizons] {site} grid anchor {alat:.5f},{alon:.5f}", flush=True)
        sun = core.horizons_observer("10", alon, alat, float(z0), a.start, a.stop, a.step, a.data / "horizons_cache")
        earth = core.horizons_observer("399", alon, alat, float(z0), a.start, a.stop, a.step, a.data / "horizons_cache")
        npz = eph_dir / f"{site}_grid_anchor.npz"
        np.savez(npz, **{f"sun_{k}": sun[k] for k in ("az", "el", "ang_diam_arcsec")},
                 **{f"earth_{k}": earth[k] for k in ("az", "el", "ang_diam_arcsec")})
        raw[f"{site}_grid"] = {"sun": sun["raw"], "earth": earth["raw"], "anchor_lonlat": [alon, alat]}
        sun_a = ref["sun"].read(1); ear_a = ref["earth"].read(1)
        for i in range(-half, half + 1):
            for j in range(-half, half + 1):
                rr, cc = r0 + i * a.grid_stride, c0 + j * a.grid_stride
                x, y = ref["sun"].xy(rr, cc)
                lon, lat = inv.transform(x, y)
                sv, ev = sun_a[rr, cc], ear_a[rr, cc]
                if sv < 0 or ev < 0:
                    continue
                pt = {"site": site, "gi": i, "gj": j, "x_m": round(x, 1), "y_m": round(y, 1), "lon": lon, "lat": lat,
                      "pgda69_sun_pct": round(float(sv) * 4e-3, 2), "pgda69_earth_pct": round(float(ev) * 4e-3, 2)}
                for v in a.variants.split(","):
                    tasks.append((pt, v, nominal if v == "fine" else None, far, a.mast, a.n_az, npz, (alon, alat)))
    print(f"[run] {len(tasks)} grid jobs on {a.workers} workers", flush=True)
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for k, res in enumerate(ex.map(_grid_job, tasks, chunksize=4), 1):
            if res:
                rows.append(res)
            if k % 50 == 0:
                print(f"[run] {k}/{len(tasks)} ({time.time() - t0:.0f} s)", flush=True)
    a.out.mkdir(parents=True, exist_ok=True)
    with open(a.out / "pgda69_grid_comparison.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    summary = []
    for site in a.grid.split(","):
        for v in a.variants.split(","):
            g = [r for r in rows if r["site"] == site and r["variant"] == v]
            if len(g) < 3:
                continue
            rec = {"site": site, "variant": v, "n_points": len(g)}
            for b, o in (("sun", "ours_sun_disc_pct"), ("earth", "ours_earth_any_pct")):
                d = np.array([r[f"diff_{b}"] for r in g])
                rec[b] = {"spearman_rho": round(float(spearmanr([r[o] for r in g], [r[f"pgda69_{b}_pct"] for r in g]).statistic), 3),
                          "pearson_r": round(float(np.corrcoef([r[o] for r in g], [r[f"pgda69_{b}_pct"] for r in g])[0, 1]), 3),
                          "mean_bias_pct_pts": round(float(d.mean()), 2), "median_abs_pct_pts": round(float(np.median(np.abs(d))), 2),
                          "rms_pct_pts": round(float(np.sqrt((d ** 2).mean())), 2)}
            summary.append(rec)
    plot_grid(rows, a.out / "pgda69_grid_maps.png")
    common.write_json(a.out / "grid_summary.json", {"summary": summary, "manifest": common.run_manifest(a, {
        "runtime_s": round(time.time() - t0, 1), "horizons_raw": raw,
        "method": "Grid on PGDA 69 pixel centres; Sun/Earth directions from one Horizons query per site, "
                  "re-expressed at each point (transfer_azel; checked vs direct Horizons <= 1e-4 deg)."})})
    for s in summary:
        print(f"[{s['site']} {s['variant']}] n={s['n_points']}  " + "  ".join(
            f"{b}: rho {s[b]['spearman_rho']}, r {s[b]['pearson_r']}, bias {s[b]['mean_bias_pct_pts']:+.2f}, "
            f"median|d| {s[b]['median_abs_pct_pts']:.2f}" for b in ("sun", "earth")))
    print(f"wrote {a.out}/ in {time.time() - t0:.0f} s")


def plot_grid(rows, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    sites = sorted({r["site"] for r in rows})
    variants = sorted({r["variant"] for r in rows}, reverse=True)
    fig, axs = plt.subplots(len(sites) * len(variants), 4, figsize=(15, 3.6 * len(sites) * len(variants)), squeeze=False)
    k = 0
    for site in sites:
        for v in variants:
            g = [r for r in rows if r["site"] == site and r["variant"] == v]
            n = max(max(abs(r["gi"]), abs(r["gj"])) for r in g)
            m = {key: np.full((2 * n + 1, 2 * n + 1), np.nan) for key in ("ref", "ours", "diff")}
            for r in g:
                ij = (r["gi"] + n, r["gj"] + n)
                m["ref"][ij], m["ours"][ij], m["diff"][ij] = r["pgda69_sun_pct"], r["ours_sun_disc_pct"], r["diff_sun"]
            for ax, key, title, cmap, lim in ((axs[k, 0], "ref", "NASA PGDA 69 Sun %", "magma", (0, 100)),
                                              (axs[k, 1], "ours", f"POLARIS Sun % ({v})", "magma", (0, 100)),
                                              (axs[k, 2], "diff", "POLARIS - NASA, pts", "RdBu_r", (-30, 30))):
                im = ax.imshow(m[key], cmap=cmap, vmin=lim[0], vmax=lim[1]); ax.set_title(f"{site}: {title}", fontsize=9)
                ax.set_xticks([]); ax.set_yticks([]); fig.colorbar(im, ax=ax, fraction=0.046)
            ax = axs[k, 3]
            ax.scatter([r["pgda69_sun_pct"] for r in g], [r["ours_sun_disc_pct"] for r in g], s=8, label="Sun")
            ax.scatter([r["pgda69_earth_pct"] for r in g], [r["ours_earth_any_pct"] for r in g], s=8, label="Earth")
            ax.plot([0, 100], [0, 100], "k--", lw=0.8); ax.set_xlabel("NASA PGDA 69 %"); ax.set_ylabel("POLARIS %")
            ax.legend(fontsize=8); ax.set_title(f"{site} {v}: point by point", fontsize=9)
            k += 1
    fig.tight_layout(); fig.savefig(path, dpi=120); plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path("data/external"))
    ap.add_argument("--out", type=Path, default=Path("results/pgda69_compare"))
    ap.add_argument("--roi-csv", type=Path, default=common.DEFAULT_ROIS)
    ap.add_argument("--sites", default=None)
    ap.add_argument("--rois", default=None, help="e.g. Site01:6,Site04:3; default: all 17 ROIs")
    ap.add_argument("--start", default="2026-01-01 00:00")
    ap.add_argument("--stop", default="2044-08-08 00:00", help="default spans one 18.6-yr nodal cycle")
    ap.add_argument("--step", default="6h")
    ap.add_argument("--mast", type=float, default=1.0, help="observer height above ground, m")
    ap.add_argument("--variants", default="fine,coarse")
    ap.add_argument("--n-az", type=int, default=720)
    ap.add_argument("--workers", type=int, default=max(1, min(4, (__import__("os").cpu_count() or 2) - 1)))
    ap.add_argument("--grid", default=None, help="grid mode: sites, e.g. Site01,Site04 (dense map comparison)")
    ap.add_argument("--grid-n", type=int, default=15, help="grid is n x n PGDA 69 pixels")
    ap.add_argument("--grid-stride", type=int, default=2, help="pixels between grid points (60 m each)")
    a = ap.parse_args(argv)
    variants = a.variants.split(",")
    rois = common.select_rois(a.roi_csv, a.sites, a.rois)
    if a.grid:
        return run_grid(a, rois)
    t0 = time.time()
    far = common.prepare_far(a.data)
    nominal = {s: common.prepare_site(s, a.data, 0)["nominal"] for s in sorted({r["site"] for r in rois})}
    eph_dir = a.out / "ephemeris"; eph_dir.mkdir(parents=True, exist_ok=True)
    tasks, raw = [], {}
    for r in rois:
        z0 = common.cached_dem(str(nominal[r["site"]])).sample_lonlat(np.array([r["lon_deg_east"]]), np.array([r["lat_deg"]]))[0]
        print(f"[horizons] {r['site']} ROI{r['roi']}  {a.start} -> {a.stop} @ {a.step}", flush=True)
        sun = core.horizons_observer("10", r["lon_deg_east"], r["lat_deg"], float(z0), a.start, a.stop, a.step, a.data / "horizons_cache")
        earth = core.horizons_observer("399", r["lon_deg_east"], r["lat_deg"], float(z0), a.start, a.stop, a.step, a.data / "horizons_cache")
        if len(sun["az"]) != len(earth["az"]):
            raise RuntimeError("Sun/Earth ephemeris length mismatch")
        npz = eph_dir / f"{r['site']}_ROI{r['roi']}.npz"
        np.savez(npz, **{f"sun_{k}": sun[k] for k in ("az", "el", "ang_diam_arcsec")},
                 **{f"earth_{k}": earth[k] for k in ("az", "el", "ang_diam_arcsec")})
        raw[f"{r['site']}_ROI{r['roi']}"] = {"sun": sun["raw"], "earth": earth["raw"], "n": len(sun["az"])}
        for v in variants:
            tasks.append((r, v, nominal[r["site"]] if v == "fine" else None, far, a.mast, a.n_az, npz))
    print(f"[run] {len(tasks)} jobs on {a.workers} workers", flush=True)
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        rows = list(ex.map(_job, tasks))
    rows.sort(key=lambda r: (r["variant"], r["site"], r["roi"]))
    a.out.mkdir(parents=True, exist_ok=True)
    with open(a.out / "pgda69_comparison.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    summary = [stats(rows, v) for v in variants]
    plot(rows, a.out / "pgda69_comparison.png")
    common.write_json(a.out / "summary.json", {"summary": summary, "manifest": common.run_manifest(a, {
        "runtime_s": round(time.time() - t0, 1), "horizons_raw": raw,
        "reference": "NASA PGDA product 69, AVGVISIB_85S_060M_201608(_EARTH).TIF, scale 4e-05",
        "caveats": ["PGDA 69 is an 18.6-yr average from a 60 m DEM; observer height not stated on the product page.",
                    "Earth 'any part visible' is slightly optimistic for DSN radio links.",
                    "Agreement means consistency with an independent NASA model, not ground truth."]})})
    for s in summary:
        print(f"\n[{s['variant']}] n={s['n_rois']}")
        for b in ("sun", "earth"):
            x = s[b]
            print(f"  {b:5s}: Spearman rho {x['spearman_rho']}, bias {x['mean_bias_pct_pts']:+.2f} pts, "
                  f"RMS {x['rms_pct_pts']:.2f}, max |d| {x['max_abs_pct_pts']:.2f}; best ROI ours {x['best_roi_ours']} vs NASA {x['best_roi_pgda69']}")
    print(f"\nwrote {a.out}/ in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
