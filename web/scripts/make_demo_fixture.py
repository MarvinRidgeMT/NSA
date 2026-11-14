#!/usr/bin/env python3
"""Generate the DEMO-ONLY viewer fixture: web/public/bundles/demo-fixture.json.

!!! SYNTHETIC. NOT NASA TERRAIN. NOT JPL EPHEMERIS. !!!

This exists only so the b-experience viewer can be built and tested before the
science branch ships `derived` outputs. Every number in it is invented here.
The viewer itself never computes skylines, visibility or metrics; this script is
offline DEMO tooling and is never imported by the app.

Layout follows POLARIS-X5D-v2 (schemas/science-bundle-v2.schema.json) plus the
additive `derived` block proposed in web/docs/VIEWER_BUNDLE_CONTRACT.md.
Deterministic: same output bytes every run.
"""
import json
import math
from pathlib import Path

R_MOON = 1737400.0
N = 121            # DEM is N x N
SPACING = 50.0     # metres
L_DEG = -137.49    # demo longitude: exercises grid<->local rotation like Site01
SAMPLES = 48       # hourly
T0 = "2026-11-14T14:00:00Z"
BIN = 0.5          # skyline bin, degrees
MAX_REACH = 2900.0


def local_basis(lon_deg):
    """South-polar stereographic grid: local north = (sin L, cos L), east = (cos L, -sin L)."""
    L = math.radians(lon_deg)
    north = (math.sin(L), math.cos(L))
    east = (math.cos(L), -math.sin(L))
    return east, north


def grid_dir(az_deg, lon_deg):
    east, north = local_basis(lon_deg)
    a = math.radians(az_deg)
    return (math.sin(a) * east[0] + math.cos(a) * north[0], math.sin(a) * east[1] + math.cos(a) * north[1])


def make_dem():
    """Synthetic terrain: a gentle bowl + a ridge to local south-west + a knoll to local east."""
    east, north = local_basis(L_DEG)
    half = (N - 1) * SPACING / 2
    vals = []
    for j in range(N):            # south-to-north rows
        for i in range(N):
            x = -half + i * SPACING
            y = -half + j * SPACING
            le = x * east[0] + y * east[1]     # local east coordinate
            ln = x * north[0] + y * north[1]   # local north coordinate
            r = math.hypot(x, y)
            z = 1500.0 + 0.0004 * r * r / 100.0
            # ridge running NW-SE, about 1.6 km to the local south-west
            d_ridge = abs((le + ln) / math.sqrt(2) + 1600.0)
            z += 80.0 * math.exp(-(d_ridge / 260.0) ** 2)
            # knoll 1.1 km local east
            z += 70.0 * math.exp(-(((le - 900.0) ** 2 + (ln + 700.0) ** 2) / (300.0 ** 2)))
            vals.append(round(z, 3))
    return vals, -half, -half


def dem_at(vals, ox, oy, x, y):
    fx = (x - ox) / SPACING
    fy = (y - oy) / SPACING
    i0, j0 = int(math.floor(fx)), int(math.floor(fy))
    if i0 < 0 or j0 < 0 or i0 >= N - 1 or j0 >= N - 1:
        return None, None
    tx, ty = fx - i0, fy - j0
    z00 = vals[j0 * N + i0]; z10 = vals[j0 * N + i0 + 1]
    z01 = vals[(j0 + 1) * N + i0]; z11 = vals[(j0 + 1) * N + i0 + 1]
    z = (z00 * (1 - tx) + z10 * tx) * (1 - ty) + (z01 * (1 - tx) + z11 * tx) * ty
    return z, (int(round(fx)), int(round(fy)))


def ray(vals, ox, oy, obs, az):
    """March along local azimuth `az`; return list of (d, x, y, z_drop_corrected, cell)."""
    dx, dy = grid_dir(az, L_DEG)
    out = []
    d = SPACING / 2
    while d <= MAX_REACH:
        x, y = obs[0] + dx * d, obs[1] + dy * d
        z, cell = dem_at(vals, ox, oy, x, y)
        if z is None:
            break
        out.append((d, x, y, z - d * d / (2 * R_MOON), z, cell))
        d += SPACING / 2
    return out


def angle(h_obs, zc, d):
    return math.degrees(math.atan2(zc - h_obs, d))


def skyline(vals, ox, oy, obs, h_obs):
    az, el, reach, cov = [], [], [], []
    for k in range(int(360 / BIN)):
        a = k * BIN
        pts = ray(vals, ox, oy, obs, a)
        best = max(angle(h_obs, p[3], p[0]) for p in pts)
        az.append(a); el.append(round(best, 4)); reach.append(round(pts[-1][0], 1))
        cov.append("truncated" if pts[-1][0] < MAX_REACH - SPACING else "full")
    return az, el, reach, cov


