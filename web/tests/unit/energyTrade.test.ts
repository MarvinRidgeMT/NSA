import { existsSync, readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { validateCube } from '../../src/bundle/scenarioCube';
import { TRADE_SERIES, tradeRows } from '../../src/components/EnergyTrade';

/** Phase 5: the trade view only slices `derived.trade` of the energy cube (no computation in the browser). */
for (const site of ['site04_roi3', 'site01_roi6']) {
  const p = resolve(__dirname, `../../../data/cubes/${site}/energy.json.gz`);
  describe.skipIf(!existsSync(p))(`${site} energy cube (science/energy/build_energy.py)`, () => {
    it('validates, is labelled ENGINEERING ASSUMPTION and trade rows equal the stored values × scale', () => {
      const c = validateCube(JSON.parse(gunzipSync(readFileSync(p)).toString('utf8')));
      expect(c.label).toBe('ENGINEERING ASSUMPTION');
      expect(c.dims.map((d) => d.name)).toEqual(['T', 'D_array', 'D_mast', 'S']);
      const tr = c.derived!.trade.metrics;
      for (const a of [0, 1]) {
        const rows = tradeRows(c, a);
        expect(rows.map((r) => r.mast)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
        rows.forEach((r, j) =>
          TRADE_SERIES.forEach((s, i) => expect(r.vals[i]).toBeCloseTo((tr[s.key].values[a * 10 + j] as number) * 0.001, 9)),
        );
      }
      // assumptions shown on screen are present in the cube
      for (const k of ['array_area_m2', 'array_efficiency', 'battery_capacity_wh', 'reserve_wh', 'load_constant_w', 'initial_soc'])
        expect(c.fixed?.[k]).not.toBeUndefined();
    });
  });
}
