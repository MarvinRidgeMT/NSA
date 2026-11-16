/**
 * Scenario cube v1 (schemas/scenario-cube-v1.schema.json, docs/SCENARIO_CUBE_CONTRACT.md).
 * The browser only loads, validates and SLICES precomputed arrays. Every number comes from the Python
 * builder (science/cube/build_cube.py); nothing here computes science. Display arithmetic is limited to
 * stored × scale (declared in the file) and picking min/max/k values that the file already holds.
 */

export const CUBE_KINDS = ['uncertainty_terrain', 'uncertainty_model', 'design', 'schedule', 'requirement', 'site', 'target'] as const;
export type CubeKind = (typeof CUBE_KINDS)[number];

export interface CubeDim {
  name: string;
  kind: CubeKind;
  values: (string | number)[];
  units: string;
  label: string;
  value_labels?: string[];
  nominal_index?: number;
  note?: string;
}
export interface CubeMetric {
  units: string;
  label: string;
  dtype: 'int32' | 'float64' | 'bool';
  values: (number | boolean | null)[];
  provenance: string;
  scale?: number;
  decimals?: number;
  description?: string;
}
export interface CubeDerived {
  dims: (string | CubeDim)[];
  metrics: Record<string, CubeMetric>;
  method: string;
  caveat?: string;
}
export interface ScenarioCube {
  schema: 'scenario-cube-v1';
  cube_id: string;
  site_id: string;
  title?: string;
  label: string;
  generated_utc: string;
  description?: string;
  fixed?: Record<string, string | number | boolean>;
  dims: CubeDim[];
  metrics: Record<string, CubeMetric>;
  missing: { encoding: 'sparse-flat-index'; by_metric: Record<string, number[]>; reasons?: Record<string, string> };
  derived?: Record<string, CubeDerived>;
  provenance: { inputs: { path: string; sha256: string; url?: string; note?: string }[]; command: string; code_commit: string; solver?: string };
  limitations?: string[];
}
export interface CubeIndex {
  schema: 'scenario-cube-index-v1';
  site_id: string;
  label: string;
  cubes: { file: string; cube_id: string; title: string; bytes: number; sha256: string; dims: string[] }[];
}

export class CubeError extends Error {}

const prod = (a: number[]) => a.reduce((x, y) => x * y, 1);

/** Validate the structural contract (the JSON schema plus the size/index rules a schema cannot state). */
export function validateCube(c: unknown): ScenarioCube {
  const fail = (m: string): never => {
    throw new CubeError(`scenario cube invalid: ${m}`);
  };
  if (!c || typeof c !== 'object') fail('not an object');
  const cube = c as ScenarioCube;
  if (cube.schema !== 'scenario-cube-v1') fail(`schema ${String(cube.schema)}`);
  for (const k of ['cube_id', 'site_id', 'label', 'generated_utc'] as const) if (typeof cube[k] !== 'string' || !cube[k]) fail(`missing ${k}`);
  if (!Array.isArray(cube.dims) || !cube.dims.length) fail('dims empty');
  const names = new Set<string>();
  for (const d of cube.dims) {
    if (!d || typeof d.name !== 'string' || !/^[A-Za-z][A-Za-z0-9_]*$/.test(d.name)) fail('bad dim name');
    if (names.has(d.name)) fail(`duplicate dim ${d.name}`);
    names.add(d.name);
    if (!(CUBE_KINDS as readonly string[]).includes(d.kind)) fail(`dim ${d.name} kind ${d.kind}`);
    if (!Array.isArray(d.values) || !d.values.length) fail(`dim ${d.name} has no values`);
    if (typeof d.units !== 'string' || typeof d.label !== 'string') fail(`dim ${d.name} units/label`);
    if (d.value_labels && d.value_labels.length !== d.values.length) fail(`dim ${d.name} value_labels length`);
    if (d.nominal_index !== undefined && (d.nominal_index < 0 || d.nominal_index >= d.values.length)) fail(`dim ${d.name} nominal_index`);
  }
  const n = prod(cube.dims.map((d) => d.values.length));
  if (!cube.metrics || !Object.keys(cube.metrics).length) fail('no metrics');
  for (const [k, m] of Object.entries(cube.metrics)) checkMetric(k, m, n, fail);
  if (!cube.missing || cube.missing.encoding !== 'sparse-flat-index' || typeof cube.missing.by_metric !== 'object') fail('missing mask');
  for (const [k, idx] of Object.entries(cube.missing.by_metric)) {
    if (!(k in cube.metrics)) fail(`missing mask for unknown metric ${k}`);
    for (const i of idx) {
      if (!Number.isInteger(i) || i < 0 || i >= n) fail(`missing index ${i} out of range`);
      if (cube.metrics[k].values[i] !== null) fail(`missing cell ${k}[${i}] is not null`);
    }
  }
  for (const [k, m] of Object.entries(cube.metrics))
    m.values.forEach((v, i) => {
      if (v === null && !(cube.missing.by_metric[k] ?? []).includes(i)) fail(`null in ${k}[${i}] not declared missing`);
    });
  for (const [dk, dv] of Object.entries(cube.derived ?? {})) {
    const dd = derivedDims(cube, dk);
    const dn = prod(dd.map((d) => d.values.length));
    for (const [k, m] of Object.entries(dv.metrics)) checkMetric(`${dk}.${k}`, m, dn, fail);
  }
  if (!cube.provenance || !Array.isArray(cube.provenance.inputs) || typeof cube.provenance.command !== 'string') fail('provenance');
  for (const i of cube.provenance.inputs) if (!/^[0-9a-f]{64}$/.test(i.sha256)) fail(`input ${i.path} sha256`);
  return cube;
}

