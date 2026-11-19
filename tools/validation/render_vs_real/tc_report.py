"""Kaguya TC report from results_tc/ (A11/A12 dev pilot) or results_tc_heldout/ (A13). Adapted from shc_report.py.
Primary-track rows (Sun >= -0.5 deg) carry every metric and the claim rule; secondary-track rows (protocol §2) are
reported on SSIM and the histogram distances only. Formatting only: the claim rule and the near-total-shadow stratum
come from the registered heldout.py (A5.5, A5.6), applied unchanged to the headline orbit (the RISE solution named in
each label, A11.3); the edge limit is 2 x the median analysis pixel (TC is unbinned, A11.5). Stereo / mono, TC1 / TC2,
RISE solution and the GRGM900C comparison orbit (scores_grgm900c.jsonl, when present) are shown separately (A11.5).

    python -m tools.validation.render_vs_real.tc_report [--gallery]
    POLARIS_TC_SPLIT=heldout python -m tools.validation.render_vs_real.tc_report [--gallery]

--gallery writes local, git-ignored PNG thumbnails (crops of Kaguya TC images, credit JAXA/SELENE).
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import math
from pathlib import Path

import numpy as np

from . import heldout as H
from .common import ROOT, read_catalogue
from .report import METRICS, PNAME, PRODUCTS, SITES, boot_ci, fmt, paired, q, table_dist
from .shc_report import _load, _png
from .tc_common import LABEL, TC_RENDER_DIR, TC_RESULTS, TC_SPLIT, eligible, guard, tc_rows

DEV = TC_SPLIT == 'dev'
DOC = ROOT / 'docs' / 'validation' / ('RENDER_VS_REAL_TC_DEV.md' if DEV else 'RENDER_VS_REAL_TC_HELDOUT.md')
GAL = ROOT / 'docs' / 'validation' / ('render_vs_real_tc' if DEV else 'render_vs_real_tc_heldout')
HERE = Path(__file__).resolve().parent


def hl(scores, product='pgda78_5m', phot='hapke', reg=True, track='primary'):
    return [r for r in scores if r.get('status') == 'scored' and r.get('product') == product and r.get('photometry') == phot
            and r.get('registered') == reg and (track is None or r.get('track', 'primary') == track)]


def _primary(scores):
    """Primary-track records with the headline orbit renamed so heldout.claim_rule / near_total_shadow (which filter on
    orbit 'grgm900c' for NAC) apply unchanged to TC's headline orbit (the label's RISE solution)."""
    return [{**r, 'orbit': 'grgm900c'} for r in scores if r.get('track') == 'primary']


def thumb(key, rec):
    """real | render | real with the predicted shadow in blue (registered offset applied), 1x."""
    from scipy import ndimage
    d = TC_RENDER_DIR / f'{key[0]}__{key[1]}'
    real = np.load(d / 'real_binned.npz')['iof'].astype(float)
    rp = d / 'pgda78_5m.reduced.npz'
    rz = np.load(rp if rp.exists() else d / 'pgda78_5m.npz')
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
    img = np.concatenate([np.stack([r8] * 3, -1), np.stack([b8] * 3, -1), ov], 1)
    GAL.mkdir(parents=True, exist_ok=True)
    p = GAL / f'{key[0]}__{key[1]}.png'
    _png(p, np.ascontiguousarray(img))
    return p.name


def _row(name, x):
    iou = [r['iouShadow'] for r in x]
    ed = [r['edgeMedianM'] for r in x]
    return (f"| {name} | {len(x)} | {fmt(q(iou, 50))} ({fmt(q(iou, 25))}–{fmt(q(iou, 75))}) | {fmt(q(ed, 50), 1)} "
            f"({fmt(q(ed, 25), 1)}–{fmt(q(ed, 75), 1)}) | {fmt(q([r['edgeMedianPx'] for r in x], 50), 2)} | "
            f"{fmt(q([r['ssim'] for r in x], 50))} | {fmt(q([r['regOffsetM'] for r in x], 50), 0)} | "
            f"{fmt(q([r['regDyPx'] for r in x], 50), 1)} / {fmt(q([r['regDxPx'] for r in x], 50), 1)} | "
            f"{fmt(q([r['regNcc'] for r in x], 50))} |")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--gallery', action='store_true')
    ap.add_argument('--doc', default='')
    a = ap.parse_args(argv)
    doc = Path(a.doc) if a.doc else DOC
    raw, geo, sel, log = _load(TC_RESULTS)
    grg, ggeo, _, _ = _load(TC_RESULTS, 'scores_grgm900c.jsonl')
    if (TC_RESULTS / 'geometry_grgm900c.csv').exists():
        import csv
        ggeo = list(csv.DictReader(open(TC_RESULTS / 'geometry_grgm900c.csv')))
    else:
        ggeo = []
    cat_rows = read_catalogue()
    guard({r['product_id'] for r in raw} | {g['product_id'] for g in geo}, cat_rows)
    cat = {(r['product_id'], r['site']): r for r in cat_rows}
    ptype = {k: ('mono' if v['instrument'].endswith('mono') else 'stereo') for k, v in cat.items()}
    secondary = hl(raw, track='secondary')
    secondary_u = hl(raw, reg=False, track='secondary')
    S = _primary(raw)
    rr = hl(S)
    native = {(r['product_id'], r['site']): float(cat[(r['product_id'], r['site'])]['pixel_scale_m']) for r in rr}
    L = []
    w = L.append
    title = 'dev (training) pilot, Amendments A11–A12' if DEV else 'held-out run, Amendment A13'
    w(f'# Render vs real — Kaguya Terrain Camera (SELENE), {title}\n')
    w(f'**{LABEL}.** Protocol `docs/v2/RENDER_VS_REAL_PROTOCOL.md` (frozen) + amendments A1–A12'
      f"{'' if DEV else ' and A13'} (hashes in `docs/v2/PREREGISTRATION.md`). Generated by "
      '`tools/validation/render_vs_real/tc_report.py`. Camera model and orbit: A11; start time, sample axis, registration '
      'radius: A12. A good score validates render geometry only; it does not certify illumination power, DSN or link '
      'availability.\n')
    w('Imagery: Kaguya (SELENE) Terrain Camera Level 2B0, JAXA DARTS (`data.darts.isas.jaxa.jp`), downloaded by the '
      'project owner (A11.7). Credit: **JAXA/SELENE**. SPICE: USGS public Kaguya kernels (`usgs_data/kaguya/kernels`). '
      'Orbit: the RISE solution named in each label (headline, A11.3). Terrain: LOLA (PGDA 78, PGDA 90, PDS LDEM). '
      'Photometry: Hapke 643 nm parameters applied to the 430–850 nm TC band (an approximation, A11.5).\n')
    # 1 accounting
    w('## 1. Every selected row\n')
    gs = collections.Counter(g['status'] for g in geo)
    w(f"- Selection: {sel.get('nRows', '?')} rows / {sel.get('nImages', '?')} images of {sel.get('eligibleRows', '?')} eligible "
      f"rows / {sel.get('eligibleImages', '?')} images; {sel.get('secondaryTrackRows', '?')} rows on the secondary track.")
    n_sel = sel.get('nRows', 0)
    w(f"- Geometry: {gs.get('ok', 0)} OK, {gs.get('gated', 0)} gated, {gs.get('failed', 0)} failed; "
      f"{n_sel - len(geo) if n_sel else '?'} without geometry (files never downloaded intact).")
    hp_all = [r for r in raw if r.get('product') == 'pgda78_5m' and r.get('photometry') == 'hapke' and r.get('registered')]
    st = collections.Counter(r.get('status') for r in hp_all)
    failed = [r for r in raw if r.get('status') == 'failed']
    sc = [r for r in hp_all if r.get('status') == 'scored']
    trk = collections.Counter((r.get('track'), r.get('camera'), ptype[(r['product_id'], r['site'])]) for r in sc)
    w(f"- Scored (PGDA 78, Hapke, registered): {st.get('scored', 0)} rows — "
      + ', '.join(f'{t} {c} {p} {n}' for (t, c, p), n in sorted(trk.items())) +
      f"; failed: {len({(r['product_id'], r['site']) for r in failed})}. RISE solutions: "
      f"{dict(collections.Counter(r.get('orbitSolution') for r in sc))}. Moving direction: "
      f"{dict(collections.Counter(r.get('movingDirection') for r in sc))}.")
    if log:
        w(f"- Run log: started {log[0].get('utc')} at commit `{str(log[0].get('commit', ''))[:10]}`; "
          f"{sum(1 for x in log if x.get('event') == 'start')} start(s); last stop "
          f"{next((x['utc'] for x in reversed(log) if x.get('event') == 'stop'), '—')}.")
    ok_geo = [g for g in geo if g['status'] == 'ok']
    if ok_geo:
        f_ = lambda k: [float(g[k]) for g in ok_geo if g.get(k) not in (None, '', 'nan')]
        w(f"- Analysis pixel at the site: median {q(f_('gsd_binned_m'), 50):.2f} m (P10 {q(f_('gsd_binned_m'), 10):.2f}, P90 "
          f"{q(f_('gsd_binned_m'), 90):.2f}); bins {dict(collections.Counter(g['bin'] for g in ok_geo))}; emission at the site "
          f"median {q(f_('emission_site_deg'), 50):.1f}° (max {max(f_('emission_site_deg')):.1f}°).")
        w(f"- Camera model vs JAXA's label geometry (reported, not a gate; A11.4): centre median "
          f"{q(f_('centre_vs_label_m'), 50):.0f} m, corners max median {q(f_('corners_vs_label_max_m'), 50):.0f} m (P90 "
          f"{q(f_('corners_vs_label_max_m'), 90):.0f} m). ISIS start − label start median {q(f_('timing_start_diff_ms'), 50):.0f} ms.")
        w(f"- SPICE fit (A12.3): position error max {max(f_('fit_pos_err_m')):.4f} m, attitude error max "
          f"{max(f_('fit_ang_err_urad')):.2f} µrad; segments {dict(sorted(collections.Counter(g['fit_segments'] for g in ok_geo).items()))}.")
    w('\nStrata of the scored primary-track rows vs all eligible primary-track TC rows of this split:\n')
    keys = {(r['product_id'], r['site']) for r in rr}
    split = 'dev' if DEV else 'heldout'
    elig = [r for r in tc_rows(cat_rows) if r['split'] == split and eligible(r)[0] and float(r['sun_el_deg']) >= -0.5]
    for col in ('site', 'instrument', 'el_bin', 'az_bin', 'em_bin'):
        ca = collections.Counter(r[col] for r in elig)
        cs = collections.Counter(cat[k][col] for k in keys)
        w(f"- **{col}**: " + ', '.join(f'{k} {cs.get(k, 0)}/{v}' for k, v in sorted(ca.items())))
    # 2 claim rule
    w('\n## 2. Protocol §8 claim rule per site (A5.6 rule, analysis pixel)\n')
    w(('**Dry run on dev records — a code check, not a claim.** ' if DEV else '') +
      'Registered, Hapke, primary-track rows, headline orbit. Conditions: (1) median shadow IoU ≥ 0.80; (2) median edge '
      'error ≤ 2 × the median analysis pixel; (3) beats the flat-sphere control on ≥ 80 % of paired images for IoU **and** '
      'for edge error.\n')

    def beat(f, n):
        return f'{round(f * n)}/{n} ({f:.1%})' if n else '—'
    crs = {}
    for p in ('pgda78_5m', 'lola_ldem875s_5m', 'pgda90_80m'):
        cr = crs[p] = H.claim_rule(S, native, sites=SITES, product=p)
        w(f'### {PNAME[p]}' + (' (headline)' if p == 'pgda78_5m' else '') + '\n')
        w('| site | n | median IoU | median edge m (n) | limit m (2 × pixel) | beats control: IoU / edge (pairs) | result |')
        w('|---|---|---|---|---|---|---|')
        for s in SITES:
            c = cr[s]
            if not c['n']:
                w(f'| {s} | 0 | — | — | — | — | no scored rows |')
                continue
            verdict = ('**met**' if c['claim'] else 'not met: ' + ', '.join(c['failed']))
            w(f"| {s} | {c['n']} | {fmt(c['medianIouShadow'])} | {fmt(c['medianEdgeM'], 1)} ({c['nEdge']}) | "
              f"{fmt(c['edgeLimitM'], 1)} | {beat(c['fracBeatsControlIou'], c['nPairs'])} / "
              f"{beat(c['fracBeatsControlEdge'], c['nPairs'])} | {verdict} |")
        w('')
    if not DEV:
        w('**Check of the A13.4 prediction (written before the run):**')
        ok = lambda b: '**confirmed**' if b else '**NOT confirmed**'
        live = lambda cr: [c for c in cr.values() if c['n']]
        w(f"- (a) §8 claim met at every site for PGDA 78 — {ok(all(c['claim'] for c in live(crs['pgda78_5m'])))}.")
        b = all(c['claim'] for c in live(crs['lola_ldem875s_5m'])) and all(not c['conditions']['edge'] for c in live(crs['pgda90_80m']))
        w(f"- (b) met at every site for LOLA LDEM_875S; PGDA 90 fails the edge condition at every site — {ok(b)}.")
        cm = q([r.get('cmIouShadow') for r in rr], 50)
        w(f"- (c) count-matched shadow IoU median ≥ 0.95 — {ok(cm >= 0.95)} ({fmt(cm)}).")
        dy = q([r['regDyPx'] for r in rr if ptype[(r['product_id'], r['site'])] == 'stereo'], 50)
        w(f"- (d) stereo along-track offset (dy) median within 18–26 lines — {ok(18 <= dy <= 26)} ({fmt(dy, 1)} lines).")
        lo = [r for r in rr if cat[(r['product_id'], r['site'])]['el_bin'] == 'el[-0.5,0.5)']
        oi, ci = q([r['iouShadow'] for r in lo], 50), q([r.get('cmIouShadow') for r in lo], 50)
        w(f"- (e) el[−0.5°, 0.5°): Otsu shadow IoU median < 0.50 and count-matched ≥ 0.90 — "
          f"{ok(bool(lo) and oi < 0.5 and ci >= 0.9)} (n {len(lo)}; {fmt(oi)} / {fmt(ci)}).")
        U = hl(S, reg=False)
        fe = []
        for s_ in SITES:
            x = [r for r in U if r['site'] == s_]
            if x:
                fe.append((s_, q([r['edgeMedianM'] for r in x], 50), 2 * q([r['gsdMedianM'] for r in x], 50)))
        w(f"- (f) unregistered PGDA 78 fails the edge condition at every site — "
          f"{ok(all(not (math.isfinite(e) and e <= l_) for _, e, l_ in fe))} ("
          + ', '.join(f'{s_} {fmt(e, 1)}/{fmt(l_, 1)} m' for s_, e, l_ in fe) + ').')
        w('\nThe claim is the §8 rule above; (c)–(f) are not claims.\n')
    w('### Headline (PGDA 78) by camera and product type — descriptive, not separate claims\n')
    w('| subset | site | n | median IoU | median edge m | limit m | beats control: IoU / edge | result |')
    w('|---|---|---|---|---|---|---|---|')
    for name, f in (('TC1', lambda r: r.get('camera') == 'TC1'), ('TC2', lambda r: r.get('camera') == 'TC2'),
                    ('stereo', lambda r: ptype[(r['product_id'], r['site'])] == 'stereo'),
                    ('mono', lambda r: ptype[(r['product_id'], r['site'])] == 'mono')):
        sub = [r for r in S if f(r)]
        cr = H.claim_rule(sub, native, sites=SITES, product='pgda78_5m')
        for s in SITES:
            c = cr[s]
            if c['n']:
                w(f"| {name} | {s} | {c['n']} | {fmt(c['medianIouShadow'])} | {fmt(c['medianEdgeM'], 1)} | "
                  f"{fmt(c['edgeLimitM'], 1)} | {beat(c['fracBeatsControlIou'], c['nPairs'])} / "
                  f"{beat(c['fracBeatsControlEdge'], c['nPairs'])} | {'met' if c['claim'] else 'not met: ' + ', '.join(c['failed'])} |")
    w('')
    # 3 distributions
    w('## 3. Score distributions — PGDA 78 5 m, Hapke, registered (headline)\n')
    w(table_dist(rr))
    w('\nSame, **unregistered** (A12.2: the systematic along-track offset is not removed, so these are expected to be poor):\n')
    w(table_dist(hl(S, reg=False)))
    w('\n### 3.1 Per site, camera and product type\n')
    hdr = ('| subset | n | shadow IoU median (IQR) | edge median m (IQR) | edge median px | SSIM median | offset median m | '
           'dy / dx median px | NCC median |')
    w(hdr)
    w('|---|---|---|---|---|---|---|---|---|')
    for s in SITES:
        x = [r for r in rr if r['site'] == s]
        if x:
            w(_row(s, x))
    for c in ('TC1', 'TC2'):
        w(_row(c, [r for r in rr if r.get('camera') == c]))
    for p in ('stereo', 'mono'):
        x = [r for r in rr if ptype[(r['product_id'], r['site'])] == p]
        if x:
            w(_row(p, x))
    for o in sorted({r.get('orbitSolution') for r in rr}):
        w(_row(f'orbit {o}', [r for r in rr if r.get('orbitSolution') == o]))
    w('\n### 3.2 By Sun elevation bin\n')
    w('| el_bin | n | shadow IoU median | lit IoU median | edge median m | obs. shadow fraction median |')
    w('|---|---|---|---|---|---|')
    for b in sorted({cat[(r['product_id'], r['site'])]['el_bin'] for r in rr}):
        x = [r for r in rr if cat[(r['product_id'], r['site'])]['el_bin'] == b]
        w(f"| {b} | {len(x)} | {fmt(q([r['iouShadow'] for r in x], 50))} | {fmt(q([r['iouLit'] for r in x], 50))} | "
          f"{fmt(q([r['edgeMedianM'] for r in x], 50), 1)} | {fmt(q([r['obsShadowFrac'] for r in x], 50))} |")
    # 4 other instruments
    w('\n## 4. Next to the NAC, WAC and ShadowCam dev pilots' + ('' if DEV else ' and the TC dev pilot') +
      ' (PGDA 78, Hapke, registered; primary track; labelled; different images)\n')
    cols = [('NAC dev', hl(_load(HERE / 'results')[0])), ('WAC dev', hl(_load(HERE / 'results_wac')[0])),
            ('ShadowCam dev', hl(_load(HERE / 'results_shc', 'scores_a10.jsonl')[0]))]
    if not DEV:
        cols.append(('TC dev', hl(_primary(_load(HERE / 'results_tc')[0]))))
    cols.append(('TC ' + ('dev' if DEV else 'held-out'), rr))
    w('| metric | ' + ' | '.join(f'{c} n | {c} median' for c, _ in cols) + ' |')
    w('|---|' + '---|---|' * len(cols))
    for k, name, d in METRICS + [('edgeMedianPx', 'edge median px', 2), ('gsdMedianM', 'pixel m', 1),
                                 ('cmIouShadow', 'count-matched shadow IoU', 3), ('regOffsetM', 'registration offset m', 0)]:
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
        x = hl(S, p)
        w(f"| {PNAME[p]} | {len(x)} | {fmt(q([r['iouShadow'] for r in x], 50))} | {fmt(q([r['edgeMedianM'] for r in x], 50), 1)} | "
          f"{fmt(q([r['edgeUnmatchedFrac'] for r in x], 50))} | {fmt(q([r['ssim'] for r in x], 50))} | "
          f"{fmt(q([r['wasserstein1'] for r in x], 50))} |")
    w('\nPaired per-row differences: median and bootstrap 95 % interval (10,000 resamples, seed `polaris-x-v2-boot`); '
      'descriptive. IoU, SSIM: positive = first better; edge, W1: negative = first better.\n')
    w('| comparison | metric | n pairs | median diff | 95 % interval | first better in |')
    w('|---|---|---|---|---|---|')
    for a_, b_ in (('pgda78_5m', 'flat'), ('pgda78_5m', 'pgda90_80m'), ('pgda78_5m', 'lola_ldem875s_5m'), ('pgda90_80m', 'flat')):
        for m in ('iouShadow', 'edgeMedianM', 'ssim', 'wasserstein1'):
            d, _k = paired(S, a_, b_, m)
            if not d:
                continue
            lo, hi = boot_ci(d)
            better = np.mean([(x > 0) if m in ('iouShadow', 'ssim') else (x < 0) for x in d])
            w(f'| {PNAME[a_]} − {PNAME[b_]} | {m} | {len(d)} | {fmt(float(np.median(d)))} | {fmt(lo)} … {fmt(hi)} | {better:.0%} |')
    # 6 strata
    w('\n## 6. Near-total-shadow windows (A5.5 stratum) and the count-matched mask\n')
    nts = H.near_total_shadow(S)
    w('| stratum | n | Otsu shadow IoU median (IQR) | Otsu lit IoU median | count-matched shadow IoU | count-matched lit IoU |')
    w('|---|---|---|---|---|---|')
    for name, x in (('all rows', rr), (f'predicted shadow ≥ {H.NEAR_TOTAL_SHADOW}', [r for r in rr if (r['product_id'], r['site']) in nts]),
                    ('the rest', [r for r in rr if (r['product_id'], r['site']) not in nts])):
        iou = [r['iouShadow'] for r in x]
        w(f"| {name} | {len(x)} | {fmt(q(iou, 50))} ({fmt(q(iou, 25))}–{fmt(q(iou, 75))}) | {fmt(q([r['iouLit'] for r in x], 50))} | "
          f"{fmt(q([r.get('cmIouShadow') for r in x], 50))} | {fmt(q([r.get('cmIouLit') for r in x], 50))} |")
    thr = [r.get('otsuThresholdLog10') for r in rr]
    w(f"\nOtsu threshold (log10 normalised radiance): median {fmt(q(thr, 50), 2)} (IQR {fmt(q(thr, 25), 2)} to "
      f"{fmt(q(thr, 75), 2)}). Observed shadow fraction median {fmt(q([r['obsShadowFrac'] for r in rr], 50))} against predicted "
      f"{fmt(q([r['predShadowFrac'] for r in rr], 50))}. Weak-bimodality rows: {sum(bool(r.get('weakBimodality')) for r in rr)}; "
      f"render median zero (A1.4 fallback): {sum(bool(r.get('renderMedianZero')) for r in rr)} of {len(rr)}.\n")
    # 7 registration
    w('## 7. Registration and the along-track offset (A12.2)\n')
    off = [r['regOffsetM'] for r in rr]
    w(f"- Search ± {fmt(q([r.get('regSearchPx') for r in rr], 50), 1)} px median (747.6 m, A12.2). Offset median "
      f"{fmt(q(off, 50), 0)} m (P90 {fmt(q(off, 90), 0)} m); at the search bound: {sum(bool(r['regAtBound']) for r in rr)}; "
      f"NCC median {fmt(q([r['regNcc'] for r in rr], 50))}; rows with NCC < 0.05: {sum(r['regNcc'] < 0.05 for r in rr)}.")
    gp = {(g['product_id'], g['site']): g for g in ok_geo}
    al = [r['regDyPx'] * r['gsdMedianM'] for r in rr]
    w(f"- Lines (dy, along track) median {fmt(q([r['regDyPx'] for r in rr], 50), 1)} px ≈ {fmt(q(al, 50), 0)} m (IQR "
      f"{fmt(q(al, 25), 0)} to {fmt(q(al, 75), 0)} m); samples (dx) median {fmt(q([r['regDxPx'] for r in rr], 50), 1)} px. "
      f"A12.2 expected 18–25 lines (≈ 200–290 m) along track from the pipeline test.")
    w(f"- Along the Sun azimuth (real − render): median {fmt(q([r.get('regOffsetAlongSunM') for r in rr], 50), 0)} m; across: "
      f"median {fmt(q([r.get('regOffsetAcrossSunM') for r in rr], 50), 0)} m.")
    cv = [(r['regOffsetM'], float(gp[(r['product_id'], r['site'])]['corners_vs_label_max_m'])) for r in rr
          if (r['product_id'], r['site']) in gp and gp[(r['product_id'], r['site'])].get('corners_vs_label_max_m') not in (None, '')]
    if len(cv) > 3:
        rho = float(np.corrcoef(*zip(*cv))[0, 1])
        w(f"- Registered offset against the model-vs-label corner distance: Pearson r = {rho:.2f} over {len(cv)} rows "
          '(descriptive: whether the real image sits where JAXA\'s label geometry puts it).')
    # 7.1 orbit comparison
    w('\n### 7.1 Orbit comparison: GRGM900C + altimetry vs the label\'s RISE solution (A11.3; comparison only)\n')
    if ggeo:
        gg = collections.Counter((g['status'], (g.get('reason') or '')[:50]) for g in ggeo)
        w('GRGM900C geometry on the selected rows: ' + '; '.join(f'{s} {r}: {n}' if r else f'{s}: {n}' for (s, r), n in gg.most_common()) + '.\n')
    G2 = {(r['product_id'], r['site']): r for r in hl(grg)}
    R1 = {(r['product_id'], r['site']): r for r in rr}
    pk = sorted(set(G2) & set(R1))
    if pk:
        w('| metric (PGDA 78, Hapke, registered) | n pairs | RISE median | GRGM900C median | median diff (GRGM − RISE) | 95 % interval |')
        w('|---|---|---|---|---|---|')
        for m, d_ in (('regOffsetM', 0), ('iouShadow', 3), ('edgeMedianM', 1), ('ssim', 3), ('regNcc', 3)):
            d = [G2[k][m] - R1[k][m] for k in pk if all(isinstance(v, float) and math.isfinite(v) for v in (G2[k][m], R1[k][m]))]
            if not d:
                continue
            lo, hi = boot_ci(d)
            w(f"| {m} | {len(d)} | {fmt(q([R1[k][m] for k in pk], 50), d_)} | {fmt(q([G2[k][m] for k in pk], 50), d_)} | "
              f"{fmt(float(np.median(d)), d_)} | {fmt(lo, d_)} … {fmt(hi, d_)} |")
        gu = {(r['product_id'], r['site']): r for r in hl(grg, reg=False)}
        ru = {(r['product_id'], r['site']): r for r in hl(S, reg=False)}
        pu = sorted(set(gu) & set(ru))
        if pu:
            w(f"\nUnregistered shadow IoU on the same rows: RISE median {fmt(q([ru[k]['iouShadow'] for k in pu], 50))}, GRGM900C "
              f"median {fmt(q([gu[k]['iouShadow'] for k in pu], 50))} (n {len(pu)}).")
    else:
        w('No GRGM900C rows scored.')
    # 7.2 secondary track
    w('\n### 7.2 Secondary-illumination track (Sun < −0.5° at the site; SSIM and histogram distances only)\n')
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
    w('\nSSIM is undefined (shown —) where the render is entirely dark; such rows test nothing on this track.')
    # 8 photometry
    w('\n## 8. Photometric models (PGDA 78, registered, primary track)\n')
    w('| photometry | n | SSIM median | W1 median | JSD median | registration NCC median |')
    w('|---|---|---|---|---|---|')
    for ph in ('hapke', 'lunarlambert:0.5', 'lommel'):
        x = hl(S, 'pgda78_5m', ph)
        w(f"| {ph} | {len(x)} | {fmt(q([r['ssim'] for r in x], 50))} | {fmt(q([r['wasserstein1'] for r in x], 50))} | "
          f"{fmt(q([r['jsdBits'] for r in x], 50))} | {fmt(q([r.get('regNcc') for r in x], 50))} |")
    # 9 gated / failed
    w('\n## 9. Gated and failed rows\n')
    reasons = collections.Counter((g.get('reason') or '')[:90] for g in geo if g['status'] != 'ok')
    for k, v in reasons.most_common():
        w(f'- geometry {v}: {k}')
    if n_sel and n_sel > len(geo):
        w(f'- no geometry: {n_sel - len(geo)} rows whose files were never downloaded intact.')
    for r in failed[:20]:
        w(f"- failed: {r['product_id']} {r['site']}: {r.get('reason', '')[:120]}")
    if not reasons and not failed:
        w('- none')
    # 10 gallery
    w('\n## 10. Gallery (local only)\n')
    rnd = sorted(rr, key=lambda r: hashlib.sha256(f"polaris-x-v2-gallery:{r['product_id']}:{r['site']}".encode()).hexdigest())[:12]
    worst = sorted(rr, key=lambda r: r['iouShadow'])[:max(1, len(rr) // 10)]
    w(f'Thumbnails (real | render | real with predicted shadow in blue) are crops of JAXA Kaguya TC images, so they are **not in '
      f'git**; `--gallery` writes them to `{GAL.relative_to(ROOT)}/`.\n')
    w('| set | product id | site | camera | shadow IoU | edge median m | pred / obs shadow frac | offset m |')
    w('|---|---|---|---|---|---|---|---|')
    for name, x in (('random', rnd), ('worst 10 %', worst)):
        for r in x:
            w(f"| {name} | {r['product_id']} | {r['site']} | {r.get('camera')} | {fmt(r['iouShadow'])} | {fmt(r['edgeMedianM'], 1)} | "
              f"{fmt(r['predShadowFrac'], 2)} / {fmt(r['obsShadowFrac'], 2)} | {fmt(r['regOffsetM'], 0)} |")
            if a.gallery:
                thumb((r['product_id'], r['site']), r)
    doc.write_text('\n'.join(L) + '\n')
    print(f'wrote {doc}')
    return crs


if __name__ == '__main__':
    main()
