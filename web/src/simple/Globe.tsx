import { addAfterEffect, Canvas, useFrame, useThree } from '@react-three/fiber';
import { lazy, Suspense, useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent as RKeyboardEvent, type MutableRefObject, type MouseEvent as RMouseEvent, type PointerEvent as RPointerEvent } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { easeCamera } from '../store/camera';
import { EXPOSURE, postColors, SKY, SUN_HEX } from './postColors';
import type { QualityTier } from './quality';
import { DRIFT_DEG_PER_S, FLIGHT_MS, GLOBE_NAV, GLOBE_V2, MODEL_HAS_RELIEF, MODEL_YAW_RAD, RELIEF_CAP_FROM_DEG, RELIEF_CAP_TO_DEG, RELIEF_SHADE, distanceForDisc, radPerPixel, releaseVelocity, reliefNormals, layoutPins, moonDir, texelsPerRadian, zoomFloor, type Pt, type Vec3 } from './globeMath';
import { HonestyTag, HoverLabel, IconArrow, IconBack, IconClose, SitePin } from './parts';
import { arcAt, distAt, glareFor, glareOut, INTRO, openMs, peekDeg, peekStillDeg, smooth as smoothStep, sunClear, SUN_RADIUS_DEG, type Arc } from './introMath';
import { newIntroLink, useMoonLoad, type IntroLink } from './introState';
import { SpotBox, SpotCard, useSpotCheck, type SpotCardSite } from './SpotPanel';
import { dirToLatLon } from './spotCheck';
import { cloneRanges, hours, hoursRange, mastLabel, pct, pctRange, siteRow, type AnySite } from './anySite';

const SimplePost = lazy(() => import('./SimplePost'));

/**
 * Simple-mode landing view (S4, 17 Nov 2026): the Moon seen from over its south pole, with the bundle's ROI sites as pins.
 *
 * VISUAL CONTEXT ONLY. The Moon is the POLARIS v2 globe (Anish Meruva; heights SOURCE-BASED · UNVALIDATED, base colour the LROC
 * WAC mosaic, VISUAL) or, when the link asks, a NASA SVS model (globeMath.globeAsset); nothing here is sampled by a calculation and
 * the shading never decides a visible / blocked state. What is real: the model is turned to true lunar axes (globeMath.ts), the
 * light comes from the Sun direction the bundle gives for the sample on the clock, and each pin's line ends at its site's
 * bundle latitude and longitude. What is a display choice: brightness, the faint earthshine, the slow drift, the pin spacing.
 * Every number on screen is passed in by SimpleApp, which reads it from the bundle or the certainty sidecar.
 */
export interface GlobeSite {
  /** dataset index in the loaded bundle */
  idx: number;
  id: string;
  name: string;
  /** unit vector of the site's bundle latitude / longitude, model frame */
  dir: Vec3;
  /** the one-line answer (sidecar), or why there is none */
  line: string;
  /** Sun-in-sight max − min across the terrain variants at the picked mast, points; null = no sidecar row */
  spreadPts: number | null;
  /** short text for the spread, e.g. "variants differ by 9.8 points" */
  spreadText: string;
  /** S13: the site's bundle coordinates and its sidecar result as words, for "Check a spot" */
  spot: SpotCardSite;
  /** S14: the mast height this card's line is for (the one picked in the top bar, or the site's own); null = no sidecar row */
  mastM: number | null;
}
/** 'intro' is the opening sequence (S3): the same scene and camera, on its way to the 'idle' view. */
export type GlobePhase = 'intro' | 'idle' | 'in' | 'hidden' | 'out';

/** The first-visit hint stays gone on this browser once something on the Moon has been clicked. */
const HINT_KEY = 'polaris-x.simple.globe-hint-seen';
/** Cards on wide windows stay this far above the bottom of the view, clear of the Check-a-spot box. CSS px. */
const CARD_CLEAR_BOTTOM = 148;
const FOV = 30;
/** Camera height above the site where the dive ends, in Moon radii (the terrain view takes over from here). */
const ALT_END = 0.03;
/** Light levels: display choices. The Sun is far below the bloom threshold on purpose (only a Sun disc may bloom). */
const SUN_LIGHT = 9;
const EARTHSHINE = 0.035;
const EARTHSHINE_HEX = '#a9c1e6';
const SOUTH = new THREE.Vector3(0, -1, 0);
const RAD = Math.PI / 180;
/** The intro's Sun disc stands this far away, in Moon radii (a display distance: only its direction is the bundle's). */
const SUN_DIST = 400;
const smooth = (a: number, b: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

/**
 * S12: the visitor's own turn and zoom of the Moon, shared between the pointer and key handlers (which write what was asked)
 * and the camera rig (which applies it each frame). Display only.
 */
interface GlobeNav {
  /** turn applied to the pole-on view (the slow drift is folded in here too) */
  q: THREE.Quaternion;
  /** height above the surface as a fraction of the whole-Moon view's: 1 = whole Moon. `zoom` is asked for, `zoomNow` is drawn */
  zoom: number;
  zoomNow: number;
  /** drag distance not yet applied, CSS px (applied whole on the next frame: the surface stays under the pointer) */
  dx: number;
  dy: number;
  /** glide after release: the drag's speed at the moment of release, rad/s about the screen's vertical and horizontal axes */
  vx: number;
  vy: number;
  /** keyboard turn still to do, radians about the screen's vertical and horizontal axes */
  nx: number;
  ny: number;
  dragging: boolean;
  /** the slow drift stays off until this time (performance.now) */
  quietUntil: number;
  /** "Back to south pole" in progress */
  home: { t0: number; q0: THREE.Quaternion; axis: THREE.Vector3; angle: number; z0: number; z1: number } | null;
  goHome: boolean;
  /** S13 "Zoom in here": asked to bring this point of the Moon under the camera and zoom to the closest this model allows */
  goTo: THREE.Vector3 | null;
  /** written by the rig: radians per CSS pixel at the view centre now, and the zoom floor of the model on screen */
  radPerPx: number;
  zoomMin: number;
  moved: boolean;
}
const newNav = (): GlobeNav => ({ q: new THREE.Quaternion(), zoom: 1, zoomNow: 1, dx: 0, dy: 0, vx: 0, vy: 0, nx: 0, ny: 0, dragging: false, quietUntil: 0, home: null, goHome: false, goTo: null, radPerPx: 0, zoomMin: 1, moved: false });

function useReducedMotion(): boolean {
  const [r, setR] = useState(() => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches);
  useEffect(() => {
    if (typeof matchMedia !== 'function') return;
    const m = matchMedia('(prefers-reduced-motion: reduce)');
    const on = () => setR(m.matches);
    m.addEventListener('change', on);
    return () => m.removeEventListener('change', on);
  }, []);
  return r;
}

/**
 * The 8k model is a latitude-longitude mesh, whose texture coordinates zigzag where its quads thin to slivers at the poles
 * (the very place this view looks at). Its image is a plain equirectangular map, so the image position is worked out per pixel
 * from the direction out of the model's centre instead (axes as in globeMath: +Y north, longitude 0° along +X, 90° E along −Z,
 * 0° at the image centre, north up). Same image, same place; only the interpolation changes. Display only.
 */
function equirectPerPixel(mat: THREE.Material) {
  mat.onBeforeCompile = (sh) => {
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vMoonDir;').replace('#include <begin_vertex>', '#include <begin_vertex>\nvMoonDir = position;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vMoonDir;').replace(
      '#include <map_fragment>',
      `
      vec3 moonD = normalize( vMoonDir );
      float moonU = atan( -moonD.z, moonD.x ) / 6.283185307179586 + 0.5;
      float moonV = 0.5 - asin( clamp( moonD.y, -1.0, 1.0 ) ) / 3.141592653589793;
      // the longitude wraps at 180°: take the image gradient from whichever of two phases has no jump at this pixel
      float moonU2 = fract( moonU + 0.5 );
      float ux = abs( dFdx( moonU ) ) < abs( dFdx( moonU2 ) ) ? dFdx( moonU ) : dFdx( moonU2 );
      float uy = abs( dFdy( moonU ) ) < abs( dFdy( moonU2 ) ) ? dFdy( moonU ) : dFdy( moonU2 );
      diffuseColor *= textureGrad( map, vec2( moonU, moonV ), vec2( ux, dFdx( moonV ) ), vec2( uy, dFdy( moonV ) ) );
      `,
    );
  };
  mat.customProgramCacheKey = () => 'moon-equirect';
}

/**
 * S14 Part B: what the v2 globe's manifest says that drawing it needs. `yawRad` is worked out from the manifest's axes
 * sentence (globeMath.yawFromAxes); `draco` says its mesh needs the Draco decoder.
 */
export interface GlobeV2 {
  yawRad: number;
  draco: boolean;
}

/** How long the 8k model takes to fade in over the compact one (none under reduced motion). */
const UPGRADE_FADE_MS = 600;

/**
 * One Moon model. `layer` is how it shares the screen while the better model fades in over the first one: 'solo' alone,
 * 'under' drawn first without writing depth (so the model over it is depth-tested only against itself, and the 8k model's
 * relief, which dips below the compact sphere in places, is not cut by it), 'over' faded in from transparent across
 * UPGRADE_FADE_MS, then `onFaded`.
 */
