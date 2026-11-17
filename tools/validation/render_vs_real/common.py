"""Shared paths, catalogue access and the held-out guard for the R4 render-vs-real pilot (dev split only).

Everything downloaded or rendered lives under $POLARIS_DATA/v2/render_vs_real (git-ignored, default data/cache). Committed
outputs (ids, geometry, scores; never imagery) go to tools/validation/render_vs_real/results/.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = Path(os.environ.get('POLARIS_DATA', ROOT / 'data' / 'cache'))
WORK = DATA / 'v2' / 'render_vs_real'
SPICE_DIR = WORK / 'spice'
IMG_DIR = DATA / 'v2' / 'imagery' / 'nac_windows'
RENDER_DIR = WORK / 'renders'
PYLIB = WORK / 'pylib'                 # spiceypy installed with pip --target (shared venv untouched)
RESULTS = Path(__file__).resolve().parent / 'results'
CATALOGUE = ROOT / 'imagery' / 'catalogue.csv.gz'
CATALOGUE_SHA256 = '4b941d61f1ecb06155a2b0ffcc7f9a5f9ea1dc5b41ef6918ff1f69f424515e01'
PROTOCOL = ROOT / 'docs' / 'v2' / 'RENDER_VS_REAL_PROTOCOL.md'
PROTOCOL_SHA256 = 'bf85659d39261f34b631be7a75110f227feb64092aa600941307128900721516'
LABEL = 'SOURCE-BASED · UNVALIDATED · dev (training) split only — not the held-out headline'
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


def assert_dev(product_ids, rows=None):
    """The guard every stage calls before it touches an image: no held-out id may pass."""
    bad = sorted(set(product_ids) & heldout_ids(rows))
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
