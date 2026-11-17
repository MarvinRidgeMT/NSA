"""Protocol metrics on synthetic images with known answers."""
import numpy as np
import pytest

from tools.validation.render_vs_real import score as S


def disc(shape, cy, cx, r):
    y, x = np.mgrid[:shape[0], :shape[1]]
    return (y - cy) ** 2 + (x - cx) ** 2 <= r * r


def test_otsu_bimodal_threshold_between_modes_and_not_weak():
    rng = np.random.default_rng(0)
    v = np.concatenate([rng.normal(-3, 0.1, 5000), rng.normal(0, 0.1, 5000)])
    thr, sb, tot = S.otsu(v)
    assert -2.7 < thr < -0.3
    assert sb > 0.5 * tot


def test_otsu_unimodal_flags_weak_bimodality():
    v = np.random.default_rng(1).normal(0, 1, 20000)
    _thr, sb, tot = S.otsu(v)
    assert sb < 0.7 * tot   # a Gaussian splits at ~0.64 of its variance
    shadow, info = S.observed_shadow(10 ** np.random.default_rng(2).normal(0, 0.01, (60, 60)), np.ones((60, 60), bool),
                                     np.zeros((60, 60), bool))
    assert 'weakBimodality' in info


def test_observed_shadow_recovers_mask_and_saturated_counts_lit():
    m = disc((80, 80), 40, 40, 20)
    img = np.where(m, 1e-3, 0.1)
    sat = np.zeros_like(m)
    sat[40, 40] = True
    sh, info = S.observed_shadow(img, np.ones_like(m), sat)
    assert np.array_equal(sh & ~sat, m & ~sat) and not sh[40, 40]
    assert not info['weakBimodality']


def test_agreement_perfect_and_disjoint():
    w = np.ones((50, 50), bool)
    a = disc((50, 50), 25, 25, 10)
    r = S.agreement(a, a, w)
    assert r['iouShadow'] == 1 and r['iouLit'] == 1 and r['kappa'] == pytest.approx(1) and r['balancedAccuracy'] == 1
    b = np.zeros_like(a)
    b[:5, :5] = True
    r = S.agreement(a, b, w)
    assert r['iouShadow'] == 0


def test_edge_error_known_shift_in_metres_and_sign():
    shape = (100, 100)
    w = np.ones(shape, bool)
    obs = np.zeros(shape, bool)
    obs[:, :50] = True                 # shadow on the left, edge at column 49
    pred = np.zeros(shape, bool)
    pred[:, :53] = True                # predicted edge 3 px further right
    gsd = np.full(shape, 2.0)
    yy, xx = np.mgrid[:100, :100]
    pos = np.stack([xx * 2.0, -yy * 2.0, np.zeros(shape)], -1)   # east = +columns
    r = S.edge_errors(pred, obs, w, gsd, pos=pos, sun_h=np.array([1.0, 0.0, 0.0]))   # Sun to the east
    assert r['edgeMedianPx'] == pytest.approx(3.0)
    assert r['edgeMedianM'] == pytest.approx(6.0)
    assert r['edgeSignedMedianM'] == pytest.approx(6.0)     # predicted edge is sunward of the observed one -> positive
    r2 = S.edge_errors(pred, obs, w, gsd, pos=pos, sun_h=np.array([-1.0, 0.0, 0.0]))
    assert r2['edgeSignedMedianM'] == pytest.approx(-6.0)


def test_edge_error_unmatched_beyond_50px():
    shape = (40, 200)
    w = np.ones(shape, bool)
    obs = np.zeros(shape, bool); obs[:, :20] = True
    pred = np.zeros(shape, bool); pred[:, :120] = True
    r = S.edge_errors(pred, obs, w, np.ones(shape))
    assert r['edgeUnmatchedFrac'] == 1.0


def test_ssim_identical_is_one_and_noise_lowers_it():
    rng = np.random.default_rng(3)
    x = rng.random((64, 64)) + 1
    v = np.ones_like(x, bool)
    s, n = S.ssim_masked(x, x, v, L=1.0)
    assert s == pytest.approx(1.0) and n > 0
    s2, _ = S.ssim_masked(x, x + rng.normal(0, 0.3, x.shape), v, L=1.0)
    assert s2 < 0.9


def test_ssim_validity_rule_excludes_sparse_windows():
    x = np.ones((40, 40))
    v = np.zeros_like(x, bool)
    v[::2, ::2] = True     # 25 % valid everywhere -> no window qualifies
    s, n = S.ssim_masked(x, x, v, L=1.0)
    assert n == 0


def test_histogram_distances():
    a = np.full((30, 30), 1.0)
    m = np.ones_like(a, bool)
    d = S.histogram_distances(a, a, m)
    assert d['wasserstein1'] == 0 and d['jsdBits'] == pytest.approx(0)
    d = S.histogram_distances(a, a * 10, m)
    assert d['wasserstein1'] == pytest.approx(1.0) and d['jsdBits'] == pytest.approx(1.0)


def test_register_recovers_subpixel_shift():
    rng = np.random.default_rng(5)
    base = np.zeros((120, 120))
    for _ in range(25):
        base[disc(base.shape, rng.integers(10, 110), rng.integers(10, 110), rng.integers(3, 9))] = 1.0
    base = S.ndimage.gaussian_filter(base, 1.0) + 0.05
    true = (2.25, -3.5)
    real = S.shift(base, *true, cval=0.05)          # the real image is the render displaced by `true`
    m = S.border_mask(base.shape, 12)
    r = S.register(real, base, m, max_px=6)
    assert r['dy'] == pytest.approx(true[0], abs=0.25) and r['dx'] == pytest.approx(true[1], abs=0.25)
    assert not r['atBound']


def test_normalise_and_window():
    x = np.arange(1, 10, dtype=float).reshape(3, 3)
    n, med = S.normalise(x, np.ones_like(x, bool))
    assert med == 5 and n[1, 1] == 1
    w = S.analysis_window(np.ones((20, 20), bool), np.zeros((20, 20), bool))
    assert w.sum() == 4 * 4


def test_count_matched_shadow_keeps_the_predicted_lit_count_and_picks_the_brightest():
    import numpy as np
    from tools.validation.render_vs_real import score as S
    rng = np.random.default_rng(0)
    real = rng.random((20, 20))
    win = np.zeros((20, 20), bool)
    win[2:18, 2:18] = True
    m = S.count_matched_shadow(real, win, 10)
    assert (~m & win).sum() == 10 and not m[~win].any()
    lit_vals = real[~m & win]
    assert lit_vals.min() >= real[m & win].max()
    assert S.count_matched_shadow(real, win, 0)[win].all()
    assert not S.count_matched_shadow(real, win, 10 ** 6)[win].any()
    # near-total shadow: 3 bright rim pixels inside dark noise -> found exactly
    dark = 0.01 * rng.random((20, 20))
    dark[5, 5:8] = 1.0
    pred = np.ones((20, 20), bool)
    pred[5, 5:8] = False
    obs = S.count_matched_shadow(dark, win, int((~pred & win).sum()))
    assert S.agreement(pred & win, obs, win)['iouLit'] == 1.0
