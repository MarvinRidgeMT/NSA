import * as THREE from 'three';

/**
 * three.js AgX tone mapping (ShaderChunk/tonemapping_pars_fragment, r181) in JavaScript, with its inverse. DISPLAY ONLY.
 *
 * Why: with the Simple-mode post chain the whole picture is tone mapped once, at the end. Today a few display colours are
 * drawn WITHOUT tone mapping (`toneMapped={false}`: the sky background, the Earth disc, the "hidden direction" Sun marker).
 * To keep those exactly the colour they are today, the post path draws them with the scene-linear colour that AgX maps back
 * to the same display colour: `agxInverse(target)`.
 */
const m3 = (cols: number[][]) => new THREE.Matrix3().set(cols[0][0], cols[1][0], cols[2][0], cols[0][1], cols[1][1], cols[2][1], cols[0][2], cols[1][2], cols[2][2]);
// GLSL mat3(vec3, vec3, vec3) is column-major: each inner array below is one column, copied from three's shader chunk
const SRGB_TO_2020 = m3([[0.6274, 0.0691, 0.0164], [0.3293, 0.9195, 0.088], [0.0433, 0.0113, 0.8956]]);
const R2020_TO_SRGB = m3([[1.6605, -0.1246, -0.0182], [-0.5876, 1.1329, -0.1006], [-0.0728, -0.0083, 1.1187]]);
const INSET = m3([[0.856627153315983, 0.137318972929847, 0.11189821299995], [0.0951212405381588, 0.761241990602591, 0.0767994186031903], [0.0482516061458583, 0.101439036467562, 0.811302368396859]]);
const OUTSET = m3([[1.1271005818144368, -0.1413297634984383, -0.14132976349843826], [-0.11060664309660323, 1.157823702216272, -0.11060664309660294], [-0.016493938717834573, -0.016493938717834257, 1.2519364065950405]]);
const MIN_EV = -12.47393;
const MAX_EV = 4.026069;

const contrast = (x: number) => {
  const x2 = x * x;
  const x4 = x2 * x2;
  return 15.5 * x4 * x2 - 40.14 * x4 * x + 31.96 * x4 - 6.868 * x2 * x + 0.4298 * x2 + 0.1191 * x - 0.00232;
};
/** inverse of the (monotonic on [0, 1]) contrast curve, by bisection */
const contrastInverse = (y: number) => {
  let lo = 0;
  let hi = 1;
  for (let i = 0; i < 50; i++) {
    const mid = (lo + hi) / 2;
    if (contrast(mid) < y) lo = mid;
    else hi = mid;
  }
  return (lo + hi) / 2;
};
const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const each = (v: THREE.Vector3, f: (x: number) => number) => v.set(f(v.x), f(v.y), f(v.z));

/** Scene-linear sRGB -> display-linear sRGB, as the renderer's AgXToneMapping does at this exposure. */
export function agx(linear: THREE.Vector3, exposure: number): THREE.Vector3 {
  const c = linear.clone().multiplyScalar(exposure).applyMatrix3(SRGB_TO_2020).applyMatrix3(INSET);
  each(c, (x) => contrast(clamp01((Math.log2(Math.max(x, 1e-10)) - MIN_EV) / (MAX_EV - MIN_EV))));
  c.applyMatrix3(OUTSET);
  each(c, (x) => Math.pow(Math.max(0, x), 2.2));
  c.applyMatrix3(R2020_TO_SRGB);
  return each(c, clamp01);
}

/** Display-linear sRGB -> the scene-linear sRGB that `agx` maps to it (for colours inside AgX's output range). */
export function agxInverse(display: THREE.Vector3, exposure: number): THREE.Vector3 {
  const c = display.clone().applyMatrix3(R2020_TO_SRGB.clone().invert());
  each(c, (x) => Math.pow(Math.max(0, x), 1 / 2.2));
  c.applyMatrix3(OUTSET.clone().invert());
  each(c, (x) => Math.pow(2, contrastInverse(x) * (MAX_EV - MIN_EV) + MIN_EV));
  c.applyMatrix3(INSET.clone().invert()).applyMatrix3(SRGB_TO_2020.clone().invert());
  return c.multiplyScalar(1 / exposure);
}

const srgbToLinear = (x: number) => (x <= 0.04045 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4));

/**
 * The scene-linear colour to draw so that, after the final AgX pass, the pixel shows exactly `hex` (a display colour that
 * is drawn without tone mapping outside the post path).
 */
export function displayColor(hex: string, exposure: number): THREE.Color {
  const t = new THREE.Color(hex); // three stores it scene-linear
  const s = agxInverse(new THREE.Vector3(t.r, t.g, t.b), exposure);
  return new THREE.Color().setRGB(s.x, s.y, s.z, THREE.LinearSRGBColorSpace);
}

/**
 * Same, for a colour drawn with `opacity` over the sky background `skyHex`. Outside the post path the two are blended as
 * display (sRGB-encoded) values; in the post path blending happens before tone mapping, so the colour is solved for the
 * same displayed result: agx(opacity * X + (1 - opacity) * sky) = the display-space blend.
 */
export function displayColorOverSky(hex: string, opacity: number, skyHex: string, exposure: number): THREE.Color {
  const enc = (h: string) => {
    const n = parseInt(h.slice(1), 16); // '#rrggbb' as display (sRGB-encoded) values
    return new THREE.Vector3(((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255);
  };
  const blend = enc(hex).multiplyScalar(opacity).add(enc(skyHex).multiplyScalar(1 - opacity));
  const target = agxInverse(each(blend, srgbToLinear), exposure);
  const sky = displayColor(skyHex, exposure);
  const x = target.sub(new THREE.Vector3(sky.r, sky.g, sky.b).multiplyScalar(1 - opacity)).multiplyScalar(1 / opacity);
  return new THREE.Color().setRGB(Math.max(0, x.x), Math.max(0, x.y), Math.max(0, x.z), THREE.LinearSRGBColorSpace);
}
