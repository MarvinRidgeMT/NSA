"""Build imagery/catalogue.csv.gz: stratified rows (one per image x site) + held-out split.

Inputs: the ODE harvest JSONs written by tools/imagery/ode.py (cached), Sun az/el at each
site centre from JPL Horizons (tools/imagery/solar.py, cached), and the 687 GSFC NAC
product IDs in tools/validation/nac/ (prior_use).

Output format: gzip CSV (mtime 0, fixed column order, rows sorted by product_id then site),
because the venv has no pyarrow/pandas. Same inputs -> same bytes -> same SHA-256.

    .venv/bin/python -m tools.imagery.catalogue build
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .http_cache import CACHE_ROOT, ROOT
from .sites import SITE_ORDER, SITES

SPLIT_SEED = 'polaris-x-v2-heldout-2026-11-16'
HELDOUT_FRAC = 0.30
OUT = ROOT / 'imagery' / 'catalogue.csv.gz'
NAC_DIR = ROOT / 'tools' / 'validation' / 'nac'

AZ_LABELS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
EL_EDGES = [(-math.inf, -0.5, 'el<-0.5'), (-0.5, 0.5, 'el[-0.5,0.5)'), (0.5, 1.5, 'el[0.5,1.5)'),
            (1.5, 2.5, 'el[1.5,2.5)'), (2.5, math.inf, 'el>=2.5')]
EM_EDGES = [(0, 5, 'em[0,5)'), (5, 15, 'em[5,15)'), (15, 30, 'em[15,30)'), (30, math.inf, 'em>=30')]
SEASON_EDGES = [(-math.inf, -0.75, 'ssl<-0.75'), (-0.75, 0.75, 'ssl[-0.75,0.75)'), (0.75, math.inf, 'ssl>=0.75')]
RES_EDGES = [(0, 1, 'res<1m'), (1, 5, 'res[1,5)m'), (5, 20, 'res[5,20)m'), (20, 100, 'res[20,100)m'),
             (100, math.inf, 'res>=100m')]

COLUMNS = ['product_id', 'site', 'instrument', 'ode_pdsid', 'ode_ihid', 'ode_iid', 'ode_pt', 'obs_utc', 'utc_start',
           'utc_stop', 'emission_deg', 'incidence_deg', 'phase_deg', 'pixel_scale_m', 'pixel_scale_source',
           'center_lat', 'center_lon', 'footprint_source', 'footprint_area_km2', 'footprint_width_km', 'overlap_frac',
           'covers_site_centre', 'footprint_suspect', 'terrain', 'sun_az_deg', 'sun_el_deg', 'subsolar_lat_deg',
           'az_bin', 'el_bin', 'em_bin', 'season_bin', 'res_bin', 'stratum', 'is_primary_row', 'prior_use',
           'split', 'label_url', 'product_page_url', 'external_url', 'data_file_url', 'data_file_kbytes', 'orbit']


def _bin(v, edges):
    if v is None:
        return 'unknown'
    for lo, hi, lab in edges:
        if lo <= v < hi:
            return lab
    return 'unknown'


def az_bin(az):
    if az is None:
        return 'unknown'
    return AZ_LABELS[int(((az % 360.0) + 22.5) // 45.0) % 8]


def bins(row):
    return {'az_bin': az_bin(row.get('sun_az_deg')), 'el_bin': _bin(row.get('sun_el_deg'), EL_EDGES),
            'em_bin': _bin(row.get('emission_deg'), EM_EDGES), 'season_bin': _bin(row.get('subsolar_lat_deg'), SEASON_EDGES),
            'res_bin': _bin(row.get('pixel_scale_m'), RES_EDGES)}


def stratum_key(row):
    return '|'.join([row['instrument'], row['az_bin'], row['el_bin'], row['em_bin'], row['season_bin'],
                     row['terrain'], row['res_bin']])


def split_hash(product_id):
    return hashlib.sha256(f'{SPLIT_SEED}:{product_id}'.encode()).hexdigest()


def prior_use_ids(nac_dir=NAC_DIR):
    """GSFC orthorectified NAC IDs used by the earlier NAC validation, keyed without the last
    letter (E = EDR / C = CDR) so M118008479LE matches ODE's CDR M118008479LC."""
    ids = {}
    for fn, region in (('nac_cams.json', 6), ('nac8_imgs.json', 8), ('nac9_cams.json', 9)):
        for r in json.loads((Path(nac_dir) / fn).read_text()):
            ids.setdefault(r['img'].upper()[:-1], []).append(region)
    return ids  # 687 list entries; some frames are in two regions' lists


