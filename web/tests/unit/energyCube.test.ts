import { existsSync, readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { cell, derivedCell, validateCube } from '../../src/bundle/scenarioCube';

/** Phase 5 energy cube (ENGINEERING ASSUMPTION): validates in the browser loader and the trade view's derived cells
 * are exactly the parent-cube cells (display only: stored × scale, no recomputation). */
for (const site of ['site04_roi3', 'site01_roi6']) {
  const p = resolve(__dirname, `../../../data/cubes/${site}/energy.json.gz`);
  describe.skipIf(!existsSync(p))(`energy cube ${site}`, () => {
    const c = validateCube(JSON.parse(gunzipSync(readFileSync(p)).toString('utf8')));
    it('is labelled ENGINEERING ASSUMPTION and lists its assumptions', () => {
      expect(c.label).toBe('ENGINEERING ASSUMPTION');
      for (const k of ['battery_capacity_wh', 'charge_efficiency', 'discharge_efficiency', 'min_reserve_fraction', 'initial_soc_fraction', 'load_constant_w', 'load_scheduled', 'array_area_m2', 'array_efficiency'])
        expect(c.fixed).toHaveProperty(k);
      expect(c.dims.map((d) => d.name)).toEqual(['T', 'D_array', 'D_mast', 'S']);
    });
    it('trade cells equal parent cells', () => {
      for (const a of [0, 1])
        for (const j of [0, 4, 9]) {
          const demo = cell(c, 'battery_needed_kwh', { T: 0, D_array: a, D_mast: j, S: 0 });
          expect(derivedCell(c, 'trade', 'needed_demo_nominal', { D_array: a, D_mast: j })).toBeCloseTo(demo!, 9);
          let worst = -1;
          for (let t = 1; t < 21; t++) for (let s = 0; s < 366; s++) worst = Math.max(worst, cell(c, 'battery_needed_kwh', { T: t, D_array: a, D_mast: j, S: s })!);
          expect(derivedCell(c, 'trade', 'needed_all_worst20', { D_array: a, D_mast: j })).toBeCloseTo(worst, 9);
        }
    });
  });
}