function Moon({ file, lite, v2 = null, show = true, layer = 'solo', run = true, onReady, onFail, onFaded, onProgress }: { file: string; lite: boolean; v2?: GlobeV2 | null; show?: boolean; layer?: 'solo' | 'under' | 'over'; run?: boolean; onReady: (texelsPerRad: number) => void; onFail: (m: string) => void; onFaded?: () => void; onProgress?: (frac: number) => void }) {
  const [model, setModel] = useState<THREE.Object3D | null>(null);
  const mats = useRef<THREE.Material[]>([]);
  // ms of fade done so far; -1 = not started, -2 = no fade (only advances while `run`, so it holds still during a flight)
  const fadeT0 = useRef(-1);
  useEffect(() => {
    if (!model) return;
    const over = layer === 'over';
    model.traverse((o) => void ((o as THREE.Mesh).isMesh && ((o as THREE.Mesh).renderOrder = layer === 'under' ? -1 : 0)));
    for (const m of mats.current) {
      m.depthWrite = layer !== 'under';
      m.transparent = over;
      m.opacity = over ? 0 : 1;
      m.needsUpdate = true;
    }
    fadeT0.current = over ? -1 : -2;
  }, [model, layer]);
  useFrame((_, dt) => {
    if (layer !== 'over' || !model || !show || !run || fadeT0.current === -2) return;
    fadeT0.current = Math.max(0, fadeT0.current) + Math.min(dt, 0.1) * 1000;
    const t = Math.min(1, fadeT0.current / UPGRADE_FADE_MS);
    const a = t * t * (3 - 2 * t);
    for (const m of mats.current) m.opacity = a;
    if (t >= 1) {
      fadeT0.current = -2;
      onFaded?.();
    }
  });
  const maxAniso = useThree((s) => s.gl.capabilities.getMaxAnisotropy());
  useEffect(() => {
    let live = true;
    let made: { geo: THREE.BufferGeometry[]; mat: THREE.Material[]; tex: THREE.Texture[] } = { geo: [], mat: [], tex: [] };
    const isV2 = file === GLOBE_V2;
    const onError = (e: unknown) => live && onFail(e instanceof Error ? e.message : String(e));
    // the v2 globe is drawn only with its manifest's axes; its mesh is Draco-compressed, so the decoder (three.js's own, served
    // as draco/*) is fetched first, and only for this model
    if (isV2 && !v2) {
      onError(new Error('the v2 globe has no manifest entry'));
      return;
    }
    const start = async () => {
      const loader = new GLTFLoader();
      let dracoLoader: { dispose(): void } | null = null;
      if (isV2 && v2!.draco) {
        const { DRACOLoader } = await import('three/examples/jsm/loaders/DRACOLoader.js');
        const d = new DRACOLoader().setDecoderPath('draco/');
        loader.setDRACOLoader(d);
        dracoLoader = d;
      }
      loader.load(
      `globe/${file}`,
      (gltf) => {
        dracoLoader?.dispose();
        const m = gltf.scene;
        m.updateMatrixWorld(true);
        // scale to a mean radius of 1 about the model's centre. The compact model is a cube-sphere, round to under 1 %, centred
        // on its box. The 8k model has relief in its mesh, which skews the box, so its centre is the mesh origin.
        // The v2 globe is centred on its origin too (kilometres from the Moon's centre), with heights at true scale in its mesh.
        const relief = !!MODEL_HAS_RELIEF[file];
        const centre = relief || isV2 ? new THREE.Vector3() : new THREE.Box3().setFromObject(m).getCenter(new THREE.Vector3());
        let sum = 0;
        let n = 0;
        let tpr = 0; // image pixels per radian of surface (S12 zoom limit), measured from this model
        const p = new THREE.Vector3();
        m.traverse((o) => {
          const mesh = o as THREE.Mesh;
          if (!mesh.isMesh) return;
          const pos = mesh.geometry.getAttribute('position');
          const step = Math.max(7, Math.floor(pos.count / 20000) | 1);
          for (let i = 0; i < pos.count; i += step) {
            sum += p.fromBufferAttribute(pos, i).applyMatrix4(mesh.matrixWorld).sub(centre).length();
            n++;
          }
          const nrm = mesh.geometry.getAttribute('normal');
          if (relief) {
            // smoothed and toned-down relief shading, smooth caps at the poles (globeMath.reliefNormals says why)
            reliefNormals(pos.array, nrm.array, RELIEF_SHADE, RELIEF_CAP_FROM_DEG, RELIEF_CAP_TO_DEG);
          } else if (isV2) {
            // the v2 globe keeps its own normals: smooth, from its true-scale heights
          } else {
            // The compact model's normals are per facet, which draws the day-night line as a staircase. That mesh is a sphere
            // with no relief of its own, so the smooth normal is the direction from its centre.
            mesh.geometry.computeBoundingBox();
            const c0 = mesh.geometry.boundingBox!.getCenter(new THREE.Vector3());
            for (let i = 0; i < pos.count; i++) {
              p.fromBufferAttribute(pos, i).sub(c0).normalize();
              nrm.setXYZ(i, p.x, p.y, p.z);
            }
          }
          nrm.needsUpdate = true;
          made.geo.push(mesh.geometry);
          const old = mesh.material as THREE.MeshStandardMaterial;
          const map = old.map;
          const img = map?.image as { width?: number; height?: number } | undefined;
          if (img?.width && img.height) {
            // an equirectangular image has height / π pixels per radian of latitude; any other unwrap is measured from its texture coordinates
            const uv = mesh.geometry.getAttribute('uv');
            const here = relief ? img.height / Math.PI : uv ? texelsPerRadian(pos.array, uv.array, mesh.geometry.index?.array ?? null, img.width, img.height, mesh.worldToLocal(centre.clone()).toArray()) : 0;
            tpr = tpr ? Math.min(tpr, here) : here;
          }
          if (map) {
            map.colorSpace = THREE.SRGBColorSpace;
            map.anisotropy = Math.min(lite ? 4 : 8, maxAniso);
            made.tex.push(map);
          }
          // matte, no gloss: the model's own material has a clear coat the Moon does not
          const mat = new THREE.MeshLambertMaterial({ map });
          if (relief && map) equirectPerPixel(mat);
          old.dispose();
          mesh.material = mat;
          made.mat.push(mat);
        });
        const s = n ? n / sum : 1;
        const yaw = isV2 ? v2!.yawRad : (MODEL_YAW_RAD[file] ?? 0);
        m.scale.setScalar(s);
        m.rotation.y = yaw;
        m.position.copy(centre).applyAxisAngle(new THREE.Vector3(0, 1, 0), yaw).multiplyScalar(-s);
        if (!live) {
          made.geo.forEach((g) => g.dispose());
          made.mat.forEach((x) => x.dispose());
          made.tex.forEach((x) => x.dispose());
          return;
        }
        mats.current = made.mat;
        setModel(m);
        onReady(tpr);
      },
      // the loader's own progress events (bytes received of bytes expected), for the opening sequence's progress line
      (ev) => live && ev.lengthComputable && ev.total > 0 && onProgress?.(ev.loaded / ev.total),
      (e) => {
        dracoLoader?.dispose();
        onError(e);
      },
      );
    };
    start().catch(onError);
    return () => {
      live = false;
      made.geo.forEach((g) => g.dispose());
      made.mat.forEach((x) => x.dispose());
      made.tex.forEach((x) => x.dispose());
      made = { geo: [], mat: [], tex: [] };
    };
  }, [file]); // eslint-disable-line react-hooks/exhaustive-deps
  return model ? <primitive object={model} visible={show} /> : null;
}

interface RigProps {
  sunDir: THREE.Vector3;
  dirs: THREE.Vector3[];
  phase: GlobePhase;
  target: number;
  still: boolean;
  hold: MutableRefObject<boolean>;
  /** S12: the visitor's turn and zoom; `texelsPerRad` of the Moon model on screen sets how close the zoom may go */
  nav: MutableRefObject<GlobeNav>;
  texelsPerRad: number;
  onMoved: (moved: boolean) => void;
  wrap: MutableRefObject<HTMLDivElement | null>;
  fade: MutableRefObject<HTMLDivElement | null>;
  place: MutableRefObject<((anchors: (Pt | null)[], w: number, h: number, spot: Pt | null) => void) | null>;
  /** S13: the checked point (unit vector, model frame) and the marker element drawn over it; `pick` is set here to a function
   *  that says which point of the unit-sphere Moon lies under a screen position (null = the position is off the Moon) */
  spotDir: MutableRefObject<THREE.Vector3 | null>;
  spotEl: MutableRefObject<HTMLDivElement | null>;
  pick: MutableRefObject<((clientX: number, clientY: number) => Vec3 | null) | null>;
  ready: boolean;
  onArrive: () => void;
  onBack: () => void;
  /** opening sequence: the Moon model has loaded or failed; it is in the scene; the post chain is in use */
  loaded: boolean;
  modelIn: boolean;
  fx: boolean;
  link: MutableRefObject<IntroLink>;
  lights: MutableRefObject<{ sun: THREE.DirectionalLight | null; earth: THREE.DirectionalLight | null }>;
  props: MutableRefObject<{ sun: THREE.Object3D | null; glow: THREE.Sprite | null; dark: THREE.Object3D | null }>;
  snap: MutableRefObject<HTMLCanvasElement | null>;
  onIntroSettle: () => void;
  onIntroEnd: () => void;
}

