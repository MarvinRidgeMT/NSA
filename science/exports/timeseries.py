"""CSV and JSON time series from any polaris-science-results-v1 bundle (committed, any-site cache, Mercury).

One row per Horizons sample in the bundle, in bundle order: no resampling, no interpolation, no extrapolation.
Values are written with Python's shortest round-trip float repr, so CSV -> float gives back the bundle value exactly.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from . import common as C

BODIES = ('sun', 'earth')
BODY_FIELDS = (('az_deg', 'deg', 'Horizons apparent azimuth (0 N, 90 E, local ENU)'),
               ('el_deg', 'deg', 'Horizons apparent elevation (airless)'),
               ('el_horizons_deg', 'deg', 'raw Horizons elevation before the ellipsoid->sphere normal rotation (worlds)'),
               ('radius_deg', 'deg', 'apparent angular radius'),
               ('range_au', 'au', 'observer range'),
               ('horizon_deg', 'deg', 'terrain skyline elevation at this azimuth'),
               ('margin_deg', 'deg', 'el_deg - horizon_deg'),
               ('center_visible', 'bool', 'centre above the terrain skyline'),
               ('disk_fraction', '1', 'visible fraction of the disc'),
               ('horizon_flag', '', 'skyline status at this azimuth'))


def columns(bundle) -> list:
    """Column list: (name, json path template with {i}, unit, description). Optional fields only if present."""
    cols = [('utc', 'samples[{i}].utc', 'UTC ISO 8601', 'Horizons sample time'),
            ('t_unix', 'samples[{i}].t_unix', 's', 'Unix seconds')]
    for b in BODIES:
        for f, unit, desc in BODY_FIELDS:
            if any(f in s.get(b, {}) for s in bundle['samples']):
                cols.append((f'{b}_{f}', f'samples[{{i}}].{b}.{f}', unit, f'{b.capitalize()}: {desc}'))
    return cols


def _cell(v):
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, float):
        return repr(v)
    return str(v)


def parse_cell(s, unit):
    """Inverse of _cell for the declared unit (used by the round-trip test and API clients)."""
    if s == '':
        return None
    if unit == 'bool':
        return s == 'true'
    if unit in ('', 'UTC ISO 8601'):
        return s
    return float(s)


def rows(bundle, cols):
    out = []
    for i, s in enumerate(bundle['samples']):
        r = []
        for _, tmpl, _, _ in cols:
            try:
                r.append(C.json_get(bundle, tmpl.format(i=i)))
            except (KeyError, IndexError):
                r.append(None)
        out.append(r)
    return out


def headline(bundle, path, sha) -> list:
    """Headline metrics of the bundle as Number records."""
    rec = (bundle.get('generator') or {}).get('command', 'see bundle generator')
    m = bundle['metrics']; out = []
    for k, unit in (('sun_center_visible_pct_hourly_samples', '% of hourly samples'),
                    ('earth_center_visible_pct_hourly_samples', '% of hourly samples'),
                    ('sun_and_earth_center_visible_pct_hourly_samples', '% of hourly samples'),
                    ('sun_center_visible_pct', '% of window (interval)'),
                    ('sun_and_earth_center_visible_pct', '% of window (interval)'),
                    ('longest_sun_center_hidden_h', 'h'), ('longest_earth_center_hidden_h', 'h'),
                    ('min_sun_margin_deg', 'deg'), ('min_earth_margin_deg', 'deg')):
        if isinstance(m.get(k), (int, float)) and not isinstance(m.get(k), bool):
            out.append(C.number(k, m[k], unit, C.LABEL, path, f'metrics.{k}', rec, sha=sha))
    return out


def build(bundle_path) -> dict:
    """The JSON time series document (also the source of the CSV)."""
    bundle_path = Path(bundle_path)
    b = C.read_json(bundle_path); sha = C.sha256_file(bundle_path)
    cols = columns(b)
    world = (b.get('world') or {}).get('world') if isinstance(b.get('world'), dict) else None
    return {
        'schema': 'polaris-export-timeseries-v1',
        'label': C.LABEL,
        'disclaimer': C.GEOMETRY_ONLY,
        'export_version': C.EXPORT_VERSION,
        'source': {'file': C.rel(bundle_path), 'sha256': sha, 'schema': b.get('schema'), 'bundle_id': b.get('bundle_id'),
                   'generator': b.get('generator'), 'world': world or 'moon'},
        'site': {k: b['site'].get(k) for k in ('id', 'name', 'lat_deg', 'lon_deg_east', 'height_m', 'observer_mast_m')},
        'frame': {'azimuth': b.get('frame', {}).get('azimuth'), 'time_scale': b.get('time', {}).get('scale', 'UTC')},
        'columns': [{'name': n, 'json_path': p, 'unit': u, 'description': d} for n, p, u, d in cols],
        'rows': rows(b, cols),
        'metrics': headline(b, bundle_path, sha),
        'reproduce': {'read': C.read_cmd(bundle_path, 'samples[{i}].<body>.<field>'),
                      'recompute': (b.get('generator') or {}).get('command'),
                      'this_export': f'{C.PY} -m science.exports bundle {C.rel(bundle_path)}'},
        'limitations': b.get('limitations', []),
    }


def to_csv(doc) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow([c['name'] for c in doc['columns']])
    for r in doc['rows']:
        w.writerow([_cell(v) for v in r])
    return buf.getvalue()


def export(bundle_path, out_dir, stem=None) -> dict:
    doc = build(bundle_path)
    stem = stem or Path(bundle_path).name.split('.json')[0]
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    pj = out_dir / f'{stem}_timeseries.json'; pc = out_dir / f'{stem}_timeseries.csv'
    pj.write_text(json.dumps(doc, ensure_ascii=False) + '\n')
    pc.write_text(to_csv(doc))
    return {'json': pj, 'csv': pc, 'doc': doc}
