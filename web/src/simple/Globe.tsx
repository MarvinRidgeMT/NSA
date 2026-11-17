import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { lazy, Suspense, useEffect, useLayoutEffect, useMemo, useRef, useState, type MutableRefObject } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { easeCamera } from '../store/camera';
import { EXPOSURE, postColors, SKY } from './postColors';
import type { QualityTier } from './quality';
import { DRIFT_DEG_PER_S, FLIGHT_MS, MODEL_HAS_RELIEF, MODEL_YAW_RAD, RELIEF_CAP_FROM_DEG, RELIEF_CAP_TO_DEG, RELIEF_SHADE, distanceForDisc, reliefNormals, layoutPins, type Pt, type Vec3 } from './globeMath';
import { HonestyTag, HoverLabel, SitePin } from './parts';

const SimplePost = lazy(() => import('./SimplePost'));

/**
 * Simple-mode landing view (S4, 17 Nov 2026): the Moon seen from over its south pole, with the bundle's ROI sites as pins.
 *
 * VISUAL CONTEXT ONLY. The Moon is the NASA SVS 14959 model with its LROC image; nothing here is sampled by a calculation and
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
}
export type GlobePhase = 'idle' | 'in' | 'hidden' | 'out';

const FOV = 30;
/** Camera height above the site where the dive ends, in Moon radii (the terrain view takes over from here). */
const ALT_END = 0.03;
/** Light levels: display choices. The Sun is far below the bloom threshold on purpose (only a Sun disc may bloom). */
const SUN_LIGHT = 9;
const EARTHSHINE = 0.035;
const EARTHSHINE_HEX = '#a9c1e6';
const SOUTH = new THREE.Vector3(0, -1, 0);
const smooth = (a: number, b: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

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

/** How long the 8k model takes to fade in over the compact one (none under reduced motion). */
const UPGRADE_FADE_MS = 600;

/**
 * One Moon model. `layer` is how it shares the screen while the better model fades in over the first one: 'solo' alone,
 * 'under' drawn first without writing depth (so the model over it is depth-tested only against itself, and the 8k model's
 * relief, which dips below the compact sphere in places, is not cut by it), 'over' faded in from transparent across
 * UPGRADE_FADE_MS, then `onFaded`.
 */
function Moon({ file, lite, show = true, layer = 'solo', run = true, onReady, onFail, onFaded }: { file: string; lite: boolean; show?: boolean; layer?: 'solo' | 'under' | 'over'; run?: boolean; onReady: () => void; onFail: (m: string) => void; onFaded?: () => void }) {
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
    new GLTFLoader().load(
      `globe/${file}`,
      (gltf) => {
        const m = gltf.scene;
        m.updateMatrixWorld(true);
        // scale to a mean radius of 1 about the model's centre. The compact model is a cube-sphere, round to under 1 %, centred
        // on its box. The 8k model has relief in its mesh, which skews the box, so its centre is the mesh origin.
        const relief = !!MODEL_HAS_RELIEF[file];
        const centre = relief ? new THREE.Vector3() : new THREE.Box3().setFromObject(m).getCenter(new THREE.Vector3());
        let sum = 0;
        let n = 0;
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
        const yaw = MODEL_YAW_RAD[file] ?? 0;
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
        onReady();
      },
      undefined,
      (e) => live && onFail(e instanceof Error ? e.message : String(e)),
    );
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
  wrap: MutableRefObject<HTMLDivElement | null>;
  fade: MutableRefObject<HTMLDivElement | null>;
  place: MutableRefObject<((anchors: (Pt | null)[], w: number, h: number) => void) | null>;
  ready: boolean;
  onArrive: () => void;
  onBack: () => void;
}

/** Camera (pole-on view, slow drift, the dive to a site and back) and the per-frame screen positions of the sites. */
function Rig({ sunDir, dirs, phase, target, still, hold, wrap, fade, place, ready, onArrive, onBack }: RigProps) {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const size = useThree((s) => s.size);
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const advance = useThree((s) => s.advance);
  const st = useRef({ drift: 0, t0: 0, last: '' as GlobePhase | '', marked: false });
  const tmp = useMemo(() => ({ dir: new THREE.Vector3(), up: new THREE.Vector3(), p: new THREE.Vector3(), q: new THREE.Quaternion() }), []);

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

  useEffect(() => {
    (window as unknown as Record<string, unknown>).__polarisGlobe = { gl, scene, camera, advance };
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
    if (phase === 'idle' && !still && !hold.current) s.drift += Math.min(dt, 0.1) * DRIFT_DEG_PER_S * (Math.PI / 180);
    tmp.up.copy(up0).applyAxisAngle(SOUTH, s.drift);

    // 0 = the whole-Moon view, 1 = just above the site
    let e = 0;
    let k = 1;
    if (phase === 'in' || phase === 'out') {
      k = Math.min(1, (now - s.t0) / FLIGHT_MS);
      e = phase === 'in' ? easeCamera(k) : 1 - easeCamera(k);
    } else if (phase === 'hidden') e = 1;
    const site = dirs[target] ?? SOUTH;
    tmp.dir.copy(SOUTH).lerp(site, e).normalize();
    // height above the surface blends in log space, so the dive slows evenly as the ground comes up
    const alt = Math.exp(Math.log(D - 1) * (1 - e) + Math.log(ALT_END) * e);
    camera.position.copy(tmp.dir).multiplyScalar(1 + alt);
    camera.up.copy(tmp.up);
    camera.lookAt(0, 0, 0);
    const near = Math.max(0.001, alt * 0.25);
    if (camera.fov !== FOV || Math.abs(camera.near - near) > near * 0.05 || camera.far !== D + 2) {
      camera.fov = FOV;
      camera.near = near;
      camera.far = D + 2;
      camera.updateProjectionMatrix();
    }
    // wide windows: the whole-Moon view stands right of the card; the shift eases away during the dive
    const shift = size.width >= 1024 ? (Math.min(240, size.width * 0.15) / 2) * (1 - e) : 0;
    if (shift > 0.01) camera.setViewOffset(size.width, size.height, -shift, 0, size.width, size.height);
    else if (camera.view?.enabled) camera.clearViewOffset();
    camera.updateMatrixWorld();

    // the Moon dips to black over the last part of the dive (the terrain view then opens from black) and returns over the
    // first part of the climb
    const el = fade.current;
    if (el) el.style.opacity = phase === 'in' ? String(1 - smooth(0.6, 1, k)) : phase === 'out' ? String(smooth(0, 0.4, k)) : phase === 'hidden' ? '0' : '';

    place.current?.(
      dirs.map((d) => {
        if (d.dot(camera.position) <= 1) return null; // behind the limb
        tmp.p.copy(d).project(camera);
        return { x: (tmp.p.x * 0.5 + 0.5) * size.width, y: (-tmp.p.y * 0.5 + 0.5) * size.height };
      }),
      size.width,
      size.height,
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
  /** told which model is on screen, each time it changes */
  onModel?: (file: string) => void;
  /** what the shimmer means, after "Shimmer = " (its numbers come from the sidecar) and the "About this view" text (its numbers come from the bundle) */
  legend: string;
  about: string;
  onPick: (i: number) => void;
  onArrive: () => void;
  onBack: () => void;
}

export default function Globe({ file: first, upgrade = null, onModel, sites, sunDir, earthDir, tier, phase, target, cover, visited, legend, about, onPick, onArrive, onBack }: GlobeProps) {
  const fx = tier === 'high' || tier === 'medium' ? tier : null;
  const lite = tier === 'low';
  const still = useReducedMotion();
  const [state, setState] = useState<'loading' | 'ready' | 'failed'>('loading');
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
  const pinEls = useRef<(HTMLDivElement | null)[]>([]);
  const lineEls = useRef<(SVGLineElement | null)[]>([]);
  const dotEls = useRef<(SVGCircleElement | null)[]>([]);
  const labelEl = useRef<HTMLDivElement | null>(null);
  const last = useRef<{ pins: Pt[]; centre: Pt; w: number; h: number; ring: number }>({ pins: [], centre: { x: 0, y: 0 }, w: 0, h: 0, ring: 0 });
  const hotRef = useRef(hot);
  hotRef.current = hot;
  hold.current = hot >= 0;

  const sun = useMemo(() => (sunDir ? new THREE.Vector3(...sunDir) : null), [sunDir]);
  const earth = useMemo(() => (earthDir ? new THREE.Vector3(...earthDir) : null), [earthDir]);
  const dirs = useMemo(() => sites.map((s) => new THREE.Vector3(...s.dir)), [sites]);
  const sunPos = useMemo(() => (sun ? sun.clone().multiplyScalar(50) : new THREE.Vector3(0, 0, -50)), [sun]);
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
    const view = el.parentElement?.getBoundingClientRect();
    const card = wrap.current?.querySelector('.s-globe-card')?.getBoundingClientRect();
    const minX = view && card && card.bottom > view.top + pin.y && card.right < view.left + L.w / 2 ? card.right - view.left + 8 : 8;
    let x = pin.x >= L.centre.x ? pin.x + 20 : pin.x - 20 - lw;
    let y = pin.y - lh / 2;
    if (L.w < 640 || x < minX || x + lw > L.w - 8) {
      x = pin.x - lw / 2;
      y = pin.y < L.centre.y && L.w < 640 ? L.centre.y - L.ring - 30 - lh : L.centre.y + L.ring + 30;
    }
    x = Math.min(Math.max(8, x), Math.max(8, L.w - lw - 8));
    el.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`;
  };

  // called by the rig every frame with the sites' true screen positions
  const place = useRef<((anchors: (Pt | null)[], w: number, h: number) => void) | null>(null);
  place.current = (anchors, w, h) => {
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
    if (hotRef.current >= 0) placeLabel();
  };
  useLayoutEffect(placeLabel, [hot]); // eslint-disable-line react-hooks/exhaustive-deps

  const live = phase === 'idle';
  // the label keeps its words while it fades out
  const lastHot = useRef(-1);
  if (hot >= 0) lastHot.current = hot;
  const hotSite = sites[hot >= 0 ? hot : lastHot.current];
  const shown = state === 'ready' && !!sun;

  return (
    <div className="s-globe" data-testid="simple-globe" data-phase={phase} data-cover={cover || undefined} data-state={state} data-shown={shown} data-asset={file} data-upgrade={upgrade && (up === 'wait' || up === 'loaded' || up === 'fading') ? upgrade : undefined} data-upgrade-state={upgrade ? up : undefined} data-still={still || undefined} ref={wrap}>
      <div className="s-globe-view">
      <div className="s-globe-canvas" aria-hidden="true" ref={fade}>
        <Canvas
          dpr={tier === 'medium' ? [1, 1.5] : [1, 2]}
          camera={{ position: [0, -4.7, 0], fov: FOV, near: 0.1, far: 20 }}
          gl={{ antialias: !fx, toneMapping: THREE.AgXToneMapping, toneMappingExposure: EXPOSURE, powerPreference: 'high-performance' }}
          frameloop={phase === 'hidden' ? 'never' : 'always'}
        >
          <color attach="background" args={[sky]} />
          {sun && <directionalLight position={sun.clone().multiplyScalar(10)} intensity={SUN_LIGHT} color="#ffffff" />}
          {earth && <directionalLight position={earth.clone().multiplyScalar(10)} intensity={EARTHSHINE} color={EARTHSHINE_HEX} />}
          {file === first && (
            <Moon
              file={first}
              lite={lite}
              layer={up === 'fading' ? 'under' : 'solo'}
              onReady={() => setState('ready')}
              onFail={(m) => {
                setWhy(m);
                setState('failed');
              }}
            />
          )}
          {upgrade && state === 'ready' && up !== 'failed' && (
            <Moon
              file={upgrade}
              lite={lite}
              show={up === 'fading' || up === 'shown'}
              layer={up === 'shown' ? 'solo' : 'over'}
              run={phase === 'idle'}
              onReady={() => setUp('loaded')}
              onFail={() => setUp('failed')}
              onFaded={() => setUp('shown')}
            />
          )}
          {sun && <Rig sunDir={sun} dirs={dirs} phase={phase} target={target} still={still} hold={hold} wrap={wrap} fade={fade} place={place} ready={shown} onArrive={onArrive} onBack={onBack} />}
          {fx && (
            <Suspense fallback={null}>
              {/* the Sun stands about 90° off this view, so its disc is never in the picture: bloom has nothing to act on here */}
              <SimplePost tier={fx} sunPos={sunPos} sunOn={false} />
            </Suspense>
          )}
        </Canvas>
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

      <div className="s-globe-pins" data-live={live}>
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
            onPointerEnter={(e) => e.pointerType === 'mouse' && setHot(i)}
            onPointerLeave={() => setHot((h) => (h === i ? -1 : h))}
            onFocus={() => setHot(i)}
            onBlur={() => setHot((h) => (h === i ? -1 : h))}
          >
            <SitePin label={`${s.name}. ${s.line}. Fly to this site.`} spreadPts={s.spreadPts ?? 0} selected={visited === i} still={still} onClick={() => live && onPick(i)} />
          </div>
        ))}
        <div ref={labelEl} className="s-globe-label" data-testid="globe-hover-label">
          <HoverLabel name={hotSite?.name ?? ''} hint={hotSite?.line} visible={hot >= 0 && live} style={{ position: 'static' }} />
        </div>
      </div>
      </div>

      <section className="s-panel s-globe-card" aria-labelledby="s-globe-h" data-testid="globe-card">
        <h1 id="s-globe-h">The Moon’s south pole</h1>
        <p className="s-globe-lede">Does a lander here keep the Sun? Pick a site to fly down to its terrain.</p>
        <ul className="s-globe-sites">
          {sites.map((s, i) => (
            // pointer shortcut only: the pins are the buttons (keyboard and screen readers use those)
            <li key={s.id} data-hot={hot === i || undefined} data-nodata={s.spreadPts === null || undefined} data-testid={`globe-row-${s.id}`} onClick={() => live && onPick(i)} onPointerEnter={(e) => e.pointerType === 'mouse' && setHot(i)} onPointerLeave={() => setHot((h) => (h === i ? -1 : h))}>
              <i aria-hidden="true" />
              <span className="s-globe-site-name">{s.name}</span>
              <span className="s-globe-site-line">{s.line}</span>
              <span className="s-globe-site-spread">{s.spreadText}</span>
            </li>
          ))}
        </ul>
        <p className="s-globe-legend" data-testid="globe-legend">
          <span className="s-globe-legend-mark" aria-hidden="true" />
          {still ? 'Ring width' : 'Shimmer'} = {legend}
        </p>
        <HonestyTag href="?mode=expert#evidence" />
      </section>

      <details className="s-globe-about" data-testid="globe-about">
        <summary>About this view</summary>
        <p>{about}</p>
      </details>
    </div>
  );
}
