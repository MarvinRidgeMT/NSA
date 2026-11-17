"""Git provenance must not fork (science/gitinfo.py): a fork while another thread is inside PROJ/SQLite crashed the
child on macOS and the API recorded `unknown` as the commit. With subprocess's fork path disabled, every helper the
solver, the exports and the API use must still return the real commit."""
from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from science import bundle, gitinfo
from science.exports import common as C
from science.limits import common as L


def _no_fork(*a, **k):
    raise AssertionError('fork_exec used: git provenance must go through posix_spawn (science/gitinfo.py)')


@unittest.skipUnless(subprocess._USE_POSIX_SPAWN, 'posix_spawn not used by subprocess on this platform')
class NoFork(unittest.TestCase):
    def setUp(self):
        self.ref = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=gitinfo.ROOT, text=True).strip()

    def test_helpers_work_without_fork(self):
        with mock.patch.object(subprocess, '_fork_exec', _no_fork):
            self.assertEqual(gitinfo.head(), self.ref)
            self.assertIsInstance(gitinfo.porcelain_dirty('science'), bool)
            self.assertIsInstance(gitinfo.diff_dirty('science'), bool)
            self.assertTrue(bundle._git().startswith(self.ref), bundle._git())
            self.assertTrue(L.git_commit().startswith(self.ref))
            self.assertEqual(C.git_commit()['commit'], self.ref)

    def test_dirty_flags_match_git(self):
        porcelain = bool(subprocess.check_output(['git', 'status', '--porcelain', '--', 'science'], cwd=gitinfo.ROOT,
                                                 text=True).strip())
        diff = subprocess.call(['git', 'diff', '--quiet', 'HEAD', '--', 'science'], cwd=gitinfo.ROOT) != 0
        self.assertEqual(gitinfo.porcelain_dirty('science'), porcelain)
        self.assertEqual(gitinfo.diff_dirty('science'), diff)

    def test_failure_is_an_error_not_a_value(self):
        with mock.patch.object(gitinfo, 'git', return_value=subprocess.CompletedProcess([], 128, '', 'fatal')):
            with self.assertRaises(RuntimeError):
                gitinfo.head()
            self.assertEqual(bundle._git(), 'unknown')          # callers keep their documented fallback


if __name__ == '__main__':
    unittest.main()
