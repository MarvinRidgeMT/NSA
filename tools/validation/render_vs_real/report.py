"""docs/validation/RENDER_VS_REAL.md + gallery thumbnails from results/{selection.json, geometry.csv, scores.jsonl}.

    python -m tools.validation.render_vs_real.report

Gallery thumbnails (docs/validation/render_vs_real/*.png): small 8-bit crops (<= 240 px wide) of LROC NAC CDR data from the
NASA PDS archive (public domain per https://lroc.im-ldi.com/about/terms; credit NASA/GSFC/Arizona State University) next to the
POLARIS render twin, the difference, and the shadow-edge overlay. Dev split only.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import json
import math

import numpy as np

from .common import RENDER_DIR, RESULTS, ROOT, assert_dev, read_catalogue

DOC = ROOT / 'docs' / 'validation' / 'RENDER_VS_REAL.md'
GAL = ROOT / 'docs' / 'validation' / 'render_vs_real'
PRODUCTS = ['pgda78_5m', 'lola_ldem875s_5m', 'pgda90_80m', 'flat']
PNAME = {'pgda78_5m': 'PGDA 78 5 m', 'lola_ldem875s_5m': 'LOLA LDEM_875S 5 m', 'pgda90_80m': 'PGDA 90 LDEM 80 m',
         'flat': 'flat-sphere control'}
SITES = ['site04_roi3', 'site01_roi6', 'site07_roi1', 'site11_roi4']
METRICS = [('iouShadow', 'shadow IoU', 3), ('iouLit', 'lit IoU', 3), ('balancedAccuracy', 'bal. acc.', 3), ('kappa', 'κ', 3),
           ('edgeMedianM', 'edge median m', 1), ('edgeP90M', 'edge P90 m', 1), ('edgeUnmatchedFrac', 'edge unmatched', 3),
           ('edgeSignedMedianM', 'edge signed m', 1), ('ssim', 'SSIM', 3), ('wasserstein1', 'W1 (log10)', 3), ('jsdBits', 'JSD bits', 3)]


def load():
    scores = [json.loads(l) for l in (RESULTS / 'scores.jsonl').read_text().splitlines() if l.strip()]
    geo = list(csv.DictReader(open(RESULTS / 'geometry.csv')))
    sel = json.loads((RESULTS / 'selection.json').read_text())
    return scores, geo, sel


def q(v, p):
    v = [x for x in v if x is not None and isinstance(x, (int, float)) and math.isfinite(x)]
    return float(np.percentile(v, p)) if v else float('nan')


def fmt(x, d=3):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return '—'
    return f'{x:.{d}f}'


def boot_ci(diffs, seed='polaris-x-v2-boot', n=10_000):
    d = np.asarray([x for x in diffs if math.isfinite(x)], float)
    if len(d) < 2:
        return float('nan'), float('nan')
    rng = np.random.default_rng(int(hashlib.sha256(seed.encode()).hexdigest(), 16) % 2 ** 63)
    idx = rng.integers(0, len(d), (n, len(d)))
    meds = np.median(d[idx], axis=1)
    return float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))


def table_dist(recs, keys=METRICS):
    rows = ['| metric | n | median | IQR | P10 | P90 |', '|---|---|---|---|---|---|']
    for k, name, d in keys:
        v = [r.get(k) for r in recs]
        n = sum(1 for x in v if isinstance(x, (int, float)) and x is not None and math.isfinite(x))
        rows.append(f'| {name} | {n} | {fmt(q(v, 50), d)} | {fmt(q(v, 25), d)}–{fmt(q(v, 75), d)} | {fmt(q(v, 10), d)} | {fmt(q(v, 90), d)} |')
    return '\n'.join(rows)


def scored(scores, product='pgda78_5m', phot='hapke', reg=True):
    return [r for r in scores if r.get('status') == 'scored' and r['product'] == product and r['photometry'] == phot
            and r['registered'] == reg]


def paired(scores, a, b, metric, reg=True, phot_a='hapke', phot_b='hapke'):
    A = {(r['product_id'], r['site']): r for r in scored(scores, a, phot_a, reg)}
    B = {(r['product_id'], r['site']): r for r in scored(scores, b, phot_b, reg)}
    keys = sorted(set(A) & set(B))
    d = [A[k][metric] - B[k][metric] for k in keys if math.isfinite(A[k].get(metric, float('nan'))) and math.isfinite(B[k].get(metric, float('nan')))]
    return d, keys


# ------------------------------------------------------------------------------------------------ gallery
def _jpg(path, img, quality=85):
    """8-bit RGB JPEG (small committed thumbnails); no GDAL .aux.xml sidecar."""
    import rasterio
    with rasterio.Env(GDAL_PAM_ENABLED='NO'):
        with rasterio.open(path, 'w', driver='JPEG', width=img.shape[1], height=img.shape[0], count=img.shape[2],
                           dtype='uint8', QUALITY=str(quality)) as dst:
            dst.write(np.moveaxis(img, -1, 0))


def thumb(key, rec, width=200, out_dir=None, max_height=700):
    """real | render | log-ratio difference | edge overlay, each `width` px wide (narrower if the panel would exceed
    `max_height`), 8-bit RGB JPEG. Returns the relative path."""
    from scipy import ndimage
    d = RENDER_DIR / f'{key[0]}__{key[1]}'
    real = np.load(d / 'real_binned.npz')
    rz = np.load(d / 'pgda78_5m.reduced.npz')
    iof = real['iof'].astype(np.float64)
    ren = rz['beauty'].astype(np.float64)
    dy, dx = rec.get('regDyPx', 0.0) or 0.0, rec.get('regDxPx', 0.0) or 0.0
    ren = ndimage.shift(ren, (dy, dx), order=1, cval=np.nan)
    lit = ndimage.shift(rz['lit'].astype(float), (dy, dx), order=1) >= 0.5
    ok = np.isfinite(iof) & ~real['special']
    from .common import WORK
    G = json.loads((WORK / 'geometry' / f'{key[0]}__{key[1]}.json').read_text())
    E = 1361.0 / (G['sunDistM'] / 149_597_870_700.0) ** 2
    lr = np.log10(np.maximum(iof, 1e-5))                      # absolute I/F, one shared stretch for real and render
    lm = np.log10(np.maximum(math.pi * ren / E, 1e-5))

    def to8(x, lo, hi):
        return (np.clip((np.nan_to_num(x, nan=lo) - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)
    lo, hi = np.nanpercentile(lr[ok], [1, 99.5])
    a = to8(lr, lo, hi)
    b = to8(lm, lo, hi)
    diff = np.clip((lm - lr) / 1.0, -1, 1)                    # +-1 decade full scale
    diff = np.nan_to_num(diff, nan=0.0)
    dif = np.stack([(255 * np.clip(diff, 0, 1)).astype(np.uint8), np.zeros(diff.shape, np.uint8),
                    (255 * np.clip(-diff, 0, 1)).astype(np.uint8)], -1)
    from scipy.ndimage import binary_dilation
    v = np.log10(np.maximum(iof / np.nanmedian(iof[ok]), 1e-5))
    from .score import otsu
    thr = otsu(v[ok])[0]
    obs = (v <= thr) & ok
    e_obs = obs & binary_dilation(~obs & ok)
    e_pre = ~lit & binary_dilation(lit)
    ov = np.stack([a, a, a], -1).copy()
    k = max(1, int(round(1 / min(width / a.shape[1], max_height / a.shape[0]) / 2)))   # edges visible after resizing
    ov[binary_dilation(e_obs, iterations=k)] = (255, 220, 0)
    ov[binary_dilation(e_pre, iterations=k)] = (0, 200, 255)
    s = min(width / a.shape[1], max_height / a.shape[0])

    def rs(x):
        if x.ndim == 2:
            x = np.stack([x] * 3, -1)
        return np.stack([ndimage.zoom(x[..., k].astype(float), s, order=1) for k in range(3)], -1).clip(0, 255).astype(np.uint8)
    panels = [rs(a), rs(b), rs(dif), rs(ov)]
    sep = np.full((panels[0].shape[0], 4, 3), 255, np.uint8)
    img = np.concatenate([panels[0], sep, panels[1], sep, panels[2], sep, panels[3]], axis=1)
    od = out_dir or GAL
    od.mkdir(parents=True, exist_ok=True)
    name = f'{key[0]}__{key[1]}.jpg'
    _jpg(od / name, img)
    return f'render_vs_real/{name}'


# ------------------------------------------------------------------------------------------------ hero point
def hero(scores):
    """Site04 RoI 3 hero point = the site centre: is it inside the scored window, and what do real and render say there?"""
    from .common import WORK
    out = []
    for r in scored(scores, 'pgda78_5m', 'hapke', True):
        if r['site'] != 'site04_roi3':
            continue
        key = (r['product_id'], r['site'])
        d = RENDER_DIR / f'{key[0]}__{key[1]}'
        G = json.loads((WORK / 'geometry' / f'{key[0]}__{key[1]}.json').read_text())
        try:
            rz = np.load(d / 'pgda78_5m.reduced.npz')
            real = np.load(d / 'real_binned.npz')
        except FileNotFoundError:
            continue
        # pixel of the hero point: nearest render surface point is not stored after reduction -> use the camera model
        from .nac_camera import fitted_rays_enu, IK
        pix = hero_pixel(G)
        if pix is None:
            out.append({'product_id': r['product_id'], 'inImage': False})
            continue
        i, j = pix
        iof = real['iof'].astype(float)
        ok = np.isfinite(iof) & ~real['special']
        from .score import otsu
        lr = np.log10(np.maximum(iof / np.nanmedian(iof[ok]), 1e-5))
        thr = otsu(lr[ok])[0]
        dy, dx = int(round(r.get('regDyPx', 0))), int(round(r.get('regDxPx', 0)))
        ii, jj = i - dy, j - dx
        inside = 0 <= ii < rz['lit'].shape[0] and 0 <= jj < rz['lit'].shape[1]

        def flip_dist(mask, a, c, rad=40):
            # distance (binned px) from (a, c) to the nearest pixel of the other class within +-rad; None if none
            w = mask[max(0, a - rad):a + rad + 1, max(0, c - rad):c + rad + 1]
            yy, xx = np.nonzero(w != mask[a, c])
            if not len(yy):
                return None
            return float(np.min(np.hypot(yy + max(0, a - rad) - a, xx + max(0, c - rad) - c)))
        gsd = r.get('gsdMedianM') or float('nan')
        dp = flip_dist(rz['lit'].astype(bool), ii, jj) if inside else None
        obs_mask = (lr <= thr) & ok
        do = flip_dist(obs_mask, i, j) if ok[i, j] else None
        out.append({'product_id': r['product_id'], 'inImage': True, 'obs_utc': G.get('label', {}).get('start_utc'), 'sunEl': G['sun_el_deg'],
                    'sunAz': G['sun_az_deg'], 'row': i, 'col': j, 'valid': bool(ok[i, j]),
                    'observed': ('shadow' if lr[i, j] <= thr else 'lit') if ok[i, j] else 'invalid',
                    'predicted': ('lit' if rz['lit'][ii, jj] else 'shadow') if inside else 'outside',
                    'iou': r['iouShadow'], 'edgeMedianM': r['edgeMedianM'],
                    'predEdgeDistM': None if dp is None else dp * gsd, 'obsEdgeDistM': None if do is None else do * gsd})
    return out


def hero_pixel(G):
    """Binned (row, col) whose pixel centre ray passes closest to the site centre's surface point (camera model, PGDA 78
    height at the centre). None if outside the crop."""
    from .nac_camera import enu_basis, eval_states, IK
    b, csum = G['bin'], G['summing']
    H, W = G['render_h'], G['render_w']
    target = np.zeros(3)                         # ENU origin = site centre at its PGDA 78 height
    rows = np.arange(H)
    lines = G['l0'] + rows * b + (b - 1) / 2.0
    P, R = eval_states(G['fit'], lines)
    # direction to the target in camera frame per line; cross-track angle -> sample; along-track ~ 0 at the right line
    v = target - P
    vc = np.einsum('nji,nj->ni', R, v / np.linalg.norm(v, axis=1, keepdims=True))
    i = int(np.argmin(np.abs(vc[:, 0] / vc[:, 2])))
    ik = IK[G['frame']]
    y = vc[i, 1] / vc[i, 2] * ik['focal_mm']
    yd = y
    for _ in range(20):                          # invert y_u = y_d / (1 + k y_d^2)
        yd = y * (1 + ik['od_k'] * yd * yd)
    det = yd / ik['transy'] + ik['boresight']
    s = (det - 0.5 - csum / 2.0) / csum + 1.0    # continuous image sample
    j = int(math.floor((s - 0.5) / b))
    if not (0 <= j < W and 0 < i < H - 1):
        return None
    return i, j


# ------------------------------------------------------------------------------------------------ document
def main():
    scores_all, geo, sel = load()
    rows = read_catalogue()
    assert_dev({r['product_id'] for r in scores_all} | {r['product_id'] for r in geo}, rows)
    scores = [r for r in scores_all if r.get('orbit') == 'grgm900c' or r.get('status') == 'failed']   # headline: A4 science orbit
    fdf_rows = [r for r in scores_all if r.get('orbit') == 'fdf']
    fdf_partial_p = RESULTS / 'scores_A3_fdf_partial.jsonl'
    fdf_partial = [json.loads(l) for l in fdf_partial_p.read_text().splitlines() if l.strip()] if fdf_partial_p.exists() else []
    cat = {(r['product_id'], r['site']): r for r in rows}
    L = []
    w = L.append
    ok_geo = [g for g in geo if g['status'] == 'ok']
    sc_keys = {(r['product_id'], r['site']) for r in scored(scores)}
    failed = [r for r in scores if r.get('status') == 'failed']
    w('# Render vs real — LROC NAC, dev (training) split pilot\n')
    w('**SOURCE-BASED · UNVALIDATED · dev split only.** These are not the held-out headline numbers of the pre-registered '
      'protocol; the §8 claim rule cannot be applied to them. Generated by `python -m tools.validation.render_vs_real.report` '
      '(session R4, 16–17 Nov 2026). Protocol `docs/v2/RENDER_VS_REAL_PROTOCOL.md` (frozen) + amendments A1–A4 (hashes in '
      '`docs/v2/PREREGISTRATION.md`, registered before any score). Plan `docs/v2/PHASE_5_R4_PLAN.md`.\n')
    w('Imagery: LROC NAC CDR, NASA PDS (public domain per the LROC terms, https://lroc.im-ldi.com/about/terms). Credit: '
      '**NASA/GSFC/Arizona State University**. SPICE: NAIF PDS `lro-l-spice-6-v1.0`. Terrain: LOLA (PGDA 78, PGDA 90, PDS LDEM).\n')
    w('## 1. What was scored\n')
    n_rows = sum(len(i['sites']) for i in sel['images'])
    w(f"- Selection: {sel['nImages']} dev NAC images / {n_rows} image × site rows from {len(sel['ckWindowsChosen'])} NAIF "
      f"spacecraft-CK windows (cluster sampling by download cost, A1.1), out of {sel['eligibleImages']} eligible dev images "
      f"({sel['eligibleRows']} rows).")
    gs = collections.Counter(g['status'] for g in geo)
    w(f"- Geometry: {gs.get('ok', 0)} rows OK, {gs.get('gated', 0)} gated, {gs.get('failed', 0)} failed (reasons in §9).")
    w(f'- Scored (PGDA 78, Hapke, registered) on the LOLA/LRO RS GRGM900C orbit (A4): **{len(sc_keys)} rows** — the '
      f'headline set below; {len({(r["product_id"], r["site"]) for r in scored(fdf_rows)})} more rows have only the FDF orbit '
      f'(July 2009, before GRGM900C coverage) and are reported separately (§6.3); render/score failures: {len(failed)}.')
    tot_px = sum(r['nWindow'] for r in scored(scores))
    w(f'- Analysis-window pixels (PGDA 78, registered, binned ≈ 5 m): {tot_px:,}.\n')
    # strata coverage
    w('Strata of the scored rows vs all eligible dev rows (A1.1 cluster sampling is not stratified):\n')
    elig = [r for r in rows if r['instrument'] == 'LROC_NAC' and r['split'] == 'dev' and r['footprint_suspect'] != 'true'
            and (r['covers_site_centre'] == 'true' or float(r['overlap_frac'] or 0) >= 0.25)]
    for ax in ('site', 'el_bin', 'az_bin', 'em_bin'):
        ce = collections.Counter(r[ax] for r in elig)
        cs = collections.Counter(cat[k][ax] for k in sc_keys)
        w(f'- **{ax}**: ' + ', '.join(f'{k} {cs.get(k, 0)}/{ce[k]}' for k in sorted(ce)))
    w('')
    # geometry checks
    w('## 2. Geometry checks (per image × site; `results/geometry.csv`)\n')

    def col(name):
        return [float(g[name]) for g in ok_geo if g.get(name) not in ('', None)]
    dsun = [abs(float(g['sun_el_deg']) - float(g['cat_sun_el_deg'])) for g in ok_geo]
    w('| check | median | P95 | max |\n|---|---|---|---|')
    for name, vals, unit in (('model start time − label START (ms)', [abs(x) for x in col('timing_start_diff_ms')], 'ms'),
                             ('line rate vs label span (ppm, abs)', [abs(x) for x in col('timing_rate_vs_label_ppm')], ''),
                             ('image centre vs ODE centre (m)', col('centre_vs_ode_m'), ''),
                             ('state fit: position (m)', col('fit_pos_err_m'), ''),
                             ('state fit: attitude (µrad)', col('fit_ang_err_urad'), ''),
                             ('emission at the site (°)', col('emission_site_deg'), '')):
        if vals:
            w(f'| {name} | {fmt(q(vals, 50), 4)} | {fmt(q(vals, 95), 4)} | {fmt(max(vals), 4)} |')
    w('\nThe Sun elevation compared with the catalogue is at a different time (catalogue: ODE mid-time of the whole strip; here: '
      'mid-time of the cropped lines), so it is not a check; the same-time check (SPICE vs the catalogue\'s Horizons values at '
      'the catalogue time) is stored per row as `spice_vs_horizons_sun` in the git-ignored geometry JSON.\n')
    # distributions
    w('## 3. Score distributions — PGDA 78 5 m, Hapke, registered (headline of this pilot)\n')
    w(table_dist(scored(scores)))
    w('\nSame, **unregistered**:\n')
    w(table_dist(scored(scores, reg=False)))
    w('\n### 3.1 Per site (PGDA 78, Hapke, registered)\n')
    w('| site | n | shadow IoU median (IQR) | edge median m (IQR) | SSIM median | W1 median | weak-bimodality rows |')
    w('|---|---|---|---|---|---|---|')
    for s in SITES:
        rr = [r for r in scored(scores) if r['site'] == s]
        if not rr:
            w(f'| {s} | 0 | — | — | — | — | — |')
            continue
        iou = [r['iouShadow'] for r in rr]
        ed = [r['edgeMedianM'] for r in rr]
        w(f"| {s} | {len(rr)} | {fmt(q(iou, 50))} ({fmt(q(iou, 25))}–{fmt(q(iou, 75))}) | {fmt(q(ed, 50), 1)} "
          f"({fmt(q(ed, 25), 1)}–{fmt(q(ed, 75), 1)}) | {fmt(q([r['ssim'] for r in rr], 50))} | "
          f"{fmt(q([r['wasserstein1'] for r in rr], 50))} | {sum(r['weakBimodality'] for r in rr)} |")
    w('\n### 3.2 By Sun elevation bin at the site centre (catalogue strata; PGDA 78, Hapke, registered)\n')
    w('| el_bin | n | shadow IoU median | lit IoU median | edge median m | obs. shadow fraction median |')
    w('|---|---|---|---|---|---|')
    byel = collections.defaultdict(list)
    for r in scored(scores):
        byel[cat[(r['product_id'], r['site'])]['el_bin']].append(r)
    for k in sorted(byel):
        rr = byel[k]
        w(f"| {k} | {len(rr)} | {fmt(q([r['iouShadow'] for r in rr], 50))} | {fmt(q([r['iouLit'] for r in rr], 50))} | "
          f"{fmt(q([r['edgeMedianM'] for r in rr], 50), 1)} | {fmt(q([r['obsShadowFrac'] for r in rr], 50))} |")
    # product comparison
    w('\n## 4. Terrain products (paired on the same rows; Hapke, registered)\n')
    w('| product | n | shadow IoU median | edge median m | edge unmatched | SSIM | W1 |')
    w('|---|---|---|---|---|---|---|')
    for p in PRODUCTS:
        rr = scored(scores, p)
        w(f"| {PNAME[p]} | {len(rr)} | {fmt(q([r['iouShadow'] for r in rr], 50))} | {fmt(q([r['edgeMedianM'] for r in rr], 50), 1)} | "
          f"{fmt(q([r['edgeUnmatchedFrac'] for r in rr], 50))} | {fmt(q([r['ssim'] for r in rr], 50))} | "
          f"{fmt(q([r['wasserstein1'] for r in rr], 50))} |")
    w('\nPaired per-row differences, median and bootstrap 95 % interval (10,000 resamples of rows, seed `polaris-x-v2-boot`); '
      'descriptive, not a hypothesis test. For IoU and SSIM positive = first product better; for edge error and W1 negative = '
      'first product better.\n')
    w('| comparison | metric | n pairs | median diff | 95 % interval | first better in |')
    w('|---|---|---|---|---|---|')
    for a, b in (('pgda78_5m', 'flat'), ('pgda78_5m', 'pgda90_80m'), ('lola_ldem875s_5m', 'flat'), ('pgda90_80m', 'flat'),
                 ('pgda78_5m', 'lola_ldem875s_5m')):
        for m, better in (('iouShadow', 1), ('edgeMedianM', -1), ('ssim', 1), ('wasserstein1', -1)):
            d, _k = paired(scores, a, b, m)
            if not d:
                continue
            lo, hi = boot_ci(d)
            frac = np.mean([(x * better) > 0 for x in d])
            w(f'| {PNAME[a]} − {PNAME[b]} | {m} | {len(d)} | {fmt(float(np.median(d)), 3)} | {fmt(lo, 3)} … {fmt(hi, 3)} | {frac:.0%} |')
    # photometry
    w('\n## 5. Photometric models (PGDA 78, registered; shadow metrics do not depend on photometry)\n')
    w('| photometry | n | SSIM median | W1 median | JSD median | registration NCC median |')
    w('|---|---|---|---|---|---|')
    for ph in ('hapke', 'lunarlambert:0.5', 'lommel'):
        rr = scored(scores, 'pgda78_5m', ph)
        w(f"| {ph} | {len(rr)} | {fmt(q([r['ssim'] for r in rr], 50))} | {fmt(q([r['wasserstein1'] for r in rr], 50))} | "
          f"{fmt(q([r['jsdBits'] for r in rr], 50))} | {fmt(q([r['regNcc'] for r in rr], 50))} |")
    # registration
    rr = scored(scores)
    off = [r['regOffsetM'] for r in rr]
    w('\n## 6. Registration (PGDA 78, Hapke; search ± 3 × 20 m, A4)\n')
    w(f"- Offset magnitude (m): median {fmt(q(off, 50), 1)}, P90 {fmt(q(off, 90), 1)}, max {fmt(max(off) if off else float('nan'), 1)}; "
      f"rows at the search bound: {sum(r['regAtBound'] for r in rr)}; beyond 60 m: {sum(r.get('offsetBeyondDocumented', False) for r in rr)}; "
      f"NCC registered median {fmt(q([r['regNcc'] for r in rr], 50))} vs unregistered {fmt(q([r['regNccZero'] for r in rr], 50))}.")
    al = [r.get('regOffsetAlongSunM') for r in rr]
    ac = [r.get('regOffsetAcrossSunM') for r in rr]
    w(f"- Ground offset split (real − render, m): along the Sun azimuth median {fmt(q(al, 50), 1)} (P10 {fmt(q(al, 10), 1)}, "
      f"P90 {fmt(q(al, 90), 1)}); across it median {fmt(q(ac, 50), 1)} (P10 {fmt(q(ac, 10), 1)}, P90 {fmt(q(ac, 90), 1)}). An "
      f"along-Sun bias would mean registration is absorbing shadow-length differences (terrain), not pointing.")
    ray_med, ray_p90 = 20 * math.sqrt(2 * math.log(2)), 20 * math.sqrt(2 * math.log(10))
    per_site = collections.defaultdict(list)
    for r in rr:
        if r.get('regOffsetAlongSunM') is not None:
            per_site[r['site']].append(r['regOffsetAlongSunM'])
    ps = '; '.join(f"{s} {fmt(q(v, 50), 1)} (n = {len(v)})" for s, v in sorted(per_site.items()))
    un = {(r['product_id'], r['site']): r for r in scored(scores, 'pgda78_5m', 'hapke', False)}
    sg = [un[(r['product_id'], r['site'])]['edgeSignedMedianM'] for r in rr if (r['product_id'], r['site']) in un]
    sg = [x for x in sg if x is not None and math.isfinite(x)]
    w(f"- Reading: for an unbiased error of σ = 20 m per axis (the documented NAC value), the offset magnitude would follow "
      f"a Rayleigh law with median {ray_med:.1f} m and P90 {ray_p90:.1f} m, so the magnitudes match the documented accuracy. "
      f"The along-Sun component is not unbiased, though: its median is negative at every site ({ps}). **Its cause is not "
      f"determined.** Two candidates: (a) an along-track timing or orbit offset that correlates with the Sun azimuth, "
      f"because polar NAC images are taken from a near-polar orbit at similar local times; (b) systematic shadow-length "
      f"differences that the registration absorbs. The unregistered signed edge error (median "
      f"{fmt(q(sg, 50), 1)} m, IQR {fmt(q(sg, 25), 1)}…{fmt(q(sg, 75), 1)} m) does not show a shadow-length bias, but "
      f"it is not a direct test. Open item.")
    wb =[r for r in rr if r['weakBimodality']]
    w(f"- Weak-bimodality rows: {len(wb)} (shadow IoU median {fmt(q([r['iouShadow'] for r in wb], 50))}); "
      f"render median zero (A1.4 fallback): {sum(r['renderMedianZero'] for r in rr)} of {len(rr)}.\n")
    # orbit comparison
    w('### 6.1 Orbit source: FDF `lrorg` (A3 run) vs LOLA/LRO RS GRGM900C (A4), same rows\n')
    w('Rows scored under A3 (FDF orbit) before the orbit change that are on the GRGM900C orbit under A4, same rows, PGDA 78, '
      'Hapke. The unregistered numbers isolate the orbit: nothing else changed between the two runs except the crop lines of '
      'some rows (and the registration radius in the registered columns).\n')
    A3u = {(r['product_id'], r['site']): r for r in fdf_partial if r.get('status') == 'scored' and r['product'] == 'pgda78_5m'
           and r['photometry'] == 'hapke' and not r['registered']}
    A3r = {(r['product_id'], r['site']): r for r in fdf_partial if r.get('status') == 'scored' and r['product'] == 'pgda78_5m'
           and r['photometry'] == 'hapke' and r['registered']}
    A4u = {(r['product_id'], r['site']): r for r in scored(scores, reg=False)}     # GRGM900C rows only
    A4r = {(r['product_id'], r['site']): r for r in scored(scores)}
    ks = sorted(set(A3u) & set(A4u))
    if ks:
        w('| metric | FDF unregistered | GRGM900C unregistered | FDF registered (± 400 m) | GRGM900C registered (± 60 m) |')
        w('|---|---|---|---|---|')
        for m, d in (('iouShadow', 3), ('iouLit', 3), ('edgeMedianM', 1), ('edgeP90M', 1), ('ssim', 3)):
            w(f"| {m} (median, n = {len(ks)}) | {fmt(q([A3u[k][m] for k in ks], 50), d)} | {fmt(q([A4u[k][m] for k in ks], 50), d)} | "
              f"{fmt(q([A3r[k][m] for k in ks if k in A3r], 50), d)} | {fmt(q([A4r[k][m] for k in ks if k in A4r], 50), d)} |")
        w(f"| registration offset m (median) | — | — | {fmt(q([A3r[k]['regOffsetM'] for k in ks if k in A3r], 50), 1)} | "
          f"{fmt(q([A4r[k]['regOffsetM'] for k in ks if k in A4r], 50), 1)} |\n")
    # unregistered vs registered, headline
    w('### 6.2 Registered vs unregistered (headline rows, PGDA 78, Hapke)\n')
    w('| metric | unregistered median | registered median |\n|---|---|---|')
    ru = scored(scores, reg=False)
    for m, name, d in METRICS[:8]:
        w(f"| {name} | {fmt(q([r.get(m) for r in ru], 50), d)} | {fmt(q([r.get(m) for r in rr], 50), d)} |")
    w('')
    w('### 6.3 Rows with only the FDF orbit (July 2009; registration ± 400 m, A3)\n')
    fr = scored(fdf_rows)
    if fr:
        w('| product id | site | shadow IoU unreg. | shadow IoU reg. | edge median m reg. | offset m |\n|---|---|---|---|---|---|')
        fu = {(r['product_id'], r['site']): r for r in scored(fdf_rows, reg=False)}
        for r in sorted(fr, key=lambda x: (x['product_id'], x['site'])):
            u = fu.get((r['product_id'], r['site']), {})
            w(f"| {r['product_id']} | {r['site']} | {fmt(u.get('iouShadow'))} | {fmt(r['iouShadow'])} | {fmt(r['edgeMedianM'], 1)} | {fmt(r['regOffsetM'], 0)} |")
    else:
        w('None scored.')
    w('')
    # gallery
    w('## 7. Gallery (real | render | log-ratio difference: red = render brighter, blue = darker | edges: yellow observed, cyan predicted)\n')
    w('PGDA 78 5 m, Hapke, registered. Thumbnails ~200 px wide per panel (binned ≈ 5 m pixels, then resized). Each caption: '
      'product id, site, shadow IoU, edge median.\n')
    byk = {(r['product_id'], r['site']): r for r in rr}
    keys = sorted(byk)
    rng = np.random.default_rng(int(hashlib.sha256(b'polaris-x-v2-gallery').hexdigest(), 16) % 2 ** 63)
    rand = [keys[i] for i in sorted(rng.choice(len(keys), size=min(12, len(keys)), replace=False))] if keys else []
    worst = sorted(keys, key=lambda k: byk[k]['iouShadow'])[:max(1, math.ceil(0.1 * len(keys)))] if keys else []
    for title, ks in (('### 7.1 Random 12 (seed `polaris-x-v2-gallery`)', rand), ('### 7.2 Worst 10 % by shadow IoU', worst)):
        w(title + '\n')
        for k in ks:
            try:
                rel = thumb(k, byk[k])
            except Exception as e:
                w(f'- {k[0]} {k[1]}: thumbnail failed ({type(e).__name__}: {e})')
                continue
            r = byk[k]
            w(f"![{k[0]} {k[1]}]({rel})  \n`{k[0]}` {k[1]} · IoU {fmt(r['iouShadow'])} · edge {fmt(r['edgeMedianM'], 1)} m · "
              f"Sun el {cat[k]['sun_el_deg'][:5]}° · offset {fmt(r['regOffsetM'], 0)} m\n")
    # worst cases table
    w('### 7.3 Worst 10 % — numbers\n')
    w('| product id | site | shadow IoU | lit IoU | obs shadow frac | pred shadow frac | edge median m | unmatched | offset m | at bound | weak bimodal |')
    w('|---|---|---|---|---|---|---|---|---|---|---|')
    for k in worst:
        r = byk[k]
        w(f"| {k[0]} | {k[1]} | {fmt(r['iouShadow'])} | {fmt(r['iouLit'])} | {fmt(r['obsShadowFrac'])} | {fmt(r['predShadowFrac'])} | "
          f"{fmt(r['edgeMedianM'], 1)} | {fmt(r['edgeUnmatchedFrac'])} | {fmt(r['regOffsetM'], 0)} | {r['regAtBound']} | {r['weakBimodality']} |")
    # post-hoc diagnostic: windows the render says are almost all shadow
    hl = scored(scores, 'pgda78_5m', 'hapke', True)
    dark = [r for r in hl if r['predShadowFrac'] >= 0.98]
    rest = [r for r in hl if r['predShadowFrac'] < 0.98]
    wd = [k for k in worst if byk[k]['predShadowFrac'] >= 0.98]
    med = lambda xs: fmt(float(np.median(xs))) if xs else '—'
    w(f"\n**Post-hoc diagnostic (not pre-registered; does not replace §3).** {len(wd)} of the {len(worst)} worst-decile rows "
      f"are windows the render predicts as ≥ 98 % shadow. In the gallery above, the real windows are also almost entirely "
      f"shadow, lit only on small rims or crater walls that the render places in the same spots. The darkness is filled with "
      f"scattered light, a cross-track gradient and the NAC readout pattern. With so few lit pixels, the protocol's fixed "
      f"Otsu rule (§2.2) puts its threshold inside the shadow's brightness distribution, and the A1 weak-bimodality test "
      f"does not flag these rows. Their low IoU therefore measures the observed-mask rule on near-total-shadow windows, not a "
      f"terrain or geometry miss. Over all headline rows: predicted shadow ≥ 98 %: n = {len(dark)}, shadow IoU median "
      f"{med([r['iouShadow'] for r in dark])}; the rest: n = {len(rest)}, median {med([r['iouShadow'] for r in rest])}. "
      f"A mask rule for such windows would have to be registered as an amendment before any held-out run; none is applied "
      f"here.\n")
    # hero
    w('\n## 8. Site04 RoI 3 hero point (site centre −89.78012°, −156.32023°)\n')
    H_all = hero(scores_all)
    H = [h for h in H_all if h.get('inImage')]
    H_out = sorted(h['product_id'] for h in H_all if not h.get('inImage'))
    if not H:
        w('No scored dev image covers the hero point in this pilot.')
    else:
        both = [h for h in H if h.get('observed') in ('shadow', 'lit') and h.get('predicted') in ('shadow', 'lit')]
        agree = sum(h['observed'] == h['predicted'] for h in both)
        cm = collections.Counter((h['observed'], h['predicted']) for h in both)
        w(f'{len(H_all)} scored dev rows of Site04 RoI 3; the hero point lies inside the imaged strip in **{len(H)}** of them '
          f'(the other {len(H_out)} images cover part of the 10 km square but not its centre: {", ".join(H_out)}). The pixel is '
          f'the camera-model projection of the site centre at its PGDA 78 height; observed class = the protocol Otsu rule on '
          f'that image; predicted = the PGDA 78 shadow pass after registration. Agreement at the point: '
          f'**{agree}/{len(both)}** (observed shadow & predicted lit: {cm[("shadow", "lit")]}; observed lit & predicted '
          f'shadow: {cm[("lit", "shadow")]}). One pixel per image, ≈ 5 m binned; a descriptive check, not a validation of '
          f'the point.\n')
        miss = [h for h in both if h['observed'] != h['predicted']]
        near = [h for h in miss if h.get('predEdgeDistM') is not None and h['predEdgeDistM'] <= 20]
        w(f'Of the {len(miss)} disagreements, {len(near)} have a predicted shadow edge within 20 m (≈ 4 binned pixels) of the '
          f'point, i.e. the point sits on a shadow boundary and the miss is an edge-position error of the size reported in §3. '
          f'Distances are to the nearest pixel of the other class within ± 40 binned pixels ("—" = none).\n')
        w('| product id | start UTC | Sun el ° | Sun az ° | observed | predicted | to predicted edge m | to observed edge m | image shadow IoU |')
        w('|---|---|---|---|---|---|---|---|---|')
        for h in sorted(H, key=lambda x: x.get('obs_utc') or ''):
            w(f"| {h['product_id']} | {h.get('obs_utc', '')} | {fmt(float(h.get('sunEl', 'nan')), 2)} | {fmt(float(h.get('sunAz', 'nan')), 1)} | "
              f"{h.get('observed')} | {h.get('predicted')} | {fmt(h.get('predEdgeDistM'), 0)} | {fmt(h.get('obsEdgeDistM'), 0)} | {fmt(h.get('iou'))} |")
    # gated
    w('\n## 9. Gated and failed rows (never dropped silently)\n')
    gg = [g for g in geo if g['status'] != 'ok']
    import re as _re
    reasons = collections.Counter(_re.sub(r'[0-9.]+ (m|urad)', 'N', g['reason']).split('(limit')[0].strip() for g in gg)
    w('| stage | reason | rows |\n|---|---|---|')
    for k, v in reasons.most_common():
        w(f'| geometry | {k} | {v} |')
    for r in failed:
        w(f"| render/score | {r['product_id']} {r['site']}: {r['reason'][:120]} | 1 |")
    sg = [r for r in scores if r.get('status') == 'gated' and r.get('product') == 'pgda78_5m' and r.get('photometry') == 'hapke' and r.get('registered')]
    for r in sg:
        w(f"| score | {r['product_id']} {r['site']}: {r['reason']} | 1 |")
    w('\nPer-row list: `tools/validation/render_vs_real/results/geometry.csv` (status, reason) and `results/scores.jsonl`.\n')
    w(LIMITS)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text('\n'.join(L) + '\n')
    print(f'wrote {DOC}')


LIMITS = '''## 10. Limits (stated, not hidden)

- **Dev split only**, cluster-sampled by SPICE download cost; strata coverage in §1. Held-out images were not fetched,
  rendered or scored (guard + test). These numbers cannot be used for the §8 claim rule.
- **Binned to ≈ 5 m** (A1.3), so sub-5 m shadow detail in the NAC images is averaged away; edge errors are in metres of the
  binned grid. Only the lines crossing each site square are scored.
- **Render physics:** Cycles path tracing with a Hapke regolith of uniform 60–70° S parameters (no albedo map at the pole),
  4 bounces, 32 samples, no earthshine, no instrument PSF / stray light / noise model. Real NAC images of shadowed ground show
  scattered and stray light that the render does not reproduce; this lowers SSIM and raises the histogram distance in shadow,
  and is a property of the twin, not of the terrain.
- **Camera:** ISIS model re-implemented here (timing, detector, distortion) with NAIF CK/SPK; not run through ISIS itself.
  The registration absorbs a constant pointing error only (no rotation/scale).
- **Observed mask** is the protocol's fixed Otsu rule on the image's log I/F; where the window is almost all shadow or all lit
  (weak bimodality) it splits noise, and the IoU then measures that.
- No terrain was tuned; no photometric parameter was fitted. Products not in hand (Kaguya TC DTM, GSFC SfS, NAC DTMs) are not
  compared; SLDEM2015 does not reach these latitudes.
'''

WEB = ROOT / 'web' / 'public' / 'render_vs_real'


def web_export():
    """web/public/render_vs_real/{index.json, <id>.png} for the in-app viewer (git-ignored; rebuild with --web)."""
    import datetime as dt
    from .common import WORK, LABEL
    scores, _geo, _sel = load()
    out = []
    for r in scored(scores):
        key = (r['product_id'], r['site'])
        try:
            thumb(key, r, width=260, out_dir=WEB)
        except Exception as e:
            print('thumb failed', key, e)
            continue
        G = json.loads((WORK / 'geometry' / f'{key[0]}__{key[1]}.json').read_text())

        def num(k):
            v = r.get(k)
            return v if isinstance(v, (int, float)) and math.isfinite(v) else None
        out.append({'id': f'{key[0]}__{key[1]}', 'productId': key[0], 'site': key[1], 'product': r['product'],
                    'photometry': r['photometry'], 'iouShadow': num('iouShadow'), 'edgeMedianM': num('edgeMedianM'),
                    'ssim': num('ssim'), 'wasserstein1': num('wasserstein1'), 'regOffsetM': num('regOffsetM'),
                    'sunElDeg': G['sun_el_deg'], 'startUtc': G['label']['start_utc'], 'image': f'{key[0]}__{key[1]}.jpg',
                    'orbit': r.get('orbit'),
                    'resultId': f"scores.jsonl:{key[0]}__{key[1]}__pgda78_5m__hapke__registered__{r.get('orbit')}"})
    idx = {'schema': 'polaris-render-vs-real-index-v1', 'label': LABEL,
           'protocol': 'docs/v2/RENDER_VS_REAL_PROTOCOL.md (frozen) + amendments A1-A4',
           'credit': 'NASA/GSFC/Arizona State University', 'generatedUtc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
           'rows': out}
    (WEB / 'index.json').write_text(json.dumps(idx, indent=1))
    print(f'wrote {WEB / "index.json"} ({len(out)} rows)')


if __name__ == '__main__':
    import sys
    if '--web' in sys.argv:
        web_export()
    else:
        main()
