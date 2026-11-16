"""Offline tests for tools/globe/fetch.py against a local HTTP server (no internet).

Run: python -m pytest -q tools/globe
"""
import hashlib
import http.server
import json
import os
import shutil
import socketserver
import tempfile
import threading
import unittest

from tools.globe import fetch
from tools.globe.products import FileSpec, Product

PAYLOAD = bytes((i * 7 + 3) % 251 for i in range(3 * (1 << 20) + 12345))  # 3 MiB + change, deterministic


class _State:
    ignore_range = False
    fail_first = 0          # respond 503 to this many GETs first
    truncate_first = 0      # close the connection early on this many GETs
    requests = []           # (method, path, range header)
    files = {}


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # quiet
        pass

    def _body(self):
        return _State.files.get(self.path)

    def do_HEAD(self):
        _State.requests.append(("HEAD", self.path, self.headers.get("Range")))
        body = self._body()
        if body is None:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

    def do_GET(self):
        rng = self.headers.get("Range")
        _State.requests.append(("GET", self.path, rng))
        body = self._body()
        if body is None:
            self.send_error(404)
            return
        if _State.fail_first > 0:
            _State.fail_first -= 1
            self.send_response(503)
            self.send_header("Retry-After", "0")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        start = 0
        if rng and not _State.ignore_range:
            start = int(rng.split("=")[1].split("-")[0])
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(body) - 1}/{len(body)}")
        else:
            self.send_response(200)
        chunk = body[start:]
        self.send_header("Content-Length", str(len(chunk)))
        self.end_headers()
        if _State.truncate_first > 0:
            _State.truncate_first -= 1
            self.wfile.write(chunk[: len(chunk) // 3])
            self.wfile.flush()
            self.close_connection = True
            return
        self.wfile.write(chunk)


class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):  # truncated responses are deliberate; keep output clean
        pass


FAST = fetch.Policy(min_interval_s=0.0, max_bytes_per_s=None, retries=3, backoff_s=0.01, backoff_max_s=0.02,
                    timeout_s=10)


class FetchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = _Server(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        cls.t = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.t.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        _State.ignore_range, _State.fail_first, _State.truncate_first = False, 0, 0
        _State.requests = []
        _State.files = {"/a.img": PAYLOAD, "/a.lbl": b"PDS_VERSION_ID = PDS3\r\nEND\r\n",
                        "/a.img.md5": (hashlib.md5(PAYLOAD).hexdigest() + "  a.img\n").encode()}
        self.tmp = tempfile.mkdtemp(prefix="polaris_fetch_test_")
        self.logs = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def log(self, s):
        self.logs.append(s)

    def test_resume_after_interruption_uses_range_and_hash_matches(self):
        dest = os.path.join(self.tmp, "x", "a.img")
        with self.assertRaises(fetch.FetchError):
            fetch.download(self.base + "/a.img", dest, len(PAYLOAD), FAST, log=self.log, stop_after_bytes=1_500_000)
        self.assertFalse(os.path.exists(dest))
        self.assertEqual(os.path.getsize(dest + ".part"), 1_500_000)
        res = fetch.download(self.base + "/a.img", dest, len(PAYLOAD), FAST, log=self.log)
        self.assertEqual(res["resumed_from"], 1_500_000)
        self.assertEqual(_State.requests[-1], ("GET", "/a.img", "bytes=1500000-"))
        self.assertEqual(res["sha256"], hashlib.sha256(PAYLOAD).hexdigest())
        with open(dest, "rb") as f:
            self.assertEqual(f.read(), PAYLOAD)
        self.assertFalse(os.path.exists(dest + ".part"))

    def test_server_dropping_the_connection_is_retried_and_resumed(self):
        _State.truncate_first = 2
        dest = os.path.join(self.tmp, "a.img")
        res = fetch.download(self.base + "/a.img", dest, len(PAYLOAD), FAST, log=self.log)
        self.assertEqual(res["sha256"], hashlib.sha256(PAYLOAD).hexdigest())
        ranges = [r for m, p, r in _State.requests if m == "GET"]
        self.assertEqual(ranges[0], None)
        self.assertTrue(all(r and r.startswith("bytes=") for r in ranges[1:]), ranges)

    def test_server_ignoring_range_restarts_from_zero_not_appends(self):
        dest = os.path.join(self.tmp, "a.img")
        with open(dest + ".part", "wb") as f:
            f.write(PAYLOAD[:1000])
        _State.ignore_range = True
        res = fetch.download(self.base + "/a.img", dest, len(PAYLOAD), FAST, log=self.log)
        self.assertEqual(res["sha256"], hashlib.sha256(PAYLOAD).hexdigest())
        self.assertEqual(os.path.getsize(dest), len(PAYLOAD))

    def test_corrupt_partial_is_caught_by_the_hash(self):
        # a .part whose bytes differ from the server's: resume appends the rest, the SHA-256 exposes it
        dest = os.path.join(self.tmp, "a.img")
        with open(dest + ".part", "wb") as f:
            f.write(b"\0" * 1000)
        res = fetch.download(self.base + "/a.img", dest, len(PAYLOAD), FAST, log=self.log)
        self.assertNotEqual(res["sha256"], hashlib.sha256(PAYLOAD).hexdigest())
        self.assertEqual(res["sha256"], fetch.sha256_file(dest))

    def test_503_is_retried_with_backoff(self):
        _State.fail_first = 2
        dest = os.path.join(self.tmp, "a.img")
        res = fetch.download(self.base + "/a.img", dest, len(PAYLOAD), FAST, log=self.log)
        self.assertEqual(res["bytes"], len(PAYLOAD))
        self.assertEqual(sum(1 for s in self.logs if "retry" in s), 2)

    def test_404_fails_without_retrying(self):
        with self.assertRaises(fetch.FetchError):
            fetch.download(self.base + "/missing.img", os.path.join(self.tmp, "m"), None, FAST, log=self.log)
        self.assertEqual(sum(1 for m, p, r in _State.requests if p == "/missing.img"), 1)

    def test_size_mismatch_against_catalogue_is_an_error(self):
        with self.assertRaises(fetch.FetchError):
            fetch.download(self.base + "/a.img", os.path.join(self.tmp, "a.img"), len(PAYLOAD) + 1, FAST,
                           log=self.log)

    def _product(self, md5=False):
        return Product("test_prod", "test", None, self.base, "local", "v9", "none", "1 m", "none",
                       "LICENCE TEXT", "ACK TEXT", 1, "download", "",
                       [FileSpec(self.base + "/a.img", len(PAYLOAD), "sub/a.img",
                                 md5_url=self.base + "/a.img.md5" if md5 else None),
                        FileSpec(self.base + "/a.lbl", None, "sub/a.lbl")])

    def _budget(self, max_gb=150, min_free_gb=0):
        return {"new_bytes": 0, "max_new_bytes": int(max_gb * fetch.GB), "min_free_bytes": int(min_free_gb * fetch.GB)}

    def test_manifest_line_per_file_with_contract_keys_and_idempotent_rerun(self):
        p = self._product(md5=True)
        budget = self._budget()
        th = fetch.Throttle(FAST)
        fetch.fetch_product(p, self.tmp, FAST, th, budget, log=self.log)
        entries = fetch.read_manifest(self.tmp)
        self.assertEqual(len(entries), 2)
        for e in entries:
            for k in fetch.MANIFEST_KEYS:
                self.assertIn(k, e)
            self.assertEqual(e["licence"], "LICENCE TEXT")
            self.assertEqual(e["acknowledgement"], "ACK TEXT")
            self.assertEqual(e["product_version"], "v9")
            self.assertTrue(e["retrieved_utc"].endswith("Z"))
            self.assertEqual(fetch.sha256_file(os.path.join(self.tmp, e["local_path"])), e["sha256"])
        img = [e for e in entries if e["local_path"].endswith("a.img")][0]
        self.assertEqual(img["local_path"], "v2/products/test_prod/sub/a.img")
        self.assertTrue(img["archive_md5_verified"])
        self.assertEqual(budget["new_bytes"], len(PAYLOAD) + len(_State.files["/a.lbl"]))
        n_get = sum(1 for m, *_ in _State.requests if m == "GET")
        fetch.fetch_product(p, self.tmp, FAST, th, budget, log=self.log)  # second run: nothing to do
        self.assertEqual(len(fetch.read_manifest(self.tmp)), 2)
        self.assertEqual(sum(1 for m, *_ in _State.requests if m == "GET"), n_get)
        out = os.path.join(self.tmp, "mirror.json")
        self.assertEqual(fetch.write_mirror(self.tmp, out), 2)
        with open(out) as f:
            doc = json.load(f)
        self.assertEqual(doc["totals"]["bytes"], len(PAYLOAD) + len(_State.files["/a.lbl"]))

    def test_archive_md5_mismatch_is_rejected_and_not_in_manifest(self):
        _State.files["/a.img.md5"] = b"0" * 32 + b"  a.img\n"
        budget = self._budget()
        fetch.fetch_product(self._product(md5=True), self.tmp, FAST, fetch.Throttle(FAST), budget, log=self.log)
        paths = [e["local_path"] for e in fetch.read_manifest(self.tmp)]
        self.assertNotIn("v2/products/test_prod/sub/a.img", paths)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "v2/products/test_prod/sub/a.img.bad")))
        self.assertEqual(len(budget["failures"]), 1)

    def test_budget_stops_before_exceeding_new_bytes_or_free_disk(self):
        with self.assertRaises(fetch.BudgetStop):
            fetch.fetch_product(self._product(), self.tmp, FAST, fetch.Throttle(FAST), self._budget(max_gb=0.001),
                                log=self.log)
        with self.assertRaises(fetch.BudgetStop):
            fetch.fetch_product(self._product(), self.tmp, FAST, fetch.Throttle(FAST), self._budget(min_free_gb=250),
                                log=self.log, free_fn=lambda _p: 250 * fetch.GB + 10)
        self.assertEqual(fetch.read_manifest(self.tmp), [])
        self.assertFalse(any(m == "GET" for m, *_ in _State.requests))

    def test_throttle_spaces_requests_and_caps_bandwidth(self):
        t = [0.0]
        slept = []

        def sleep(s):
            slept.append(s)
            t[0] += s

        th = fetch.Throttle(fetch.Policy(min_interval_s=2.0, max_bytes_per_s=1000), clock=lambda: t[0], sleep=sleep)
        th.before_request()
        th.before_request()
        self.assertEqual(slept, [2.0])
        th.pace(500, t0=t[0], done=5000)  # 5000 B at 1000 B/s must take 5 s
        self.assertAlmostEqual(slept[-1], 5.0)

    def test_manifest_rejects_entries_missing_contract_keys(self):
        with self.assertRaises(ValueError):
            fetch.append_manifest(self.tmp, {"url": "x"})


if __name__ == "__main__":
    unittest.main()
