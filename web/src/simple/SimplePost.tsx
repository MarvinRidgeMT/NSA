import { useFrame, useThree } from '@react-three/fiber';
import { useEffect, useMemo } from 'react';
import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { FullScreenQuad, Pass } from 'three/examples/jsm/postprocessing/Pass.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { ShaderPass } from 'three/examples/jsm/postprocessing/ShaderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { CopyShader } from 'three/examples/jsm/shaders/CopyShader.js';
import { FXAAShader } from 'three/examples/jsm/shaders/FXAAShader.js';
import { BLOOM_THRESHOLD, SUN_DISC_RADIANCE, type QualityTier } from './quality';

/**
 * Section R: the Simple-mode post chain (WebGL, three's EffectComposer). Mounted inside the Simple canvas only, on the high
 * and medium quality tiers; Expert mode and the low tier never load this file and draw exactly as before.
 *
 * CAMERA EFFECTS, DISPLAY ONLY. Nothing here is read back: every number and every visible / blocked state comes from the
 * bundle. What the chain does, in order:
 *   1. the scene is drawn into a half-float (HDR) buffer, scene-linear, not tone mapped;
 *   2. bloom (UnrealBloomPass) with a threshold only the Sun disc exceeds (quality.ts BLOOM_THRESHOLD), so only the Sun glows.
 *      It runs on a half-size copy of the picture and its result is added in step 3;
 *   3. the glow is added, then a soft six-point starburst centred on the Sun (lens diffraction; it falls off steadily from
 *      the disc, so there is no separate ghost disc anywhere), then the renderer's own AgX tone mapping and sRGB output (the
 *      same functions the terrain material runs when it draws straight to the screen, so the ground keeps its brightness);
 *   4. FXAA on edges (large canvases; small ones multisample the HDR buffer instead, see MSAA_MAX_PIXELS), then zero-mean
 *      film grain in display space.
 * No haze, rays, colour wash, ambient occlusion or global illumination: the Moon has no air.
 * The two tiers run the same chain; medium differs only in the canvas pixel ratio (at most 1.5, set in Scene3D).
 */
const SUN_ANGULAR_RADIUS = (0.2665 * Math.PI) / 180;

/**
 * Weights of UnrealBloomPass's five blur levels, tight to wide (display choices, judged on the Mast-eye view): brightest at the
 * disc's edge and falling off quickly, so it reads as lens glare on the Sun, not as a ball of haze. The two widest levels are
 * left out: a glow that reaches across the black sky would read as air. The bloom buffers are sized from CSS pixels (not
 * device pixels), so the glow is the same size next to the Sun on every tier and pixel ratio.
 */
const BLOOM_MIPS = [0.03, 0.06, 0.05, 0, 0];
/** Starburst peak, in scene-linear units next to the disc (scene white is 1). */
const FLARE = 0.12;
/** Grain amplitude in display units (full range of the +/- noise; 0.03 is about +/- 4 of 255). */
const GRAIN = 0.03;

/**
 * Runs UnrealBloomPass beside the picture instead of into it: the scene is copied to a half-size, single-sample target, the
 * bloom pass works on that copy (and blends into it, which is cheap and unused), and `texture` is the glow alone. The
 * composer's own buffer is only read here, so it is resolved once per frame.
 */
