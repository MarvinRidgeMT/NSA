"""L1 — Disc vs centre visibility.

Per hourly sample of the 14-28 Nov 2026 demo window (1 m mast), on the nominal PGDA 78 tile and
the 20 PGDA 78 clones (near field), PGDA 90 80 m far field to 280 km (bundle settings, skyline
reproduced bit-for-bit, test_limits_l1), three visibility variants:

  any   : some part of the disc is above the terrain     m_perp > -r
  centre: the disc centre is above the terrain (bundle)   m_perp > 0
  full  : the whole disc is above the terrain            m_perp > +r

m_perp is the bundle's perpendicular margin (vertical margin / sqrt(1+s^2), s = local skyline
slope). r is the apparent radius the bundle carries per sample (from the Horizons angular
diameter; Sun ~0.267-0.270 deg, Earth ~0.90-0.95 deg). Visible disc fraction is given two ways:
'flat' treats the horizon as locally horizontal across the disc (the assumption the prompt asks to
state) and 'tilted' as a straight line with the local skyline slope (the bundle's disk_fraction).

Longest gap here = longest run of hidden HOURLY samples (x 1 h); the sub-hour version is L2.
"""
from __future__ import annotations

import json

import numpy as np

from .. import crossings as X
from . import skylines as S
from .common import BUNDLES, ROOT, load_bundle, longest_run, write_result

VARIANTS = ('any', 'centre', 'full')
NAC_SUMMARY = ROOT / 'tools' / 'validation' / 'nac' / 'nac_v2_summary.json'
SUN_R_NAC = (0.2620, 0.2666, 0.2711)   # min / typical / max apparent solar radius (0.983-1.017 au)


def hourly_terms(b, sky):
    out = {}
    for body in ('sun', 'earth'):
        mp, m, r, sl = [], [], [], []
        for smp in b['samples']:
            row = smp[body]
            mm = X.margins({'az_deg': row['az_deg'], 'el_deg': row['el_deg'], 'radius_deg': row['radius_deg']}, sky)
            mp.append(np.nan if mm is None else mm['margin_perp_deg'])
            m.append(np.nan if mm is None else mm['margin_deg'])
            sl.append(np.nan if mm is None else mm['slope'])
            r.append(row['radius_deg'])
        out[body] = {k: np.array(v, float) for k, v in (('mp', mp), ('m', m), ('r', r), ('slope', sl))}
    return out


def visible(t, variant):
    mp, r = t['mp'], t['r']
    return {'any': mp > -r, 'centre': mp > 0, 'full': mp > r}[variant]


def disc_fraction(t, flat=True):
    if flat:
        return np.array([X.disk_fraction_visible(m, r, 0.0) for m, r in zip(t['m'], t['r'])])
    return np.array([X.disk_fraction_visible(m, r, s) for m, r, s in zip(t['m'], t['r'], t['slope'])])


def metrics(terms):
    res = {}
    for v in VARIANTS:
        s = visible(terms['sun'], v); e = visible(terms['earth'], v)
        res[v] = {'sun_pct': round(100 * float(s.mean()), 3),
                  'earth_pct': round(100 * float(e.mean()), 3),
                  'sun_and_earth_pct': round(100 * float((s & e).mean()), 3),
                  'longest_sun_gap_h_hourly': longest_run(s),
                  'longest_earth_gap_h_hourly': longest_run(e)}
    for body in ('sun', 'earth'):
        res[f'{body}_mean_disc_fraction_flat'] = round(float(disc_fraction(terms[body], True).mean()), 5)
        res[f'{body}_mean_disc_fraction_tilted'] = round(float(disc_fraction(terms[body], False).mean()), 5)
    return res


