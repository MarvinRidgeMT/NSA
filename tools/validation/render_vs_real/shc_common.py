"""Paths, catalogue v2 access and the held-out guard for the ShadowCam render-vs-real pipeline (A8 onwards).

The NAC (A5) and WAC (A7) modules are frozen and imported, never edited; their split switches must stay `dev` here.
ShadowCam has its own switch, POLARIS_SHC_SPLIT, set only by the ShadowCam held-out driver.
Rows come from catalogue v2 (imagery/catalogue_shadowcam_v2.csv.gz, A8): the frozen v1 ShadowCam rows with camera-model
footprints; split unchanged. Its SHA-256 is checked against CATALOGUE_V2_SHA256 once A8 has fixed it.
"""
from __future__ import annotations

import csv
import gzip
import os
from pathlib import Path

from . import common
from .common import HeldOutError, ROOT, WORK, read_catalogue, sha256_file

if common.SPLIT != 'dev':
    raise SystemExit('the ShadowCam pipeline does not run in the NAC held-out mode (POLARIS_RVR_SPLIT must be dev)')
SHC_SPLIT = os.environ.get('POLARIS_SHC_SPLIT', 'dev')
if SHC_SPLIT not in ('dev', 'heldout'):
    raise SystemExit(f'POLARIS_SHC_SPLIT={SHC_SPLIT!r}: must be dev or heldout')
HERE = Path(__file__).resolve().parent
SHC_WORK = WORK / ('shc' if SHC_SPLIT == 'dev' else 'shc_heldout')
SHC_GEOM_DIR = SHC_WORK / 'geometry'
SHC_RENDER_DIR = SHC_WORK / 'renders'
SHC_RESULTS = HERE / ('results_shc' if SHC_SPLIT == 'dev' else 'results_shc_heldout')
INSTRUMENT = 'ShadowCam'
CATALOGUE_V2 = ROOT / 'imagery' / 'catalogue_shadowcam_v2.csv.gz'
CATALOGUE_V2_SHA256 = None            # set by A8 (the amendment that registers catalogue v2)
CATALOGUE_AMENDMENT = 'docs/v2/RENDER_VS_REAL_PROTOCOL_A8.md'
HELDOUT_AMENDMENT = 'docs/v2/RENDER_VS_REAL_PROTOCOL_A10.md'
LABEL = ('SOURCE-BASED · UNVALIDATED · ShadowCam dev (training) split only — not a held-out result' if SHC_SPLIT == 'dev' else
         'SOURCE-BASED · UNVALIDATED · ShadowCam held-out split, pre-registered run')
SECONDARY_EL_DEG = -0.5               # protocol §2: Sun elevation below this -> secondary-illumination track
_HELD = []


def read_v2():
    if CATALOGUE_V2_SHA256 and sha256_file(CATALOGUE_V2) != CATALOGUE_V2_SHA256:
        raise SystemExit(f'{CATALOGUE_V2} changed after A8: refusing to run')
    with gzip.open(CATALOGUE_V2, 'rt', newline='') as f:
        return list(csv.DictReader(f))


def eligible(r):
    """Protocol §2 metadata gates on a catalogue v2 row."""
    if r['footprint_suspect'] == 'true':
        return False, 'footprint not resolved: ' + (r.get('v2_reason') or '')[:80]
    if r['covers_site_centre'] == 'true' or float(r['overlap_frac'] or 0) >= 0.25:
        return True, ''
    return False, 'overlap_frac < 0.25 and site centre not covered (catalogue v2, every convention)'


def guard(product_ids, rows=None, required=()):
    ids = set(product_ids)
    if SHC_SPLIT == 'heldout':
        if not _HELD:
            common.verify_heldout_registration(required=(HELDOUT_AMENDMENT, CATALOGUE_AMENDMENT, *required))
            _HELD.append({r['product_id'] for r in (rows if rows is not None else read_catalogue())
                          if r['split'] == 'heldout' and r['instrument'] == INSTRUMENT})
        bad = sorted(ids - _HELD[0])
        if bad:
            raise HeldOutError(f'{len(bad)} non-held-out or non-ShadowCam id(s) reached the ShadowCam held-out run: {bad[:5]}')
        return
    bad = sorted(ids & common.heldout_ids(rows))
    if bad:
        raise HeldOutError(f'{len(bad)} held-out product id(s) reached the ShadowCam dev pipeline: {bad[:5]}')
