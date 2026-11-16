/**
 * Adapter: Person A's `science-bundle-v2` (branch a-science, docs/SCIENTIFIC_CONTRACT.md) -> the viewer's
 * internal model. Pure re-shaping: every number is copied from the bundle. Nothing is recomputed,
 * interpolated or filled. Contract rules honoured here and downstream:
 *   - status: `validation_status.overall` and every check are shown;
 *   - truncated skyline bins are kept as lower bounds; null bins stay null;
 *   - the time slider snaps to sample times (snapToSamples);
 *   - azimuths are LOCAL; the viewer does not rotate them by longitude (no `derived.frame`, and the 3D view
 *     for this format draws in local east/north/up).
 */
import type { ArrivalSlipBlock, Attribution, Bundle, BundleEvent, CertaintyCurve, Coverage, CriticalCell, Dataset, FlipForecastBlock, Gate, HotspotsBlock, MarginRange, Metric, RawStatus, Scenario, TargetSeries } from './types';
import { BundleError } from './errors';
import { TEAM_REQUIREMENTS, TEAM_REQUIREMENTS_SOURCE } from './requirements';

/* ---------- raw shape (only the fields the viewer reads) ---------- */
interface RawTarget {
  az_deg: number;
  el_deg: number;
  horizon_deg: number | null;
  margin_deg: number | null;
  center_visible: boolean | null;
  disk_fraction?: number | null;
  horizon_flag?: string;
}
interface RawSample {
  utc: string;
  t_unix: number;
  sun: RawTarget;
  earth: RawTarget;
}
type RawMetrics = Record<string, unknown> & { label?: string };
interface RawScenario {
  id: string;
  family: string;
  parameters?: Record<string, unknown>;
  label?: string;
  method?: string;
  site_lat_deg?: number;
  site_lon_deg_east?: number;
  site_height_m?: number;
  metrics: Record<string, number>;
  delta_vs_baseline?: Record<string, number>;
  skyline_summary?: Scenario['skylineSummary'];
  events?: { body: 'sun' | 'earth'; event: string; utc: string }[];
}
export interface RawScienceV2 {
  /** Person A renamed the results schema on 14 Nov (A_SCIENCE_STATUS); both names carry the same structure. */
  schema: 'science-bundle-v2' | 'polaris-science-results-v1';
  /** decision-evidence outputs (additive, snake_case in the bundle; see VIEWER_BUNDLE_CONTRACT §Decision-evidence) */
  /** a-science 13d23d4+: decision-evidence blocks live under `derived` (A1 `derived.attribution`); top level also accepted */
  derived?: { attribution?: unknown; coverage?: unknown; certainty_curve?: unknown; margin_range?: unknown; margins?: unknown; margin_series?: unknown; certainty_height_m?: unknown; requirements?: unknown; certainty_note?: unknown; arrival_slip?: ArrivalSlipBlock; hotspots?: HotspotsBlock; flip_forecast?: FlipForecastBlock; [key: string]: unknown };
  attribution?: unknown;
  coverage?: unknown;
  certainty_curve?: unknown;
  margin_range?: unknown;
  certainty_height_m?: unknown;
  requirements?: unknown;
  near_zero_margin_deg?: number;
  bundle_id: string;
  generated_utc: string;
  generator?: { code?: string; git_commit?: string; command?: string };
  validation_status: { overall: string; checks: { id: string; status: string; evidence?: string }[] };
  site: { id: string; name: string; lat_deg: number; lon_deg_east: number; height_m?: number; observer_mast_m?: number; observer_eye_height_m?: number; grid_x_m?: number; grid_y_m?: number; coordinates_source?: string };
  frame?: Record<string, unknown>;
  time: { scale: string; start_utc: string; stop_utc: string; step_h?: number; n_samples: number };
  skyline: {
    bins: number;
    azimuth_deg: number[];
    elevation_deg: (number | null)[];
    status: string[];
    range_limited?: boolean[];
    valid_reach_m?: number[];
    critical?: CriticalCell[];
    dem_layers?: { role?: string; name: string; step_m?: number; source_url?: string; file_sha256?: string; array_sha256?: string }[];
    label?: string;
  };
  samples: RawSample[];
  events?: { body: 'sun' | 'earth'; kind?: string; event: string; direction?: string; utc: string; bracket_width_s?: number; horizon_flag?: string }[];
  metrics: RawMetrics;
  scenarios?: RawScenario[];
  provenance?: { sources?: { id: string; description?: string; url?: string; sha256?: string }[]; horizons_raw?: { role?: string; path: string; sha256: string; retrieved_utc?: string }[] };
  limitations?: string[];
  fixture?: { of_bundle?: string; sample_indices?: number[]; note?: string };
}

