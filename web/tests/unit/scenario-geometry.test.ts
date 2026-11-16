import { describe, expect, it } from 'vitest';
import { withScenarioGeometry } from '../../src/store/view';
import type { Dataset, Scenario } from '../../src/bundle/types';

const times = ['2026-11-14T00:00:00Z', '2026-11-14T01:00:00Z'];
const ms = times.map((t) => Date.parse(t));
const ds = {
  ephemeris: { samples: times.map((time) => ({ time, sun: { az: 10, el: 1 }, earth: { az: 20, el: 5 } })) },
  derived: { frame: { localNorthInGrid: [0, 1], localEastInGrid: [1, 0] }, scenarios: [] },
} as unknown as Dataset;

const sc = (over: Partial<Scenario>) => ({ id: 'x', label: 'x', kind: 'position_offset', metrics: [], failures: [], ...over }) as Scenario;

describe('withScenarioGeometry (5th-axis position offsets)', () => {
  it('leaves the dataset alone for scenarios without their own geometry', () => {
    expect(withScenarioGeometry(ds, sc({}), ms)).toBe(ds);
    expect(withScenarioGeometry(ds, null, ms)).toBe(ds);
  });

  it("uses the scenario's own JPL samples and local basis when the UTC times match", () => {
    const own = times.map((time) => ({ time, sun: { az: 11, el: 1.1 }, earth: { az: 21, el: 5.1 } }));
    const out = withScenarioGeometry(ds, sc({ ephemeris: { samples: own }, frame: { localNorthInGrid: [0.1, 0.99], localEastInGrid: [0.99, -0.1] } }), ms);
    expect(out.ephemeris.samples[1].sun.az).toBe(11);
    expect(out.derived?.frame?.localNorthInGrid).toEqual([0.1, 0.99]);
    expect(ds.ephemeris.samples[1].sun.az).toBe(10); // input not mutated
  });

  it('refuses samples whose times differ from the dataset (never re-times or extrapolates)', () => {
    const shifted = times.map((t) => ({ time: new Date(Date.parse(t) + 3600e3).toISOString(), sun: { az: 11, el: 1 }, earth: { az: 21, el: 5 } }));
    const out = withScenarioGeometry(ds, sc({ ephemeris: { samples: shifted } }), ms);
    expect(out.ephemeris.samples[0].sun.az).toBe(10);
  });
});
