"""Solver API: OpenAPI validates, routes == spec, live responses validate, values equal the source files, batch == single,
cache by site hash, error codes (docs/v2/PHASE_7_T1_PLAN.md §2). Fixtures use committed files only; one test uses the
real (git-ignored) any-site cache if present."""
from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import jsonschema

from science.api import server as SV, spec as S
from science.api.service import Service, request_key
from science.exports import card, common as C, timeseries

ROOT = C.ROOT
BUNDLE = ROOT / 'data' / 'bundles' / 'site04_roi3_2026-11-14_14d_mast1m.json'
MERCURY = ROOT / 'data' / 'worlds' / 'mercury' / 'mercury_prokofiev_rim_2026-11-14_176d_mast1m.json'
MARS = ROOT / 'data' / 'worlds' / 'mars' / 'mars_jezero_rim_2026-11-14_687d_mast1m.json.gz'
HASH = '0123456789abcdef'


def fixture_service(tmp: Path, solver=None, api_dir=None):
    """Service over a 1-site precompute summary whose bundle is the committed Site04 RoI 3 1 m bundle."""
    b = C.read_json(BUNDLE)
    cache = tmp / 'bundles'; cache.mkdir(parents=True, exist_ok=True)
    shutil.copy(BUNDLE, cache / f'{HASH}.json')
    pre = {'schema': 'polaris-anysite-precompute-summary-v1', 'window': '2026-11-14 00:00 UTC + 14 d, hourly; mast 1 m',
           'sites': [{'id': 'fixture_site04', 'name': 'fixture', 'group': 'current_sites', 'status': 'done',
                      'lat': b['site']['lat_deg'], 'lon': b['site']['lon_deg_east'], 'site_hash': HASH, 'uncertainty': {},
                      'sun_pct': b['metrics']['sun_center_visible_pct_hourly_samples'],
                      'earth_pct': b['metrics']['earth_center_visible_pct_hourly_samples'],
                      'sun_earth_pct': b['metrics']['sun_and_earth_center_visible_pct_hourly_samples'],
                      'longest_sun_gap_h': 19.0},   # group current_sites -> requested members clones+assumed+products
                     {'id': 'needs', 'group': 'artemis3_regions', 'status': 'needs coordinates', 'lat': None, 'lon': None}]}
    pp = tmp / 'pre.json'; pp.write_text(json.dumps(pre))
    return Service(cache_dir=api_dir or tmp / 'api', bundle_cache=cache, precompute=pp, solver=solver)


def schema_for(op_path, method, status):
    op = S.OPENAPI['paths'][op_path][method.lower()]
    r = op['responses'][str(status)]
    content = r.get('content', {})
    for ct, c in content.items():
        return ct, S._inline(c['schema'])
    return None, None


