/**
 * S13 "Check a spot" (18 Nov 2026): what the data files say about a latitude and longitude near the Moon's south pole.
 *
 * Two sources, never mixed:
 *  - our own 14-day results exist only at the sites we computed (bundle + certainty sidecar); nearestSite() says how far
 *    the point is from the closest one, and the card shows that site's result only inside a stated distance;
 *  - NASA PGDA product 69 (Mazarico et al. 2011), per 60 m cell over hourly timesteps spanning 18.6 years: for the Sun the
 *    average fraction of the solar disc in view (label title and column: "average illumination by the solar disc",
 *    "average solar disc visibility"); for the Earth the share of timesteps with any part of its disc in view (product
 *    page). The manifest's `meaning` carries the words and the one label sentence that reads otherwise. Looked up in the
 *    web copy made by scripts/build_pgda69_web.py (public/pgda69-spot, original int16 values, fetched only when S13 opens).
 *
 * Nothing here computes visibility. The only arithmetic is the map projection (layers/pgda69.latLonToXY), the cell index,
 * value x scale x 100 for a percentage, and a great-circle distance on the map's own sphere.
 */
import { latLonToXY } from '../layers/pgda69';

export const SPOT_BASE = 'pgda69-spot/';

export interface SpotManifest {
  schema: 'POLARIS-X-pgda69-spot-v1';
  citation: string;
  /** what the values mean, in the words of the product's labels (written into the manifest by the build script) */
  meaning: { sunShort: string; earthShort: string; basis: string; sun: string; earth: string; labelConflict?: string; statedIn: string[] };
  sources: { layer: 'sun' | 'earth'; file: string; url: string; sha256: string }[];
  grid: { radiusM: number; cellM: number; fullWidthPx: number; fullHeightPx: number; fullX0M: number; fullY0M: number; fullEdgeLatDeg: number; scale: number; offset: number; nodata: number };
  copy: { col0: number; row0: number; widthPx: number; heightPx: number; halfWidthM: number; inscribedLatDeg: number; tilePx: number; encoding: string; totalTileBytes: number };
  tiles: { r: number; c: number; file: string; bytes: number; sha256: string }[];
  checks: SpotCheckPoint[];
}
/** A point whose cell and values the build script read from the original TIFs (rasterio + pyproj). */
export interface SpotCheckPoint {
  name: string;
  siteId?: string;
  lat: number;
  lonE: number;
  row: number;
  col: number;
  inCopy: boolean;
  sunRaw: number;
  earthRaw: number;
  sun3x3: [number, number];
  earth3x3: [number, number];
}

// ---------------------------------------------------------------- input

export type ParseResult = { ok: true; lat: number; lon: number } | { ok: false; field: 'lat' | 'lon' | 'both'; message: string };

const NUM = /^([+\-−–]?\d+(?:\.\d+)?|[+\-−–]?\.\d+)\s*°?\s*([NSEW])?$/i;
function one(text: string): { v: number; hemi: string } | null {
  const m = NUM.exec(text.trim());
  if (!m) return null;
  const v = Number(m[1].replace(/[−–]/, '-'));
  return Number.isFinite(v) ? { v, hemi: (m[2] ?? '').toUpperCase() } : null;
}

/** Splits a pasted "lat, lon" (comma, semicolon or space between two numbers); null when the text is not such a pair. */
export function splitPair(text: string): [string, string] | null {
  const t = text.trim();
  const parts = t.includes(',') || t.includes(';') ? t.split(/[,;]/) : t.split(/\s+(?=[+-−–.\d])/);
  if (parts.length !== 2) return null;
  const a = parts[0].trim();
  const b = parts[1].trim();
  return one(a) && one(b) ? [a, b] : null;
}

/**
 * Latitude and longitude in decimal degrees. South and west are negative, or carry an S / W letter ("89.78 S").
 * Longitude is east-positive; 0 to 360 is accepted and read as the same meridian in −180 to 180.
 */
export function parseLatLon(latText: string, lonText: string): ParseResult {
  if (!latText.trim() && !lonText.trim()) return { ok: false, field: 'both', message: 'Enter a latitude and a longitude in decimal degrees, for example −89.5 and −137.4.' };
  const a = one(latText);
  if (!a || a.hemi === 'E' || a.hemi === 'W') return { ok: false, field: 'lat', message: 'Latitude is not a number in decimal degrees. Example: −89.5 (south is negative), or 89.5 S.' };
  const b = one(lonText);
  if (!b || b.hemi === 'N' || b.hemi === 'S') return { ok: false, field: 'lon', message: 'Longitude is not a number in decimal degrees. Example: −137.4 (west is negative), or 137.4 W.' };
  if (a.hemi && a.v < 0) return { ok: false, field: 'lat', message: 'Latitude has both a minus sign and a letter. Use one: −89.5 or 89.5 S.' };
  if (b.hemi && b.v < 0) return { ok: false, field: 'lon', message: 'Longitude has both a minus sign and a letter. Use one: −137.4 or 137.4 W.' };
  const lat = a.hemi === 'S' ? -a.v : a.v;
  let lon = b.hemi === 'W' ? -b.v : b.v;
  if (lat < -90 || lat > 90) return { ok: false, field: 'lat', message: 'Latitude must be between −90 and 90 degrees.' };
  if (lon < -180 || lon > 360) return { ok: false, field: 'lon', message: 'Longitude must be between −180 and 180 degrees (or 0 to 360).' };
  if (lon > 180) lon -= 360;
  return { ok: true, lat, lon };
}

