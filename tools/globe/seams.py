"""Seam QA for the science pyramid (prompt §2.2 item 4, plan §7).

For every ordered product pair (hi = higher merge priority, lo) whose footprints overlap in a zone, on the grid of the
level matching the coarser of the two native postings:
  * the finer product is block-averaged to that posting (removes the resolution difference, leaves real disagreement);
  * the seam band = pixels of hi within FEATHER_PX level pixels of hi's own valid-data edge where lo also has data
    (exactly where the merge blends the two);
  * delta = hi - lo in the band (after any applied co-registration).
Reported per pair: N, signed median, median |delta|, p99 |delta|, max |delta|, and the extra slope the feather adds
(atan(p99 |delta| / (FEATHER_PX * pixel))). Plus the eq <-> polar overlap (55-60 deg), which compares the same
merged sources on two grids (a reprojection check), once both zones exist.

    python -m tools.globe.seams [--zones sp] [--check]

Writes $POLARIS_DATA/v2/pyramid/qa/seams.json, the committed numbers docs/v2/PYRAMID_QA.json (section "seams") and the
map web/public/globe/qa/seams_<zone>.png (git-ignored: derived from NASA rasters). --check exits 1 if a pair exceeds
its tolerance (tools/globe/tests/test_globe_seams.py does the same).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import sys
from pathlib import Path

import numpy as np

from science.terrain import stack as S
from tools.globe import pyramid as PY
from tools.globe import pyramid_products as PP

REPO = Path(__file__).resolve().parents[2]
QA_DOC = REPO / 'docs' / 'v2' / 'PYRAMID_QA.json'
MAP_DIR = REPO / 'web' / 'public' / 'globe' / 'qa'

FAMILY = {1: 'nac', 2: 'sfs', 3: 'lola', 4: 'kaguya', 5: 'lola', 6: 'sldem', 7: 'lola', 8: 'lola'}

# Tolerances on |hi - lo| in the seam band, both at lo's posting [decision, plan §7]. Reasons:
# - lola/lola: same LOLA altimetry, different gridding/crossover adjustment (PGDA 78 tiles are adjusted per site);
#   vertical agreement of LOLA products is a few metres (LOLA radial precision ~1 m, orbit-adjusted ~ few m), steep
#   crater walls at 80 m posting add binning differences -> median 2 m, p99 20 m.
# - sldem/lola: SLDEM2015 vertical accuracy ~3-4 m (Barker et al. 2016) plus Kaguya TC stereo noise -> 5 m / 40 m.
# - kaguya, nac, sfs vs lola: stereo / photoclinometry products, accuracy 3-10 m class -> 5 m / 40 m (provisional).
# - zone (eq vs polar grid of the same merge): reprojection only -> 0.5 m / 10 m.
# Revised 16 Nov 07:55 EST after investigation (plan §7: cause found before any change):
# - sldem/lola p99 40 -> 50 m. SLDEM2015 over LOLA LDEM_60N at the +60 deg edge measured p99 41.8 m (median 2.7 m),
#   LDEM_60S 21.7 m. The same pair disagrees as much AWAY from any seam (SLDEM vs LOLA global at 118 m posting:
#   p99 61 m at 30N, 75 m at the equator): LOLA gridded products interpolate between tracks where SLDEM has Kaguya TC
#   detail. The seam is no worse than the products' intrinsic disagreement; the 8-px feather (470 m at 59 m) limits
#   the added slope to atan(50 / 470) < 6 deg for the worst 1 % of band pixels.
# - zone p99 10 -> 20 m, median 0.5 -> 2 m. The eq and polar zones are not one grid resampled twice: at 55-60 deg
#   both show SLDEM, eq at its 59 m posting, polar resampled onto 80 m pixels (L4), so the 57.5 deg switch in
#   TerrainStack.sample carries a posting change. Measured sp/eq: median 1.14 m, p99 12.3 m.
TOLERANCES = {
    ('lola', 'lola'): {'median_abs_m': 2.0, 'p99_abs_m': 20.0},
    ('lola', 'sldem'): {'median_abs_m': 5.0, 'p99_abs_m': 50.0},
    ('kaguya', 'lola'): {'median_abs_m': 5.0, 'p99_abs_m': 40.0},
    ('kaguya', 'sldem'): {'median_abs_m': 5.0, 'p99_abs_m': 40.0},
    ('lola', 'nac'): {'median_abs_m': 5.0, 'p99_abs_m': 40.0},
    ('lola', 'sfs'): {'median_abs_m': 5.0, 'p99_abs_m': 40.0},
    ('zone', 'zone'): {'median_abs_m': 2.0, 'p99_abs_m': 20.0},
}
DEFAULT_TOL = {'median_abs_m': 5.0, 'p99_abs_m': 40.0}
MIN_N = 50                      # fewer band pixels than this: reported, not judged
MAX_KEEP = 2_000_000            # band samples kept per pair for percentiles (uniform subsample beyond)
CELL = {'polar': 10_000.0, 'eq': 0.5}   # map cell: 10 km (polar grid) / 0.5 deg (eq)


def tolerance(sid_a, sid_b):
    key = tuple(sorted((FAMILY.get(sid_a, 'other'), FAMILY.get(sid_b, 'other'))))
    return key, TOLERANCES.get(key, DEFAULT_TOL)


def _stats(d):
    a = np.abs(d)
    return {'n': int(d.size), 'median_signed_m': float(np.median(d)), 'median_abs_m': float(np.median(a)),
            'p99_abs_m': float(np.percentile(a, 99)), 'max_abs_m': float(a.max()),
            'rms_m': float(np.sqrt(np.mean(d * d)))}


def _covers(a, b, zone):
    """True if product a's rectangle (in this zone's own grid) contains product b's footprint bbox."""
    if PY.reader(a).kind != zone:
        return False
    ba, bb = PY.product_zone_bbox(a, zone), PY.product_zone_bbox(b, zone)
    return ba is not None and bb is not None and ba[0] <= bb[0] and ba[1] <= bb[1] and ba[2] >= bb[2] and ba[3] >= bb[3]


