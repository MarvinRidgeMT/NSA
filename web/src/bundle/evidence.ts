/**
 * Decision-evidence helpers. Pure bookkeeping over values the bundle already carries:
 * nothing here samples terrain, computes a skyline, a margin or a visibility flag.
 *
 *   - binForAzimuth: the skyline bin NEAREST a target azimuth (bins are centred; same rule as the science branch)
 *   - controllingCells: for every blocked sample, the bundle's critical cell of the target's bin,
 *     tallied per cell (a display tally of bundle samples, NOT a solver "hours controlled" metric —
 *     that comes from derived.attribution when the science branch emits it)
 *   - marginFlagMismatches: samples where sign(margin) disagrees with the visible flag (consistency check)
 */
import type { Attribution, CriticalCell, EphemerisSample, Ridge, Scenario, TargetSeries } from './types';

/**
 * Skyline bins are CENTRED on i·(360/n)° (the science branch casts one ray per bin centre and attributes a body to the
 * NEAREST bin: science/attribution.py method.hours). Rounding down instead put 4 of 75 Earth-loss hours on the wrong ridge
 * at Site04 ROI3 (found 14 Nov 14:10 EST); nearest reproduces the bundle's per-ridge hours exactly (unit-tested).
 */
export function binForAzimuth(az: number, nBins: number): number {
  const a = ((az % 360) + 360) % 360;
  return Math.round((a / 360) * nBins) % nBins;
}

export interface CellTally {
  key: string;
  cell: CriticalCell;
  /** skyline bins (indices) in which this cell set the horizon for a blocked sample */
  bins: number[];
  azimuthDeg: [number, number];
  /** sample indices where the target was blocked with this cell as the critical cell */
  samples: number[];
  firstIndex: number;
  /** flat sum of sample spacings (h) over the tallied samples; honest only for regular sampling */
  sampledHours: number;
  coverage: string[];
}

export interface Controlling {
  target: 'sun' | 'earth';
  nBlocked: number;
  nBlockedWithoutCell: number;
  cells: CellTally[];
}

function cellKey(c: CriticalCell): string {
  return `${c.dem ?? '?'}|${c.grid_x_m ?? '?'}|${c.grid_y_m ?? '?'}`;
}

export function controllingCells(
  samples: EphemerisSample[],
  series: TargetSeries,
  skyline: NonNullable<Scenario['skyline']>,
  target: 'sun' | 'earth',
  times: number[],
): Controlling {
  const n = skyline.azimuthDeg.length;
  const byKey = new Map<string, CellTally>();
  let nBlocked = 0;
  let nBlockedWithoutCell = 0;
  for (let i = 0; i < samples.length; i++) {
    if (series.visible[i] !== false) continue;
    nBlocked++;
    const bin = binForAzimuth(samples[i][target].az, n);
    const cell = skyline.critical?.[bin];
    if (!cell || cell.distance_m === null || cell.distance_m === undefined) {
      nBlockedWithoutCell++;
      continue;
    }
    const key = cellKey(cell);
    let t = byKey.get(key);
    if (!t) {
      t = { key, cell, bins: [], azimuthDeg: [skyline.azimuthDeg[bin], skyline.azimuthDeg[bin]], samples: [], firstIndex: i, sampledHours: 0, coverage: [] };
      byKey.set(key, t);
    }
    if (!t.bins.includes(bin)) {
      t.bins.push(bin);
      t.azimuthDeg = [Math.min(t.azimuthDeg[0], skyline.azimuthDeg[bin]), Math.max(t.azimuthDeg[1], skyline.azimuthDeg[bin])];
      const cov = skyline.coverage?.[bin];
      if (cov && !t.coverage.includes(cov)) t.coverage.push(cov);
    }
    t.samples.push(i);
    const dt = i + 1 < times.length ? times[i + 1] - times[i] : i > 0 ? times[i] - times[i - 1] : 0;
    t.sampledHours += dt / 3.6e6;
  }
  const cells = [...byKey.values()].sort((a, b) => b.samples.length - a.samples.length || a.firstIndex - b.firstIndex);
  return { target, nBlocked, nBlockedWithoutCell, cells };
}

