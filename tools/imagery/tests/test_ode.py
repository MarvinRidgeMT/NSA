import json
import urllib.parse
from pathlib import Path

import pytest

from tools.imagery import ode
from tools.imagery import geometry as geo
from tools.imagery.http_cache import PoliteCache, canonical_url

FIX = Path(__file__).parent / 'fixtures'


def _products(name):
    p = json.loads((FIX / name).read_text())['ODEResults']['Products']['Product']
    return p if isinstance(p, list) else [p]


class FakeODE:
    """Serves count and pages from a list of product dicts; records calls."""
    def __init__(self, products, short_page_at=None):
        self.products, self.calls, self.short = products, [], short_page_at

    def __call__(self, url, timeout):
        self.calls.append(url)
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
        if q['results'] == 'c':
            return json.dumps({'ODEResults': {'Count': str(len(self.products)), 'Status': 'Success'}}).encode()
        off, lim = int(q['offset']), int(q['limit'])
        page = self.products[off:off + lim]
        if self.short is not None and off >= self.short:
            page = []
        prods = {'Product': page} if page else 'No Products Found'
        return json.dumps({'ODEResults': {'Products': prods, 'Status': 'Success'}}).encode()


def _cache(tmp_path, transport):
    t = [0.0]
    sleeps = []
    def clock():
        return t[0]
    def sleep(s):
        sleeps.append(s); t[0] += s
    c = PoliteCache(tmp_path, min_interval_s=2.0, transport=transport, sleep=sleep, clock=clock)
    return c, sleeps


def test_pagination_reaches_count_and_is_rate_limited(tmp_path):
    prods = _products('ode_nac_page.json') + _products('ode_wac_page.json') + _products('ode_tc_page.json')
    fake = FakeODE(prods)
    c, sleeps = _cache(tmp_path, fake)
    params = ode.base_params('LROC_NAC', -89.9, -89.5, 190, 220)
    out, src = ode.fetch_all(c, params, limit=2)
    assert len(out) == len(prods)
    assert len(fake.calls) == 1 + 4  # count + 3 full pages of 2 + the empty page that ends paging
    assert all(s == pytest.approx(2.0) for s in sleeps) and len(sleeps) == 4
    assert all(len(s['sha256']) == 64 for s in src)
    # second run: all cached, no network
    fake2 = FakeODE(prods)
    c2, _ = _cache(tmp_path, fake2)
    out2, _ = ode.fetch_all(c2, params, limit=2)
    assert fake2.calls == [] and len(out2) == len(prods) and c2.cache_hits == 5
    man = (tmp_path / 'MANIFEST.jsonl').read_text().splitlines()
    assert len(man) == 5 and all('sha256' in json.loads(l) for l in man)


def test_short_page_raises(tmp_path):
    prods = _products('ode_nac_page.json') * 3
    c, _ = _cache(tmp_path, FakeODE(prods, short_page_at=2))
    with pytest.raises(ode.ODEError):
        ode.fetch_all(c, ode.base_params('LROC_NAC', -90, -89, 0, 360), limit=2)


def test_page_boundary_duplicate_is_dropped_but_a_skip_raises(tmp_path):
    prods = _products('ode_nac_page.json') + _products('ode_wac_page.json')  # 4 unique
    class Dup(FakeODE):
        def __call__(self, url, timeout):
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
            if q['results'] == 'c':
                return json.dumps({'ODEResults': {'Count': '4', 'Status': 'Success'}}).encode()
            off = int(q['offset'])
            pages = {0: [self.products[0], self.products[1]], 2: [self.products[1], self.products[2]],
                     4: [self.products[3]]}
            return json.dumps({'ODEResults': {'Products': {'Product': pages[off]}, 'Status': 'Success'}}).encode()
    c, _ = _cache(tmp_path / 'a', Dup(prods))
    out, src = ode.fetch_all(c, ode.base_params('LROC_NAC', -90, -89, 0, 360), limit=2)
    assert len(out) == 4 and src[0]['duplicates_dropped'] == 1

    class Skip(Dup):
        def __call__(self, url, timeout):
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
            if q['results'] == 'c':
                return json.dumps({'ODEResults': {'Count': '4', 'Status': 'Success'}}).encode()
            off = int(q['offset'])
            pages = {0: [self.products[0], self.products[1]], 2: [self.products[1], self.products[1]], 4: []}
            pr = {'Product': pages[off]} if pages[off] else 'No Products Found'
            return json.dumps({'ODEResults': {'Products': pr, 'Status': 'Success'}}).encode()
    c, _ = _cache(tmp_path / 'b', Skip(prods))
    with pytest.raises(ode.ODEError):
        ode.fetch_all(c, ode.base_params('LROC_NAC', -90, -89, 0, 360), limit=2)


