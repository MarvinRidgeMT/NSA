import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import { agx, agxInverse, displayColor, displayColorOverSky } from '../../src/simple/agx';

const EXPOSURE = 1.2;
const encode = (x: number) => (x <= 0.0031308 ? x * 12.92 : 1.055 * Math.pow(x, 1 / 2.4) - 0.055);
/** the 8-bit display colour a scene-linear colour ends up as after AgX + sRGB output */
const shown = (c: { r: number; g: number; b: number }) => {
  const d = agx(new THREE.Vector3(c.r, c.g, c.b), EXPOSURE);
  return [d.x, d.y, d.z].map((x) => Math.round(encode(x) * 255));
};
const rgb = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));

describe('AgX in JavaScript (Simple post path, display only)', () => {
  it('matches known behaviour of the tone curve: black stays black, mid grey stays mid, bright values approach white', () => {
    expect(shown({ r: 0, g: 0, b: 0 })).toEqual([0, 0, 0]);
    const grey = agx(new THREE.Vector3(0.18, 0.18, 0.18), 1);
    expect(grey.x).toBeGreaterThan(0.12);
    expect(grey.x).toBeLessThan(0.25);
    expect(grey.x).toBeCloseTo(grey.y, 3);
    expect(Math.min(...shown({ r: 60, g: 59, b: 57 }))).toBeGreaterThan(250);
  });
  it('agxInverse undoes agx', () => {
    for (const c of [[0.02, 0.02, 0.02], [0.2, 0.39, 0.7], [0.9, 0.5, 0.1], [1.4, 1.3, 1.2]]) {
      const back = agxInverse(agx(new THREE.Vector3(...c), EXPOSURE), EXPOSURE);
      expect(back.x).toBeCloseTo(c[0], 4);
      expect(back.y).toBeCloseTo(c[1], 4);
      expect(back.z).toBeCloseTo(c[2], 4);
    }
  });
  it('display colours come out of the final tone-mapping pass as the same 8-bit colour they have today', () => {
    for (const hex of ['#050505', '#7FA8DA']) expect(shown(displayColor(hex, EXPOSURE))).toEqual(rgb(hex));
  });
  it('a translucent marker over the sky shows the same blend as today', () => {
    for (const [hex, opacity] of [['#fff6e6', 0.28], ['#7FA8DA', 0.3]] as const) {
      const sky = displayColor('#050505', EXPOSURE);
      const x = displayColorOverSky(hex, opacity, '#050505', EXPOSURE);
      const mixed = { r: opacity * x.r + (1 - opacity) * sky.r, g: opacity * x.g + (1 - opacity) * sky.g, b: opacity * x.b + (1 - opacity) * sky.b };
      const today = rgb(hex).map((v, i) => Math.round(opacity * v + (1 - opacity) * rgb('#050505')[i]));
      expect(shown(mixed)).toEqual(today);
    }
  });
});
