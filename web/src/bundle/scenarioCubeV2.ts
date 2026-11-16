/**
 * Scenario cube v2 reader (schemas/scenario-cube-v2.schema.json, docs/v2/6D_MODEL.md).
 *
 * Reads `scenario-cube-v1` and `scenario-cube-v2` files. Both come back as the same in-memory form: the v1 slicing view
 * that `scenarioCube.ts` already validates and slices, with a `role` on every dim (parent and inline derived dims) and
 * `source_schema` recording which file version it was. For a v2 file the view is `toV1()` of it (the exact inverse of
 * the migration) with the stored roles kept; for a v1 file the roles come from the same deterministic rule as
 * `science/cube/v2.py`.
 *
 * Roles only group controls on screen. Nothing here computes science: robust choice and regret are Python
 * (`science/cube/v2.py`).
 */
import {
  CubeError,
  cubeBase,
  parseMaybeGzip,
  validateCube,
  type CubeDerived,
  type CubeDim,
  type CubeKind,
  type ScenarioCube,
} from './scenarioCube';

export const CUBE_ROLES = ['uncertainty', 'decision', 'requirement', 'context'] as const;
export type CubeRole = (typeof CUBE_ROLES)[number];

/** Same table as `x-role-by-kind` in the v2 schema and ROLE_BY_KIND in science/cube/v2.py (tested). */
export const ROLE_BY_KIND: Record<CubeKind, CubeRole> = {
  uncertainty_terrain: 'uncertainty',
  uncertainty_model: 'uncertainty',
  design: 'decision',
  schedule: 'decision',
  requirement: 'requirement',
  site: 'context',
  target: 'context',
};

/** Same list as `x-role-overrides` in the v2 schema (tested). */
export const ROLE_OVERRIDES: { kind: CubeKind; name: string; role: CubeRole; reason: string }[] = [
  { kind: 'schedule', name: 'H', role: 'context', reason: 'hourly sample time coordinate (axis 4 itself), not a start date the mission chooses' },
  { kind: 'schedule', name: 'S_window', role: 'context', reason: 'evaluation horizon (14-day demo window vs 12 months), a question selector, not a lever' },
  { kind: 'uncertainty_terrain', name: 'k', role: 'context', reason: 'outcome bin (number of clone maps passing), a measure, not a member of the uncertainty set X' },
];

export const ROLE_RULE = 'role = ROLE_BY_KIND[kind] unless (kind, name) in ROLE_OVERRIDES (science/cube/v2.py)';

/** Plain-language group headings used by the slicer. */
export const ROLE_HEADING: Record<CubeRole, string> = {
  uncertainty: "What we don't know",
  decision: 'What we choose',
  requirement: 'Requirement (filter on outcomes)',
  context: 'Context (selector)',
};

export interface CubeDimV2 extends CubeDim {
  role: CubeRole;
  role_note?: string;
}
export interface CubeDerivedV2 extends Omit<CubeDerived, 'dims'> {
  dims: (string | CubeDimV2)[];
}
/** A v2 file as stored. */
export interface ScenarioCubeV2File extends Omit<ScenarioCube, 'schema' | 'dims' | 'derived'> {
  schema: 'scenario-cube-v2';
  world?: 'moon' | 'mercury' | 'mars';
  migration?: { from_schema: 'scenario-cube-v1'; tool: string; source_sha256?: string; role_rule?: string };
  dims: CubeDimV2[];
  derived?: Record<string, CubeDerivedV2>;
}
/** In-memory form for both versions: the v1 slicing view plus roles. Assignable to ScenarioCube. */
export interface RoledCube extends ScenarioCube {
  dims: CubeDimV2[];
  derived?: Record<string, CubeDerivedV2>;
  source_schema: 'scenario-cube-v1' | 'scenario-cube-v2';
}

export function roleFor(kind: CubeKind, name: string): { role: CubeRole; note?: string } {
  const o = ROLE_OVERRIDES.find((x) => x.kind === kind && x.name === name);
  if (o) return { role: o.role, note: o.reason };
  const role = ROLE_BY_KIND[kind];
  if (!role) throw new CubeError(`no role for kind ${String(kind)} (dim ${name})`);
  return { role };
}

