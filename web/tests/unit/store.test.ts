import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { beforeEach, describe, expect, it } from 'vitest';
import { renderHook } from '@testing-library/react';
import { usePolaris } from '../../src/store/store';
import { useView } from '../../src/store/view';
import { loadBundleBytes } from '../../src/bundle/validate';

const buf = readFileSync(resolve(__dirname, '../../public/bundles/demo-fixture.json'));

beforeEach(async () => {
  const lb = await loadBundleBytes(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer, 'demo-fixture.json', 'test');
  usePolaris.setState({ loaded: lb, datasetIdx: 0, scenarioId: 'baseline', utcMs: lb.times[0][0], timeError: null, selectedFailureId: null });
});

describe('one store drives every view', () => {
  it('displayed margins at a sample equal the bundle values exactly', () => {
    const s = usePolaris.getState();
    const sc = s.loaded!.bundle.datasets[0].derived!.scenarios[0];
    for (const k of [0, 7, 23, 47]) {
      s.setSampleIndex(k);
      const { result } = renderHook(() => useView());
      expect(result.current!.sun.marginDeg).toBe(sc.samples.sun.marginDeg[k]);
      expect(result.current!.earth.marginDeg).toBe(sc.samples.earth.marginDeg[k]);
      expect(result.current!.sun.visible).toBe(sc.samples.sun.visible[k]);
      expect(result.current!.sun.az).toBe(s.loaded!.bundle.datasets[0].ephemeris.samples[k].sun.az);
    }
  });
  it('refuses times outside coverage and keeps the previous time', () => {
    const s = usePolaris.getState();
    const before = s.utcMs;
    expect(s.setTime(Date.parse('2026-11-13T00:00:00Z'))).toBe(false);
    expect(usePolaris.getState().utcMs).toBe(before);
    expect(usePolaris.getState().timeError).toMatch(/outside bundle coverage/);
    expect(s.setTime(Date.parse('2026-11-14T15:30:00Z'))).toBe(true);
    expect(usePolaris.getState().timeError).toBeNull();
  });
  it('scenario switch changes margins; time and site stay', () => {
    const s = usePolaris.getState();
    s.setSampleIndex(10);
    const a = renderHook(() => useView()).result.current!;
    s.setScenario('mast10');
    const b = renderHook(() => useView()).result.current!;
    expect(b.utcMs).toBe(a.utcMs);
    expect(b.sun.az).toBe(a.sun.az);
    expect(b.sun.marginDeg).not.toBe(a.sun.marginDeg);
  });
  it('selecting a failure seeks to its sample', () => {
    const s = usePolaris.getState();
    const f = s.loaded!.bundle.datasets[0].derived!.scenarios[0].failures[1];
    s.selectFailure(f.id);
    const st = usePolaris.getState();
    expect(st.selectedFailureId).toBe(f.id);
    expect(st.utcMs).toBe(st.loaded!.times[0][f.sampleIndex]);
  });
});