def pair_seam(hi, lo, zone, cells=None, feather_px=PY.FEATHER_PX, between=(), above=()):
    """Seam statistics of (hi over lo) in one zone, or None if they do not meet there. `between`: products whose
    priority lies between hi and lo; band pixels where any of them has data are excluded (there the merge blends hi
    with that product, not with lo), so only seams that exist in the merge are judged. `above`: products of higher
    priority than hi; pixels they cover are excluded too (the merge shows them there), and a pair whose hi lies
    entirely inside one of them is skipped."""
    if any(_covers(a, hi, zone) for a in above):
        return None
    Z = S.ZONES[zone]
    bh, bl = PY.product_zone_bbox(hi, zone), PY.product_zone_bbox(lo, zone)
    if bh is None or bl is None:
        return None
    if not (bh[0] < bl[2] and bh[2] > bl[0] and bh[1] < bl[3] and bh[3] > bl[1]):
        return None
    rl, rh = PY.reader(lo), PY.reader(hi)
    L = Z.level_for_res(max(rl.native_px_m(), rh.native_px_m()))     # compare at the coarser posting
    p = Z.pixel(L)
    pad = feather_px + 2
    m = pad * p
    box = (bh[0] - m, bh[1] - m, bh[2] + m, bh[3] + m)
    tiles = PY.tiles_for_bbox(zone, L, box)
    keep = []
    own = rh.kind == zone or (Z.kind == 'eq' and rh.kind == 'lonlat')
    for ix, iy in tiles:
        if own:
            tb = Z.tile_bounds(L, ix, iy)
            if bh[0] < tb[0] - m and bh[2] > tb[2] + m and bh[1] < tb[1] - m and bh[3] > tb[3] + m:
                continue                              # hi covers the padded tile: no hi edge here (no read needed)
        U, V = Z.pixel_centres(L, ix, iy, pad)
        lat, lon = Z.inverse(U, V)
        inz = Z.in_zone(lat)
        if not inz.any():
            continue
        h_hi, _, _ = rh.sample(lat, lon, Z.pixel_m(L))
        vh = np.isfinite(h_hi) & inz
        if not vh.any() or vh.all():
            continue                                  # no edge of hi in this padded tile
        h_lo, _, _ = rl.sample(lat, lon, Z.pixel_m(L))
        w = PY.feather_weight(vh, feather_px)
        band = vh & (w < 1.0) & np.isfinite(h_lo)
        for mid in list(between) + list(above):
            if not band.any():
                break
            bm = PY.product_zone_bbox(mid, zone)
            if bm is None:
                continue
            band &= ~np.isfinite(PY.reader(mid).sample(lat, lon, Z.pixel_m(L))[0])
        sl = (slice(pad, pad + Z.tile_px), slice(pad, pad + Z.tile_px))
        band = band[sl]
        if not band.any():
            continue
        d = (h_hi - h_lo)[sl][band]
        keep.append(d)
        if cells is not None:
            cu, cv = U[sl][band], V[sl][band]
            c = CELL[Z.kind]
            key = np.stack([np.floor((cu - Z.left) / c), np.floor((Z.top - cv) / c)], 1).astype(np.int64)
            for (kx, ky) in np.unique(key, axis=0):
                mm = (key[:, 0] == kx) & (key[:, 1] == ky)
                cells.setdefault((zone, int(kx), int(ky)), []).append(np.abs(d[mm]))
    if not keep:
        return None
    d = np.concatenate(keep)
    if d.size > MAX_KEEP:
        d = d[np.linspace(0, d.size - 1, MAX_KEEP).astype(np.int64)]
    st = _stats(d)
    fam, tol = tolerance(hi.source_id, lo.source_id)
    st.update({'hi': hi.product_id, 'lo': lo.product_id, 'hi_source_id': hi.source_id, 'lo_source_id': lo.source_id,
               'zone': zone, 'level': L, 'pixel_m': Z.pixel_m(L), 'feather_px': feather_px,
               'feather_extra_slope_p99_deg': math.degrees(math.atan(st['p99_abs_m'] / (feather_px * Z.pixel_m(L)))),
               'families': list(fam), 'tolerance': tol})
    st['judged'] = st['n'] >= MIN_N
    st['pass'] = (not st['judged']) or (st['median_abs_m'] <= tol['median_abs_m'] and st['p99_abs_m'] <= tol['p99_abs_m'])
    return st


