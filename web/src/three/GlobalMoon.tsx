import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Line, OrbitControls } from '@react-three/drei';
import { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { easeCamera, reducedMotion } from '../store/camera';
import type { View } from '../store/view';
import { useWheelGuard } from './wheelGuard';

/**
 * Global Moon: VISUAL CONTEXT ONLY. The NASA SVS 14959 LRO Moon model (compact GLB) with a marker at the selected site,
 * so the user sees where on the Moon the terrain crop is before entering it. Nothing here is numerical: the mesh is
 * never sampled, its lighting is a display light (not the Sun at the bundle time), and the source notes pinching at the
 * poles of this model. Marker mapping: Y is the north pole, longitude measured from +Z toward +X (east-positive); the
 * model's longitude origin was not verified against its texture, which at 89.5° S moves the marker by at most the
 * site's ~15 km distance from the pole.
 */
const R = 1; // model radius after normalisation
export const GLOBE_ASSET = 'globe/NASA_SVS_moon_small.glb';

export function angularPoint(latDeg: number, lonEastDeg: number, radius: number): THREE.Vector3 {
  const lat = (latDeg * Math.PI) / 180;
  const lon = (lonEastDeg * Math.PI) / 180;
  const c = Math.cos(lat);
  return new THREE.Vector3(radius * c * Math.sin(lon), radius * Math.sin(lat), radius * c * Math.cos(lon));
}

function Moon({ onReady, onFail }: { onReady: () => void; onFail: (m: string) => void }) {
  const [model, setModel] = useState<THREE.Object3D | null>(null);
  useEffect(() => {
    let live = true;
    let loaded: THREE.Object3D | null = null;
    new GLTFLoader().load(
      GLOBE_ASSET,
      (gltf) => {
        if (!live) return;
        const m = gltf.scene;
        const sphere = new THREE.Box3().setFromObject(m).getBoundingSphere(new THREE.Sphere());
        const s = R / sphere.radius;
        m.scale.setScalar(s);
        m.position.copy(sphere.center).multiplyScalar(-s);
        m.traverse((n) => {
          const mesh = n as THREE.Mesh;
          if (!mesh.isMesh) return;
          for (const mat of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
            const std = mat as THREE.MeshStandardMaterial;
            if (std.map) std.map.colorSpace = THREE.SRGBColorSpace;
            if ('roughness' in std) std.roughness = 1;
            if ('metalness' in std) std.metalness = 0;
            std.needsUpdate = true;
          }
        });
        loaded = m;
        setModel(m);
        onReady();
      },
      undefined,
      (e) => live && onFail(e instanceof Error ? e.message : String(e)),
    );
    return () => {
      live = false;
      loaded?.traverse((n) => {
        const mesh = n as THREE.Mesh;
        if (!mesh.isMesh) return;
        mesh.geometry.dispose();
        for (const mat of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
          (mat as THREE.MeshStandardMaterial).map?.dispose();
          mat.dispose();
        }
      });
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return model ? <primitive object={model} /> : null;
}

function Flight({ site, go }: { site: THREE.Vector3; go: number }) {
  const { camera, controls, gl } = useThree() as unknown as { camera: THREE.PerspectiveCamera; controls: { target: THREE.Vector3; update: () => void } | null; gl: THREE.WebGLRenderer };
  const anim = useRef<{ p0: THREE.Vector3; p1: THREE.Vector3; t0: number } | null>(null);
  const end = useMemo(() => {
    // above the site, pulled back toward the equator side so the limb and the pole are both in frame
    const out = site.clone().normalize();
    const side = new THREE.Vector3(out.x, 0, out.z).lengthSq() > 1e-6 ? new THREE.Vector3(out.x, 0, out.z).normalize() : new THREE.Vector3(0, 0, 1);
    return out.multiplyScalar(2.35).add(side.multiplyScalar(0.55));
  }, [site]);
  useEffect(() => {
    if (go === 0) return;
    if (reducedMotion()) {
      camera.position.copy(end);
      controls?.update();
      return;
    }
    anim.current = { p0: camera.position.clone(), p1: end.clone(), t0: performance.now() };
  }, [go]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const stop = () => (anim.current = null);
    const key = (e: KeyboardEvent) => e.key === 'Escape' && stop();
    const el = gl.domElement;
    el.addEventListener('pointerdown', stop);
    el.addEventListener('wheel', stop, { passive: true });
    window.addEventListener('keydown', key);
    return () => {
      el.removeEventListener('pointerdown', stop);
      el.removeEventListener('wheel', stop);
      window.removeEventListener('keydown', key);
    };
  }, [gl]);
  useFrame(() => {
    const a = anim.current;
    if (!a) return;
    const k = Math.min(1, (performance.now() - a.t0) / 2400);
    const e = easeCamera(k);
    // great-circle style blend: interpolate direction and distance separately so the camera never cuts through the Moon
    const d = a.p0.length() * (1 - e) + a.p1.length() * e;
    camera.position.copy(a.p0.clone().normalize().lerp(a.p1.clone().normalize(), e).normalize().multiplyScalar(Math.max(d, 1.5)));
    controls?.update();
    if (k >= 1) anim.current = null;
  });
  return null;
}

export default function GlobalMoon({ v, onEnter }: { v: View; onEnter: () => void }) {
  const wrap = useRef<HTMLDivElement>(null);
  useWheelGuard(wrap);
  const [state, setState] = useState<'loading' | 'ready' | 'failed'>('loading');
  const [why, setWhy] = useState('');
  const [go, setGo] = useState(0);
  const s = v.dataset.site;
  const site = useMemo(() => angularPoint(s.latitudePlanetocentricDeg, s.longitudeEastDeg, R), [s.latitudePlanetocentricDeg, s.longitudeEastDeg]);
  const tip = useMemo(() => site.clone().setLength(R * 1.16), [site]);
  useEffect(() => {
    if (state === 'ready') setGo((g) => g + 1); // fly to the site once the model is visible
  }, [state]);
  return (
    <div className="globe-layer" data-testid="global-moon" data-loaded={state === 'ready'} ref={wrap}>
      <Canvas dpr={[1, 2]} camera={{ position: [0, -0.9, 3.3], fov: 36, near: 0.05, far: 60 }} gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.0 }}>
        <color attach="background" args={['#050505']} />
        {/* display light only: NOT the Sun at the bundle time (the south pole would be near-dark under the real one) */}
        <hemisphereLight args={['#ffffff', '#2a2a2a', 1.15]} />
        <directionalLight position={[2, -3, 2.5]} intensity={1.6} />
        <Moon onReady={() => setState('ready')} onFail={(m) => { setWhy(m); setState('failed'); }} />
        <Line points={[site.clone().setLength(R * 1.004), tip]} color="#E8A53C" lineWidth={2} />
        <mesh position={tip}>
          <sphereGeometry args={[0.012, 16, 16]} />
          <meshBasicMaterial color="#E8A53C" toneMapped={false} />
        </mesh>
        <Flight site={site} go={go} />
        <OrbitControls makeDefault target={[0, 0, 0]} enablePan={false} minDistance={1.25} maxDistance={8} enableDamping dampingFactor={0.08} />
      </Canvas>
      <div className="globe-card" data-testid="globe-card">
        <span className="lab">Global Moon · visual context</span>
        <strong>{s.name}</strong>
        <span>
          {Math.abs(s.latitudePlanetocentricDeg).toFixed(4)}° {s.latitudePlanetocentricDeg < 0 ? 'S' : 'N'} · {Math.abs(s.longitudeEastDeg).toFixed(4)}° {s.longitudeEastDeg < 0 ? 'W' : 'E'}
        </span>
        <span className="globe-note">
          NASA SVS 14959 LRO Moon model (compact GLB). VISUAL CONTEXT, not numerical terrain: never sampled by any calculation. Display lighting, not
          the Sun at the bundle time. The source notes artifacts near the poles of this model.
        </span>
        {state === 'loading' && <span className="globe-note">Loading the Moon model…</span>}
        {state === 'failed' && <span className="globe-note" role="alert">Moon model could not be loaded ({why}). The terrain view is unaffected.</span>}
        <div className="actions">
          <button type="button" className="btn" onClick={() => setGo((g) => g + 1)} data-testid="globe-fly" disabled={state !== 'ready'}>
            Fly to site
          </button>
          <button type="button" className="btn primary" onClick={onEnter} data-testid="globe-enter">
            Enter terrain →
          </button>
        </div>
      </div>
    </div>
  );
}