class Spec(unittest.TestCase):
    def test_committed_files_up_to_date(self):
        self.assertEqual(S.YAML_PATH.read_text(), S.yaml_text(), 'run python -m science.api.spec --write')
        self.assertEqual(S.TOOLS_PATH.read_text(), S.tools_text(), 'run python -m science.api.spec --write')

    def test_yaml_parses_to_the_spec_with_an_independent_parser(self):
        ruby = shutil.which('ruby')
        if not ruby:
            self.skipTest('ruby (independent YAML parser) not installed')
        out = subprocess.run([ruby, '-ryaml', '-rjson', '-e', 'puts JSON.generate(YAML.load_file(ARGV[0]))', str(S.YAML_PATH)],
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(out), S.OPENAPI)

    def test_openapi_structure(self):
        o = S.OPENAPI
        self.assertTrue(o['openapi'].startswith('3.1'))
        for name, sch in o['components']['schemas'].items():
            jsonschema.Draft202012Validator.check_schema(S._inline(sch))
        refs = re.findall(r'"\$ref": "#/components/schemas/(\w+)"', json.dumps(o))
        self.assertTrue(refs)
        for r in refs:
            self.assertIn(r, o['components']['schemas'])
        ops = []
        for path, item in o['paths'].items():
            params = set(re.findall(r'\{(\w+)\}', path))
            for method, op in item.items():
                self.assertIn(method, ('get', 'post'))
                ops.append(op['operationId'])
                self.assertIn('200', op['responses'])
                for code, resp in op['responses'].items():
                    self.assertRegex(code, r'^[1-5]\d\d$'); self.assertIn('description', resp)
                declared = {p['name'] for p in op.get('parameters', []) if p['in'] == 'path'}
                self.assertEqual(declared, params, (path, method))
                for p in op.get('parameters', []):
                    jsonschema.Draft202012Validator.check_schema(p['schema'])
                    if p['in'] == 'path':
                        self.assertTrue(p['required'])
                if method == 'post':
                    self.assertIn('requestBody', op)
        self.assertEqual(len(ops), len(set(ops)))

    def test_routes_equal_spec(self):
        spec_routes = {(m.upper(), p) for p, item in S.OPENAPI['paths'].items() for m in item}
        self.assertEqual(set(SV.ROUTES), spec_routes)

    def test_tool_spec(self):
        ops = {op['operationId']: (m.upper(), p) for p, item in S.OPENAPI['paths'].items() for m, op in item.items()}
        self.assertIn('no AI planner', S.TOOLS['note'])
        for t in S.TOOLS['tools']:
            self.assertRegex(t['name'], r'^[a-z_]{1,64}$')
            jsonschema.Draft202012Validator.check_schema(t['input_schema'])
            self.assertNotIn('$ref', json.dumps(t['input_schema']))
            r = t['x-polaris-route']
            self.assertEqual(ops[r['operationId']], (r['method'], r['path']))
            self.assertEqual(set(r['path_params']), set(re.findall(r'\{(\w+)\}', r['path'])))
        solve = next(t for t in S.TOOLS['tools'] if t['name'] == 'polaris_solve_site')
        jsonschema.validate({'lat': -89.78012, 'lon': -156.32023, 'mast_m': 1}, solve['input_schema'])
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({'lat': -91, 'lon': 0}, solve['input_schema'])

    def test_yaml_emitter_quotes(self):
        for v in ['true', 'no', 'a: b', '#x', '3.1.0', '200', '', 'x #y', ' lead', "it's", 'é·–', '$ref', '[x]']:
            y = S.to_yaml({'k': v})
            if shutil.which('ruby'):
                out = subprocess.run([shutil.which('ruby'), '-ryaml', '-rjson', '-e', 'puts JSON.generate(YAML.load(STDIN.read))'],
                                     input=y, capture_output=True, text=True, check=True).stdout
                self.assertEqual(json.loads(out), {'k': v}, y)


