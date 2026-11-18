"""Catalogue v2 for ShadowCam (protocol §2): footprints from the camera model, not from ODE's browse-map extent.

    python -m tools.validation.render_vs_real.shc_catalogue [--limit N]

Rows: exactly the ShadowCam image x site rows of the frozen catalogue v1 (SHA-256 4b941d61...), every column kept, split
kept. Recomputed per row, with the v1 definitions (tools/imagery/ode.py site_filter: the 10 km x 10 km south-polar
stereographic square, overlap_frac = overlap area / square area, covers_site_centre = square centre inside the footprint):
  footprint_source, footprint_area_km2, footprint_width_km, overlap_frac, covers_site_centre, footprint_suspect.
Footprint: the image outline (64 points per long side, 8 per short side) from shc_camera on the IAU sphere R = 1737.4 km,
using only the PDS4 label (metadata) and KPLO SPICE. No image pixel is read.
Unresolved conventions are bracketed, and a row covers only under every one of them (A8.3):
  start time   ISIS (SCLK ExecutionSpacecraftTime + StartTimeOffset + TDI offset)  |  label start_date_time + TDI offset
  sample axis  as ISIS (no flip)  |  flipped (ALE driver, TDI direction B)
  first pixel  SampleFirstPixel 0  |  72 (3144 - 3072 detector samples)
  -> overlap_frac = the minimum, covers_site_centre = all, plus the max overlap and the number of conventions covering.
footprint_suspect = true only when the camera model cannot resolve (no KPLO CK / SPK, label unreadable), with the reason.
Writes imagery/catalogue_shadowcam_v2.csv.gz and .provenance.json. Labels: $POLARIS_DATA/v2/imagery/shc/labels (manifest).
"""
from __future__ import annotations

import argparse
import csv
import gzip
import itertools
import json
import math
import traceback

import numpy as np

from tools.imagery import geometry as geo
from tools.imagery.sites import BOX_HALF_M, SITES

from . import fetch, shc_kernels as K
from .common import CATALOGUE_SHA256, DATA, ROOT, check_frozen, read_catalogue, sha256_file
from .nac_camera import me_to_latlon, sphere_hit, utc
from .shc_camera import IK, parse_label

OUT = ROOT / 'imagery' / 'catalogue_shadowcam_v2.csv.gz'
LABELS = DATA / 'v2' / 'imagery' / 'shc' / 'labels'
R_IAU = 1_737_400.0
SWATH_SAMPLES = 3072


