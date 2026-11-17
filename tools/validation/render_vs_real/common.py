"""Shared paths, catalogue access and the held-out guard for the render-vs-real pipeline.

Everything downloaded or rendered lives under $POLARIS_DATA/v2/render_vs_real (git-ignored, default data/cache). Committed
outputs (ids, geometry, scores; never imagery) go to tools/validation/render_vs_real/results/ (dev split).

Split: dev unless POLARIS_RVR_SPLIT=heldout, which only `python -m tools.validation.render_vs_real.heldout` sets (Amendment
A5). In held-out mode the outputs go to results_heldout/ and $POLARIS_DATA/v2/render_vs_real/heldout/{geometry,renders}, the
guard admits only the held-out LROC NAC ids of the frozen catalogue, and nothing runs unless every file registered in
docs/v2/PREREGISTRATION.md (protocol, catalogue, amendments A1-A5, the frozen pipeline code) still matches its SHA-256.
SPICE kernels, terrain and the NAC line-window cache are shared (keyed by file / product id).
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = Path(os.environ.get('POLARIS_DATA', ROOT / 'data' / 'cache'))
WORK = DATA / 'v2' / 'render_vs_real'
SPICE_DIR = WORK / 'spice'
IMG_DIR = DATA / 'v2' / 'imagery' / 'nac_windows'
PYLIB = WORK / 'pylib'                 # spiceypy installed with pip --target (shared venv untouched)
SPLIT = os.environ.get('POLARIS_RVR_SPLIT', 'dev')
if SPLIT not in ('dev', 'heldout'):
    raise SystemExit(f'POLARIS_RVR_SPLIT={SPLIT!r}: must be dev or heldout')
SPLIT_WORK = WORK if SPLIT == 'dev' else WORK / 'heldout'
GEOM_DIR = SPLIT_WORK / 'geometry'
RENDER_DIR = SPLIT_WORK / 'renders'
RESULTS = Path(__file__).resolve().parent / ('results' if SPLIT == 'dev' else 'results_heldout')
PREREG = ROOT / 'docs' / 'v2' / 'PREREGISTRATION.md'
HELDOUT_AMENDMENT = 'docs/v2/RENDER_VS_REAL_PROTOCOL_A5.md'
HELDOUT_INSTRUMENT = 'LROC_NAC'
CATALOGUE = ROOT / 'imagery' / 'catalogue.csv.gz'
CATALOGUE_SHA256 = '4b941d61f1ecb06155a2b0ffcc7f9a5f9ea1dc5b41ef6918ff1f69f424515e01'
PROTOCOL = ROOT / 'docs' / 'v2' / 'RENDER_VS_REAL_PROTOCOL.md'
PROTOCOL_SHA256 = 'bf85659d39261f34b631be7a75110f227feb64092aa600941307128900721516'
LABEL = ('SOURCE-BASED · UNVALIDATED · dev (training) split only — not the held-out headline' if SPLIT == 'dev' else
         'SOURCE-BASED · UNVALIDATED · held-out split, pre-registered run (Amendment A5)')
USER_AGENT = 'polaris-x-render-vs-real/0.1 (research; public PDS/NAIF data; sequential, rate-limited)'


def sha256_file(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


def check_frozen():
    """Refuse to run if the frozen protocol or catalogue changed (protocol §0)."""
    for p, want in ((PROTOCOL, PROTOCOL_SHA256), (CATALOGUE, CATALOGUE_SHA256)):
        got = sha256_file(p)
        if got != want:
            raise SystemExit(f'{p} SHA-256 {got} != frozen {want}: refusing to run')


def read_catalogue():
    with gzip.open(CATALOGUE, 'rt', newline='') as f:
        return list(csv.DictReader(f))


def heldout_ids(rows=None):
    rows = rows if rows is not None else read_catalogue()
    return {r['product_id'] for r in rows if r['split'] == 'heldout'}


class HeldOutError(RuntimeError):
    pass


_ROW = re.compile(r'^\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{64})`\s*\|\s*$')
_VERIFIED = []
_HELD_NAC = []


def preregistered():
    """[(path, sha256)] of every frozen-file row in docs/v2/PREREGISTRATION.md."""
    return [m.groups() for line in PREREG.read_text().splitlines() if (m := _ROW.match(line))]


def verify_heldout_registration(required=()):
    """Held-out gate (A5): every registered file matches its hash, A5 itself and `required` are registered."""
    rows = preregistered()
    reg = {p for p, _ in rows}
    missing = [p for p in (HELDOUT_AMENDMENT, *required) if p not in reg]
    if missing:
        raise HeldOutError(f'not pre-registered in {PREREG.name}: {missing}; the held-out run cannot start')
    bad = [p for p, sha in rows if sha256_file(ROOT / p) != sha]
    if bad:
        raise HeldOutError(f'changed after pre-registration: {bad}; append an amendment instead')
    _VERIFIED.append(True)


def assert_dev(product_ids, rows=None):
    """The guard every stage calls before it touches an image.
    dev mode: no held-out id may pass. held-out mode (A5): only held-out LROC NAC ids pass, after the registration check."""
    ids = set(product_ids)
    if SPLIT == 'heldout':
        if not _VERIFIED:
            verify_heldout_registration()
        if not _HELD_NAC:
            _HELD_NAC.append({r['product_id'] for r in (rows if rows is not None else read_catalogue())
                              if r['split'] == 'heldout' and r['instrument'] == HELDOUT_INSTRUMENT})
        bad = sorted(ids - _HELD_NAC[0])
        if bad:
            raise HeldOutError(f'{len(bad)} non-held-out or non-NAC id(s) reached the held-out run: {bad[:5]}')
        return
    bad = sorted(ids & heldout_ids(rows))
    if bad:
        raise HeldOutError(f'{len(bad)} held-out product id(s) reached the dev pipeline: {bad[:5]}')


def eligible_by_metadata(r):
    """Protocol §2 gates that are decidable from catalogue metadata alone."""
    if r['footprint_suspect'] == 'true':
        return False, 'footprint_suspect'
    if r['covers_site_centre'] == 'true' or float(r['overlap_frac'] or 0) >= 0.25:
        return True, ''
    return False, 'overlap_frac < 0.25 and site centre not covered'


def spiceypy():
    if str(PYLIB) not in sys.path:
        sys.path.append(str(PYLIB))
    import spiceypy as sp       # noqa: E402
    return sp


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=1, sort_keys=False) + '\n')
