"""Write the list of Kaguya TC files the project owner downloads by hand (DARTS rejects this pipeline's requests).

    python -m tools.validation.render_vs_real.tc_download_list [--set dev]

Dev only until the held-out amendment (A13) fixes its sample: every image of the dev pilot and the pipeline test, each as
its .lbl and .img.gz URL. Writes results_tc/download_dev.txt (one URL per line) and prints the folder to put them in and
what is still missing there. The guard refuses any held-out id.
"""
from __future__ import annotations

import argparse
import json

from .common import read_catalogue
from .tc_common import TC_RESULTS, TC_SPLIT, guard
from .tc_io import INCOMING, TC_DIR


def wanted(sel):
    ims = {}
    for key in ('pipelineTestImages', 'images'):
        for im in sel[key]:
            ims.setdefault(im['product_id'], im)
    return ims


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--set', default='dev', choices=['dev'])
    ap.add_argument('--check', action='store_true', help='test every .img.gz in incoming/ and list the damaged ones')
    a = ap.parse_args(argv)
    if TC_SPLIT != 'dev':
        raise SystemExit('dev list only (the held-out list comes with A13)')
    sel = json.loads((TC_RESULTS / 'selection.json').read_text())
    ims = wanted(sel)
    guard(list(ims), read_catalogue())
    urls, missing = [], 0
    for pid, im in ims.items():
        for url, name in ((im['label_url'], f'{pid}.lbl'), (im['data_file_url'], f'{pid}.img.gz')):
            urls.append(url)
            cached = (TC_DIR / ('labels' if name.endswith('.lbl') else 'img') / name).exists()
            if not cached and not any(INCOMING.rglob(name) if INCOMING.exists() else []):
                missing += 1
    if a.check:
        import subprocess
        from .tc_io import gzip_problem
        busy = subprocess.run(['pgrep', '-fl', 'curl'], capture_output=True, text=True).stdout
        bad = []
        for pid, im in ims.items():
            for f in (INCOMING.rglob(f'{pid}.img.gz') if INCOMING.exists() else []):
                if f.name in busy:
                    print(f'still downloading: {f.name}')
                    continue
                why = gzip_problem(f)
                if why:
                    bad.append(im['data_file_url'])
                    print(f'damaged: {f.name}: {why}')
        (TC_RESULTS / 'redownload_dev.txt').write_text(''.join(u + '\n' for u in bad))
        print(f'{len(bad)} damaged image(s) listed in {TC_RESULTS / "redownload_dev.txt"} (delete them, then download again)')
    out = TC_RESULTS / 'download_dev.txt'
    out.write_text('\n'.join(urls) + '\n')
    INCOMING.mkdir(parents=True, exist_ok=True)
    kb = sum(int(r['data_file_kbytes'] or 0) for r in {r['product_id']: r for r in read_catalogue() if r['product_id'] in ims}.values())
    print(f'{len(ims)} dev images, {len(urls)} files (~{kb / 1024:.0f} MB) listed in {out}')
    print(f'put them in {INCOMING.resolve()}/ (subfolders are fine); still missing there: {missing}')


if __name__ == '__main__':
    main()