class SunBloomPass extends Pass {
  readonly bloom: UnrealBloomPass;
  private readonly feed = new THREE.WebGLRenderTarget(2, 2, { type: THREE.HalfFloatType, depthBuffer: false });
  private readonly copy = new FullScreenQuad(new THREE.ShaderMaterial({ ...CopyShader, uniforms: THREE.UniformsUtils.clone(CopyShader.uniforms), depthTest: false, depthWrite: false, toneMapped: false }));
  /** device pixels per CSS pixel of the canvas; set by the owner before setSize */
  pixelRatio = 1;
  constructor() {
    super();
    this.needsSwap = false;
    this.bloom = new UnrealBloomPass(new THREE.Vector2(4, 4), 1, 0, BLOOM_THRESHOLD); // strength 1, radius 0: BLOOM_MIPS are used as given
    this.bloom.compositeMaterial.uniforms.bloomFactors.value = BLOOM_MIPS;
  }
  /** the glow alone (all mips combined, strength applied), scene-linear */
  get texture(): THREE.Texture {
    return this.bloom.renderTargetsHorizontal[0].texture;
  }
  setSize(w: number, h: number) {
    this.feed.setSize(Math.max(2, Math.round(w / 2)), Math.max(2, Math.round(h / 2)));
    this.bloom.setSize(Math.max(4, Math.round(w / this.pixelRatio)), Math.max(4, Math.round(h / this.pixelRatio))); // its first level is half of this
  }
  render(renderer: THREE.WebGLRenderer, _write: THREE.WebGLRenderTarget, read: THREE.WebGLRenderTarget) {
    (this.copy.material as THREE.ShaderMaterial).uniforms.tDiffuse.value = read.texture;
    renderer.setRenderTarget(this.feed);
    this.copy.render(renderer);
    this.bloom.render(renderer, this.feed, this.feed, 0, false);
  }
  dispose() {
    this.feed.dispose();
    this.copy.material.dispose();
    this.copy.dispose();
    this.bloom.dispose();
  }
}

const FinalShader = {
  name: 'PolarisSimpleFinal',
  uniforms: {
    tDiffuse: { value: null as THREE.Texture | null },
    tBloom: { value: null as THREE.Texture | null },
    uSun: { value: new THREE.Vector2(-10, -10) }, // Sun centre, uv
    uSunR: { value: 0.01 }, // Sun disc radius as a fraction of the picture height
    uAspect: { value: 1 },
    uFlare: { value: 0 },
    toneMappingExposure: { value: 1 },
    uSunLevel: { value: SUN_DISC_RADIANCE * 0.5 },
  },
  vertexShader: /* glsl */ `
    uniform sampler2D tDiffuse;
    uniform vec2 uSun;
    uniform float uSunR;
    uniform float uAspect;
    uniform float uFlare;
    uniform float uSunLevel;
    varying vec2 vUv;
    varying float vVis;
    float lit(vec2 o) {
      vec2 p = uSun + o * vec2(uSunR / uAspect, uSunR);
      if (p.x < 0.0 || p.x > 1.0 || p.y < 0.0 || p.y > 1.0) return 0.0;
      vec3 c = textureLod(tDiffuse, p, 0.0).rgb;
      return step(uSunLevel, dot(c, vec3(0.2126, 0.7152, 0.0722)));
    }
    void main() {
      vUv = uv;
      // How much of the Sun disc is actually in the picture (not behind drawn terrain, not off the edge): seven taps on the
      // disc, once per vertex of the full-screen triangle. The starburst scales with it and is absent when the disc is.
      vVis = 0.0;
      if (uFlare > 0.0) {
        vVis = lit(vec2(0.0));
        for (int i = 0; i < 6; i++) {
          float a = float(i) * 1.0471976;
          vVis += lit(0.6 * vec2(cos(a), sin(a)));
        }
        vVis /= 7.0;
      }
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }`,
  fragmentShader: /* glsl */ `
    uniform sampler2D tDiffuse;
    uniform sampler2D tBloom;
    uniform vec2 uSun;
    uniform float uSunR;
    uniform float uAspect;
    uniform float uFlare;
    varying vec2 vUv;
    varying float vVis;
    #include <tonemapping_pars_fragment>
    void main() {
      vec3 c = texture2D(tDiffuse, vUv).rgb + texture2D(tBloom, vUv).rgb;
      if (vVis > 0.0) {
        // six thin diffraction spikes from the Sun, brightest at the disc and gone within 18 Sun radii
        vec2 d = (vUv - uSun) * vec2(uAspect, 1.0) / uSunR;
        float r = length(d);
        float spikes = pow(abs(cos(3.0 * atan(d.y, d.x) + 0.42)), 90.0);
        float fall = exp(-r / 4.5) * (1.0 - smoothstep(10.0, 18.0, r));
        c += vVis * uFlare * fall * spikes * vec3(1.0, 0.98, 0.95);
      }
      // the renderer's own AgX and sRGB functions (the ones the terrain material runs when it draws straight to the screen),
      // called explicitly because this pass draws into a buffer, where three.js leaves tone mapping off
      gl_FragColor = sRGBTransferOETF(vec4(AgXToneMapping(c), 1.0));
    }`,
};

