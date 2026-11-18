"""ShadowCam CAL cube access: the ISIS header (first 64 KiB) and the image lines crossing a site (HTTP byte ranges), binned.

Cache (git-ignored): $POLARIS_DATA/v2/imagery/shc/{headers/<id>.hdr, windows/<id>_L<l0>_<l1>_b<b>.npz, MANIFEST.jsonl}.
Only the binned window is kept (float32 mean radiance, invalid and saturated masks). The manifest records the URL, byte
range, bytes and the SHA-256 of the raw block as fetched, so the block can be re-fetched and checked.
Pixels: float32 radiance (label unit "Radiance"; the protocol's per-image median normalisation makes the scale irrelevant).
Special constants as in the label (NULL, LRS, LIS, HRS, HIS as float32 bit patterns). Binning (A1.3 rule, as the NAC):
b x b blocks aligned to the window's first line and the image's first sample; a block is invalid if any member is
NULL/LRS/LIS, saturated if any member is HRS/HIS (and none invalid), else the mean.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json

import numpy as np

from . import fetch
from .common import DATA, sha256_file
from .shc_catalogue import label as _label
from .shc_common import guard
from .wac_camera import classify_bits

SHC_DIR = DATA / 'v2' / 'imagery' / 'shc'


def _record(rec):
    rec['retrieved_utc'] = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    SHC_DIR.mkdir(parents=True, exist_ok=True)
    with open(SHC_DIR / 'MANIFEST.jsonl', 'a') as f:
        f.write(json.dumps(rec) + '\n')


def label(pid, url):
    guard([pid])
    return _label(pid, url)


def header(pid, data_url):
    guard([pid])
    p = SHC_DIR / 'headers' / f'{pid}.hdr'
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        part = p.with_suffix('.partial')
        _b, final, code = fetch._get(data_url, headers={'Range': 'bytes=0-65535'}, stream_to=part)
        if code != 206 or part.stat().st_size != 65536:
            part.unlink(missing_ok=True)
            raise RuntimeError(f'{pid}: header range request returned HTTP {code}')
        part.rename(p)
        _record({'product_id': pid, 'kind': 'cube-header', 'url': final, 'byte_range': [0, 65535], 'bytes': 65536,
                 'sha256': sha256_file(p)})
    return p.read_bytes()


def binned_window(lab, data_url, l0, l1, b):
    """(iof-like radiance mean, invalid, saturated) of lines l0..l1 (1-based, inclusive), binned b x b."""
    pid = lab['product_id']
    guard([pid])
    p = SHC_DIR / 'windows' / f'{pid}_L{l0}_{l1}_b{b}.npz'
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        ns = lab['samples']
        a = lab['data_offset'] + (l0 - 1) * ns * 4
        e = lab['data_offset'] + l1 * ns * 4 - 1
        part = p.with_suffix('.raw.partial')
        _b, final, code = fetch._get(data_url, headers={'Range': f'bytes={a}-{e}'}, stream_to=part, timeout=900)
        if code != 206 or part.stat().st_size != e - a + 1:
            part.unlink(missing_ok=True)
            raise RuntimeError(f'{pid}: range request returned HTTP {code}')
        raw = np.fromfile(part, dtype='<u4').reshape(l1 - l0 + 1, ns)
        h = hashlib.sha256(raw.tobytes()).hexdigest()
        inv, high = classify_bits(raw, lab['special_bits'])
        val = raw.view(np.float32).astype(np.float64)
        val[inv | high] = np.nan
        nl, nsb = (raw.shape[0] // b) * b, (ns // b) * b

        def blocks(x, fn):
            return fn(x[:nl, :nsb].reshape(nl // b, b, nsb // b, b), axis=(1, 3))
        binv = blocks(inv, np.any)
        bsat = blocks(high, np.any) & ~binv
        with np.errstate(invalid='ignore'):
            mean = blocks(val, np.nanmean) if b > 1 else val[:nl, :nsb]
        mean[binv | bsat] = np.nan
        np.savez_compressed(p, value=mean.astype(np.float32), invalid=binv, saturated=bsat)
        part.unlink()
        _record({'product_id': pid, 'kind': 'image-lines', 'url': final, 'lines': [l0, l1], 'byte_range': [a, e],
                 'bytes': e - a + 1, 'sha256_raw_block': h, 'kept': f'binned {b}x{b} only', 'label_md5_whole_file': lab['md5']})
    z = np.load(p)
    return z['value'].astype(np.float64), z['invalid'], z['saturated']
