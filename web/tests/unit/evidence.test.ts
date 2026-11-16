import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { binForAzimuth, controllingCells, fmtRidgeDistance, groupAdjacentCells, marginFlagMismatches, mastScenarios, ridgeBins, ridgeForTarget } from '../../src/bundle/evidence';
import { adaptScienceV2 } from '../../src/bundle/scienceV2';

const raw = JSON.parse(readFileSync(resolve(__dirname, '../fixtures/science-v2_site01_ui_fixture_50.json'), 'utf8'));
const b = adaptScienceV2(raw);
const ds = b.datasets[0];
const base = ds.derived!.scenarios[0];
const times = ds.ephemeris.samples.map((s) => Date.parse(s.time));

describe('binForAzimuth', () => {
  it('matches the bundle binning (720 bins CENTRED on i·0.5°; nearest bin, as science/attribution.py)', () => {
    expect(binForAzimuth(0, 720)).toBe(0);
    expect(binForAzimuth(0.24, 720)).toBe(0);
    expect(binForAzimuth(0.26, 720)).toBe(1); // nearest centre, not floor
    expect(binForAzimuth(0.5, 720)).toBe(1);
    expect(binForAzimuth(359.74, 720)).toBe(719);
    expect(binForAzimuth(359.9, 720)).toBe(0); // wraps to the bin centred on 0°
    expect(binForAzimuth(360, 720)).toBe(0);
    expect(binForAzimuth(-0.3, 720)).toBe(719);
  });
});

describe('controllingCells (Ridge of Record tally)', () => {
  it('attributes every blocked Earth sample to a bundle critical cell, never computing one', () => {
    const c = controllingCells(ds.ephemeris.samples, base.samples!.earth, base.skyline!, 'earth', times);
    const blocked = base.samples!.earth.visible.filter((v) => !v).length;
    expect(c.nBlocked).toBe(blocked);
    expect(c.nBlocked).toBeGreaterThan(0);
    const tallied = c.cells.reduce((a, t) => a + t.samples.length, 0);
    expect(tallied + c.nBlockedWithoutCell).toBe(blocked);
    for (const t of c.cells) {
      // every tallied cell is a verbatim bundle cell for one of its bins
      for (const bin of t.bins) expect(base.skyline!.critical![bin].grid_x_m).toBe(t.cell.grid_x_m);
      expect(t.cell.dem).toMatch(/PGDA/);
    }
    // sorted by how many samples they control
    for (let i = 1; i < c.cells.length; i++) expect(c.cells[i - 1].samples.length).toBeGreaterThanOrEqual(c.cells[i].samples.length);
  });
  it('tallies zero cells when nothing is blocked', () => {
    const allClear = { ...base.samples!.sun, visible: base.samples!.sun.visible.map(() => true) };
    expect(controllingCells(ds.ephemeris.samples, allClear, base.skyline!, 'sun', times).cells).toEqual([]);
  });
});

describe('marginFlagMismatches (Margin Ribbon consistency)', () => {
  it('the fixture is self-consistent: sign(margin) == centre visible for every sample, both targets', () => {
    expect(marginFlagMismatches(base.samples!.sun)).toEqual([]);
    expect(marginFlagMismatches(base.samples!.earth)).toEqual([]);
  });
  it('flags a disagreeing sample', () => {
    const bad = { ...base.samples!.sun, visible: base.samples!.sun.visible.map((v, i) => (i === 3 ? !v : v)) };
    expect(marginFlagMismatches(bad)).toEqual([3]);
  });
});

describe('mastScenarios (Certainty Height fallback)', () => {
  it('finds the mast-only scenarios in the bundle, sorted', () => {
    const m = mastScenarios(ds.derived!.scenarios);
    expect(m.map((x) => x.mastM)).toEqual([2, 5, 10]);
  });
});

describe('schema rename', () => {
  it('accepts polaris-science-results-v1 as the same structure', () => {
    const renamed = adaptScienceV2({ ...raw, schema: 'polaris-science-results-v1' });
    expect(renamed.format).toBe('polaris-science-results-v1');
    expect(renamed.datasets[0].derived!.scenarios.length).toBe(ds.derived!.scenarios.length);
  });
  it('passes decision-evidence fields through verbatim (camelCased), never inventing them', () => {
    expect(ds.derived!.attribution).toBeUndefined();
    expect(ds.derived!.coverage).toBeUndefined();
    const withCov = adaptScienceV2({
      ...raw,
      coverage: { method: 'm', footprint: { dem: 'p78' }, critical_margin_deg: 0.25, sun: { controlling_hours_inside: 0.4, critical_hours_inside: null, unknown_hours: 0.1, hours_total: 10 }, earth: { controlling_hours_inside: 1, critical_hours_inside: 1, unknown_hours: 0, hours_total: 5 } },
    });
    expect(withCov.datasets[0].derived!.coverage!.sun.controllingHoursInside).toBe(0.4);
    expect(withCov.datasets[0].derived!.coverage!.criticalMarginDeg).toBe(0.25);
  });
});