/**
 * Last pass, on the finished display-space picture: three's FXAA (edges only: sub-pixel blending is turned down so ground
 * texture is not softened), then zero-mean film grain. The grain comes after the anti-aliasing so it is not smoothed away.
 * The FXAA shader text is three's, with two marked lines replaced; `fxaaPatched` is false if a three.js update changes them
 * (then the stock shader is used and there is no grain; tests/unit/simple-post.test.ts fails so it is noticed).
 */
const FXAA_OUT = 'gl_FragColor = ApplyFXAA( tDiffuse, resolution.xy, vUv );';
const FXAA_SUBPIXEL = 'float _SubpixelBlending = 1.0;';
export const fxaaPatched = FXAAShader.fragmentShader.includes(FXAA_OUT) && FXAAShader.fragmentShader.includes(FXAA_SUBPIXEL);
const GRAIN_GLSL = /* glsl */ `
  uniform float uGrain;
  uniform vec2 uSeed;
  float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
  }
  // display space, zero mean: +/- noise weighted by brightness so it never lifts the black sky (weight 0 at black, and small
  // enough near black and white that neither half of the noise is clipped)
  vec3 grain(vec3 c) {
    float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
    float w = smoothstep(0.0, 0.04, l) * (1.0 - smoothstep(0.9, 1.0, l));
    return c + (hash12(gl_FragCoord.xy + uSeed) - 0.5) * uGrain * w;
  }`;
/** Last pass when the HDR buffer is multisampled (small canvases): grain only, no FXAA. */
const GrainShader = {
  name: 'PolarisSimpleGrain',
  uniforms: { tDiffuse: { value: null as THREE.Texture | null }, uGrain: { value: GRAIN }, uSeed: { value: new THREE.Vector2(0, 0) } },
  vertexShader: CopyShader.vertexShader,
  fragmentShader: `${GRAIN_GLSL}
    uniform sampler2D tDiffuse;
    varying vec2 vUv;
    void main() { gl_FragColor = texture2D(tDiffuse, vUv); gl_FragColor.rgb = grain(gl_FragColor.rgb); }`,
};
/**
 * Anti-aliasing by canvas size. Up to this many drawing-buffer pixels (a pixel-ratio-1 display, or a small stage) the HDR buffer
 * is 4x multisampled, as the screen is today: thin lines and the horizon need it most there, and it costs little at that size.
 * Above it (a Retina stage is about 2.3 million pixels) multisampling the float buffer cost about 2 ms a frame on the M4 Pro
 * (measured 16 Nov), so edges are smoothed by FXAA instead, which at that pixel density looks the same.
 */
export const MSAA_MAX_PIXELS = 1_300_000;
const LastShader = {
  name: 'PolarisSimpleFxaaGrain',
  uniforms: { ...THREE.UniformsUtils.clone(FXAAShader.uniforms), uGrain: { value: fxaaPatched ? GRAIN : 0 }, uSeed: { value: new THREE.Vector2(0, 0) } },
  vertexShader: FXAAShader.vertexShader,
  fragmentShader: fxaaPatched
    ? GRAIN_GLSL + FXAAShader.fragmentShader.replace(FXAA_SUBPIXEL, 'float _SubpixelBlending = 0.35;').replace(FXAA_OUT, `${FXAA_OUT} gl_FragColor.rgb = grain(gl_FragColor.rgb);`)
    : FXAAShader.fragmentShader,
};

export interface SimplePostProps {
  tier: Exclude<QualityTier, 'low'>;
  /** world position of the Sun disc (bundle direction; display placement) */
  sunPos: THREE.Vector3;
  /** false when the bundle says the Sun is blocked: the disc is then only a faint marker, with no glow and no starburst */
  sunOn: boolean;
}

