"""Stage the v2 global analytics layers for the web globe (T2, docs/v2/PHASE_7_T2_PLAN.md §1–2). DISPLAY ONLY.

    $POLARIS_PYTHON web/scripts/sync_v2_layers.py [--from DIR ...] [--check]

What it does (nothing here computes science; it moves and describes outputs of tools/globe/*):
  1. Coverage (tools/globe/coverage.py) and slope/roughness (tools/globe/analytics.py) PNGs: these builds read the whole
     science pyramid and rewrite committed QA documents, so they are NOT rerun here. If they are missing under
     web/public/globe/{coverage,analytics}/, they are copied from each --from DIR (a web/public/globe directory where the
     same tools already wrote them, e.g. another worktree of this branch family).
  2. Earth/Sun visibility PNGs: re-rendered from the cached fractions $POLARIS_DATA/v2/analytics/*.npz with
     tools.globe.visibility's own PNG writer (same ramp, same grid), else copied from --from.
  3. Writes web/public/layers/v2/manifest.json: per layer the files (SHA-256, pixel size, projection), the legend (class
     swatches from the tool's legend.json, or the tool's colour ramp sampled at 11 points), the label, the source, the
     rebuild command, and headline QA numbers read from docs/v2/PYRAMID_QA.json / COVERAGE_SUMMARY.json.
All outputs are git-ignored (NASA-derived rasters stay out of git).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import shutil
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
GLOBE = REPO / 'web' / 'public' / 'globe'
OUT = REPO / 'web' / 'public' / 'layers' / 'v2'
PY = '$POLARIS_PYTHON'  # shown in commands; the project venv

COVERAGE_FILES = ['coverage_res_eqc_4096.png', 'coverage_res_eqc.png', 'coverage_src_eqc.png', 'coverage_res_sp.png',
                  'coverage_res_np.png', 'legend.json', 'web_manifest.json']
ANALYTICS_FILES = ['slope_eqc.png', 'roughness_eqc.png', 'legend.json']
VIS_FILES = ['earth_visibility_eqc.png', 'earth_visibility_sp_1000m.png', 'earth_visibility_np_1000m.png',
             'sun_visibility_sp_1000m.png', 'sun_visibility_np_1000m.png', 'visibility_legend.json']
POLAR_HALF_COVERAGE_M = 1310720.0  # science.terrain.stack.POLAR_HALF_M (coverage polar grids, 2560 m cells)


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def png_size(p: Path):
    b = p.read_bytes()[:24]
    if b[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError(f'{p} is not a PNG')
    return struct.unpack('>II', b[16:24])


def copy_missing(sub: str, names: list[str], sources: list[Path], log) -> dict:
    """Copy each missing file of GLOBE/sub from the first --from dir that has it. Returns {name: origin}."""
    origin = {}
    dst = GLOBE / sub
    for name in names:
        if (dst / name).exists():
            origin[name] = 'present'
            continue
        for s in sources:
            src = s / sub / name
            if src.exists():
                dst.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst / name)
                origin[name] = f'copied from {src}'
                log(f'copied {src} -> {dst / name}')
                break
    if sub == 'coverage' and (dst / 'coverage_res_eqc_4096.png').exists() and not (dst / 'tiles').exists():
        for s in sources:
            if (s / 'coverage' / 'tiles').exists():
                shutil.copytree(s / 'coverage' / 'tiles', dst / 'tiles')
                log(f'copied {s / "coverage" / "tiles"}')
                break
    return origin


def render_visibility(log) -> dict:
    """Re-render the visibility PNGs from the cached npz with the tool's own writer."""
    done = {}
    try:
        import numpy as np
        from tools.globe import visibility as V
    except Exception as exc:  # noqa: BLE001
        log(f'visibility PNGs not re-rendered ({type(exc).__name__}: {exc}); will copy from --from if given')
        return done
    for kind, zone in (('sun', 'sp'), ('sun', 'np'), ('earth', 'sp'), ('earth', 'np')):
        f = V.cache_dir() / f'{kind}_{zone}_1000m.npz'
        if f.exists():
            z = np.load(f)
            V.write_polar_png(kind, zone, z['any'], 1000.0)
            done[f'{kind}_visibility_{zone}_1000m.png'] = f'rendered from {f.name} (sha256 {sha256(f)[:16]})'
    f = V.cache_dir() / 'earth_global_0.125.npz'
    if f.exists():
        z = np.load(f)
        V.write_global_png(z['any'], 0.125)
        done['earth_visibility_eqc.png'] = f'rendered from {f.name} (sha256 {sha256(f)[:16]})'
    if done:
        done['visibility_legend.json'] = 'written by tools.globe.visibility._legend'
    log(f'visibility PNGs rendered: {sorted(done)}')
    return done