function withRole(d: CubeDim): CubeDimV2 {
  const { role, note } = roleFor(d.kind, d.name);
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(d)) {
    out[k] = v;
    if (k === 'kind') {
      out.role = role;
      if (note) out.role_note = note;
    }
  }
  return out as unknown as CubeDimV2;
}

function withoutRole(d: CubeDimV2): CubeDim {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(d)) if (k !== 'role' && k !== 'role_note') out[k] = v;
  return out as unknown as CubeDim;
}

function mapDims<A, B>(dims: (string | A)[], f: (d: A) => B): (string | B)[] {
  return dims.map((d) => (typeof d === 'string' ? d : f(d)));
}

/** v1 → v2 file object (mirror of science/cube/v2.py migrate_v1_to_v2; arrays are shared, not copied). */
export function migrateV1toV2(c: ScenarioCube, sourceSha256?: string): ScenarioCubeV2File {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(c)) {
    out[k] = k === 'schema' ? 'scenario-cube-v2' : v;
    if (k === 'site_id') out.world = 'moon';
  }
  out.dims = c.dims.map(withRole);
  if (c.derived) out.derived = Object.fromEntries(Object.entries(c.derived).map(([k, b]) => [k, { ...b, dims: mapDims(b.dims, withRole) }]));
  out.migration = { from_schema: 'scenario-cube-v1', tool: 'science/cube/v2.py migrate_v1_to_v2', role_rule: ROLE_RULE, ...(sourceSha256 ? { source_sha256: sourceSha256 } : {}) };
  return out as unknown as ScenarioCubeV2File;
}

/** v2 file → v1 cube (exact inverse of migrateV1toV2). */
export function toV1(c: ScenarioCubeV2File): ScenarioCube {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(c)) if (k !== 'world' && k !== 'migration') out[k] = k === 'schema' ? 'scenario-cube-v1' : v;
  out.dims = c.dims.map(withoutRole);
  if (c.derived) out.derived = Object.fromEntries(Object.entries(c.derived).map(([k, b]) => [k, { ...b, dims: mapDims(b.dims, withoutRole) }]));
  return out as unknown as ScenarioCube;
}

function checkRoles(dims: (string | CubeDimV2)[], where: string) {
  for (const d of dims) {
    if (typeof d === 'string') continue;
    if (!(CUBE_ROLES as readonly string[]).includes(d.role)) throw new CubeError(`scenario cube invalid: ${where} dim ${d.name} role ${String(d.role)}`);
  }
}

/** Validate a v1 or v2 object and return the roled slicing view. */
export function readCubeAny(c: unknown): RoledCube {
  const schema = (c as { schema?: unknown } | null)?.schema;
  if (schema === 'scenario-cube-v1') {
    const v1 = validateCube(c);
    const v2 = migrateV1toV2(v1);
    return asView(v2, 'scenario-cube-v1');
  }
  if (schema === 'scenario-cube-v2') {
    const f = c as ScenarioCubeV2File;
    if (!Array.isArray(f.dims)) throw new CubeError('scenario cube invalid: dims');
    checkRoles(f.dims, 'parent');
    for (const [k, b] of Object.entries(f.derived ?? {})) checkRoles(b.dims ?? [], `derived ${k}`);
    validateCube(toV1(f));
    return asView(f, 'scenario-cube-v2');
  }
  throw new CubeError(`scenario cube invalid: schema ${String(schema)}`);
}

function asView(f: ScenarioCubeV2File, source: RoledCube['source_schema']): RoledCube {
  const rest: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(f)) if (k !== 'world' && k !== 'migration') rest[k] = v;
  return { ...rest, schema: 'scenario-cube-v1', source_schema: source } as unknown as RoledCube;
}

/** Role of any dim object (parent or derived inline). Falls back to the rule for an un-roled dim. */
export function dimRole(d: CubeDim | CubeDimV2): CubeRole {
  return (d as CubeDimV2).role ?? roleFor(d.kind, d.name).role;
}

/** Parent dims grouped by role, in cube order within each group. */
export function groupByRole<D extends CubeDim>(dims: D[]): Record<CubeRole, D[]> {
  const g: Record<CubeRole, D[]> = { uncertainty: [], decision: [], requirement: [], context: [] };
  for (const d of dims) g[dimRole(d)].push(d);
  return g;
}

