"""Grid arithmetic, merge/feather rules, co-registration recovery, and the full build -> TerrainStack chain on a
synthetic mini pyramid. Real-data checks (PGDA 90 / PGDA 78 on disk, built pyramid) skip cleanly when absent."""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from globe_fixtures import SP, grid_centres, plane, write_raster  # noqa: E402

from science import frames  # noqa: E402
from science.dem import ArrayDEM  # noqa: E402
from science.terrain import stack as S  # noqa: E402
from tools.globe import pyramid as PY  # noqa: E402
from tools.globe import pyramid_coreg as PC  # noqa: E402
from tools.globe import pyramid_products as PP  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
P90 = REPO / 'data' / 'external' / 'pgda90' / 'LDEM_80S_80MPP_ADJ.TIF'


# ------------------------------------------------------------------ geometry
def test_levels_and_tiles():
    sp, eq = S.ZONES['sp'], S.ZONES['eq']
    assert sp.pixel(0) == 1280.0 and sp.pixel(4) == 80.0 and sp.pixel(8) == 5.0
    assert sp.n_tiles(0) == (4, 4) and sp.n_tiles(8) == (1024, 1024)
    assert eq.n_tiles(0) == (24, 8) and eq.n_pixels(4) == (360 * 512, 120 * 512)
    assert abs(eq.pixel_m(4) - 59.225) < 0.01            # SLDEM2015 512 ppd
    assert sp.level_for_res(80.0) == 4 and sp.level_for_res(5.0) == 8 and sp.level_for_res(59.2) == 4
    assert eq.level_for_res(59.2) == 4 and eq.level_for_res(118.45) == 3
    # tiles tile the zone exactly
    l, b, r, t = sp.tile_bounds(3, 31, 31)
    assert r == sp.right and b == sp.bottom
    # PGDA 90 / 78 grids are pixel-aligned with their levels
    assert ((sp.left + 304000.0) / 80.0).is_integer() and ((sp.left + 19000.0) / 5.0).is_integer()


def test_zone_switch_and_coverage_extent():
    assert list(S.zone_name_for([-90, -57.5, -57.4, 0, 57.4, 57.5, 90])) == ['sp', 'sp', 'eq', 'eq', 'eq', 'np', 'np']
    sp = S.ZONES['sp']
    rho55 = 2 * S.R * math.tan(math.radians(35) / 2)
    assert rho55 < S.POLAR_HALF_M                           # the square covers the whole |lat| >= 55 cap
    assert sp.in_zone(-55.0) and not sp.in_zone(-54.99)


def test_oblique_stereo_roundtrip_and_scale():
    x, y = S.oblique_stereo_forward(10.3, 20.7, 10.0, 20.0)
    la, lo = S.oblique_stereo_inverse(x, y, 10.0, 20.0)
    assert abs(la - 10.3) < 1e-9 and abs(lo - 20.7) < 1e-9
    # 25 km along a meridian: projected distance = true arc * k, k - 1 ~ 5e-5
    d = 25000.0
    la2 = 10.0 + math.degrees(d / S.R)
    _, y2 = S.oblique_stereo_forward(la2, 20.0, 10.0, 20.0)
    assert abs(y2 / d - 1) < 1.1e-4


# ------------------------------------------------------------------ merge rules (synthetic sampler)
def _sampler(values):
    """values: {pid: (fn(lat, lon) -> h or NaN, native_m)}"""
    def f(spec, lat, lon, px_m):
        fn, native = values[spec.product_id]
        h = fn(lat, lon)
        q = np.where(np.isfinite(h), 2, 0).astype(np.uint8)
        return h, q, np.full(lat.shape, native), native
    return f


def _xy(lat, lon):
    return S.ZONES['sp'].forward(lat, lon)


