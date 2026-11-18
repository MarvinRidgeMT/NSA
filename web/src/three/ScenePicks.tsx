import { useFrame, useThree, type ThreeEvent } from '@react-three/fiber';
import { useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';
import { gridDirection } from '../bundle/frame';
import { ridgeBins } from '../bundle/evidence';
import type { Ridge } from '../bundle/types';
import { easeCamera, reducedMotion } from '../store/camera';
import { useUi } from '../store/ui';
import type { View } from '../store/view';
import { blockingRidges, cropReachM, placeHoverLabel, ridgeNearM, useSceneFocus, type FocusId } from '../simple/sceneFocus';
import { BASE_FOV } from './CameraRig';
import { StableLine } from './StableLine';

/**
 * Clickable site scene (S12, 18 Nov 2026), the part inside the canvas. Simple mode only: Expert never mounts it.
 *
 * What a visitor can point at: the landing site and its mast, the Sun and Earth discs, and the ridges the bundle holds
 * responsible for lost Sun or Earth hours. Each has an unseen hit shape larger than what is drawn (the mast is 6 cm wide,
 * the Sun about ten pixels), a thin bone outline that comes up under the pointer, and a camera framing the view eases to
 * when it is picked (FLY_MS; a cut under reduced motion). Leaving returns the camera to the framing it left.
 *
 * DISPLAY ONLY. Positions come from the bundle (observer, the sample's Sun / Earth direction, attribution per-bin controlling
 * distances, ridge bearing and skyline elevation); nothing here decides visible or blocked, and no light is added: the
 * outlines are flat interface marks, dimmer than anything that blooms. A ridge beyond the terrain crop is not drawn on the
 * ground: a bracket on the skyline marks its bearing.
 */
export const FLY_MS = 1200;
const BONE = '#ECE7DD';
const SELENITE = '#B8C9C4';
const RAD = Math.PI / 180;
const PHONE = '(max-width: 639px)';

interface Framing {
  pos: THREE.Vector3;
  target: THREE.Vector3;
}

export interface ScenePicksProps {
  v: View;
  obs: { x: number; y: number; ground: number; mast: number };
  /** display-only vertical scale of the drawn scene */
  k: number;
  /** distance at which the Sun and Earth discs are drawn, and where they are */
  skyDist: number;
  sunDisc: THREE.Vector3;
  earthDisc: THREE.Vector3;
  /** ground vector of length d toward a local azimuth */
  toward: (az: number, d: number) => THREE.Vector3;
  /** the Approach view's bearing (cross-light), reused so a close view of the mast is lit the same way */
  viewAz: number;
  /** terrain height at a grid position (bundle DEM), or null outside the crop */
  demZ: (gx: number, gy: number) => number | null;
}

/** A small round dot for the ridge points (procedural). Made on first use, so Expert mode, which never mounts this, makes none. */
let dotTex: THREE.Texture | null = null;
function dot(): THREE.Texture | null {
  if (dotTex || typeof document === 'undefined') return dotTex;
  const c = document.createElement('canvas');
  c.width = c.height = 32;
  const g = c.getContext('2d');
  if (!g) return null;
  g.fillStyle = '#fff';
  g.beginPath();
  g.arc(16, 16, 13, 0, Math.PI * 2);
  g.fill();
  return (dotTex = new THREE.CanvasTexture(c));
}

interface RidgeGeo {
  ridge: Ridge;
  id: FocusId;
  far: boolean;
  /** near: the bundle's per-bin controlling points on the terrain (scene units, before the vertical display scale) */
  pts: THREE.Vector3[];
  positions: Float32Array;
  /** far: a bracket on the skyline over the ridge's bearing range, and its middle */
  bracket: THREE.Vector3[];
  mid: THREE.Vector3;
  azMid: number;
  spanDeg: number;
}

export function ScenePicks({ v, obs, k, skyDist, sunDisc, earthDisc, toward, viewAz, demZ }: ScenePicksProps) {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const controls = useThree((s) => s.controls) as unknown as { target: THREE.Vector3; update: () => void } | null;
  const gl = useThree((s) => s.gl);
  const size = useThree((s) => s.size);
  const focus = useSceneFocus((s) => s.focus);
  const hover = useSceneFocus((s) => s.hover);
  const mastPick = useUi((s) => s.mastPick);
  const siteKey = `${v.dataset.siteId}:${v.series?.id ?? ''}`;

  // ---- ridges the bundle holds responsible for a loss: where each one is ----
  const att = v.dataset.derived?.attribution;
  const sk = v.series?.skyline;
  const reach = cropReachM(v);
  const ridges = useMemo<RidgeGeo[]>(() => {
    const out: RidgeGeo[] = [];
    const sky = (az: number, el: number, dist: number) => {
      const d = gridDirection(v.basis, az, el);
      return new THREE.Vector3(d[0], d[2] * k, -d[1]).normalize().multiplyScalar(dist);
    };
    for (const r of blockingRidges(v)) {
      const far = ridgeNearM(r) > reach;
      const [a0, a1] = r.azimuthDeg;
      const azMid = (a0 + a1) / 2;
      const pts: THREE.Vector3[] = [];
      const bracket: THREE.Vector3[] = [];
      let mid = new THREE.Vector3();
      if (!far && att?.perBin?.ctrlDistM && sk) {
        for (const b of ridgeBins(att, att.ridges.indexOf(r))) {
          const d = att.perBin.ctrlDistM[b];
          if (d === null || d === undefined || !Number.isFinite(d)) continue;
          const dir = gridDirection(v.basis, sk.azimuthDeg[b], 0);
          const gx = obs.x + dir[0] * d;
          const gy = obs.y + dir[1] * d;
          const z = demZ(gx, gy);
          if (z === null) continue; // outside the crop: not drawn, nothing invented
          pts.push(new THREE.Vector3(gx - obs.x, z - obs.ground + 0.2, -(gy - obs.y)));
        }
        if (pts.length) mid = pts[pts.length >> 1].clone();
      } else if (far) {
        // skyline elevation of the ridge from the bundle (max_elev_deg); the bracket stands just above it
        const el = r.maxElevDeg ?? 0;
        const dist = skyDist * 0.985;
        const lift = 0.45;
        bracket.push(sky(a0, el, dist));
        const n = Math.max(2, Math.ceil((a1 - a0) / 0.5));
        for (let i = 0; i <= n; i++) bracket.push(sky(a0 + ((a1 - a0) * i) / n, el + lift, dist));
        bracket.push(sky(a1, el, dist));
        mid = sky(azMid, el + lift, dist);
      }
      if (far || pts.length) out.push({ ridge: r, id: `ridge:${r.id}`, far, pts, positions: new Float32Array(pts.flatMap((p) => [p.x, p.y, p.z])), bracket, mid, azMid, spanDeg: a1 - a0 });
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- the view's basis and attribution change with the site and series
  }, [siteKey, att, sk, reach, k, skyDist, obs.x, obs.y, obs.ground]);

  // ---- camera framings (display only; observer at the origin, 1 unit = 1 m) ----
  const frameH = Math.max(obs.mast, mastPick ?? 0);
  const framingFor = (id: FocusId): Framing | null => {
    const top = obs.mast * k;
    // keep the camera above the drawn ground where it stands
    const clear = (f: Framing, min: number) => {
      const g = demZ(obs.x + f.pos.x, obs.y - f.pos.z);
      if (g !== null) f.pos.y = Math.max(f.pos.y, (g - obs.ground) * k + min);
      return f;
    };
    // looking out along a bearing from behind the mast: the mast low in the frame, the skyline and the body above it
    const along = (az: number, el: number): Framing => {
      const L = 120;
      const ty = top + L * Math.tan(el * RAD) * k;
      const pos = toward(az + 180, 60);
      pos.y = Math.max(top + 9, ty + 2);
      const f = clear({ pos, target: toward(az, L).setY(ty) }, 3);
      // the controls never look up past the horizontal: stay just above the point looked at
      f.pos.y = Math.max(f.pos.y, ty + 2);
      return f;
    };
    if (id === 'site') {
      const h = frameH * k;
      const d = 7 + frameH * 2.4;
      return clear({ pos: toward(viewAz + 180, d).setY(h * 0.6 + 2.6), target: new THREE.Vector3(0, h * 0.5, 0) }, 1.6);
    }
    if (id === 'sun' || id === 'earth') return along(v[id].az, v[id].el);
    const g = ridges.find((r) => r.id === id);
    if (!g) return null;
    if (g.far) return along(g.azMid, g.ridge.maxElevDeg ?? 0);
    // a ridge on the drawn terrain: frame its points together with the mast, from beside the sight line and above, so
    // the mast, the ground between and the rise all read
    // (centred on where most of the points are: a few far ones must not push the rest out of the picture)
    const all = [new THREE.Vector3(0, top, 0), ...g.pts.map((p) => new THREE.Vector3(p.x, p.y * k, p.z))];
    const c = all.reduce((a, p) => a.add(p), new THREE.Vector3()).multiplyScalar(1 / all.length);
    const dists = all.map((p) => p.distanceTo(c)).sort((a, b) => a - b);
    const R = Math.max(dists[Math.floor((dists.length - 1) * 0.85)] * 1.25, 10);
    return clear({ pos: c.clone().add(toward(g.azMid + 90, R * 1.9)).setY(c.y + R * 0.95), target: c }, 3);
  };
  const framingRef = useRef(framingFor);
  framingRef.current = framingFor;

  // ---- the fly-to and the exact return ----
  const st = useRef({
    home: null as { pos: THREE.Vector3; target: THREE.Vector3; fov: number } | null,
    anim: null as { p0: THREE.Vector3; t0v: THREE.Vector3; p1: THREE.Vector3; t1v: THREE.Vector3; f0: number; f1: number; t0: number; out: boolean; off0: THREE.Vector2 } | null,
    off: new THREE.Vector2(),
    offTo: new THREE.Vector2(),
    measured: 0,
    key: siteKey,
    mix: {} as Record<string, number>,
  });
  const setFlying = (f: 'in' | 'out' | null) => useSceneFocus.getState().flying !== f && useSceneFocus.setState({ flying: f });

  // a new site or series redraws the terrain and re-frames the view with a cut (CameraRig): nothing to return to
  useLayoutEffect(() => {
    const s = st.current;
    if (s.key === siteKey) return;
    const newSite = s.key.split(':')[0] !== siteKey.split(':')[0];
    s.key = siteKey;
    s.home = null;
    s.anim = null;
    s.off.set(0, 0);
    s.offTo.set(0, 0);
    if (camera.view?.enabled) camera.clearViewOffset();
    // a new site starts over (answer card open, nothing flown to). A new series at the same site (a mast height that has
    // its own bundle series) keeps what is open: the fly-to below runs again from the re-framed view.
    if (newSite) useSceneFocus.getState().reset();
    else setFlying(null);
  }, [siteKey, camera]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const s = st.current;
    const tgt = controls?.target ?? new THREE.Vector3();
    const cut = reducedMotion();
    const go = (p1: THREE.Vector3, t1v: THREE.Vector3, f1: number, out: boolean) => {
      if (cut) {
        camera.position.copy(p1);
        camera.fov = f1;
        camera.updateProjectionMatrix();
        if (controls) {
          controls.target.copy(t1v);
          controls.update();
        } else camera.lookAt(t1v);
        if (out) {
          s.home = null;
          s.off.set(0, 0);
          s.offTo.set(0, 0);
          camera.clearViewOffset();
        }
        setFlying(null);
        return;
      }
      s.anim = { p0: camera.position.clone(), t0v: tgt.clone(), p1, t1v, f0: camera.fov, f1, t0: performance.now(), out, off0: s.off.clone() };
      setFlying(out ? 'out' : 'in');
    };
    // a named-view move still running (CameraRig eases to Approach on arrival) gives way: it stops on a wheel event, and
    // one with no travel changes nothing else (ctrl marks it as a zoom gesture, which the scene's wheel guard lets through)
    if (focus || s.home) gl.domElement.dispatchEvent(new WheelEvent('wheel', { deltaY: 0, ctrlKey: true }));
    if (focus) {
      const f = framingRef.current(focus);
      if (!f) {
        // the object is not in this view any more (a ridge, under a series its attribution does not describe)
        useSceneFocus.setState({ focus: null, byKeys: false });
        return;
      }
      // the framing to come back to is the one the visitor had before the first object was opened
      if (!s.home) s.home = { pos: camera.position.clone(), target: tgt.clone(), fov: camera.fov };
      s.measured = 0;
      go(f.pos, f.target, BASE_FOV, false);
    } else if (s.home) go(s.home.pos.clone(), s.home.target.clone(), s.home.fov, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- re-framed when the object changes, or the mast it frames grows
    // (also re-framed when the clock moves the Sun or the Earth while its card is open, so the picture and the card's
    // values stay on the same sample; the framing to return to is kept)
  }, [focus, focus === 'site' ? frameH : 0, focus === 'sun' || focus === 'earth' ? `${v[focus].az.toFixed(2)}:${v[focus].el.toFixed(2)}` : '', controls, camera, siteKey]);

  // any press or wheel on the scene takes the camera back from a move in progress (the card stays as it is)
  useEffect(() => {
    const el = gl.domElement;
    const stop = () => {
      const s = st.current;
      if (!s.anim) return;
      if (s.anim.out) s.home = null; // the visitor took over on the way back: where they are now is the framing
      s.anim = null;
      setFlying(null);
    };
    el.addEventListener('pointerdown', stop);
    el.addEventListener('wheel', stop, { passive: true });
    return () => {
      el.removeEventListener('pointerdown', stop);
      el.removeEventListener('wheel', stop);
      el.style.cursor = '';
    };
  }, [gl]);
  // for tests and screenshots: the camera, and where an object stands in the canvas (CSS px)
  const anchorRef = useRef<(id: string) => THREE.Vector3 | null>(() => null);
  useEffect(() => {
    const screen = (id: string) => {
      const p = anchorRef.current(id);
      if (!p) return null;
      p.project(camera);
      return { x: (p.x * 0.5 + 0.5) * gl.domElement.clientWidth, y: (-p.y * 0.5 + 0.5) * gl.domElement.clientHeight, front: p.z < 1 };
    };
    (window as unknown as Record<string, unknown>).__polarisScene = { camera, controls, screen, hits: hits.current };
    return () => {
      delete (window as unknown as Record<string, unknown>).__polarisScene;
    };
  }, [camera, controls, gl]);
  // leaving the site: nothing stays hovered or flown to, and the camera keeps no picture offset
  useEffect(
    () => () => {
      st.current.anim = null;
      st.current.home = null;
      st.current.off.set(0, 0);
      if (camera.view?.enabled) camera.clearViewOffset();
      useSceneFocus.getState().reset();
    },
    [camera],
  );

  // ---- what is drawn: outlines that come up under the pointer ----
  const siteRing = useRef<THREE.Mesh>(null);
  const siteHit = useRef<THREE.Mesh>(null);
  const sunRing = useRef<THREE.Mesh>(null);
  const earthRing = useRef<THREE.Mesh>(null);
  const dotMats = useRef<Record<string, THREE.PointsMaterial | null>>({});
  const hits = useRef<Record<string, THREE.InstancedMesh | null>>({});
  useLayoutEffect(() => {
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const sc = new THREE.Vector3();
    for (const g of ridges) {
      const mesh = hits.current[g.id];
      if (!mesh || g.far) continue;
      g.pts.forEach((p, i) => {
        // big enough to press from the Approach view, never so big that neighbours swallow the mast
        const r = Math.min(9, Math.max(2.5, Math.hypot(p.x, p.z) * 0.05));
        mesh.setMatrixAt(i, m.compose(p, q, sc.set(r, r / k, r)));
      });
      mesh.instanceMatrix.needsUpdate = true;
      mesh.computeBoundingSphere();
    }
  }, [ridges, k]);

  const hitR = Math.max(obs.mast * 0.5 + 0.6, 1.2);
  const tmp = useMemo(() => ({ p: new THREE.Vector3(), a: new THREE.Vector3(), b: new THREE.Vector3() }), []);
  anchorRef.current = (id) => {
    if (id === 'site') return new THREE.Vector3(0, obs.mast * k * 0.5, 0);
    if (id === 'sun') return sunDisc.clone();
    if (id === 'earth') return earthDisc.clone();
    const g = ridges.find((r) => r.id === id);
    return g ? g.mid.clone().setY(g.far ? g.mid.y : g.mid.y * k) : null;
  };
  useFrame((_, dtRaw) => {
    const s = st.current;
    const dt = Math.min(dtRaw, 0.1);
    const now = performance.now();
    const still = reducedMotion();
    const cur = useSceneFocus.getState();

    // camera move: target eased, distance blended in log space (as CameraRig does), then set exactly at the end
    const a = s.anim;
    if (a) {
      const kk = Math.min(1, (now - a.t0) / FLY_MS);
      const e = easeCamera(kk);
      if (kk >= 1) {
        camera.position.copy(a.p1);
        if (controls) controls.target.copy(a.t1v);
        camera.fov = a.f1;
      } else {
        const tgt = tmp.p.copy(a.t0v).lerp(a.t1v, e);
        const r0 = tmp.a.copy(a.p0).sub(a.t0v);
        const r1 = tmp.b.copy(a.p1).sub(a.t1v);
        const d0 = Math.max(r0.length(), 1e-3);
        const d1 = Math.max(r1.length(), 1e-3);
        const dist = Math.exp(Math.log(d0) * (1 - e) + Math.log(d1) * e);
        const dir = r0.normalize().lerp(r1.normalize(), e);
        if (dir.lengthSq() < 1e-8) dir.set(0, 1, 0);
        camera.position.copy(tgt).add(dir.normalize().multiplyScalar(dist));
        if (controls) controls.target.copy(tgt);
        if (a.f0 !== a.f1) camera.fov = a.f0 + (a.f1 - a.f0) * e;
      }
      if (a.out) {
        // on the way back the picture's centre returns with the camera, and ends where it began: no offset at all
        s.off.copy(a.off0).multiplyScalar(1 - e);
        s.offTo.set(0, 0);
        if (kk >= 1 || s.off.lengthSq() === 0) camera.clearViewOffset();
        else camera.setViewOffset(size.width, size.height, -s.off.x, -s.off.y, size.width, size.height);
      }
      camera.updateProjectionMatrix();
      if (controls) controls.update();
      else camera.lookAt(a.t1v);
      if (kk >= 1) {
        if (a.out) {
          s.off.set(0, 0);
          s.home = null;
          // the return ends on the very numbers that were saved
          camera.position.copy(a.p1);
        }
        s.anim = null;
        setFlying(null);
      }
    }

    // The picture's centre moves to the middle of the space the card and the panels leave free, so the object flown to is
    // never under its own card. Measured from the page a few times a second (the phone sheet slides, windows resize).
    if (cur.focus) {
      if (now - s.measured > 200) {
        s.measured = now;
        const stage = gl.domElement.getBoundingClientRect();
        const box = (sel: string) => {
          const r = document.querySelector(sel)?.getBoundingClientRect();
          return r && r.width > 0 && r.height > 0 ? r : null;
        };
        let [L, R, T, B] = [stage.left, stage.right, stage.top, stage.bottom];
        for (const sel of ['.simple .s-chrome', '.simple .s-banner', '.simple .simple-stage .s-back']) T = Math.max(T, box(sel)?.bottom ?? T);
        B = Math.min(B, box('.simple .s-bottom')?.top ?? B);
        if (matchMedia(PHONE).matches) B = Math.min(B, box('.simple .s-dock')?.top ?? B);
        else {
          L = Math.max(L, (box('.simple .s-cardslot .s-objcard') ?? box('.simple .s-answerpanel'))?.right ?? L);
          R = Math.min(R, box('.simple .s-statspanel')?.left ?? R);
        }
        if (R - L > 120 && B - T > 120) s.offTo.set((L + R) / 2 - (stage.left + stage.right) / 2, (T + B) / 2 - (stage.top + stage.bottom) / 2);
        else s.offTo.set(0, 0);
      }
    } else s.offTo.set(0, 0);
    if (!s.off.equals(s.offTo) && !s.anim?.out) {
      s.off.lerp(s.offTo, still ? 1 : 1 - Math.exp(-dt * 7));
      if (s.off.distanceTo(s.offTo) < 0.25) s.off.copy(s.offTo);
      if (s.off.lengthSq() === 0) camera.clearViewOffset();
      else camera.setViewOffset(size.width, size.height, -s.off.x, -s.off.y, size.width, size.height);
    }

    // outlines: up under the pointer or the keyboard, and held while the object's card is open
    const lens = Math.tan((camera.fov * RAD) / 2) / Math.tan((BASE_FOV * RAD) / 2);
    const ease = still ? 1 : 1 - Math.exp(-dt * 18);
    const level = (id: string) => {
      const to = cur.hover === id || cur.focus === id ? 1 : 0;
      const m = (s.mix[id] ?? 0) + (to - (s.mix[id] ?? 0)) * ease;
      return (s.mix[id] = Math.abs(m - to) < 0.004 ? to : m);
    };
    const ring = (mesh: THREE.Mesh | null, id: string, radius: number, face: boolean) => {
      if (!mesh) return;
      const o = level(id);
      mesh.visible = o > 0;
      (mesh.material as THREE.MeshBasicMaterial).opacity = o * 0.9;
      // the outline settles onto the object as it comes up
      mesh.scale.setScalar(radius * (1.12 - 0.12 * o));
      if (face) mesh.quaternion.copy(camera.quaternion);
    };
    // the mast is 6 cm wide: its ring and the area that answers the pointer keep a constant size on screen (about 30 px
    // in radius), and never less than the mast itself
    const siteR = Math.max(camera.position.length() * 0.03 * lens, 0.5);
    ring(siteRing.current, 'site', siteR, false);
    if (siteHit.current) {
      const r = Math.max(siteR, hitR);
      siteHit.current.scale.set(r, Math.max(obs.mast * k * 0.5 + 0.8, r), r);
    }
    // at least 0.75° across on the sky (the Sun's own disc is 0.27° in radius), so the ring reads at any zoom
    ring(sunRing.current, 'sun', skyDist * Math.tan(0.75 * RAD), true);
    ring(earthRing.current, 'earth', skyDist * Math.tan(1.3 * RAD), true);
    for (const g of ridges) {
      const mat = dotMats.current[g.id];
      if (!mat) continue;
      const o = level(g.id);
      mat.opacity = 0.5 + 0.5 * o;
      mat.size = 4 + 2 * o;
    }

    // keyboard: the label stands at the object the focused list button names
    if (cur.hover && cur.hoverBy === 'keys') {
      const p = anchorRef.current(cur.hover) ?? tmp.p.set(0, 0, 0);
      p.project(camera);
      const inView = p.z < 1 && Math.abs(p.x) <= 1 && Math.abs(p.y) <= 1;
      placeHoverLabel((p.x * 0.5 + 0.5) * size.width, (-p.y * 0.5 + 0.5) * size.height, size.width, size.height, inView);
    }
  });

  // ---- pointer ----
  const over = (id: FocusId) => (e: ThreeEvent<PointerEvent>) => {
    if (e.nativeEvent.pointerType !== 'mouse' || e.nativeEvent.buttons !== 0) return; // no hover on touch or mid-drag
    e.stopPropagation();
    useSceneFocus.getState().setHover(id, 'pointer');
    gl.domElement.style.cursor = 'pointer';
    const r = gl.domElement.getBoundingClientRect();
    placeHoverLabel(e.nativeEvent.clientX - r.left, e.nativeEvent.clientY - r.top, r.width, r.height);
  };
  const out = (id: FocusId) => () => {
    const s = useSceneFocus.getState();
    if (s.hover === id && s.hoverBy === 'pointer') {
      s.setHover(null);
      gl.domElement.style.cursor = '';
    }
  };
  const click = (id: FocusId) => (e: ThreeEvent<MouseEvent>) => {
    // a press that travelled is an orbit drag, not a pick
    if (e.delta > 4) return;
    e.stopPropagation();
    useSceneFocus.getState().open(id);
  };
  const handlers = (id: FocusId) => ({ onPointerOver: over(id), onPointerMove: over(id), onPointerOut: out(id), onClick: click(id) });
  const ringMat = <meshBasicMaterial color={BONE} transparent opacity={0} depthTest={false} depthWrite={false} toneMapped={false} side={THREE.DoubleSide} />;
  const lit = (id: string) => hover === id || focus === id;

  return (
    <group>
      {/* landing site and mast */}
      <mesh ref={siteRing} rotation-x={-Math.PI / 2} position={[0, 0.06, 0]} renderOrder={6} visible={false}>
        <ringGeometry args={[0.93, 1, 72]} />
        {ringMat}
      </mesh>
      <mesh ref={siteHit} position={[0, (obs.mast * k) / 2, 0]} scale={[hitR, Math.max(obs.mast * k * 0.5 + 0.8, hitR), hitR]} visible={false} {...handlers('site')}>
        <sphereGeometry args={[1, 12, 8]} />
      </mesh>

      {/* Sun and Earth discs */}
      <mesh ref={sunRing} position={sunDisc} renderOrder={6} visible={false}>
        <ringGeometry args={[0.92, 1, 64]} />
        {ringMat}
      </mesh>
      <mesh position={sunDisc} visible={false} {...handlers('sun')}>
        <sphereGeometry args={[skyDist * Math.tan(1.5 * RAD), 12, 8]} />
      </mesh>
      <mesh ref={earthRing} position={earthDisc} renderOrder={6} visible={false}>
        <ringGeometry args={[0.95, 1, 64]} />
        {ringMat}
      </mesh>
      <mesh position={earthDisc} visible={false} {...handlers('earth')}>
        <sphereGeometry args={[skyDist * Math.tan(1.9 * RAD), 12, 8]} />
      </mesh>

      {/* blocking ridges */}
      {ridges.map((g) =>
        g.far ? (
          <group key={g.id}>
            <StableLine points={g.bracket} color={lit(g.id) ? BONE : SELENITE} lineWidth={lit(g.id) ? 2 : 1.25} transparent opacity={lit(g.id) ? 1 : 0.6} depthTest={false} depthWrite={false} renderOrder={6} />
            <mesh position={g.mid} visible={false} {...handlers(g.id)}>
              <sphereGeometry args={[skyDist * Math.tan(Math.max(1.4, g.spanDeg / 2 + 0.6) * RAD), 12, 8]} />
            </mesh>
          </group>
        ) : (
          <group key={g.id} scale={[1, k, 1]}>
            <points renderOrder={5}>
              <bufferGeometry>
                <bufferAttribute attach="attributes-position" args={[g.positions, 3]} />
              </bufferGeometry>
              <pointsMaterial ref={(m) => void (dotMats.current[g.id] = m)} color={BONE} size={4} sizeAttenuation={false} map={dot()} alphaTest={0.4} transparent opacity={0.5} depthWrite={false} toneMapped={false} />
            </points>
            <instancedMesh ref={(m) => void (hits.current[g.id] = m)} args={[undefined, undefined, g.pts.length]} visible={false} {...handlers(g.id)}>
              <icosahedronGeometry args={[1, 0]} />
            </instancedMesh>
          </group>
        ),
      )}
    </group>
  );
}