def label(pid, url):
    """PDS4 label bytes (metadata only; never the image). Cached with a manifest record."""
    p = LABELS / f'{pid}.xml'
    if not p.exists():
        LABELS.mkdir(parents=True, exist_ok=True)
        body, final, _ = fetch._get(url)
        if body.lstrip()[:1] != b'<' or b'Product_Observational' not in body[:4000]:
            raise RuntimeError(f'{pid}: label response is not a PDS4 product label ({final})')
        p.write_bytes(body)
        import datetime as dt
        with open(LABELS.parent / 'MANIFEST.jsonl', 'a') as f:
            f.write(json.dumps({'product_id': pid, 'kind': 'label', 'url': final, 'bytes': len(body), 'sha256': sha256_file(p),
                                'retrieved_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}) + '\n')
    return p.read_bytes()


class _Geom:
    """Spacecraft states for one image; look vectors for a convention (flip, first pixel)."""

    def __init__(self, lab, kernels):
        from .common import spiceypy
        self.L, self.sp = lab, spiceypy()
        self.sp.kclear()
        for k in kernels:
            self.sp.furnsh(str(k))
        self.rate = lab['line_rate_ms'] / 1000.0
        tdi = 64.0 * self.rate
        self.et0 = {'isis': self.sp.scs2e(-155, lab['exec_sclk']) + lab['start_time_offset_s'] + tdi,
                    'label': self.sp.utc2et(lab['start_utc'].replace('Z', '')) + tdi}

    def outline(self, start, flip, sfp, n_along=64, n_across=8):
        L = self.L
        ls = np.linspace(0.5, L['lines'] + 0.5, n_along)
        ss = np.linspace(0.5, L['samples'] + 0.5, n_across)
        edge = ([(l, ss[0]) for l in ls] + [(ls[-1], s) for s in ss[1:]] + [(l, ss[-1]) for l in ls[::-1][1:]] +
                [(ls[0], s) for s in ss[::-1][1:]])
        lines = np.array([e[0] for e in edge])
        samp = np.array([e[1] for e in edge])
        ets = self.et0[start] + self.rate * (lines - 0.5)
        P = np.array([self.sp.spkpos('KPLO', float(e), 'MOON_ME', 'NONE', 'MOON')[0] for e in ets]) * 1000.0
        Rm = np.array([self.sp.pxform(IK['frame'], 'MOON_ME', float(e)) for e in ets])
        det = samp + sfp
        y = IK['pixel_mm'] * (det - IK['boresight_sample']) * (-1.0 if flip else 1.0)
        x = np.full_like(y, IK['pixel_mm'] * (0.0 - IK['boresight_line']))
        yu = y * (1.0 + IK['od_k'] * y * y)
        v = np.stack([x, yu, np.full_like(yu, IK['focal_mm'])], -1)
        v /= np.linalg.norm(v, axis=-1, keepdims=True)
        X = sphere_hit(P, np.einsum('nij,nj->ni', Rm, v), R_IAU)
        lat, lon = me_to_latlon(X)
        if not np.all(np.isfinite(lat)):
            return None
        return [[[geo.stereo_forward(a, b) for a, b in zip(lat, lon)]]]

    def close(self):
        self.sp.kclear()


CONVENTIONS = list(itertools.product(('isis', 'label'), (False, True), (0, 72)))


def rows_for_image(rs, lab_xml):
    lab = parse_label(lab_xml, None)
    kern, krec = K.kernels_for(utc(lab['start_utc']), utc(lab['stop_utc']))
    if kern is None:
        return [{**r, 'footprint_source': 'camera model: not resolved', 'footprint_suspect': 'true',
                 'v2_reason': krec['error']} for r in rs]
    g = _Geom(lab, kern)
    try:
        polys = {c: g.outline(*c) for c in CONVENTIONS}
    finally:
        g.close()
    if any(p is None for p in polys.values()):
        return [{**r, 'footprint_source': 'camera model: not resolved', 'footprint_suspect': 'true',
                 'v2_reason': 'an outline ray misses the reference sphere'} for r in rs]
    ref = polys[('isis', False, 0)]
    area = geo.polygon_area(ref[0])
    diag = geo.bbox_diag(ref)
    width = area / diag if diag > 0 else 0.0
    out = []
    for r in rs:
        s = SITES[r['site']]
        rect, (cx, cy) = geo.site_square(s['lat'], s['lon'], BOX_HALF_M)
        ov = [geo.overlap_area_rect(p, *rect) / (2 * BOX_HALF_M) ** 2 for p in polys.values()]
        cov = [geo.point_in_polys(cx, cy, p) for p in polys.values()]
        out.append({**r, 'footprint_source': 'camera model (ISIS ShadowCamCamera; USGS KPLO kernels; 8 conventions, A8.3)',
                    'footprint_area_km2': round(area / 1e6, 6), 'footprint_width_km': round(width / 1e3, 6),
                    'overlap_frac': round(min(ov), 6), 'covers_site_centre': 'true' if all(cov) else 'false',
                    'footprint_suspect': 'false', 'v2_overlap_max': round(max(ov), 6), 'v2_conventions_covering': sum(cov),
                    'v2_tdi_direction': lab['tdi_direction'], 'v2_kernels': f"{krec['ck'].split('/')[-1]} {krec['spk'].split('/')[-1]}",
                    'v2_reason': ''})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args(argv)
    check_frozen()
    rows = [r for r in read_catalogue() if r['instrument'] == 'ShadowCam']
    by = {}
    for r in rows:
        by.setdefault(r['product_id'], []).append(r)
    pids = sorted(by)
    if a.limit:
        pids = pids[:a.limit]
    part = OUT.with_suffix('.partial.jsonl')
    done = {}
    if part.exists():
        for line in part.read_text().splitlines():
            rec = json.loads(line)
            done.setdefault(rec['product_id'], []).append(rec)
    with open(part, 'a') as f:
        for i, pid in enumerate(pids):
            if pid in done:
                continue
            try:
                res = rows_for_image(by[pid], label(pid, by[pid][0]['label_url']))
            except Exception as e:
                traceback.print_exc()
                res = [{**r, 'footprint_source': 'camera model: not resolved', 'footprint_suspect': 'true',
                        'v2_reason': f'{type(e).__name__}: {str(e)[:160]}'} for r in by[pid]]
            for rec in res:
                f.write(json.dumps(rec) + '\n')
            f.flush()
            done[pid] = res
            if i % 25 == 0:
                print(f'[{i + 1}/{len(pids)}] {pid}: ' + ', '.join(f"{x['site']} {x['overlap_frac']}/{x['covers_site_centre']}" for x in res),
                      flush=True)
    if a.limit:
        return
    out = [rec for pid in sorted(done) for rec in done[pid]]
    cols = list(rows[0].keys()) + ['v2_overlap_max', 'v2_conventions_covering', 'v2_tdi_direction', 'v2_kernels', 'v2_reason']
    with gzip.open(OUT, 'wt', newline='') as fz:
        w = csv.DictWriter(fz, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for rec in out:
            w.writerow(rec)
    prov = {'built_from': 'imagery/catalogue.csv.gz', 'built_from_sha256': CATALOGUE_SHA256, 'rows': len(out),
            'images': len(done), 'sha256': sha256_file(OUT), 'method': __doc__.strip().splitlines()[2:17],
            'kernels': 'tools/validation/render_vs_real/shc_kernels.py (USGS usgs_data/kplo)'}
    OUT.with_suffix('').with_suffix('.provenance.json').write_text(json.dumps(prov, indent=1) + '\n')
    print(f"wrote {OUT} ({len(out)} rows, sha256 {prov['sha256']})")


if __name__ == '__main__':
    main()
