"""Choose the dev (training) LROC NAC images for the R4 pilot.

Rule (fixed before any image is fetched; never uses image content or scores):
  1. rows with split = dev, instrument LROC_NAC, passing the protocol §2 metadata gates;
  2. each image is assigned to the NAIF `lrosc` spacecraft-attitude CK window (≈10 days) that contains its start time;
  3. whole windows are taken in descending order of (eligible images / CK megabytes), ties by SHA-256(seed:window), until the
     target image count is reached. This is cluster sampling under a download budget: the CK files dominate the bytes.
The strata of the sample are reported against the eligible population (report.py).

    python -m tools.validation.render_vs_real.select --target 200
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib

from . import spice_kernels as sk
from .common import RESULTS, assert_dev, check_frozen, eligible_by_metadata, read_catalogue, write_json

SEED = 'polaris-x-v2-r4-dev-sample-2026-11-16'


def _t(s):
    return dt.datetime.fromisoformat(s.replace('Z', '')).replace(tzinfo=None)


def eligible_rows(rows, instrument='LROC_NAC'):
    out, gated = [], collections.Counter()
    for r in rows:
        if r['instrument'] != instrument or r['split'] != 'dev':
            continue
        ok, why = eligible_by_metadata(r)
        if ok:
            out.append(r)
        else:
            gated[why] += 1
    return out, gated


def choose(rows, ck_windows, target):
    elig, gated = eligible_rows(rows)
    by_img = collections.defaultdict(list)
    for r in elig:
        by_img[r['product_id']].append(r)
    win_of, nowin = {}, []
    for pid, rs in by_img.items():
        t0 = _t(rs[0]['utc_start'])
        w = [x for x in ck_windows if x[0] <= t0 < x[1] + dt.timedelta(days=1)]
        if w:
            win_of[pid] = w[-1]
        else:
            nowin.append(pid)
    groups = collections.defaultdict(list)
    for pid, w in win_of.items():
        groups[w[2]].append(pid)
    sizes = {w[2]: sk.size_bytes(w[3]) for w in ck_windows}

    def key(name):
        return (-len(groups[name]) / (sizes[name] / 1e6), hashlib.sha256(f'{SEED}:{name}'.encode()).hexdigest())

    picked, chosen = [], []
    for name in sorted(groups, key=key):
        if len(picked) >= target:
            break
        chosen.append({'ck': name, 'images': len(groups[name]), 'ckMB': round(sizes[name] / 1e6, 1)})
        picked += sorted(groups[name])
    assert_dev(picked, rows)
    images = []
    for pid in picked:
        rs = sorted(by_img[pid], key=lambda r: -float(r['overlap_frac']))
        images.append({'product_id': pid, 'ck': win_of[pid][2], 'sites': [r['site'] for r in rs], 'obs_utc': rs[0]['obs_utc'],
                       'utc_start': rs[0]['utc_start'], 'utc_stop': rs[0]['utc_stop'], 'pixel_scale_m': float(rs[0]['pixel_scale_m']),
                       'data_file_url': rs[0]['data_file_url'], 'label_url': rs[0]['label_url'],
                       'strata': {r['site']: r['stratum'] for r in rs}})
    return {'rule': __doc__.strip().splitlines()[2:7], 'seed': SEED, 'target': target, 'eligibleRows': len(elig),
            'eligibleImages': len(by_img), 'gatedByMetadata': dict(gated), 'imagesWithoutCk': sorted(nowin),
            'ckWindowsChosen': chosen, 'nImages': len(images), 'nRows': sum(len(i['sites']) for i in images), 'images': images}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', type=int, default=200)
    a = ap.parse_args(argv)
    check_frozen()
    rows = read_catalogue()
    sel = choose(rows, sk.windows('lrosc', sk.listing('ck')), a.target)
    sel['catalogueSha256'] = '4b941d61f1ecb06155a2b0ffcc7f9a5f9ea1dc5b41ef6918ff1f69f424515e01'
    write_json(RESULTS / 'selection.json', sel)
    print(f"{sel['nImages']} images ({sel['nRows']} rows) from {len(sel['ckWindowsChosen'])} CK windows, "
          f"{sum(c['ckMB'] for c in sel['ckWindowsChosen']):.0f} MB of CK")


if __name__ == '__main__':
    main()
