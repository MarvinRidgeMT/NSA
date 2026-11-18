"""Gap-filled colour maps for the giant planets (project venv). OPAL global maps leave unobserved pixels black (polar
regions in darkness or never in view). Giant-planet clouds are organised in latitude bands, so each empty pixel takes its
latitude row's median of observed pixels; rows with no observed pixel take the nearest observed row. The filled fraction
is recorded in map.json. VISUAL (cloud features of the OPAL epoch, not of the scene date).

    .venv/bin/python blender/v2/giants_pack.py
"""
import json
import struct
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'data' / 'cache' / 'v2' / 'products' / 'outer_planets_maps'
HD = ROOT / 'blender' / 'output' / 'v2' / 'showcase' / 'hd'
FILES = {'jupiter': 'hlsp_opal_hst_wfc3-uvis_jupiter-2025b_f395n-f502n-f631n_v1_globalmap.tif',
         'saturn': 'hlsp_opal_hst_wfc3-uvis_saturn-2025b_f395n-f502n-f631n_v1_globalmap.tif',
         'uranus': 'hlsp_opal_hst_wfc3-uvis_uranus-2024b_f657n-f547m-f467m_v1_globalmap.tif',
         'neptune': 'hlsp_opal_hst_wfc3-uvis_neptune-2025c_f467m-f547m-f657n_v1_globalmap.tif'}


def png(path, img):
    h, w, _ = img.shape

    def ch(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    raw = b''.join(b'\x00' + img[i].tobytes() for i in range(h))
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) +
                           ch(b'IDAT', zlib.compress(raw, 6)) + ch(b'IEND', b''))


def main():
    import rasterio
    for body, f in FILES.items():
        a = rasterio.open(SRC / f).read().astype(np.float32)          # (3, H, W)
        ok = a.sum(0) > 15
        H = a.shape[1]
        rowmed = np.full((H, 3), np.nan, np.float32)
        for r in range(H):
            if ok[r].any():
                rowmed[r] = np.median(a[:, r, ok[r]], axis=1)
        have = np.flatnonzero(np.isfinite(rowmed[:, 0]))
        for r in range(H):
            if not np.isfinite(rowmed[r, 0]):
                rowmed[r] = rowmed[have[np.argmin(np.abs(have - r))]]
        out = a.copy()
        for c in range(3):
            out[c][~ok] = np.broadcast_to(rowmed[:, c][:, None], ok.shape)[~ok]
        d = HD / body
        d.mkdir(parents=True, exist_ok=True)
        png(d / 'map.png', np.ascontiguousarray(np.clip(np.transpose(out, (1, 2, 0)), 0, 255).astype(np.uint8)))
        (d / 'map.json').write_text(json.dumps({'source': f, 'filledFraction': float((~ok).mean()),
                                                'rule': 'empty pixel -> its latitude row median (nearest observed row if none)'},
                                               indent=1) + '\n')
        print(body, 'filled %.3f' % (~ok).mean())


if __name__ == '__main__':
    main()
