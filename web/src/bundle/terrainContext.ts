/**
 * Terrain context pack (`polaris-terrain-context-v1`): DISPLAY-ONLY data that lets the scene draw the 5 m crop inside
 * its 80 m regional surroundings and shade both from the bundle's Sun direction without a shadow-map rectangle.
 *
 *  - regional_f32.bin: the PGDA 90 80 m crop (display copy), site-relative grid metres, rows south-to-north;
 *  - *_horizon_u8.bin: horizon maps, (K, m, m) uint8, degrees = q * 0.05 − 3. For each terrain node and each of K grid
 *    azimuths: the elevation angle of the highest *displayed* terrain in that direction.
 *
 * Built by tools/terrain/build_terrain_context.py. Status VISUAL, numericalAuthority false: nothing here feeds a
 * number, and the viewer still takes every visible/blocked state, margin and metric from the bundle.
 */
export interface HorizonGridMeta { file: string; sha256: string; m: number; spacingM: number; originX: number; originY: number }
export interface TerrainContextMeta {
  schema: 'polaris-terrain-context-v1';
  status: 'VISUAL';
  numericalAuthority: false;
  label: string;
  datasetId: string;
  displayReachM: number;
  local: { n: number; spacingM: number; originX: number; originY: number; cropValuesSha256: string };
  regional: { file: string; sha256: string; n: number; spacingM: number; originX: number; originY: number; product: string; source: string };
  /** L1: 20 m block means of the 5 m PGDA 78 tile (optional; older packs have none) */
  mid?: { sfsFraction?: number; file: string; sha256: string; n: number; spacingM: number; originX: number; originY: number; product: string; source: string };
  /** DISPLAY surface of the 5 m crop (NASA GSFC shape-from-shading blended into the LOLA crop); optional */
  localDisplay?: { file: string; sha256: string; n: number; spacingM: number; product: string; citation: string; doi: string; licence: string; coverageFraction: number; fullWeightFraction: number; minusSolverCropM: { rms: number; mean: number; maxAbs: number; atSitePoint: number } };
  horizon: { azimuths: number; encoding: { minDeg: number; stepDeg: number }; local: HorizonGridMeta; regional: HorizonGridMeta; mid?: HorizonGridMeta };
  skylineCrossCheck?: unknown;
  limitations: string[];
}
export interface TerrainContext {
  meta: TerrainContextMeta;
  regional: Float32Array;
  localHorizon: Uint8Array;
  regionalHorizon: Uint8Array;
  mid?: Float32Array;
  midHorizon?: Uint8Array;
  localDisplay?: Float32Array;
}

export class TerrainContextError extends Error {}
const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const fin = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

export function validateContextMeta(j: unknown): TerrainContextMeta {
  if (!isObj(j) || j.schema !== 'polaris-terrain-context-v1') throw new TerrainContextError('not a polaris-terrain-context-v1 pack');
  if (j.status !== 'VISUAL' || j.numericalAuthority !== false) throw new TerrainContextError('terrain context must be VISUAL with numericalAuthority false');
  const m = j as unknown as TerrainContextMeta;
  const grids = [m.local, m.regional, m.horizon?.local, m.horizon?.regional, ...(m.mid ? [m.mid, m.horizon?.mid] : [])] as unknown[];
  if (grids.some((g) => !isObj(g) || !fin(g.originX) || !fin(g.originY) || !fin(g.spacingM) || (g.spacingM as number) <= 0)) throw new TerrainContextError('terrain context grid metadata incomplete');
  if (!Number.isInteger(m.horizon.azimuths) || m.horizon.azimuths < 8) throw new TerrainContextError('terrain context needs at least 8 azimuths');
  if (m.horizon.encoding?.minDeg !== -3 || m.horizon.encoding?.stepDeg !== 0.05) throw new TerrainContextError('unknown horizon encoding');
  if (!fin(m.displayReachM) || m.displayReachM <= 0) throw new TerrainContextError('displayReachM missing');
  return m;
}

/** Throws unless the byte lengths match the metadata (a truncated download must never be drawn). */
export function assembleContext(meta: TerrainContextMeta, regional: ArrayBuffer, localHorizon: ArrayBuffer, regionalHorizon: ArrayBuffer, mid?: ArrayBuffer, midHorizon?: ArrayBuffer, localDisplay?: ArrayBuffer): TerrainContext {
  const K = meta.horizon.azimuths;
  if (regional.byteLength !== meta.regional.n * meta.regional.n * 4) throw new TerrainContextError('regional DEM size mismatch');
  if (localHorizon.byteLength !== K * meta.horizon.local.m ** 2) throw new TerrainContextError('local horizon map size mismatch');
  if (regionalHorizon.byteLength !== K * meta.horizon.regional.m ** 2) throw new TerrainContextError('regional horizon map size mismatch');
  const out: TerrainContext = { meta, regional: new Float32Array(regional), localHorizon: new Uint8Array(localHorizon), regionalHorizon: new Uint8Array(regionalHorizon) };
  if (meta.mid && meta.horizon.mid && mid && midHorizon) {
    if (mid.byteLength !== meta.mid.n * meta.mid.n * 4) throw new TerrainContextError('L1 grid size mismatch');
    if (midHorizon.byteLength !== K * meta.horizon.mid.m ** 2) throw new TerrainContextError('L1 horizon map size mismatch');
    out.mid = new Float32Array(mid);
    out.midHorizon = new Uint8Array(midHorizon);
  }
  if (meta.localDisplay && localDisplay) {
    if (meta.localDisplay.n !== meta.local.n || localDisplay.byteLength !== meta.local.n * meta.local.n * 4) throw new TerrainContextError('display surface size mismatch');
    out.localDisplay = new Float32Array(localDisplay);
  }
  return out;
}

