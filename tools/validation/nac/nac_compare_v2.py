"""Confirmatory illumination comparison v2: POLARIS model vs observed LROC NAC images (NAC_PROTOCOL_V2.md + amendment A1, frozen)."""
import hashlib, json, math, re, sys, time
from pathlib import Path
import numpy as np, rasterio
from scipy.ndimage import map_coordinates
from multiprocessing import Pool

ROOT = Path(__file__).parent
for doc in ['NAC_PROTOCOL_V2', 'NAC_PROTOCOL_V2_A1']:
    if hashlib.sha256((ROOT / f'{doc}.md').read_bytes()).hexdigest() != (ROOT / f'{doc}.sha256').read_text().split()[0]:
        sys.exit(f'{doc} changed since freeze; refusing to run')
FROZEN = {d: (ROOT / f'{d}.sha256').read_text().split()[0] for d in ['NAC_PROTOCOL_V2', 'NAC_PROTOCOL_V2_A1']}

R = 1737400.0
GRID = 25.0
AREAS = {
    'C_site07_roi1': dict(tile='pgda78/Site07_final_adj_5mpp_surf.tif', lat=-88.8063, lon=123.54887, radius=1000.0, xmax=None, region=8),
    'D_site11_roi1': dict(tile='pgda78/Site11_final_adj_5mpp_surf.tif', lat=-88.66821, lon=-68.38199, radius=1000.0, xmax=None, region=9),
}
SHADOW_MAX, LIT_MIN = 0.0020, 0.0040
NEAR_STEP, FAR_STEP, FAR_MAX = 2.5, 80.0, 200000.0
NEAR_CRIT = 0.5


def ll2ps(lon, lat):
    lon = np.radians(lon); c = np.pi / 2 + np.radians(lat); rho = 2 * R * np.tan(c / 2)
    return rho * np.sin(lon), rho * np.cos(lon)


def ps2ll(x, y):
    rho = np.hypot(x, y); c = 2 * np.arctan(rho / (2 * R))
    return np.degrees(np.arctan2(x, y)), np.degrees(-(np.pi / 2 - c))


class Dem:
    def __init__(self, p):
        with rasterio.open(ROOT / p) as d:
            self.z = d.read(1).astype(np.float64)
            if d.nodata is not None: self.z[self.z == d.nodata] = np.nan
            self.inv = ~d.transform; self.b = d.bounds
    def sample(self, x, y):
        col, row = self.inv * (x, y)
        return map_coordinates(self.z, [np.ravel(row) - 0.5, np.ravel(col) - 0.5], order=1, mode='constant', cval=np.nan).reshape(np.shape(x))
    def inside(self, x, y):
        return (x > self.b.left + 10) & (x < self.b.right - 10) & (y > self.b.bottom + 10) & (y < self.b.top - 10)


def dest(lon0, lat0, az, d):
    """great-circle points from (lon0,lat0) [deg] along az [deg] at distances d [m]; az, lon0, lat0 broadcast with d."""
    p1, l1, th, dl = np.radians(lat0), np.radians(lon0), np.radians(az), d / R
    sp2 = np.sin(p1) * np.cos(dl) + np.cos(p1) * np.sin(dl) * np.cos(th)
    p2 = np.arcsin(np.clip(sp2, -1, 1))
    l2 = l1 + np.arctan2(np.sin(th) * np.sin(dl) * np.cos(p1), np.cos(dl) - np.sin(p1) * sp2)
    return np.degrees(l2), np.degrees(p2)


def elev(h0, h, d):
    a = d / R
    return np.degrees(np.arctan2((R + h) * np.cos(a) - (R + h0), (R + h) * np.sin(a)))