def zone_seam(stack, step_deg=0.05):
    """eq vs polar zone in the 55-60 deg overlap, sampled on a lat/lon lattice (both hemispheres)."""
    out = []
    for pole, lats in (('sp', np.arange(-59.975, -55.0, step_deg)), ('np', np.arange(55.025, 60.0, step_deg))):
        if not stack.levels(pole) or not stack.levels('eq'):
            continue
        lon = np.arange(-179.975, 180.0, step_deg)
        La, Lo = np.meshgrid(lats, lon)
        qe = stack._query(La, Lo, zone='eq'); qp = stack._query(La, Lo, zone=pole)
        ok = np.isfinite(qe['height']) & np.isfinite(qp['height'])
        if ok.sum() < MIN_N:
            continue
        d = (qp['height'] - qe['height'])[ok]
        st = _stats(d)
        st.update({'hi': f'{pole} zone', 'lo': 'eq zone', 'zone': f'{pole}/eq', 'families': ['zone', 'zone'],
                   'tolerance': TOLERANCES[('zone', 'zone')], 'lattice_deg': step_deg, 'judged': True})
        t = st['tolerance']
        st['pass'] = st['median_abs_m'] <= t['median_abs_m'] and st['p99_abs_m'] <= t['p99_abs_m']
        out.append(st)
    return out


def run(zones=('sp', 'np', 'eq'), specs=None, root=None, write=True, maps=True, log=print):
    specs = specs if specs is not None else PP.all_products()
    root = Path(root) if root else PY.pyramid_root()
    coreg = PY.load_coreg(root)
    for s in specs:
        if s.product_id in coreg:
            s.coreg = coreg[s.product_id]
    order = sorted(specs, key=lambda s: s.priority)
    pairs, cells = [], {}
    for zone in zones:
        for i, hi in enumerate(order):
            for j in range(i + 1, len(order)):
                lo = order[j]
                st = pair_seam(hi, lo, zone, cells=cells, between=order[i + 1:j], above=order[:i])
                if st is not None:
                    pairs.append(st)
                    log(f"{zone} {hi.product_id} over {lo.product_id}: n={st['n']} median|d|={st['median_abs_m']:.2f} m "
                        f"p99={st['p99_abs_m']:.2f} m {'PASS' if st['pass'] else 'FAIL'}")
    try:
        stack = S.TerrainStack.open(root)
        zs = zone_seam(stack)
    except FileNotFoundError:
        zs = []
    for st in zs:
        log(f"zone seam {st['zone']}: n={st['n']} median|d|={st['median_abs_m']:.2f} p99={st['p99_abs_m']:.2f} "
            f"{'PASS' if st['pass'] else 'FAIL'}")
    res = {'created_utc': _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
           'label': 'SOURCE-BASED · UNVALIDATED (QA of the merge, not an accuracy assessment)',
           'method': __doc__.strip().split('\n\n')[1], 'feather_px': PY.FEATHER_PX,
           'tolerances': {'/'.join(k): v for k, v in TOLERANCES.items()}, 'default_tolerance': DEFAULT_TOL,
           'pairs': pairs, 'zone_seams': zs,
           'all_pass': all(p['pass'] for p in pairs + zs)}
    if write:
        qa = root / 'qa'; qa.mkdir(parents=True, exist_ok=True)
        cell_rows = [{'zone': z, 'cx': cx, 'cy': cy, 'n': int(sum(a.size for a in v)),
                      'p99_abs_m': float(np.percentile(np.concatenate(v), 99))} for (z, cx, cy), v in cells.items()]
        (qa / 'seams.json').write_text(json.dumps({**res, 'cells': cell_rows}, indent=1))
        update_qa_doc('seams', res)
        if maps:
            write_maps(cell_rows)
    return res


