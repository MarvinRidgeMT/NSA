"""One test per datum/frame conversion at ingest (contract §2, plan §3)."""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from globe_fixtures import EQC, LONLAT, NP, SP, grid_centres, plane, write_raster  # noqa: E402

from science import frames  # noqa: E402
from science.terrain import stack as S  # noqa: E402
from tools.globe import pyramid_products as PP  # noqa: E402


def test_dn_scale_offset_then_radius_to_height():
    # PDS LOLA LDEM: radius = DN * 0.5 + 1737400 (m); height = radius - 1737400
    dn = np.array([-200, 0, 100], dtype=np.int16)
    spec = PP.ProductSpec('t', 8, '/dev/null', 118.0, units='m', datum='radius', scale=0.5, offset=1737400.0)
    assert np.allclose(PP.convert_values(dn, spec), [-100.0, 0.0, 50.0])
    assert PP.dn_to_value(100, 0.5, 1737400) == 1737450.0
    assert PP.radius_to_height(1737450.0) == 50.0


def test_km_to_m():
    # SLDEM2015 / LOLA *_FLOAT.IMG store heights in km above 1737.4 km
    spec = PP.ProductSpec('t', 6, '/dev/null', 59.0, units='km')
    assert np.allclose(PP.convert_values(np.array([2.5, -1.234]), spec), [2500.0, -1234.0])


def test_rebase_other_sphere():
    # 100 m above a 1,738,000 m sphere is 700 m above the 1,737,400 m sphere
    assert PP.rebase_sphere(100.0, 1_738_000.0) == pytest.approx(700.0)
    spec = PP.ProductSpec('t', 4, '/dev/null', 10.0, ref_radius_m=1_737_150.0)
    assert PP.convert_values(np.array([0.0]), spec)[0] == pytest.approx(-250.0)


def test_unknown_units_or_datum_raise():
    with pytest.raises(ValueError):
        PP.convert_values(np.zeros(1), PP.ProductSpec('t', 8, '/dev/null', 1.0, units='ft'))
    with pytest.raises(ValueError):
        PP.convert_values(np.zeros(1), PP.ProductSpec('t', 8, '/dev/null', 1.0, datum='geoid'))


def test_lon_wrap():
    assert np.allclose(PP.wrap_lon_360([-10.0, 0.0, 359.0, 370.0]), [350.0, 0.0, 359.0, 10.0])
    assert np.allclose(PP.wrap_lon_180([350.0, 180.0, -190.0]), [-10.0, -180.0, 170.0])


def test_pa_to_me_rotation():
    lat = np.linspace(-89, 89, 37); lon = np.linspace(-180, 180, 73)
    La, Lo = np.meshgrid(lat, lon)
    la2, lo2 = PP.pa_to_me(La, Lo)
    back = PP.pa_to_me(la2, lo2, inverse=True)
    assert np.allclose(back[0], La, atol=1e-9)
    d = np.abs(((back[1] - Lo) + 180) % 360 - 180)
    assert d.max() < 1e-7
    # rotation angle = |(67.92, 78.56, 0.30)| arcsec ~= 103.9"; surface displacement <= R * angle ~= 875 m
    u1 = frames.unit(La, Lo); u2 = frames.unit(la2, lo2)
    ang = np.arccos(np.clip((u1 * u2).sum(-1), -1, 1))
    max_disp = float(ang.max() * PP.R)
    total = math.radians(math.sqrt(sum(a * a for a in PP.PA_TO_ME_ARCSEC)) / 3600) * PP.R
    assert 800 < max_disp <= total * 1.001
    assert abs(total - 875.6) < 2.0


