"""Polite, resumable downloader for the POLARIS X v2 terrain catalogue (S2; docs/v2/TERRAIN_STACK_CONTRACT.md section 1).

- Sequential only (one connection at a time), a minimum gap between requests and an optional bandwidth cap.
- Resumable: data goes to `<file>.part`; a restart sends `Range: bytes=<have>-` and appends on HTTP 206. If the server
  ignores the range (HTTP 200) the partial file is discarded and the download restarts from zero.
- Retries with exponential backoff on network errors, HTTP 429 and 5xx (honours Retry-After).
- On completion: size check against Content-Range/Content-Length and the catalogue, SHA-256 of the whole file,
  optional archive checksum (USGS .md5 sidecar), atomic rename, then one JSON line appended to
  `$POLARIS_DATA/v2/manifest.jsonl`.
- Budget guards: stops before a file that would push this run's new bytes over `--max-new-gb` or leave less than
  `--min-free-gb` free on the cache volume.

Usage:
  python -m tools.globe.fetch --check                       # HEAD every file, compare sizes, download nothing
  python -m tools.globe.fetch                               # download the plan in priority order
  python -m tools.globe.fetch --products lola_ldem_global   # just one product
  python -m tools.globe.fetch --mirror docs/v2/DATA_MANIFEST.json   # write the committed manifest mirror

Never sends credentials; only public, no-login URLs are in the catalogue.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional

USER_AGENT = "POLARIS-X-terrain-fetch/1.0 (research; sequential, rate-limited, resumable)"
CHUNK = 1 << 20
GB = 1_000_000_000


class FetchError(RuntimeError):
    pass


class BudgetStop(RuntimeError):
    pass


def polaris_data(root: Optional[str] = None) -> str:
    return os.path.abspath(root or os.environ.get("POLARIS_DATA") or os.path.join("data", "cache"))


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(8 * CHUNK), b""):
            h.update(b)
    return h.hexdigest()


def md5_file(path: str) -> str:
    h = hashlib.md5()  # archive-published checksum only; SHA-256 is the manifest hash
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(8 * CHUNK), b""):
            h.update(b)
    return h.hexdigest()


@dataclass
class Policy:
    min_interval_s: float = 1.0        # gap between consecutive requests
    max_bytes_per_s: Optional[float] = 16 * 1024 * 1024
    retries: int = 6
    backoff_s: float = 2.0             # first retry delay; doubles each time, capped at backoff_max_s
    backoff_max_s: float = 120.0
    timeout_s: float = 60.0


class Throttle:
    def __init__(self, policy: Policy, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.p, self.clock, self.sleep = policy, clock, sleep
        self._last_request = -1e18

    def before_request(self) -> None:
        wait = self._last_request + self.p.min_interval_s - self.clock()
        if wait > 0:
            self.sleep(wait)
        self._last_request = self.clock()

    def pace(self, nbytes: int, t0: float, done: int) -> None:
        if not self.p.max_bytes_per_s:
            return
        ahead = (done / self.p.max_bytes_per_s) - (self.clock() - t0)
        if ahead > 0:
            self.sleep(ahead)


def _request(url: str, method: str = "GET", start: int = 0, timeout: float = 60.0):
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
    if start > 0:
        headers["Range"] = f"bytes={start}-"
    req = urllib.request.Request(url, headers=headers, method=method)
    return urllib.request.urlopen(req, timeout=timeout)


def _retry_after(err: urllib.error.HTTPError) -> Optional[float]:
    v = err.headers.get("Retry-After") if err.headers else None
    try:
        return float(v) if v is not None else None
    except ValueError:
        return None


def head(url: str, policy: Policy = Policy(), throttle: Optional[Throttle] = None) -> Dict[str, Optional[str]]:
    throttle = throttle or Throttle(policy)
    throttle.before_request()
    with _request(url, "HEAD", timeout=policy.timeout_s) as r:
        return {"status": str(r.status), "length": r.headers.get("Content-Length"),
                "accept_ranges": r.headers.get("Accept-Ranges"), "last_modified": r.headers.get("Last-Modified")}


def download(url: str, dest: str, expected_bytes: Optional[int] = None, policy: Policy = Policy(),
             throttle: Optional[Throttle] = None, log: Callable[[str], None] = print,
             stop_after_bytes: Optional[int] = None) -> Dict[str, object]:
    """Download `url` to `dest` resumably. Returns {bytes, sha256, resumed_from}. Raises FetchError.

    `stop_after_bytes` is for tests: abort (as if the connection dropped) after writing that many bytes this call.
    """
    throttle = throttle or Throttle(policy)
    part = dest + ".part"
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    attempt, resumed_from, total = 0, None, None
    while True:
        have = os.path.getsize(part) if os.path.exists(part) else 0
        if resumed_from is None:
            resumed_from = have
        if expected_bytes is not None and have == expected_bytes and have > 0:
            total = expected_bytes
            break
        try:
            throttle.before_request()
            with _request(url, "GET", start=have, timeout=policy.timeout_s) as r:
                if have > 0 and r.status == 200:
                    log(f"  server ignored Range for {url}; restarting from 0")
                    have = 0
                    mode = "wb"
                elif have > 0 and r.status == 206:
                    mode = "ab"
                else:
                    mode = "wb"
                    have = 0
                cr = r.headers.get("Content-Range")  # bytes a-b/total
                if cr and "/" in cr and cr.rsplit("/", 1)[1].strip().isdigit():
                    total = int(cr.rsplit("/", 1)[1])
                    first = int(cr.split()[1].split("-")[0])
                    if first != have:
                        raise FetchError(f"Content-Range starts at {first}, expected {have}: {url}")
                elif r.headers.get("Content-Length") is not None:
                    total = have + int(r.headers["Content-Length"])
                if expected_bytes is not None and total is not None and total != expected_bytes:
                    raise FetchError(f"size mismatch for {url}: server {total} B, catalogue {expected_bytes} B")
                t0, done = throttle.clock(), 0
                with open(part, mode) as f:
                    while True:
                        b = r.read(CHUNK)
                        if not b:
                            break
                        if stop_after_bytes is not None and done + len(b) > stop_after_bytes:
                            f.write(b[: max(0, stop_after_bytes - done)])
                            raise ConnectionResetError("simulated interruption (test)")
                        f.write(b)
                        done += len(b)
                        throttle.pace(len(b), t0, done)
            size = os.path.getsize(part)
            if total is not None and size != total:
                raise ConnectionResetError(f"short read: {size} of {total} B")
            total = size
            break
        except urllib.error.HTTPError as e:
            if e.code == 416 and have > 0 and expected_bytes == have:
                total = have
                break
            if e.code not in (408, 429, 500, 502, 503, 504) or attempt >= policy.retries:
                raise FetchError(f"HTTP {e.code} for {url}") from e
            delay = _retry_after(e) or min(policy.backoff_max_s, policy.backoff_s * 2 ** attempt)
        except FetchError:
            raise
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
            if stop_after_bytes is not None and "simulated interruption" in str(e):
                raise FetchError(str(e)) from e
            if attempt >= policy.retries:
                raise FetchError(f"giving up on {url} after {attempt} retries: {e}") from e
            delay = min(policy.backoff_max_s, policy.backoff_s * 2 ** attempt)
        attempt += 1
        log(f"  retry {attempt}/{policy.retries} in {delay:.0f} s ({url})")
        throttle.sleep(delay)
    digest = sha256_file(part)
    os.replace(part, dest)
    return {"bytes": total, "sha256": digest, "resumed_from": resumed_from}


# ---- manifest -------------------------------------------------------------------------------------------------------
MANIFEST_KEYS = ("product_id", "url", "sha256", "bytes", "licence", "acknowledgement", "retrieved_utc",
                 "product_version", "local_path")


def manifest_path(root: str) -> str:
    return os.path.join(root, "v2", "manifest.jsonl")


def read_manifest(root: str) -> List[dict]:
    p = manifest_path(root)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def append_manifest(root: str, entry: dict) -> None:
    missing = [k for k in MANIFEST_KEYS if k not in entry]
    if missing:
        raise ValueError(f"manifest entry missing {missing}")
    p = manifest_path(root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def latest_by_path(entries: Iterable[dict]) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for e in entries:
        out[e["local_path"]] = e
    return out


def write_mirror(root: str, out_path: str) -> int:
    """Committed mirror (no data): latest entry per local_path, sorted, with the keys of the contract."""
    entries = sorted(latest_by_path(read_manifest(root)).values(), key=lambda e: (e["product_id"], e["local_path"]))
    doc = {"_note": "Mirror of $POLARIS_DATA/v2/manifest.jsonl (latest entry per file). No data is committed. "
                    "Written by tools/globe/fetch.py --mirror.",
           "generated_utc": utc_now(), "files": entries,
           "totals": {"files": len(entries), "bytes": sum(int(e["bytes"]) for e in entries)}}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, sort_keys=False)
        f.write("\n")
    return len(entries)


# ---- running the plan -----------------------------------------------------------------------------------------------
def free_bytes(path: str) -> int:
    p = path
    while not os.path.exists(p):
        p = os.path.dirname(p)
    return shutil.disk_usage(p).free


def fetch_product(product, root: str, policy: Policy, throttle: Throttle, budget: dict,
                  log: Callable[[str], None] = print, free_fn: Callable[[str], int] = free_bytes) -> List[dict]:
    """Fetch every file of a catalogue Product. Skips files already complete with a manifest line and matching size."""
    done = latest_by_path(read_manifest(root))
    base = os.path.join(root, "v2", "products", product.product_id)
    written = []
    for fs in product.files:
        local_rel = os.path.relpath(os.path.join(base, fs.relpath), root)
        dest = os.path.join(root, local_rel)
        prev = done.get(local_rel)
        if prev and os.path.exists(dest) and os.path.getsize(dest) == int(prev["bytes"]):
            continue
        need = fs.bytes or 0
        part = dest + ".part"
        have = os.path.getsize(part) if os.path.exists(part) else 0
        remaining = max(0, need - have)
        if budget["new_bytes"] + remaining > budget["max_new_bytes"]:
            raise BudgetStop(f"stop: {fs.url} would take new data to "
                             f"{(budget['new_bytes'] + remaining) / GB:.2f} GB > {budget['max_new_bytes'] / GB:.0f} GB")
        if free_fn(root) - remaining < budget["min_free_bytes"]:
            raise BudgetStop(f"stop: {fs.url} would leave < {budget['min_free_bytes'] / GB:.0f} GB free")
        log(f"[{product.product_id}] {fs.url} ({(fs.bytes or 0) / 1e6:.1f} MB)")
        t = time.monotonic()
        try:
            res = download(fs.url, dest, fs.bytes, policy, throttle, log)
            archive_md5 = None
            if fs.md5_url:
                throttle.before_request()
                with _request(fs.md5_url, timeout=policy.timeout_s) as r:
                    archive_md5 = r.read().decode("ascii", "replace").split()[0].lower()
                got = md5_file(dest)
                if got != archive_md5:
                    os.replace(dest, dest + ".bad")
                    raise FetchError(f"archive MD5 mismatch for {fs.url}: {got} != {archive_md5}")
        except (FetchError, urllib.error.URLError, OSError) as e:
            log(f"  FAILED {fs.url}: {e}")
            budget.setdefault("failures", []).append({"url": fs.url, "error": str(e)})
            continue
        dt = time.monotonic() - t
        entry = {"product_id": product.product_id, "url": fs.url, "sha256": res["sha256"], "bytes": res["bytes"],
                 "licence": product.licence, "acknowledgement": product.acknowledgement,
                 "retrieved_utc": utc_now(), "product_version": product.product_version,
                 "local_path": local_rel.replace(os.sep, "/"),
                 "catalogue_bytes": fs.bytes, "resumed_from": res["resumed_from"],
                 "landing_page": product.landing_page}
        if archive_md5:
            entry["archive_md5"] = archive_md5
            entry["archive_md5_verified"] = True
        append_manifest(root, entry)
        budget["new_bytes"] += int(res["bytes"]) - have
        written.append(entry)
        rate = int(res["bytes"]) / max(dt, 1e-6) / 1e6
        log(f"  ok {res['bytes']} B sha256={res['sha256'][:16]}... {rate:.1f} MB/s; run total "
            f"{budget['new_bytes'] / GB:.2f} GB")
    return written


def check(products, policy: Policy, log: Callable[[str], None] = print) -> int:
    """HEAD every file; report size mismatches and missing files. Returns the number of problems."""
    throttle = Throttle(policy)
    problems = 0
    for p in products:
        for fs in p.files:
            try:
                h = head(fs.url, policy, throttle)
                n = int(h["length"]) if h["length"] else None
                ok = fs.bytes is None or n == fs.bytes
                if not ok:
                    problems += 1
                log(f"{'OK ' if ok else 'BAD'} {p.product_id} {fs.url} server={n} catalogue={fs.bytes} "
                    f"ranges={h['accept_ranges']}")
            except Exception as e:  # noqa: BLE001 - report and continue
                problems += 1
                log(f"ERR {p.product_id} {fs.url}: {e}")
    return problems


def main(argv: Optional[List[str]] = None) -> int:
    from tools.globe import products as catalogue

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=None, help="cache root (default $POLARIS_DATA or data/cache)")
    ap.add_argument("--products", default=None, help="comma-separated product_ids (default: the whole plan)")
    ap.add_argument("--check", action="store_true", help="HEAD every file and compare sizes; download nothing")
    ap.add_argument("--max-new-gb", type=float, default=150.0)
    ap.add_argument("--min-free-gb", type=float, default=250.0)
    ap.add_argument("--max-mbps", type=float, default=16.0, help="bandwidth cap in MiB/s (0 = none)")
    ap.add_argument("--min-interval", type=float, default=1.0, help="seconds between requests")
    ap.add_argument("--mirror", default=None, help="write the committed manifest mirror to this path and exit")
    a = ap.parse_args(argv)
    root = polaris_data(a.root)
    if a.mirror:
        n = write_mirror(root, a.mirror)
        print(f"wrote {n} entries to {a.mirror}")
        return 0
    plan = catalogue.download_plan()
    if a.products:
        want = a.products.split(",")
        plan = [catalogue.get(w) for w in want]
    policy = Policy(min_interval_s=a.min_interval, max_bytes_per_s=(a.max_mbps * 1024 * 1024) or None)
    if a.check:
        return 1 if check(plan, policy) else 0
    budget = {"new_bytes": 0, "max_new_bytes": int(a.max_new_gb * GB), "min_free_bytes": int(a.min_free_gb * GB)}
    throttle = Throttle(policy)
    print(f"{utc_now()} root={root} free={free_bytes(root) / GB:.1f} GB plan={[p.product_id for p in plan]}")
    try:
        for p in plan:
            fetch_product(p, root, policy, throttle, budget)
            print(f"{utc_now()} product done: {p.product_id}; run total {budget['new_bytes'] / GB:.2f} GB")
    except BudgetStop as e:
        print(f"{utc_now()} {e}")
        return 0
    for f in budget.get("failures", []):
        print(f"{utc_now()} FAILED {f['url']}: {f['error']}")
    print(f"{utc_now()} plan complete; run total {budget['new_bytes'] / GB:.2f} GB; free {free_bytes(root) / GB:.1f} GB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
