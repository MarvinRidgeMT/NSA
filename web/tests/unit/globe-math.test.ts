import { existsSync, readFileSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { GLOBE_8K, GLOBE_FULL, GLOBE_LITE, MODEL_YAW_RAD, RELIEF_CAP_FROM_DEG, RELIEF_CAP_TO_DEG, distanceForDisc, globePlan, reliefNormals, globeAsset, layoutPins, moonDir, pinReading, skyDirFromSite, type CurveRow, type SidecarSite } from '../../src/simple/globeMath';

/** S4 globe arithmetic. Expected values are read from the sidecar and the bundle files, never typed in. */
const sidecarPath = resolve(__dirname, '../../public/certainty/sidecar.json');
const bundlePath = resolve(__dirname, '../../../data/viewer/polaris-x5d-roi-2026-11-14-v2.json');
const DEG = 180 / Math.PI;
/** east longitude of a model-frame direction (inverse of moonDir) */
const lonOf = (d: number[]) => Math.atan2(-d[0], -d[2]) * DEG;
const latOf = (d: number[]) => Math.asin(d[1]) * DEG;

describe('model frame of the Moon GLB', () => {
  it('north is +Y, longitude 0° is −Z, 90° E is −X', () => {
    const near = (a: number[], b: number[]) => a.forEach((x, i) => expect(x).toBeCloseTo(b[i], 12));
    near(moonDir(90, 0), [0, 1, 0]);
    near(moonDir(-90, 0), [0, -1, 0]);
    near(moonDir(0, 0), [0, 0, -1]);
    near(moonDir(0, 90), [-1, 0, 0]);
    near(moonDir(0, 180), [0, 0, 1]);
  });
  it('round trip: latitude and longitude come back', () => {
    for (const [lat, lon] of [[-89.5, -137.4], [12, 33], [-45, 170], [60, -100]]) {
      const d = moonDir(lat, lon);
      expect(latOf(d)).toBeCloseTo(lat, 9);
      expect(lonOf(d)).toBeCloseTo(lon, 9);
    }
  });
  it('a body at the zenith is the site direction; due north on the horizon at the equator is the pole', () => {
    const z = skyDirFromSite(-89.5, 40, 123, 90);
    moonDir(-89.5, 40).forEach((x, i) => expect(z[i]).toBeCloseTo(x, 9));
    const n = skyDirFromSite(0, 25, 0, 0);
    [0, 1, 0].forEach((x, i) => expect(n[i]).toBeCloseTo(x, 9));
    const e = skyDirFromSite(0, 25, 90, 0);
    moonDir(0, 115).forEach((x, i) => expect(e[i]).toBeCloseTo(x, 9));
  });
});

describe.skipIf(!existsSync(bundlePath))('Sun and Earth directions from the ROI bundle', () => {
  const bundle = existsSync(bundlePath) ? JSON.parse(readFileSync(bundlePath, 'utf8')) : { datasets: [] };
  type Ds = { site: { latitudePlanetocentricDeg: number; longitudeEastDeg: number }; ephemeris: { samples: { sun: { az: number; el: number }; earth: { az: number; el: number } }[] } };
  const ds = bundle.datasets as Ds[];
  it('every site gives the same Sun direction at the same sample (to 0.05°), first, middle and last sample', () => {
    const n = ds[0].ephemeris.samples.length;
    for (const k of [0, Math.floor(n / 2), n - 1]) {
      const dirs = ds.map((d) => skyDirFromSite(d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg, d.ephemeris.samples[k].sun.az, d.ephemeris.samples[k].sun.el));
      for (const d of dirs.slice(1)) {
        const dot = d[0] * dirs[0][0] + d[1] * dirs[0][1] + d[2] * dirs[0][2];
        expect(Math.acos(Math.min(1, dot)) * DEG).toBeLessThan(0.05);
      }
      // the Sun never stands more than about 1.6° from the Moon's equator
      expect(Math.abs(latOf(dirs[0]))).toBeLessThan(2);
    }
  });
  it('the Earth stands near longitude 0° and the equator (within the libration range), as it must in true lunar axes', () => {
    for (const d of ds) {
      const s = d.ephemeris.samples[0];
      const e = skyDirFromSite(d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg, s.earth.az, s.earth.el);
      expect(Math.abs(lonOf(e))).toBeLessThan(9);
      expect(Math.abs(latOf(e))).toBeLessThan(8);
    }
  });
});

describe('pin reading = the sidecar row', () => {
  const sc = JSON.parse(readFileSync(sidecarPath, 'utf8')) as { sites: Record<string, SidecarSite> };
  it('shimmer amplitude for each site and each sampled mast equals the sidecar spread (max − min)', () => {
    let checked = 0;
    for (const site of Object.values(sc.sites)) {
      for (const m of site.sampled_masts_m) {
        const row = (site.certainty_curve as CurveRow[]).find((r) => r.mast_m === m && r.metric === 'sun_centre_pct')!;
        const r = pinReading(site, m, null)!;
        expect(r.mastM).toBe(m);
        expect(r.spreadPts).toBe(row.max - row.min);
        expect(r.all100).toBe(row.min >= 100);
        if (row.max === row.min) expect(r.spreadPts).toBe(0);
        checked++;
      }
    }
    expect(checked).toBeGreaterThan(0);
  });
  it('no pick: the bundle series mast when sampled, else the lowest sampled mast', () => {
    for (const site of Object.values(sc.sites)) {
      const masts = site.sampled_masts_m;
      expect(pinReading(site, null, null)!.mastM).toBe(masts[0]);
      expect(pinReading(site, null, masts[masts.length - 1])!.mastM).toBe(masts[masts.length - 1]);
      expect(pinReading(site, null, masts[0] + 0.001)!.mastM).toBe(masts[0]);
    }
  });
  it('a height the site was not sampled at has no row and no spread: nothing is interpolated', () => {
    for (const site of Object.values(sc.sites)) {
      const between = (site.sampled_masts_m[0] + site.sampled_masts_m[1]) / 2;
      const r = pinReading(site, between, null)!;
      expect(r.sun).toBeUndefined();
      expect(r.spreadPts).toBeNull();
    }
    expect(pinReading(undefined, 1, 1)).toBeNull();
  });
});

describe('pin layout', () => {
  const sep = (50 * Math.PI) / 180;
  it('pins stand on the ring, on the side their site lies, at least the minimum angle apart', () => {
    const anchors = [{ x: 100, y: 100 }, { x: 97, y: 101 }, { x: 97.1, y: 101.2 }];
    const { pins, centre, angles } = layoutPins(anchors, 78, sep);
    for (const p of pins) expect(Math.hypot(p.x - centre.x, p.y - centre.y)).toBeCloseTo(78, 6);
    for (let i = 0; i < 3; i++) for (let j = i + 1; j < 3; j++) expect(Math.hypot(pins[i].x - pins[j].x, pins[i].y - pins[j].y)).toBeGreaterThanOrEqual(2 * 78 * Math.sin(sep / 2) - 1e-6);
    expect(pins[0].x).toBeGreaterThan(centre.x); // the first site lies to the right of the group
    expect(pins[1].x).toBeLessThan(centre.x);
    expect(layoutPins(anchors, 78, sep).angles).toEqual(angles); // deterministic
  });
  it('sites on top of each other are spread evenly; none and one are handled', () => {
    const { pins } = layoutPins([{ x: 5, y: 5 }, { x: 5, y: 5 }, { x: 5, y: 5 }], 10, sep);
    expect(new Set(pins.map((p) => `${p.x.toFixed(3)},${p.y.toFixed(3)}`)).size).toBe(3);
    expect(layoutPins([], 10, sep).pins).toEqual([]);
    expect(layoutPins([{ x: 1, y: 2 }], 10, sep).pins).toHaveLength(1);
  });
});

describe('model choice and framing', () => {
  it('lite model for phones when built; the 8k model when present; else the compact NASA model', () => {
    expect(globeAsset([GLOBE_FULL], false)).toBe(GLOBE_FULL);
    expect(globeAsset([GLOBE_FULL], true)).toBe(GLOBE_FULL);
    expect(globeAsset([GLOBE_FULL, GLOBE_LITE], true)).toBe(GLOBE_LITE);
    expect(globeAsset([GLOBE_FULL, GLOBE_LITE], false)).toBe(GLOBE_FULL);
    expect(globeAsset([GLOBE_FULL, GLOBE_LITE, GLOBE_8K], false)).toBe(GLOBE_8K);
    expect(globeAsset([], false)).toBe(GLOBE_FULL);
  });
  it('the disc spans the asked share of the shorter side', () => {
    for (const [w, h] of [[1440, 900], [390, 844]]) {
      const d = distanceForDisc(30, w, h, 0.8);
      const discPx = (h / Math.tan((15 * Math.PI) / 180)) * Math.tan(Math.asin(1 / d));
      expect(discPx).toBeCloseTo(0.8 * Math.min(w, h), 6);
    }
  });
});

describe('relief shading of a model with relief', () => {
  // two flat-shaded facets meeting at one corner on the equator, and one vertex inside the polar cap
  const corner = [0, 0, 1];
  const pos = new Float32Array([...corner, ...corner, 0, Math.sin((89 * Math.PI) / 180), Math.cos((89 * Math.PI) / 180)]);
  const tilt = (deg: number) => [Math.sin((deg * Math.PI) / 180), 0, Math.cos((deg * Math.PI) / 180)];
  it('vertices at one position share one normal; the lean from the sphere normal is scaled; the polar cap is a smooth sphere', () => {
    const nrm = new Float32Array([...tilt(30), ...tilt(-10), 1, 0, 0]);
    reliefNormals(pos, nrm, 1, RELIEF_CAP_FROM_DEG, RELIEF_CAP_TO_DEG);
    expect([...nrm.slice(0, 3)]).toEqual([...nrm.slice(3, 6)]);
    expect((Math.atan2(nrm[0], nrm[2]) * 180) / Math.PI).toBeCloseTo(10, 4); // the mean of the two facets
    for (let k = 0; k < 3; k++) expect(nrm[6 + k]).toBeCloseTo(pos[6 + k], 6); // radial inside the cap
    const half = new Float32Array([...tilt(30), ...tilt(-10), 1, 0, 0]);
    reliefNormals(pos, half, 0.5, RELIEF_CAP_FROM_DEG, RELIEF_CAP_TO_DEG);
    const lean = (Math.atan2(half[0], half[2]) * 180) / Math.PI;
    expect(lean).toBeGreaterThan(0);
    expect(lean).toBeLessThan(10);
    const none = new Float32Array([...tilt(30), ...tilt(-10), 1, 0, 0]);
    reliefNormals(pos, none, 0, RELIEF_CAP_FROM_DEG, RELIEF_CAP_TO_DEG);
    expect([...none.slice(0, 3)].map((x) => +x.toFixed(6))).toEqual(corner);
  });
  it('the 8k model is turned a quarter turn into the model frame; phones never get it while a lighter model is present', () => {
    expect(MODEL_YAW_RAD[GLOBE_8K]).toBeCloseTo(Math.PI / 2, 12);
    expect(MODEL_YAW_RAD[GLOBE_FULL]).toBeUndefined();
    expect(globeAsset([GLOBE_8K, GLOBE_FULL], true)).toBe(GLOBE_FULL);
    expect(globeAsset([GLOBE_8K, GLOBE_FULL, GLOBE_LITE], true)).toBe(GLOBE_LITE);
    expect(globeAsset([GLOBE_8K], true)).toBe(GLOBE_8K);
    expect(globeAsset([GLOBE_8K, GLOBE_FULL], false, 'compact')).toBe(GLOBE_FULL);
    expect(globeAsset([GLOBE_8K], false, 'compact')).toBe(GLOBE_8K);
  });
  it('a device that gets the 8k model opens on the compact one and brings the 8k one in after', () => {
    expect(globePlan([GLOBE_8K, GLOBE_FULL, GLOBE_LITE], false)).toEqual({ first: GLOBE_FULL, then: GLOBE_8K });
    expect(globePlan([GLOBE_8K, GLOBE_FULL, GLOBE_LITE], true)).toEqual({ first: GLOBE_LITE, then: null });
    expect(globePlan([GLOBE_8K, GLOBE_FULL], false, 'compact')).toEqual({ first: GLOBE_FULL, then: null });
    expect(globePlan([GLOBE_FULL], false)).toEqual({ first: GLOBE_FULL, then: null });
    expect(globePlan([GLOBE_8K], false)).toEqual({ first: GLOBE_8K, then: null });
  });
});

// A clean clone has only the files git tracks: the compact model must be one of them (so the globe draws), and the 8k model
// (81.5 MB, over the 50 MB kept in git) must not be.
const tracked = (() => {
  try {
    return execSync('git ls-files public/globe', { cwd: resolve(__dirname, '../..'), encoding: 'utf8' }).split('\n').filter(Boolean).map((f) => f.replace('public/globe/', ''));
  } catch {
    return null; // not a git checkout (an exported tree): nothing to check
  }
})();
describe.skipIf(tracked === null)('a clean clone', () => {
  it('has the compact Moon model in git and not the 8k one; its globe plan draws the compact model with nothing to bring in', () => {
    expect(tracked).toContain(GLOBE_FULL);
    expect(tracked).not.toContain(GLOBE_8K);
    expect(tracked!.filter((f) => f.endsWith('.glb'))).toEqual([GLOBE_FULL]);
    expect(globePlan(tracked!.filter((f) => f.endsWith('.glb')), false)).toEqual({ first: GLOBE_FULL, then: null });
    expect(globePlan(tracked!.filter((f) => f.endsWith('.glb')), true)).toEqual({ first: GLOBE_FULL, then: null });
  });
});
