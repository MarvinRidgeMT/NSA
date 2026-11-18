"""Choose the dev ShadowCam rows (A8/A9): the pipeline-test rows and the dev pilot sample.

Rule (fixed before any ShadowCam image is rendered; never uses image content or scores):
  1. dev rows of catalogue v2 passing the protocol §2 gates (shc_common.eligible);
  2. order them by SHA-256(SEED:product_id:site);
  3. pipeline test (A8.4): the first PT_PER_GROUP rows of each TDI direction among rows with Sun elevation >= -0.5 deg;
  4. dev pilot: the first N_PILOT rows in that order (both tracks), excluding nothing (pipeline-test rows may recur).

    python -m tools.validation.render_vs_real.shc_select
"""
from __future__ import annotations

import collections
import hashlib

from .common import check_frozen, read_catalogue, write_json
from .shc_common import INSTRUMENT, SHC_RESULTS, eligible, guard, read_v2

SEED = 'polaris-x-v2-shadowcam-dev-2026-11-17'
PT_PER_GROUP = 3
N_PILOT = 150


def _key(r):
    return hashlib.sha256(f"{SEED}:{r['product_id']}:{r['site']}".encode()).hexdigest()


def images_of(rows):
    by = collections.OrderedDict()
    for r in rows:
        by.setdefault(r['product_id'], []).append(r)
    return [{'product_id': pid, 'sites': [r['site'] for r in rs], 'obs_utc': rs[0]['obs_utc'], 'utc_start': rs[0]['utc_start'],
             'utc_stop': rs[0]['utc_stop'], 'data_file_url': rs[0]['data_file_url'], 'label_url': rs[0]['label_url'],
             'strata': {r['site']: r['stratum'] for r in rs}} for pid, rs in by.items()]


def choose(v2, split='dev'):
    rows = [r for r in v2 if r['instrument'] == INSTRUMENT and r['split'] == split]
    elig, gated = [], collections.Counter()
    for r in rows:
        ok, why = eligible(r)
        if ok:
            elig.append(r)
        else:
            gated[why.split(':')[0]] += 1
    elig.sort(key=_key)
    return rows, elig, gated


def main(argv=None):
    check_frozen()
    v2 = read_v2()
    rows, elig, gated = choose(v2)
    guard([r['product_id'] for r in elig], read_catalogue())
    pt = []
    for tdi in ('A', 'B'):
        pt += [r for r in elig if r.get('v2_tdi_direction') == tdi and float(r['sun_el_deg']) >= -0.5][:PT_PER_GROUP]
    pilot = elig[:N_PILOT]
    sec = sum(float(r['sun_el_deg']) < -0.5 for r in pilot)
    sel = {'rule': __doc__.strip().splitlines()[2:7], 'seed': SEED, 'devRows': len(rows), 'eligibleRows': len(elig),
           'eligibleImages': len({r['product_id'] for r in elig}), 'gatedByMetadata': dict(gated),
           'tdiOfEligible': dict(collections.Counter(r.get('v2_tdi_direction') for r in elig)),
           'pipelineTest': [{'product_id': r['product_id'], 'site': r['site'], 'tdi': r.get('v2_tdi_direction')} for r in pt],
           'nImages': len({r['product_id'] for r in pilot}), 'nRows': len(pilot), 'secondaryTrackRows': sec,
           'images': images_of(pilot), 'pipelineTestImages': images_of(pt)}
    write_json(SHC_RESULTS / 'selection.json', sel)
    print(f"dev eligible {len(elig)} rows; pilot {len(pilot)} rows ({sec} secondary); pipeline test {len(pt)} rows; "
          f"TDI {sel['tdiOfEligible']}; gated {dict(gated)}")


if __name__ == '__main__':
    main()
