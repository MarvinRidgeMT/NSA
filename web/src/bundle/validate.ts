import type { Bundle, Dataset, DisplayStatus, LoadedBundle, RawStatus, Scenario } from './types';
import { BundleError } from './errors';
import { adaptScienceV2, isScienceV2, normalizeDerivedBlocks } from './scienceV2';

export { BundleError };

const RAW_TO_DISPLAY: Record<RawStatus, DisplayStatus> = {
  DEMO_ONLY: 'DEMO',
  SOURCE_BASED_UNVALIDATED: 'SOURCE-BASED UNVALIDATED',
  VALIDATED_NASA_JPL: 'VALIDATED',
};

function fail(msg: string): never {
  throw new BundleError(msg);
}

function finiteArray(a: unknown, len: number | null, where: string): number[] {
  if (!Array.isArray(a)) fail(`${where}: expected an array`);
  if (len !== null && a.length !== len) fail(`${where}: expected ${len} values, got ${a.length}`);
  for (let i = 0; i < a.length; i++) {
    if (typeof a[i] !== 'number' || !Number.isFinite(a[i])) fail(`${where}[${i}] is not a finite number`);
  }
  return a as number[];
}

/**
 * Display status is the most cautious of: top-level status, every dataset's status,
 * every derived block's status, and the `demo` flag. Synthetic content always reads DEMO.
 */
export function displayStatus(b: Bundle): DisplayStatus {
  const raws: string[] = [b.validation?.status];
  for (const d of b.datasets ?? []) {
    raws.push(d.validation?.status);
    if (d.derived) raws.push(d.derived.status);
    if (d.dem?.kind && d.dem.kind !== 'nasa') raws.push('DEMO_ONLY');
  }
  if (b.demo) raws.push('DEMO_ONLY');
  if (raws.some((r) => r === 'DEMO_ONLY' || !(r in RAW_TO_DISPLAY))) return 'DEMO';
  if (raws.some((r) => r === 'SOURCE_BASED_UNVALIDATED')) return 'SOURCE-BASED UNVALIDATED';
  return 'VALIDATED';
}

/** Numbers or explicit "no value" (null / NaN). Infinity and non-numbers are refused. */
function numberOrGap(a: unknown, len: number, where: string) {
  if (!Array.isArray(a) || a.length !== len) fail(`${where}: expected ${len} values`);
  for (let i = 0; i < a.length; i++) {
    const x = a[i];
    if (x === null || (typeof x === 'number' && (Number.isFinite(x) || Number.isNaN(x)))) continue;
    fail(`${where}[${i}] is not a number`);
  }
}

function checkScenario(s: Scenario, nSamples: number, where: string) {
  if (!s.id) fail(`${where}: scenario without id`);
  const sk = s.skyline;
  if (sk) {
    const nb = finiteArray(sk.azimuthDeg, null, `${where}.skyline.azimuthDeg`).length;
    numberOrGap(sk.elevationDeg, nb, `${where}.skyline.elevationDeg`);
    for (const az of sk.azimuthDeg) if (az < 0 || az >= 360) fail(`${where}.skyline.azimuthDeg out of [0,360)`);
  }
  if (s.samples) {
    for (const t of ['sun', 'earth'] as const) {
      const ser = s.samples[t];
      if (!ser) fail(`${where}.samples.${t} missing`);
      if (!Array.isArray(ser.visible) || ser.visible.length !== nSamples) fail(`${where}.samples.${t}.visible must have ${nSamples} entries`);
      numberOrGap(ser.marginDeg, nSamples, `${where}.samples.${t}.marginDeg`);
      numberOrGap(ser.horizonElDeg, nSamples, `${where}.samples.${t}.horizonElDeg`);
      if (!Array.isArray(ser.firstHitM) || ser.firstHitM.length !== nSamples) fail(`${where}.samples.${t}.firstHitM must have ${nSamples} entries`);
    }
    if (!Array.isArray(s.samples.both?.visible) || s.samples.both.visible.length !== nSamples) fail(`${where}.samples.both.visible must have ${nSamples} entries`);
  }
  for (const m of s.metrics ?? []) if (!Number.isFinite(m.value)) fail(`${where}.metrics.${m.id} not finite`);
  for (const f of s.failures ?? []) {
    if (f.sampleIndex < 0 || f.sampleIndex >= nSamples) fail(`${where}.failures.${f.id} sampleIndex out of range`);
    const n = f.profile?.distanceM?.length ?? 0;
    finiteArray(f.profile?.terrainM, n, `${where}.failures.${f.id}.profile.terrainM`);
    finiteArray(f.profile?.rayM, n, `${where}.failures.${f.id}.profile.rayM`);
  }
}

