"""Render, fetch and score Kaguya TC rows (A11 dev; the held-out run through its driver).

    python -m tools.validation.render_vs_real.tc_run [--workers 4 --threads 4] [--only ids] [--geometry geometry.csv]
                                                     [--scores scores.jsonl] [--render-only]

Same products, photometry variants, render settings and §4 metrics as the NAC (run.py, frozen; imported):
  * renders: wac_twin.py (frozen with A7; camera-agnostic: OSL camera + the view cone in the geometry file);
  * real image: Level 2B0 radiance lines (tc_io), b = 1 (TC pixels ~8-10 m); invalid pixels leave the window; saturated
    pixels stay in the window and count as lit (protocol §4.1);
  * registration: S.register with radius REG_RADIUS_M on the image grid;
  * pixel size on the ground: range x TC IFOV x bin.
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
from . import tc_io
from .common import ROOT, check_frozen, read_catalogue
from .nac_camera import enu_basis, eval_states, me_to_latlon, stereo_xy
from .run import AU, BLENDER, BOUNCES, HALF_M, PHOTOMETRY_VARIANTS, PRODUCTS, SPP, TSI, ground_offset, metrics, reduce_npz
from .tc_camera import parse_label
from .tc_common import TC_GEOM_DIR, TC_RENDER_DIR, TC_RESULTS, guard

TWIN = ROOT / 'tools/validation/render_vs_real/wac_twin.py'
REG_RADIUS_M = 150.0          # A11: +- max(3 px, 150 m), to be confirmed by the A11.4 pipeline test (recorded in A12)


def render_row(gpath, threads, products=None, variants=True):
    """products / variants: the A8.4 pipeline test renders PGDA 78 with Hapke only."""
    G = json.loads(gpath.read_text())
    out = TC_RENDER_DIR / gpath.stem
    osl = gpath.with_suffix('.osl')
    todo = [p for p in (products or PRODUCTS) if not (out / f'{p}.npz').exists() and not (out / f'{p}.reduced.npz').exists()]
    base = [BLENDER, '-b', '--factory-startup', '--python-exit-code', '1', '-P', str(TWIN), '--', '--geometry', str(gpath),
            '--osl', str(osl), '--out', str(out), '--spp', str(SPP), '--bounces', str(BOUNCES), '--threads', str(threads)]
    if todo:
        r = subprocess.run(base + ['--products', ','.join(todo)], capture_output=True, text=True, timeout=7200)
        if r.returncode:
            raise RuntimeError(f'blender failed for {gpath.stem}: {r.stderr[-800:]}')
    for ph in (PHOTOMETRY_VARIANTS if variants else []):
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
    gsd = np.linalg.norm(pos - Psc[:, None, :], axis=-1) * G['view']['ifov']          # TC IFOV x bin
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
        base = {'product_id': G['product_id'], 'site': G['site'], 'product': prod, 'photometry': phot,
                'orbit': G['orbit'], 'orbitSolution': G['orbit_solution'], 'instrument': 'Kaguya_TC', 'camera': G['camera'],
                'movingDirection': G['moving_direction'], 'track': G['track'], 'start_convention': G['start_convention'],
                'flip': G['flip']}
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
        # register on the valid non-saturated window pixels (saturated pixels carry a fill value, no gradient; as A10)
        reg = S.register(rn, mn, nsm, max(3.0, REG_RADIUS_M / gm))
        r = metrics(G, real, special, sat, rend, pred, in_sq, gsd, pos, offset=(reg['dy'], reg['dx']))
        g_al, g_x = ground_offset(pos, reg['dy'], reg['dx'], np.asarray(G['sunEnu']))
        off_m = math.hypot(g_al, g_x) if math.isfinite(g_al) else math.hypot(reg['dy'], reg['dx']) * gm
        recs.append({**base, 'registered': True, **r, 'regDyPx': reg['dy'], 'regDxPx': reg['dx'], 'regNcc': reg['ncc'],
                     'regNccZero': reg['nccZero'], 'regSearchPx': reg['searchPx'], 'regAtBound': reg['atBound'],
                     'regOffsetM': off_m, 'regOffsetAlongSunM': g_al, 'regOffsetAcrossSunM': g_x})
    return recs


def saturation_fill(val, inv, sat):
    """A10: saturated blocks carry no radiance (ISIS high-saturation special pixels), so they take the brightest valid
    non-saturated value of the window -- a lower bound on their true radiance. Only registration (NCC), the count-matched
    mask and the gallery see this value; every §4 metric that uses radiance excludes saturated pixels."""
    ok = np.isfinite(val) & ~inv & ~sat
    fill = float(np.max(val[ok])) if ok.any() else 1.0
    return np.where(sat & ~inv, fill, val)


def saturation_fill(val, inv, sat):
    """Saturated pixels carry no radiance: they take the brightest valid non-saturated value of the window (as A10). Only
    registration, the count-matched mask and the gallery see it; every §4 radiance metric excludes saturated pixels."""
    ok = np.isfinite(val) & ~inv & ~sat
    fill = float(np.max(val[ok])) if ok.any() else 1.0
    return np.where(sat & ~inv, fill, val)


def load_real(G):
    lab = parse_label(tc_io.label(G['product_id'], G['labelUrl']))
    val, inv, sat = tc_io.binned_window(lab, G['dataUrl'], G['l0'], G['l1'], G['bin'], G['s0'], G['s1'])
    return saturation_fill(val, inv, sat), inv, sat & ~inv


def score_and_save(gpath, G, scores, keep_renders=False):
    out = TC_RENDER_DIR / gpath.stem
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
    for p in (() if keep_renders else PRODUCTS):
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
    ap.add_argument('--keep-renders', action='store_true', help='dev diagnosis only: keep the full render arrays')
    a = ap.parse_args(argv)
    check_frozen()
    rows = read_catalogue()
    geo = [r for r in csv.DictReader(open(TC_RESULTS / a.geometry)) if r['status'] == 'ok']
    if a.only:
        geo = [r for r in geo if r['product_id'] in a.only.split(',')]
    guard([r['product_id'] for r in geo], rows, required=required)
    scores = TC_RESULTS / a.scores
    done = set()
    if scores.exists():
        done = set()
        for line in scores.read_text().splitlines():
            if line.strip():
                j = json.loads(line)
                done.add((j['product_id'], j['site'], j.get('start_convention'), j.get('flip'), j.get('orbit')))
    todo = [TC_GEOM_DIR / f"{r['tag']}.json" for r in geo
            if (r['product_id'], r['site'], r['start_convention'], r['flip'] == 'True', r['orbit']) not in done]
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
                recs = score_and_save(gp, G, scores, keep_renders=a.keep_renders)
                hp = next((r for r in recs if r['product'] == 'pgda78_5m' and r['photometry'] == 'hapke' and r['registered']), {})
                print(f"{gp.stem}: {G['track']} IoU {hp.get('iouShadow')} SSIM {hp.get('ssim')} off ({hp.get('regDyPx')}, "
                      f"{hp.get('regDxPx')}) ncc {hp.get('regNcc')}", flush=True)
            except Exception as e:
                traceback.print_exc()
                if not a.render_only:
                    pid, site = gp.stem.split('__')[:2]
                    with open(scores, 'a') as f:
                        f.write(json.dumps({'product_id': pid, 'site': site, 'status': 'failed', 'instrument': 'Kaguya_TC',
                                            'reason': f'{type(e).__name__}: {str(e)[:300]}'}) + '\n')


if __name__ == '__main__':
    main()