def test_error_status_raises(tmp_path):
    def bad(url, timeout):
        return json.dumps({'ODEResults': {'Status': 'ERROR', 'Error': 'bad ihid'}}).encode()
    c, _ = _cache(tmp_path, bad)
    with pytest.raises(ode.ODEError):
        ode.count(c, ode.base_params('LROC_NAC', -90, -89, 0, 360))


def test_canonical_url_is_order_independent():
    a = canonical_url(ode.ODE_BASE, {'b': 1, 'a': 2})
    b = canonical_url(ode.ODE_BASE, {'a': 2, 'b': 1})
    assert a == b and a.endswith('?a=2&b=1')


def test_parse_products_each_instrument():
    nac = ode.parse_product(_products('ode_nac_page.json')[0], 'LROC_NAC')
    assert nac['product_id'] == 'M101350392LC' and nac['ode_pt'] == 'CDRNAC4'
    assert nac['emission_deg'] == pytest.approx(1.69) and nac['incidence_deg'] == pytest.approx(90.46)
    assert nac['pixel_scale_m'] == pytest.approx(0.904) and nac['pixel_scale_source'] == 'ODE Map_resolution'
    assert nac['obs_utc'] == '2009-07-04T12:39:00.489Z'
    assert nac['label_url'].endswith('M101350392LC.xml') and nac['data_file_url'].endswith('.IMG')
    sc = ode.parse_product(_products('ode_shadowcam_page.json')[0], 'ShadowCam')
    assert sc['product_id'] == 'M013371158SC' and sc['pixel_scale_m'] == pytest.approx(1.7709)
    assert sc['pixel_scale_source'] == 'ODE Map_scale'
    tc = ode.parse_product(_products('ode_tc_page.json')[0], 'Kaguya_TC_stereo')
    assert tc['product_id'] == 'TC1W2B0_01_00366S891E1767'
    assert tc['pixel_scale_m'] == 10.0 and 'nominal' in tc['pixel_scale_source']
    assert tc['data_file_url'].lower().endswith('.img.gz')
    wac = ode.parse_product(_products('ode_wac_page.json')[0], 'LROC_WAC')
    assert wac['product_id'] == 'M101013765CC' and wac['pixel_scale_m'] == pytest.approx(64.415)


def test_site_filter_exact_overlap():
    row = ode.parse_product(_products('ode_shadowcam_page.json')[0], 'ShadowCam')
    # A site square placed on the footprint's first SP vertex overlaps; one 300 km away does not.
    polys = geo.parse_wkt_polygons(row['sp_wkt'])
    x0, y0 = polys[0][0][0]
    lat, lon = geo.stereo_inverse(x0, y0)
    from tools.imagery import sites
    sites.SITES['_test_on'] = {'name': 't', 'lat': lat, 'lon': lon, 'terrain': 'test'}
    sites.SITES['_test_off'] = {'name': 't', 'lat': -80.0, 'lon': 0.0, 'terrain': 'test'}
    try:
        on = ode.site_filter(row, '_test_on')
        off = ode.site_filter(row, '_test_off')
    finally:
        del sites.SITES['_test_on'], sites.SITES['_test_off']
    assert on is not None and 0 < on['overlap_frac'] <= 1 and 'sp_wkt' not in on
    assert off is None


def test_nac_footprint_suspect_flag():
    # The first commissioning NAC frame's index-table footprint spans ~-89 to the pole.
    row = ode.parse_product(_products('ode_nac_page.json')[0], 'LROC_NAC')
    polys = geo.parse_wkt_polygons(row['sp_wkt'])
    area = sum(geo.polygon_area(p) for p in polys)
    nominal = ode.NAC_SAMPLES * ode.NAC_MAX_LINES * row['pixel_scale_m'] ** 2
    x, y = polys[0][0][0]
    lat, lon = geo.stereo_inverse(x * 0.5, y * 0.5)
    from tools.imagery import sites
    sites.SITES['_t'] = {'name': 't', 'lat': lat, 'lon': lon, 'terrain': 'test'}
    try:
        r = ode.site_filter(row, '_t')
    finally:
        del sites.SITES['_t']
    if r is not None:
        assert r['footprint_suspect'] == (area > 4 * nominal)