// ---------------------------------------------------------------- the map cell

export type Coverage =
  | { kind: 'cell'; row: number; col: number }
  /** north of the whole NASA product (it covers 85°S to the pole) */
  | { kind: 'outside-map' }
  /** on NASA's map, but outside the part this site carries */
  | { kind: 'outside-copy' };

/** Which 60 m cell of the full map holds this point (row from the top, column from the left), or why there is none. */
export function cellOf(m: SpotManifest, lat: number, lon: number): Coverage {
  if (lat > m.grid.fullEdgeLatDeg) return { kind: 'outside-map' };
  const [x, y] = latLonToXY(lat, lon);
  const col = Math.floor((x - m.grid.fullX0M) / m.grid.cellM);
  const row = Math.floor((m.grid.fullY0M - y) / m.grid.cellM);
  if (row < 0 || col < 0 || row >= m.grid.fullHeightPx || col >= m.grid.fullWidthPx) return { kind: 'outside-map' };
  const r = row - m.copy.row0;
  const c = col - m.copy.col0;
  if (r < 0 || c < 0 || r >= m.copy.heightPx || c >= m.copy.widthPx) return { kind: 'outside-copy' };
  return { kind: 'cell', row, col };
}

export interface Tile {
  sun: Int16Array;
  earth: Int16Array;
}

/**
 * Undo the tile encoding (manifest copy.tileLayout): Sun layer then Earth layer; each is the low bytes then the high bytes
 * of row-wise differences, which add back up (wrapping in 16 bits) to the original int16 values.
 */
export function decodeTile(bytes: Uint8Array, tilePx: number): Tile {
  const n = tilePx * tilePx;
  if (bytes.length !== 4 * n) throw new Error(`tile has ${bytes.length} bytes, expected ${4 * n}`);
  const layer = (o: number) => {
    const out = new Int16Array(n);
    for (let r = 0; r < tilePx; r++) {
      let acc = 0;
      for (let c = 0; c < tilePx; c++) {
        const i = r * tilePx + c;
        acc = (acc + (bytes[o + i] | (bytes[o + n + i] << 8))) & 0xffff;
        out[i] = acc; // Int16Array wraps 0..65535 to −32768..32767
      }
    }
    return out;
  };
  return { sun: layer(0), earth: layer(2 * n) };
}

/**
 * The tile's bytes, gzip undone. Some servers send a .gz file with "Content-Encoding: gzip", and the browser has then already
 * undone it; the expected length says which case this is.
 */
