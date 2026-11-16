import { useEffect, useMemo, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { gridDirection } from '../bundle/frame';
import { farHorizonFromBundle, gridAngles, type TerrainContext } from '../bundle/terrainContext';
import type { Dem } from '../bundle/types';
import type { VisualLayer } from '../bundle/visualLayers';
import { useSurface, type SurfaceLayerId } from '../store/surface';
import type { View } from '../store/view';
import { useUi } from '../store/ui';

/**
 * The terrain surface when a display context pack exists for the dataset (DISPLAY ONLY; no number comes from here):
 *
 *   L0  the bundle's 5 m DEM crop, full resolution, true scale (the same geometry the crop-only path draws);
 *   L1  20 m block means of the 5 m PGDA 78 tile, about ±4 km (context pack `mid`, when present), cut out under L0;
 *   L2  the 80 m PGDA 90 regional crop around it (context pack), true scale, cut out under L1 (or L0 without L1);
 *   a skirt along L0's edge hides the metre-level mismatch between the two source DEMs (visual seam only).
 *
 * Both are shaded by one material: direct light from the bundle's Sun direction, switched off where the horizon map
 * (displayed crops) or the bundle skyline (terrain beyond the crops) puts the Sun below the local horizon, with a
 * penumbra one solar radius wide. There is no shadow map, so there is no shadow-map rectangle. Surface colour is a
 * neutral regolith grey unless a registered VISUAL image layer covers the crop.
 */
const MODE: Record<SurfaceLayerId, number> = { regolith: 0, albedo: 1, elevation: 2, slope: 3, normal: 4, coverage: 5, shadow: 6 };
/** Rows of the 201² shadow texture computed per frame (~1/25 of the pass; ~5 ms on an M5 Pro). */
const MARCH_ROWS = 8;
const SKIRT_DROP_M = 60;
/** Fixed camera exposures (like an ISO/shutter choice): scientific mode keeps one constant exposure for every sample so
 *  brightness changes are the Sun's; display mode is brighter and adds the disclosed fill term. */
const SCIENCE_EXPOSURE = 1.4;
const DISPLAY_EXPOSURE = 1.4;

const VERT = /* glsl */ `
#include <common>
#include <logdepthbuf_pars_vertex>
uniform vec2 uObsXY;
uniform float uObsGround;
varying vec3 vN;
varying vec2 vGrid;
varying float vH;
varying vec3 vW;
void main() {
  vN = normal;
  vW = (modelMatrix * vec4(position, 1.0)).xyz;
  vGrid = vec2(position.x, -position.z) + uObsXY;
  vH = position.y + uObsGround;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  #include <logdepthbuf_vertex>
}`;

const FRAG = /* glsl */ `
precision highp sampler3D;
#include <common>
#include <logdepthbuf_pars_fragment>
uniform sampler3D uHorizon;
uniform vec4 uHorizonGrid;   // originX, originY, spacing, nodes
uniform float uK;
uniform float uSunTheta;     // grid angle of the Sun, radians from +y toward +x
uniform float uSunEl;        // true Sun elevation at this sample, degrees
uniform float uFarHorizon;   // bundle skyline elevation for terrain beyond the displayed crops (degrees; -90 = none)
uniform vec3 uSunDir;        // three.js axes; elevation clamped for display
uniform float uSunI;
uniform float uFill;
uniform int uMode;
uniform float uIsRegional;
uniform float uLevel;        // 0 = L0 5 m crop, 1 = L1 20 m, 2 = L2 80 m (coverage tint, contour spacing)
uniform vec4 uCut;           // footprint of the finer level drawn on top: xmin, xmax, ymin, ymax (site-relative m)
uniform float uCutOn;
uniform vec4 uLocal;         // 5 m crop bounds: xmin, xmax, ymin, ymax (site-relative grid metres)
uniform sampler2D uAlbedo;
uniform vec4 uAlbedoBounds;  // xmin, xmax, ymin, ymax (site-relative grid metres)
uniform float uHasAlbedo;
uniform vec2 uHRange;
uniform sampler2D uShadowL;  // per 5 m cell: horizon elevation toward the Sun from the DEM march below, (deg + 3) / 12.75
uniform vec4 uDemLGrid;      // originX, originY, spacing, n
uniform vec4 uShadowGrid;    // grid of uShadowL: originX, originY, spacing, n (every 2nd 5 m cell)
uniform float uMarch;        // 1 = use uShadowL on the 5 m crop
uniform float uScience;      // 1 = scientific lighting (true Sun elevation, no fill); 0 = display adjustments (see TerrainSurface doc)
uniform float uExposure;
uniform float uGrain;        // 1 = add synthetic sub-5 m regolith grain to the shading normal (Display mode only; never geometry)
varying vec3 vN;
varying vec2 vGrid;
varying float vH;
varying vec3 vW;

// McEwen (1991) Lunar-Lambert photometric function, the standard model for the lunar surface:
//   r = A [ 2 L(a) mu0 / (mu0 + mu) + (1 - L(a)) mu0 ],  L(a) = 1 - 0.019 a + 2.42e-4 a^2 - 1.46e-6 a^3  (a = phase angle, degrees)
// At the grazing Sun of the lunar pole it is far less contrasty than Lambert (which over-darkens flat ground and blows out
// Sun-facing slopes). DISPLAY ONLY: it shades the picture; no visibility state or number comes from here.
float lunarLambert(float mu0, float mu, float phaseDeg) {
  if (mu0 <= 0.0) return 0.0;
  float a = clamp(phaseDeg, 0.0, 140.0);
  float L = clamp(1.0 - 0.019 * a + 2.42e-4 * a * a - 1.46e-6 * a * a * a, 0.0, 1.0);
  return 2.0 * L * mu0 / (mu0 + max(mu, 0.05)) + (1.0 - L) * mu0;
}

// Synthetic regolith grain (DISPLAY ONLY): gradient-noise bump at 3.1 m, 1.2 m and 0.45 m wavelengths (all below the 5 m data
// grid), each octave rotated and fading out before it would alias (pixel footprint > 40 % of its wavelength). Slopes stay near
// 1.5 deg so that a grazing Sun does not turn it into a pattern. It perturbs the shading normal only, in Display mode, and is
// declared on screen as synthetic; real relief stops at the 5 m grid.
vec2 hash22(vec2 p) {
  vec3 q = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
  q += dot(q, q.yzx + 33.33);
  return fract((q.xx + q.yz) * q.zy) * 2.0 - 1.0;
}
// gradient noise with its analytic derivative (xy = d/dx, d/dy), quintic fade
vec2 gnoiseGrad(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
  vec2 du = 30.0 * f * f * (f * (f - 2.0) + 1.0);
  vec2 ga = hash22(i), gb = hash22(i + vec2(1.0, 0.0)), gc = hash22(i + vec2(0.0, 1.0)), gd = hash22(i + vec2(1.0, 1.0));
  float va = dot(ga, f), vb = dot(gb, f - vec2(1.0, 0.0)), vc = dot(gc, f - vec2(0.0, 1.0)), vd = dot(gd, f - vec2(1.0, 1.0));
  return ga + u.x * (gb - ga) + u.y * (gc - ga) + u.x * u.y * (ga - gb - gc + gd) + du * (u.yx * (va - vb - vc + vd) + vec2(vb, vc) - va);
}
vec2 grainSlope(vec2 g, float footprint) {
  vec2 s = vec2(0.0);
  float wl = 3.1;
  float amp = 0.028;                               // slope amplitude (rise / run), about 1.6 deg
  mat2 rot = mat2(0.8, -0.6, 0.6, 0.8);
  vec2 q = g;
  for (int o = 0; o < 3; o++) {
    float fade = 1.0 - smoothstep(0.2 * wl, 0.4 * wl, footprint);
    q = rot * q + 19.7;
    if (fade > 0.0) s += fade * amp * gnoiseGrad(q / wl);                 // amp is scaled by the caller for a grazing Sun
    wl *= 0.39;
    amp *= 0.85;
  }
  return s;
}

vec3 ramp(float t) {
  vec3 a = vec3(0.10, 0.13, 0.20), b = vec3(0.42, 0.45, 0.47), c = vec3(0.86, 0.80, 0.68), d = vec3(0.98, 0.93, 0.86);
  t = clamp(t, 0.0, 1.0);
  return t < 0.4 ? mix(a, b, t / 0.4) : t < 0.8 ? mix(b, c, (t - 0.4) / 0.4) : mix(c, d, (t - 0.8) / 0.2);
}

void main() {
  bool inLocal = vGrid.x > uLocal.x && vGrid.x < uLocal.y && vGrid.y > uLocal.z && vGrid.y < uLocal.w;
  if (uCutOn > 0.5 && vGrid.x > uCut.x + 5.0 && vGrid.x < uCut.y - 5.0 && vGrid.y > uCut.z + 5.0 && vGrid.y < uCut.w - 5.0) discard;
  #include <logdepthbuf_fragment>
  vec3 n = normalize(vN);
  if (uGrain > 0.5 && uScience < 0.5 && uLevel < 1.5 && (uMode == 0 || uMode == 1)) {
    float fp = max(length(dFdx(vGrid)), length(dFdy(vGrid)));
    vec2 gs = grainSlope(vGrid, fp) * clamp(uSunEl / 6.0, 0.3, 1.0);      // gentler at a grazing Sun, where 1 deg of slope flips light to dark
    n = normalize(n - vec3(gs.x, 0.0, -gs.y));      // grid x -> three x, grid y -> three -z
  }
  vec3 uvw = vec3(((vGrid - uHorizonGrid.xy) / uHorizonGrid.z + 0.5) / uHorizonGrid.w, fract(uSunTheta / (2.0 * PI)) + 0.5 / uK);
  float hDeg = max(texture(uHorizon, uvw).r * 255.0 * 0.05 - 3.0, uFarHorizon);
  if (uMarch > 0.5 && uIsRegional < 0.5 && inLocal) {
    // crisp cast shadows on the 5 m crop (the 10 m / 7.5° horizon map smears crater shadow edges at a grazing Sun)
    vec2 uvS = ((vGrid - uShadowGrid.xy) / uShadowGrid.z + 0.5) / uShadowGrid.w;
    hDeg = max(texture2D(uShadowL, uvS).r * 12.75 - 3.0, uFarHorizon);
  }
  float vis = smoothstep(hDeg - 0.266, hDeg + 0.266, uSunEl);
  float mu0 = max(dot(n, uSunDir), 0.0);
  vec3 vdir = normalize(cameraPosition - vW);
  float mu = abs(dot(n, vdir));
  float phase = degrees(acos(clamp(dot(normalize(uSunDir), vdir), -1.0, 1.0)));
  float direct = lunarLambert(mu0, mu, phase) * vis;
  // Display mode only ("relief fill"): a weak hillshade light from the Sun's azimuth, 35° up, standing in for the light that
  // sunlit terrain scatters into shadow (real on the airless Moon, but far weaker). It keeps relief readable inside shadows.
  // Scientific mode: 0, so every shadow is as dark as the direct-light geometry makes it.
  vec3 fillDir = normalize(vec3(uSunDir.x, 0.0, uSunDir.z) * 0.819 + vec3(0.0, 0.574, 0.0));
  float fill = uScience > 0.5 ? 0.0 : uFill * (0.2 + 0.8 * max(dot(n, fillDir), 0.0));
  float light = uExposure * (uSunI * direct + fill);

  // regolith: normal albedo ~0.16 with the slightly red slope of lunar soil (linear RGB)
  vec3 base = vec3(0.172, 0.160, 0.146);
  float covered = 0.0;
  float img = 0.0;
  if (uHasAlbedo > 0.5) {
    vec2 a = (vGrid - uAlbedoBounds.xz) / (uAlbedoBounds.yw - uAlbedoBounds.xz);
    if (a.x > 0.0 && a.x < 1.0 && a.y > 0.0 && a.y < 1.0) {
      img = texture2D(uAlbedo, a).r;
      float edge = min(min(a.x, 1.0 - a.x), min(a.y, 1.0 - a.y));
      covered = img > 0.002 ? smoothstep(0.0, 0.03, edge) : 0.0;
    }
  }
  vec3 col;
  if (uMode == 1) {
    col = mix(base, base * (0.25 + 2.1 * img), covered) * light;          // image modulates colour; light and shadow stay the bundle's
  } else if (uMode == 2) {
    float t = (vH - uHRange.x) / max(uHRange.y - uHRange.x, 1.0);
    float step = uLevel > 1.5 ? 100.0 : uLevel > 0.5 ? 25.0 : 10.0;
    float line = 1.0 - smoothstep(0.0, 1.5, abs(fract(vH / step + 0.5) - 0.5) * step / max(fwidth(vH), 1e-4));
    col = mix(ramp(t), vec3(0.03), 0.55 * line) * (0.55 + 0.45 * n.y);
  } else if (uMode == 3) {
    float s = degrees(acos(clamp(n.y, 0.0, 1.0)));
    col = s < 10.0 ? mix(vec3(0.20), vec3(0.91, 0.65, 0.24), s / 10.0) : mix(vec3(0.91, 0.65, 0.24), vec3(0.88, 0.39, 0.35), clamp((s - 10.0) / 15.0, 0.0, 1.0));
  } else if (uMode == 4) {
    col = vec3(n.x, -n.z, n.y) * 0.5 + 0.5;
  } else if (uMode == 5) {
    vec3 tint = uLevel < 0.5 ? vec3(0.72, 0.79, 0.77) : uLevel < 1.5 ? vec3(0.52, 0.56, 0.58) : vec3(0.36, 0.36, 0.37);
    float stripes = step(0.5, fract((vGrid.x + vGrid.y) / 40.0));
    tint = mix(tint, vec3(0.91, 0.65, 0.24), covered * 0.55 * stripes);
    col = tint * (0.35 + 0.65 * n.y) * (0.6 + 0.4 * clamp(mu0 * 6.0, 0.0, 1.0));
  } else if (uMode == 6) {
    col = vec3(0.04 + 0.92 * vis);
  } else {
    col = base * light;
  }
  gl_FragColor = vec4(col, 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;


const MARCH_VERT = /* glsl */ `
void main() { gl_Position = vec4(position.xy, 0.0, 1.0); }`;

/** One texel per 5 m DEM cell: the horizon elevation toward the Sun, found by marching the true DEMs. Runs once per sample. */
const MARCH_FRAG = /* glsl */ `
precision highp float;
uniform sampler2D uDemL;     // the bundle's 5 m DEM crop (absolute heights, m)
uniform vec4 uDemLGrid;      // originX, originY, spacing, n
uniform vec4 uMarchGrid;     // grid of the output texture (every 2nd DEM cell)
uniform sampler2D uDemM;     // L1 20 m grid (absolute heights, m); uHasMid 0 = absent
uniform vec4 uDemMGrid;
uniform float uHasMid;
uniform sampler2D uDemR;     // the 80 m regional crop (absolute heights, m)
uniform vec4 uDemRGrid;
uniform float uNear;         // first march distance, m. 3 on the LOLA crop; 7 on the SfS display surface, whose 5 m-scale relief is
                             // shaded by the surface normal instead (binary shadows from single-pixel bumps look like blobs at a 1 deg Sun)
uniform float uHMax;         // highest height in either DEM (early exit)
uniform float uReach;        // march reach, m (the context pack's display reach)
uniform float uSunTheta;
uniform float uSunEl;
// Cast-shadow horizon toward the Sun by marching the true DEMs (5 m crop, then the 20 m ring when present, then 80 m regional), with the Moon's curvature
// (height drop t^2 / 2R). Returns the highest terrain elevation angle seen along the Sun azimuth, degrees. DISPLAY ONLY.
float marchHorizonDeg(vec2 g0, float h0, vec2 dir, float tanSun) {
  float maxTan = -1.0;
  float t = uNear;
  for (int i = 0; i < 240; i++) {
    vec2 g = g0 + dir * t;
    vec2 uvL = ((g - uDemLGrid.xy) / uDemLGrid.z + 0.5) / uDemLGrid.w;
    float h;
    if (uvL.x > 0.0 && uvL.x < 1.0 && uvL.y > 0.0 && uvL.y < 1.0) {
      h = texture2D(uDemL, uvL).r;
    } else {
      vec2 uvM = ((g - uDemMGrid.xy) / uDemMGrid.z + 0.5) / uDemMGrid.w;
      if (uHasMid > 0.5 && uvM.x > 0.0 && uvM.x < 1.0 && uvM.y > 0.0 && uvM.y < 1.0) {
        h = texture2D(uDemM, uvM).r;
      } else {
        vec2 uvR = ((g - uDemRGrid.xy) / uDemRGrid.z + 0.5) / uDemRGrid.w;
        if (uvR.x <= 0.0 || uvR.x >= 1.0 || uvR.y <= 0.0 || uvR.y >= 1.0) break;
        h = texture2D(uDemR, uvR).r;
      }
    }
    float drop = t * t / 3474800.0; // 2 R_moon, R = 1737.4 km
    maxTan = max(maxTan, (h - drop - h0) / t);
    if (maxTan > tanSun + 0.012) break;                                 // already > ~0.7 deg above the Sun's centre: shadow
    if ((uHMax - h0) / t < min(maxTan, tanSun - 0.012)) break;          // nothing farther can rise high enough to matter
    t += 2.5 + 0.025 * t;
    if (t > uReach) break;
  }
  return degrees(atan(maxTan));
}


void main() {
  vec2 ij = gl_FragCoord.xy - 0.5;
  vec2 g0 = uMarchGrid.xy + ij * uMarchGrid.z;
  float h0 = texture2D(uDemL, ((g0 - uDemLGrid.xy) / uDemLGrid.z + 0.5) / uDemLGrid.w).r + 0.4;
  vec2 sdir = vec2(sin(uSunTheta), cos(uSunTheta));
  float d = marchHorizonDeg(g0, h0, sdir, tan(radians(max(uSunEl, -2.0))));
  gl_FragColor = vec4(clamp((d + 3.0) / 12.75, 0.0, 1.0), 0.0, 0.0, 1.0);
}`;

/**
 * Regular n x n grid mesh. Index and normals are written straight into typed arrays (no per-cell allocations, no generic
 * computeVertexNormals pass): the 801 x 801 L1 ring has 640k vertices and 1.28M triangles, and the generic path took seconds.
 * Normal = cross(p[i+1] - p[i-1], p[j+1] - p[j-1]) (one-sided at the edges), which points up after the (x, z, -y) mapping.
 */
function gridGeometry(n: number, at: (i: number, j: number) => [number, number, number]) {
  const pos = new Float32Array(n * n * 3);
  let k = 0;
  for (let j = 0; j < n; j++)
    for (let i = 0; i < n; i++) {
      const p = at(i, j);
      pos[k++] = p[0];
      pos[k++] = p[1];
      pos[k++] = p[2];
    }
  const index = new Uint32Array((n - 1) * (n - 1) * 6);
  let q = 0;
  for (let j = 0; j < n - 1; j++)
    for (let i = 0; i < n - 1; i++) {
      const a = j * n + i;
      index[q++] = a;                                // faces up after the (x, z, -y) mapping
      index[q++] = a + 1;
      index[q++] = a + n;
      index[q++] = a + 1;
      index[q++] = a + n + 1;
      index[q++] = a + n;
    }
  const nor = new Float32Array(n * n * 3);
  for (let j = 0; j < n; j++) {
    const jm = (j > 0 ? j - 1 : j) * n;
    const jp = (j < n - 1 ? j + 1 : j) * n;
    for (let i = 0; i < n; i++) {
      const im = i > 0 ? i - 1 : i;
      const ip = i < n - 1 ? i + 1 : i;
      const a0 = (j * n + im) * 3;
      const a1 = (j * n + ip) * 3;
      const b0 = (jm + i) * 3;
      const b1 = (jp + i) * 3;
      const ux = pos[a1] - pos[a0], uy = pos[a1 + 1] - pos[a0 + 1], uz = pos[a1 + 2] - pos[a0 + 2];
      const vx = pos[b1] - pos[b0], vy = pos[b1 + 1] - pos[b0 + 1], vz = pos[b1 + 2] - pos[b0 + 2];
      let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
      if (ny < 0) { nx = -nx; ny = -ny; nz = -nz; }
      const l = Math.hypot(nx, ny, nz) || 1;
      const o = (j * n + i) * 3;
      nor[o] = nx / l;
      nor[o + 1] = ny / l;
      nor[o + 2] = nz / l;
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  g.setIndex(new THREE.BufferAttribute(index, 1));
  return g;
}

/** Skirt: the crop's edge vertices repeated SKIRT_DROP_M lower, with the edge normals (so it shades like the ground it hangs from). */
function skirtGeometry(local: THREE.BufferGeometry, n: number) {
  const P = local.getAttribute('position') as THREE.BufferAttribute;
  const N = local.getAttribute('normal') as THREE.BufferAttribute;
  const ring: number[] = [];
  for (let i = 0; i < n - 1; i++) ring.push(i);
  for (let j = 0; j < n - 1; j++) ring.push(j * n + (n - 1));
  for (let i = n - 1; i > 0; i--) ring.push((n - 1) * n + i);
  for (let j = n - 1; j > 0; j--) ring.push(j * n);
  const m = ring.length;
  const pos = new Float32Array(m * 2 * 3);
  const nor = new Float32Array(m * 2 * 3);
  ring.forEach((v, r) => {
    for (const lower of [0, 1]) {
      const o = (r * 2 + lower) * 3;
      pos[o] = P.getX(v);
      pos[o + 1] = P.getY(v) - lower * SKIRT_DROP_M;
      pos[o + 2] = P.getZ(v);
      nor[o] = N.getX(v);
      nor[o + 1] = N.getY(v);
      nor[o + 2] = N.getZ(v);
    }
  });
  const index: number[] = [];
  for (let r = 0; r < m; r++) {
    const a = r * 2;
    const b = ((r + 1) % m) * 2;
    index.push(a, b, a + 1, b, b + 1, a + 1);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  g.setIndex(index);
  return g;
}

function horizonTexture(data: Uint8Array, m: number, K: number) {
  const t = new THREE.Data3DTexture(data, m, m, K);
  t.format = THREE.RedFormat;
  t.type = THREE.UnsignedByteType;
  t.minFilter = THREE.LinearFilter;
  t.magFilter = THREE.LinearFilter;
  t.wrapS = THREE.ClampToEdgeWrapping;
  t.wrapT = THREE.ClampToEdgeWrapping;
  t.wrapR = THREE.RepeatWrapping; // azimuth wraps
  t.unpackAlignment = 1;
  t.needsUpdate = true;
  return t;
}

export interface TerrainSurfaceProps {
  v: View;
  dem: Dem;
  obs: { x: number; y: number; ground: number };
  /** the crop geometry already built by the scene (positions relative to the observer, true scale) */
  local: THREE.BufferGeometry;
  ctx: TerrainContext;
  layer: SurfaceLayerId;
  albedo: { texture: THREE.Texture; layer: VisualLayer } | null;
}

export function TerrainSurface({ v, dem, obs, local, ctx, layer, albedo }: TerrainSurfaceProps) {
  const { meta } = ctx;
  const detail = useSurface((s) => s.detail);
  const setDetailFacts = useSurface((s) => s.setDetailFacts);
  const hasDisplay = !!(ctx.localDisplay && meta.localDisplay);
  useEffect(() => {
    setDetailFacts({ detailCoverage: hasDisplay ? meta.localDisplay!.coverageFraction : 0, detailRmsM: hasDisplay ? meta.localDisplay!.minusSolverCropM.rms : 0 });
    return () => setDetailFacts({ detailCoverage: 0, detailRmsM: 0 });
  }, [hasDisplay, meta, setDetailFacts]);
  const gl = useThree((st) => st.gl);
  const site = v.dataset.site.projectedMeters;

  const built = useMemo(() => {
    // Display surface of the 5 m crop: NASA GSFC shape-from-shading relief where the pack has it. Shifted vertically by a constant
    // so it meets the bundle's ground height at the observer's cell (the mast, rays and markers are placed on bundle heights). The same
    // constant is applied to L1 and L2, so the displayed levels keep their heights relative to each other.
    const D = detail && ctx.localDisplay && meta.localDisplay ? ctx.localDisplay : null;
    let dShift = 0;
    if (D) {
      const oi = Math.min(dem.n - 1, Math.max(0, Math.round((obs.x - dem.originX) / dem.spacing)));
      const oj = Math.min(dem.n - 1, Math.max(0, Math.round((obs.y - dem.originY) / dem.spacing)));
      dShift = dem.values[oj * dem.n + oi] - D[oj * dem.n + oi];
    }
    const localGeo = D ? gridGeometry(dem.n, (i, j) => [dem.originX + i * dem.spacing - obs.x, D[j * dem.n + i] + dShift - obs.ground, -(dem.originY + j * dem.spacing - obs.y)]) : local;
    const ownsLocal = !!D;
    const R = meta.regional;
    const regional = gridGeometry(R.n, (i, j) => [R.originX + i * R.spacingM - obs.x, ctx.regional[j * R.n + i] + dShift - obs.ground, -(R.originY + j * R.spacingM - obs.y)]);
    const skirt = skirtGeometry(localGeo, dem.n);
    // L1 carries the SfS blend where it exists. With the relief toggle off, the 5 m crop is the solver's LOLA surface, so an
    // SfS-blended ring around it would not match it: the ring is then left out (5 m LOLA crop inside the 80 m LOLA context).
    const midOk = meta.mid && ctx.mid && ctx.midHorizon && meta.horizon.mid && (D || !(meta.mid.sfsFraction && meta.mid.sfsFraction > 0));
    const M = midOk ? meta.mid! : null;
    const mid = M ? gridGeometry(M.n, (i, j) => [M.originX + i * M.spacingM - obs.x, ctx.mid![j * M.n + i] + dShift - obs.ground, -(M.originY + j * M.spacingM - obs.y)]) : null;
    const midSkirt = mid && M ? skirtGeometry(mid, M.n) : null;
    const K = meta.horizon.azimuths;
    const texLocal = horizonTexture(ctx.localHorizon, meta.horizon.local.m, K);
    const texRegional = horizonTexture(ctx.regionalHorizon, meta.horizon.regional.m, K);
    const texMid = M ? horizonTexture(ctx.midHorizon!, meta.horizon.mid!.m, K) : null;
    let lo = Infinity;
    let hi = -Infinity;
    for (const z of dem.values) {
      if (z < lo) lo = z;
      if (z > hi) hi = z;
    }
    let rlo = Infinity;
    let rhi = -Infinity;
    for (let k = 0; k < ctx.regional.length; k++) {
      const z = ctx.regional[k];
      if (z < rlo) rlo = z;
      if (z > rhi) rhi = z;
    }
    const ext = (dem.n - 1) * dem.spacing;
    const linearFloat = gl.extensions.has('OES_texture_float_linear');
    const floatTex = (data: Float32Array, n: number) => {
      const t = new THREE.DataTexture(data, n, n, THREE.RedFormat, THREE.FloatType);
      t.minFilter = t.magFilter = linearFloat ? THREE.LinearFilter : THREE.NearestFilter;
      t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
      t.needsUpdate = true;
      return t;
    };
    const demL = floatTex(D ? Float32Array.from(D, (z) => z + dShift) : dem.values instanceof Float32Array ? dem.values : Float32Array.from(dem.values), dem.n);
    const demR = floatTex(dShift ? Float32Array.from(ctx.regional, (z) => z + dShift) : ctx.regional, R.n);
    const demM = M ? floatTex(dShift ? Float32Array.from(ctx.mid!, (z) => z + dShift) : ctx.mid!, M.n) : floatTex(new Float32Array(1), 1);
    // Shadow texture on every 2nd DEM cell (10 m for the 5 m crops). Two targets: the front one is sampled while the back one is
    // filled a few rows per frame (session A, 15 Nov: filling all 161k cells in one frame stalled the M5 Pro GPU ~1 s per sample).
    // LOLA crop: every 2nd cell (10 m). SfS display surface: every cell (5 m), because its relief is real at that scale and
    // 10 m shadow texels turn the many small shadows of a grazing Sun into blobs.
    const sStep = D ? 1 : 2;
    const sm = Math.floor((dem.n - 1) / sStep) + 1;
    const shadowGrid = new THREE.Vector4(dem.originX, dem.originY, dem.spacing * sStep, sm);
    const mkRT = () => new THREE.WebGLRenderTarget(sm, sm, { type: THREE.UnsignedByteType, format: THREE.RGBAFormat, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter, depthBuffer: false, stencilBuffer: false });
    const shadowRT = mkRT();
    const shadowBack = mkRT();
    const marchMat = new THREE.ShaderMaterial({
      vertexShader: MARCH_VERT,
      fragmentShader: MARCH_FRAG,
      uniforms: {
        uDemL: { value: demL },
        uDemLGrid: { value: new THREE.Vector4(dem.originX, dem.originY, dem.spacing, dem.n) },
        uMarchGrid: { value: shadowGrid },
        uDemM: { value: demM },
        uDemMGrid: { value: M ? new THREE.Vector4(M.originX, M.originY, M.spacingM, M.n) : new THREE.Vector4(0, 0, 1, 1) },
        uHasMid: { value: M ? 1 : 0 },
        uNear: { value: D ? 7 : 3 },
        uDemR: { value: demR },
        uDemRGrid: { value: new THREE.Vector4(R.originX, R.originY, R.spacingM, R.n) },
        uHMax: { value: Math.max(hi, rhi) },
        uReach: { value: meta.displayReachM },
        uSunTheta: { value: 0 },
        uSunEl: { value: 0 },
      },
      depthTest: false,
      depthWrite: false,
    });
    const marchScene = new THREE.Scene();
    const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), marchMat);
    quad.frustumCulled = false;
    marchScene.add(quad);
    const marchCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    const common = () => ({
      uShadowL: { value: shadowRT.texture },
      uShadowGrid: { value: shadowGrid },
      uDemLGrid: { value: new THREE.Vector4(dem.originX, dem.originY, dem.spacing, dem.n) },
      uMarch: { value: linearFloat ? 1 : 0 },
      uObsXY: { value: new THREE.Vector2(obs.x, obs.y) },
      uObsGround: { value: obs.ground },
      uK: { value: K },
      uSunTheta: { value: 0 },
      uSunEl: { value: 0 },
      uFarHorizon: { value: -90 },
      uSunDir: { value: new THREE.Vector3(0, 1, 0) },
      uSunI: { value: 3.1 },
      uFill: { value: 0.1 },
      uScience: { value: 0 },
      uExposure: { value: 1 },
      uGrain: { value: 0 },
      uMode: { value: 0 },
      uLocal: { value: new THREE.Vector4(dem.originX, dem.originX + ext, dem.originY, dem.originY + ext) },
      uCut: { value: new THREE.Vector4(0, 0, 0, 0) },
      uCutOn: { value: 0 },
      uLevel: { value: 0 },
      uAlbedo: { value: null as THREE.Texture | null },
      uAlbedoBounds: { value: new THREE.Vector4(0, 1, 0, 1) },
      uHasAlbedo: { value: 0 },
    });
    const mk = (uniforms: Record<string, THREE.IUniform>, side: THREE.Side) => new THREE.ShaderMaterial({ vertexShader: VERT, fragmentShader: FRAG, uniforms, side });
    const hl = meta.horizon.local;
    const hr = meta.horizon.regional;
    const matLocal = mk({ ...common(), uHorizon: { value: texLocal }, uHorizonGrid: { value: new THREE.Vector4(hl.originX, hl.originY, hl.spacingM, hl.m) }, uIsRegional: { value: 0 }, uHRange: { value: new THREE.Vector2(lo, hi) } }, THREE.DoubleSide);
    const localCut = new THREE.Vector4(dem.originX, dem.originX + ext, dem.originY, dem.originY + ext);
    const midCut = M ? new THREE.Vector4(M.originX, M.originX + (M.n - 1) * M.spacingM, M.originY, M.originY + (M.n - 1) * M.spacingM) : localCut;
    const matRegional = mk({ ...common(), uHorizon: { value: texRegional }, uHorizonGrid: { value: new THREE.Vector4(hr.originX, hr.originY, hr.spacingM, hr.m) }, uIsRegional: { value: 1 }, uLevel: { value: 2 }, uCut: { value: midCut }, uCutOn: { value: 1 }, uHRange: { value: new THREE.Vector2(rlo, rhi) } }, THREE.FrontSide);
    let mlo = Infinity;
    let mhi = -Infinity;
    if (ctx.mid) for (let k = 0; k < ctx.mid.length; k++) { const z = ctx.mid[k]; if (z < mlo) mlo = z; if (z > mhi) mhi = z; }
    const hm = meta.horizon.mid;
    const matMid = M && texMid && hm ? mk({ ...common(), uHorizon: { value: texMid }, uHorizonGrid: { value: new THREE.Vector4(hm.originX, hm.originY, hm.spacingM, hm.m) }, uIsRegional: { value: 1 }, uLevel: { value: 1 }, uCut: { value: localCut }, uCutOn: { value: 1 }, uHRange: { value: new THREE.Vector2(mlo, mhi) } }, THREE.DoubleSide) : null;
    return { localGeo, ownsLocal, dShift, regional, skirt, mid, midSkirt, texMid, matMid, demM, texLocal, texRegional, matLocal, matRegional, demL, demR, shadowRT, shadowBack, sm, marchMat, marchScene, marchCam, quad, linearFloat };
  }, [ctx, meta, local, dem, obs.x, obs.y, obs.ground, gl, detail]);

  // GPU resources are owned here: free them when the dataset / context changes or the scene unmounts
  const prev = useRef(built);
  useEffect(() => {
    prev.current = built;
    return () => {
      built.regional.dispose();
      if (built.ownsLocal) built.localGeo.dispose();
      built.mid?.dispose();
      built.midSkirt?.dispose();
      built.texMid?.dispose();
      built.matMid?.dispose();
      built.demM.dispose();
      built.skirt.dispose();
      built.texLocal.dispose();
      built.texRegional.dispose();
      built.demL.dispose();
      built.demR.dispose();
      built.shadowRT.dispose();
      built.shadowBack.dispose();
      built.marchMat.dispose();
      built.quad.geometry.dispose();
      built.matLocal.dispose();
      built.matRegional.dispose();
    };
  }, [built]);

  // per-sample state: uniforms only, no geometry work
  const sk = v.series?.skyline;
  const ctrl = v.dataset.derived?.attribution?.perBin?.ctrlDistM ?? null;
  const trueDir = gridDirection(v.basis, v.sun.az, v.sun.el);
  const trueLight = useUi((s) => s.trueLight); // Apex lighting toggle: true elevation, no clamp (shared with the crop-only path)
  const shown = gridDirection(v.basis, v.sun.az, trueLight ? v.sun.el : Math.max(v.sun.el, 0.5)); // same display clamp as the crop-only path
  const { thetaDeg } = gridAngles(trueDir);
  const far = sk ? farHorizonFromBundle(sk.azimuthDeg, sk.elevationDeg, ctrl, v.sun.az, meta.displayReachM) : null;
  for (const m of [built.matLocal, built.matRegional, ...(built.matMid ? [built.matMid] : [])]) {
    const u = m.uniforms;
    u.uSunTheta.value = (thetaDeg * Math.PI) / 180;
    u.uSunEl.value = v.sun.el;
    u.uScience.value = trueLight ? 1 : 0;
    u.uGrain.value = detail ? 1 : 0;
    u.uExposure.value = trueLight ? SCIENCE_EXPOSURE : DISPLAY_EXPOSURE;

    u.uFarHorizon.value = far ?? -90;
    (u.uSunDir.value as THREE.Vector3).set(shown[0], shown[2], -shown[1]);
    u.uMode.value = layer === 'albedo' && !albedo ? 0 : MODE[layer];
    u.uHasAlbedo.value = albedo ? 1 : 0;
    u.uAlbedo.value = albedo?.texture ?? null;
    if (albedo) {
      const b = albedo.layer.boundsM;
      (u.uAlbedoBounds.value as THREE.Vector4).set(b.xmin - site.x, b.xmax - site.x, b.ymin - site.y, b.ymax - site.y);
    }
  }

  // cast-shadow pass: once per Sun position (sample), spread over frames. The back target is filled MARCH_ROWS rows per frame
  // (scissored full-screen quad); when complete it is swapped in, so the scene never shows a half-updated shadow. A newer
  // sample arriving mid-job waits for the current job to finish (playback can't starve the update).
  const marchKey = useRef('');
  const job = useRef<{ key: string; row: number; theta: number; el: number } | null>(null);
  const pending = useRef<{ key: string; theta: number; el: number } | null>(null);
  const front = useRef<'a' | 'b'>('a');
  useFrame(() => {
    if (!built.linearFloat) return;
    const key = `${v.sun.az.toFixed(4)}:${v.sun.el.toFixed(4)}`;
    if (marchKey.current !== key) {
      marchKey.current = key;
      const td = gridDirection(v.basis, v.sun.az, v.sun.el);
      pending.current = { key, theta: (gridAngles(td).thetaDeg * Math.PI) / 180, el: v.sun.el };
    }
    if (!job.current && pending.current) {
      job.current = { ...pending.current, row: 0 };
      pending.current = null;
    }
    const j = job.current;
    if (!j) return;
    const [frontRT, backRT] = front.current === 'a' ? [built.shadowRT, built.shadowBack] : [built.shadowBack, built.shadowRT];
    built.marchMat.uniforms.uSunTheta.value = j.theta;
    built.marchMat.uniforms.uSunEl.value = j.el;
    const rows = Math.min(built.sm > 300 ? MARCH_ROWS * 2 : MARCH_ROWS, built.sm - j.row);
    const prevRT = gl.getRenderTarget();
    const prevTM = gl.toneMapping;
    gl.toneMapping = THREE.NoToneMapping;
    backRT.scissorTest = true;
    backRT.scissor.set(0, j.row, built.sm, rows);
    gl.setRenderTarget(backRT);
    gl.render(built.marchScene, built.marchCam);
    backRT.scissorTest = false;
    gl.setRenderTarget(prevRT);
    gl.toneMapping = prevTM;
    j.row += rows;
    if (j.row >= built.sm) {
      for (const m of [built.matLocal, built.matRegional, ...(built.matMid ? [built.matMid] : [])]) m.uniforms.uShadowL.value = backRT.texture;
      front.current = front.current === 'a' ? 'b' : 'a';
      void frontRT;
      job.current = null;
    }
  }, -1);
  useEffect(() => {
    marchKey.current = '';
    job.current = null;
    pending.current = null;
    front.current = 'a';
  }, [built]);
  return (
    <group>
      <mesh geometry={built.localGeo} material={built.matLocal} userData={{ displayShiftM: built.dShift }} />
      <mesh geometry={built.skirt} material={built.matLocal} />
      {built.mid && built.matMid && <mesh geometry={built.mid} material={built.matMid} />}
      {built.midSkirt && built.matMid && <mesh geometry={built.midSkirt} material={built.matMid} />}
      <mesh geometry={built.regional} material={built.matRegional} frustumCulled />
    </group>
  );
}
