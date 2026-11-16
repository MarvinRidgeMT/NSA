import { readdirSync, readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { CubeError, cell, derivedCell, type ScenarioCube } from '../../src/bundle/scenarioCube';
import {
  CUBE_ROLES,
  ROLE_BY_KIND,
  ROLE_OVERRIDES,
  groupByRole,
  migrateV1toV2,
  readCubeAny,
  roleFor,
  toV1,
  type ScenarioCubeV2File,
} from '../../src/bundle/scenarioCubeV2';

const ROOT = resolve(__dirname, '../../..');
const CUBES = resolve(ROOT, 'data/cubes');
const schemaV1 = JSON.parse(readFileSync(resolve(ROOT, 'schemas/scenario-cube-v1.schema.json'), 'utf8'));
const schemaV2 = JSON.parse(readFileSync(resolve(ROOT, 'schemas/scenario-cube-v2.schema.json'), 'utf8'));

function readJson(p: string): unknown {
  const raw = readFileSync(p);
  return JSON.parse((raw[0] === 0x1f && raw[1] === 0x8b ? gunzipSync(raw) : raw).toString('utf8'));
}
const files: { id: string; cube: ScenarioCube }[] = [];
for (const site of readdirSync(CUBES))
  for (const f of readdirSync(resolve(CUBES, site))) {
    if (!/\.json(\.gz)?$/.test(f)) continue;
    const c = readJson(resolve(CUBES, site, f)) as ScenarioCube;
    if (c.schema === 'scenario-cube-v1') files.push({ id: `${site}/${f}`, cube: c });
  }

describe('scenario cube v2 roles (docs/v2/6D_MODEL.md)', () => {
  it('TS role table equals the table embedded in the v2 schema', () => {
    expect(ROLE_BY_KIND).toEqual(schemaV2['x-role-by-kind']);
    expect(ROLE_OVERRIDES).toEqual(schemaV2['x-role-overrides']);
    expect([...CUBE_ROLES]).toEqual(schemaV2.$defs.role.enum);
    expect(Object.keys(ROLE_BY_KIND).sort()).toEqual([...schemaV1.$defs.dim.properties.kind.enum].sort());
  });

  it('reads all 28 committed v1 cubes with the deterministic roles', () => {
    expect(files.length).toBe(28);
    for (const { id, cube } of files) {
      const v = readCubeAny(cube);
      expect(v.source_schema, id).toBe('scenario-cube-v1');
      v.dims.forEach((d, i) => {
        expect(d.role, `${id} ${d.name}`).toBe(roleFor(cube.dims[i].kind, cube.dims[i].name).role);
      });
      for (const b of Object.values(v.derived ?? {}))
        for (const d of b.dims) if (typeof d !== 'string') expect(CUBE_ROLES).toContain(d.role);
    }
  });

  it('the documented role of each 5D axis', () => {
    const roles: Record<string, string> = {};
    for (const { cube } of files) for (const d of readCubeAny(cube).dims) roles[d.name] = d.role;
    expect(roles).toMatchObject({
      T: 'uncertainty', M: 'uncertainty',
      D_mast: 'decision', D_pos: 'decision', D_array: 'decision', S: 'decision', S_day: 'decision', S_slip: 'decision',
      R: 'requirement', R_vis: 'requirement', R_margin: 'requirement', R_slope: 'requirement',
      target: 'context', H: 'context', S_window: 'context', k: 'context',
    });
  });

  it('v1 → v2 → v1 is identical through JSON text, and a v2 file slices to the same cells', () => {
    for (const { id, cube } of files) {
      const text = JSON.stringify(migrateV1toV2(cube));
      const back = toV1(JSON.parse(text) as ScenarioCubeV2File);
      expect(JSON.stringify(back), id).toBe(JSON.stringify(cube));
    }
    const c = files.find((f) => f.id === 'site04_roi3/centre_mast_schedule.json.gz')!.cube;
    const fromV1 = readCubeAny(c);
    const fromV2 = readCubeAny(JSON.parse(JSON.stringify(migrateV1toV2(c, 'a'.repeat(64)))));
    expect(fromV2.source_schema).toBe('scenario-cube-v2');
    for (const at of [{ T: 0, D_mast: 0, S: 0 }, { T: 7, D_mast: 4, S: 4000 }, { T: 20, D_mast: 9, S: 8760 }])
      expect(cell(fromV2, 'sun_earth_pct', at)).toBe(cell(fromV1, 'sun_earth_pct', at));
    expect(cell(fromV2, 'sun_earth_pct', { T: 0, D_mast: 0, S: 0 })).toBeCloseTo(72.107, 2);
    expect(derivedCell(fromV2, 'k_of_N', 'k_pass', { R: 1, D_mast: 4, S: 4000 })).toBe(derivedCell(fromV1, 'k_of_N', 'k_pass', { R: 1, D_mast: 4, S: 4000 }));
    expect(fromV2.dims.map((d) => d.role)).toEqual(['uncertainty', 'decision', 'decision']);
  });

  it('groups parent dims by role in cube order', () => {
    const link = readCubeAny(files.find((f) => f.id === 'site04_roi3/link.json.gz')!.cube);
    const g = groupByRole(link.dims);
    expect(g.uncertainty.map((d) => d.name)).toEqual(['T']);
    expect(g.decision.map((d) => d.name)).toEqual(['D_mast', 'S']);
    expect(g.requirement.map((d) => d.name)).toEqual(['R_margin']);
    expect(g.context.map((d) => d.name)).toEqual(['target']);
  });

  it('rejects a bad role, a missing role, an unknown schema, and a v2 file with broken v1 structure', () => {
    const c = files.find((f) => f.id === 'site04_roi3/products.json')!.cube;
    const good = JSON.parse(JSON.stringify(migrateV1toV2(c)));
    expect(readCubeAny(good).dims[0].role).toBe('uncertainty');
    const bad = JSON.parse(JSON.stringify(good));
    bad.dims[0].role = 'world';
    expect(() => readCubeAny(bad)).toThrow(CubeError);
    const none = JSON.parse(JSON.stringify(good));
    delete none.dims[0].role;
    expect(() => readCubeAny(none)).toThrow(CubeError);
    expect(() => readCubeAny({ schema: 'scenario-cube-v0' })).toThrow(CubeError);
    const short = JSON.parse(JSON.stringify(good));
    short.metrics[Object.keys(short.metrics)[0]].values.pop();
    expect(() => readCubeAny(short)).toThrow(CubeError);
  });
});
