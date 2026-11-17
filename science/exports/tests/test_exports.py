"""Exports round-trip the source files exactly (prompt §7; docs/v2/PHASE_7_T1_PLAN.md §1). Each test can fail."""
from __future__ import annotations

import contextlib
import csv
import io
import json
import math
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np

from science.exports import __main__ as cli
from science.exports import bundle_export as E, card, common as C, geotiff, pdf, timeseries

ROOT = C.ROOT
SITE = 'site04_roi3'
BUNDLE = ROOT / 'data' / 'bundles' / 'site04_roi3_2026-11-14_14d_mast1m.json'
MERCURY = ROOT / 'data' / 'worlds' / 'mercury' / 'mercury_prokofiev_rim_2026-11-14_176d_mast1m.json'


def run_value(file, path):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert cli.main(['value', str(file), path]) == 0
    return json.loads(buf.getvalue())


def same(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='polaris_exports_'))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class JsonPath(unittest.TestCase):
    def test_paths(self):
        o = {'a': {'b': [10, {'c': 3}]}, 'x.y': 5}
        self.assertEqual(C.json_get(o, 'a.b[0]'), 10)
        self.assertEqual(C.json_get(o, 'a.b[1].c'), 3)
        self.assertEqual(C.json_get(o, '["x.y"]'), 5)
        with self.assertRaises(ValueError):
            C.parse_path('a..b')
        with self.assertRaises(KeyError):
            C.json_get(o, 'a.z')


class TimeSeries(Tmp):
    def _roundtrip(self, bundle_path):
        b = C.read_json(bundle_path)
        r = timeseries.export(bundle_path, self.tmp)
        doc = json.loads(r['json'].read_text())
        cols = doc['columns']
        self.assertEqual(len(doc['rows']), len(b['samples']))
        with open(r['csv']) as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows[0], [c['name'] for c in cols])
        self.assertEqual(len(rows) - 1, len(b['samples']))
        n = 0
        for i, s in enumerate(b['samples']):
            for j, c in enumerate(cols):
                body_field = c['json_path'].format(i=i)
                try:
                    want = C.json_get(b, body_field)
                except KeyError:
                    want = None
                self.assertTrue(same(doc['rows'][i][j], want), (i, c['name']))
                got = timeseries.parse_cell(rows[i + 1][j], c['unit'])
                if isinstance(want, int) and not isinstance(want, bool) and got is not None:
                    got = int(got) if float(got).is_integer() else got
                self.assertTrue(same(got, want), (i, c['name'], rows[i + 1][j], want))
                n += 1
        self.assertGreater(n, 1000)
        self.assertEqual(doc['source']['sha256'], C.sha256_file(bundle_path))
        return doc

    def test_committed_moon_bundle(self):
        doc = self._roundtrip(BUNDLE)
        m = {x['name']: x for x in doc['metrics']}
        self.assertEqual(m['sun_center_visible_pct_hourly_samples']['value'], 94.362)
        self.assertEqual(m['sun_and_earth_center_visible_pct_hourly_samples']['value'], 72.107)
        for x in doc['metrics']:
            self.assertEqual(run_value(BUNDLE, x['json_path']), x['value'])

    def test_mercury_bundle(self):
        doc = self._roundtrip(MERCURY)
        self.assertIn('sun_el_horizons_deg', [c['name'] for c in doc['columns']])

    def test_no_extrapolation(self):
        b = C.read_json(BUNDLE); doc = timeseries.build(BUNDLE)
        self.assertEqual(doc['rows'][0][0], b['samples'][0]['utc'])
        self.assertEqual(doc['rows'][-1][0], b['samples'][-1]['utc'])

    def test_anysite_bundle_if_cached(self):
        i, s = E.precompute_site(site_id=SITE)
        p = s and E.anysite_bundle_path(s['site_hash'])
        if not p:
            self.skipTest('any-site cache not present (git-ignored)')
        self._roundtrip(p)


