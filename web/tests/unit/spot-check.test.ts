import { createHash } from 'node:crypto';
import { existsSync, readFileSync, statSync } from 'node:fs';
import { resolve } from 'node:path';
import { gunzipSync } from 'node:zlib';
import { describe, expect, it } from 'vitest';
import { moonDir } from '../../src/simple/globeMath';
import {
  cellOf,
  decodeTile,
  dirToLatLon,
  distanceM,
  fmtDistance,
  fmtLatLon,
  lookupCell,
  matchDistanceM,
  nearestSite,
  parseLatLon,
  pct1,
  splitPair,
  type SpotManifest,
  type Tile,
  type TileGetter,
} from '../../src/simple/spotCheck';

/**
 * S13 "Check a spot". The expected cells and values are the manifest's check points, which scripts/build_pgda69_web.py read
 * from the original NASA TIFs with rasterio and pyproj (scripts/test_pgda69_web.py compares every shipped cell with the
 * TIFs). Here the page's own projection, cell index and tile decoder must land on the same cells and values.
 */
const dir = resolve(__dirname, '../../public/pgda69-spot');
const m = JSON.parse(readFileSync(resolve(dir, 'manifest.json'), 'utf8')) as SpotManifest;
const bundle = JSON.parse(readFileSync(resolve(__dirname, '../../../data/viewer/polaris-x5d-roi-2026-11-14-v2.json'), 'utf8')) as {
  datasets: { siteId: string; site: { name: string; latitudePlanetocentricDeg: number; longitudeEastDeg: number }; derived: { scenarios: { kind?: string; parameters?: Record<string, unknown> }[] } }[];
};

const cache = new Map<string, Tile>();
const get: TileGetter = async (r, c) => {
  const key = `${r},${c}`;
  let t = cache.get(key);
  if (!t) {
    const file = m.tiles.find((x) => x.r === r && x.c === c)!.file;
    t = decodeTile(new Uint8Array(gunzipSync(readFileSync(resolve(dir, file)))), m.copy.tilePx);
    cache.set(key, t);
  }
  return t;
};

