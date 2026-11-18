"""Render, fetch and score ShadowCam rows (A8/A9 dev; A10 held-out through its driver).

    python -m tools.validation.render_vs_real.shc_run [--workers 4 --threads 4] [--only ids] [--geometry geometry.csv]
                                                      [--scores scores.jsonl] [--render-only]

Same products, photometry variants, render settings and §4 metrics as the NAC (run.py, frozen; imported):
  * renders: wac_twin.py (frozen with A7; camera-agnostic: OSL camera + the view cone in the geometry file);
  * real image: radiance lines binned to the 5 m grid (shc_io), special and saturated blocks leave the window (A1.3 rule);
  * registration: S.register with radius REG_RADIUS_M (A9) on the binned grid;
  * pixel size on the ground: range x ShadowCam IFOV x bin.
Records carry 'track' (primary | secondary, protocol §2); secondary rows are reported on SSIM and histogram only.
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
from . import shc_io
from .common import ROOT, check_frozen, read_catalogue
from .nac_camera import enu_basis, eval_states, me_to_latlon, stereo_xy
from .run import AU, BLENDER, BOUNCES, HALF_M, PHOTOMETRY_VARIANTS, PRODUCTS, SPP, TSI, ground_offset, metrics, reduce_npz
from .shc_camera import IK, parse_label
from .shc_common import SHC_GEOM_DIR, SHC_RENDER_DIR, SHC_RESULTS, guard

TWIN = ROOT / 'tools/validation/render_vs_real/wac_twin.py'
REG_RADIUS_M = 150.0          # A9: +- max(3 binned px, 150 m) (3 x 50 m; the dev label check put the centre pixel 51 m off)


def render_row(gpath, threads):
    G = json.loads(gpath.read_text())
    out = SHC_RENDER_DIR / gpath.stem
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
    b, H = G['bin'], G['render_h']
    Psc, _ = eval_states(G['fit'], G['l0'] + np.arange(H) * b + (b - 1) / 2.0)
    return M, P0, Psc


def square_and_gsd(G, R, M, P0, Psc):
    pos = R['pos'].astype(np.float64)
    lat, lon = me_to_latlon(P0 + pos @ M)
    x, y = stereo_xy(lat, lon)
    cx, cy = G['siteXY']
    with np.errstate(invalid='ignore'):
        in_sq = R['hit'] & (np.abs(x - cx) <= HALF_M) & (np.abs(y - cy) <= HALF_M)
    gsd = np.linalg.norm(pos - Psc[:, None, :], axis=-1) * IK['ifov_rad'] * G['bin']
    return in_sq & np.isfinite(gsd), gsd


def score_row(G, beauties, real, special, sat):
    M, P0, Psc = row_context(G)
    E = TSI / (G['sunDistM'] / AU) ** 2
    recs = []
    for prod, phot, Rp, beauty in beauties:
        in_sq, gsd = square_and_gsd(G, Rp, M, P0, Psc)
        rend = np.where(Rp['hit'], math.pi * beauty.astype(np.float64) / E, np.nan)
        pred = ~Rp['lit']
        pos = Rp['pos'].astype(np.float64)
        base = {'product_id': G['product_id'], 'site': G['site'], 'product': prod, 'photometry': phot, 'orbit': 'kplo',
                'instrument': 'ShadowCam', 'track': G['track'], 'start_convention': G['start_convention'], 'flip': G['flip'],
                'tdi': G['tdi']}
        u = metrics(G, real, special, sat, rend, pred, in_sq, gsd, pos)
        recs.append({**base, 'registered': False, **u})
        if u['status'] != 'scored':
            recs.append({**base, 'registered': True, **u})
            continue
        window = S.analysis_window(in_sq, special) & np.isfinite(real) & np.isfinite(rend)
        nsm = window & ~sat
        med_r = float(np.median(real[nsm]))
        rn = np.where(np.isfinite(real) & ~special, real / med_r, 1.0)
        mm = float(np.median(rend[nsm]))
        mn = rend / (mm if mm > 0 else med_r)
        mn = np.where(np.isfinite(mn), mn, 0.0)
        gm = float(np.median(gsd[window]))
        reg = S.register(rn, mn, window, max(3.0, REG_RADIUS_M / gm))
        r = metrics(G, real, special, sat, rend, pred, in_sq, gsd, pos, offset=(reg['dy'], reg['dx']))
        g_al, g_x = ground_offset(pos, reg['dy'], reg['dx'], np.asarray(G['sunEnu']))
        off_m = math.hypot(g_al, g_x) if math.isfinite(g_al) else math.hypot(reg['dy'], reg['dx']) * gm
        recs.append({**base, 'registered': True, **r, 'regDyPx': reg['dy'], 'regDxPx': reg['dx'], 'regNcc': reg['ncc'],
                     'regNccZero': reg['nccZero'], 'regSearchPx': reg['searchPx'], 'regAtBound': reg['atBound'],
                     'regOffsetM': off_m, 'regOffsetAlongSunM': g_al, 'regOffsetAcrossSunM': g_x})
    return recs


def load_real(G):
    lab = parse_label(shc_io.label(G['product_id'], G['labelUrl']), shc_io.header(G['product_id'], G['dataUrl']))
    val, inv, sat = shc_io.binned_window(lab, G['dataUrl'], G['l0'], G['l1'], G['bin'])
    return val, inv | sat, np.zeros_like(sat)


def score_and_save(gpath, G, scores):
    out = SHC_RENDER_DIR / gpath.stem
    real, special, sat = load_real(G)
    beauties = []
    for p in PRODUCTS:
        R = dict(np.load(out / f'{p}.npz'))
        beauties.append((p, 'hapke', R, R['beauty']))
    Rp = dict(np.load(out / 'pgda78_5m.npz'))
    for ph in PHOTOMETRY_VARIANTS:
        beauties.append(('pgda78_5m', ph, Rp, np.load(out / f'pgda78_5m__{ph.replace(":", "")}.npz')['beauty']))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        recs = score_row(G, beauties, real, special, sat)
    with open(scores, 'a') as f:
        for r in recs:
            f.write(json.dumps(r, default=float) + '\n')
    np.savez_compressed(out / 'real_binned.npz', iof=real.astype(np.float16), special=special)
    for p in PRODUCTS:
        reduce_npz(out / f'{p}.npz')
    return recs


def main(argv=None, required=()):
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--only', default='')
    ap.add_argument('--geometry', default='geometry.csv')
    ap.add_argument('--scores', default='scores.jsonl')
    ap.add_argument('--render-only', action='store_true')
    a = ap.parse_args(argv)
    check_frozen()
    rows = read_catalogue()
    geo = [r for r in csv.DictReader(open(SHC_RESULTS / a.geometry)) if r['status'] == 'ok']
    if a.only:
        geo = [r for r in geo if r['product_id'] in a.only.split(',')]
    guard([r['product_id'] for r in geo], rows, required=required)
    scores = SHC_RESULTS / a.scores
    done = set()
    if scores.exists():
        done = {(json.loads(l)['product_id'], json.loads(l)['site'], json.loads(l).get('start_convention'), json.loads(l).get('flip'))
                for l in scores.read_text().splitlines() if l.strip()}
    todo = [SHC_GEOM_DIR / f"{r['tag']}.json" for r in geo
            if (r['product_id'], r['site'], r['start_convention'], r['flip'] == 'True') not in done]
    print(f'{len(todo)} rows to do', flush=True)
    for gp in todo:
        try:
            load_real(json.loads(gp.read_text()))
        except Exception as e:
            print('fetch failed', gp.stem, e, flush=True)
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(render_row, gp, a.threads): gp for gp in todo}
        for fu in cf.as_completed(futs):
            gp = futs[fu]
            try:
                G = fu.result()
                if a.render_only:
                    print(f'{gp.stem}: rendered', flush=True)
                    continue
                recs = score_and_save(gp, G, scores)
                hp = next((r for r in recs if r['product'] == 'pgda78_5m' and r['photometry'] == 'hapke' and r['registered']), {})
                print(f"{gp.stem}: {G['track']} IoU {hp.get('iouShadow')} SSIM {hp.get('ssim')} off ({hp.get('regDyPx')}, "
                      f"{hp.get('regDxPx')}) ncc {hp.get('regNcc')}", flush=True)
            except Exception as e:
                traceback.print_exc()
                if not a.render_only:
                    pid, site = gp.stem.split('__')[:2]
                    with open(scores, 'a') as f:
                        f.write(json.dumps({'product_id': pid, 'site': site, 'status': 'failed', 'instrument': 'ShadowCam',
                                            'reason': f'{type(e).__name__}: {str(e)[:300]}'}) + '\n')


if __name__ == '__main__':
    main()