export async function loadCubeAny(siteId: string, file: string, f: typeof fetch = fetch): Promise<RoledCube> {
  const r = await f(`${cubeBase(siteId)}${file}`);
  if (!r.ok) throw new CubeError(`cube ${file}: HTTP ${r.status}`);
  return readCubeAny(await parseMaybeGzip(await r.arrayBuffer()));
}

// ------------------------------------------------------------------------------------------------ decision6d (R5, §4)
/**
 * Reader for data/cubes/<site>/decision6d.json (science/decision/build.py): a scenario-cube-v2 with one context dim `Q`
 * (decision question) and per-question derived blocks `q__<id>__{table,by_choice,by_member,voi,summary}`, plus
 * `landing__<R>__*` and `pareto__positions`. Display only: every number is a stored cell (× declared scale at most).
 * Robust choice, regret and VoI are computed in Python (science/decision/core.py), never here.
 */
export const DECISION6D_FILE = 'decision6d.json';

export interface Decision6DQuestion {
  id: string;
  text: string;
  kind: 'cube' | 'landing';
  source_file: string;
  source_sha256: string;
  metric: string;
  measure: string;
  units: string;
  sense: 'max' | 'min';
  label: string;
  x_axes: string[];
  l_axes: string[];
  fixed: Record<string, string>;
  reduce: Record<string, string>;
  threshold: number | null;
  threshold_text: string | null;
  ordered: boolean;
  radius_km?: number;
  candidates_block?: string;
  screen_block?: string;
}

export interface Decision6D {
  cube: RoledCube;
  questions: Decision6DQuestion[];
}

/** Parse and check a decision6d cube object: v2, `Q` is a context axis, question metadata matches the Q values. */
export function readDecision6D(raw: unknown): Decision6D {
  const cube = readCubeAny(raw);
  if (cube.source_schema !== 'scenario-cube-v2') throw new CubeError('decision6d must be a scenario-cube-v2 file');
  const q = cube.dims[0];
  if (cube.dims.length !== 1 || q.name !== 'Q' || q.role !== 'context') throw new CubeError('decision6d: expected one context dim Q');
  let meta: Decision6DQuestion[];
  try {
    meta = JSON.parse(q.note ?? '[]') as Decision6DQuestion[];
  } catch {
    throw new CubeError('decision6d: Q.note is not JSON');
  }
  if (meta.length !== q.values.length || meta.some((m, i) => m.id !== q.values[i])) throw new CubeError('decision6d: question metadata does not match Q');
  for (const m of meta)
    for (const part of ['table', 'by_choice', 'by_member', 'voi', 'summary'])
      if (!cube.derived?.[`q__${m.id}__${part}`]) throw new CubeError(`decision6d: block q__${m.id}__${part} missing`);
  return { cube, questions: meta };
}

export async function loadDecision6D(siteId: string, f: typeof fetch = fetch): Promise<Decision6D | null> {
  const r = await f(`${cubeBase(siteId)}${DECISION6D_FILE}`);
  if (!r.ok || (r.headers.get('content-type') ?? '').includes('text/html')) return null;
  return readDecision6D(await parseMaybeGzip(await r.arrayBuffer()));
}

/** Stored values of a derived block metric (× scale when declared), or null when the block/metric is absent. */
export function blockMetric(cube: RoledCube, block: string, metric: string): (number | boolean | null)[] | null {
  const m = cube.derived?.[block]?.metrics[metric];
  if (!m) return null;
  const s = m.scale ?? 1;
  return m.values.map((v) => (typeof v === 'number' ? v * s : v));
}

/** Inline dim of a derived block (decision6d blocks carry their own roled dims). */
export function blockDim(cube: RoledCube, block: string, i = 0): CubeDimV2 | null {
  const d = cube.derived?.[block]?.dims[i];
  return d && typeof d !== 'string' ? d : null;
}

/** Parent metric value for question index qi. */
export function questionValue(cube: RoledCube, metric: string, qi: number): number | boolean | null {
  return cube.metrics[metric]?.values[qi] ?? null;
}
