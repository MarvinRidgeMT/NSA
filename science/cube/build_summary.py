"""Decision Card rows, one per sub-axis question, precomputed from the cubes (the browser only displays them).

  python -m science.cube.build_summary [site ...]   -> data/cubes/<site>/decision_summary.json

Rows: T how sure? · M do the data products agree? · D what fixes it? · S when? · R against which requirement? ·
link who can we talk to? · energy does the battery survive? · safety safe and lit?  A row whose cube is absent says
"not in bundle". k of N maps is not a probability.
"""
from __future__ import annotations

import gzip
import json
import sys

import numpy as np

from .build_cube import LABEL, OUT, R_PRESETS

EA = 'ENGINEERING ASSUMPTION'
N = 337


def _load(site, name):
    p = OUT / site / name
    if not p.exists():
        return None
    raw = p.read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)


def _shape(c, dims=None):
    return [len(d['values']) for d in (dims or c['dims'])]


def _ddims(c, key):
    return [x if isinstance(x, dict) else next(y for y in c['dims'] if y['name'] == x) for x in c['derived'][key]['dims']]


def rows(site):
    out = []
    cm = _load(site, 'centre_mast_schedule.json.gz')
    if cm:
        sun = np.array(cm['metrics']['sun_pct']['values']).reshape(_shape(cm)) * 100 / N
        both = np.array(cm['metrics']['sun_earth_pct']['values']).reshape(_shape(cm)) * 100 / N
        k = np.array(cm['derived']['k_of_N']['metrics']['k_pass']['values']).reshape(_shape(cm, _ddims(cm, 'k_of_N')))
        masts = cm['dims'][1]['values']
        src = f'scenario cube {cm["cube_id"]}'
        out.append({'axis': 'T', 'question': 'how sure?', 'label': LABEL, 'source': src,
                    'value': f'{sun[0, 0, 0]:.2f} % (range {sun[:, 0, 0].min():.2f}–{sun[:, 0, 0].max():.2f} %)',
                    'answer': 'Sun at 1 m, 2026-11-14 window: nominal map, range over 21 maps.'})
        ok = [m for j, m in enumerate(masts) if k[0, j, 0] == 20]
        out.append({'axis': 'D', 'question': 'what fixes it?', 'label': LABEL, 'source': src,
                    'value': f'{ok[0]:g} m' if ok else 'no mast ≤ 10 m',
                    'answer': 'lowest mast passing the team requirement on all 20 maps for the 2026-11-14 window.'})
        share = 100 * float((k[0, 0] == 20).mean())
        out.append({'axis': 'S', 'question': 'when?', 'label': LABEL, 'source': src,
                    'value': f'{share:.1f} % of starts',
                    'answer': 'hourly starts over 12 months passing the team requirement on all 20 maps at 1 m.'})
        rk = ', '.join(f'{r["id"]} {int(k[i, 0, 0])}/20' for i, r in enumerate(R_PRESETS))
        out.append({'axis': 'R', 'question': 'against which requirement?', 'label': LABEL, 'source': src,
                    'value': rk, 'answer': '1 m, 2026-11-14 window (team = Sun ≥ 70 %, Sun+Earth ≥ 40 %, gap ≤ 120 h).'})
    pr = _load(site, 'products.json')
    if pr:
        v = [x for x in pr['metrics']['sun_pct']['values'] if x is not None]
        miss = len(pr['metrics']['sun_pct']['values']) - len(v)
        out.insert(1, {'axis': 'M', 'question': 'do the data products agree?', 'label': LABEL, 'source': f'scenario cube {pr["cube_id"]}',
                       'value': f'{min(v):.2f}–{max(v):.2f} %',
                       'answer': f'Sun, 1 m, demo window across {len(v)} NASA terrain products' + (f' ({miss} not covered)' if miss else '') + '.'})
    ln = _load(site, 'link.json.gz')
    if ln:
        y = np.array(ln['derived']['year_summary']['metrics']['available_pct']['values']).reshape(_shape(ln, _ddims(ln, 'year_summary')))
        tg = ln['dims'][2]['values']
        g = lambda name: y[0, 0, tg.index(name), 0]
        out.append({'axis': 'link', 'question': 'who can we talk to?', 'label': f'{LABEL} · {EA}', 'source': f'scenario cube {ln["cube_id"]}',
                    'value': f'DTE {g("earth_dsn"):.1f} % · +1 relay {g("dte_plus_1_relay"):.1f} % · +2 relays {g("dte_plus_2_relays"):.1f} %',
                    'answer': '12 months, 1 m, nominal map, LCRNS reference constellation (not an operational schedule).'})
    en = _load(site, 'energy.json.gz') or _load(site, 'energy.json')
    if en and 'trade' in en.get('derived', {}):
        tr = en['derived']['trade']; dd = _ddims(en, 'trade')
        arr = dd[0]['values']; masts = dd[1]['values']
        mm = tr['metrics']['needed_all_worst20']
        nw = np.array(mm['values'], float).reshape(len(arr), len(masts)) * mm.get('scale', 1.0)   # stored Wh, scale 0.001 -> kWh
        a = arr.index('vsat') if 'vsat' in arr else 0
        val = ' · '.join(f'{m:g} m: {nw[a, masts.index(m)]:.1f} kWh' for m in (1.0, 5.0) if m in masts)
        out.append({'axis': 'energy', 'question': 'does the battery survive?', 'label': EA, 'source': f'scenario cube {en["cube_id"]}',
                    'value': val, 'answer': f'battery needed so charge stays above reserve for every daily start on all 20 maps ({arr[a]} array; '
                                            f'{en["fixed"].get("load_constant_w", "?")} W base load, assumptions in {en["fixed"].get("assumptions_file", "the cube")}).'})
    else:
        out.append({'axis': 'energy', 'question': 'does the battery survive?', 'label': EA, 'source': 'not in bundle',
                    'value': 'not in bundle', 'answer': 'energy cube not built on this branch.'})
    ts = _load(site, 'terrain_safety.json')
    if ts:
        sl = np.array(ts['derived']['safe_and_lit']['metrics']['k_safe_and_lit']['values']).reshape(2, -1)
        out.append({'axis': 'safety', 'question': 'safe and lit?', 'label': f'{LABEL} · {EA} thresholds', 'source': f'scenario cube {ts["cube_id"]}',
                    'value': f'{int((sl[0] == 20).sum())} of {sl.shape[1]} cells',
                    'answer': 'landing slope < 10° and team visibility on all 20 maps (2026-11-14 window).'})
    return out


def write(site):
    s = {'schema': 'polaris-decision-summary-v1', 'site_id': site, 'label': LABEL, 'rows': rows(site),
         'note': 'k of N maps is not a probability; scenario counts are never combined across axes.'}
    (OUT / site / 'decision_summary.json').write_text(json.dumps(s, indent=1, ensure_ascii=False) + '\n')
    return s


if __name__ == '__main__':
    for s in sys.argv[1:] or ['site04_roi3', 'site01_roi6']:
        for r in write(s)['rows']:
            print(s, r['axis'], '|', r['value'], '|', r['answer'])
