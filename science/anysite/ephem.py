"""JPL Horizons for any site: the identical query of science/horizons.build_params, with raw responses cached by the
SHA-256 of the query parameters.

Lookup order (no network if either hits):
 1. the committed archive data/raw/horizons/MANIFEST.json: an entry whose params equal ours (read-only reuse; the file's
    SHA-256 is re-verified against the manifest);
 2. data/cache/anysite/horizons/<key>.txt with a JSON sidecar (sha256, bytes, retrieved_utc, params, api).
Otherwise the API is queried once and the raw bytes are written to (2). The committed archive is never written.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from .. import horizons as H

ROOT = H.ROOT
CACHE_DIR = ROOT / 'data' / 'cache' / 'anysite' / 'horizons'
BODIES = {'sun': '10', 'earth': '399'}


class TamperedCache(RuntimeError):
    pass


def params_key(params):
    return hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:20]


def _archive_hit(params):
    man_p = H.RAW_DIR / 'MANIFEST.json'
    if not man_p.exists():
        return None
    q = {k: v for k, v in params.items() if k != 'TLIST'}
    for m in json.loads(man_p.read_text()):
        if m.get('params') == q and 'TLIST' not in params:
            p = ROOT / m['path']
            if p.exists():
                body = p.read_bytes()
                if hashlib.sha256(body).hexdigest() != m['sha256']:
                    raise TamperedCache(f'{p} does not match its MANIFEST SHA-256')
                return body, {'path': m['path'], 'sha256': m['sha256'], 'retrieved_utc': m['retrieved_utc'],
                              'cache': 'committed-archive'}
    return None


def fetch_cached(params, cache_dir=CACHE_DIR, allow_network=True):
    hit = _archive_hit(params)
    if hit:
        return hit
    key = params_key(params)
    txt, side = Path(cache_dir) / f'{key}.txt', Path(cache_dir) / f'{key}.json'
    if txt.exists() and side.exists():
        meta = json.loads(side.read_text()); body = txt.read_bytes()
        if hashlib.sha256(body).hexdigest() != meta['sha256']:
            raise TamperedCache(f'{txt} does not match its sidecar SHA-256')
        return body, {'path': _rel(txt), 'sha256': meta['sha256'], 'retrieved_utc': meta['retrieved_utc'], 'cache': 'anysite'}
    if not allow_network:
        raise LookupError(f'Horizons response {key} not cached and network disabled')
    import requests
    for k in range(4):
        try:
            r = requests.get(H.API, params=params, timeout=120); r.raise_for_status(); break
        except Exception:
            if k == 3:
                raise
            time.sleep(3 * (k + 1))
    body = r.content
    if b'$$SOE' not in body:
        raise ValueError(f'Horizons returned no ephemeris: {body[:400]!r}')
    sha = hashlib.sha256(body).hexdigest()
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    tmp = txt.with_suffix(f'.{os.getpid()}.part'); tmp.write_bytes(body); tmp.replace(txt)
    meta = {'sha256': sha, 'bytes': len(body), 'retrieved_utc': H.unix_to_iso(time.time()), 'api': H.API,
            'params': {k: v for k, v in params.items() if k != 'TLIST'}}
    side.write_text(json.dumps(meta, indent=1))
    return body, {'path': _rel(txt), 'sha256': sha, 'retrieved_utc': meta['retrieved_utc'], 'cache': 'anysite-new'}


def _rel(p):
    try:
        return Path(p).relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def hourly(body_name, lat, lon, height_m, start, stop, step_h, allow_network=True):
    """Rows as science.horizons.ephemeris returns them (+ 't'), and the raw-file record."""
    params = H.build_params(BODIES[body_name], lat, lon, height_m, start, stop, f'{step_h} h')
    body, src = fetch_cached(params, allow_network=allow_network)
    rows = H.parse_text(body.decode('utf-8'))
    for r in rows:
        r['t'] = H.iso_to_unix(r['utc'])
    src['params_key'] = params_key(params)
    return rows, src
