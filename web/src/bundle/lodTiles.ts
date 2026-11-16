/**
 * Near-field LOD tiles (`polaris-lod-tiles-v1`, 5D Phase 9.4): DISPLAY-ONLY quadtree tiles of the NASA PGDA 78 5 m tile,
 * ±7 km around the site, 5 levels (80, 40, 20, 10, 5 m). Built by tools/terrain/build_lod_tiles.py into
 * public/context/lod/<datasetId>/ (git-ignored: NASA-derived rasters stay out of git).
 *
 * Status VISUAL, numericalAuthority false. The browser only chooses which tiles to draw from the camera distance; no
 * visible/blocked state, margin or metric is ever computed from these heights (the bundles carry all of them).
 *
 * Frame: bundle grid axes (x toward 90° E, y toward 0° E), metres, relative to the dataset site point; heights in metres.
 */
export const LOD_SCHEMA = 'polaris-lod-tiles-v1';
export const MAX_TILE_BYTES = 2 * 1024 * 1024;

export interface Bounds { xmin: number; xmax: number; ymin: number; ymax: number }
export interface LodTileMeta {
  level: number;
  ix: number;
  iy: number;
  file: string;
  bytes: number;
  sha256: string;
  bounds: Bounds;
  zMin: number | null;
  zMax: number | null;
  nanNodes: number;
}
export interface LodLevel { level: number; spacingM: number; tilesPerSide: number; tileWidthM: number; boxPixels: number }
export interface LodManifest {
  schema: typeof LOD_SCHEMA;
  status: 'VISUAL';
  numericalAuthority: false;
  label: string;
  datasetId: string;
  siteName: string;
  halfExtentM: number;
  sitePointProjectedM: { x: number; y: number };
  source: { product: string; url: string; sha256: string; pixelM: number };
  levels: LodLevel[];
  area: Bounds;
  tileGrid: { cells: number; nodes: number; apron: number; stored: number; dtype: 'float32-le' };
  tiles: LodTileMeta[];
  rule: string;
  limitations: string[];
}

export class LodError extends Error {}
const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const fin = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

export const tileKey = (level: number, ix: number, iy: number) => `${level}/${ix}/${iy}`;
export const keyOf = (t: Pick<LodTileMeta, 'level' | 'ix' | 'iy'>) => tileKey(t.level, t.ix, t.iy);

/** Throws unless the manifest is a VISUAL, non-authoritative pack whose tiles form a complete quadtree of ≤ 2 MB files. */
export function validateLodManifest(j: unknown): LodManifest {
  if (!isObj(j) || j.schema !== LOD_SCHEMA) throw new LodError(`not a ${LOD_SCHEMA} manifest`);
  if (j.status !== 'VISUAL' || j.numericalAuthority !== false) throw new LodError('LOD tiles must be VISUAL with numericalAuthority false');
  const m = j as unknown as LodManifest;
  const src = m.source as unknown;
  if (!isObj(src) || typeof src.url !== 'string' || !/^[0-9a-f]{64}$/.test(String(src.sha256))) throw new LodError('LOD manifest needs the source URL and SHA-256');
  const g = m.tileGrid;
  if (!isObj(g) || !Number.isInteger(g.cells) || g.nodes !== g.cells + 1 || g.stored !== g.nodes + 2 * g.apron || g.dtype !== 'float32-le') throw new LodError('LOD tile grid metadata incomplete');
  if (!Array.isArray(m.levels) || !m.levels.length) throw new LodError('LOD manifest has no levels');
  const a = m.area;
  if (!isObj(a) || ![a.xmin, a.xmax, a.ymin, a.ymax].every(fin)) throw new LodError('LOD area bounds missing');
  const seen = new Set<string>();
  for (const t of m.tiles ?? []) {
    if (!fin(t.bytes) || t.bytes > MAX_TILE_BYTES) throw new LodError(`${t.file}: tile larger than 2 MB`);
    if (t.bytes !== g.stored * g.stored * 4) throw new LodError(`${t.file}: byte size does not match the tile grid`);
    if (![t.bounds?.xmin, t.bounds?.xmax, t.bounds?.ymin, t.bounds?.ymax].every(fin)) throw new LodError(`${t.file}: bounds missing`);
    seen.add(keyOf(t));
  }
  for (const lv of m.levels) {
    if (lv.tilesPerSide !== 2 ** lv.level) throw new LodError(`level ${lv.level}: not a quadtree level`);
    for (let iy = 0; iy < lv.tilesPerSide; iy++)
      for (let ix = 0; ix < lv.tilesPerSide; ix++) if (!seen.has(tileKey(lv.level, ix, iy))) throw new LodError(`missing tile ${tileKey(lv.level, ix, iy)}`);
  }
  return m;
}

/** Index of a manifest's tiles by key. */
export function indexTiles(m: LodManifest): Map<string, LodTileMeta> {
  return new Map(m.tiles.map((t) => [keyOf(t), t]));
}

export interface GridPoint { x: number; y: number; z: number }

