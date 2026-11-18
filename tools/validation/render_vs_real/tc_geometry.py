"""Per image x site geometry for Kaguya TC rows: camera model, crop lines, state polynomials, Sun, view cone, OSL camera.

    python -m tools.validation.render_vs_real.tc_geometry [--limit N] [--only ids] [--start isis|label] [--flip yes|no]
                                                          [--orbit label|grgm900c]

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

from . import tc_io, tc_kernels as K, terrain_products as tp
from .common import check_frozen
from .geometry import HALF_M, az_el
from .nac_camera import enu_basis, window_lines
from .tc_camera import SOURCES, TcCamera, corner_check, eval_fit, fit_piecewise, osl_source, parse_label
from .tc_common import SECONDARY_EL_DEG, TC_GEOM_DIR, TC_RESULTS, guard

TARGET_GSD_M = 5.0
# The SELENE CK is linearly interpolated between quaternions 2 s (~308 lines) apart, so its attitude has small kinks that
# one polynomial often cannot follow to 0.1 px over TC's ~13 s windows: tc_camera.fit_piecewise tries one polynomial
# (degrees 3..11), then 2-16 equal line segments. The gate itself (1 m, 0.1 binned pixel; A1.2/A2) is unchanged. In A12.
DEFAULT = ('isis', False, 'label')      # start, flip, orbit: the default conventions (no suffix in the tag)
# A12 (the A11.4 pipeline test): no sample flip for satellite moving direction -1 (median offset 249 m vs 2,478 m flipped,
# 7 rows, TC1 and TC2); no pipeline-test row had direction +1, so A11.4 gates those rows. Start time unresolved: 'isis'.
FLIP_BY_DIRECTION = {-1: False}
FIELDS = ['product_id', 'site', 'status', 'reason', 'track', 'camera', 'moving_direction', 'start_convention', 'flip', 'orbit',
          'orbit_solution', 'bin', 'l0', 'l1', 's0', 's1', 'render_w',
          'render_h', 'gsd_binned_m', 'sc_alt_km', 'emission_site_deg', 'sun_az_deg', 'sun_el_deg', 'cat_sun_az_deg',
          'cat_sun_el_deg', 'timing_start_diff_ms', 'centre_vs_label_m', 'corners_vs_label_max_m', 'fit_pos_err_m', 'fit_ang_err_urad', 'fit_degree', 'fit_segments',
          'kernels']


def window_samples(cam, l0, l1, site_xy, half_m, h_lo, h_hi, margin_m, step=16):
    """1-based [s0, s1] of the samples whose rays (lines l0..l1, 33 across) hit the square site_xy +- (half + margin) on
    spheres R + h_lo and R + h_hi (as nac_camera.window_lines, across track). Cropping the render to these samples
    changes no metric: pixels outside the square never enter the analysis window. None if no sample does."""
    from .nac_camera import R_MOON_M, me_to_latlon, sphere_hit, stereo_xy
    ns = cam.L['samples']
    samples = np.arange(1, ns + 1, step, dtype=float)
    lines = np.linspace(l0 - 0.5, l1 + 0.5, 33)
    LL, SS = np.meshgrid(lines, samples, indexing='ij')
    P, d = cam.rays_me(LL, SS)
    hit = np.zeros(len(samples), bool)
    for h in (h_lo, h_hi):
        lat, lon = me_to_latlon(sphere_hit(P, d, R_MOON_M + h))
        x, y = stereo_xy(lat, lon)
        inside = (np.abs(x - site_xy[0]) <= half_m + margin_m) & (np.abs(y - site_xy[1]) <= half_m + margin_m)
        hit |= inside.reshape(LL.shape).any(axis=0)
    if not hit.any():
        return None
    idx = np.flatnonzero(hit)
    return max(1, int(samples[idx[0]]) - step), min(ns, int(samples[idx[-1]]) + step)


def view_cone(cam, fit, l0, l1, h_lo, h0, s0, s1, b):
    ll = np.array([l0, l0, (l0 + l1) / 2, l1, l1, (l0 + l1) / 2])
    ss = np.array([s0 - 0.5, s1 + 0.5, s0 - 0.5, s0 - 0.5, s1 + 0.5, s1 + 0.5])
    Pp, Rr = eval_fit(fit, ll)
    dd = np.einsum('nij,nj->ni', Rr, cam.look_cam(ss))
    C = np.array([0.0, 0.0, -(1_737_400.0 + h0)])
    oc = Pp - C
    bq = np.einsum('ij,ij->i', oc, dd)
    tt = -bq - np.sqrt(np.maximum(bq * bq - (np.einsum('ij,ij->i', oc, oc) - (1_737_400.0 + h_lo) ** 2), 0))
    X = Pp + tt[:, None] * dd
    Pm, Rm = eval_fit(fit, [fit['lmid']])
    fwd = Rm[0] @ np.array([0.0, 0.0, 1.0])
    vv = X - Pm[0]
    ang = np.arccos(np.clip(vv @ fwd / np.linalg.norm(vv, axis=1), -1, 1))
    return {'pos': Pm[0].tolist(), 'fwd': fwd.tolist(), 'cone': float(ang.max()) + 0.03, 'ifov': cam.ifov * b}


def one(im, site, cat_row, start='isis', flip=None, orbit='label'):
    pid = im['product_id']
    guard([pid])
    out = {'product_id': pid, 'site': site}
    lab = parse_label(tc_io.label(pid, im['label_url']))
    if flip is None:                                    # A12: decided per moving direction
        if lab['moving_direction'] not in FLIP_BY_DIRECTION:
            return {**out, 'status': 'gated', 'moving_direction': lab['moving_direction'],
                    'reason': f"sample axis not settled for satellite moving direction {lab['moving_direction']:+d} (A11.4, A12)"}
        flip = FLIP_BY_DIRECTION[lab['moving_direction']]
    kern, krec = K.kernels_for(lab, orbit)
    if kern is None:
        return {**out, 'status': 'gated', 'reason': f"camera model: {krec['error']}"}
    cam = TcCamera(lab, kern, start=start, flip=flip)
    try:
        tc = cam.timing_check()
        try:
            corners = corner_check(cam)
        except Exception as e:          # SPICE gap (CK or SPK) at the image ends
            return {**out, 'status': 'gated', 'reason': f'camera model: no SPICE data at the image ends: {str(e).split(chr(10))[0][:120]}'}
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
        sw = window_samples(cam, l0, l1, (cx, cy), HALF_M, h_lo, h_hi, margin)
        if sw is None:
            return {**out, 'status': 'gated', 'reason': 'no image sample reaches the site square (camera model footprint)'}
        s0, s1 = sw
        nsr = (s1 - s0 + 1) // b
        s1 = s0 + nsr * b - 1
        ang_lim = 0.1 * cam.ifov * 1e6 * b
        fit = fit_piecewise(cam, l0, l1, M, P0, ang_lim)
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
        d_lab = corners['CENTER']
        gsd = cam.ifov * b * float(np.linalg.norm(Pm - P0))
        track = 'secondary' if sun_el < SECONDARY_EL_DEG else 'primary'
        rec = {**out, 'status': 'ok', 'reason': '', 'track': track, 'camera': lab['instrument_id'], 'moving_direction': lab['moving_direction'],
               'start_convention': start, 'flip': cam.flip, 'orbit': orbit, 'orbit_solution': krec['orbitSolution'], 'bin': b, 'l0': l0, 'l1': l1, 's0': s0, 's1': s1, 'render_w': nsr, 'render_h': nlr, 'gsd_binned_m': round(gsd, 3),
               'sc_alt_km': round(alt / 1000, 3), 'emission_site_deg': round(emission, 3), 'sun_az_deg': round(sun_az, 4),
               'sun_el_deg': round(sun_el, 4), 'cat_sun_az_deg': float(cat_row['sun_az_deg']),
               'cat_sun_el_deg': float(cat_row['sun_el_deg']), 'timing_start_diff_ms': round(tc['startDiffS'] * 1000, 3),
               'centre_vs_label_m': round(d_lab, 1), 'corners_vs_label_max_m': round(max(corners.values()), 1),
               'fit_pos_err_m': round(fit['fitMaxPosErrM'], 5),
               'fit_ang_err_urad': round(fit['fitMaxAngErrUrad'], 4), 'fit_degree': fit['degree'], 'fit_segments': len(fit.get('segments', [fit])),
               'kernels': ' '.join(krec['kernels'])}
        detail = {**rec, 'instrument': 'Kaguya_TC', 'cornersVsLabelM': corners, 'label': dict(lab), 'fit': fit,
                  'view': view_cone(cam, fit, l0, l1, h_lo, h0, s0, s1, b), 'sunEnu': sun_enu.tolist(),
                  'sunDistM': sun_dist, 'etMid': et_mid, 'enu': {'lat': lat0, 'lon': lon0, 'h0': h0}, 'siteXY': [cx, cy],
                  'heightRange': [h_lo, h_hi], 'marginM': margin, 'scPosEnuMid': ((Pm - P0) @ M.T).tolist(), 'timing': tc,
                  'sources': SOURCES, 'dataUrl': im['data_file_url'], 'labelUrl': im['label_url']}
        TC_GEOM_DIR.mkdir(parents=True, exist_ok=True)
        tag = f'{pid}__{site}' + ('' if (start, cam.flip, orbit) == DEFAULT else f'__{start}{"_flip" if cam.flip else ""}_{orbit}')
        (TC_GEOM_DIR / f'{tag}.json').write_text(json.dumps(detail, indent=1, default=str))
        (TC_GEOM_DIR / f'{tag}.osl').write_text(osl_source(cam, fit, l0, nlr, b, s0=s0, ns_render=nsr))
        return {**rec, 'tag': tag}
    finally:
        cam.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--only', default='')
    ap.add_argument('--start', default=DEFAULT[0], choices=['isis', 'label'])
    ap.add_argument('--flip', default='auto', choices=['auto', 'yes', 'no'], help='auto = A12 rule by moving direction')
    ap.add_argument('--orbit', default=DEFAULT[2], choices=list(K.ORBITS))
    ap.add_argument('--out', default='geometry.csv')
    ap.add_argument('--set', default='images', choices=['images', 'pipelineTestImages'])
    a = ap.parse_args(argv)
    check_frozen()
    from .common import read_catalogue
    rows = read_catalogue()
    cat = {(r['product_id'], r['site']): r for r in rows}
    sel = json.loads((TC_RESULTS / 'selection.json').read_text())
    todo = [(im, s) for im in sel[a.set] for s in im['sites']]
    if a.only:
        todo = [t for t in todo if t[0]['product_id'] in a.only.split(',')]
    if a.limit:
        todo = todo[:a.limit]
    guard([im['product_id'] for im, _ in todo], rows)
    recs = []
    for i, (im, site) in enumerate(todo):
        try:
            rec = one(im, site, cat[(im['product_id'], site)], a.start, None if a.flip == 'auto' else a.flip == 'yes', a.orbit)
        except Exception as e:
            traceback.print_exc()
            rec = {'product_id': im['product_id'], 'site': site, 'status': 'failed', 'reason': f'{type(e).__name__}: {str(e)[:200]}'}
        recs.append(rec)
        print(f"[{i + 1}/{len(todo)}] {im['product_id']} {site}: {rec['status']} {rec.get('reason', '')} {rec.get('track', '')}", flush=True)
    TC_RESULTS.mkdir(parents=True, exist_ok=True)
    with open(TC_RESULTS / a.out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS + ['tag'], extrasaction='ignore')
        w.writeheader()
        for r in recs:
            w.writerow(r)


if __name__ == '__main__':
    main()
