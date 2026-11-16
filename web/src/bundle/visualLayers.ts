/**
 * Visual-layer contract (`polaris-visual-layers-v1`): display rasters kept apart from numerical terrain.
 *
 * A visual layer (albedo, morphology…) is never terrain: `status` is 'VISUAL', `numericalAuthority` is the literal
 * `false`, and DEM fields (values, spacing, n, verticalUnits…) are forbidden. The viewer computes nothing, so the
 * guard here is mostly a type-level and load-time one: `VisualLayer` has no height samples, and
 * `assertNumericalDem` refuses a visual layer wherever a DEM is expected.
 * Same rules as tools/sources/visual_layers.py and app/src/visual-layers.js; all three run the shared cases in
 * schemas/fixtures/visual-layers-cases.json.
 */
export const VISUAL_LAYERS_SCHEMA = 'polaris-visual-layers-v1' as const;
export const VISUAL_ROLES = ['albedo', 'morphology', 'hillshade', 'reference-image'] as const;
export type VisualRole = (typeof VISUAL_ROLES)[number];

export interface VisualLayer {
  id: string;
  role: VisualRole;
  title: string;
  /** Shown wherever the layer is active; must contain the word VISUAL, e.g. "LROC NAC AVG · VISUAL". */
  label: string;
  status: 'VISUAL';
  numericalAuthority: false;
  productId: string;
  sourceUrl: string;
  productPage?: string;
  cite?: string;
  siteId?: string;
  artifact: { path: string; sha256: string; width: number; height: number; format: 'png-8bit-gray' | 'webp-8bit-gray' | 'jpeg-8bit-gray'; bytes?: number; noDataValue?: number };
  sourceHash: { kind: 'whole-file' | 'byte-range-window'; sha256: string; wholeFileSha256?: string | null; note?: string };
  pixelSizeM: number;
  projection: { type: 'south_polar_stereographic'; centreLatDeg: -90; centreLonEastDeg: 0; radiusM: 1737400; units: 'm'; axes?: string };
  frame: string;
  /** Pixel-edge bounds in polar stereographic metres (+x toward 90° E, +y toward 0° E). */
  boundsM: { xmin: number; xmax: number; ymin: number; ymax: number; boundsAre: 'pixel-edges' };
  rowOrder: 'north-to-south';
  registration: {
    method: string;
    against: string;
    /** Measured shift of the image relative to the DEM, metres. Evidence for display alignment only. */
    offsetM: { x: number; y: number };
    peakNcc?: number;
    nccAtZeroShift?: number;
    comparedPixels?: number;
    appliedShiftM?: { x: number; y: number };
    status: 'display-alignment-evidence-only';
    evidencePath?: string;
  };
  display: { processing: string; stretchLow?: number; stretchHigh?: number };
  limitations: string[];
}

export interface VisualLayersDoc {
  schema: typeof VISUAL_LAYERS_SCHEMA;
  generatedUTC?: string;
  releaseStatus: 'SOURCE_BASED_UNVALIDATED';
  note?: string;
  layers: VisualLayer[];
}

export class VisualLayerError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(`${code}: ${message}`);
    this.code = code;
    this.name = 'VisualLayerError';
  }
}

const DEM_FIELDS = ['values', 'verticalUnits', 'spacing', 'n', 'originX', 'originY', 'layer', 'kind'];
const HEX = /^[0-9a-f]{64}$/;
const ID = /^[a-z0-9][a-z0-9_-]{2,63}$/;
const PATH = /^(?!\/)(?!.*\.\.)[A-Za-z0-9_./-]+$/;
type Rec = Record<string, unknown>;
const isObj = (v: unknown): v is Rec => !!v && typeof v === 'object' && !Array.isArray(v);
const num = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
const rec = (v: unknown): Rec => (isObj(v) ? v : {});
function fail(code: string, message: string): never {
  throw new VisualLayerError(code, message);
}

