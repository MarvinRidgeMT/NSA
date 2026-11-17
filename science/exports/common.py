"""Shared helpers for exports: file hashing, JSON paths, reproduce commands, labels.

Exports only READ precomputed files. Every exported number is a `Number` record: value, unit, label, source file,
its SHA-256, a JSON path into it and two one-line commands -- `read` prints the value from the file, `recompute`
rebuilds the file (the file's own provenance command).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EXPORT_VERSION = 'polaris-exports-1'
LABEL = 'SOURCE-BASED · UNVALIDATED'
ENGINEERING = 'ENGINEERING ASSUMPTION'
K_OF_N = 'k of N maps is not a probability'
GEOMETRY_ONLY = ('Local geometric visibility only: not certified illumination, power, or DSN link availability.')
PY = 'python'   # commands are written for the repository's venv python, run from the repository root


def rel(p) -> str:
    """Path relative to the repository root when inside it (exports and commands never carry home directories)."""
    a = Path(os.path.abspath(p))               # no symlink resolution: data/cache may be a link to another checkout
    for base in (ROOT, ROOT.resolve()):
        try:
            return str(a.relative_to(base))
        except ValueError:
            pass
    return str(a)


def sha256_file(p) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read_json(p) -> Any:
    raw = Path(p).read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)


def git_commit() -> dict:
    try:
        from .. import gitinfo       # posix_spawn, no fork (see science/gitinfo.py)
        return {'commit': gitinfo.head(), 'science_dirty': gitinfo.porcelain_dirty('science')}
    except Exception:  # noqa: BLE001
        return {'commit': 'unknown', 'science_dirty': None}


_TOK = re.compile(r'\.?([A-Za-z_][\w\-]*)|\[(\d+)\]|\["([^"]+)"\]')


def parse_path(path: str) -> list:
    out, pos = [], 0
    while pos < len(path):
        m = _TOK.match(path, pos)
        if not m or m.end() == pos:
            raise ValueError(f'bad JSON path {path!r} at {pos}')
        out.append(int(m.group(2)) if m.group(2) is not None else (m.group(1) or m.group(3)))
        pos = m.end()
    return out


def json_get(obj, path: str):
    for k in parse_path(path):
        obj = obj[k]
    return obj


def read_cmd(file, path: str) -> str:
    return f"{PY} -m science.exports value {rel(file)} '{path}'"


def number(name, value, unit, label, file, path, recompute, sha=None, note=None) -> dict:
    d = {'name': name, 'value': value, 'unit': unit, 'label': label, 'source_file': rel(file),
         'source_sha256': sha or sha256_file(file), 'json_path': path, 'read': read_cmd(file, path),
         'recompute': recompute}
    if note:
        d['note'] = note
    return d


def write_json(p, obj):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + '\n')
    return p
