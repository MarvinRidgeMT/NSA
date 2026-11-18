"""The single pre-registered held-out run for ShadowCam (Amendment A10).

    python -m tools.validation.render_vs_real.shc_heldout verify|select|geometry|run|all [--workers 4 --threads 4]

Refuses to start unless the frozen protocol and catalogue match and every file registered in docs/v2/PREREGISTRATION.md
matches its SHA-256 with A10, catalogue v2 and all of FROZEN_CODE among them. Stages run in a child process with
POLARIS_SHC_SPLIT=heldout (shc_common.py): outputs in results_shc_heldout/ and $POLARIS_DATA/v2/render_vs_real/shc_heldout/.
Camera conventions as A9: ISIS start time, TDI B without sample flip.
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
                               ('shc_camera', 'shc_kernels', 'shc_catalogue', 'shc_common', 'shc_io', 'shc_geometry', 'shc_run',
                                'shc_select', 'shc_heldout')]
REQUIRED = ('imagery/catalogue_shadowcam_v2.csv.gz',)


def verify():
    C.check_frozen()
    C.verify_heldout_registration(('docs/v2/RENDER_VS_REAL_PROTOCOL_A10.md', *REQUIRED, *FROZEN_CODE))


def _log(event, **kw):
    from .shc_common import SHC_RESULTS
    SHC_RESULTS.mkdir(parents=True, exist_ok=True)
    rec = {'utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'event': event, **kw}
    with open(SHC_RESULTS / 'RUN_LOG.jsonl', 'a') as f:
        f.write(json.dumps(rec) + '\n')
    print(json.dumps(rec), flush=True)


def select():
    """A10.2: every held-out ShadowCam row of catalogue v2 passing the protocol §2 gates; no sampling."""
    from .shc_common import SHC_RESULTS, guard, read_v2
    from .shc_select import choose, images_of
    rows, elig, gated = choose(read_v2(), 'heldout')
    guard([r['product_id'] for r in elig], required=FROZEN_CODE)
    sel = {'rule': 'A10.2: every held-out ShadowCam row of catalogue v2 passing the §2 gates; no sampling',
           'heldoutRows': len(rows), 'eligibleRows': len(elig), 'eligibleImages': len({r['product_id'] for r in elig}),
           'gatedByMetadata': dict(gated), 'nImages': len({r['product_id'] for r in elig}), 'nRows': len(elig),
           'secondaryTrackRows': sum(float(r['sun_el_deg']) < -0.5 for r in elig), 'images': images_of(elig)}
    C.write_json(SHC_RESULTS / 'selection.json', sel)
    print(f"held-out ShadowCam rows {len(rows)}: eligible {len(elig)} rows / {sel['nImages']} images", flush=True)


def _child(a):
    from . import shc_common as SC
    assert SC.SHC_SPLIT == 'heldout'
    verify()
    SC.guard([], required=FROZEN_CODE)
    from science import gitinfo
    _log('start', stages=a.stage, commit=gitinfo.head(), workers=a.workers, threads=a.threads,
         resumed=(SC.SHC_RESULTS / 'scores.jsonl').exists())
    if a.stage in ('select', 'all'):
        select()
    if a.stage in ('geometry', 'all'):
        from . import shc_geometry
        shc_geometry.main(['--start', 'isis', '--flip-b', 'no'])
    if a.stage in ('run', 'all'):
        from . import shc_run
        shc_run.main(['--workers', str(a.workers), '--threads', str(a.threads)], required=FROZEN_CODE)
    _log('stop', stages=a.stage)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['verify', 'select', 'geometry', 'run', 'all'])
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--threads', type=int, default=4)
    a = ap.parse_args(argv)
    if os.environ.get('POLARIS_SHC_SPLIT') == 'heldout':
        return _child(a)
    verify()
    print('pre-registration verified: protocol, catalogues, amendments and the frozen NAC + WAC + ShadowCam code match', flush=True)
    if a.stage == 'verify':
        return
    env = {**os.environ, 'POLARIS_SHC_SPLIT': 'heldout', 'POLARIS_RVR_SPLIT': 'dev'}
    r = subprocess.run([sys.executable, '-m', 'tools.validation.render_vs_real.shc_heldout', *(argv or sys.argv[1:])], env=env,
                       cwd=C.ROOT, close_fds=False)
    sys.exit(r.returncode)


if __name__ == '__main__':
    main()
