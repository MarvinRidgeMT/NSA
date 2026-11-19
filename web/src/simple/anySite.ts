/**
 * S14 Part A (18 Nov 2026): the any-site results (POLARIS v2, Anish Meruva) for Simple mode.
 *
 * public/anysite/points.json is a field-for-field copy of data/anysite/precompute_summary.json made by
 * scripts/build_anysite_web.mjs: one row per point that was computed for the file's own window and mast (the current sites,
 * past landing sites, a 1° grid around each pole and a 10° grid over the rest of the Moon), plus rows that have no result
 * because no coordinates are published for them. The page fetches it the first time "Check a spot" or a pin card is used.
 *
 * Nothing here computes visibility. A spot is answered from the nearest row that has a result; the only arithmetic is the
 * great-circle distance to it (spotCheck.distanceM, on the sphere of the NASA map copy) and from a grid point to its closest
 * neighbour in the same grid. Every value shown is the row's own.
 */
import { distanceM } from './spotCheck';

export const ANYSITE_FILE = 'anysite/points.json';
/** the credit line, as the file's own `credit` field has it (a unit test holds the two equal); used where the file is not loaded yet */
export const ANYSITE_CREDIT = 'Any-site results: POLARIS v2 (Anish Meruva)';
/** the member of a row's `uncertainty` the page shows: the spread across the PGDA 78 terrain clones */
export const CLONES = 'pgda78-clone';

export interface CloneStat {
  min: number;
  max: number;
  median: number;
  n: number;
}
export interface CloneRanges {
  sun_center_visible_pct_hourly_samples: CloneStat;
  sun_and_earth_center_visible_pct_hourly_samples: CloneStat;
  earth_center_visible_pct_hourly_samples: CloneStat;
  longest_sun_center_hidden_h: CloneStat;
  label: string;
}
/** One row of the file. Only rows with status "done" carry coordinates and values. */
export interface AnyRow {
  id: string;
  name: string;
  group: string;
  lat: number | null;
  lon: number | null;
  status: string;
  reason?: string;
  slope_deg?: number;
  sun_pct?: number;
  earth_pct?: number;
  sun_earth_pct?: number;
  longest_sun_gap_h?: number;
  uncertainty?: { [CLONES]?: CloneRanges };
}
/** A row with a result: the only kind a spot is answered from. */
export interface AnyPoint extends AnyRow {
  lat: number;
  lon: number;
  status: 'done';
  slope_deg: number;
  sun_pct: number;
  earth_pct: number;
  sun_earth_pct: number;
  longest_sun_gap_h: number;
}
export interface AnySiteFile {
  schema: 'POLARIS-X-anysite-web-v1';
  credit: string;
  source: { file: string; schema: string; sha256: string; bytes: number; branch: string; commit: string };
  label: string;
  window: string;
  counts: Record<string, Record<string, number>>;
  kept: string[];
  sites: AnyRow[];
}

const num = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

/**
 * The rows a spot may be answered from: status "done" with coordinates and every value the card shows. Rows marked
 * "needs coordinates" (the file has nine, Artemis III regions with no published coordinates) are skipped.
 */
export function computedPoints(file: AnySiteFile): AnyPoint[] {
  return file.sites.filter((s): s is AnyPoint => s.status === 'done' && num(s.lat) && num(s.lon) && num(s.sun_pct) && num(s.earth_pct) && num(s.sun_earth_pct) && num(s.longest_sun_gap_h) && num(s.slope_deg));
}

/** The computed point closest to a spot (great circle on a sphere of `radiusM`), and how far away it is. The first wins a tie. */
export function nearestPoint(radiusM: number, points: AnyPoint[], lat: number, lon: number): { point: AnyPoint; distM: number } | null {
  let best: { point: AnyPoint; distM: number } | null = null;
  for (const p of points) {
    const d = distanceM(radiusM, lat, lon, p.lat, p.lon);
    if (!best || d < best.distM) best = { point: p, distM: d };
  }
  return best;
}

/** "1" for south_grid_1deg, "10" for global_grid_10deg; null when the row is a named point, not part of a grid. */
export function gridDeg(p: AnyRow): string | null {
  return /_grid_(\d+(?:\.\d+)?)deg$/.exec(p.group)?.[1] ?? null;
}

/**
 * The grid spacing at a grid point: the distance to its closest neighbour in the same grid (the 1° grids have fewer points
 * per ring toward the pole, so this differs from place to place). Null for a named point.
 */
export function gridSpacingM(radiusM: number, points: AnyPoint[], p: AnyPoint): number | null {
  if (gridDeg(p) === null) return null;
  let best = Infinity;
  for (const q of points) {
    if (q === p || q.group !== p.group) continue;
    best = Math.min(best, distanceM(radiusM, p.lat, p.lon, q.lat, q.lon));
  }
  return Number.isFinite(best) ? best : null;
}

/** up to one decimal, trailing ".0" dropped: 88 and 138.5 */
const deg = (v: number) => String(Number(Math.abs(v).toFixed(1)));
/** A grid point is at a pole when it rounds to 90° at the precision shown (the file stores its two poles at ±89.999999°). */
const atPole = (p: AnyPoint) => deg(p.lat) === '90';

/** What the card calls a point: its name in the file, or for a grid point "1° grid point 88°S 138.5°W". */
export function pointLabel(p: AnyPoint): string {
  const g = gridDeg(p);
  if (g === null) return p.name;
  if (atPole(p)) return `${g}° grid point at the ${p.lat < 0 ? 'south' : 'north'} pole`;
  return `${g}° grid point ${deg(p.lat)}°${p.lat < 0 ? 'S' : 'N'} ${deg(p.lon)}°${p.lon < 0 ? 'W' : 'E'}`;
}

