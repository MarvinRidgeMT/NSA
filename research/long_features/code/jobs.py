"""Generic horizon-job runner. Each job: dict(out, site, dem ('nominal'|'clone_NNNN'|path), lon, lat, mast, near_step,
far ('80m' or path), near_max). Saves az, elev, dist, h0, z0 to work/jobs/<out>.npz; skips existing outputs."""
import json, sys, time
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from pathlib import Path
import numpy as np
from polaris_batch import core

D = Path("data/external"); OUT = Path("work/jobs"); OUT.mkdir(parents=True, exist_ok=True)
FAR80 = D / "pgda90/LDEM_80S_80MPP_ADJ.TIF"


@lru_cache(3)
def dem(p):
    return core.Dem.open(Path(p))


def dem_path(site, dem_id):
    if dem_id == "nominal":
        return core.site_files(site, D)["surf"][1]
    if dem_id.startswith("clone_"):
        return core.clone_file(site, int(dem_id[-4:]), D)[1]
    return Path(dem_id)


def run(j):
    f = OUT / f"{j['out']}.npz"
    if f.exists():
        return j["out"], 0.0
    t = time.time()
    near = dem(str(dem_path(j["site"], j["dem"])))
    far = dem(str(j.get("far") or FAR80))
    hz = core.compute_horizon(j["lon"], j["lat"], near, far, mast_m=j["mast"], near_step=j.get("near_step", 1.0),
                              near_max_m=j.get("near_max", 25000.0))
    z0 = hz.h0 - j["mast"]
    np.savez(f, az=hz.az, elev=hz.elev, dist=hz.dist, h0=hz.h0, z0=z0)
    return j["out"], time.time() - t


if __name__ == "__main__":
    jobs = json.load(open(sys.argv[1]))
    jobs = [j for j in jobs if not (OUT / f"{j['out']}.npz").exists()]
    # group by DEM so the per-process cache is reused
    jobs.sort(key=lambda j: (j["site"], j["dem"]))
    print(f"{len(jobs)} jobs", flush=True)
    t0 = time.time()
    with ProcessPoolExecutor(int(sys.argv[2]) if len(sys.argv) > 2 else 2) as ex:
        for i, (o, dt) in enumerate(ex.map(run, jobs, chunksize=4), 1):
            if i % 25 == 0 or i == len(jobs):
                print(i, o, round(dt, 1), round(time.time() - t0), flush=True)
