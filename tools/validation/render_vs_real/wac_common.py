"""Paths and the held-out guard for the LROC WAC render-vs-real pipeline (Amendments A6 dev pilot, A7 held-out run).

The NAC pipeline modules are frozen for the held-out NAC record (A5) and are imported, never edited. Their split switch
(POLARIS_RVR_SPLIT) must stay `dev` here; WAC has its own switch, POLARIS_WAC_SPLIT, which only `wac_heldout.py` sets.

dev:      outputs in results_wac/ and $POLARIS_DATA/v2/render_vs_real/wac/; no held-out id of any instrument passes the guard.
heldout:  outputs in results_wac_heldout/ and .../wac_heldout/; the guard first verifies every file registered in
          docs/v2/PREREGISTRATION.md (A7 and the frozen WAC code must be among them), then admits only held-out LROC WAC ids.
"""
from __future__ import annotations

import os
from pathlib import Path

from . import common
from .common import HeldOutError, WORK, heldout_ids, read_catalogue

if common.SPLIT != 'dev':
    raise SystemExit('the WAC pipeline does not run in the NAC held-out mode (POLARIS_RVR_SPLIT must be dev)')
WAC_SPLIT = os.environ.get('POLARIS_WAC_SPLIT', 'dev')
if WAC_SPLIT not in ('dev', 'heldout'):
    raise SystemExit(f'POLARIS_WAC_SPLIT={WAC_SPLIT!r}: must be dev or heldout')
HERE = Path(__file__).resolve().parent
WAC_WORK = WORK / ('wac' if WAC_SPLIT == 'dev' else 'wac_heldout')
WAC_GEOM_DIR = WAC_WORK / 'geometry'
WAC_RENDER_DIR = WAC_WORK / 'renders'
WAC_RESULTS = HERE / ('results_wac' if WAC_SPLIT == 'dev' else 'results_wac_heldout')
INSTRUMENT = 'LROC_WAC'
DEV_AMENDMENT = 'docs/v2/RENDER_VS_REAL_PROTOCOL_A6.md'
HELDOUT_AMENDMENT = 'docs/v2/RENDER_VS_REAL_PROTOCOL_A7.md'
LABEL = ('SOURCE-BASED · UNVALIDATED · LROC WAC dev (training) split only — not a held-out result' if WAC_SPLIT == 'dev' else
         'SOURCE-BASED · UNVALIDATED · LROC WAC held-out split, pre-registered run (Amendment A7)')
_HELD = []


def guard(product_ids, rows=None, required=()):
    """Every WAC stage calls this before it touches an image."""
    ids = set(product_ids)
    if WAC_SPLIT == 'heldout':
        if not _HELD:
            common.verify_heldout_registration(required=(HELDOUT_AMENDMENT, *required))
            _HELD.append({r['product_id'] for r in (rows if rows is not None else read_catalogue())
                          if r['split'] == 'heldout' and r['instrument'] == INSTRUMENT})
        bad = sorted(ids - _HELD[0])
        if bad:
            raise HeldOutError(f'{len(bad)} non-held-out or non-WAC id(s) reached the WAC held-out run: {bad[:5]}')
        return
    bad = sorted(ids & heldout_ids(rows))
    if bad:
        raise HeldOutError(f'{len(bad)} held-out product id(s) reached the WAC dev pipeline: {bad[:5]}')