def test_polar_closed_forms_match_pyproj():
    from pyproj import CRS, Transformer
    for z, proj in (('sp', SP), ('np', NP)):
        Z = S.ZONES[z]
        lat = np.linspace(-89.99, -55, 50) if z == 'sp' else np.linspace(55, 89.99, 50)
        lon = np.linspace(-179, 179, 50)
        La, Lo = np.meshgrid(lat, lon)
        x, y = Z.forward(La, Lo)
        t = Transformer.from_crs(CRS.from_proj4(proj).geodetic_crs, CRS.from_proj4(proj), always_xy=True)
        xp, yp = t.transform(Lo, La)
        assert np.abs(x - xp).max() < 1e-3 and np.abs(y - yp).max() < 1e-3
        la2, lo2 = Z.inverse(x, y)
        assert np.abs(la2 - La).max() < 1e-9
    xs, ys = S.ZONES['sp'].forward(-89.5, 30.0)
    assert np.allclose((xs, ys), frames.stereo_forward(-89.5, 30.0), atol=1e-9)


def test_classify_crs(tmp_path):
    from rasterio.crs import CRS

    class _C:
        def __init__(self, p):
            self._c = CRS.from_proj4(p)

        def to_wkt(self):
            return self._c.to_wkt()
    assert PP.classify_crs(_C(SP))[0] == 'sp'
    assert PP.classify_crs(_C(NP))[0] == 'np'
    assert PP.classify_crs(_C(LONLAT))[0] == 'lonlat'
    assert PP.classify_crs(_C(EQC))[0] == 'eqc'
    with pytest.raises(ValueError):
        PP.classify_crs(_C('+proj=longlat +datum=WGS84 +no_defs'))      # Earth datum must never pass silently


def test_reader_polar_exact_and_block_mean(tmp_path):
    left, top, px = 1000.0, 3000.0, 10.0
    X, Y = grid_centres(left, top, px, 200, 200)
    f = write_raster(tmp_path / 'p.tif', plane(X, Y), left, top, px, SP)
    rd = PP.ProductReader(PP.ProductSpec('p', 3, f, 10.0))
    lat, lon = S.ZONES['sp'].inverse(X[50:60, 50:60], Y[50:60, 50:60])
    h, q, res = rd.sample(lat, lon, 10.0)
    assert np.abs(h - plane(X[50:60, 50:60], Y[50:60, 50:60])).max() < 1e-3     # float32 storage
    assert (q == 2).all()
    # 20 m target: 2x2 block mean, centres of blocks aligned to the product grid
    Xb, Yb = grid_centres(left, top, 20.0, 100, 100)
    lat, lon = S.ZONES['sp'].inverse(Xb[10:20, 10:20], Yb[10:20, 10:20])
    h, q, _ = rd.sample(lat, lon, 20.0)
    assert np.abs(h - plane(Xb[10:20, 10:20], Yb[10:20, 10:20])).max() < 1e-3
    # outside -> NaN
    lat, lon = S.ZONES['sp'].inverse(np.array([-5000.0]), np.array([-5000.0]))
    assert np.isnan(rd.sample(lat, lon, 10.0)[0]).all()


def test_reader_int16_radius_product(tmp_path):
    left, top, px = -2000.0, 2000.0, 40.0
    dn = np.full((100, 100), 300, dtype=np.int16)     # radius = 300*0.5 + 1737400 -> h = 150 m
    f = write_raster(tmp_path / 'r.tif', dn, left, top, px, SP, dtype='int16', nodata=-32768, scale=0.5, offset=1737400.0)
    rd = PP.ProductReader(PP.ProductSpec('r', 7, f, 40.0, datum='radius'))
    lat, lon = S.ZONES['sp'].inverse(np.array([0.0, 100.0]), np.array([0.0, -300.0]))
    h, q, _ = rd.sample(lat, lon, 40.0)
    assert np.allclose(h, 150.0)


def test_reader_lonlat_0_360_wraps(tmp_path):
    # global 1 ppd lon/lat grid 0..360, value = lon (east, 0..360) -> sample at lon -10 must read column 350
    px = 1.0
    lon_c = np.arange(360) + 0.5; lat_c = 60 - (np.arange(120) + 0.5)
    Lo, La = np.meshgrid(lon_c, lat_c)
    f = write_raster(tmp_path / 'g.tif', Lo * 1.0, 0.0, 60.0, px, LONLAT)
    rd = PP.ProductReader(PP.ProductSpec('g', 8, f, PP.R * math.radians(1.0)))
    assert rd.lon360 and rd.global_lon
    h, _, _ = rd.sample(np.array([0.5, 0.5]), np.array([-9.5, 10.5]), 30000.0)
    assert np.allclose(h, [350.5, 10.5])
    # across the 0/360 seam the bilinear uses both edge columns
    h, _, _ = rd.sample(np.array([0.5]), np.array([0.0]), 30000.0)
    assert np.allclose(h, (359.5 + 0.5) / 2)


