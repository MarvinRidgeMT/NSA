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
  /** where the constraint came from when the bundle did not declare it (e.g. the team requirement) */
  constraintSource?: string;
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
  /** position-offset scenarios: JPL samples for THIS observer point (same UTC times as the dataset); replaces the
   * dataset ephemeris while this scenario drives the view */
  ephemeris?: { note?: string; records?: { target: string; rawFile: string; sha256: string }[]; samples: EphemerisSample[] };
  /** local-ENU basis at this scenario's observer point (position offsets) */
  frame?: { localNorthInGrid?: [number, number]; localEastInGrid?: [number, number]; note?: string };
  sourceBundle?: { file: string; sha256: string };
}

/* ---------- decision-evidence fields (additive; emitted by the science branch, read here) ----------
 * See web/docs/VIEWER_BUNDLE_CONTRACT.md §"Decision-evidence fields". All optional: when absent the
 * panels say "not in bundle" and fall back to what the bundle does carry (per-bin critical cells,
 * per-sample margins, mast scenarios). The viewer never computes any of these. */

/** Ridge of Record: one controlling terrain feature (a cluster of horizon-setting cells). */
export interface Ridge {
  id: string;
  label?: string;
  /** azimuth span of the skyline bins this ridge controls, deg clockwise from local north */
  azimuthDeg: [number, number];
  distanceM: { min: number; max: number } | number;
  heightM?: { min: number; max: number } | number;
  horizonElDeg?: { min: number; max: number } | number;
  /** representative cell (e.g. the one controlling the most hours) */
  cell?: CriticalCell & { index?: [number, number] };
  dem?: string;
  resolutionM?: number;
  elevationSigmaM?: number | null;
  /** angular gap to the runner-up obstruction in the same bins, deg (null = not computed) */
  runnerUpGapDeg?: number | null;
  /** per target: hours this ridge sets the horizon in the target's direction, and hours of visibility lost to it */
  hours: Record<'sun' | 'earth', { controlled: number; lost: number; intervals?: [string, string][] }>;
  /** science/attribution.py: the ridge caused at least one Sun or Earth loss sample */
  ofRecord?: boolean;
  reliefM?: number;
  maxElevDeg?: number;
}

export interface Attribution {
  label?: string;
  /** scenario whose skyline this attribution describes (export: scenarioId; default = baseline) */
  scenarioId?: string;
  method: string;
  methodDetail?: Record<string, string>;
  /** per skyline bin: index into ridges[] (null = cluster that never held Sun/Earth), controlling distance, runner-up gap, source layer */
  perBin?: { ridgeIdx: (number | null)[]; ctrlDistM?: (number | null)[]; gapDeg?: (number | null)[]; source?: (string | null)[] };
  clusteringNote?: string;
  ridges: Ridge[];
}

/** Coverage Gauge: how much of the controlling terrain the uncertainty models (clones) cover. */
export interface CoverageTarget {
  /** fraction 0..1 of controlling-cell-hours whose cell lies inside the clone footprint */
  controllingHoursInside: number;
  /** same, restricted to near-zero-margin samples (|margin| < criticalMarginDeg) */
  criticalHoursInside: number | null;
  /** fraction of controlling-cell-hours in truncated/range-limited bins (horizon unknown beyond reach) */
  unknownHours: number;
  hoursTotal: number;
  /** bundle all_hours_covered_frac (0..1): same near-tile test over every hourly sample; copied, never computed here */
  allHoursInside?: number | null;
}

export interface Coverage {
  method: string;
  footprint: { dem: string; boundsGridM?: [number, number, number, number]; cloneIds?: string[] };
  criticalMarginDeg: number;
  sun: CoverageTarget;
  earth: CoverageTarget;
  /** ridge ids (from attribution) whose controlling terrain lies outside the clone footprint */
  uncoveredRidges?: string[];
}

/** Certainty Height: a mast-height sweep across terrain realizations. */
export interface CertaintyPoint {
  mastM: number;
  nominal: { sunPct: number; earthPct?: number; bothPct?: number; longestSunGapH?: number; longestEarthGapH?: number };
  min: { sunPct: number; bothPct?: number };
  max: { sunPct: number; bothPct?: number };
  nModels: number;
  /** joint pass count over every requirement; null unless the bundle states it (marginal counts are never combined) */
  nPass: number | null;
  /** per-requirement pass counts exactly as the bundle states them ("k/N") */
  passBy?: Record<string, { k: number; n: number }>;
  median?: { sunPct?: number; bothPct?: number };
  /** worst requirement margin across models (unit per requirement), null when no requirements declared */
  worstMargins?: Record<string, number> | null;
  coverageInside?: number | null;
}

export interface CertaintyCurve {
  method: string;
  rayStepM?: number;
  requirements?: { id: string; label: string; op: '<=' | '>='; threshold: number; unit: string }[];
  realizations: string[];
  points: CertaintyPoint[];
  /** smallest sampled mast at which every realization meets the requirements (null = none in sweep) */
  minTestedFeasibleMastM: number | null;
  /** smallest sampled mast at which max-min spread of sunPct <= agreementToleranceP */
  agreementMastM: number | null;
  agreementToleranceP: number;
  /** per requirement: smallest tested mast at which every realization passes it (bundle), null = none in sweep */
  heightByRequirement?: Record<string, number | null>;
  note?: string;
}

