import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Html, OrbitControls } from '@react-three/drei';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useWheelGuard } from './wheelGuard';
import * as THREE from 'three';
import { gridDirection } from '../bundle/frame';
import type { Dem } from '../bundle/types';
import { usePolaris } from '../store/store';
import type { View } from '../store/view';
import HorizonDome from './HorizonDome';
import { useRidgeFocus } from '../store/ridge';
import { fmtRidgeDistance, type RidgeNow } from '../bundle/evidence';
import { CameraRig, MAP_FOV, dollyFactor, type Framing } from './CameraRig';
import { setCameraHeading } from '../store/heading';
import { useCamera, type CameraViewId } from '../store/camera';
import { useUi } from '../store/ui';
import { loadTerrainContext, type TerrainContext } from '../bundle/terrainContext';
import { validateVisualLayers, type VisualLayer } from '../bundle/visualLayers';
import { useSurface } from '../store/surface';
import { albedoLayerFor } from '../components/SurfaceLayer';
import { TerrainSurface } from './TerrainSurface';
import { ExaggerationPicker } from '../components/SurfaceLayer';
import { StableLine } from './StableLine';
import GlobalMoon from './GlobalMoon';
import { LodTerrain } from './LodTerrain';
import { LodPanel } from './LodPanel';
import { loadLodManifest, type LodManifest } from '../bundle/lodTiles';
import { useLod } from '../store/lod';

/**
 * Axes: bundle grid (x = grid east, y = grid north, z = up, metres) is drawn as
 * three.js (x, z, -y) with the observer at the origin. 1 unit = 1 m. Physical scale by default; the optional
 * DISPLAY-ONLY vertical exaggeration (useUi.exaggeration) scales the drawn scene's up axis as one group, so every
 * above/below relation between a sight line and the terrain is unchanged. Bundle numbers are never touched.
 */
const toThree = (gx: number, gy: number, gz: number) => new THREE.Vector3(gx, gz, -gy);

/** Where a sky body is drawn: its bundle direction with the up component scaled by the display exaggeration `k`, at `dist`.
 * The scene group is scaled by k in the up axis, so this keeps the body on the same (exaggerated) sight line. */
export function skyBodyPosition(dir: [number, number, number], k: number, dist: number): THREE.Vector3 {
  return toThree(dir[0], dir[1], dir[2] * k).normalize().multiplyScalar(dist);
}
const MAX_AXIS = 401;
/** soft radial glow texture for the Sun's corona sprite (display only) */
const GLOW = (() => {
  if (typeof document === 'undefined') return null;
  const c = document.createElement('canvas');
  c.width = c.height = 64;
  const g = c.getContext('2d');
  if (!g) return null;
  const r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  r.addColorStop(0, 'rgba(255,255,255,1)');
  r.addColorStop(0.2, 'rgba(255,255,255,0.35)');
  r.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = r;
  g.fillRect(0, 0, 64, 64);
  const t = new THREE.CanvasTexture(c);
  return t;
})(); // display decimation only (a 401² crop is drawn at full source resolution: metre-scale rises matter)

export interface Observer {
  x: number;
  y: number;
  ground: number;
  mast: number;
  source: 'bundle' | 'display-grid-centre';
}

/** Observer from the scenario, else the DEM sample nearest the crop centre (display placement only). */
export function observerFor(v: View): Observer {
  const o = v.series?.observer;
  if (o && Number.isFinite(o.xM)) return { x: o.xM, y: o.yM, ground: o.groundM, mast: o.mastM, source: 'bundle' };
  const d = v.dataset.dem!;
  const i = Math.round(-d.originX / d.spacing);
  const j = Math.round(-d.originY / d.spacing);
  const ci = Math.min(d.n - 1, Math.max(0, i));
  const cj = Math.min(d.n - 1, Math.max(0, j));
  return { x: d.originX + ci * d.spacing, y: d.originY + cj * d.spacing, ground: d.values[cj * d.n + ci], mast: 2, source: 'display-grid-centre' };
}

function useDemGeometry(dem: Dem, obs: Observer) {
  return useMemo(() => {
    const n = dem.n;
    const m = Math.min(n, MAX_AXIS);
    const idx = Array.from({ length: m }, (_, k) => Math.round((k * (n - 1)) / (m - 1)));
    const pos = new Float32Array(m * m * 3);
    const col = new Float32Array(m * m * 3);
    let lo = Infinity;
    let hi = -Infinity;
    for (const j of idx) for (const i of idx) {
      const z = dem.values[j * n + i];
      if (z < lo) lo = z;
      if (z > hi) hi = z;
    }
    const c0 = new THREE.Color('#6f6c66');
    const c1 = new THREE.Color('#b3aea4'); // neutral regolith ramp by height (display only; no albedo data)
    const c = new THREE.Color();
    let k = 0;
    for (const j of idx) {
      for (const i of idx) {
        const gx = dem.originX + i * dem.spacing - obs.x;
        const gy = dem.originY + j * dem.spacing - obs.y;
        const gz = dem.values[j * n + i] - obs.ground;
        const p = toThree(gx, gy, gz);
        pos.set([p.x, p.y, p.z], k * 3);
        c.copy(c0).lerp(c1, hi > lo ? (dem.values[j * n + i] - lo) / (hi - lo) : 0.5);
        col.set([c.r, c.g, c.b], k * 3);
        k++;
      }
    }
    const index: number[] = [];
    for (let j = 0; j < m - 1; j++)
      for (let i = 0; i < m - 1; i++) {
        const a = j * m + i;
        // winding chosen so faces point up after the (x, z, -y) mapping
        index.push(a, a + 1, a + m, a + 1, a + m + 1, a + m);
      }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    g.setAttribute('color', new THREE.BufferAttribute(col, 3));
    g.setIndex(index);
    g.computeVertexNormals();
    const halfExtent = ((n - 1) * dem.spacing) / 2;
    return { g, halfExtent, decimatedTo: m };
  }, [dem, obs.x, obs.y, obs.ground]);
}


