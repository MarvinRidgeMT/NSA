import { useMemo } from 'react';
import { bracket, flagAt, lerp, lerpAzimuth, nearestIndex, valueAt, type Bracket } from '../bundle/sampling';
import { basisFor, type Basis } from '../bundle/frame';
import type { Dataset, DisplayStatus, Failure, LoadedBundle, Scenario } from '../bundle/types';
import { usePolaris } from './store';

export interface TargetView {
  az: number;
  el: number;
  /** null when the bundle has no derived outputs */
  marginDeg: number | null;
  horizonElDeg: number | null;
  visible: boolean | null | undefined; // undefined: no derived; null: transition between samples
  firstHitM: number | null | undefined;
}

export interface View {
  loaded: LoadedBundle;
  status: DisplayStatus;
  dataset: Dataset;
  /** the selected scenario (metrics, deltas, label) */
  scenario: Scenario | null;
  /** the scenario whose per-sample series drive charts/strips/3D: the selected one if it has series, else the baseline */
  series: Scenario | null;
  /** true when the selected scenario has metrics only and the series shown are the baseline's */
  seriesIsBaseline: boolean;
  times: number[];
  utcMs: number;
  br: Bracket;
  nearest: number;
  sun: TargetView;
  earth: TargetView;
  both: boolean | null | undefined;
  basis: Basis;
  failure: Failure | null;
}

function target(ds: Dataset, sc: Scenario | null, br: Bracket, key: 'sun' | 'earth'): TargetView {
  const s = ds.ephemeris.samples;
  const a = s[br.i0][key];
  const b = s[br.i1][key];
  const az = br.exact !== null ? s[br.exact][key].az : lerpAzimuth(a.az, b.az, br.f);
  const el = br.exact !== null ? s[br.exact][key].el : lerp(a.el, b.el, br.f);
  if (!sc?.samples) return { az, el, marginDeg: null, horizonElDeg: null, visible: undefined, firstHitM: undefined };
  const ser = sc.samples[key];
  const num = (x: number) => (Number.isFinite(x) ? x : null);
  return {
    az,
    el,
    marginDeg: num(valueAt(ser.marginDeg, br)),
    horizonElDeg: num(valueAt(ser.horizonElDeg, br)),
    visible: flagAt(ser.visible, br),
    firstHitM: ser.firstHitM[nearestIndex(br)],
  };
}

/** A position-offset scenario was computed with its own JPL samples and local basis. While it drives the view, every
 * panel reads those instead of the dataset's (same UTC times required; otherwise the dataset is left unchanged). */
export function withScenarioGeometry(ds: Dataset, sc: Scenario | null, times: number[]): Dataset {
  const e = sc?.ephemeris;
  const f = sc?.frame;
  if (!e && !f) return ds;
  let out = ds;
  if (e && e.samples.length === times.length && e.samples.every((s, k) => Date.parse(s.time) === times[k]))
    out = { ...out, ephemeris: { ...out.ephemeris, samples: e.samples } };
  if (f?.localNorthInGrid && f.localEastInGrid && out.derived) out = { ...out, derived: { ...out.derived, frame: f } };
  return out;
}

/** Everything a panel needs, derived from the ONE store. Returns null until a bundle is loaded. */
export function useView(): View | null {
  const loaded = usePolaris((s) => s.loaded);
  const datasetIdx = usePolaris((s) => s.datasetIdx);
  const scenarioId = usePolaris((s) => s.scenarioId);
  const utcMs = usePolaris((s) => s.utcMs);
  const failureId = usePolaris((s) => s.selectedFailureId);
  return useMemo(() => {
    if (!loaded || utcMs === null) return null;
    const base = loaded.bundle.datasets[datasetIdx];
    const times = loaded.times[datasetIdx];
    let br: Bracket;
    try {
      br = bracket(times, utcMs);
    } catch {
      return null;
    }
    const scenario = base.derived?.scenarios.find((s) => s.id === scenarioId) ?? null;
    const series = scenario?.samples ? scenario : (base.derived?.scenarios.find((s) => s.samples) ?? null);
    const dataset = withScenarioGeometry(base, series, times);
    return {
      loaded,
      status: loaded.status,
      dataset,
      scenario,
      series,
      seriesIsBaseline: !!scenario && series !== scenario,
      times,
      utcMs,
      br,
      nearest: nearestIndex(br),
      sun: target(dataset, series, br, 'sun'),
      earth: target(dataset, series, br, 'earth'),
      both: series?.samples ? flagAt(series.samples.both.visible, br) : undefined,
      basis: basisFor(dataset),
      failure: series?.failures.find((f) => f.id === failureId) ?? null,
    };
  }, [loaded, datasetIdx, scenarioId, utcMs, failureId]);
}

export function fmtUtc(ms: number): string {
  return new Date(ms).toISOString().replace('.000Z', 'Z');
}

export function fmtDeg(v: number | null | undefined, digits = 2): string {
  return v === null || v === undefined ? '—' : `${v >= 0 && digits > 0 ? '' : ''}${v.toFixed(digits)}°`;
}

export function fmtSigned(v: number | null | undefined, digits = 2, unit = '°'): string {
  if (v === null || v === undefined) return '—';
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(digits)}${unit}`;
}
