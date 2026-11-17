"""Gate: label audit (docs/SCIENCE_LABEL_AUDIT.md rules) + traceability of every NEW number (T1 exports and API).

  .venv/bin/python web/scripts/gates/label_audit.py      # from the repository root; exit 1 on any violation

1. Traceability: every record in data/exports/**/numbers.json carries label, source file, SHA-256, JSON path, read and
   recompute commands, and its read path returns the exported value from the (unchanged) source file. The exports are
   rebuilt first (python -m science.exports site/grid/bundle) so the scan covers the current code.
2. Labels on API output: every solve result and site list carries the SOURCE-BASED · UNVALIDATED label and the
   geometric-only disclaimer; the tool spec carries the grounding rule and AI-GENERATED.
3. Wording: phrases the audit retired or forbids (probability for k of N, "equally plausible", unqualified "validated" /
   "certified", NASA accuracy) in T1 text (exports, API, docs, PDF text, decision summaries) and in web/src (read only).
Writes docs/v2/gates/labels-<date>.json.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from science.api.service import Service  # noqa: E402
from science.api import spec as S  # noqa: E402
from science.exports import bundle_export as E, card, common as C, pdf  # noqa: E402

FORBIDDEN = [
    (r'equally plausible', 'retired wording (SCIENCE_LABEL_AUDIT.md)'),
    (r'(?<!not a )(?<!not )\bprobabilit(?:y|ies)\b(?! ?(?:is|are)? ?not)', 'k of N maps / scenario counts called a probability'),
    (r'\bchance of\b|\b\d+ ?% likely\b|\blikelihood\b', 'probability language'),
    (r'(?<![Uu]n)(?<!not )(?<!NOT )(?<!never )\bvalidated\b(?! ?by)(?!_)', 'unqualified "validated"'),
    (r'(?<!not )(?<!not\n)\bcertified\b', 'unqualified "certified"'),
    (r'NASA[- ]accura', 'NASA accuracy claim'),
    (r'\b19 h of Sun lost\b|\b20 alternate NASA terrain maps\b', 'retired wording (SCIENCE_LABEL_AUDIT.md)'),
]
# lines that state the rule itself / quote the forbidden phrase on purpose
ALLOW = re.compile(r'not a probability|not calibrated probabilit|not probabilistically|not certified|never .*validated|'
                   r'UNVALIDATED|unvalidated|validation_status|VALIDATED_NASA_JPL|VALIDATED\'|\'VALIDATED|"VALIDATED"|'
                   r'validated against|independently validated|Not independently validated|FORBIDDEN|retired wording|'
                   r'is not validated|are not validated|not yet validated|until .* validated|validated NASA|LabelValue|'
                   r'probability language|called a probability|calibrated|never a probability|never probabilities|'
                   r'not[- ]validated|Not validated yet', re.I)
# reviewed one-off exceptions (file:line text -> why it is not a science claim)
EXCEPTIONS = {'web/src/store/surface.ts': ('file (validated)', 'the visual-layers JSON file passed its schema check; not a '
                                                               'statement about science accuracy')}


def rebuild_exports():
    py = sys.executable
    cmds = [['site', 'site04_roi3'], ['site', 'site01_roi6'], ['grid'],
            ['bundle', 'data/worlds/mercury/mercury_prokofiev_rim_2026-11-14_176d_mast1m.json'],
            ['anysite', '--lat', '-89.78012', '--lon', '-156.32023']]
    out = []
    for c in cmds:
        r = subprocess.run([py, '-m', 'science.exports', *c], cwd=ROOT, capture_output=True, text=True)
        out.append({'cmd': ' '.join(c), 'rc': r.returncode, 'out': (r.stdout or r.stderr).strip()[-300:]})
    return out


def traceability():
    files = sorted((ROOT / 'data' / 'exports').rglob('numbers.json'))
    n, bad, cache = 0, [], {}
    for f in files:
        for x in C.read_json(f)['numbers']:
            n += 1
            miss = [k for k in ('label', 'source_file', 'source_sha256', 'json_path', 'read', 'recompute') if not x.get(k)]
            if miss:
                bad.append({'file': C.rel(f), 'name': x.get('name'), 'missing': miss}); continue
            src = ROOT / x['source_file']
            if src not in cache:
                cache[src] = (C.read_json(src), C.sha256_file(src))
            doc, sha = cache[src]
            if sha != x['source_sha256']:
                bad.append({'file': C.rel(f), 'name': x['name'], 'error': 'source changed since export'}); continue
            if C.json_get(doc, x['json_path']) != x['value']:
                bad.append({'file': C.rel(f), 'name': x['name'], 'error': 'read value differs'})
    return {'files': [C.rel(f) for f in files], 'numbers_scanned': n, 'failed': bad}


def api_labels():
    svc = Service(cache_dir=ROOT / 'data' / 'cache' / 'api_gate')
    bad = []
    _, sites = svc.sites(limit=5000)
    if sites['label'] != C.LABEL:
        bad.append('site list label')
    checked = 0
    for s in sites['sites'][:: max(1, len(sites['sites']) // 40)]:
        if not s['bundle_cached']:
            continue
        _, r = svc.site(s['site_hash'])
        checked += 1
        if r['label'] != C.LABEL or 'not certified' not in r['disclaimer']:
            bad.append(f'site {s["site_hash"]}: label/disclaimer')
        for k, m in r['metrics'].items():
            if m['label'] != C.LABEL:
                bad.append(f'site {s["site_hash"]}: metric {k} label')
    t = json.dumps(S.TOOLS)
    for need in ('AI-GENERATED', 'not a probability', 'no AI planner'):
        if need not in t:
            bad.append(f'tool spec lacks "{need}"')
    if 'not a probability' not in S.OPENAPI['info']['description']:
        bad.append('OpenAPI description lacks "not a probability"')
    return {'results_checked': checked, 'failed': bad}


def texts():
    """(source, text) pairs to scan for wording."""
    t1 = [p for p in list((ROOT / 'science' / 'exports').rglob('*.py')) + list((ROOT / 'science' / 'api').rglob('*.py'))
          if '/tests/' not in str(p)]
    t1 += [ROOT / 'docs/v2/API.md', ROOT / 'docs/v2/openapi.yaml', ROOT / 'docs/v2/tool_spec.json']
    t1 += sorted((ROOT / 'data' / 'cubes').glob('*/decision_summary.json'))
    for p in t1:
        yield 't1', C.rel(p), p.read_text()
    for site in ('site04_roi3', 'site01_roi6'):
        yield 't1', f'Decision Card PDF {site}', '\n'.join(pdf.extract_text(card.render(site)[0]))
    for p in sorted((ROOT / 'web' / 'src').rglob('*.ts*')):
        if '.test.' in p.name:
            continue
        yield 'web', C.rel(p), p.read_text()


def wording():
    hits = {'t1': [], 'web': []}
    for scope, name, text in texts():
        lines = text.splitlines()
        for i, line in enumerate(lines, 1):
            prev = lines[i - 2][-40:] if i > 1 else ''          # a phrase broken across a line ("not a" / "probability")
            if ALLOW.search(prev + ' ' + line):
                continue
            ex = EXCEPTIONS.get(name)
            if ex and ex[0] in line:
                continue
            for pat, why in FORBIDDEN:
                if re.search(pat, line, re.I if 'validated' not in pat and 'certified' not in pat else 0):
                    hits[scope].append({'where': f'{name}:{i}', 'rule': why, 'text': line.strip()[:160]})
    return hits


def main():
    rb = rebuild_exports()
    tr = traceability(); api = api_labels(); w = wording()
    ok = (all(r['rc'] == 0 for r in rb) and not tr['failed'] and not api['failed'] and not w['t1'] and not w['web'])
    out = {'schema': 'polaris-gates-labels-v1', 'measuredUTC': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'pass': ok, 'exports_rebuilt': rb, 'traceability_new_numbers': tr, 'api_labels': api,
           'wording': {'t1_violations': w['t1'], 'web_src_violations': w['web']},
           'rules': [why for _, why in FORBIDDEN]}
    d = ROOT / 'docs' / 'v2' / 'gates'; d.mkdir(parents=True, exist_ok=True)
    f = d / f'labels-{out["measuredUTC"][:10]}.json'
    f.write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n')
    print(json.dumps({'pass': ok, 'numbers_scanned': tr['numbers_scanned'], 'trace_failed': len(tr['failed']),
                      'api_results_checked': api['results_checked'], 'api_failed': api['failed'],
                      't1_wording': len(w['t1']), 'web_wording': len(w['web'])}, indent=1))
    for h in (w['t1'] + w['web'])[:30]:
        print(' ', h['where'], '|', h['rule'], '|', h['text'])
    print('wrote', C.rel(f))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
