"""The web viewer's "compute now" fixture (web/tests/fixtures/v1-solve-result.site01_roi6.json) is a real POST /v1/solve
answer. This test keeps it honest: its request and response validate against the OpenAPI schemas, the request is what
web/src/globe/anysite.ts `solveRequest` sends, and, when the (git-ignored) any-site cache is present, the live API answers
exactly the stored response.

Regenerate the fixture (needs data/cache/anysite/bundles/):
  python -c "import json; from science.api.tests.test_web_fixture import capture; capture()"
"""
from __future__ import annotations

import json
import unittest

import jsonschema

from science.api import server as SV, spec as S
from science.api.service import Service
from science.exports import common as C

FIXTURE = C.ROOT / 'web' / 'tests' / 'fixtures' / 'v1-solve-result.site01_roi6.json'
NOTE = ('Captured from python -m science.api.server POST /v1/solve (science.api.server.dispatch) for the request below; '
        'regenerate with the command in science/api/tests/test_web_fixture.py. Values are copied from the precomputed '
        'bundle; SOURCE-BASED · UNVALIDATED.')
# Keys and fixed values of the request web/src/globe/anysite.ts solveRequest() builds (SOLVE_WINDOW + compute flags).
WEB_REQUEST_FIXED = {'world': 'moon', 'mast_m': 1, 'start': '2026-11-14 00:00', 'days': 14, 'step_h': 1,
                     'compute': True, 'allow_network': True}


def _live(req):
    return SV.dispatch(Service(), 'POST', '/v1/solve', json.dumps(req).encode())


def capture():
    fx = json.loads(FIXTURE.read_text())
    st, out, _ = _live(fx['request'])
    assert st == 200, out
    FIXTURE.write_text(json.dumps({'_note': NOTE, 'request': fx['request'], 'status': st, 'response': out}, indent=1,
                                  ensure_ascii=False) + '\n')


class WebFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = json.loads(FIXTURE.read_text())

    def test_request_is_the_web_request_and_valid(self):
        req = self.fx['request']
        jsonschema.validate(req, S._inline(S.SCHEMAS['SolveRequest']))
        self.assertEqual({k: req[k] for k in WEB_REQUEST_FIXED}, WEB_REQUEST_FIXED)
        self.assertEqual(set(req), set(WEB_REQUEST_FIXED) | {'lat', 'lon', 'members'})
        self.assertEqual(req['members'], sorted(req['members']))
        src = (C.ROOT / 'web' / 'src' / 'globe' / 'anysite.ts').read_text()
        self.assertIn("SOLVE_WINDOW = { mast_m: 1, start: '2026-11-14 00:00', days: 14, step_h: 1 }", src)
        self.assertIn("world: 'moon', lat, lon, ...SOLVE_WINDOW, members: [...members].sort(), compute: true, "
                      "allow_network: true", src)

    def test_response_validates_and_has_what_the_panel_reads(self):
        out = self.fx['response']
        self.assertEqual(self.fx['status'], 200)
        jsonschema.validate(out, S._inline(S.SCHEMAS['SolveResult']))
        for k in ('sun_center_visible_pct_hourly_samples', 'sun_and_earth_center_visible_pct_hourly_samples',
                  'longest_sun_center_hidden_h'):
            self.assertIn(k, out['metrics'])
        self.assertEqual(set(out['terrain']), {'near_product', 'far_product', 'n_truncated_bins'})

    def test_live_api_answers_the_fixture(self):
        svc = Service()
        if not svc.bundle_path(self.fx['response']['site_hash']):
            self.skipTest('any-site bundle cache not present (git-ignored)')
        st, out, _ = SV.dispatch(svc, 'POST', '/v1/solve', json.dumps(self.fx['request']).encode())
        self.assertEqual(st, 200)
        out['cache'] = self.fx['response']['cache']        # request-index vs precompute depends on earlier calls
        self.assertEqual(out, self.fx['response'], 'API answer changed: regenerate the fixture (see module docstring)')


if __name__ == '__main__':
    unittest.main()