def assign_split(rows, prior):
    """Mark primary rows, strata, prior_use and the held-out split, in place.

    Primary row per image: largest overlap_frac, ties by SITE_ORDER. Eligible images (not prior_use)
    are sorted by (stratum, split_hash) and held out by systematic sampling with step 1/0.3:
    image i (0-based) is held out iff floor((i+1)*f) > floor(i*f). That gives round-down(0.3 N)
    overall and 0.3 n +/- 1 in every stratum. prior_use images are always 'dev'."""
    by_img = defaultdict(list)
    for r in rows:
        by_img[r['product_id']].append(r)
    primaries = []
    for pid, rs in by_img.items():
        rs.sort(key=lambda r: (-r['overlap_frac'], SITE_ORDER.index(r['site'])))
        for k, r in enumerate(rs):
            r['is_primary_row'] = k == 0
        primaries.append(rs[0])
    for r in rows:
        r['prior_use'] = (r['instrument'] == 'LROC_NAC' and r['product_id'][:-1] in prior)
    for r in rows:
        r.update(bins(r))
        r['stratum'] = stratum_key(r)
    eligible = sorted((p for p in primaries if not p['prior_use']), key=lambda p: (p['stratum'], split_hash(p['product_id'])))
    held = set()
    for i, p in enumerate(eligible):
        if math.floor((i + 1) * HELDOUT_FRAC) > math.floor(i * HELDOUT_FRAC):
            held.add(p['product_id'])
    for r in rows:
        r['split'] = 'heldout' if r['product_id'] in held else 'dev'
    return held


def _fmt(v):
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, float):
        return f'{v:.6f}'.rstrip('0').rstrip('.') if math.isfinite(v) else ''
    return str(v)


def write_csv_gz(rows, path):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(COLUMNS)
    for r in sorted(rows, key=lambda r: (r['product_id'], SITE_ORDER.index(r['site']))):
        w.writerow([_fmt(r.get(c)) for c in COLUMNS])
    raw = buf.getvalue().encode('utf-8')
    gz = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=gz, mtime=0, compresslevel=9) as g:
        g.write(raw)
    data = gz.getvalue()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def read_csv_gz(path):
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def load_harvest(harvest_dir=CACHE_ROOT / 'harvest'):
    rows, metas = [], []
    for site_id in SITE_ORDER:
        for p in sorted(Path(harvest_dir).glob(f'{site_id}__*.json')):
            d = json.loads(p.read_text())
            rows += d['rows']
            metas.append(d['meta'])
    return rows, metas


def add_sun(rows, sun_fn=None):
    from . import solar
    sun_fn = sun_fn or solar.sun_at
    by_site = defaultdict(set)
    for r in rows:
        r['_t'] = solar.parse_utc(r['obs_utc'])
        by_site[r['site']].add(r['_t'])
    sources = {}
    for site_id in SITE_ORDER:
        if not by_site.get(site_id):
            continue
        s = SITES[site_id]
        sun, src = sun_fn(s['lat'], s['lon'], sorted(by_site[site_id]))
        sources[site_id] = src
        for r in rows:
            if r['site'] == site_id:
                az, el = sun[r['_t']]
                r['sun_az_deg'], r['sun_el_deg'] = az, el
                r['subsolar_lat_deg'] = solar.subsolar_lat_deg(s['lat'], s['lon'], az, el)
    for r in rows:
        r.pop('_t', None)
    return sources


