"""Per image x site geometry for LROC WAC 643 nm rows: camera model, crop (frame sets x samples), state polynomials, Sun, view cone.

    python -m tools.validation.render_vs_real.wac_geometry [--limit N]

Writes <WAC work>/geometry/<id>__<site>.json (+ the OSL camera source) and the committed summary
<WAC results>/geometry.csv (one row per image x site, with failures and their reasons). Mirrors geometry.py (NAC), which is
frozen for the held-out NAC record (A5) and is therefore not edited.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import traceback

import numpy as np

from tools.imagery.sites import SITES

from . import spice_kernels as sk, terrain_products as tp, wac_io
from .common import check_frozen
from .geometry import HALF_M, _gc, az_el
from .nac_camera import enu_basis, me_to_latlon, sphere_hit, utc
from .wac_camera import (IFOV_RAD, SOURCES, WacCamera, eval_states, fit_states, fitted_rays_enu, osl_source, parse_label,
                         window)
from .wac_common import WAC_GEOM_DIR, WAC_RESULTS, guard

FIELDS = ['product_id', 'site', 'status', 'reason', 'r0', 'r1', 's0', 's1', 'render_w', 'render_h', 'gsd_m', 'sc_alt_km',
          'sub_sc_lat', 'sub_sc_lon', 'emission_site_deg', 'sun_az_deg', 'sun_el_deg', 'cat_sun_az_deg', 'cat_sun_el_deg',
          'timing_start_diff_ms', 'timing_span_diff_ms', 'centre_vs_ode_m', 'fit_pos_err_m', 'fit_ang_err_urad', 'fit_degree',
          'orbit', 'kernels']
ANG_LIMIT_URAD = 0.1 * IFOV_RAD * 1e6          # A1.2 gate carried over: 0.1 pixel


def view_cone(cam, fit, r0, r1, s0, s1, h_lo, h0):
    """Boresight-centred cone (rad) that contains every ground point the crop sees (corners and edge midpoints on R + h_lo),
    for the terrain tile planner; + 0.03 rad as for the NAC."""
    ys = np.array([r0, r0, (r0 + r1 + 1) / 2, r1 + 1, r1 + 1, (r0 + r1 + 1) / 2, r0, r1 + 1], float)
    ss = np.array([s0 - 0.5, s1 + 0.5, s0 - 0.5, s0 - 0.5, s1 + 0.5, s1 + 0.5, (s0 + s1) / 2, (s0 + s1) / 2])
    Pp, dd = fitted_rays_enu(cam, fit, np.clip(ys, r0, r1 + 0.999), ss)
    C = np.array([0.0, 0.0, -(1_737_400.0 + h0)])
    oc = Pp - C
    bq = np.einsum('ij,ij->i', oc, dd)
    tt = -bq - np.sqrt(np.maximum(bq * bq - (np.einsum('ij,ij->i', oc, oc) - (1_737_400.0 + h_lo) ** 2), 0))
    X = Pp + tt[:, None] * dd
    Pm, Rm = eval_states(fit, [fit['etMid']])
    pos = Pm[0]
    fwd = Rm[0] @ np.array([0.0, 0.0, 1.0])
    vv = X - pos
    ang = np.arccos(np.clip(vv @ fwd / np.linalg.norm(vv, axis=1), -1, 1))
    return {'pos': pos.tolist(), 'fwd': fwd.tolist(), 'cone': float(ang.max()) + 0.03, 'ifov': IFOV_RAD}


def one(im, site, cat_row):
    pid = im['product_id']
    guard([pid])
    out = {'product_id': pid, 'site': site}
    try:
        lab = parse_label(wac_io.label(pid, im['label_url']))
    except ValueError as e:
        return {**out, 'status': 'gated', 'reason': f'label: {e}'}
    kern, krec = sk.kernels_for(utc(lab['start_utc']), utc(lab['stop_utc']))
    if kern is None:
        return {**out, 'status': 'gated', 'reason': f"camera model: {krec['error']}"}
    orbit = 'fdf'
    g = sk.grgm_for(utc(lab['start_utc']), utc(lab['stop_utc']))
    if g is not None:
        kern = list(kern) + [g]
        krec = {**krec, 'kernels': krec['kernels'] + [g.name]}
        orbit = 'grgm900c'
    cam = WacCamera(lab, kern)
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
            w = window(cam, (cx, cy), HALF_M, h_lo, h_hi, margin)
        except Exception as e:
            return {**out, 'status': 'gated', 'reason': f'camera model does not resolve: {type(e).__name__}: {str(e)[:160]}',
                    'kernels': ' '.join(krec['kernels'])}
        if w is None:
            return {**out, 'status': 'gated', 'reason': 'no image pixel reaches the site square (camera model footprint)'}
        r0, r1, s0, s1 = w
        k0, k1 = r0 // 14, r1 // 14
        for degree in (3, 4, 5, 6, 7):                                    # A2 rule: smallest degree passing the gate
            fit = fit_states(cam, k0, k1, M, P0, degree=degree, nodes=max(41, 8 * (degree + 1)))
            if fit['fitMaxPosErrM'] <= 1.0 and fit['fitMaxAngErrUrad'] <= ANG_LIMIT_URAD:
                break
        if fit['fitMaxPosErrM'] > 1.0 or fit['fitMaxAngErrUrad'] > ANG_LIMIT_URAD:
            return {**out, 'status': 'gated', 'reason': f"camera model: state-polynomial fit error {fit['fitMaxPosErrM']:.3f} m / "
                                                        f"{fit['fitMaxAngErrUrad']:.2f} urad (limit 1 m / {ANG_LIMIT_URAD:.1f} urad)"}
        et_mid = fit['etMid']
        sun_me, sun_dist = cam.sun_me(et_mid)
        sun_vec = sun_me * sun_dist - P0
        sun_dist = float(np.linalg.norm(sun_vec))
        sun_enu = M @ (sun_vec / sun_dist)
        sun_az, sun_el = az_el(sun_enu)
        et_obs = cam.sp.utc2et(cat_row['obs_utc'].replace('Z', ''))
        s_obs, d_obs = cam.sun_me(et_obs)
        cat_az, cat_el = az_el(M @ (s_obs * d_obs - P0))
        Pm = cam.sc_pos_me([et_mid])[0]
        alt = np.linalg.norm(Pm) - 1_737_400.0
        sslat, sslon = me_to_latlon(Pm[None])
        los = (Pm - P0) / np.linalg.norm(Pm - P0)
        emission = math.degrees(math.acos(float(np.dot(los, P0 / np.linalg.norm(P0)))))
        Pc, dc = cam.rays_me(np.array([cam.nrows / 2]), np.array([352.5]))
        Xc = sphere_hit(Pc, dc, 1_737_400.0)
        clat, clon = me_to_latlon(Xc)
        d_ode = 1_737_400.0 * math.radians(_gc(clat[0], clon[0], float(cat_row['center_lat']), float(cat_row['center_lon'])))
        gsd = IFOV_RAD * float(np.linalg.norm(Pm - P0))
        view = view_cone(cam, fit, r0, r1, s0, s1, h_lo, h0)
        rec = {**out, 'status': 'ok', 'reason': '', 'r0': r0, 'r1': r1, 's0': s0, 's1': s1, 'render_w': s1 - s0 + 1,
               'render_h': r1 - r0 + 1, 'gsd_m': round(gsd, 3), 'sc_alt_km': round(alt / 1000, 3),
               'sub_sc_lat': round(float(sslat[0]), 5), 'sub_sc_lon': round(float(sslon[0]), 5),
               'emission_site_deg': round(emission, 3), 'sun_az_deg': round(sun_az, 4), 'sun_el_deg': round(sun_el, 4),
               'cat_sun_az_deg': float(cat_row['sun_az_deg']), 'cat_sun_el_deg': float(cat_row['sun_el_deg']),
               'timing_start_diff_ms': round(tc['startDiffS'] * 1000, 4),
               'timing_span_diff_ms': round((tc['modelSpanS'] - tc['labelSpanS']) * 1000, 4),
               'centre_vs_ode_m': round(d_ode, 1), 'fit_pos_err_m': round(fit['fitMaxPosErrM'], 5),
               'fit_ang_err_urad': round(fit['fitMaxAngErrUrad'], 4), 'fit_degree': fit['degree'], 'orbit': orbit,
               'kernels': ' '.join(krec['kernels'])}
        detail = {**rec, 'instrument': 'LROC_WAC', 'band_nm': 643, 'label': dict(lab), 'fit': fit, 'view': view,
                  'sunEnu': sun_enu.tolist(), 'sunDistM': sun_dist, 'etMid': et_mid, 'enu': {'lat': lat0, 'lon': lon0, 'h0': h0},
                  'siteXY': [cx, cy], 'heightRange': [h_lo, h_hi], 'marginM': margin, 'scPosEnuMid': ((Pm - P0) @ M.T).tolist(),
                  'spice_vs_horizons_sun': [round(cat_az, 5), round(cat_el, 5)], 'timing': tc, 'sources': SOURCES,
                  'dataUrl': im['data_file_url'], 'labelUrl': im['label_url']}
        WAC_GEOM_DIR.mkdir(parents=True, exist_ok=True)
        (WAC_GEOM_DIR / f'{pid}__{site}.json').write_text(json.dumps(detail, indent=1))
        (WAC_GEOM_DIR / f'{pid}__{site}.osl').write_text(osl_source(cam, fit, r0, r1 - r0 + 1, s0, s1 - s0 + 1))
        return rec
    finally:
        cam.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--only', default='')
    a = ap.parse_args(argv)
    check_frozen()
    from .common import read_catalogue
    rows = read_catalogue()
    cat = {(r['product_id'], r['site']): r for r in rows}
    sel = json.loads((WAC_RESULTS / 'selection.json').read_text())
    todo = [(im, s) for im in sel['images'] for s in im['sites']]
    if a.only:
        todo = [t for t in todo if t[0]['product_id'] in a.only.split(',')]
    if a.limit:
        todo = todo[:a.limit]
    guard([im['product_id'] for im, _ in todo], rows)
    out_csv = WAC_RESULTS / 'geometry.csv'
    prev = {}
    if out_csv.exists() and not a.only:
        prev = {(r['product_id'], r['site']): r for r in csv.DictReader(open(out_csv))}
    recs = []
    for i, (im, site) in enumerate(todo):
        key = (im['product_id'], site)
        if key in prev and prev[key]['status'] in ('ok', 'gated'):
            recs.append(prev[key])
            continue
        try:
            rec = one(im, site, cat[key])
        except Exception as e:
            traceback.print_exc()
            rec = {'product_id': key[0], 'site': site, 'status': 'failed', 'reason': f'{type(e).__name__}: {str(e)[:200]}'}
        recs.append(rec)
        print(f"[{i + 1}/{len(todo)}] {key[0]} {site}: {rec['status']} {rec.get('reason', '')}", flush=True)
    if a.only:
        keep = {(r['product_id'], r['site']) for r in recs}
        recs = [r for r in csv.DictReader(open(out_csv)) if (r['product_id'], r['site']) not in keep] + recs if out_csv.exists() else recs
    WAC_RESULTS.mkdir(parents=True, exist_ok=True)
    with open(out_csv, 'w', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
        wr.writeheader()
        for r in recs:
            wr.writerow(r)


if __name__ == '__main__':
    main()
