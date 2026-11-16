/**
 * Ported from the `integration` build's tests/unit/decision.test.ts (Part B merge, 14 Nov ~14:00 ET), adapted to this
 * tree's normalized types. Fixture: public/bundles/demo-decision-fixture.json (DEMO, scripts/make_decision_fixture.py).
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { validateBundle } from '../../src/bundle/validate';

const fx = resolve(__dirname, '../../public/bundles/demo-decision-fixture.json');
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const raw = (): any => JSON.parse(readFileSync(fx, 'utf8'));

describe('decision-evidence DEMO fixture (A1–A4 shape)', () => {
  it('loads as DEMO and every block is copied, not computed', () => {
    const v = validateBundle(raw());
    expect(v.status).toBe('DEMO');
    const d = v.bundle.datasets[0].derived!;
    const rd = raw().datasets[0].derived; // fresh copy: validateBundle normalizes its input in place
    expect(d.attribution!.ridges.length).toBe(rd.attribution.ridges.length);
    const r05 = d.attribution!.ridges.find((x) => x.id === 'R05')!;
    const raw05 = rd.attribution.ridges.find((x: { id: string }) => x.id === 'R05');
    expect(r05.hours.sun.lost).toBe(raw05.sun_loss_h);
    expect(r05.distanceM).toBe(raw05.dist_km * 1000);
    expect(d.attribution!.perBin!.ridgeIdx.length).toBe(rd.attribution.per_bin.ridge_id.length);
    expect(d.coverage!.sun.controllingHoursInside).toBe(rd.coverage.covered_frac);
    expect(d.coverage!.criticalMarginDeg).toBe(rd.coverage.critical_threshold_deg);
    const c = d.certaintyCurve!;
    expect(c.points.length).toBe(new Set(rd.certainty_curve.map((x: { mast_m: number }) => x.mast_m)).size);
    for (const row of rd.certainty_curve) {
      const p = c.points.find((q) => q.mastM === row.mast_m)!;
      const [k, n] = row.pass.split('/').map(Number);
      expect(p.passBy![row.metric]).toEqual({ k, n });
      if (row.metric === 'sun_centre_pct') expect([p.min.sunPct, p.median!.sunPct, p.max.sunPct]).toEqual([row.min, row.median, row.max]);
    }
    expect(c.heightByRequirement).toEqual(rd.certainty_height_m);
    // one requirement has no certainty height in the sweep -> no mast meets every requirement
    expect(c.minTestedFeasibleMastM).toBeNull();
    expect(d.marginRange!.sun.minDeg).toEqual(rd.margins.sun_clone_min_deg);
    expect(d.marginRange!.scenarioId).toBe(rd.margins.scenario_id);
  });

  it('never invents a joint pass count from marginal ones', () => {
    const c = validateBundle(raw()).bundle.datasets[0].derived!.certaintyCurve!;
    for (const p of c.points) {
      const ks = Object.values(p.passBy!);
      if (ks.length > 1 && !ks.every((x) => x.k === x.n)) expect(p.nPass).toBeNull();
    }
  });

  it('margin sign equals the visibility flag at every sample (A4 acceptance, on the fixture)', () => {
    const d = raw().datasets[0].derived;
    const base = d.scenarios[0].samples;
    for (const t of ['sun', 'earth']) d.margins[`${t}_margin_deg`].forEach((m: number, i: number) => expect(m > 0).toBe(base[t].visible[i]));
  });

  it('certainty curve is monotonic in mast height on the nominal map', () => {
    const curve = raw().datasets[0].derived.certainty_curve as { mast_m: number; metric: string; nominal: number }[];
    for (const metric of ['sun_centre_pct', 'both_centre_pct']) {
      const rows = curve.filter((c) => c.metric === metric).sort((a, b) => a.mast_m - b.mast_m);
      rows.forEach((r, i) => i && expect(r.nominal).toBeGreaterThanOrEqual(rows[i - 1].nominal));
    }
  });

  it('refuses malformed blocks with a specific message', () => {
    const a = raw();
    a.datasets[0].derived.margins.sun_margin_deg.pop();
    expect(() => validateBundle(a)).toThrow(/margins\.sun_margin_deg: expected 48 values/);
    const b = raw();
    b.datasets[0].derived.attribution.ridges[0].source = 'lidar';
    expect(() => validateBundle(b)).toThrow(/source must be near_5m or far_80m/);
    const c = raw();
    c.datasets[0].derived.certainty_curve[0].pass = '11/10';
    expect(() => validateBundle(c)).toThrow(/pass must be "k\/N"/);
    const e = raw();
    e.datasets[0].derived.coverage.covered_frac = 1.4;
    expect(() => validateBundle(e)).toThrow(/covered_frac must be in \[0, 1\]/);
    const f = raw();
    f.datasets[0].derived.attribution.per_bin.ridge_id[3] = 'R99';
    expect(() => validateBundle(f)).toThrow(/"R99" is not a listed ridge/);
  });
});

describe('team requirements (Anish 13:55 ET: Sun ≥ 70 %, Sun+Earth ≥ 40 %)', () => {
  it('attach to a-science metrics only when the bundle declares none, with the source labelled', () => {
    const r = JSON.parse(readFileSync(resolve(__dirname, '../fixtures/science-v2_site01_ui_fixture_50.json'), 'utf8'));
    const m = validateBundle(r).bundle.datasets[0].derived!.scenarios[0].metrics;
    const sun = m.find((x) => x.id === 'sun_center_visible_pct')!;
    expect(sun.constraint).toEqual({ op: '>=', threshold: 70 });
    expect(sun.marginToLimit).toBeCloseTo(sun.value - 70, 10);
    expect(sun.pass).toBe(sun.value >= 70);
    expect(sun.constraintSource).toMatch(/team requirement/);
    const both = m.find((x) => x.id === 'sun_and_earth_center_visible_pct')!;
    expect(both.constraint!.threshold).toBe(40);
    expect(m.find((x) => x.id === 'earth_center_visible_pct')!.constraint).toBeUndefined();
  });
});
