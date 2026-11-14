import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { latLonToXY, lut, toPercent, xyToLatLon, type Pgda69Meta } from '../../src/layers/pgda69';

const meta: Pgda69Meta = JSON.parse(readFileSync(resolve(__dirname, '../../public/layers/pgda69/pgda69.json'), 'utf8'));

describe('PGDA 69 layer', () => {
  it('projection matches the bundle grid (Site01 tile centre -> projectedMeters)', () => {
    const [x, y] = latLonToXY(-89.4632, -137.49);
    expect(x).toBeCloseTo(-10999.14, 0);
    expect(y).toBeCloseTo(-11999.26, 0);
    const [lat, lon] = xyToLatLon(x, y);
    expect(lat).toBeCloseTo(-89.4632, 9);
    expect(lon).toBeCloseTo(-137.49, 9);
  });
  it('ROI centroids round-trip through the projection', () => {
    for (const r of meta.rois) {
      const [x, y] = latLonToXY(r.lat, r.lonE);
      expect(Math.hypot(x - r.centroidXY[0], y - r.centroidXY[1])).toBeLessThan(1);
    }
  });
  it('has the 17 PGDA 78 regions for Sites 01/04/07/11 with finite stats', () => {
    expect(meta.rois.length).toBe(17);
    expect(new Set(meta.rois.map((r) => r.site))).toEqual(new Set(['Site01', 'Site04', 'Site07', 'Site11']));
    for (const r of meta.rois) {
      expect(r.sun.n60mPixels).toBeGreaterThan(0);
      expect(r.sun.mean!).toBeGreaterThanOrEqual(r.sun.min!);
      expect(r.sun.mean!).toBeLessThanOrEqual(r.sun.max!);
      expect(r.sun.max!).toBeLessThanOrEqual(88.5); // map maximum is 22111 * 4e-5 = 88.44 %
    }
  });
  it('labels itself as NASA reference data with pinned sources', () => {
    expect(meta.kind).toBe('NASA_REFERENCE_PRODUCT');
    expect(meta.sources.every((s) => /^[0-9a-f]{64}$/.test(s.sha256))).toBe(true);
    expect(meta.citation).toMatch(/Mazarico/);
  });
  it('decodes the 8-bit encoding and marks no-data', () => {
    expect(toPercent(250, meta.encoding)).toBeCloseTo(100, 9);
    expect(toPercent(125, meta.encoding)).toBeCloseTo(50, 9);
    expect(toPercent(255, meta.encoding)).toBeNull();
    const L = lut('sun');
    expect(Array.from(L.slice(0, 3))).toEqual([10, 12, 18]);
    expect(L[255 * 4 + 3]).toBe(255);
  });
});
