#!/usr/bin/env python3
"""Generate the DEMO-ONLY decision-evidence fixture: web/public/bundles/demo-decision-fixture.json.

!!! SYNTHETIC. NOT NASA TERRAIN. NOT JPL EPHEMERIS. NOT A SCIENCE RESULT. !!!

Purpose: let the b-experience viewer build and test B1-B4 (Margin Ribbon, Ridge of Record, Certainty curve,
Coverage Gauge) before the science branch ships A1-A4. The JSON is shaped exactly like the fields named in
claude/IMPLEMENTATION_PROMPT_DECISION_EVIDENCE_2026-11-14.md (Part A) and web/docs/VIEWER_BUNDLE_CONTRACT.md
("Decision evidence"). Every number here is invented by this script, in Python, on synthetic terrain; the viewer
never computes any of it.

What is simulated (DEMO only):
- "near_5m" tile = the inner square of half-width NEAR_HALF_M around the observer; everything outside is labelled
  "far_80m". Only the inner square is perturbed in the clones, mirroring the real situation (PGDA 78 clones cover the
  5 m tile only).
- N_CLONES alternate terrain maps = nominal DEM + smooth deterministic noise inside the near tile.
Deterministic: the same output bytes every run.
"""
import json
import math
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_demo_fixture as base  # noqa: E402  (reuse the DEMO terrain, sky and scenario builder)

base.MAX_REACH = 3080.0      # rays leave the 6 km crop along the grid axes -> some truncated bins to exercise hatching
NEAR_HALF_M = 1500.0         # DEMO stand-in for the 5 m clone tile
N_CLONES = 10
CLONE_SIGMA_M = 6.0
MASTS = [1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0]
REQUIREMENTS = [
    {"metric": "sun_centre_pct", "label": "Sun centre visible", "op": ">=", "threshold": 70.0, "unit": "%"},
    {"metric": "both_centre_pct", "label": "Sun and Earth together", "op": ">=", "threshold": 40.0, "unit": "%"},
]
CRITICAL_DEG = 1.0
CLUSTER_M = 2 * base.SPACING  # "within 2 far-field cells" (DEMO grid cell = 50 m)
RUNNER_UP_MIN_CELLS = 2


def make_dem():
    """DEMO terrain for this fixture: mild bowl, a near knoll (local E-SE, inside the near tile), a finite ridge
    segment to the local south-west and a distant massif to the local north-west (both outside the near tile),
    plus a small bump 350 m local south so that low masts depend on near terrain."""
    east, north = base.local_basis(base.L_DEG)
    half = (base.N - 1) * base.SPACING / 2
    feats = [  # (local east m, local north m, height m, sigma m)
        (1100.0, -190.0, 70.0, 300.0),    # knoll ~1.1 km, az ~100 deg (blocks Earth)
        (-60.0, -350.0, 6.0, 90.0),       # small bump ~0.35 km, az ~190 deg
        (-2100.0, 1500.0, 95.0, 380.0),   # massif ~2.6 km, az ~306 deg
    ]
    vals = []
    for j in range(base.N):
        for i in range(base.N):
            x = -half + i * base.SPACING
            y = -half + j * base.SPACING
            le = x * east[0] + y * east[1]
            ln = x * north[0] + y * north[1]
            r = math.hypot(x, y)
            z = 1500.0 + 0.0002 * r * r / 100.0
            # finite ridge segment, axis NW-SE, centred 1.9 km local south-west, 1.8 km long
            u = (le - ln) / math.sqrt(2) - 0.0          # along-axis coordinate
            w = (le + ln) / math.sqrt(2) + 1900.0       # across-axis offset from the axis
            z += 75.0 * math.exp(-(w / 240.0) ** 2) * math.exp(-max(0.0, abs(u) - 900.0) ** 2 / (250.0 ** 2))
            for fe, fn, fh, fs in feats:
                z += fh * math.exp(-(((le - fe) ** 2 + (ln - fn) ** 2) / (fs * fs)))
            vals.append(round(z, 3))
    return vals, -half, -half


