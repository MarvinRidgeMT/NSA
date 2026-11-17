/**
 * "Query any point" (V2 §2.5, T2): precomputed any-site rows and the local solver API. The browser computes no science:
 * it picks the nearest precomputed row (a table lookup by great-circle distance, never interpolated to the clicked point)
 * or forwards the point to the local solver API (science/anysite/api.py, or T1's science/api) and shows its answer.
 */
import { greatCircleKm } from './geo';

export const SUMMARY_URL = 'anysite/precompute_summary.json';
export const SUMMARY_META_URL = 'anysite/precompute_summary.meta.json';
/** Vite dev/preview proxy prefix -> http://127.0.0.1:8766 (override with POLARIS_SOLVER_API); see vite.config.ts */
export const SOLVER_BASE = 'solver-api/';
export const SOLVER_START = '$POLARIS_PYTHON -m science.anysite.api --serve 8766';

export interface MemberStat {
  min: number;
  max: number;
  median: number;
  n: number;
}
export interface MemberSet {
  label?: string;
  status?: string;
  reason?: string;
  sun_center_visible_pct_hourly_samples?: MemberStat;
  sun_and_earth_center_visible_pct_hourly_samples?: MemberStat;
  earth_center_visible_pct_hourly_samples?: MemberStat;
  longest_sun_center_hidden_h?: MemberStat;
}
export interface AnysiteRow {
  id: string;
  name: string;
  group: string;
  lat: number | null;
  lon: number | null;
  status: string;
  reason?: string;
  site_hash?: string;
  terrain?: string;
  near_product?: string;
  far_product?: string;
  near_cut_m?: number;
  near_level?: number;
  near_zone?: string;
  ground_m?: number;
  slope_deg?: number;
  sun_pct?: number;
  earth_pct?: number;
  sun_earth_pct?: number;
  longest_sun_gap_h?: number;
  n_unknown_sun?: number;
  n_truncated_bins?: number;
  max_range_m?: number;
  required_range_world_m?: number;
  wall_s?: number;
  uncertainty?: Record<string, MemberSet | Record<string, unknown>>;
  horizons_raw?: string[];
}
export interface AnysiteSummary {
  schema: 'polaris-anysite-precompute-summary-v1';
  label: string;
  window: string;
  terrain: string;
  counts: Record<string, Record<string, number>>;
  sites: AnysiteRow[];
}
export interface SummaryMeta {
  source: string;
  sha256: string;
  bytes: number;
}

export function validateSummary(j: unknown): AnysiteSummary {
  const s = j as AnysiteSummary;
  if (!s || s.schema !== 'polaris-anysite-precompute-summary-v1' || !Array.isArray(s.sites)) throw new Error('not a polaris-anysite-precompute-summary-v1 file');
  return s;
}

export const isDone = (r: AnysiteRow): r is AnysiteRow & { lat: number; lon: number } =>
  r.status === 'done' && typeof r.lat === 'number' && typeof r.lon === 'number' && Number.isFinite(r.lat) && Number.isFinite(r.lon);

/** Nearest done row by great-circle distance on the 1,737.4 km sphere. Rows without coordinates are never picked. */
export function nearestSite(rows: AnysiteRow[], lat: number, lon: number): { row: AnysiteRow & { lat: number; lon: number }; distanceKm: number } | null {
  let best: (AnysiteRow & { lat: number; lon: number }) | null = null;
  let bd = Infinity;
  for (const r of rows) {
    if (!isDone(r)) continue;
    const d = greatCircleKm(lat, lon, r.lat, r.lon);
    if (d < bd) {
      bd = d;
      best = r;
    }
  }
  return best ? { row: best, distanceKm: bd } : null;
}

/** Members the precompute ran per group (science/anysite/precompute.py `_members_for`). */
export const membersFor = (group: string) => (group === 'current_sites' || group === 'landing_sites' ? 'clones,assumed,products' : '');

