import { useFrame, useThree } from '@react-three/fiber';
import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { CAMERA_MS, easeCamera, reducedMotion, useCamera, type CameraViewId } from '../store/camera';

export interface Framing {
  pos: THREE.Vector3;
  target: THREE.Vector3;
  /** vertical field of view in degrees; omitted = BASE_FOV. A narrow FOV seen from far away reads as a flat map. */
  fov?: number;
}

/** The scene's normal lens (degrees). */
export const BASE_FOV = 42;
/** Lens for the Overhead map view: from this far away perspective almost vanishes (parallel lines stay parallel). */
export const MAP_FOV = 6;
/** Camera distance factor that keeps the same footprint at `fov` as at BASE_FOV: d·tan(fov/2) stays constant. */
export const dollyFactor = (fov: number) => Math.tan((BASE_FOV * Math.PI) / 360) / Math.tan((fov * Math.PI) / 360);

/**
 * Eases the camera to a named view when the user asks for one (Penumbra motion: ~1.4 s, camera ease, log-distance blend so
 * long approaches decelerate evenly). Any pointer/wheel input on the canvas interrupts the move. Under prefers-reduced-motion
 * the camera cuts. The camera never moves unless a view is requested.
 */
export function CameraRig({ frame, frameKey = '' }: { frame: (v: CameraViewId) => Framing | null; frameKey?: string }) {
  const { camera, controls, gl } = useThree() as unknown as {
    camera: THREE.PerspectiveCamera;
    controls: { target: THREE.Vector3; update: () => void } | null;
    gl: THREE.WebGLRenderer;
  };
  const nonce = useCamera((s) => s.nonce);
  const view = useCamera((s) => s.view);
  const anim = useRef<{ p0: THREE.Vector3; p1: THREE.Vector3; t0v: THREE.Vector3; t1v: THREE.Vector3; t0: number; f0: number; f1: number; ms: number } | null>(null);
  const first = useRef(true);
  const lastKey = useRef(frameKey);
  // a new site / DEM re-frames the current view with a cut (the old camera may sit inside the new terrain)
  if (lastKey.current !== frameKey) {
    lastKey.current = frameKey;
    first.current = true;
  }
  const frameRef = useRef(frame);
  frameRef.current = frame;

  useEffect(() => {
    const stop = () => (anim.current = null);
    const el = gl.domElement;
    el.addEventListener('pointerdown', stop);
    el.addEventListener('wheel', stop, { passive: true });
    return () => {
      el.removeEventListener('pointerdown', stop);
      el.removeEventListener('wheel', stop);
    };
  }, [gl]);

  useEffect(() => {
    const f = frameRef.current(view);
    if (!f) return;
    // the first framing (mount) cuts; later requests ease unless reduced motion is on
    const fov1 = f.fov ?? BASE_FOV;
    if (first.current || reducedMotion()) {
      first.current = false;
      if (camera.fov !== fov1) {
        camera.fov = fov1;
        camera.updateProjectionMatrix();
      }
      camera.position.copy(f.pos);
      if (controls) {
        controls.target.copy(f.target);
        controls.update();
      } else camera.lookAt(f.target);
      return;
    }
    // cinematic entry (guided demo opening): cut to a far view first, then ease in over a longer time
    const entry = useCamera.getState().entry;
    const from = entry ? frameRef.current(entry.from) ?? frameRef.current('regional') : null;
    if (from) {
      camera.fov = from.fov ?? BASE_FOV;
      camera.updateProjectionMatrix();
      camera.position.copy(from.pos);
      if (controls) {
        controls.target.copy(from.target);
        controls.update();
      } else camera.lookAt(from.target);
    }
    anim.current = { p0: camera.position.clone(), p1: f.pos, t0v: controls?.target.clone() ?? new THREE.Vector3(), t1v: f.target, t0: performance.now(), f0: camera.fov, f1: fov1, ms: from && entry ? entry.ms : CAMERA_MS };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce, controls, frameKey]);

  useFrame(() => {
    const a = anim.current;
    if (!a) return;
    const k = Math.min(1, (performance.now() - a.t0) / a.ms);
    const e = easeCamera(k);
    const tgt = a.t0v.clone().lerp(a.t1v, e);
    const r0 = a.p0.clone().sub(a.t0v);
    const r1 = a.p1.clone().sub(a.t1v);
    const d0 = Math.max(r0.length(), 1e-3);
    const d1 = Math.max(r1.length(), 1e-3);
    const dist = Math.exp(Math.log(d0) * (1 - e) + Math.log(d1) * e);
    // Lens: interpolate tan(fov/2) in log space with the same ease as the log distance. When the distance and the lens change by
    // the same factor (Overhead <-> its neighbours) the subject keeps its size while perspective flattens or deepens: the dolly
    // zoom ("Jaws effect") that 14islands uses to turn a flat 2D view into 3D (journal: "Using the Jaws-effect to transition
    // between 2D and 3D", used on Pluto). Display only.
    if (a.f0 !== a.f1) {
      const h0 = Math.log(Math.tan((a.f0 * Math.PI) / 360));
      const h1 = Math.log(Math.tan((a.f1 * Math.PI) / 360));
      camera.fov = (Math.atan(Math.exp(h0 * (1 - e) + h1 * e)) * 360) / Math.PI;
      camera.updateProjectionMatrix();
    }
    const dir = r0.normalize().lerp(r1.normalize(), e);
    if (dir.lengthSq() < 1e-8) dir.set(0, 1, 0);
    camera.position.copy(tgt).add(dir.normalize().multiplyScalar(dist));
    if (controls) {
      controls.target.copy(tgt);
      controls.update();
    } else camera.lookAt(tgt);
    if (k >= 1) anim.current = null;
  });
  return null;
}
