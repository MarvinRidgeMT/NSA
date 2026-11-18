"""Run the Kaguya TC dev pilot (A11.5, A12) while the project owner's downloads arrive.

    python -m tools.validation.render_vs_real.tc_pilot [--workers 4 --threads 4] [--idle-minutes 60]

Each round: rows of selection.json whose label and image are both complete in incoming/ or the cache (not still being
written by curl, gzip intact) get geometry (tc_geometry.one, A12 conventions), merged into results_tc/geometry.csv;
then tc_run renders and scores every geometry-OK row not yet scored (resumable; rows already scored are never
re-scored). It waits 10 minutes when nothing new is ready and stops when every row has geometry, or after
--idle-minutes without a new ready row. Rows never downloaded or damaged stay out of geometry.csv and are reported.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import time
import traceback

from . import tc_geometry as TG
from . import tc_run
from .common import check_frozen, read_catalogue
from .tc_common import TC_RESULTS, guard
from .tc_io import INCOMING, TC_DIR, gzip_problem


def _find(name, sub):
    p = TC_DIR / sub / name
    if p.exists():
        return p
    hits = sorted(INCOMING.rglob(name)) if INCOMING.exists() else []
    return hits[0] if hits else None


def ready(pid, busy):
    lbl, img = _find(f'{pid}.lbl', 'labels'), _find(f'{pid}.img.gz', 'img')
    if lbl is None or img is None or f'{pid}.' in busy:
        return False, 'not downloaded' if (lbl is None or img is None) else 'downloading'
    if img.parent != TC_DIR / 'img':
        why = gzip_problem(img)
        if why:
            return False, why
    return True, ''


def _read_geo():
    p = TC_RESULTS / 'geometry.csv'
    return {(r['product_id'], r['site']): r for r in csv.DictReader(open(p))} if p.exists() else {}


def _write_geo(rows):
    with open(TC_RESULTS / 'geometry.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=TG.FIELDS + ['tag'], extrasaction='ignore')
        w.writeheader()
        for r in rows.values():
            w.writerow(r)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--idle-minutes', type=float, default=60)
    a = ap.parse_args(argv)
    check_frozen()
    cat_rows = read_catalogue()
    cat = {(r['product_id'], r['site']): r for r in cat_rows}
    sel = json.loads((TC_RESULTS / 'selection.json').read_text())
    todo = [(im, s) for im in sel['images'] for s in im['sites']]
    guard([im['product_id'] for im, _ in todo], cat_rows)
    last_new = time.time()
    while True:
        busy = subprocess.run(['pgrep', '-fl', 'curl'], capture_output=True, text=True).stdout
        geo = _read_geo()
        new, waiting = 0, {}
        for im, site in todo:
            if (im['product_id'], site) in geo:
                continue
            ok, why = ready(im['product_id'], busy)
            if not ok:
                waiting[why[:40]] = waiting.get(why[:40], 0) + 1
                continue
            try:
                rec = TG.one(im, site, cat[(im['product_id'], site)])
            except Exception as e:
                traceback.print_exc()
                rec = {'product_id': im['product_id'], 'site': site, 'status': 'failed',
                       'reason': f'{type(e).__name__}: {str(e)[:200]}'}
            geo[(im['product_id'], site)] = rec
            _write_geo(geo)
            new += 1
            print(f"geometry {im['product_id']} {site}: {rec['status']} {rec.get('reason', '')}", flush=True)
        if new:
            last_new = time.time()
            tc_run.main(['--workers', str(a.workers), '--threads', str(a.threads)])
        n_geo = len(geo)
        print(f"round: {n_geo}/{len(todo)} rows with geometry; waiting {waiting}", flush=True)
        if n_geo == len(todo):
            break
        if time.time() - last_new > a.idle_minutes * 60:
            print(f'stopping: no new ready row for {a.idle_minutes} min', flush=True)
            break
        if not new:
            time.sleep(600)
    print('pilot rounds done', flush=True)


if __name__ == '__main__':
    main()