/* ---------- labels ---------- */
const METRICS: { key: string; label: string; unit: string }[] = [
  { key: 'sun_center_visible_pct', label: 'Sun centre visible', unit: '%' },
  { key: 'earth_center_visible_pct', label: 'Earth centre visible', unit: '%' },
  { key: 'sun_and_earth_center_visible_pct', label: 'Sun and Earth together', unit: '%' },
  { key: 'longest_sun_center_hidden_h', label: 'Longest Sun obstruction', unit: 'h' },
  { key: 'longest_earth_center_hidden_h', label: 'Longest Earth obstruction', unit: 'h' },
  { key: 'sun_disk_mean_visible_fraction', label: 'Mean visible Sun disk', unit: 'fraction' },
  { key: 'earth_disk_mean_visible_fraction', label: 'Mean visible Earth disk', unit: 'fraction' },
  { key: 'min_sun_margin_deg', label: 'Worst Sun margin', unit: '°' },
  { key: 'min_earth_margin_deg', label: 'Worst Earth margin', unit: '°' },
  { key: 'max_earth_margin_deg', label: 'Best Earth margin', unit: '°' },
];

const FAMILY_LABEL: Record<string, string> = {
  'position-offset': 'Position offset',
  'mast-height': 'Mast height',
  'arrival-shift': 'Arrival shift',
  'dem-uncertainty': 'Terrain uncertainty',
  repair: 'Repair',
};

export function rawStatus(overall: string): RawStatus {
  const s = overall.toUpperCase().replace(/[\s-]+/g, '_');
  if (s.includes('DEMO')) return 'DEMO_ONLY';
  if (s === 'VALIDATED' || s === 'VALIDATED_NASA_JPL') return 'VALIDATED_NASA_JPL';
  if (s.includes('SOURCE_BASED') && s.includes('UNVALIDATED')) return 'SOURCE_BASED_UNVALIDATED';
  return 'UNKNOWN' as RawStatus; // displayStatus() treats anything unknown as DEMO (most cautious)
}

function scenarioLabel(r: RawScenario): string {
  const fam = FAMILY_LABEL[r.family] ?? r.family;
  const p = r.parameters ?? {};
  switch (r.family) {
    case 'position-offset':
      return `${fam}: ${p.east_m ?? 0} m E, ${p.north_m ?? 0} m N`;
    case 'mast-height':
      return `${fam}: ${p.mast_m} m`;
    case 'arrival-shift':
      return `${fam}: ${Number(p.shift_h) > 0 ? '+' : ''}${p.shift_h} h`;
    case 'dem-uncertainty':
      return p.kind === 'product-78-clone' ? `${fam}: PGDA 78 clone ${p.clone}` : `${fam}: ${p.kind} ${Number(p.sigma) > 0 ? '+' : ''}${p.sigma}σ`;
    case 'repair':
      return `${fam}: ${p.east_m} m E, ${p.north_m} m N, mast ${p.mast_m} m`;
    default:
      return `${fam}: ${r.id}`;
  }
}

function teamConstraint(key: string, value: number): Partial<Metric> {
  const r = TEAM_REQUIREMENTS[key];
  if (!r || !Number.isFinite(value)) return {};
  const margin = r.op === '>=' ? value - r.threshold : r.threshold - value;
  return { constraint: { op: r.op, threshold: r.threshold }, marginToLimit: margin, pass: margin >= 0, constraintSource: TEAM_REQUIREMENTS_SOURCE };
}

function metricList(m: Record<string, unknown>, delta?: Record<string, number>): Metric[] {
  return METRICS.filter((d) => typeof m[d.key] === 'number').map((d) => ({
    id: d.key,
    label: d.label,
    value: m[d.key] as number,
    unit: d.unit,
    ...(delta && typeof delta[d.key] === 'number' ? { delta: delta[d.key] } : {}),
    ...teamConstraint(d.key, m[d.key] as number),
  }));
}

function fail(msg: string): never {
  throw new BundleError(`science-bundle-v2: ${msg}`);
}

