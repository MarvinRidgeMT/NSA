/// <reference lib="webworker" />
/**
 * Near-field LOD worker (5D Phase 9.4): fetches one tile, checks its size and SHA-256 against the manifest, and builds the
 * mesh arrays off the main thread so streaming never stalls a frame. DISPLAY ONLY: nothing here is a science computation.
 */
import { tileMeshArrays, type TileGrid } from './lodMesh';

export interface LodJob {
  key: string;
  url: string;
  bytes: number;
  sha256: string;
  grid: TileGrid;
  bounds: { xmin: number; xmax: number; ymin: number; ymax: number };
  zMin: number | null;
  obs: { x: number; y: number; ground: number };
}
export type LodReply =
  | { key: string; ok: true; position: Float32Array; normal: Float32Array; index: Uint16Array | Uint32Array; sphere: [number, number, number, number] }
  | { key: string; ok: false; error: string };

const hex = (b: ArrayBuffer) => [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, '0')).join('');

self.onmessage = async (ev: MessageEvent<LodJob>) => {
  const j = ev.data;
  try {
    const r = await fetch(j.url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const buf = await r.arrayBuffer();
    if (buf.byteLength !== j.bytes || buf.byteLength !== j.grid.stored * j.grid.stored * 4) throw new Error(`size ${buf.byteLength} does not match the manifest`);
    if (crypto?.subtle) {
      const h = hex(await crypto.subtle.digest('SHA-256', buf));
      if (h !== j.sha256) throw new Error('SHA-256 differs from the manifest');
    }
    const m = tileMeshArrays(j.grid, j.bounds, j.zMin, new Float32Array(buf), j.obs);
    const reply: LodReply = { key: j.key, ok: true, ...m };
    (self as unknown as Worker).postMessage(reply, [m.position.buffer, m.normal.buffer, m.index.buffer]);
  } catch (e) {
    const reply: LodReply = { key: j.key, ok: false, error: `${j.url}: ${e instanceof Error ? e.message : String(e)}` };
    (self as unknown as Worker).postMessage(reply);
  }
};
