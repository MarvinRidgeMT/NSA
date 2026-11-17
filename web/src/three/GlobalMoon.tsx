import { Canvas, useFrame, useThree, type ThreeEvent } from '@react-three/fiber';
import { Line, OrbitControls } from '@react-three/drei';
import { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';
import { easeCamera, reducedMotion } from '../store/camera';
import type { View } from '../store/view';
import { useWheelGuard } from './wheelGuard';
import { BLENDER_GLOBE_COMMAND, globeOrder, loadGlobeManifest, type GlobeEntry } from '../globe/globeAsset';
import { loadLayerManifest } from '../globe/layers';
import { latLonFromDir, raySphere } from '../globe/geo';
import { makeDrapeUniforms, patchGlobeMaterial, setDrape, type DrapeUniforms } from './globeLayerShader';
import { useGlobe } from '../store/globe';
import GlobeLayers, { type LayerDocState } from '../components/GlobeLayers';
import QueryPanel from '../components/QueryPanel';

/**
 * Global Moon: VISUAL CONTEXT + display-only v2 layers (T2). Primary mesh: the Blender whole-Moon globe
 * (blender/v2/globe.py → Draco GLB via the Khronos exporter; cube-sphere displaced from S3 pyramid level 0, heights
 * SOURCE-BASED · UNVALIDATED, WAC morphologic base colour VISUAL with shading baked in). Fallback only when that GLB is
 * absent or fails: the NASA SVS 14959 LRO Moon model. The mesh is never sampled by any calculation; the lighting is a
 * display light, not the Sun at the bundle time.
 * Frame (both): Y is the north pole, longitude measured from +Z toward +X (east-positive). The Blender globe is in km
 * with its origin at the Moon's centre, so it is scaled by 1/1737.4 and NOT re-centred (a bounding-box centre would shift
 * every lat/lon). The SVS model's longitude origin was never verified, so the layer drape is offered on the Blender globe
 * only and a click on the SVS fallback is labelled as unverified in longitude.
 */
const R = 1; // reference sphere radius after normalisation (1,737.4 km)
export const GLOBE_ASSET = 'globe/polaris_moon_globe.glb';

export function angularPoint(latDeg: number, lonEastDeg: number, radius: number): THREE.Vector3 {
  const lat = (latDeg * Math.PI) / 180;
  const lon = (lonEastDeg * Math.PI) / 180;
  const c = Math.cos(lat);
  return new THREE.Vector3(radius * c * Math.sin(lon), radius * Math.sin(lat), radius * c * Math.cos(lon));
}

function makeLoader(entry: GlobeEntry): GLTFLoader {
  const l = new GLTFLoader();
  if (entry.draco) {
    const d = new DRACOLoader();
    d.setDecoderPath('draco/');
    l.setDRACOLoader(d);
  }
  return l;
}

function disposeTree(o: THREE.Object3D | null) {
  o?.traverse((n) => {
    const mesh = n as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.geometry.dispose();
    for (const mat of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
      (mat as THREE.MeshStandardMaterial).map?.dispose();
      mat.dispose();
    }
  });
}

function Moon({ order, drape, onReady, onFail }: { order: GlobeEntry[]; drape: DrapeUniforms; onReady: (e: GlobeEntry, fellBack: string) => void; onFail: (m: string) => void }) {
  const [model, setModel] = useState<THREE.Object3D | null>(null);
  useEffect(() => {
    let live = true;
    let loaded: THREE.Object3D | null = null;
    const tried: string[] = [];
    const attempt = (i: number) => {
      const entry = order[i];
      if (!entry) return live && onFail(tried.join('; '));
      makeLoader(entry).load(
        entry.url,
        (gltf) => {
          if (!live) return disposeTree(gltf.scene);
          const m = gltf.scene;
          if (entry.kind === 'blender') {
            m.scale.setScalar(R / (entry.radiusKm ?? 1737.4)); // km -> reference radius 1, origin = Moon centre
          } else {
            // radius = half the largest box extent (the box's own bounding sphere is sqrt(3) too large for a sphere,
            // which drew the old SVS globe at 0.58 of the marker radius)
            const box = new THREE.Box3().setFromObject(m);
            const size = box.getSize(new THREE.Vector3());
            const s = R / (Math.max(size.x, size.y, size.z) / 2);
            m.scale.setScalar(s);
            m.position.copy(box.getCenter(new THREE.Vector3())).multiplyScalar(-s);
          }
          m.traverse((n) => {
            const mesh = n as THREE.Mesh;
            if (!mesh.isMesh) return;
            for (const mat of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
              const std = mat as THREE.MeshStandardMaterial;
              if (std.map) std.map.colorSpace = THREE.SRGBColorSpace;
              if ('roughness' in std) std.roughness = 1;
              if ('metalness' in std) std.metalness = 0;
              if (entry.kind === 'blender') patchGlobeMaterial(std, drape);
              std.needsUpdate = true;
            }
          });
          loaded = m;
          setModel(m);
          onReady(entry, tried.join('; '));
        },
        undefined,
        (e) => {
          tried.push(`${entry.url}: ${e instanceof Error ? e.message : String(e)}`);
          if (live) attempt(i + 1);
        },
      );
    };
    attempt(0);
    return () => {
      live = false;
      disposeTree(loaded);
    };
  }, [order]); // eslint-disable-line react-hooks/exhaustive-deps
  return model ? <primitive object={model} /> : null;
}

function Flight({ site, go }: { site: THREE.Vector3; go: number }) {
  const { camera, controls, gl } = useThree() as unknown as { camera: THREE.PerspectiveCamera; controls: { target: THREE.Vector3; update: () => void } | null; gl: THREE.WebGLRenderer };
  const anim = useRef<{ p0: THREE.Vector3; p1: THREE.Vector3; t0: number } | null>(null);
  const end = useMemo(() => {
    // above the site, pulled back toward the equator side so the limb and the pole are both in frame
    const out = site.clone().normalize();
    const side = new THREE.Vector3(out.x, 0, out.z).lengthSq() > 1e-6 ? new THREE.Vector3(out.x, 0, out.z).normalize() : new THREE.Vector3(0, 0, 1);
    // 3.6 R out: the whole true-scale disc (radius R) fits the 36° field with the limb in view
    return out.multiplyScalar(3.6).add(side.multiplyScalar(0.8));
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

/** Click (not drag) on the globe -> lat/lon on the reference sphere. Exposes a test hook to click a given lat/lon. */
function Picker({ enabled }: { enabled: boolean }) {
  const pick = useGlobe((s) => s.pick);
  const { camera, gl } = useThree();
  useEffect(() => {
    // test/automation hook: screen position of a lat/lon on the reference sphere (null when on the far side)
    const w = window as unknown as { __polarisGlobeScreen?: (lat: number, lon: number) => { x: number; y: number } | null };
    w.__polarisGlobeScreen = (lat, lon) => {
      const p = angularPoint(lat, lon, R);
      if (p.clone().sub(camera.position).dot(p) > 0) return null; // facing away
      const v = p.clone().project(camera);
      const r = gl.domElement.getBoundingClientRect();
      return { x: r.left + ((v.x + 1) / 2) * r.width, y: r.top + ((1 - v.y) / 2) * r.height };
    };
    return () => {
      delete w.__polarisGlobeScreen;
    };
  }, [camera, gl]);
  const onClick = (e: ThreeEvent<MouseEvent>) => {
    if (!enabled || e.delta > 4) return; // a drag that rotated the globe is not a pick
    const o = e.ray.origin;
    const d = e.ray.direction;
    const t = raySphere([o.x, o.y, o.z], [d.x, d.y, d.z], R);
    if (t === null) return;
    const h = o.clone().addScaledVector(d, t);
    pick({ ...latLonFromDir(h.x, h.y, h.z), via: 'click' });
  };
  return (
    <mesh onClick={onClick}>
      <sphereGeometry args={[R, 64, 32]} />
      <meshBasicMaterial colorWrite={false} depthWrite={false} />
    </mesh>
  );
}

function Marker({ lat, lon, color, size = 0.012, stem = 1.16 }: { lat: number; lon: number; color: string; size?: number; stem?: number }) {
  const base = useMemo(() => angularPoint(lat, lon, R * 1.004), [lat, lon]);
  const tip = useMemo(() => angularPoint(lat, lon, R * stem), [lat, lon, stem]);
  return (
    <>
      <Line points={[base, tip]} color={color} lineWidth={2} />
      <mesh position={tip}>
        <sphereGeometry args={[size, 16, 16]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>
    </>
  );
}

function DrapeSync({ drape, doc, enabled, onDrawn }: { drape: DrapeUniforms; doc: LayerDocState; enabled: boolean; onDrawn: (id: string) => void }) {
  const layer = useGlobe((s) => s.layer);
  const opacity = useGlobe((s) => s.opacity);
  const invalidate = useThree((s) => s.invalidate);
  useEffect(() => {
    drape.uOpacity.value = opacity;
    invalidate();
  }, [opacity, drape, invalidate]);
  useEffect(() => {
    let live = true;
    let dispose: () => void = () => undefined;
    const l = enabled && doc.state === 'ok' && layer !== 'none' ? doc.doc.layers.find((x) => x.id === layer) ?? null : null;
    setDrape(drape, l)
      .then((d) => {
        if (!live) return d();
        dispose = d;
        onDrawn(l?.id ?? 'none');
        invalidate();
      })
      .catch((e) => console.warn(`globe layer not drawn: ${e instanceof Error ? e.message : e}`));
    return () => {
      live = false;
      dispose();
    };
  }, [layer, doc, enabled, drape, invalidate]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

export default function GlobalMoon({ v, onEnter }: { v: View; onEnter: () => void }) {
  const wrap = useRef<HTMLDivElement>(null);
  useWheelGuard(wrap);
  const [state, setState] = useState<'loading' | 'ready' | 'failed'>('loading');
  const [why, setWhy] = useState('');
  const [go, setGo] = useState(0);
  const [order, setOrder] = useState<GlobeEntry[] | null>(null);
  const [shown, setShown] = useState<{ entry: GlobeEntry; fellBack: string } | null>(null);
  const [doc, setDoc] = useState<LayerDocState>({ state: 'loading' });
  const [drawn, setDrawn] = useState('none');
  const drape = useMemo(makeDrapeUniforms, []);
  const { tab, setTab, picked, nearest } = useGlobe();
  const s = v.dataset.site;
  const site = useMemo(() => angularPoint(s.latitudePlanetocentricDeg, s.longitudeEastDeg, R), [s.latitudePlanetocentricDeg, s.longitudeEastDeg]);
  useEffect(() => {
    let live = true;
    loadGlobeManifest().then((m) => live && setOrder(globeOrder(m)));
    loadLayerManifest()
      .then((d) => live && setDoc(d ? { state: 'ok', doc: d } : { state: 'missing' }))
      .catch((e) => live && setDoc({ state: 'error', why: e instanceof Error ? e.message : String(e) }));
    return () => {
      live = false;
    };
  }, []);
  useEffect(() => {
    if (state === 'ready') setGo((g) => g + 1); // fly to the site once the model is visible
  }, [state]);
  const blender = shown?.entry.kind === 'blender';
  const latS = `${Math.abs(s.latitudePlanetocentricDeg).toFixed(4)}° ${s.latitudePlanetocentricDeg < 0 ? 'S' : 'N'}`;
  const lonS = `${Math.abs(s.longitudeEastDeg).toFixed(4)}° ${s.longitudeEastDeg < 0 ? 'W' : 'E'}`;
  return (
    <div className="globe-layer" data-testid="global-moon" data-loaded={state === 'ready'} data-asset={shown?.entry.kind ?? 'none'} data-drape={drawn} data-tab={tab} ref={wrap}>
      <Canvas dpr={[1, 2]} camera={{ position: [0, -1.4, 4.6], fov: 36, near: 0.05, far: 60 }} gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.0 }}>
        <color attach="background" args={['#050505']} />
        {/* display light only: NOT the Sun at the bundle time (the south pole would be near-dark under the real one) */}
        <hemisphereLight args={['#ffffff', '#2a2a2a', 1.15]} />
        <directionalLight position={[2, -3, 2.5]} intensity={1.6} />
        {order && (
          <Moon
            order={order}
            drape={drape}
            onReady={(entry, fellBack) => {
              setShown({ entry, fellBack });
              setState('ready');
            }}
            onFail={(m) => {
              setWhy(m);
              setState('failed');
            }}
          />
        )}
        <DrapeSync drape={drape} doc={doc} enabled={blender} onDrawn={setDrawn} />
        <Marker lat={s.latitudePlanetocentricDeg} lon={s.longitudeEastDeg} color="#E8A53C" />
        {picked && <Marker lat={picked.lat} lon={picked.lon} color="#7FD4FF" size={0.01} stem={1.09} />}
        {picked && nearest && (Math.abs(nearest.lat - picked.lat) > 1e-6 || Math.abs(nearest.lon - picked.lon) > 1e-6) && <Marker lat={nearest.lat} lon={nearest.lon} color="#B9F18C" size={0.009} stem={1.06} />}
        <Picker enabled={state === 'ready'} />
        <Flight site={site} go={go} />
        <OrbitControls makeDefault target={[0, 0, 0]} enablePan={false} minDistance={1.25} maxDistance={10} enableDamping dampingFactor={0.08} />
      </Canvas>
      <div className="globe-panel" data-tab={tab}>
      <div className="globe-tabs" role="tablist" aria-label="Globe panels">
        {(['site', 'layers', 'query'] as const).map((t) => (
          <button key={t} type="button" role="tab" aria-selected={tab === t} aria-controls={`globe-panel-${t}`} className="btn" onClick={() => setTab(t)} data-testid={`globe-tab-${t}`}>
            {t === 'site' ? 'Site' : t === 'layers' ? 'Layers' : 'Query'}
          </button>
        ))}
      </div>
      <div className="globe-card" id="globe-panel-site" role="tabpanel" data-testid="globe-card" data-panel="site" data-source={`bundle site coordinates · globe ${shown?.entry.url ?? 'loading'}`} data-label="SOURCE-BASED · UNVALIDATED (site position); globe VISUAL CONTEXT">
        <span className="lab">Global Moon · visual context</span>
        <strong>{s.name}</strong>
        <span>
          {latS} · {lonS}
        </span>
        {blender && shown && (
          <span className="globe-note" data-testid="globe-asset-note">
            Blender whole-Moon globe ({shown.entry.builder}, {shown.entry.generator}, tag {shown.entry.tag}): cube-sphere displaced from the science pyramid’s coarsest level
            (heights {shown.entry.labels?.heights ?? 'SOURCE-BASED · UNVALIDATED'}), true scale. Base colour VISUAL: {shown.entry.textureCredit} VISUAL CONTEXT, not numerical terrain: never
            sampled by any calculation. Display lighting, not the Sun at the bundle time.
          </span>
        )}
        {shown && !blender && (
          <span className="globe-note" data-testid="globe-asset-note">
            NASA SVS 14959 LRO Moon model (compact GLB), shown as a fallback{shown.fellBack ? ` because the Blender globe failed (${shown.fellBack})` : ' because the Blender globe is not built in this copy'} (build it with{' '}
            <code>{BLENDER_GLOBE_COMMAND}</code>). VISUAL CONTEXT, not numerical terrain: never sampled by any calculation. Display lighting, not the Sun at the bundle time. The source notes artifacts
            near the poles of this model.
          </span>
        )}
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
      <section className="globe-tools" id="globe-panel-layers" role="tabpanel" data-panel="layers" aria-label="Global layers">
          <GlobeLayers doc={doc} drapeOk={blender} drapeNote="Layers are registered to the Blender globe’s Moon-fixed frame; they are not draped on the SVS fallback model, whose longitude origin was never verified." />
      </section>
      <section className="globe-tools" id="globe-panel-query" role="tabpanel" data-panel="query" aria-label="Query any point">
          <QueryPanel
            markerLat={s.latitudePlanetocentricDeg}
            markerLon={s.longitudeEastDeg}
            pickNote={blender ? undefined : 'On the SVS fallback model the longitude origin is unverified, so the clicked longitude may be offset from the surface you see.'}
          />
      </section>
      </div>
    </div>
  );
}