function checkMetric(k: string, m: CubeMetric, n: number, fail: (m: string) => never) {
  if (!m || !Array.isArray(m.values)) fail(`metric ${k} values`);
  if (m.values.length !== n) fail(`metric ${k} has ${m.values.length} values, dims give ${n}`);
  if (typeof m.units !== 'string' || typeof m.label !== 'string' || typeof m.provenance !== 'string') fail(`metric ${k} units/label/provenance`);
  if (!['int32', 'float64', 'bool'].includes(m.dtype)) fail(`metric ${k} dtype`);
}

/** Resolve a derived block's dims (names refer to parent dims). */
export function derivedDims(cube: ScenarioCube, key: string): CubeDim[] {
  const d = cube.derived?.[key];
  if (!d) throw new CubeError(`derived ${key} not in cube`);
  return d.dims.map((x) => {
    if (typeof x !== 'string') return x;
    const p = cube.dims.find((y) => y.name === x);
    if (!p) throw new CubeError(`derived ${key} refers to unknown dim ${x}`);
    return p;
  });
}

export function flatIndex(dims: CubeDim[], at: Record<string, number>): number {
  let i = 0;
  for (const d of dims) {
    const k = at[d.name];
    if (k === undefined || !Number.isInteger(k) || k < 0 || k >= d.values.length) throw new CubeError(`index for ${d.name} missing or out of range`);
    i = i * d.values.length + k;
  }
  return i;
}

/** Stored value × declared scale (null stays null). */
export function display(m: CubeMetric, v: number | boolean | null | undefined): number | null {
  if (v === null || v === undefined) return null;
  if (typeof v === 'boolean') return v ? 1 : 0;
  return m.scale !== undefined ? v * m.scale : v;
}

/** Value of one cell. `at` must give an index for every dim. */
export function cell(cube: ScenarioCube, metric: string, at: Record<string, number>): number | null {
  const m = cube.metrics[metric];
  if (!m) throw new CubeError(`metric ${metric} not in cube`);
  return display(m, m.values[flatIndex(cube.dims, at)]);
}

export function derivedCell(cube: ScenarioCube, key: string, metric: string, at: Record<string, number>): number | null {
  const d = cube.derived?.[key];
  const m = d?.metrics[metric];
  if (!d || !m) throw new CubeError(`derived ${key}.${metric} not in cube`);
  return display(m, m.values[flatIndex(derivedDims(cube, key), at)]);
}

/** 1-d slice along `free` with every other dim fixed by `at`. */
export function slice1d(cube: ScenarioCube, metric: string, free: string, at: Record<string, number>): (number | null)[] {
  const d = cube.dims.find((x) => x.name === free);
  if (!d) throw new CubeError(`dim ${free} not in cube`);
  return d.values.map((_, i) => cell(cube, metric, { ...at, [free]: i }));
}

export function derivedSlice1d(cube: ScenarioCube, key: string, metric: string, free: string, at: Record<string, number>): (number | null)[] {
  const d = derivedDims(cube, key).find((x) => x.name === free);
  if (!d) throw new CubeError(`dim ${free} not in derived ${key}`);
  return d.values.map((_, i) => derivedCell(cube, key, metric, { ...at, [free]: i }));
}

/** Gzip-or-plain JSON: checks the gzip magic bytes, so a server that already decoded Content-Encoding also works. */
export async function parseMaybeGzip(buf: ArrayBuffer): Promise<unknown> {
  const u8 = new Uint8Array(buf);
  if (u8.length > 2 && u8[0] === 0x1f && u8[1] === 0x8b) {
    const ds = new Response(u8).body!.pipeThrough(new DecompressionStream('gzip'));
    return JSON.parse(await new Response(ds).text());
  }
  return JSON.parse(new TextDecoder().decode(u8));
}

export function cubeBase(siteId: string): string {
  const base = (import.meta as { env?: { BASE_URL?: string } }).env?.BASE_URL ?? '/';
  return `${base}cubes/${encodeURIComponent(siteId)}/`;
}

/** null = this site has no cube (UI shows "not in bundle"). */
export async function loadCubeIndex(siteId: string, f: typeof fetch = fetch): Promise<CubeIndex | null> {
  const r = await f(`${cubeBase(siteId)}index.json`);
  if (!r.ok) return null;
  const ct = r.headers.get('content-type') ?? '';
  if (ct.includes('text/html')) return null; // SPA fallback page, not a cube index
  try {
    const j = (await r.json()) as CubeIndex;
    return j?.schema === 'scenario-cube-index-v1' ? j : null;
  } catch {
    return null;
  }
}

export async function loadCube(siteId: string, file: string, f: typeof fetch = fetch): Promise<ScenarioCube> {
  const r = await f(`${cubeBase(siteId)}${file}`);
  if (!r.ok) throw new CubeError(`cube ${file}: HTTP ${r.status}`);
  return validateCube(await parseMaybeGzip(await r.arrayBuffer()));
}