/** Sight-line labels are plain DOM over the canvas (no extra React roots): Ray publishes text + a 3D anchor, the overlay
 *  projects the anchor every frame. */
type SightLabel = { k: string; m: string; a: string; r: string; state: string };
const sightText: Record<'sun' | 'earth', SightLabel | null> = { sun: null, earth: null };
const sightAnchor: Record<string, THREE.Object3D | null> = { sun: null, earth: null };
const sightEl: Record<string, HTMLDivElement | null> = { sun: null, earth: null };
const flipCache = { t: -1e9, limit: Infinity, w: { sun: 0, earth: 0 } as Record<'sun' | 'earth', number> };

function LabelAnchor({ id, position }: { id: 'sun' | 'earth'; position: THREE.Vector3 }) {
  const ref = useRef<THREE.Object3D>(null);
  useEffect(() => {
    sightAnchor[id] = ref.current;
    return () => {
      sightAnchor[id] = null;
    };
  }, [id]);
  return <object3D ref={ref} position={position} />;
}

/** Projects the label anchors to screen space each frame and moves the DOM labels (inside the Canvas tree, no DOM output). */
function SightLabelDriver() {
  const { camera, size } = useThree();
  const p = useMemo(() => new THREE.Vector3(), []);
  useFrame(() => {
    for (const id of ['sun', 'earth'] as const) {
      const el = sightEl[id];
      const a = sightAnchor[id];
      const t = sightText[id];
      if (!el) continue;
      if (!a || !t) {
        el.style.display = 'none';
        continue;
      }
      a.getWorldPosition(p);
      p.project(camera);
      const on = p.z < 1 && p.x > -1.2 && p.x < 1.2 && p.y > -1.2 && p.y < 1.2;
      el.style.display = on ? 'flex' : 'none';
      const sx = ((p.x + 1) / 2) * size.width;
      el.style.left = `${sx}px`;
      el.style.top = `${((1 - p.y) / 2) * size.height}px`;
      // Final Apex P6: a label that would run under the instrument panel (or off the right edge) flips to the left of its anchor.
      // Layout is read at most every 250 ms (cached), never right after the style writes above, so no frame forces a layout.
      const now = performance.now();
      if (now - flipCache.t > 250) {
        const host = el.parentElement?.getBoundingClientRect();
        const ins = document.querySelector('[data-testid="instrument"]')?.getBoundingClientRect();
        let limit = size.width;
        if (host && ins && ins.width > 0 && ins.left > host.left && ins.top < host.top + size.height && ins.bottom > host.top) limit = Math.min(limit, ins.left - host.left);
        flipCache.limit = limit;
        flipCache.w.sun = sightEl.sun?.offsetWidth ?? 0;
        flipCache.w.earth = sightEl.earth?.offsetWidth ?? 0;
        flipCache.t = now;
      }
      const flip = sx + 8 + flipCache.w[id] > flipCache.limit - 4;
      if (el.classList.contains('flip') !== flip) el.classList.toggle('flip', flip);
      const k = el.querySelector('.k');
      const m = el.querySelector('.m');
      const r = el.querySelector('.r') as HTMLElement | null;
      if (k && k.textContent !== t.k) k.textContent = t.k;
      if (m && m.textContent !== t.m) m.textContent = t.m;
      const aa = el.querySelector('.a');
      if (aa && aa.textContent !== t.a) aa.textContent = t.a;
      if (r) {
        if (r.textContent !== t.r) r.textContent = t.r;
        r.style.display = t.r ? '' : 'none';
      }
      el.className = `sight-tag ${id} ${t.state}${flip ? ' flip' : ''}`;
    }
  });
  return null;
}

/** The DOM side of the sight labels (rendered next to the Canvas). */
function SightLabels() {
  return (
    <div className="sight-layer" aria-hidden="true">
      {(['sun', 'earth'] as const).map((id) => (
        <div key={id} className={`sight-tag ${id}`} data-testid={`sight-${id}`} style={{ display: 'none' }} ref={(e) => void (sightEl[id] = e)}>
          <span className="k" />
          <span className="m" />
          <span className="a" />
          <span className="r" />
        </div>
      ))}
    </div>
  );
}

/** A line drawn in segments whose opacity falls to 0 toward the end: "continues beyond what is drawn". */
function FadeLine({ a, b, color, width, dashed, fade, opacity = 1 }: { a: THREE.Vector3; b: THREE.Vector3; color: string; width: number; dashed?: boolean; fade: boolean; opacity?: number }) {
  const N = fade ? 7 : 1;
  const segs = [];
  for (let i = 0; i < N; i++) {
    const p0 = a.clone().lerp(b, i / N);
    const p1 = a.clone().lerp(b, (i + 1) / N);
    const o = fade ? opacity * (1 - i / N) ** 1.6 : opacity;
    segs.push(<StableLine key={i} points={[p0, p1]} color={color} lineWidth={width} transparent opacity={o} dashed={dashed} dashSize={dashed ? 18 : undefined} gapSize={dashed ? 12 : undefined} depthWrite={false} />);
  }
  return <>{segs}</>;
}

/**
 * Sight-line annotation for one target, all from bundle values (nothing computed here):
 *   - the target's sight line from the mast top along its true direction (az, el): to the bundle's first terrain hit when it
 *     is blocked inside this crop, otherwise fading out at the crop edge ("continues");
 *   - the skyline line in the same azimuth at the bundle's skyline elevation: to the controlling ridge point when that lies
 *     inside this crop; when the controlling terrain is farther (e.g. a ridge 128 km away) it fades at the crop edge and the
 *     label says so, so a distant ridge is never drawn as if it were local terrain;
 *   - a margin arc between the two, in the target colour (alarm when blocked), labelled with the bundle margin.
 */