/** Indices where the bundle's own margin sign and visible flag disagree (margin exactly 0 or non-finite is skipped). */
export function marginFlagMismatches(series: TargetSeries): number[] {
  const out: number[] = [];
  for (let i = 0; i < series.visible.length; i++) {
    const m = series.marginDeg[i];
    if (!Number.isFinite(m) || m === 0) continue;
    if (m > 0 !== series.visible[i]) out.push(i);
  }
  return out;
}

/** Scenarios that vary only the mast height, sorted by mast (fallback when derived.certaintyCurve is absent). */
export function mastScenarios(scenarios: Scenario[]): { mastM: number; scenario: Scenario }[] {
  const out: { mastM: number; scenario: Scenario }[] = [];
  for (const s of scenarios) {
    const p = s.parameters ?? {};
    const m = p.mast_m ?? p.mastM ?? (s.observer && s.family === 'mast-height' ? s.observer.mastM : undefined);
    if (typeof m === 'number' && Number.isFinite(m) && Object.keys(p).every((k) => /mast/i.test(k))) out.push({ mastM: m, scenario: s });
  }
  return out.sort((a, b) => a.mastM - b.mastM);
}

/** A run of adjacent skyline bins whose critical cells share a DEM layer: one terrain feature for display. */
export interface CellGroup {
  id: string;
  dem: string | null;
  cells: CellTally[];
  bins: number[];
  azimuthDeg: [number, number];
  distanceM: { min: number; max: number };
  heightM: { min: number; max: number } | null;
  samples: number;
  sampledHours: number;
  firstIndex: number;
  truncated: boolean;
}

/**
 * Group cell tallies into contiguous azimuth runs (bins at most `gapBins` apart, same DEM layer).
 * Display grouping only: it merges rows of the table; it does not decide what a ridge is scientifically
 * (that is derived.attribution's job) and it changes no number — totals are sums of the member tallies.
 */
export function groupAdjacentCells(cells: CellTally[], nBins: number, gapBins = 2): CellGroup[] {
  const byBin = new Map<number, CellTally>();
  for (const c of cells) for (const b of c.bins) if (!byBin.has(b)) byBin.set(b, c);
  const bins = [...byBin.keys()].sort((a, b) => a - b);
  const groups: CellGroup[] = [];
  let cur: CellGroup | null = null;
  const push = (g: CellGroup) => groups.push(g);
  for (const b of bins) {
    const c = byBin.get(b)!;
    const dem = c.cell.dem ?? null;
    const joins = cur && dem === cur.dem && b - cur.bins[cur.bins.length - 1] <= gapBins;
    if (!joins) {
      if (cur) push(cur);
      cur = { id: `g${b}`, dem, cells: [], bins: [], azimuthDeg: [(b / nBins) * 360, (b / nBins) * 360], distanceM: { min: Infinity, max: -Infinity }, heightM: null, samples: 0, sampledHours: 0, firstIndex: Infinity, truncated: false };
    }
    const g = cur!;
    g.bins.push(b);
    g.azimuthDeg = [g.azimuthDeg[0], (b / nBins) * 360];
    if (!g.cells.includes(c)) {
      g.cells.push(c);
      g.samples += c.samples.length;
      g.sampledHours += c.sampledHours;
      g.firstIndex = Math.min(g.firstIndex, c.firstIndex);
      const d = c.cell.distance_m;
      if (d != null) g.distanceM = { min: Math.min(g.distanceM.min, d), max: Math.max(g.distanceM.max, d) };
      const h = c.cell.height_m;
      if (h != null) g.heightM = g.heightM ? { min: Math.min(g.heightM.min, h), max: Math.max(g.heightM.max, h) } : { min: h, max: h };
      if (c.coverage.includes('truncated')) g.truncated = true;
    }
  }
  if (cur) push(cur);
  // wrap-around: a run ending at the last bin joins one starting at bin 0
  if (groups.length > 1) {
    const first = groups[0];
    const last = groups[groups.length - 1];
    if (first.dem === last.dem && first.bins[0] + nBins - last.bins[last.bins.length - 1] <= gapBins) {
      for (const c of first.cells) if (!last.cells.includes(c)) { last.cells.push(c); last.samples += c.samples.length; last.sampledHours += c.sampledHours; last.firstIndex = Math.min(last.firstIndex, c.firstIndex); }
      last.bins.push(...first.bins);
      last.distanceM = { min: Math.min(last.distanceM.min, first.distanceM.min), max: Math.max(last.distanceM.max, first.distanceM.max) };
      if (first.heightM) last.heightM = last.heightM ? { min: Math.min(last.heightM.min, first.heightM.min), max: Math.max(last.heightM.max, first.heightM.max) } : first.heightM;
      last.truncated ||= first.truncated;
      groups.shift();
    }
  }
  return groups.sort((a, b) => b.samples - a.samples || a.firstIndex - b.firstIndex);
}