function series(samples: RawSample[], key: 'sun' | 'earth', critical: CriticalCell[] | undefined, binDeg: number): TargetSeries {
  return {
    visible: samples.map((s, i) => {
      const v = s[key].center_visible;
      if (typeof v !== 'boolean') fail(`samples[${i}].${key}.center_visible is not boolean`);
      return v;
    }),
    horizonElDeg: samples.map((s) => s[key].horizon_deg ?? Number.NaN),
    marginDeg: samples.map((s) => s[key].margin_deg ?? Number.NaN),
    // the bundle names the horizon-setting cell per skyline bin; for a blocked target we show that cell's distance
    firstHitM: samples.map((s) => {
      if (s[key].center_visible) return null;
      const bin = Math.round(s[key].az_deg / binDeg) % Math.round(360 / binDeg);
      return critical?.[bin]?.distance_m ?? null;
    }),
    firstHitKind: 'horizon-setting-cell',
    diskFraction: samples.map((s) => s[key].disk_fraction ?? Number.NaN),
    horizonFlag: samples.map((s) => s[key].horizon_flag ?? ''),
  };
}

/** snake_case → camelCase, recursively; the bundle writes snake_case, the TS types are camelCase. Values are copied, never computed. */
export function camelize<T>(x: unknown): T {
  if (Array.isArray(x)) return x.map((v) => camelize(v)) as T;
  if (x && typeof x === 'object') {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(x as Record<string, unknown>)) out[k.replace(/_([a-z0-9])/g, (_, c: string) => c.toUpperCase())] = camelize(v);
    return out as T;
  }
  return x as T;
}

/* ---- decision-evidence normalizers ----
 * Two accepted shapes each: the IMPLEMENTATION_PROMPT (A1–A3) shape the science branch emits, and the
 * earlier VIEWER_BUNDLE_CONTRACT proposal. Values are copied; nothing is derived. */
type Rec = Record<string, unknown>;
const num = (x: unknown): number | null => (typeof x === 'number' && Number.isFinite(x) ? x : null);
const numOr = (x: unknown, d: number): number => num(x) ?? d;
const isRec = (x: unknown): x is Rec => !!x && typeof x === 'object' && !Array.isArray(x);

export function normalizeAttribution(raw: unknown): Attribution {
  const c = camelize<Rec>(raw);
  const ridges = Array.isArray(c.ridges) ? (c.ridges as Rec[]) : [];
  const pb = isRec(c.perBin) ? c.perBin : null;
  return {
    label: typeof c.label === 'string' ? c.label : undefined,
    scenarioId: typeof c.scenarioId === 'string' ? c.scenarioId : undefined,
    perBin: pb && !Array.isArray(pb.ridgeIdx) && Array.isArray(pb.ridgeId) && Array.isArray(c.ridges)
      ? { ridgeIdx: (pb.ridgeId as (string | null)[]).map((id) => { const k = (c.ridges as Rec[]).findIndex((r) => r.id === id); return k < 0 ? null : k; }), gapDeg: Array.isArray(pb.gapDeg) ? (pb.gapDeg as (number | null)[]) : undefined, source: Array.isArray(pb.source) ? (pb.source as (string | null)[]) : undefined }
      : pb && Array.isArray(pb.ridgeIdx) ? { ridgeIdx: pb.ridgeIdx as (number | null)[], ctrlDistM: Array.isArray(pb.ctrlDistM) ? (pb.ctrlDistM as (number | null)[]) : undefined, gapDeg: Array.isArray(pb.gapDeg) ? (pb.gapDeg as (number | null)[]) : undefined, source: Array.isArray(pb.source) ? (pb.source as (string | null)[]) : undefined } : undefined,
    method: typeof c.method === 'string' ? c.method : isRec(c.method) ? String(c.method.clustering ?? 'bundle attribution') : 'bundle attribution',
    methodDetail: isRec(c.method) ? (c.method as Record<string, string>) : undefined,
    clusteringNote: typeof c.clusteringNote === 'string' ? c.clusteringNote : undefined,
    ridges: ridges.map((r, i) => {
      if (isRec(r.hours)) return r as unknown as Attribution['ridges'][number]; // already the contract shape
      // IMPLEMENTATION_PROMPT A1: {id, centroid_lat, centroid_lon, dist_km, az_span_deg:[a,b], height_m, source, sun_loss_h, earth_loss_h, ctrl_h}
      const span = Array.isArray(r.azSpanDeg) ? (r.azSpanDeg as number[]) : [0, 0];
      const range = Array.isArray(r.distRangeKm) ? (r.distRangeKm as number[]) : null;
      const distM = num(r.distKm) !== null ? (r.distKm as number) * 1000 : (num(r.distanceM) ?? Number.NaN);
      const ctrl = num(r.ctrlH) ?? 0;
      return {
        id: String(r.id ?? `ridge-${i + 1}`),
        label: typeof r.label === 'string' ? r.label : undefined,
        azimuthDeg: [numOr(span[0], 0), numOr(span[1], 0)],
        distanceM: range && range.length === 2 && num(range[0]) !== null ? { min: range[0] * 1000, max: range[1] * 1000 } : distM,
        heightM: num(r.heightM) ?? undefined,
        cell: num(r.centroidLat) !== null ? { distance_m: distM, lat_deg: r.centroidLat as number, lon_deg: num(r.centroidLon), height_m: num(r.heightM), dem: typeof r.source === 'string' ? r.source : null } : undefined,
        dem: typeof r.source === 'string' ? r.source : undefined,
        runnerUpGapDeg: num(r.minGapDeg) ?? num(r.gapDeg),
        ofRecord: typeof r.ofRecord === 'boolean' ? r.ofRecord : undefined,
        reliefM: num(r.reliefM) ?? undefined,
        maxElevDeg: num(r.maxElevDeg) ?? undefined,
        // ctrl_h is a single "hours controlled" figure in the A1 shape; shown for both targets, loss per target
        hours: { sun: { controlled: num(r.sunCtrlH) ?? ctrl, lost: num(r.sunLossH) ?? 0 }, earth: { controlled: num(r.earthCtrlH) ?? ctrl, lost: num(r.earthLossH) ?? 0 } },
      };
    }),
  };
}