function Ray({ v, obs, target, edge, ridgeNow }: { v: View; obs: Observer; target: 'sun' | 'earth'; edge: number; ridgeNow: RidgeNow | null }) {
  const t = v[target];
  const camera = useThree((st) => st.camera);
  const arcRef = useRef<THREE.Group>(null);
  const top = toThree(0, 0, obs.mast);
  useFrame(() => arcRef.current?.scale.setScalar(Math.max(camera.position.distanceTo(top) * 0.09 * lensScale(camera), 0.4)));
  if (!Number.isFinite(t.az) || !Number.isFinite(t.el)) return null;
  const state = t.visible === undefined ? 'unknown' : t.visible === null ? 'transition' : t.visible ? 'clear' : 'blocked';
  const color = target === 'sun' ? '#E8A53C' : '#7FA8DA';
  const dirAt = (el: number) => {
    const d = gridDirection(v.basis, t.az, el);
    return toThree(d[0], d[1], d[2]);
  };
  const along = (el: number, horiz: number) => top.clone().add(dirAt(el).multiplyScalar(horiz / Math.max(Math.cos((el * Math.PI) / 180), 1e-6)));
  // target line
  const hitInside = state === 'blocked' && typeof t.firstHitM === 'number' && t.firstHitM <= edge;
  const tEnd = along(t.el, hitInside ? (t.firstHitM as number) : edge);
  // skyline line (bundle skyline elevation in this azimuth) and its controlling distance (bundle attribution)
  const hz = t.horizonElDeg;
  const ctrl = ridgeNow?.ctrlDistM ?? null;
  const ridgeInside = ctrl !== null && ctrl <= edge;
  const sEnd = hz !== null && hz !== undefined ? along(hz, ridgeInside ? (ctrl as number) : edge) : null;
  // margin arc (unit radius, scaled to a constant screen size)
  const arc: THREE.Vector3[] = [];
  if (hz !== null && hz !== undefined) {
    const n = 16;
    for (let i = 0; i <= n; i++) arc.push(dirAt(hz + ((t.el - hz) * i) / n));
  }
  const arcColor = state === 'blocked' ? '#E0645A' : color;
  const m = t.marginDeg;
  const r = ridgeNow?.ridge;
  const far = !!r && ctrl !== null && !ridgeInside;
  const name = target === 'sun' ? 'Sun' : 'Earth';
  const label = {
    k: `${name} · ${state === 'unknown' ? 'not evaluated' : state === 'transition' ? 'at the skyline' : state}`,
    m: m !== null && m !== undefined ? `${m >= 0 ? '+' : '−'}${Math.abs(m).toFixed(2)}° vs skyline` : 'margin not in bundle',
    // direction from the bundle ephemeris (Final Apex P5): azimuth clockwise from local north, apparent centre elevation
    a: `az ${t.az.toFixed(1)}° · el ${t.el >= 0 ? '+' : '−'}${Math.abs(t.el).toFixed(2)}°`,
    r: state === 'blocked' && r ? `skyline: ${r.label ?? r.id}, ${fmtRidgeDistance(r)}${far ? ' · beyond this crop' : ''}` : '',
    state,
  };
  sightText[target] = label;
  return (
    <group>
      <FadeLine a={top} b={tEnd} color={color} width={state === 'blocked' ? 2.2 : 1.6} dashed={target === 'earth'} fade={!hitInside} />
      {sEnd && <FadeLine a={top} b={sEnd} color="#ECE7DD" width={1} fade={!ridgeInside} opacity={0.55} />}
      {hitInside && (
        <ScreenSized position={tEnd} k={0.006}>
          <mesh>
            <ringGeometry args={[0.7, 1.0, 24]} />
            <meshBasicMaterial color="#E0645A" side={THREE.DoubleSide} depthTest={false} transparent />
          </mesh>
        </ScreenSized>
      )}
      {arc.length > 1 && (
        <group ref={arcRef} position={top}>
          <StableLine points={arc} color={arcColor} lineWidth={2} depthTest={false} transparent />
          <LabelAnchor id={target} position={arc[arc.length - 1].clone().multiplyScalar(1.12)} />
        </group>
      )}
    </group>
  );
}

/**
 * Display choice for the Approach view: among cross-light directions (50–110° either side of the Sun azimuth, where Sun-facing
 * slopes and their shadows both read) pick the one where the bundle skyline is lowest, so the camera looks out over open
 * ground instead of into a wall. Uses only the bundle skyline; falls back to 70° off the Sun.
 */
function openCrossLightAz(v: View): number {
  const sk = v.series?.skyline;
  if (!sk || !sk.azimuthDeg.length) return v.sun.az - 70;
  const n = sk.azimuthDeg.length;
  const elAt = (az: number) => {
    const a = ((az % 360) + 360) % 360;
    let best = 0;
    let bd = 1e9;
    for (let i = 0; i < n; i++) {
      const d = Math.abs(((sk.azimuthDeg[i] - a + 540) % 360) - 180);
      if (d < bd) { bd = d; best = i; }
    }
    return sk.elevationDeg[best] ?? 0;
  };
  let pick = v.sun.az - 70;
  let low = Infinity;
  for (const side of [-1, 1])
    for (let off = 50; off <= 110; off += 5) {
      const az = v.sun.az + side * off;
      // average over the field of view (±20°) so one notch does not decide
      let s = 0;
      for (let d = -20; d <= 20; d += 5) s += elAt(az + d);
      if (s < low) { low = s; pick = az; }
    }
  return pick;
}

/** tan(fov/2) relative to the base lens; 1 for the normal views, < 1 for the Overhead map lens (screen-constant markers). */
const TAN_BASE = Math.tan((42 * Math.PI) / 360);
function lensScale(camera: THREE.Camera): number {
  const fov = (camera as THREE.PerspectiveCamera).fov;
  return typeof fov === 'number' ? Math.tan((fov * Math.PI) / 360) / TAN_BASE : 1;
}

/** Keeps a marker a constant apparent size (k × camera distance) so true-scale terrain is never hidden behind symbols. */
function ScreenSized({ position, k, children }: { position: THREE.Vector3; k: number; children: React.ReactNode }) {
  const ref = useRef<THREE.Group>(null);
  const { camera } = useThree();
  // apparent size ∝ distance × tan(fov/2): with the Overhead map lens (narrow FOV) the marker keeps the same on-screen size
  useFrame(() => ref.current?.scale.setScalar(Math.max(camera.position.distanceTo(position) * k * lensScale(camera), 1e-3)));
  return (
    <group ref={ref} position={position}>
      {children}
    </group>
  );
}