const sh = (s: string) => `'${s.replace(/'/g, `'\\''`)}'`;
/** CLI that recomputes a row (same window and mast as the precompute summary: 2026-11-14 00:00 UTC + 14 d hourly, mast 1 m). */
export function reproduceCommand(lat: number, lon: number, opts: { members?: string; name?: string } = {}): string {
  const members = opts.members ?? 'clones,assumed,products';
  return [
    '$POLARIS_PYTHON -m science.anysite.solve',
    `--lat ${lat}`,
    `--lon ${lon}`,
    '--mast 1',
    `--start '2026-11-14 00:00'`,
    '--days 14',
    `--members ${sh(members)}`,
    ...(opts.name ? [`--name ${sh(opts.name)}`] : []),
  ].join(' ');
}

/** Member sets with numbers (clones / assumed error model), in display order; 'products' and not-run sets are reported separately. */
export function memberRanges(r: AnysiteRow): { key: string; label: string; set: MemberSet }[] {
  const out: { key: string; label: string; set: MemberSet }[] = [];
  for (const [k, v] of Object.entries(r.uncertainty ?? {})) {
    if (k === 'products') continue;
    const m = v as MemberSet;
    if (m.sun_center_visible_pct_hourly_samples) out.push({ key: k, label: m.label ?? k, set: m });
  }
  return out;
}
export function membersNotRun(r: AnysiteRow): { key: string; reason: string }[] {
  return Object.entries(r.uncertainty ?? {})
    .filter(([k, v]) => k !== 'products' && (v as MemberSet).status === 'not-run')
    .map(([k, v]) => ({ key: k, reason: (v as MemberSet).reason ?? 'not run' }));
}

export async function loadSummary(fetcher: typeof fetch = fetch): Promise<{ summary: AnysiteSummary; meta: SummaryMeta | null }> {
  const r = await fetcher(SUMMARY_URL);
  if (!r.ok || !(r.headers.get('content-type') ?? '').includes('json')) throw new Error(`${SUMMARY_URL} is not in this build (run npm run sync-bundles)`);
  const summary = validateSummary(await r.json());
  let meta: SummaryMeta | null = null;
  try {
    const m = await fetcher(SUMMARY_META_URL);
    if (m.ok && (m.headers.get('content-type') ?? '').includes('json')) meta = (await m.json()) as SummaryMeta;
  } catch {
    meta = null;
  }
  return { summary, meta };
}

// ------------------------------------------------------------------------------------------------ solver API client
export type SolverProbe = { state: 'running'; name: string; endpoint: string } | { state: 'down'; why: string };

/** GET solver-api/ : the stub answers its SPEC ({name, endpoint, …}). Anything else (proxy error, HTML, timeout) = down. */
export async function probeSolver(fetcher: typeof fetch = fetch, timeoutMs = 2500): Promise<SolverProbe> {
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), timeoutMs);
  try {
    const r = await fetcher(SOLVER_BASE, { signal: ac.signal });
    if (!r.ok) return { state: 'down', why: `HTTP ${r.status} from the proxy (nothing answering on the solver port)` };
    if (!(r.headers.get('content-type') ?? '').includes('json')) return { state: 'down', why: 'no solver proxy in this server (static hosting)' };
    const j = (await r.json()) as { name?: string; endpoint?: string };
    if (!j || typeof j !== 'object' || !j.endpoint) return { state: 'down', why: 'the answer is not a POLARIS solver spec' };
    return { state: 'running', name: j.name ?? 'solver', endpoint: j.endpoint };
  } catch (e) {
    return { state: 'down', why: ac.signal.aborted ? `no answer within ${timeoutMs / 1000} s` : e instanceof Error ? e.message : String(e) };
  } finally {
    clearTimeout(timer);
  }
}

/** Compact answer of science/anysite/api.py (POST /anysite). Fields are optional so a newer API can add to it. */
export interface SolverAnswer {
  site_hash?: string;
  bundle_path?: string;
  cache_hit?: boolean;
  label?: string;
  ground_m?: number;
  sun_center_visible_pct_hourly_samples?: number;
  sun_and_earth_center_visible_pct_hourly_samples?: number;
  longest_sun_center_hidden_h?: number;
  n_truncated_bins?: number;
  near_product?: string;
  far_product?: string;
  timing_s?: Record<string, number>;
  error?: string;
}

export async function computeNow(lat: number, lon: number, members: string[] = [], fetcher: typeof fetch = fetch, timeoutMs = 180_000): Promise<SolverAnswer> {
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), timeoutMs);
  try {
    const r = await fetcher(`${SOLVER_BASE}anysite`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lat, lon, mast_m: 1, start: '2026-11-14 00:00', days: 14, step_h: 1, members }),
      signal: ac.signal,
    });
    const ct = r.headers.get('content-type') ?? '';
    if (!ct.includes('json')) return { error: `HTTP ${r.status}: the solver API did not answer JSON` };
    const j = (await r.json()) as SolverAnswer;
    if (!r.ok && !j.error) return { error: `HTTP ${r.status}` };
    return j;
  } catch (e) {
    return { error: ac.signal.aborted ? `no answer within ${timeoutMs / 1000} s` : e instanceof Error ? e.message : String(e) };
  } finally {
    clearTimeout(timer);
  }
}
