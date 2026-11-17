"""Fetch → render → score every geometry-OK dev row (resumable).

    python -m tools.validation.render_vs_real.run [--workers 4] [--limit N] [--only ID,...]

Per row: real lines fetched by byte range (sequential, polite); Blender render twins (≤ `workers` Blender processes, each with
`threads` CPU threads) for every terrain product + the photometry variants on PGDA 78; scores for each product × photometry,
unregistered and registered, appended to results/scores.jsonl (numbers only, no imagery). Full-resolution render arrays are
reduced after scoring to what the gallery and viewer need (git-ignored).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import json
import math
import subprocess
import time
import traceback
import warnings

import numpy as np

from . import fetch, realimage, score as S
from .common import GEOM_DIR, RENDER_DIR, RESULTS, ROOT, assert_dev, check_frozen, read_catalogue
from .nac_camera import enu_basis, eval_states, me_to_latlon, parse_label, stereo_xy

BLENDER = '/Applications/Blender.app/Contents/MacOS/Blender'
PRODUCTS = ['pgda78_5m', 'lola_ldem875s_5m', 'pgda90_80m', 'flat']
PHOTOMETRY_VARIANTS = ['lunarlambert:0.5', 'lommel']
SPP, BOUNCES = 32, 4
SEARCH_RADIUS_M = 400.0          # A3 (was 3 x 50 m in A1); A4: only for rows on the FDF orbit
DOCUMENTED_POINTING_M = 20.0     # Speyerer et al. 2012; Wagner et al. 2024 (single-image NAC accuracy)
TSI = 1361.0
AU = 149_597_870_700.0
SCORES = RESULTS / 'scores.jsonl'
HALF_M = 5000.0


def render_row(gpath, threads):
    G = json.loads(gpath.read_text())
    out = RENDER_DIR / gpath.stem
    osl = gpath.with_suffix('.osl')
    todo = [p for p in PRODUCTS if not (out / f'{p}.npz').exists() and not (out / f'{p}.reduced.npz').exists()]
    logs = []
    base = [BLENDER, '-b', '--factory-startup', '--python-exit-code', '1', '-P', str(ROOT / 'tools/validation/render_vs_real/blender_twin.py'),
            '--', '--geometry', str(gpath), '--osl', str(osl), '--out', str(out), '--spp', str(SPP), '--bounces', str(BOUNCES),
            '--threads', str(threads)]
    if todo:
        r = subprocess.run(base + ['--products', ','.join(todo)], capture_output=True, text=True, timeout=7200)
        logs.append(r.stdout[-3000:] + r.stderr[-3000:])
        if r.returncode:
            raise RuntimeError(f'blender failed for {gpath.stem}: {r.stderr[-800:]}')
    for ph in PHOTOMETRY_VARIANTS:
        if not (out / f'pgda78_5m__{ph.replace(":", "")}.npz').exists():
            r = subprocess.run(base + ['--products', 'pgda78_5m', '--photometry', ph, '--beauty-only'], capture_output=True, text=True,
                               timeout=7200)
            if r.returncode:
                raise RuntimeError(f'blender ({ph}) failed for {gpath.stem}: {r.stderr[-800:]}')
    return G


# ------------------------------------------------------------------------------------------------ scoring
def row_context(G):
    M, P0 = enu_basis(G['enu']['lat'], G['enu']['lon'], G['enu']['h0'])
    b, H = G['bin'], G['render_h']
    lines = G['l0'] + np.arange(H) * b + (b - 1) / 2.0
    Psc, _ = eval_states(G['fit'], lines)
    return M, P0, Psc


def square_and_gsd(G, R, M, P0, Psc):
    pos = R['pos'].astype(np.float64)
    X = P0 + pos @ M
    lat, lon = me_to_latlon(X)
    x, y = stereo_xy(lat, lon)
    cx, cy = G['siteXY']
    with np.errstate(invalid='ignore'):
        in_sq = R['hit'] & (np.abs(x - cx) <= HALF_M) & (np.abs(y - cy) <= HALF_M)
    rng = np.linalg.norm(pos - Psc[:, None, :], axis=-1)
    gsd = rng * 10.0054e-6 * G['summing'] * G['bin']
    return in_sq & np.isfinite(gsd), gsd


def metrics(G, real_iof, special, sat, rend_iof, pred_shadow, in_sq, gsd, pos, offset=None):
    """All §4 orbital metrics for one registration state."""
    if offset is not None:
        dy, dx = offset
        rend_iof = S.shift(rend_iof, dy, dx)
        pred_shadow = S.shift(pred_shadow, dy, dx)
        in_sq = S.shift(in_sq, dy, dx)
        gsd = S.shift(gsd, dy, dx, order=0)
        pos = S.shift(pos, dy, dx, order=0)
    window = S.analysis_window(in_sq, special) & np.isfinite(real_iof) & np.isfinite(rend_iof)
    ns = window & ~sat
    out = {'nWindow': int(window.sum())}
    if ns.sum() < 500:
        return {**out, 'status': 'gated', 'reason': f'analysis window too small ({int(ns.sum())} px)'}
    real_n, med_real = S.normalise(real_iof, ns)
    rend_n, med_rend = S.normalise(rend_iof, ns)
    flags = {'renderMedianZero': False}
    if not med_rend > 0:
        rend_n = rend_iof / med_real
        flags['renderMedianZero'] = True
    obs, oinfo = S.observed_shadow(real_n, window, sat)
    ag = S.agreement(pred_shadow & window, obs, window)
    cm = S.agreement(pred_shadow & window, S.count_matched_shadow(real_n, window, int((~pred_shadow & window).sum())), window)
    ag = {**ag, 'cmIouShadow': cm['iouShadow'], 'cmIouLit': cm['iouLit']}      # A5.5 secondary (sensitivity only)
    ed = S.edge_errors(pred_shadow & window, obs, window, gsd, pos=pos, sun_h=np.asarray(G['sunEnu']))
    lo, hi = np.percentile(real_n[ns], [0.5, 99.5])
    ss, nss = S.ssim_masked(real_n, rend_n, ns, L=float(hi - lo))
    hd = S.histogram_distances(real_n, rend_n, ns)
    return {**out, 'status': 'scored', **ag, **ed, 'ssim': ss, 'ssimWindows': nss, **hd, **oinfo, **flags,
            'medianIofReal': med_real, 'medianIofRender': med_rend, 'gsdMedianM': float(np.median(gsd[window]))}


def ground_offset(pos, dy, dx, sun_enu):
    """Image offset (px) -> ground displacement of the real image relative to the render, split along/across the horizontal
    Sun direction (m), from the render's surface points around the crop centre (A3)."""
    H, W, _ = pos.shape
    r, c = H // 2, W // 2
    e_row = (pos[min(r + 5, H - 1), c] - pos[max(r - 5, 0), c]) / 10.0
    e_col = (pos[r, min(c + 5, W - 1)] - pos[r, max(c - 5, 0)]) / 10.0
    g = (dy * e_row + dx * e_col)[:2]
    s = np.asarray(sun_enu[:2], float)
    s = s / (np.linalg.norm(s) or 1.0)
    return float(g @ s), float(g[0] * s[1] - g[1] * s[0])