/** Bilinear DEM height at a grid position (display placement of bundle-located features only). */
function demHeight(dem: Dem, gx: number, gy: number): number | null {
  const fx = (gx - dem.originX) / dem.spacing;
  const fy = (gy - dem.originY) / dem.spacing;
  const i = Math.floor(fx);
  const j = Math.floor(fy);
  if (i < 0 || j < 0 || i >= dem.n - 1 || j >= dem.n - 1) return null;
  const tx = fx - i;
  const ty = fy - j;
  const at = (a: number, b: number) => dem.values[b * dem.n + a];
  const z = (at(i, j) * (1 - tx) + at(i + 1, j) * tx) * (1 - ty) + (at(i, j + 1) * (1 - tx) + at(i + 1, j + 1) * tx) * ty;
  return Number.isFinite(z) ? z : null;
}

/**
 * Ridge of Record on the real DEM: the bundle's per-bin controlling points (azimuth of each skyline bin, per_bin.ctrl_dist_m)
 * drawn as a line on the terrain, at true scale. Points outside this DEM crop are not drawn and are counted in the label:
 * nothing is invented beyond source coverage. An explicit selection eases the camera to a close view from behind the mast.
 */
function RidgeOnTerrain({ v, obs, dem }: { v: View; obs: Observer; dem: Dem }) {
  const { focus } = useRidgeFocus(v);
  const att = v.dataset.derived?.attribution;
  const sk = v.series?.skyline;
  const geo = useMemo(() => {
    if (!focus || !sk || !att?.perBin?.ctrlDistM) return null;
    const pts: THREE.Vector3[] = [];
    const runs: THREE.Vector3[][] = [];
    let lastD: number | null = null;
    let outside = 0;
    for (const b of focus.bins) {
      const d = att.perBin.ctrlDistM[b];
      if (d === null || d === undefined || !Number.isFinite(d)) continue;
      const dir = gridDirection(v.basis, sk.azimuthDeg[b], 0);
      const gx = obs.x + dir[0] * d;
      const gy = obs.y + dir[1] * d;
      const z = demHeight(dem, gx, gy);
      if (z === null) {
        outside++;
        continue;
      }
      const p = toThree(gx - obs.x, gy - obs.y, z - obs.ground + 0.18);
      pts.push(p);
      // a new run where the controlling distance jumps (neighbouring bins controlled by different terrain): never join them
      if (lastD === null || Math.abs(d - lastD) > Math.max(6, 0.25 * Math.min(d, lastD))) runs.push([]);
      runs[runs.length - 1].push(p);
      lastD = d;
    }
    return { pts, runs, outside };
  }, [focus, sk, att, v.basis, obs.x, obs.y, obs.ground, dem]);
  if (!focus || !geo) return null;
  if (!geo.pts.length) return null;
  return (
    <group>
      {/* one dot per skyline bin's controlling point (bundle per_bin.ctrl_dist_m): no connecting line is invented between them */}
      {geo.pts.map((p, i) => (
        <ScreenSized key={i} position={p} k={0.0032}>
          <mesh>
            <sphereGeometry args={[0.6, 10, 10]} />
            <meshBasicMaterial color="#B8C9C4" />
          </mesh>
        </ScreenSized>
      ))}
    </group>
  );
}

/**
 * Picked sampled mast with no bundle series: an outline that GROWS from the bundle mast to the picked height when the user picks it
 * (Blobmixer: a parameter change answers at once in the 3D object). Only the drawing eases; the instrument's numbers switch
 * discretely between evaluated heights and are never interpolated. A bracket shows the extra height. Display only.
 */
function GhostMast({ from, to }: { from: number; to: number }) {
  const grp = useRef<THREE.Group>(null);
  const cyl = useRef<THREE.Mesh>(null);
  const t0 = useRef(performance.now());
  const instant = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  useFrame(() => {
    const k = instant ? 1 : Math.min(1, (performance.now() - t0.current) / 650);
    const e = 1 - Math.pow(1 - k, 3);
    const h = from + (to - from) * e;
    if (cyl.current) {
      cyl.current.scale.set(1, Math.max(h, 0.01), 1);
      cyl.current.position.set(0, h / 2, 0);
    }
    if (grp.current) grp.current.userData.h = h;
  });
  const dh = to - from;
  return (
    <group ref={grp}>
      <mesh ref={cyl} position={toThree(0, 0, from / 2)}>
        <cylinderGeometry args={[0.08, 0.08, 1, 10, 1, true]} />
        <meshBasicMaterial color="#F2B84B" wireframe transparent opacity={0.75} />
      </mesh>
      {/* bracket from the bundle mast top to the picked height, offset to the side */}
      <StableLine points={[toThree(0.35, 0, from), toThree(0.45, 0, from), toThree(0.45, 0, to), toThree(0.35, 0, to)]} color="#F2B84B" lineWidth={1.2} transparent opacity={0.85} />
      <Html position={toThree(0.45, 0, (from + to) / 2)} distanceFactor={undefined} zIndexRange={[5, 0]}>
        <span className="ghost-mast side" data-testid="ghost-mast" title="display outline: a sampled batch height with no bundle time series">
          {to} m <em>({dh > 0 ? '+' : '−'}{Math.abs(dh).toFixed(2)} m vs bundle mast)</em> · outline
        </span>
      </Html>
    </group>
  );
}

