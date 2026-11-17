import * as THREE from 'three';
import { displayColor, displayColorOverSky } from './agx';
import { SUN_DISC_RADIANCE } from './quality';

/** Renderer exposure of the DEM scene (Expert and Simple). */
export const EXPOSURE = 1.2;
/** Display colours of the sky, the Sun disc and the Earth disc, as drawn without tone mapping outside the post path. */
export const SKY = '#050505';
export const SUN_HEX = '#fff6e6';
export const EARTH_HEX = '#7FA8DA';
/** Opacity of the faint "hidden direction" markers drawn when the bundle says the Sun or Earth is blocked. */
export const SUN_HIDDEN_OPACITY = 0.28;
export const EARTH_HIDDEN_OPACITY = 0.3;

export interface PostColors {
  sky: THREE.Color;
  earth: THREE.Color;
  earthHidden: THREE.Color;
  sunHidden: THREE.Color;
  sun: THREE.Color;
}

/**
 * Colours for the Simple post path, where the whole picture is tone mapped once at the end. The sky, the Earth disc and the
 * "hidden direction" markers are display colours drawn without tone mapping today; here they get the scene-linear colour that
 * AgX maps back to the same display colour (simple/agx.ts). The visible Sun disc is the one HDR object. Display only.
 */
let cache: PostColors | null = null;
export const postColors = (): PostColors =>
  (cache ??= {
    sky: displayColor(SKY, EXPOSURE),
    earth: displayColor(EARTH_HEX, EXPOSURE),
    earthHidden: displayColorOverSky(EARTH_HEX, EARTH_HIDDEN_OPACITY, SKY, EXPOSURE),
    sunHidden: displayColorOverSky(SUN_HEX, SUN_HIDDEN_OPACITY, SKY, EXPOSURE),
    sun: new THREE.Color().setRGB(SUN_DISC_RADIANCE, SUN_DISC_RADIANCE * 0.98, SUN_DISC_RADIANCE * 0.95, THREE.LinearSRGBColorSpace),
  });
