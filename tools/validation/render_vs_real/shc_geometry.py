"""Per image x site geometry for ShadowCam rows: camera model, crop lines, state polynomials, Sun, view cone, OSL camera.

    python -m tools.validation.render_vs_real.shc_geometry [--limit N] [--only ids] [--start isis|label] [--flip-b yes|no]

Mirrors geometry.py (NAC; frozen for A5, its generic helpers imported): binned to the 5 m terrain posting (A1.3 rule),
the 10 km square plus margin, polynomial state fit with the A1.2/A2 gate (1 m, 0.1 binned pixel). Track: 'secondary' when
the Sun is below SECONDARY_EL_DEG at the site (protocol §2: SSIM and histogram only), else 'primary'.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import traceback

import numpy as np

from tools.imagery.sites import SITES

from . import shc_io, shc_kernels as K, terrain_products as tp
from .common import check_frozen
from .geometry import HALF_M, _gc, az_el
from .nac_camera import enu_basis, eval_states, fit_states, me_to_latlon, sphere_hit, utc, window_lines
from .shc_camera import IK, SOURCES, ShcCamera, osl_source, parse_label
from .shc_common import SECONDARY_EL_DEG, SHC_GEOM_DIR, SHC_RESULTS, guard

TARGET_GSD_M = 5.0
FIELDS = ['product_id', 'site', 'status', 'reason', 'track', 'tdi', 'start_convention', 'flip', 'bin', 'l0', 'l1', 'render_w',
          'render_h', 'gsd_binned_m', 'sc_alt_km', 'emission_site_deg', 'sun_az_deg', 'sun_el_deg', 'cat_sun_az_deg',
          'cat_sun_el_deg', 'timing_start_diff_ms', 'centre_vs_label_m', 'fit_pos_err_m', 'fit_ang_err_urad', 'fit_degree',
          'kernels']


def view_cone(cam, fit, l0, l1, h_lo, h0, ns, b):
    ll = np.array([l0, l0, (l0 + l1) / 2, l1, l1, (l0 + l1) / 2])
    ss = np.array([0.5, ns + 0.5, 0.5, 0.5, ns + 0.5, ns + 0.5])
    Pp, Rr = eval_states(fit, ll)
    dd = np.einsum('nij,nj->ni', Rr, cam.look_cam(ss))
    C = np.array([0.0, 0.0, -(1_737_400.0 + h0)])
    oc = Pp - C
    bq = np.einsum('ij,ij->i', oc, dd)
    tt = -bq - np.sqrt(np.maximum(bq * bq - (np.einsum('ij,ij->i', oc, oc) - (1_737_400.0 + h_lo) ** 2), 0))
    X = Pp + tt[:, None] * dd
    Pm, Rm = eval_states(fit, [fit['lmid']])
    fwd = Rm[0] @ np.array([0.0, 0.0, 1.0])
    vv = X - Pm[0]
    ang = np.arccos(np.clip(vv @ fwd / np.linalg.norm(vv, axis=1), -1, 1))
    return {'pos': Pm[0].tolist(), 'fwd': fwd.tolist(), 'cone': float(ang.max()) + 0.03, 'ifov': IK['ifov_rad'] * b}


def one(im, site, cat_row, start='isis', flip_b=None):
    pid = im['product_id']
    guard([pid])
    out = {'product_id': pid, 'site': site}
    lab = parse_label(shc_io.label(pid, im['label_url']), shc_io.header(pid, im['data_file_url']))
    if lab['tdi_direction'] == 'B' and flip_b is None:
        return {**out, 'status': 'gated', 'reason': 'TDI direction B: sample flip not settled (A8.4)', 'tdi': 'B'}
    kern, krec = K.kernels_for(utc(lab['start_utc']), utc(lab['stop_utc']))
    if kern is None:
        return {**out, 'status': 'gated', 'reason': f"camera model: {krec['error']}"}
    cam = ShcCamera(lab, kern, start=start, flip=(flip_b if lab['tdi_direction'] == 'B' else None))
    try:
        tc = cam.timing_check()
        level = tp.load(tp.build(site, 'pgda78_5m'))
        cx, cy = level['centre']
        h = level['h']
        xs = level['x0'] + np.arange(h.shape[1]) * level['step']
        ys = level['y0'] + np.arange(h.shape[0]) * level['step']
        sq = (np.abs(xs - cx) <= HALF_M + 2000)[None, :] & (np.abs(ys - cy) <= HALF_M + 2000)[:, None]
        h_lo, h_hi = float(np.nanmin(h[sq])), float(np.nanmax(h[sq]))
        h0 = float(tp.sample(level, np.array([cx]), np.array([cy]))[0])
        lat0, lon0 = SITES[site]['lat'], SITES[site]['lon']
        M, P0 = enu_basis(lat0, lon0, h0)
        em_guess = float(cat_row['emission_deg'] or 0)
        margin = 1000.0 + (h_hi - h_lo) * math.tan(math.radians(min(em_guess + 2.0, 60.0)))
        try:
            wl = window_lines(cam, (cx, cy), HALF_M, h_lo, h_hi, margin, step=256)
        except Exception as e:
            return {**out, 'status': 'gated', 'reason': f'camera model does not resolve: {type(e).__name__}: {str(e)[:160]}'}
        if wl is None:
            return {**out, 'status': 'gated', 'reason': 'no image line reaches the site square (camera model footprint)'}
        b = max(1, int(round(TARGET_GSD_M / float(cat_row['pixel_scale_m']))))
        l0, l1 = wl
        nlr = (l1 - l0 + 1) // b
        l1 = l0 + nlr * b - 1
        nsr = lab['samples'] // b
        ang_lim = 0.1 * IK['ifov_rad'] * 1e6 * b
        for degree in (3, 4, 5, 6, 7):
            fit = fit_states(cam, l0, l1, M, P0, degree=degree, nodes=max(41, 8 * (degree + 1)))
            if fit['fitMaxPosErrM'] <= 1.0 and fit['fitMaxAngErrUrad'] <= ang_lim:
                break
        if fit['fitMaxPosErrM'] > 1.0 or fit['fitMaxAngErrUrad'] > ang_lim:
            return {**out, 'status': 'gated', 'reason': f"camera model: state-polynomial fit error {fit['fitMaxPosErrM']:.3f} m / "
                                                        f"{fit['fitMaxAngErrUrad']:.2f} urad (limit 1 m / {ang_lim:.2f} urad)"}
        lmid = (l0 + l1) / 2
        et_mid = float(cam.et(lmid))
        sun_me, sun_dist = cam.sun_me(et_mid)
        sun_vec = sun_me * sun_dist - P0
        sun_dist = float(np.linalg.norm(sun_vec))
        sun_enu = M @ (sun_vec / sun_dist)
        sun_az, sun_el = az_el(sun_enu)
        Pm = cam.sc_pos_me([et_mid])[0]
        alt = np.linalg.norm(Pm) - 1_737_400.0
        los = (Pm - P0) / np.linalg.norm(Pm - P0)
        emission = math.degrees(math.acos(float(np.dot(los, P0 / np.linalg.norm(P0)))))
        et_ref = cam.sp.utc2et(lab['geometry_utc'].replace('Z', ''))
        Pc, dc = cam.rays_me(np.array([(et_ref - cam.et0) / cam.rate + 0.5]), np.array([lab['samples'] / 2 + 0.5]))
        Xc = sphere_hit(Pc, dc, 1_737_400.0)
        clat, clon = me_to_latlon(Xc)
        d_lab = 1_737_400.0 * math.radians(_gc(clat[0], clon[0], lab['centre_lat'], lab['centre_lon']))
        gsd = IK['ifov_rad'] * b * float(np.linalg.norm(Pm - P0))
        track = 'secondary' if sun_el < SECONDARY_EL_DEG else 'primary'
        rec = {**out, 'status': 'ok', 'reason': '', 'track': track, 'tdi': lab['tdi_direction'], 'start_convention': start,
               'flip': cam.flip, 'bin': b, 'l0': l0, 'l1': l1, 'render_w': nsr, 'render_h': nlr, 'gsd_binned_m': round(gsd, 3),
               'sc_alt_km': round(alt / 1000, 3), 'emission_site_deg': round(emission, 3), 'sun_az_deg': round(sun_az, 4),
               'sun_el_deg': round(sun_el, 4), 'cat_sun_az_deg': float(cat_row['sun_az_deg']),
               'cat_sun_el_deg': float(cat_row['sun_el_deg']), 'timing_start_diff_ms': round(tc['startDiffS'] * 1000, 3),
               'centre_vs_label_m': round(d_lab, 1), 'fit_pos_err_m': round(fit['fitMaxPosErrM'], 5),
               'fit_ang_err_urad': round(fit['fitMaxAngErrUrad'], 4), 'fit_degree': fit['degree'],
               'kernels': ' '.join(krec['kernels'])}
        detail = {**rec, 'instrument': 'ShadowCam', 'label': dict(lab), 'fit': fit,
                  'view': view_cone(cam, fit, l0, l1, h_lo, h0, lab['samples'], b), 'sunEnu': sun_enu.tolist(),
                  'sunDistM': sun_dist, 'etMid': et_mid, 'enu': {'lat': lat0, 'lon': lon0, 'h0': h0}, 'siteXY': [cx, cy],
                  'heightRange': [h_lo, h_hi], 'marginM': margin, 'scPosEnuMid': ((Pm - P0) @ M.T).tolist(), 'timing': tc,
                  'sources': SOURCES, 'dataUrl': im['data_file_url'], 'labelUrl': im['label_url'], 'orbit': 'kplo'}
        SHC_GEOM_DIR.mkdir(parents=True, exist_ok=True)
        tag = f'{pid}__{site}' + ('' if start == 'isis' and not cam.flip else f'__{start}{"_flip" if cam.flip else ""}')
        (SHC_GEOM_DIR / f'{tag}.json').write_text(json.dumps(detail, indent=1, default=str))
        (SHC_GEOM_DIR / f'{tag}.osl').write_text(osl_source(cam, fit, l0, nlr, b))
        return {**rec, 'tag': tag}
    finally:
        cam.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--only', default='')
    ap.add_argument('--start', default='isis', choices=['isis', 'label'])
    ap.add_argument('--flip-b', default=None, choices=['yes', 'no'])
    ap.add_argument('--out', default='geometry.csv')
    ap.add_argument('--set', default='images', choices=['images', 'pipelineTestImages'])
    a = ap.parse_args(argv)
    check_frozen()
    from .common import read_catalogue
    rows = read_catalogue()
    from .shc_common import read_v2
    cat = {(r['product_id'], r['site']): r for r in read_v2()}
    sel = json.loads((SHC_RESULTS / 'selection.json').read_text())
    todo = [(im, s) for im in sel[a.set] for s in im['sites']]
    if a.only:
        todo = [t for t in todo if t[0]['product_id'] in a.only.split(',')]
    if a.limit:
        todo = todo[:a.limit]
    guard([im['product_id'] for im, _ in todo], rows)
    flip = None if a.flip_b is None else a.flip_b == 'yes'
    recs = []
    for i, (im, site) in enumerate(todo):
        try:
            rec = one(im, site, cat[(im['product_id'], site)], a.start, flip)
        except Exception as e:
            traceback.print_exc()
            rec = {'product_id': im['product_id'], 'site': site, 'status': 'failed', 'reason': f'{type(e).__name__}: {str(e)[:200]}'}
        recs.append(rec)
        print(f"[{i + 1}/{len(todo)}] {im['product_id']} {site}: {rec['status']} {rec.get('reason', '')} {rec.get('track', '')}", flush=True)
    SHC_RESULTS.mkdir(parents=True, exist_ok=True)
    with open(SHC_RESULTS / a.out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS + ['tag'], extrasaction='ignore')
        w.writeheader()
        for r in recs:
            w.writerow(r)


if __name__ == '__main__':
    main()
