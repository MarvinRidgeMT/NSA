"""Co-registration of each product to the LOLA geodetic frame (S3). Estimates and logs horizontal and vertical shifts.

Method: reference pixel centres of a LOLA product G inside the product P's footprint (strided to <= MAX_POINTS);
P is block-averaged to G's posting (k = floor(G/P)) once, then sampled bilinearly at the reference points shifted by
(dx, dy) in P's own grid units. The shift minimises the robust spread (NMAD) of P(x + d) - G(x) on a 0.5-px grid over
+-MAX_SHIFT_PX reference pixels, refined on a 0.1-px grid; dz = median(P(x + d) - G(x)).
Corrected product: P'(x) = P(x + dx, y + dy) - dz.

Policy [decision, docs/v2/PHASE_1_PYRAMID_PLAN.md §4]:
- LOLA-family products (source_id 3 PGDA 78, 5 PGDA 90, 7 LOLA polar, 8 LOLA global) ARE the LOLA frame: shifts are
  estimated and logged, never applied. A LOLA-family shift above threshold is flagged for investigation.
- Other products: applied when |dz| > DZ_APPLY_M or |dxy| > DXY_APPLY_PX reference pixels.
- Reference: LOLA global/polar LDEM (source 8/7) when one overlaps; else PGDA 90 (source 5, LOLA polar 80 m).
"""
from __future__ import annotations

import datetime as _dt
import json
import math
from pathlib import Path

import numpy as np

from tools.globe import pyramid_products as PP

MAX_SHIFT_PX = 2.0
MAX_POINTS = 200_000
DZ_APPLY_M = 1.0
DXY_APPLY_PX = 0.25
LOLA_FAMILY = {3, 5, 7, 8}


