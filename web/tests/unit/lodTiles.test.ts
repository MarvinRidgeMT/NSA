import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import {
  MAX_TILE_BYTES,
  distanceToTile,
  drawSet,
  indexTiles,
  keyOf,
  selectTiles,
  validateLodManifest,
  type LodManifest,
  type LodTileMeta,
} from '../../src/bundle/lodTiles';
import { tileGeometry } from '../../src/three/LodTerrain';

/** 5D Phase 9.4: tile selection for the display-only near-field quadtree (same layout as tools/terrain/build_lod_tiles.py). */
const LEVELS = 5;
const CELLS = 175;
const STORED = CELLS + 1 + 2;
function synthManifest(): LodManifest {
  const tiles: LodTileMeta[] = [];
  const levels = [];
  for (let l = 0; l < LEVELS; l++) {
    const n = 2 ** l;
    const w = 14000 / n;
    levels.push({ level: l, spacingM: 5 * 2 ** (LEVELS - 1 - l), tilesPerSide: n, tileWidthM: w, boxPixels: 1 });
    for (let iy = 0; iy < n; iy++)
      for (let ix = 0; ix < n; ix++)
        tiles.push({ level: l, ix, iy, file: `L${l}_${ix}_${iy}.f32`, bytes: STORED * STORED * 4, sha256: '0'.repeat(64),
          bounds: { xmin: -7000 + ix * w, xmax: -7000 + (ix + 1) * w, ymin: -7000 + iy * w, ymax: -7000 + (iy + 1) * w }, zMin: 0, zMax: 50, nanNodes: 0 });
  }
  return validateLodManifest({
    schema: 'polaris-lod-tiles-v1', status: 'VISUAL', numericalAuthority: false, label: 'x', datasetId: 'synthetic', siteName: 'synthetic',
    halfExtentM: 7000, sitePointProjectedM: { x: 0, y: 0 }, source: { product: 'synthetic', url: 'https://example.invalid/x.tif', sha256: 'a'.repeat(64), pixelM: 5 },
    levels, area: { xmin: -7000, xmax: 7000, ymin: -7000, ymax: 7000 }, tileGrid: { cells: CELLS, nodes: CELLS + 1, apron: 1, stored: STORED, dtype: 'float32-le' },
    tiles, rule: '', limitations: [],
  });
}
const M = synthManifest();
const IDX = indexTiles(M);

/** Exact cover check on a 25 m sample lattice: every sample point lies in exactly one tile (interiors), no gap, no overlap. */
function coverCounts(ts: readonly LodTileMeta[], step = 125) {
  let gaps = 0;
  let overlaps = 0;
  for (let y = -7000 + step / 2; y < 7000; y += step)
    for (let x = -7000 + step / 2; x < 7000; x += step) {
      const c = ts.filter((t) => x > t.bounds.xmin && x < t.bounds.xmax && y > t.bounds.ymin && y < t.bounds.ymax).length;
      if (c === 0) gaps++;
      if (c > 1) overlaps++;
    }
  return { gaps, overlaps };
}
const area = (ts: readonly LodTileMeta[]) => ts.reduce((s, t) => s + (t.bounds.xmax - t.bounds.xmin) * (t.bounds.ymax - t.bounds.ymin), 0);

