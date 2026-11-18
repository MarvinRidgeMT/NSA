/**
 * Opening sequence (S3): the arithmetic, with no three.js and no DOM so it can be unit-tested.
 *
 * DISPLAY ONLY. The sequence is drawn in the globe's own scene with the globe's own camera (simple/Globe.tsx), so its last
 * frame is the globe's first: nothing is cut or cross-faded at the hand-off. What is real: the Sun direction (the bundle's,
 * through globeMath.skyDirFromSite) and the load progress (the loaders' own events). Everything else here is a display choice.
 *
 * The camera's place is one angle, psi, measured at the Moon's centre from the south-pole view toward the point opposite the
 * Sun. psi = 0 is the globe view. The sequence opens near psi = (angle from south pole to anti-Sun) − a few degrees, far
 * enough back that the Sun stands just clear of the dark Moon's limb, holds there while the data loads, then eases to 0.
 */

export const INTRO = {
  /** shortest time from first light to the start of the move to the pole, ms */
  OPEN_MS: 1600,
  /** the same when everything had loaded within CACHED_BY_MS of first light (a repeat visit) */
  OPEN_CACHED_MS: 900,
  CACHED_BY_MS: 500,
  /** the move from the eclipse view to the globe view, ms */
  ARC_MS: 2800,
  /** the same move after Skip, from wherever the camera is, ms */
  SKIP_MS: 600,
  /** the lens glare takes at least this long to reach full strength (WCAG 2.3.1: no flash), ms */
  GLARE_RAMP_MS: 1200,
  /** the lens effects never lift a pixel above this display level (0-1); only the small Sun disc itself is brighter */
  WHITE_CAP: 0.8,
  /** sunlight comes up on the Moon over this long once its model is in the scene, ms */
  LIGHT_RAMP_MS: 800,
  /** the camera starts this many times farther away than the globe view */
  FAR: 1.75,
  /** the same on a narrow window (phones), where the view is small already */
  FAR_NARROW: 1.35,
  /** progress of the move (0-1, eased) at which the interface starts to come in */
  CHROME_AT: 0.62,
  /** reduced motion: the still frame gives way to the globe over this long, ms */
  STILL_FADE_MS: 600,
} as const;

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
export const smooth = (a: number, b: number, x: number) => {
  const t = clamp01((x - a) / (b - a));
  return t * t * (3 - 2 * t);
};
/** ease-out cubic, for the short finish after Skip (it starts at the speed the eye is already following) */
export const easeOut = (k: number) => 1 - Math.pow(1 - clamp01(k), 3);

/** Angular radius of the Sun's disc seen from the Moon, degrees (same value as the post chain's). */
export const SUN_RADIUS_DEG = 0.2665;

/** How long the opening holds before the move may start: shorter when the data was there almost at once. */
export function openMs(loadedAfterMs: number): number {
  return loadedAfterMs <= INTRO.CACHED_BY_MS ? INTRO.OPEN_CACHED_MS : INTRO.OPEN_MS;
}

/**
 * Angle of the Sun from the Moon's centre as the camera sees it, t ms after first light, for a Moon of angular radius
 * `moonRadiusDeg`. It starts with the disc hidden just inside the limb, comes clear within about half a second, and then
 * only creeps (so a long load is never a frozen picture), never more than 1.2 degrees past the limb.
 */
export function peekDeg(tMs: number, moonRadiusDeg: number): number {
  const t = Math.max(0, tMs);
  const out = 1.0 * (1 - Math.exp(-t / 650));
  const creep = Math.min(0.6, (t / 1000) * 0.06);
  return moonRadiusDeg - 0.4 + out + creep;
}
/** The still frame under reduced motion: the Sun clear of the limb, nothing moving. */
export const peekStillDeg = (moonRadiusDeg: number) => moonRadiusDeg + 0.7;