/** Camera (pole-on view, slow drift, the dive to a site and back) and the per-frame screen positions of the sites. */
function Rig({ sunDir, dirs, phase, target, still, hold, nav, texelsPerRad, onMoved, wrap, fade, place, spotDir, spotEl, pick, ready, onArrive, onBack, loaded, modelIn, fx, link, lights, props, snap, onIntroSettle, onIntroEnd }: RigProps) {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const size = useThree((s) => s.size);
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const advance = useThree((s) => s.advance);
  const st = useRef({ t0: 0, last: '' as GlobePhase | '', marked: false, i0: -1, loadedAt: -1, arc: null as Arc | null, psi0: 0, settled: false, done: false, snapAsked: false, fadeT0: -2 });
  const tmp = useMemo(() => ({ dir: new THREE.Vector3(), up: new THREE.Vector3(), p: new THREE.Vector3(), q: new THREE.Quaternion(), home: new THREE.Vector3(), right: new THREE.Vector3() }), []);

  // "up" on screen at the start: turned so the Sun stands to the upper left (display choice; the light itself is the bundle's)
  const up0 = useMemo(() => {
    const flat = new THREE.Vector3(sunDir.x, 0, sunDir.z);
    if (flat.lengthSq() < 1e-8) flat.set(0, 0, -1);
    flat.normalize();
    const f = new THREE.Vector3(0, 1, 0); // the camera looks from the south toward the north
    const a = flat.clone().applyAxisAngle(f, Math.PI / 4);
    const right = new THREE.Vector3().crossVectors(f, a);
    return flat.dot(right) < 0 ? a : flat.clone().applyAxisAngle(f, -Math.PI / 4);
  }, [sunDir]);

  // Opening sequence: a turn about this axis by `total` takes the south-pole view to the point opposite the Sun.
  const turn = useMemo(() => {
    const anti = sunDir.clone().negate();
    const a = new THREE.Vector3().crossVectors(SOUTH, anti);
    if (a.lengthSq() < 1e-8) a.set(1, 0, 0);
    return { a: a.normalize(), total: SOUTH.angleTo(anti) };
  }, [sunDir]);
  const endCbs = useRef({ onIntroSettle, onIntroEnd });
  endCbs.current = { onIntroSettle, onIntroEnd };
  // Reduced motion: the still frame is copied (right after it is drawn, while the drawing buffer still holds it) onto a canvas
  // laid over the view; the camera then goes to the globe view underneath and the copy fades away. A cross-fade, no movement.
  useEffect(
    () =>
      addAfterEffect(() => {
        const I = link.current;
        if (!I.snap) return;
        I.snap = false;
        const c = snap.current;
        const s = st.current;
        try {
          if (c) {
            c.width = gl.domElement.width;
            c.height = gl.domElement.height;
            c.getContext('2d')?.drawImage(gl.domElement, 0, 0);
            c.style.opacity = '1';
            c.dataset.on = 'true';
            s.fadeT0 = -1; // the frame loop fades it (below), starting once the globe view has been drawn underneath
          }
        } catch {
          /* no copy: the view simply changes */
        }
        s.done = true;
        s.settled = true;
        I.fx = 0;
        endCbs.current.onIntroSettle();
        endCbs.current.onIntroEnd();
      }),
    [gl, link, snap],
  );

  // S13: the point of the Moon under a screen position. The Moon is taken as the unit sphere the pins are placed on (the 8k
  // model's drawn relief is display only), seen through this frame's camera, view shift included.
  useEffect(() => {
    const ray = new THREE.Raycaster();
    const ball = new THREE.Sphere(new THREE.Vector3(), 1);
    const hit = new THREE.Vector3();
    pick.current = (cx, cy) => {
      const r = gl.domElement.getBoundingClientRect();
      if (r.width <= 0 || r.height <= 0) return null;
      ray.setFromCamera(new THREE.Vector2(((cx - r.left) / r.width) * 2 - 1, -((cy - r.top) / r.height) * 2 + 1), camera);
      return ray.ray.intersectSphere(ball, hit) ? [hit.x, hit.y, hit.z] : null;
    };
    return () => void (pick.current = null);
  }, [gl, camera, pick]);

  useEffect(() => {
    (window as unknown as Record<string, unknown>).__polarisGlobe = { gl, scene, camera, advance, nav: nav.current };
    return () => {
      delete (window as unknown as Record<string, unknown>).__polarisGlobe;
    };
  }, [gl, scene, camera, advance]);

  useFrame((state, dt) => {
    const s = st.current;
    const now = performance.now();
    if (s.last !== phase) {
      s.last = phase;
      s.t0 = now;
    }
    const fill = size.width < 640 ? 0.92 : 0.86;
    const D = distanceForDisc(FOV, size.width, size.height, fill);
    // ---- S12: the visitor's own turn and zoom (display only). `N.q` turns the pole-on view; the slow drift is a turn about
    // the Moon's own axis folded into it, so with no input this is the S4 view exactly. ----
    const N = nav.current;
    const altHome = D - 1;
    N.zoomMin = zoomFloor(texelsPerRad, size.height, FOV, altHome);
    N.zoom = Math.min(1, Math.max(N.zoomMin, N.zoom));
    // a smaller window or a coarser model raises the floor: the picture follows at once, never left past the limit
    N.zoomNow = Math.min(1, Math.max(N.zoomMin, N.zoomNow));
    if (phase === 'idle') {
      const step = Math.min(dt, 0.1);
      if (N.goHome || N.goTo) {
        // "Back to south pole": the shortest turn that brings the pole back under the camera, and the zoom back out.
        // S13 "Zoom in here": the same turn toward the asked point, and the zoom in to the closest this model allows.
        const to = N.goHome ? SOUTH : N.goTo!;
        const z1 = N.goHome ? 1 : N.zoomMin;
        N.goHome = false;
        N.goTo = null;
        tmp.home.copy(SOUTH).applyQuaternion(N.q);
        const axis = new THREE.Vector3().crossVectors(tmp.home, to);
        const angle = tmp.home.angleTo(to);
        if (axis.lengthSq() < 1e-10) axis.copy(up0).applyQuaternion(N.q); // exactly opposite: any axis across the view
        N.home = { t0: now, q0: N.q.clone(), axis: axis.normalize(), angle, z0: N.zoomNow, z1 };
        N.dx = N.dy = N.vx = N.vy = N.nx = N.ny = 0;
      }
      if (N.home) {
        const kh = still ? 1 : Math.min(1, (now - N.home.t0) / GLOBE_NAV.HOME_MS);
        const eh = 1 - Math.pow(1 - kh, 3);
        N.q.copy(tmp.q.setFromAxisAngle(N.home.axis, N.home.angle * eh)).multiply(N.home.q0);
        N.zoom = N.zoomNow = N.home.z1 === 1 ? Math.exp(Math.log(N.home.z0) * (1 - eh)) : Math.exp(Math.log(N.home.z0) + (Math.log(N.home.z1) - Math.log(N.home.z0)) * eh);
        if (kh >= 1) N.home = null;
      } else {
        // the scale of a drag: the surface under the view centre moves with the pointer, one for one
        N.radPerPx = radPerPixel(altHome * N.zoomNow, size.height, FOV);
        let ax = -N.dx * N.radPerPx; // about the screen's vertical axis
        let ay = -N.dy * N.radPerPx; // about its horizontal axis
        N.dx = N.dy = 0;
        if (!N.dragging && (N.vx !== 0 || N.vy !== 0)) {
          // glide after release, dying away; none under reduced motion
          if (still) N.vx = N.vy = 0;
          else {
            ax -= N.vx * step;
            ay -= N.vy * step;
            const keep = Math.exp((-step * 1000) / GLOBE_NAV.GLIDE_TAU_MS);
            N.vx *= keep;
            N.vy *= keep;
            if (Math.hypot(N.vx, N.vy) < GLOBE_NAV.MIN_GLIDE_RAD_S) N.vx = N.vy = 0;
          }
        }
        if (N.nx !== 0 || N.ny !== 0) {
          // arrow keys: each press asks for a step, taken quickly (at once under reduced motion)
          const f = still ? 1 : 1 - Math.exp(-step * 14);
          const tx = Math.abs(N.nx) < 1e-4 ? N.nx : N.nx * f;
          const ty = Math.abs(N.ny) < 1e-4 ? N.ny : N.ny * f;
          ax += tx;
          ay += ty;
          N.nx -= tx;
          N.ny -= ty;
        }
        if (ax !== 0 || ay !== 0) {
          tmp.up.copy(up0).applyQuaternion(N.q);
          tmp.home.copy(SOUTH).applyQuaternion(N.q);
          tmp.right.crossVectors(tmp.up, tmp.home); // the camera looks along −home, so right = (−home) × up
          N.q.premultiply(tmp.q.setFromAxisAngle(tmp.up, ax)).premultiply(tmp.q.setFromAxisAngle(tmp.right, ay));
        }
        // the slow drift: off while a pin is hovered, while dragging and for a few seconds after any input
        const drifting = !still && !hold.current && !N.dragging && now >= N.quietUntil && N.vx === 0 && N.vy === 0;
        if (drifting) N.q.premultiply(tmp.q.setFromAxisAngle(SOUTH, step * DRIFT_DEG_PER_S * RAD));
        // (only when something turned: at rest the view is left exactly as it is, to the last bit)
        if (drifting || ax !== 0 || ay !== 0) N.q.normalize();
        // zoom eases toward what was asked, in log height (at once under reduced motion)
        const fz = still ? 1 : 1 - Math.exp(-step * 12);
        const lz = Math.log(N.zoomNow) + (Math.log(N.zoom) - Math.log(N.zoomNow)) * fz;
        N.zoomNow = Math.abs(lz - Math.log(N.zoom)) < 1e-4 ? N.zoom : Math.exp(lz);
      }
      tmp.home.copy(SOUTH).applyQuaternion(N.q);
      const moved = tmp.home.angleTo(SOUTH) > GLOBE_NAV.MOVED_DEG * RAD || N.zoom < 0.999;
      if (moved !== N.moved) {
        N.moved = moved;
        onMoved(moved);
      }
    }
    tmp.up.copy(up0).applyQuaternion(N.q);
    tmp.home.copy(SOUTH).applyQuaternion(N.q);

    // 0 = the whole-Moon view, 1 = just above the site
    let e = 0;
    let k = 1;
    if (phase === 'in' || phase === 'out') {
      k = Math.min(1, (now - s.t0) / FLIGHT_MS);
      e = phase === 'in' ? easeCamera(k) : 1 - easeCamera(k);
    } else if (phase === 'hidden') e = 1;
    const site = dirs[target] ?? SOUTH;
    tmp.dir.copy(tmp.home).lerp(site, e).normalize();
    // height above the surface blends in log space, so the dive slows evenly as the ground comes up
    const alt = Math.exp(Math.log(altHome * N.zoomNow) * (1 - e) + Math.log(ALT_END) * e);
    camera.position.copy(tmp.dir).multiplyScalar(1 + alt);
    camera.up.copy(tmp.up);
    camera.lookAt(0, 0, 0);
    let near = Math.max(0.001, alt * 0.25);
    let far = D + 2;
    // (until 18 Nov the whole-Moon view stood right of a card on wide windows; the card is gone and the Moon is centred)
    let shift = 0;

    // ---- opening sequence (S3): the same camera on its way to the view above. Display only. ----
    const intro = phase === 'intro';
    const I = link.current;
    let light = 1;
    let introE = 1;
    let tI = 0;
    if (intro) {
      const far0 = D * (size.width < 640 ? INTRO.FAR_NARROW : INTRO.FAR);
      const moonDeg = Math.asin(1 / far0) / RAD;
      if (s.i0 < 0 && (!fx || I.post)) s.i0 = now; // first light: on the post tiers, not before the post chain draws
      tI = s.i0 < 0 ? 0 : now - s.i0;
      if (loaded && s.i0 >= 0 && s.loadedAt < 0) s.loadedAt = now;
      const peek = still ? peekStillDeg(moonDeg) : peekDeg(tI, moonDeg);
      if (!s.done && s.loadedAt >= 0) {
        if (still) {
          if (!s.snapAsked) {
            s.snapAsked = true;
            s.psi0 = turn.total - peek * RAD;
            I.snap = true; // finished by the after-frame effect above
          }
        } else if (!s.arc) {
          if (I.skip || tI >= openMs(s.loadedAt - s.i0)) {
            s.arc = { t0: now, durMs: I.skip ? INTRO.SKIP_MS : INTRO.ARC_MS, from: 0, skip: I.skip };
            s.psi0 = turn.total - peek * RAD;
          }
        } else if (I.skip && !s.arc.skip) {
          // Skip during the move: finish from where the camera is, quickly, without a cut
          s.arc = { t0: now, durMs: INTRO.SKIP_MS, from: arcAt(s.arc, now, easeCamera).e, skip: true };
        }
      }
      let ki = 0;
      introE = 0;
      if (s.done) introE = 1;
      else if (s.arc) ({ e: introE, k: ki } = arcAt(s.arc, now, easeCamera));
      const psi = (s.arc || s.done || s.snapAsked ? s.psi0 : turn.total - peek * RAD) * (1 - introE);
      const dist = distAt(introE, far0, D);
      tmp.q.setFromAxisAngle(turn.a, psi);
      camera.position.copy(SOUTH).applyQuaternion(tmp.q).multiplyScalar(dist);
      camera.up.copy(up0).applyQuaternion(tmp.q);
      camera.lookAt(0, 0, 0);
      near = Math.max(0.001, (dist - 1) * 0.25);
      far = SUN_DIST + 10; // the Sun disc is in this scene
      shift *= introE;
      // sunlight comes up on the Moon once its model is in the scene (black on black until then), and is full by the hand-off
      light = !modelIn || s.loadedAt < 0 ? 0 : still ? (s.done ? 1 : 0) : Math.max(smoothStep(0, INTRO.LIGHT_RAMP_MS, now - s.loadedAt), introE);
      if (!s.settled && introE >= INTRO.CHROME_AT) {
        s.settled = true;
        onIntroSettle();
      }
      if (s.arc && ki >= 1 && !s.done) {
        s.done = true;
        onIntroEnd();
      }
    }
    if (lights.current.sun) lights.current.sun.intensity = SUN_LIGHT * light;
    if (lights.current.earth) lights.current.earth.intensity = EARTHSHINE * light;

    if (camera.fov !== FOV || Math.abs(camera.near - near) > near * 0.05 || camera.far !== far) {
      camera.fov = FOV;
      camera.near = near;
      camera.far = far;
      camera.updateProjectionMatrix();
    }
    if (shift > 0.01) camera.setViewOffset(size.width, size.height, -shift, 0, size.width, size.height);
    else if (camera.view?.enabled) camera.clearViewOffset();
    camera.updateMatrixWorld();

    // reduced motion: the still frame's copy fades away over the globe view (opacity only; set here because Simple mode's
    // reduced-motion rule turns CSS transitions off)
    if (s.fadeT0 > -2 && snap.current) {
      if (s.fadeT0 === -1) s.fadeT0 = now + 34; // two frames of the globe view first
      const a = 1 - Math.min(1, Math.max(0, (now - s.fadeT0) / INTRO.STILL_FADE_MS));
      snap.current.style.opacity = a.toFixed(3);
      if (a <= 0) {
        s.fadeT0 = -2;
        snap.current.dataset.on = 'done';
        snap.current.width = snap.current.height = 1; // free the copy
      }
    }

    // opening sequence: the Sun disc, the dark stand-in for a Moon that has not loaded yet, and the lens-effect strength
    const P = props.current;
    const lit = intro && s.i0 >= 0 && !s.done;
    if (P.sun) P.sun.visible = lit;
    if (P.dark) P.dark.visible = intro && !modelIn;
    if (lit) {
      const dist = camera.position.length();
      const sunDeg = Math.acos(Math.min(1, Math.max(-1, -camera.position.dot(sunDir) / dist))) / RAD;
      tmp.p.copy(sunDir).multiplyScalar(SUN_DIST).project(camera);
      const edge = 1 - smoothStep(0.72, 1.0, Math.max(Math.abs(tmp.p.x), Math.abs(tmp.p.y)));
      I.fx = glareFor(tI, still) * glareOut(introE) * sunClear(sunDeg, Math.asin(1 / dist) / RAD) * edge;
      tmp.p.set(0, 0, 0).project(camera);
      I.moonX = tmp.p.x * 0.5 + 0.5;
      I.moonY = tmp.p.y * 0.5 + 0.5;
      I.moonR = Math.tan(Math.asin(1 / dist)) / Math.tan((FOV * RAD) / 2) / 2;
    } else I.fx = 0;
    if (P.glow) {
      P.glow.visible = lit && I.fx > 0.002;
      P.glow.material.opacity = I.fx;
    }

    // the Moon dips to black over the last part of the dive (the terrain view then opens from black) and returns over the
    // first part of the climb
    const el = fade.current;
    if (el) el.style.opacity = phase === 'in' ? String(1 - smooth(0.6, 1, k)) : phase === 'out' ? String(smooth(0, 0.4, k)) : phase === 'hidden' ? '0' : '';

    // S13: the marker of the checked point follows the Moon; hidden while the point is behind the limb
    const mark = spotEl.current;
    let spotAt: Pt | null = null;
    const sd = spotDir.current;
    if (sd && sd.dot(camera.position) > 1) {
      tmp.p.copy(sd).project(camera);
      spotAt = { x: (tmp.p.x * 0.5 + 0.5) * size.width, y: (-tmp.p.y * 0.5 + 0.5) * size.height };
    }
    if (mark) {
      if (!spotAt) mark.style.visibility = 'hidden';
      else {
        mark.style.visibility = '';
        mark.style.transform = `translate(${spotAt.x.toFixed(1)}px, ${spotAt.y.toFixed(1)}px)`;
      }
    }

    place.current?.(
      dirs.map((d) => {
        if (d.dot(camera.position) <= 1) return null; // behind the limb
        tmp.p.copy(d).project(camera);
        return { x: (tmp.p.x * 0.5 + 0.5) * size.width, y: (-tmp.p.y * 0.5 + 0.5) * size.height };
      }),
      size.width,
      size.height,
      spotAt,
    );

    if (ready && !s.marked) {
      s.marked = true;
      // the frame being drawn now is the first with the Moon in it
      requestAnimationFrame(() => {
        performance.mark('polaris-globe-first-frame');
        wrap.current?.setAttribute('data-first-frame-ms', performance.now().toFixed(0));
      });
    }
    if (k >= 1 && phase === 'in') onArrive();
    if (k >= 1 && phase === 'out') onBack();
    void state;
  });
  return null;
}

