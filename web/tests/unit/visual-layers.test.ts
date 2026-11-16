import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { assertNumericalDem, layerCoverageOnCrop, validateVisualLayers, VisualLayerError, type VisualLayer } from '../../src/bundle/visualLayers';

type Case = { name: string; set?: Record<string, unknown>; delete?: string[]; duplicateLayer?: number; code: string };
const CASES = JSON.parse(readFileSync(resolve(__dirname, '../../../schemas/fixtures/visual-layers-cases.json'), 'utf8'));
const clone = <T,>(o: T): T => JSON.parse(JSON.stringify(o));
function mutate(c: Case) {
  const doc = clone(CASES.valid);
  const walk = (path: string): [any, string] => {
    const parts = path.split('.');
    const leaf = parts.pop()!;
    let node: any = doc;
    for (const p of parts) node = node[Array.isArray(node) ? Number(p) : p];
    return [node, leaf];
  };
  for (const [path, value] of Object.entries(c.set ?? {})) { const [n, l] = walk(path); n[l] = value; }
  for (const path of c.delete ?? []) { const [n, l] = walk(path); delete n[l]; }
  if (c.duplicateLayer !== undefined) doc.layers.push(clone(doc.layers[c.duplicateLayer]));
  return doc;
}
const guardObjects = (key: 'rejected' | 'accepted'): [string, unknown][] =>
  CASES.solverGuard[key].map((c: any) => [c.name, 'useLayer' in c ? clone(CASES.valid.layers[c.useLayer]) : clone(c.object)]);

describe('visual-layer contract (shared cases)', () => {
  it('accepts the shared valid fixture', () => {
    expect(validateVisualLayers(clone(CASES.valid)).layers).toHaveLength(1);
  });
  it.each((CASES.invalid as Case[]).map((c) => [c.name, c] as const))('rejects: %s', (_name, c) => {
    try {
      validateVisualLayers(mutate(c));
      throw new Error('accepted an invalid document');
    } catch (e) {
      expect(e).toBeInstanceOf(VisualLayerError);
      expect((e as VisualLayerError).code).toBe(c.code);
    }
  });
  it('refuses a visual layer where a DEM is expected, and accepts a numerical DEM', () => {
    for (const [, o] of guardObjects('rejected')) expect(() => assertNumericalDem(o)).toThrow(/VISUAL_LAYER_AS_DEM/);
    for (const [, o] of guardObjects('accepted')) expect(assertNumericalDem(o)).toBe(o);
  });
  it('reports coverage of a DEM crop and never claims coverage outside its bounds', () => {
    const layer = validateVisualLayers(clone(CASES.valid)).layers[0] as VisualLayer;
    expect(layerCoverageOnCrop(layer, { x: -11000, y: -12000 }, 1000).overlapFraction).toBeCloseTo(1, 9);
    expect(layerCoverageOnCrop(layer, { x: -10000, y: -12000 }, 1000).overlapFraction).toBeCloseTo(0.5, 9);
    const none = layerCoverageOnCrop(layer, { x: 5000, y: 5000 }, 1000);
    expect(none.overlapFraction).toBe(0);
    expect(none.overlapBoundsM).toBeNull();
  });
});