export function normalizeCoverage(raw: unknown, layers: RawScienceV2['skyline']['dem_layers']): Coverage {
  const c = camelize<Rec>(raw);
  if (isRec(c.sun) && isRec(c.earth) && isRec(c.footprint)) return c as unknown as Coverage; // contract shape
  // IMPLEMENTATION_PROMPT A3: {critical_threshold_deg, n_critical_h, covered_frac, uncovered_ridges:[ids]} (Sun-critical hours)
  const near = (layers ?? []).find((l) => l.role === 'near');
  const tgt = (x: unknown) => {
    const r = isRec(x) ? x : c;
    return { controllingHoursInside: numOr(r.coveredFrac, Number.NaN), criticalHoursInside: num(r.coveredFrac), unknownHours: numOr(r.unknownFrac, 0), hoursTotal: numOr(r.nCriticalH, 0), allHoursInside: num(r.allHoursCoveredFrac) };
  };
  const t = tgt(c.sun);
  return {
    method: String(c.method ?? 'share of Sun-critical hours whose controlling sample lies in the 5 m tile (A3)'),
    footprint: { dem: near?.name ?? 'near_5m', boundsGridM: (near as Rec | undefined)?.bounds_grid_m as Coverage['footprint']['boundsGridM'] },
    uncoveredRidges: Array.isArray(c.uncoveredRidges) ? (c.uncoveredRidges as string[]) : undefined,
    criticalMarginDeg: numOr(c.criticalThresholdDeg, 1.0),
    sun: t,
    earth: isRec(c.earth) ? tgt(c.earth) : { controllingHoursInside: Number.NaN, criticalHoursInside: null, unknownHours: 0, hoursTotal: 0 },
  };
}

