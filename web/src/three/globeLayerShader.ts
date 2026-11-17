import * as THREE from 'three';
import { layerTextures, type GlobeLayer, type LayerFile } from '../globe/layers';
import { MOON_R_M } from '../globe/geo';

/**
 * DISPLAY-ONLY drape of a v2 analytics PNG on the Blender globe (T2). The globe material's fragment shader turns the
 * Moon-fixed world position into planetocentric lat / east lon (globe axes +Y north, +Z lon 0, +X 90 E) and samples
 *  - an equirectangular texture (lon -180..180, lat 90..-90), and/or
 *  - a polar-stereographic texture per pole (sphere R = 1,737,400 m, lat_ts = pole: rho = 2R tan(45° - |lat|/2),
 *    x = rho sin lon, south y = rho cos lon, north y = -rho cos lon; same formulas as src/globe/geo.ts polarStereo),
 *    which wins wherever its alpha is non-zero (finer polar grids).
 * The layer colour is mixed in after tone mapping, so a drawn pixel has exactly the legend colour at opacity 1 (unlit).
 * Pixels are never read back: no number on screen comes from this shader.
 */
export interface DrapeUniforms {
  [k: string]: THREE.IUniform;
  uLayerOn: THREE.IUniform<number>;
  uOpacity: THREE.IUniform<number>;
  uEqc: THREE.IUniform<THREE.Texture | null>;
  uHasEqc: THREE.IUniform<number>;
  uSp: THREE.IUniform<THREE.Texture | null>;
  uHasSp: THREE.IUniform<number>;
  uSpHalf: THREE.IUniform<number>;
  uNp: THREE.IUniform<THREE.Texture | null>;
  uHasNp: THREE.IUniform<number>;
  uNpHalf: THREE.IUniform<number>;
}

export function makeDrapeUniforms(): DrapeUniforms {
  return {
    uLayerOn: { value: 0 },
    uOpacity: { value: 0.75 },
    uEqc: { value: null },
    uHasEqc: { value: 0 },
    uSp: { value: null },
    uHasSp: { value: 0 },
    uSpHalf: { value: 1 },
    uNp: { value: null },
    uHasNp: { value: 0 },
    uNpHalf: { value: 1 },
  };
}

const VERT_DECL = 'varying vec3 vMoonPos;\n';
const FRAG_DECL = `
varying vec3 vMoonPos;
uniform float uLayerOn; uniform float uOpacity;
uniform sampler2D uEqc; uniform float uHasEqc;
uniform sampler2D uSp; uniform float uHasSp; uniform float uSpHalf;
uniform sampler2D uNp; uniform float uHasNp; uniform float uNpHalf;
vec4 polarSample(sampler2D tex, float halfR, float lat, float lon, float ySign) {
  float rho = 2.0 * tan(0.25 * PI - 0.5 * abs(lat));
  vec2 xy = vec2(rho * sin(lon), ySign * rho * cos(lon));
  vec2 uv = (xy + halfR) / (2.0 * halfR); // texture flipY: v = 0 at the image's bottom row (the -y edge)
  if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) return vec4(0.0);
  return texture2D(tex, uv);
}
`;
const FRAG_MIX = `
if (uLayerOn > 0.5) {
  vec3 nrm = normalize(vMoonPos);
  float lat = asin(clamp(nrm.y, -1.0, 1.0));
  float lon = atan(nrm.x, nrm.z);
  vec4 lc = vec4(0.0);
  if (uHasEqc > 0.5) lc = texture2D(uEqc, vec2((lon + PI) / (2.0 * PI), (lat + 0.5 * PI) / PI));
  if (uHasSp > 0.5 && lat < 0.0) { vec4 p = polarSample(uSp, uSpHalf, lat, lon, 1.0); if (p.a > 0.02) lc = p; }
  if (uHasNp > 0.5 && lat > 0.0) { vec4 p = polarSample(uNp, uNpHalf, lat, lon, -1.0); if (p.a > 0.02) lc = p; }
  gl_FragColor.rgb = mix(gl_FragColor.rgb, lc.rgb, lc.a * uOpacity);
}
`;

/** Patch a globe material so it can show a drape; all patched materials share one uniforms object. */
export function patchGlobeMaterial(mat: THREE.Material, u: DrapeUniforms): void {
  mat.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, u);
    shader.vertexShader = VERT_DECL + shader.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\nvMoonPos = (modelMatrix * vec4(transformed, 1.0)).xyz;');
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', `#include <common>\n${FRAG_DECL}`) // after <common>: PI is defined there
      .replace('#include <tonemapping_fragment>', `#include <tonemapping_fragment>\n${FRAG_MIX}`);
  };
  mat.customProgramCacheKey = () => 'polaris-globe-drape-v1';
  mat.needsUpdate = true;
}

const loader = new THREE.TextureLoader();
function loadTex(f: LayerFile, classes: boolean): Promise<THREE.Texture> {
  return new Promise((resolve, reject) =>
    loader.load(
      f.path,
      (t) => {
        t.colorSpace = THREE.SRGBColorSpace;
        t.generateMipmaps = false; // no mip seam at the antimeridian / pole
        t.minFilter = classes ? THREE.NearestFilter : THREE.LinearFilter;
        t.magFilter = classes ? THREE.NearestFilter : THREE.LinearFilter;
        t.wrapS = THREE.RepeatWrapping;
        t.wrapT = THREE.ClampToEdgeWrapping;
        t.needsUpdate = true;
        resolve(t);
      },
      undefined,
      () => reject(new Error(`could not load ${f.path}`)),
    ),
  );
}

/** Load a layer's textures into the shared uniforms (null layer = off). Returns a disposer. */
export async function setDrape(u: DrapeUniforms, layer: GlobeLayer | null): Promise<() => void> {
  for (const k of ['uEqc', 'uSp', 'uNp'] as const) {
    (u[k].value as THREE.Texture | null)?.dispose();
    u[k].value = null;
  }
  u.uHasEqc.value = u.uHasSp.value = u.uHasNp.value = 0;
  u.uLayerOn.value = 0;
  if (!layer || !layer.built) return () => undefined;
  const classes = layer.legend.kind === 'classes';
  const t = layerTextures(layer);
  const [eqc, sp, np] = await Promise.all([t.eqc && loadTex(t.eqc, classes), t.sp && loadTex(t.sp, classes), t.np && loadTex(t.np, classes)]);
  if (eqc) {
    u.uEqc.value = eqc;
    u.uHasEqc.value = 1;
  }
  if (sp && t.sp) {
    u.uSp.value = sp;
    u.uHasSp.value = 1;
    u.uSpHalf.value = (t.sp.halfExtentM ?? 0) / MOON_R_M;
  }
  if (np && t.np) {
    u.uNp.value = np;
    u.uHasNp.value = 1;
    u.uNpHalf.value = (t.np.halfExtentM ?? 0) / MOON_R_M;
  }
  u.uLayerOn.value = 1;
  return () => {
    eqc?.dispose();
    sp?.dispose();
    np?.dispose();
  };
}
