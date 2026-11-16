"""5D Phase 9.4: display-only near-field LOD tiles (tools/terrain/build_lod_tiles.py).
Synthetic cases always run; the built-tile checks skip when the tiles or the NASA cache are absent."""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

from science.dem import ArrayDEM

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'terrain'))
import build_lod_tiles as B  # noqa: E402

N_SRC = 2900          # synthetic raster > 2800 px area + apron + the widest box


@pytest.fixture(scope='module')
def synth():
    rng = np.random.default_rng(7)
    Z = (1700 + rng.normal(0, 30, (N_SRC, N_SRC))).astype('float32').astype('float64')
    Z[1500, 1400] = np.nan                       # one nodata pixel near the centre
    dem = ArrayDEM(Z, x_left=-7250.0, y_top=7250.0, step=5.0)
    site = (1.234, -2.345)                       # off-lattice, like the bundle site points
    part, files = B.build_tiles(dem, site)
    return dem, site, part, files


def tile_array(part, files, t):
    st = part['tileGrid']['stored']
    return np.frombuffer(files[t['file']], dtype='<f4').reshape(st, st)


def test_levels_tile_the_area_exactly(synth):
    _, _, part, _ = synth
    a = part['area']
    assert a['xmax'] - a['xmin'] == pytest.approx(14000.0) and a['ymax'] - a['ymin'] == pytest.approx(14000.0)
    for lv in part['levels']:
        ts = [t for t in part['tiles'] if t['level'] == lv['level']]
        n = lv['tilesPerSide']
        assert len(ts) == n * n and sorted((t['ix'], t['iy']) for t in ts) == [(i, j) for i in range(n) for j in range(n)]
        w = lv['tileWidthM']
        assert w * n == pytest.approx(14000.0)
        for t in ts:
            b = t['bounds']
            assert b['xmin'] == pytest.approx(a['xmin'] + t['ix'] * w, abs=1e-6)
            assert b['ymin'] == pytest.approx(a['ymin'] + t['iy'] * w, abs=1e-6)
            assert b['xmax'] - b['xmin'] == pytest.approx(w) and b['ymax'] - b['ymin'] == pytest.approx(w)
        # sum of tile areas = area (no overlap, no gap, given the grid indices above)
        assert sum((t['bounds']['xmax'] - t['bounds']['xmin']) * (t['bounds']['ymax'] - t['bounds']['ymin']) for t in ts) == pytest.approx(14000.0 ** 2)


def test_centre_node_is_the_pixel_centre_nearest_the_site(synth):
    dem, site, part, _ = synth
    c = part['area']['centreNode']
    assert abs(c['x']) <= 2.5 and abs(c['y']) <= 2.5
    # it is a pixel centre of the source lattice
    assert ((site[0] + c['x'] - dem.x_left) / 5.0 - 0.5) % 1 == pytest.approx(0, abs=1e-6)
    assert ((dem.y_top - (site[1] + c['y'])) / 5.0 - 0.5) % 1 == pytest.approx(0, abs=1e-6)


def _node_pixel(part, t, i, j):
    s = 2 ** (B.LEVELS - 1 - t['level'])
    sw = part['area']['southWestSourcePixel']
    return sw['row'] - (t['iy'] * B.TILE_CELLS + j) * s, sw['col'] + (t['ix'] * B.TILE_CELLS + i) * s, s


def test_heights_equal_the_source_at_sampled_pixels(synth):
    dem, _, part, files = synth
    rng = np.random.default_rng(1)
    a = B.APRON
    for lv in range(B.LEVELS):
        ts = [t for t in part['tiles'] if t['level'] == lv]
        for t in rng.choice(ts, size=min(6, len(ts)), replace=False):
            z = tile_array(part, files, t)
            for i, j in rng.integers(-1, B.TILE_CELLS + 2, size=(40, 2)):
                r, c, s = _node_pixel(part, t, i, j)
                h = s // 2
                box = dem.Z[r - h:r + h + 1, c - h:c + h + 1]
                want = np.float32(box.mean()) if np.isfinite(box).all() else np.nan
                got = z[j + a, i + a]
                if lv == B.LEVELS - 1:          # 5 m: bit-identical to the source pixel
                    assert (np.isnan(got) and np.isnan(want)) or got == np.float32(dem.Z[r, c])
                else:
                    assert (np.isnan(got) and np.isnan(want)) or abs(float(got) - float(want)) < 1e-3


def test_neighbours_share_edge_nodes_and_nodata_is_never_filled(synth):
    dem, _, part, files = synth
    a, n = B.APRON, B.TILE_CELLS
    by = {(t['level'], t['ix'], t['iy']): t for t in part['tiles']}
    for (lv, ix, iy), t in by.items():
        z = tile_array(part, files, t)
        if (lv, ix + 1, iy) in by:
            e = tile_array(part, files, by[(lv, ix + 1, iy)])
            np.testing.assert_array_equal(z[a:a + n + 1, a + n], e[a:a + n + 1, a])
        if (lv, ix, iy + 1) in by:
            e = tile_array(part, files, by[(lv, ix, iy + 1)])
            np.testing.assert_array_equal(z[a + n, a:a + n + 1], e[a, a:a + n + 1])
    # the NaN pixel: its 5 m node is NaN, and so is every coarser node whose box contains it
    nan_r, nan_c = 1500, 1400
    for t in part['tiles']:
        z = tile_array(part, files, t)
        for j in range(-1, n + 2):
            r0, c0, s = _node_pixel(part, t, 0, j)
            if abs(r0 - nan_r) > s // 2:
                continue
            for i in range(-1, n + 2):
                r, c, _ = _node_pixel(part, t, i, j)
                if abs(c - nan_c) <= s // 2:
                    assert np.isnan(z[j + a, i + a])