def sky(t):
    """Invented sky (DEMO). Same Sun as make_demo_fixture; Earth centred on az 100 deg so it does not sit on a grid
    axis (where the square crop truncates rays)."""
    (sa, se), (ea, ee) = base.sky(t)
    return (sa, se), (round((100.0 + 6.0 * math.sin(2 * math.pi * t / 40.0)) % 360.0, 4), ee)


def near(x, y, obs):
    return abs(x - obs[0]) <= NEAR_HALF_M and abs(y - obs[1]) <= NEAR_HALF_M


def clone_dem(vals, ox, oy, obs, k):
    """Nominal DEM + smooth noise (sum of a few random bumps) inside the near tile only."""
    rnd = random.Random(1000 + k)
    bumps = [(rnd.uniform(-NEAR_HALF_M, NEAR_HALF_M), rnd.uniform(-NEAR_HALF_M, NEAR_HALF_M),
              rnd.uniform(150, 450), rnd.gauss(0, CLONE_SIGMA_M)) for _ in range(14)]
    out = list(vals)
    n = base.N
    for j in range(n):
        for i in range(n):
            x = ox + i * base.SPACING
            y = oy + j * base.SPACING
            if not near(x, y, obs):
                continue
            dz = sum(a * math.exp(-((x - obs[0] - bx) ** 2 + (y - obs[1] - by) ** 2) / (2 * s * s)) for bx, by, s, a in bumps)
            out[j * n + i] = round(out[j * n + i] + dz, 3)
    return out


def rays_for(vals, ox, oy, obs):
    return [base.ray(vals, ox, oy, obs, k * base.BIN) for k in range(int(360 / base.BIN))]


def skyline_from_rays(rays, h_obs):
    el, arg = [], []
    for pts in rays:
        angs = [base.angle(h_obs, p[3], p[0]) for p in pts]
        k = max(range(len(angs)), key=lambda q: angs[q])
        el.append(angs[k]); arg.append((k, angs))
    return el, arg


def series_metrics(sk_el, skies):
    sun = [s[1] - base.horizon_at(None, sk_el, s[0]) > 0 for s, _ in skies]
    earth = [e[1] - base.horizon_at(None, sk_el, e[0]) > 0 for _, e in skies]
    n = len(sun)
    return {"sun_centre_pct": 100 * sum(sun) / n, "both_centre_pct": 100 * sum(a and b for a, b in zip(sun, earth)) / n}


