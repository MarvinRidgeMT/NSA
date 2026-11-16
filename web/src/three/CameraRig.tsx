import { useFrame, useThree } from '@react-three/fiber';
import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { CAMERA_MS, easeCamera, reducedMotion, useCamera, type CameraViewId } from '../store/camera';

export interface Framing {
  pos: THREE.Vector3;
  target: THREE.Vector3;
}

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
  const anim = useRef<{ p0: THREE.Vector3; p1: THREE.Vector3; t0v: THREE.Vector3; t1v: THREE.Vector3; t0: number } | null>(null);
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
    if (first.current || reducedMotion()) {
      first.current = false;
      camera.position.copy(f.pos);
      if (controls) {
        controls.target.copy(f.target);
        controls.update();
      } else camera.lookAt(f.target);
      return;
    }
    anim.current = { p0: camera.position.clone(), p1: f.pos, t0v: controls?.target.clone() ?? new THREE.Vector3(), t1v: f.target, t0: performance.now() };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce, controls, frameKey]);

  useFrame(() => {
    const a = anim.current;
    if (!a) return;
    const k = Math.min(1, (performance.now() - a.t0) / CAMERA_MS);
    const e = easeCamera(k);
    const tgt = a.t0v.clone().lerp(a.t1v, e);
    const r0 = a.p0.clone().sub(a.t0v);
    const r1 = a.p1.clone().sub(a.t1v);
    const d0 = Math.max(r0.length(), 1e-3);
    const d1 = Math.max(r1.length(), 1e-3);
    const dist = Math.exp(Math.log(d0) * (1 - e) + Math.log(d1) * e);
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
