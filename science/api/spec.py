"""Single source of truth for the POLARIS X solver API: OpenAPI 3.1 document + AI-planner tool spec.

  python -m science.api.spec --write     # -> docs/v2/openapi.yaml, docs/v2/tool_spec.json
  python -m science.api.spec --check     # exit 1 if the committed files differ from this module

PyYAML is not installed, so `to_yaml` is a small emitter for the subset used here (maps, lists, strings, numbers,
booleans, null); test_api checks that the committed YAML equals `to_yaml(OPENAPI)` and that the schemas are valid
JSON Schema 2020-12 (the dialect of OpenAPI 3.1). There is no AI planner and no API key in this repository: the tool
spec only describes how a planner could call the local server.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
YAML_PATH = ROOT / 'docs' / 'v2' / 'openapi.yaml'
TOOLS_PATH = ROOT / 'docs' / 'v2' / 'tool_spec.json'
API_VERSION = '1.0.0'
LABEL = 'SOURCE-BASED · UNVALIDATED'
WORLDS = ['moon', 'mercury', 'mars']
DEFAULT_START = '2026-11-14 00:00'
MEMBER_KINDS = ['clones', 'assumed', 'products']

_ref = lambda n: {'$ref': f'#/components/schemas/{n}'}

SCHEMAS = {
    'Error': {'type': 'object', 'required': ['error', 'status'], 'additionalProperties': True, 'properties': {
        'error': {'type': 'string'}, 'status': {'type': 'integer'},
        'detail': {'type': ['string', 'null']}}},
    'SolveRequest': {
        'type': 'object', 'additionalProperties': False, 'required': ['lat', 'lon'],
        'properties': {
            'world': {'type': 'string', 'enum': WORLDS, 'default': 'moon',
                      'description': 'Context selector (not a scenario axis). Mercury: precomputed Prokofiev rim only; '
                                     'Mars: not available.'},
            'lat': {'type': 'number', 'minimum': -90, 'maximum': 90, 'description': 'planetocentric latitude, deg'},
            'lon': {'type': 'number', 'minimum': -360, 'maximum': 360, 'description': 'east longitude, deg'},
            'mast_m': {'type': 'number', 'minimum': 0, 'maximum': 1000, 'default': 1.0,
                       'description': 'observer height above the local terrain, m'},
            'start': {'type': 'string', 'pattern': r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$', 'default': DEFAULT_START,
                      'description': 'UTC window start'},
            'days': {'type': 'integer', 'minimum': 1, 'maximum': 400, 'description': 'window length (Moon default 14)'},
            'step_h': {'type': 'integer', 'minimum': 1, 'maximum': 24, 'default': 1},
            'members': {'type': 'array', 'items': {'type': 'string', 'enum': MEMBER_KINDS}, 'uniqueItems': True,
                        'description': 'uncertainty members. Omitted: use whatever member set was precomputed at this '
                                       'point; when computing, all three.'},
            'n_members': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 20},
            'compute': {'type': 'boolean', 'default': False,
                        'description': 'false: cache/precompute lookup only (404 if absent). true: run the any-site '
                                       'solver (needs the local terrain pyramid; seconds to a minute).'},
            'allow_network': {'type': 'boolean', 'default': False,
                              'description': 'allow JPL Horizons requests when computing (raw responses are cached)'},
            'full': {'type': 'boolean', 'default': False, 'description': 'return the whole results bundle'}}},
    'SolveResult': {
        'type': 'object', 'additionalProperties': True,
        'required': ['world', 'site_hash', 'label', 'cache', 'metrics', 'site', 'links', 'reproduce', 'disclaimer'],
        'properties': {
            'world': {'type': 'string', 'enum': WORLDS}, 'site_hash': {'type': 'string', 'pattern': '^[0-9a-f]{16}$'},
            'label': {'type': 'string'}, 'disclaimer': {'type': 'string'},
            'cache': {'type': 'object', 'required': ['hit', 'source'], 'properties': {
                'hit': {'type': 'boolean'},
                'source': {'type': 'string', 'enum': ['request-index', 'precompute', 'world-bundle', 'computed', 'solver-cache']}}},
            'site': {'type': 'object', 'required': ['lat_deg', 'lon_deg_east', 'observer_mast_m'], 'properties': {
                'id': {'type': ['string', 'null']}, 'name': {'type': ['string', 'null']},
                'lat_deg': {'type': 'number'}, 'lon_deg_east': {'type': 'number'},
                'height_m': {'type': ['number', 'null']}, 'observer_mast_m': {'type': 'number'}}},
            'window': {'type': 'object'},
            'members': {'type': 'array', 'items': {'type': 'string'}},
            'metrics': {'type': 'object', 'additionalProperties': {'$ref': '#/components/schemas/Number'}},
            'uncertainty': {'type': ['object', 'null']},
            'solver_version': {'type': ['string', 'null']},
            'links': {'type': 'object', 'additionalProperties': {'type': 'string'}},
            'reproduce': {'type': 'object', 'required': ['recompute'], 'properties': {'recompute': {'type': ['string', 'null']},
                                                                                      'export': {'type': 'string'}}},
            'bundle': {'type': 'object', 'description': 'whole polaris-science-results-v1 bundle (full=true)'}}},
    'Number': {
        'type': 'object', 'required': ['value', 'unit', 'label', 'json_path', 'read'], 'additionalProperties': True,
        'properties': {'value': {'type': ['number', 'integer', 'null']}, 'unit': {'type': 'string'},
                       'label': {'type': 'string'}, 'json_path': {'type': 'string'}, 'read': {'type': 'string'},
                       'source_file': {'type': 'string'}}},
    'BatchRequest': {'type': 'object', 'additionalProperties': False, 'required': ['requests'], 'properties': {
        'requests': {'type': 'array', 'minItems': 1, 'maxItems': 2000, 'items': _ref('SolveRequest')}}},
    'BatchResult': {'type': 'object', 'required': ['n', 'results', 'n_ok'], 'properties': {
        'n': {'type': 'integer'}, 'n_ok': {'type': 'integer'},
        'results': {'type': 'array', 'items': {'type': 'object', 'required': ['status', 'body'], 'properties': {
            'status': {'type': 'integer'}, 'body': {'type': 'object'}}}}}},
    'SiteList': {'type': 'object', 'required': ['n_total', 'sites', 'label'], 'properties': {
        'n_total': {'type': 'integer'}, 'offset': {'type': 'integer'}, 'label': {'type': 'string'},
        'window': {'type': ['string', 'null']},
        'sites': {'type': 'array', 'items': _ref('SiteSummary')}}},
    'SiteSummary': {'type': 'object', 'required': ['world', 'id', 'lat', 'lon', 'site_hash'], 'properties': {
        'world': {'type': 'string'}, 'id': {'type': 'string'}, 'name': {'type': ['string', 'null']},
        'group': {'type': ['string', 'null']}, 'lat': {'type': 'number'}, 'lon': {'type': 'number'},
        'site_hash': {'type': 'string'}, 'sun_pct': {'type': ['number', 'null']}, 'earth_pct': {'type': ['number', 'null']},
        'sun_earth_pct': {'type': ['number', 'null']}, 'longest_sun_gap_h': {'type': ['number', 'null']},
        'members': {'type': 'array', 'items': {'type': 'string'}}, 'bundle_cached': {'type': 'boolean'}}},
    'World': {'type': 'object', 'required': ['name', 'available'], 'additionalProperties': True, 'properties': {
        'name': {'type': 'string'}, 'available': {'type': 'boolean'}, 'availability_note': {'type': 'string'},
        'api_support': {'type': 'string'}}},
    'WorldList': {'type': 'object', 'required': ['worlds'], 'properties': {'worlds': {'type': 'array', 'items': _ref('World')}}},
    'Health': {'type': 'object', 'required': ['ok', 'version'], 'properties': {
        'ok': {'type': 'boolean'}, 'version': {'type': 'string'}, 'git': {'type': 'object'},
        'precomputed_sites': {'type': 'integer'}, 'bundle_cache': {'type': 'boolean'}}},
    'TimeSeries': {'type': 'object', 'required': ['schema', 'columns', 'rows', 'source'], 'additionalProperties': True,
                   'properties': {'schema': {'const': 'polaris-export-timeseries-v1'}, 'columns': {'type': 'array'},
                                  'rows': {'type': 'array'}, 'source': {'type': 'object'}}},
    'DecisionSummary': {'type': 'object', 'required': ['schema', 'site_id', 'rows'], 'additionalProperties': True,
                        'properties': {'schema': {'const': 'polaris-decision-summary-v1'}, 'site_id': {'type': 'string'},
                                       'rows': {'type': 'array', 'items': {'type': 'object', 'required': ['axis', 'value', 'label']}}}},
}


def _resp(desc, schema=None, ctype='application/json'):
    r = {'description': desc}
    if schema is not None:
        r['content'] = {ctype: {'schema': schema}}
    return r


def _err(*codes):
    text = {400: 'invalid request', 404: 'not found / not precomputed', 422: 'not available for this world/point',
            500: 'solver error', 501: 'world not available'}
    return {str(c): _resp(text[c], _ref('Error')) for c in codes}


_hash = {'name': 'site_hash', 'in': 'path', 'required': True, 'schema': {'type': 'string', 'pattern': '^[0-9a-f]{16}$'}}
_site_id = {'name': 'site_id', 'in': 'path', 'required': True, 'schema': {'type': 'string', 'pattern': '^[a-z0-9_]+$'}}
_world = {'name': 'world', 'in': 'path', 'required': True, 'schema': {'type': 'string', 'enum': WORLDS}}

PATHS = {
    '/v1/health': {'get': {'operationId': 'health', 'summary': 'Server status',
                           'responses': {'200': _resp('ok', _ref('Health'))}}},
    '/v1/worlds': {'get': {'operationId': 'listWorlds', 'summary': 'Worlds and what the API supports on each',
                           'responses': {'200': _resp('worlds', _ref('WorldList'))}}},
    '/v1/worlds/{world}': {'get': {'operationId': 'getWorld', 'parameters': [_world], 'summary': 'One world',
                                   'responses': {'200': _resp('world', _ref('World')), **_err(404)}}},
    '/v1/sites': {'get': {
        'operationId': 'listSites', 'summary': 'Precomputed sites (Moon any-site precompute + world bundles)',
        'parameters': [
            {'name': 'world', 'in': 'query', 'schema': {'type': 'string', 'enum': WORLDS}},
            {'name': 'group', 'in': 'query', 'schema': {'type': 'string'}},
            {'name': 'lat_min', 'in': 'query', 'schema': {'type': 'number'}},
            {'name': 'lat_max', 'in': 'query', 'schema': {'type': 'number'}},
            {'name': 'limit', 'in': 'query', 'schema': {'type': 'integer', 'minimum': 1, 'maximum': 5000, 'default': 100}},
            {'name': 'offset', 'in': 'query', 'schema': {'type': 'integer', 'minimum': 0, 'default': 0}}],
        'responses': {'200': _resp('sites', _ref('SiteList')), **_err(400)}}},
    '/v1/sites/{site_hash}': {'get': {
        'operationId': 'getSite', 'summary': 'Result of one precomputed / cached site',
        'parameters': [_hash, {'name': 'full', 'in': 'query', 'schema': {'type': 'boolean', 'default': False}}],
        'responses': {'200': _resp('result', _ref('SolveResult')), **_err(404)}}},
    '/v1/sites/{site_hash}/timeseries.json': {'get': {
        'operationId': 'getTimeSeriesJson', 'parameters': [_hash], 'summary': 'Hourly samples as JSON (exports format)',
        'responses': {'200': _resp('time series', _ref('TimeSeries')), **_err(404)}}},
    '/v1/sites/{site_hash}/timeseries.csv': {'get': {
        'operationId': 'getTimeSeriesCsv', 'parameters': [_hash], 'summary': 'Hourly samples as CSV',
        'responses': {'200': _resp('CSV, header row = column names of timeseries.json', {'type': 'string'}, 'text/csv'),
                      **_err(404)}}},
    '/v1/solve': {'post': {
        'operationId': 'solve', 'summary': 'Visibility metrics at one point (cache lookup; compute=true runs the solver)',
        'requestBody': {'required': True, 'content': {'application/json': {'schema': _ref('SolveRequest')}}},
        'responses': {'200': _resp('result', _ref('SolveResult')), **_err(400, 404, 422, 500, 501)}}},
    '/v1/batch': {'post': {
        'operationId': 'batch', 'summary': 'Many solve requests; result i equals POST /v1/solve with request i',
        'requestBody': {'required': True, 'content': {'application/json': {'schema': _ref('BatchRequest')}}},
        'responses': {'200': _resp('results in request order', _ref('BatchResult')), **_err(400)}}},
    '/v1/cubes/{site_id}/decision_summary': {'get': {
        'operationId': 'getDecisionSummary', 'parameters': [_site_id], 'summary': 'Precomputed Decision Card rows',
        'responses': {'200': _resp('rows', _ref('DecisionSummary')), **_err(404)}}},
    '/v1/cubes/{site_id}/decision_card.pdf': {'get': {
        'operationId': 'getDecisionCardPdf', 'parameters': [_site_id], 'summary': 'Decision Card PDF (from the precomputed rows)',
        'responses': {'200': _resp('PDF', {'type': 'string', 'contentMediaType': 'application/pdf'}, 'application/pdf'),
                      **_err(404)}}},
    '/v1/openapi.yaml': {'get': {'operationId': 'getOpenApiYaml', 'summary': 'This document (YAML)',
                                 'responses': {'200': _resp('OpenAPI', {'type': 'string'}, 'application/yaml')}}},
    '/v1/openapi.json': {'get': {'operationId': 'getOpenApiJson', 'summary': 'This document (JSON)',
                                 'responses': {'200': _resp('OpenAPI', {'type': 'object'})}}},
    '/v1/tools': {'get': {'operationId': 'getToolSpec', 'summary': 'Tool definitions (JSON Schema) for an AI planner',
                          'responses': {'200': _resp('tools', {'type': 'object'})}}},
}

OPENAPI = {
    'openapi': '3.1.0',
    'info': {'title': 'POLARIS X solver API', 'version': API_VERSION,
             'description': ('Local any-site visibility solver and precomputed results for the Moon (any point), Mercury '
                             '(precomputed Prokofiev rim) and Mars (not available). Binds to 127.0.0.1 only; no keys, no '
                             'paid services. Every number is ' + LABEL + ': local geometric visibility from NASA DEMs and '
                             'JPL Horizons, not certified illumination, power or DSN link availability. k of N maps is '
                             'not a probability. Docs: docs/v2/API.md.')},
    'servers': [{'url': 'http://127.0.0.1:8767', 'description': 'python -m science.api.server'}],
    'jsonSchemaDialect': 'https://json-schema.org/draft/2020-12/schema',
    'paths': PATHS,
    'components': {'schemas': SCHEMAS},
}


def _tool(name, desc, op, schema, method, path, path_params=()):
    return {'name': name, 'description': desc, 'input_schema': schema,
            'x-polaris-route': {'method': method, 'path': path, 'operationId': op, 'path_params': list(path_params)}}


def _inline(schema):
    """Resolve local $refs so each tool's input_schema stands alone."""
    if isinstance(schema, dict):
        if '$ref' in schema:
            return _inline(SCHEMAS[schema['$ref'].rsplit('/', 1)[1]])
        return {k: _inline(v) for k, v in schema.items()}
    if isinstance(schema, list):
        return [_inline(v) for v in schema]
    return schema