describe('groupAdjacentCells (display grouping of adjacent bins)', () => {
  it('merges contiguous bins of the same DEM layer and preserves the sample totals exactly', () => {
    const c = controllingCells(ds.ephemeris.samples, base.samples!.earth, base.skyline!, 'earth', times);
    const g = groupAdjacentCells(c.cells, base.skyline!.azimuthDeg.length);
    expect(g.length).toBeLessThan(c.cells.length);
    expect(g.reduce((a, x) => a + x.samples, 0)).toBe(c.cells.reduce((a, x) => a + x.samples.length, 0));
    for (const grp of g) {
      const sorted = [...grp.bins].sort((a, b) => a - b);
      for (let i = 1; i < sorted.length; i++) expect(sorted[i] - sorted[i - 1]).toBeLessThanOrEqual(2);
      expect(grp.distanceM.min).toBeLessThanOrEqual(grp.distanceM.max);
      for (const cell of grp.cells) expect(cell.cell.dem ?? null).toBe(grp.dem);
    }
  });
  it('wraps a run across 360°', () => {
    const mk = (bin: number, key: string) => ({ key, cell: { distance_m: 100, dem: 'd' }, bins: [bin], azimuthDeg: [0, 0] as [number, number], samples: [1], firstIndex: 1, sampledHours: 1, coverage: [] });
    const g = groupAdjacentCells([mk(719, 'a'), mk(0, 'b'), mk(300, 'c')], 720);
    expect(g.length).toBe(2);
    expect(g.find((x) => x.bins.includes(719))!.bins.sort()).toEqual([0, 719]);
  });
});

describe('IMPLEMENTATION_PROMPT A1–A3 shapes are read verbatim', () => {
  it('A1 attribution: ridges with dist_km / az_span_deg / *_loss_h / ctrl_h', () => {
    const b2 = adaptScienceV2({
      ...raw,
      attribution: { method: 'argmax+cluster', ridges: [{ id: 'r1', centroid_lat: -89.78, centroid_lon: -156.3, dist_km: 0.016, az_span_deg: [119, 123], height_m: 1990.2, source: 'near_5m', sun_loss_h: 19.4, earth_loss_h: 0, ctrl_h: 40 }], per_bin: { ctrl_idx: [], gap_deg: [], source: [] } },
    });
    const a = b2.datasets[0].derived!.attribution!;
    expect(a.ridges[0].azimuthDeg).toEqual([119, 123]);
    expect(a.ridges[0].distanceM).toBe(16);
    expect(a.ridges[0].hours.sun).toEqual({ controlled: 40, lost: 19.4 });
    expect(a.ridges[0].dem).toBe('near_5m');
  });
  it('A3 coverage: covered_frac / critical_threshold_deg', () => {
    const b2 = adaptScienceV2({ ...raw, coverage: { critical_threshold_deg: 1.0, n_critical_h: 31, covered_frac: 0.42, uncovered_ridges: ['r2'] } });
    const c = b2.datasets[0].derived!.coverage!;
    expect(c.sun.controllingHoursInside).toBe(0.42);
    expect(c.criticalMarginDeg).toBe(1.0);
    expect(c.sun.hoursTotal).toBe(31);
    expect(c.uncoveredRidges).toEqual(['r2']);
    expect(c.footprint.dem).toMatch(/PGDA product 78/);
  });
  it('A2 certainty curve rows + certainty_height_m, 1 m and 10 m points carried exactly', () => {
    const rows = [
      { mast_m: 1, metric: 'sun_centre_pct', nominal: 94.4, min: 88.7, p10: 89, median: 92, p90: 94, max: 94.4, n_clones: 6, pass: '0/6' },
      { mast_m: 10, metric: 'sun_centre_pct', nominal: 100, min: 100, p10: 100, median: 100, p90: 100, max: 100, n_clones: 6, pass: '6/6' },
      { mast_m: 1, metric: 'both_centre_pct', nominal: 72.1, min: 64.4, max: 72.1, n_clones: 6, pass: '6/6' },
    ];
    const b2 = adaptScienceV2({ ...raw, certainty_curve: rows, certainty_height_m: { sun_centre_pct: 10, both_centre_pct: 1 } });
    const c = b2.datasets[0].derived!.certaintyCurve!;
    expect(c.points.map((p) => p.mastM)).toEqual([1, 10]);
    expect(c.points[0].min.sunPct).toBe(88.7);
    expect(c.points[0].min.bothPct).toBe(64.4);
    expect(c.points[0].nPass).toBeNull(); // Sun 0/6 and Sun+Earth 6/6 are marginal counts; no joint count is invented
    expect(c.points[0].passBy).toEqual({ sun_centre_pct: { k: 0, n: 6 }, both_centre_pct: { k: 6, n: 6 } });
    expect(c.points[1].nPass).toBe(6); // single requirement at 10 m: its count is the joint count
    expect(c.minTestedFeasibleMastM).toBe(10); // the largest per-requirement certainty height = all requirements met
    expect(c.agreementMastM).toBeNull(); // not in the A2 shape; never invented
  });
});

