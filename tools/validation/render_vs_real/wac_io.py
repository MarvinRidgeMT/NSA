"""Polite fetch of LROC WAC CDR frame sets crossing a site (HTTP byte ranges) and the 643 nm band I/F with its special pixels.

Cache (git-ignored): $POLARIS_DATA/v2/imagery/wac_windows/{<id>_K<k0>_<k1>.f32, MANIFEST.jsonl}. Each manifest record: product id, URL after redirect, byte range, bytes,
SHA-256 of the block, retrieval UTC, the label md5 of the whole file. Labels: wac_windows/labels/<id>.xml. Never committed.

I/F: the CDR stores I/F as float32 (label unit "I/F"); no scaling. Special pixels (label Special_Constants, float32 bit
patterns): NULL, LRS, LIS and any other value below -1e30 are invalid (leave the window); HRS/HIS are saturated and also
leave the window (the A1.3 rule of the NAC pilot).
"""
from __future__ import annotations

import json

import numpy as np

from . import fetch
from .common import DATA, sha256_file
from .wac_common import guard
from .wac_camera import FRAMELET, SET_LINES, band_from_sets, classify_bits

WAC_DIR = DATA / 'v2' / 'imagery' / 'wac_windows'


def _record(rec):
    import datetime as dt
    rec['retrieved_utc'] = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    WAC_DIR.mkdir(parents=True, exist_ok=True)
    with open(WAC_DIR / 'MANIFEST.jsonl', 'a') as f:
        f.write(json.dumps(rec) + '\n')


def label(product_id, label_url):
    guard([product_id])
    p = WAC_DIR / 'labels' / f'{product_id}.xml'
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        body, final, _ = fetch._get(label_url)
        if body.lstrip()[:1] != b'<' or b'Product_Observational' not in body[:4000]:
            raise RuntimeError(f'{product_id}: label response is not a PDS4 product label ({final})')
        p.write_bytes(body)
        _record({'product_id': product_id, 'kind': 'label', 'url': final, 'bytes': len(body), 'sha256': sha256_file(p)})
    return p.read_bytes()


def sets(lab, data_url, k0, k1):
    """uint32 bit patterns (k1-k0+1, 78, 704) of frame sets k0..k1 (0-based, inclusive), fetched once by byte range."""
    pid = lab['product_id']
    guard([pid])
    ns = lab['samples']
    p = WAC_DIR / f'{pid}_K{k0}_{k1}.f32'
    if not p.exists():
        WAC_DIR.mkdir(parents=True, exist_ok=True)
        a = lab['data_offset'] + k0 * SET_LINES * ns * 4
        b = lab['data_offset'] + (k1 + 1) * SET_LINES * ns * 4 - 1
        part = p.with_suffix('.partial')
        _body, final, code = fetch._get(data_url, headers={'Range': f'bytes={a}-{b}'}, stream_to=part)
        if code != 206 or part.stat().st_size != b - a + 1:
            part.unlink(missing_ok=True)
            raise RuntimeError(f'{pid}: range request returned HTTP {code}, {b - a + 1} bytes expected')
        part.rename(p)
        _record({'product_id': pid, 'kind': 'wac-frame-sets', 'url': final, 'sets': [k0, k1], 'byte_range': [a, b],
                 'bytes': b - a + 1, 'sha256': sha256_file(p), 'label_md5_whole_file': lab['md5']})
    return np.fromfile(p, dtype='<u4').reshape(k1 - k0 + 1, SET_LINES, ns)


def band_iof(lab, data_url, r0, r1, s0, s1):
    """643 nm I/F (rows r0..r1 of the band image, samples s0..s1, 1-based inclusive) -> (iof, invalid, saturated)."""
    k0, k1 = r0 // FRAMELET, r1 // FRAMELET
    raw = sets(lab, data_url, k0, k1)
    band = band_from_sets(raw)[r0 - k0 * FRAMELET: r1 - k0 * FRAMELET + 1, s0 - 1: s1]
    inv, high = classify_bits(band, lab['special_bits'])
    iof = band.view(np.float32).astype(np.float64)
    iof[inv | high] = np.nan
    return iof, inv, high & ~inv


def manifest():
    p = WAC_DIR / 'MANIFEST.jsonl'
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
