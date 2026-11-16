"""POLARIS X — Sun / Earth / skyline sky model for the Blender scene. Pure Python (no bpy), unit-tested.

Two displays, both built ONLY from bundle values (JPL az/el samples, the bundle skyline, the bundle's per-sample
visible flags). Nothing here computes visibility, a skyline or a margin.

1. TRUE SKY SHELL (`shell_*`): a sphere of radius R around the observer's eye, beyond the drawn terrain. Directions and
   angular sizes are true, so from the mast-eye camera the Sun disc, the Earth disc, the bundle skyline and the drawn
   terrain silhouette line up as the observer would see them. Distance is not to scale (the Sun is not 20 km away).
2. SKY CHART (`chart_*`): the same directions with ELEVATION EXAGGERATED by a stated factor, on a small dome over the
   site, so an overview camera can see the Sun/Earth paths dip below the skyline and compare 5th-axis scenario skylines
   (they differ by tenths of a degree). Labelled "not to scale" everywhere it appears.

Frame: x grid east, y grid north, z up, metres, origin at the observer ground point (same as build_from_nasa_bundle.py).
"""
from __future__ import annotations

import math

# Display angular radii (deg). Sun: the solver's documented fallback (science/crossings.py, 0.2666); Earth: asin(6371 / 384400)
# for the mean Earth-Moon distance. The viewer bundle carries no per-sample radii, so these are nominal DISPLAY sizes only.
SUN_RADIUS_DEG = 0.2666
EARTH_RADIUS_DEG = math.degrees(math.asin(6371.0 / 384400.0))  # 0.9497


def basis_vectors(north, east):
    return tuple(north), tuple(east)


def direction(north, east, az_deg, el_deg):
    """Unit vector toward local az (clockwise from local north) / el, in grid axes (same formula as bundle_v2.grid_direction)."""
    a, e = math.radians(az_deg), math.radians(el_deg)
    h = math.cos(e)
    return ((math.sin(a) * east[0] + math.cos(a) * north[0]) * h,
            (math.sin(a) * east[1] + math.cos(a) * north[1]) * h,
            math.sin(e))


def shell_point(north, east, eye, radius, az_deg, el_deg):
    d = direction(north, east, az_deg, el_deg)
    return (eye[0] + radius * d[0], eye[1] + radius * d[1], eye[2] + radius * d[2])


def chart_point(north, east, centre, radius, az_deg, el_deg, exaggeration):
    """Elevation multiplied by `exaggeration`, clamped to +-89 deg; azimuth true."""
    e = max(-89.0, min(89.0, el_deg * exaggeration))
    return shell_point(north, east, centre, radius, az_deg, e)


def body_radius(radius, angular_radius_deg, scale=1.0):
    """Sphere radius that subtends `angular_radius_deg * scale` from the centre of a shell of `radius`."""
    return radius * math.tan(math.radians(angular_radius_deg * scale))


def skyline_polylines(skyline, point):
    """Closed ring through the bundle skyline bins, split where a bin has no elevation (never filled in).
    `point(az, el)` maps a bin to 3D. Returns a list of polylines (lists of points)."""
    az, el = skyline['azimuthDeg'], skyline['elevationDeg']
    n = len(az)
    if n == 0:
        return []
    runs, cur = [], []
    for k in range(n):
        if el[k] is None:
            if len(cur) > 1:
                runs.append(cur)
            cur = []
            continue
        cur.append(point(az[k], el[k]))
    if all(v is not None for v in el):
        cur.append(point(az[0], el[0]))  # close the ring
        runs.append(cur)
    elif len(cur) > 1:
        runs.append(cur)
    return runs


def path_runs(samples, target, visible, point):
    """The target's sky path through every ephemeris sample, split into runs of equal bundle state.
    visible[k] is the bundle flag (True / False / None = not evaluated). Consecutive runs share their boundary sample
    so the path has no gaps; the state change happens somewhere between the two hourly samples (not refined here).
    Returns [(state, [points], first_index, last_index)], state in {'clear', 'blocked', 'not evaluated'}."""
    def st(k):
        v = visible[k] if visible is not None else None
        return 'not evaluated' if v is None else ('clear' if v else 'blocked')

    out = []
    k0 = 0
    for k in range(1, len(samples) + 1):
        if k == len(samples) or st(k) != st(k0):
            idx = range(k0, min(k + 1, len(samples)))  # include the next sample to join the runs
            pts = [point(samples[i][target]['az'], samples[i][target]['el']) for i in idx]
            if len(pts) == 1:
                pts = pts * 2
            out.append((st(k0), pts, k0, idx[-1]))
            k0 = k
    return out


def chart_scenarios(scenarios):
    """Scenarios whose skyline is from the SAME observer point as the dataset (baseline, mast heights, terrain clones).
    Position offsets are excluded: their skyline is seen from another point and would be misleading on this chart."""
    out = []
    for s in scenarios:
        fam = s.get('family') or s.get('kind', '').replace('_', '-')
        if not s.get('skyline'):
            continue
        if fam == 'position-offset':
            continue
        out.append((s['id'], s.get('label', s['id']), fam))
    return out


def eye_camera(north, east, eye, az_deg, el_deg):
    """Look direction for a camera at the eye aimed at az / el (unit vector)."""
    return direction(north, east, az_deg, el_deg)


def summary(samples, sc):
    """Counts the manifest records, all from bundle flags (not recomputed)."""
    res = {}
    for t in ('sun', 'earth'):
        vis = sc['samples'][t]['visible'] if sc else [None] * len(samples)
        res[t] = {'samples': len(samples), 'clear': sum(1 for v in vis if v is True),
                  'blocked': sum(1 for v in vis if v is False), 'notEvaluated': sum(1 for v in vis if v is None),
                  'elevationRangeDeg': [round(min(s[t]['el'] for s in samples), 4), round(max(s[t]['el'] for s in samples), 4)]}
    return res
