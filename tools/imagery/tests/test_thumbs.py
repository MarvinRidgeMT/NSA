import struct
import zlib

import pytest

from tools.imagery import thumbs


def _png(w, h):
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0)
    chunk = struct.pack('>I', len(ihdr)) + b'IHDR' + ihdr + struct.pack('>I', zlib.crc32(b'IHDR' + ihdr))
    return thumbs.PNG_SIG + chunk


def test_png_size():
    assert thumbs.png_size(_png(64, 128)) == (64, 128)
    with pytest.raises(ValueError):
        thumbs.png_size(b'<html>error</html>')


def test_pick_is_dev_only_capped_and_round_robin():
    rows = []
    for ins in ('A', 'B'):
        for i in range(30):
            rows.append({'product_id': f'{ins}{i}', 'instrument': ins, 'split': 'heldout' if i % 3 == 0 else 'dev',
                         'is_primary_row': 'true'})
    got = thumbs.pick(rows, 50)
    assert len(got) == thumbs.HARD_CAP
    assert all(r['split'] == 'dev' for r in got)
    assert [r['instrument'] for r in got[:4]] == ['A', 'B', 'A', 'B']
    assert thumbs.pick(rows, 50) == got
