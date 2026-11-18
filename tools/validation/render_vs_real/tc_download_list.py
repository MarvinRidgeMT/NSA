"""Write the list of Kaguya TC files the project owner downloads by hand (DARTS rejects this pipeline's requests).

    python -m tools.validation.render_vs_real.tc_download_list [--check]
    (held-out: python -m tools.validation.render_vs_real.tc_heldout list|check, after A13)

Every image of the split's selection (dev: the pilot and the pipeline test; held-out: the A13 sample), each as its .lbl
and .img.gz URL. Writes results_tc[_heldout]/download_<split>.txt (one URL per line) and prints the folder to put them in,
what is still missing there, and a shell loop that fetches each file until its gzip stream is complete (DARTS ends some
transfers early and does not support resuming). --check lists damaged files in redownload_<split>.txt. The guard refuses
any id outside the split.
"""
from __future__ import annotations

import argparse
import json

from .common import read_catalogue
from .tc_common import TC_RESULTS, TC_SPLIT, guard
from .tc_io import INCOMING, TC_DIR


LOOP = ('cd {dir} && while read -r u; do f=$(basename "$u"); case "$f" in *.lbl) [ -s "$f" ] || curl -fsSL --retry 3 -O "$u";; '
        '*) for i in 1 2 3 4 5 6; do gzip -t "$f" 2>/dev/null && break; rm -f "$f"; curl -fsSL --retry 3 -O "$u" || sleep 5; '
        'done; gzip -t "$f" 2>/dev/null || echo "STILL BAD $f";; esac; done < {list}')


def wanted(sel):
    ims = {}
    for key in ('pipelineTestImages', 'images'):
        for im in sel[key]:
            ims.setdefault(im['product_id'], im)
    return ims


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='test every .img.gz in incoming/ and list the damaged ones')
    a = ap.parse_args(argv)
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
        (TC_RESULTS / f'redownload_{TC_SPLIT}.txt').write_text(''.join(u + '\n' for u in bad))
        print(f'{len(bad)} damaged image(s) listed in {TC_RESULTS / f"redownload_{TC_SPLIT}.txt"} (delete them, then download again)')
    out = TC_RESULTS / f'download_{TC_SPLIT}.txt'
    out.write_text('\n'.join(urls) + '\n')
    INCOMING.mkdir(parents=True, exist_ok=True)
    kb = sum(int(r['data_file_kbytes'] or 0) for r in {r['product_id']: r for r in read_catalogue() if r['product_id'] in ims}.values())
    print(f'{len(ims)} {TC_SPLIT} images, {len(urls)} files (~{kb / 1024:.0f} MB) listed in {out}')
    print(f'put them in {INCOMING.resolve()}/ (subfolders are fine); still missing there: {missing}')
    print('fetch-until-valid loop:\n' + LOOP.format(dir=INCOMING.resolve(), list=out))


if __name__ == '__main__':
    main()
