"""Refresh the input SHA-256s recorded in the cube files after an upstream file changed WITHOUT changing any value a
cube was built from (e.g. a bundle gained new `derived` keys). Cube values are never touched.

  python -m science.cube.refresh_provenance --reason "<why>" [--check-bundle-values]

For every cube file in data/cubes/<site>/ (json or json.gz), every provenance input whose `path` is a real file in the
repo gets its `sha256` set to the file's current hash, and a note with the reason is appended when the hash changed.
Repeats until nothing changes (cubes can record other cubes' hashes), then rewrites each index.json entry's bytes and
sha256. With --check-bundle-values the script first refuses to run unless every referenced bundle's metrics, samples,
site and derived.margin_series equal the committed HEAD version.
"""
from __future__ import annotations

import argparse
import gzip
import json
import subprocess
from pathlib import Path

from ..limits.common import sha256_file

ROOT = Path(__file__).resolve().parents[2]
CUBES = ROOT / 'data' / 'cubes'
BUNDLE_KEYS = ('metrics', 'samples', 'site')


def _read(p):
    raw = p.read_bytes()
    gz = raw[:2] == b'\x1f\x8b'
    text = (gzip.decompress(raw) if gz else raw).decode()
    return json.loads(text), gz, text.startswith('{\n')


def _write(p, obj, gz, indented):
    text = json.dumps(obj, indent=1, ensure_ascii=False) + '\n' if indented else json.dumps(obj, separators=(',', ':')) + ('' if gz else '\n')
    if gz:
        p.write_bytes(gzip.compress(text.encode(), mtime=0, compresslevel=9))
    else:
        p.write_text(text)


def check_bundles(ref='HEAD'):
    seen = set()
    for p in CUBES.glob('*/*.json*'):
        if p.name in ('index.json', 'decision_summary.json'):
            continue
        c, _, _ = _read(p)
        for i in c.get('provenance', {}).get('inputs', []):
            if i['path'].startswith('data/bundles/') and (ROOT / i['path']).is_file():
                seen.add(i['path'])
    for path in sorted(seen):
        old = json.loads(subprocess.check_output(['git', 'show', f'{ref}:{path}'], cwd=ROOT))
        new = json.loads((ROOT / path).read_text())
        for k in BUNDLE_KEYS:
            if old.get(k) != new.get(k):
                raise SystemExit(f'{path}: {k} changed vs {ref}; cube values may be stale, rebuild instead')
        if old.get('derived', {}).get('margin_series') != new.get('derived', {}).get('margin_series'):
            raise SystemExit(f'{path}: derived.margin_series changed vs {ref}; rebuild instead')
    return sorted(seen)


def refresh(reason):
    changed_total = []
    for _ in range(10):
        changed = []
        for p in sorted(CUBES.glob('*/*.json*')):
            if p.name in ('index.json', 'decision_summary.json'):
                continue
            c, gz, ind = _read(p)
            dirty = False
            for i in c.get('provenance', {}).get('inputs', []):
                f = ROOT / i['path']
                if '*' in i['path'] or not f.is_file():
                    continue
                h = sha256_file(f)
                if i.get('sha256') != h:
                    i['sha256'] = h
                    i['note'] = (i.get('note', '') + f' [hash refreshed: {reason}]').strip()
                    dirty = True
            if dirty:
                _write(p, c, gz, ind)
                changed.append(str(p.relative_to(ROOT)))
        if not changed:
            break
        changed_total += changed
    for ip in CUBES.glob('*/index.json'):
        idx = json.loads(ip.read_text())
        for e in idx.get('cubes', []):
            f = ip.parent / e['file']
            if f.exists():
                e['sha256'] = sha256_file(f); e['bytes'] = f.stat().st_size
        ip.write_text(json.dumps(idx, indent=1) + '\n')
    return sorted(set(changed_total))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--reason', required=True)
    ap.add_argument('--check-bundle-values', action='store_true')
    a = ap.parse_args()
    if a.check_bundle_values:
        print('bundle values identical to HEAD for:', check_bundles())
    for f in refresh(a.reason):
        print('refreshed', f)