describe('real a-science A1 output (science/attribution.py, a-science 13d23d4) — skipped if not synced', () => {
  const p = resolve(__dirname, '../../../data/bundles/site04_roi3_2026-11-14_14d_mast1m.json');
  const has = require('node:fs').existsSync(p) as boolean;
  it.skipIf(!has)('Site04 ROI3 1 m: derived.attribution is read verbatim (R3 = 16 m bump, 19 h Sun loss)', () => {
    const r = JSON.parse(readFileSync(p, 'utf8'));
    const ds2 = adaptScienceV2(r).datasets[0];
    const a = ds2.derived!.attribution!;
    expect(a.ridges.length).toBe(r.derived.attribution.ridges.length);
    expect(a.perBin!.ridgeIdx.length).toBe(720);
    const r3 = a.ridges.find((x) => x.id === 'R3')!;
    const raw3 = r.derived.attribution.ridges.find((x: { id: string }) => x.id === 'R3');
    expect(r3.hours.sun.lost).toBe(raw3.sun_loss_h);
    expect(r3.hours.sun.controlled).toBe(raw3.sun_ctrl_h);
    expect(r3.hours.earth.controlled).toBe(raw3.earth_ctrl_h);
    expect(r3.ofRecord).toBe(raw3.of_record);
    expect(r3.runnerUpGapDeg).toBe(raw3.min_gap_deg);
    expect(r3.distanceM).toEqual({ min: raw3.dist_range_km[0] * 1000, max: raw3.dist_range_km[1] * 1000 });
    expect(a.ridges.filter((x) => x.ofRecord).map((x) => x.id).sort()).toEqual(
      r.derived.attribution.ridges.filter((x: { of_record: boolean }) => x.of_record).map((x: { id: string }) => x.id).sort(),
    );
  });
  it.skipIf(!has)('viewer lookups reproduce the bundle per-ridge loss hours EXACTLY for Sun and Earth (nearest-bin rule); hours are disjoint', () => {
    const r = JSON.parse(readFileSync(p, 'utf8'));
    const d2 = adaptScienceV2(r).datasets[0];
    const a = d2.derived!.attribution!;
    const eph = d2.ephemeris.samples;
    const base2 = d2.derived!.scenarios[0].samples!;
    for (const k of ['sun', 'earth'] as const) {
      const tally = new Map<number, number>();
      eph.forEach((_, i) => {
        if (base2[k].visible[i] !== false) return;
        const now = ridgeForTarget(a, eph, base2[k], k, i, 720)!;
        tally.set(now.ridgeIdx, (tally.get(now.ridgeIdx) ?? 0) + 1);
        expect(now.run!.i0).toBeLessThanOrEqual(i);
        expect(now.run!.i1).toBeGreaterThanOrEqual(i);
      });
      a.ridges.forEach((ridge, idx) => expect(tally.get(idx) ?? 0).toBe(ridge.hours[k].lost));
      // disjoint: per-ridge loss hours sum to the number of blocked samples
      expect(a.ridges.reduce((x, ridge) => x + ridge.hours[k].lost, 0)).toBe(base2[k].visible.filter((x) => !x).length);
    }
    const r3 = a.ridges.find((x) => x.id === 'R3')!;
    expect(r3.reliefM).toBeCloseTo(r.derived.attribution.ridges.find((x: { id: string }) => x.id === 'R3').relief_m, 9);
    expect(fmtRidgeDistance(r3)).toBe('12–169 m');
    expect(fmtRidgeDistance(a.ridges.find((x) => x.id === 'R1')!)).toBe('127.7–129.6 km');
    expect(ridgeBins(a, a.ridges.indexOf(r3)).length).toBe(r.derived.attribution.ridges.find((x: { id: string }) => x.id === 'R3').n_bins);
  });
  it.skipIf(!has)('every Sun-loss hour lands on a bin whose ridge is of record (bundle self-consistency, lookup only)', () => {
    const r = JSON.parse(readFileSync(p, 'utf8'));
    const a = adaptScienceV2(r).datasets[0].derived!.attribution!;
    for (const s of r.samples) {
      if (s.sun.center_visible) continue;
      const ri = a.perBin!.ridgeIdx[binForAzimuth(s.sun.az_deg, 720)];
      expect(ri).not.toBeNull();
      expect(a.ridges[ri!].ofRecord).toBe(true);
    }
  });
});