def sky(t):
    """Invented sky. DEMO: Sun sweeps 7.5 deg/h so things happen in 48 h."""
    sun_az = (210.0 + 7.5 * t) % 360.0
    sun_el = 1.45 + 1.1 * math.sin(2 * math.pi * t / 30.0)
    earth_az = (135.0 + 6.0 * math.sin(2 * math.pi * t / 40.0)) % 360.0
    earth_el = 3.2 + 1.6 * math.sin(2 * math.pi * t / 26.0 + 1.0)
    return (round(sun_az, 4), round(sun_el, 4)), (round(earth_az, 4), round(earth_el, 4))


def horizon_at(sk_az, sk_el, az):
    """Linear in azimuth with 360-wrap (generator side only)."""
    f = (az % 360.0) / BIN
    i0 = int(math.floor(f)) % len(sk_el)
    i1 = (i0 + 1) % len(sk_el)
    t = f - math.floor(f)
    return sk_el[i0] * (1 - t) + sk_el[i1] * t


def first_hit(pts, h_obs, el):
    for p in pts:
        if angle(h_obs, p[3], p[0]) > el:
            return p
    return None


def longest_run(flags, want):
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f == want else 0
        best = max(best, cur)
    return best


def scenario(sid, label, kind, desc, vals, ox, oy, dx_local_e, mast, times, skies):
    east, north = local_basis(L_DEG)
    obs = (east[0] * dx_local_e, east[1] * dx_local_e)
    ground, _ = dem_at(vals, ox, oy, *obs)
    h_obs = ground + mast
    sk_az, sk_el, sk_reach, sk_cov = skyline(vals, ox, oy, obs, h_obs)
    series = {}
    failures = []
    for tgt, idx in (("sun", 0), ("earth", 1)):
        vis, hor, mar, hit = [], [], [], []
        for (s, e) in skies:
            az, el = (s, e)[idx]
            h = horizon_at(sk_az, sk_el, az)
            m = el - h
            vis.append(m > 0); hor.append(round(h, 4)); mar.append(round(m, 4))
            p = None if m > 0 else first_hit(ray(vals, ox, oy, obs, az), h_obs, el)
            hit.append(None if p is None else round(p[0], 1))
        series[tgt] = {"visible": vis, "horizonElDeg": hor, "marginDeg": mar, "firstHitM": hit}
        # one failure per contiguous blocked run: the sample with the worst margin
        k = 0
        while k < len(vis):
            if vis[k]:
                k += 1; continue
            j = k
            while j < len(vis) and not vis[j]:
                j += 1
            worst = min(range(k, j), key=lambda q: mar[q])
            az, el = skies[worst][idx]
            pts = ray(vals, ox, oy, obs, az)
            p = first_hit(pts, h_obs, el)
            step = max(1, len(pts) // 80)
            prof = pts[::step]
            failures.append({
                "id": f"{sid}-{tgt}-{worst:03d}",
                "target": tgt,
                "sampleIndex": worst,
                "time": times[worst],
                "azimuthDeg": az,
                "targetElDeg": el,
                "horizonElDeg": hor[worst],
                "marginDeg": mar[worst],
                "blockedSamples": j - k,
                "firstHit": None if p is None else {
                    "distanceM": round(p[0], 1), "xM": round(p[1], 2), "yM": round(p[2], 2),
                    "heightM": round(p[4], 3), "cell": list(p[5])},
                "profile": {
                    "distanceM": [round(q[0], 1) for q in prof],
                    "terrainM": [round(q[3], 3) for q in prof],
                    "rayM": [round(h_obs + q[0] * math.tan(math.radians(el)), 3) for q in prof],
                },
            })
            k = j
    both = [a and b for a, b in zip(series["sun"]["visible"], series["earth"]["visible"])]
    n = len(both)
    sun_frac = sum(series["sun"]["visible"]) / n
    earth_frac = sum(series["earth"]["visible"]) / n
    both_frac = sum(both) / n
    dark = longest_run(series["sun"]["visible"], False)
    black = longest_run(series["earth"]["visible"], False)

    def metric(mid, lab, value, unit, op=None, thr=None):
        m = {"id": mid, "label": lab, "value": round(value, 4), "unit": unit}
        if op:
            m["constraint"] = {"op": op, "threshold": thr}
            m["marginToLimit"] = round((thr - value) if op == "<=" else (value - thr), 4)
            m["pass"] = m["marginToLimit"] >= 0
        return m

    return {
        "id": sid, "label": label, "kind": kind, "description": desc,
        "observer": {"xM": round(obs[0], 3), "yM": round(obs[1], 3), "groundM": round(ground, 3), "mastM": mast},
        "skyline": {"azimuthDeg": sk_az, "elevationDeg": sk_el, "reachM": sk_reach, "coverage": sk_cov},
        "samples": {"sun": series["sun"], "earth": series["earth"], "both": {"visible": both}},
        "metrics": [
            metric("sun_fraction", "Sun visible (centre)", 100 * sun_frac, "%", ">=", 60.0),
            metric("earth_fraction", "Earth visible (centre)", 100 * earth_frac, "%", ">=", 50.0),
            metric("both_fraction", "Sun and Earth together", 100 * both_frac, "%"),
            metric("longest_dark", "Longest Sun obstruction", float(dark), "h", "<=", 12.0),
            metric("longest_blackout", "Longest Earth obstruction", float(black), "h", "<=", 10.0),
        ],
        "failures": failures,
    }


def iso(h):
    return f"2026-11-{14 + (14 + h) // 24:02d}T{(14 + h) % 24:02d}:00:00Z"


def main():
    vals, ox, oy = make_dem()
    times = [iso(h) for h in range(SAMPLES)]
    skies = [sky(h) for h in range(SAMPLES)]
    scen = [
        scenario("baseline", "Baseline · 2 m mast", "baseline", "DEMO reference case", vals, ox, oy, 0.0, 2.0, times, skies),
        scenario("mast10", "Mast 10 m", "mast_height", "DEMO: observer raised to 10 m", vals, ox, oy, 0.0, 10.0, times, skies),
        scenario("east100", "Offset +100 m east", "observer_offset", "DEMO: observer moved 100 m local east", vals, ox, oy, 100.0, 2.0, times, skies),
    ]
    bundle = {
        "format": "POLARIS-X5D-v2",
        "schemaVersion": "2.0.0",
        "generatedUTC": "2026-11-14T00:00:00Z",
        "demo": True,
        "producer": {"name": "web/scripts/make_demo_fixture.py", "version": "demo-1"},
        "validation": {
            "status": "DEMO_ONLY",
            "reason": "SYNTHETIC terrain and invented sky for viewer development. Not NASA, not JPL.",
            "gates": [{"gate": "synthetic_fixture", "status": "DEMO", "evidence": "generated by make_demo_fixture.py"}],
        },
        "sources": {"DEMO": "web/scripts/make_demo_fixture.py (synthetic)"},
        "contract": {
            "localAxes": {"x": "grid east metres (south-polar stereographic)", "y": "grid north metres", "z": "elevation metres"},
            "time": "UTC ISO-8601",
            "scenarioAxis": "named deterministic case; never a spatial dimension or probability",
            "visibility": "target centre above finite-DEM skyline (DEMO)",
        },
        "datasets": [{
            "siteId": "demo-ridge",
            "site": {"id": "demo-ridge", "name": "DEMO Ridge (synthetic)", "code": "DEMO",
                     "latitudePlanetocentricDeg": -89.5, "longitudeEastDeg": L_DEG,
                     "projectedMeters": {"x": 0.0, "y": 0.0}, "coordinateRole": "synthetic"},
            "dem": {"kind": "demo", "layer": "synthetic", "siteId": "demo-ridge", "n": N, "spacing": SPACING,
                    "originX": ox, "originY": oy, "values": vals, "source": "synthetic",
                    "verticalUnits": "meters", "frame": "DEMO grid (south-polar stereographic axes)",
                    "rowOrder": "south-to-north after explicit source flip"},
            "localDem": None,
            "ephemeris": {"kind": "demo-sky", "source": "invented", "frame": "DEMO",
                          "longitudeConvention": "east-positive",
                          "azimuthConvention": "clockwise from north: N=0, E=90, S=180, W=270",
                          "timeScale": "UTC", "sampling": "60 min", "records": [],
                          "samples": [{"time": t, "sun": {"az": s[0], "el": s[1]}, "earth": {"az": e[0], "el": e[1]}}
                                      for t, (s, e) in zip(times, skies)]},
            "validation": {"status": "DEMO_ONLY", "gates": []},
            "derived": {
                "producer": {"name": "make_demo_fixture.py", "version": "demo-1"},
                "status": "DEMO_ONLY",
                "frame": {"localNorthInGrid": list(local_basis(L_DEG)[1]), "localEastInGrid": list(local_basis(L_DEG)[0]),
                          "note": "rotation from site longitude; DEMO"},
                "skylineBinDeg": BIN,
                "scenarios": scen,
            },
        }],
    }
    out = Path(__file__).resolve().parent.parent / "public" / "bundles" / "demo-fixture.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, separators=(",", ":")))
    b = scen[0]
    print("wrote", out, out.stat().st_size, "bytes")
    for s in scen:
        print(s["id"], [(m["id"], m["value"]) for m in s["metrics"]], "failures", len(s["failures"]))


if __name__ == "__main__":
    main()