/** The range across the terrain clones for a point, when the file has one (it does for two of the current sites). */
export function cloneRanges(p: AnyRow): CloneRanges | null {
  const c = p.uncertainty?.[CLONES];
  return c && num(c.sun_center_visible_pct_hourly_samples?.min) ? c : null;
}

export interface AnyWindow {
  /** "14 Nov 2026" */
  start: string;
  /** "00:00" */
  startTime: string;
  days: number;
  mastM: number;
  /** "14 days from 14 Nov 2026 00:00 UTC, hourly samples" */
  text: string;
}
/**
 * The file states its window and mast in one line ("2026-11-14 00:00 UTC + 14 d, hourly; mast 1 m"). This reads the date,
 * the number of days and the mast height out of that line; null when the line is not in that form (the card then shows the
 * line as written).
 */
export function parseWindow(line: string): AnyWindow | null {
  const m = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}:\d{2}) UTC \+ (\d+(?:\.\d+)?) d, hourly; mast (\d+(?:\.\d+)?) m$/.exec(line.trim());
  if (!m) return null;
  const when = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
  if (Number.isNaN(when.getTime())) return null;
  const start = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(when);
  const days = Number(m[5]);
  return { start, startTime: m[4], days, mastM: Number(m[6]), text: `${days} days from ${start} ${m[4]} UTC, hourly samples` };
}
/** Window and mast as one phrase: "14 days from 14 Nov 2026 00:00 UTC, hourly samples, 1 m mast", or the file's own line. */
export function windowPhrase(file: AnySiteFile): string {
  const w = parseWindow(file.window);
  return w ? `${w.text}, ${w.mastM} m mast` : file.window;
}

/**
 * The file's results are for one mast height (1 m). Where they sit beside numbers for the mast picked in the top bar, the
 * card says which mast they are for: just "1 m mast" when the picked mast is that height, and otherwise "for a 1 m mast (not
 * the 10 m mast picked above)", so they are never read as values for the picked mast. `pickedM` null = no mast is shown.
 */
export function mastLabel(any: AnySite, pickedM: number | null): { same: boolean; label: string; window: string } {
  const own = any.window?.mastM ?? null;
  const window = any.window?.text ?? any.file.window;
  if (own === null) return { same: false, label: `for the mast the file states (${any.file.window}), not necessarily the mast picked above`, window };
  if (pickedM === own) return { same: true, label: `${own} m mast`, window };
  return { same: false, label: `for a ${own} m mast (not the ${pickedM === null ? 'mast' : `${pickedM} m mast`} picked above)`, window };
}

/** One decimal, the precision the Simple cards use for a percentage. */
export const pct = (v: number) => `${v.toFixed(1)} %`;
/** "87.5–97.3 %", or one value when the clones all agree. */
export const pctRange = (s: CloneStat) => (s.min === s.max ? pct(s.min) : `${s.min.toFixed(1)}–${s.max.toFixed(1)} %`);
/** Hours from hourly samples: "19 h". */
export const hours = (v: number) => `${Number(v.toFixed(1))} h`;
export const hoursRange = (s: CloneStat) => (s.min === s.max ? hours(s.min) : `${Number(s.min.toFixed(1))}–${Number(s.max.toFixed(1))} h`);
/** "0.7°" */
export const slopeText = (v: number) => `${v.toFixed(1)}°`;

/**
 * The file's row for one of the bundle's sites: same id and the same coordinates as the bundle gives. Null when the file has
 * no such row (then the pin card adds nothing for that site).
 */
export function siteRow(points: AnyPoint[], id: string, lat: number, lon: number): AnyPoint | null {
  return points.find((p) => p.id === id && p.lat === lat && p.lon === lon) ?? null;
}

const HONESTY = 'SOURCE-BASED UNVALIDATED';
export interface AnySite {
  file: AnySiteFile;
  points: AnyPoint[];
  window: AnyWindow | null;
  windowPhrase: string;
}
/** How long the page waits for the any-site file before giving up on that try (the next use tries again). A display choice, ms. */
export const ANYSITE_TIMEOUT_MS = 20_000;
export async function loadAnySite(url = ANYSITE_FILE, timeoutMs = ANYSITE_TIMEOUT_MS): Promise<AnySite> {
  // a request that never answers must not leave the card waiting for ever: it is dropped, the card says so, and the next
  // check or pin card asks again
  const stop = new AbortController();
  const timer = setTimeout(() => stop.abort(), timeoutMs);
  try {
    return await fetchAnySite(url, stop.signal);
  } catch (e) {
    if (stop.signal.aborted) throw new Error(`${url}: no answer after ${timeoutMs / 1000} s`);
    throw e;
  } finally {
    clearTimeout(timer);
  }
}
async function fetchAnySite(url: string, signal: AbortSignal): Promise<AnySite> {
  const r = await fetch(url, { signal });
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  const file = (await r.json()) as AnySiteFile;
  if (file.schema !== 'POLARIS-X-anysite-web-v1' || !Array.isArray(file.sites)) throw new Error(`unexpected any-site file (${String(file.schema)})`);
  // the card prints SOURCE-BASED · UNVALIDATED beside these numbers: only for a file that carries that label itself
  if (file.label !== HONESTY) throw new Error(`any-site file is labelled "${String(file.label)}", not "${HONESTY}"`);
  return { file, points: computedPoints(file), window: parseWindow(file.window), windowPhrase: windowPhrase(file) };
}