def update_qa_doc(section, payload):
    doc = json.loads(QA_DOC.read_text()) if QA_DOC.exists() else {}
    doc['_note'] = ('Numbers only (no rasters). Written by tools/globe/{seams,coverage,roughness}.py; '
                    'plan docs/v2/PHASE_1_PYRAMID_PLAN.md.')
    doc[section] = payload
    QA_DOC.write_text(json.dumps(doc, indent=1) + '\n')


# ---------------------------------------------------------------------------------------- PNG maps
def colormap(v, vmax):
    """Sequential light->dark ramp (magma-like stops), NaN -> transparent."""
    stops = np.array([[252, 253, 191], [254, 176, 120], [241, 96, 93], [183, 55, 121], [114, 31, 129], [44, 17, 95]], float)
    t = np.clip(np.asarray(v, float) / vmax, 0, 1) * (len(stops) - 1)
    i = np.clip(np.floor(t).astype(int), 0, len(stops) - 2)
    f = (t - i)[..., None]
    rgb = stops[i] * (1 - f) + stops[i + 1] * f
    a = np.where(np.isfinite(v), 255, 0)
    return np.concatenate([np.nan_to_num(rgb).astype(np.uint8), a[..., None].astype(np.uint8)], axis=-1)


def write_png(path, rgba):
    import rasterio
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    rgba = np.asarray(rgba, np.uint8)
    with rasterio.open(path, 'w', driver='PNG', width=rgba.shape[1], height=rgba.shape[0], count=rgba.shape[2],
                       dtype='uint8') as ds:
        ds.write(np.moveaxis(rgba, -1, 0))
    aux = Path(str(path) + '.aux.xml')
    if aux.exists():
        aux.unlink()


def write_maps(cell_rows, out_dir=MAP_DIR, vmax=20.0):
    for zone in ('sp', 'np', 'eq'):
        rows = [r for r in cell_rows if r['zone'] == zone]
        if not rows:
            continue
        Z = S.ZONES[zone]
        c = CELL[Z.kind]
        nx = int(round((Z.right - Z.left) / c)); ny = int(round((Z.top - Z.bottom) / c))
        img = np.full((ny, nx), np.nan)
        for r in rows:
            img[r['cy'], r['cx']] = r['p99_abs_m']
        ys, xs = np.nonzero(np.isfinite(img))
        # crop to the populated area (+ margin) so polar maps of small regions stay readable
        y0, y1 = max(0, ys.min() - 5), min(ny, ys.max() + 6); x0, x1 = max(0, xs.min() - 5), min(nx, xs.max() + 6)
        crop = img[y0:y1, x0:x1]
        scale = max(1, int(512 // max(crop.shape)))
        crop = np.kron(crop, np.ones((scale, scale)))
        write_png(Path(out_dir) / f'seams_{zone}.png', colormap(crop, vmax))
        meta = {'zone': zone, 'value': 'p99 |hi - lo| in the seam band per cell (m)', 'vmax_m': vmax,
                'cell': c, 'cell_units': 'm' if Z.kind == 'polar' else 'deg', 'crop_cells_x0y0x1y1': [int(x0), int(y0), int(x1), int(y1)],
                'pixels_per_cell': scale, 'crs_proj4': Z.proj4, 'label': 'SOURCE-BASED · UNVALIDATED'}
        (Path(out_dir) / f'seams_{zone}.json').write_text(json.dumps(meta, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.globe.seams')
    ap.add_argument('--zones', default='sp,np,eq')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args(argv)
    res = run(zones=tuple(a.zones.split(',')))
    if a.check and not res['all_pass']:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
