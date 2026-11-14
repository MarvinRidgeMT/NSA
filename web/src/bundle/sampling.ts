/**
 * Indexing and interpolation of bundle samples. This is the ONLY numeric work the
 * viewer does: locate a UTC time among bundle samples and interpolate between the
 * two bracketing samples. Azimuth is interpolated circularly (359° → 1° passes
 * through 0°). Times outside the bundle's coverage are refused, never extrapolated.
 */

export class CoverageError extends Error {
  constructor(
    public readonly t: number,
    public readonly start: number,
    public readonly end: number,
  ) {
    const iso = (x: number) => (Number.isFinite(x) ? new Date(x).toISOString().replace('.000Z', 'Z') : String(x));
    super(`${iso(t)} is outside bundle coverage ${iso(start)} – ${iso(end)}`);
  }
}

export interface Bracket {
  i0: number;
  i1: number;
  f: number; // 0..1 between i0 and i1
  exact: number | null; // sample index when t is exactly a sample time
}

/** Binary search. Throws CoverageError outside [times[0], times[n-1]]. */
export function bracket(times: number[], t: number): Bracket {
  const n = times.length;
  if (n === 0 || !Number.isFinite(t) || t < times[0] || t > times[n - 1]) throw new CoverageError(t, times[0], times[n - 1]);
  let lo = 0;
  let hi = n - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (times[mid] <= t) lo = mid;
    else hi = mid;
  }
  if (times[lo] === t) return { i0: lo, i1: lo, f: 0, exact: lo };
  if (times[hi] === t) return { i0: hi, i1: hi, f: 0, exact: hi };
  return { i0: lo, i1: hi, f: (t - times[lo]) / (times[hi] - times[lo]), exact: null };
}

export function wrap360(a: number): number {
  const r = a % 360;
  return r < 0 ? r + 360 : r;
}

/** Shortest-arc interpolation between two azimuths, result in [0, 360). */
export function lerpAzimuth(a0: number, a1: number, f: number): number {
  let d = wrap360(a1) - wrap360(a0);
  if (d > 180) d -= 360;
  if (d < -180) d += 360;
  return wrap360(a0 + d * f);
}

export function lerp(a: number, b: number, f: number): number {
  return a + (b - a) * f;
}

export function valueAt(series: number[], br: Bracket): number {
  return br.exact !== null ? series[br.exact] : lerp(series[br.i0], series[br.i1], br.f);
}

/** Boolean at a time: exact sample value, or the shared value of both bracketing samples, else null (transition). */
export function flagAt(series: boolean[], br: Bracket): boolean | null {
  if (br.exact !== null) return series[br.exact];
  return series[br.i0] === series[br.i1] ? series[br.i0] : null;
}

/** Nearest sample index (ties go to the earlier sample). */
export function nearestIndex(br: Bracket): number {
  return br.exact ?? (br.f <= 0.5 ? br.i0 : br.i1);
}
