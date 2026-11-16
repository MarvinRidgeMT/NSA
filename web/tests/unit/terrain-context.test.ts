import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { basisFromLongitude, gridDirection } from '../../src/bundle/frame';
import { assembleContext, decodeHorizonDeg, farHorizonFromBundle, gridAngles, horizonW, sampleHorizonDeg, sunVisibility, TerrainContextError, validateContextMeta } from '../../src/bundle/terrainContext';

const meta = (over: Record<string, unknown> = {}) => ({
  schema: 'polaris-terrain-context-v1', status: 'VISUAL', numericalAuthority: false, label: 'TERRAIN CONTEXT · VISUAL', datasetId: 't', displayReachM: 14000,
  local: { n: 5, spacingM: 5, originX: -10, originY: -10, cropValuesSha256: 'x' },
  regional: { file: 'r.bin', sha256: 'x', n: 3, spacingM: 80, originX: -80, originY: -80, product: 'p', source: 's' },
  horizon: { azimuths: 8, encoding: { minDeg: -3, stepDeg: 0.05 }, local: { file: 'l', sha256: 'x', m: 3, spacingM: 10, originX: -10, originY: -10 }, regional: { file: 'g', sha256: 'x', m: 3, spacingM: 80, originX: -80, originY: -80 } },
  limitations: ['display only'],
  ...over,
});

describe('terrain context pack (display only)', () => {
  it('accepts a VISUAL pack and refuses one that claims numerical authority or is not VISUAL', () => {
    expect(validateContextMeta(meta()).horizon.azimuths).toBe(8);
    expect(() => validateContextMeta(meta({ numericalAuthority: true }))).toThrow(TerrainContextError);
    expect(() => validateContextMeta(meta({ status: 'SOURCE' }))).toThrow(TerrainContextError);
    expect(() => validateContextMeta(meta({ schema: 'other' }))).toThrow(TerrainContextError);
  });

  it('refuses truncated binaries (sizes must match the metadata)', () => {
    const m = validateContextMeta(meta());
    const ok = assembleContext(m, new ArrayBuffer(3 * 3 * 4), new ArrayBuffer(8 * 9), new ArrayBuffer(8 * 9));
    expect(ok.regional).toHaveLength(9);
    expect(() => assembleContext(m, new ArrayBuffer(3 * 3 * 4 - 4), new ArrayBuffer(8 * 9), new ArrayBuffer(8 * 9))).toThrow(/regional DEM size/);
    expect(() => assembleContext(m, new ArrayBuffer(3 * 3 * 4), new ArrayBuffer(8 * 9 - 1), new ArrayBuffer(8 * 9))).toThrow(/local horizon/);
  });

  it('grid angle convention: +y is 0°, +x is 90°, matching tools/terrain (index k → 360·k/K from +y toward +x)', () => {
    expect(gridAngles([0, 1, 0]).thetaDeg).toBeCloseTo(0, 9);
    expect(gridAngles([1, 0, 0]).thetaDeg).toBeCloseTo(90, 9);
    expect(gridAngles([0, -1, 0]).thetaDeg).toBeCloseTo(180, 9);
    expect(gridAngles([-1, 0, 0]).thetaDeg).toBeCloseTo(270, 9);
    expect(gridAngles([0, Math.cos(0.025), Math.sin(0.025)]).elDeg).toBeCloseTo((0.025 * 180) / Math.PI, 9);
    // slice k sits at w = (k + 0.5) / K
    expect(horizonW(90, 8)).toBeCloseTo((2 + 0.5) / 8, 12);
    expect(horizonW(360, 8)).toBeCloseTo(0.5 / 8, 12);
  });

  it('a local azimuth goes through the site basis before the lookup (JPL azimuth is local, the map is in grid axes)', () => {
    const b = basisFromLongitude(-156.32023); // Site04 ROI3
    const north = gridAngles(gridDirection(b, 0, 0)).thetaDeg;
    const east = gridAngles(gridDirection(b, 90, 0)).thetaDeg;
    expect(((east - north + 360) % 360)).toBeCloseTo(90, 6); // local east is 90° clockwise of local north in the (+y → +x) grid angle
    expect(north).toBeCloseTo((-156.32023 + 360) % 360, 4);    // local north points along the meridian toward the pole-opposite side
  });

  it('CPU reference lookup interpolates between azimuth slices and wraps', () => {
    const m = 1, K = 4;
    const tex = new Uint8Array([60, 100, 60, 80]); // degrees: 0, 2, 0, 1
    expect(decodeHorizonDeg(100)).toBeCloseTo(2, 12);
    expect(sampleHorizonDeg(tex, m, K, 0, 0, 90)).toBeCloseTo(2, 12);
    expect(sampleHorizonDeg(tex, m, K, 0, 0, 45)).toBeCloseTo(1, 12);
    expect(sampleHorizonDeg(tex, m, K, 0, 0, 315)).toBeCloseTo(0.5, 12); // between slice 3 (1°) and slice 0 (0°)
  });

  it('visibility model: dark below the horizon, lit above, half at the horizon', () => {
    expect(sunVisibility(1, 0.5)).toBe(0);
    expect(sunVisibility(1, 1.5)).toBe(1);
    expect(sunVisibility(1, 1)).toBeCloseTo(0.5, 12);
  });

  it('far horizon comes from the bundle only when its controlling terrain is beyond the displayed crops', () => {
    const az = [0, 90, 180, 270];
    const el = [0.5, 1.8, null, -1];
    expect(farHorizonFromBundle(az, el, [200, 128000, 50, 90000], 92, 14000)).toBe(1.8);
    expect(farHorizonFromBundle(az, el, [200, 128000, 50, 90000], 2, 14000)).toBeNull(); // 200 m: already in the horizon map
    expect(farHorizonFromBundle(az, el, [200, 128000, 50, 90000], 181, 14000)).toBeNull(); // no skyline value
    expect(farHorizonFromBundle(az, el, null, 92, 14000)).toBeNull(); // bundle does not say: never guessed
  });
});

