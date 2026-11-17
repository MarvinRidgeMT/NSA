"""Minimal NAIF text-PCK reader and IAU rotation-model evaluator (no SPICE toolkit needed).

Reads the `\\begindata ... \\begintext` assignments of a text PCK (pck00010.tpc, pck00011.tpc, MESSENGER
pck00010_msgr_v23.tpc) and evaluates, for body B with barycentre b = B // 100 (NAIF "PCK" conventions, Required Reading
pck.req):
    T = TDB Julian centuries from J2000, d = TDB days from J2000
    theta_i = sum_k ANGLES[i][k] T^k            (BODYb_NUT_PREC_ANGLES; BODYb_MAX_PHASE_DEGREE + 1 coefficients, default 2)
    alpha0  = RA0 + RA1 T + RA2 T^2 + sum_i NUT_PREC_RA[i]  sin theta_i
    delta0  = DEC0 + DEC1 T + DEC2 T^2 + sum_i NUT_PREC_DEC[i] cos theta_i
    W       = PM0 + PM1 d + PM2 d^2 + sum_i NUT_PREC_PM[i]  sin theta_i
and the ICRF -> body-fixed rotation  M = R3(W) R1(90 - delta0) R3(90 + alpha0)  (degrees).
Verified on the kernels' own published constants in science/worlds/tests/test_frame_tie.py.
"""
from __future__ import annotations

import math
import re
from functools import lru_cache

import numpy as np

J2000_JD = 2451545.0


@lru_cache(maxsize=8)
def read_pck(path) -> dict:
    text = open(path, errors='replace').read()
    blocks = re.findall(r'\\begindata(.*?)(?:\\begintext|$)', text, re.S)
    data = {}
    for b in blocks:
        for name, val in re.findall(r'([A-Z0-9_]+)\s*=\s*(\([^)]*\)|[^\s(]+)', b):
            toks = val.strip('()').replace(',', ' ').split()
            nums = []
            for t in toks:
                try:
                    nums.append(float(t.replace('D', 'E').replace('d', 'e')))
                except ValueError:
                    nums = None
                    break
            if nums is not None:
                data[name] = nums
    return data


def rotation(path, body: int, jd_tdb):
    """(alpha0, delta0, W) in degrees at TDB Julian date(s)."""
    k = read_pck(path)
    jd = np.asarray(jd_tdb, float)
    d = jd - J2000_JD; T = d / 36525.0
    ra = k[f'BODY{body}_POLE_RA']; dec = k[f'BODY{body}_POLE_DEC']; pm = k[f'BODY{body}_PM']
    pad = lambda c: list(c) + [0.0] * (3 - len(c))
    ra, dec, pm = pad(ra), pad(dec), pad(pm)
    a = ra[0] + ra[1] * T + ra[2] * T * T
    de = dec[0] + dec[1] * T + dec[2] * T * T
    w = pm[0] + pm[1] * d + pm[2] * d * d
    bary = body // 100
    ang = k.get(f'BODY{bary}_NUT_PREC_ANGLES')
    if ang:
        deg = int(k.get(f'BODY{bary}_MAX_PHASE_DEGREE', [1])[0]) + 1
        n = len(ang) // deg
        th = [np.radians(sum(ang[i * deg + j] * T ** j for j in range(deg))) for i in range(n)]
        for key, f, tgt in (('RA', np.sin, 'a'), ('DEC', np.cos, 'de'), ('PM', np.sin, 'w')):
            c = k.get(f'BODY{body}_NUT_PREC_{key}', [])
            s = sum(ci * f(th[i]) for i, ci in enumerate(c) if ci)
            if tgt == 'a':
                a = a + s
            elif tgt == 'de':
                de = de + s
            else:
                w = w + s
    return a, de, w


def icrf_to_body(alpha0, delta0, W):
    """3x3 (or ...x3x3) matrix M with v_body = M v_icrf."""
    def R1(x):
        c, s = np.cos(x), np.sin(x)
        o, z = np.ones_like(c), np.zeros_like(c)
        return np.stack([np.stack([o, z, z], -1), np.stack([z, c, s], -1), np.stack([z, -s, c], -1)], -2)

    def R3(x):
        c, s = np.cos(x), np.sin(x)
        o, z = np.ones_like(c), np.zeros_like(c)
        return np.stack([np.stack([c, s, z], -1), np.stack([-s, c, z], -1), np.stack([z, z, o], -1)], -2)
    r = np.radians
    return R3(r(np.asarray(W, float))) @ R1(r(90.0 - np.asarray(delta0, float))) @ R3(r(90.0 + np.asarray(alpha0, float)))


def sub_point(path, body, jd_tdb, v_icrf):
    """Planetocentric (lat, east lon) where the ICRF direction(s) v_icrf (body centre -> point, any length) pierce the
    body, with the orientation at jd_tdb."""
    M = icrf_to_body(*rotation(path, body, jd_tdb))
    v = np.einsum('...ij,...j->...i', M, np.asarray(v_icrf, float))
    v = v / np.linalg.norm(v, axis=-1, keepdims=True)
    return np.degrees(np.arcsin(v[..., 2])), np.degrees(np.arctan2(v[..., 1], v[..., 0])) % 360.0