export interface GlobeProps {
  sites: GlobeSite[];
  /** Sun and Earth directions from the bundle at the current sample (model frame); null until a bundle is loaded */
  sunDir: Vec3 | null;
  earthDir: Vec3 | null;
  tier: QualityTier;
  phase: GlobePhase;
  /** index into `sites` of the site being flown to or returned from */
  target: number;
  /** at a site, before its terrain has drawn: stay on screen (black) so the terrain opens from black, not from nothing */
  cover: boolean;
  /** index into `sites` of the site last visited (drawn as selected), or -1 */
  visited: number;
  /** the Moon model to draw first (a file in public/globe), and a better one to bring in after it, if any (globeMath.globePlan) */
  file: string;
  upgrade?: string | null;
  /** S14 Part B: the v2 globe's turn and decoder need, from its manifest; null when it has no manifest entry */
  v2?: GlobeV2 | null;
  /** S14 Part B: the model to draw instead when the v2 globe fails to load (globeMath.globeFallback); null = none */
  fallback?: string | null;
  /** told which model is on screen, each time it changes */
  onModel?: (file: string) => void;
  /** what the shimmer means, after "Shimmer = " (its numbers come from the sidecar) and the "About this view" text (its numbers come from the bundle) */
  legend: string;
  about: string;
  /** S13 "Check a spot": how close counts as at a site, and the window our results cover (both read from the bundle) */
  spotMatch?: { stepM: number; withinM: number; file: string } | null;
  spotWindow?: string | null;
  /** S14: the mast height shown in the top bar, for the spot card's any-site rows (anySite.mastLabel) */
  topMastM?: number | null;
  onPick: (i: number) => void;
  onArrive: () => void;
  onBack: () => void;
  /** opening sequence (phase 'intro'): Skip is read from `intro`; `onIntroSettle` when the interface may come in, `onIntroEnd` at the hand-off */
  intro?: MutableRefObject<IntroLink>;
  onIntroSettle?: () => void;
  onIntroEnd?: () => void;
}

