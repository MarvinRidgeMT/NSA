import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { BundleError, displayStatus, validateBundle } from '../../src/bundle/validate';
import type { Bundle } from '../../src/bundle/types';

const demoPath = resolve(__dirname, '../../public/bundles/demo-fixture.json');
const demo = (): Bundle => JSON.parse(readFileSync(demoPath, 'utf8'));

describe('validateBundle', () => {
  it('accepts the DEMO fixture and labels it DEMO', () => {
    const v = validateBundle(demo());
    expect(v.status).toBe('DEMO');
    expect(v.warnings).toEqual([]);
    expect(v.times[0].length).toBe(48);
  });
  it('rejects wrong format, non-UTC times, non-monotonic times, bad DEM length', () => {
    const a = demo(); (a as unknown as { format: string }).format = 'POLARIS-X5D-v1';
    expect(() => validateBundle(a)).toThrow(/unsupported format/);
    const b = demo(); b.datasets[0].ephemeris.samples[3].time = '2026-11-14T17:00:00';
    expect(() => validateBundle(b)).toThrow(/UTC/);
    const c = demo(); [c.datasets[0].ephemeris.samples[2], c.datasets[0].ephemeris.samples[3]] = [c.datasets[0].ephemeris.samples[3], c.datasets[0].ephemeris.samples[2]];
    expect(() => validateBundle(c)).toThrow(/strictly increasing/);
    const d = demo(); d.datasets[0].dem!.values.pop();
    expect(() => validateBundle(d)).toThrow(BundleError);
    const e = demo(); (e.datasets[0].derived!.scenarios[0].samples!.sun.marginDeg as unknown[])[5] = '1.2';
    expect(() => validateBundle(e)).toThrow(/not a number/);
  });
  it('warns (does not invent) when derived outputs are missing', () => {
    const a = demo(); delete a.datasets[0].derived; a.validation.status = 'SOURCE_BASED_UNVALIDATED'; a.datasets[0].validation.status = 'SOURCE_BASED_UNVALIDATED'; delete a.demo; a.datasets[0].dem!.kind = 'nasa';
    const v = validateBundle(a);
    expect(v.status).toBe('SOURCE-BASED UNVALIDATED');
    expect(v.warnings[0]).toMatch(/does not compute/);
  });
});

describe('displayStatus is the most cautious label', () => {
  it('any DEMO_ONLY or synthetic layer forces DEMO', () => {
    const a = demo(); a.validation.status = 'VALIDATED_NASA_JPL'; a.datasets[0].validation.status = 'VALIDATED_NASA_JPL'; a.datasets[0].derived!.status = 'VALIDATED_NASA_JPL'; delete a.demo;
    expect(displayStatus(a)).toBe('DEMO'); // dem.kind is 'demo'
    a.datasets[0].dem!.kind = 'nasa';
    expect(displayStatus(a)).toBe('VALIDATED');
    a.datasets[0].derived!.status = 'SOURCE_BASED_UNVALIDATED';
    expect(displayStatus(a)).toBe('SOURCE-BASED UNVALIDATED');
    (a.validation as { status: string }).status = 'SOMETHING_NEW';
    expect(displayStatus(a)).toBe('DEMO');
  });
});

const real = resolve(__dirname, '../../public/bundles/polaris-source-site01-2026-11-14-v2.json');
describe.runIf(existsSync(real))('real Codex source bundle', () => {
  it('validates, is SOURCE-BASED UNVALIDATED, and has no derived outputs', () => {
    const v = validateBundle(JSON.parse(readFileSync(real, 'utf8')));
    expect(v.status).toBe('SOURCE-BASED UNVALIDATED');
    expect(v.times[0].length).toBe(337);
    expect(v.warnings.length).toBe(1);
  });
});