def test_feather_continuity_and_priority():
    L, ix, iy = 4, 31, 31                      # tile with the pole at its lower-right corner, 80 m pixels
    hi = PP.ProductSpec('hi', 3, '-', 80.0)
    lo = PP.ProductSpec('lo', 8, '-', 80.0)
    left, _, right, top = S.ZONES['sp'].tile_bounds(L, ix, iy)
    xm = (left + right) / 2
    vals = {'hi': (lambda la, lo_: np.where(_xy(la, lo_)[0] < xm, 10.0, np.nan), 80.0),
            'lo': (lambda la, lo_: np.zeros(la.shape), 80.0)}
    arr, used = PY.merge_tile('sp', L, ix, iy, [lo, hi], sampler=_sampler(vals))
    H, SRC = arr[0], arr[1]
    row = H[256]
    assert np.isfinite(row).all()
    assert row[0] == pytest.approx(10.0) and row[-1] == pytest.approx(0.0)
    steps = np.abs(np.diff(row))
    assert steps.max() <= 10.0 / PY.FEATHER_PX + 1e-6        # the 10 m offset is spread over FEATHER_PX pixels
    assert set(np.unique(SRC)) == {3, 8}
    # priority: away from the edge the higher-priority product wins whatever the order given
    arr2, _ = PY.merge_tile('sp', L, ix, iy, [hi, lo], sampler=_sampler(vals))
    assert np.array_equal(arr, arr2, equal_nan=True)


def test_never_upsampled():
    L, ix, iy = 6, 127, 127                    # 20 m level
    coarse = PP.ProductSpec('c', 5, '-', 80.0)
    vals = {'c': (lambda la, lo_: np.zeros(la.shape), 80.0)}
    arr, _ = PY.merge_tile('sp', L, ix, iy, [coarse], sampler=_sampler(vals))
    assert arr is None                         # an 80 m product never produces a 20 m tile


def test_coarse_partner_only_inside_feather_band():
    L, ix, iy = 6, 127, 127                    # 20 m level, fine product covers the left half
    fine = PP.ProductSpec('f', 3, '-', 5.0)
    coarse = PP.ProductSpec('c', 5, '-', 80.0)
    left, _, right, _ = S.ZONES['sp'].tile_bounds(L, ix, iy)
    xm = (left + right) / 2
    vals = {'f': (lambda la, lo_: np.where(_xy(la, lo_)[0] < xm, 7.0, np.nan), 5.0),
            'c': (lambda la, lo_: np.zeros(la.shape), 80.0)}
    arr, _ = PY.merge_tile('sp', L, ix, iy, [fine, coarse], sampler=_sampler(vals))
    H, RES = arr[0], arr[2]
    row, res = H[256], RES[256]
    fin = np.isfinite(row)
    assert fin[:256].all() and not fin[256:].any()         # nothing beyond the fine product's edge
    band = fin & (row < 7.0 - 1e-9)
    assert 1 <= band.sum() <= PY.FEATHER_PX                # blend only within the feather band ...
    assert (res[band] == 80.0).all()                       # ... and labelled with the coarser native res
    assert (res[fin & ~band] == 5.0).all()


def test_polar_zone_masks_below_55():
    L = 0
    a = PP.ProductSpec('a', 8, '-', 1280.0)
    vals = {'a': (lambda la, lo_: np.zeros(la.shape), 1280.0)}
    arr, _ = PY.merge_tile('sp', L, 0, 0, [a], sampler=_sampler(vals))   # corner tile reaches lat ~ -48.7
    lat, _ = S.ZONES['sp'].inverse(*S.ZONES['sp'].pixel_centres(L, 0, 0))
    assert np.isnan(arr[0][lat > -55]).all() and np.isfinite(arr[0][lat <= -55]).all()