/** Low tier (no post chain): the intro's Sun gets a plain soft glow, drawn once into a small image. Procedural. */
function glowTexture(): THREE.Texture {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d');
  if (g) {
    const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    grad.addColorStop(0, 'rgba(255,250,240,0.9)');
    grad.addColorStop(0.08, 'rgba(255,250,240,0.5)');
    grad.addColorStop(0.3, 'rgba(255,250,240,0.12)');
    grad.addColorStop(1, 'rgba(255,250,240,0)');
    g.fillStyle = grad;
    g.fillRect(0, 0, 128, 128);
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/**
 * The card that opens beside a pin: that site's answer (the same words and numbers its row in the old side panel had, from the
 * certainty sidecar), what the shimmer means, and the way down to its terrain.
 */
function PinCard({ site, legend, any, anyFailed, topMastM, cardRef, onFly, onClose }: { site: GlobeSite; legend: string; any: AnySite | null; anyFailed: string | null; topMastM: number | null; cardRef: (el: HTMLElement | null) => void; onFly: () => void; onClose: () => void }) {
  const id = `s-pincard-${site.id}`;
  // S14: Earth in sight and the longest Sun gap from this site's own row of the any-site file (same id, same coordinates)
  const row = any ? siteRow(any.points, site.id, site.spot.lat, site.spot.lon) : null;
  const clones = row ? cloneRanges(row) : null;
  // the file is for a 1 m mast; when the card's line (or, with no line for a mast, the top bar) is for another mast, every
  // any-site row says so beside its value
  const ml = any ? mastLabel(any, site.mastM ?? topMastM) : null;
  return (
    <section className="s-panel s-gcard s-pincard" ref={cardRef} aria-labelledby={id} data-testid="pin-card" data-site={site.id} data-nodata={site.spreadPts === null || undefined} style={{ visibility: 'hidden' }}>
      <div className="s-gcard-head">
        <h2 className="s-gcard-title" id={id}>
          {site.name}
        </h2>
        <button type="button" className="s-btn s-btn--sm s-btn--icon s-btn--quiet" aria-label="Close this card" data-testid="pin-card-close" onClick={onClose}>
          <IconClose />
        </button>
      </div>
      <p className="s-pincard-q">Does a lander here keep the Sun?</p>
      <p className="s-pincard-line" data-testid="pin-card-line">
        {site.line}
      </p>
      {site.spreadText && (
        <p className="s-globe-site-spread" data-testid="pin-card-spread">
          {site.spreadText}
        </p>
      )}
      {any &&
        (row ? (
          <>
            <dl className="s-facts" data-testid="pin-card-any" data-point={row.id}>
              <div className="s-fact" data-tone="earth">
                <dt>
                  Earth in sight
                  {ml && !ml.same && (
                    <span className="s-fact-hint" data-testid="pin-card-earth-mast">
                      {ml.label}
                    </span>
                  )}
                </dt>
                <dd>
                  <span className="s-fact-value" data-testid="pin-card-earth">
                    {pct(row.earth_pct)}
                  </span>
                  {clones && (
                    <span className="s-fact-sub" data-testid="pin-card-earth-clones">
                      {pctRange(clones.earth_center_visible_pct_hourly_samples)} across {clones.earth_center_visible_pct_hourly_samples.n} terrain variants
                    </span>
                  )}
                </dd>
              </div>
              <div className="s-fact">
                <dt>
                  Longest Sun gap
                  {ml && !ml.same && (
                    <span className="s-fact-hint" data-testid="pin-card-gap-mast">
                      {ml.label}
                    </span>
                  )}
                </dt>
                <dd>
                  <span className="s-fact-value" data-testid="pin-card-gap">
                    {hours(row.longest_sun_gap_h)}
                  </span>
                  {clones && (
                    <span className="s-fact-sub" data-testid="pin-card-gap-clones">
                      {hoursRange(clones.longest_sun_center_hidden_h)} across {clones.longest_sun_center_hidden_h.n} terrain variants
                    </span>
                  )}
                </dd>
              </div>
            </dl>
            <p className="s-pincard-fine" data-testid="pin-card-any-note" data-same-mast={ml!.same}>
              {ml!.same ? `Both for ${ml!.window}, ${ml!.label}.` : `Both ${ml!.label}, ${ml!.window}.`} Line of sight to the disc centre, not power or communications. {any.file.credit}.
            </p>
          </>
        ) : (
          <p className="s-pincard-fine" data-testid="pin-card-any-none">
            Earth in sight and longest Sun gap: the any-site file has no row for this site.
          </p>
        ))}
      {!any && (
        // the file is still on its way, or did not load (then opening a pin card or checking a spot asks again)
        <p className="s-pincard-fine" data-testid={anyFailed ? 'pin-card-any-failed' : 'pin-card-any-wait'}>
          {anyFailed
            ? `Earth in sight and longest Sun gap could not be loaded (${anyFailed}), so they are not shown. Nothing is substituted; opening a card again tries again.`
            : 'Loading Earth in sight and longest Sun gap…'}
        </p>
      )}
      <p className="s-globe-legend">
        <span className="s-globe-legend-mark" aria-hidden="true" />
        {legend}
      </p>
      <div className="s-gcard-actions">
        <button type="button" className="s-btn s-btn--sm s-btn--primary" data-testid="pin-card-fly" onClick={onFly}>
          Fly down to the terrain
          <IconArrow />
        </button>
        <HonestyTag href="?mode=expert#evidence" />
      </div>
    </section>
  );
}

export default function Globe({ file: asked, upgrade = null, v2 = null, fallback = null, onModel, sites, sunDir, earthDir, tier, phase, target, cover, visited, legend, about, spotMatch = null, spotWindow = null, topMastM = null, onPick, onArrive, onBack, intro, onIntroSettle, onIntroEnd }: GlobeProps) {
  const fx = tier === 'high' || tier === 'medium' ? tier : null;
  const lite = tier === 'low';
  const still = useReducedMotion();
  const [state, setState] = useState<'loading' | 'ready' | 'failed'>('loading');
  // S14 Part B: when the v2 globe (or its decoder) fails, the light SVS model takes its place instead of an empty view
  const [fellBack, setFellBack] = useState(false);
  const first = fellBack && fallback ? fallback : asked;
  // the better model loads after the first one is on screen and takes its place while the view is at rest (never mid-flight):
  // it fades in over the first one for UPGRADE_FADE_MS (an instant cut under reduced motion), then the first one is dropped.
  // If it fails to load the first model simply stays.
  const [up, setUp] = useState<'wait' | 'loaded' | 'fading' | 'shown' | 'failed'>('wait');
  useEffect(() => {
    if (up === 'loaded' && phase === 'idle') {
      setUp(still ? 'shown' : 'fading');
      wrap.current?.setAttribute('data-upgrade-ms', performance.now().toFixed(0));
    }
  }, [up, phase, still]);
  const file = upgrade && up === 'shown' ? upgrade : first;

  useEffect(() => onModel?.(file), [file]); // eslint-disable-line react-hooks/exhaustive-deps
  const [why, setWhy] = useState('');
  const [hot, setHot] = useState(-1); // pin under the pointer or holding focus
  const wrap = useRef<HTMLDivElement | null>(null);
  const fade = useRef<HTMLDivElement | null>(null);
  const hold = useRef(false);
  // S12: turning and zooming by hand
  const nav = useRef<GlobeNav>(newNav());
  const view = useRef<HTMLDivElement | null>(null);
  const pad = useRef<HTMLDivElement | null>(null);
  const homeBtn = useRef<HTMLButtonElement | null>(null);
  const [moved, setMoved] = useState(false);
  const [used, setUsed] = useState(false); // the visitor has turned or zoomed the Moon once: the hint has done its job
  const [tpr, setTpr] = useState<Record<string, number>>({});
  const ownLink = useRef<IntroLink>(newIntroLink());
  const link = intro ?? ownLink;
  const lights = useRef<{ sun: THREE.DirectionalLight | null; earth: THREE.DirectionalLight | null }>({ sun: null, earth: null });
  const introProps = useRef<{ sun: THREE.Object3D | null; glow: THREE.Sprite | null; dark: THREE.Object3D | null }>({ sun: null, glow: null, dark: null });
  const snap = useRef<HTMLCanvasElement | null>(null);
  const playing = phase === 'intro';
  const glowMap = useMemo(() => (playing && !fx ? glowTexture() : null), []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => glowMap?.dispose(), [glowMap]);
  useEffect(() => {
    if (state !== 'loading') useMoonLoad.setState({ frac: 1, failed: state === 'failed' });
  }, [state]);
  const pinEls = useRef<(HTMLDivElement | null)[]>([]);
  const lineEls = useRef<(SVGLineElement | null)[]>([]);
  const dotEls = useRef<(SVGCircleElement | null)[]>([]);
  const labelEl = useRef<HTMLDivElement | null>(null);
  const last = useRef<{ pins: Pt[]; centre: Pt; w: number; h: number; ring: number }>({ pins: [], centre: { x: 0, y: 0 }, w: 0, h: 0, ring: 0 });
  const hotRef = useRef(hot);
  hotRef.current = hot;
  const liveRef = useRef(false);
  liveRef.current = phase === 'idle';

  // ---- S12 pointer: drag turns the Moon, two fingers or the wheel zoom it. A press that moved is never a click. ----
  const touch = useRef<{ pts: Map<number, { x: number; y: number }>; start: { x: number; y: number } | null; slop: number; trail: { x: number; y: number; t: number }[]; pinch: number; noClick: boolean }>({ pts: new Map(), start: null, slop: 0, trail: [], pinch: 0, noClick: false });
  const quiet = () => (nav.current.quietUntil = performance.now() + GLOBE_NAV.PAUSE_AFTER_MS);
  const setDragging = (on: boolean) => {
    nav.current.dragging = on;
    if (on) {
      wrap.current?.setAttribute('data-dragging', 'true');
      setHot(-1);
      setUsed(true);
    } else wrap.current?.removeAttribute('data-dragging');
  };
  const capture = (id: number) => {
    try {
      view.current?.setPointerCapture(id);
    } catch {
      /* the pointer is already gone: the drag still ends on its pointerup or pointercancel */
    }
  };

  // ---- 18 Nov layout: no side panel. One card at a time opens beside what was pressed: a pin's card (that site's answer and
  // the way down to its terrain) or the S13 card of a checked spot (beside its marker). ----
  const [card, setCard] = useState<{ kind: 'pin'; i: number } | { kind: 'spot' } | null>(null);
  const cardRef = useRef(card);
  cardRef.current = card;
  hold.current = hot >= 0 || card !== null; // the slow drift waits while a pin is hovered or a card is open
  const cardEl = useRef<HTMLElement | null>(null);
  /** what had focus when a card was opened by keyboard: focus goes back there when the card closes */
  const opener = useRef<HTMLElement | null>(null);
  const [marked, setMarked] = useState(false);
  const spotDir = useRef<THREE.Vector3 | null>(null);
  const spotEl = useRef<HTMLDivElement | null>(null);
  const pickAt = useRef<((clientX: number, clientY: number) => Vec3 | null) | null>(null);
  const spotSites = useMemo(() => sites.map((s) => s.spot), [sites]);
  const setSpotPoint = (p: { lat: number; lon: number } | null) => {
    spotDir.current = p ? new THREE.Vector3(...moonDir(p.lat, p.lon)) : null;
    setMarked(!!p);
  };
  const byKeys = () => !!document.activeElement?.matches(':focus-visible');
  const spot = useSpotCheck(setSpotPoint, () => {
    opener.current = byKeys() ? (document.activeElement as HTMLElement) : null;
    setCard({ kind: 'spot' });
  });
  // the first-visit hint ("Click a pin or anywhere on the Moon") goes away after the first click, for good on this browser
  const [hinted, setHinted] = useState(() => {
    try {
      return window.localStorage.getItem(HINT_KEY) === '1';
    } catch {
      return false;
    }
  });
  const clicked = () => {
    if (hinted) return;
    setHinted(true);
    try {
      window.localStorage.setItem(HINT_KEY, '1');
    } catch {
      /* storage blocked: the hint is still gone until the next load */
    }
  };
  const openPin = (i: number, el: HTMLElement | null) => {
    if (!liveRef.current) return;
    clicked();
    opener.current = byKeys() || (el !== null && document.activeElement === el && el.matches(':focus-visible')) ? el : null;
    if (cardRef.current?.kind === 'spot') spot.clear();
    void spot.warmAny(); // S14: the pin card's Earth and Sun-gap rows come from the any-site file
    setCard({ kind: 'pin', i });
  };
  const closeCard = () => {
    const c = cardRef.current;
    if (!c) return;
    // focus inside the card goes back to what opened it; a card opened by a click on the Moon has no such control, so the
    // page's main region takes it instead of the document body
    const back = cardEl.current?.contains(document.activeElement) ? (opener.current ?? document.getElementById('simple-main')) : null;
    if (c.kind === 'spot') spot.clear();
    setCard(null);
    if (back) requestAnimationFrame(() => back.focus());
  };
  // a card opened by keyboard takes focus (its first action), so Enter again acts and Esc brings focus back
  useEffect(() => {
    if (!card || !opener.current) return;
    if (card.kind === 'pin') (cardEl.current?.querySelector<HTMLElement>('.s-gcard-actions .s-btn') ?? cardEl.current?.querySelector<HTMLElement>('.s-gcard-head .s-btn'))?.focus();
  }, [card]);
  // the S13 card closes itself when its answer is cleared (an edit of the boxes, a failed load, not a coordinate)
  useEffect(() => {
    if (card?.kind === 'spot' && !spot.res && !spot.busy) setCard(null);
  }, [card, spot.res, spot.busy]);
  // a long card scrolls: it says when there is more above or below its visible part (data-above / data-below), so the CSS can
  // fade that edge instead of cutting a line in half with no hint
  useEffect(() => {
    const el = cardEl.current;
    if (!card || !el) return;
    const mark = () => {
      el.toggleAttribute('data-above', el.scrollTop > 1);
      el.toggleAttribute('data-below', el.scrollHeight - el.clientHeight - el.scrollTop > 1);
    };
    mark();
    el.addEventListener('scroll', mark, { passive: true });
    const ro = new ResizeObserver(mark);
    ro.observe(el);
    const mo = new MutationObserver(() => {
      for (const c of el.children) ro.observe(c);
      mark();
    });
    for (const c of el.children) ro.observe(c);
    mo.observe(el, { childList: true, subtree: true, characterData: true });
    return () => {
      el.removeEventListener('scroll', mark);
      ro.disconnect();
      mo.disconnect();
    };
  }, [card]);
  // a flight to a site leaves no card behind on the globe
  useEffect(() => {
    if (phase !== 'idle' && cardRef.current) {
      if (cardRef.current.kind === 'spot') spot.clear();
      setCard(null);
    }
  }, [phase]); // eslint-disable-line react-hooks/exhaustive-deps
  // Esc closes the open card, after anything smaller that is open (a tooltip, the phone menu, a disclosure: SimpleApp's Esc)
  useEffect(() => {
    if (!card) return;
    const onEsc = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || !liveRef.current) return;
      if (document.querySelector('.s-shell details[open], .s-more[data-open="true"]') || document.activeElement?.closest('.s-tipwrap')) return;
      closeCard();
    };
    // capture phase: this runs before SimpleApp's own Esc handler closes that smaller thing, so one press closes one thing
    window.addEventListener('keydown', onEsc, true);
    return () => window.removeEventListener('keydown', onEsc, true);
  }, [card]); // eslint-disable-line react-hooks/exhaustive-deps
  // A click on the Moon drops a point there and opens its card; a click on the sky closes whatever card is open. A press that
  // turned into a drag never gets here: the view's capture handler below swallows the click that ends a drag.
  const onPadClick = (e: RMouseEvent<HTMLDivElement>) => {
    if (!liveRef.current || touch.current.noClick || nav.current.dragging) return;
    const d = pickAt.current?.(e.clientX, e.clientY);
    quiet();
    clicked();
    if (!d) {
      closeCard();
      return;
    }
    const { lat, lon } = dirToLatLon(d);
    opener.current = null;
    spot.drop(lat, lon, nav.current.radPerPx);
  };
  const zoomTo = (lat: number, lon: number) => {
    nav.current.goTo = new THREE.Vector3(...moonDir(lat, lon));
    nav.current.vx = nav.current.vy = 0;
    quiet();
    setUsed(true);
  };
  const flyTo = (siteId: string) => {
    const i = sites.findIndex((x) => x.id === siteId);
    if (i >= 0 && liveRef.current) onPick(i);
  };

  const onDown = (e: RPointerEvent<HTMLDivElement>) => {
    if (!liveRef.current || (e.pointerType === 'mouse' && e.button !== 0)) return;
    const T = touch.current;
    const N = nav.current;
    T.pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    // catching the Moon mid-glide or mid-return stops it there
    N.vx = N.vy = 0;
    N.home = null;
    if (T.pts.size === 1) {
      T.start = { x: e.clientX, y: e.clientY };
      T.slop = e.pointerType === 'mouse' ? GLOBE_NAV.SLOP_MOUSE_PX : GLOBE_NAV.SLOP_TOUCH_PX;
      T.trail = [{ x: e.clientX, y: e.clientY, t: e.timeStamp }];
      T.noClick = false;
    } else if (T.pts.size === 2) {
      const [a, b] = [...T.pts.values()];
      T.pinch = Math.hypot(a.x - b.x, a.y - b.y);
      T.noClick = true;
      if (!N.dragging) setDragging(true);
      for (const id of T.pts.keys()) capture(id);
    }
  };
  const onMove = (e: RPointerEvent<HTMLDivElement>) => {
    const T = touch.current;
    const N = nav.current;
    const was = T.pts.get(e.pointerId);
    if (!was) return;
    const dx = e.clientX - was.x;
    const dy = e.clientY - was.y;
    if (!N.dragging) {
      if (!T.start || Math.hypot(e.clientX - T.start.x, e.clientY - T.start.y) < T.slop) return;
      // now it is a drag: from here the pointer belongs to the Moon, wherever it travels (over a pin, off the view)
      T.noClick = true;
      setDragging(true);
      capture(e.pointerId);
      // start from where the pointer is now, so the Moon does not jump by the slop
      T.pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
      return;
    }
    T.pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (T.pts.size >= 2) {
      // two fingers: their spread zooms, their midpoint turns
      const [a, b] = [...T.pts.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      if (T.pinch > 0 && d > 0) N.zoom = N.zoomNow = Math.min(1, Math.max(N.zoomMin, N.zoomNow * (T.pinch / d)));
      T.pinch = d;
      N.dx += dx / 2;
      N.dy += dy / 2;
      return;
    }
    N.dx += dx;
    N.dy += dy;
    // the events' own times, not the time they are handled: a slow frame must not turn a flick into a stop
    T.trail.push({ x: e.clientX, y: e.clientY, t: e.timeStamp });
    if (T.trail.length > 12) T.trail.shift();
  };
  const onUp = (e: RPointerEvent<HTMLDivElement>) => {
    const T = touch.current;
    const N = nav.current;
    if (!T.pts.delete(e.pointerId)) return;
    if (T.pts.size > 0) {
      // one finger of a pinch lifted: the other carries on turning, with no fling from the pinch
      T.trail = [];
      return;
    }
    T.start = null;
    if (!N.dragging) return;
    setDragging(false);
    quiet();
    const v = releaseVelocity(T.trail, e.timeStamp);
    const cap = GLOBE_NAV.MAX_GLIDE_RAD_S;
    N.vx = Math.max(-cap, Math.min(cap, v.vx * N.radPerPx));
    N.vy = Math.max(-cap, Math.min(cap, v.vy * N.radPerPx));
    // the click that follows this release (on whatever lies under the pointer) is not a click
    window.setTimeout(() => (T.noClick = false), 0);
  };
  // the system took the pointer away (a call, a system gesture): the drag ends where it is, with no fling and no click
  const onCancel = (e: RPointerEvent<HTMLDivElement>) => {
    const T = touch.current;
    if (!T.pts.delete(e.pointerId)) return;
    T.trail = [];
    if (T.pts.size > 0) return;
    T.start = null;
    T.noClick = false;
    if (!nav.current.dragging) return;
    nav.current.vx = nav.current.vy = 0;
    setDragging(false);
    quiet();
  };
  // the wheel (and a trackpad pinch, which arrives as a wheel with ctrl held) zooms; never the page
  useEffect(() => {
    const el = view.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (!liveRef.current) return;
      e.preventDefault();
      const N = nav.current;
      const px = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaMode === 2 ? e.deltaY * el.clientHeight : e.deltaY;
      N.home = null;
      N.zoom = Math.min(1, Math.max(N.zoomMin, N.zoom * Math.exp(px * (e.ctrlKey ? 0.01 : 0.0016))));
      quiet();
      setUsed(true);
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);
  const goHome = () => {
    nav.current.goHome = true;
    quiet();
    // the button goes away once the view is back: a keyboard visitor's focus moves to the Moon itself
    if (document.activeElement === homeBtn.current) pad.current?.focus();
  };
  const onKey = (e: RKeyboardEvent<HTMLDivElement>) => {
    if (!liveRef.current || e.altKey || e.ctrlKey || e.metaKey) return;
    const N = nav.current;
    const step = GLOBE_NAV.KEY_STEP_DEG * RAD * Math.max(0.25, N.zoomNow);
    // an arrow turns the Moon that way: the surface moves toward the arrow, as it does under a drag
    if (e.key === 'ArrowLeft') N.nx += step;
    else if (e.key === 'ArrowRight') N.nx -= step;
    else if (e.key === 'ArrowUp') N.ny += step;
    else if (e.key === 'ArrowDown') N.ny -= step;
    else if (e.key === '+' || e.key === '=') N.zoom = Math.max(N.zoomMin, N.zoom / GLOBE_NAV.KEY_ZOOM);
    else if (e.key === '-' || e.key === '_') N.zoom = Math.min(1, N.zoom * GLOBE_NAV.KEY_ZOOM);
    else if (e.key === 'Home' || e.key === '0') goHome();
    else return;
    e.preventDefault();
    N.home = e.key === 'Home' || e.key === '0' ? N.home : null;
    N.vx = N.vy = 0;
    quiet();
    setUsed(true);
  };

  const sun = useMemo(() => (sunDir ? new THREE.Vector3(...sunDir) : null), [sunDir]);
  const earth = useMemo(() => (earthDir ? new THREE.Vector3(...earthDir) : null), [earthDir]);
  const dirs = useMemo(() => sites.map((s) => new THREE.Vector3(...s.dir)), [sites]);
  const sunPos = useMemo(() => (sun ? sun.clone().multiplyScalar(SUN_DIST) : new THREE.Vector3(0, 0, -SUN_DIST)), [sun]);
  const sky = fx ? postColors().sky : SKY;

  const placeLabel = () => {
    const el = labelEl.current;
    const i = hotRef.current;
    const L = last.current;
    const pin = L.pins[i];
    if (!el || !pin) return;
    const lw = el.offsetWidth;
    const lh = el.offsetHeight;
    // beside the pin, on the side away from the group; when that would run under the card or off the window, under the group
    const minX = 8;
    let x = pin.x >= L.centre.x ? pin.x + 20 : pin.x - 20 - lw;
    let y = pin.y - lh / 2;
    if (L.w < 640 || x < minX || x + lw > L.w - 8) {
      x = pin.x - lw / 2;
      y = pin.y < L.centre.y && L.w < 640 ? L.centre.y - L.ring - 30 - lh : L.centre.y + L.ring + 30;
    }
    x = Math.min(Math.max(8, x), Math.max(8, L.w - lw - 8));
    el.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`;
  };

  // The open card stands beside what it belongs to (a pin, or the checked spot's marker) and follows it as the Moon turns. On
  // phones it is a sheet along the bottom instead (styles.css), so nothing is positioned here.
  const lastSpot = useRef<Pt | null>(null);
  const placeCard = () => {
    const el = cardEl.current;
    const c = cardRef.current;
    const L = last.current;
    if (!el || !c || !L.w) return;
    if (L.w < 640) {
      if (el.style.transform) el.style.transform = '';
      el.style.visibility = '';
      return;
    }
    const a = (c.kind === 'pin' ? L.pins[c.i] : lastSpot.current) ?? { x: L.w / 2, y: L.h / 2 }; // out of sight: mid-view
    const w = el.offsetWidth;
    const h = el.offsetHeight;
    const gap = c.kind === 'pin' ? 30 : 24;
    let x = c.kind === 'spot' || a.x >= L.centre.x ? a.x + gap : a.x - gap - w;
    if (x + w > L.w - 12) x = a.x - gap - w;
    if (x < 12) x = a.x + gap;
    x = Math.min(Math.max(12, x), Math.max(12, L.w - w - 12));
    // clear of the box along the bottom
    const y = Math.min(Math.max(12, a.y - Math.min(h / 2, 96)), Math.max(12, L.h - CARD_CLEAR_BOTTOM - h));
    el.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`;
    el.style.visibility = '';
  };
  // called by the rig every frame with the sites' true screen positions
  const place = useRef<((anchors: (Pt | null)[], w: number, h: number, spot: Pt | null) => void) | null>(null);
  place.current = (anchors, w, h, spotAt) => {
    const shown = anchors.map((a, i) => (a ? i : -1)).filter((i) => i >= 0);
    const ring = w < 640 ? 60 : 78;
    const { pins, centre } = layoutPins(shown.map((i) => anchors[i]!), ring, (50 * Math.PI) / 180);
    const all: Pt[] = [];
    anchors.forEach((a, i) => {
      const k = shown.indexOf(i);
      const pinEl = pinEls.current[i];
      const line = lineEls.current[i];
      const dot = dotEls.current[i];
      if (!a || k < 0) {
        if (pinEl) pinEl.style.visibility = 'hidden';
        line?.setAttribute('visibility', 'hidden');
        dot?.setAttribute('visibility', 'hidden');
        return;
      }
      const p = pins[k];
      all[i] = p;
      if (pinEl) {
        pinEl.style.visibility = '';
        pinEl.style.transform = `translate(${(p.x - 22).toFixed(1)}px, ${(p.y - 22).toFixed(1)}px)`;
      }
      // the line stops short of the pin's dot
      const len = Math.hypot(p.x - a.x, p.y - a.y) || 1;
      const t = Math.max(0, (len - 9) / len);
      if (line) {
        line.setAttribute('visibility', 'visible');
        line.setAttribute('x1', a.x.toFixed(1));
        line.setAttribute('y1', a.y.toFixed(1));
        line.setAttribute('x2', (a.x + (p.x - a.x) * t).toFixed(1));
        line.setAttribute('y2', (a.y + (p.y - a.y) * t).toFixed(1));
      }
      if (dot) {
        dot.setAttribute('visibility', 'visible');
        dot.setAttribute('cx', a.x.toFixed(1));
        dot.setAttribute('cy', a.y.toFixed(1));
      }
    });
    last.current = { pins: all, centre, w, h, ring };
    lastSpot.current = spotAt;
    if (hotRef.current >= 0) placeLabel();
    if (cardRef.current) placeCard();
  };
  useLayoutEffect(placeLabel, [hot]); // eslint-disable-line react-hooks/exhaustive-deps
  useLayoutEffect(placeCard, [card, spot.res, spot.busy]); // eslint-disable-line react-hooks/exhaustive-deps

  const live = phase === 'idle';
  // the label keeps its words while it fades out
  const lastHot = useRef(-1);
  if (hot >= 0) lastHot.current = hot;
  const hotSite = sites[hot >= 0 ? hot : lastHot.current];
  const drawn = state === 'ready' && !!sun;
  // "shown" is the globe as a place to use: not before the opening sequence has handed over
  const shown = drawn && !playing;

  return (
    <div className="s-globe" data-testid="simple-globe" data-card={card?.kind} data-phase={phase} data-cover={cover || undefined} data-state={state} data-shown={shown} data-asset={file} data-upgrade={upgrade && (up === 'wait' || up === 'loaded' || up === 'fading') ? upgrade : undefined} data-upgrade-state={upgrade ? up : undefined} data-still={still || undefined} data-moved={moved || undefined} ref={wrap}>
      <div
        className="s-globe-view"
        ref={view}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerCancel={onCancel}
        onKeyDown={onKey}
        onClickCapture={(e) => {
          // a drag that ends over a pin (or began on one) is not a press of that pin
          if (touch.current.noClick) {
            e.preventDefault();
            e.stopPropagation();
          }
        }}
      >
      <div className="s-globe-canvas" aria-hidden="true" ref={fade}>
        <Canvas
          dpr={tier === 'medium' ? [1, 1.5] : [1, 2]}
          camera={{ position: [0, -4.7, 0], fov: FOV, near: 0.1, far: 20 }}
          gl={{ antialias: !fx, toneMapping: THREE.AgXToneMapping, toneMappingExposure: EXPOSURE, powerPreference: 'high-performance' }}
          frameloop={phase === 'hidden' ? 'never' : 'always'}
        >
          <color attach="background" args={[sky]} />
          {sun && <directionalLight ref={(l) => void (lights.current.sun = l)} position={sun.clone().multiplyScalar(10)} intensity={playing ? 0 : SUN_LIGHT} color="#ffffff" />}
          {earth && <directionalLight ref={(l) => void (lights.current.earth = l)} position={earth.clone().multiplyScalar(10)} intensity={playing ? 0 : EARTHSHINE} color={EARTHSHINE_HEX} />}
          {playing && sun && (
            <>
              {/* Opening sequence only. The Sun disc at the bundle's direction (true angular size); white. */}
              <mesh ref={(o) => void (introProps.current.sun = o)} position={sunPos} visible={false}>
                <sphereGeometry args={[SUN_DIST * Math.tan(SUN_RADIUS_DEG * RAD), 24, 12]} />
                <meshBasicMaterial color={fx ? postColors().sun : SUN_HEX} toneMapped={false} />
              </mesh>
              {glowMap && (
                <sprite ref={(o) => void (introProps.current.glow = o)} position={sunPos} scale={SUN_DIST * Math.tan(3 * RAD) * 2} visible={false}>
                  <spriteMaterial map={glowMap} transparent opacity={0} depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
                </sprite>
              )}
              {/* a sky-black ball where the Moon will be, so the Sun is hidden behind the Moon before its model has loaded */}
              <mesh ref={(o) => void (introProps.current.dark = o)} visible={false}>
                <sphereGeometry args={[0.98, 64, 32]} />
                <meshBasicMaterial color={sky} toneMapped={false} />
              </mesh>
            </>
          )}
          {file === first && (
            <Moon
              file={first}
              lite={lite}
              v2={v2}
              layer={up === 'fading' ? 'under' : 'solo'}
              onReady={(t) => {
                setTpr((m) => ({ ...m, [first]: t }));
                setState('ready');
              }}
              onProgress={(f) => useMoonLoad.setState({ frac: f })}
              onFail={(m) => {
                if (first === GLOBE_V2 && fallback && !fellBack) {
                  // eslint-disable-next-line no-console
                  console.warn(`POLARIS: the v2 globe did not load (${m}); drawing ${fallback} instead`);
                  wrap.current?.setAttribute('data-fallback-from', GLOBE_V2);
                  setFellBack(true);
                  return;
                }
                setWhy(m);
                setState('failed');
              }}
            />
          )}
          {upgrade && state === 'ready' && up !== 'failed' && !playing && (
            <Moon
              file={upgrade}
              lite={lite}
              v2={v2}
              show={up === 'fading' || up === 'shown'}
              layer={up === 'shown' ? 'solo' : 'over'}
              run={phase === 'idle'}
              onReady={(t) => {
                setTpr((m) => ({ ...m, [upgrade]: t }));
                setUp('loaded');
              }}
              onFail={() => setUp('failed')}
              onFaded={() => setUp('shown')}
            />
          )}
          {sun && (
            <Rig
              sunDir={sun}
              dirs={dirs}
              phase={phase}
              target={target}
              still={still}
              hold={hold}
              nav={nav}
              texelsPerRad={tpr[file] ?? 0}
              onMoved={setMoved}
              wrap={wrap}
              fade={fade}
              place={place}
              spotDir={spotDir}
              spotEl={spotEl}
              pick={pickAt}
              ready={drawn}
              onArrive={onArrive}
              onBack={onBack}
              loaded={state !== 'loading'}
              modelIn={state === 'ready'}
              fx={!!fx}
              link={link}
              lights={lights}
              props={introProps}
              snap={snap}
              onIntroSettle={() => onIntroSettle?.()}
              onIntroEnd={() => onIntroEnd?.()}
            />
          )}
          {fx && (
            <Suspense fallback={null}>
              {/* the Sun stands about 90° off the globe view, so its disc is never in that picture: bloom has nothing to act on
                  there. Only the opening sequence has the Sun in frame, with its intro-only lens effects (link.fx). */}
              <SimplePost tier={fx} sunPos={sunPos} sunOn={playing} intro={link} />
            </Suspense>
          )}
        </Canvas>
        {/* reduced motion: the still frame of the opening sequence, fading away over the globe view */}
        <canvas className="s-intro-still" ref={snap} />
      </div>

      {state === 'loading' && (
        <p className="note s-globe-status" role="status">
          Loading the Moon…
        </p>
      )}
      {state === 'failed' && (
        <p className="error s-globe-status" role="alert">
          The Moon model could not be loaded ({why}). The site buttons still work.
        </p>
      )}

      {/* S12: the Moon itself takes the keyboard. Its focus ring is drawn inside the view's edge. */}
      <div
        className="s-globe-pad"
        ref={pad}
        tabIndex={live ? 0 : -1}
        role="application"
        aria-label="The Moon. Arrow keys turn it, plus and minus zoom, Home goes back to the south pole. The site buttons follow. A click on the Moon checks that spot; the Check a spot boxes below do the same from typed coordinates."
        data-testid="globe-pad"
        inert={playing}
        onClick={onPadClick}
      />
      {/* during the opening sequence the pins are unseen and do nothing: out of the tab order and the accessibility tree */}
        <div className="s-globe-pins" data-live={live} inert={playing}>
        <svg className="s-globe-leaders" aria-hidden="true" focusable="false">
          {sites.map((s, i) => (
            <g key={s.id} data-hot={hot === i || undefined}>
              <line ref={(el) => void (lineEls.current[i] = el)} visibility="hidden" />
              <circle ref={(el) => void (dotEls.current[i] = el)} r="2" visibility="hidden" />
            </g>
          ))}
        </svg>
        {sites.map((s, i) => (
          <div
            key={s.id}
            className="s-globe-pin"
            data-testid={`globe-pin-${s.id}`}
            data-nodata={s.spreadPts === null || undefined}
            data-spread={s.spreadPts ?? ''}
            style={{ visibility: 'hidden' }}
            ref={(el) => void (pinEls.current[i] = el)}
            onPointerEnter={(e) => e.pointerType === 'mouse' && !nav.current.dragging && setHot(i)}
            onPointerLeave={() => setHot((h) => (h === i ? -1 : h))}
            onFocus={() => setHot(i)}
            onBlur={() => setHot((h) => (h === i ? -1 : h))}
          >
            <SitePin label={`${s.name}. ${s.line}. Open this site’s card.`} spreadPts={s.spreadPts ?? 0} selected={visited === i} still={still} onClick={(e) => openPin(i, e.currentTarget)} />
          </div>
        ))}
        {/* S13: where the checked point is. A mark only; its coordinates and values are in the card beside it. */}
        <div className="s-spot-mark" ref={spotEl} data-on={marked || undefined} data-testid="spot-mark" aria-hidden="true" style={{ visibility: 'hidden' }}>
          <i />
        </div>
        <div ref={labelEl} className="s-globe-label" data-testid="globe-hover-label">
          <HoverLabel name={hotSite?.name ?? ''} hint={hotSite?.line} visible={hot >= 0 && live && !(card?.kind === 'pin' && card.i === hot)} style={{ position: 'static' }} />
        </div>
      </div>
      {/* S12: once the view has moved, the way back to the sites */}
      <div className="s-globe-nav" data-live={live} inert={playing}>
        {moved && (
          <button type="button" className="s-btn s-btn--sm s-globe-home" data-testid="globe-home" ref={homeBtn} onClick={goHome}>
            <IconBack />
            Back to south pole
          </button>
        )}
      </div>
      </div>

      {/* The sites as a list of buttons, for the keyboard and screen readers: off screen until one of them has focus. Each
          opens the same card as its pin. The page's heading and the question it answers live here too. */}
      <nav className="s-globe-list" aria-labelledby="s-globe-h" data-testid="globe-sites" inert={playing}>
        <h1 id="s-globe-h">The Moon’s south pole</h1>
        <p className="s-globe-lede">Does a lander here keep the Sun? Pick a site to fly down to its terrain.</p>
        <ul className="s-globe-sites">
          {sites.map((s, i) => (
            <li key={s.id} data-hot={hot === i || undefined} data-nodata={s.spreadPts === null || undefined} data-testid={`globe-row-${s.id}`}>
              <button type="button" aria-expanded={card?.kind === 'pin' && card.i === i} onClick={(e) => openPin(i, e.currentTarget)} onFocus={() => setHot(i)} onBlur={() => setHot((h) => (h === i ? -1 : h))}>
                <span className="s-globe-site-name">{s.name}</span>
                <span className="s-globe-site-line">{s.line}</span>
                <span className="s-globe-site-spread">{s.spreadText}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* the open card: beside its pin or marker on wide windows, a sheet along the bottom on phones */}
      <div className="s-gcard-layer" data-live={live}>
        {card?.kind === 'pin' && sites[card.i] && (
          <PinCard
            key={card.i}
            site={sites[card.i]}
            legend={`${still ? 'Ring width' : 'Shimmer'} = ${legend}`}
            any={spot.any}
            anyFailed={spot.anyFailed}
            topMastM={topMastM}
            cardRef={(el) => void (cardEl.current = el)}
            onFly={() => live && onPick(card.i)}
            onClose={closeCard}
          />
        )}
        {card?.kind === 'spot' && <SpotCard spot={spot} sites={spotSites} match={spotMatch} windowText={spotWindow} topMastM={topMastM} cardRef={(el) => void (cardEl.current = el)} onZoom={zoomTo} onFly={flyTo} onClose={closeCard} />}
      </div>

      {/* S13: the box along the bottom, with the hints above it until they have done their job */}
      <div className="s-spot-layer" data-live={live} inert={playing}>
        <SpotBox
          spot={spot}
          hint={
            // both hints wait while a card is open: on wide windows the card would sit over them
            !card && (!hinted || (!used && !moved)) && (
              <div className="s-globe-hints">
                {!hinted && (
                  <p className="s-globe-hint" data-testid="spot-hint">
                    Click a pin or anywhere on the Moon
                  </p>
                )}
                {!used && !moved && (
                  <p className="s-globe-hint s-globe-hint--move" data-testid="globe-hint" aria-hidden="true">
                    Drag to turn · scroll to zoom
                  </p>
                )}
              </div>
            )
          }
        />
      </div>

      <details className="s-globe-about" data-testid="globe-about">
        <summary>About this view</summary>
        <p>{about}</p>
        <p className="s-globe-legend" data-testid="globe-legend">
          <span className="s-globe-legend-mark" aria-hidden="true" />
          {still ? 'Ring width' : 'Shimmer'} = {legend}
        </p>
        <p className="s-globe-about-tag">
          Every site answer on this view is <HonestyTag href="?mode=expert#evidence" />
        </p>
      </details>
    </div>
  );
}