/* ---------- Ridge of Record lookups over derived.attribution (bundle values only) ---------- */

/** Index into attribution.ridges of the ridge that owns a skyline bin (null = none / not attributed). */
export function ridgeIndexAtBin(att: Attribution | null | undefined, bin: number | null): number | null {
  if (!att?.perBin || bin === null) return null;
  const r = att.perBin.ridgeIdx[bin];
  return r === null || r === undefined ? null : r;
}

/** All skyline bins the bundle assigns to one ridge, ascending. */
export function ridgeBins(att: Attribution | null | undefined, ridgeIdx: number | null): number[] {
  if (!att?.perBin || ridgeIdx === null) return [];
  const out: number[] = [];
  att.perBin.ridgeIdx.forEach((x, b) => x === ridgeIdx && out.push(b));
  return out;
}

export interface RidgeNow {
  ridge: Ridge;
  ridgeIdx: number;
  bin: number;
  /** bundle per-bin controlling distance at this azimuth (m), when given */
  ctrlDistM: number | null;
  gapDeg: number | null;
  /** contiguous run of bundle samples around `sample` in which this target is blocked and its bin belongs to this ridge */
  run: { i0: number; i1: number } | null;
}

/**
 * The ridge the bundle holds responsible for a target at one sample: nearest bin -> per_bin.ridge_idx. `run` is the
 * stretch of consecutive blocked samples attributed to the same ridge (sample flags and azimuths are the bundle's).
 */
export function ridgeForTarget(att: Attribution | null | undefined, samples: EphemerisSample[], series: TargetSeries | undefined, target: 'sun' | 'earth', sample: number, nBins: number): RidgeNow | null {
  if (!att?.perBin || !nBins || !samples[sample]) return null;
  const binAt = (i: number) => binForAzimuth(samples[i][target].az, nBins);
  const bin = binAt(sample);
  const ridgeIdx = ridgeIndexAtBin(att, bin);
  if (ridgeIdx === null || !att.ridges[ridgeIdx]) return null;
  let run: RidgeNow['run'] = null;
  if (series && series.visible[sample] === false) {
    const same = (i: number) => i >= 0 && i < samples.length && series.visible[i] === false && ridgeIndexAtBin(att, binAt(i)) === ridgeIdx;
    let i0 = sample;
    let i1 = sample;
    while (same(i0 - 1)) i0--;
    while (same(i1 + 1)) i1++;
    run = { i0, i1 };
  }
  return { ridge: att.ridges[ridgeIdx], ridgeIdx, bin, ctrlDistM: att.perBin.ctrlDistM?.[bin] ?? null, gapDeg: att.perBin.gapDeg?.[bin] ?? null, run };
}

/** "12–169 m" / "127.7–129.6 km" from a ridge's bundle distance (range when the bundle gives one). */
export function fmtRidgeDistance(r: Ridge): string {
  const f = (m: number) => (m >= 1000 ? `${(m / 1000).toFixed(m >= 10000 ? 1 : 2)} km` : `${m.toFixed(0)} m`);
  if (typeof r.distanceM === 'number') return Number.isFinite(r.distanceM) ? f(r.distanceM) : '—';
  const { min, max } = r.distanceM;
  if (min === max) return f(min);
  return max >= 1000 ? `${(min / 1000).toFixed(max >= 10000 ? 1 : 2)}–${f(max)}` : `${min.toFixed(0)}–${f(max)}`;
}
