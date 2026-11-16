"""Local solver API stub for "query any point -> compute now" (§2.5). Pattern: tools/polaris_solver/__main__.py.

  python -m science.anysite.api --serve 8766      # POST http://127.0.0.1:8766/anysite {"lat":..,"lon":..,"mast_m":1}
  python -m science.anysite.api request.json      # one request from a file

Binds to 127.0.0.1 only. The response is a compact summary plus the path of the full bundle (data/cache/anysite/bundles/);
pass "full": true to receive the whole polaris-science-results-v1 bundle. Errors (e.g. no cached terrain at the point) are
returned as {"error": ...} with HTTP 400.
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

from .solve import OUT_DIR, solve

SPEC = {'name': 'polaris_anysite', 'endpoint': 'POST /anysite',
        'request': {'lat': 'deg, planetocentric (required)', 'lon': 'deg east (required)', 'mast_m': 'default 1',
                    'start': "default '2026-11-14 00:00' (UTC)", 'days': 'default 14', 'step_h': 'default 1',
                    'members': "list from ['clones','assumed','products'], default all", 'full': 'return the whole bundle'},
        'labels': {'geometry': 'SOURCE-BASED UNVALIDATED', 'error-model members': 'assumed error model'}}


def handle(req):
    b = solve(float(req['lat']), float(req['lon']), float(req.get('mast_m', 1.0)), req.get('start', '2026-11-14 00:00'),
              int(req.get('days', 14)), int(req.get('step_h', 1)),
              tuple(req.get('members', ('clones', 'assumed', 'products'))), int(req.get('n_members', 20)),
              allow_network=bool(req.get('allow_network', True)))
    if req.get('full'):
        return b
    m = b['metrics']; a = b['anysite']
    return {'site_hash': a['site_hash'], 'bundle_path': str(OUT_DIR / f"{a['site_hash']}.json"), 'cache_hit': a['cache_hit'],
            'label': m['label'], 'ground_m': b['site']['height_m'],
            'sun_center_visible_pct_hourly_samples': m['sun_center_visible_pct_hourly_samples'],
            'sun_and_earth_center_visible_pct_hourly_samples': m['sun_and_earth_center_visible_pct_hourly_samples'],
            'longest_sun_center_hidden_h': m['longest_sun_center_hidden_h'], 'n_truncated_bins': b['skyline']['n_truncated'],
            'near_product': a['near_field']['product_id'], 'far_product': a['far_field']['product_id'],
            'uncertainty': a['uncertainty']['summary'], 'timing_s': a['timing_s']}


class _H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        if self.path != '/anysite':
            self.send_error(404); return
        try:
            req = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            self._send(200, handle(req))
        except Exception as exc:  # noqa: BLE001
            self._send(400, {'error': f'{type(exc).__name__}: {exc}'})

    def do_GET(self):
        self._send(200, SPEC)


def main(argv=None):
    a = sys.argv[1:] if argv is None else argv
    if a and a[0] == '--serve':
        port = int(a[1]) if len(a) > 1 else 8766
        print(f'POST http://127.0.0.1:{port}/anysite   (GET / returns the spec)', flush=True)
        HTTPServer(('127.0.0.1', port), _H).serve_forever()
    else:
        req = json.load(open(a[0])) if a else json.load(sys.stdin)
        print(json.dumps(handle(req), indent=1))


if __name__ == '__main__':
    main()
