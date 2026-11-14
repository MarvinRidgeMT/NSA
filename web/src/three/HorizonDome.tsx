import { Canvas } from '@react-three/fiber';
import { Html, Line, OrbitControls } from '@react-three/drei';
import { useMemo, useRef } from 'react';
import { useWheelGuard } from './wheelGuard';
import * as THREE from 'three';
import type { View } from '../store/view';

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
  // near (≤1 km) teal -> far (≥100 km) violet, log scale; unknown = slate
  if (d == null || !Number.isFinite(d)) return new THREE.Color('#5b6577');
  const t = Math.min(Math.max((Math.log10(d) - 3) / 2, 0), 1);
  return new THREE.Color('#45d9c9').lerp(new THREE.Color('#9d7bea'), t);
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

  const ray = (key: 'sun' | 'earth', color: string) => {
    const t = v[key];
    const end = enu(t.az, t.el, R0 * 1.25);
    const state = t.visible === undefined ? 'not evaluated' : t.visible === null ? 'transition' : t.visible ? 'clear' : 'blocked';
    const label = `${key === 'sun' ? 'Sun' : 'Earth'} · ${state}${t.marginDeg !== null ? ` · ${t.marginDeg >= 0 ? '+' : ''}${t.marginDeg.toFixed(2)}°` : ''}`;
    return (
      <group>
        <Line points={[new THREE.Vector3(0, 0, 0), end]} color={color} lineWidth={state === 'blocked' ? 3 : 2} dashed={state === 'blocked'} dashSize={30} gapSize={20} />
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
      <color attach="background" args={['#05080d']} />
      <mesh geometry={wallGeo}>
        <meshBasicMaterial vertexColors side={THREE.DoubleSide} transparent opacity={0.75} />
      </mesh>
      <Line points={top} color="#e8eef6" lineWidth={1.5} />
      {truncPts.map((p, i) => (
        <Line key={i} points={p} color="#e0a73a" lineWidth={2} />
      ))}
      <gridHelper args={[R0 * 2.2, 22, '#2a3546', '#151d29']} position={[0, wall(0, -3).y - 1, 0]} />
      {(['N', 'E', 'S', 'W'] as const).map((c, i) => (
        <Html key={c} position={enu(i * 90, -2.5, R0 * 1.08)} center>
          <span className="tag3d">{c}</span>
        </Html>
      ))}
      <mesh>
        <sphereGeometry args={[10, 16, 16]} />
        <meshBasicMaterial color="#45d9c9" />
      </mesh>
      {ray('sun', '#f2b84b')}
      {ray('earth', '#5aa9e6')}
      <OrbitControls makeDefault target={[0, 0, 0]} minDistance={50} maxDistance={R0 * 4} />
    </>
  );
}

export default function HorizonDome({ v }: { v: View }) {
  const wrap = useRef<HTMLDivElement>(null);
  useWheelGuard(wrap);
  if (!v.series?.skyline) return <p className="note">No skyline in this bundle.</p>;
  const crit = v.series.skyline.critical?.map((c) => c.distance_m).filter((d): d is number => d != null && Number.isFinite(d)) ?? [];
  return (
    <div className="scene3d" data-testid="horizon-dome" ref={wrap}>
      <Canvas camera={{ position: [R0 * 0.9, R0 * 0.55, R0 * 1.3], fov: 50, near: 1, far: R0 * 20 }} gl={{ preserveDrawingBuffer: true }}>
        <Dome v={v} />
      </Canvas>
      <div className="dome-legend">
        <span>horizon-setting terrain:</span> <span className="dk near" /> ≤1 km <span className="dk ramp" /> <span className="dk far" /> ≥100 km
        {crit.length > 0 && (
          <span className="muted">
            {' '}
            (this site: {(Math.min(...crit) / 1000).toFixed(2)}–{(Math.max(...crit) / 1000).toFixed(0)} km)
          </span>
        )}
      </div>
      <p className="scene-note">
        Angular panorama from the observer’s eye (mast {v.series.observer?.mastM ?? '?'} m): every horizon point is drawn at the same radius so its elevation angle is exactly the
        bundle’s skyline value; colour shows how far away the blocking terrain really is. Local east/north/up, no longitude rotation. No DEM grid ships with this bundle.
      </p>
    </div>
  );
}
