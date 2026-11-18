import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { arcAt, distAt, fmtPublicUtc, glareFor, lightCaption, glare, glareOut, INTRO, loadFraction, loadLabel, LOAD_WEIGHTS, openMs, peekDeg, peekStillDeg, sunClear, SUN_RADIUS_DEG, type Arc } from '../../src/simple/introMath';
import { easeCamera } from '../../src/store/camera';

/** S3 opening sequence: the arithmetic the camera, the lens effects and the progress line run on. */
describe('opening sequence: timing', () => {
  it('lasts under 6 s when nothing has to be waited for, and is shorter when the data was there at once', () => {
    expect(INTRO.OPEN_MS + INTRO.ARC_MS).toBeLessThan(6000);
    expect(openMs(0)).toBe(INTRO.OPEN_CACHED_MS);
    expect(openMs(INTRO.CACHED_BY_MS + 1)).toBe(INTRO.OPEN_MS);
    expect(INTRO.OPEN_CACHED_MS).toBeLessThan(INTRO.OPEN_MS);
  });

  it('the move to the globe view ends exactly on it, and Skip finishes from where the camera is without a jump', () => {
    const arc: Arc = { t0: 1000, durMs: INTRO.ARC_MS, from: 0, skip: false };
    expect(arcAt(arc, 1000, easeCamera).e).toBe(0);
    expect(arcAt(arc, 1000 + INTRO.ARC_MS, easeCamera).e).toBe(1);
    expect(arcAt(arc, 1e9, easeCamera)).toEqual({ e: 1, k: 1 });
    // Skip part-way through: the new arc starts at the position the old one had reached
    const mid = arcAt(arc, 1000 + 900, easeCamera).e;
    const skip: Arc = { t0: 1900, durMs: INTRO.SKIP_MS, from: mid, skip: true };
    expect(arcAt(skip, 1900, easeCamera).e).toBeCloseTo(mid, 12);
    expect(arcAt(skip, 1900 + INTRO.SKIP_MS, easeCamera).e).toBe(1);
    let last = mid;
    for (let t = 0; t <= INTRO.SKIP_MS; t += 20) {
      const e = arcAt(skip, 1900 + t, easeCamera).e;
      expect(e).toBeGreaterThanOrEqual(last);
      last = e;
    }
    expect(INTRO.SKIP_MS).toBeLessThan(1000);
  });

  it('the camera distance runs from the far start to the globe view', () => {
    expect(distAt(0, 8, 4)).toBeCloseTo(8, 12);
    expect(distAt(1, 8, 4)).toBeCloseTo(4, 12);
    expect(distAt(0.5, 8, 4)).toBeCloseTo(Math.sqrt(32), 12);
  });
});

describe('opening sequence: light safety (WCAG 2.3.1)', () => {
  it('the lens glare takes at least one second to reach full strength, and never steps', () => {
    expect(INTRO.GLARE_RAMP_MS).toBeGreaterThanOrEqual(1000);
    expect(glare(0)).toBe(0);
    expect(glare(INTRO.GLARE_RAMP_MS)).toBe(1);
    let last = 0;
    for (let t = 0; t <= INTRO.GLARE_RAMP_MS; t += 16) {
      const g = glare(t);
      expect(g).toBeGreaterThanOrEqual(last);
      expect(g - last).toBeLessThan(0.03); // per 16 ms frame
      if (t < 1000) expect(g).toBeLessThan(1);
      last = g;
    }
  });

  it('the lens effects are capped at about 80 % of display white', () => {
    expect(INTRO.WHITE_CAP).toBeLessThanOrEqual(0.8);
  });

  it('the lens effects are gone before the interface comes in, so none reaches the globe view', () => {
    expect(glareOut(0)).toBe(1);
    expect(glareOut(INTRO.CHROME_AT)).toBe(0);
    expect(glareOut(1)).toBe(0);
  });
});

describe('opening sequence: the Sun at the limb', () => {
  const moon = 7.4; // an angular radius in the range the view uses; any value works
  it('starts with the Sun hidden behind the Moon and brings it clear', () => {
    expect(sunClear(peekDeg(0, moon), moon)).toBe(0);
    expect(sunClear(peekDeg(1500, moon), moon)).toBe(1);
    expect(sunClear(peekStillDeg(moon), moon)).toBe(1);
  });
  it('keeps the Sun close to the limb however long the load takes', () => {
    let last = -Infinity;
    for (let t = 0; t <= 120_000; t += 250) {
      const p = peekDeg(t, moon);
      expect(p).toBeGreaterThanOrEqual(last);
      last = p;
    }
    expect(last - moon).toBeLessThanOrEqual(1.2 + 1e-9);
    expect(SUN_RADIUS_DEG).toBeCloseTo(0.2665, 6);
  });
});

