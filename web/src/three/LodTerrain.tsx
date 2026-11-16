import { useFrame, useThree } from '@react-three/fiber';
import { useEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';
import { distanceToTile, drawSet, indexTiles, keyOf, lodBase, parentKey, selectTiles, type GridPoint, type LodManifest, type LodTileMeta } from '../bundle/lodTiles';
import { useLod, type LodStats } from '../store/lod';
import { tileMeshArrays, type TileMeshArrays } from './lodMesh';
import type { LodJob, LodReply } from './lodWorker';

/**
 * Near field ±7 km at 5 m, streamed as quadtree tiles by camera distance (5D Phase 9.4). DISPLAY ONLY: the tiles are drawn,
 * never sampled for a number; the bundle stays the only source of visible/blocked states, margins and metrics.
 *
 * Streaming: tiles are fetched, verified (size + SHA-256) and turned into mesh arrays in Web Workers; the render loop only
 * wraps at most MAX_NEW_PER_FRAME finished arrays per frame (within WRAP_BUDGET_MS) in a BufferGeometry, so streaming never stalls a frame.
 * While a tile is on its way its nearest loaded ancestor is drawn instead (drawSet): no gaps, no overlaps.
 */
const WORKERS = 2;
const MAX_INFLIGHT = 8;
const MAX_CACHED = 160; // ~1.1 MB of GPU buffers per 5 m tile
const MAX_NEW_PER_FRAME = 8;
const WRAP_BUDGET_MS = 2; // wrapping is cheap; the cap keeps first-draw GPU uploads spread over frames
const SELECT_EVERY_MS = 100;

interface Obs { x: number; y: number; ground: number }

/** BufferGeometry of one tile (main-thread path; used by tests and when Web Workers are unavailable). */
export function tileGeometry(m: LodManifest, t: LodTileMeta, z: Float32Array, obs: Obs): THREE.BufferGeometry {
  return toGeometry(tileMeshArrays(m.tileGrid, t.bounds, t.zMin, z, obs));
}

function toGeometry(a: TileMeshArrays): THREE.BufferGeometry {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(a.position, 3));
  g.setAttribute('normal', new THREE.BufferAttribute(a.normal, 3));
  g.setIndex(new THREE.BufferAttribute(a.index, 1));
  g.boundingSphere = new THREE.Sphere(new THREE.Vector3(a.sphere[0], a.sphere[1], a.sphere[2]), a.sphere[3]);
  return g;
}

function freeArray(this: THREE.BufferAttribute) {
  (this as unknown as { array: unknown }).array = null;
}

interface Entry { mesh: THREE.Mesh; used: number; tris: number }

