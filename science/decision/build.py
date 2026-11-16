"""Write data/cubes/<site>/decision6d.json (scenario-cube-v2): robust choice, regret, VoI per question, plus the landing
search and Pareto results when their runs exist (docs/v2/PHASE_3_DECISION_PLAN.md §2–4).

  python -m science.decision.build [site ...]

Reads the committed cubes (never writes them), the Pareto run (science/decision/pareto.py) and the landing search
(science/decision/landing.py) from data/cache/decision/. Missing runs are recorded in `limitations`, never filled.
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from ..cube import v2
from . import questions as Q
from .core import TIE_RULES, Axis, analyse

ROOT = Q.ROOT
RUNS = ROOT / 'data' / 'cache' / 'decision'
SITES = ('site04_roi3', 'site01_roi6')
FILE = 'decision6d.json'
NOT_PROB = ('k of N maps is not a probability: the 20 PGDA 78 clones are deterministic alternates with no weights. '
            'Counts are never combined across axes or questions.')
WORST_NOTE = ('"Worst" is the worst of the listed members (nominal + 20 PGDA 78 error clones), a stress test over this '
              'scenario set, not a bound over all possible terrain.')


def _commit() -> str:
    try:
        sha = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(['git', 'status', '--porcelain', '--', 'science/decision'], cwd=ROOT, capture_output=True,
                               text=True).stdout.strip()
        return sha + ('-dirty' if dirty else '')
    except OSError:
        return 'unknown'


def _r(v, nd=6):
    return None if v is None else round(float(v), nd)


def metric(units, label, values, prov, dtype='float64', decimals=None, description=None):
    m = {'units': units, 'label': label, 'dtype': dtype, 'values': values, 'provenance': prov}
    if decimals is not None:
        m['decimals'] = decimals
    if description:
        m['description'] = description
    return m


def inline_dim(name, kind, role, values, labels, label, units='', nominal=None, note=None):
    d = {'name': name, 'kind': kind, 'role': role, 'values': values, 'value_labels': labels, 'units': units, 'label': label}
    if nominal is not None:
        d['nominal_index'] = int(nominal)
    if note:
        d['note'] = note
    return d


def x_dim(tb):
    names = [d['name'] for d in tb['x_dims']]
    kind = tb['x_dims'][0]['kind'] if len(tb['x_dims']) == 1 else 'uncertainty_terrain'
    return inline_dim('X', kind, 'uncertainty', list(range(len(tb['x_labels']))), tb['x_labels'],
                      f'What we don\'t know: {" × ".join(names)}', nominal=tb['nominal_x'],
                      note=f'members of {" × ".join(names)} from the source cube, row-major')


def l_dim(tb):
    names = [d['name'] for d in tb['l_dims']]
    return inline_dim('L', 'design', 'decision', list(range(len(tb['l_labels']))), tb['l_labels'],
                      f'What we choose: {" × ".join(names)}', nominal=tb['nominal_l'],
                      note=f'options of {" × ".join(names)} from the source cube, row-major')


def question_blocks(qid, q, tb, r, src_file, src_sha, label):
    nd = 6
    units = tb['units']
    dec = tb['decimals'] if isinstance(tb['decimals'], int) else 2
    prov = f'data/cubes/<site>/{src_file} (sha256 {src_sha[:16]}…) {q.metric}; science/decision/core.py'
    fixed_txt = ', '.join(f'{k} = {v}' for k, v in tb['fixed_labels'].items()) or 'none'
    red = ', '.join(f'unweighted mean over {k}' for k in q.reduce)
    method = (f'X x L table of {q.metric} from {src_file} with {fixed_txt}' + (f'; {red}' if red else '') +
              f'. Sense: {"higher" if q.sense == "max" else "lower"} is better. Robust = best worst-case over X; '
              f'regret(x, l) = best option under x minus option l under x (>= 0). Tie rules: robust {TIE_RULES["robust"]}; '
              f'nominal {TIE_RULES["nominal"]}.')
    caveat = f'{label}. {WORST_NOTE} {NOT_PROB}'
    X, L = x_dim(tb), l_dim(tb)
    vals = r['values']; R = r['regret']
    blocks = {}
    blocks[f'q__{qid}__table'] = {'dims': [X, L], 'method': method, 'caveat': caveat, 'metrics': {
        'value': metric(units, tb['metric_label'], [_r(v, nd) for v in vals.reshape(-1)], prov, decimals=dec),
        'regret': metric(units, 'Regret: best option under this member minus this option', [_r(v, nd) for v in R.reshape(-1)],
                         'science/decision/core.py regret_matrix', decimals=dec),
        'source_flat_index': metric('index', 'Flat index of the source cell in ' + src_file,
                                    [None if v is None else int(v) for row in tb['source_flat_index'] for v in row],
                                    f'{src_file} row-major flat index; null = cell is a reduction ({red or "none"})',
                                    dtype='int32')}}
    by_choice = {
        'worst_over_x': metric(units, 'Worst over the listed members', [_r(v) for v in r['worst_by_choice']], prov, decimals=dec),
        'best_over_x': metric(units, 'Best over the listed members', [_r(v) for v in r['best_by_choice']], prov, decimals=dec),
        'nominal_value': metric(units, 'On the nominal map', [_r(v) for v in r['nominal_by_choice']], prov, decimals=dec),
        'max_regret': metric(units, 'Max regret over the listed members', [_r(v) for v in r['max_regret_by_choice']],
                             'science/decision/core.py', decimals=dec),
        'mean_regret_unweighted': metric(units, 'Unweighted mean regret over the listed members (not an expectation)',
                                         [_r(v) for v in r['mean_regret_by_choice']], 'science/decision/core.py', decimals=dec),
    }
    if 'requirement' in r:
        req = r['requirement']
        by_choice['k_members_meeting'] = metric(f'members of {r["n_x"]}', f'Members meeting: {q.threshold_text}',
                                                req['k_members_meeting'], 'count over X', dtype='int32', decimals=0,
                                                description=NOT_PROB)
    blocks[f'q__{qid}__by_choice'] = {'dims': [L], 'method': method, 'caveat': caveat, 'metrics': by_choice}
    blocks[f'q__{qid}__by_member'] = {'dims': [X], 'method': 'per member of X: the best option if this member were known '
                                      'to be the truth (ties -> the robust choice) and the regret of the nominal and robust '
                                      'choices under it', 'caveat': caveat, 'metrics': {
        'best_choice_if_known': metric('index into L', 'Best option if this member were the truth', r['best_if_known'],
                                       'science/decision/core.py', dtype='int32'),
        'regret_of_nominal_choice': metric(units, 'Regret of the nominal-map choice under this member',
                                           [_r(v) for v in r['regret_of_nominal_choice']], 'science/decision/core.py', decimals=dec),
        'regret_of_robust_choice': metric(units, 'Regret of the robust choice under this member',
                                          [_r(v) for v in r['regret_of_robust_choice']], 'science/decision/core.py', decimals=dec)}}
    voi = r['voi']
    A = inline_dim('A', 'uncertainty_terrain', 'uncertainty', [v['axis'] for v in voi],
                   [('every member resolved (perfect information)' if v['axis'] == 'all' else f'resolve {v["axis"]}') for v in voi],
                   'Uncertainty resolved', note='resolving an axis = learning which of its values is the truth')
    blocks[f'q__{qid}__voi'] = {'dims': [A], 'method': (
        'Non-probabilistic value of information: for each value v of the resolved axis, the robust choice over the '
        'members with that value, L*(v); gain(v) = worst over those members of m(., L*(v)) minus that of the unresolved '
        'robust choice (>= 0). k = values with gain > 0. For a single uncertainty axis, resolving it = perfect information.'),
        'caveat': caveat + ' No expected value of information: the members have no weights.', 'metrics': {
            'k_values_choice_changes': metric('values', 'Values of the axis where knowing it changes the choice',
                                              [v['k_values_choice_changes'] for v in voi], 'science/decision/core.py',
                                              dtype='int32', description=NOT_PROB),
            'n_values': metric('values', 'Values on the axis', [v['n_values'] for v in voi], 'axis size', dtype='int32'),
            'max_gain': metric(units, 'Largest worst-case gain from knowing the axis', [_r(v['max_gain']) for v in voi],
                               'science/decision/core.py', decimals=dec),
            'mean_gain_unweighted': metric(units, 'Unweighted mean gain over the axis values (not an expectation)',
                                           [_r(v['mean_gain_unweighted']) for v in voi], 'science/decision/core.py', decimals=dec)}}
    summ = {
        'robust_worst': metric(units, 'Worst-case value of the robust choice', [_r(r['robust_worst'])], prov, decimals=dec),
        'nominal_choice_worst': metric(units, 'Worst-case value of the nominal-map choice', [_r(r['nominal_choice_worst'])],
                                       prov, decimals=dec),
        'nominal_choice_nominal_value': metric(units, 'Nominal-map value of the nominal-map choice',
                                               [_r(r['nominal_choice_nominal_value'])], prov, decimals=dec),
        'max_regret_nominal_choice': metric(units, 'Max regret of choosing on the nominal map',
                                            [_r(r['max_regret_nominal_choice'])], 'science/decision/core.py', decimals=dec),
        'mean_regret_nominal_choice': metric(units, 'Unweighted mean regret of choosing on the nominal map (not an expectation)',
                                             [_r(r['mean_regret_nominal_choice'])], 'science/decision/core.py', decimals=dec),
        'max_regret_robust_choice': metric(units, 'Max regret of the robust choice', [_r(r['max_regret_robust_choice'])],
                                           'science/decision/core.py', decimals=dec),
        'minimax_regret': metric(units, 'Max regret of the minimax-regret choice', [_r(r['minimax_regret'])],
                                 'science/decision/core.py', decimals=dec),
    }
    if 'requirement' in r:
        req = r['requirement']
        summ['threshold'] = metric(units, q.threshold_text, [req['threshold']], 'requirement preset (filter, not optimised)')
        if q.ordered:
            summ['first_meeting_all'] = metric('index into L', 'Cheapest option meeting the requirement on every member',
                                               [req['first_meeting_all']], 'science/decision/core.py requirement_screen', dtype='int32')
            summ['first_meeting_nominal'] = metric('index into L', 'Cheapest option meeting it on the nominal map',
                                                   [req['first_meeting_nominal']], 'science/decision/core.py requirement_screen',
                                                   dtype='int32')
    blocks[f'q__{qid}__summary'] = {'dims': [], 'method': method, 'caveat': caveat, 'metrics': summ}
    return blocks


def _meta(q, tb, src_file, src_sha, label, kind='cube'):
    return {'id': q.id, 'text': q.text, 'kind': kind, 'source_file': src_file, 'source_sha256': src_sha,
            'metric': q.metric, 'measure': tb['metric_label'], 'units': tb['units'], 'sense': q.sense, 'label': label,
            'x_axes': [d['name'] for d in tb['x_dims']], 'l_axes': [d['name'] for d in tb['l_dims']],
            'fixed': tb['fixed_labels'], 'reduce': q.reduce, 'threshold': q.threshold, 'threshold_text': q.threshold_text,
            'ordered': q.ordered}


def build(site: str) -> dict:
    qmeta, qrows, derived, inputs, lims = [], [], {}, {}, []
    for q in Q.QUESTIONS:
        cube, sha = Q.load(site, q.file)
        tb = Q.table(cube, q)
        axes = [Axis(d['name'], len(d['values'])) for d in tb['x_dims']]
        r = analyse(tb['values'], q.sense, tb['nominal_x'], tb['nominal_l'], axes=axes, threshold=q.threshold)
        label = q.label
        derived.update(question_blocks(q.id, q, tb, r, q.file, sha, label))
        qmeta.append(_meta(q, tb, q.file, sha, label))
        qrows.append(r)
        inputs[q.file] = sha
    extra = {}
    for name, mod in (('pareto', 'pareto'), ('landing', 'landing')):
        p = RUNS / f'{site}_{name}.json'
        if p.exists():
            run = json.loads(p.read_text())
            from importlib import import_module
            m = import_module(f'science.decision.{mod}')
            got = m.to_blocks(site, run)
            derived.update(got['blocks'])
            for item in got.get('questions', []):
                derived.update(item['blocks'])
                qmeta.append(item['meta']); qrows.append(item['analysis'])
            extra[name] = got.get('summary', {})
            inputs[str(p.relative_to(ROOT))] = Q.sha256_of(p)
        else:
            lims.append(f'{name} run not present ({p.relative_to(ROOT)}): not computed for this site')
    n = len(qmeta)
    qdim = {'name': 'Q', 'kind': 'target', 'role': 'context', 'values': [m['id'] for m in qmeta],
            'value_labels': [m['text'] for m in qmeta], 'units': '', 'label': 'Decision question', 'nominal_index': 0,
            'role_note': 'question selector (context): picks which X x L table is shown; never optimised or stressed over',
            'note': json.dumps(qmeta, ensure_ascii=False)}
    P = 'science/decision/core.py analyse'
    metrics = {
        'robust_choice_index': metric('index into L', 'Robust choice (best worst case over X)',
                                      [r['robust_choice'] for r in qrows], P, dtype='int32'),
        'nominal_choice_index': metric('index into L', 'Choice made on the nominal map alone',
                                       [r['nominal_choice'] for r in qrows], P, dtype='int32'),
        'minimax_regret_choice_index': metric('index into L', 'Minimax-regret choice',
                                              [r['minimax_regret_choice'] for r in qrows], P, dtype='int32'),
        'n_tied_robust': metric('options', 'Options tied for the robust choice', [len(r['robust_tied']) for r in qrows], P,
                                dtype='int32'),
        'n_x_members': metric('members', 'Listed members of X', [r['n_x'] for r in qrows], P, dtype='int32'),
        'n_l_options': metric('options', 'Options in L', [r['n_l'] for r in qrows], P, dtype='int32'),
        'k_members_choice_changes': metric('members', 'Members under which a different option beats the robust choice',
                                           [r['k_members_choice_changes'] for r in qrows], P, dtype='int32',
                                           description=NOT_PROB),
        'robust_equals_nominal': metric('', 'Robust choice equals the nominal-map choice',
                                        [bool(r['robust_equals_nominal']) for r in qrows], P, dtype='bool'),
    }
    cube = {
        'schema': v2.V2, 'cube_id': f'{site}_decision6d', 'site_id': site, 'world': 'moon',
        'title': f'6D decision tools: robust choice, regret, value of information ({site})',
        'label': 'SOURCE-BASED · UNVALIDATED (geometry) · ENGINEERING ASSUMPTION (energy, link) — per question in Q.note',
        'generated_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'description': ('One row per decision question (Q). X = what we don\'t know (listed uncertainty members), '
                        'L = what we choose. Per question: q__<id>__table (X x L values and regret), __by_choice, '
                        '__by_member, __voi, __summary. Landing search: landing__<R>__*. Pareto view: pareto__*. '
                        'docs/v2/PHASE_3_DECISION_PLAN.md.'),
        'fixed': {'world': 'moon'},
        'dims': [qdim], 'metrics': metrics,
        'missing': {'encoding': 'sparse-flat-index', 'by_metric': {}},   # missing source cells are refused, never filled
        'derived': derived,
        'provenance': {'inputs': [{'path': f'data/cubes/{site}/{f}' if '/' not in f else f, 'sha256': s,
                                   'note': 'read only; values copied x stored scale'} for f, s in inputs.items()],
                       'command': f'python -m science.decision.build {site}', 'code_commit': _commit(),
                       'solver': 'science/decision (display-free Python); no new terrain or ephemeris computed here'},
        'limitations': [WORST_NOTE, NOT_PROB,
                        'No expected value of information: the clones carry no weights; "mean" means unweighted mean over the listed members.',
                        'Questions hold every other decision axis at the stated value (start date 2026-11-14 unless "12 months").',
                        'Geometric line of sight only; energy and link are ENGINEERING ASSUMPTION models.'] + lims,
    }
    if extra:
        cube['description'] += ' Summaries: ' + json.dumps(extra, ensure_ascii=False)
    return cube


def check_provenance_block(cube):
    v2.validate_v2(cube)
    return True


def write(site: str) -> Path:
    cube = build(site)
    v2.validate_v2(cube)
    p = Q.CUBES / site / FILE
    p.write_text(json.dumps(cube, ensure_ascii=False, separators=(',', ':')))
    return p


def main(argv=None):
    for s in (argv if argv is not None else sys.argv[1:]) or SITES:
        p = write(s)
        print(f'wrote {p.relative_to(ROOT)} ({p.stat().st_size / 1024:.0f} kB)')


if __name__ == '__main__':
    main()