/** Publishes the camera's view azimuth in the site's local frame (0 = local north) for the heading tape. Display only. */
function HeadingProbe({ toward }: { toward: (az: number, d: number) => THREE.Vector3 }) {
  const camera = useThree((s) => s.camera);
  const basis = useMemo(() => ({ n: new THREE.Vector3(), e: new THREE.Vector3(), d: new THREE.Vector3(), u: new THREE.Vector3() }), []);
  useFrame(() => {
    basis.n.copy(toward(0, 1)).normalize();
    basis.e.copy(toward(90, 1)).normalize();
    camera.getWorldDirection(basis.d);
    let x = basis.d.dot(basis.e);
    let y = basis.d.dot(basis.n);
    if (Math.hypot(x, y) < 0.2) {
      // looking (nearly) straight down: the screen's up direction is the heading
      basis.u.set(0, 1, 0).applyQuaternion(camera.quaternion);
      x = basis.u.dot(basis.e);
      y = basis.u.dot(basis.n);
    }
    setCameraHeading(((Math.atan2(x, y) * 180) / Math.PI + 360) % 360);
  });
  useEffect(() => () => setCameraHeading(null), []);
  return null;
}

interface SurfaceExtras {
  ctx: TerrainContext | null;
  albedo: { texture: THREE.Texture; layer: VisualLayer } | null;
  /** 5D Phase 9.4: near-field LOD tiles to draw instead of the crop/context surface (display only), or null */
  lod?: LodManifest | null;
}

