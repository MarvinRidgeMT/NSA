"""Shared helpers for the science-limits work (branch science/limits-2026-11-15).

Every result is written to a NEW directory data/science_limits/<item>/ with result.json,
manifest.json (inputs + SHA-256, command, code commit, date) and README.md. Nothing here
edits an existing bundle. Label: PILOT · SOURCE-BASED · UNVALIDATED.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = ROOT / 'data' / 'science_limits'
SKY_CACHE = ROOT / 'data' / 'cache' / 'science_limits'
LABEL = 'PILOT · SOURCE-BASED · UNVALIDATED'
BUNDLES = {
    'site04_roi3': ROOT / 'data' / 'bundles' / 'site04_roi3_2026-11-14_14d_mast1m.json',
    'site01_roi6': ROOT / 'data' / 'bundles' / 'site01_roi6_2026-11-14_14d_mast1m.json',
}


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def git_commit():
    try:
        c = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        dirty = subprocess.call(['git', 'diff', '--quiet', 'HEAD', '--', 'science'], cwd=ROOT) != 0
        return c + ('-dirty' if dirty else '')
    except Exception:
        return 'unknown'


def load_bundle(site):
    return json.loads(Path(BUNDLES[site]).read_text())


def write_result(item, result, inputs, readme, extra_files=None):
    """inputs: list of paths (hashed) or dicts {'path','sha256','note'} for files outside git."""
    d = OUT_ROOT / item
    d.mkdir(parents=True, exist_ok=True)
    result = {'label': LABEL, **result}
    (d / 'result.json').write_text(json.dumps(result, indent=1, default=_np_default) + '\n')
    ins = []
    for p in inputs:
        if isinstance(p, dict):
            ins.append(p)
        else:
            p = Path(p)
            rel = str(p.resolve().relative_to(ROOT.resolve())) if str(p.resolve()).startswith(str(ROOT.resolve())) else str(p)
            ins.append({'path': rel, 'sha256': sha256_file(p)})
    manifest = {
        'item': item, 'label': LABEL,
        'date_utc': _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'command': ' '.join(['python'] + [Path(sys.argv[0]).name if i == 0 else a for i, a in enumerate(sys.argv)]),
        'module': sys.argv[0],
        'code_commit': git_commit(),
        'inputs': ins,
        'outputs': {'result.json': sha256_file(d / 'result.json')},
    }
    for name, content in (extra_files or {}).items():
        (d / name).write_text(content)
        manifest['outputs'][name] = sha256_file(d / name)
    (d / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
    (d / 'README.md').write_text(readme.strip() + '\n')
    return d


def _np_default(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(type(o))


def longest_run(flags, dt_h=1.0):
    """Longest run of False in a boolean hourly series, in hours (samples x dt)."""
    best = cur = 0
    for f in flags:
        cur = 0 if f else cur + 1
        best = max(best, cur)
    return best * dt_h
