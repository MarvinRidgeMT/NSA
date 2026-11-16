/**
 * Mesh arrays of one near-field LOD tile (5D Phase 9.4), as plain typed arrays so they can be built in a Web Worker and
 * transferred. DISPLAY ONLY. Axes as in Scene3D: grid (x, y, z up) -> three.js (x, z, −y), observer at the origin, 1 unit = 1 m.
 *
 *  - vertices: the tile's (cells + 1)² nodes, then 4 × (cells + 1) skirt vertices hanging 4 node spacings below the edges
 *    (they hide cracks where a finer tile meets a coarser one);
 *  - normals: central differences over the stored one-node apron (one-sided next to NaN), so neighbouring tiles shade alike;
 *  - triangles: a quad is drawn only when its four nodes are finite. NaN nodes (outside the PGDA 78 tile) are never filled.
 */
export interface TileGrid { cells: number; nodes: number; stored: number; apron: number }
export interface TileMeshArrays { position: Float32Array; normal: Float32Array; index: Uint16Array | Uint32Array; sphere: [number, number, number, number] }

export function tileMeshArrays(g: TileGrid, bounds: { xmin: number; xmax: number; ymin: number; ymax: number }, zMin: number | null, z: Float32Array, obs: { x: number; y: number; ground: number }): TileMeshArrays {
  const n = g.nodes;
  const st = g.stored;
  const a = g.apron;
  const sp = (bounds.xmax - bounds.xmin) / g.cells;
  const skirt = 4 * sp;
  const nv = n * n + 4 * n;
  const pos = new Float32Array(nv * 3);
  const nor = new Float32Array(nv * 3);
  const fallback = (zMin ?? obs.ground) - obs.ground;
  const x0 = bounds.xmin - obs.x;
  const y0 = bounds.ymin - obs.y;
  const inv2 = 1 / (2 * sp);
  const inv1 = 1 / sp;
  const fin = (v: number) => v === v; // finite heights only: the builder writes NaN, never ±Infinity
  for (let j = 0; j < n; j++) {
    const row = (j + a) * st + a;
    for (let i = 0; i < n; i++) {
      const s = row + i;
      const h = z[s];
      const k = (j * n + i) * 3;
      pos[k] = x0 + i * sp;
      pos[k + 1] = fin(h) ? h - obs.ground : fallback;
      pos[k + 2] = -(y0 + j * sp);
      const e = z[s + 1];
      const w = z[s - 1];
      const nn = z[s + st];
      const so = z[s - st];
      let gx = 0;
      if (fin(e) && fin(w)) gx = (e - w) * inv2;
      else if (fin(h) && fin(e)) gx = (e - h) * inv1;
      else if (fin(h) && fin(w)) gx = (h - w) * inv1;
      let gy = 0;
      if (fin(nn) && fin(so)) gy = (nn - so) * inv2;
      else if (fin(h) && fin(nn)) gy = (nn - h) * inv1;
      else if (fin(h) && fin(so)) gy = (h - so) * inv1;
      // grid normal (−dz/dx, −dz/dy, 1) -> three.js (x, z, −y)
      const L = 1 / Math.sqrt(gx * gx + gy * gy + 1);
      nor[k] = -gx * L;
      nor[k + 1] = L;
      nor[k + 2] = gy * L;
    }
  }
  const ok = (i: number, j: number) => fin(z[(j + a) * st + a + i]);
  const big = nv >= 65536;
  const idx = big ? new Uint32Array((n - 1) * (n - 1) * 6 + 4 * (n - 1) * 6) : new Uint16Array((n - 1) * (n - 1) * 6 + 4 * (n - 1) * 6);
  let c = 0;
  for (let j = 0; j < n - 1; j++)
    for (let i = 0; i < n - 1; i++) {
      if (!ok(i, j) || !ok(i + 1, j) || !ok(i, j + 1) || !ok(i + 1, j + 1)) continue;
      const q = j * n + i;
      // same winding as Scene3D's crop mesh (faces up after the axis mapping)
      idx[c++] = q; idx[c++] = q + 1; idx[c++] = q + n;
      idx[c++] = q + 1; idx[c++] = q + n + 1; idx[c++] = q + n;
    }
  // skirts along the S, N, W, E edges
  let base = n * n;
  for (let edge = 0; edge < 4; edge++) {
    for (let k = 0; k < n; k++) {
      const i = edge === 0 || edge === 1 ? k : edge === 2 ? 0 : n - 1;
      const j = edge === 2 || edge === 3 ? k : edge === 0 ? 0 : n - 1;
      const src = (j * n + i) * 3;
      const dst = (base + k) * 3;
      pos[dst] = pos[src];
      pos[dst + 1] = pos[src + 1] - skirt;
      pos[dst + 2] = pos[src + 2];
      nor[dst] = nor[src];
      nor[dst + 1] = nor[src + 1];
      nor[dst + 2] = nor[src + 2];
      if (k > 0) {
        const pi = edge === 0 || edge === 1 ? k - 1 : i;
        const pj = edge === 2 || edge === 3 ? k - 1 : j;
        if (ok(i, j) && ok(pi, pj)) {
          const e0 = pj * n + pi;
          const e1 = j * n + i;
          idx[c++] = e0; idx[c++] = e1; idx[c++] = base + k - 1;
          idx[c++] = e1; idx[c++] = base + k; idx[c++] = base + k - 1;
        }
      }
    }
    base += n;
  }
  // bounding sphere (box centre, farthest vertex), computed here so the render thread never walks the vertices
  let lo0 = Infinity, lo1 = Infinity, lo2 = Infinity, hi0 = -Infinity, hi1 = -Infinity, hi2 = -Infinity;
  for (let v = 0; v < nv * 3; v += 3) {
    if (pos[v] < lo0) lo0 = pos[v]; if (pos[v] > hi0) hi0 = pos[v];
    if (pos[v + 1] < lo1) lo1 = pos[v + 1]; if (pos[v + 1] > hi1) hi1 = pos[v + 1];
    if (pos[v + 2] < lo2) lo2 = pos[v + 2]; if (pos[v + 2] > hi2) hi2 = pos[v + 2];
  }
  const cx = (lo0 + hi0) / 2, cy = (lo1 + hi1) / 2, cz = (lo2 + hi2) / 2;
  let r2 = 0;
  for (let v = 0; v < nv * 3; v += 3) {
    const d = (pos[v] - cx) ** 2 + (pos[v + 1] - cy) ** 2 + (pos[v + 2] - cz) ** 2;
    if (d > r2) r2 = d;
  }
  return { position: pos, normal: nor, index: idx.slice(0, c), sphere: [cx, cy, cz, Math.sqrt(r2)] };
}
