import hashlib
import math
from collections import Counter

import pytest

from tools.imagery import catalogue as cat
from tools.imagery import solar
from tools.imagery.sites import SITES, SITE_ORDER


def test_az_bins_and_wrap():
    assert cat.az_bin(0.0) == 'N' and cat.az_bin(22.49) == 'N' and cat.az_bin(22.5) == 'NE'
    assert cat.az_bin(337.49) == 'NW' and cat.az_bin(337.5) == 'N' and cat.az_bin(359.99) == 'N'
    assert cat.az_bin(90) == 'E' and cat.az_bin(180) == 'S' and cat.az_bin(270) == 'W'
    assert cat.az_bin(-90) == 'W' and cat.az_bin(None) == 'unknown'


def test_edge_bins():
    assert cat._bin(-0.5, cat.EL_EDGES) == 'el[-0.5,0.5)'
    assert cat._bin(-0.5000001, cat.EL_EDGES) == 'el<-0.5'
    assert cat._bin(2.5, cat.EL_EDGES) == 'el>=2.5'
    assert cat._bin(5.0, cat.EM_EDGES) == 'em[5,15)'
    assert cat._bin(0.999, cat.RES_EDGES) == 'res<1m' and cat._bin(100, cat.RES_EDGES) == 'res>=100m'
    assert cat._bin(None, cat.RES_EDGES) == 'unknown'


def test_subsolar_latitude_closed_forms():
    # At the pole every direction is "north"-ish; with az = 0 at lat -90, s_z = sin(el) * sin(-90) = -sin(el)
    assert solar.subsolar_lat_deg(-90.0, 0.0, 0.0, 1.0) == pytest.approx(-1.0)
    # At the equator facing north with the Sun on the horizon, the Sun is over the north pole
    assert solar.subsolar_lat_deg(0.0, 0.0, 0.0, 0.0) == pytest.approx(90.0)
    # Sun at zenith: sub-solar latitude = site latitude
    assert solar.subsolar_lat_deg(-88.7, 10.0, 123.0, 90.0) == pytest.approx(-88.7)
    # 1 deg from the south pole, Sun toward local north (away from the pole) at elevation e:
    # on the horizon it is over latitude +c, so ssl = c - e
    lat = -89.0
    assert solar.subsolar_lat_deg(lat, 0.0, 0.0, 1.5) == pytest.approx(1.0 - 1.5, abs=1e-3)
    # toward local south (over the pole) at elevation e: ssl = -(c + e)
    assert solar.subsolar_lat_deg(lat, 0.0, 180.0, 1.5) == pytest.approx(-(1.0 + 1.5), abs=1e-3)


def test_parse_utc_formats():
    a = solar.parse_utc('2009-07-04T12:39:00.489Z')
    b = solar.parse_utc('2009-07-04T12:39:00.489')
    c = solar.parse_utc('2023-01-06T17:20:38.977048Z')
    assert a == b and a == pytest.approx(1246711140.489)
    assert c - solar.parse_utc('2023-01-06T17:20:38Z') == pytest.approx(0.977048)


def _fake_rows(n_images=200, seed=0):
    rows = []
    for i in range(n_images):
        pid = f'M{100000000 + i:09d}LC'
        h = int(hashlib.sha256(f'{seed}:{i}'.encode()).hexdigest(), 16)
        n_sites = 1 + h % 2
        for k in range(n_sites):
            site = SITE_ORDER[(h >> 3) % 4 if k == 0 else ((h >> 3) + 1) % 4]
            rows.append({'product_id': pid, 'site': site, 'instrument': 'LROC_NAC' if h % 3 else 'ShadowCam',
                         'terrain': SITES[site]['terrain'], 'overlap_frac': ((h >> (8 + k)) % 100) / 100 + 0.001 * k,
                         'sun_az_deg': (h >> 12) % 360, 'sun_el_deg': ((h >> 20) % 50) / 10 - 1.5,
                         'emission_deg': (h >> 26) % 40, 'subsolar_lat_deg': ((h >> 30) % 30) / 10 - 1.5,
                         'pixel_scale_m': 0.5 + (h >> 34) % 3, 'obs_utc': '2010-01-01T00:00:00Z'})
    return rows