function checkDataset(d: Dataset, i: number): number[] {
  const w = `datasets[${i}]`;
  if (!d.siteId) fail(`${w}.siteId missing`);
  if (!d.site || !Number.isFinite(d.site.longitudeEastDeg)) fail(`${w}.site.longitudeEastDeg missing`);
  const dem = d.dem;
  if (dem) {
    if (!Number.isInteger(dem.n) || dem.n < 4) fail(`${w}.dem.n invalid`);
    if (!(dem.spacing > 0)) fail(`${w}.dem.spacing must be > 0`);
    if (dem.verticalUnits !== 'meters') fail(`${w}.dem.verticalUnits must be "meters"`);
    if (!/south-to-north/.test(dem.rowOrder ?? '')) fail(`${w}.dem.rowOrder must be south-to-north`);
    finiteArray(dem.values, dem.n * dem.n, `${w}.dem.values`);
  } else if (!d.derived) {
    fail(`${w}: neither a DEM nor derived science outputs`);
  }
  const e = d.ephemeris;
  if (!e || e.timeScale !== 'UTC') fail(`${w}.ephemeris.timeScale must be UTC`);
  if (!Array.isArray(e.samples) || e.samples.length < 2) fail(`${w}.ephemeris needs at least 2 samples`);
  const times = e.samples.map((s, k) => {
    const t = Date.parse(s.time);
    if (!Number.isFinite(t) || !/Z$|[+-]00:?00$/.test(s.time)) fail(`${w}.ephemeris.samples[${k}].time is not UTC ISO-8601`);
    for (const tgt of ['sun', 'earth'] as const) {
      const v = s[tgt];
      if (!v || !Number.isFinite(v.az) || !Number.isFinite(v.el) || v.az < 0 || v.az > 360 || v.el < -90 || v.el > 90)
        fail(`${w}.ephemeris.samples[${k}].${tgt} az/el invalid`);
    }
    return t;
  });
  for (let k = 1; k < times.length; k++) if (!(times[k] > times[k - 1])) fail(`${w}.ephemeris times must be strictly increasing (index ${k})`);
  if (d.derived) {
    if (!Array.isArray(d.derived.scenarios) || d.derived.scenarios.length === 0) fail(`${w}.derived.scenarios empty`);
    d.derived.scenarios.forEach((s, k) => checkScenario(s, times.length, `${w}.derived.scenarios[${k}]`));
  }
  return times;
}