async function sha256Hex(buf: ArrayBuffer): Promise<string | null> {
  if (typeof crypto === 'undefined' || !crypto.subtle) return null; // non-secure context: cannot verify, sizes are still checked
  const d = await crypto.subtle.digest('SHA-256', buf);
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Loads the pack for a dataset. Returns null when there is none, or when it was built for a different DEM crop
 * (`cropValuesSha256` differs): the scene then falls back to the crop-only rendering. Hashes are verified where
 * WebCrypto is available.
 */
export async function loadTerrainContext(datasetId: string, demCropSha256: string | undefined, base = 'context/'): Promise<TerrainContext | null> {
  const r = await fetch(`${base}${encodeURIComponent(datasetId)}/context.json`);
  if (!r.ok || !(r.headers.get('content-type') ?? '').includes('json')) return null;
  const meta = validateContextMeta(await r.json());
  if (!demCropSha256 || meta.local.cropValuesSha256 !== demCropSha256) return null;
  const get = async (file: string, sha: string) => {
    const b = await (await fetch(`${base}${encodeURIComponent(datasetId)}/${file}`)).arrayBuffer();
    const h = await sha256Hex(b);
    if (h !== null && h !== sha) throw new TerrainContextError(`${file}: SHA-256 differs from context.json`);
    return b;
  };
  const [reg, lh, rh] = await Promise.all([get(meta.regional.file, meta.regional.sha256), get(meta.horizon.local.file, meta.horizon.local.sha256), get(meta.horizon.regional.file, meta.horizon.regional.sha256)]);
  const [md, mh] = meta.mid && meta.horizon.mid ? await Promise.all([get(meta.mid.file, meta.mid.sha256), get(meta.horizon.mid.file, meta.horizon.mid.sha256)]) : [undefined, undefined];
  const ld = meta.localDisplay ? await get(meta.localDisplay.file, meta.localDisplay.sha256) : undefined;
  return assembleContext(meta, reg, lh, rh, md, mh, ld);
}

/** Grid angle (degrees from +y toward +x) and elevation of a unit direction given in grid axes (x, y, z up). */
export function gridAngles(dir: readonly [number, number, number]): { thetaDeg: number; elDeg: number } {
  const thetaDeg = ((Math.atan2(dir[0], dir[1]) * 180) / Math.PI + 360) % 360;
  return { thetaDeg, elDeg: (Math.asin(Math.max(-1, Math.min(1, dir[2]))) * 180) / Math.PI };
}

/** 3D-texture w coordinate for a grid angle: slice k is centred at (k + 0.5) / K and the texture repeats in w. */
export const horizonW = (thetaDeg: number, K: number) => (((thetaDeg % 360) + 360) % 360) / 360 + 0.5 / K;

export const decodeHorizonDeg = (q: number) => q * 0.05 - 3;

/** CPU reference of the shader lookup: nearest node, linear between the two neighbouring azimuth slices. */
export function sampleHorizonDeg(tex: Uint8Array, m: number, K: number, i: number, j: number, thetaDeg: number): number {
  const f = ((((thetaDeg % 360) + 360) % 360) / 360) * K;
  const k0 = Math.floor(f) % K;
  const k1 = (k0 + 1) % K;
  const t = f - Math.floor(f);
  const at = (k: number) => decodeHorizonDeg(tex[(k * m + j) * m + i]);
  return at(k0) * (1 - t) + at(k1) * t;
}

/** Same display model as the shader and tools/terrain/terrain_context.py: smoothstep across the solar disc. */
export function sunVisibility(horizonDeg: number, sunElDeg: number, sunRadiusDeg = 0.266): number {
  const t = Math.min(1, Math.max(0, (sunElDeg - (horizonDeg - sunRadiusDeg)) / (2 * sunRadiusDeg)));
  return t * t * (3 - 2 * t);
}

/**
 * Horizon set by terrain BEYOND the displayed crops, taken from the bundle (solver output): the skyline elevation in
 * the Sun's azimuth bin when the bundle says its controlling terrain is farther than `displayReachM`. Returns null when
 * the bundle does not say (no attribution) or the controlling terrain is inside the displayed crops (the horizon map
 * already has it). This keeps the shaded scene consistent with the bundle's "Sun blocked by distant terrain" state.
 */
export function farHorizonFromBundle(skylineAzDeg: readonly number[], skylineElDeg: readonly (number | null)[], ctrlDistM: readonly (number | null)[] | null | undefined, sunAzDeg: number, displayReachM: number): number | null {
  if (!ctrlDistM || !skylineAzDeg.length) return null;
  let best = 0;
  let bd = Infinity;
  for (let b = 0; b < skylineAzDeg.length; b++) {
    const d = Math.abs(((skylineAzDeg[b] - sunAzDeg + 540) % 360) - 180);
    if (d < bd) { bd = d; best = b; }
  }
  const dist = ctrlDistM[best];
  const el = skylineElDeg[best];
  return dist !== null && dist !== undefined && Number.isFinite(dist) && dist > displayReachM && el !== null && Number.isFinite(el) ? el : null;
}