def test_reader_eqc_metres(tmp_path):
    # simple cylindrical in metres (GDAL's view of PDS SIMPLE CYLINDRICAL IMGs), lon -180..180, value = lat
    ppd = 4
    px = PP.R * math.radians(1.0 / ppd)
    nx, ny = 360 * ppd, 120 * ppd
    lat_c = 60 - (np.arange(ny) + 0.5) / ppd
    Z = np.repeat(lat_c[:, None], nx, axis=1)
    f = write_raster(tmp_path / 'e.tif', Z, -math.pi * PP.R, PP.R * math.radians(60), px, EQC)
    rd = PP.ProductReader(PP.ProductSpec('e', 6, f, px))
    assert rd.crs_kind == 'eqc' and rd.global_lon and not rd.lon360
    h, _, _ = rd.sample(np.array([10.125, -33.375]), np.array([45.0, -170.0]), px)
    assert np.allclose(h, [10.125, -33.375], atol=1e-4)


def test_reader_pds_style_eqc_lon0_180_rounded_scale(tmp_path):
    """GDAL's view of a LOLA LDEM_<ppd>_FLOAT.IMG: eqc with lon_0 = 180, x from -pi R to +pi R (= lon 0..360), pixel
    size from the label's rounded MAP_SCALE. Columns must follow lon exactly (360 / width deg per pixel)."""
    ppd = 4
    px_rounded = round(PP.R * math.radians(1.0 / ppd), 3)          # the label value, rounded like 236.901
    nx, ny = 360 * ppd, 180 * ppd
    lon_c = (np.arange(nx) + 0.5) / ppd                              # 0..360 east
    lat_c = 90 - (np.arange(ny) + 0.5) / ppd
    Lo, La = np.meshgrid(lon_c, lat_c)
    proj = '+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=180 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs'
    f = write_raster(tmp_path / 'pds.tif', Lo / 100.0, -nx / 2 * px_rounded, ny / 2 * px_rounded, px_rounded, proj)
    rd = PP.ProductReader(PP.ProductSpec('pds', 8, f, PP.R * math.radians(1.0 / ppd), units='km', scale=1.0, offset=0.0))
    assert rd.crs_kind == 'eqc' and rd.kind == 'lonlat' and rd.lon360 and rd.global_lon
    assert rd.px_x == 1.0 / ppd and rd.left == 0.0 and rd.top == 90.0
    lon = np.array([10.125, 359.875, -0.125, -179.875, 0.125])
    h, _, _ = rd.sample(np.zeros(5) + 0.125, lon, rd.native_px_m())
    assert np.allclose(h / 10.0, PP.wrap_lon_360(lon), atol=1e-5)     # value lon/100 km -> lon*10 m


def test_file_offset_overridden_by_spec():
    # GDAL reports OFFSET = 1737.4 (km) for LOLA LDEMs; the spec's explicit offset 0 must win (heights, not radii)
    spec = PP.ProductSpec('t', 7, '/dev/null', 5.0, units='km', scale=1.0, offset=0.0)
    assert PP.convert_values(np.array([1.25]), spec, file_scale=1.0, file_offset=1737.4)[0] == pytest.approx(1250.0)


def test_small_gap_fill_only():
    G = np.ones((20, 20)) * 5.0
    G[5, 5] = np.nan                 # 1 px hole -> filled
    G[10:15, 10:15] = np.nan         # 5x5 hole -> stays NaN
    out, filled = PP.fill_small_gaps(G, max_px=2)
    assert out[5, 5] == 5.0 and filled[5, 5]
    assert np.isnan(out[10:15, 10:15]).all() and not filled[10:15, 10:15].any()
