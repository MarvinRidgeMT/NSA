"""Starfield orientation check (runs inside Blender; needs the SVS 4851 map in data/cache).

Renders a long exposure (+14 EV) from site01_roi6 at 2026-11-21T02Z aimed at the Large and at the Small Magellanic Cloud, using
the ENU directions predicted by the spec's ICRF->ENU rotation (IAU 2009 pole + Horizons Sun). In each heavily smoothed render the
brightest blob must lie within TOL_DEG of the frame centre and stand out from the median sky. A 180 deg RA error (found and fixed on
16 Nov 2026: the texture vector had been flipped) puts the Crux Milky Way there instead and fails this check.
"""
import math
import sys
import tempfile
from pathlib import Path

import bpy
import numpy as np

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent))
ROOT = TESTS.parents[1]
TOL_DEG = 1.5
CLOUDS = {'LMC': (80.894, -69.756), 'SMC': (13.187, -72.83)}   # RA, Dec (deg), J2000 centres (SIMBAD)


def project(az, el, laz, lel, f_mm, sw_mm, W, H):
    from v2 import astro as A
    d, fwd = A.enu_direction(az, el), A.enu_direction(laz, lel)
    r = (fwd[1], -fwd[0], 0.0)                     # fwd x up(0,0,1)
    n = math.hypot(r[0], r[1])
    r = (r[0] / n, r[1] / n, 0.0)
    u = (r[1] * fwd[2] - r[2] * fwd[1], r[2] * fwd[0] - r[0] * fwd[2], r[0] * fwd[1] - r[1] * fwd[0])
    z = sum(a * b for a, b in zip(d, fwd))
    s = W / (sw_mm / f_mm)
    return W / 2 + sum(a * b for a, b in zip(d, r)) / z * s, H / 2 - sum(a * b for a, b in zip(d, u)) / z * s


def run():
    """One long exposure aimed at each cloud's PREDICTED direction; the smoothed blob must sit at the frame centre."""
    import json
    from v2 import astro as A, build_scene
    out = Path(tempfile.mkdtemp(prefix='polaris_stars_'))
    base = ['--lat', '-89.47409', '--lon', '-137.3813', '--utc', '2026-11-21T02:00Z', '--camera', 'eva_eye', '--resolution', '256',
            '--samples', '8', '--ev-comp', '14', '--no-overlays', '--layout', 'single', '--out', str(out)]
    res, ok = {}, True
    for name, (ra, dec) in CLOUDS.items():
        # direction predicted by the spec (built once with a throwaway look, then the camera is aimed at it)
        from v2 import spec as S
        sp = S.build_spec(-89.47409, -137.3813, '2026-11-21T02:00Z', camera='eva_eye')
        v = A.matvec(sp['stars']['icrfToEnu'], A.radec_unit(ra, dec))
        az, el = math.degrees(math.atan2(v[0], v[1])) % 360, math.degrees(math.asin(v[2]))
        manifest, _, _ = build_scene.build(build_scene.parse(base + ['--look-az', f'{az:.4f}', '--look-el', f'{el:.4f}', '--tag', name]))
        if not manifest['lighting']['world']['stars'].get('present'):
            return None, 'star map not in the cache'
        W, H = manifest['render']['resolution']
        im = bpy.data.images.load(str(out / f'{name}.png'))
        a = np.empty(len(im.pixels), np.float32)
        im.pixels.foreach_get(a)
        img = a.reshape(H, W, 4)[::-1, :, :3].mean(-1)
        k = 9
        pad = np.pad(img, k, mode='edge')
        c = np.cumsum(np.cumsum(pad, 0), 1)
        blur = (c[2 * k:, 2 * k:] - c[:-2 * k, 2 * k:] - c[2 * k:, :-2 * k] + c[:-2 * k, :-2 * k])[:H, :W]
        jy, jx = np.unravel_index(int(np.argmax(blur)), blur.shape)
        deg_per_px = math.degrees(2 * math.atan(18 / 50)) / W
        err = math.hypot(jx - W / 2, jy - H / 2) * deg_per_px
        contrast = float(blur.max() / max(np.median(blur), 1e-12))
        res[name] = {'predictedAzEl': [round(az, 3), round(el, 3)], 'brightestBlobOffsetDeg': round(err, 3), 'contrast': round(contrast, 2)}
        ok &= err <= TOL_DEG and contrast > 1.5
    return ok, res


if __name__ == '__main__':
    ok, res = run()
    print('[stars]', ok, res)
    sys.exit(0 if ok else 1)
