"""Frozen files must match the hashes recorded in docs/v2/PREREGISTRATION.md."""
import hashlib
import re

from tools.imagery.http_cache import ROOT

PREREG = ROOT / 'docs' / 'v2' / 'PREREGISTRATION.md'
ROW = re.compile(r'^\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{64})`\s*\|\s*$')


def _rows():
    return [m.groups() for line in PREREG.read_text().splitlines() if (m := ROW.match(line))]


def test_preregistered_hashes_match():
    rows = _rows()
    assert len(rows) >= 2 and any(p == 'docs/v2/RENDER_VS_REAL_PROTOCOL.md' for p, _ in rows)
    assert any(p == 'imagery/catalogue.csv.gz' for p, _ in rows)
    for path, sha in rows:
        got = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        assert got == sha, f'{path} changed after pre-registration ({got} != {sha}); append an amendment instead'


def test_catalogue_split_reproduces_from_its_own_rows():
    """Re-derive the held-out split from the frozen catalogue's rows with the frozen rule."""
    from tools.imagery import catalogue as cat
    rows = cat.read_csv_gz(ROOT / 'imagery' / 'catalogue.csv.gz')
    stored = {r['product_id']: r['split'] for r in rows}
    for r in rows:
        r['overlap_frac'] = float(r['overlap_frac'])
        for k in ('sun_az_deg', 'sun_el_deg', 'subsolar_lat_deg', 'emission_deg', 'pixel_scale_m'):
            r[k] = float(r[k]) if r[k] != '' else None
    held = cat.assign_split(rows, cat.prior_use_ids())
    assert {p for p, s in stored.items() if s == 'heldout'} == held
