"""VISUAL sub-resolution relief: deterministic by tile id, seamless across tiles, statistics as specified, and the
roughness check against the real PGDA 78 5 m surface (skips without the real pyramid)."""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from globe_fixtures import SP, grid_centres, write_raster  # noqa: E402

from science.terrain import stack as S  # noqa: E402
from tools.globe import pyramid as PY  # noqa: E402
from tools.globe import pyramid_products as PP  # noqa: E402
from tools.globe import roughness as RG  # noqa: E402


def test_value_noise_deterministic_unit_variance():
    rng = np.random.default_rng(0)
    u = rng.uniform(-1e5, 1e5, 200000); v = rng.uniform(-1e5, 1e5, 200000)
    a = RG.value_noise(u, v, 11); b = RG.value_noise(u, v, 11)
    assert np.array_equal(a, b)
    assert not np.allclose(a, RG.value_noise(u, v, 12))
    # lattice values have unit variance; the quintic blend of 4 iid values has variance E[sum w_i^2] ~ 0.5-0.6
    lat = RG.value_noise(np.floor(u), np.floor(v), 11)
    assert abs(lat.var() - 1.0) < 0.02
    assert 0.3 < a.var() < 0.8


def test_structure_function_calibration():
    assert RG.d1(1e-3) < RG.d1(0.1) < RG.d1(0.5)
    big = RG.d1(20.0)
    # saturates at 2 var(noise) (~1.2 for the blended field): flat beyond a few lattice spacings
    assert 0.6 < big < 1.6 and abs(RG.d1(30.0) - big) < 0.05 * big


def test_rms_slope_of_a_plane():
    a = 0.1
    X, Y = np.meshgrid(np.arange(400) * 5.0, np.arange(400) * 5.0)
    prof = RG.rms_slope_profile(a * X, 5.0, baselines=(20.0, 80.0))
    # pooled over both axes: half the differences are a*D, half 0 -> RMS = a D / sqrt 2
    for b, s in prof.items():
        assert s == pytest.approx(math.degrees(math.atan(a / math.sqrt(2))), abs=1e-9)


def test_fit_params_recovers_hurst_of_synthetic_fbm():
    # 2D spectral fBm with H = 0.7 at 80 m posting: the self-fit at lags 2-8 px should land near 0.7
    rng = np.random.default_rng(3)
    n = 512
    kx = np.fft.fftfreq(n); ky = np.fft.fftfreq(n)
    K = np.hypot(*np.meshgrid(kx, ky)); K[0, 0] = np.inf
    H = 0.7
    amp = K ** (-(H + 1.0))
    Z = np.real(np.fft.ifft2(amp * np.exp(2j * np.pi * rng.uniform(size=(n, n)))))
    Hf, nu0, s1 = RG.fit_params(Z, 80.0, cell_px=128)
    assert abs(np.median(Hf) - H) < 0.12


@pytest.fixture(scope='module')
def mini_rough(tmp_path_factory):
    d = tmp_path_factory.mktemp('rough')
    rng = np.random.default_rng(5)
    cl, ct, cpx, cn = -30000.0, 30000.0, 80.0, 750
    n = cn
    K = np.hypot(*np.meshgrid(np.fft.fftfreq(n), np.fft.fftfreq(n))); K[0, 0] = np.inf
    Z = np.real(np.fft.ifft2(K ** (-1.8) * np.exp(2j * np.pi * rng.uniform(size=(n, n)))))
    Z = 200.0 * Z / Z.std()
    f = write_raster(d / 'c.tif', Z, cl, ct, cpx, SP)
    root = d / 'v2' / 'pyramid'
    PY.build(zones=('sp',), max_level=4, workers=1, root=root, specs=[PP.ProductSpec('c', 5, f, 80.0)],
             log=lambda *a: None)
    return S.TerrainStack.open(root), d