def horizon(near, far, lon, lat, h0, az):
    """max terrain elevation angle along az for points (vectors lon, lat, h0, az)."""
    dn = np.arange(5.0, 12000.0, NEAR_STEP)
    best = np.full(lon.shape, -90.0)
    for k in range(0, len(dn), 400):
        d = dn[k:k + 400][None, :]
        L, P = dest(lon[:, None], lat[:, None], az[:, None], d)
        x, y = ll2ps(L, P)
        h = near.sample(x, y)
        ok = near.inside(x, y) & np.isfinite(h)
        e = np.where(ok, elev(h0[:, None], np.where(ok, h, 0), d), -90.0)
        best = np.maximum(best, e.max(1))
    df = np.arange(0.0, FAR_MAX, FAR_STEP)
    for k in range(0, len(df), 500):
        d = df[k:k + 500][None, :]
        L, P = dest(lon[:, None], lat[:, None], az[:, None], d)
        x, y = ll2ps(L, P)
        inner = near.inside(x, y)
        h = far.sample(x, y)
        ok = (~inner) & np.isfinite(h) & (d > 0)
        e = np.where(ok, elev(h0[:, None], np.where(ok, h, 0), np.maximum(d, 1)), -90.0)
        best = np.maximum(best, e.max(1))
    return best


import spiceypy as sp
for k in ['naif0012.tls', 'de440s.bsp', 'moon_pa_de440_200625.bpc', 'moon_de440_250416.tf', 'pck00011.tpc']: sp.furnsh(str(ROOT / 'spice' / k))


def sun_vec(et):
    s, _ = sp.spkpos('SUN', et, 'MOON_ME', 'LT+S', 'MOON'); return np.array(s) * 1000.0


def sun_azel(s, lon, lat, h):
    lo, la = np.radians(lon), np.radians(lat)
    up = np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], -1)
    east = np.stack([-np.sin(lo), np.cos(lo), np.zeros_like(lo)], -1)
    north = np.cross(up, east)
    v = s[None, :] - up * (R + h)[:, None]; v /= np.linalg.norm(v, axis=1)[:, None]
    el = np.degrees(np.arcsin(np.sum(v * up, 1)))
    az = np.degrees(np.arctan2(np.sum(v * east, 1), np.sum(v * north, 1))) % 360
    return az, el


def area_points(a, near):
    x0, y0 = ll2ps(a['lon'], a['lat'])
    g = np.arange(-a['radius'], a['radius'] + 1e-6, GRID)
    X, Y = np.meshgrid(x0 + g, y0 + g)
    m = np.hypot(X - x0, Y - y0) <= a['radius']
    if a['xmax'] is not None: m &= X <= a['xmax']
    x, y = X[m], Y[m]
    h = near.sample(x, y)
    ok = np.isfinite(h)
    return x[ok], y[ok], h[ok]


def observe(img_path, x, y):
    """DN at the point pixel and the lit/shadow/ambiguous class, with the 3x3 edge rule."""
    with rasterio.open(img_path) as d:
        inv = ~d.transform; z = d.read(1).astype(np.float64)
    col, row = inv * (x, y); c = np.floor(col).astype(int); r = np.floor(row).astype(int)
    H, W = z.shape
    inb = (c >= 1) & (c < W - 1) & (r >= 1) & (r < H - 1)
    dn = np.full(x.shape, np.nan); dn[inb] = z[r[inb], c[inb]]
    valid = inb & np.isfinite(dn) & (dn > 0)
    if valid.sum() < 200: return None
    p90 = float(np.percentile(dn[valid], 90))
    cls = np.full(x.shape, 'x', dtype='<U1')
    lit_t, sh_t = LIT_MIN, SHADOW_MAX
    cls[valid & (dn >= lit_t)] = 'L'; cls[valid & (dn <= sh_t)] = 'S'
    # 3x3 edge rule
    nb_l = np.zeros(x.shape, bool); nb_s = np.zeros(x.shape, bool)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            v = np.full(x.shape, np.nan); v[inb] = z[r[inb] + dr, c[inb] + dc]
            nb_l |= np.isfinite(v) & (v >= lit_t); nb_s |= np.isfinite(v) & (v > 0) & (v <= sh_t)
    cls[valid & nb_l & nb_s] = 'e'
    return dict(dn=dn, cls=cls, valid=valid, p90=p90)


