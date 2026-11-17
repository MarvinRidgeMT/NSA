"""VISUAL sub-resolution relief (R2 plan §1-2): deterministic by tile id, seamless, amplitude set by LOLA 5-spot
roughness, and the HARD roughness check against LOLA's published spread and the real PGDA 78 5 m surface (the real
checks skip only when the pyramid / LOLA maps are not on disk)."""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from globe_fixtures import SP, write_raster  # noqa: E402

from science.terrain import stack as S  # noqa: E402
from tools.globe import pyramid as PY  # noqa: E402
from tools.globe import pyramid_products as PP  # noqa: E402
from tools.globe import roughness as RG  # noqa: E402


class FakeLola:
    """Constant LOLA parameters (no NASA data needed)."""

    def __init__(self, target=0.4, H=0.9):
        self.t, self.H = target, H

    def target(self, lat, lon):
        return np.full(np.shape(lat), self.t)

    def hurst(self, lat, lon):
        return np.full(np.shape(lat), self.H)


def test_value_noise_deterministic_unit_variance():
    rng = np.random.default_rng(0)
    u = rng.uniform(-1e5, 1e5, 200000); v = rng.uniform(-1e5, 1e5, 200000)
    a = RG.value_noise(u, v, 11)
    assert np.array_equal(a, RG.value_noise(u, v, 11))
    assert not np.allclose(a, RG.value_noise(u, v, 12))
    lat = RG.value_noise(np.floor(u), np.floor(v), 11)
    assert abs(lat.var() - 1.0) < 0.02


def test_value_noise3_deterministic_continuous_and_global():
    rng = np.random.default_rng(1)
    lat = rng.uniform(-90, 90, 50000); lon = rng.uniform(-180, 180, 50000)
    P = RG.sphere_points(lat, lon)
    a = RG.value_noise3(P, 40.0, RG.octave_seed(40.0))
    assert np.array_equal(a, RG.value_noise3(P, 40.0, RG.octave_seed(40.0)))
    assert 0.15 < a.var() < 0.8                                      # trilinear blend of unit-variance lattice values
    d = RG.value_noise3(P + 0.01, 40.0, RG.octave_seed(40.0)) - a     # 1 cm away: nearly identical (smooth field)
    assert np.abs(d).max() < 0.01
    # the same Moon-fixed point gives the same value whichever zone asks for it (lon wrap)
    P2 = RG.sphere_points(lat, lon + 360.0)
    assert np.allclose(RG.value_noise3(P2, 40.0, 7), RG.value_noise3(P, 40.0, 7), atol=1e-6)


def test_five_spot_estimator():
    rng = np.random.default_rng(2)
    # a plane has zero roughness
    x = np.array([0, 25, -25, 0, 0.0]); y = np.array([0, 0, 0, 25, -25.0])
    h = 3.0 + 0.1 * x - 0.05 * y
    assert RG.five_spot_sigma(*h) == pytest.approx(0.0, abs=1e-12)
    # unbiased for iid heights (SSR / (5 - 3)): E[sigma^2] = var
    hs = rng.normal(0, 2.0, (5, 400000))
    assert np.mean(RG.five_spot_sigma(*hs) ** 2) == pytest.approx(4.0, rel=0.01)
    # agrees with a generic least-squares plane fit
    A = np.stack([np.ones(5), x, y], 1)
    hh = rng.normal(size=5)
    r = hh - A @ np.linalg.lstsq(A, hh, rcond=None)[0]
    assert RG.five_spot_sigma(*hh) == pytest.approx(math.sqrt((r @ r) / 2.0), rel=1e-12)


def test_g_table_monotone():
    Hs, LL, G = RG.g_table()
    assert G.shape == (Hs.size, LL.size) and np.all(G[:, 0] == 0)       # lam_max = LAM_MIN: no octave allowed
    assert np.all(np.diff(G, axis=1) >= -0.01)                          # more octaves never lower the roughness
    assert np.all(G[:, -1] > 0.5)


@pytest.fixture(scope='module')
def mini_rough(tmp_path_factory):
    d = tmp_path_factory.mktemp('rough')
    rng = np.random.default_rng(5)
    cl, ct, cpx, n = -30000.0, 30000.0, 80.0, 750
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
    fake = FakeLola()
    p1 = RG.write_visual_tile(st, 'sp', L, 127, 127, root=vroot, params=fake)
    b1 = Path(p1).read_bytes()
    Path(p1).unlink()
    p2 = RG.write_visual_tile(st, 'sp', L, 127, 127, root=vroot, params=fake)
    assert Path(p2).read_bytes() == b1                       # same tile id -> same bytes
    RG.write_visual_tile(st, 'sp', L, 128, 127, root=vroot, params=fake)
    import rasterio
    with rasterio.open(vroot / 'sp' / str(L) / '127_127.tif') as a, rasterio.open(vroot / 'sp' / str(L) / '128_127.tif') as b:
        A = a.read(1).astype(float); B = b.read(1).astype(float)
        assert a.tags()['label'] == 'VISUAL' and a.tags()['seed'] == hex(RG.SEED)
    across = np.abs(B[:, 0] - A[:, -1])
    inside = np.abs(A[:, -1] - A[:, -2])
    assert np.nanmedian(across) < 2.0 * np.nanmedian(inside) + 1e-6