class GeoTiff(Tmp):
    def test_safety_values_and_georef(self):
        import rasterio
        from rasterio.warp import transform as wtrans
        from science import frames, sites
        g = geotiff.safety(SITE, self.tmp)
        cube = g['cube']; offs, xs, ys, step, rc = g['layout']
        nP = len(offs)
        x0, y0 = frames.stereo_forward(sites.SITES[SITE]['lat'], sites.SITES[SITE]['lon'])
        with rasterio.open(g['path']) as ds:
            p4 = ds.crs.to_proj4()
            for tok in ('+proj=stere', '+lat_0=-90', '+lon_0=0', '+x_0=0', '+y_0=0', '+R=1737400', '+units=m'):
                self.assertIn(tok, p4)
            self.assertIn('Moon (2015)', ds.crs.to_wkt())
            arr = ds.read(); desc = ds.descriptions
            # site lat/lon through the GeoTIFF CRS lands on the cube's centre pixel centre
            X, Y = wtrans('IAU_2015:30100', ds.crs, [sites.SITES[SITE]['lon']], [sites.SITES[SITE]['lat']])
            self.assertAlmostEqual(X[0], x0, delta=1e-6); self.assertAlmostEqual(Y[0], y0, delta=1e-6)
            for k, (dx, dy) in enumerate(offs):
                r, c = rc[k]
                cx, cy = ds.xy(r, c)
                self.assertAlmostEqual(cx, x0 + dx, delta=1e-6); self.assertAlmostEqual(cy, y0 + dy, delta=1e-6)
                self.assertEqual(arr[desc.index('landing_slope_100m_nominal'), r, c],
                                 cube['metrics']['landing_slope_100m']['values'][k])
                sl = cube['derived']['safe_and_lit']
                for name, m in sl['metrics'].items():
                    for ri, lim in enumerate(sl['dims'][0]['values']):
                        v = m['values'][ri * nP + k]
                        self.assertEqual(arr[desc.index(f'{name}_slope_lt_{lim:g}deg'), r, c], float(v), (name, k))
            self.assertEqual(ds.tags()['POLARIS_SOURCE_SHA256'], C.sha256_file(g['source']))
            self.assertIn('not a probability', ds.tags()['POLARIS_NOTE'])

    def test_safe_and_lit_count_matches_decision_row(self):
        """Pixels with k_safe_and_lit == 20 (slope < 10 deg) == the decision_summary 'safety' row."""
        import rasterio
        g = geotiff.safety(SITE, self.tmp)
        with rasterio.open(g['path']) as ds:
            a = ds.read(ds.descriptions.index('k_safe_and_lit_slope_lt_10deg') + 1)
        n = int((a == 20).sum())
        row = next(r for r in C.read_json(ROOT / 'data/cubes' / SITE / 'decision_summary.json')['rows'] if r['axis'] == 'safety')
        self.assertEqual(row['value'], f'{n} of {a.size} cells')

    def test_global_grid(self):
        import rasterio
        from rasterio.warp import transform as wtrans
        g = geotiff.global_grid(self.tmp)
        d = C.read_json(geotiff.PRECOMPUTE)
        self.assertEqual(len(g['index']), 540)
        with rasterio.open(g['path']) as ds:
            arr = ds.read(); desc = list(ds.descriptions)
            self.assertEqual(ds.crs.to_proj4().split(' +no_defs')[0], '+proj=longlat +R=1737400')
            for (la, lo), (i, s) in g['index'].items():
                r, c = ds.index(lo, la)
                self.assertEqual(ds.xy(r, c), (lo, la))
                for f, _ in geotiff.GRID_FIELDS:
                    self.assertTrue(same(float(arr[desc.index(f), r, c]), float(d['sites'][i][f])), (s['id'], f))
            # lon/lat of the CRS is the planetocentric lon/lat of the 1 737.4 km sphere (identity with IAU 30100)
            X, Y = wtrans('IAU_2015:30100', ds.crs, [10.0], [-20.0])
            self.assertEqual((X[0], Y[0]), (10.0, -20.0))

    def test_polar_points(self):
        p = geotiff.polar_points(self.tmp)
        d = C.read_json(geotiff.PRECOMPUTE)
        with open(p['path']) as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), sum(s['group'] in ('south_grid_1deg', 'north_grid_1deg') and s['status'] == 'done'
                                        for s in d['sites']))
        for r in rows[:50] + rows[-50:]:
            s = d['sites'][int(r['json_index'])]
            self.assertEqual(float(r['sun_pct']), s['sun_pct']); self.assertEqual(float(r['lat_deg']), s['lat'])