/** Structural checks on the raw (snake_case) A1–A4 blocks of a POLARIS-X5D-v2 derived object. Refuses; never repairs. */
function checkDecisionBlocks(d: Record<string, unknown>, nSamples: number, w: string): void {
  const rec = (x: unknown): x is Record<string, unknown> => !!x && typeof x === 'object' && !Array.isArray(x);
  const a = d.attribution;
  if (rec(a) && Array.isArray(a.ridges)) {
    const ids = new Set<string>();
    (a.ridges as Record<string, unknown>[]).forEach((r, k) => {
      if (r.source !== undefined && r.source !== 'near_5m' && r.source !== 'far_80m') fail(`${w}.attribution.ridges[${k}].source must be near_5m or far_80m`);
      if (typeof r.id === 'string') ids.add(r.id);
    });
    const pb = a.per_bin;
    if (rec(pb) && Array.isArray(pb.ridge_id))
      (pb.ridge_id as (string | null)[]).forEach((id, k) => {
        if (id !== null && !ids.has(id)) fail(`${w}.attribution.per_bin.ridge_id[${k}]: "${id}" is not a listed ridge`);
      });
  }
  if (Array.isArray(d.certainty_curve))
    (d.certainty_curve as Record<string, unknown>[]).forEach((c, k) => {
      if (c.pass !== undefined) {
        const m = typeof c.pass === 'string' ? /^(\d+)\/(\d+)$/.exec(c.pass) : null;
        if (!m || Number(m[1]) > Number(m[2]) || (typeof c.n_clones === 'number' && Number(m[2]) !== c.n_clones)) fail(`${w}.certainty_curve[${k}].pass must be "k/N" with k ≤ N = n_clones`);
      }
      const lo = c.min as number, med = c.median as number, hi = c.max as number;
      if ([lo, med, hi].every((x) => typeof x === 'number') && !(lo <= med && med <= hi)) fail(`${w}.certainty_curve[${k}]: min ≤ median ≤ max violated`);
    });
  if (rec(d.coverage) && typeof d.coverage.covered_frac === 'number' && !(d.coverage.covered_frac >= 0 && d.coverage.covered_frac <= 1))
    fail(`${w}.coverage.covered_frac must be in [0, 1]`);
  const mg = d.margins ?? d.margin_series;
  if (rec(mg))
    for (const k of ['sun_margin_deg', 'earth_margin_deg', 'sun_clone_min_deg', 'sun_clone_max_deg', 'earth_clone_min_deg', 'earth_clone_max_deg'])
      if (Array.isArray(mg[k]) && (mg[k] as unknown[]).length !== nSamples) fail(`${w}.margins.${k}: expected ${nSamples} values, got ${(mg[k] as unknown[]).length}`);
}

/** Parse + structurally validate. Throws BundleError with a specific message. */
export function validateBundle(raw: unknown): { bundle: Bundle; times: number[][]; status: DisplayStatus; warnings: string[] } {
  if (!raw || typeof raw !== 'object') fail('bundle is not a JSON object');
  const b = isScienceV2(raw) ? adaptScienceV2(raw) : (raw as Bundle);
  if (b.format !== 'POLARIS-X5D-v2' && b.format !== 'science-bundle-v2' && b.format !== 'polaris-science-results-v1')
    fail(`unsupported format "${String((b as { format?: unknown }).format ?? (b as { schema?: unknown }).schema)}" (expected science-bundle-v2, polaris-science-results-v1 or POLARIS-X5D-v2)`);
  if (!/^2/.test(b.schemaVersion ?? '')) fail(`unsupported schemaVersion "${b.schemaVersion}"`);
  if (!b.validation?.status) fail('validation.status missing');
  if (!Array.isArray(b.datasets) || b.datasets.length === 0) fail('datasets empty');
  const times = b.datasets.map(checkDataset);
  // POLARIS-X5D-v2 exports (science/viewer.py) carry derived.attribution in the science branch's snake_case A1 shape
  b.datasets.forEach((d, i) => d.derived && checkDecisionBlocks(d.derived as unknown as Record<string, unknown>, times[i].length, `datasets[${i}].derived`));
  for (const d of b.datasets) if (d.derived) normalizeDerivedBlocks(d.derived as unknown as Record<string, unknown>);
  const warnings: string[] = [];
  b.datasets.forEach((d) => {
    if (!d.dem && d.derived)
      warnings.push(`${d.site.name}: this bundle ships no DEM grid. The 3D view shows the bundle's own 720-bin horizon silhouette (angles exact from the observer).`);
    if (!d.derived)
      warnings.push(
        `${d.site.name}: bundle has no "derived" science outputs (skyline, margins, metrics). Visibility and margins are not shown; the viewer does not compute them.`,
      );
  });
  return { bundle: b, times, status: displayStatus(b), warnings };
}

export async function sha256Hex(buf: ArrayBuffer): Promise<string> {
  const h = await crypto.subtle.digest('SHA-256', buf);
  return Array.from(new Uint8Array(h), (x) => x.toString(16).padStart(2, '0')).join('');
}

export async function loadBundleBytes(buf: ArrayBuffer, name: string, origin: string): Promise<LoadedBundle> {
  let json: unknown;
  try {
    json = JSON.parse(new TextDecoder().decode(buf));
  } catch (e) {
    throw new BundleError(`${name}: not valid JSON (${(e as Error).message})`);
  }
  const v = validateBundle(json);
  return { name, origin, sha256: await sha256Hex(buf), bytes: buf.byteLength, ...v };
}
