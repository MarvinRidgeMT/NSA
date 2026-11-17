"""The single pre-registered held-out run for LROC WAC 643 nm (Amendment A7).

    python -m tools.validation.render_vs_real.wac_heldout verify|select|geometry|run|all [--workers 4 --threads 4]

Refuses to start unless the frozen protocol and catalogue match, and every file registered in docs/v2/PREREGISTRATION.md
matches its SHA-256 with A7 and all of FROZEN_CODE among them. Stages run in a child process with POLARIS_WAC_SPLIT=heldout
(wac_common.py): outputs go to results_wac_heldout/ and $POLARIS_DATA/v2/render_vs_real/wac_heldout/; dev outputs are never
touched. SPICE kernels are fetched by the geometry stage as each image needs them (spice_kernels.kernels_for).
The claim rule and the stratum are heldout.claim_rule / near_total_shadow (A5.5, A5.6), applied by wac_report.py.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys

from . import common as C
from . import heldout as NAC

FROZEN_CODE = NAC.FROZEN_CODE + [f'tools/validation/render_vs_real/{m}.py' for m in
                                 ('wac_camera', 'wac_common', 'wac_io', 'wac_geometry', 'wac_run', 'wac_twin', 'wac_select',
                                  'wac_heldout')]


def verify():
    C.check_frozen()
    from .wac_common import HELDOUT_AMENDMENT
    C.verify_heldout_registration((HELDOUT_AMENDMENT, *FROZEN_CODE))


def _log(event, **kw):
    from .wac_common import WAC_RESULTS
    WAC_RESULTS.mkdir(parents=True, exist_ok=True)
    rec = {'utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'event': event, **kw}
    with open(WAC_RESULTS / 'RUN_LOG.jsonl', 'a') as f:
        f.write(json.dumps(rec) + '\n')
    print(json.dumps(rec), flush=True)


def select():
    """A7.2: every held-out WAC row passing the protocol §2 metadata gates; no sampling."""
    from .wac_common import WAC_RESULTS, guard
    from .wac_select import eligible_rows, images_of
    rows = C.read_catalogue()
    held = [r for r in rows if r['split'] == 'heldout' and r['instrument'] == 'LROC_WAC']
    elig, gated = eligible_rows(rows, 'heldout')
    guard([r['product_id'] for r in elig], rows, required=FROZEN_CODE)
    images = images_of(elig)
    sel = {'rule': 'A7.2: every held-out LROC WAC row of the frozen catalogue; protocol §2 metadata gates; no sampling',
           'instrument': 'LROC_WAC', 'catalogueSha256': C.CATALOGUE_SHA256, 'heldoutRows': len(held),
           'eligibleRows': len(elig), 'eligibleImages': len(images), 'gatedByMetadata': dict(gated),
           'notSelectedRowsByReason': {}, 'nImages': len(images), 'nRows': len(elig), 'images': images}
    C.write_json(WAC_RESULTS / 'selection.json', sel)
    print(f"held-out WAC rows {len(held)}: eligible {sel['nRows']} rows / {sel['nImages']} images", flush=True)


def _child(a):
    from . import wac_common as WC
    assert WC.WAC_SPLIT == 'heldout'
    verify()
    WC.guard([], required=FROZEN_CODE)
    from science import gitinfo
    _log('start', stages=a.stage, commit=gitinfo.head(), workers=a.workers, threads=a.threads,
         resumed=(WC.WAC_RESULTS / 'scores.jsonl').exists())
    if a.stage in ('select', 'all'):
        select()
    if a.stage in ('geometry', 'all'):
        from . import wac_geometry
        wac_geometry.main([])
    if a.stage in ('run', 'all'):
        from . import wac_run
        wac_run.main(['--workers', str(a.workers), '--threads', str(a.threads)], required=FROZEN_CODE)
    _log('stop', stages=a.stage)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['verify', 'select', 'geometry', 'run', 'all'])
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--threads', type=int, default=4)
    a = ap.parse_args(argv)
    if os.environ.get('POLARIS_WAC_SPLIT') == 'heldout':
        return _child(a)
    verify()
    print('pre-registration verified: protocol, catalogue, amendments and the frozen NAC + WAC code match', flush=True)
    if a.stage == 'verify':
        return
    env = {**os.environ, 'POLARIS_WAC_SPLIT': 'heldout', 'POLARIS_RVR_SPLIT': 'dev'}
    r = subprocess.run([sys.executable, '-m', 'tools.validation.render_vs_real.wac_heldout', *(argv or sys.argv[1:])], env=env,
                       cwd=C.ROOT, close_fds=False)
    sys.exit(r.returncode)


if __name__ == '__main__':
    main()
