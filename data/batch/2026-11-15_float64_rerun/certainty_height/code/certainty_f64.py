"""Re-run of the polaris_batch v2 Certainty Height sweep (Site04 ROI3, nominal + 20 clones, 10 masts) with the batch's own
definitions, in two precisions: float32 heights (as the batch did; must reproduce the published sidecar) and float64 heights
(the fix in LONG_FEATURES_2026-11-15 §0). Ephemeris: the bundle's own Horizons Sun/Earth az/el for Site04 ROI3 (337 samples)."""
import json, math, sys, time
import numpy as np, rasterio
from scipy.ndimage import map_coordinates
from pathlib import Path

R = 1737400.0
ROOT = Path(__file__).parent
import os
SITE = os.environ.get('SITE', 'site04_roi3')
LON0, LAT0 = {'site04_roi3': (-156.32023, -89.78012), 'site01_roi6': (-137.3813, -89.47409)}[SITE]
MASTS = [1.0, 1.25, 1.5, 1.75, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0] if SITE == 'site04_roi3' else [1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0]
TILE, CL = ('Site04', 'clones') if SITE == 'site04_roi3' else ('Site01', 'clones01')


def ll2ps(lon, lat):
    lon = np.radians(lon); c = np.pi / 2 + np.radians(lat); rho = 2 * R * np.tan(c / 2)
    return rho * np.sin(lon), rho * np.cos(lon)


class Dem:
    def __init__(self, p, dtype):
        with rasterio.open(p) as d:
            self.z = d.read(1).astype(dtype)
            if d.nodata is not None: self.z[self.z == d.nodata] = np.nan
            self.z[~np.isfinite(self.z)] = np.nan
            self.inv = ~d.transform
    def s(self, x, y):
        col, row = self.inv * (x, y)
        return map_coordinates(self.z, [np.ravel(row) - 0.5, np.ravel(col) - 0.5], order=1, mode='constant', cval=np.nan).reshape(np.shape(x))


def destination(lon0, lat0, az, d):
    p1, l1 = math.radians(lat0), math.radians(lon0)
    th = np.radians(az)[:, None]; dl = (d / R)[None, :]
    sp2 = math.sin(p1) * np.cos(dl) + math.cos(p1) * np.sin(dl) * np.cos(th)
    p2 = np.arcsin(np.clip(sp2, -1, 1))
    l2 = l1 + np.arctan2(np.sin(th) * np.sin(dl) * math.cos(p1), np.cos(dl) - math.sin(p1) * sp2)
    return np.degrees(l2), np.degrees(p2)


def horizons(near, far, masts, n_az=720):
    x0, y0 = ll2ps(np.array([LON0]), np.array([LAT0]))
    z0 = float(near.s(x0, y0)[0])
    d = np.concatenate([np.arange(1.0, 25000.0, 1.0), np.arange(25000.0, 280001.0, 80.0)])
    az = (np.arange(n_az) + 0.5) * 360.0 / n_az
    th = d / R
    out = {m: np.empty(n_az) for m in masts}
    for s in range(0, n_az, 60):
        lon, lat = destination(LON0, LAT0, az[s:s + 60], d)
        x, y = ll2ps(lon, lat)
        hn = near.s(x, y); hf = far.s(x, y)
        h = np.where(np.isfinite(hn), hn, hf)
        for m in masts:
            h0 = z0 + m   # same arithmetic as the batch: R_MOON + h in the array's dtype
            r0, r = R + h0, R + h
            e = np.degrees(np.arctan2(r * np.cos(th) - r0, r * np.sin(th)))
            out[m][s:s + 60] = np.where(np.isfinite(e), e, -np.inf).max(1)
    return az, out, z0


def at(az_bins, elev, a):
    step = 360.0 / len(az_bins)
    q = np.mod(a - az_bins[0], 360.0) / step
    i0 = np.floor(q).astype(int) % len(az_bins); i1 = (i0 + 1) % len(az_bins); f = q - np.floor(q)
    return elev[i0] * (1 - f) + elev[i1] * f


if __name__ == '__main__':
    dtype = {'f32': np.float32, 'f64': np.float64}[sys.argv[1]]
    b = json.load(open('/home/claude/px/web/public/bundles/polaris-x5d-roi-2026-11-14-v2.json'))
    ds = [d for d in b['datasets'] if d['siteId'] == SITE][0]
    S = ds['ephemeris']['samples']
    saz = np.array([s['sun']['az'] for s in S]); sel = np.array([s['sun']['el'] for s in S])
    eaz = np.array([s['earth']['az'] for s in S]); eel = np.array([s['earth']['el'] for s in S])
    far = Dem(ROOT / 'pgda90/LDEM_80S_80MPP_ADJ.TIF', dtype)
    maps = [('nominal', ROOT / f'pgda78/{TILE}_final_adj_5mpp_surf.tif')] + [
        (f'clone_{n:04d}', ROOT / f'pgda78/{CL}/{TILE}_final_adj_5mpp_{n:04d}_err.tif') for n in range(1, 21)]
    rows = []
    t0 = time.time()
    for name, p in maps:
        near = Dem(p, dtype)
        az, hz, z0 = horizons(near, far, MASTS)
        for m in MASTS:
            hs, he = at(az, hz[m], saz), at(az, hz[m], eaz)
            sun = sel > hs; earth = eel > he
            rows.append(dict(dem=name, mast_m=m, z0=z0, sun_centre_pct=100 * sun.mean(), both_centre_pct=100 * (sun & earth).mean(),
                             sun_samples=int(sun.sum()), both_samples=int((sun & earth).sum()),
                             sun_margin_min=float(np.min(sel - hs)) if m == 1.0 else None))
        print(name, round(time.time() - t0), [round(r['sun_centre_pct'], 3) for r in rows if r['dem'] == name][:3], flush=True)
    json.dump(dict(dtype=sys.argv[1], n_samples=len(S), rows=rows), open(ROOT / (f'certainty_{sys.argv[1]}.json' if SITE == 'site04_roi3' else f'certainty_{SITE}_{sys.argv[1]}.json'), 'w'), indent=0)
    print('done', round(time.time() - t0))
