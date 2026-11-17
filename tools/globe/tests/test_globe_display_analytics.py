"""R2 display formats and analytics: quantized-mesh codec, horizon geometry, visibility fractions, Horizons geometry.
Synthetic tests need no NASA data; the real-data checks skip when the cached products are absent."""
import json
import math

import numpy as np
import pytest

from tools.globe import ephem as EP
from tools.globe import qmesh as QM
from tools.globe import visibility as VI


# ------------------------------------------------------------------------------------------ quantized mesh
def _synthetic_tile(z=3, x=5, y=2):
    w, s, e, n = QM.tile_rect(z, x, y)
    d = (e - w) / (QM.N - 1)
    lon = w + np.arange(-1, QM.N + 1) * d
    lat = s + np.arange(-1, QM.N + 1) * ((n - s) / (QM.N - 1))
    LA, LO = np.meshgrid(lat, lon, indexing='ij')
    H = 1500.0 * np.sin(np.radians(LA) * 7) * np.cos(np.radians(LO) * 5) - 300.0
    return LA, LO, H, (w, s, e, n)


def test_qmesh_round_trip_and_topology():
    LA, LO, H, rect = _synthetic_tile()
    raw = QM.encode(LA, LO, H, rect)
    t = QM.decode(raw)
    g = np.full(QM.N * QM.N, np.nan); g[QM.ORDER] = t['h_m']
    ref = H[1:-1, 1:-1].ravel()
    step = (ref.max() - ref.min()) / 32767
    assert np.abs(g - ref).max() <= 0.51 * step + 1e-9                  # 16-bit quantisation only
    assert t['hmin'] == pytest.approx(ref.min(), abs=1e-3) and t['hmax'] == pytest.approx(ref.max(), abs=1e-3)
    tris = t['tris']
    assert tris.shape == (2 * (QM.N - 1) ** 2, 3) and tris.max() == QM.N * QM.N - 1
    # counter-clockwise in (u east, v north), as Cesium expects
    u, v = t['u'].astype(float), t['v'].astype(float)
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    cross = (u[b] - u[a]) * (v[c] - v[a]) - (v[b] - v[a]) * (u[c] - u[a])
    assert np.all(cross > 0)
    # edges: west u = 0, south v = 0, east u = 32767, north v = 32767, N vertices each
    for k, (arr, val) in enumerate(((u, 0), (v, 0), (u, 32767), (v, 32767))):
        assert t['edges'][k].size == QM.N and np.all(arr[t['edges'][k]] == val)
    # normals: unit, close to the radial direction for gentle relief
    assert t['normals'] is not None and np.allclose(np.linalg.norm(t['normals'], axis=1), 1, atol=1e-6)


def test_qmesh_codecs():
    rng = np.random.default_rng(0)
    v = rng.integers(-32767, 32767, 1000)
    assert np.array_equal(QM.unzigzag(QM.zigzag(v).astype(np.int64)), v)
    assert np.array_equal(QM.hwm_decode(QM.hwm_encode(QM.TRIS)), QM.TRIS)
    n = rng.normal(size=(2000, 3)); n /= np.linalg.norm(n, axis=1, keepdims=True)
    back = QM.oct_decode(QM.oct_encode(n))
    assert np.degrees(np.arccos(np.clip((n * back).sum(1), -1, 1))).max() < 1.0


def test_qmesh_occlusion_point_and_tiling():
    LA, LO, H, rect = _synthetic_tile(5, 20, 10)
    P = QM.ecef(LA, LO, H).reshape(-1, 3)
    hop = QM.occlusion_point(P, P.mean(0))
    assert np.linalg.norm(hop) >= QM.R                                   # outside the sphere
    assert QM.tile_rect(0, 0, 0) == (-180.0, -90.0, 0.0, 90.0)
    assert len(QM.tiles_at(2)) == 32
    pol = QM.tiles_at(4, polar_only=True)
    assert pol and all(QM.tile_rect(4, x, y)[3] > 80 or QM.tile_rect(4, x, y)[1] < -80 for x, y in pol)