export function LodTerrain({ manifest, obs, splitFactor = 1.2 }: { manifest: LodManifest; obs: Obs; splitFactor?: number }) {
  const camera = useThree((s) => s.camera);
  const group = useRef<THREE.Group>(null);
  const material = useMemo(() => new THREE.MeshStandardMaterial({ color: '#a8a399', roughness: 1, metalness: 0, side: THREE.DoubleSide }), []);
  // heights are relative to the observer: rebuild everything if the observer moves (a different dataset or scenario point)
  const obsKey = `${obs.x}|${obs.y}|${obs.ground}`;
  const st = useRef({
    index: indexTiles(manifest),
    cache: new Map<string, Entry>(),
    inflight: new Set<string>(),
    failed: new Set<string>(),
    ready: [] as { key: string; arrays: TileMeshArrays }[],
    workers: [] as Worker[],
    next: 0,
    lastSelect: -1e9,
    lastStats: '',
    lastStatsT: -1e9,
    drawn: new Set<string>(),
    live: true,
    started: false,
  });

  useEffect(() => {
    const s = st.current;
    s.live = true;
    if (typeof Worker !== 'undefined') {
      for (let i = 0; i < WORKERS; i++) {
        const w = new Worker(new URL('./lodWorker.ts', import.meta.url), { type: 'module' });
        w.onmessage = (ev: MessageEvent<LodReply>) => {
          const r = ev.data;
          s.inflight.delete(r.key);
          if (!s.live) return;
          if (r.ok) s.ready.push({ key: r.key, arrays: { position: r.position, normal: r.normal, index: r.index, sphere: r.sphere } });
          else {
            s.failed.add(r.key);
            console.warn(`LOD tile not used: ${r.error}`);
          }
        };
        s.workers.push(w);
      }
    }
    s.started = true;
    return () => {
      s.live = false;
      s.started = false;
      for (const w of s.workers) w.terminate();
      s.workers = [];
      s.inflight.clear();
      s.ready = [];
      for (const e of s.cache.values()) {
        e.mesh.geometry.dispose();
        e.mesh.removeFromParent();
      }
      s.cache.clear();
      s.drawn.clear();
      s.failed.clear();
      useLod.getState().setStats(null);
    };
  }, [manifest, obsKey]);
  useEffect(() => () => material.dispose(), [material]);

  const request = (t: LodTileMeta) => {
    const s = st.current;
    const key = keyOf(t);
    s.inflight.add(key);
    const url = new URL(`${lodBase(manifest.datasetId)}${t.file}`, document.baseURI).href;
    const job: LodJob = { key, url, bytes: t.bytes, sha256: t.sha256, grid: manifest.tileGrid, bounds: t.bounds, zMin: t.zMin, obs: { x: obs.x, y: obs.y, ground: obs.ground } };
    if (s.workers.length) {
      s.workers[s.next++ % s.workers.length].postMessage(job);
      return;
    }
    // no Web Workers: fetch and build here (slower, still correct)
    fetch(url)
      .then((r) => (r.ok ? r.arrayBuffer() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((b) => {
        if (b.byteLength !== t.bytes) throw new Error('size does not match the manifest');
        if (s.live) s.ready.push({ key, arrays: tileMeshArrays(manifest.tileGrid, t.bounds, t.zMin, new Float32Array(b), obs) });
      })
      .catch((e) => {
        s.failed.add(key);
        console.warn(`LOD tile not used: ${e instanceof Error ? e.message : e}`);
      })
      .finally(() => s.inflight.delete(key));
  };

  const p = useMemo(() => new THREE.Vector3(), []);
  useFrame(() => {
    const s = st.current;
    const g = group.current;
    if (!g || !s.started) return;
    const now = performance.now();
    // 1) wrap finished arrays in meshes (cheap: no per-node work on this thread); the GPU upload happens on first draw
    for (let k = 0; k < MAX_NEW_PER_FRAME && s.ready.length && (k === 0 || performance.now() - now < WRAP_BUDGET_MS); k++) {
      const { key, arrays } = s.ready.shift()!;
      if (s.cache.has(key)) continue;
      const geom = toGeometry(arrays);
      // the GPU keeps the buffers; drop the JS copies after upload (nothing raycasts or reads these meshes)
      for (const att of [geom.getAttribute('position'), geom.getAttribute('normal'), geom.index!] as THREE.BufferAttribute[]) att.onUpload(freeArray);
      const mesh = new THREE.Mesh(geom, material);
      mesh.visible = false;
      mesh.matrixAutoUpdate = false;
      mesh.userData.lodKey = key;
      g.add(mesh);
      s.cache.set(key, { mesh, used: now, tris: arrays.index.length / 3 });
    }
    if (now - s.lastSelect < SELECT_EVERY_MS) return;
    s.lastSelect = now;
    // 2) select by camera distance (grid frame: three (x, y, z) -> grid (x, −z, y), site-relative + observer)
    camera.getWorldPosition(p);
    const cam: GridPoint = { x: p.x + obs.x, y: -p.z + obs.y, z: p.y + obs.ground };
    const wanted = selectTiles(manifest, cam, splitFactor, undefined, s.index);
    // 3) request what is missing: the wanted tiles and their ancestors, coarse first, then nearest
    const need = new Map<string, LodTileMeta>();
    for (const t of wanted) {
      let cur: LodTileMeta | undefined = t;
      while (cur && !need.has(keyOf(cur))) {
        need.set(keyOf(cur), cur);
        const pk = parentKey(cur);
        cur = pk ? s.index.get(pk) : undefined;
      }
    }
    const queued = new Set(s.ready.map((r) => r.key));
    const missing = [...need.values()]
      .filter((t) => { const k = keyOf(t); return !s.cache.has(k) && !s.inflight.has(k) && !s.failed.has(k) && !queued.has(k); })
      .sort((a, b) => a.level - b.level || distanceToTile(cam, a) - distanceToTile(cam, b));
    for (const t of missing) {
      if (s.inflight.size >= MAX_INFLIGHT) break;
      request(t);
    }
    // 4) draw: wanted tiles, or their nearest loaded ancestor while they stream
    const draw = drawSet(wanted, (k) => s.cache.has(k), s.index);
    const next = new Set(draw.map(keyOf));
    for (const k of s.drawn) if (!next.has(k)) { const e = s.cache.get(k); if (e) e.mesh.visible = false; }
    let tris = 0;
    let finest: number | null = null;
    let coarsest: number | null = null;
    for (const t of draw) {
      const e = s.cache.get(keyOf(t))!;
      e.mesh.visible = true;
      e.used = now;
      tris += e.tris;
      const sp = manifest.levels[t.level].spacingM;
      finest = finest === null ? sp : Math.min(finest, sp);
      coarsest = coarsest === null ? sp : Math.max(coarsest, sp);
    }
    s.drawn = next;
    // 5) evict least recently used tiles that are neither drawn nor needed
    if (s.cache.size > MAX_CACHED) {
      const old = [...s.cache.entries()].filter(([k]) => !next.has(k) && !need.has(k)).sort((a, b) => a[1].used - b[1].used);
      for (const [k, e] of old.slice(0, s.cache.size - MAX_CACHED)) {
        e.mesh.geometry.dispose();
        e.mesh.removeFromParent();
        s.cache.delete(k);
      }
    }
    // 6) on-screen facts at most 4 times a second, and only when they change
    const pending = s.inflight.size + s.ready.length + missing.filter((t) => !s.inflight.has(keyOf(t))).length;
    const stats: LodStats = { drawn: draw.length, loaded: s.cache.size, pending, finestM: finest, coarsestM: coarsest, triangles: Math.round(tris) };
    const sig = JSON.stringify(stats);
    if (sig !== s.lastStats && now - s.lastStatsT > 250) {
      s.lastStats = sig;
      s.lastStatsT = now;
      useLod.getState().setStats(stats);
    }
  });

  return <group ref={group} name="lod-near-field" />;
}