def pct(xs, q):
    xs = sorted(xs)
    pos = (len(xs) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def latlon(site_lat, site_lon, gx, gy):
    """DEMO south-polar stereographic inverse around the demo site (labelled DEMO; not a mapping product)."""
    rho0 = 2 * base.R_MOON * math.tan(math.radians(90 + site_lat) / 2)
    x0, y0 = rho0 * math.sin(math.radians(site_lon)), rho0 * math.cos(math.radians(site_lon))
    x, y = x0 + gx, y0 + gy
    rho = math.hypot(x, y)
    return -90 + 2 * math.degrees(math.atan(rho / (2 * base.R_MOON))), math.degrees(math.atan2(x, y))


def attribution(rays, arg, obs, skies, sun_vis, earth_vis, site):
    nb = len(rays)
    per = {"ctrl_idx": [], "gap_deg": [], "source": [], "dist_km": [], "ridge_id": []}
    pts = []
    min_sep = RUNNER_UP_MIN_CELLS * base.SPACING
    for b in range(nb):
        k, angs = arg[b]
        p = rays[b][k]
        others = [angs[q] for q in range(len(angs)) if abs(rays[b][q][0] - p[0]) >= min_sep]
        gap = angs[k] - max(others) if others else None
        src = "near_5m" if near(p[1], p[2], obs) else "far_80m"
        per["ctrl_idx"].append(k)
        per["gap_deg"].append(None if gap is None else round(gap, 4))
        per["source"].append(src)
        per["dist_km"].append(round(p[0] / 1000, 4))
        pts.append(p)
    # cluster consecutive bins whose controlling points lie within CLUSTER_M of each other (wrap through north)
    lab = [0] * nb
    cur = 0
    for b in range(1, nb):
        if math.hypot(pts[b][1] - pts[b - 1][1], pts[b][2] - pts[b - 1][2]) > CLUSTER_M:
            cur += 1
        lab[b] = cur
    if cur > 0 and math.hypot(pts[0][1] - pts[-1][1], pts[0][2] - pts[-1][2]) <= CLUSTER_M:
        lab = [0 if x == cur else x for x in lab]
    ids = sorted(set(lab), key=lambda c: next(b for b in range(nb) if lab[b] == c))
    name = {c: f"R{i + 1:02d}" for i, c in enumerate(ids)}
    per["ridge_id"] = [name[c] for c in lab]
    stats = {name[c]: {"sun_loss_h": 0, "earth_loss_h": 0, "ctrl_h": 0, "earth_ctrl_h": 0} for c in ids}
    for i, (s, e) in enumerate(skies):
        bs = int(round(s[0] / base.BIN)) % nb
        be = int(round(e[0] / base.BIN)) % nb
        stats[per["ridge_id"][bs]]["ctrl_h"] += 1
        stats[per["ridge_id"][be]]["earth_ctrl_h"] += 1
        if not sun_vis[i]:
            stats[per["ridge_id"][bs]]["sun_loss_h"] += 1
        if not earth_vis[i]:
            stats[per["ridge_id"][be]]["earth_loss_h"] += 1
    ridges = []
    for c in ids:
        rid = name[c]
        bins = [b for b in range(nb) if lab[b] == c]
        # span: start = first bin after a bin of another ridge, going clockwise
        start = next((b for b in bins if lab[(b - 1) % nb] != c), bins[0])
        end = next((b for b in bins if lab[(b + 1) % nb] != c), bins[-1])
        cx = statistics.fmean(pts[b][1] for b in bins)
        cy = statistics.fmean(pts[b][2] for b in bins)
        lat, lon = latlon(site["latitudePlanetocentricDeg"], site["longitudeEastDeg"], cx, cy)
        srcs = [per["source"][b] for b in bins]
        ridges.append({
            "id": rid,
            "centroid_lat": round(lat, 6), "centroid_lon": round(lon, 6),
            "centroid_x_m": round(cx, 2), "centroid_y_m": round(cy, 2),
            "dist_km": round(statistics.fmean(pts[b][0] for b in bins) / 1000, 3),
            "az_span_deg": [start * base.BIN, end * base.BIN],
            "height_m": round(max(pts[b][4] for b in bins), 2),
            "source": max(set(srcs), key=srcs.count),
            **stats[rid],
            "n_bins": len(bins),
        })
    ridges.sort(key=lambda r: (-r["sun_loss_h"], -r["ctrl_h"], r["id"]))
    return {"scenario_id": "baseline", "ridges": ridges, "per_bin": per}


def main():
    vals, ox, oy = make_dem()
    times = [base.iso(h) for h in range(base.SAMPLES)]
    skies = [sky(h) for h in range(base.SAMPLES)]
    obs = (0.0, 0.0)
    ground, _ = base.dem_at(vals, ox, oy, *obs)

    scen = [base.scenario("baseline", "Baseline · 2 m mast", "baseline", "DEMO reference case", vals, ox, oy, 0.0, 2.0, times, skies)]
    for m in MASTS:
        if m == 2.0:
            continue
        sid = f"mast{m:g}"
        scen.append(base.scenario(sid, f"Mast {m:g} m", "mast_height", f"DEMO: observer raised to {m:g} m", vals, ox, oy, 0.0, m, times, skies))
    scen.append(base.scenario("east100", "Offset +100 m east", "observer_offset", "DEMO: observer moved 100 m local east", vals, ox, oy, 100.0, 2.0, times, skies))
    b0 = scen[0]

    # A2: certainty sweep (nominal + clones) and A4 clone envelope at the baseline mast
    dems = [vals] + [clone_dem(vals, ox, oy, obs, k) for k in range(1, N_CLONES + 1)]
    all_rays = [rays_for(d, ox, oy, obs) for d in dems]
    curve, env = [], {"sun": [[] for _ in times], "earth": [[] for _ in times]}
    by_mast = {}
    grounds = [base.dem_at(d, ox, oy, *obs)[0] for d in dems]
    for m in MASTS:
        res = []
        for di, rays in enumerate(all_rays):
            sk_el, _ = skyline_from_rays(rays, grounds[di] + m)
            res.append(series_metrics(sk_el, list(skies)))
            if m == 2.0 and di > 0:
                for i, (s, e) in enumerate(skies):
                    env["sun"][i].append(s[1] - base.horizon_at(None, sk_el, s[0]))
                    env["earth"][i].append(e[1] - base.horizon_at(None, sk_el, e[0]))
        by_mast[m] = res
        for req in REQUIREMENTS:
            key = req["metric"]
            clones = [r[key] for r in res[1:]]
            ok = sum(1 for x in clones if (x >= req["threshold"] if req["op"] == ">=" else x <= req["threshold"]))
            curve.append({
                "mast_m": m, "metric": key, "nominal": round(res[0][key], 3),
                "min": round(min(clones), 3), "p10": round(pct(clones, 0.1), 3), "median": round(pct(clones, 0.5), 3),
                "p90": round(pct(clones, 0.9), 3), "max": round(max(clones), 3),
                "n_clones": len(clones), "pass": f"{ok}/{len(clones)}",
            })
    cert = {}
    for req in REQUIREMENTS:
        rows = [c for c in curve if c["metric"] == req["metric"]]
        full = [c["mast_m"] for c in rows if c["pass"].split("/")[0] == c["pass"].split("/")[1]]
        cert[req["metric"]] = min(full) if full else None

    # A1: attribution on the nominal DEM at the baseline mast
    h0 = ground + 2.0
    rays0 = all_rays[0]
    sk_el0, arg0 = skyline_from_rays(rays0, h0)
    att = attribution(rays0, arg0, obs, skies, b0["samples"]["sun"]["visible"], b0["samples"]["earth"]["visible"],
                      {"latitudePlanetocentricDeg": -89.5, "longitudeEastDeg": base.L_DEG})

    # A3: coverage of critical hours (|Sun margin| < CRITICAL_DEG) by the near tile
    sm = b0["samples"]["sun"]["marginDeg"]
    nb = len(rays0)
    crit = [i for i, x in enumerate(sm) if abs(x) < CRITICAL_DEG]
    src_at = [att["per_bin"]["source"][int(round(skies[i][0][0] / base.BIN)) % nb] for i in crit]
    rid_at = [att["per_bin"]["ridge_id"][int(round(skies[i][0][0] / base.BIN)) % nb] for i in crit]
    cov = {
        "critical_threshold_deg": CRITICAL_DEG,
        "n_critical_h": len(crit),
        "covered_frac": round(sum(1 for s in src_at if s == "near_5m") / len(crit), 4) if crit else 0.0,
        "uncovered_ridges": sorted({r for r, s in zip(rid_at, src_at) if s != "near_5m"}),
    }

    # A4: margin series (copied from the baseline scenario) + clone envelope + truncation flags
    cov_bins = b0["skyline"]["coverage"]
    margins = {
        "scenario_id": "baseline",
        "sun_margin_deg": b0["samples"]["sun"]["marginDeg"],
        "earth_margin_deg": b0["samples"]["earth"]["marginDeg"],
        "sun_clone_min_deg": [round(min(x), 4) for x in env["sun"]],
        "sun_clone_max_deg": [round(max(x), 4) for x in env["sun"]],
        "earth_clone_min_deg": [round(min(x), 4) for x in env["earth"]],
        "earth_clone_max_deg": [round(max(x), 4) for x in env["earth"]],
        "n_clones": N_CLONES,
        "sun_truncated": [cov_bins[int(round(s[0] / base.BIN)) % nb] == "truncated" for s, _ in skies],
        "earth_truncated": [cov_bins[int(round(e[0] / base.BIN)) % nb] == "truncated" for _, e in skies],
    }

    east, north = base.local_basis(base.L_DEG)
    bundle = {
        "format": "POLARIS-X5D-v2",
        "schemaVersion": "2.0.0",
        "generatedUTC": "2026-11-14T00:00:00Z",
        "demo": True,
        "producer": {"name": "web/scripts/make_decision_fixture.py", "version": "demo-decision-1"},
        "validation": {
            "status": "DEMO_ONLY",
            "reason": "SYNTHETIC terrain, invented sky and invented alternate terrain maps for viewer development (B1-B4). Not NASA, not JPL, not a science result.",
            "gates": [{"gate": "synthetic_fixture", "status": "DEMO", "evidence": "generated by make_decision_fixture.py"}],
        },
        "sources": {"DEMO": "web/scripts/make_decision_fixture.py (synthetic)"},
        "contract": {
            "localAxes": {"x": "grid east metres (south-polar stereographic)", "y": "grid north metres", "z": "elevation metres"},
            "time": "UTC ISO-8601",
            "scenarioAxis": "named deterministic case; never a spatial dimension or probability",
            "visibility": "target centre above finite-DEM skyline (DEMO)",
            "decisionEvidence": "web/docs/VIEWER_BUNDLE_CONTRACT.md#decision-evidence (A1-A4)",
            "cloneSpread": "pass on k of N alternate terrain maps tested; not a probability",
        },
        "datasets": [{
            "siteId": "demo-ridge",
            "site": {"id": "demo-ridge", "name": "DEMO Ridge (synthetic, decision evidence)", "code": "DEMO",
                     "latitudePlanetocentricDeg": -89.5, "longitudeEastDeg": base.L_DEG,
                     "projectedMeters": {"x": 0.0, "y": 0.0}, "coordinateRole": "synthetic"},
            "dem": {"kind": "demo", "layer": "synthetic", "siteId": "demo-ridge", "n": base.N, "spacing": base.SPACING,
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
                "producer": {"name": "make_decision_fixture.py", "version": "demo-decision-1"},
                "status": "DEMO_ONLY",
                "frame": {"localNorthInGrid": list(north), "localEastInGrid": list(east), "note": "rotation from site longitude; DEMO"},
                "skylineBinDeg": base.BIN,
                "scenarios": scen,
                "attribution": att,
                "certainty_curve": curve,
                "certainty_height_m": cert,
                "requirements": REQUIREMENTS,
                "coverage": cov,
                "margins": margins,
                "decision_notes": {
                    "near_tile": f"DEMO: inner {2 * NEAR_HALF_M / 1000:g} km square stands in for the 5 m clone tile",
                    "clones": f"DEMO: {N_CLONES} synthetic alternate terrain maps (smooth noise, sigma ~{CLONE_SIGMA_M:g} m, near tile only)",
                    "cluster": f"controlling points within {CLUSTER_M:g} m of each other in consecutive bins",
                    "runner_up": f"second-best sample at least {RUNNER_UP_MIN_CELLS} DEM cells from the best",
                },
            },
        }],
    }
    out = Path(__file__).resolve().parent.parent / "public" / "bundles" / "demo-decision-fixture.json"
    out.write_text(json.dumps(bundle, separators=(",", ":")))
    print("wrote", out, out.stat().st_size, "bytes")
    for s in scen:
        print(s["id"], [(m["id"], m["value"]) for m in s["metrics"][:3]])
    for c in curve:
        print(c)
    print("certainty", cert)
    print("coverage", cov)
    for r in att["ridges"]:
        print(r)
    print("truncated samples sun/earth", sum(margins["sun_truncated"]), sum(margins["earth_truncated"]))


if __name__ == "__main__":
    main()
