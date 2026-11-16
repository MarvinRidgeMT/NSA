"""Phase 3 — visibility rule as a requirement sub-axis (R_vis), reusing science-limits L1 definitions.

  python -m science.cube.build_visibility [site ...]

Rules, per hourly sample and body, with m_perp = perpendicular margin to the local skyline (straight-line
horizon of the local slope, as the bundles) and r = apparent radius from the Horizons angular diameter
(i.e. from the Horizons distance):
  any_limb   m_perp > -r       some part of the disc is above the terrain
  centre     m_perp > 0        bundle default; existing numbers unchanged
  half_disc  visible fraction >= 1/2 under the straight-line horizon  ==  centre exactly (a line through the
             centre halves a disc). Kept as a named rule so a curved-horizon model can differ later.
  full_disc  m_perp > +r       the whole disc is above the terrain
Visible disc fraction per hour uses the LOCAL-FLAT-HORIZON assumption (vertical margin m, horizon taken as
horizontal across the disc; circular-segment area), as science-limits L1 'flat'.

Outputs data/cubes/<site>/visibility_rule.json.gz      T(21) x R_vis(4) x D_mast(10) x S(366 daily starts)
        data/cubes/<site>/disc_fraction_hourly.json.gz  T(21) x D_mast(10) x H(9097 hours), Sun and Earth,
                                                        visible fraction in per-mille (scale 0.001)
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

from . import compute as C
from . import ephem_year as E
from .build_cube import LABEL, METRICS, NOT_PROB, OUT, _dims, _gz, _metric_block, _provenance, site_inputs
from ..limits.common import sha256_file

RULES = ('any_limb', 'centre', 'half_disc', 'full_disc')
DAILY = 24


def disc_fraction_flat(m, r):
    """Visible fraction of a disc of radius r whose centre is m above a horizontal horizon (vectorised
    science/crossings.disk_fraction_visible with slope 0)."""
    m = np.asarray(m, float); r = np.asarray(r, float)
    x = np.clip(m / r, -1.0, 1.0)
    seg = np.arccos(x) - x * np.sqrt(1.0 - x * x)            # (segment area below) / r^2
    f = 1.0 - seg / np.pi
    return np.where(np.isfinite(m), f, np.nan)


def rule_flags(mp, r, rule):
    mp = np.nan_to_num(mp, nan=-1e9)
    if rule == 'any_limb':
        return mp > -r
    if rule in ('centre', 'half_disc'):
        return mp > 0
    if rule == 'full_disc':
        return mp > r
    raise ValueError(rule)


def terms(site, eph, t_id, mast):
    sky = C.skyline(site, t_id, mast)
    out = {}
    for body in ('sun', 'earth'):
        m, mp = C.margins_vec(eph[f'{body}_az'], eph[f'{body}_el'], sky)
        out[body] = {'m': m, 'mp': mp, 'r': eph[f'{body}_r']}
    return out


def build(site):
    b, eph = site_inputs(site)
    nT, nR, nM = len(C.T_IDS), len(RULES), len(C.MASTS)
    starts = np.arange(0, E.N_STARTS, DAILY)
    keys = ('sun_n', 'both_n', 'earth_n', 'sun_gap_h', 'earth_gap_h')
    vals = {k: np.zeros((nT, nR, nM, starts.size), np.int32) for k in keys}
    nH = eph['t'].size
    frac = {body: np.zeros((nT, nM, nH), np.int32) for body in ('sun', 'earth')}
    disc_mean = {body: np.zeros((nT, nM, starts.size), np.int32) for body in ('sun', 'earth')}
    L = E.WINDOW_H + 1
    for i, t in enumerate(C.T_IDS):
        for j, mast in enumerate(C.MASTS):
            tm = terms(site, eph, t, mast)
            for body in ('sun', 'earth'):
                f = disc_fraction_flat(tm[body]['m'], tm[body]['r'])
                frac[body][i, j] = np.rint(np.nan_to_num(f, nan=0.0) * 1000).astype(np.int32)
                c = np.concatenate([[0.0], np.cumsum(np.nan_to_num(f, nan=0.0))])
                disc_mean[body][i, j] = np.rint(1000 * (c[starts + L] - c[starts]) / L).astype(np.int32)
            for k, rule in enumerate(RULES):
                s_ = rule_flags(tm['sun']['mp'], tm['sun']['r'], rule)
                e_ = rule_flags(tm['earth']['mp'], tm['earth']['r'], rule)
                w = C.window_metrics(s_, e_, E.N_STARTS, E.WINDOW_H, DAILY)
                for kk in keys:
                    vals[kk][i, k, j] = w[kk]
    n = L
    T, Dm, S = _dims(eph, {'name': 'D_mast', 'kind': 'design', 'values': list(C.MASTS), 'units': 'm', 'nominal_index': 0,
                           'label': 'Observer height above ground (mast)'}, DAILY)
    R = {'name': 'R_vis', 'kind': 'requirement', 'values': list(RULES), 'units': '', 'nominal_index': 1,
         'label': 'Visibility rule (Sun and Earth)',
         'value_labels': ['any limb above terrain', 'centre above terrain (bundle default)',
                          'half disc (= centre under straight-line horizon)', 'full disc above terrain'],
         'note': 'apparent radii from the Horizons angular diameter (distance); straight-line local horizon'}
    metrics = {key: _metric_block(vals[src], key, n) for key, (src, *_r) in METRICS.items()}
    for body in ('sun', 'earth'):
        metrics[f'{body}_disc_mean'] = {
            'units': 'fraction', 'label': f'{body.capitalize()} mean visible disc fraction (flat local horizon)',
            'dtype': 'int32', 'scale': 0.001, 'decimals': 3,
            'values': np.repeat(disc_mean[body][:, None], nR, axis=1).reshape(-1).astype(int).tolist(),
            'provenance': 'circular-segment model, local-flat-horizon assumption; independent of R_vis'}
    now = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    cube = {'schema': 'scenario-cube-v1', 'cube_id': f'{site}-visibility-rule-v1', 'site_id': site,
            'title': 'Visibility rule: map x rule x mast x daily start', 'label': LABEL, 'generated_utc': now,
            'description': 'Same windows as the centre cube under four disc-visibility rules.',
            'fixed': {'position': 'bundle site', 'window_h': E.WINDOW_H, 'default_rule': 'centre'},
            'dims': [T, R, Dm, S], 'metrics': metrics,
            'missing': {'encoding': 'sparse-flat-index', 'by_metric': {k: [] for k in metrics}},
            'provenance': _provenance(site, eph, []),
            'limitations': ['Local geometric visibility only.', NOT_PROB,
                            'Disc fraction assumes a locally flat horizon across the disc; the rules use the straight-line (local slope) horizon.']}
    H = {'name': 'H', 'kind': 'schedule', 'values': [int(x) for x in eph['t']], 'units': 'unix s (UTC)', 'nominal_index': 0,
         'label': 'Hourly sample (JPL Horizons)'}
    hourly = {'schema': 'scenario-cube-v1', 'cube_id': f'{site}-disc-fraction-hourly-v1', 'site_id': site,
              'title': 'Hourly visible disc fraction: map x mast x hour', 'label': LABEL, 'generated_utc': now,
              'description': 'Visible fraction of the Sun and Earth discs per hourly sample (circular segment, flat local horizon).',
              'fixed': {'position': 'bundle site'}, 'dims': [T, Dm, H],
              'metrics': {f'{body}_fraction': {'units': 'fraction', 'label': f'{body.capitalize()} visible disc fraction',
                                               'dtype': 'int32', 'scale': 0.001, 'decimals': 3,
                                               'values': frac[body].reshape(-1).astype(int).tolist(),
                                               'provenance': 'science/cube/build_visibility.disc_fraction_flat'}
                          for body in ('sun', 'earth')},
              'missing': {'encoding': 'sparse-flat-index', 'by_metric': {'sun_fraction': [], 'earth_fraction': []}},
              'provenance': _provenance(site, eph, []),
              'limitations': ['Stored in per-mille (rounded to 0.001).', 'Flat-local-horizon assumption.']}
    return cube, hourly


def write(site):
    cube, hourly = build(site)
    d = OUT / site
    entries = []
    for name, c in (('visibility_rule.json.gz', cube), ('disc_fraction_hourly.json.gz', hourly)):
        raw = _gz(d / name, c)
        entries.append({'file': name, 'cube_id': c['cube_id'], 'title': c['title'], 'bytes': (d / name).stat().st_size,
                        'uncompressed_bytes': raw, 'sha256': sha256_file(d / name), 'dims': [x['name'] for x in c['dims']]})
    add_to_index(site, entries)
    return cube


def add_to_index(site, entries):
    p = OUT / site / 'index.json'
    idx = json.loads(p.read_text())
    names = {e['file'] for e in entries}
    idx['cubes'] = [c for c in idx['cubes'] if c['file'] not in names] + entries
    p.write_text(json.dumps(idx, indent=1) + '\n')


if __name__ == '__main__':
    for s in sys.argv[1:] or ['site04_roi3', 'site01_roi6']:
        c = write(s)
        n = E.WINDOW_H + 1
        v = c['metrics']['sun_pct']['values']
        per = len(v) // (21 * 4)
        print(s, 'nominal 1 m demo start Sun % by rule:',
              [round(v[(0 * 4 + k) * per] * 100 / n, 3) for k in range(4)])
