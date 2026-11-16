"""Phase 9.3 — launch-window calendar (schedule view), SOURCE-BASED · UNVALIDATED.

  python -m science.cube.build_calendar [site ...]

Every start date (365 days from 2026-11-14 00:00 UTC) x arrival slip (0..23 h after 00:00 UTC that day), colour =
k of 20 clone maps passing all of a requirement preset R for the 14-day window that starts then. This is a re-indexing
of centre_mast_schedule derived.k_of_N (hourly starts): start index = 24*day + slip. Plus the nominal-map verdict.
Writes data/cubes/<site>/launch_calendar.json.gz: D_mast(10) x R(3) x day(365) x slip_h(24).
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import sys

import numpy as np

from . import compute as C
from .build_cube import LABEL, NOT_PROB, OUT, R_PRESETS, _gz
from .build_visibility import add_to_index
from ..limits.common import git_commit, sha256_file

N_DAYS = 365


def build(site):
    src = OUT / site / 'centre_mast_schedule.json.gz'
    c = json.loads(gzip.decompress(src.read_bytes()))
    nS = len(c['dims'][2]['values'])
    k = np.array(c['derived']['k_of_N']['metrics']['k_pass']['values']).reshape(len(R_PRESETS), len(C.MASTS), nS)
    nom = np.array(c['derived']['k_of_N']['metrics']['nominal_pass']['values']).reshape(len(R_PRESETS), len(C.MASTS), nS)
    k = k[:, :, :N_DAYS * 24].reshape(len(R_PRESETS), len(C.MASTS), N_DAYS, 24).transpose(1, 0, 2, 3)
    nom = nom[:, :, :N_DAYS * 24].reshape(len(R_PRESETS), len(C.MASTS), N_DAYS, 24).transpose(1, 0, 2, 3)
    t0 = c['dims'][2]['values'][0]
    days = [dt.datetime.fromtimestamp(t0 + 86400 * d, dt.timezone.utc).strftime('%Y-%m-%d') for d in range(N_DAYS)]
    dims = [next(d for d in c['dims'] if d['name'] == 'D_mast'),
            {'name': 'R', 'kind': 'requirement', 'values': [r['id'] for r in R_PRESETS], 'value_labels': [r['label'] for r in R_PRESETS],
             'units': '', 'label': 'Requirement preset', 'nominal_index': 0},
            {'name': 'S_day', 'kind': 'schedule', 'values': days, 'units': 'UTC date', 'label': 'Start date', 'nominal_index': 0},
            {'name': 'S_slip', 'kind': 'schedule', 'values': list(range(24)), 'units': 'h', 'label': 'Arrival slip (hours after 00:00 UTC)', 'nominal_index': 0}]
    return {'schema': 'scenario-cube-v1', 'cube_id': f'{site}-launch-calendar-v1', 'site_id': site,
            'title': 'Launch-window calendar: start date x arrival slip', 'label': LABEL,
            'generated_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'description': 'k of 20 clone maps on which the 14-day window starting at that date and hour passes all of R.',
            'fixed': {'position': 'bundle site', 'window_h': 336},
            'dims': dims,
            'metrics': {'k_pass': {'units': 'maps of 20', 'label': 'Clone maps passing all of R', 'dtype': 'int32', 'decimals': 0,
                                   'values': k.reshape(-1).astype(int).tolist(), 'provenance': 'centre_mast_schedule derived.k_of_N, re-indexed'},
                        'nominal_pass': {'units': '', 'label': 'Nominal map passes all of R', 'dtype': 'bool',
                                         'values': nom.reshape(-1).astype(bool).tolist(), 'provenance': 'centre_mast_schedule derived.k_of_N'}},
            'missing': {'encoding': 'sparse-flat-index', 'by_metric': {'k_pass': [], 'nominal_pass': []}},
            'provenance': {'inputs': [{'path': str(src.relative_to(OUT.parents[1])), 'sha256': sha256_file(src), 'note': 'parent cube'}],
                           'command': 'python -m science.cube.build_calendar ' + ' '.join(sys.argv[1:]), 'code_commit': git_commit(),
                           'solver': 're-indexing only'},
            'limitations': [NOT_PROB, 'Start index = 24 x day + slip; the last hourly start (2027-11-14 00:00) is not shown.']}


def write(site):
    cube = build(site)
    p = OUT / site / 'launch_calendar.json.gz'
    raw = _gz(p, cube)
    add_to_index(site, [{'file': p.name, 'cube_id': cube['cube_id'], 'title': cube['title'], 'bytes': p.stat().st_size,
                         'uncompressed_bytes': raw, 'sha256': sha256_file(p), 'dims': [d['name'] for d in cube['dims']]}])
    return cube


if __name__ == '__main__':
    for s in sys.argv[1:] or ['site04_roi3', 'site01_roi6']:
        c = write(s)
        k = np.array(c['metrics']['k_pass']['values']).reshape(10, 3, N_DAYS, 24)
        print(s, 'days with an all-20 hour (1 m, team):', int((k[0, 0] == 20).any(axis=1).sum()), 'of', N_DAYS)
