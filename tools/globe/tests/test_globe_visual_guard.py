"""Science never sees synthetic relief (prompt §2.3, contract §4): this test FAILS if any code under science/ reads the
VISUAL tree (pyramid_visual)."""
import re
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from globe_fixtures import SP, grid_centres, plane, write_raster  # noqa: E402

from science.terrain import stack as S  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
SCIENCE = REPO / 'science'
PATTERN = re.compile(r'pyramid_visual|height_visual')


def test_no_science_module_references_visual_tree():
    """Static: the only mention allowed under science/ is the guard constant in science/terrain/stack.py."""
    hits = []
    for f in SCIENCE.rglob('*.py'):
        txt = f.read_text(errors='replace')
        for m in PATTERN.finditer(txt):
            line = txt[:m.start()].count('\n') + 1
            src = txt.splitlines()[line - 1].strip()
            hits.append((str(f.relative_to(REPO)), line, src))
    allowed = [h for h in hits if h[0] == 'science/terrain/stack.py' and h[2].startswith("VISUAL_DIRNAME = 'pyramid_visual'")]
    others = [h for h in hits if h not in allowed and not (h[0] == 'science/terrain/stack.py' and '(pyramid_visual)' in h[2])]
    assert len(allowed) == 1, hits
    assert not others, f'science code references the VISUAL tree: {others}'


def test_no_science_module_builds_visual_path_dynamically():
    """Static: no science module joins 'visual' into a data path (e.g. 'pyramid' + '_visual')."""
    bad = []
    for f in SCIENCE.rglob('*.py'):
        txt = f.read_text(errors='replace')
        if re.search(r"['\"]_visual['\"]", txt):
            bad.append(str(f.relative_to(REPO)))
    assert not bad, bad


def test_open_refuses_visual_root(tmp_path):
    vis = tmp_path / 'v2' / 'pyramid_visual'
    vis.mkdir(parents=True)
    (vis / 'index.json').write_text('{"tiles": []}')
    with pytest.raises(PermissionError):
        S.TerrainStack.open(vis)
    with pytest.raises(PermissionError):
        S.TerrainStack(vis, {'tiles': []})
    # a symlink into the VISUAL tree is refused as well
    link = tmp_path / 'innocent'
    link.symlink_to(vis)
    with pytest.raises(PermissionError):
        S.TerrainStack.open(link)


def test_runtime_reads_never_touch_visual(tmp_path, monkeypatch):
    """Runtime spy: every raster the science stack opens while sampling and windowing is outside pyramid_visual,
    even when a VISUAL tree sits right next to the science pyramid."""
    import rasterio
    from tools.globe import pyramid as PY
    from tools.globe import pyramid_products as PP
    l, t, px, n = -5000.0, 5000.0, 80.0, 125
    X, Y = grid_centres(l, t, px, n, n)
    f = write_raster(tmp_path / 'c.tif', plane(X, Y), l, t, px, SP)
    root = tmp_path / 'v2' / 'pyramid'
    PY.build(zones=('sp',), max_level=4, workers=1, root=root, specs=[PP.ProductSpec('c', 5, f, 80.0)],
             log=lambda *a: None)
    vis = tmp_path / 'v2' / 'pyramid_visual' / 'sp' / '4'
    vis.mkdir(parents=True)
    opened = []
    real_open = rasterio.open

    def spy(path, *a, **k):
        opened.append(str(path))
        return real_open(path, *a, **k)
    monkeypatch.setattr(rasterio, 'open', spy)
    st = S.TerrainStack.open(root)
    lat, lon = S.ZONES['sp'].inverse(np.array([0.0, 1000.0]), np.array([0.0, -2000.0]))
    h, _, _ = st.sample(lat, lon)
    assert np.isfinite(h).all()
    st.window(float(lat[0]), float(lon[0]), 2000.0, res_m=80.0)
    assert opened and not [p for p in opened if 'pyramid_visual' in p]
