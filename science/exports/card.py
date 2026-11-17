"""Decision Card PDF from the precomputed `data/cubes/<site>/decision_summary.json` + the cube index (+ the committed
1 m results bundle headline when it exists). No computation: every value is copied from those files, and each row
prints where it came from and the one-line commands to read it and to rebuild it.
"""
from __future__ import annotations

from pathlib import Path

from .. import sites
from . import common as C
from .pdf import Doc

CUBES = C.ROOT / 'data' / 'cubes'
BUNDLES = C.ROOT / 'data' / 'bundles'
SUMMARY_CMD = '{py} -m science.cube.build_summary {site}'


def _cube_by_id(index):
    return {c['cube_id']: c for c in index['cubes']}


def _cube_command(site, entry):
    """The cube's own recompute command (its provenance.command); small files read directly, large ones too (gz)."""
    try:
        return C.read_json(CUBES / site / entry['file']).get('provenance', {}).get('command')
    except Exception:  # noqa: BLE001
        return None


def card_numbers(site) -> dict:
    """Everything the card prints, as data (the PDF and the tests use the same object)."""
    sp = CUBES / site / 'decision_summary.json'; ip = CUBES / site / 'index.json'
    summ = C.read_json(sp); index = C.read_json(ip)
    ssha = C.sha256_file(sp)
    by_id = _cube_by_id(index)
    rows = []
    for i, r in enumerate(summ['rows']):
        cid = r['source'].replace('scenario cube ', '') if r['source'].startswith('scenario cube ') else None
        ce = by_id.get(cid)
        cube_file = CUBES / site / ce['file'] if ce else None
        rows.append({
            'axis': r['axis'], 'question': r['question'], 'value': r['value'], 'answer': r['answer'], 'label': r['label'],
            'source': r['source'],
            'cube_file': C.rel(cube_file) if cube_file else None,
            'cube_sha256_index': ce['sha256'] if ce else None,
            'cube_sha256_file': C.sha256_file(cube_file) if cube_file and cube_file.exists() else None,
            'number': C.number(f'decision_summary.{r["axis"]}', r['value'], 'text (formatted by build_summary)', r['label'],
                               sp, f'rows[{i}].value', SUMMARY_CMD.format(py=C.PY, site=site), sha=ssha),
            'cube_recompute': _cube_command(site, ce) if ce else None,
        })
    bundle = BUNDLES / f'{site}_2026-11-14_14d_mast1m.json'
    head = []
    if bundle.exists():
        from .timeseries import headline
        b = C.read_json(bundle)
        head = [n for n in headline(b, bundle, C.sha256_file(bundle))
                if n['name'] in ('sun_center_visible_pct_hourly_samples', 'sun_and_earth_center_visible_pct_hourly_samples',
                                 'longest_sun_center_hidden_h', 'sun_center_visible_pct')]
    s = sites.SITES.get(site, {})
    return {'site': site, 'name': s.get('name', site), 'lat': s.get('lat'), 'lon': s.get('lon'),
            'coordinates_source': s.get('coordinates_source'), 'summary_file': C.rel(sp), 'summary_sha256': ssha,
            'index_file': C.rel(ip), 'index_sha256': C.sha256_file(ip), 'rows': rows, 'note': summ.get('note'),
            'headline': head, 'bundle_file': C.rel(bundle) if bundle.exists() else None,
            'git': C.git_commit()}


def render(site) -> tuple:
    d = card_numbers(site)
    doc = Doc(footer=f'POLARIS X Decision Card · {site} · {C.LABEL} · exported by science.exports ({C.EXPORT_VERSION})')
    doc.add(f'POLARIS X · Decision Card · {d["name"]}', 15, 'F2', gap=2)
    doc.add(f'{C.LABEL}. {C.GEOMETRY_ONLY} {d["note"]}', 8.5, 'F2', gap=4)
    if d['lat'] is not None:
        doc.add(f'Site {site}: lat {d["lat"]} deg, lon {d["lon"]} deg east (planetocentric). Coordinates: '
                f'{d["coordinates_source"]}.', 8.5)
    doc.add(f'Source: {d["summary_file"]} (SHA-256 {d["summary_sha256"]}); cube index {d["index_file"]} '
            f'(SHA-256 {d["index_sha256"]}).', 8)
    doc.add(f'Rebuild every row: {SUMMARY_CMD.format(py=C.PY, site=site)}', 8, 'F3', gap=6)
    for r in d['rows']:
        doc.add(f'{r["axis"]} · {r["question"]}', 11, 'F2')
        doc.add(r['value'], 11, 'F1', indent=12)
        doc.add(r['answer'], 8.5, 'F1', indent=12)
        doc.add(f'Label: {r["label"]}', 8, 'F1', indent=12)
        if r['cube_file']:
            ok = 'matches index' if r['cube_sha256_file'] == r['cube_sha256_index'] else 'DIFFERS FROM INDEX'
            doc.add(f'Source: {r["source"]} · {r["cube_file"]} SHA-256 {r["cube_sha256_file"]} ({ok})', 7.5, 'F1', indent=12)
        else:
            doc.add(f'Source: {r["source"]}', 7.5, 'F1', indent=12)
        doc.add(f'Read: {r["number"]["read"]}', 7, 'F3', indent=12)
        if r['cube_recompute']:
            doc.add(f'Cube rebuilt by: {r["cube_recompute"]}', 7, 'F3', indent=12)
        doc.space(5)
    if d['headline']:
        doc.add('Results bundle headline (1 m mast, 2026-11-14 + 14 d)', 11, 'F2')
        for n in d['headline']:
            doc.add(f'{n["name"]} = {n["value"]} {n["unit"]}', 9, 'F1', indent=12)
            doc.add(f'Read: {n["read"]}', 7, 'F3', indent=12)
        doc.add(f'Bundle {d["bundle_file"]} rebuilt by: {d["headline"][0]["recompute"]}', 7, 'F3', indent=12, gap=4)
    doc.add('Limits', 11, 'F2')
    for t in ('Every value is copied from the files above; this card computes nothing.',
              'Terrain maps are deterministic alternates (PGDA 78 error clones); k of N maps is not a probability, and '
              'scenario counts are never combined across axes.',
              'Requirements (Sun >= 70 %, Sun+Earth >= 40 %, gap <= 120 h) are team requirements, not NASA standards; '
              'energy and link rows are ENGINEERING ASSUMPTIONS; slope limits are ENGINEERING ASSUMPTIONS.',
              'Not independently validated (no NASA/JPL check of the solver yet).'):
        doc.add(f'- {t}', 8, indent=6)
    g = d['git']
    doc.add(f'Exported from commit {g["commit"]}{" (science/ has uncommitted changes)" if g["science_dirty"] else ""}.', 7.5,
            gap=2)
    pdf = doc.render(title=f'POLARIS X Decision Card {site}', subject=C.LABEL)
    return pdf, d


def export(site, out_dir) -> dict:
    pdf, d = render(site)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    p = out / f'{site}_decision_card.pdf'; p.write_bytes(pdf)
    C.write_json(out / f'{site}_decision_card.json', {'schema': 'polaris-export-decision-card-v1', 'label': C.LABEL, **d})
    return {'pdf': p, 'json': out / f'{site}_decision_card.json', 'data': d}