def run_image(args):
    an, img, path, svec = args
    out = {}
    for an2, (x, y, h, lon, lat, near_p) in POINTS.items():
        if an2 != an: continue
        o = observe(path, x, y)
        if o is None: continue
        sel = np.where(np.isin(o['cls'], ['L', 'S']))[0]
        if len(sel) == 0: continue
        az, el = sun_azel(np.asarray(svec), lon[sel], lat[sel], h[sel])
        hz = horizon(DEMS[near_p], FAR, lon[sel], lat[sel], h[sel] + 0.05, az)
        out[an2] = dict(idx=sel.tolist(), obs=o['cls'][sel].tolist(), margin=np.round(el - hz, 4).tolist(), el=np.round(el, 4).tolist(),
                       az=np.round(az, 3).tolist(), n_valid=int(o['valid'].sum()), n_amb=int(np.sum(o['cls'] == 'x') - np.sum(~o['valid'])), n_edge=int(np.sum(o['cls'] == 'e')))
    return img, out


DEMS = {a['tile']: Dem(a['tile']) for a in AREAS.values()}
FAR = Dem('pgda90/LDEM_80S_80MPP_ADJ.TIF')
POINTS = {}
for an, a in AREAS.items():
    x, y, h = area_points(a, DEMS[a['tile']])
    lon, lat = ps2ll(x, y)
    POINTS[an] = (x, y, h, lon, lat, a['tile'])

def et_from_id(img):
    """amendment A1 (region 8 only): ET from the LROC product ID, linear fit to the region 6 + 9 camera files"""
    n = int(re.match(r'M(\d+)', img).group(1))
    return 0.9999999698934682 * n + 198632811.7400536 if n < 10**9 else 0.9999999996511174 * n - 701367195.2147683


if __name__ == '__main__':
    todo, missing = [], {}
    c9 = json.load(open(ROOT / 'nac9_cams.json'))
    for r in c9:
        p = ROOT / 'nac9' / f"{r['img']}.tif"
        if p.exists() and p.stat().st_size == r['bytes']: todo.append(('D_site11_roi1', r['img'], str(p), sun_vec(r['et']).tolist(), r['et'], 'camera json'))
        else: missing['D'] = missing.get('D', 0) + 1
    i8 = json.load(open(ROOT / 'nac8_imgs.json')) if (ROOT / 'nac8_imgs.json').exists() else []
    for r in i8:
        p = ROOT / 'nac8' / Path(r['tif']).name
        if p.exists() and p.stat().st_size == r['tif_bytes']:
            et = et_from_id(r['img']); todo.append(('C_site07_roi1', r['img'], str(p), sun_vec(et).tolist(), et, 'product id (A1)'))
        else: missing['C'] = missing.get('C', 0) + 1
    if not i8: missing['C'] = 'no image list'
    print({k: len(v[0]) for k, v in POINTS.items()}, 'images', len(todo), 'missing', missing, flush=True)
    meta = {f'{t[0]}|{t[1]}': dict(et=t[4], time_source=t[5]) for t in todo}
    res = {}
    t0 = time.time()
    with Pool(2) as pool:
        for i, (img, out) in enumerate(pool.imap_unordered(run_image, [t[:4] for t in todo])):
            for an, v in out.items(): res[f'{an}|{img}'] = v
            print(i, img, {k: len(v['idx']) for k, v in out.items()}, round(time.time() - t0), flush=True)
    json.dump(dict(protocol_sha256=FROZEN, missing=missing, meta=meta,
                   points={k: dict(x=v[0].tolist(), y=v[1].tolist(), h=np.round(v[2], 3).tolist()) for k, v in POINTS.items()}, images=res),
              open(ROOT / 'nac_v2_results.json', 'w'))
    print('done', round(time.time() - t0))