def test_visual_tile_deterministic_and_seamless(mini_rough):
    st, d = mini_rough
    vroot = d / 'v2' / 'pyramid_visual'
    L = 6                                         # 20 m VISUAL over 80 m data
    p1 = RG.write_visual_tile(st, 'sp', L, 127, 127, base_level=4, root=vroot)
    b1 = Path(p1).read_bytes()
    p2 = RG.write_visual_tile(st, 'sp', L, 127, 127, base_level=4, root=vroot)
    assert Path(p2).read_bytes() == b1                       # same tile id -> same bytes
    RG.write_visual_tile(st, 'sp', L, 128, 127, base_level=4, root=vroot)
    import rasterio
    with rasterio.open(vroot / 'sp' / str(L) / '127_127.tif') as a, rasterio.open(vroot / 'sp' / str(L) / '128_127.tif') as b:
        A = a.read(1).astype(float); B = b.read(1).astype(float)
        assert a.tags()['label'] == 'VISUAL'
    across = np.abs(B[:, 0] - A[:, -1])                       # neighbouring pixels across the tile edge
    inside = np.abs(A[:, -1] - A[:, -2])
    assert np.nanmedian(across) < 2.0 * np.nanmedian(inside) + 1e-6


def test_visual_adds_relief_only_below_native(mini_rough):
    st, _ = mini_rough
    Z = S.ZONES['sp']
    l, b, r, t = Z.tile_bounds(6, 127, 127)
    vis, base, noise, diag = RG.visual_grid(st, 'sp', l, t, 20.0, 256, 256, base_level=4)
    assert diag['params_source'] == 'self-fit' and max(diag['octaves_m']) <= 320.0
    assert np.isfinite(noise).all() and noise.std() > 0
    # the noise has no power at wavelengths >= 2x native (160 m): block means over 320 m are ~0
    nb = noise[:256, :256].reshape(16, 16, 16, 16).mean(axis=(1, 3))
    assert nb.std() < 0.35 * noise.std()


REAL = (Path(__file__).resolve().parents[3] / 'data' / 'external' / 'pgda90' / 'LDEM_80S_80MPP_ADJ.TIF').exists()


def _real_stack():
    try:
        return S.TerrainStack.open()
    except FileNotFoundError:
        return None


@pytest.mark.skipif(_real_stack() is None or not REAL, reason='real pyramid not built')
def test_roughness_check_against_real_5m():
    r = RG.run_check(write=False, log=lambda *a: None)
    assert r['sites'], 'no PGDA 78 site to check against'
    for s in r['sites']:
        # plan §9 criterion: displayed / real RMS slope within the band at every baseline 15 m .. 2.56 km
        assert s['pass'], [(row['baseline_m'], row['ratio_visual']) for row in s['rows']]
        # VISUAL really adds sub-resolution relief (bilinear alone is too smooth below 2x the 80 m post)
        assert s['sub_resolution_mean_ratio_visual'] > s['sub_resolution_mean_ratio_bilinear']
        # known open item (reported, not hidden): the added component is 1.2-2x the PGDA 78 residual; fail loudly if
        # a change makes it much worse
        assert s['sub_resolution_mean_ratio_residual'] < 2.5, s['sub_resolution_mean_ratio_residual']


def test_median_abs_slope_and_deviogram_hurst():
    a = 0.05
    X, Y = np.meshgrid(np.arange(600) * 5.0, np.arange(600) * 5.0)
    Z = a * (X + Y)
    for b in (57.0, 225.0, 560.0):
        assert RG.median_abs_slope_deg(Z, 5.0, b) == pytest.approx(math.degrees(math.atan(a)), abs=1e-9)
    assert RG.deviogram_hurst(Z, 5.0) == pytest.approx(1.0, abs=1e-9)        # a plane is self-affine with H = 1


def _pgda70():
    try:
        return RG.PGDA70()
    except FileNotFoundError:
        return None


@pytest.mark.skipif(_pgda70() is None, reason='PGDA 70 not on disk')
def test_pgda70_decoding():
    p = _pgda70()
    lat = np.array([0.0, 30.0, -89.5, 5.4]); lon = np.array([10.0, -15.0, -150.0, -158.6])
    H = p.hurst(lat, lon)
    assert np.all((H > 0.0) & (H <= 1.0))                          # label: 0..1 mapped to -20000..20000
    for b in RG.PGDA70_BASELINES:
        m = p.median_abs_slope_deg(lat, lon, b)
        assert np.all((m > 0.0) & (m < 45.0))
    # slopes decrease with baseline on average (self-affine, H < 1)
    m57 = p.median_abs_slope_deg(lat, lon, 57.0); m560 = p.median_abs_slope_deg(lat, lon, 560.0)
    assert np.mean(m57) > np.mean(m560)
