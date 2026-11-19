/**
 * Simple-mode render quality (section R). DISPLAY ONLY: the tier changes how the picture is drawn, never a number or a
 * visible / blocked state. Picked once at start from what the browser reports about the device:
 *
 *   high    desktop GPU of the Apple M-series / discrete class: post effects on, pixel ratio up to 2
 *   medium  any other hardware GPU, and tablets: post effects on, pixel ratio up to 1.5 (fewer pixels to fill)
 *   low     phones and software rendering (SwiftShader, llvmpipe: the headless tests): post effects off, the scene is
 *           drawn exactly as before section R
 *
 * `?quality=high|medium|low` overrides the automatic choice (for measurements and tests); high and medium only where the
 * device can run the post chain (see pickQuality).
 */
export type QualityTier = 'high' | 'medium' | 'low';
export const QUALITY_TIERS: readonly QualityTier[] = ['high', 'medium', 'low'];

export interface DeviceFacts {
  /** WEBGL_debug_renderer_info's unmasked renderer, or gl.RENDERER; '' when WebGL is not available */
  renderer: string;
  /** matchMedia('(pointer: coarse)'): the main input is a finger */
  coarsePointer: boolean;
  /** shorter side of the screen in CSS pixels */
  shortSidePx: number;
  /**
   * WebGL2 with a renderable half-float colour buffer (EXT_color_buffer_float or EXT_color_buffer_half_float): the post chain
   * draws the scene into one. Without it the post chain is not used. Optional so older callers default to "not known" = false.
   */
  floatTargets?: boolean;
}

const SOFTWARE = /swiftshader|llvmpipe|software|basic render/i;
const STRONG_GPU = /apple m\d|apple gpu|nvidia|geforce|rtx|gtx|radeon (rx|pro)|\barc\b/i;

/** Software rendering (SwiftShader, llvmpipe and the like): no GPU. The Moon model choice (globeMath.globeAsset) reads it. */
export function isSoftwareRenderer(renderer: string): boolean {
  return SOFTWARE.test(renderer);
}

export function tierFor(f: DeviceFacts): QualityTier {
  if (!f.renderer || SOFTWARE.test(f.renderer)) return 'low';
  if (!f.floatTargets) return 'low'; // no WebGL2 half-float render target: post chain cannot run
  if (f.coarsePointer && f.shortSidePx < 600) return 'low'; // phones
  if (f.coarsePointer) return 'medium'; // tablets
  return STRONG_GPU.test(f.renderer) ? 'high' : 'medium';
}

export function deviceFacts(): DeviceFacts {
  let renderer = '';
  let floatTargets = false;
  try {
    const c = document.createElement('canvas');
    const gl2 = c.getContext('webgl2');
    const gl = (gl2 ?? c.getContext('webgl')) as WebGLRenderingContext | null;
    if (gl) {
      const ext = gl.getExtension('WEBGL_debug_renderer_info');
      renderer = String(ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
      floatTargets = !!gl2 && !!(gl2.getExtension('EXT_color_buffer_float') ?? gl2.getExtension('EXT_color_buffer_half_float'));
      gl.getExtension('WEBGL_lose_context')?.loseContext();
    }
  } catch {
    /* renderer stays '' -> low */
  }
  const coarsePointer = typeof matchMedia === 'function' && matchMedia('(pointer: coarse)').matches;
  const shortSidePx = typeof screen !== 'undefined' ? Math.min(screen.width, screen.height) : 0;
  return { renderer, coarsePointer, shortSidePx, floatTargets };
}

export interface QualityChoice {
  tier: QualityTier;
  /** 'device' = picked from the device facts; 'link' = set by ?quality= */
  source: 'device' | 'link';
}

export function pickQuality(search: string, facts: () => DeviceFacts = deviceFacts): QualityChoice {
  const q = new URLSearchParams(search).get('quality');
  if (q === 'low') return { tier: q, source: 'link' };
  const f = facts();
  // the link may ask for the post chain on any device that can run it, but never on one that cannot (no WebGL, or no
  // half-float render target): there it gets the low tier, as the automatic choice would
  if ((q === 'high' || q === 'medium') && f.renderer && f.floatTargets) return { tier: q, source: 'link' };
  return { tier: tierFor(f), source: 'device' };
}

/** What each tier draws, for "About this view". */
export const QUALITY_NOTE: Record<QualityTier, string> = {
  high: 'high (camera effects on, full resolution)',
  medium: 'medium (camera effects on, reduced resolution)',
  low: 'low (bloom, flare and grain off; the Sun keeps a plain glow)',
};

/** The "About this view" line for a tier (Simple mode only). */
export function qualityNote(tier: QualityTier): string {
  const post = tier !== 'low';
  return (
    `Quality: ${QUALITY_NOTE[tier]}, picked at start for this device. Sun glow: camera effect, display only; lens flare and starburst are in the opening sequence only.` +
    (post ? ' Film grain: camera effect, display only. No haze or rays: the Moon has no air.' : '')
  );
}

/** Display choice: radiance of the visible Sun disc relative to scene white. Far above anything else in the scene. */
export const SUN_DISC_RADIANCE = 60;
/**
 * Bloom threshold (scene-linear luminance). The brightest ground the terrain shader can produce is about 3.4 (image layer on a
 * Sun-facing slope at a grazing view); lines and markers are at most 1. Only the Sun disc passes, so only the Sun glows.
 */
export const BLOOM_THRESHOLD = 8;