/** Margin Ribbon range across realizations (per sample), when the bundle provides it. */
export interface MarginRange {
  realizations: string[];
  scenarioId?: string;
  truncated?: { sun?: boolean[]; earth?: boolean[] };
  sun: { minDeg: (number | null)[]; maxDeg: (number | null)[] };
  earth: { minDeg: (number | null)[]; maxDeg: (number | null)[] };
}

export interface ArrivalSlipPoint {
  result_id: string;
  label: 'PILOT';
  slip_h: number;
  window_start_utc: string;
  window_stop_utc: string;
  sample_count: number;
  nominal: {
    sun_center_visible_pct: number;
    sun_and_earth_center_visible_pct: number;
    sun_pass: boolean;
    sun_and_earth_pass: boolean;
    joint_pass: boolean;
  };
  clones: {
    count: number;
    sun_center_visible_pct_min: number;
    sun_center_visible_pct_max: number;
    sun_and_earth_center_visible_pct_min: number;
    sun_and_earth_center_visible_pct_max: number;
    sun_pass_count: number;
    sun_and_earth_pass_count: number;
    joint_pass_count: number;
    pass_denominator: number;
    joint_pass_pct: number;
    pass_band: 'all' | 'dropped';
  };
}

export interface ArrivalSlipBlock {
  result_id: string;
  label: 'PILOT';
  validation_status: 'SOURCE-BASED UNVALIDATED';
  site_id: string;
  input_bundle_id: string;
  observer_mast_m: number;
  thresholds: {
    sun_center_visible_pct_min: number;
    sun_and_earth_center_visible_pct_min: number;
    joint_rule: string;
  };
  slip_hours: number[];
  points: ArrivalSlipPoint[];
  method: {
    mission_window: string;
    visibility_percentage: string;
    terrain: string;
    ephemeris: string;
    uncertainty: string;
    limitation: string;
  };
}

export interface HotspotTile {
  result_id: string;
  label: 'PILOT';
  rank: number;
  tile_id: string;
  lat_deg: number;
  lon_deg_east: number;
  grid_x_m: number;
  grid_y_m: number;
  distance_m_min: number;
  distance_m_max: number;
  controlled_bins: number;
  controlled_bin_indices: number[];
  clone_height_variance_m2_max: number;
  clone_relative_height_variance_m2_max: number;
  horizon_variance_deg2_max: number;
  sun_score: number;
  earth_score: number;
  sun_critical_h: number;
  earth_critical_h: number;
  score: number;
  display_band: 'positive' | 'zero';
  method: string;
}

export interface HotspotsBlock {
  result_id: string;
  label: 'PILOT';
  validation_status: 'SOURCE-BASED UNVALIDATED';
  site_id: string;
  input_bundle_id: string;
  observer_mast_m: number;
  clone_count: number;
  tile_step_m: number;
  horizon_distance_m: number;
  critical_margin_deg: number;
  score_unit: string;
  tiles_evaluated: number;
  tiles_positive: number;
  zero_state_caption: string | null;
  top_k: number;
  top_tiles: HotspotTile[];
  tiles: HotspotTile[];
  method: {
    id: string;
    caption: string;
    candidate: string;
    dispersion: string;
    jacobian: string;
    score: string;
    coverage: string;
    limitation: string;
  };
}

export interface FlipForecastRow {
  result_id: string;
  label: 'PILOT';
  row_id: string;
  scope: string;
  case_count: number;
  predicted_flips: number;
  actual_flips: number;
  true_positive: number;
  false_positive: number;
  false_negative: number;
  true_negative: number;
  precision: number | null;
  recall: number | null;
  precision_display: string;
  recall_display: string;
  note: string;
}

export interface FlipForecastBlock {
  result_id: string;
  label: 'PILOT';
  validation_status: 'SOURCE-BASED UNVALIDATED';
  site_id: string;
  input_bundle_id: string;
  observer_mast_m: number;
  clone_count: number;
  sample_count: number;
  thresholds: {
    sun_center_visible_pct_min: number;
    sun_and_earth_center_visible_pct_min: number;
    source_result_id: string;
  };
  nominal: {
    sun_center_visible_pct: number;
    sun_and_earth_center_visible_pct: number;
    mission_pass: boolean;
  };
  ridge_ids_considered: string[];
  forecast_vs_actual: FlipForecastRow[];
  per_clone: unknown[];
  method: {
    id: string;
    caption: string;
    forecast: string;
    actual: string;
    hourly_flip: string;
    mission_flip: string;
    metrics: string;
    limitation: string;
  };
}

export interface Derived {
  producer: { name: string; version: string };
  status: RawStatus;
  /** decision-evidence outputs (optional, additive) */
  attribution?: Attribution;
  coverage?: Coverage;
  certaintyCurve?: CertaintyCurve;
  marginRange?: MarginRange;
  /** display threshold below which |margin| is called "near zero" (deg); from the bundle when given */
  nearZeroMarginDeg?: number;
  frame?: { localNorthInGrid?: [number, number]; localEastInGrid?: [number, number]; note?: string };
  skylineBinDeg?: number;
  scenarios: Scenario[];
  /** PILOT block computed by science/stretch/arrival_slip.py; display-only in the browser. */
  arrivalSlip?: ArrivalSlipBlock;
  /** PILOT block computed by science/stretch/hotspots.py; display-only in the browser. */
  hotspots?: HotspotsBlock;
  /** PILOT block computed by science/stretch/flip_forecast.py; display-only in the browser. */
  flipForecast?: FlipForecastBlock;
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
  format: 'POLARIS-X5D-v2' | 'science-bundle-v2' | 'polaris-science-results-v1';
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
