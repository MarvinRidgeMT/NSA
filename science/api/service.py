"""The API's logic, independent of HTTP: every route is `Service.<op>(...) -> (status, body, content_type)`.

Cache by site hash: a solve request is normalised (`request_key`) and mapped to the any-site solver's `site_hash`
(the solver's own cache key, which includes the window, members and terrain products). Lookup order:
  1. request index  data/cache/api/request_index.json (requests answered before)
  2. precompute     data/anysite/precompute_summary.json (1,251 Moon points; mast 1 m, 2026-11-14 + 14 d, hourly)
  3. world bundles  data/worlds/<world>/*.json[.gz] (Mercury Prokofiev rim; Mars Jezero rim)
  4. compute=true   science.worlds.moon.solve (= science.anysite.solve.solve, unchanged); result added to the index.
Nothing here changes a number: responses copy bundle values and carry their JSON path + read/recompute commands.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import threading
from pathlib import Path

import jsonschema

from ..exports import common as C
from . import spec as S

DEFAULT_CACHE = C.ROOT / 'data' / 'cache' / 'api'
BUNDLE_CACHE = C.ROOT / 'data' / 'cache' / 'anysite' / 'bundles'
PRECOMPUTE = C.ROOT / 'data' / 'anysite' / 'precompute_summary.json'
WORLD_BUNDLES = {'mercury': C.ROOT / 'data' / 'worlds' / 'mercury', 'mars': C.ROOT / 'data' / 'worlds' / 'mars'}
CUBES = C.ROOT / 'data' / 'cubes'
DEFAULT_DAYS = 14
METRIC_UNITS = {'sun_center_visible_pct_hourly_samples': '% of hourly samples',
                'earth_center_visible_pct_hourly_samples': '% of hourly samples',
                'sun_and_earth_center_visible_pct_hourly_samples': '% of hourly samples',
                'longest_sun_center_hidden_h': 'h', 'longest_earth_center_hidden_h': 'h',
                'min_sun_margin_deg': 'deg', 'min_earth_margin_deg': 'deg',
                'n_samples': 'samples', 'n_unknown_sun': 'samples', 'n_unknown_earth': 'samples'}


class ApiError(Exception):
    def __init__(self, status, msg, detail=None):
        super().__init__(msg); self.status = status; self.msg = msg; self.detail = detail

    def body(self):
        return {'error': self.msg, 'status': self.status, 'detail': self.detail}


def _norm_lon(lon):
    return ((float(lon) + 180.0) % 360.0) - 180.0


_KIND = {'pgda78-clone': 'clones', 'clone': 'clones', 'clones': 'clones', 'product': 'products', 'products': 'products',
         'assumed': 'assumed', 'assumed-error-model': 'assumed'}


def _members_of(bundle):
    """Member kinds PRESENT in a bundle (anysite.uncertainty.members[].kind), in request vocabulary."""
    unc = (bundle.get('anysite') or {}).get('uncertainty') or {}
    ms = unc.get('members') if isinstance(unc, dict) else None
    return sorted({_KIND.get(m.get('kind'), m.get('kind')) for m in ms or [] if isinstance(m, dict)})


def request_key(r: dict) -> str:
    key = {'world': r['world'], 'lat': round(float(r['lat']), 7), 'lon': round(_norm_lon(r['lon']), 7),
           'mast_m': float(r['mast_m']), 'start': r['start'], 'days': r['days'], 'step_h': int(r['step_h']),
           'members': None if r.get('members') is None else sorted(r['members']), 'n_members': int(r['n_members'])}
    return hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:16]


class Service:
    def __init__(self, cache_dir=None, bundle_cache=BUNDLE_CACHE, precompute=PRECOMPUTE, world_bundles=None,
                 solver=None):
        self.cache_dir = Path(cache_dir or os.environ.get('POLARIS_API_CACHE') or DEFAULT_CACHE)
        self.bundle_cache = Path(bundle_cache)
        self.precompute_path = Path(precompute)
        self.world_bundles = world_bundles or WORLD_BUNDLES
        self._solver = solver            # injectable for tests; default: science.worlds.moon.solve
        self._lock = threading.Lock()
        self._pre = None; self._worldb = None
        self._req_validator = jsonschema.Draft202012Validator(S.SCHEMAS['SolveRequest'])

    # ------------------------------------------------------------------------------------------- indexes
    @property
    def precompute(self):
        if self._pre is None:
            d = C.read_json(self.precompute_path) if self.precompute_path.exists() else {'sites': []}
            sites = [s for s in d['sites'] if s.get('status') == 'done' and s.get('site_hash')]
            self._pre = {'doc': d, 'sites': sites, 'by_hash': {s['site_hash']: s for s in sites},
                         'index': {i: s for i, s in enumerate(d['sites'])}}
        return self._pre

    @property
    def world_bundle_index(self):
        """site_hash -> (world, path, bundle) for precomputed world bundles (hash = SHA-256 of the file, 16 hex)."""
        if self._worldb is None:
            out = {}
            for w, d in self.world_bundles.items():
                ps = sorted([*Path(d).glob('*.json'), *Path(d).glob('*.json.gz')]) if Path(d).exists() else []
                for p in ps:
                    b = C.read_json(p)
                    if b.get('schema') != 'polaris-science-results-v1':
                        continue
                    out[C.sha256_file(p)[:16]] = (w, p, b)
            self._worldb = out
        return self._worldb

    def _index_path(self):
        return self.cache_dir / 'request_index.json'

    def _index(self):
        p = self._index_path()
        return json.loads(p.read_text()) if p.exists() else {}

    def _index_put(self, key, site_hash, req):
        with self._lock:
            idx = self._index(); idx[key] = {'site_hash': site_hash, 'request': req}
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            tmp = self._index_path().with_suffix(f'.{os.getpid()}.tmp'); tmp.write_text(json.dumps(idx, indent=1))
            tmp.replace(self._index_path())

    def bundle_path(self, site_hash):
        if site_hash in self.world_bundle_index:
            return self.world_bundle_index[site_hash][1]
        p = self.bundle_cache / f'{site_hash}.json'
        return p if p.exists() else None

    # ------------------------------------------------------------------------------------------- routes
    def health(self):
        return 200, {'ok': True, 'version': S.API_VERSION, 'git': C.git_commit(),
                     'precomputed_sites': len(self.precompute['sites']) + len(self.world_bundle_index),
                     'bundle_cache': self.bundle_cache.exists()}

    def worlds(self):
        return 200, {'worlds': [self._world(w) for w in S.WORLDS]}

    def world(self, name):
        if name not in S.WORLDS:
            raise ApiError(404, f'unknown world {name!r}')
        return 200, self._world(name)

    def _world(self, name):
        from ..worlds import get_world
        s = get_world(name).summary()
        s['api_support'] = {'moon': 'any point (cache lookup; compute=true runs the any-site solver)',
                            'mercury': 'precomputed world bundles only (any-site world= hook is session T3\'s)',
                            'mars': 'precomputed world bundles only (Jezero rim, one Mars year); relay-orbiter geometry '
                                    'in data/worlds/mars/mars_jezero_rim_relays_2026-11-14_16d.json'}[name]
        return s

    def sites(self, world=None, group=None, lat_min=None, lat_max=None, limit=100, offset=0):
        try:
            limit = int(limit); offset = int(offset)
            lat_min = None if lat_min is None else float(lat_min); lat_max = None if lat_max is None else float(lat_max)
        except (TypeError, ValueError) as e:
            raise ApiError(400, f'bad query parameter: {e}')
        if not (1 <= limit <= 5000) or offset < 0:
            raise ApiError(400, 'limit must be 1..5000 and offset >= 0')
        if world is not None and world not in S.WORLDS:
            raise ApiError(400, f'unknown world {world!r}')
        rows = []
        if world in (None, 'moon'):
            for s in self.precompute['sites']:
                rows.append({'world': 'moon', 'id': s['id'], 'name': s.get('name'), 'group': s.get('group'),
                             'lat': s['lat'], 'lon': s['lon'], 'site_hash': s['site_hash'], 'sun_pct': s.get('sun_pct'),
                             'earth_pct': s.get('earth_pct'), 'sun_earth_pct': s.get('sun_earth_pct'),
                             'longest_sun_gap_h': s.get('longest_sun_gap_h'),
                             'members': self._pre_members(s),
                             'bundle_cached': (self.bundle_cache / f'{s["site_hash"]}.json').exists()})
        for h, (w, p, b) in self.world_bundle_index.items():
            if world in (None, w):
                m = b['metrics']
                rows.append({'world': w, 'id': b['site']['id'], 'name': b['site'].get('name'), 'group': 'world_bundle',
                             'lat': b['site']['lat_deg'], 'lon': b['site']['lon_deg_east'], 'site_hash': h,
                             'sun_pct': m.get('sun_center_visible_pct_hourly_samples'),
                             'earth_pct': m.get('earth_center_visible_pct_hourly_samples'),
                             'sun_earth_pct': m.get('sun_and_earth_center_visible_pct_hourly_samples'),
                             'longest_sun_gap_h': m.get('longest_sun_center_hidden_h'), 'members': [],
                             'bundle_cached': True})
        rows = [r for r in rows if (group is None or r['group'] == group)
                and (lat_min is None or r['lat'] >= lat_min) and (lat_max is None or r['lat'] <= lat_max)]
        return 200, {'n_total': len(rows), 'offset': offset, 'label': C.LABEL,
                     'window': self.precompute['doc'].get('window'), 'sites': rows[offset:offset + limit]}

    @staticmethod
    def _pre_members(s):
        """Member kinds REQUESTED by the precompute for this site (they enter the solver's site_hash); a kind may be
        requested and still absent (e.g. 'assumed' where real PGDA 78 clones exist)."""
        from ..anysite.precompute import _members_for
        return sorted(_members_for(s.get('group')))

    def site(self, site_hash, full=False):
        p = self.bundle_path(site_hash)
        if p is None:
            s = self.precompute['by_hash'].get(site_hash)
            if s is None:
                raise ApiError(404, f'unknown site_hash {site_hash}')
            raise ApiError(404, f'site {site_hash} ({s["id"]}) is in the precompute summary but its bundle is not in '
                                f'the local cache (data/cache/anysite/bundles, git-ignored)',
                           detail='summary values: GET /v1/sites?group=' + s['group'])
        world = self.world_bundle_index[site_hash][0] if site_hash in self.world_bundle_index else 'moon'
        source = 'world-bundle' if world != 'moon' else ('precompute' if site_hash in self.precompute['by_hash']
                                                          else 'solver-cache')
        return 200, self.result(p, world, site_hash, hit=True, source=source, full=full)

    def timeseries(self, site_hash, fmt):
        from ..exports import timeseries as TS
        p = self.bundle_path(site_hash)
        if p is None:
            raise ApiError(404, f'no cached bundle for site_hash {site_hash}')
        doc = TS.build(p)
        if fmt == 'csv':
            return 200, TS.to_csv(doc), 'text/csv; charset=utf-8'
        return 200, doc

    def decision_summary(self, site_id):
        p = self._cube_dir(site_id) / 'decision_summary.json'
        if not p.exists():
            raise ApiError(404, f'no decision_summary.json for {site_id}')
        return 200, C.read_json(p)

    def decision_card(self, site_id):
        from ..exports import card
        if not (self._cube_dir(site_id) / 'decision_summary.json').exists():
            raise ApiError(404, f'no decision_summary.json for {site_id}')
        return 200, card.render(site_id)[0], 'application/pdf'

    def _cube_dir(self, site_id):
        allowed = {p.name for p in CUBES.iterdir() if p.is_dir()} if CUBES.exists() else set()
        if site_id not in allowed:
            raise ApiError(404, f'no scenario cubes for {site_id!r} (available: {sorted(allowed)})')
        return CUBES / site_id

    # ------------------------------------------------------------------------------------------- solve
    def normalise(self, req):
        if not isinstance(req, dict):
            raise ApiError(400, 'request body must be a JSON object')
        errs = sorted(self._req_validator.iter_errors(req), key=lambda e: list(e.path))
        if errs:
            raise ApiError(400, 'invalid solve request', detail='; '.join(
                f'{"/".join(map(str, e.path)) or "(root)"}: {e.message}' for e in errs[:5]))
        if not all(math.isfinite(float(req[k])) for k in ('lat', 'lon')):
            raise ApiError(400, 'lat and lon must be finite')
        r = {'world': req.get('world', 'moon'), 'lat': float(req['lat']), 'lon': _norm_lon(req['lon']),
             'mast_m': float(req.get('mast_m', 1.0)), 'start': req.get('start', S.DEFAULT_START),
             'days': req.get('days'), 'step_h': int(req.get('step_h', 1)),
             'members': None if req.get('members') is None else sorted(req['members']),
             'n_members': int(req.get('n_members', 20)), 'compute': bool(req.get('compute', False)),
             'allow_network': bool(req.get('allow_network', False)), 'full': bool(req.get('full', False))}
        if r['world'] == 'moon' and r['days'] is None:
            r['days'] = DEFAULT_DAYS
        return r

    def solve(self, req):
        r = self.normalise(req)
        if r['world'] != 'moon':
            from ..worlds import get_world
            w = get_world(r['world'])
            if not w.available:
                raise ApiError(501, f"{r['world']} is not available", detail=w.availability_note)
        if r['world'] != 'moon':
            return 200, self._solve_world_bundle(r)
        key = request_key(r)
        hit = self._index().get(key)
        if hit and self.bundle_path(hit['site_hash']):
            return 200, self.result(self.bundle_path(hit['site_hash']), 'moon', hit['site_hash'], True, 'request-index',
                                    r['full'])
        s = self._precompute_match(r)
        if s is not None and self.bundle_path(s['site_hash']):
            self._index_put(key, s['site_hash'], self._public(r))
            return 200, self.result(self.bundle_path(s['site_hash']), 'moon', s['site_hash'], True, 'precompute', r['full'])
        if not r['compute']:
            raise ApiError(404, 'not precomputed for this request; pass "compute": true to run the solver',
                           detail=(f'precomputed: mast 1 m, {self.precompute["doc"].get("window")}; '
                                   f'{len(self.precompute["sites"])} points (GET /v1/sites)'))
        return 200, self._compute(r, key)

    def _public(self, r):
        return {k: v for k, v in r.items() if k not in ('compute', 'full', 'allow_network')}

    def _precompute_match(self, r):
        if (r['mast_m'] != 1.0 or r['start'] != S.DEFAULT_START or r['days'] != DEFAULT_DAYS or r['step_h'] != 1
                or r['n_members'] != 20):
            return None
        for s in self.precompute['sites']:
            if abs(s['lat'] - r['lat']) < 1e-6 and abs(_norm_lon(s['lon'] - r['lon'])) < 1e-6:
                if r['members'] is None or r['members'] == self._pre_members(s):
                    return s
        return None

    def _solve_world_bundle(self, r):
        for h, (w, p, b) in self.world_bundle_index.items():
            if w != r['world']:
                continue
            s = b['site']
            same_pt = abs(s['lat_deg'] - r['lat']) < 1e-6 and abs(_norm_lon(s['lon_deg_east'] - r['lon'])) < 1e-6
            win_days = round((C_time(b['time']['stop_utc']) - C_time(b['time']['start_utc'])) / 86400)
            ok = (same_pt and r['mast_m'] == float(s.get('observer_mast_m', 1.0))
                  and r['start'] == b['time']['start_utc'][:16].replace('T', ' ')
                  and r['days'] in (None, win_days) and r['step_h'] == b['time'].get('step_h', 1))
            if ok:
                return self.result(p, w, h, True, 'world-bundle', r['full'])
        sites = [(b['site']['id'], b['site']['lat_deg'], b['site']['lon_deg_east'])
                 for w, _, b in self.world_bundle_index.values() if w == r['world']]
        raise ApiError(422, f'{r["world"]}: only precomputed world bundles are served; any-site solving on '
                            f'{r["world"]} is not wired into the API', detail=f'available: {sites}')

    def _compute(self, r, key):
        solver = self._solver
        if solver is None:
            from ..worlds.moon import solve as solver
        kinds = tuple(r['members']) if r['members'] is not None else tuple(S.MEMBER_KINDS)
        try:
            b = solver(r['lat'], r['lon'], mast_m=r['mast_m'], start=r['start'], days=r['days'], step_h=r['step_h'],
                       member_kinds=kinds, n_members=r['n_members'], allow_network=r['allow_network'],
                       command=(f'python -m science.anysite.solve --lat {r["lat"]} --lon {r["lon"]} '
                                f'--mast {r["mast_m"]:g}'))
        except LookupError as e:
            raise ApiError(422, (f'cannot solve offline: {e} (pass "allow_network": true to query JPL Horizons)'
                                 if 'Horizons' in str(e) else f'no terrain at this point: {e}'))
        except Exception as e:  # noqa: BLE001
            raise ApiError(500, f'solver error: {type(e).__name__}: {e}')
        h = b['anysite']['site_hash']
        self._index_put(key, h, self._public(r))
        p = self.bundle_path(h)
        src = 'solver-cache' if b['anysite'].get('cache_hit') else 'computed'
        if p is None:                    # solver wrote elsewhere (injected solver in tests): answer from the object
            return self._result_from(b, 'moon', h, b['anysite'].get('cache_hit', False), src, r['full'], None)
        return self.result(p, 'moon', h, bool(b['anysite'].get('cache_hit')), src, r['full'])

    def batch(self, body):
        if not isinstance(body, dict) or not isinstance(body.get('requests'), list) or not body['requests']:
            raise ApiError(400, 'body must be {"requests": [SolveRequest, ...]} with at least one request')
        if len(body['requests']) > 2000:
            raise ApiError(400, 'at most 2000 requests per batch')
        out = []
        for q in body['requests']:
            try:
                st, b = self.solve(q)
            except ApiError as e:
                st, b = e.status, e.body()
            out.append({'status': st, 'body': b})
        return 200, {'n': len(out), 'n_ok': sum(o['status'] == 200 for o in out), 'results': out}

    # ------------------------------------------------------------------------------------------- result
    def result(self, path, world, site_hash, hit, source, full=False):
        return self._result_from(C.read_json(path), world, site_hash, hit, source, full, path)

    def _result_from(self, b, world, site_hash, hit, source, full, path):
        m = b['metrics']; s = b['site']; a = b.get('anysite') or {}
        src = C.rel(path) if path else None
        metrics = {}
        for k, unit in METRIC_UNITS.items():
            if k in m and (m[k] is None or isinstance(m[k], (int, float))):
                metrics[k] = {'value': m[k], 'unit': unit, 'label': C.LABEL, 'json_path': f'metrics.{k}',
                              'read': C.read_cmd(path, f'metrics.{k}') if path else f'bundle metrics.{k}',
                              **({'source_file': src} if src else {})}
        unc = a.get('uncertainty')
        out = {
            'world': world, 'site_hash': site_hash, 'label': C.LABEL, 'disclaimer': C.GEOMETRY_ONLY,
            'cache': {'hit': bool(hit), 'source': source},
            'site': {'id': s.get('id'), 'name': s.get('name'), 'lat_deg': s['lat_deg'], 'lon_deg_east': s['lon_deg_east'],
                     'height_m': s.get('height_m'), 'observer_mast_m': s.get('observer_mast_m', 1.0)},
            'window': b.get('time'), 'members': _members_of(b), 'metrics': metrics,
            'uncertainty': unc,
            'solver_version': a.get('solver_version') or (b.get('generator') or {}).get('code'),
            'terrain': ({'near_product': (a.get('near_field') or {}).get('product_id'),
                         'far_product': (a.get('far_field') or {}).get('product_id'),
                         'n_truncated_bins': (b.get('skyline') or {}).get('n_truncated')} if a else None),
            'links': {'self': f'/v1/sites/{site_hash}', 'timeseries_json': f'/v1/sites/{site_hash}/timeseries.json',
                      'timeseries_csv': f'/v1/sites/{site_hash}/timeseries.csv'},
            'reproduce': {'recompute': (b.get('generator') or {}).get('command'),
                          **({'export': f'{C.PY} -m science.exports bundle {src}'} if src else {})},
            'note': C.K_OF_N,
        }
        if src:
            out['bundle_file'] = src
        if full:
            out['bundle'] = b
        return out


def C_time(iso):
    import datetime as dt
    return dt.datetime.fromisoformat(iso.replace('Z', '+00:00')).timestamp()
