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


def test_jpeg_size_and_image_size():
    # minimal JFIF: SOI, APP0 (16 bytes), SOF0 with 240 x 320 (h x w)
    app0 = b'\xff\xe0' + struct.pack('>H', 16) + b'JFIF\x00' + b'\x01\x01\x00\x00\x01\x00\x01\x00\x00'
    sof0 = b'\xff\xc0' + struct.pack('>HBHHB', 11, 8, 240, 320, 1) + b'\x01\x11\x00'
    jpg = b'\xff\xd8' + app0 + sof0 + b'\xff\xd9'
    assert thumbs.jpeg_size(jpg) == (320, 240)
    assert thumbs.image_size(jpg) == ('jpeg', 320, 240)
    assert thumbs.image_size(_png(3, 4)) == ('png', 3, 4)
    with pytest.raises(ValueError):
        thumbs.image_size(b'{"ODEResults": {"Error": "Unable to find products"}}')


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
