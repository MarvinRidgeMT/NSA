"""Render, fetch and score ShadowCam rows (A8/A9 dev; A10 held-out through its driver).

    python -m tools.validation.render_vs_real.shc_run [--workers 4 --threads 4] [--only ids] [--geometry geometry.csv]
                                                      [--scores scores.jsonl] [--render-only]

Same products, photometry variants, render settings and §4 metrics as the NAC (run.py, frozen; imported):
  * renders: wac_twin.py (frozen with A7; camera-agnostic: OSL camera + the view cone in the geometry file);
  * real image: radiance lines binned to the 5 m grid (shc_io); invalid blocks leave the window. Saturated blocks: see
    SATURATION_RULE (A8.5 dropped them; A10 restores protocol §4.1: they stay in the window and count as lit);
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
# A10: 'lit' = protocol §4.1 (saturated window pixels count as lit; Otsu, normalisation, SSIM and histograms use the
# non-saturated pixels only). 'dropped' = the A8.5 dev pilot as registered (saturated blocks removed from the window).
SATURATION_RULE = 'lit'


def render_row(gpath, threads, products=None, variants=True):
    """products / variants: the A8.4 pipeline test renders PGDA 78 with Hapke only."""
    G = json.loads(gpath.read_text())
    out = SHC_RENDER_DIR / gpath.stem
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
    gsd = np.linalg.norm(pos - Psc[:, None, :], axis=-1) * IK['ifov_rad'] * G['bin']
    return in_sq & np.isfinite(gsd), gsd


def saturation_metrics(G, real, special, sat, rend, pred, in_sq, gsd, pos, offset=None):
    """A10.4 secondary analysis (never the claim): the saturation mask as the observed lit class. Agreement and symmetric
    edge errors between the predicted shadow and the non-saturated window pixels, on the same window and registration as
    the §4 metrics. Keys are prefixed 'sat'."""
    if offset is not None:
        dy, dx = offset
        rend, pred, in_sq = S.shift(rend, dy, dx), S.shift(pred, dy, dx), S.shift(in_sq, dy, dx)
        gsd, pos = S.shift(gsd, dy, dx, order=0), S.shift(pos, dy, dx, order=0)
    window = S.analysis_window(in_sq, special) & np.isfinite(real) & np.isfinite(rend)
    if window.sum() < 500:
        return {}
    obs = window & ~sat
    ag = S.agreement(pred & window, obs, window)
    ed = S.edge_errors(pred & window, obs, window, gsd, pos=pos, sun_h=np.asarray(G['sunEnu']))
    out = {'satIouShadow': ag['iouShadow'], 'satIouLit': ag['iouLit'], 'satKappa': ag['kappa'], 'satFrac': 1 - ag['obsShadowFrac']}
    out.update({'sat' + k[0].upper() + k[1:]: v for k, v in ed.items()})
    return out


def score_row(G, beauties, real, special, sat, rule=None):
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
                'tdi': G['tdi'], 'saturationRule': rule or SATURATION_RULE}
        u = metrics(G, real, special, sat, rend, pred, in_sq, gsd, pos)
        lit_rule = (rule or SATURATION_RULE) == 'lit'
        if lit_rule and u['status'] == 'scored':
            u = {**u, **saturation_metrics(G, real, special, sat, rend, pred, in_sq, gsd, pos)}
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
        # A10: register on the valid non-saturated window pixels. Saturated blocks have no radiance and so no gradient of
        # their own; inside them the render keeps its sunlit texture while the real image is a flat fill. Under the A8.5
        # rule `sat` is empty, so nsm == window and the A8.5 registration is unchanged.
        reg = S.register(rn, mn, nsm, max(3.0, REG_RADIUS_M / gm))
        r = metrics(G, real, special, sat, rend, pred, in_sq, gsd, pos, offset=(reg['dy'], reg['dx']))
        if lit_rule and r['status'] == 'scored':
            r = {**r, **saturation_metrics(G, real, special, sat, rend, pred, in_sq, gsd, pos, offset=(reg['dy'], reg['dx']))}
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


def load_real(G, rule=None):
    rule = rule or SATURATION_RULE
    lab = parse_label(shc_io.label(G['product_id'], G['labelUrl']), shc_io.header(G['product_id'], G['dataUrl']))
    val, inv, sat = shc_io.binned_window(lab, G['dataUrl'], G['l0'], G['l1'], G['bin'])
    if rule == 'lit':
        return saturation_fill(val, inv, sat), inv, sat & ~inv
    if rule == 'dropped':
        return val, inv | sat, np.zeros_like(sat)
    raise ValueError(f'unknown saturation rule {rule!r}')


def score_and_save(gpath, G, scores, keep_renders=False):
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
        # A10.3: the same renders are also scored under the A8.5 rule (saturated blocks dropped), as a sensitivity record
        alt = []
        if SATURATION_RULE == 'lit':
            r2, sp2, st2 = load_real(G, 'dropped')
            alt = score_row(G, beauties, r2, sp2, st2, rule='dropped')
    for path, rs in ((scores, recs), (scores.with_name(scores.stem + '_dropped.jsonl'), alt)):
        if rs:
            with open(path, 'a') as f:
                for r in rs:
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
                recs = score_and_save(gp, G, scores, keep_renders=a.keep_renders)
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
