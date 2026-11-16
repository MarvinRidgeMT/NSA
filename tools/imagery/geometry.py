"""Planar geometry for ODE south-polar footprints (no shapely in the venv).

Frame: the south-polar stereographic grid of science/frames.py,
x = rho sin(lon), y = rho cos(lon), rho = 2 R tan(pi/4 + lat/2), R = 1,737,400 m.
ODE's ``Footprint_SP_geometry`` is in the same frame (checked by a test on a recorded
vertex). Pure Python; deliberately small.
"""
from __future__ import annotations

import math
import re

R_MOON_M = 1_737_400.0


def stereo_forward(lat_deg, lon_deg):
    rho = 2.0 * R_MOON_M * math.tan(math.pi / 4.0 + math.radians(lat_deg) / 2.0)
    lam = math.radians(lon_deg)
    return rho * math.sin(lam), rho * math.cos(lam)


def stereo_inverse(x, y):
    rho = math.hypot(x, y)
    lat = math.degrees(2.0 * math.atan(rho / (2.0 * R_MOON_M)) - math.pi / 2.0)
    lon = math.degrees(math.atan2(x, y)) % 360.0
    return lat, lon


# ---------------------------------------------------------------- WKT
_NUM = r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?'
_RING = re.compile(r'\(\s*(' + _NUM + r'\s+' + _NUM + r'(?:\s*,\s*' + _NUM + r'\s+' + _NUM + r')*)\s*\)')


def parse_wkt_polygons(wkt):
    """Return a list of polygons; each polygon is a list of rings (outer first), each ring a
    list of (x, y). Handles POLYGON, MULTIPOLYGON and GEOMETRYCOLLECTION of polygons.
    Non-polygon members (LINESTRING, POINT) are ignored. Empty geometries give []."""
    if not wkt:
        return []
    s = wkt.strip()
    if 'EMPTY' in s.upper() and '(' not in s:
        return []
    out = []
    # Split into polygon bodies by tracking parenthesis depth around POLYGON keywords.
    up = s.upper()
    i = 0
    while True:
        j = up.find('POLYGON', i)
        if j < 0:
            break
        if up[j + 7:].lstrip().startswith('EMPTY'):
            i = j + 7
            continue
        if j >= 5 and up[j - 5:j] == 'MULTI':
            # MULTIPOLYGON (((..)),((..)))
            k = s.index('(', j)
            end = _match_paren(s, k)
            body = s[k + 1:end]
            for poly in _split_top(body):
                out.append(_rings(poly))
            i = end + 1
        else:
            k = s.find('(', j)
            if k < 0:
                break
            end = _match_paren(s, k)
            out.append(_rings(s[k:end + 1]))
            i = end + 1
    return [p for p in out if p and len(p[0]) >= 3]


def _match_paren(s, k):
    depth = 0
    for n in range(k, len(s)):
        if s[n] == '(':
            depth += 1
        elif s[n] == ')':
            depth -= 1
            if depth == 0:
                return n
    raise ValueError('unbalanced WKT parentheses')


def _split_top(body):
    """'((a)),((b))' -> ['((a))', '((b))'] at depth 0."""
    parts, depth, start = [], 0, None
    for n, c in enumerate(body):
        if c == '(':
            if depth == 0:
                start = n
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                parts.append(body[start:n + 1])
    return parts


def _rings(poly_text):
    rings = []
    for m in _RING.finditer(poly_text):
        pts = []
        for pair in m.group(1).split(','):
            a, b = pair.split()
            pts.append((float(a), float(b)))
        if len(pts) >= 2 and pts[0] == pts[-1]:
            pts = pts[:-1]
        rings.append(pts)
    return rings


# ---------------------------------------------------------------- polygons
def ring_area(ring):
    """Signed shoelace area."""
    a = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return 0.5 * a


def polygon_area(poly):
    """Outer ring area minus holes (absolute values)."""
    if not poly:
        return 0.0
    return abs(ring_area(poly[0])) - sum(abs(ring_area(h)) for h in poly[1:])


