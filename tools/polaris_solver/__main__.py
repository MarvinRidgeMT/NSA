"""CLI: python -m polaris_solver request.json   |   python -m polaris_solver --serve 8765   |   python -m polaris_solver --tool-spec"""
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from .api import solve, TOOL_SPEC


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/solve":
            self.send_error(404); return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            res, code = solve(body), 200
        except Exception as e:  # noqa: BLE001
            res, code = {"error": str(e)}, 400
        b = json.dumps(res).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        b = json.dumps(TOOL_SPEC).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--serve":
        port = int(a[1]) if len(a) > 1 else 8765
        print(f"POST http://127.0.0.1:{port}/solve   (GET / returns the tool spec)"); HTTPServer(("127.0.0.1", port), H).serve_forever()
    elif a and a[0] == "--tool-spec":
        print(json.dumps(TOOL_SPEC, indent=1))
    else:
        req = json.load(open(a[0])) if a else json.load(sys.stdin)
        print(json.dumps(solve(req), indent=1))