describe('S13 web copy of NASA PGDA 69', () => {
  it('ships every tile the manifest lists, byte for byte, inside the size budget', () => {
    let total = 0;
    for (const t of m.tiles) {
      const bytes = readFileSync(resolve(dir, t.file));
      expect(createHash('sha256').update(bytes).digest('hex'), t.file).toBe(t.sha256);
      total += bytes.length;
    }
    expect(m.tiles.length).toBe((m.copy.widthPx / m.copy.tilePx) * (m.copy.heightPx / m.copy.tilePx));
    expect(total).toBe(m.copy.totalTileBytes);
    // "small enough to ship": under 10 MB with the manifest
    expect(total + statSync(resolve(dir, 'manifest.json')).size).toBeLessThan(10 * 1000 * 1000);
  });

  it('keeps the NASA TIFs themselves out of the web folder', () => {
    expect(existsSync(resolve(dir, m.sources[0].file))).toBe(false);
    expect(m.sources.every((s) => /^[0-9a-f]{64}$/.test(s.sha256))).toBe(true);
  });

  it('the page’s projection lands on the same cell as pyproj at every check point', () => {
    expect(m.checks.length).toBeGreaterThan(200);
    for (const k of m.checks) {
      const c = cellOf(m, k.lat, k.lonE);
      if (k.inCopy) expect(c, k.name).toEqual({ kind: 'cell', row: k.row, col: k.col });
      else expect(c.kind, k.name).toBe('outside-copy');
    }
    expect(m.checks.some((k) => !k.inCopy)).toBe(true);
  });

  it('the decoded cell and its 3 × 3 block equal the values read from the TIFs', async () => {
    let n = 0;
    for (const k of m.checks) {
      if (!k.inCopy) continue;
      // check points on the copy's outer ring have neighbours outside it; the TIF block there is not what the page shows
      const edge = k.row - m.copy.row0 < 1 || k.col - m.copy.col0 < 1 || k.row - m.copy.row0 > m.copy.heightPx - 2 || k.col - m.copy.col0 > m.copy.widthPx - 2;
      const v = await lookupCell(m, get, k.row, k.col);
      expect(v.sun.raw, k.name).toBe(k.sunRaw);
      expect(v.earth.raw, k.name).toBe(k.earthRaw);
      if (!edge) {
        expect([v.sun.min, v.sun.max, v.sun.cells], k.name).toEqual([...k.sun3x3, 9]);
        expect([v.earth.min, v.earth.max, v.earth.cells], k.name).toEqual([...k.earth3x3, 9]);
      }
      n++;
    }
    expect(n).toBeGreaterThan(100);
  });

  it('the three sites of the bundle are check points, in the copy, and no warning threshold exists anywhere in the manifest', async () => {
    expect(JSON.stringify(m)).not.toMatch(/variationWarn|threshold/i);
    for (const d of bundle.datasets) {
      const k = m.checks.find((x) => x.siteId === d.siteId)!;
      expect(k, d.siteId).toBeTruthy();
      expect([k.lat, k.lonE]).toEqual([d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg]);
      const c = cellOf(m, k.lat, k.lonE);
      expect(c.kind).toBe('cell');
      const v = await lookupCell(m, get, k.row, k.col);
      expect(pct1(m, v.sun.raw)).toBe((k.sunRaw * m.grid.scale * 100).toFixed(1));
      expect([pct1(m, v.sun.min), pct1(m, v.sun.max)]).toEqual(k.sun3x3.map((r) => (r * m.grid.scale * 100).toFixed(1)));
    }
  });

  it('a cell on the edge of the copy reports how many neighbours it has', async () => {
    const v = await lookupCell(m, get, m.copy.row0, m.copy.col0);
    expect(v.sun.cells).toBe(4);
    await expect(lookupCell(m, get, m.copy.row0 - 1, m.copy.col0)).rejects.toThrow();
  });

  it('says which points are off NASA’s map and which are only off the web copy', () => {
    expect(cellOf(m, -84.99, 10).kind).toBe('outside-map');
    expect(cellOf(m, 12, 10).kind).toBe('outside-map');
    expect(cellOf(m, m.grid.fullEdgeLatDeg - 0.01, 45).kind).toBe('outside-copy');
    expect(cellOf(m, m.copy.inscribedLatDeg + 0.01, 0).kind).toBe('outside-copy');
    // just inside the copy's inscribed circle, on a grid axis and on a diagonal
    for (const lon of [0, 45, 90, 137, 180, -90]) expect(cellOf(m, m.copy.inscribedLatDeg - 0.001, lon).kind, String(lon)).toBe('cell');
    expect(cellOf(m, -90, 0).kind).toBe('cell');
  });
});

describe('S13 input', () => {
  it('reads decimal degrees, signs and hemisphere letters', () => {
    expect(parseLatLon('-89.5', '-137.4')).toEqual({ ok: true, lat: -89.5, lon: -137.4 });
    expect(parseLatLon('−89.5°', '137.4 W')).toEqual({ ok: true, lat: -89.5, lon: -137.4 });
    expect(parseLatLon('89.5 S', '222.6')).toEqual({ ok: true, lat: -89.5, lon: 222.6 - 360 });
    expect(parseLatLon(' -90 ', '180')).toEqual({ ok: true, lat: -90, lon: 180 });
  });
  it('rejects what is not a coordinate, and says which box', () => {
    expect(parseLatLon('', '')).toMatchObject({ ok: false, field: 'both' });
    expect(parseLatLon('abc', '10')).toMatchObject({ ok: false, field: 'lat' });
    expect(parseLatLon('-89', '')).toMatchObject({ ok: false, field: 'lon' });
    expect(parseLatLon('-91', '10')).toMatchObject({ ok: false, field: 'lat' });
    expect(parseLatLon('-89', '400')).toMatchObject({ ok: false, field: 'lon' });
    expect(parseLatLon('-89 S', '10')).toMatchObject({ ok: false, field: 'lat' });
    expect(parseLatLon('89 E', '10')).toMatchObject({ ok: false, field: 'lat' });
    expect(parseLatLon('1e5', '10')).toMatchObject({ ok: false, field: 'lat' });
  });
  it('splits a pasted "lat, lon"', () => {
    expect(splitPair('-89.78012, -156.32023')).toEqual(['-89.78012', '-156.32023']);
    expect(splitPair('  -89.78012 -156.32023 ')).toEqual(['-89.78012', '-156.32023']);
    expect(splitPair('89.78 S; 156.32 W')).toEqual(['89.78 S', '156.32 W']);
    expect(splitPair('-89.78012')).toBeNull();
    expect(splitPair('hello, world')).toBeNull();
    expect(splitPair('1, 2, 3')).toBeNull();
  });
});

