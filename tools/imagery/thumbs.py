"""Pipeline test: fetch at most 20 ODE thumbnails (small PNG) of DEV images only.

Purpose: prove the catalogue -> archive -> cached file -> SHA-256 -> decode path works, without
downloading science imagery. Thumbnails go to data/cache/v2/imagery/thumbs/ (git-ignored) and are
never committed. Held-out images are never fetched (protocol §1.4). Nobody inspects them for scoring.

    .venv/bin/python -m tools.imagery.thumbs [--n 20]
"""
from __future__ import annotations

import argparse
import json
import struct
import sys

from . import catalogue as cat
from .http_cache import CACHE_ROOT, PoliteCache, canonical_url
from .ode import ODE_BASE, PRODUCTS

HARD_CAP = 20
PNG_SIG = b'\x89PNG\r\n\x1a\n'


def png_size(body):
    if not body.startswith(PNG_SIG) or body[12:16] != b'IHDR':
        raise ValueError('not a PNG')
    w, h = struct.unpack('>II', body[16:24])
    return w, h


def pick(rows, n):
    """Deterministic: dev primary rows, round-robin over instruments, each instrument's rows in
    split-hash order."""
    n = min(n, HARD_CAP)
    by = {}
    for r in rows:
        if r['split'] == 'dev' and r['is_primary_row'] in (True, 'true'):
            by.setdefault(r['instrument'], []).append(r)
    for v in by.values():
        v.sort(key=lambda r: cat.split_hash(r['product_id']))
    out, k = [], 0
    insts = sorted(by)
    while len(out) < n and any(k < len(by[i]) for i in insts):
        for i in insts:
            if k < len(by[i]) and len(out) < n:
                out.append(by[i][k])
        k += 1
    assert all(r['split'] == 'dev' for r in out)
    return out


def thumb_url(r):
    ihid, iid, pt = PRODUCTS[r['instrument']][:3]
    return canonical_url(ODE_BASE, {'query': 'thumbnail', 'pdsid': r['ode_pdsid'], 'ihid': ihid, 'iid': iid, 'pt': pt,
                                    'target': 'moon'})


def run(n=HARD_CAP, catalogue_path=cat.OUT, cache=None):
    rows = cat.read_csv_gz(catalogue_path)
    cache = cache or PoliteCache(CACHE_ROOT / 'thumbs', min_interval_s=2.0)
    report = []
    for r in pick(rows, n):
        url = thumb_url(r)
        try:
            body, sha, path, hit = cache.get(url, ext='png')
            w, h = png_size(body)
            report.append({'product_id': r['product_id'], 'instrument': r['instrument'], 'bytes': len(body),
                           'sha256': sha, 'width': w, 'height': h, 'ok': True})
        except Exception as e:  # recorded, not hidden
            report.append({'product_id': r['product_id'], 'instrument': r['instrument'], 'ok': False, 'error': repr(e)[:200]})
    (CACHE_ROOT / 'thumbs').mkdir(parents=True, exist_ok=True)
    (CACHE_ROOT / 'thumbs' / 'pipeline_test.json').write_text(json.dumps(report, indent=1))
    return report


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=HARD_CAP)
    a = ap.parse_args(argv)
    rep = run(a.n)
    ok = sum(r['ok'] for r in rep)
    print(json.dumps({'requested': len(rep), 'ok': ok, 'total_bytes': sum(r.get('bytes', 0) for r in rep),
                      'by_instrument': {i: sum(1 for r in rep if r['instrument'] == i and r['ok']) for i in sorted({r['instrument'] for r in rep})}},
                     indent=1))
    return 0 if ok == len(rep) else 1


if __name__ == '__main__':
    sys.exit(main())
