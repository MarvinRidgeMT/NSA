"""Inputs for the v2 showcase .blend (project venv; Blender itself computes nothing). Writes
blender/output/v2/showcase/showcase_inputs.json (git-ignored):

  * mars: the Jezero rim bundle's stored terrain skyline (az/el) and, for the first 24 h of the relay window, each relay
    orbiter's per-minute apparent az/el from the cached JPL Horizons tables (offline; the same rotation to the sphere normal
    as science/worlds/mars/relays.py) with its visible/hidden state against that skyline;
  * galleries: the local render-vs-real thumbnails (NAC held-out, WAC dev) with each row's numbers from the committed scores.

    .venv/bin/python blender/v2/showcase_prep.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / 'blender' / 'output' / 'v2' / 'showcase'


def mars(hours=24):
    from science.worlds.mars import relays as R
    from science import horizons as H
    from science.anysite.ephem import fetch_cached
    from science.crossings import horizon_at
    from science.worlds import ephem as WE
    from science.worlds.mars.world import MARS
    B = R.load_bundle()
    sky = B['skyline']
    s = B['site']
    lat, lon = s['lat_deg'], s['lon_deg_east']
    h_eye = s['height_m'] + s['observer_mast_m']                         # as relays.build
    lon_offset = B['frame']['horizons_longitude_offset_deg']
    out = {'skyline': {'az': sky['azimuth_deg'], 'el': sky['elevation_deg']}, 'site': s['name'], 'orbiters': [],
           'window_start_utc': R.START, 'hours': hours, 'label': R.LABEL}
    n = hours * 60 + 1
    for rid, naif, name in R.ORBITERS:
        p = MARS.horizons_params(naif, lat, lon + lon_offset, h_eye, R.START, R.STOP, R.STEP, quantities='4,20')
        try:
            body, _src = fetch_cached(p, cache_dir=WE.cache_dir(MARS), allow_network=False)
        except Exception as e:      # noqa: BLE001
            out['orbiters'].append({'id': rid, 'name': name, 'status': f'not available ({type(e).__name__})'})
            continue
        text = body.decode('utf-8', 'replace')
        if '$$SOE' not in text:
            out['orbiters'].append({'id': rid, 'name': name, 'status': 'not available (no Horizons trajectory)'})
            continue
        rows = H.parse_text(text)[:n]
        az, el, _ = MARS.horizons_azel_to_sphere(np.array([r['az_deg'] for r in rows]), np.array([r['el_deg'] for r in rows]),
                                                 lat, lon, h_eye)
        hz = np.array([horizon_at(sky, a)[0] for a in az], float)
        out['orbiters'].append({'id': rid, 'name': name, 'status': 'computed', 'utc0': rows[0]['utc'],
                                'az': np.round(az, 3).tolist(), 'el': np.round(el, 3).tolist(),
                                'visible': (el > hz).tolist()})
    return out


def galleries():
    res = {}
    for key, gal, scores in (('nac_heldout', 'docs/validation/render_vs_real_heldout',
                              'tools/validation/render_vs_real/results_heldout/scores.jsonl'),
                             ('wac_dev', 'docs/validation/render_vs_real_wac',
                              'tools/validation/render_vs_real/results_wac/scores.jsonl'),
                             ('wac_heldout', 'docs/validation/render_vs_real_wac_heldout',
                              'tools/validation/render_vs_real/results_wac_heldout/scores.jsonl')):
        g = ROOT / gal
        sp = ROOT / scores
        if not g.exists() or not sp.exists():
            res[key] = []
            continue
        rec = {}
        for line in sp.read_text().splitlines():
            r = json.loads(line)
            if r.get('product') == 'pgda78_5m' and r.get('photometry') == 'hapke' and r.get('registered') and r.get('status') == 'scored':
                rec[(r['product_id'], r['site'])] = r
        items = []
        for f in sorted(g.iterdir()):
            if f.suffix.lower() not in ('.jpg', '.png') or '__' not in f.stem:
                continue
            pid, site = f.stem.split('__')[:2]
            r = rec.get((pid, site), {})
            items.append({'path': str(f), 'product_id': pid, 'site': site, 'iouShadow': r.get('iouShadow'),
                          'edgeMedianM': r.get('edgeMedianM')})
        res[key] = items
    return res


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = {'mars': mars(), 'galleries': galleries()}
    (OUT / 'showcase_inputs.json').write_text(json.dumps(data))
    print('mars orbiters:', [(o['id'], o['status']) for o in data['mars']['orbiters']],
          '| galleries:', {k: len(v) for k, v in data['galleries'].items()})


if __name__ == '__main__':
    main()
