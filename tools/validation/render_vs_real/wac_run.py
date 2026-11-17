"""Render, fetch and score the LROC WAC 643 nm rows (A6 dev pilot; A7 held-out run through wac_heldout.py).

    python -m tools.validation.render_vs_real.wac_run [--workers 4 --threads 4] [--limit N] [--only ids]

Same products, photometry variants, render settings and §4 metrics as the NAC pipeline (run.py, frozen for A5, imported):
  * renders: wac_twin.py (Blender), one per product + the two beauty-only photometry variants on PGDA 78;
  * real image: the 643 nm band I/F on the native WAC grid (no binning; A6), special and saturated pixels leave the window;
  * metrics: run.metrics and S.register unchanged, on a strip-padded grid: the 14-line framelets are separated by GAP_ROWS
    rows that never enter the window, so no neighbourhood operation crosses a framelet seam (A6.4);
  * registration radius: the A4.2 rule in WAC pixels;
  * pixel size on the ground: range x IFOV (wac_camera.IFOV_RAD) per pixel.
Records go to <WAC results>/scores.jsonl (ids and numbers only).
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

from . import score as S
from .common import ROOT, check_frozen, read_catalogue
from .nac_camera import enu_basis, me_to_latlon, stereo_xy
from .run import (AU, BLENDER, BOUNCES, DOCUMENTED_POINTING_M, HALF_M, PHOTOMETRY_VARIANTS, PRODUCTS, SEARCH_RADIUS_M, SPP, TSI,
                  ground_offset, metrics, reduce_npz)
from .wac_camera import FRAMELET, IFOV_RAD, eval_states, parse_label
from .wac_common import WAC_GEOM_DIR, WAC_RENDER_DIR, WAC_RESULTS, guard
from . import wac_io

SCORES = WAC_RESULTS / 'scores.jsonl'
TWIN = ROOT / 'tools/validation/render_vs_real/wac_twin.py'


def render_row(gpath, threads):
    G = json.loads(gpath.read_text())
    out = WAC_RENDER_DIR / gpath.stem
    osl = gpath.with_suffix('.osl')
    todo = [p for p in PRODUCTS if not (out / f'{p}.npz').exists() and not (out / f'{p}.reduced.npz').exists()]
    base = [BLENDER, '-b', '--factory-startup', '--python-exit-code', '1', '-P', str(TWIN), '--', '--geometry', str(gpath),
            '--osl', str(osl), '--out', str(out), '--spp', str(SPP), '--bounces', str(BOUNCES), '--threads', str(threads)]
    if todo:
        r = subprocess.run(base + ['--products', ','.join(todo)], capture_output=True, text=True, timeout=7200)
        if r.returncode:
            raise RuntimeError(f'blender failed for {gpath.stem}: {r.stderr[-800:]}')
    for ph in PHOTOMETRY_VARIANTS:
        if not (out / f'pgda78_5m__{ph.replace(":", "")}.npz').exists():
            r = subprocess.run(base + ['--products', 'pgda78_5m', '--photometry', ph, '--beauty-only'], capture_output=True,
                               text=True, timeout=7200)
            if r.returncode:
                raise RuntimeError(f'blender ({ph}) failed for {gpath.stem}: {r.stderr[-800:]}')
    return G


def row_context(G):
    M, P0 = enu_basis(G['enu']['lat'], G['enu']['lon'], G['enu']['h0'])
    rows = G['r0'] + np.arange(G['render_h'])
    k = rows // FRAMELET
    Psc, _ = eval_states(G['fit'], G['fit']['et0'] + G['fit']['ifd'] * k)
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
    gsd = rng * IFOV_RAD
    return in_sq & np.isfinite(gsd), gsd


GAP_ROWS = 64          # A6.4: rows inserted between framelet strips (> EDGE_UNMATCHED_PX 50, > SSIM and search radii)


def pad_strips(a, fill='edge'):
    """Band-image rows (H = 14 n) -> framelet strips separated by GAP_ROWS rows (A6.4). fill='edge' repeats each strip's
    first / last row into the gap (no artificial gradients); fill=<value> writes that constant."""
    n = a.shape[0] // FRAMELET
    st = a[:n * FRAMELET].reshape(n, FRAMELET, *a.shape[1:])
    pw = [(0, 0), (GAP_ROWS // 2, GAP_ROWS - GAP_ROWS // 2)] + [(0, 0)] * (a.ndim - 1)
    p = np.pad(st, pw, mode='edge') if fill == 'edge' else np.pad(st, pw, mode='constant', constant_values=fill)
    return p.reshape(n * (FRAMELET + GAP_ROWS), *a.shape[1:])


def unpad(a):
    n = a.shape[0] // (FRAMELET + GAP_ROWS)
    st = a.reshape(n, FRAMELET + GAP_ROWS, *a.shape[1:])
    return st[:, GAP_ROWS // 2: GAP_ROWS // 2 + FRAMELET].reshape(n * FRAMELET, *a.shape[1:])


def score_row(G, beauties, real_iof, special, sat):
    """One record per (product, photometry) x (unregistered, registered); run.metrics on the strip-padded grid (A6.4)."""
    M, P0, Psc = row_context(G)
    E = TSI / (G['sunDistM'] / AU) ** 2
    gap = pad_strips(np.zeros(real_iof.shape, bool), fill=True)
    real_p = pad_strips(real_iof)                                   # edge-filled gaps: finite, used only by the registration
    special_p = pad_strips(special) | gap                           # gap rows never enter the window, shifted or not
    sat_p = pad_strips(sat) & ~gap
    real_m = np.where(gap, np.nan, real_p)
    mid = (G['render_h'] // FRAMELET) // 2 * FRAMELET              # a whole framelet for the ground-offset Jacobian
    recs = []
    for prod, phot, Rp, beauty in beauties:
        in_sq, gsd = square_and_gsd(G, Rp, M, P0, Psc)
        rend_iof = math.pi * beauty.astype(np.float64) / E
        rend_iof = np.where(Rp['hit'], rend_iof, np.nan)
        pred = ~Rp['lit']
        pos = Rp['pos'].astype(np.float64)
        in_sq_p, gsd_p, pos_p = pad_strips(in_sq, fill=False), pad_strips(gsd), pad_strips(pos)
        rend_p, pred_p = pad_strips(rend_iof), pad_strips(pred)
        base = {'product_id': G['product_id'], 'site': G['site'], 'product': prod, 'photometry': phot,
                'orbit': G.get('orbit', 'fdf'), 'instrument': 'LROC_WAC'}
        u = metrics(G, real_m, special_p, sat_p, rend_p, pred_p, in_sq_p, gsd_p, pos_p)
        recs.append({**base, 'registered': False, **u})
        if u['status'] != 'scored':
            recs.append({**base, 'registered': True, **u})
            continue
        window = S.analysis_window(in_sq_p, special_p) & np.isfinite(real_m) & np.isfinite(rend_p)
        nsm = window & ~sat_p
        med_r = float(np.median(real_m[nsm]))
        true_special = pad_strips(special)
        rn = np.where(np.isfinite(real_p) & ~true_special, real_p / med_r, 1.0)
        mm = float(np.median(rend_p[nsm]))
        mn = rend_p / (mm if mm > 0 else med_r)
        mn = np.where(np.isfinite(mn), mn, 0.0)
        radius = 3 * DOCUMENTED_POINTING_M if G.get('orbit') == 'grgm900c' else SEARCH_RADIUS_M
        gm = float(np.median(gsd_p[window]))
        max_px = max(3.0, radius / gm)
        reg = S.register(rn, mn, window, max_px)
        r = metrics(G, real_m, special_p, sat_p, rend_p, pred_p, in_sq_p, gsd_p, pos_p, offset=(reg['dy'], reg['dx']))
        g_al, g_x = ground_offset(pos[mid:mid + FRAMELET], reg['dy'], reg['dx'], np.asarray(G['sunEnu']))
        off_m = math.hypot(g_al, g_x) if math.isfinite(g_al) else math.hypot(reg['dy'], reg['dx']) * gm
        recs.append({**base, 'registered': True, **r, 'regDyPx': reg['dy'], 'regDxPx': reg['dx'], 'regNcc': reg['ncc'],
                     'regNccZero': reg['nccZero'], 'regSearchPx': reg['searchPx'], 'regAtBound': reg['atBound'],
                     'regOffsetM': off_m, 'regOffsetAlongSunM': g_al, 'regOffsetAcrossSunM': g_x,
                     'offsetBeyondDocumented': bool(off_m > 3 * DOCUMENTED_POINTING_M)})
    return recs


def load_real(G):
    lab = parse_label(wac_io.label(G['product_id'], G['labelUrl']))
    iof, inv, sat = wac_io.band_iof(lab, G['dataUrl'], G['r0'], G['r1'], G['s0'], G['s1'])
    return iof, inv | sat, np.zeros_like(sat)        # A1.3 rule: special (incl. HRS/HIS) leave the window


def score_and_save(gpath, G):
    out = WAC_RENDER_DIR / gpath.stem
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
        recs = score_row(G, beauties, real_iof, special, sat)
    SCORES.parent.mkdir(parents=True, exist_ok=True)
    with open(SCORES, 'a') as f:
        for r in recs:
            f.write(json.dumps(r, default=float) + '\n')
    np.savez_compressed(out / 'real_band.npz', iof=real_iof.astype(np.float16), special=special)
    for p in PRODUCTS:
        reduce_npz(out / f'{p}.npz')
    return recs


def done_keys():
    if not SCORES.exists():
        return set()
    return {(json.loads(l)['product_id'], json.loads(l)['site']) for l in SCORES.read_text().splitlines() if l.strip()}


def main(argv=None, required=()):
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--only', default='')
    ap.add_argument('--render-only', action='store_true', help='render, do not score (pipeline tests before A6)')
    a = ap.parse_args(argv)
    check_frozen()
    rows = read_catalogue()
    geo = [r for r in csv.DictReader(open(WAC_RESULTS / 'geometry.csv')) if r['status'] == 'ok']
    if a.only:
        geo = [r for r in geo if r['product_id'] in a.only.split(',')]
    guard([r['product_id'] for r in geo], rows, required=required)
    done = done_keys()
    todo = [WAC_GEOM_DIR / f"{r['product_id']}__{r['site']}.json" for r in geo if (r['product_id'], r['site']) not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f'{len(todo)} rows to do', flush=True)
    for gp in todo:                                  # fetch sequentially (polite), render in parallel, score here
        try:
            load_real(json.loads(gp.read_text()))
        except Exception as e:
            print('fetch failed', gp.stem, e, flush=True)
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(render_row, gp, a.threads): gp for gp in todo}
        for fu in cf.as_completed(futs):
            gp = futs[fu]
            t0 = time.time()
            try:
                G = fu.result()
                if a.render_only:
                    print(f'{gp.stem}: rendered', flush=True)
                    continue
                recs = score_and_save(gp, G)
                hp = [r for r in recs if r['product'] == 'pgda78_5m' and r['photometry'] == 'hapke' and r['registered']]
                msg = hp[0] if hp else {}
                print(f"{gp.stem}: scored in {time.time() - t0:.0f}s IoU {msg.get('iouShadow')} edge {msg.get('edgeMedianM')} "
                      f"off ({msg.get('regDyPx')}, {msg.get('regDxPx')})", flush=True)
            except Exception as e:
                traceback.print_exc()
                if a.render_only:
                    continue
                with open(SCORES, 'a') as f:
                    f.write(json.dumps({'product_id': gp.stem.split('__')[0], 'site': gp.stem.split('__')[1], 'status': 'failed',
                                        'reason': f'{type(e).__name__}: {str(e)[:300]}', 'instrument': 'LROC_WAC'}) + '\n')


if __name__ == '__main__':
    main()
