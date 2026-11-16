"""POLARIS-X batch science core (copied from claude/POLARIS_BATCH_SOURCE.md, polaris_batch v2).

Conventions: Moon sphere R = 1737400 m; PGDA south polar stereographic rasters read via their CRS;
azimuth clockwise from local north (JPL Horizons); great-circle rays; elevation angles include curvature.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyproj
import rasterio
from scipy.ndimage import map_coordinates

R_MOON = 1737400.0
LONLAT = pyproj.CRS.from_proj4(f"+proj=longlat +R={R_MOON} +no_defs")
PGDA78 = "https://pgda.gsfc.nasa.gov/data/LOLA_5mpp"
PGDA90_80M = "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF"
HORIZONS_API = "https://ssd.jpl.nasa.gov/api/horizons.api"
DEFAULT_NEAR_STEP_M = 1.0


def download(url: str, dest: Path, retries: int = 3) -> Path:
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
                expected = int(r.headers.get("Content-Length") or -1)
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            got = tmp.stat().st_size
            if expected >= 0 and got != expected:
                raise IOError(f"truncated download {url}: {got} of {expected} bytes")
            tmp.replace(dest)
            return dest
        except Exception:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))
    return dest


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class Dem:
    path: Path
    z: np.ndarray
    inv: object
    to_grid: pyproj.Transformer
    res: float

    @classmethod
    def open(cls, path: Path) -> "Dem":
        with rasterio.open(path) as ds:
            z = ds.read(1).astype(np.float64)  # float64: float32 + R_MOON loses ~0.125 m (bug in batch v2)
            if ds.nodata is not None:
                z[z == ds.nodata] = np.nan
            z[~np.isfinite(z)] = np.nan
            return cls(Path(path), z, ~ds.transform,
                       pyproj.Transformer.from_crs(LONLAT, ds.crs, always_xy=True),
                       float(abs(ds.res[0])))

    def sample_lonlat(self, lon, lat):
        x, y = self.to_grid.transform(lon, lat)
        return self.sample_xy(x, y)

    def sample_xy(self, x, y):
        col, row = self.inv * (np.asarray(x), np.asarray(y))
        coords = np.vstack([np.ravel(row) - 0.5, np.ravel(col) - 0.5])
        v = map_coordinates(self.z, coords, order=1, mode="constant", cval=np.nan)
        return v.reshape(np.shape(x))


def site_files(site: str, root: Path) -> dict:
    d = Path(root) / "pgda78" / site
    return {"surf": (f"{PGDA78}/{site}/{site}_final_adj_5mpp_surf.tif", d / f"{site}_final_adj_5mpp_surf.tif"),
            "toterr": (f"{PGDA78}/{site}/{site}_final_adj_5mpp_toterr.tif", d / f"{site}_final_adj_5mpp_toterr.tif")}


def clone_file(site: str, n: int, root: Path):
    name = f"{site}_final_adj_5mpp_{n:04d}_err.tif"
    return f"{PGDA78}/{site}/Clones/{name}", Path(root) / "pgda78" / site / "Clones" / name


def destination(lon0, lat0, az_deg, dist_m):
    phi1, lam1 = math.radians(lat0), math.radians(lon0)
    th = np.radians(az_deg)[:, None]
    dl = (np.asarray(dist_m) / R_MOON)[None, :]
    sp2 = math.sin(phi1) * np.cos(dl) + math.cos(phi1) * np.sin(dl) * np.cos(th)
    phi2 = np.arcsin(np.clip(sp2, -1, 1))
    lam2 = lam1 + np.arctan2(np.sin(th) * np.sin(dl) * math.cos(phi1), np.cos(dl) - math.sin(phi1) * sp2)
    return np.degrees(lam2), np.degrees(phi2)


def elevation_angle_deg(h0, h, dist_m):
    th = np.asarray(dist_m) / R_MOON
    r0, r = R_MOON + h0, R_MOON + h
    return np.degrees(np.arctan2(r * np.cos(th) - r0, r * np.sin(th)))


@dataclass
class Horizon:
    az: np.ndarray
    elev: np.ndarray
    dist: np.ndarray
    complete: np.ndarray
    h0: float

    def at(self, az_deg):
        step = 360.0 / len(self.az)
        a = np.mod(np.asarray(az_deg) - self.az[0], 360.0) / step
        i0 = np.floor(a).astype(int) % len(self.az)
        i1 = (i0 + 1) % len(self.az)
        f = a - np.floor(a)
        return self.elev[i0] * (1 - f) + self.elev[i1] * f


def compute_horizon(lon0, lat0, near, far, mast_m=1.0, n_az=720, near_max_m=25000.0, far_max_m=280000.0,
                    near_step=None, far_step=None, az_chunk=60):
    near_step = near_step or near.res
    far_step = far_step or far.res
    z0 = float(near.sample_lonlat(np.array([lon0]), np.array([lat0]))[0])
    if not np.isfinite(z0):
        z0 = float(far.sample_lonlat(np.array([lon0]), np.array([lat0]))[0])
    h0 = z0 + mast_m
    az = (np.arange(n_az) + 0.5) * 360.0 / n_az
    d = np.concatenate([np.arange(near_step, near_max_m, near_step), np.arange(near_max_m, far_max_m + 1, far_step)])
    same_crs = far.to_grid.target_crs == near.to_grid.target_crs
    elev = np.empty(n_az); dist = np.empty(n_az); complete = np.empty(n_az, bool)
    for s in range(0, n_az, az_chunk):
        sl = slice(s, min(s + az_chunk, n_az))
        lon, lat = destination(lon0, lat0, az[sl], d)
        x, y = near.to_grid.transform(lon, lat)
        hn = near.sample_xy(x, y)
        hf = far.sample_xy(x, y) if same_crs else far.sample_lonlat(lon, lat)
        h = np.where(np.isfinite(hn), hn, hf)
        e = elevation_angle_deg(h0, h, d[None, :])
        e_masked = np.where(np.isfinite(e), e, -np.inf)
        k = np.argmax(e_masked, axis=1)
        el = e_masked[np.arange(len(k)), k]
        dist[sl] = np.where(np.isfinite(el), d[k], np.nan)
        elev[sl] = np.where(np.isfinite(el), el, np.nan)
        complete[sl] = np.isfinite(h).all(axis=1)
    return Horizon(az, elev, dist, complete, h0)


def horizons_observer(body, lon, lat, h_m, start, stop, step, cache_dir, chunk_years=4):
    from datetime import datetime
    cache_dir = Path(cache_dir); cache_dir.mkdir(parents=True, exist_ok=True)
    t0, t1 = datetime.fromisoformat(start), datetime.fromisoformat(stop)
    edges = [t0]
    while edges[-1] < t1:
        nxt = edges[-1].replace(year=edges[-1].year + chunk_years)
        edges.append(min(nxt, t1))
    times, az, el, diam, raw_files = [], [], [], [], []
    for a, b in zip(edges[:-1], edges[1:]):
        params = {"format": "text", "COMMAND": f"'{body}'", "CENTER": "'coord@301'", "COORD_TYPE": "'GEODETIC'",
                  "SITE_COORD": f"'{lon:.6f},{lat:.6f},{h_m / 1000.0:.6f}'", "MAKE_EPHEM": "'YES'",
                  "EPHEM_TYPE": "'OBSERVER'", "START_TIME": f"'{a:%Y-%m-%d %H:%M}'",
                  "STOP_TIME": f"'{b:%Y-%m-%d %H:%M}'", "STEP_SIZE": f"'{step}'", "QUANTITIES": "'4,13'",
                  "ANG_FORMAT": "'DEG'", "CSV_FORMAT": "'YES'", "APPARENT": "'AIRLESS'", "TIME_DIGITS": "'MINUTES'"}
        key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:20]
        f = cache_dir / f"horizons_{body}_{key}.txt"
        if not f.exists():
            url = HORIZONS_API + "?" + urllib.parse.urlencode(params)
            for attempt in range(4):
                try:
                    with urllib.request.urlopen(url, timeout=180) as r:
                        txt = r.read().decode()
                    break
                except Exception:  # noqa: BLE001
                    if attempt == 3:
                        raise
                    time.sleep(5 * (attempt + 1))
            if "$$SOE" not in txt:
                raise RuntimeError(f"Horizons error for body {body}: {txt[-800:]}")
            f.write_text(txt); time.sleep(1.0)
        txt = f.read_text()
        raw_files.append({"file": f.name, "sha256": sha256(f)})
        lines = txt.splitlines(); soe = lines.index("$$SOE"); header = None
        for ln in lines[soe - 3:soe]:
            if "Date__" in ln:
                header = [c.strip() for c in ln.split(",")]
        ia = next(i for i, c in enumerate(header) if c.startswith("Azi"))
        ie = next(i for i, c in enumerate(header) if c.startswith("Elev"))
        idm = next(i for i, c in enumerate(header) if c.startswith("Ang-diam"))
        for ln in lines[soe + 1: lines.index("$$EOE")]:
            c = [x.strip() for x in ln.split(",")]
            if times and c[0] == times[-1]:
                continue
            times.append(c[0]); az.append(float(c[ia])); el.append(float(c[ie])); diam.append(float(c[idm]))
    return {"time": times, "az": np.array(az), "el": np.array(el), "ang_diam_arcsec": np.array(diam), "raw": raw_files}


def disc_fraction_above(elev_deg, horizon_deg, radius_deg):
    u = np.clip((np.asarray(elev_deg) - horizon_deg) / radius_deg, -1.0, 1.0)
    return (np.arccos(-u) + u * np.sqrt(1 - u * u)) / math.pi


def visibility(hz, sun, earth):
    hs = hz.at(sun["az"]); he = hz.at(earth["az"])
    sun_centre = sun["el"] > hs; earth_centre = earth["el"] > he
    return {"sun_centre_pct": 100 * float(np.mean(sun_centre)), "earth_centre_pct": 100 * float(np.mean(earth_centre)),
            "both_centre_pct": 100 * float(np.mean(sun_centre & earth_centre)), "n_steps": int(len(sun_centre))}
