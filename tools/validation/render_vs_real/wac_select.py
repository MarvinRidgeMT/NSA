"""Choose the dev (training) LROC WAC images for the A6 pilot.

Rule (fixed before any WAC image is scored; never uses image content or scores):
  1. rows with split = dev, instrument LROC_WAC, passing the protocol §2 metadata gates;
  2. keep the images for which every SPICE kernel the camera model needs (spice_kernels.kernels_for over the image's
     start/stop) is already in the local kernel cache, i.e. was downloaded for the NAC pilots before this rule was written;
  3. take all of them. This is cluster sampling by download cost (as A1.1): the CK files dominate the bytes.
The list is written to results_wac/selection.json; the strata of the sample are reported against the eligible population.

    python -m tools.validation.render_vs_real.wac_select
"""
from __future__ import annotations

import collections

from . import spice_kernels as sk
from .common import check_frozen, eligible_by_metadata, read_catalogue, write_json
from .nac_camera import utc
from .wac_common import INSTRUMENT, WAC_RESULTS, guard


def eligible_rows(rows, split='dev'):
    out, gated = [], collections.Counter()
    for r in rows:
        if r['instrument'] != INSTRUMENT or r['split'] != split:
            continue
        ok, why = eligible_by_metadata(r)
        if ok:
            out.append(r)
        else:
            gated[why] += 1
    return out, gated


def images_of(rows):
    by = collections.defaultdict(list)
    for r in rows:
        by[r['product_id']].append(r)
    images = []
    for pid, rs in sorted(by.items()):
        rs = sorted(rs, key=lambda r: -float(r['overlap_frac']))
        images.append({'product_id': pid, 'sites': [r['site'] for r in rs], 'obs_utc': rs[0]['obs_utc'],
                       'utc_start': rs[0]['utc_start'], 'utc_stop': rs[0]['utc_stop'], 'data_file_url': rs[0]['data_file_url'],
                       'label_url': rs[0]['label_url'], 'data_file_kbytes': int(rs[0]['data_file_kbytes'] or 0),
                       'strata': {r['site']: r['stratum'] for r in rs}})
    return images


def main(argv=None):
    check_frozen()
    rows = read_catalogue()
    elig, gated = eligible_rows(rows)
    cached, missing = [], collections.Counter()
    status = {}
    for r in elig:
        pid = r['product_id']
        if pid not in status:
            k, rec = sk.kernels_for(utc(r['utc_start']), utc(r['utc_stop']), fetch_missing=False)
            if k is None:
                status[pid] = rec['error']
            else:
                miss = [p.name for p in k if not p.exists()]
                status[pid] = 'ok' if not miss else f'{len(miss)} kernel(s) not cached'
        if status[pid] == 'ok':
            cached.append(r)
        else:
            missing[status[pid].split(':')[0]] += 1
    guard([r['product_id'] for r in cached], rows)
    images = images_of(cached)
    sel = {'rule': __doc__.strip().splitlines()[2:8], 'instrument': INSTRUMENT, 'eligibleRows': len(elig),
           'eligibleImages': len({r['product_id'] for r in elig}), 'gatedByMetadata': dict(gated),
           'notSelectedRowsByReason': dict(missing), 'nImages': len(images), 'nRows': sum(len(i['sites']) for i in images),
           'catalogueSha256': '4b941d61f1ecb06155a2b0ffcc7f9a5f9ea1dc5b41ef6918ff1f69f424515e01', 'images': images}
    write_json(WAC_RESULTS / 'selection.json', sel)
    print(f"{sel['nImages']} images ({sel['nRows']} rows) of {sel['eligibleImages']} eligible images ({sel['eligibleRows']} rows)")


if __name__ == '__main__':
    main()