/** Strength of the lens glare, 0-1, t ms after first light: a ramp of GLARE_RAMP_MS, never a step. */
export function glare(tMs: number): number {
  return smooth(0, INTRO.GLARE_RAMP_MS, tMs);
}
/**
 * The same for the reduced-motion still frame: at its final strength from the first lit frame, so nothing in the still
 * changes while the data loads (no flare animation). One onset, capped at INTRO.WHITE_CAP, is not a flash (WCAG 2.3.1 counts
 * pairs of opposing changes); the still then leaves by the cross-fade.
 */
export function glareFor(tMs: number, still: boolean): number {
  return still ? 1 : glare(tMs);
}
/** The lens effects leave as the move to the pole proceeds; gone before the interface comes in. */
export function glareOut(e: number): number {
  return 1 - smooth(0.2, INTRO.CHROME_AT, e);
}

/** How much of the Sun's disc clears a Moon of angular radius `moonRadiusDeg` when it stands `sunDeg` from the Moon's centre. */
export function sunClear(sunDeg: number, moonRadiusDeg: number): number {
  return smooth(moonRadiusDeg - SUN_RADIUS_DEG, moonRadiusDeg + SUN_RADIUS_DEG, sunDeg);
}

export interface Arc {
  /** performance.now() at its start */
  t0: number;
  durMs: number;
  /** path position it starts from (0 = the hold, 1 = the globe view) */
  from: number;
  /** true after Skip: ease-out from the current position instead of the full in-out move */
  skip: boolean;
}
/** Path position 0-1 of an arc at `now`; `inOut` is the camera's in-out ease (store/camera.ts easeCamera). */
export function arcAt(a: Arc, now: number, inOut: (k: number) => number): { e: number; k: number } {
  const k = clamp01((now - a.t0) / a.durMs);
  return { e: a.from + (1 - a.from) * (a.skip ? easeOut(k) : inOut(k)), k };
}

/** Camera distance along the path: blended in log space so the push-in slows evenly as the Moon fills the view. */
export function distAt(e: number, far: number, near: number): number {
  return Math.exp(Math.log(far) * (1 - e) + Math.log(near) * e);
}

export interface LoadParts {
  /** the bundle has been read and validated */
  bundle: boolean;
  /** the certainty sidecar has been read (or has failed: it is optional) */
  sidecar: boolean;
  /** bytes of the Moon model received / expected, from the loader's progress events; 1 when it is in the scene or has failed */
  moon: number;
  /** the Moon model's loader gave up (it then counts as finished, but is never called loaded) */
  moonFailed?: boolean;
}
/**
 * One figure for the progress line. Each part is a real loader state; the weights only say how much of the line each part
 * takes (the Moon model is by far the largest download).
 */
export const LOAD_WEIGHTS = { bundle: 0.3, sidecar: 0.05, moon: 0.65 } as const;
export function loadFraction(p: LoadParts): number {
  return clamp01((p.bundle ? LOAD_WEIGHTS.bundle : 0) + (p.sidecar ? LOAD_WEIGHTS.sidecar : 0) + LOAD_WEIGHTS.moon * clamp01(p.moon));
}
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'] as const;
/** A UTC instant for the public, to the minute: "14 Nov 2026, 00:00 UTC". */
export function fmtPublicUtc(ms: number): string {
  const d = new Date(ms);
  const p2 = (n: number) => String(n).padStart(2, '0');
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}, ${p2(d.getUTCHours())}:${p2(d.getUTCMinutes())} UTC`;
}
/**
 * The light caption under the progress line. Time, azimuth and site name are passed in from the bundle (the opening site's
 * ephemeris sample at the view's time); nothing here is a number of its own.
 */
export function lightCaption(utcMs: number, sunAzDeg: number, siteName: string): string {
  return `Sunlight from our data · ${fmtPublicUtc(utcMs)} · Sun azimuth ${sunAzDeg.toFixed(1)}° at ${siteName}`;
}

/** What is being waited for, in words. */
export function loadLabel(p: LoadParts): string {
  if (!p.bundle) return 'Reading the bundle';
  if (p.moonFailed) return 'The Moon model could not be loaded';
  if (p.moon < 1) return 'Loading the Moon';
  if (!p.sidecar) return 'Reading the certainty sidecar';
  return 'Loaded';
}
