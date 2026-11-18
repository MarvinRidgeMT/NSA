"""Choose the dev Kaguya TC rows (A11): the pipeline-test rows and the dev pilot sample.

Rule (fixed before any TC image is rendered; never uses image content or scores):
  1. dev TC rows (stereo and mono Level 2B0) of the frozen v1 catalogue passing the protocol §2 gates (tc_common.eligible);
  2. order them by SHA-256(SEED:product_id:site);
  3. pipeline test (A11.4): the first PT_PER_CAMERA rows of each camera (TC1, TC2, from the product id) among rows with
     Sun elevation >= -0.5 deg;
  4. dev pilot: the first N_PILOT rows in that order (both tracks), excluding nothing (pipeline-test rows may recur).

    python -m tools.validation.render_vs_real.tc_select
"""
from __future__ import annotations

import collections
import hashlib

from .common import check_frozen, read_catalogue, write_json
from .tc_common import TC_RESULTS, eligible, guard, tc_rows

SEED = 'polaris-x-v2-kaguya-tc-dev-2026-11-18'
PT_PER_CAMERA = 4
N_PILOT = 150


def _key(r):
    return hashlib.sha256(f"{SEED}:{r['product_id']}:{r['site']}".encode()).hexdigest()


def camera_of(pid):
    return pid[:3]                     # 'TC1' or 'TC2' (Level 2B0 product ids start with the instrument)


def images_of(rows):
    by = collections.OrderedDict()
    for r in rows:
        by.setdefault(r['product_id'], []).append(r)
    return [{'product_id': pid, 'sites': [r['site'] for r in rs], 'instrument': rs[0]['instrument'], 'obs_utc': rs[0]['obs_utc'],
             'utc_start': rs[0]['utc_start'], 'utc_stop': rs[0]['utc_stop'], 'data_file_url': rs[0]['data_file_url'],
             'label_url': rs[0]['label_url'], 'strata': {r['site']: r['stratum'] for r in rs}} for pid, rs in by.items()]


def choose(rows, split='dev'):
    rows = [r for r in tc_rows(rows) if r['split'] == split]
    elig, gated = [], collections.Counter()
    for r in rows:
        ok, why = eligible(r)
        if ok:
            elig.append(r)
        else:
            gated[why] += 1
    elig.sort(key=_key)
    return rows, elig, gated


def main(argv=None):
    check_frozen()
    cat = read_catalogue()
    rows, elig, gated = choose(cat)
    guard([r['product_id'] for r in elig], cat)
    pt = []
    for cam in ('TC1', 'TC2'):
        pt += [r for r in elig if camera_of(r['product_id']) == cam and float(r['sun_el_deg']) >= -0.5][:PT_PER_CAMERA]
    pilot = elig[:N_PILOT]
    sec = sum(float(r['sun_el_deg']) < -0.5 for r in pilot)
    sel = {'rule': __doc__.strip().splitlines()[2:8], 'seed': SEED, 'devRows': len(rows), 'eligibleRows': len(elig),
           'eligibleImages': len({r['product_id'] for r in elig}), 'gatedByMetadata': dict(gated),
           'cameraOfEligible': dict(collections.Counter(camera_of(r['product_id']) for r in elig)),
           'productOfEligible': dict(collections.Counter(r['instrument'] for r in elig)),
           'pipelineTest': [{'product_id': r['product_id'], 'site': r['site']} for r in pt],
           'nImages': len({r['product_id'] for r in pilot}), 'nRows': len(pilot), 'secondaryTrackRows': sec,
           'images': images_of(pilot), 'pipelineTestImages': images_of(pt)}
    write_json(TC_RESULTS / 'selection.json', sel)
    print(f"dev eligible {len(elig)} rows; pilot {len(pilot)} rows / {sel['nImages']} images ({sec} secondary); pipeline test "
          f"{len(pt)} rows; cameras {sel['cameraOfEligible']}; products {sel['productOfEligible']}; gated {dict(gated)}")


if __name__ == '__main__':
    main()