export function normalizeCertainty(raw: unknown, certaintyHeight: unknown, requirements: unknown, note?: unknown): CertaintyCurve {
  const c = camelize<unknown>(raw);
  if (isRec(c) && Array.isArray(c.points)) return c as unknown as CertaintyCurve; // contract shape
  // A2: [{mast_m, metric, nominal, min, p10, median, p90, max, n_clones, pass:"k/N"}] + certainty_height_m per requirement
  const rows = (Array.isArray(c) ? c : []) as Rec[];
  const byMast = new Map<number, Rec[]>();
  for (const r of rows) {
    const m = num(r.mastM);
    if (m === null) continue;
    byMast.set(m, [...(byMast.get(m) ?? []), r]);
  }
  const pick = (rs: Rec[], metric: string) => rs.find((r) => String(r.metric ?? '').startsWith(metric));
  const passOf = (r: Rec | undefined) => {
    const p = typeof r?.pass === 'string' ? r.pass.split('/') : null;
    return p && p.length === 2 && Number.isFinite(Number(p[0])) && Number.isFinite(Number(p[1])) ? { k: Number(p[0]), n: Number(p[1]) } : null;
  };
  const points = [...byMast.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([mastM, rs]) => {
      const sun = pick(rs, 'sun') ?? rs[0];
      const both = pick(rs, 'both');
      const passBy: Record<string, { k: number; n: number }> = {};
      for (const r of rs) {
        const p = passOf(r);
        if (p && typeof r.metric === 'string') passBy[r.metric] = p;
      }
      const ks = Object.values(passBy);
      // a joint count exists only when there is one requirement, or every requirement passes on every model (then joint = N)
      const joint = ks.length === 1 ? ks[0].k : ks.length && ks.every((p) => p.k === p.n) ? ks[0].n : null;
      return {
        mastM,
        nominal: { sunPct: numOr(sun?.nominal, Number.NaN), bothPct: num(both?.nominal) ?? undefined },
        min: { sunPct: numOr(sun?.min, Number.NaN), bothPct: num(both?.min) ?? undefined },
        max: { sunPct: numOr(sun?.max, Number.NaN), bothPct: num(both?.max) ?? undefined },
        median: { sunPct: num(sun?.median) ?? undefined, bothPct: num(both?.median) ?? undefined },
        nModels: numOr(sun?.nClones, ks[0]?.n ?? 0),
        nPass: joint,
        passBy,
      };
    });
  const ch = isRec(certaintyHeight) ? (certaintyHeight as Rec) : null;
  const byReq: Record<string, number | null> = {};
  if (ch) for (const [k, v] of Object.entries(ch)) byReq[k.replace(/[A-Z]/g, (m) => `_${m.toLowerCase()}`)] = num(v);
  const vals = Object.values(byReq);
  const chNum = num(certaintyHeight);
  return {
    method: 'mast sweep across PGDA 78 clones (A2)',
    requirements: Array.isArray(requirements) ? (camelize<CertaintyCurve['requirements']>(requirements) as CertaintyCurve['requirements']) : undefined,
    realizations: points.length ? Array.from({ length: points[0].nModels }, (_, i) => `model ${i + 1}`) : [],
    points,
    // every requirement met by every tested map = the largest per-requirement height; any null means none in the sweep
    minTestedFeasibleMastM: chNum ?? (vals.length ? (vals.some((x) => x === null) ? null : Math.max(...(vals as number[]))) : null),
    agreementMastM: null,
    agreementToleranceP: Number.NaN,
    heightByRequirement: ch ? byReq : undefined,
    note: typeof note === 'string' ? note : undefined,
  };
}

/** A4: `margins` (viewer contract) or `margin_series` (a-science name). Per-sample clone min/max become the ribbon band. */
export function normalizeMargins(raw: unknown): MarginRange | undefined {
  const m = camelize<Rec>(raw);
  if (!isRec(m)) return undefined;
  if (isRec(m.sun) && Array.isArray((m.sun as Rec).minDeg)) return m as unknown as MarginRange; // contract shape
  const arr = (k: string) => (Array.isArray(m[k]) ? (m[k] as (number | null)[]) : null);
  const sMin = arr('sunCloneMinDeg') ?? arr('sunMinDeg');
  const sMax = arr('sunCloneMaxDeg') ?? arr('sunMaxDeg');
  const eMin = arr('earthCloneMinDeg') ?? arr('earthMinDeg');
  const eMax = arr('earthCloneMaxDeg') ?? arr('earthMaxDeg');
  if (!sMin || !sMax || !eMin || !eMax) return undefined;
  const n = num(m.nClones);
  return {
    realizations: Array.isArray(m.cloneIds) ? (m.cloneIds as string[]) : Array.from({ length: n ?? 0 }, (_, i) => `clone ${i + 1}`),
    scenarioId: typeof m.scenarioId === 'string' ? m.scenarioId : undefined,
    sun: { minDeg: sMin, maxDeg: sMax },
    earth: { minDeg: eMin, maxDeg: eMax },
    truncated: { sun: Array.isArray(m.sunTruncated) ? (m.sunTruncated as boolean[]) : undefined, earth: Array.isArray(m.earthTruncated) ? (m.earthTruncated as boolean[]) : undefined },
  };
}

