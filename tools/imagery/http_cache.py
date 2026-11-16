"""Polite, cached, sequential HTTP GET for metadata archives.

- One request at a time; at least ``min_interval_s`` between network requests per host.
- Raw response bytes are stored under ``<cache_dir>/<sha256(url)[:24]>.<ext>``; the SHA-256 of
  the body, the URL, byte count and retrieval UTC go to ``<cache_dir>/MANIFEST.jsonl``.
- A cached URL is never fetched again (delete the file to refresh).
- The transport is injectable so tests never touch the network.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE_ROOT = ROOT / 'data' / 'cache' / 'v2' / 'imagery'
USER_AGENT = 'polaris-x-imagery-catalogue/0.1 (research; metadata only; sequential, rate-limited)'


def canonical_url(base, params):
    """Deterministic URL: parameters sorted by key."""
    q = urllib.parse.urlencode(sorted((k, str(v)) for k, v in params.items()))
    return f'{base}?{q}' if q else base


def url_key(url):
    return hashlib.sha256(url.encode('utf-8')).hexdigest()[:24]


def _requests_transport(url, timeout):
    import requests
    r = requests.get(url, timeout=timeout, headers={'User-Agent': USER_AGENT})
    r.raise_for_status()
    return r.content


class PoliteCache:
    def __init__(self, cache_dir, min_interval_s=2.0, transport=None, timeout=180, retries=3,
                 sleep=time.sleep, clock=time.monotonic):
        self.dir = Path(cache_dir)
        self.min_interval_s = float(min_interval_s)
        self.transport = transport or _requests_transport
        self.timeout = timeout
        self.retries = retries
        self.sleep, self.clock = sleep, clock
        self._last = {}
        self.network_calls = 0
        self.cache_hits = 0

    def path_for(self, url, ext):
        return self.dir / f'{url_key(url)}.{ext}'

    def get(self, url, ext='json'):
        """Return (body_bytes, sha256, path, from_cache)."""
        p = self.path_for(url, ext)
        if p.exists():
            body = p.read_bytes()
            self.cache_hits += 1
            return body, hashlib.sha256(body).hexdigest(), p, True
        host = urllib.parse.urlsplit(url).netloc
        last = self._last.get(host)
        if last is not None:
            wait = self.min_interval_s - (self.clock() - last)
            if wait > 0:
                self.sleep(wait)
        err = None
        for k in range(self.retries):
            try:
                self._last[host] = self.clock()
                self.network_calls += 1
                body = self.transport(url, self.timeout)
                break
            except Exception as e:  # network/HTTP error: back off, then retry
                err = e
                if k == self.retries - 1:
                    raise
                self.sleep(5.0 * (k + 1))
        else:  # pragma: no cover
            raise err
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + '.partial')
        tmp.write_bytes(body)
        tmp.replace(p)
        sha = hashlib.sha256(body).hexdigest()
        with open(self.dir / 'MANIFEST.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'url': url, 'file': p.name, 'sha256': sha, 'bytes': len(body),
                                'retrieved_utc': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')},
                               sort_keys=True) + '\n')
        return body, sha, p, False
