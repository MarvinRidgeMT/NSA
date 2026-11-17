"""Per image × site geometry for the selected dev NAC images (task 1): camera model, crop lines, state polynomials, Sun.

    python -m tools.validation.render_vs_real.geometry [--limit N]

Writes $POLARIS_DATA/v2/render_vs_real/geometry/<id>__<site>.json (+ the OSL camera source) and the committed summary
tools/validation/render_vs_real/results/geometry.csv (one row per image × site, with failures and their reasons).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import traceback

import numpy as np

from tools.imagery.sites import SITES

from . import fetch, spice_kernels as sk, terrain_products as tp
from .common import GEOM_DIR, RESULTS, SPLIT, WORK, assert_dev, check_frozen
from .nac_camera import (SOURCES, NacCamera, enu_basis, fit_states, me_to_latlon, osl_source, parse_label, sphere_hit,
                         stereo_xy, utc, window_lines)

FIRST_PASS = {}
_fp = WORK / 'geometry_fdf' / 'geometry_fdf.csv'                     # A4.3 dev first pass; none for held-out (A5)
if SPLIT == 'dev' and _fp.exists():
    FIRST_PASS = {(r['product_id'], r['site']): r for r in csv.DictReader(open(_fp)) if r['status'] == 'ok'}
TARGET_GSD_M = 5.0          # A1: bin to the 5 m terrain posting
HALF_M = 5000.0             # protocol: 10 km x 10 km square
FIELDS = ['product_id', 'site', 'status', 'reason', 'frame', 'summing', 'bin', 'l0', 'l1', 'render_w', 'render_h',
          'gsd_binned_m', 'sc_alt_km', 'sub_sc_lat', 'sub_sc_lon', 'emission_site_deg', 'sun_az_deg', 'sun_el_deg',
          'cat_sun_az_deg', 'cat_sun_el_deg', 'timing_start_diff_ms', 'timing_rate_vs_label_ppm', 'centre_vs_ode_m',
          'fit_pos_err_m', 'fit_ang_err_urad', 'fit_degree', 'orbit', 'crop', 'kernels']


def az_el(vec_enu):
    e, n, u = vec_enu
    return (math.degrees(math.atan2(e, n)) % 360.0, math.degrees(math.asin(u / np.linalg.norm(vec_enu))))


def one(im, site, cat_row):
    pid = im['product_id']
    assert_dev([pid])
    out = {'product_id': pid, 'site': site}
    lab = parse_label(fetch.label(pid, im['label_url']))
    kern, krec = sk.kernels_for(utc(lab['start_utc']), utc(lab['stop_utc']))
    if kern is None:
        return {**out, 'status': 'gated', 'reason': f"camera model: {krec['error']}"}
    orbit = 'fdf'
    g = sk.grgm_for(utc(lab['start_utc']), utc(lab['stop_utc']))       # A4: LOLA/LRO RS science orbit when it covers the image
    if g is not None:
        kern = list(kern) + [g]                                         # loaded last -> takes precedence over lrorg
        krec = {**krec, 'kernels': krec['kernels'] + [g.name]}
        orbit = 'grgm900c'
    cam = NacCamera(lab, kern)
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
            wl = window_lines(cam, (cx, cy), HALF_M, h_lo, h_hi, margin)
        except Exception as e:      # SPICE coverage gaps surface here
            return {**out, 'status': 'gated', 'reason': f'camera model does not resolve: {type(e).__name__}: {str(e)[:160]}',
                    'kernels': ' '.join(krec['kernels'])}
        if wl is None:
            return {**out, 'status': 'gated', 'reason': 'no image line reaches the site square (camera model footprint)'}
        b = max(1, int(round(TARGET_GSD_M / float(im['pixel_scale_m']))))
        l0, l1 = wl
        crop_note = 'computed'
        prev = FIRST_PASS.get((pid, site))                              # A4.3: keep the first-pass crop if it contains this one
        if prev and int(prev['bin']) == b and int(prev['l0']) <= l0 and l1 <= int(prev['l1']) + b:
            l0, l1, crop_note = int(prev['l0']), int(prev['l1']), 'first-pass crop kept (contains the A4 crop)'
        elif prev:
            crop_note = f"recomputed: A4 crop {wl} not inside first-pass crop {prev['l0']}-{prev['l1']}" 
        nlr = (l1 - l0 + 1) // b
        l1 = l0 + nlr * b - 1
        nsr = lab['samples'] // b
        ang_lim = 0.1 * 10.0054 * lab['crosstrack_summing'] * b          # A1.2 gate: 0.1 binned pixel (urad)
        for degree in (3, 4, 5, 6, 7):                                    # A2: smallest degree that passes the A1.2 gate
            fit = fit_states(cam, l0, l1, M, P0, degree=degree, nodes=max(41, 8 * (degree + 1)))
            if fit['fitMaxPosErrM'] <= 1.0 and fit['fitMaxAngErrUrad'] <= ang_lim:
                break
        if fit['fitMaxPosErrM'] > 1.0 or fit['fitMaxAngErrUrad'] > ang_lim:
            return {**out, 'status': 'gated', 'reason': f"camera model: state-polynomial fit error {fit['fitMaxPosErrM']:.3f} m / "
                                                        f"{fit['fitMaxAngErrUrad']:.2f} urad (limit 1 m / {ang_lim:.2f} urad)"}
        lmid = (l0 + l1) / 2
        et_mid = float(cam.et(lmid))
        sun_me, sun_dist = cam.sun_me(et_mid)
        sun_vec = sun_me * sun_dist - P0                      # topocentric: from the site, not the Moon's centre
        sun_dist = float(np.linalg.norm(sun_vec))
        sun_enu = M @ (sun_vec / sun_dist)
        sun_az, sun_el = az_el(sun_enu)
        et_obs = cam.sp.utc2et(cat_row['obs_utc'].replace('Z', ''))
        s_obs, d_obs = cam.sun_me(et_obs)
        cat_az, cat_el = az_el(M @ (s_obs * d_obs - P0))
        Pm = cam.sc_pos_me([et_mid])[0]
        alt = np.linalg.norm(Pm) - 1_737_400.0
        sslat, sslon = me_to_latlon(Pm[None])
        site_me = P0
        los = (Pm - site_me) / np.linalg.norm(Pm - site_me)
        up = site_me / np.linalg.norm(site_me)
        emission = math.degrees(math.acos(float(np.dot(los, up))))
        Pc, dc = cam.rays_me(np.array([lab['lines'] / 2 + 0.5]), np.array([lab['samples'] / 2 + 0.5]))
        Xc = sphere_hit(Pc, dc, 1_737_400.0)
        clat, clon = me_to_latlon(Xc)
        ode = (float(cat_row['center_lat']), float(cat_row['center_lon']))
        d_ode = 1_737_400.0 * math.radians(_gc(clat[0], clon[0], *ode))
        gsd = 10.0054e-6 * lab['crosstrack_summing'] * b * float(np.linalg.norm(Pm - site_me))
        rec = {**out, 'status': 'ok', 'reason': '', 'frame': lab['frame_id'], 'summing': lab['crosstrack_summing'], 'bin': b,
               'l0': l0, 'l1': l1, 'render_w': nsr, 'render_h': nlr, 'gsd_binned_m': round(gsd, 3), 'sc_alt_km': round(alt / 1000, 3),
               'sub_sc_lat': round(float(sslat[0]), 5), 'sub_sc_lon': round(float(sslon[0]), 5),
               'emission_site_deg': round(emission, 3), 'sun_az_deg': round(sun_az, 4), 'sun_el_deg': round(sun_el, 4),
               'cat_sun_az_deg': float(cat_row['sun_az_deg']), 'cat_sun_el_deg': float(cat_row['sun_el_deg']),
               'spice_vs_horizons_sun': [round(cat_az, 5), round(cat_el, 5)],
               'timing_start_diff_ms': round(tc['startDiffS'] * 1000, 4),
               'timing_rate_vs_label_ppm': round((tc['lineRateS'] / tc['labelSpanRateS'] - 1) * 1e6, 2),
               'centre_vs_ode_m': round(d_ode, 1), 'fit_pos_err_m': round(fit['fitMaxPosErrM'], 5),
               'fit_ang_err_urad': round(fit['fitMaxAngErrUrad'], 4), 'fit_degree': fit['degree'], 'orbit': orbit, 'crop': crop_note, 'kernels': ' '.join(krec['kernels'])}
        detail = {**rec, 'label': {k: v for k, v in lab.items()}, 'fit': fit, 'sunEnu': sun_enu.tolist(), 'sunDistM': sun_dist,
                  'etMid': et_mid, 'enu': {'lat': lat0, 'lon': lon0, 'h0': h0}, 'siteXY': [cx, cy], 'heightRange': [h_lo, h_hi],
                  'marginM': margin, 'scPosEnuMid': ((Pm - P0) @ M.T).tolist(), 'timing': tc, 'sources': SOURCES,
                  'dataUrl': im['data_file_url'], 'labelUrl': im['label_url']}
        GEOM_DIR.mkdir(parents=True, exist_ok=True)
        (GEOM_DIR / f'{pid}__{site}.json').write_text(json.dumps(detail, indent=1))
        (GEOM_DIR / f'{pid}__{site}.osl').write_text(osl_source(cam, fit, l0, nlr, b))
        return rec
    finally:
        cam.close()


def _gc(lat1, lon1, lat2, lon2):
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    return math.degrees(math.acos(max(-1.0, min(1.0, math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * math.cos(dl)))))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--only', default='')
    a = ap.parse_args(argv)
    check_frozen()
    from .common import read_catalogue
    rows = read_catalogue()
    cat = {(r['product_id'], r['site']): r for r in rows}
    sel = json.loads((RESULTS / 'selection.json').read_text())
    images = sel['images']
    if a.only:
        images = [i for i in images if i['product_id'] in a.only.split(',')]
    if a.limit:
        images = images[:a.limit]
    assert_dev([i['product_id'] for i in images], rows)
    prev = {}
    p = RESULTS / 'geometry.csv'
    if p.exists():
        prev = {(r['product_id'], r['site']): r for r in csv.DictReader(open(p))}
    for k, im in enumerate(images):
        for site in im['sites']:
            if (im['product_id'], site) in prev and prev[(im['product_id'], site)]['status'] == 'ok' and \
                    (GEOM_DIR / f"{im['product_id']}__{site}.json").exists():
                continue
            try:
                rec = one(im, site, cat[(im['product_id'], site)])
            except Exception as e:
                rec = {'product_id': im['product_id'], 'site': site, 'status': 'failed',
                       'reason': f'{type(e).__name__}: {str(e)[:200]}'}
                traceback.print_exc()
            prev[(im['product_id'], site)] = rec
            print(k, im['product_id'], site, rec['status'], rec.get('reason', ''), rec.get('bin', ''), rec.get('render_w', ''),
                  rec.get('render_h', ''), rec.get('centre_vs_ode_m', ''), rec.get('timing_start_diff_ms', ''), flush=True)
            with open(p, 'w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
                w.writeheader()
                for key in sorted(prev):
                    w.writerow(prev[key])


if __name__ == '__main__':
    main()