function Scene({ v, ctx, albedo, lod = null }: { v: View } & SurfaceExtras) {
  const layer = useSurface((s) => s.layer);
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const obs = observerFor(v);
  const dem = v.dataset.dem!;
  const { g, halfExtent } = useDemGeometry(dem, obs);
  const edge = dem.validCoverageRadiusM ?? halfExtent;
  const { selectFailure } = usePolaris.getState();
  // Lighting mode (display only): 'display' keeps the bundle Sun azimuth but shows its elevation at >= 0.5 deg so the terrain
  // stays readable; 'true' uses the bundle elevation as is, and with the Sun below the horizon the key light is off.
  const trueLight = useUi((s) => s.trueLight);
  const exag = useUi((s) => s.exaggeration);
  const mastPick = useUi((s) => s.mastPick);
  const camView = useCamera((s) => s.view);
  // the mast-eye camera sits at the true eye height, so the eye view is always physical
  const k = camView === 'mast' ? 1 : exag;
  const lightEl = trueLight ? v.sun.el : Math.max(v.sun.el, 0.5);
  const keyOn = !trueLight || v.sun.el > 0;
  const sunDir = gridDirection(v.basis, v.sun.az, Math.max(lightEl, 0.05));
  const light = toThree(sunDir[0], sunDir[1], sunDir[2]).multiplyScalar(halfExtent * 2);
  const failures = v.series?.failures ?? [];
  const n = gridDirection(v.basis, 0, 0);
  const north = toThree(n[0], n[1], 0).multiplyScalar(halfExtent * 0.9);

  // camera framings for the named views (display only; the observer is the origin, 1 unit = 1 m)
  const { focus, sun: ridgeNowSun, earth: ridgeNowEarth } = useRidgeFocus(v);
  const eye = toThree(0, 0, obs.mast);
  const sunAzDir = gridDirection(v.basis, v.sun.az, 0);
  const toward = (az: number, d: number) => {
    const dd = gridDirection(v.basis, az, 0);
    return toThree(dd[0] * d, dd[1] * d, 0);
  };
  const frame = (id: CameraViewId): Framing | null => {
    const H = halfExtent;
    if (id === 'approach' || id === 'horizon') {
      // cross-light: the view runs ~75° from the Sun azimuth, so Sun-facing slopes and their long shadows both read
      // (looking into the Sun shows only backlit, shadowed faces). Low over the terrain, black sky above. Display only.
      const viewAz = openCrossLightAz(v);
      const back = toward(viewAz + 180, H * 0.42);
      return { pos: back.setY(H * 0.14), target: toward(viewAz, H * 0.05).setY(-H * 0.02) };
    }
    // with the context pack the 'regional' view frames the 8 km 20 m ring around the 5 m crop (the crop alone is only 2 km wide)
    if (id === 'regional')
      return ctx
        ? { pos: new THREE.Vector3(H * 2.9, H * 1.9, H * 2.9), target: new THREE.Vector3(0, -H * 0.15, 0) }
        : { pos: new THREE.Vector3(H * 0.95, H * 0.8, H * 0.95), target: new THREE.Vector3(0, 0, 0) };
    // the 5 m crop inside its 80 m surroundings (only meaningful when the context pack is drawn)
    if (id === 'context') return ctx ? { pos: new THREE.Vector3(H * 6.5, H * 5.2, H * 6.5), target: new THREE.Vector3(0, 0, 0) } : null;
    if (id === 'overhead') {
      // a true plan view: far away through a long lens (MAP_FOV), same footprint as before; perspective nearly vanishes, so the
      // crop reads as a map. Moving in or out of it is a dolly zoom (CameraRig). Display only.
      const D = H * 2.3 * dollyFactor(MAP_FOV);
      // a tiny southward offset (0.1°) keeps local north at the top of the screen; it must scale with the distance, or lookAt
      // loses the orientation (the up vector becomes parallel to the view) and the map keeps the previous heading
      const up = toThree(0, 0, D);
      return { pos: up.add(toward(180, D * 0.002)), target: new THREE.Vector3(0, 0, 0), fov: MAP_FOV };
    }
    if (id === 'mast') {
      // the eye IS the mast top (bundle observer height), looking along the Sun azimuth about 2° down so the near ground and
      // the horizon share the frame; the mast itself is hidden in this view (it would sit inside the camera)
      const ahead = toThree(sunAzDir[0] * 600, sunAzDir[1] * 600, 0);
      return { pos: eye.clone().add(toThree(-sunAzDir[0] * 0.05, -sunAzDir[1] * 0.05, 0.02)), target: ahead.setY(eye.y - 21) };
    }
    if (id === 'ridge') {
      const r = focus?.ridge ?? v.dataset.derived?.attribution?.ridges.find((x) => x.ofRecord) ?? null;
      if (!r) return null;
      const az = (r.azimuthDeg[0] + r.azimuthDeg[1]) / 2;
      const dMin = typeof r.distanceM === 'number' ? r.distanceM : r.distanceM.min;
      // obstruction distance: the blocked target's bundle first hit when it is this ridge, else the ridge's nearest distance
      const hit = [v.sun, v.earth].find((t) => t.visible === false && typeof t.firstHitM === 'number')?.firstHitM ?? null;
      const d = Math.min(Number.isFinite(dMin) ? Math.max(hit ?? dMin, dMin) : edge, edge * 0.9);
      const mid = toward(az, d * 0.5);
      // stand beside the sight line (perpendicular), a little above it: the mast, the line and the rise read in profile.
      // The target sits past the midpoint so the scene clears the instrument panel on the right.
      const side = toward(az + 90, Math.max(d * 2.0, 18));
      return { pos: mid.clone().add(side).setY(Math.max(d * 0.42, obs.mast + 3.5)), target: toward(az, d * 0.95).setY(obs.mast * 0.5) };
    }
    return null;
  };
  // the Sun disc sits on the bundle's true Sun direction (az, el), far away; its light is clamped to >= 0.5 deg so the terrain stays readable
  // Bodies are drawn BEYOND the drawn terrain (context reach ~16 km), so any drawn ridge can hide them; terrain past the drawn
  // area (the solver looks 280 km out) cannot, so a body the bundle calls blocked is drawn as a faint "hidden direction" marker.
  const skyDist = ctx ? Math.max(ctx.meta.displayReachM * 1.4, halfExtent * 6) : halfExtent * 6;
  const trueSun = gridDirection(v.basis, v.sun.az, v.sun.el);
  const sunDisc = skyBodyPosition(trueSun, k, skyDist);
  const trueEarth = gridDirection(v.basis, v.earth.az, v.earth.el);
  const earthDisc = skyBodyPosition(trueEarth, k, skyDist);
  const sunHidden = v.sun.visible === false;
  const earthHidden = v.earth.visible === false;
  const S = halfExtent * 1.05;
  // with the regional context drawn the far plane must reach its corners (~23 km); display only
  const farPlane = ctx || lod ? 90000 : halfExtent * 48; // the Overhead map view sits ~39 half-extents away (long lens)
  useEffect(() => {
    if (camera.far !== farPlane) {
      camera.far = farPlane;
      camera.updateProjectionMatrix();
    }
  }, [camera, farPlane]);

  return (
    <>
      <color attach="background" args={['#050505']} />
      <CameraRig frame={frame} frameKey={`${v.dataset.siteId}:${v.series?.id ?? ''}:${dem.n}`} />
      {/* airless low-Sun look: one hard key light from the bundle's Sun azimuth with cast shadows, almost no fill (visual only) */}
      {/* fill is a disclosed display choice (no air, so the real shadows are near black): a faint earthshine-like hemisphere */}
      <ambientLight intensity={0.035} />
      <hemisphereLight args={['#9fb4d8', '#1a1712', trueLight ? 0.05 : 0.2]} />
      <directionalLight
        position={light}
        intensity={keyOn ? 4.2 : 0}
        color="#fff4e2"
        castShadow={!ctx}
        shadow-mapSize-width={4096}
        shadow-mapSize-height={4096}
        shadow-bias={-0.0004}
        shadow-normalBias={0.6}
        shadow-camera-left={-S}
        shadow-camera-right={S}
        shadow-camera-top={S}
        shadow-camera-bottom={-S}
        shadow-camera-near={1}
        shadow-camera-far={halfExtent * 5}
      />
      {/* Sun and Earth discs on their true bundle directions at their true angular sizes (Sun 0.53°, Earth ~1.9° from the Moon) */}
      <mesh position={sunDisc} renderOrder={sunHidden ? 2 : 0}>
        <sphereGeometry args={[skyDist * Math.tan((0.2665 * Math.PI) / 180), 32, 32]} />
        <meshBasicMaterial color="#fff6e6" toneMapped={false} transparent={sunHidden} opacity={sunHidden ? 0.28 : 1} depthWrite={!sunHidden} />
      </mesh>
      {!sunHidden && (
        <sprite position={sunDisc} scale={[skyDist * 0.05, skyDist * 0.05, 1]}>
          <spriteMaterial map={GLOW} color="#ffd9a0" transparent opacity={0.55} depthWrite={false} toneMapped={false} blending={THREE.AdditiveBlending} />
        </sprite>
      )}
      <mesh position={earthDisc} renderOrder={earthHidden ? 2 : 0}>
        <sphereGeometry args={[skyDist * Math.tan((0.95 * Math.PI) / 180), 32, 32]} />
        <meshBasicMaterial color="#7FA8DA" toneMapped={false} transparent={earthHidden} opacity={earthHidden ? 0.3 : 1} depthWrite={!earthHidden} />
      </mesh>
      {/* always mounted (mounting/unmounting drei Html during a render warns); shown only when the bundle says blocked */}
      <Html position={sunDisc} center zIndexRange={[4, 0]} style={{ display: sunHidden && camView !== 'overhead' ? 'block' : 'none' }}>
        <span className="tag3d hidden-body" data-testid="sun-hidden-marker" data-hidden={sunHidden}>Sun direction · hidden by terrain (bundle)</span>
      </Html>
      <Html position={earthDisc} center zIndexRange={[4, 0]} style={{ display: earthHidden && camView !== 'overhead' ? 'block' : 'none' }}>
        <span className="tag3d hidden-body" data-testid="earth-hidden-marker" data-hidden={earthHidden}>Earth direction · hidden by terrain (bundle)</span>
      </Html>
      <group scale={[1, k, 1]}>
      {lod ? (
        <LodTerrain manifest={lod} obs={obs} />
      ) : ctx ? (
        <TerrainSurface v={v} dem={dem} obs={obs} local={g} ctx={ctx} layer={layer} albedo={albedo} />
      ) : (
        <mesh geometry={g} receiveShadow castShadow>
          <meshStandardMaterial vertexColors roughness={1} metalness={0} side={THREE.DoubleSide} />
        </mesh>
      )}
      {/* observer mast, drawn to scale (hidden in mast-eye, where the camera sits at its top) */}
      {camView !== 'mast' && (
        <>
          <mesh position={toThree(0, 0, obs.mast / 2)}>
            <cylinderGeometry args={[0.06, 0.06, obs.mast, 12]} />
            <meshBasicMaterial color="#ECE7DD" />
          </mesh>
          <ScreenSized position={toThree(0, 0, obs.mast)} k={0.009}>
            <mesh>
              <sphereGeometry args={[0.6, 16, 16]} />
              <meshBasicMaterial color="#ECE7DD" />
            </mesh>
          </ScreenSized>
        </>
      )}
      {/* picked sampled height with no bundle series: an outline only, labelled; rays and timeline stay on the bundle mast */}
      {mastPick !== null && mastPick !== obs.mast && camView !== 'mast' && <GhostMast key={mastPick} from={obs.mast} to={mastPick} />}
      <RidgeOnTerrain v={v} obs={obs} dem={dem} />
      <HeadingProbe toward={toward} />
      <SightLabelDriver />
      {camView !== 'mast' && (
        <>
          <Ray v={v} obs={obs} target="sun" edge={edge} ridgeNow={ridgeNowSun} />
          <Ray v={v} obs={obs} target="earth" edge={edge} ridgeNow={ridgeNowEarth} />
        </>
      )}
      {failures.map((f) =>
        f.firstHit ? (
          <ScreenSized key={f.id} k={0.011} position={toThree(f.firstHit.xM - obs.x, f.firstHit.yM - obs.y, f.firstHit.heightM - obs.ground + 0.3)}>
          <mesh
            onClick={(e) => {
              e.stopPropagation();
              selectFailure(f.id);
            }}
            onPointerOver={() => (document.body.style.cursor = 'pointer')}
            onPointerOut={() => (document.body.style.cursor = '')}
          >
            <octahedronGeometry args={[0.8]} />
            <meshBasicMaterial color={v.failure?.id === f.id ? '#ffffff' : '#E0645A'} />
          </mesh>
          </ScreenSized>
        ) : null,
      )}
      </group>
      <Html position={north} center>
        <span className="tag3d">local N</span>
      </Html>
      <Html position={north.clone().multiplyScalar(-1)} center style={{ display: k !== 1 ? 'block' : 'none' }}>
        <span className="tag3d" data-testid="exaggeration-tag">vertical ×{k} · display only</span>
      </Html>
      <OrbitControls makeDefault target={[0, 0, 0]} maxPolarAngle={Math.PI * 0.495} enableDamping dampingFactor={0.08} minDistance={3} />
    </>
  );
}