# ------------------------------------------------------------------ co-registration
def test_coreg_recovers_known_shift(tmp_path):
    # reference: smooth hills at 40 m; product: same surface at 10 m, shifted by (+30 m, -20 m) and +4 m
    def surf(x, y):
        return 300 * np.sin(x / 1500.0) * np.cos(y / 1100.0) + 0.02 * x
    ref_left, ref_top, rpx = -20000.0, 20000.0, 40.0
    X, Y = grid_centres(ref_left, ref_top, rpx, 1000, 1000)
    fr = write_raster(tmp_path / 'ref.tif', surf(X, Y), ref_left, ref_top, rpx, SP)
    dx, dy, dz = 30.0, -20.0, 4.0
    pl, pt, ppx = -8000.0, 8000.0, 10.0
    Xp, Yp = grid_centres(pl, pt, ppx, 1600, 1600)
    fp = write_raster(tmp_path / 'p.tif', surf(Xp - dx, Yp - dy) + dz, pl, pt, ppx, SP)
    ref = PP.ProductSpec('ref', 5, fr, 40.0)
    prod = PP.ProductSpec('prod', 4, fp, 10.0)
    r = PC.estimate(prod, ref)
    # corrected P'(x) = P(x + d) - dz  =>  d = (dx, dy)
    assert abs(r['dx'] - dx) < 4.0 and abs(r['dy'] - dy) < 4.0       # 0.1 reference px
    assert abs(r['dz'] - dz) < 0.5
    assert r['applied'] and r['nmad_after_m'] < r['nmad_before_m']
    # LOLA-family products are logged, never shifted
    r2 = PC.estimate(PP.ProductSpec('lola', 3, fp, 10.0), ref)
    assert r2['significant'] and not r2['applied'] and r2['flag']


# ------------------------------------------------------------------ full chain on a synthetic mini pyramid
@pytest.fixture(scope='module')
def mini(tmp_path_factory):
    d = tmp_path_factory.mktemp('mini')
    # coarse 80 m product: +-20 km around the south pole; fine 5 m product: 2 km square off the pole
    cl, ct, cpx, cn = -20000.0, 20000.0, 80.0, 500
    Xc, Yc = grid_centres(cl, ct, cpx, cn, cn)
    fc = write_raster(d / 'coarse.tif', plane(Xc, Yc), cl, ct, cpx, SP)
    fl, ft, fpx, fn = 1000.0, 3000.0, 5.0, 400
    Xf, Yf = grid_centres(fl, ft, fpx, fn, fn)
    ff = write_raster(d / 'fine.tif', plane(Xf, Yf) + 3.0, fl, ft, fpx, SP)
    specs = [PP.ProductSpec('fine5', 3, ff, 5.0), PP.ProductSpec('coarse80', 5, fc, 80.0)]
    root = d / 'pyramid'
    n = PY.build(zones=('sp',), max_level=8, workers=1, root=root, specs=specs, log=lambda *a: None)
    assert n > 0
    return root, specs


def test_mini_index_and_tiles(mini):
    root, _ = mini
    st = S.TerrainStack.open(root)
    assert st.levels('sp') == list(range(9))
    idx = st.index
    assert idx['bands'] == list(S.BANDS) and all(len(t['sha256']) == 64 for t in idx['tiles'])
    fine_levels = {t['level'] for t in idx['tiles'] if 3 in t['sources']}
    # a 2 km product dominates (feather weight >= 0.5) only where it spans >= 8 level pixels: 160 m and finer
    assert set(range(3, 9)) <= fine_levels
    coarse_only_levels = {t['level'] for t in idx['tiles'] if t['sources'] == [5]}
    assert max(coarse_only_levels) <= 4                    # 80 m never appears alone at 40 m or finer


def test_mini_sample_matches_products(mini):
    root, _ = mini
    st = S.TerrainStack.open(root)
    sp = S.ZONES['sp']
    # inside the fine product (away from its feather band): exact 5 m values (+3 offset)
    x = np.array([1500.0, 2002.5, 2700.0]); y = np.array([1500.0, 2002.5, 1200.0])
    lat, lon = sp.inverse(x, y)
    h, src, res = st.sample(lat, lon)
    assert np.allclose(h, plane(x, y) + 3.0, atol=1e-3)
    assert (src == 3).all() and np.allclose(res, 5.0, atol=1e-3)
    # coarse-only area: L4 bilinear of the 80 m plane is the plane itself
    x = np.array([-10000.0, 15000.0]); y = np.array([8000.0, -12000.0])
    lat, lon = sp.inverse(x, y)
    h, src, res = st.sample(lat, lon)
    assert np.allclose(h, plane(x, y), atol=1e-3) and (src == 5).all()
    c = st.coverage(lat, lon)
    assert (c['level'] == 4).all() and (c['zone'] == 'sp').all() and (c['quality'] == 2).all()
    # outside everything -> NaN, source 0
    h, src, _ = st.sample(np.array([-70.0, 10.0]), np.array([0.0, 0.0]))
    assert np.isnan(h).all() and (src == 0).all()


