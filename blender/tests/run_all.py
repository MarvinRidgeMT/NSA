"""Blender acceptance tests for the v2 pipeline (prompt §5.3). Run:

    /Applications/Blender.app/Contents/MacOS/Blender -b --python-exit-code 1 -P blender/tests/run_all.py

1. every pure unit test in blender/tests/ under Blender's own Python;
2. Hapke node material radiometry: flat-plane Cycles renders equal r(i,e,g) E from blender/v2/hapke.py within 2 %;
3. reference scene rebuilt headless FROM SCRATCH using committed inputs only (data/bundles/site01_2026-11-14_14d.json and the
   80 m crop in app/data/polaris-source-site01-2026-11-14-v2.json; no cache, no stars), rendered on CPU with a fixed seed and
   compared with blender/tests/reference/ref_site01_eva_eye.png (mean |d| <= 2/255 and 99th percentile <= 16/255);
4. negative control: the same scene 72 h later (Sun ~40 deg further round) must FAIL that tolerance (the comparison can detect a change);
5. the build wrote a non-empty .blend and a manifest with Blender version, script hashes, input hashes, CYCLES, samples, device;
5b. when the solver DEM cache exists: the drawn site01_roi6 terrain reproduces the bundle skyline (blender/tests/skyline_check.py);
6. glTF provenance rule over web/public/ (blender/tests/glb_proof.py).
Set POLARIS_UPDATE_REFERENCE=1 to (re)write the reference PNG; the run then reports it and still exits 1 so it is never silent.
"""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

import bpy
import numpy as np

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent))
sys.path.insert(0, str(TESTS))
ROOT = TESTS.parents[1]
REF = TESTS / 'reference' / 'ref_site01_eva_eye.png'
REF_ARGS = ['--lat', '-89.4632', '--lon', '-137.49', '--utc', '2026-11-14T00:00Z', '--camera', 'eva_eye', '--terrain', 'committed',
            '--no-stars', '--resolution', '256', '--samples', '16', '--seed', '0', '--device', 'CPU']
REF_ORBITAL = TESTS / 'reference' / 'ref_site01_wac15km.png'
REF_ORBITAL_ARGS = ['--lat', '-89.4632', '--lon', '-137.49', '--utc', '2026-11-14T00:00Z', '--camera', 'lroc_wac', '--alt-km', '15',
                    '--terrain', 'committed', '--no-stars', '--resolution', '192', '--samples', '16', '--seed', '0', '--device', 'CPU']
MEAN_TOL, P99_TOL = 2 / 255, 16 / 255

results = []


def record(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print(f"[run_all] {'PASS' if ok else 'FAIL'}  {name}  {detail}")


def load_png(path):
    im = bpy.data.images.load(str(path), check_existing=False)
    a = np.empty(len(im.pixels), np.float32)
    im.pixels.foreach_get(a)
    w, h = im.size
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)[..., :3]


def diff(a, b):
    if a.shape != b.shape:
        return None
    d = np.abs(a.astype(np.float64) - b.astype(np.float64))
    return float(d.mean()), float(np.percentile(d, 99))