class DecisionCard(Tmp):
    def test_pdf_contains_every_value_and_command(self):
        r = card.export(SITE, self.tmp)
        raw = r['pdf'].read_bytes()
        self.assertTrue(raw.startswith(b'%PDF-1.4') and raw.rstrip().endswith(b'%%EOF'))
        lines = pdf.extract_text(raw)
        spaced, tight = ' '.join(lines), ''.join(lines)
        summ = C.read_json(ROOT / 'data/cubes' / SITE / 'decision_summary.json')
        for i, row in enumerate(summ['rows']):
            self.assertIn(pdf.translit(row['value']), spaced, row['axis'])
            self.assertIn(pdf.translit(row['label']), spaced, row['axis'])
            cmd = C.read_cmd(ROOT / 'data/cubes' / SITE / 'decision_summary.json', f'rows[{i}].value')
            self.assertIn(cmd.replace(' ', ''), tight.replace(' ', ''))
            self.assertEqual(run_value(ROOT / 'data/cubes' / SITE / 'decision_summary.json', f'rows[{i}].value'), row['value'])
        self.assertIn('not a probability', spaced)
        self.assertIn('SOURCE-BASED · UNVALIDATED', spaced)
        for row in r['data']['rows']:
            if row['cube_file']:
                self.assertEqual(row['cube_sha256_file'], row['cube_sha256_index'], row['cube_file'])
        for n in r['data']['headline']:
            self.assertIn(f'{n["name"]} = {n["value"]}', spaced)
            self.assertEqual(run_value(BUNDLE, n['json_path']), n['value'])

    def test_pdf_xref_offsets_valid(self):
        raw = card.render(SITE)[0]
        start = int(raw.rsplit(b'startxref\n', 1)[1].split(b'\n')[0])
        self.assertTrue(raw[start:].startswith(b'xref'))
        table = raw[start:].split(b'\n')
        n = int(table[1].split()[1])
        for i in range(1, n):
            off = int(table[2 + i].split()[0])
            self.assertTrue(raw[off:].startswith(b'%d 0 obj' % i), i)

    def test_summary_still_recomputes_from_cubes(self):
        """The card copies decision_summary.json; that file must still equal what build_summary computes now."""
        from science.cube import build_summary
        self.assertEqual(build_summary.rows(SITE), C.read_json(ROOT / 'data/cubes' / SITE / 'decision_summary.json')['rows'])

    def test_wrap_keeps_text(self):
        t = 'alpha beta ' + 'x' * 300 + ' gamma'
        self.assertEqual(''.join(pdf.wrap(t, 9, 200)).replace(' ', ''), t.replace(' ', ''))


class Provenance(Tmp):
    def test_site_export(self):
        r = E.export_site(SITE, self.tmp, command='test')
        prov = json.loads(r['provenance'].read_text())
        for rec in prov['inputs'] + prov['outputs']:
            self.assertEqual(C.sha256_file(ROOT / rec['path'] if not Path(rec['path']).is_absolute() else rec['path']),
                             rec['sha256'], rec['path'])
        self.assertEqual(prov['command'], 'test')
        self.assertIn('commit', prov['git'])
        names = zipfile.ZipFile(r['zip']).namelist()
        self.assertIn('provenance.json', names); self.assertIn(f'{SITE}_decision_card.pdf', names)
        self.assertIn(f'{SITE}_terrain_safety.tif', names)
        nums = json.loads(r['numbers'].read_text())['numbers']
        self.assertGreaterEqual(len(nums), 8)
        for n in nums:            # traceability: every exported number reads back from its source file
            for k in ('source_file', 'source_sha256', 'json_path', 'read', 'recompute', 'label'):
                self.assertTrue(n.get(k), (n['name'], k))
            self.assertEqual(C.json_get(C.read_json(ROOT / n['source_file']), n['json_path']), n['value'], n['name'])
            self.assertEqual(C.sha256_file(ROOT / n['source_file']), n['source_sha256'])

    def test_zip_deterministic_and_input_change_detected(self):
        src = self.tmp / 'in.json'; shutil.copy(BUNDLE, src)
        a = E.export_bundle(src, self.tmp / 'a', command='x'); za = a['zip'].read_bytes()
        b = E.export_bundle(src, self.tmp / 'a', command='x')       # same inputs, same destination -> same bytes
        self.assertEqual(za, b['zip'].read_bytes())
        d = json.loads(src.read_text()); d['samples'][3]['sun']['el_deg'] += 1e-6; src.write_text(json.dumps(d))
        c = E.export_bundle(src, self.tmp / 'c', command='x')
        self.assertNotEqual(a['prov']['inputs'][0]['sha256'], c['prov']['inputs'][0]['sha256'])
        self.assertNotEqual(za, E.export_bundle(src, self.tmp / 'a', command='x')['zip'].read_bytes())

    def test_grid_numbers_read_back(self):
        r = E.export_grid(self.tmp, command='x')
        nums = json.loads(r['numbers'].read_text())['numbers']
        self.assertEqual(len(nums), 540 * 4 - sum(1 for s in C.read_json(geotiff.PRECOMPUTE)['sites']
                                                  if s['group'] == 'global_grid_10deg' for f, _ in geotiff.GRID_FIELDS
                                                  if s.get(f) is None))
        d = C.read_json(geotiff.PRECOMPUTE)
        for n in nums[::97]:
            self.assertEqual(C.json_get(d, n['json_path']), n['value'])


if __name__ == '__main__':
    unittest.main()
