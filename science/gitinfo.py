"""Git provenance (commit + dirty flag) without fork().

The any-site solver and the threaded API server (science/api/server.py) call git while another thread may be inside
PROJ/SQLite (rasterio). A fork() then runs PROJ's pthread_atfork child handler, which closes cached SQLite handles and
crashes the child on macOS (SIGSEGV in os_log; "Python quit unexpectedly"); the parent then recorded `unknown` as the
commit (reproduced: 11 crashes in 2,668 health probes during 4 solves, 17 Nov 2026). posix_spawn runs no atfork handlers,
so every git call goes through it: absolute git path, `git -C` instead of `cwd`, `close_fds=False` (Python's own fds
are non-inheritable, PEP 446), which are CPython's conditions for using posix_spawn in subprocess.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which('git') or '/usr/bin/git'


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([GIT, '-C', str(ROOT), *args], capture_output=True, text=True, close_fds=False,
                          stdin=subprocess.DEVNULL)


def head() -> str:
    r = git('rev-parse', 'HEAD')
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f'git rev-parse failed ({r.returncode}): {r.stderr.strip()}')
    return r.stdout.strip()


def porcelain_dirty(path: str = 'science') -> bool:
    """`git status --porcelain -- path` non-empty (tracked changes or untracked files)."""
    r = git('status', '--porcelain', '--', path)
    if r.returncode != 0:
        raise RuntimeError(f'git status failed ({r.returncode}): {r.stderr.strip()}')
    return bool(r.stdout.strip())


def diff_dirty(path: str = 'science') -> bool:
    """`git diff --quiet HEAD -- path` reports a change (tracked files only)."""
    r = git('diff', '--quiet', 'HEAD', '--', path)
    if r.returncode not in (0, 1):
        raise RuntimeError(f'git diff failed ({r.returncode}): {r.stderr.strip()}')
    return r.returncode == 1