def test_mini_window(mini):
    root, _ = mini
    st = S.TerrainStack.open(root)
    lat0, lon0 = S.ZONES['sp'].inverse(2000.0, 2000.0)
    dem = st.window(float(lat0), float(lon0), 500.0)          # native step at the centre: 5 m
    assert isinstance(dem, ArrayDEM) and dem.step == 5.0 and dem.proj == 'sp'
    X, Y = grid_centres(dem.x_left, dem.y_top, dem.step, *dem.Z.shape)
    assert np.allclose(dem.Z, plane(X, Y) + 3.0, atol=1e-3)
    assert dem.meta['source_ids'] == [3] and dem.meta['label'].startswith('SOURCE-BASED')
    # 80 m window over the coarse area, aligned: equals the product pixels
    lat1, lon1 = S.ZONES['sp'].inverse(-10000.0, 8000.0)
    d80 = st.window(float(lat1), float(lon1), 4000.0, res_m=80.0)
    X, Y = grid_centres(d80.x_left, d80.y_top, 80.0, *d80.Z.shape)
    assert np.allclose(d80.Z, plane(X, Y), atol=1e-3)
    # 20 m request where only 80 m exists: NaN unless fill_coarser
    d20 = st.window(float(lat1), float(lon1), 1000.0, res_m=20.0)
    assert np.isnan(d20.Z).all()
    d20f = st.window(float(lat1), float(lon1), 1000.0, res_m=20.0, fill_coarser=True)
    assert np.isfinite(d20f.Z).all() and d20f.meta['filled_from_coarser_px'] == d20f.Z.size
    # sample_latlon round trip
    assert np.allclose(dem.sample_latlon(lat0, lon0), plane(2000.0, 2000.0) + 3.0, atol=1e-3)


# ------------------------------------------------------------------ real data (skips if absent)
@pytest.mark.skipif(not P90.exists(), reason='PGDA 90 LDEM_80S not on disk')
def test_real_pgda90_tile_is_bit_identical():
    import rasterio
    spec = [s for s in PP.local_products() if s.source_id == 5][0]
    # tile far from every PGDA 78 site: x, y in [163840, 204800]
    L, ix, iy = 4, 36, 27
    l, b, r, t = S.ZONES['sp'].tile_bounds(L, ix, iy)
    assert l >= 100000 and t <= 304000
    arr, used = PY.merge_tile('sp', L, ix, iy, [spec])
    with rasterio.open(spec.abspath) as ds:
        win = rasterio.windows.from_bounds(l, b, r, t, ds.transform)
        ref = ds.read(1, window=win)
    assert np.array_equal(arr[0], ref)
    assert (arr[1] == 5).all() and (arr[3] == 2).all()


def _real_stack():
    try:
        return S.TerrainStack.open()
    except FileNotFoundError:
        return None


@pytest.mark.skipif(_real_stack() is None, reason='real pyramid not built ($POLARIS_DATA/v2/pyramid)')
def test_real_stack_matches_existing_site_dems():
    st = _real_stack()
    from science import sites
    for sid in ('site04_roi3', 'site01_roi6'):
        s = sites.SITES[sid]
        near = sites.near_dem(sid)                       # cached PGDA 78 window (data/cache)
        la = s['lat'] + np.array([0.0, 0.003, -0.002]); lo = s['lon'] + np.array([0.0, 0.2, -0.3])
        x, y = frames.stereo_forward(la, lo)
        h, src, res = st.sample(la, lo)
        assert np.allclose(h, near.sample(x, y), atol=2e-3)
        assert (src == 3).all()
        far = sites.far_dem(sid)
        # 100-150 km away (beyond every PGDA 78 tile): only PGDA 90
        la2, lo2 = frames.destination(s['lat'], s['lon'], 45.0, np.array([100000.0, 150000.0]))
        x2, y2 = frames.stereo_forward(la2, lo2)
        h2, src2, _ = st.sample(la2, lo2)
        assert np.allclose(h2, far.sample(x2, y2), atol=2e-3) and (src2 == 5).all()
