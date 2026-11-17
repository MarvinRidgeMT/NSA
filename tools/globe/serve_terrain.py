"""Static server for the display tiles (quantized-mesh terrain, coverage, analytics) with the headers Cesium needs.

The .terrain files are stored gzip-compressed (the usual Cesium terrain convention); a browser only inflates them if the
server sends `Content-Encoding: gzip`, which generic static servers do not. This server does, for *.terrain, and adds
CORS so a viewer on another port can read the tiles. Local use only (binds 127.0.0.1 by default).

    python -m tools.globe.serve_terrain [--dir web/public/globe] [--port 8765]
"""
from __future__ import annotations

import argparse
import functools
import http.server
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      '.terrain': 'application/vnd.quantized-mesh', '.json': 'application/json'}

    def end_headers(self):
        if self.path.split('?')[0].endswith('.terrain'):
            self.send_header('Content-Encoding', 'gzip')
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    def log_message(self, *a):
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.globe.serve_terrain')
    ap.add_argument('--dir', default=str(REPO / 'web' / 'public' / 'globe'))
    ap.add_argument('--port', type=int, default=8765); ap.add_argument('--bind', default='127.0.0.1')
    a = ap.parse_args(argv)
    h = functools.partial(Handler, directory=a.dir)
    with http.server.ThreadingHTTPServer((a.bind, a.port), h) as s:
        print(f'serving {a.dir} on http://{a.bind}:{a.port}/')
        s.serve_forever()
    return 0


if __name__ == '__main__':
    sys.exit(main())