def test_split_deterministic_by_image_and_30pct():
    rows = _fake_rows(600)
    prior = {r['product_id'][:-1]: 6 for r in rows[:30] if r['instrument'] == 'LROC_NAC'}
    held = cat.assign_split(rows, prior)
    rows2 = _fake_rows(600)
    held2 = cat.assign_split(rows2, prior)
    assert held == held2
    imgs = {r['product_id'] for r in rows}
    elig = {r['product_id'] for r in rows if not r['prior_use']}
    assert len(held) == math.floor(len(elig) * cat.HELDOUT_FRAC)
    # never prior_use, and split is per image (all rows of an image agree)
    assert not any(r['prior_use'] and r['split'] == 'heldout' for r in rows)
    per = {}
    for r in rows:
        per.setdefault(r['product_id'], set()).add(r['split'])
    assert all(len(v) == 1 for v in per.values())
    # exactly one primary row per image, the one with the largest overlap
    prim = [r for r in rows if r['is_primary_row']]
    assert len(prim) == len(imgs)
    for p in prim:
        assert p['overlap_frac'] == max(r['overlap_frac'] for r in rows if r['product_id'] == p['product_id'])
    # per-stratum held-out count within 0.3 n +/- 1
    n = Counter(p['stratum'] for p in prim if not p['prior_use'])
    h = Counter(p['stratum'] for p in prim if p['split'] == 'heldout')
    for k, v in n.items():
        assert abs(h[k] - cat.HELDOUT_FRAC * v) <= 1.0, (k, v, h[k])


def test_split_hash_depends_on_seed_and_id():
    assert cat.split_hash('A') != cat.split_hash('B')
    assert cat.split_hash('A') == hashlib.sha256(b'polaris-x-v2-heldout-2026-11-16:A').hexdigest()


def test_prior_use_ids_are_the_687_gsfc_images():
    ids = cat.prior_use_ids()
    assert sum(len(v) for v in ids.values()) == 687
    assert Counter(g for v in ids.values() for g in v) == {6: 322, 8: 172, 9: 193}
    assert len(ids) < 687  # some frames appear in two regions' lists
    assert 'M118008479L' in ids


def test_csv_gz_bytes_reproducible(tmp_path):
    rows = _fake_rows(50)
    cat.assign_split(rows, {})
    a = cat.write_csv_gz(rows, tmp_path / 'a.csv.gz')
    b = cat.write_csv_gz(list(reversed(rows)), tmp_path / 'b.csv.gz')
    assert a == b
    back = cat.read_csv_gz(tmp_path / 'a.csv.gz')
    assert len(back) == len(rows) and list(back[0]) == cat.COLUMNS


def test_build_end_to_end_with_fake_sun(tmp_path):
    import json
    hd = tmp_path / 'harvest'
    hd.mkdir()
    rows = _fake_rows(40)
    for r in rows:
        for k in ('sun_az_deg', 'sun_el_deg', 'subsolar_lat_deg'):
            r.pop(k)
    by = {}
    for r in rows:
        by.setdefault((r['site'], r['instrument']), []).append(r)
    for (s, ins), rs in by.items():
        (hd / f'{s}__{ins}.json').write_text(json.dumps({'meta': {'site': s, 'instrument': ins, 'bbox': {},
                                                       'ode_candidates': len(rs), 'kept': len(rs), 'sources': []}, 'rows': rs}))

    def fake_sun(lat, lon, ts):
        return {t: (123.0, 1.0) for t in ts}, [{'sha256': '0' * 64}]
    out = tmp_path / 'imagery' / 'catalogue.csv.gz'
    got, side = cat.build(out=out, harvest_dir=hd, sun_fn=fake_sun, prior={})
    assert side['rows'] == len(rows) and side['images'] == 40
    assert side['sha256'] == hashlib.sha256(out.read_bytes()).hexdigest()
    assert all(r['az_bin'] == 'SE' and r['el_bin'] == 'el[0.5,1.5)' for r in got)
    txt = cat.counts_tables(cat.read_csv_gz(out))
    assert 'Unique images' in txt and 'Full strata' in txt
