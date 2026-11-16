import json
import math
from pathlib import Path

import pytest

from tools.imagery import geometry as geo
from tools.imagery.sites import SITES

FIX = Path(__file__).parent / 'fixtures'


def _prod(name, k=0):
    p = json.loads((FIX / name).read_text())['ODEResults']['Products']['Product']
    return (p if isinstance(p, list) else [p])[k]


def test_wkt_polygon_multipolygon_collection():
    assert geo.parse_wkt_polygons('MULTIPOLYGON EMPTY') == []
    assert geo.parse_wkt_polygons('') == []
    p = geo.parse_wkt_polygons('POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))')
    assert p == [[[(0, 0), (1, 0), (1, 1), (0, 1)]]]
    m = geo.parse_wkt_polygons('MULTIPOLYGON (((0 0, 1 0, 1 1, 0 0)), ((5 5, 6 5, 6 6, 5 5)))')
    assert len(m) == 2 and m[1][0][0] == (5, 5)
    g = geo.parse_wkt_polygons('GEOMETRYCOLLECTION (POLYGON EMPTY, POLYGON ((0 0, 2 0, 2 2, 0 0)), '
                               'LINESTRING (0 0, 1 1), POLYGON ((0 0, 4 0, 4 4, 0 4, 0 0), (1 1, 2 1, 2 2, 1 2, 1 1)))')
    assert len(g) == 2 and len(g[1]) == 2
    assert geo.polygon_area(g[1]) == pytest.approx(15.0)
    e = geo.parse_wkt_polygons('POLYGON ((1.5e3 -2E-1, 3 4, -5 6, 1.5e3 -2E-1))')
    assert e[0][0][0] == (1500.0, -0.2)


def test_real_ode_sp_footprints_parse():
    for name in ('ode_nac_page.json', 'ode_wac_page.json', 'ode_shadowcam_page.json', 'ode_tc_page.json'):
        polys = geo.parse_wkt_polygons(_prod(name)['Footprint_SP_geometry'])
        assert polys and all(len(p[0]) >= 3 for p in polys), name
        assert sum(geo.polygon_area(p) for p in polys) > 1e5, name


def test_ode_sp_frame_matches_science_frames():
    """ODE Footprint_SP_geometry uses x = rho sin(lon), y = rho cos(lon), R = 1737.4 km.
    The TC fixture's GL vertex (162.3202 E, -88.3242) appears as an SP vertex."""
    p = _prod('ode_tc_page.json')
    sp = geo.parse_wkt_polygons(p['Footprint_SP_geometry'])[0][0]
    x, y = geo.stereo_forward(-88.3242, 162.3202)
    d = min(math.hypot(x - a, y - b) for a, b in sp)
    assert d < 2.0, d
    from science import frames
    fx, fy = frames.stereo_forward(-88.3242, 162.3202)
    assert abs(float(fx) - x) < 1e-6 and abs(float(fy) - y) < 1e-6
    # and every GL vertex has an SP counterpart
    gl = geo.parse_wkt_polygons(p['Footprint_GL_geometry'])[0][0]
    for lon, lat in gl:
        X, Y = geo.stereo_forward(lat, lon)
        assert min(math.hypot(X - a, Y - b) for a, b in sp) < 2.0


def test_stereo_roundtrip():
    for lat, lon in ((-89.78012, -156.32023), (-88.70606, -68.52994), (-85.0, 359.9)):
        la, lo = geo.stereo_inverse(*geo.stereo_forward(lat, lon))
        assert la == pytest.approx(lat, abs=1e-9)
        assert (lo - lon) % 360 == pytest.approx(0, abs=1e-9) or (lo - lon) % 360 == pytest.approx(360, abs=1e-9)


def test_clip_areas():
    sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert abs(geo.ring_area(geo.clip_ring_to_rect(sq, 5, 5, 20, 20))) == pytest.approx(25)
    assert geo.clip_ring_to_rect(sq, 20, 20, 30, 30) == []
    tri = [(0, 0), (10, 0), (0, 10)]
    assert abs(geo.ring_area(geo.clip_ring_to_rect(tri, 0, 0, 5, 5))) == pytest.approx(25 - 0)  # square fully under hypotenuse
    assert abs(geo.ring_area(geo.clip_ring_to_rect(tri, 0, 0, 10, 10))) == pytest.approx(50)
    L = [(0, 0), (10, 0), (10, 2), (2, 2), (2, 10), (0, 10)]  # concave, area 36
    assert abs(geo.ring_area(L)) == pytest.approx(36)
    assert abs(geo.ring_area(geo.clip_ring_to_rect(L, 1, 1, 9, 9))) == pytest.approx(8 + 7)  # 8x1 strip + 1x7 strip
    poly = [[sq, [(4, 4), (6, 4), (6, 6), (4, 6)]]]
    assert geo.overlap_area_rect(poly, 0, 0, 10, 10) == pytest.approx(96)
    assert geo.point_in_polys(1, 1, poly) and not geo.point_in_polys(5, 5, poly)


def test_envelope_contains_square_and_cases():
    for sid, s in SITES.items():
        rect, (cx, cy) = geo.site_square(s['lat'], s['lon'], 5000)
        minlat, maxlat, lons = geo.square_envelope(rect)
        for k in range(41):
            for m in range(41):
                la, lo = geo.stereo_inverse(rect[0] + k * 250, rect[1] + m * 250)
                assert minlat <= la <= maxlat, sid
                assert any(w <= lo <= e for w, e in lons), (sid, lo, lons)
    # pole inside
    minlat, maxlat, lons = geo.square_envelope((-1000, -1000, 1000, 1000))
    assert minlat == -90.0 and lons == [(0.0, 360.0)]
    # straddling the 0/360 meridian (y axis = lon 0 direction) gives two ranges
    x, y = geo.stereo_forward(-88.0, 0.0)
    _, _, lons = geo.square_envelope((x - 3000, y - 3000, x + 3000, y + 3000))
    assert len(lons) == 2 and lons[0][1] == 360.0 and lons[1][0] == 0.0