def score_row(G, R, beauties, real_iof, special, sat):
    """Returns a list of records: one per (product, photometry) x (unregistered, registered)."""
    M, P0, Psc = row_context(G)
    E = TSI / (G['sunDistM'] / AU) ** 2
    recs = []
    for prod, phot, Rp, beauty in beauties:
        in_sq, gsd = square_and_gsd(G, Rp, M, P0, Psc)
        rend_iof = math.pi * beauty.astype(np.float64) / E
        rend_iof = np.where(Rp['hit'], rend_iof, np.nan)
        pred = ~Rp['lit']
        pos = Rp['pos'].astype(np.float64)
        base = {'product_id': G['product_id'], 'site': G['site'], 'product': prod, 'photometry': phot, 'orbit': G.get('orbit', 'fdf')}
        u = metrics(G, real_iof, special, sat, rend_iof, pred, in_sq, gsd, pos)
        recs.append({**base, 'registered': False, **u})
        if u['status'] != 'scored':
            recs.append({**base, 'registered': True, **u})
            continue
        window = S.analysis_window(in_sq, special) & np.isfinite(real_iof) & np.isfinite(rend_iof)
        nsm = window & ~sat
        med_r = float(np.median(real_iof[nsm]))
        rn = np.where(np.isfinite(real_iof) & ~special, real_iof / med_r, 1.0)        # A3: whole crop, specials -> 1.0
        mm = float(np.median(rend_iof[nsm]))
        mn = rend_iof / (mm if mm > 0 else med_r)
        mn = np.where(np.isfinite(mn), mn, 0.0)
        radius = 3 * DOCUMENTED_POINTING_M if G.get('orbit') == 'grgm900c' else SEARCH_RADIUS_M     # A4.2
        max_px = max(3.0, radius / float(np.median(gsd[window])))
        reg = S.register(rn, mn, window, max_px)
        r = metrics(G, real_iof, special, sat, rend_iof, pred, in_sq, gsd, pos, offset=(reg['dy'], reg['dx']))
        gm = float(np.median(gsd[window]))
        g_al, g_x = ground_offset(pos, reg['dy'], reg['dx'], np.asarray(G['sunEnu']))
        off_m = math.hypot(g_al, g_x) if math.isfinite(g_al) else math.hypot(reg['dy'], reg['dx']) * gm
        recs.append({**base, 'registered': True, **r, 'regDyPx': reg['dy'], 'regDxPx': reg['dx'], 'regNcc': reg['ncc'],
                     'regNccZero': reg['nccZero'], 'regSearchPx': reg['searchPx'], 'regAtBound': reg['atBound'],
                     'regOffsetM': off_m, 'regOffsetAlongSunM': g_al, 'regOffsetAcrossSunM': g_x,
                     'offsetBeyondDocumented': bool(off_m > 3 * DOCUMENTED_POINTING_M)})
    return recs