def build(out=OUT, harvest_dir=CACHE_ROOT / 'harvest', sun_fn=None, prior=None):
    rows, metas = load_harvest(harvest_dir)
    if not rows:
        raise SystemExit('no harvest rows: run python -m tools.imagery.ode harvest first')
    sun_sources = add_sun(rows, sun_fn)
    # Round every float to the CSV's precision BEFORE strata and the split, so both can be re-derived
    # exactly from the published file (overlaps that differ past 1e-6 would otherwise tie differently).
    for r in rows:
        for k, v in r.items():
            if isinstance(v, float) and math.isfinite(v):
                r[k] = round(v, 6)
    held = assign_split(rows, prior if prior is not None else prior_use_ids())
    sha = write_csv_gz(rows, out)
    side = {'catalogue': str(Path(out).relative_to(ROOT)) if Path(out).is_relative_to(ROOT) else str(out),
            'sha256': sha, 'rows': len(rows), 'images': len({r['product_id'] for r in rows}),
            'heldout_images': len(held), 'split_seed': SPLIT_SEED, 'heldout_frac': HELDOUT_FRAC,
            'harvest': [{k: m[k] for k in ('site', 'instrument', 'bbox', 'ode_candidates', 'kept')} |
                        {'ode_responses': [s['sha256'] for s in m['sources']]} for m in metas],
            'horizons_responses': {k: [s['sha256'] for s in v] for k, v in sun_sources.items()}}
    Path(out).with_name('catalogue.provenance.json').write_text(json.dumps(side, indent=1, sort_keys=True) + '\n')
    return rows, side


