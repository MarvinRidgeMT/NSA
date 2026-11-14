import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { beforeEach, describe, expect, it } from 'vitest';
import { renderHook } from '@testing-library/react';
import { validateBundle, loadBundleBytes } from '../../src/bundle/validate';
import { usePolaris } from '../../src/store/store';
import { useView } from '../../src/store/view';
import type { RawScienceV2 } from '../../src/bundle/scienceV2';

const fxPath = resolve(__dirname, '../fixtures/science-v2_site01_ui_fixture_50.json');
const raw = (): RawScienceV2 => JSON.parse(readFileSync(fxPath, 'utf8'));

describe('science-bundle-v2 (Person A) adapter', () => {
  it('adapts the UI fixture without changing any number', () => {
    const r = raw();
    const v = validateBundle(r);
    expect(v.bundle.format).toBe('science-bundle-v2');
    expect(v.status).toBe('SOURCE-BASED UNVALIDATED');
    const ds = v.bundle.datasets[0];
    expect(ds.dem).toBeUndefined();
    expect(ds.snapToSamples).toBe(true);
    expect(v.times[0].length).toBe(50);
    const base = ds.derived!.scenarios[0];
    expect(base.skyline!.elevationDeg).toEqual(r.skyline.elevation_deg);
    expect(base.skyline!.critical).toBe(r.skyline.critical);
    r.samples.forEach((s, i) => {
      expect(ds.ephemeris.samples[i].sun.az).toBe(s.sun.az_deg);
      expect(base.samples!.sun.marginDeg[i]).toBe(s.sun.margin_deg);
      expect(base.samples!.earth.visible[i]).toBe(s.earth.center_visible);
      expect(base.samples!.sun.diskFraction![i]).toBe(s.sun.disk_fraction);
    });
    expect(base.metrics.find((m) => m.id === 'sun_center_visible_pct')!.value).toBe(r.metrics.sun_center_visible_pct);
  });

  it('carries all 22 scenarios with the bundle deltas, repair included', () => {
    const r = raw();
    const ds = validateBundle(r).bundle.datasets[0];
    const scs = ds.derived!.scenarios;
    expect(scs.length).toBe(1 + r.scenarios!.length);
    const rep = r.scenarios!.find((s) => s.family === 'repair')!;
    const a = scs.find((s) => s.id === rep.id)!;
    expect(a.samples).toBeUndefined();
    expect(a.metrics.find((m) => m.id === 'sun_and_earth_center_visible_pct')!.delta).toBe(rep.delta_vs_baseline!.sun_and_earth_center_visible_pct);
    expect(a.label).toMatch(/^Repair: 100 m E, 100 m N, mast 10 m$/);
  });

  it('shows the status of every validation check and treats unknown overall status as DEMO', () => {
    const r = raw();
    const ds = validateBundle(r).bundle.datasets[0];
    expect(ds.validation.gates.map((g) => g.status)).toContain('NOT_RUN');
    r.validation_status.overall = 'SOMETHING ELSE';
    expect(validateBundle(r).status).toBe('DEMO');
  });

  it('refuses inconsistent skylines and non-boolean visibility', () => {
    const a = raw();
    a.skyline.elevation_deg.pop();
    expect(() => validateBundle(a)).toThrow(/inconsistent/);
    const b = raw();
    (b.samples[3].sun as { center_visible: unknown }).center_visible = 'yes';
    expect(() => validateBundle(b)).toThrow(/center_visible/);
  });
});

describe('contract rules in the store', () => {
  beforeEach(async () => {
    const buf = readFileSync(fxPath);
    const lb = await loadBundleBytes(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer, 'fx.json', 'test');
    usePolaris.setState({ loaded: lb, datasetIdx: 0, scenarioId: 'baseline', utcMs: lb.times[0][0], timeError: null, timeNote: null });
  });
  it('snaps any requested time to a sample (no interpolation between samples)', () => {
    const s = usePolaris.getState();
    const t = s.loaded!.times[0];
    s.setTime(t[3] + 0.4 * (t[4] - t[3]));
    expect(usePolaris.getState().utcMs).toBe(t[3]);
    expect(usePolaris.getState().timeNote).toMatch(/snapped/);
    s.setTime(t[3] + 0.6 * (t[4] - t[3]));
    expect(usePolaris.getState().utcMs).toBe(t[4]);
  });
  it('a metrics-only scenario keeps the baseline series and says so', () => {
    const r = raw();
    const rep = r.scenarios!.find((s) => s.family === 'repair')!;
    usePolaris.getState().setScenario(rep.id);
    usePolaris.getState().setSampleIndex(10);
    const v = renderHook(() => useView()).result.current!;
    expect(v.seriesIsBaseline).toBe(true);
    expect(v.sun.marginDeg).toBe(r.samples[10].sun.margin_deg);
    expect(v.scenario!.id).toBe(rep.id);
  });
});

const full = resolve(__dirname, '../../../data/bundles/site01_2026-11-14_14d.json');
describe.runIf(existsSync(full))('full Site01 a-science bundle', () => {
  it('validates with 337 samples, 720 bins, 22 scenarios', () => {
    const v = validateBundle(JSON.parse(readFileSync(full, 'utf8')));
    expect(v.times[0].length).toBe(337);
    expect(v.bundle.datasets[0].derived!.scenarios[0].skyline!.azimuthDeg.length).toBe(720);
    expect(v.bundle.datasets[0].derived!.scenarios.length).toBe(23);
  });
});
