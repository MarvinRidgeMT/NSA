"""POLARIS X solver API, local server (stdlib http.server; binds 127.0.0.1 only; no keys, no paid services).

  python -m science.api.server [--port 8767]          # GET http://127.0.0.1:8767/v1/health
  python -m science.api.server --batch requests.json  # offline batch: {"requests": [...]} -> results on stdout

Routes = `ROUTES` below = the paths of docs/v2/openapi.yaml (test_api checks both directions).
The older single-route stub `python -m science.anysite.api` (POST /anysite) is left as it is (owned by the solver session).
"""
from __future__ import annotations

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import spec as S
from .service import ApiError, Service

# (method, OpenAPI path) -> handler(service, path_params, query, body)
_b = lambda q, k: str(q.get(k, ['false'])[0]).lower() in ('1', 'true', 'yes')
_q = lambda q, k, d=None: q.get(k, [d])[0]
ROUTES = {
    ('GET', '/v1/health'): lambda s, p, q, b: s.health(),
    ('GET', '/v1/worlds'): lambda s, p, q, b: s.worlds(),
    ('GET', '/v1/worlds/{world}'): lambda s, p, q, b: s.world(p['world']),
    ('GET', '/v1/sites'): lambda s, p, q, b: s.sites(_q(q, 'world'), _q(q, 'group'), _q(q, 'lat_min'), _q(q, 'lat_max'),
                                                     _q(q, 'limit', 100), _q(q, 'offset', 0)),
    ('GET', '/v1/sites/{site_hash}'): lambda s, p, q, b: s.site(p['site_hash'], _b(q, 'full')),
    ('GET', '/v1/sites/{site_hash}/timeseries.json'): lambda s, p, q, b: s.timeseries(p['site_hash'], 'json'),
    ('GET', '/v1/sites/{site_hash}/timeseries.csv'): lambda s, p, q, b: s.timeseries(p['site_hash'], 'csv'),
    ('POST', '/v1/solve'): lambda s, p, q, b: s.solve(b),
    ('POST', '/v1/batch'): lambda s, p, q, b: s.batch(b),
    ('GET', '/v1/cubes/{site_id}/decision_summary'): lambda s, p, q, b: s.decision_summary(p['site_id']),
    ('GET', '/v1/cubes/{site_id}/decision_card.pdf'): lambda s, p, q, b: s.decision_card(p['site_id']),
    ('GET', '/v1/openapi.yaml'): lambda s, p, q, b: (200, S.yaml_text(), 'application/yaml; charset=utf-8'),
    ('GET', '/v1/openapi.json'): lambda s, p, q, b: (200, S.OPENAPI),
    ('GET', '/v1/tools'): lambda s, p, q, b: (200, S.TOOLS),
}


def _pattern(path):
    return re.compile('^' + re.sub(r'\{(\w+)\}', r'(?P<\1>[A-Za-z0-9_.-]+)', re.escape(path).replace(r'\{', '{')
                                   .replace(r'\}', '}')) + '$')


_COMPILED = [(m, p, _pattern(p), h) for (m, p), h in ROUTES.items()]


def dispatch(service, method, raw_path, body_bytes=b''):
    """-> (status, body, content_type). Shared by the HTTP handler and the tests."""
    u = urlparse(raw_path)
    q = parse_qs(u.query)
    allowed = False
    for m, path, rx, h in _COMPILED:
        mt = rx.match(u.path)
        if not mt:
            continue
        allowed = True
        if m != method:
            continue
        # literal routes win over templated ones (timeseries.json vs {site_hash})
        try:
            body = None
            if method == 'POST':
                try:
                    body = json.loads(body_bytes or b'null')
                except json.JSONDecodeError as e:
                    raise ApiError(400, f'invalid JSON: {e}')
            r = h(service, mt.groupdict(), q, body)
        except ApiError as e:
            return e.status, e.body(), 'application/json'
        except Exception as e:  # noqa: BLE001
            return 500, {'error': f'{type(e).__name__}: {e}', 'status': 500, 'detail': None}, 'application/json'
        status, out = r[0], r[1]
        ctype = r[2] if len(r) > 2 else 'application/json'
        return status, out, ctype
    if allowed:
        return 405, {'error': f'method {method} not allowed', 'status': 405, 'detail': None}, 'application/json'
    return 404, {'error': f'no route {u.path}', 'status': 404, 'detail': 'GET /v1/openapi.yaml lists the routes'}, \
        'application/json'


def encode(out, ctype):
    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    if isinstance(out, str):
        return out.encode()
    return json.dumps(out, ensure_ascii=False).encode()


def make_handler(service):
    class H(BaseHTTPRequestHandler):
        server_version = 'polaris-api/' + S.API_VERSION

        def _go(self, method):
            n = int(self.headers.get('Content-Length') or 0)
            st, out, ctype = dispatch(service, method, self.path, self.rfile.read(n) if n else b'')
            data = encode(out, ctype)
            self.send_response(st)
            self.send_header('Content-Type', ctype if 'charset' in ctype or ctype == 'application/pdf'
                             else f'{ctype}; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Access-Control-Allow-Origin', 'http://localhost')   # local viewer only
            self.end_headers(); self.wfile.write(data)

        def do_GET(self):
            self._go('GET')

        def do_POST(self):
            self._go('POST')

        def log_message(self, fmt, *args):   # quiet unless asked
            if getattr(self.server, 'verbose', False):
                super().log_message(fmt, *args)
    return H


def serve(port=8767, service=None, verbose=True):
    srv = ThreadingHTTPServer(('127.0.0.1', port), make_handler(service or Service()))
    srv.verbose = verbose
    return srv


def main(argv=None):
    a = sys.argv[1:] if argv is None else argv
    if '--batch' in a:
        body = json.load(open(a[a.index('--batch') + 1]))
        st, out, _ = dispatch(Service(), 'POST', '/v1/batch', json.dumps(body).encode())
        print(json.dumps(out, indent=1, ensure_ascii=False))
        return 0 if st == 200 else 1
    port = int(a[a.index('--port') + 1]) if '--port' in a else 8767
    srv = serve(port)
    print(f'POLARIS X solver API on http://127.0.0.1:{port}/v1/health  (spec: /v1/openapi.yaml; tools: /v1/tools)',
          flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