def test_every_tile_is_at_most_2_MB(synth):
    _, _, part, _ = synth
    assert max(t['bytes'] for t in part['tiles']) <= B.MAX_TILE_BYTES


def test_coarse_level_is_an_average_not_a_sample():
    # a checkerboard of +-1 m averages to ~0 at 80 m, while the 5 m level keeps it
    Z = 1000 + np.where((np.add.outer(np.arange(N_SRC), np.arange(N_SRC)) % 2) == 0, 1.0, -1.0)
    part, files = B.build_tiles(ArrayDEM(Z, -7250.0, 7250.0, 5.0), (0.0, 0.0))
    root = tile_array(part, files, next(t for t in part['tiles'] if t['level'] == 0))
    leaf = tile_array(part, files, next(t for t in part['tiles'] if t['level'] == B.LEVELS - 1))
    assert np.nanmax(np.abs(root - 1000)) < 0.01           # 17 x 17 box of a +-1 checkerboard: |mean| = 1/289
    assert set(np.unique(leaf)) == {999.0, 1001.0}


# ---------------------------------------------------------------- built tiles (real NASA data, skip if absent)
LOD = ROOT / 'web' / 'public' / 'context' / 'lod'


@pytest.mark.parametrize('site', B.SITES_DEFAULT)
def test_built_tiles_match_the_solver_dem_and_the_bundle_crop(site):
    mpath = LOD / site / 'manifest.json'
    if not mpath.exists():
        pytest.skip(f'no LOD tiles for {site} (run tools/terrain/build_lod_tiles.py)')
    from science import sites
    cached = (ROOT / 'data' / 'cache' / f'{site}_p78_p78.npy').exists()
    if not cached:
        pytest.skip('PGDA 78 cache absent')
    m = json.loads(mpath.read_text())
    assert m['status'] == 'VISUAL' and m['numericalAuthority'] is False
    dem = sites.near_dem(site)
    assert m['source']['sha256'] == dem.meta['file_sha256'] and m['source']['url'] == dem.meta['source_url']
    st = m['tileGrid']['stored']
    rng = np.random.default_rng(3)
    leaves = [t for t in m['tiles'] if t['level'] == B.LEVELS - 1]
    for t in rng.choice(leaves, 12, replace=False):
        raw = (LOD / site / t['file']).read_bytes()
        assert len(raw) == t['bytes'] <= B.MAX_TILE_BYTES
        import hashlib
        assert hashlib.sha256(raw).hexdigest() == t['sha256']
        z = np.frombuffer(raw, '<f4').reshape(st, st)
        for i, j in rng.integers(0, B.TILE_CELLS + 1, size=(30, 2)):
            r, c, _ = _node_pixel(m, t, i, j)
            src = dem.Z[r, c] if 0 <= r < dem.Z.shape[0] and 0 <= c < dem.Z.shape[1] else np.nan
            got = z[j + 1, i + 1]
            assert (np.isnan(got) and np.isnan(src)) or got == np.float32(src)
    # frame: the bundle's 5 m crop nodes coincide with LOD 5 m nodes and carry the same heights
    viewer = json.loads((ROOT / 'data' / 'viewer' / 'polaris-x5d-roi-2026-11-14-v2.json').read_text())
    ds = next(d for d in viewer['datasets'] if d['siteId'] == site)
    assert ds['site']['projectedMeters'] == m['sitePointProjectedM']
    crop = ds['dem']
    a = m['area']
    di = (crop['originX'] - a['xmin']) / 5.0
    dj = (crop['originY'] - a['ymin']) / 5.0
    assert abs(di - round(di)) < 1e-3 and abs(dj - round(dj)) < 1e-3
    di, dj = int(round(di)), int(round(dj))
    vals = np.asarray(crop['values'], dtype=float).reshape(crop['n'], crop['n'])
    for ci, cj in rng.integers(0, crop['n'], size=(40, 2)):
        gi, gj = di + ci, dj + cj                     # area node index
        ix, iy = min(gi // B.TILE_CELLS, 15), min(gj // B.TILE_CELLS, 15)
        t = next(t for t in leaves if t['ix'] == ix and t['iy'] == iy)
        z = np.frombuffer((LOD / site / t['file']).read_bytes(), '<f4').reshape(st, st)
        got = float(z[gj - iy * B.TILE_CELLS + 1, gi - ix * B.TILE_CELLS + 1])
        assert abs(got - vals[cj, ci]) < 1e-3, (site, ci, cj, got, vals[cj, ci])