describe('opening sequence: load progress', () => {
  it('is a sum of real loader states and reaches 1 only when all are done', () => {
    expect(LOAD_WEIGHTS.bundle + LOAD_WEIGHTS.sidecar + LOAD_WEIGHTS.moon).toBeCloseTo(1, 12);
    expect(loadFraction({ bundle: false, sidecar: false, moon: 0 })).toBe(0);
    expect(loadFraction({ bundle: true, sidecar: false, moon: 0 })).toBeCloseTo(LOAD_WEIGHTS.bundle, 12);
    expect(loadFraction({ bundle: true, sidecar: true, moon: 0.5 })).toBeCloseTo(LOAD_WEIGHTS.bundle + LOAD_WEIGHTS.sidecar + LOAD_WEIGHTS.moon / 2, 12);
    expect(loadFraction({ bundle: true, sidecar: true, moon: 1 })).toBe(1);
    expect(loadFraction({ bundle: true, sidecar: true, moon: 0.999 })).toBeLessThan(1);
    expect(loadFraction({ bundle: true, sidecar: true, moon: 7 })).toBe(1);
  });
  it('says what is being waited for', () => {
    expect(loadLabel({ bundle: false, sidecar: false, moon: 0 })).toBe('Reading the bundle');
    expect(loadLabel({ bundle: true, sidecar: true, moon: 0.2 })).toBe('Loading the Moon');
    expect(loadLabel({ bundle: true, sidecar: true, moon: 1 })).toBe('Loaded');
  });
});

describe('opening sequence: the light caption', () => {
  // expected values are read from the ROI bundle the Simple mode opens on, never typed in
  const b = JSON.parse(readFileSync(resolve(__dirname, '../../public/bundles/polaris-x5d-roi-2026-11-14-v2.json'), 'utf8')) as {
    datasets: { siteId: string; site: { name: string }; ephemeris: { samples: { time: string; sun: { az: number } }[] } }[];
  };
  const d = b.datasets.find((x) => x.siteId === 'site04_roi3')!;
  const s0 = d.ephemeris.samples[0];
  const ms = Date.parse(s0.time);
  it('says the time in words a visitor reads, to the minute, in UTC', () => {
    const t = new Date(ms);
    const month = t.toLocaleString('en-GB', { month: 'short', timeZone: 'UTC' }).slice(0, 3);
    const hhmm = s0.time.slice(11, 16);
    expect(fmtPublicUtc(ms)).toBe(`${t.getUTCDate()} ${month} ${t.getUTCFullYear()}, ${hhmm} UTC`);
  });
  it('carries the bundle azimuth to one decimal and the site name', () => {
    const c = lightCaption(ms, s0.sun.az, d.site.name);
    expect(c.startsWith('Sunlight from our data · ')).toBe(true);
    expect(c).toContain(` · ${fmtPublicUtc(ms)} · `);
    expect(c).toContain(`Sun azimuth ${s0.sun.az.toFixed(1)}° at ${d.site.name}`);
  });
});

describe('opening sequence: reduced motion', () => {
  it('the still frame has its glare at final strength from the first lit frame: nothing in it animates while data loads', () => {
    for (const t of [0, 1, INTRO.GLARE_RAMP_MS / 2, INTRO.GLARE_RAMP_MS, 10 * INTRO.GLARE_RAMP_MS]) expect(glareFor(t, true)).toBe(1);
    // with motion, the ramp is unchanged
    expect(glareFor(0, false)).toBe(0);
    expect(glareFor(INTRO.GLARE_RAMP_MS, false)).toBe(1);
  });
});

describe('opening sequence: what the progress line says', () => {
  it('a failed Moon model is never called loaded', () => {
    expect(loadLabel({ bundle: true, sidecar: true, moon: 1, moonFailed: true })).toBe('The Moon model could not be loaded');
    expect(loadLabel({ bundle: true, sidecar: true, moon: 1 })).toBe('Loaded');
  });
});
