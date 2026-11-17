"""Frozen inputs and the held-out wall."""
import csv
import json
from pathlib import Path

import pytest

from tools.validation.render_vs_real import common
from tools.validation.render_vs_real.common import RESULTS


def test_frozen_protocol_and_catalogue_hashes():
    assert common.sha256_file(common.PROTOCOL) == 'bf85659d39261f34b631be7a75110f227feb64092aa600941307128900721516'
    assert common.sha256_file(common.CATALOGUE) == '4b941d61f1ecb06155a2b0ffcc7f9a5f9ea1dc5b41ef6918ff1f69f424515e01'


def test_assert_dev_rejects_a_heldout_id():
    rows = common.read_catalogue()
    held = sorted(common.heldout_ids(rows))[0]
    with pytest.raises(common.HeldOutError):
        common.assert_dev([held], rows)
    dev = next(r['product_id'] for r in rows if r['split'] == 'dev')
    common.assert_dev([dev], rows)


def _ids_in_results():
    ids = set()
    for p in RESULTS.rglob('*'):
        if p.suffix == '.json':
            txt = p.read_text()
        elif p.suffix in ('.csv', '.jsonl', '.md'):
            txt = p.read_text()
        else:
            continue
        ids.update(w.strip('",[]{}: ') for w in txt.replace(',', ' ').split())
    return ids


def test_no_heldout_id_in_any_committed_r4_output():
    held = common.heldout_ids()
    outs = _ids_in_results()
    doc = Path(common.ROOT / 'docs' / 'validation' / 'RENDER_VS_REAL.md')
    if doc.exists():
        outs |= {w.strip('|`*,.():[]') for w in doc.read_text().split()}
    gal = common.ROOT / 'docs' / 'validation' / 'render_vs_real'
    if gal.exists():
        outs |= {p.stem.split('__')[0] for p in gal.iterdir()}
    bad = held & outs
    assert not bad, f'held-out ids in R4 outputs: {sorted(bad)[:10]}'


def test_selection_is_dev_only_and_metadata_eligible():
    sel = json.loads((RESULTS / 'selection.json').read_text())
    rows = {(r['product_id'], r['site']): r for r in common.read_catalogue()}
    for im in sel['images']:
        for site in im['sites']:
            r = rows[(im['product_id'], site)]
            assert r['split'] == 'dev'
            assert common.eligible_by_metadata(r)[0]