def load_real(G):
    lab = parse_label(fetch.label(G['product_id'], G['labelUrl']))
    dn = fetch.window(lab, G['dataUrl'], G['l0'], G['l1'])
    iof, inv, sat = realimage.binned_iof(dn, lab, G['bin'])
    return iof, inv | sat, np.zeros_like(sat)        # A1.3: special (incl. HRS/HIS) leave the window; no other saturation


def reduce_npz(path, keep=('beauty', 'lit', 'hit')):
    if not path.exists():
        return
    z = np.load(path)
    red = {k: (z[k].astype(np.float16) if z[k].dtype == np.float32 else z[k]) for k in keep if k in z.files}
    np.savez_compressed(path.with_suffix('.reduced.npz'), **red)
    path.unlink()


def score_and_save(gpath, G):
    out = RENDER_DIR / gpath.stem
    real_iof, special, sat = load_real(G)
    beauties = []
    for p in PRODUCTS:
        R = dict(np.load(out / f'{p}.npz'))
        beauties.append((p, 'hapke', R, R['beauty']))
    Rp = dict(np.load(out / 'pgda78_5m.npz'))
    for ph in PHOTOMETRY_VARIANTS:
        z = np.load(out / f'pgda78_5m__{ph.replace(":", "")}.npz')
        beauties.append(('pgda78_5m', ph, Rp, z['beauty']))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        recs = score_row(G, None, beauties, real_iof, special, sat)
    with open(SCORES, 'a') as f:
        for r in recs:
            f.write(json.dumps(r, default=float) + '\n')
    # gallery inputs: binned real I/F (float16, git-ignored) + reduced renders
    np.savez_compressed(out / 'real_binned.npz', iof=real_iof.astype(np.float16), special=special)
    for p in PRODUCTS:
        reduce_npz(out / f'{p}.npz')
    return recs


def done_keys():
    if not SCORES.exists():
        return set()
    return {(json.loads(l)['product_id'], json.loads(l)['site']) for l in SCORES.read_text().splitlines() if l.strip()}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--only', default='')
    ap.add_argument('--prefetch-only', action='store_true')
    ap.add_argument('--no-prefetch', action='store_true')
    a = ap.parse_args(argv)
    check_frozen()
    rows = read_catalogue()
    geo = [r for r in csv.DictReader(open(RESULTS / 'geometry.csv')) if r['status'] == 'ok']
    if a.only:
        geo = [r for r in geo if r['product_id'] in a.only.split(',')]
    assert_dev([r['product_id'] for r in geo], rows)
    done = done_keys()
    todo = [GEOM_DIR / f"{r['product_id']}__{r['site']}.json" for r in geo if (r['product_id'], r['site']) not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f'{len(todo)} rows to do', flush=True)
    # prefetch real windows sequentially in this process (polite), render in parallel, score here
    if not a.no_prefetch:
        for gp in todo:
            try:
                load_real(json.loads(gp.read_text()))
            except Exception as e:
                print('fetch failed', gp.stem, e, flush=True)
    if a.prefetch_only:
        return
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(render_row, gp, a.threads): gp for gp in todo}
        for fu in cf.as_completed(futs):
            gp = futs[fu]
            t0 = time.time()
            try:
                G = fu.result()
                recs = score_and_save(gp, G)
                hp = [r for r in recs if r['product'] == 'pgda78_5m' and r['photometry'] == 'hapke' and r['registered']]
                msg = hp[0] if hp else {}
                print(f"{gp.stem}: scored in {time.time() - t0:.0f}s IoU {msg.get('iouShadow')} edge {msg.get('edgeMedianM')} "
                      f"off ({msg.get('regDyPx')}, {msg.get('regDxPx')})", flush=True)
            except Exception as e:
                traceback.print_exc()
                with open(SCORES, 'a') as f:
                    f.write(json.dumps({'product_id': gp.stem.split('__')[0], 'site': gp.stem.split('__')[1], 'status': 'failed',
                                        'reason': f'{type(e).__name__}: {str(e)[:300]}'}) + '\n')


if __name__ == '__main__':
    main()