def site_result(site, clones=range(1, 21)):
    b = load_bundle(site)
    nom_sky = S.skyline(site)
    nom = hourly_terms(b, nom_sky)
    out = {'nominal': metrics(nom), 'clones': {}}
    for c in clones:
        out['clones'][c] = metrics(hourly_terms(b, S.skyline(site, clone=c)))
    rng = {}
    for v in VARIANTS:
        rng[v] = {}
        for k in ('sun_pct', 'sun_and_earth_pct', 'longest_sun_gap_h_hourly'):
            vals = [out['clones'][c][v][k] for c in clones]
            rng[v][k] = [min(vals), max(vals)]
    out['clone_range'] = rng
    out['per_hour_nominal'] = {
        'utc': [s['utc'] for s in b['samples']],
        'sun_disc_fraction_flat': [round(x, 4) for x in disc_fraction(nom['sun'], True)],
        'sun_disc_fraction_tilted': [round(x, 4) for x in disc_fraction(nom['sun'], False)],
        'earth_disc_fraction_flat': [round(x, 4) for x in disc_fraction(nom['earth'], True)],
        'sun_margin_perp_deg': [round(x, 5) for x in nom['sun']['mp']],
        'sun_radius_deg': [round(x, 6) for x in nom['sun']['r']],
    }
    out['reproduction'] = {'bundle_sun_center_hourly_pct': b['metrics']['sun_center_visible_pct_hourly_samples'],
                           'bundle_sun_earth_center_hourly_pct': b['metrics']['sun_and_earth_center_visible_pct_hourly_samples'],
                           'bundle_clone_sun_pct': b['derived']['margin_series']['sun_center_visible_pct_hourly_by_clone']}
    return out


def nac_rescore(path=NAC_SUMMARY):
    """The NAC v2 crossing is the Sun-CENTRE margin at which the observed-lit fraction reaches 0.5.
    Re-expressed per variant: the variant's own threshold sits at -r / 0 / +r in centre-margin units,
    so the crossing offset from the variant's threshold is crossing - threshold. 'disc fraction >= 0.5'
    with a flat (or straight) horizon is exactly m >= 0, i.e. identical to the centre rule."""
    s = json.loads(path.read_text())
    out = {}
    for area, a in s['areas'].items():
        c = a.get('crossing_deg')
        if c is None:
            continue
        rr = SUN_R_NAC
        out[area] = {
            'crossing_centre_margin_deg': round(c, 4),
            'offset_centre_rule_deg': round(c, 4),
            'offset_disc_fraction_ge_0p5_deg': round(c, 4),
            'offset_full_disc_rule_deg': [round(c - r, 4) for r in rr],
            'offset_any_part_rule_deg': [round(c + r, 4) for r in rr],
            'disc_fraction_at_crossing_flat': [round(X.disk_fraction_visible(c, r, 0.0), 4) for r in rr],
            'crossing_in_solar_radii': [round(c / r, 3) for r in rr],
        }
    return out


README = """# L1 — Disc vs centre visibility

**Label:** PILOT · SOURCE-BASED · UNVALIDATED. Geometric visibility only (not power, not comms).

**Question.** The bundles call the Sun/Earth "visible" when the disc centre is above the terrain horizon. How do the
headline numbers change if "visible" means *any part of the disc* or *the full disc*, and does a disc-based rule explain the
NAC v2 finding that images look lit only when the centre is ~+0.31° to +0.45° above the horizon?

**Method.** `python -m science.limits.l1_disc`. Hourly samples of the 1 m-mast bundles (14–28 Nov 2026, 337 samples),
the bundle's perpendicular margin m⊥ and per-sample apparent radius r (Horizons angular diameter). Skylines recomputed
with the bundle settings (720 bins, 1 m near step, PGDA 90 far field to 280 km); the nominal skyline equals the bundle's
bit-for-bit, and the centre variant reproduces the bundle's 94.362 % / 72.107 % and the clone range. Variants:
any = m⊥ > −r, centre = m⊥ > 0, full = m⊥ > +r. Disc fraction from the circular-segment formula, with the horizon
**assumed locally flat across the disc** ("flat") and, for comparison, as a straight line at the local skyline slope
("tilted", the bundle's own `disk_fraction`). Longest gap counts hidden hourly samples (× 1 h); L2 gives sub-hour gaps.

**Result.** See `result.json` → `sites.<site>.nominal|clone_range`, and the table in `RESULT.md`.

**NAC.** A "disc fraction ≥ 0.5" rule is mathematically the centre rule (flat or straight horizon ⇒ half the disc is up
exactly when the centre is on the horizon), so it does **not** shrink the crossing offset. The observed crossings
(+0.31° region 8, +0.45° region 9) are ≈ 1.2–1.7 solar radii: at the crossing the disc is already fully up under
the flat-horizon assumption. Measured against a full-disc rule the offsets shrink to ≈ +0.05° and +0.18°.

**What it does not show.** It does not say which rule matches a real lander (power depends on panel geometry and on
the partial disc; this is geometry only). Limb darkening is ignored (disc fraction is area, not flux). The NAC re-score uses
the binned crossing, not per-point re-classification; it holds for the two NAC v2 test areas only and does not observe the
Site04 RoI 3 lander point. Sites 07/11 are not included (no local clone tiles or demo-window Horizons series on this Mac).
k of N clones is not a probability.
"""


