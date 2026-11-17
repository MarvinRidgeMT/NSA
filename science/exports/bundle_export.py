"""Export orchestration + provenance bundle.

  site export   : decision card (PDF + JSON), terrain-safety GeoTIFF, time series of the committed 1 m / 10 m bundles and
                  of the cached any-site bundle at the same point, numbers.json, provenance.json, <name>_provenance.zip
  bundle export : time series of one results bundle (any world) + numbers.json + provenance
  grid export   : global 10 deg GeoTIFF + polar 1 deg CSV from the precompute summary

provenance.json = inputs (path, SHA-256, bytes) + outputs (path, SHA-256, bytes) + the command + git commit. The ZIP is
deterministic (sorted names, fixed 1980-01-01 timestamps) so the same inputs give the same ZIP bytes.
"""
from __future__ import annotations

import os
import shlex
import sys
import zipfile
from pathlib import Path

from . import card, common as C, geotiff, timeseries

DEFAULT_OUT = C.ROOT / 'data' / 'exports'
ANYSITE_CACHE = C.ROOT / 'data' / 'cache' / 'anysite' / 'bundles'


def _command(argv=None):
    a = sys.argv[1:] if argv is None else argv
    return f'{C.PY} -m science.exports ' + ' '.join(shlex.quote(x) for x in a)


def _file_rec(p):
    p = Path(p)
    return {'path': C.rel(p), 'sha256': C.sha256_file(p), 'bytes': p.stat().st_size}


def write_provenance(out_dir, name, inputs, outputs, command, numbers):
    out_dir = Path(out_dir)
    np_ = C.write_json(out_dir / 'numbers.json', {'schema': 'polaris-export-numbers-v1', 'label': C.LABEL,
                                                   'note': f'{C.K_OF_N}. Each number: source file + SHA-256 + JSON path + '
                                                           f'read/recompute commands.', 'numbers': numbers})
    outputs = list(outputs) + [np_]
    prov = {'schema': 'polaris-export-provenance-v1', 'label': C.LABEL, 'export_version': C.EXPORT_VERSION,
            'command': command, 'git': C.git_commit(),
            'inputs': [_file_rec(p) for p in sorted({Path(os.path.abspath(p)) for p in inputs})],
            'outputs': [_file_rec(p) for p in sorted({Path(os.path.abspath(p)) for p in outputs})],
            'n_numbers': len(numbers),
            'rules': ['exports read precomputed files only; no science is computed',
                      'NASA-derived rasters (GeoTIFF) are written under data/exports/ (git-ignored)',
                      C.K_OF_N, C.GEOMETRY_ONLY]}
    pp = C.write_json(out_dir / 'provenance.json', prov)
    zp = out_dir / f'{name}_provenance.zip'
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(set(outputs + [pp]), key=lambda q: Path(q).name):
            zi = zipfile.ZipInfo(Path(p).name, date_time=(1980, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED; zi.external_attr = 0o644 << 16
            z.writestr(zi, Path(p).read_bytes())
    return {'provenance': pp, 'zip': zp, 'numbers': np_, 'prov': prov}


def export_bundle(bundle_path, out_dir=None, command=None):
    bundle_path = Path(bundle_path)
    stem = bundle_path.name.split('.json')[0]
    out_dir = Path(out_dir or DEFAULT_OUT / 'bundles' / stem)
    ts = timeseries.export(bundle_path, out_dir, stem)
    res = write_provenance(out_dir, stem, [bundle_path], [ts['json'], ts['csv']], command or _command(),
                           ts['doc']['metrics'])
    return {'out_dir': out_dir, 'timeseries': ts, **res}


def precompute_site(site_id=None, lat=None, lon=None, summary_path=geotiff.PRECOMPUTE):
    d = C.read_json(summary_path)
    for i, s in enumerate(d['sites']):
        if s.get('status') != 'done':
            continue
        if site_id is not None and s['id'] == site_id:
            return i, s
        if lat is not None and abs(s['lat'] - float(lat)) < 1e-6 and abs(((s['lon'] - float(lon) + 180) % 360) - 180) < 1e-6:
            return i, s
    return None, None


def anysite_bundle_path(site_hash):
    p = ANYSITE_CACHE / f'{site_hash}.json'
    return p if p.exists() else None


def export_site(site, out_dir=None, command=None):
    out_dir = Path(out_dir or DEFAULT_OUT / site)
    inputs, outputs, numbers = [], [], []
    c = card.export(site, out_dir)
    inputs += [C.ROOT / c['data']['summary_file'], C.ROOT / c['data']['index_file']]
    inputs += [C.ROOT / r['cube_file'] for r in c['data']['rows'] if r['cube_file']]
    outputs += [c['pdf'], c['json']]
    numbers += [r['number'] for r in c['data']['rows']] + c['data']['headline']
    g = geotiff.safety(site, out_dir)
    inputs.append(g['source']); outputs.append(g['path'])
    for b in sorted(card.BUNDLES.glob(f'{site}_2026-11-14_14d_mast*m.json')):
        ts = timeseries.export(b, out_dir)
        inputs.append(b); outputs += [ts['json'], ts['csv']]; numbers += ts['doc']['metrics']
    i, s = precompute_site(site_id=site)
    if s is not None and anysite_bundle_path(s['site_hash']):
        ab = anysite_bundle_path(s['site_hash'])
        ts = timeseries.export(ab, out_dir, f'{site}_anysite_{s["site_hash"]}')
        inputs.append(ab); outputs += [ts['json'], ts['csv']]; numbers += ts['doc']['metrics']
    res = write_provenance(out_dir, site, inputs, outputs, command or _command(), numbers)
    return {'out_dir': out_dir, 'card': c, 'geotiff': g, **res}


def export_grid(out_dir=None, command=None):
    out_dir = Path(out_dir or DEFAULT_OUT / 'moon_grid')
    g = geotiff.global_grid(out_dir); p = geotiff.polar_points(out_dir)
    numbers = []
    sp = geotiff.PRECOMPUTE
    for (la, lo), (i, s) in sorted(g['index'].items()):
        for f, u in geotiff.GRID_FIELDS:
            if s.get(f) is not None:
                numbers.append(C.number(f'{s["id"]}.{f}', s[f], u, C.LABEL, sp, f'sites[{i}].{f}',
                                        f'{C.PY} -m science.anysite.precompute', sha=g['sha256']))
    res = write_provenance(out_dir, 'moon_grid', [sp], [g['path'], p['path']], command or _command(), numbers)
    return {'out_dir': out_dir, 'global': g, 'polar': p, **res}
