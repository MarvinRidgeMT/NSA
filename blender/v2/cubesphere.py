"""Cube-sphere geometry for the whole-Moon base mesh (prompt §5.1a). numpy only (used by pack.py in the project venv and by
globe.py inside Blender). Unit-tested in blender/tests/test_cubesphere.py.

Frame: Moon-fixed ME axes (x toward lon 0 on the equator, y toward lon 90 E, z north), as science/frames.unit. Each of the six
faces is parameterised by (a, b) in [-1, 1]^2 with the EQUAL-ANGLE map u = tan(a pi/4), v = tan(b pi/4), direction =
normalise(c + u e_u + v e_v): cell sizes vary by at most ~1.41x over the sphere (gnomonic would be 5.2x). Face order and axes:
  0 +X (lon 0)   1 +Y (lon 90 E)   2 -X (lon 180)   3 -Y (lon 90 W)   4 +Z (north)   5 -Z (south)
e_u x e_v = c for every face, so quads (i, j) -> (i+1, j) -> (i+1, j+1) -> (i, j+1) wind counter-clockwise seen from outside.
"""
from __future__ import annotations

import math

import numpy as np

FACES = (
    ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    ((0, 1, 0), (-1, 0, 0), (0, 0, 1)),
    ((-1, 0, 0), (0, -1, 0), (0, 0, 1)),
    ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
    ((0, 0, 1), (0, 1, 0), (-1, 0, 0)),
    ((0, 0, -1), (0, 1, 0), (1, 0, 0)),
)
FACE_NAMES = ('+X lon 0', '+Y lon 90E', '-X lon 180', '-Y lon 90W', '+Z north', '-Z south')


def directions(face, a, b):
    """Unit directions for face parameters a, b (arrays, broadcast) -> (..., 3)."""
    c, eu, ev = (np.asarray(v, float) for v in FACES[face])
    u = np.tan(np.asarray(a, float) * math.pi / 4)[..., None]
    v = np.tan(np.asarray(b, float) * math.pi / 4)[..., None]
    d = c + u * eu + v * ev
    return d / np.linalg.norm(d, axis=-1, keepdims=True)


def node_params(n):
    """Face parameters of the (n+1) x (n+1) grid nodes: A[j, i] = a_i, B[j, i] = b_j."""
    t = -1.0 + 2.0 * np.arange(n + 1) / n
    return np.meshgrid(t, t)


def texel_params(n):
    """Face parameters of n x n texel centres (row 0 = b near +1, so an image's top row is the face's +v edge)."""
    t = -1.0 + (2.0 * np.arange(n) + 1.0) / n
    A, B = np.meshgrid(t, t[::-1])
    return A, B


def latlon_deg(d):
    """(lat, lon) degrees of vectors of ANY length (normalised here: a globe vertex in km is not a unit vector)."""
    d = np.asarray(d, float)
    r = np.linalg.norm(d, axis=-1)
    return np.degrees(np.arcsin(np.clip(d[..., 2] / r, -1, 1))), np.degrees(np.arctan2(d[..., 1], d[..., 0]))


def supersample_params(n, s):
    """Sub-sample offsets (s x s) inside each node's footprint (+-half a cell), for box-filtering heights onto the nodes."""
    h = 1.0 / n                                  # half the node spacing (cell = 2/n)
    o = (np.arange(s) + 0.5) / s * 2 * h - h
    return np.meshgrid(o, o)


def mesh(n, heights, radius_m=1_737_400.0, scale=1.0):
    """Welded cube-sphere. heights: (6, n+1, n+1) metres above `radius_m` (NaN allowed: such nodes are dropped with their
    quads). Returns V (N, 3) in Moon-fixed metres x scale, F (M, 4) quads, face_of_quad (M,), uv (M, 4, 2) per-corner face
    UVs ((a+1)/2, (b+1)/2), and the number of dropped quads."""
    A, B = node_params(n)
    verts, quads, fids, uvs = [], [], [], []
    base = 0
    for f in range(6):
        d = directions(f, A, B)
        r = radius_m + np.asarray(heights[f], float)
        verts.append((d * r[..., None]).reshape(-1, 3))
        q = (np.arange(n)[:, None] * (n + 1) + np.arange(n)[None, :]).ravel()
        quads.append(np.stack([q, q + 1, q + n + 2, q + n + 1], axis=1) + base)
        fids.append(np.full(n * n, f, np.int8))
        ua, vb = (A.ravel() + 1) / 2, (B.ravel() + 1) / 2
        uv = np.stack([ua, vb], axis=1)
        uvs.append(uv[np.stack([q, q + 1, q + n + 2, q + n + 1], axis=1)])
        base += (n + 1) ** 2
    V = np.vstack(verts)
    F = np.vstack(quads)
    fid = np.concatenate(fids)
    UV = np.vstack(uvs)
    # weld shared edge/corner nodes: identical directions from different faces (rounded unit vectors as keys)
    D = V / np.linalg.norm(V, axis=1, keepdims=True)
    key = np.round(D * 1e9).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.ravel()
    Vw = V[first]
    Fw = inv[F]
    ok = np.all(np.isfinite(Vw[Fw]).reshape(len(Fw), -1), axis=1)
    return Vw * scale, Fw[ok], fid[ok], UV[ok], int((~ok).sum())


def node_spacing_m(n, radius_m=1_737_400.0):
    """Largest and smallest great-circle node spacing on a face (equal-angle map), metres."""
    A, B = node_params(n)
    d = directions(0, A, B)
    s1 = np.arccos(np.clip(np.sum(d[:, 1:] * d[:, :-1], axis=-1), -1, 1)) * radius_m
    return float(s1.max()), float(s1.min())