def _grid(lat0, lon0, q, n, pad):
    xs = (np.arange(-pad, n + pad) + 0.5) * q - n * q / 2
    X, Y = np.meshgrid(xs, -xs)
    return S.oblique_stereo_inverse(X, Y, lat0, lon0)


def test_visual_adds_relief_only_below_native_and_hits_target(mini_rough):
    st, _ = mini_rough
    pad, q, n = 16, 2.5, 1024
    lat, lon = _grid(-89.9, 30.0, q, n, pad)
    vis, base, noise, diag = RG.synthesize(st, lat, lon, q, zone='sp', pad=pad, params=FakeLola(0.4, 0.9))
    sl = (slice(pad, -pad), slice(pad, -pad))
    noise = noise[sl]
    assert max(diag['octaves_m']) <= 160.0 and min(diag['octaves_m']) == RG.LAM_MIN
    assert np.isfinite(noise).all() and noise.std() > 0
    # no power at wavelengths >= 2x native (160 m): block means over 320 m are ~0
    nb = noise[:1024, :1024].reshape(8, 128, 8, 128).mean(axis=(1, 3))
    assert nb.std() < 0.35 * noise.std()
    # displayed 5-spot roughness ~ the target (base adds a little in quadrature)
    got = float(np.median(RG.five_spot_shots(vis[sl], q)))
    assert got == pytest.approx(0.4, rel=0.12), got


def test_ldrm_label_geometry():
    try:
        P = RG.LolaRoughness()
    except FileNotFoundError:
        pytest.skip('LOLA LDRM not on disk')
    lbl = (P.dir / 'ldrm_32_50.lbl').read_text()
    for k, v in (('LINES', '5760'), ('LINE_SAMPLES', '11520'), ('SCALING_FACTOR', '0.001'),
                 ('MISSING_CONSTANT', '-32768'), ('LINE_PROJECTION_OFFSET', '2879.5'),
                 ('SAMPLE_PROJECTION_OFFSET', '5759.5'), ('WESTERNMOST_LONGITUDE', '0')):
        assert any(l.split('=')[0].strip() == k and l.split('=')[1].strip().split()[0] == v
                   for l in lbl.splitlines() if '=' in l), k
    q25, q50, q75 = (P.quantile(np.array([0.0, 30.0, -60.0]), np.array([10.0, -40.0, 120.0]), k) for k in ('25', '50', '75'))
    assert np.all((q25 <= q50) & (q50 <= q75)) and np.all((q50 > 0.05) & (q50 < 5.0))


def _real_ready():
    try:
        S.TerrainStack.open(); RG.LolaRoughness(); RG.PGDA70()
    except (FileNotFoundError, OSError):
        return False
    return any(s.source_id == 3 for s in PP.local_products())


@pytest.mark.skipif(not _real_ready(), reason='real pyramid / LOLA LDRM / PGDA 70 / PGDA 78 not on disk')
def test_roughness_check_hard():
    """HARD: every fixed window's displayed 5-spot roughness lies inside LOLA's published IQR; at the PGDA 78 sites the
    displayed / real 5 m RMS slope is within SLOPE_BAND at every baseline 15 m - 2.56 km, the Hurst exponent within
    0.1 of PGDA 70, the added relief at most RESIDUAL_GUARD x the real sub-80 m residual, and inside LOLA's IQR."""
    r = RG.run_check(write=False, log=lambda *a: None)
    assert len(r['pgda78_sites']) >= 4 and len(r['windows']) >= 12
    bad = [(s['product'], s['pass_slope_band'], s['pass_lola_spread'], s['pass_hurst_guard'], s['pass_residual_guard'])
           for s in r['pgda78_sites'] if not s['pass']]
    bad += [(w['name'], w.get('five_spot_median_m'), w.get('lola_spread')) for w in r['windows'] if not w['pass']]
    assert not bad, bad
    assert r['all_pass']


def test_rms_slope_of_a_plane():
    a = 0.1
    X, Y = np.meshgrid(np.arange(400) * 5.0, np.arange(400) * 5.0)
    prof = RG.rms_slope_profile(a * X, 5.0, baselines=(20.0, 80.0))
    for b, s in prof.items():
        assert s == pytest.approx(math.degrees(math.atan(a / math.sqrt(2))), abs=1e-9)


def test_median_abs_slope_and_deviogram_hurst():
    a = 0.05
    X, Y = np.meshgrid(np.arange(600) * 5.0, np.arange(600) * 5.0)
    Z = a * (X + Y)
    for b in (57.0, 225.0, 560.0):
        assert RG.median_abs_slope_deg(Z, 5.0, b) == pytest.approx(math.degrees(math.atan(a)), abs=1e-9)
    assert RG.deviogram_hurst(Z, 5.0) == pytest.approx(1.0, abs=1e-9)


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
    assert np.all((H > 0.0) & (H <= 1.0))
    for b in RG.PGDA70_BASELINES:
        m = p.median_abs_slope_deg(lat, lon, b)
        assert np.all((m > 0.0) & (m < 45.0))
    m57 = p.median_abs_slope_deg(lat, lon, 57.0); m560 = p.median_abs_slope_deg(lat, lon, 560.0)
    assert np.mean(m57) > np.mean(m560)
