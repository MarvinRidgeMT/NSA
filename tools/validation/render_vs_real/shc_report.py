"""ShadowCam report from results_shc/ (A8/A9 dev pilot) or results_shc_heldout/ (A10). Adapted from wac_report.py.
Primary-track rows (Sun >= -0.5 deg) carry every metric and the claim rule; secondary-track rows (protocol §2) are
reported on SSIM and the histogram distances only. Formatting only: the claim rule and the
near-total-shadow stratum come from the registered heldout.py (A5.5, A5.6), applied unchanged; the edge limit is
2 x the median analysis pixel (the ~5 m binned grid, A8.5), as for NAC.

    python -m tools.validation.render_vs_real.shc_report [--gallery]
    POLARIS_SHC_SPLIT=heldout python -m tools.validation.render_vs_real.shc_report [--gallery]

--gallery writes local, git-ignored PNG thumbnails (crops of ShadowCam images, credit NASA/KARI/Arizona State University).
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import struct
import zlib
from pathlib import Path

import numpy as np

from . import heldout as H
from .common import ROOT, read_catalogue
from .report import METRICS, PNAME, PRODUCTS, SITES, boot_ci, fmt, paired, q, table_dist
from .shc_common import LABEL, SHC_RENDER_DIR as WAC_RENDER_DIR, SHC_RESULTS as WAC_RESULTS, SHC_SPLIT as WAC_SPLIT, eligible, guard, read_v2

DOC = ROOT / 'docs' / 'validation' / ('RENDER_VS_REAL_SHC_DEV.md' if WAC_SPLIT == 'dev' else 'RENDER_VS_REAL_SHC_HELDOUT.md')
GAL = ROOT / 'docs' / 'validation' / ('render_vs_real_shc' if WAC_SPLIT == 'dev' else 'render_vs_real_shc_heldout')
HERE = Path(__file__).resolve().parent


def _load(d, scores='scores.jsonl'):
    s = [json.loads(l) for l in (d / scores).read_text().splitlines() if l.strip()] if (d / scores).exists() else []
    g = list(csv.DictReader(open(d / 'geometry.csv'))) if (d / 'geometry.csv').exists() else []
    sel = json.loads((d / 'selection.json').read_text()) if (d / 'selection.json').exists() else {}
    log = [json.loads(l) for l in (d / 'RUN_LOG.jsonl').read_text().splitlines() if l.strip()] if (d / 'RUN_LOG.jsonl').exists() else []
    return s, g, sel, log


def hl(scores, product='pgda78_5m', phot='hapke', reg=True, track='primary'):
    return [r for r in scores if r.get('status') == 'scored' and r.get('product') == product and r.get('photometry') == phot
            and r.get('registered') == reg and (track is None or r.get('track', 'primary') == track)]


def _primary(scores):
    """Records of primary-track rows with orbit renamed so heldout.claim_rule / near_total_shadow (GRGM900C filter) apply."""
    return [{**r, 'orbit': 'grgm900c'} for r in scores if r.get('track') == 'primary']


def _png(path, img):
    h, w, _ = img.shape
    raw = b''.join(b'\x00' + img[i].tobytes() for i in range(h))

    def ch(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) +
                           ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b''))


def thumb(key, rec):
    """real | render | real with the predicted shadow in blue (registered offset applied), 2x nearest-neighbour."""
    from scipy import ndimage
    d = WAC_RENDER_DIR / f'{key[0]}__{key[1]}'
    real = np.load(d / 'real_binned.npz')['iof'].astype(float)
    rz = np.load(d / 'pgda78_5m.reduced.npz')
    ren = rz['beauty'].astype(float)
    dy, dx = rec.get('regDyPx', 0.0) or 0.0, rec.get('regDxPx', 0.0) or 0.0
    lit = ndimage.shift(rz['lit'].astype(float), (dy, dx), order=0) >= 0.5

    def st(a):
        a = np.where(np.isfinite(a), a, 0)
        lo, hi = np.percentile(a, [1, 99.5])
        return (np.clip((a - lo) / (hi - lo + 1e-12), 0, 1) ** 0.5 * 255).astype(np.uint8)
    r8, b8 = st(real), st(ren)
    ov = np.stack([r8] * 3, -1)
    ov[~lit, 2] = 255
    ov[~lit, 0] //= 2
    img = np.concatenate([np.stack([r8] * 3, -1), np.stack([b8] * 3, -1), ov], 1).repeat(2, 0).repeat(2, 1)
    GAL.mkdir(parents=True, exist_ok=True)
    p = GAL / f'{key[0]}__{key[1]}.png'
    _png(p, np.ascontiguousarray(img))
    return p.name


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--gallery', action='store_true')
    ap.add_argument('--scores', default='scores.jsonl', help='scores file in the results directory')
    ap.add_argument('--doc', default='', help='output Markdown path (default: RENDER_VS_REAL_SHC_DEV/HELDOUT.md)')
    ap.add_argument('--title', default='', help='title override')
    a = ap.parse_args(argv)
    doc = Path(a.doc) if a.doc else DOC
    scores_all, geo, sel, log = _load(WAC_RESULTS, a.scores)
    nac_dev, *_ = _load(HERE / 'results')
    guard({r['product_id'] for r in scores_all} | {g['product_id'] for g in geo}, read_catalogue())
    rows = read_v2()
    cat = {(r['product_id'], r['site']): r for r in rows}
    raw = scores_all
    secondary = hl(raw, track='secondary')
    secondary_u = hl(raw, reg=False, track='secondary')
    scores_all = _primary(raw)
    rr = hl(scores_all)
    native = {(r['product_id'], r['site']): float(cat[(r['product_id'], r['site'])]['pixel_scale_m']) for r in rr}
    L = []
    w = L.append
    title = a.title or ('dev (training) pilot, Amendments A8–A9' if WAC_SPLIT == 'dev' else 'held-out run, Amendment A10')
    rule = collections.Counter(r.get('saturationRule', 'dropped (A8.5)') for r in raw)
    w(f'# Render vs real — ShadowCam (KPLO), {title}\n')
    w(f'**{LABEL}.** Protocol `docs/v2/RENDER_VS_REAL_PROTOCOL.md` (frozen) + amendments A1–A9'
      f"{' and A10' if WAC_SPLIT != 'dev' else ''} (hashes in `docs/v2/PREREGISTRATION.md`). Generated by "
      '`tools/validation/render_vs_real/shc_report.py`. Catalogue v2 and the camera model: A8; TDI-B sample axis and start '
      'time: A9. A good score validates render geometry only; it does not certify illumination power, DSN or link '
      'availability.\n')
    w('Imagery: ShadowCam CAL radiance, NASA PDS ShadowCam archive (ASU). Credit: '
      '**NASA/KARI/Arizona State University**. SPICE: USGS public KPLO kernels (asc-isisdata `usgs_data/kplo`). Terrain: '
      'LOLA (PGDA 78, PGDA 90, PDS LDEM). Photometry: Hapke 643 nm parameters applied to the 450–750 nm ShadowCam band '
      '(an approximation, A8.5).\n')
    w(f'Saturated blocks (directly sunlit ground saturates ShadowCam): {dict(rule)} — "dropped" = removed from the window '
      '(A8.5 as registered); "lit" = kept in the window and counted as lit, the base protocol §4.1 rule (restored by A10).\n')
    # 1 accounting
    w('## 1. Every selected row\n')
    gs = collections.Counter(g['status'] for g in geo)
    w(f"- Selection: {sel.get('nRows', '?')} rows / {sel.get('nImages', '?')} images of {sel.get('eligibleRows', '?')} eligible rows "
      f"/ {sel.get('eligibleImages', '?')} images; gated by metadata: {sel.get('gatedByMetadata', {})}; not selected: "
      f"{sel.get('notSelectedRowsByReason', {})}.")
    w(f"- Geometry: {gs.get('ok', 0)} OK, {gs.get('gated', 0)} gated, {gs.get('failed', 0)} failed.")
    hp_all = [r for r in raw if r.get('product') == 'pgda78_5m' and r.get('photometry') == 'hapke' and r.get('registered')]
    st = collections.Counter(r.get('status') for r in hp_all)
    failed = [r for r in raw if r.get('status') == 'failed']
    trk = collections.Counter((r.get('track'), r.get('tdi')) for r in hp_all if r.get('status') == 'scored')
    w(f"- Scored (PGDA 78, Hapke, registered): {st.get('scored', 0)} rows — primary track {trk[('primary', 'A')]} TDI A + "
      f"{trk[('primary', 'B')]} TDI B; secondary track {trk[('secondary', 'A')]} TDI A + {trk[('secondary', 'B')]} TDI B; "
      f"gated at scoring: {st.get('gated', 0)}; failed: {len({(r['product_id'], r['site']) for r in failed})}. Orbit: KPLO "
      'reconstructed SPK (USGS); every primary-track row enters the claim.')
    sg_ = [r for r in raw if r.get('status') == 'gated']
    if sg_:
        w('- Gated at scoring (any product): ' + '; '.join(f"{r['product_id']} {r['site']} {r['product']} "
                                                            f"{'reg' if r['registered'] else 'unreg'}: {r.get('reason', '')[:80]}" for r in sg_))
    if log:
        w(f"- Run log: started {log[0].get('utc')} at commit `{str(log[0].get('commit', ''))[:10]}`; "
          f"{sum(1 for x in log if x.get('event') == 'start')} start(s); last stop {next((x['utc'] for x in reversed(log) if x.get('event') == 'stop'), '—')}.")
    ok_geo = [g for g in geo if g['status'] == 'ok']
    if ok_geo:
        gsd = [float(g['gsd_binned_m']) for g in ok_geo]
        em = [float(g['emission_site_deg']) for g in ok_geo]
        w(f"- Binned analysis pixel at the site: median {q(gsd, 50):.2f} m (P10 {q(gsd, 10):.2f}, P90 {q(gsd, 90):.2f}); bins "
          f"{dict(collections.Counter(g['bin'] for g in ok_geo))}; emission at the site median {q(em, 50):.1f}° (max {max(em):.1f}°). "
          f"Camera-model centre vs the label centre: median {q([float(g['centre_vs_label_m']) for g in ok_geo], 50):.0f} m; "
          f"ISIS start time − label start median {q([float(g['timing_start_diff_ms']) for g in ok_geo], 50):.0f} ms "
          f"(reported, not gates; A8, A9). SPICE fit position error max {max(float(g['fit_pos_err_m']) for g in ok_geo):.4f} m.")
    w('\nStrata of the scored primary-track rows vs all eligible primary-track rows of this split (catalogue v2 gates):\n')
    keys = {(r['product_id'], r['site']) for r in rr}
    split = 'dev' if WAC_SPLIT == 'dev' else 'heldout'
    elig = [r for r in rows if r['split'] == split and eligible(r)[0] and float(r['sun_el_deg']) >= -0.5]
    for col in ('site', 'el_bin', 'az_bin', 'em_bin'):
        ca = collections.Counter(r[col] for r in elig)
        cs = collections.Counter(cat[k][col] for k in keys)
        w(f"- **{col}**: " + ', '.join(f'{k} {cs.get(k, 0)}/{v}' for k, v in sorted(ca.items())))
    # 2 claim rule
    w('\n## 2. Protocol §8 claim rule per site (A5.6 rule, binned analysis pixel)\n')
    w(('**Dry run on dev records — a code check, not a claim.** ' if WAC_SPLIT == 'dev' else '') +
      'Registered, Hapke, primary-track rows. Conditions: (1) median shadow IoU ≥ 0.80; (2) median edge error ≤ 2 × the median '
      'binned analysis pixel (~5 m, A8.5); (3) beats the flat-sphere control on ≥ 80 % of paired images for '
      'IoU **and** for edge error.\n')

    def beat(f, n):
        return f'{round(f * n)}/{n} ({f:.1%})' if n else '—'
    for p in ('pgda78_5m', 'lola_ldem875s_5m', 'pgda90_80m'):
        cr = H.claim_rule(scores_all, native, sites=SITES, product=p)
        w(f'### {PNAME[p]}' + (' (headline)' if p == 'pgda78_5m' else '') + '\n')
        w('| site | n | median IoU | median edge m (n) | limit m (2 × pixel) | beats control: IoU / edge (pairs) | result |')
        w('|---|---|---|---|---|---|---|')
        for s in SITES:
            c = cr[s]
            if not c['n']:
                w(f'| {s} | 0 | — | — | — | — | no scored rows |')
                continue
            verdict = ('**met**' if c['claim'] else 'not met: ' + ', '.join(c['failed']))
            w(f"| {s} | {c['n']} | {fmt(c['medianIouShadow'])} | {fmt(c['medianEdgeM'], 1)} ({c['nEdge']}) | {fmt(c['edgeLimitM'], 1)} | "
              f"{beat(c['fracBeatsControlIou'], c['nPairs'])} / {beat(c['fracBeatsControlEdge'], c['nPairs'])} | {verdict} |")
        w('')
    if WAC_SPLIT != 'dev':
        crs = {p: H.claim_rule(scores_all, native, sites=SITES, product=p) for p in ('pgda78_5m', 'lola_ldem875s_5m', 'pgda90_80m')}
        fail12 = all(not c['conditions']['iou'] and not c['conditions']['edge'] for cr in crs.values() for c in cr.values() if c['n'])
        cm = q([r.get('cmIouShadow') for r in rr], 50)
        w('**Check of the A7.4 prediction (written before the run):** (a) the claim fails conditions 1 and 2 at every site for '
          f"every product — **{'confirmed' if fail12 else 'NOT confirmed'}**; (b) count-matched shadow IoU median ≥ 0.9 — "
          f"**{'confirmed' if cm >= 0.9 else 'NOT confirmed'}** ({fmt(cm)}). The claim is therefore not met for LROC WAC at any "
          'site under the registered rule; the count-matched mask is a sensitivity result and is not a claim.\n')
    # 3 distributions
    w('## 3. Score distributions — PGDA 78 5 m, Hapke, registered (headline)\n')
    w(table_dist(rr))
    w('\nSame, **unregistered**:\n')
    w(table_dist(hl(scores_all, reg=False)))
    w('\n### 3.1 Per site\n')
    w('| site | n | shadow IoU median (IQR) | edge median m (IQR) | edge median px | SSIM median | weak-bimodality rows |')
    w('|---|---|---|---|---|---|---|')
    for s in SITES:
        x = [r for r in rr if r['site'] == s]
        iou = [r['iouShadow'] for r in x]
        ed = [r['edgeMedianM'] for r in x]
        w(f"| {s} | {len(x)} | {fmt(q(iou, 50))} ({fmt(q(iou, 25))}–{fmt(q(iou, 75))}) | {fmt(q(ed, 50), 1)} "
          f"({fmt(q(ed, 25), 1)}–{fmt(q(ed, 75), 1)}) | {fmt(q([r['edgeMedianPx'] for r in x], 50), 2)} | "
          f"{fmt(q([r['ssim'] for r in x], 50))} | {sum(bool(r.get('weakBimodality')) for r in x)} |")
    w('\n### 3.2 By Sun elevation bin\n')
    w('| el_bin | n | shadow IoU median | lit IoU median | edge median m | obs. shadow fraction median |')
    w('|---|---|---|---|---|---|')
    for b in sorted({cat[(r['product_id'], r['site'])]['el_bin'] for r in rr}):
        x = [r for r in rr if cat[(r['product_id'], r['site'])]['el_bin'] == b]
        w(f"| {b} | {len(x)} | {fmt(q([r['iouShadow'] for r in x], 50))} | {fmt(q([r['iouLit'] for r in x], 50))} | "
          f"{fmt(q([r['edgeMedianM'] for r in x], 50), 1)} | {fmt(q([r['obsShadowFrac'] for r in x], 50))} |")
    # 4 NAC and WAC next to ShadowCam
    w('\n## 4. Next to the NAC and WAC dev pilots' + (' and the ShadowCam dev pilot' if WAC_SPLIT != 'dev' else '') +
      ' (PGDA 78, Hapke, registered; primary track; labelled; different images)\n')
    nd = hl(nac_dev)
    wd = hl(_load(HERE / 'results_wac')[0])
    cols = [('NAC dev', nd), ('WAC dev', wd)] + \
        ([('ShadowCam dev', hl(_load(HERE / 'results_shc')[0]))] if WAC_SPLIT != 'dev' else []) + \
        [('ShadowCam ' + ('dev' if WAC_SPLIT == 'dev' else 'held-out'), rr)]
    w('| metric | ' + ' | '.join(f'{c} n | {c} median' for c, _ in cols) + ' |')
    w('|---|' + '---|---|' * len(cols))
    for k, name, d in METRICS + [('edgeMedianPx', 'edge median px', 2), ('gsdMedianM', 'pixel m', 1), ('cmIouShadow', 'count-matched shadow IoU', 3)]:
        cells = []
        for _c, recs in cols:
            v = [r.get(k) for r in recs]
            cells.append(f"{sum(1 for x in v if isinstance(x, (int, float)) and math.isfinite(x))} | {fmt(q(v, 50), d)}")
        w(f"| {name} | {' | '.join(cells)} |")
    # 5 products
    w('\n## 5. Terrain products (paired on the same rows; Hapke, registered, primary track)\n')
    w('| product | n | shadow IoU median | edge median m | edge unmatched | SSIM | W1 |')
    w('|---|---|---|---|---|---|---|')
    for p in PRODUCTS:
        x = hl(scores_all, p)
        w(f"| {PNAME[p]} | {len(x)} | {fmt(q([r['iouShadow'] for r in x], 50))} | {fmt(q([r['edgeMedianM'] for r in x], 50), 1)} | "
          f"{fmt(q([r['edgeUnmatchedFrac'] for r in x], 50))} | {fmt(q([r['ssim'] for r in x], 50))} | "
          f"{fmt(q([r['wasserstein1'] for r in x], 50))} |")
    w('\nPaired per-row differences: median and bootstrap 95 % interval (10,000 resamples, seed `polaris-x-v2-boot`); '
      'descriptive. IoU, SSIM: positive = first better; edge, W1: negative = first better.\n')
    w('| comparison | metric | n pairs | median diff | 95 % interval | first better in |')
    w('|---|---|---|---|---|---|')
    sub = [r for r in scores_all if r.get('orbit') == 'grgm900c']
    for a_, b_ in (('pgda78_5m', 'flat'), ('pgda78_5m', 'pgda90_80m'), ('pgda78_5m', 'lola_ldem875s_5m'), ('pgda90_80m', 'flat')):
        for m in ('iouShadow', 'edgeMedianM', 'ssim', 'wasserstein1'):
            d, _k = paired(sub, a_, b_, m)
            if not d:
                continue
            lo, hi = boot_ci(d)
            better = np.mean([(x > 0) if m in ('iouShadow', 'ssim') else (x < 0) for x in d])
            w(f'| {PNAME[a_]} − {PNAME[b_]} | {m} | {len(d)} | {fmt(float(np.median(d)))} | {fmt(lo)} … {fmt(hi)} | {better:.0%} |')
    # 6 strata
    w('\n## 6. Near-total-shadow windows (A5.5 stratum) and the count-matched mask\n')
    nts = H.near_total_shadow(scores_all)
    w('| stratum | n | Otsu shadow IoU median (IQR) | Otsu lit IoU median | count-matched shadow IoU | count-matched lit IoU |')
    w('|---|---|---|---|---|---|')
    for name, x in (('all rows', rr), (f'predicted shadow ≥ {H.NEAR_TOTAL_SHADOW}', [r for r in rr if (r['product_id'], r['site']) in nts]),
                    ('the rest', [r for r in rr if (r['product_id'], r['site']) not in nts])):
        iou = [r['iouShadow'] for r in x]
        w(f"| {name} | {len(x)} | {fmt(q(iou, 50))} ({fmt(q(iou, 25))}–{fmt(q(iou, 75))}) | {fmt(q([r['iouLit'] for r in x], 50))} | "
          f"{fmt(q([r.get('cmIouShadow') for r in x], 50))} | {fmt(q([r.get('cmIouLit') for r in x], 50))} |")
    thr = [r.get('otsuThresholdLog10') for r in rr]
    w(f"\n**Where the fixed Otsu rule puts the threshold on ShadowCam:** median log10 normalised-radiance threshold {fmt(q(thr, 50), 2)} (IQR "
      f"{fmt(q(thr, 25), 2)} to {fmt(q(thr, 75), 2)}); rows with the threshold within 0.1 of the -5 floor of "
      f"v = log10(max(I/F, 1e-5)): {sum(1 for t in thr if isinstance(t, float) and t <= -4.9)} of {len(rr)}. Observed shadow "
      f"fraction median {fmt(q([r['obsShadowFrac'] for r in rr], 50))} against predicted {fmt(q([r['predShadowFrac'] for r in rr], 50))}. "
      'ShadowCam is built to image permanently shadowed ground by light scattered from nearby sunlit terrain, so its '
      'shadows are not dark at the floor; the render has no secondary illumination, so the fixed rule can separate lit '
      'from shadowed ground differently in the two images. The count-matched mask (A5.5) does not depend on that '
      'threshold.\n')
    w(f"\nWeak-bimodality rows: {sum(bool(r.get('weakBimodality')) for r in rr)}; render median zero (A1.4 fallback): "
      f"{sum(bool(r.get('renderMedianZero')) for r in rr)} of {len(rr)}.\n")
    # 7 registration
    w('## 7. Registration and orbit\n')
    off = [r['regOffsetM'] for r in rr]
    px = [math.hypot(r['regDyPx'], r['regDxPx']) for r in rr]
    w(f"- Offset ( primary track; search ± max(3 binned px, 150 m) on each image axis, A8.5): median {fmt(q(px, 50), 2)} px = {fmt(q(off, 50), 0)} m; "
      f"P90 {fmt(q(px, 90), 2)} px = {fmt(q(off, 90), 0)} m; at the search bound: {sum(bool(r['regAtBound']) for r in rr)}; "
      f"NCC median {fmt(q([r['regNcc'] for r in rr], 50))}; rows with NCC < 0.05: {sum(r['regNcc'] < 0.05 for r in rr)}.")
    w(f"- Along the Sun azimuth (real − render): median {fmt(q([r.get('regOffsetAlongSunM') for r in rr], 50), 0)} m; across: "
      f"median {fmt(q([r.get('regOffsetAcrossSunM') for r in rr], 50), 0)} m. Lines (dy) median {fmt(q([r['regDyPx'] for r in rr], 50), 2)} px, "
      f"samples (dx) median {fmt(q([r['regDxPx'] for r in rr], 50), 2)} px.")
    for t in ('A', 'B'):
        x = [r for r in rr if r.get('tdi') == t]
        if x:
            w(f"- TDI {t}: {len(x)} rows; offset median {fmt(q([r['regOffsetM'] for r in x], 50), 0)} m, lines (dy) median "
              f"{fmt(q([r['regDyPx'] for r in x], 50), 2)} px, samples (dx) median {fmt(q([r['regDxPx'] for r in x], 50), 2)} px; "
              f"shadow IoU median {fmt(q([r['iouShadow'] for r in x], 50))}; edge median {fmt(q([r['edgeMedianM'] for r in x], 50), 1)} m.")
    # 7.1 secondary track
    w('\n### 7.1 Secondary-illumination track (Sun < −0.5° at the site; SSIM and histogram distances only, A8.5)\n')
    w('Shadow metrics are not applicable to these rows and are not shown. The render has no light scattered from nearby '
      'terrain, so these rows test only whether the scene geometry lines up with what ShadowCam sees in scattered light.\n')
    w('| site | n | SSIM median registered (unregistered) | W1 median | JSD bits median | NCC median | offset median m |')
    w('|---|---|---|---|---|---|---|')
    for s in SITES + ['all']:
        x = secondary if s == 'all' else [r for r in secondary if r['site'] == s]
        xu = secondary_u if s == 'all' else [r for r in secondary_u if r['site'] == s]
        if not x:
            continue
        w(f"| {s} | {len(x)} | {fmt(q([r['ssim'] for r in x], 50))} ({fmt(q([r['ssim'] for r in xu], 50))}) | "
          f"{fmt(q([r['wasserstein1'] for r in x], 50))} | {fmt(q([r['jsdBits'] for r in x], 50))} | "
          f"{fmt(q([r.get('regNcc') for r in x], 50))} | {fmt(q([r['regOffsetM'] for r in x], 50), 0)} |")
    sp = {(r['product_id'], r['site']): r for r in raw if r.get('track') == 'secondary' and r.get('status') == 'scored'
          and r['product'] == 'flat' and r['photometry'] == 'hapke' and r['registered']}
    pr = [(r['ssim'], sp[(r['product_id'], r['site'])]['ssim']) for r in secondary if (r['product_id'], r['site']) in sp]
    if pr:
        w(f"\nSecondary-track PGDA 78 SSIM above the flat control on {sum(a > b for a, b in pr)} of {len(pr)} rows (descriptive).")
    # 8 photometry
    w('\n## 8. Photometric models (PGDA 78, registered, primary track)\n')
    w('| photometry | n | SSIM median | W1 median | JSD median | registration NCC median |')
    w('|---|---|---|---|---|---|')
    for ph in ('hapke', 'lunarlambert:0.5', 'lommel'):
        x = hl(scores_all, 'pgda78_5m', ph)
        w(f"| {ph} | {len(x)} | {fmt(q([r['ssim'] for r in x], 50))} | {fmt(q([r['wasserstein1'] for r in x], 50))} | "
          f"{fmt(q([r['jsdBits'] for r in x], 50))} | {fmt(q([r.get('regNcc') for r in x], 50))} |")
    # 9 gated / failed
    w('\n## 9. Gated and failed rows\n')
    reasons = collections.Counter(g['reason'].split(':')[0] + (':' + g['reason'].split(':')[1][:40] if ':' in g['reason'] else '')
                                  for g in geo if g['status'] != 'ok')
    for k, v in reasons.most_common():
        w(f'- geometry {v}: {k}')
    sg = collections.Counter(r.get('reason', '')[:60] for r in hp_all if r.get('status') == 'gated')
    for k, v in sg.most_common():
        w(f'- scoring gated {v}: {k}')
    for r in failed[:20]:
        w(f"- failed: {r['product_id']} {r['site']}: {r.get('reason', '')[:120]}")
    # 10 gallery
    w('\n## 10. Gallery (local only)\n')
    rnd = sorted(rr, key=lambda r: hashlib.sha256(f"polaris-x-v2-gallery:{r['product_id']}:{r['site']}".encode()).hexdigest())[:12]
    worst = sorted(rr, key=lambda r: r['iouShadow'])[:max(1, len(rr) // 10)]
    w(f'Thumbnails (real | render | real with predicted shadow in blue) are crops of NASA/KARI/ASU ShadowCam images, so they are **not in '
      f'git**; `--gallery` writes them to `{GAL.relative_to(ROOT)}/`.\n')
    w('| set | product id | site | shadow IoU | edge median m | pred / obs shadow frac | offset px |')
    w('|---|---|---|---|---|---|---|')
    for name, x in (('random', rnd), ('worst 10 %', worst)):
        for r in x:
            w(f"| {name} | {r['product_id']} | {r['site']} | {fmt(r['iouShadow'])} | {fmt(r['edgeMedianM'], 1)} | "
              f"{fmt(r['predShadowFrac'], 2)} / {fmt(r['obsShadowFrac'], 2)} | {fmt(math.hypot(r['regDyPx'], r['regDxPx']), 2)} |")
            if a.gallery:
                thumb((r['product_id'], r['site']), r)
    doc.write_text('\n'.join(L) + '\n')
    print(f'wrote {doc}')


if __name__ == '__main__':
    main()