describe('generated packs on disk (when present)', () => {
  const dir = resolve(__dirname, '../../public/context');
  const ids = ['site04_roi3', 'site01_roi6', 'site04_roi4'].filter((id) => existsSync(`${dir}/${id}/context.json`));
  it.skipIf(ids.length === 0).each(ids.map((id) => [id]))('%s: metadata valid, sizes match, built for the ROI export crop', (id) => {
    const m = validateContextMeta(JSON.parse(readFileSync(`${dir}/${id}/context.json`, 'utf8')));
    const buf = (f: string) => { const b = readFileSync(`${dir}/${id}/${f}`); return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength); };
    const c = assembleContext(m, buf(m.regional.file), buf(m.horizon.local.file), buf(m.horizon.regional.file));
    expect(c.meta.datasetId).toBe(id);
    const exportPath = resolve(__dirname, '../../public/bundles/polaris-x5d-roi-2026-11-14-v2.json');
    if (existsSync(exportPath)) {
      const ds = JSON.parse(readFileSync(exportPath, 'utf8')).datasets.find((d: { siteId: string }) => d.siteId === id);
      expect(m.local.cropValuesSha256).toBe(ds.dem.cropValuesSha256);
    }
    expect(Number.isFinite(c.regional[0])).toBe(true);
    if (m.mid) {
      const md = assembleContext(m, buf(m.regional.file), buf(m.horizon.local.file), buf(m.horizon.regional.file), buf(m.mid.file), buf(m.horizon.mid!.file));
      expect(md.mid).toHaveLength(m.mid.n * m.mid.n);
      expect(m.mid.spacingM).toBe(5); // L1 is full-resolution PGDA 78 5 m data (1601², 8 km) since 15 Nov 22:00
      if (m.localDisplay) {
        const withDisplay = assembleContext(m, buf(m.regional.file), buf(m.horizon.local.file), buf(m.horizon.regional.file), buf(m.mid.file), buf(m.horizon.mid!.file), buf(m.localDisplay.file));
        expect(withDisplay.localDisplay).toHaveLength(m.local.n * m.local.n);
        expect(m.localDisplay.licence).toBe('CC-BY-4.0');
        expect(m.localDisplay.coverageFraction).toBeGreaterThan(0);
      }
      // L1 must enclose the 5 m crop and lie inside the 80 m crop
      const e = (g: { originX: number; originY: number; spacingM: number; n: number }) => [g.originX, g.originX + (g.n - 1) * g.spacingM, g.originY, g.originY + (g.n - 1) * g.spacingM];
      const [l0x0, l0x1, l0y0, l0y1] = e(m.local);
      const [l1x0, l1x1, l1y0, l1y1] = e(m.mid);
      const [l2x0, l2x1, l2y0, l2y1] = e(m.regional);
      expect(l1x0 < l0x0 && l1x1 > l0x1 && l1y0 < l0y0 && l1y1 > l0y1).toBe(true);
      expect(l2x0 < l1x0 && l2x1 > l1x1 && l2y0 < l1y0 && l2y1 > l1y1).toBe(true);
    }
  });
});

describe('meshStride (display mesh density only)', () => {
  it('draws every 5 m node on a GPU and ~401² on a software renderer, always on whole nodes', async () => {
    const { meshStride } = await import('../../src/three/TerrainSurface');
    expect(meshStride(1601, false)).toBe(1);
    expect(meshStride(1601, true)).toBe(4);
    expect(meshStride(401, true)).toBe(1);
    expect(1600 % meshStride(1601, true)).toBe(0);
  });
});