describe('near-field LOD tile selection', () => {
  it('a far camera draws only the root; a camera on the ground draws 5 m tiles under it', () => {
    expect(selectTiles(M, { x: 0, y: 0, z: 200_000 }).map(keyOf)).toEqual(['0/0/0']);
    const near = selectTiles(M, { x: 10, y: -20, z: 30 });
    const under = near.find((t) => t.bounds.xmin <= 10 && 10 <= t.bounds.xmax && t.bounds.ymin <= -20 && -20 <= t.bounds.ymax)!;
    expect(under.level).toBe(LEVELS - 1);
    expect(M.levels[under.level].spacingM).toBe(5);
  });

  it('every selected tile has the right level for its distance: not split, and its parent was split', () => {
    const f = 1.2;
    for (const cam of [{ x: 0, y: 0, z: 40 }, { x: 3000, y: -5000, z: 1500 }, { x: -9000, y: 9000, z: 4000 }, { x: 500, y: 500, z: 12_000 }]) {
      const sel = selectTiles(M, cam, f);
      for (const t of sel) {
        const w = t.bounds.xmax - t.bounds.xmin;
        if (t.level < LEVELS - 1) expect(distanceToTile(cam, t)).toBeGreaterThanOrEqual(f * w);
        if (t.level > 0) {
          const p = IDX.get(`${t.level - 1}/${t.ix >> 1}/${t.iy >> 1}`)!;
          expect(distanceToTile(cam, p)).toBeLessThan(f * (p.bounds.xmax - p.bounds.xmin));
        }
      }
    }
  });

  it('level never increases with distance from the camera (coarser farther away)', () => {
    const cam = { x: -1200, y: 800, z: 300 };
    const sel = selectTiles(M, cam).sort((a, b) => distanceToTile(cam, a) - distanceToTile(cam, b));
    // a tile at distance d is never finer than a tile closer than d / 2 (the split rule halves the width per level)
    for (const a of sel) for (const b of sel) if (distanceToTile(cam, b) > 2 * distanceToTile(cam, a) + 1e-6) expect(b.level).toBeLessThanOrEqual(a.level);
    expect(new Set(sel.map((t) => t.level)).size).toBeGreaterThan(2);
  });

  it('no gaps and no overlaps for any camera, and the area is covered exactly', () => {
    for (const cam of [{ x: 0, y: 0, z: 5 }, { x: 6999, y: -6999, z: 10 }, { x: 2000, y: 3000, z: 900 }, { x: 0, y: 0, z: 1e6 }]) {
      const sel = selectTiles(M, cam);
      expect(area(sel)).toBeCloseTo(14000 * 14000, 3);
      expect(coverCounts(sel)).toEqual({ gaps: 0, overlaps: 0 });
    }
  });

  it('while tiles stream in, ancestors stand in: still no gaps and no overlaps', () => {
    const sel = selectTiles(M, { x: 100, y: 100, z: 20 });
    const loadedSome = new Set(['0/0/0', '1/1/1', '2/2/2', ...sel.filter((_, i) => i % 3 === 0).map(keyOf)]);
    for (const loaded of [new Set(['0/0/0']), loadedSome, new Set(sel.map(keyOf))]) {
      const d = drawSet(sel, (k) => loaded.has(k), IDX);
      expect(d.every((t) => loaded.has(keyOf(t)))).toBe(true);
      expect(coverCounts(d)).toEqual({ gaps: 0, overlaps: 0 });
    }
    expect(drawSet(sel, () => true, IDX).map(keyOf).sort()).toEqual(sel.map(keyOf).sort());
  });

  it('the manifest validator rejects a tile over 2 MB, a missing tile and a numerically authoritative pack', () => {
    const j = JSON.parse(JSON.stringify(M));
    j.tiles[3].bytes = MAX_TILE_BYTES + 4;
    expect(() => validateLodManifest(j)).toThrow(/2 MB/);
    const k = JSON.parse(JSON.stringify(M));
    k.tiles.pop();
    expect(() => validateLodManifest(k)).toThrow(/missing tile/);
    expect(() => validateLodManifest({ ...JSON.parse(JSON.stringify(M)), numericalAuthority: true })).toThrow(/VISUAL/);
  });

  it('a tile mesh skips NaN nodes (nothing is filled in) and keeps true-scale heights', () => {
    const t = M.tiles.find((x) => x.level === LEVELS - 1)!;
    const z = new Float32Array(STORED * STORED).fill(1740);
    z[(1 + 10) * STORED + (1 + 10)] = NaN;
    const g = tileGeometry(M, t, z, { x: 0, y: 0, ground: 1700 });
    const full = tileGeometry(M, t, new Float32Array(STORED * STORED).fill(1740), { x: 0, y: 0, ground: 1700 });
    expect(full.index!.count - g.index!.count).toBe(4 * 6 + 0); // the 4 quads around the NaN node, 2 triangles each
    expect(g.getAttribute('position').getY(0)).toBeCloseTo(40, 4);
    expect(g.getAttribute('position').getX(1) - g.getAttribute('position').getX(0)).toBeCloseTo(5, 6);
  });
});

// the built tiles (git-ignored; tools/terrain/build_lod_tiles.py). Skipped when absent.
const here = dirname(fileURLToPath(import.meta.url));
const lodDir = resolve(here, '../../public/context/lod');
const sites = existsSync(lodDir) ? readdirSync(lodDir).filter((d) => existsSync(resolve(lodDir, d, 'manifest.json'))) : [];
describe.skipIf(!sites.length)('built near-field LOD manifests', () => {
  for (const s of sites) {
    it(`${s}: valid, complete quadtree, every tile ≤ 2 MB in the manifest and on disk`, () => {
      const m = validateLodManifest(JSON.parse(readFileSync(resolve(lodDir, s, 'manifest.json'), 'utf8')));
      expect(m.halfExtentM).toBe(7000);
      expect(m.levels.at(-1)!.spacingM).toBe(5);
      for (const t of m.tiles) {
        expect(t.bytes).toBeLessThanOrEqual(MAX_TILE_BYTES);
        expect(statSync(resolve(lodDir, s, t.file)).size).toBe(t.bytes);
      }
      expect(coverCounts(selectTiles(m, { x: m.area.xmin + 50, y: m.area.ymin + 50, z: 1800 }).map((t) => ({ ...t, bounds: { xmin: t.bounds.xmin - m.area.xmin - 7000, xmax: t.bounds.xmax - m.area.xmin - 7000, ymin: t.bounds.ymin - m.area.ymin - 7000, ymax: t.bounds.ymax - m.area.ymin - 7000 } })))).toEqual({ gaps: 0, overlaps: 0 });
    });
  }
});