class Live(unittest.TestCase):
    """A real HTTP server on 127.0.0.1 (ephemeral port) over the fixture service."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='polaris_api_'))
        cls.svc = fixture_service(cls.tmp)
        cls.srv = SV.serve(0, cls.svc, verbose=False)
        cls.port = cls.srv.server_address[1]
        cls.th = threading.Thread(target=cls.srv.serve_forever, daemon=True); cls.th.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close(); shutil.rmtree(cls.tmp, ignore_errors=True)

    def call(self, method, path, body=None):
        data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}{path}', data=data, method=method,
                                     headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.headers.get('Content-Type'), r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get('Content-Type'), e.read()

    def check(self, method, path, spec_path, body=None, status=200):
        st, ct, raw = self.call(method, path, body)
        self.assertEqual(st, status, raw[:300])
        sct, sch = schema_for(spec_path, method, status)
        self.assertTrue(ct.startswith(sct.split(';')[0]), (ct, sct))
        if sct == 'application/json':
            out = json.loads(raw)
            jsonschema.validate(out, sch)
            return out
        return raw

    def test_health_worlds(self):
        h = self.check('GET', '/v1/health', '/v1/health')
        self.assertTrue(h['ok'])
        w = self.check('GET', '/v1/worlds', '/v1/worlds')
        self.assertEqual([x['name'] for x in w['worlds']], ['moon', 'mercury', 'mars'])
        # availability comes from the worlds registry (T3 made Mars available after this test was written)
        from science.worlds import get_world
        for x in w['worlds']:
            self.assertEqual(x['available'], bool(get_world(x['name']).available), x['name'])
        self.check('GET', '/v1/worlds/mercury', '/v1/worlds/{world}')
        self.check('GET', '/v1/worlds/pluto', '/v1/worlds/{world}', status=404)

    def test_sites_and_site(self):
        s = self.check('GET', '/v1/sites', '/v1/sites')
        self.assertEqual(s['n_total'], len(self.svc.precompute['sites']) + len(self.svc.world_bundle_index))  # fixture Moon site + every committed world bundle
        self.assertEqual({x['world'] for x in s['sites']}, {'moon', 'mercury', 'mars'})
        s = self.check('GET', '/v1/sites?world=moon&lat_max=-80', '/v1/sites')
        self.assertEqual([x['site_hash'] for x in s['sites']], [HASH])
        self.check('GET', '/v1/sites?limit=0', '/v1/sites', status=400)
        r = self.check('GET', f'/v1/sites/{HASH}', '/v1/sites/{site_hash}')
        b = C.read_json(BUNDLE)
        for k, m in r['metrics'].items():
            self.assertEqual(m['value'], b['metrics'][k], k)
            self.assertEqual(C.json_get(b, m['json_path']), m['value'])
        full = self.check('GET', f'/v1/sites/{HASH}?full=1', '/v1/sites/{site_hash}')
        self.assertEqual(full['bundle'], b)
        self.check('GET', '/v1/sites/ffffffffffffffff', '/v1/sites/{site_hash}', status=404)

    def test_timeseries_round_trip(self):
        doc = self.check('GET', f'/v1/sites/{HASH}/timeseries.json', '/v1/sites/{site_hash}/timeseries.json')
        self.assertEqual(doc['rows'], json.loads(json.dumps(timeseries.build(BUNDLE)['rows'])))
        b = C.read_json(BUNDLE)
        self.assertEqual(len(doc['rows']), len(b['samples']))
        i = [c['name'] for c in doc['columns']].index('sun_el_deg')
        self.assertEqual([r[i] for r in doc['rows']], [s['sun']['el_deg'] for s in b['samples']])
        raw = self.check('GET', f'/v1/sites/{HASH}/timeseries.csv', '/v1/sites/{site_hash}/timeseries.csv')
        self.assertEqual(raw.decode(), timeseries.to_csv(timeseries.build(BUNDLE)))

    def test_cubes(self):
        d = self.check('GET', '/v1/cubes/site04_roi3/decision_summary', '/v1/cubes/{site_id}/decision_summary')
        self.assertEqual(d, C.read_json(ROOT / 'data/cubes/site04_roi3/decision_summary.json'))
        pdf = self.check('GET', '/v1/cubes/site04_roi3/decision_card.pdf', '/v1/cubes/{site_id}/decision_card.pdf')
        self.assertEqual(pdf, card.render('site04_roi3')[0])
        self.check('GET', '/v1/cubes/nosuchsite/decision_summary', '/v1/cubes/{site_id}/decision_summary', status=404)
        st, _, _ = self.call('GET', '/v1/cubes/../decision_summary')
        self.assertEqual(st, 404)

    def test_spec_and_tools_served(self):
        raw = self.check('GET', '/v1/openapi.yaml', '/v1/openapi.yaml')
        self.assertEqual(raw.decode(), S.yaml_text())
        self.assertEqual(self.check('GET', '/v1/openapi.json', '/v1/openapi.json'), S.OPENAPI)
        self.assertEqual(self.check('GET', '/v1/tools', '/v1/tools'), json.loads(S.tools_text()))

    def test_solve_codes(self):
        b = C.read_json(BUNDLE)
        r = self.check('POST', '/v1/solve', '/v1/solve', {'lat': b['site']['lat_deg'], 'lon': b['site']['lon_deg_east']})
        self.assertEqual(r['site_hash'], HASH)
        self.assertEqual(r['metrics']['sun_center_visible_pct_hourly_samples']['value'], 94.362)
        m = C.read_json(MERCURY)['site']
        r = self.check('POST', '/v1/solve', '/v1/solve', {'world': 'mercury', 'lat': m['lat_deg'], 'lon': m['lon_deg_east']})
        self.assertEqual(r['world'], 'mercury'); self.assertEqual(r['cache']['source'], 'world-bundle')
        self.assertEqual(r['metrics']['sun_center_visible_pct_hourly_samples']['value'],
                         C.read_json(MERCURY)['metrics']['sun_center_visible_pct_hourly_samples'])
        self.check('POST', '/v1/solve', '/v1/solve', {'world': 'mercury', 'lat': 0, 'lon': 0}, status=422)
        self.check('POST', '/v1/solve', '/v1/solve', {'world': 'mars', 'lat': 0, 'lon': 0}, status=422)
        j = C.read_json(MARS)
        r = self.check('POST', '/v1/solve', '/v1/solve', {'world': 'mars', 'lat': j['site']['lat_deg'],
                                                          'lon': j['site']['lon_deg_east']})
        self.assertEqual((r['world'], r['cache']['source']), ('mars', 'world-bundle'))
        self.assertEqual(r['metrics']['sun_center_visible_pct_hourly_samples']['value'],
                         j['metrics']['sun_center_visible_pct_hourly_samples'])
        self.check('POST', '/v1/solve', '/v1/solve', {'lat': 95, 'lon': 0}, status=400)
        self.check('POST', '/v1/solve', '/v1/solve', {'lat': 0, 'lon': 0, 'bogus': 1}, status=400)
        self.check('POST', '/v1/solve', '/v1/solve', b'{not json', status=400)
        self.check('POST', '/v1/solve', '/v1/solve', {'lat': -45.0, 'lon': 10.0}, status=404)   # not precomputed
        st, _, _ = self.call('GET', '/v1/solve'); self.assertEqual(st, 405)
        st, _, _ = self.call('GET', '/v1/nothing'); self.assertEqual(st, 404)


class BatchAndCache(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='polaris_api_'))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def reqs(self):
        b = C.read_json(BUNDLE)['site']; m = C.read_json(MERCURY)['site']
        return [{'lat': b['lat_deg'], 'lon': b['lon_deg_east']},
                {'world': 'mercury', 'lat': m['lat_deg'], 'lon': m['lon_deg_east']},
                {'world': 'mars', 'lat': 1, 'lon': 2}, {'lat': 91, 'lon': 0}, {'lat': -45.0, 'lon': 10.0},
                {'lat': b['lat_deg'], 'lon': b['lon_deg_east'] + 360.0}]      # same point, other longitude convention

    def test_batch_equals_single(self):
        bs = fixture_service(self.tmp)
        st, out, _ = SV.dispatch(bs, 'POST', '/v1/batch', json.dumps({'requests': self.reqs()}).encode())
        self.assertEqual(st, 200); self.assertEqual(out['n'], 6); self.assertEqual(out['n_ok'], 3)
        jsonschema.validate(out, S._inline(S.SCHEMAS['BatchResult']))
        single = fixture_service(self.tmp, api_dir=self.tmp / 'api_single')   # fresh request index, same files
        for q, res in zip(self.reqs(), out['results']):
            st1, out1, _ = SV.dispatch(single, 'POST', '/v1/solve', json.dumps(q).encode())
            a, b = copy.deepcopy(res['body']), copy.deepcopy(out1)
            for x in (a, b):                       # cache provenance differs only by call order (index vs precompute)
                x.pop('cache', None)
            self.assertEqual((res['status'], a), (st1, b), q)
        st, out, _ = SV.dispatch(bs, 'POST', '/v1/batch', b'{"requests": []}')
        self.assertEqual(st, 400)

    def test_cli_batch_equals_dispatch(self):
        p = self.tmp / 'q.json'; p.write_text(json.dumps({'requests': [{'world': 'mars', 'lat': 0, 'lon': 0}]}))
        out = subprocess.run([__import__('sys').executable, '-m', 'science.api.server', '--batch', str(p)], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(out)['results'][0]['status'], 422)      # Mars: only the precomputed Jezero point

    def test_cache_by_site_hash(self):
        svc = fixture_service(self.tmp)
        b = C.read_json(BUNDLE)['site']
        q = {'lat': b['lat_deg'], 'lon': b['lon_deg_east']}
        _, r1 = svc.solve(q); _, r2 = svc.solve(q)
        self.assertEqual(r1['cache']['source'], 'precompute'); self.assertEqual(r2['cache']['source'], 'request-index')
        r1.pop('cache'); r2.pop('cache'); self.assertEqual(r1, r2)
        idx = json.loads((self.tmp / 'api' / 'request_index.json').read_text())
        self.assertEqual(idx[request_key(svc.normalise(q))]['site_hash'], HASH)
        _, r3 = svc.solve({**q, 'lon': q['lon'] + 360})
        self.assertEqual(r3['cache']['source'], 'request-index')         # normalised longitude -> same key

    def test_compute_path_calls_solver_once(self):
        calls = []
        cache = self.tmp / 'bundles'

        def fake_solver(lat, lon, **kw):
            calls.append((lat, lon, kw))
            b = C.read_json(BUNDLE); b['site']['lat_deg'] = lat; b['site']['lon_deg_east'] = lon
            b['anysite'] = {'site_hash': 'feedfacecafebeef', 'solver_version': 'fake', 'cache_hit': False,
                            'uncertainty': {}}
            (cache / 'feedfacecafebeef.json').write_text(json.dumps(b))
            return b
        svc = fixture_service(self.tmp, solver=fake_solver)
        q = {'lat': -45.0, 'lon': 10.0, 'mast_m': 2.5, 'members': [], 'compute': True}
        st, r = svc.solve(q)
        self.assertEqual(r['cache'], {'hit': False, 'source': 'computed'}); self.assertEqual(r['site_hash'], 'feedfacecafebeef')
        self.assertEqual(calls[0][2]['mast_m'], 2.5); self.assertEqual(calls[0][2]['member_kinds'], ())
        st, r = svc.solve({**q, 'compute': False})
        self.assertEqual(r['cache']['source'], 'request-index'); self.assertEqual(len(calls), 1)


class RealCache(unittest.TestCase):
    def test_site04_from_real_precompute(self):
        svc = Service(cache_dir=Path(tempfile.mkdtemp(prefix='polaris_api_')))
        s = next((x for x in svc.precompute['sites'] if x['id'] == 'site04_roi3'), None)
        if s is None or svc.bundle_path(s['site_hash']) is None:
            self.skipTest('any-site cache not present (git-ignored)')
        st, r = svc.solve({'lat': s['lat'], 'lon': s['lon']})
        self.assertEqual(r['site_hash'], s['site_hash'])
        self.assertEqual(r['metrics']['sun_center_visible_pct_hourly_samples']['value'], s['sun_pct'])
        self.assertEqual(r['metrics']['sun_and_earth_center_visible_pct_hourly_samples']['value'], s['sun_earth_pct'])
        self.assertEqual(r['members'], ['clones', 'products'])          # present in the bundle (no assumed: real clones)
        self.assertEqual(svc._pre_members(s), ['assumed', 'clones', 'products'])   # requested -> enters the site_hash
        st, sites = svc.sites(limit=5000)
        self.assertEqual(sites['n_total'], len(svc.precompute['sites']) + len(svc.world_bundle_index))


if __name__ == '__main__':
    unittest.main()
