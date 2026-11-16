import { existsSync, readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { resolve } from 'node:path';
import { beforeAll, describe, expect, it } from 'vitest';
import {
  CubeError,
  cell,
  derivedCell,
  flatIndex,
  parseMaybeGzip,
  slice1d,
  validateCube,
  type ScenarioCube,
} from '../../src/bundle/scenarioCube';

/** Tiny synthetic cube: T(3) × D(2) × S(4). value = 100·t + 10·d + s, so every cell is checkable by hand. */
function synth(): ScenarioCube {
  const vals: number[] = [];
  for (let t = 0; t < 3; t++) for (let d = 0; d < 2; d++) for (let s = 0; s < 4; s++) vals.push(100 * t + 10 * d + s);
  return {
    schema: 'scenario-cube-v1',
    cube_id: 'synthetic',
    site_id: 'test',
    label: 'DEMO',
    generated_utc: '2026-11-15T00:00:00Z',
    dims: [
      { name: 'T', kind: 'uncertainty_terrain', values: ['nominal', 'c1', 'c2'], units: '', label: 'T', nominal_index: 0 },
      { name: 'D_mast', kind: 'design', values: [1, 2], units: 'm', label: 'mast' },
      { name: 'S', kind: 'schedule', values: [0, 1, 2, 3], units: 'h', label: 'start' },
    ],
    metrics: {
      v: { units: '%', label: 'v', dtype: 'int32', values: vals, provenance: 'synthetic', scale: 0.5 },
      w: { units: 'h', label: 'w', dtype: 'int32', values: vals.map((x, i) => (i === 5 ? null : x)), provenance: 'synthetic' },
    },
    missing: { encoding: 'sparse-flat-index', by_metric: { w: [5] } },
    derived: {
      band_over_T: {
        dims: ['D_mast', 'S'],
        metrics: { v_min: { units: '%', label: 'min', dtype: 'int32', values: [0, 1, 2, 3, 10, 11, 12, 13], provenance: 'x', scale: 0.5 } },
        method: 'min over T',
      },
    },
    provenance: { inputs: [{ path: 'x', sha256: 'a'.repeat(64) }], command: 'x', code_commit: 'x' },
  };
}

describe('scenario cube contract (docs/SCENARIO_CUBE_CONTRACT.md)', () => {
  it('row-major flat index and scale', () => {
    const c = validateCube(synth());
    expect(flatIndex(c.dims, { T: 2, D_mast: 1, S: 3 })).toBe(23);
    expect(cell(c, 'v', { T: 2, D_mast: 1, S: 3 })).toBe(213 * 0.5);
    expect(cell(c, 'w', { T: 0, D_mast: 1, S: 1 })).toBeNull();
    expect(slice1d(c, 'v', 'S', { T: 1, D_mast: 0 })).toEqual([50, 50.5, 51, 51.5]);
    expect(derivedCell(c, 'band_over_T', 'v_min', { D_mast: 1, S: 2 })).toBe(6);
  });
  it('rejects broken cubes', () => {
    const wrongLen = synth();
    wrongLen.metrics.v.values.pop();
    expect(() => validateCube(wrongLen)).toThrow(CubeError);
    const badKind = synth();
    (badKind.dims[0] as { kind: string }).kind = 'probability';
    expect(() => validateCube(badKind)).toThrow(/kind/);
    const silentNull = synth();
    silentNull.metrics.v.values[3] = null;
    expect(() => validateCube(silentNull)).toThrow(/not declared missing/);
    const badMask = synth();
    badMask.missing.by_metric.w = [6];
    expect(() => validateCube(badMask)).toThrow(/not null/);
    expect(() => flatIndex(synth().dims, { T: 3, D_mast: 0, S: 0 })).toThrow(CubeError);
  });
  it('parses gzip and plain JSON', async () => {
    const plain = new TextEncoder().encode(JSON.stringify({ a: 1 }));
    expect(await parseMaybeGzip(plain.buffer)).toEqual({ a: 1 });
    const { gzipSync } = await import('node:zlib');
    const gz = gzipSync(Buffer.from(JSON.stringify({ b: 2 })));
    expect(await parseMaybeGzip(gz.buffer.slice(gz.byteOffset, gz.byteOffset + gz.byteLength))).toEqual({ b: 2 });
  });
});

const real = resolve(__dirname, '../../../data/cubes/site04_roi3/centre_mast_schedule.json.gz');
const bundle = resolve(__dirname, '../../../data/bundles/site04_roi3_2026-11-14_14d_mast1m.json');
describe.skipIf(!existsSync(real))('Site04 RoI 3 cube (built by science/cube/build_cube.py)', () => {
  let c: ScenarioCube;
  let b: { metrics: Record<string, number> };
  beforeAll(() => {
    c = validateCube(JSON.parse(gunzipSync(readFileSync(real)).toString('utf8')));
    b = JSON.parse(readFileSync(bundle, 'utf8'));
  });
  it('baseline cell equals the bundle hourly-sample metrics (94.36 % / 72.11 % / 19 h)', () => {
    const at = { T: 0, D_mast: 0, S: 0 };
    expect(Number(cell(c, 'sun_pct', at)!.toFixed(3))).toBe(b.metrics.sun_center_visible_pct_hourly_samples);
    expect(Number(cell(c, 'sun_earth_pct', at)!.toFixed(3))).toBe(b.metrics.sun_and_earth_center_visible_pct_hourly_samples);
    expect(cell(c, 'sun_gap_h', at)).toBe(19);
    const clones = Array.from({ length: 20 }, (_, k) => cell(c, 'sun_pct', { T: k + 1, D_mast: 0, S: 0 })!);
    expect(Math.min(...clones)).toBeCloseTo(87.537, 2);
    expect(Math.max(...clones)).toBeCloseTo(97.329, 2);
  });
  it('10 random cells: slice equals the raw flat array', () => {
    let seed = 5;
    const rnd = (n: number) => ((seed = (seed * 1103515245 + 12345) % 2 ** 31), seed % n);
    for (let i = 0; i < 10; i++) {
      const at = { T: rnd(21), D_mast: rnd(10), S: rnd(8761) };
      const flat = (at.T * 10 + at.D_mast) * 8761 + at.S;
      expect(cell(c, 'sun_earth_pct', at)).toBe((c.metrics.sun_earth_pct.values[flat] as number) * c.metrics.sun_earth_pct.scale!);
      const lo = derivedCell(c, 'band_over_T', 'sun_earth_pct_min', at)!;
      const hi = derivedCell(c, 'band_over_T', 'sun_earth_pct_max', at)!;
      const all = Array.from({ length: 21 }, (_, t) => cell(c, 'sun_earth_pct', { ...at, T: t })!);
      expect(lo).toBe(Math.min(...all));
      expect(hi).toBe(Math.max(...all));
    }
  });
});
