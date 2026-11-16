import { Canvas } from '@react-three/fiber';
import { Html, Line, OrbitControls } from '@react-three/drei';
import { useMemo, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { binRuns, useRidgeFocus } from '../store/ridge';
import { RidgeCaption } from './Scene3D';
import { useWheelGuard } from './wheelGuard';
import * as THREE from 'three';
import type { View } from '../store/view';
import { CameraRig, type Framing } from './CameraRig';
import type { CameraViewId } from '../store/camera';

/**
 * 3D view for bundles that ship a skyline but no DEM grid (science-bundle-v2).
 * Drawn in LOCAL east/north/up straight from bundle azimuths (no longitude rotation, per the contract).
 * Every horizon point is placed at the same radius R0 with height R0·tan(elevation), so the angle seen
 * from the observer's eye is exactly the bundle's skyline angle. True distances are shown by colour.
 * three.js axes: x = east, y = up, z = -north.
 */
const R0 = 1000;
const enu = (az: number, el: number, r = R0) => {
  const a = (az * Math.PI) / 180;
  const e = (el * Math.PI) / 180;
  return new THREE.Vector3(r * Math.sin(a) * Math.cos(e), r * Math.sin(e), -r * Math.cos(a) * Math.cos(e));
};
/** a point on the horizon wall at azimuth az whose elevation angle from the eye is el */
const wall = (az: number, el: number) => {
  const a = (az * Math.PI) / 180;
  return new THREE.Vector3(R0 * Math.sin(a), R0 * Math.tan((el * Math.PI) / 180), -R0 * Math.cos(a));
};

function distColor(d: number | null | undefined) {
  // near (≤1 km) teal -> far (≥100 km) slate, log scale; unknown = slate
  if (d == null || !Number.isFinite(d)) return new THREE.Color('#4b4a45');
  const t = Math.min(Math.max((Math.log10(d) - 3) / 2, 0), 1);
  return new THREE.Color('#B8C9C4').lerp(new THREE.Color('#4b4a45'), t);
}

/** Ridge of Record highlight: the ridge's whole skyline span on the horizon wall, and a short eased camera move to face it. */
function RidgeHighlight({ v, sk }: { v: View; sk: NonNullable<NonNullable<View['series']>['skyline']> }) {
  const { focus } = useRidgeFocus(v);
  const { camera, controls } = useThree() as unknown as { camera: THREE.PerspectiveCamera; controls: { target: THREE.Vector3; update: () => void } | null };
  const anim = useRef<{ from: THREE.Vector3; to: THREE.Vector3; t0: number } | null>(null);
  const last = useRef<string | null>(null);
  const bins = (focus?.bins ?? []).filter((b) => sk.elevationDeg[b] !== null && Number.isFinite(sk.elevationDeg[b] as number));
  const key = focus && bins.length ? `${focus.source}:${focus.ridgeIdx ?? bins[0]}` : null;
  const mid = bins.length ? bins[Math.floor(bins.length / 2)] : null;
  // fly only for an explicit selection; an auto-highlight (target just became blocked) must not steal the camera
  if (key !== last.current && focus?.source === 'selected' && mid !== null && !(typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches)) {
    const dir = wall(sk.azimuthDeg[mid], 0).normalize();
    anim.current = { from: camera.position.clone(), to: dir.clone().multiplyScalar(-R0 * 0.55).add(new THREE.Vector3(0, R0 * 0.12, 0)), t0: performance.now() };
  }
  last.current = key;
  useFrame(() => {
    const a = anim.current;
    if (!a) return;
    const k = Math.min(1, (performance.now() - a.t0) / 900);
    const e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
    camera.position.copy(a.from).lerp(a.to, e);
    if (controls) {
      controls.target.set(0, 0, 0);
      controls.update();
    }
    if (k >= 1) anim.current = null;
  });
  if (!bins.length || mid === null) return null;
  const runs = binRuns(bins);
  const top = wall(sk.azimuthDeg[mid], sk.elevationDeg[mid] as number);
  return (
    <group>
      {runs.map(([b0, b1]) => {
        const pts: THREE.Vector3[] = [];
        for (let b = b0; b <= b1; b++) pts.push(wall(sk.azimuthDeg[b], sk.elevationDeg[b] as number).add(new THREE.Vector3(0, 3, 0)));
        if (pts.length === 1) pts.push(pts[0].clone().add(new THREE.Vector3(0, 30, 0)));
        return <Line key={b0} points={pts} color="#ECE7DD" lineWidth={5} />;
      })}
      <Line points={[top.clone().add(new THREE.Vector3(0, 3, 0)), top.clone().add(new THREE.Vector3(0, 46, 0))]} color="#ECE7DD" lineWidth={2} />
    </group>
  );
}

function Dome({ v }: { v: View }) {
  const sk = v.series!.skyline!;
  const { wallGeo, top, truncPts } = useMemo(() => {
    const n = sk.azimuthDeg.length;
    const pos: number[] = [];
    const col: number[] = [];
    const idx: number[] = [];
    const top: THREE.Vector3[] = [];
    const truncPts: THREE.Vector3[][] = [];
    const floor = -3; // draw the wall down to -3° (display only)
    let k = 0;
    for (let i = 0; i <= n; i++) {
      const j = i % n;
      const el = sk.elevationDeg[j];
      const az = i === n ? 360 : sk.azimuthDeg[j];
      if (el === null || !Number.isFinite(el)) {
        top.push(new THREE.Vector3(Number.NaN, Number.NaN, Number.NaN));
        continue;
      }
      const p = wall(az, el);
      const b = wall(az, Math.min(floor, el - 0.5));
      top.push(p);
      const c = distColor(sk.critical?.[j]?.distance_m);
      pos.push(b.x, b.y, b.z, p.x, p.y, p.z);
      col.push(c.r * 0.35, c.g * 0.35, c.b * 0.35, c.r, c.g, c.b);
      if (k > 0) idx.push(2 * (k - 1), 2 * (k - 1) + 1, 2 * k, 2 * (k - 1) + 1, 2 * k + 1, 2 * k);
      k++;
      if (sk.coverage?.[j] === 'truncated') truncPts.push([p, p.clone().add(new THREE.Vector3(0, 12, 0))]);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
    g.setIndex(idx);
    return { wallGeo: g, top: top.filter((p) => Number.isFinite(p.x)), truncPts };
  }, [sk]);

  // named camera views over the angular panorama (display only)
  const { focus } = useRidgeFocus(v);
  const frame = (id: CameraViewId): Framing | null => {
    if (id === 'approach' || id === 'regional') {
      // oblique, from the anti-Sun side, far enough that the whole skyline ring sits inside the frame
      const back = wall(v.sun.az + 180, 0).normalize();
      return { pos: back.multiplyScalar(R0 * 2.1).setY(R0 * 0.75), target: new THREE.Vector3(0, -R0 * 0.08, 0) };
    }
    if (id === 'overhead') return { pos: new THREE.Vector3(0, R0 * 2.6, 0.01), target: new THREE.Vector3(0, 0, 0) };
    if (id === 'mast') {
      const ahead = wall(v.sun.az, 0);
      return { pos: ahead.clone().normalize().multiplyScalar(-60).setY(12), target: ahead.setY(R0 * Math.tan((Math.max(v.sun.el, 0) * Math.PI) / 180)) };
    }
    if (id === 'horizon') {
      const back = wall(v.sun.az + 180, 0).normalize();
      return { pos: back.multiplyScalar(R0 * 1.55).setY(R0 * 0.16), target: new THREE.Vector3(0, R0 * 0.02, 0) };
    }
    if (id === 'ridge') {
      const r = focus?.ridge ?? v.dataset.derived?.attribution?.ridges.find((x) => x.ofRecord) ?? null;
      if (!r) return null;
      const az = (r.azimuthDeg[0] + r.azimuthDeg[1]) / 2;
      const dir = wall(az, 0).normalize();
      return { pos: dir.clone().multiplyScalar(-R0 * 0.55).add(new THREE.Vector3(0, R0 * 0.12, 0)), target: dir.multiplyScalar(R0 * 0.6) };
    }
    return null;
  };

  const ray = (key: 'sun' | 'earth', color: string) => {
    const t = v[key];
    const end = enu(t.az, t.el, R0 * 1.25);
    const state = t.visible === undefined ? 'not evaluated' : t.visible === null ? 'transition' : t.visible ? 'clear' : 'blocked';
    const label = `${key === 'sun' ? 'Sun' : 'Earth'} · ${state}${t.marginDeg !== null ? ` · ${t.marginDeg >= 0 ? '+' : ''}${t.marginDeg.toFixed(2)}°` : ''}`;
    return (
      <group>
        <Line points={[new THREE.Vector3(0, 0, 0), end]} color={color} lineWidth={state === 'blocked' ? 3 : 2} dashed={key === 'earth'} dashSize={30} gapSize={20} />
        <mesh position={end}>
          <sphereGeometry args={[key === 'sun' ? 22 : 16, 20, 20]} />
          <meshBasicMaterial color={color} />
        </mesh>
        <Html position={end} center zIndexRange={[10, 0]}>
          <span className={`tag3d ${key}`}>{label}</span>
        </Html>
      </group>
    );
  };

  return (
    <>
      <color attach="background" args={['#050505']} />
      <CameraRig frame={frame} frameKey={`${v.dataset.siteId}:${v.series?.id ?? ''}`} />
      <mesh geometry={wallGeo}>
        <meshBasicMaterial vertexColors side={THREE.DoubleSide} transparent opacity={0.75} />
      </mesh>
      <Line points={top} color="#ECE7DD" lineWidth={1.25} />
      {truncPts.map((p, i) => (
        <Line key={i} points={p} color="#ECE7DD" lineWidth={2} dashed dashSize={4} gapSize={4} />
      ))}
      <gridHelper args={[R0 * 2.2, 22, '#2a2925', '#151513']} position={[0, wall(0, -3).y - 1, 0]} />
      {(['N', 'E', 'S', 'W'] as const).map((c, i) => (
        <Html key={c} position={enu(i * 90, -2.5, R0 * 1.08)} center>
          <span className="tag3d">{c}</span>
        </Html>
      ))}
      <mesh>
        <sphereGeometry args={[10, 16, 16]} />
        <meshBasicMaterial color="#ECE7DD" />
      </mesh>
      {ray('sun', '#E8A53C')}
      {ray('earth', '#7FA8DA')}
      <RidgeHighlight v={v} sk={sk} />
      <OrbitControls makeDefault target={[0, 0, 0]} minDistance={50} maxDistance={R0 * 4} />
    </>
  );
}

export default function HorizonDome({ v, active = true }: { v: View; active?: boolean }) {
  const wrap = useRef<HTMLDivElement>(null);
  useWheelGuard(wrap);
  if (!v.series?.skyline) return <p className="note">No skyline in this bundle.</p>;
  const crit = v.series.skyline.critical?.map((c) => c.distance_m).filter((d): d is number => d != null && Number.isFinite(d)) ?? [];
  return (
    <div className="scene3d" data-testid="horizon-dome" ref={wrap}>
      <Canvas
        dpr={[1, 2]}
        camera={{ position: [R0 * 0.9, R0 * 0.55, R0 * 1.3], fov: 46, near: 1, far: R0 * 20 }}
        gl={{ antialias: true }}
        frameloop={active ? 'always' : 'never'}
      >
        <Dome v={v} />
      </Canvas>
      <RidgeCaption v={v} />
      <div className="dome-legend">
        <span>horizon-setting terrain:</span> <span className="dk near" /> ≤1 km <span className="dk ramp" /> <span className="dk far" /> ≥100 km
        {crit.length > 0 && (
          <span className="muted">
            {' '}
            (this site: {(Math.min(...crit) / 1000).toFixed(2)}–{(Math.max(...crit) / 1000).toFixed(0)} km)
          </span>
        )}
      </div>
      <details className="scene-note">
        <summary>About this view</summary>
        Angular panorama from the observer’s eye (mast {v.series.observer?.mastM ?? '?'} m): every horizon point is drawn at the same radius so its elevation angle is exactly the
        bundle’s skyline value; shade shows how far away the blocking terrain really is (light = near, dark = far). Local east/north/up, no longitude rotation. No DEM grid ships with this bundle.
      </details>
    </div>
  );
}
