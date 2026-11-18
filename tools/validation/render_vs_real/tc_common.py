"""Paths, catalogue access and the held-out guard for the Kaguya TC render-vs-real pipeline (A11 onwards).

The NAC (A5), WAC (A7) and ShadowCam (A10) modules are frozen and imported, never edited; their split switches must stay
`dev` here. Kaguya TC has its own switch, POLARIS_TC_SPLIT, set only by the TC held-out driver.
Rows come from the frozen v1 catalogue (imagery/catalogue.csv.gz): TC footprints there are the PDS label corner
coordinates (ODE "Footprint from PDS Label", none flagged suspect), so protocol §2 needs no new catalogue version.
Both TC products are one instrument here: Level 2B0 stereo (TC1/TC2 W, 'Kaguya_TC_stereo') and mono (S, 'Kaguya_TC_mono').
"""
from __future__ import annotations

import os
from pathlib import Path

from . import common
from .common import HeldOutError, WORK, read_catalogue

if common.SPLIT != 'dev':
    raise SystemExit('the Kaguya TC pipeline does not run in the NAC held-out mode (POLARIS_RVR_SPLIT must be dev)')
if os.environ.get('POLARIS_SHC_SPLIT', 'dev') != 'dev':
    raise SystemExit('the Kaguya TC pipeline does not run in the ShadowCam held-out mode (POLARIS_SHC_SPLIT must be dev)')
TC_SPLIT = os.environ.get('POLARIS_TC_SPLIT', 'dev')
if TC_SPLIT not in ('dev', 'heldout'):
    raise SystemExit(f'POLARIS_TC_SPLIT={TC_SPLIT!r}: must be dev or heldout')
HERE = Path(__file__).resolve().parent
TC_WORK = WORK / ('tc' if TC_SPLIT == 'dev' else 'tc_heldout')
TC_GEOM_DIR = TC_WORK / 'geometry'
TC_RENDER_DIR = TC_WORK / 'renders'
TC_RESULTS = HERE / ('results_tc' if TC_SPLIT == 'dev' else 'results_tc_heldout')
INSTRUMENTS = ('Kaguya_TC_stereo', 'Kaguya_TC_mono')
CAMERA_AMENDMENT = 'docs/v2/RENDER_VS_REAL_PROTOCOL_A11.md'
HELDOUT_AMENDMENT = 'docs/v2/RENDER_VS_REAL_PROTOCOL_A13.md'
LABEL = ('SOURCE-BASED · UNVALIDATED · Kaguya TC dev (training) split only — not a held-out result' if TC_SPLIT == 'dev' else
         'SOURCE-BASED · UNVALIDATED · Kaguya TC held-out split, pre-registered run')
SECONDARY_EL_DEG = -0.5               # protocol §2: Sun elevation below this -> secondary-illumination track
_HELD = []


def tc_rows(rows=None):
    return [r for r in (rows if rows is not None else read_catalogue()) if r['instrument'] in INSTRUMENTS]


def eligible(r):
    """Protocol §2 metadata gates (as common.eligible_by_metadata, the NAC rule) on a v1 TC row."""
    return common.eligible_by_metadata(r)


def guard(product_ids, rows=None, required=()):
    ids = set(product_ids)
    if TC_SPLIT == 'heldout':
        if not _HELD:
            common.verify_heldout_registration(required=(HELDOUT_AMENDMENT, CAMERA_AMENDMENT, *required))
            _HELD.append({r['product_id'] for r in tc_rows(rows) if r['split'] == 'heldout'})
        bad = sorted(ids - _HELD[0])
        if bad:
            raise HeldOutError(f'{len(bad)} non-held-out or non-TC id(s) reached the Kaguya TC held-out run: {bad[:5]}')
        return
    bad = sorted(ids & common.heldout_ids(rows))
    if bad:
        raise HeldOutError(f'{len(bad)} held-out product id(s) reached the Kaguya TC dev pipeline: {bad[:5]}')