/** Normalize every decision-evidence block of one derived object in place (POLARIS-X5D-v2 export, snake_case). */
export function normalizeDerivedBlocks(d: Record<string, unknown>, layers: RawScienceV2['skyline']['dem_layers'] = []): void {
  if (d.attribution) d.attribution = normalizeAttribution(d.attribution);
  if (d.certainty_curve) d.certaintyCurve = normalizeCertainty(d.certainty_curve, d.certainty_height_m, d.requirements, d.certainty_note);
  if (d.coverage && !(isRec(d.coverage) && isRec((d.coverage as Rec).sun))) d.coverage = normalizeCoverage(d.coverage, layers);
  const mr = d.margin_range ?? d.margins ?? d.margin_series;
  if (mr && !d.marginRange) d.marginRange = normalizeMargins(mr);
}

export function isScienceV2(raw: unknown): raw is RawScienceV2 {
  const s = !!raw && typeof raw === 'object' ? (raw as { schema?: unknown }).schema : undefined;
  return s === 'science-bundle-v2' || s === 'polaris-science-results-v1';
}

export function adaptScienceV2(r: RawScienceV2): Bundle {
  if (!r.skyline || !Array.isArray(r.skyline.azimuth_deg) || r.skyline.azimuth_deg.length !== r.skyline.bins) fail('skyline.azimuth_deg length != bins');
  if (r.skyline.elevation_deg.length !== r.skyline.bins || r.skyline.status.length !== r.skyline.bins) fail('skyline arrays have inconsistent lengths');
  if (!Array.isArray(r.samples) || r.samples.length < 2) fail('needs at least 2 samples');
  if (!r.fixture && r.samples.length !== r.time.n_samples) fail(`samples (${r.samples.length}) != time.n_samples (${r.time.n_samples})`);
  const binDeg = 360 / r.skyline.bins;
  const status = rawStatus(r.validation_status.overall);
  const gates: Gate[] = r.validation_status.checks.map((c) => ({ gate: c.id, status: c.status.toUpperCase().replace('-', '_'), evidence: c.evidence }));
  const skyline: NonNullable<Scenario['skyline']> = {
    azimuthDeg: r.skyline.azimuth_deg,
    elevationDeg: r.skyline.elevation_deg,
    reachM: r.skyline.valid_reach_m,
    coverage: r.skyline.status,
    rangeLimited: r.skyline.range_limited,
    critical: r.skyline.critical,
  };
  const events: BundleEvent[] = (r.events ?? []).map((e) => ({
    body: e.body,
    kind: e.kind,
    event: e.event,
    direction: e.direction,
    utc: e.utc,
    bracketWidthS: e.bracket_width_s,
    horizonFlag: e.horizon_flag,
  }));
  const baseline: Scenario = {
    id: 'baseline',
    label: `Baseline · mast ${r.site.observer_mast_m ?? '?'} m (full time series)`,
    kind: 'baseline',
    family: 'baseline',
    observer: { xM: r.site.grid_x_m ?? 0, yM: r.site.grid_y_m ?? 0, groundM: r.site.height_m ?? 0, mastM: r.site.observer_mast_m ?? 0, lat: r.site.lat_deg, lon: r.site.lon_deg_east },
    skyline,
    samples: {
      sun: series(r.samples, 'sun', r.skyline.critical, binDeg),
      earth: series(r.samples, 'earth', r.skyline.critical, binDeg),
      both: { visible: r.samples.map((s) => !!s.sun.center_visible && !!s.earth.center_visible) },
    },
    metrics: metricList(r.metrics),
    failures: [],
    events,
  };
  const others: Scenario[] = (r.scenarios ?? []).map((x) => ({
    id: x.id,
    label: scenarioLabel(x),
    kind: x.family,
    family: x.family,
    parameters: x.parameters,
    description: x.method,
    observer: x.site_lat_deg !== undefined ? { xM: Number.NaN, yM: Number.NaN, groundM: x.site_height_m ?? Number.NaN, mastM: Number((x.parameters ?? {}).mast_m ?? r.site.observer_mast_m ?? Number.NaN), lat: x.site_lat_deg, lon: x.site_lon_deg_east } : undefined,
    metrics: metricList(x.metrics, x.delta_vs_baseline),
    failures: [],
    skylineSummary: x.skyline_summary,
    events: (x.events ?? []).map((e) => ({ body: e.body, event: e.event, utc: e.utc })),
  }));

  const ds: Dataset = {
    siteId: r.site.id,
    site: {
      id: r.site.id,
      name: r.site.name,
      latitudePlanetocentricDeg: r.site.lat_deg,
      longitudeEastDeg: r.site.lon_deg_east,
      projectedMeters: { x: r.site.grid_x_m ?? Number.NaN, y: r.site.grid_y_m ?? Number.NaN },
      coordinateRole: r.site.coordinates_source,
    },
    ephemeris: {
      kind: 'jpl-horizons-observer-ephemeris',
      source: 'NASA/JPL Horizons API',
      frame: String(r.frame?.body_fixed_frame ?? 'see bundle frame'),
      longitudeConvention: String(r.frame?.longitude ?? 'east-positive'),
      azimuthConvention: String(r.frame?.azimuth ?? 'clockwise from local north'),
      angleType: 'airless apparent target-centre az/el',
      timeScale: 'UTC',
      sampling: r.fixture ? `subset of ${r.fixture.of_bundle} (irregular step)` : `${r.time.step_h ?? '?'} h`,
      records: (r.provenance?.horizons_raw ?? []).map((h) => ({ target: h.role ?? 'horizons', rawFile: h.path, sha256: h.sha256 })),
      samples: r.samples.map((s) => ({ time: s.utc, sun: { az: s.sun.az_deg, el: s.sun.el_deg }, earth: { az: s.earth.az_deg, el: s.earth.el_deg } })),
    },
    validation: { status, gates },
    derived: {
      producer: { name: r.generator?.code ?? 'science/', version: r.generator?.git_commit?.slice(0, 7) ?? '?' },
      status,
      skylineBinDeg: binDeg,
      scenarios: [baseline, ...others],
      ...((r.derived?.attribution ?? r.attribution) ? { attribution: normalizeAttribution(r.derived?.attribution ?? r.attribution) } : {}),
      ...((r.derived?.coverage ?? r.coverage) ? { coverage: normalizeCoverage(r.derived?.coverage ?? r.coverage, r.skyline.dem_layers ?? []) } : {}),
      ...((r.derived?.certainty_curve ?? r.certainty_curve) ? { certaintyCurve: normalizeCertainty(r.derived?.certainty_curve ?? r.certainty_curve, r.derived?.certainty_height_m ?? r.certainty_height_m, r.derived?.requirements ?? r.requirements, r.derived?.certainty_note) } : {}),
      ...((r.derived?.margin_range ?? r.derived?.margins ?? r.derived?.margin_series ?? r.margin_range) ? { marginRange: normalizeMargins(r.derived?.margin_range ?? r.derived?.margins ?? r.derived?.margin_series ?? r.margin_range) } : {}),
      ...(typeof r.near_zero_margin_deg === 'number' ? { nearZeroMarginDeg: r.near_zero_margin_deg } : {}),
      arrivalSlip: r.derived?.arrival_slip,
      hotspots: r.derived?.hotspots,
      flipForecast: r.derived?.flip_forecast,
    },
    events,
    snapToSamples: true,
    sourceLayers: (r.skyline.dem_layers ?? []).map((l) => ({ name: l.name, role: l.role, stepM: l.step_m, url: l.source_url, sha256: l.file_sha256, arraySha256: l.array_sha256 })),
    limitations: r.limitations,
  };
  return {
    format: r.schema,
    bundleId: r.bundle_id,
    schemaVersion: '2',
    generatedUTC: r.generated_utc,
    producer: { name: r.generator?.code ?? 'science/', version: r.generator?.git_commit?.slice(0, 7) ?? '?' },
    validation: { status, reason: `${r.schema} ${r.bundle_id}${r.fixture ? ` (UI fixture: ${r.fixture.note ?? ''})` : ''}`, gates: [] },
    sources: Object.fromEntries((r.provenance?.sources ?? []).map((s) => [s.id, s.url ?? s.description ?? ''])),
    contract: { azimuth: r.frame?.azimuth, note: 'docs/SCIENTIFIC_CONTRACT.md (a-science)' },
    datasets: [ds],
  };
}