def ramp_samples(kind: str, vmax: float, n: int = 11):
    """The tool's colour ramp sampled at n evenly spaced values 0..vmax (exact tool code, not a copy of its stops)."""
    import numpy as np
    v = np.linspace(0.0, vmax, n)
    if kind == 'magma':
        from tools.globe.seams import colormap
        rgba = colormap(v, vmax)
    else:
        from tools.globe.visibility import _ramp
        rgba = _ramp(v / vmax)
    return [{'value': round(float(x), 6), 'rgb': [int(c) for c in rgba[i, :3]]} for i, x in enumerate(v)]


def file_entry(rel: str, projection: str, **extra):
    p = REPO / 'web' / 'public' / rel
    if not p.exists():
        return None
    w, h = png_size(p)
    e = {'path': rel, 'sha256': sha256(p), 'bytes': p.stat().st_size, 'width': w, 'height': h, 'projection': projection}
    e.update(extra)
    return e


def polar_entry(rel, zone, cell_m=None, half_m=None):
    p = REPO / 'web' / 'public' / rel
    if not p.exists():
        return None
    w, _ = png_size(p)
    half = half_m if half_m is not None else w / 2 * cell_m
    return file_entry(rel, f'polar-stereographic-{zone}', halfExtentM=half, pole=zone,
                      proj4=f'+proj=stere +lat_0={-90 if zone == "sp" else 90} +lat_ts={-90 if zone == "sp" else 90} '
                            '+lon_0=0 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs',
                      axes=('+x toward 90 E, ' + ('+y toward 0 E' if zone == 'sp' else '-y toward 0 E') +
                            '; row 0 = +y edge, column 0 = -x edge'))


EQC = 'equirectangular: lon -180..180 left->right, lat 90..-90 top->bottom'