class _Surface:
    """P block-averaged by k over a window, with bilinear sampling in P's grid coordinates."""

    def __init__(self, rd, x, y, k, margin_px):
        c = (x - rd.left) / rd.px_x; r = (rd.top - y) / rd.px_y
        m = int(math.ceil(margin_px)) * k + 2 * k
        c0 = int(math.floor(np.nanmin(c))) - m; c1 = int(math.ceil(np.nanmax(c))) + m
        r0 = int(math.floor(np.nanmin(r))) - m; r1 = int(math.ceil(np.nanmax(r))) + m
        r0 = (r0 // k) * k; c0 = (c0 // k) * k
        nr = ((r1 - r0 + k - 1) // k) * k; nc = ((c1 - c0 + k - 1) // k) * k
        self.G = rd.read_block(r0, c0, nr, nc, k)
        self.rd, self.k, self.r0, self.c0 = rd, k, r0, c0

    def at(self, x, y):
        rd = self.rd
        c = ((x - rd.left) / rd.px_x - self.c0) / self.k - 0.5
        r = ((rd.top - y) / rd.px_y - self.r0) / self.k - 0.5
        return PP.bilinear_nan(self.G, r, c)[0]


def _nmad(d):
    d = d[np.isfinite(d)]
    if d.size < 10:
        return np.inf
    return 1.4826 * float(np.median(np.abs(d - np.median(d))))


def estimate(spec, ref_spec, max_shift_px=MAX_SHIFT_PX, max_points=MAX_POINTS):
    """Shift of `spec` relative to `ref_spec`. The comparison is always made at the coarser posting: if the reference
    is finer (e.g. PGDA 90 80 m vs LOLA LDEM_85S 10 m), the roles are swapped and the result negated
    (G(x) ~ P(x + d) - dz  <=>  P(x) ~ G(x - d) + dz), which requires both grids to be of the same kind."""
    rd, rg = PP.ProductReader(spec), PP.ProductReader(ref_spec)
    swap = rg.native_px_m() < rd.native_px_m() / 1.01
    if swap:
        same = rd.kind == rg.kind
        rd.close(); rg.close()
        if not same:
            return None
        r = estimate(ref_spec, spec, max_shift_px, max_points)
        if r is None:
            return None
        for k in ('dx', 'dy', 'dz', 'dx_ref_px', 'dy_ref_px', 'dz_zero_shift_m'):
            r[k] = -r[k]
        lola = spec.source_id in LOLA_FAMILY
        r.update({'reference': ref_spec.product_id, 'reference_source_id': ref_spec.source_id,
                  'compared_at': f'{spec.product_id} posting (reference block-averaged; roles swapped, signs negated)',
                  'applied': bool(r['significant'] and not lola),
                  'policy': ('LOLA-family product: logged, never applied' if lola else
                             f'applied if |dz| > {DZ_APPLY_M} m or |dxy| > {DXY_APPLY_PX} px'),
                  'flag': ('LOLA-family shift above threshold: investigate' if (lola and r['significant']) else '')})
        return r
    try:
        lat_f, lon_f = rd.footprint_latlon(200)
        xr, yr = rg.to_grid(lat_f, lon_f)
        if not np.isfinite(xr).any():
            return None
        # reference pixel centres inside the product footprint, inset so every shifted point stays inside P
        inset = int(math.ceil(max_shift_px)) + 2
        c0 = max(0, int(math.floor((np.nanmin(xr) - rg.left) / rg.px_x)) + inset)
        c1 = min(rg.w, int(math.ceil((np.nanmax(xr) - rg.left) / rg.px_x)) - inset)
        r0 = max(0, int(math.floor((rg.top - np.nanmax(yr)) / rg.px_y)) + inset)
        r1 = min(rg.h, int(math.ceil((rg.top - np.nanmin(yr)) / rg.px_y)) - inset)
        if c1 - c0 < 8 or r1 - r0 < 8:
            return None
        stride = max(1, int(math.ceil(math.sqrt((c1 - c0) * (r1 - r0) / max_points))))
        G = rg.read_block(r0, c0, r1 - r0, c1 - c0, 1)[::stride, ::stride]
        cc = c0 + 0.5 + np.arange(0, c1 - c0, stride); rr = r0 + 0.5 + np.arange(0, r1 - r0, stride)
        X, Y = np.meshgrid(rg.left + cc * rg.px_x, rg.top - rr * rg.px_y)
        lat, lon = rg.grid_to_latlon(X, Y)
        px, py = rd.to_grid(lat, lon)
        ref_px_m = rg.native_px_m()
        k = max(1, int(math.floor(ref_px_m / rd.native_px_m() * 1.0001)))
        # one reference pixel expressed in P grid units (polar: metres; lonlat: degrees of latitude)
        unit = ref_px_m if rd.kind != 'lonlat' else math.degrees(ref_px_m / PP.R)
        surf = _Surface(rd, px, py, k, margin_px=(max_shift_px + 1) * unit / max(rd.px_x, rd.px_y) / k)
        g = G.ravel(); px = px.ravel(); py = py.ravel()
        ok = np.isfinite(g) & np.isfinite(surf.at(px, py))
        g, px, py = g[ok], px[ok], py[ok]
        if g.size < 100:
            return None

        def cost(dx, dy):
            return _nmad(surf.at(px + dx * unit, py + dy * unit) - g)

        best = (cost(0.0, 0.0), 0.0, 0.0)
        before = best[0]
        grid = np.arange(-max_shift_px, max_shift_px + 1e-9, 0.5)
        for dx in grid:
            for dy in grid:
                c = cost(dx, dy)
                if c < best[0]:
                    best = (c, dx, dy)
        bx, by = best[1], best[2]
        fine = np.arange(-0.5, 0.5 + 1e-9, 0.1)
        for dx in bx + fine:
            for dy in by + fine:
                c = cost(dx, dy)
                if c < best[0]:
                    best = (c, dx, dy)
        _, dxp, dyp = best
        d = surf.at(px + dxp * unit, py + dyp * unit) - g
        d0 = surf.at(px, py) - g
        dz = float(np.nanmedian(d))
        shift_px = math.hypot(dxp, dyp)
        lola = spec.source_id in LOLA_FAMILY
        significant = abs(dz) > DZ_APPLY_M or shift_px > DXY_APPLY_PX
        return {
            'reference': ref_spec.product_id, 'reference_source_id': ref_spec.source_id,
            'reference_px_m': ref_px_m, 'n_points': int(g.size), 'stride_ref_px': stride, 'block_k': k,
            'dx': float(dxp * unit), 'dy': float(dyp * unit), 'dz': dz,
            'shift_units': 'm (product grid)' if rd.kind != 'lonlat' else 'deg (product grid)',
            'dx_ref_px': float(dxp), 'dy_ref_px': float(dyp), 'dxy_m': float(shift_px * ref_px_m),
            'dz_zero_shift_m': float(np.nanmedian(d0)),
            'nmad_before_m': float(before), 'nmad_after_m': float(best[0]),
            'rms_before_m': float(np.sqrt(np.nanmean(d0 ** 2))),
            'rms_after_m': float(np.sqrt(np.nanmean((d - dz) ** 2))),
            'p99_abs_after_m': float(np.nanpercentile(np.abs(d - dz), 99)),
            'search': f'+-{max_shift_px} ref px, 0.5 px grid then 0.1 px refine, NMAD cost',
            'estimated': True,
            'significant': bool(significant),
            'applied': bool(significant and not lola),
            'policy': ('LOLA-family product: logged, never applied' if lola else
                       f'applied if |dz| > {DZ_APPLY_M} m or |dxy| > {DXY_APPLY_PX} ref px'),
            'flag': ('LOLA-family shift above threshold: investigate' if (lola and significant) else ''),
        }
    finally:
        rd.close(); rg.close()


def choose_reference(spec, specs):
    """LOLA gridded (8 global / 7 polar) overlapping the product if any, else PGDA 90 (5); never the product itself."""
    from tools.globe.pyramid import product_zone_bbox
    zones = ('sp', 'np', 'eq')

    def overlaps(a, b):
        for z in zones:
            A, B = product_zone_bbox(a, z), product_zone_bbox(b, z)
            if A and B and A[0] < B[2] and A[2] > B[0] and A[1] < B[3] and A[3] > B[1]:
                return True
        return False

    for sid in (7, 8, 5):
        cands = [s for s in specs if s.source_id == sid and s.product_id != spec.product_id and overlaps(spec, s)]
        if spec.source_id == sid:
            continue                     # a reference product family is not co-registered to itself
        if cands:
            # closest posting not finer than the product (compared at the product's or a coarser posting); else the
            # coarsest finer one (largest overlap; the comparison is then made at the product's posting)
            ge = [s for s in cands if s.native_res_m >= spec.native_res_m / 1.01]
            return min(ge, key=lambda s: s.native_res_m) if ge else max(cands, key=lambda s: s.native_res_m)
    return None


def main(root, specs=None):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    specs = specs if specs is not None else PP.all_products()
    out = {}
    for s in specs:
        ref = choose_reference(s, specs)
        if ref is None:
            out[s.product_id] = {'estimated': False, 'applied': False,
                                 'reason': 'no overlapping LOLA reference (or the product is the reference)'}
            continue
        r = estimate(s, ref)
        out[s.product_id] = r if r is not None else {'estimated': False, 'applied': False,
                                                     'reason': f'too little overlap with {ref.product_id}'}
        print(s.product_id, '->', ref.product_id, json.dumps({k: out[s.product_id].get(k) for k in
                                                               ('dx', 'dy', 'dz', 'nmad_before_m', 'nmad_after_m', 'applied', 'flag')}))
    doc = {'created_utc': _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
           'method': __doc__.strip().splitlines()[0], 'products': out}
    (root / 'coreg.json').write_text(json.dumps(doc, indent=1))
    return doc