GROUNDING = ('Quote only numbers that appear in this turn\'s tool results, with their label; every result carries '
             'json_path/read commands. Visibility is geometric only (not power or DSN availability); '
             'k of N maps is not a probability; requirements are team requirements, not NASA standards.')

TOOLS = {
    'schema': 'polaris-tool-spec-v1',
    'api_version': API_VERSION,
    'server': 'http://127.0.0.1:8767 (python -m science.api.server)',
    'note': ('Tool definitions an AI planner COULD call. This repository contains no AI planner and no API key. '
             'Output written from these results must be labelled AI-GENERATED. ' + GROUNDING),
    'tools': [
        _tool('polaris_solve_site', 'Visibility of the Sun and Earth centre from one surface point (hourly samples, '
              'terrain skyline from NASA DEMs, ephemerides from JPL Horizons). Returns percentages, longest Sun gap, '
              'uncertainty ranges over terrain maps, and the commands that reproduce each number. ' + GROUNDING,
              'solve', _inline(SCHEMAS['SolveRequest']), 'POST', '/v1/solve'),
        _tool('polaris_batch_solve', 'Many polaris_solve_site requests at once; results in request order.',
              'batch', _inline(SCHEMAS['BatchRequest']), 'POST', '/v1/batch'),
        _tool('polaris_list_sites', 'List precomputed sites (1,251 Moon points + Mercury Prokofiev rim) with headline '
              'metrics, filterable by world, group and latitude.', 'listSites',
              {'type': 'object', 'additionalProperties': False, 'properties': {
                  'world': {'type': 'string', 'enum': WORLDS}, 'group': {'type': 'string'},
                  'lat_min': {'type': 'number'}, 'lat_max': {'type': 'number'},
                  'limit': {'type': 'integer', 'minimum': 1, 'maximum': 5000}, 'offset': {'type': 'integer', 'minimum': 0}}},
              'GET', '/v1/sites'),
        _tool('polaris_get_site', 'Result of one precomputed site by site_hash.', 'getSite',
              {'type': 'object', 'additionalProperties': False, 'required': ['site_hash'], 'properties': {
                  'site_hash': {'type': 'string', 'pattern': '^[0-9a-f]{16}$'}, 'full': {'type': 'boolean'}}},
              'GET', '/v1/sites/{site_hash}', ['site_hash']),
        _tool('polaris_get_timeseries', 'Hourly Sun/Earth samples (az, el, skyline, margin, visible) of one site.',
              'getTimeSeriesJson', {'type': 'object', 'additionalProperties': False, 'required': ['site_hash'],
                                    'properties': {'site_hash': {'type': 'string', 'pattern': '^[0-9a-f]{16}$'}}},
              'GET', '/v1/sites/{site_hash}/timeseries.json', ['site_hash']),
        _tool('polaris_decision_summary', 'Precomputed Decision Card rows (how sure, products, mast, when, requirement, '
              'link, energy, safety) for a site with scenario cubes (site04_roi3, site01_roi6).', 'getDecisionSummary',
              {'type': 'object', 'additionalProperties': False, 'required': ['site_id'],
               'properties': {'site_id': {'type': 'string', 'pattern': '^[a-z0-9_]+$'}}},
              'GET', '/v1/cubes/{site_id}/decision_summary', ['site_id']),
        _tool('polaris_list_worlds', 'Worlds and what the API supports on each.', 'listWorlds',
              {'type': 'object', 'additionalProperties': False, 'properties': {}}, 'GET', '/v1/worlds'),
    ],
}