def test_qmesh_built_tiles_if_present():
    man = QM.OUT / 'manifest.json'
    if not man.exists():
        pytest.skip('display terrain not built in this tree')
    m = json.loads(man.read_text())
    assert m['label'].startswith('SOURCE-BASED') and 'no VISUAL' in m['label']
    layer = json.loads((QM.OUT / 'layer.json').read_text())
    assert layer['format'] == 'quantized-mesh-1.0' and layer['scheme'] == 'tms'
    f = next((QM.OUT / '0' / '0').glob('*.terrain'))
    t = QM.decode(f.read_bytes())
    assert -10000 < t['hmin'] < t['hmax'] < 11000


# ------------------------------------------------------------------------------------------ horizon / visibility
class _Flat:
    def sample(self, lat, lon, near=False):
        return np.zeros(np.shape(lat))


class _Wall:
    """A ring wall of height H at angular distance g0 from the north pole (else 0)."""

    def __init__(self, g0_m, H):
        self.lat0 = 90.0 - math.degrees(g0_m / VI.R); self.H = H

    def sample(self, lat, lon, near=False):
        return np.where(np.abs(lat - self.lat0) < 0.02, self.H, 0.0)


def test_horizon_flat_sphere_and_wall():
    lat = np.array([90.0 - 1e-9]); lon = np.array([0.0]); h0 = np.array([0.0])
    az = np.array([[0.0, 90.0, 200.0]])
    d = VI.distances(80.0, 320.0)
    hz = VI.horizon(_Flat(), lat, lon, h0, az, d)
    # flat sphere: the terrain falls away; the highest point is the nearest sample, el = -g/2
    assert np.all(hz < 0) and np.allclose(hz, -math.degrees(d[0] / VI.R) / 2, atol=1e-6)
    g0, H = 30_000.0, 2000.0
    hz = VI.horizon(_Wall(g0, H), lat, lon, h0, az, d)
    g = g0 / VI.R
    expect = math.degrees(math.atan2((VI.R + H) * math.cos(g) - VI.R, (VI.R + H) * math.sin(g)))
    assert np.allclose(hz, expect, atol=0.08)                           # wall sampled within its +-0.02 deg band


def _toy_samples(n=2000):
    # sub-point uniformly in latitude +-6 deg, longitude 0 (Earth) at 384,400 km
    la = np.linspace(-6, 6, n); lo = np.zeros(n)
    return EP.unit(la, lo), np.full(n, 384_400e3), np.full(n, 1.0 / n)


def test_visibility_fraction_flat_sphere():
    smp = _toy_samples()
    lat = np.array([0.0, 0.0, 0.0, -89.0]); lon = np.array([0.0, 180.0, 90.0, 0.0]); h0 = np.zeros(4)
    d = VI.distances(1900.0, 1900.0, ratio=1.05)
    a, c, _ = VI.fraction_window(_Flat(), lat, lon, h0, 'earth', d, n_az=8, samples=smp)
    assert a[0] == pytest.approx(1.0) and a[1] == pytest.approx(0.0)
    # at the limb (lon 90 E, sub-Earth longitude always 0): Earth centre at el ~ -parallax, half the disc above
    assert a[2] == pytest.approx(1.0) and c[2] == pytest.approx(0.0)
    # at (89 S, 0 E) the Earth centre's elevation is 1 deg - sub-Earth latitude - parallax (0.26 deg): the centre is
    # up while the sub-Earth latitude < ~0.74 deg, i.e. (6 + 0.74) / 12 of the uniform -6..6 samples
    assert c[3] == pytest.approx(6.74 / 12, abs=0.02) and a[3] > c[3]


def test_ephemeris_cached_matches_horizons_site_azel():
    try:
        g = EP.geometry()
    except FileNotFoundError:
        pytest.skip('Horizons geometry not cached (python -m tools.globe.ephem fetch)')
    assert g['unix'].size > 50000 and (g['unix'][-1] - g['unix'][0]) / 86400 / 365.25 > 18.5
    assert 6.5 < g['se_lat'].max() < 7.2 and 7.5 < g['se_lon'].max() < 8.5             # optical libration
    assert np.abs(g['ss_lat']).max() < 1.7
    try:
        r = EP.check()          # uses the archived coord@301 responses when present (no network)
    except Exception as e:      # offline and not archived
        pytest.skip(f'Horizons site check unavailable: {e}')
    assert r['earth']['max_abs_del_deg'] < 0.01 and r['sun']['max_abs_del_deg'] < 0.001