def build_manifest(origins: dict) -> dict:
    qa = json.loads((REPO / 'docs' / 'v2' / 'PYRAMID_QA.json').read_text())
    cov_sum = json.loads((REPO / 'docs' / 'v2' / 'COVERAGE_SUMMARY.json').read_text())
    cov_leg_p = GLOBE / 'coverage' / 'legend.json'
    cov_leg = json.loads(cov_leg_p.read_text()) if cov_leg_p.exists() else None
    an = qa.get('analytics', {})
    r2 = qa.get('analytics_r2', {})
    p69 = r2.get('pgda69_comparison_85_90S', {})
    eglob = r2.get('earth_global_0.125deg', {})
    geo = 'SOURCE-BASED · UNVALIDATED'
    layers = []

    def add(**kw):
        kw['files'] = [f for f in kw['files'] if f]
        kw['built'] = bool(kw['files'])
        layers.append(kw)

    classes = [{'label': c['label'], 'rgb': c['rgb']} for c in (cov_leg or {}).get('resolution_classes', [])]
    sources = [{'label': s['name'], 'rgb': s['rgb'], 'sourceId': s['source_id']} for s in (cov_leg or {}).get('sources', [])]
    pct = cov_sum.get('percent_by_resolution', {})
    add(id='coverage-res', title='Terrain coverage · native resolution', label=geo,
        what='Finest native resolution of real terrain backing each point of the science pyramid (never upsampled).',
        legend={'kind': 'classes', 'classes': classes},
        files=[file_entry('globe/coverage/coverage_res_eqc_4096.png', EQC, role='global'),
               polar_entry('globe/coverage/coverage_res_sp.png', 'sp', half_m=POLAR_HALF_COVERAGE_M),
               polar_entry('globe/coverage/coverage_res_np.png', 'np', half_m=POLAR_HALF_COVERAGE_M)],
        cellRule=(cov_leg or {}).get('cell_rule'),
        cells='2560 m (polar, |lat| >= 57.5 deg) / 1/8 deg (eq) coverage cells',
        stats={'source': 'docs/v2/COVERAGE_SUMMARY.json', 'created_utc': cov_sum.get('created_utc'),
               'percentByResolution': pct},
        source='science pyramid (tools/globe/pyramid.py), merge priority NAC DTM > SfS > PGDA 78 > Kaguya TC > PGDA 90 > SLDEM2015 > LOLA polar > LOLA global',
        command=f'{PY} -m tools.globe.coverage')
    add(id='coverage-src', title='Terrain coverage · product', label=geo,
        what='Dominant product (source_id) backing each 0.25 deg cell of the science pyramid.',
        legend={'kind': 'classes', 'classes': sources},
        files=[file_entry('globe/coverage/coverage_src_eqc.png', EQC, role='global')],
        cellRule=(cov_leg or {}).get('cell_rule'), cells='0.25 deg cells',
        stats={'source': 'docs/v2/COVERAGE_SUMMARY.json', 'created_utc': cov_sum.get('created_utc'),
               'percentBySourceId': cov_sum.get('percent_by_source_id')},
        source='science pyramid band source_id (docs/v2/SOURCE_IDS.json)', command=f'{PY} -m tools.globe.coverage')
    moon = (an.get('slope_stats_area_weighted') or {}).get('moon', {})
    add(id='slope', title='Slope (~1 km baseline)', label=geo,
        what='Area-weighted mean surface slope per 0.125 deg cell; central differences on pyramid eq L1 (~948 m) / polar L2 (640 m).',
        legend={'kind': 'ramp', 'unit': '°', 'min': 0, 'max': 40, 'samples': ramp_samples('magma', 40.0),
                'note': 'light = gentle, dark = steep; values above 40° drawn as 40°'},
        files=[file_entry('globe/analytics/slope_eqc.png', EQC, role='global')], cells='0.125 deg cells',
        stats={'source': 'docs/v2/PYRAMID_QA.json analytics', 'created_utc': an.get('created_utc'),
               'medianSlopeDeg': moon.get('median_slope_deg'), 'p90SlopeDeg': moon.get('p90_slope_deg'),
               'pctAreaSlopeGt10Deg': moon.get('pct_area_slope_gt_10deg')},
        source='science pyramid (real terrain only, never VISUAL relief)', command=f'{PY} -m tools.globe.analytics')
    add(id='roughness', title='Roughness (RMS slope, ~1 km)', label=geo,
        what='RMS slope at a ~1 km baseline per 0.125 deg cell (gridded pyramid; not the PGDA 70 / LOLA shot-based maps).',
        legend={'kind': 'ramp', 'unit': '°', 'min': 0, 'max': 30, 'samples': ramp_samples('magma', 30.0),
                'note': 'light = smooth, dark = rough; values above 30° drawn as 30°'},
        files=[file_entry('globe/analytics/roughness_eqc.png', EQC, role='global')], cells='0.125 deg cells',
        stats={'source': 'docs/v2/PYRAMID_QA.json analytics', 'created_utc': an.get('created_utc'),
               'medianRmsSlopeDeg': an.get('roughness_median_rms_slope_deg_1km')},
        source='science pyramid (real terrain only, never VISUAL relief)', command=f'{PY} -m tools.globe.analytics')
    vis_note = ('fraction of 3-h (global) / 6-h (polar) samples 2026-01-01..2044-08-01 with any part of the disc above the '
                'terrain horizon, observer on the surface (0 m mast); terrain geometry only, not link or power availability; '
                'not a probability')
    add(id='earth-vis', title='Earth visibility (libration-aware)', label=geo,
        what='Fraction of time the Earth disc is above the terrain horizon. Global 0.125 deg; 1 km poleward of 80 deg.',
        legend={'kind': 'ramp', 'unit': 'fraction', 'min': 0, 'max': 1, 'samples': ramp_samples('vis', 1.0), 'note': vis_note},
        files=[file_entry('globe/analytics/earth_visibility_eqc.png', EQC, role='global'),
               polar_entry('globe/analytics/earth_visibility_sp_1000m.png', 'sp', cell_m=1000.0),
               polar_entry('globe/analytics/earth_visibility_np_1000m.png', 'np', cell_m=1000.0)],
        cells='0.125 deg global; 1 km polar (|lat| >= 80 deg)',
        stats={'source': 'docs/v2/PYRAMID_QA.json analytics_r2', 'created_utc': r2.get('created_utc'),
               'areaPctAlwaysVisible': eglob.get('area_pct_always_visible'),
               'areaPctNeverVisible': eglob.get('area_pct_never_visible'),
               'pgda69MedianAbsDiff': (p69.get('earth') or {}).get('mine_minus_pgda69_cellmean', {}).get('median_abs'),
               'pgda69PearsonR': (p69.get('earth') or {}).get('pearson_r_cellmean')},
        source='JPL Horizons sub-Earth points 2026–2044 (tools/globe/ephem.py) + science pyramid horizons (tools/globe/visibility.py)',
        command=f'{PY} -m tools.globe.visibility global-earth; {PY} -m tools.globe.visibility polar-earth --pole sp|np')
    add(id='sun-vis', title='Sun visibility (poles, ≥ 85°)', label=geo,
        what='Fraction of time any part of the Sun is above the terrain horizon, 1 km cells poleward of 85 deg (both poles).',
        legend={'kind': 'ramp', 'unit': 'fraction', 'min': 0, 'max': 1, 'samples': ramp_samples('vis', 1.0), 'note': vis_note},
        files=[polar_entry('globe/analytics/sun_visibility_sp_1000m.png', 'sp', cell_m=1000.0),
               polar_entry('globe/analytics/sun_visibility_np_1000m.png', 'np', cell_m=1000.0)],
        cells='1 km polar (|lat| >= 85 deg); nothing equatorward',
        stats={'source': 'docs/v2/PYRAMID_QA.json analytics_r2', 'created_utc': r2.get('created_utc'),
               'medianSp': (r2.get('sun_sp_1km') or {}).get('median'), 'medianNp': (r2.get('sun_np_1km') or {}).get('median'),
               'pgda69MedianAbsDiff': (p69.get('sun') or {}).get('mine_minus_pgda69_cellmean', {}).get('median_abs'),
               'pgda69PearsonR': (p69.get('sun') or {}).get('pearson_r_cellmean')},
        source='JPL Horizons sub-solar points 2026–2044 (tools/globe/ephem.py) + science pyramid horizons (tools/globe/visibility.py)',
        command=f'{PY} -m tools.globe.visibility polar-sun --pole sp|np')
    return {'schema': 'polaris-globe-layers-v1', 'label': 'display-only analytics; never read by any calculation',
            'created_utc': _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'script': 'web/scripts/sync_v2_layers.py', 'origins': origins, 'layers': layers}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--from', dest='sources', action='append', default=[], type=Path,
                    help='a web/public/globe directory that already holds tools/globe outputs (repeatable)')
    ap.add_argument('--check', action='store_true', help='only report what is present; write nothing')
    a = ap.parse_args(argv)
    log = print
    if a.check:
        for sub, names in (('coverage', COVERAGE_FILES), ('analytics', ANALYTICS_FILES + VIS_FILES)):
            for n in names:
                print(f'{"ok " if (GLOBE / sub / n).exists() else "-- "} globe/{sub}/{n}')
        return 0
    origins = {'coverage': copy_missing('coverage', COVERAGE_FILES, a.sources, log)}
    rendered = render_visibility(log)
    an = copy_missing('analytics', ANALYTICS_FILES + [f for f in VIS_FILES if f not in rendered], a.sources, log)
    an.update(rendered)
    origins['analytics'] = an
    m = build_manifest(origins)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'manifest.json').write_text(json.dumps(m, indent=1, ensure_ascii=False))
    log(f'wrote {OUT / "manifest.json"}: ' + ', '.join(f'{l["id"]}={"built" if l["built"] else "missing"}' for l in m['layers']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
