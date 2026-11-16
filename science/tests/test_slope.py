"""Phase 2 slope operator (science/cube/slope.py). Synthetic cases always run; DEM cases skip without the cache."""
import numpy as np
import pytest

from science.cube import slope as SL
from science.dem import ArrayDEM


def _plane(theta_deg, az_deg=37.0, n=300):
    x = np.arange(n) * 5.0
    X, Y = np.meshgrid(x, -x)
    a = np.radians(az_deg)
    return np.tan(np.radians(theta_deg)) * (np.sin(a) * X + np.cos(a) * Y)


@pytest.mark.parametrize('theta', [0.5, 8.0, 10.0, 20.0, 31.0])
@pytest.mark.parametrize('b', SL.BASELINES_M)
def test_synthetic_plane_within_0p1deg(theta, b):
    S = SL.plane_slope_deg(_plane(theta), 5.0, b)
    assert np.nanmax(np.abs(S - theta)) < 0.1


def test_flat_is_zero():
    S = SL.plane_slope_deg(np.full((100, 100), 1737.5), 5.0, 25)
    assert np.nanmax(np.abs(S)) < 1e-9   # float round-off only


def test_edges_and_nodata_are_nan():
    Z = _plane(5.0, n=100); Z[50, 50] = np.nan
    S = SL.plane_slope_deg(Z, 5.0, 25)
    assert np.isnan(S[0, 0]) and np.isnan(S[50, 50]) and np.isnan(S[52, 49])
    assert np.isfinite(S[20, 20])


def test_cell_window_shape_and_bounds():
    Z = _plane(7.0, n=400)
    d = ArrayDEM(Z, 0.0, 2000.0, 5.0)
    S = SL.plane_slope_deg(Z, 5.0, 100)
    w = SL.cell_window(S, d, 1000.0, 1000.0, 150.0)
    assert w.shape == (60, 60) and np.allclose(w, 7.0, atol=0.1)
    w[0, 0] = -1.0
    assert S[np.isfinite(S)].min() > 0          # a copy, not a view
    with pytest.raises(ValueError):
        SL.cell_window(S, d, 10.0, 1000.0, 150.0)


def test_shackleton_wall_steep_and_roi3_gentle():
    try:
        from science import frames, sites
        dem = sites.near_dem('site04_roi3')
    except Exception as e:  # noqa: BLE001
        pytest.skip(f'DEM cache unavailable: {e}')
    S = SL.plane_slope_deg(dem.Z, dem.step, 100)
    s = sites.SITES['site04']
    x, y = frames.stereo_forward(s['lat'], s['lon'])
    assert SL.at_point(S, dem, x, y) > 20.0                       # tile centre on the Shackleton inner wall (~31.6 deg)
    assert SL.at_point(S, dem, *SL.site_xy('site04_roi3')) < 10.0  # ROI 3 landing point is gentle