def table_md(res):
    lines = ['| site | variant | Sun % nominal | Sun % clones | Sun+Earth % nominal | Sun+Earth % clones | longest Sun gap h (hourly) nominal | clones |',
             '|---|---|---|---|---|---|---|---|']
    for site, r in res['sites'].items():
        for v in VARIANTS:
            n = r['nominal'][v]; cr = r['clone_range'][v]
            lines.append(f"| {site} | {v} | {n['sun_pct']:.2f} | {cr['sun_pct'][0]:.2f}–{cr['sun_pct'][1]:.2f} | "
                         f"{n['sun_and_earth_pct']:.2f} | {cr['sun_and_earth_pct'][0]:.2f}–{cr['sun_and_earth_pct'][1]:.2f} | "
                         f"{n['longest_sun_gap_h_hourly']:.0f} | {cr['longest_sun_gap_h_hourly'][0]:.0f}–{cr['longest_sun_gap_h_hourly'][1]:.0f} |")
        lines.append(f"| {site} | mean disc fraction (flat / tilted) | Sun {r['nominal']['sun_mean_disc_fraction_flat']:.4f} / "
                     f"{r['nominal']['sun_mean_disc_fraction_tilted']:.4f} | | Earth {r['nominal']['earth_mean_disc_fraction_flat']:.4f} / "
                     f"{r['nominal']['earth_mean_disc_fraction_tilted']:.4f} | | | |")
    lines += ['', '| NAC area | crossing (centre margin) | offset vs disc-frac ≥ 0.5 | offset vs full-disc rule | disc fraction at crossing (flat) |',
              '|---|---|---|---|---|']
    for a, n in res['nac_v2_rescore'].items():
        lines.append(f"| {a} | {n['crossing_centre_margin_deg']:+.3f}° | {n['offset_disc_fraction_ge_0p5_deg']:+.3f}° | "
                     f"{n['offset_full_disc_rule_deg'][1]:+.3f}° ({n['offset_full_disc_rule_deg'][2]:+.3f} to {n['offset_full_disc_rule_deg'][0]:+.3f}) | "
                     f"{n['disc_fraction_at_crossing_flat'][1]:.3f} |")
    return '# L1 result table\n\nPILOT · SOURCE-BASED · UNVALIDATED. Clone ranges are min–max over 20 PGDA 78 clones (not a probability).\n\n' + '\n'.join(lines) + '\n'


def main():
    res = {'item': 'L1_disc_visibility', 'window_utc': ['2026-11-14T00:00Z', '2026-11-28T00:00Z'], 'mast_m': 1.0,
           'variants': {'any': 'm_perp > -r', 'centre': 'm_perp > 0 (bundle rule)', 'full': 'm_perp > +r'},
           'assumption_flat': 'disc fraction "flat": horizon locally horizontal across the disc (slope 0)',
           'sites': {}}
    for site in BUNDLES:
        res['sites'][site] = site_result(site)
        n = res['sites'][site]['nominal']
        print(site, {v: (n[v]['sun_pct'], n[v]['sun_and_earth_pct'], n[v]['longest_sun_gap_h_hourly']) for v in VARIANTS},
              res['sites'][site]['clone_range']['centre']['sun_pct'], flush=True)
    res['nac_v2_rescore'] = nac_rescore()
    inputs = list(BUNDLES.values()) + [NAC_SUMMARY] + [
        {'path': 'data/cache/p78/* (PGDA 78 Site01/Site04 surf + clones 0001-0020)',
         'sha256': 'per-file SHA-256 recorded in each bundle skyline.dem_layers and derived.margin_series.clones[].near_sha256',
         'note': 'NASA rasters, git-ignored'},
        {'path': 'data/cache/ldem/LDEM_80S_80MPP_ADJ.TIF', 'sha256': S.sites.LDEM_SHA256, 'note': 'PGDA 90, git-ignored'}]
    write_result('L1_disc_visibility', res, inputs, README, {'RESULT.md': table_md(res)})


if __name__ == '__main__':
    main()
