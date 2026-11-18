"""The single pre-registered held-out run for Kaguya TC (Amendment A13).

    python -m tools.validation.render_vs_real.tc_heldout verify|select|list|check|run [--workers 4 --threads 4]

Refuses to start unless the frozen protocol and catalogue match and every file registered in docs/v2/PREREGISTRATION.md
matches its SHA-256, with A11, A12, A13 and all of FROZEN_CODE among them. Stages run in a child process with
POLARIS_TC_SPLIT=heldout (tc_common.py): outputs in results_tc_heldout/ and $POLARIS_DATA/v2/render_vs_real/tc_heldout/.
  select  A13.2: the first N_HELDOUT eligible held-out rows in SHA-256(SEED:product_id:site) order (metadata only)
  list    the URLs the project owner downloads (DARTS rejects this pipeline's requests; A11.7) -> download_heldout.txt
  check   damaged or missing downloads -> redownload_heldout.txt
  run     tc_pilot: geometry, render and score rows as their files arrive (resumable; scored rows are never re-scored)
Conventions as A12: ISIS start time; no sample flip for moving direction -1; +1 gated; registration +- 747.6 m.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys

from . import common as C
from . import wac_heldout as W

FROZEN_CODE = W.FROZEN_CODE + [f'tools/validation/render_vs_real/{m}.py' for m in
                               ('tc_camera', 'tc_kernels', 'tc_common', 'tc_io', 'tc_geometry', 'tc_run', 'tc_select',
                                'tc_pilot', 'tc_download_list', 'tc_heldout')]
AMENDMENTS = ('docs/v2/RENDER_VS_REAL_PROTOCOL_A11.md', 'docs/v2/RENDER_VS_REAL_PROTOCOL_A12.md',
              'docs/v2/RENDER_VS_REAL_PROTOCOL_A13.md')
SEED = 'polaris-x-v2-kaguya-tc-heldout-2026-11-18'
N_HELDOUT = 200


def verify():
    C.check_frozen()
    C.verify_heldout_registration((*AMENDMENTS, *FROZEN_CODE))


def _log(event, **kw):
    from .tc_common import TC_RESULTS
    TC_RESULTS.mkdir(parents=True, exist_ok=True)
    rec = {'utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'event': event, **kw}
    with open(TC_RESULTS / 'RUN_LOG.jsonl', 'a') as f:
        f.write(json.dumps(rec) + '\n')
    print(json.dumps(rec), flush=True)


def select():
    import hashlib
    from .tc_common import TC_RESULTS, guard
    from .tc_select import choose, images_of
    cat = C.read_catalogue()
    rows, elig, gated = choose(cat, 'heldout')
    elig.sort(key=lambda r: hashlib.sha256(f"{SEED}:{r['product_id']}:{r['site']}".encode()).hexdigest())
    pick = elig[:N_HELDOUT]
    guard([r['product_id'] for r in pick], cat, required=FROZEN_CODE)
    sel = {'rule': f'A13.2: the first {N_HELDOUT} eligible held-out TC rows in SHA-256(seed:product_id:site) order; metadata only',
           'seed': SEED, 'heldoutRows': len(rows), 'eligibleRows': len(elig),
           'eligibleImages': len({r['product_id'] for r in elig}), 'gatedByMetadata': dict(gated),
           'nImages': len({r['product_id'] for r in pick}), 'nRows': len(pick),
           'secondaryTrackRows': sum(float(r['sun_el_deg']) < -0.5 for r in pick),
           'images': images_of(pick), 'pipelineTestImages': [], 'pipelineTest': []}
    C.write_json(TC_RESULTS / 'selection.json', sel)
    print(f"held-out TC: {len(elig)} eligible rows; sample {len(pick)} rows / {sel['nImages']} images "
          f"({sel['secondaryTrackRows']} secondary track)", flush=True)


def _child(a):
    from . import tc_common as TCm
    assert TCm.TC_SPLIT == 'heldout'
    verify()
    TCm.guard([], required=FROZEN_CODE)
    from science import gitinfo
    _log('start', stage=a.stage, commit=gitinfo.head(), workers=a.workers, threads=a.threads,
         resumed=(TCm.TC_RESULTS / 'scores.jsonl').exists())
    if a.stage == 'select':
        select()
    elif a.stage == 'list':
        from . import tc_download_list
        tc_download_list.main([])
    elif a.stage == 'check':
        from . import tc_download_list
        tc_download_list.main(['--check'])
    elif a.stage == 'run':
        from . import tc_pilot
        tc_pilot.main(['--workers', str(a.workers), '--threads', str(a.threads), '--idle-minutes', str(a.idle_minutes)])
    _log('stop', stage=a.stage)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['verify', 'select', 'list', 'check', 'run'])
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--idle-minutes', type=float, default=120)
    a = ap.parse_args(argv)
    if os.environ.get('POLARIS_TC_SPLIT') == 'heldout':
        return _child(a)
    verify()
    print('pre-registration verified: protocol, catalogue, amendments and the frozen NAC + WAC + Kaguya TC code match', flush=True)
    if a.stage == 'verify':
        return
    env = {**os.environ, 'POLARIS_TC_SPLIT': 'heldout', 'POLARIS_RVR_SPLIT': 'dev', 'POLARIS_SHC_SPLIT': 'dev'}
    r = subprocess.run([sys.executable, '-m', 'tools.validation.render_vs_real.tc_heldout', *(argv or sys.argv[1:])], env=env,
                       cwd=C.ROOT, close_fds=False)
    sys.exit(r.returncode)


if __name__ == '__main__':
    main()
