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
import type { Bundle, BundleEvent, CriticalCell, Dataset, Gate, Metric, RawStatus, Scenario, TargetSeries } from './types';
import { BundleError } from './errors';

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
  schema: 'science-bundle-v2';
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

function metricList(m: Record<string, unknown>, delta?: Record<string, number>): Metric[] {
  return METRICS.filter((d) => typeof m[d.key] === 'number').map((d) => ({
    id: d.key,
    label: d.label,
    value: m[d.key] as number,
    unit: d.unit,
    ...(delta && typeof delta[d.key] === 'number' ? { delta: delta[d.key] } : {}),
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

export function isScienceV2(raw: unknown): raw is RawScienceV2 {
  return !!raw && typeof raw === 'object' && (raw as { schema?: unknown }).schema === 'science-bundle-v2';
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
    },
    events,
    snapToSamples: true,
    sourceLayers: (r.skyline.dem_layers ?? []).map((l) => ({ name: l.name, role: l.role, stepM: l.step_m, url: l.source_url, sha256: l.file_sha256, arraySha256: l.array_sha256 })),
    limitations: r.limitations,
  };
  return {
    format: 'science-bundle-v2',
    bundleId: r.bundle_id,
    schemaVersion: '2',
    generatedUTC: r.generated_utc,
    producer: { name: r.generator?.code ?? 'science/', version: r.generator?.git_commit?.slice(0, 7) ?? '?' },
    validation: { status, reason: `science-bundle-v2 ${r.bundle_id}${r.fixture ? ` (UI fixture: ${r.fixture.note ?? ''})` : ''}`, gates: [] },
    sources: Object.fromEntries((r.provenance?.sources ?? []).map((s) => [s.id, s.url ?? s.description ?? ''])),
    contract: { azimuth: r.frame?.azimuth, note: 'docs/SCIENTIFIC_CONTRACT.md (a-science)' },
    datasets: [ds],
  };
}