async function gunzip(buf: ArrayBuffer, rawLength: number): Promise<Uint8Array> {
  if (buf.byteLength === rawLength) return new Uint8Array(buf);
  const stream = new Blob([buf]).stream().pipeThrough(new DecompressionStream('gzip'));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

export type TileGetter = (r: number, c: number) => Promise<Tile>;

/** Fetches and decodes tiles of the web copy, each once. */
export function tileLoader(m: SpotManifest, base = SPOT_BASE): TileGetter {
  const cache = new Map<string, Promise<Tile>>();
  const byRc = new Map(m.tiles.map((t) => [`${t.r},${t.c}`, t]));
  return (r, c) => {
    const key = `${r},${c}`;
    let p = cache.get(key);
    if (!p) {
      const t = byRc.get(key);
      p = !t
        ? Promise.reject(new Error(`no tile r${r}c${c}`))
        : fetch(base + t.file)
            .then((res) => {
              if (!res.ok) throw new Error(`${t.file}: HTTP ${res.status}`);
              return res.arrayBuffer();
            })
            .then((buf) => gunzip(buf, 4 * m.copy.tilePx * m.copy.tilePx))
            .then((b) => decodeTile(b, m.copy.tilePx));
      p.catch(() => cache.delete(key)); // a failed fetch may be tried again
      cache.set(key, p);
    }
    return p;
  };
}

export async function loadSpotManifest(base = SPOT_BASE): Promise<SpotManifest> {
  const r = await fetch(`${base}manifest.json`);
  if (!r.ok) throw new Error(`${base}manifest.json: HTTP ${r.status}`);
  const m = (await r.json()) as SpotManifest;
  if (m.schema !== 'POLARIS-X-pgda69-spot-v1' || m.copy.encoding !== 'rowdelta-bytesplit-gzip') throw new Error(`unexpected map copy (${String(m.schema)})`);
  return m;
}

export interface Around {
  /** the cell's own stored value */
  raw: number;
  /** smallest and largest stored value among the cell and its neighbours that the copy holds, and how many cells that is */
  min: number;
  max: number;
  cells: number;
}
export interface SpotValues {
  row: number;
  col: number;
  sun: Around;
  earth: Around;
}

/** The stored values of a cell and of the 3 x 3 block around it. Cells outside the copy, or marked no-data, are left out. */
export async function lookupCell(m: SpotManifest, get: TileGetter, row: number, col: number): Promise<SpotValues> {
  const t = m.copy.tilePx;
  const at = async (r: number, c: number): Promise<[number, number] | null> => {
    const wr = r - m.copy.row0;
    const wc = c - m.copy.col0;
    if (wr < 0 || wc < 0 || wr >= m.copy.heightPx || wc >= m.copy.widthPx) return null;
    const tile = await get(Math.floor(wr / t), Math.floor(wc / t));
    const i = (wr % t) * t + (wc % t);
    return [tile.sun[i], tile.earth[i]];
  };
  const here = await at(row, col);
  if (!here) throw new Error('cell is outside the map copy');
  const sun: Around = { raw: here[0], min: Infinity, max: -Infinity, cells: 0 };
  const earth: Around = { raw: here[1], min: Infinity, max: -Infinity, cells: 0 };
  for (let dr = -1; dr <= 1; dr++)
    for (let dc = -1; dc <= 1; dc++) {
      const v = await at(row + dr, col + dc);
      if (!v) continue;
      for (const [a, x] of [[sun, v[0]], [earth, v[1]]] as const) {
        if (x === m.grid.nodata) continue;
        a.min = Math.min(a.min, x);
        a.max = Math.max(a.max, x);
        a.cells++;
      }
    }
  return { row, col, sun, earth };
}

// ---------------------------------------------------------------- words and numbers

/** Stored value as a percentage (value x scale x 100), exactly as far as the file goes. */
export const rawToPct = (m: SpotManifest, raw: number) => raw * m.grid.scale * 100 + m.grid.offset * 100;
/** One decimal, the precision the card shows. */
export const pct1 = (m: SpotManifest, raw: number) => rawToPct(m, raw).toFixed(1);

/** Great-circle distance in metres on a sphere of `radiusM` (the map's own sphere). */
export function distanceM(radiusM: number, lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = Math.PI / 180;
  const p1 = lat1 * R;
  const p2 = lat2 * R;
  const h = Math.sin((p2 - p1) / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(((lon2 - lon1) * R) / 2) ** 2;
  return 2 * radiusM * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** Metres as words: whole metres under a kilometre, then kilometres to one decimal. */
export function fmtDistance(m: number): string {
  return m < 999.5 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`;
}

/** "89.7801° S, 156.3202° W": what the card says back, to four decimals (about 3 m of latitude). */
export function fmtLatLon(lat: number, lon: number): string {
  return `${Math.abs(lat).toFixed(4)}° ${lat <= 0 ? 'S' : 'N'}, ${Math.abs(lon).toFixed(4)}° ${lon < 0 ? 'W' : 'E'}`;
}

export interface SpotSite {
  id: string;
  name: string;
  lat: number;
  lon: number;
}
/** The computed site closest to the point, and how far away it is. */
export function nearestSite<T extends SpotSite>(radiusM: number, sites: T[], lat: number, lon: number): { site: T; distM: number } | null {
  let best: { site: T; distM: number } | null = null;
  for (const s of sites) {
    const d = distanceM(radiusM, lat, lon, s.lat, s.lon);
    if (!best || d < best.distM) best = { site: s, distM: d };
  }
  return best;
}

/**
 * How close a point must be to a computed site for that site's result to be shown as "ours": half the smallest step between
 * the positions the bundle was computed at, so the site is the nearest computed position. The step is read from the bundle:
 * datasets[].derived.scenarios[] with kind "position_offset", length of (parameters.east_m, parameters.north_m); in the
 * opening bundle (polaris-x5d-roi-2026-11-14-v2.json) those are the ±100 m offsets pos_e±100_n+0 and pos_e+0_n±100.
 * Null when the bundle has no position offsets (then no distance is claimed and no result is shown).
 */
export const MATCH_FIELD = 'east_m / north_m of its position_offset scenarios';
export function matchDistanceM(scenarios: { kind?: string; parameters?: Record<string, unknown> }[] | undefined): { stepM: number; withinM: number } | null {
  let step = Infinity;
  for (const s of scenarios ?? []) {
    if (s.kind !== 'position_offset') continue;
    const e = Number(s.parameters?.east_m);
    const n = Number(s.parameters?.north_m);
    const d = Math.hypot(e, n);
    if (Number.isFinite(d) && d > 0) step = Math.min(step, d);
  }
  return Number.isFinite(step) ? { stepM: step, withinM: step / 2 } : null;
}

/** Latitude / east longitude of a unit vector in the globe's model frame (inverse of globeMath.moonDir). */
export function dirToLatLon(d: readonly [number, number, number]): { lat: number; lon: number } {
  const n = Math.hypot(d[0], d[1], d[2]) || 1;
  return { lat: (Math.asin(Math.max(-1, Math.min(1, d[1] / n))) * 180) / Math.PI, lon: (Math.atan2(-d[0], -d[2]) * 180) / Math.PI };
}