def clip_ring_to_rect(ring, xmin, ymin, xmax, ymax):
    """Sutherland-Hodgman clip of a (possibly concave) ring against an axis-aligned rectangle.
    The clipped area is exact for any simple subject ring because the window is convex."""
    def clip(pts, inside, inter):
        out = []
        n = len(pts)
        for i in range(n):
            cur, prev = pts[i], pts[i - 1]
            ci, pi_ = inside(cur), inside(prev)
            if ci:
                if not pi_:
                    out.append(inter(prev, cur))
                out.append(cur)
            elif pi_:
                out.append(inter(prev, cur))
        return out

    def ix(x0):
        return lambda p, q: (x0, p[1] + (q[1] - p[1]) * (x0 - p[0]) / (q[0] - p[0]))

    def iy(y0):
        return lambda p, q: (p[0] + (q[0] - p[0]) * (y0 - p[1]) / (q[1] - p[1]), y0)

    pts = list(ring)
    for inside, inter in ((lambda p: p[0] >= xmin, ix(xmin)), (lambda p: p[0] <= xmax, ix(xmax)),
                          (lambda p: p[1] >= ymin, iy(ymin)), (lambda p: p[1] <= ymax, iy(ymax))):
        if not pts:
            break
        pts = clip(pts, inside, inter)
    return pts


def overlap_area_rect(polys, xmin, ymin, xmax, ymax):
    """Area of the union-free sum of polygon parts inside the rectangle (holes subtracted).
    ODE multipolygon parts do not overlap each other (they are meridian/pole splits)."""
    tot = 0.0
    for poly in polys:
        outer = abs(ring_area(clip_ring_to_rect(poly[0], xmin, ymin, xmax, ymax)))
        holes = sum(abs(ring_area(clip_ring_to_rect(h, xmin, ymin, xmax, ymax))) for h in poly[1:])
        tot += max(0.0, outer - holes)
    return tot


def point_in_ring(x, y, ring):
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xc = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xc:
                inside = not inside
    return inside


def point_in_polys(x, y, polys):
    for poly in polys:
        if point_in_ring(x, y, poly[0]) and not any(point_in_ring(x, y, h) for h in poly[1:]):
            return True
    return False


def bbox_diag(polys):
    xs = [p[0] for poly in polys for p in poly[0]]
    ys = [p[1] for poly in polys for p in poly[0]]
    if not xs:
        return 0.0
    return math.hypot(max(xs) - min(xs), max(ys) - min(ys))


# ---------------------------------------------------------------- site boxes
def site_square(lat, lon, half_m):
    x, y = stereo_forward(lat, lon)
    return (x - half_m, y - half_m, x + half_m, y + half_m), (x, y)


def square_envelope(rect, n_per_side=200):
    """Planetocentric lat/lon envelope of a stereographic rectangle.

    Returns (minlat, maxlat, lon_ranges) where lon_ranges is a list of (west, east) in
    0-360 E, west < east, split at 0/360 when needed. If the pole (0, 0) is inside the
    rectangle, lat runs to -90 and lon covers 0-360."""
    xmin, ymin, xmax, ymax = rect
    pts = []
    for k in range(n_per_side + 1):
        t = k / n_per_side
        pts += [(xmin + t * (xmax - xmin), ymin), (xmin + t * (xmax - xmin), ymax),
                (xmin, ymin + t * (ymax - ymin)), (xmax, ymin + t * (ymax - ymin))]
    lls = [stereo_inverse(px, py) for px, py in pts]
    pole_inside = xmin <= 0.0 <= xmax and ymin <= 0.0 <= ymax
    maxlat = max(la for la, _ in lls)
    if pole_inside:
        return -90.0, maxlat, [(0.0, 360.0)]
    # nearest point of the rectangle to the pole may be on an edge interior: clamp (0,0)
    cx, cy = min(max(0.0, xmin), xmax), min(max(0.0, ymin), ymax)
    minlat = min(min(la for la, _ in lls), stereo_inverse(cx, cy)[0])
    # Longitude: the rectangle does not contain the pole so its azimuth span is < 180 deg.
    xc, yc = (xmin + xmax) / 2, (ymin + ymax) / 2
    lon_c = math.degrees(math.atan2(xc, yc)) % 360.0
    rel = [((lo - lon_c + 180.0) % 360.0) - 180.0 for _, lo in lls]
    west, east = lon_c + min(rel), lon_c + max(rel)
    pad = 1e-3
    west, east = west - pad, east + pad
    minlat, maxlat = minlat - pad, maxlat + pad
    if west < 0.0:
        return minlat, maxlat, [(west + 360.0, 360.0), (0.0, east)]
    if east > 360.0:
        return minlat, maxlat, [(west, 360.0), (0.0, east - 360.0)]
    return minlat, maxlat, [(west, east)]