export default function SimplePost({ tier, sunPos, sunOn }: SimplePostProps) {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);

  const built = useMemo(() => {
    const target = new THREE.WebGLRenderTarget(4, 4, { type: THREE.HalfFloatType, resolveDepthBuffer: false });
    const composer = new EffectComposer(gl, target);
    composer.setPixelRatio(1); // sizes below are drawing-buffer pixels (the composer would otherwise multiply by the device pixel ratio again)
    const render = new RenderPass(scene, camera);
    const glow = new SunBloomPass();
    const final = new ShaderPass(FinalShader);
    final.material.toneMapped = false; // tone mapping is called in the shader itself
    final.uniforms.tBloom.value = glow.texture;
    final.uniforms.toneMappingExposure.value = gl.toneMappingExposure;
    const last = new ShaderPass(LastShader);
    last.material.toneMapped = false;
    last.setSize = (w: number, h: number) => (last.uniforms.resolution.value as THREE.Vector2).set(1 / w, 1 / h);
    composer.addPass(render);
    composer.addPass(glow);
    composer.addPass(final);
    const grainOnly = new ShaderPass(GrainShader);
    grainOnly.material.toneMapped = false;
    grainOnly.enabled = false;
    composer.addPass(last);
    composer.addPass(grainOnly);
    return { composer, render, glow, final, last, grainOnly, msaa: false, w: 0, h: 0 };
  }, [gl, scene, camera]);

  useEffect(() => {
    // measurement hook for scripts/post_compare.mjs (display only)
    (window as unknown as Record<string, unknown>).__polarisPost = { tier, bloom: built.glow.bloom, final: built.final, last: built.last, grainOnly: built.grainOnly, composer: built.composer, state: built };
    return () => {
      delete (window as unknown as Record<string, unknown>).__polarisPost;
      built.composer.dispose();
      built.glow.dispose();
      built.final.dispose();
      built.last.dispose();
      built.grainOnly.dispose();
      built.render.dispose();
    };
  }, [built, tier]);

  const tmp = useMemo(() => ({ p: new THREE.Vector3(), size: new THREE.Vector2(), still: typeof matchMedia === 'function' ? matchMedia('(prefers-reduced-motion: reduce)') : null }), []);

  // priority 1: react-three-fiber stops its own gl.render and this draws the frame instead
  useFrame((state) => {
    const { composer, final, last } = built;
    gl.getDrawingBufferSize(tmp.size);
    if (tmp.size.x !== built.w || tmp.size.y !== built.h) {
      built.w = tmp.size.x;
      built.h = tmp.size.y;
      built.glow.pixelRatio = gl.getPixelRatio();
      const msaa = built.w * built.h <= MSAA_MAX_PIXELS;
      if (msaa !== built.msaa) {
        built.msaa = msaa;
        // only the buffer the scene is drawn into (the passes swap buffers twice a frame, so it is the same one every frame)
        composer.readBuffer.samples = msaa ? 4 : 0;
        composer.readBuffer.dispose(); // re-created with the new sample count on next use
        last.enabled = !msaa;
        built.grainOnly.enabled = msaa;
      }
      composer.setSize(built.w, built.h); // sizes every pass, the glow pass included
    }
    const cam = state.camera as THREE.PerspectiveCamera;
    built.render.camera = cam;
    const u = final.uniforms;
    tmp.p.copy(sunPos).project(cam);
    const inFront = tmp.p.z < 1 && Math.abs(tmp.p.x) < 1.2 && Math.abs(tmp.p.y) < 1.2;
    u.uFlare.value = sunOn && inFront ? FLARE : 0;
    (u.uSun.value as THREE.Vector2).set(tmp.p.x * 0.5 + 0.5, tmp.p.y * 0.5 + 0.5);
    u.uSunR.value = (Math.tan(SUN_ANGULAR_RADIUS) / Math.tan((cam.fov * Math.PI) / 360)) * 0.5;
    u.uAspect.value = built.w / Math.max(built.h, 1);
    // grain: a new pattern 24 times a second; one fixed pattern under prefers-reduced-motion
    const tick = tmp.still?.matches ? 0 : Math.floor(state.clock.elapsedTime * 24);
    (last.uniforms.uSeed.value as THREE.Vector2).set((tick * 37) % 251, (tick * 91) % 241);
    (built.grainOnly.uniforms.uSeed.value as THREE.Vector2).copy(last.uniforms.uSeed.value as THREE.Vector2);
    composer.render();
  }, 1);

  return null;
}
