"""Polite, resumable fetch of LROC NAC CDR labels and of only the image lines crossing a site square (HTTP byte ranges).

Cache (git-ignored): $POLARIS_DATA/v2/imagery/nac_windows/{labels/<id>.xml, <id>_L<l0>_<l1>.i16, MANIFEST.jsonl}.
Each manifest record: product id, URL (after redirect), byte range, bytes, SHA-256 of the block, retrieval UTC, label md5 of the
whole file (the block itself cannot be checked against it). Never committed.
"""
from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path

import numpy as np

from .common import IMG_DIR, USER_AGENT, assert_dev, sha256_file

MIN_INTERVAL_S = 1.5
_last = [0.0]


def _pause():
    wait = MIN_INTERVAL_S - (time.monotonic() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.monotonic()


def _get(url, headers=None, stream_to=None, timeout=300):
    import requests
    h = {'User-Agent': USER_AGENT, **(headers or {})}
    for attempt in range(5):
        _pause()
        try:
            r = requests.get(url, headers=h, timeout=timeout, stream=stream_to is not None, allow_redirects=True)
            if r.status_code in (429, 503):
                time.sleep(30 * (attempt + 1))
                continue
            r.raise_for_status()
            if stream_to is None:
                return r.content, r.url, r.status_code
            with open(stream_to, 'wb') as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
            return None, r.url, r.status_code
        except Exception:
            if attempt == 4:
                raise
            time.sleep(10 * (attempt + 1))


def label(product_id, label_url):
    assert_dev([product_id])
    p = IMG_DIR / 'labels' / f'{product_id}.xml'
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        body, final, _ = _get(label_url)
        if body.lstrip()[:1] != b'<' or b'Product_Observational' not in body[:4000]:
            raise RuntimeError(f'{product_id}: label response is not a PDS4 product label ({final})')
        p.write_bytes(body)
        _record({'product_id': product_id, 'kind': 'label', 'url': final, 'bytes': len(body), 'sha256': sha256_file(p)})
    return p.read_bytes()


def _record(rec):
    rec['retrieved_utc'] = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    with open(IMG_DIR / 'MANIFEST.jsonl', 'a') as f:
        f.write(json.dumps(rec) + '\n')


def window(lab, data_url, l0, l1):
    """int16 array (l1-l0+1, samples) of image lines l0..l1 (1-based, inclusive), fetched once by byte range."""
    pid = lab['product_id']
    assert_dev([pid])
    ns = lab['samples']
    p = IMG_DIR / f'{pid}_L{l0}_{l1}.i16'
    if not p.exists():
        a = lab['data_offset'] + (l0 - 1) * ns * 2
        b = lab['data_offset'] + l1 * ns * 2 - 1
        part = p.with_suffix('.partial')
        _body, final, code = _get(data_url, headers={'Range': f'bytes={a}-{b}'}, stream_to=part)
        if code != 206 or part.stat().st_size != b - a + 1:
            part.unlink(missing_ok=True)
            raise RuntimeError(f'{pid}: range request returned HTTP {code}, {b - a + 1} bytes expected')
        part.rename(p)
        _record({'product_id': pid, 'kind': 'image-lines', 'url': final, 'lines': [l0, l1], 'byte_range': [a, b],
                 'bytes': b - a + 1, 'sha256': sha256_file(p), 'label_md5_whole_file': lab['md5']})
    return np.fromfile(p, dtype='<i2').reshape(l1 - l0 + 1, ns)


def manifest():
    p = IMG_DIR / 'MANIFEST.jsonl'
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
