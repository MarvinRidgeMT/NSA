"""POLARIS-X batch science core: DEMs, terrain horizon, JPL Horizons, visibility.

Conventions (all checked in tests/test_core.py):
- Moon sphere R = 1737400 m. PGDA LOLA DEM heights are metres relative to that sphere.
- Rasters are south polar stereographic (MOON_ME / DE421), read via their own CRS.
- Azimuth = local bearing clockwise from local north (same as JPL Horizons 'Azi').
  Rays are great circles built in lat/lon, so no grid-azimuth conversion is needed.
- Elevation angle of a terrain point uses Moon-centred geometry (curvature included).

14 Nov 12:00 ET change: compute_horizon takes near_fine_step / near_fine_m. With the default
5 m step (one DEM post) a 1 m-mast skyline is not converged when the blocking terrain is
within tens of metres (Site04 ROI3: Sun 98.5 % at 5 m -> 94.4 % at 1 m). The clone sweep now
samples every near_fine_step (1 m) out to near_fine_m (1 km), then the DEM pixel.
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


# --------------------------------------------------------------------------- downloads
def download(url: str, dest: Path, retries: int = 3) -> Path:
    """Download a whole file (no range reads: they were unreliable through proxies)."""
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
                want = int(r.headers.get("Content-Length") or -1)
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            got = tmp.stat().st_size
            if want >= 0 and got != want:  # truncated transfers produced unreadable clone TIFFs (14 Nov)
                raise IOError(f"short download {got} != {want} bytes for {url}")
            tmp.rename(dest)
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


# --------------------------------------------------------------------------- DEMs
@dataclass
class Dem:
    path: Path
    z: np.ndarray            # float32, NaN where nodata
    inv: object              # affine inverse transform (x, y) -> (col, row)
    to_grid: pyproj.Transformer
    res: float

    @classmethod
    def open(cls, path: Path) -> "Dem":
        with rasterio.open(path) as ds:
            z = ds.read(1).astype(np.float32)
            if ds.nodata is not None:
                z[z == ds.nodata] = np.nan
            z[~np.isfinite(z)] = np.nan
            return cls(Path(path), z, ~ds.transform,
                       pyproj.Transformer.from_crs(LONLAT, ds.crs, always_xy=True),
                       float(abs(ds.res[0])))

    def sample_lonlat(self, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
        x, y = self.to_grid.transform(lon, lat)
        return self.sample_xy(x, y)

    def sample_xy(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        col, row = self.inv * (np.asarray(x), np.asarray(y))
        # pixel-centre convention: affine maps to pixel corners, so subtract 0.5
        coords = np.vstack([np.ravel(row) - 0.5, np.ravel(col) - 0.5])
        v = map_coordinates(self.z, coords, order=1, mode="constant", cval=np.nan)
        # map_coordinates propagates NaN from any neighbour, which is what we want
        return v.reshape(np.shape(x))


def site_files(site: str, root: Path) -> dict:
    d = Path(root) / "pgda78" / site
    return {
        "surf": (f"{PGDA78}/{site}/{site}_final_adj_5mpp_surf.tif", d / f"{site}_final_adj_5mpp_surf.tif"),
        "toterr": (f"{PGDA78}/{site}/{site}_final_adj_5mpp_toterr.tif", d / f"{site}_final_adj_5mpp_toterr.tif"),
    }


def clone_file(site: str, n: int, root: Path):
    """PGDA 78 clone n. NOTE: despite the '_err' suffix, each clone is a COMPLETE alternative
    DEM (heights ~ the nominal surface), verified 2026-11-14 on Site01 clone 0001; use it directly."""
    name = f"{site}_final_adj_5mpp_{n:04d}_err.tif"
    return f"{PGDA78}/{site}/Clones/{name}", Path(root) / "pgda78" / site / "Clones" / name


# --------------------------------------------------------------------------- geometry
def destination(lon0: float, lat0: float, az_deg: np.ndarray, dist_m: np.ndarray):
    """Great-circle destination points. az: (A,), dist: (D,) -> lon, lat: (A, D) in degrees."""
    phi1, lam1 = math.radians(lat0), math.radians(lon0)
    th = np.radians(az_deg)[:, None]
    dl = (np.asarray(dist_m) / R_MOON)[None, :]
    sp2 = math.sin(phi1) * np.cos(dl) + math.cos(phi1) * np.sin(dl) * np.cos(th)
    phi2 = np.arcsin(np.clip(sp2, -1, 1))
    lam2 = lam1 + np.arctan2(np.sin(th) * np.sin(dl) * math.cos(phi1), np.cos(dl) - math.sin(phi1) * sp2)
    return np.degrees(lam2), np.degrees(phi2)


def elevation_angle_deg(h0: float, h: np.ndarray, dist_m: np.ndarray) -> np.ndarray:
    """Apparent elevation of a surface point at height h, great-circle distance d, seen from height h0."""
    th = np.asarray(dist_m) / R_MOON
    r0, r = R_MOON + h0, R_MOON + h
    return np.degrees(np.arctan2(r * np.cos(th) - r0, r * np.sin(th)))


@dataclass
class Horizon:
    az: np.ndarray           # bin centres, deg
    elev: np.ndarray         # horizon elevation, deg
    dist: np.ndarray         # distance of the obstructing sample, m (NaN if none)
    complete: np.ndarray     # bool: ray reached max range with DEM coverage throughout
    h0: float                # observer height above sphere, m

    def at(self, az_deg: np.ndarray) -> np.ndarray:
        step = 360.0 / len(self.az)
        a = np.mod(np.asarray(az_deg) - self.az[0], 360.0) / step
        i0 = np.floor(a).astype(int) % len(self.az)
        i1 = (i0 + 1) % len(self.az)
        f = a - np.floor(a)
        return self.elev[i0] * (1 - f) + self.elev[i1] * f

    def to_json(self) -> dict:
        return {"az_deg": self.az.round(3).tolist(), "elev_deg": np.round(self.elev, 4).tolist(),
                "obstruction_dist_m": np.round(self.dist, 1).tolist(),
                "complete": self.complete.tolist(), "observer_height_m": self.h0}


def ray_distances(near_step, near_max_m, far_step, far_max_m, near_fine_step=None, near_fine_m=0.0):
    if near_fine_step and near_fine_m > 0:
        d0 = np.arange(near_fine_step, near_fine_m, near_fine_step)
        d1 = np.arange(near_fine_m, near_max_m, near_step)
    else:
        d0, d1 = np.empty(0), np.arange(near_step, near_max_m, near_step)
    return np.concatenate([d0, d1, np.arange(near_max_m, far_max_m + 1, far_step)])


def compute_horizon(lon0: float, lat0: float, near: Dem, far: Dem, mast_m: float = 1.0,
                    n_az: int = 720, near_max_m: float = 25000.0, far_max_m: float = 280000.0,
                    near_step: float | None = None, far_step: float | None = None,
                    near_fine_step: float | None = None, near_fine_m: float = 0.0) -> Horizon:
    near_step = near_step or near.res
    far_step = far_step or far.res
    z0 = float(near.sample_lonlat(np.array([lon0]), np.array([lat0]))[0])
    if not np.isfinite(z0):
        z0 = float(far.sample_lonlat(np.array([lon0]), np.array([lat0]))[0])
    if not np.isfinite(z0):
        raise ValueError(f"observer {lon0},{lat0} outside DEM coverage")
    h0 = z0 + mast_m
    az = (np.arange(n_az) + 0.5) * 360.0 / n_az
    d = ray_distances(near_step, near_max_m, far_step, far_max_m, near_fine_step, near_fine_m)
    lon, lat = destination(lon0, lat0, az, d)
    x, y = near.to_grid.transform(lon, lat)
    hn = near.sample_xy(x, y)
    hf = far.sample_xy(x, y) if far.to_grid.target_crs == near.to_grid.target_crs else far.sample_lonlat(lon, lat)
    h = np.where(np.isfinite(hn), hn, hf)
    e = elevation_angle_deg(h0, h, d[None, :])
    e_masked = np.where(np.isfinite(e), e, -np.inf)
    k = np.argmax(e_masked, axis=1)
    elev = e_masked[np.arange(n_az), k]
    dist = np.where(np.isfinite(elev), d[k], np.nan)
    elev = np.where(np.isfinite(elev), elev, np.nan)
    complete = np.isfinite(h).all(axis=1)
    return Horizon(az, elev, dist, complete, h0)


# --------------------------------------------------------------------------- JPL Horizons
def horizons_observer(body: str, lon: float, lat: float, h_m: float, start: str, stop: str, step: str,
                      cache_dir: Path, chunk_years: int = 4) -> dict:
    """Topocentric apparent az/el + angular diameter of body ('10' Sun, '399' Earth) from a lunar site.

    Raw responses are cached (and hashed) so every run is reproducible offline."""
    from datetime import datetime
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    t0, t1 = datetime.fromisoformat(start), datetime.fromisoformat(stop)
    edges = [t0]
    while edges[-1] < t1:
        nxt = edges[-1].replace(year=edges[-1].year + chunk_years)
        edges.append(min(nxt, t1))
    times, az, el, diam, raw_files = [], [], [], [], []
    for a, b in zip(edges[:-1], edges[1:]):
        params = {
            "format": "text", "COMMAND": f"'{body}'", "CENTER": "'coord@301'", "COORD_TYPE": "'GEODETIC'",
            "SITE_COORD": f"'{lon:.6f},{lat:.6f},{h_m / 1000.0:.6f}'", "MAKE_EPHEM": "'YES'",
            "EPHEM_TYPE": "'OBSERVER'", "START_TIME": f"'{a:%Y-%m-%d %H:%M}'",
            "STOP_TIME": f"'{b:%Y-%m-%d %H:%M}'", "STEP_SIZE": f"'{step}'", "QUANTITIES": "'4,13'",
            "ANG_FORMAT": "'DEG'", "CSV_FORMAT": "'YES'", "APPARENT": "'AIRLESS'", "TIME_DIGITS": "'MINUTES'",
        }
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
            f.write_text(txt)
            time.sleep(1.0)  # be polite to JPL
        txt = f.read_text()
        raw_files.append({"file": f.name, "sha256": sha256(f)})
        header = None
        lines = txt.splitlines()
        soe = lines.index("$$SOE")
        for ln in lines[soe - 3:soe]:
            if "Date__" in ln:
                header = [c.strip() for c in ln.split(",")]
        if header is None:
            raise RuntimeError("Horizons CSV header not found")
        ia = next(i for i, c in enumerate(header) if c.startswith("Azi"))
        ie = next(i for i, c in enumerate(header) if c.startswith("Elev"))
        idm = next(i for i, c in enumerate(header) if c.startswith("Ang-diam"))
        for ln in lines[soe + 1: lines.index("$$EOE")]:
            c = [x.strip() for x in ln.split(",")]
            if times and c[0] == times[-1]:
                continue  # chunk boundary duplicate
            times.append(c[0]); az.append(float(c[ia])); el.append(float(c[ie])); diam.append(float(c[idm]))
    return {"time": times, "az": np.array(az), "el": np.array(el), "ang_diam_arcsec": np.array(diam),
            "raw": raw_files}


# --------------------------------------------------------------------------- visibility
def disc_fraction_above(elev_deg, horizon_deg, radius_deg):
    """Fraction of a circular disc above a locally straight horizon line."""
    u = np.clip((np.asarray(elev_deg) - horizon_deg) / radius_deg, -1.0, 1.0)
    return (np.arccos(-u) + u * np.sqrt(1 - u * u)) / math.pi


def visibility(hz: Horizon, sun: dict, earth: dict) -> dict:
    hs = hz.at(sun["az"]); he = hz.at(earth["az"])
    rs = sun["ang_diam_arcsec"] / 7200.0
    re = earth["ang_diam_arcsec"] / 7200.0
    sun_frac = disc_fraction_above(sun["el"], hs, rs)
    sun_centre = sun["el"] > hs
    earth_any = earth["el"] + re > he          # PGDA 69 convention: any part of the disc
    earth_centre = earth["el"] > he
    return {
        "sun_disc_mean_pct": 100 * float(np.mean(sun_frac)),
        "sun_centre_pct": 100 * float(np.mean(sun_centre)),
        "earth_any_pct": 100 * float(np.mean(earth_any)),
        "earth_centre_pct": 100 * float(np.mean(earth_centre)),
        "both_centre_pct": 100 * float(np.mean(sun_centre & earth_centre)),
        "n_steps": int(len(sun_frac)),
        "_sun_frac": sun_frac, "_earth_any": earth_any,
    }


def load_rois(csv_path: Path) -> list[dict]:
    import csv
    with open(csv_path) as f:
        return [{**r, "roi": int(r["roi"]), "lat_deg": float(r["lat_deg"]), "lon_deg_east": float(r["lon_deg_east"]),
                 "avg_sun_pct_18p6yr": float(r["avg_sun_pct_18p6yr"]),
                 "avg_earth_pct_18p6yr": float(r["avg_earth_pct_18p6yr"])} for r in csv.DictReader(f)]


# --------------------------------------------------------------------------- direction transfer
def _enu(lon_deg: float, lat_deg: float):
    lam, phi = math.radians(lon_deg), math.radians(lat_deg)
    e = np.array([-math.sin(lam), math.cos(lam), 0.0])
    n = np.array([-math.sin(phi) * math.cos(lam), -math.sin(phi) * math.sin(lam), math.cos(phi)])
    u = np.array([math.cos(phi) * math.cos(lam), math.cos(phi) * math.sin(lam), math.sin(phi)])
    return e, n, u


def transfer_azel(az_deg, el_deg, lon_a, lat_a, lon_b, lat_b):
    """Re-express a distant body's direction, given as az/el at site A, in site B's local frame.

    Valid when the body is far compared with |A-B| (Sun: always; Earth: parallax ~ |A-B|/384,400 km,
    i.e. about 0.0015 deg per 10 km). Near the pole this is NOT negligible to skip: the local
    north direction rotates with longitude, so raw azimuths cannot be reused between sites."""
    ea, na, ua = _enu(lon_a, lat_a)
    eb, nb, ub = _enu(lon_b, lat_b)
    az, el = np.radians(az_deg), np.radians(el_deg)
    d = (np.cos(el) * np.sin(az))[:, None] * ea + (np.cos(el) * np.cos(az))[:, None] * na + np.sin(el)[:, None] * ua
    el_b = np.degrees(np.arcsin(np.clip(d @ ub, -1, 1)))
    az_b = np.degrees(np.arctan2(d @ eb, d @ nb)) % 360.0
    return az_b, el_b