def main():
    t0 = time.time()
    # 1. unit tests ------------------------------------------------------------------------------------------------------
    suite = unittest.defaultTestLoader.discover(str(TESTS), pattern='test_*.py', top_level_dir=str(TESTS.parent))
    res = unittest.TextTestRunner(verbosity=1).run(suite)
    record('unit tests under Blender Python', res.wasSuccessful(), f'{res.testsRun} run, {len(res.failures)} failures, {len(res.errors)} errors, {len(res.skipped)} skipped')

    # 2. photometry -------------------------------------------------------------------------------------------------------
    import photometry_check
    ok, rows = photometry_check.run(tol=0.02)
    record('Hapke node material = Python Hapke (Cycles flat plane, 6 geometries)', ok, f'max rel err {max(r["relErr"] for r in rows):.2e}')

    # 3. reference rebuild ------------------------------------------------------------------------------------------------
    from v2 import build_scene
    tmp = Path(tempfile.mkdtemp(prefix='polaris_v2_ref_'))
    manifest, out, tag = build_scene.build(build_scene.parse(REF_ARGS + ['--out', str(tmp), '--tag', 'ref']))
    png = out / 'ref.png'
    update = os.environ.get('POLARIS_UPDATE_REFERENCE') == '1'
    if update or not REF.exists():
        REF.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(png, REF)
        record('reference image', False, f'WROTE {REF.relative_to(ROOT)} ({REF.stat().st_size} bytes); rerun without POLARIS_UPDATE_REFERENCE to test')
    else:
        m = diff(load_png(png), load_png(REF))
        ok = m is not None and m[0] <= MEAN_TOL and m[1] <= P99_TOL
        record('rebuilt scene matches stored reference', ok, f'mean |d| {m[0]*255:.3f}/255, p99 {m[1]*255:.2f}/255 (tol {MEAN_TOL*255:.0f}, {P99_TOL*255:.0f})' if m else 'size differs')
        record('reference PNG <= 200 KB', REF.stat().st_size <= 200_000, f'{REF.stat().st_size} bytes')

    # 3b. orbital reference: LROC WAC preset 15 km above the site over the committed crop (instrument path: Raw, 16-bit BW)
    _, oout, _ = build_scene.build(build_scene.parse(REF_ORBITAL_ARGS + ['--out', str(tmp), '--tag', 'ref_wac']))
    if update or not REF_ORBITAL.exists():
        shutil.copyfile(oout / 'ref_wac.png', REF_ORBITAL)
        record('orbital reference image', False, f'WROTE {REF_ORBITAL.relative_to(ROOT)} ({REF_ORBITAL.stat().st_size} bytes)')
    else:
        m = diff(load_png(oout / 'ref_wac.png'), load_png(REF_ORBITAL))
        ok = m is not None and m[0] <= MEAN_TOL and m[1] <= P99_TOL
        record('rebuilt orbital (WAC preset) scene matches stored reference', ok,
               f'mean |d| {m[0]*255:.3f}/255, p99 {m[1]*255:.2f}/255' if m else 'size differs')
        record('orbital reference PNG <= 200 KB', REF_ORBITAL.stat().st_size <= 200_000, f'{REF_ORBITAL.stat().st_size} bytes')

    # 4. negative control -------------------------------------------------------------------------------------------------
    if REF.exists():
        neg_args = list(REF_ARGS)
        neg_args[neg_args.index('2026-11-14T00:00Z')] = '2026-11-17T00:00Z'
        # same camera look (the default look follows the Sun): pin it to the reference look azimuth
        look = manifest['camera']['pose']['lookAzDeg']
        _, nout, _ = build_scene.build(build_scene.parse(neg_args + ['--look-az', str(look), '--out', str(tmp), '--tag', 'neg']))
        m = diff(load_png(nout / 'neg.png'), load_png(REF))
        changed = m is None or m[0] > MEAN_TOL or m[1] > P99_TOL
        record('negative control (Sun 72 h later) exceeds the tolerance', changed, f'mean |d| {m[0]*255:.2f}/255, p99 {m[1]*255:.1f}/255' if m else 'size differs')

    # 5. manifest ---------------------------------------------------------------------------------------------------------
    blend = out / manifest['outputs']['blend']['file']
    need = {'blenderVersion': manifest.get('blenderVersion') == bpy.app.version_string,
            'scripts hashed': len(manifest.get('scriptsSha256', {})) >= 6 and all(len(v) == 64 for v in manifest['scriptsSha256'].values()),
            'bundle hashed': len(manifest['inputs']['bundle']['sha256']) == 64,
            'terrain hashed': all(len(l.get('sha256', '')) == 64 for l in manifest['inputs']['terrainLevels']),
            'engine CYCLES': manifest['render']['engine'] == 'CYCLES',
            'samples': manifest['render']['samples'] == 16, 'device': manifest['render']['device'] == 'CPU',
            '.blend non-empty': blend.exists() and blend.stat().st_size > 100_000,
            'scene provenance in .blend': True}
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    prov = json.loads(bpy.context.scene.get('polaris', '{}'))
    need['scene provenance in .blend'] = prov.get('builder') == 'blender/v2/build_scene.py' and prov.get('scriptsSha256') == manifest['scriptsSha256']
    record('manifest + .blend provenance', all(need.values()), ', '.join(k for k, v in need.items() if not v) or 'all fields present')

    # 5b. skyline consistency (needs the solver's DEM cache; skipped and reported when absent) ------------------------------
    if (ROOT / 'data' / 'cache' / 'site01_roi6_p78_p78.npy').exists():
        import skyline_check
        r = skyline_check.measure('site01_roi6', 'cache', 0.05, out=str(tmp / 'skyline'))
        far = r['far (critical point >= 100 m)']
        ok = r['unbracketed'] == 0 and r['medianAbsDeg'] <= 0.02 and far['p95AbsDeg'] <= 0.1 and r['p95AbsDeg'] <= 0.3
        record('drawn terrain reproduces the solver skyline (site01_roi6, 720 bins, Blender ray casts)', ok,
               f"median |d| {r['medianAbsDeg']:.4f} deg, p95 {r['p95AbsDeg']:.3f}, far-bin p95 {far['p95AbsDeg']:.3f}, max {r['maxAbsDeg']:.3f}")
    else:
        print('[run_all] SKIP  skyline consistency: data/cache/site01_roi6_p78_p78.npy not present (solver DEM cache)')

    # 6. glTF provenance --------------------------------------------------------------------------------------------------
    import glb_proof
    rows = glb_proof.scan(ROOT)
    record('web/public glTF provenance', all(ok for _, ok, _ in rows), '; '.join(f'{r}: {"ok" if ok else why}' for r, ok, why in rows))

    shutil.rmtree(tmp, ignore_errors=True)
    n_fail = sum(1 for _, ok, _ in results if not ok)
    print(f'[run_all] {len(results) - n_fail}/{len(results)} checks passed in {time.time() - t0:.1f} s (Blender {bpy.app.version_string})')
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    code = 1
    try:
        code = main()
    except Exception:
        import traceback
        traceback.print_exc()
    sys.exit(code)