/** Euclidean distance from a point to a tile's box (x, y bounds; z from the tile's height range, or the point's own height when unknown). */
export function distanceToTile(p: GridPoint, t: LodTileMeta): number {
  const b = t.bounds;
  const dx = Math.max(b.xmin - p.x, 0, p.x - b.xmax);
  const dy = Math.max(b.ymin - p.y, 0, p.y - b.ymax);
  const zlo = t.zMin ?? p.z;
  const zhi = t.zMax ?? p.z;
  const dz = Math.max(zlo - p.z, 0, p.z - zhi);
  return Math.hypot(dx, dy, dz);
}

/**
 * Quadtree selection: start at the root and split a tile while the camera is closer to it than `splitFactor` × its width
 * (and a finer level exists). The result is the set of leaves of that traversal: it covers the area exactly once.
 * `maxLevel` caps the finest level (default: the finest in the manifest).
 */
export function selectTiles(m: LodManifest, cam: GridPoint, splitFactor = 1.2, maxLevel?: number, index = indexTiles(m)): LodTileMeta[] {
  const top = Math.min(maxLevel ?? Infinity, m.levels.length - 1);
  const out: LodTileMeta[] = [];
  const visit = (t: LodTileMeta) => {
    const w = t.bounds.xmax - t.bounds.xmin;
    if (t.level < top && distanceToTile(cam, t) < splitFactor * w) {
      for (const [dx, dy] of [[0, 0], [1, 0], [0, 1], [1, 1]]) {
        const c = index.get(tileKey(t.level + 1, t.ix * 2 + dx, t.iy * 2 + dy));
        if (c) visit(c);
      }
    } else out.push(t);
  };
  const root = index.get(tileKey(0, 0, 0));
  if (root) visit(root);
  return out;
}

export const parentKey = (t: Pick<LodTileMeta, 'level' | 'ix' | 'iy'>) => (t.level > 0 ? tileKey(t.level - 1, t.ix >> 1, t.iy >> 1) : null);

/**
 * What to draw while tiles stream in: each wanted tile, or its nearest loaded ancestor when it is not loaded yet; a drawn
 * ancestor suppresses its drawn descendants. Never a gap (as long as the root is loaded) and never an overlap.
 */
export function drawSet(wanted: readonly LodTileMeta[], isLoaded: (key: string) => boolean, index: Map<string, LodTileMeta>): LodTileMeta[] {
  const chosen = new Map<string, LodTileMeta>();
  for (const t of wanted) {
    let cur: LodTileMeta | undefined = t;
    while (cur && !isLoaded(keyOf(cur))) {
      const pk = parentKey(cur);
      cur = pk ? index.get(pk) : undefined;
    }
    if (cur) chosen.set(keyOf(cur), cur);
  }
  const out: LodTileMeta[] = [];
  for (const t of chosen.values()) {
    let pk = parentKey(t);
    let covered = false;
    while (pk) {
      if (chosen.has(pk)) {
        covered = true;
        break;
      }
      const p = index.get(pk);
      pk = p ? parentKey(p) : null;
    }
    if (!covered) out.push(t);
  }
  return out;
}

/** Throws unless the bytes match the manifest (a truncated download must never be drawn). */
export function parseTile(m: LodManifest, t: LodTileMeta, buf: ArrayBuffer): Float32Array {
  const st = m.tileGrid.stored;
  if (buf.byteLength !== t.bytes || buf.byteLength !== st * st * 4) throw new LodError(`${t.file}: size ${buf.byteLength} does not match the manifest`);
  return new Float32Array(buf);
}

async function sha256Hex(buf: ArrayBuffer): Promise<string | null> {
  if (typeof crypto === 'undefined' || !crypto.subtle) return null;
  const d = await crypto.subtle.digest('SHA-256', buf);
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export const lodBase = (datasetId: string, base = 'context/lod/') => `${base}${encodeURIComponent(datasetId)}/`;

/** The manifest for a dataset, or null when no tiles were built for it. */
export async function loadLodManifest(datasetId: string, base = 'context/lod/'): Promise<LodManifest | null> {
  const r = await fetch(`${lodBase(datasetId, base)}manifest.json`);
  if (!r.ok || !(r.headers.get('content-type') ?? '').includes('json')) return null;
  return validateLodManifest(await r.json());
}

/** One tile's heights (size and, where WebCrypto exists, SHA-256 verified). */
export async function fetchTile(m: LodManifest, t: LodTileMeta, base = 'context/lod/', signal?: AbortSignal): Promise<Float32Array> {
  const r = await fetch(`${lodBase(m.datasetId, base)}${t.file}`, { signal });
  if (!r.ok) throw new LodError(`${t.file}: HTTP ${r.status}`);
  const b = await r.arrayBuffer();
  const h = await sha256Hex(b);
  if (h !== null && h !== t.sha256) throw new LodError(`${t.file}: SHA-256 differs from the manifest`);
  return parseTile(m, t, b);
}
