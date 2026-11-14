/**
 * TypeScript view of POLARIS-X5D-v2 ("science-bundle-v2").
 *
 * Sources of truth, in order:
 *   1. docs/SCIENTIFIC_CONTRACT.md
 *   2. schemas/science-bundle-v2.schema.json
 *   3. web/docs/VIEWER_BUNDLE_CONTRACT.md — the additive `derived` block the viewer
 *      needs from the science branch (skyline, per-sample margins, metrics, failures).
 *
 * The viewer only READS these values. It never computes a skyline, a visibility
 * flag, a margin or a metric. When `derived` is absent it says so on screen.
 */

export type RawStatus = 'DEMO_ONLY' | 'SOURCE_BASED_UNVALIDATED' | 'VALIDATED_NASA_JPL';
export type DisplayStatus = 'DEMO' | 'SOURCE-BASED UNVALIDATED' | 'VALIDATED';

export interface Gate {
  gate: string;
  status: string;
  evidence?: string;
  [k: string]: unknown;
}

export interface Dem {
  kind: string; // 'nasa' | 'demo'
  layer?: string;
  siteId?: string;
  n: number;
  spacing: number;
  originX: number;
  originY: number;
  values: number[]; // n*n, rows south-to-north
  source: string;
  sourceSha256?: string | null;
  cropValuesSha256?: string;
  verticalUnits: 'meters';
  frame: string;
  crsConvention?: string;
  rowOrder: string;
  validCoverageRadiusM?: number;
}

export interface AzEl {
  az: number; // deg clockwise from local north
  el: number; // deg above local horizontal
}

export interface EphemerisSample {
  time: string; // UTC ISO-8601
  sun: AzEl;
  earth: AzEl;
}

export interface EphemerisRecord {
  target: string;
  command?: string;
  queryUrl?: string;
  sha256?: string;
  rawFile?: string;
  [k: string]: unknown;
}

export interface Ephemeris {
  kind: string;
  source: string;
  sourceUrl?: string;
  frame: string;
  longitudeConvention: string;
  azimuthConvention: string;
  angleType?: string;
  timeScale: 'UTC';
  sampling?: string;
  records: EphemerisRecord[];
  samples: EphemerisSample[];
}

export interface Site {
  id: string;
  name: string;
  code?: string;
  latitudePlanetocentricDeg: number;
  longitudeEastDeg: number;
  projectedMeters: { x: number; y: number };
  coordinateRole?: string;
}

/* ---------- additive `derived` block (science branch output) ---------- */

export interface TargetSeries {
  visible: boolean[];
  horizonElDeg: number[];
  marginDeg: number[];
  /** distance to the terrain that blocks the ray; null when clear */
  firstHitM: (number | null)[];
  /** what firstHitM means for this bundle */
  firstHitKind?: 'first-hit' | 'horizon-setting-cell';
  /** visible share of the target disk 0..1 (science-bundle-v2 only) */
  diskFraction?: number[];
  horizonFlag?: string[];
}

/** One skyline bin's horizon-setting terrain sample (science-bundle-v2 `skyline.critical[i]`). */
export interface CriticalCell {
  distance_m: number | null;
  lat_deg?: number | null;
  lon_deg?: number | null;
  grid_x_m?: number | null;
  grid_y_m?: number | null;
  height_m?: number | null;
  dem?: string | null;
}

/** A refined crossing event from the bundle (bisection-refined; between hourly samples). */
export interface BundleEvent {
  body: 'sun' | 'earth';
  kind?: string;
  event: string;
  direction?: string;
  utc: string;
  bracketWidthS?: number;
  horizonFlag?: string;
}

export interface Metric {
  id: string;
  label: string;
  value: number;
  unit: string;
  constraint?: { op: '<=' | '>='; threshold: number };
  marginToLimit?: number;
  pass?: boolean;
  /** scenario value minus baseline value, as given by the bundle */
  delta?: number;
}

export interface Failure {
  id: string;
  target: 'sun' | 'earth';
  sampleIndex: number;
  time: string;
  azimuthDeg: number;
  targetElDeg: number;
  horizonElDeg: number;
  marginDeg: number;
  blockedSamples?: number;
  firstHit: { distanceM: number; xM: number; yM: number; heightM: number; cell: [number, number] } | null;
  profile: { distanceM: number[]; terrainM: number[]; rayM: number[] };
}

export interface Scenario {
  id: string;
  label: string;
  kind: string;
  family?: string;
  parameters?: Record<string, unknown>;
  description?: string;
  observer?: { xM: number; yM: number; groundM: number; mastM: number; lat?: number; lon?: number };
  /** elevation null = no terrain samples in that bin (never filled in) */
  skyline?: {
    azimuthDeg: number[];
    elevationDeg: (number | null)[];
    reachM?: number[];
    coverage?: string[];
    rangeLimited?: boolean[];
    critical?: CriticalCell[];
  };
  /** absent = this scenario carries metrics only (no per-sample series) */
  samples?: { sun: TargetSeries; earth: TargetSeries; both: { visible: boolean[] } };
  metrics: Metric[];
  failures: Failure[];
  skylineSummary?: { min_deg?: number; max_deg?: number; n_truncated?: number; n_range_limited?: number };
  events?: BundleEvent[];
}

export interface Derived {
  producer: { name: string; version: string };
  status: RawStatus;
  frame?: { localNorthInGrid?: [number, number]; localEastInGrid?: [number, number]; note?: string };
  skylineBinDeg?: number;
  scenarios: Scenario[];
}

/* ---------- top level ---------- */

export interface Dataset {
  siteId: string;
  site: Site;
  /** absent for science-bundle-v2 (Person A): no DEM grid is shipped, only the skyline */
  dem?: Dem;
  localDem?: Dem | null;
  uncertainty?: { classification?: string; totalZRms?: Dem; clones?: { id: string; dem: Dem }[] };
  ephemeris: Ephemeris;
  validation: { status: RawStatus; gates: Gate[] };
  derived?: Derived;
  /** refined crossing events (science-bundle-v2) */
  events?: BundleEvent[];
  /** contract rule: the time slider snaps to sample times; no interpolation between samples */
  snapToSamples?: boolean;
  /** source layers used by the science pipeline (for provenance display) */
  sourceLayers?: { name: string; role?: string; stepM?: number; url?: string; sha256?: string; arraySha256?: string }[];
  limitations?: string[];
}

export interface Bundle {
  /** POLARIS-X5D-v2 = Codex source cases; science-bundle-v2 = Person A (a-science), adapted on load */
  format: 'POLARIS-X5D-v2' | 'science-bundle-v2';
  bundleId?: string;
  schemaVersion: string;
  generatedUTC: string;
  demo?: boolean;
  producer?: { name: string; version: string };
  validation: { status: RawStatus; reason?: string; gates: Gate[] };
  sources?: Record<string, string>;
  contract: Record<string, unknown>;
  datasets: Dataset[];
}

export interface BundleIndexEntry {
  file: string;
  origin: string;
  status: string;
  label: string;
  sha256: string;
  bytes: number;
}

/** A bundle as the viewer holds it: parsed JSON + provenance of the bytes. */
export interface LoadedBundle {
  name: string;
  origin: string;
  sha256: string;
  bytes: number;
  bundle: Bundle;
  times: number[][]; // per dataset: epoch ms of each ephemeris sample
  status: DisplayStatus;
  warnings: string[];
}
