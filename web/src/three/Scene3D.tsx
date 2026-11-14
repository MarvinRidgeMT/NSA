import { Canvas } from '@react-three/fiber';
import { Html, Line, OrbitControls } from '@react-three/drei';
import { useMemo } from 'react';
import * as THREE from 'three';
import { gridDirection } from '../bundle/frame';
import type { Dem } from '../bundle/types';
import { usePolaris } from '../store/store';
import type { View } from '../store/view';
import HorizonDome from './HorizonDome';

/**
 * Axes: bundle grid (x = grid east, y = grid north, z = up, metres) is drawn as
 * three.js (x, z, -y) with the observer at the origin. 1 unit = 1 m. NO vertical
 * exaggeration: the terrain looks flat because lunar polar terrain at this scale is.
 */
const toThree = (gx: number, gy: number, gz: number) => new THREE.Vector3(gx, gz, -gy);
const MAX_AXIS = 201; // display decimation only

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
    const c0 = new THREE.Color('#2b3440');
    const c1 = new THREE.Color('#b9b2a4');
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

function Ray({
  v,
  obs,
  target,
  edge,
}: {
  v: View;
  obs: Observer;
  target: 'sun' | 'earth';
  edge: number;
}) {
  const t = v[target];
  const dir = gridDirection(v.basis, t.az, t.el);
  const top = toThree(0, 0, obs.mast);
  // clip at the bundle's first-hit distance (horizontal metres); otherwise run to the crop edge
  const horiz = t.firstHitM ?? edge;
  const len = horiz / Math.max(Math.cos((t.el * Math.PI) / 180), 1e-6);
  const end = top.clone().add(toThree(dir[0] * len, dir[1] * len, dir[2] * len));
  const state = t.visible === undefined ? 'unknown' : t.visible === null ? 'transition' : t.visible ? 'clear' : 'blocked';
  const color = target === 'sun' ? '#f2b84b' : '#5aa9e6';
  return (
    <group>
      <Line points={[top, end]} color={color} lineWidth={state === 'blocked' ? 3 : 2} dashed={state === 'unknown'} dashSize={60} gapSize={40} />
      {state === 'blocked' && (
        <mesh position={end}>
          <sphereGeometry args={[Math.max(edge / 180, 8), 16, 16]} />
          <meshBasicMaterial color="#e5534b" />
        </mesh>
      )}
      <Html position={end} center distanceFactor={undefined} zIndexRange={[10, 0]}>
        <span className={`tag3d ${target}`}>
          {target === 'sun' ? 'Sun' : 'Earth'} · {state === 'unknown' ? 'not evaluated' : state}
        </span>
      </Html>
    </group>
  );
}

function Scene({ v }: { v: View }) {
  const obs = observerFor(v);
  const dem = v.dataset.dem!;
  const { g, halfExtent } = useDemGeometry(dem, obs);
  const edge = dem.validCoverageRadiusM ?? halfExtent;
  const { selectFailure } = usePolaris.getState();
  const sunDir = gridDirection(v.basis, v.sun.az, Math.max(v.sun.el, 0.5));
  const light = toThree(sunDir[0], sunDir[1], sunDir[2]).multiplyScalar(halfExtent * 2);
  const failures = v.series?.failures ?? [];
  const n = gridDirection(v.basis, 0, 0);
  const north = toThree(n[0], n[1], 0).multiplyScalar(halfExtent * 0.9);

  return (
    <>
      <color attach="background" args={['#05080d']} />
      <ambientLight intensity={0.35} />
      <hemisphereLight args={['#c9d4e3', '#1a1f27', 0.9]} />
      <directionalLight position={light} intensity={2.2} />
      <mesh geometry={g} receiveShadow>
        <meshStandardMaterial vertexColors roughness={0.95} metalness={0} side={THREE.DoubleSide} />
      </mesh>
      {/* observer mast, drawn to scale */}
      <mesh position={toThree(0, 0, obs.mast / 2)}>
        <cylinderGeometry args={[Math.max(halfExtent / 400, 1), Math.max(halfExtent / 400, 1), obs.mast, 12]} />
        <meshBasicMaterial color="#45d9c9" />
      </mesh>
      <mesh position={toThree(0, 0, obs.mast)}>
        <sphereGeometry args={[Math.max(halfExtent / 250, 3), 16, 16]} />
        <meshBasicMaterial color="#45d9c9" />
      </mesh>
      <Ray v={v} obs={obs} target="sun" edge={edge} />
      <Ray v={v} obs={obs} target="earth" edge={edge} />
      {failures.map((f) =>
        f.firstHit ? (
          <mesh
            key={f.id}
            position={toThree(f.firstHit.xM - obs.x, f.firstHit.yM - obs.y, f.firstHit.heightM - obs.ground + 4)}
            onClick={(e) => {
              e.stopPropagation();
              selectFailure(f.id);
            }}
            onPointerOver={() => (document.body.style.cursor = 'pointer')}
            onPointerOut={() => (document.body.style.cursor = '')}
          >
            <octahedronGeometry args={[Math.max(halfExtent / 120, 10)]} />
            <meshBasicMaterial color={v.failure?.id === f.id ? '#ffffff' : '#e5534b'} />
          </mesh>
        ) : null,
      )}
      <Html position={north} center>
        <span className="tag3d">local N</span>
      </Html>
      <OrbitControls makeDefault target={[0, 0, 0]} maxPolarAngle={Math.PI * 0.495} />
    </>
  );
}

export default function Scene3D({ v }: { v: View }) {
  if (!v.dataset.dem) return <HorizonDome v={v} />;
  return <DemScene v={v} />;
}

function DemScene({ v }: { v: View }) {
  const dem = v.dataset.dem!;
  const half = ((dem.n - 1) * dem.spacing) / 2;
  const obs = observerFor(v);
  return (
    <div className="scene3d" data-testid="scene3d">
      <Canvas camera={{ position: [half * 0.7, half * 0.42, half * 0.95], fov: 45, near: 1, far: half * 20 }} gl={{ preserveDrawingBuffer: true }}>
        <Scene v={v} />
      </Canvas>
      <p className="scene-note">
        DEM {dem.n}×{dem.n} @ {dem.spacing} m (display decimated to ≤{MAX_AXIS}²), 1:1 vertical. Observer{' '}
        {obs.source === 'bundle' ? `from bundle, mast ${obs.mast} m` : 'placed at crop centre for display (no scenario in bundle)'}. Rays end at the bundle's first-hit
        distance; red octahedra are bundle critical cells — click one.
      </p>
    </div>
  );
}
