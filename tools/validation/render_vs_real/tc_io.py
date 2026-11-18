"""Kaguya TC Level 2B0 access (JAXA DARTS, public, no account): PDS3 labels and the image lines crossing a site, binned.

Cache (git-ignored): $POLARIS_DATA/v2/imagery/tc/{labels/<id>.lbl, img/<id>.img.gz, windows/<id>_L<l0>_<l1>_b<b>.npz,
MANIFEST.jsonl}. The products are gzip files, so HTTP byte ranges cannot be used: the whole .img.gz is fetched once and
kept (5-13 MB each); every download is recorded in the manifest (URL, bytes, SHA-256, retrieval UTC).
Pixels (label IMAGE object): MSB 16-bit integers, radiance = DN x SCALING_FACTOR + OFFSET (W m-2 um-1 sr-1). Invalid
codes (INVALID_TYPE / INVALID_VALUE): SATURATION -20000 -> saturated; MINUS -21000, DUMMY_DEFECT -22000, OTHER -23000 ->
invalid (protocol §3.1 special pixels). Binning (A1.3 rule, as the NAC): b x b blocks aligned to the window's first line and
the image's first sample; a block is invalid if any member is invalid, saturated if any member is saturated (and none
invalid), else the mean. TC pixels are ~8-10 m, so b = 1 at every site (round(5 / 10) -> 1): no binning in practice.
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json

import numpy as np

from . import fetch
from .common import DATA, sha256_file
from .tc_common import guard

TC_DIR = DATA / 'v2' / 'imagery' / 'tc'


def _record(rec):
    rec['retrieved_utc'] = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    TC_DIR.mkdir(parents=True, exist_ok=True)
    with open(TC_DIR / 'MANIFEST.jsonl', 'a') as f:
        f.write(json.dumps(rec) + '\n')


def label(pid, url):
    """PDS3 label text (metadata only)."""
    guard([pid])
    p = TC_DIR / 'labels' / f'{pid}.lbl'
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        body, final, _ = fetch._get(url)
        if b'PDS_VERSION_ID' not in body[:400] or pid.encode() not in body:
            raise RuntimeError(f'{pid}: label response is not this PDS3 product label ({final})')
        p.write_bytes(body)
        _record({'product_id': pid, 'kind': 'label', 'url': final, 'bytes': len(body), 'sha256': sha256_file(p)})
    return p.read_text(encoding='latin-1')


def image_gz(pid, data_url):
    guard([pid])
    p = TC_DIR / 'img' / f'{pid}.img.gz'
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        part = p.with_suffix('.partial')
        _b, final, code = fetch._get(data_url, stream_to=part, timeout=900)
        if code != 200 or part.read_bytes()[:2] != b'\x1f\x8b':
            part.unlink(missing_ok=True)
            raise RuntimeError(f'{pid}: image request returned HTTP {code} or not gzip')
        part.rename(p)
        _record({'product_id': pid, 'kind': 'image-gz', 'url': final, 'bytes': p.stat().st_size, 'sha256': sha256_file(p)})
    return p


def read_image(lab, data_url):
    """Whole image as (radiance float64 with NaN at special pixels, invalid mask, saturated mask, SHA-256 of the
    decompressed file)."""
    return decode(lab, gzip.decompress(image_gz(lab['product_id'], data_url).read_bytes()))


def decode(lab, raw):
    """Decode decompressed Level 2B0 bytes; checks the label's layout (MSB_INTEGER 16 bit, LINES x LINE_SAMPLES) against
    the size."""
    nl, ns = lab['lines'], lab['samples']
    off = lab['image_byte_offset']
    if len(raw) < off + nl * ns * 2:
        raise RuntimeError(f"{lab['product_id']}: decompressed image {len(raw)} bytes < label layout {off + nl * ns * 2}")
    dn = np.frombuffer(raw, dtype='>i2', count=nl * ns, offset=off).reshape(nl, ns).astype(np.int32)
    codes = lab['invalid_codes']
    sat = dn == codes['SATURATION']
    inv = np.isin(dn, [v for k, v in codes.items() if k != 'SATURATION'])
    val = dn * lab['scaling_factor'] + lab['offset']
    val = val.astype(np.float64)
    val[inv | sat] = np.nan
    return val, inv, sat, hashlib.sha256(raw).hexdigest()


def binned_window(lab, data_url, l0, l1, b):
    """(radiance mean, invalid, saturated) of lines l0..l1 (1-based, inclusive), binned b x b."""
    pid = lab['product_id']
    guard([pid])
    p = TC_DIR / 'windows' / f'{pid}_L{l0}_{l1}_b{b}.npz'
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        val, inv, sat, h = read_image(lab, data_url)
        val, inv, sat = val[l0 - 1:l1], inv[l0 - 1:l1], sat[l0 - 1:l1]
        nl, nsb = (val.shape[0] // b) * b, (val.shape[1] // b) * b

        def blocks(x, fn):
            return fn(x[:nl, :nsb].reshape(nl // b, b, nsb // b, b), axis=(1, 3))
        binv = blocks(inv, np.any)
        bsat = blocks(sat, np.any) & ~binv
        with np.errstate(invalid='ignore'):
            mean = blocks(val, np.nanmean) if b > 1 else val[:nl, :nsb].copy()
        mean[binv | bsat] = np.nan
        np.savez_compressed(p, value=mean.astype(np.float32), invalid=binv, saturated=bsat)
        _record({'product_id': pid, 'kind': 'window', 'lines': [l0, l1], 'bin': b, 'sha256_decompressed_image': h,
                 'kept': f'binned {b}x{b} window (the .img.gz is cached alongside)'})
    z = np.load(p)
    return z['value'].astype(np.float64), z['invalid'], z['saturated']