export default function Scene3D({ v, active = true }: { v: View; active?: boolean }) {
  if (!v.dataset.dem) return <HorizonDome v={v} active={active} />;
  return <DemScene v={v} active={active} />;
}

function DemScene({ v, active }: { v: View; active: boolean }) {
  const wrap = useRef<HTMLDivElement>(null);
  useWheelGuard(wrap);
  const dem = v.dataset.dem!;
  const half = ((dem.n - 1) * dem.spacing) / 2;
  const obs = observerFor(v);

  // DISPLAY-ONLY extras: the terrain context pack for this dataset and a registered image layer, when they exist.
  // Absent or mismatched (different DEM crop hash) -> the crop-only rendering below is used unchanged.
  const [ctx, setCtx] = useState<TerrainContext | null>(null);
  const [albedo, setAlbedo] = useState<SurfaceExtras['albedo']>(null);
  const visualLayers = useSurface((s) => s.visualLayers);
  const siteId = v.dataset.siteId;
  const cropSha = dem.cropValuesSha256;
  useEffect(() => {
    let live = true;
    setCtx(null);
    loadTerrainContext(siteId, cropSha)
      .then((c) => live && setCtx(c))
      .catch((e) => {
        console.warn(`terrain context not used: ${e instanceof Error ? e.message : e}`);
      });
    return () => {
      live = false;
    };
  }, [siteId, cropSha]);
  useEffect(() => {
    if (useSurface.getState().visualLayers) return;
    fetch('visual/visual_layers.json')
      .then((r) => (r.ok && (r.headers.get('content-type') ?? '').includes('json') ? r.json() : null))
      .then((j) => j && useSurface.getState().setVisualLayers(validateVisualLayers(j)))
      .catch((e) => console.warn(`visual layers not used: ${e instanceof Error ? e.message : e}`));
  }, []);
  const pick = useMemo(() => albedoLayerFor(v, visualLayers?.layers), [v.dataset, visualLayers]); // eslint-disable-line react-hooks/exhaustive-deps
  const pickId = pick?.layer.id ?? null;
  useEffect(() => {
    if (!pick) {
      setAlbedo(null);
      return;
    }
    let live = true;
    let tex: THREE.Texture | null = null;
    new THREE.TextureLoader().load(`visual/${pick.layer.artifact.path.split('/').pop()}`, (t) => {
      if (!live) {
        t.dispose();
        return;
      }
      t.colorSpace = THREE.NoColorSpace; // brightness data with a documented display stretch, not sRGB colour
      t.anisotropy = 8;
      tex = t;
      setAlbedo({ texture: t, layer: pick.layer });
    });
    return () => {
      live = false;
      tex?.dispose();
    };
  }, [pickId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    useSurface.getState().setSceneFacts({ contextLoaded: !!ctx, albedoCoverage: albedo && pick ? pick.coverage : 0 });
    return () => useSurface.getState().setSceneFacts({ contextLoaded: false, albedoCoverage: 0 });
  }, [ctx, albedo, pick]);

  // 5D Phase 9.4: near-field LOD tiles for this dataset when they were built (display only; opt-in toggle, or ?lod=1)
  const [lod, setLod] = useState<LodManifest | null>(null);
  const lodOn = useLod((s) => s.on);
  useEffect(() => {
    let live = true;
    setLod(null);
    loadLodManifest(siteId)
      .then((m) => live && setLod(m))
      .catch((e) => console.warn(`near-field LOD tiles not used: ${e instanceof Error ? e.message : e}`));
    return () => {
      live = false;
    };
  }, [siteId]);
  const lodDrawn = lod && lodOn ? lod : null;

  // the global Moon is an overlay: the terrain canvas stays mounted underneath (paused), so nothing is torn down mid-frame
  const globe = useSurface((s) => s.globe);

  return (
    <div className="scene3d" data-testid="scene3d" data-globe={globe ? 'on' : 'off'} data-context={ctx ? 'loaded' : 'none'} data-albedo={albedo ? albedo.layer.id : 'none'} data-lod={lodDrawn ? 'on' : lod ? 'available' : 'none'} ref={wrap}>
      <Canvas
        shadows
        dpr={[1, 2]}
        camera={{ position: [half * 0.26, half * 0.12, half * 0.34], fov: 42, near: 0.3, far: half * 20 }}
        gl={{ antialias: true, logarithmicDepthBuffer: true, toneMapping: THREE.AgXToneMapping, toneMappingExposure: 1.2 }}
        frameloop={active && !globe ? 'always' : 'never'}
      >
        <Scene v={v} ctx={ctx} albedo={albedo} lod={lodDrawn} />
      </Canvas>
      {/* display-only vertical exaggeration, overlaid on the stage (out of the layout flow) */}
      {ctx && !globe && <ExaggerationPicker />}
      <SightLabels />
      {globe && (
        <GlobalMoon
          v={v}
          onEnter={() => {
            useSurface.getState().setGlobe(false);
            useCamera.getState().request(ctx ? 'context' : 'regional'); // arrive on the regional framing, then the user picks Approach
          }}
        />
      )}
      <RidgeCaption v={v} cropHalfM={half} selectedOnly />
      <LightTag v={v} />
      {lod && <LodPanel manifest={lod} />}
      <details className="scene-note">
        <summary>About this view</summary>
        DEM {dem.n}×{dem.n} @ {dem.spacing} m (display decimated to ≤{MAX_AXIS}²), 1:1 vertical. Observer{' '}
        {obs.source === 'bundle' ? `from bundle, mast ${obs.mast} m` : 'placed at crop centre for display (no scenario in bundle)'}. Rays end at the bundle's first-hit
        distance; red octahedra are bundle critical cells — click one. Markers keep a constant screen size; the mast and terrain are true scale.
        The light dots are the selected ridge of record: the bundle's per-bin controlling points. Lighting follows the bundle's Sun azimuth;
        its elevation is shown at no less than 0.5° so the terrain stays readable, unless “Light: true Sun elevation” is on (display only; shadows and the faint fill light are illustrative, not the solver's).
        {ctx
          ? `${ctx.meta.mid ? ` Around the 5 m crop: ${ctx.meta.mid.n}² × ${ctx.meta.mid.spacingM} m block means of the PGDA 78 5 m tile (about ±4 km), then` : ' Around the 5 m crop:'} the ${ctx.meta.regional.product} crop (${ctx.meta.regional.n}² × ${ctx.meta.regional.spacingM} m), true scale, display context only. Shadows here come from horizon maps of these displayed crops plus the bundle skyline for terrain farther than ${(ctx.meta.displayReachM / 1000).toFixed(0)} km; they are a display model and never set a visible/blocked state.`
          : ''}
      </details>
    </div>
  );
}

/** On-screen statement of the lighting mode, so the 0.5° display clamp is never silent. */
function LightTag({ v }: { v: View }) {
  const trueLight = useUi((s) => s.trueLight);
  const el = v.sun.el;
  return (
    <div className="light-tag" data-testid="light-tag">
      {trueLight
        ? `Light: true Sun elevation ${el.toFixed(2)}° · scientific, no fill${el <= 0 ? ' · Sun below the horizon' : ''}`
        : `Light: display · Sun ${el.toFixed(2)}°${el < 0.5 ? ' shown as 0.50°' : ''} · relief fill on (display only)`}
    </div>
  );
}

/**
 * DOM caption over a 3D scene naming the highlighted ridge of record (bundle values). `cropHalfM` = half-width of the DEM
 * crop being drawn: a ridge farther than that is declared outside the crop and is not drawn (nothing is invented).
 */
export function RidgeCaption({ v, cropHalfM, selectedOnly = false }: { v: View; cropHalfM?: number; selectedOnly?: boolean }) {
  const { focus } = useRidgeFocus(v);
  // in the 3D stage the instrument already names the ridge blocking a target now; the caption appears for an explicit selection
  // or in the Ridge of Record camera view (which must say when the ridge lies beyond the crop)
  const camView = useCamera((s) => s.view);
  if (!focus?.ridge || (selectedOnly && focus.source !== 'selected' && camView !== 'ridge')) return null;
  const r = focus.ridge;
  const dMin = typeof r.distanceM === 'number' ? r.distanceM : r.distanceM.min;
  const outside = cropHalfM !== undefined && Number.isFinite(dMin) && dMin > cropHalfM;
  const why = focus.source === 'selected' ? 'selected' : `blocking the ${focus.source === 'sun' ? 'Sun' : 'Earth'} now`;
  return (
    <div className={`ridge-caption ${outside ? 'is-outside' : ''}`} data-testid={outside ? 'ridge-3d-outside' : 'ridge-3d-label'}>
      <span className="rcap-kicker">Ridge of record · {why}</span>
      <strong>{r.label ?? r.id}</strong>
      <span>
        {fmtRidgeDistance(r)} away · az {r.azimuthDeg[0].toFixed(1)}–{r.azimuthDeg[1].toFixed(1)}°
        {r.reliefM !== undefined ? ` · ${r.reliefM >= 0 ? '+' : '−'}${Math.abs(r.reliefM).toFixed(Math.abs(r.reliefM) < 100 ? 2 : 0)} m vs site ground` : ''}
      </span>
      <span className="rcap-note">
        {outside
          ? `beyond this ${((cropHalfM! * 2) / 1000).toFixed(0)} km DEM crop: not drawn here (${r.dem === 'far_80m' ? '80 m regional DEM' : (r.dem ?? 'source')}); see the horizon chart`
          : cropHalfM !== undefined
            ? 'light dots = the bundle’s per-bin controlling points on the true-scale DEM'
            : 'light arc = this ridge’s span on the horizon silhouette'}
      </span>
    </div>
  );
}