export function validateVisualLayer(input: unknown): VisualLayer {
  if (!isObj(input)) fail('LAYER', 'layer must be an object');
  const layer = input;
  for (const f of DEM_FIELDS) if (f in layer) fail('DEM_FIELDS', `visual layer must not carry the numerical DEM field '${f}'`);
  if (layer.status !== 'VISUAL' || !String(layer.label ?? '').includes('VISUAL')) fail('VISUAL_STATUS', "status must be 'VISUAL' and the label must contain the word VISUAL");
  if (layer.numericalAuthority !== false) fail('NUMERICAL_AUTHORITY', 'numericalAuthority must be exactly false');
  if (typeof layer.id !== 'string' || !ID.test(layer.id)) fail('ID', 'id must be a stable lower-case slug');
  if (!(VISUAL_ROLES as readonly unknown[]).includes(layer.role)) fail('ROLE', `role must be one of ${VISUAL_ROLES.join(', ')}`);
  for (const k of ['title', 'productId', 'frame']) if (typeof layer[k] !== 'string' || (layer[k] as string).length < 3) fail('FIELD', `${k} missing`);
  if (!String(layer.sourceUrl ?? '').startsWith('https://')) fail('FIELD', 'sourceUrl must be https');
  const p = rec(layer.projection);
  if (p.units !== 'm') fail('UNITS', "projection.units must be 'm'");
  if (p.type !== 'south_polar_stereographic' || p.centreLatDeg !== -90 || p.centreLonEastDeg !== 0 || p.radiusM !== 1737400) fail('PROJECTION', 'only south polar stereographic, 90 S / 0 E, R = 1737400 m is accepted');
  const a = rec(layer.artifact);
  if (typeof a.path !== 'string' || !PATH.test(a.path)) fail('ARTIFACT', 'artifact.path must be a repository-relative path');
  if (typeof a.sha256 !== 'string' || !HEX.test(a.sha256)) fail('HASH', 'artifact.sha256 must be 64 lower-case hex characters');
  const sh = rec(layer.sourceHash);
  if (!['whole-file', 'byte-range-window'].includes(sh.kind as string) || typeof sh.sha256 !== 'string' || !HEX.test(sh.sha256)) fail('HASH', 'sourceHash.sha256 must be 64 lower-case hex characters');
  if (sh.wholeFileSha256 != null && !HEX.test(String(sh.wholeFileSha256))) fail('HASH', 'sourceHash.wholeFileSha256 must be null or 64 hex characters');
  const w = a.width, h = a.height;
  if (!Number.isInteger(w) || !Number.isInteger(h) || (w as number) < 1 || (h as number) < 1) fail('ARTIFACT', 'artifact width/height must be positive integers');
  const px = layer.pixelSizeM;
  if (!num(px) || px <= 0) fail('UNITS', 'pixelSizeM must be a positive number of metres');
  const b = rec(layer.boundsM);
  const { xmin, xmax, ymin, ymax } = b;
  if (!num(xmin) || !num(xmax) || !num(ymin) || !num(ymax) || b.boundsAre !== 'pixel-edges') fail('BOUNDS', 'boundsM needs xmin/xmax/ymin/ymax (pixel-edges)');
  if (!(xmin < xmax && ymin < ymax)) fail('BOUNDS', 'bounds are inverted');
  if (Math.abs(xmax - xmin - (w as number) * px) > 1e-6 || Math.abs(ymax - ymin - (h as number) * px) > 1e-6) fail('BOUNDS', 'bounds do not equal artifact size x pixelSizeM');
  if (layer.rowOrder !== 'north-to-south') fail('BOUNDS', 'rowOrder must be north-to-south');
  const r = rec(layer.registration);
  const o = rec(r.offsetM);
  if (r.status !== 'display-alignment-evidence-only' || !num(o.x) || !num(o.y) || !r.method || !r.against) fail('REGISTRATION', "registration needs method, against, offsetM and status 'display-alignment-evidence-only'");
  if (typeof rec(layer.display).processing !== 'string') fail('DISPLAY', 'display.processing must describe the stretch');
  const lim = layer.limitations;
  if (!Array.isArray(lim) || !lim.length || !lim.every((x) => typeof x === 'string' && x.length >= 8)) fail('LIMITATIONS', 'at least one limitation is required');
  return layer as unknown as VisualLayer;
}

export function validateVisualLayers(input: unknown): VisualLayersDoc {
  if (!isObj(input) || input.schema !== VISUAL_LAYERS_SCHEMA) fail('SCHEMA', `schema must be ${VISUAL_LAYERS_SCHEMA}`);
  if (input.releaseStatus !== 'SOURCE_BASED_UNVALIDATED') fail('RELEASE_STATUS', 'releaseStatus must stay SOURCE_BASED_UNVALIDATED');
  if (!Array.isArray(input.layers)) fail('SCHEMA', 'layers must be an array');
  const seen = new Set<string>();
  for (const l of input.layers) {
    const layer = validateVisualLayer(l);
    if (seen.has(layer.id)) fail('DUPLICATE_ID', layer.id);
    seen.add(layer.id);
  }
  return input as unknown as VisualLayersDoc;
}

export function isVisualLayer(o: unknown): boolean {
  return isObj(o) && (o.status === 'VISUAL' || o.numericalAuthority === false || (isObj(o.artifact) && !('values' in o)));
}

/** Guard for any code path that expects terrain: a visual layer is never a DEM. */
export function assertNumericalDem<T>(dem: T): T {
  if (isVisualLayer(dem)) fail('VISUAL_LAYER_AS_DEM', 'a visual layer cannot be used as solver terrain (numericalAuthority is false)');
  return dem;
}

/**
 * Where a visual layer sits on a local DEM crop, as UV corners in the crop's grid frame. Pure geometry for the
 * renderer: `demCentre` is the crop centre in polar stereographic metres, `halfExtentM` half its pixel-edge width.
 * Returns the overlap fraction so the caller can refuse to drape a layer that does not cover the terrain.
 */
export function layerCoverageOnCrop(layer: VisualLayer, demCentre: { x: number; y: number }, halfExtentM: number) {
  const b = layer.boundsM;
  const x0 = Math.max(b.xmin, demCentre.x - halfExtentM), x1 = Math.min(b.xmax, demCentre.x + halfExtentM);
  const y0 = Math.max(b.ymin, demCentre.y - halfExtentM), y1 = Math.min(b.ymax, demCentre.y + halfExtentM);
  const overlap = x1 > x0 && y1 > y0 ? ((x1 - x0) * (y1 - y0)) / (4 * halfExtentM * halfExtentM) : 0;
  return { overlapFraction: overlap, overlapBoundsM: overlap > 0 ? { xmin: x0, xmax: x1, ymin: y0, ymax: y1 } : null };
}