# ---------------------------------------------------------------- counts doc
def counts_tables(rows):
    prim = [r for r in rows if r['is_primary_row'] in (True, 'true')]
    insts = sorted({r['instrument'] for r in rows})
    out = []
    out.append('### Rows (image × site) and unique images per instrument and site\n')
    out.append('| Instrument | ' + ' | '.join(SITE_ORDER) + ' | Unique images | Held-out images | prior_use |')
    out.append('|---|' + '---|' * (len(SITE_ORDER) + 3))
    for ins in insts:
        cells = []
        for s in SITE_ORDER:
            rs = [r for r in rows if r['instrument'] == ins and r['site'] == s]
            cov = sum(1 for r in rs if r['covers_site_centre'] in (True, 'true'))
            cells.append(f'{len(rs)} ({cov} cover centre)')
        p = [r for r in prim if r['instrument'] == ins]
        out.append(f'| {ins} | ' + ' | '.join(cells) + f' | {len(p)} | {sum(1 for r in p if r["split"] == "heldout")} | '
                   f'{sum(1 for r in p if r["prior_use"] in (True, "true"))} |')
    p = prim
    out.append(f'| **All** | ' + ' | '.join(str(sum(1 for r in rows if r['site'] == s)) for s in SITE_ORDER) +
               f' | {len(p)} | {sum(1 for r in p if r["split"] == "heldout")} | {sum(1 for r in p if r["prior_use"] in (True, "true"))} |')
    for axis, order in (('az_bin', AZ_LABELS), ('el_bin', [e[2] for e in EL_EDGES]), ('em_bin', [e[2] for e in EM_EDGES]),
                        ('season_bin', [e[2] for e in SEASON_EDGES]), ('terrain', sorted({r['terrain'] for r in rows})),
                        ('res_bin', [e[2] for e in RES_EDGES])):
        labs = list(order) + (['unknown'] if any(r[axis] == 'unknown' for r in prim) else [])
        out.append(f'\n### Images by `{axis}` (primary rows; held-out in brackets)\n')
        out.append('| Instrument | ' + ' | '.join(labs) + ' |')
        out.append('|---|' + '---|' * len(labs))
        for ins in insts:
            c = Counter(r[axis] for r in prim if r['instrument'] == ins)
            h = Counter(r[axis] for r in prim if r['instrument'] == ins and r['split'] == 'heldout')
            out.append(f'| {ins} | ' + ' | '.join(f'{c[l]} [{h[l]}]' for l in labs) + ' |')
    def _t(v):
        return v in (True, 'true')
    gated = [r for r in rows if not _t(r['footprint_suspect']) and (_t(r['covers_site_centre']) or float(r['overlap_frac']) >= 0.25)]
    out.append('\n### Rows passing the protocol\'s metadata gates (§2: not `footprint_suspect`, and covers the site centre '
               'or overlap ≥ 0.25)\n\nThese are upper bounds: the other gates (product and label fetch, camera model, terrain '
               'coverage) are checked only when an image is rendered.\n')
    out.append('| Instrument | ' + ' | '.join(SITE_ORDER) + ' | dev images | held-out images |')
    out.append('|---|' + '---|' * (len(SITE_ORDER) + 2))
    for ins in insts:
        g = [r for r in gated if r['instrument'] == ins]
        imgs = {}
        for r in g:
            imgs[r['product_id']] = r['split']
        out.append(f'| {ins} | ' + ' | '.join(str(sum(1 for r in g if r['site'] == s)) for s in SITE_ORDER) +
                   f' | {sum(1 for v in imgs.values() if v == "dev")} | {sum(1 for v in imgs.values() if v == "heldout")} |')
    hero = Counter(r['instrument'] for r in rows if r['site'] == 'site04_roi3' and _t(r['covers_site_centre'])
                   and not _t(r['footprint_suspect']))
    hero_h = Counter(r['instrument'] for r in rows if r['site'] == 'site04_roi3' and _t(r['covers_site_centre'])
                     and not _t(r['footprint_suspect']) and r['split'] == 'heldout')
    out.append('\n**Site04 RoI 3 hero point** (footprint contains the point, footprint not suspect): ' +
               ', '.join(f'{k} {v} ({hero_h[k]} held out)' for k, v in sorted(hero.items())) +
               '. Coverage is by ODE footprint only; whether the point is resolved and unsaturated in each image is not yet checked.\n')
    strata = Counter(r['stratum'] for r in prim)
    hs = Counter(r['stratum'] for r in prim if r['split'] == 'heldout')
    sizes = Counter(min(n, 10) for n in strata.values())
    out.append(f'\n### Full strata\n\n{len(strata)} non-empty strata (instrument × az × el × emission × season × terrain × '
               f'resolution). Stratum size distribution (10 = 10 or more): ' +
               ', '.join(f'{k}: {sizes[k]}' for k in sorted(sizes)) + '.\n')
    out.append('<details><summary>Every non-empty stratum: images [held-out]</summary>\n')
    out.append('| Stratum | Images | Held-out |')
    out.append('|---|---|---|')
    for k in sorted(strata):
        out.append(f'| `{k}` | {strata[k]} | {hs[k]} |')
    out.append('\n</details>')
    return '\n'.join(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('build')
    c = sub.add_parser('counts')
    c.add_argument('--catalogue', default=str(OUT))
    sub.add_parser('doc')
    a = ap.parse_args(argv)
    if a.cmd == 'build':
        rows, side = build()
        print(json.dumps({k: side[k] for k in ('catalogue', 'sha256', 'rows', 'images', 'heldout_images')}, indent=1))
    elif a.cmd == 'doc':
        write_doc()
    else:
        print(counts_tables(read_csv_gz(a.catalogue)))
    return 0


def write_doc(out_md=ROOT / 'docs' / 'v2' / 'IMAGERY_CATALOGUE.md', catalogue=OUT):
    rows = read_csv_gz(catalogue)
    side = json.loads(Path(catalogue).with_name('catalogue.provenance.json').read_text())
    sha = hashlib.sha256(Path(catalogue).read_bytes()).hexdigest()
    if sha != side['sha256']:
        raise SystemExit('catalogue SHA-256 differs from catalogue.provenance.json')
    head = (Path(__file__).parent / 'catalogue_doc_header.md').read_text()
    harvest = '\n'.join(f'| {h["site"]} | {h["instrument"]} | {h["ode_candidates"]} | {h["kept"]} | {len(h["ode_responses"])} |'
                        for h in side['harvest'])
    summary = (f'\n## Counts\n\nCatalogue SHA-256 `{sha}`: **{side["rows"]} rows** (image × site), **{side["images"]} unique images**, '
               f'**{side["heldout_images"]} held out** (seed `{side["split_seed"]}`, {int(side["heldout_frac"] * 100)} % of eligible images; '
               f'`prior_use` images are never held out).\n\n'
               f'### ODE harvest (bounding-box candidates → kept after the exact stereographic clip)\n\n'
               f'| Site | Instrument | ODE candidates | Kept rows | ODE responses |\n|---|---|---|---|---|\n{harvest}\n\n')
    out_md.write_text(head + summary + counts_tables(rows) + '\n')
    return out_md


if __name__ == '__main__':
    sys.exit(main())