# ------------------------------------------------------------------------------------------------------- YAML emitter
_PLAIN = re.compile(r'^[A-Za-z_][A-Za-z0-9_ ./()+,-]*$')
_RESERVED = {'true', 'false', 'null', 'yes', 'no', 'on', 'off', 'y', 'n', '~'}


def _scalar(v):
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return json.dumps(v)
    s = str(v)
    if _PLAIN.match(s) and s.lower() not in _RESERVED and not s.endswith(' ') and ': ' not in s and ' #' not in s:
        return s
    return json.dumps(s, ensure_ascii=False)        # a JSON string is a valid YAML double-quoted scalar


def _key(k):
    return _scalar(k) if _PLAIN.match(str(k)) and str(k).lower() not in _RESERVED else json.dumps(str(k))


def to_yaml(obj, indent=0) -> str:
    pad = '  ' * indent
    out = []
    if isinstance(obj, dict):
        if not obj:
            return pad + '{}\n'
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and v:
                out.append(f'{pad}{_key(k)}:\n' + to_yaml(v, indent + 1))
            else:
                out.append(f'{pad}{_key(k)}: {"{}" if v == {} else "[]" if v == [] else _scalar(v)}\n')
    elif isinstance(obj, list):
        for v in obj:
            if isinstance(v, (dict, list)) and v:
                body = to_yaml(v, indent + 1)
                out.append(f'{pad}- ' + body[len(pad) + 2:])
            else:
                out.append(f'{pad}- {"{}" if v == {} else "[]" if v == [] else _scalar(v)}\n')
    else:
        out.append(pad + _scalar(obj) + '\n')
    return ''.join(out)


HEADER = '# Generated by python -m science.api.spec --write (source: science/api/spec.py). Do not edit by hand.\n'


def yaml_text():
    return HEADER + to_yaml(OPENAPI)


def tools_text():
    return json.dumps(TOOLS, indent=1, ensure_ascii=False) + '\n'


def main(argv=None):
    a = sys.argv[1:] if argv is None else argv
    if '--write' in a:
        YAML_PATH.write_text(yaml_text()); TOOLS_PATH.write_text(tools_text())
        print(f'wrote {YAML_PATH.relative_to(ROOT)}, {TOOLS_PATH.relative_to(ROOT)}')
        return 0
    if '--check' in a:
        ok = YAML_PATH.exists() and YAML_PATH.read_text() == yaml_text() and TOOLS_PATH.read_text() == tools_text()
        print('up to date' if ok else 'STALE: run python -m science.api.spec --write')
        return 0 if ok else 1
    print(yaml_text())
    return 0


if __name__ == '__main__':
    sys.exit(main())