describe('S13 distances and our own results', () => {
  const sites = bundle.datasets.map((d) => ({ id: d.siteId, name: d.site.name, lat: d.site.latitudePlanetocentricDeg, lon: d.site.longitudeEastDeg }));
  it('takes the match distance from the bundle’s own position steps', () => {
    const offsets = bundle.datasets.flatMap((d) => d.derived.scenarios).filter((s) => s.kind === 'position_offset');
    expect(offsets.length).toBeGreaterThan(0);
    const step = Math.min(...offsets.map((s) => Math.hypot(Number(s.parameters!.east_m), Number(s.parameters!.north_m))));
    expect(matchDistanceM(bundle.datasets.flatMap((d) => d.derived.scenarios))).toEqual({ stepM: step, withinM: step / 2 });
    expect(matchDistanceM([])).toBeNull();
    expect(matchDistanceM(undefined)).toBeNull();
  });
  it('measures great-circle distance on the map’s sphere', () => {
    const R = m.grid.radiusM;
    expect(distanceM(R, -90, 0, -89, 0)).toBeCloseTo((R * Math.PI) / 180, 6);
    expect(distanceM(R, -89, 0, -89, 180)).toBeCloseTo((2 * R * Math.PI) / 180, 6);
    expect(distanceM(R, -89.5, 20, -89.5, 20)).toBe(0);
    // agrees with the map projection near the pole (true scale there): grid distance between two of the bundle's sites
    const [a, b] = sites;
    const ka = m.checks.find((k) => k.siteId === a.id) as unknown as { xM: number; yM: number };
    const kb = m.checks.find((k) => k.siteId === b.id) as unknown as { xM: number; yM: number };
    const grid = Math.hypot(ka.xM - kb.xM, ka.yM - kb.yM);
    expect(Math.abs(distanceM(R, a.lat, a.lon, b.lat, b.lon) - grid) / grid).toBeLessThan(1e-4);
  });
  it('finds the nearest computed site', () => {
    for (const s of sites) expect(nearestSite(m.grid.radiusM, sites, s.lat, s.lon)).toEqual({ site: s, distM: 0 });
    expect(nearestSite(m.grid.radiusM, [], -89, 0)).toBeNull();
  });
  it('formats without inventing digits', () => {
    expect(fmtDistance(0)).toBe('0 m');
    expect(fmtDistance(49.6)).toBe('50 m');
    expect(fmtDistance(999.4)).toBe('999 m');
    expect(fmtDistance(1234)).toBe('1.2 km');
    expect(fmtLatLon(-89.78012, -156.32023)).toBe('89.7801° S, 156.3202° W');
    expect(fmtLatLon(-90, 12)).toBe('90.0000° S, 12.0000° E');
  });
  it('turns a point of the globe back into its latitude and longitude', () => {
    for (const [lat, lon] of [[-89.78012, -156.32023], [-85, 10], [-60, 179.5], [12, -90]]) {
      const p = dirToLatLon(moonDir(lat, lon));
      expect(p.lat).toBeCloseTo(lat, 9);
      expect(p.lon).toBeCloseTo(lon, 9);
    }
  });
});
