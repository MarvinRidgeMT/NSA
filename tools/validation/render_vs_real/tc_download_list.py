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
    ap.parse_args(argv)
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
    out = TC_RESULTS / 'download_dev.txt'
    out.write_text('\n'.join(urls) + '\n')
    INCOMING.mkdir(parents=True, exist_ok=True)
    kb = sum(int(r['data_file_kbytes'] or 0) for r in {r['product_id']: r for r in read_catalogue() if r['product_id'] in ims}.values())
    print(f'{len(ims)} dev images, {len(urls)} files (~{kb / 1024:.0f} MB) listed in {out}')
    print(f'put them in {INCOMING.resolve()}/ (subfolders are fine); still missing there: {missing}')


if __name__ == '__main__':
    main()
