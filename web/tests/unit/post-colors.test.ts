import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import { postColors, SUN_HIDDEN_OPACITY } from '../../src/simple/postColors';
import { BLOOM_THRESHOLD } from '../../src/simple/quality';

const lum = (c: THREE.Color) => 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;

describe('Simple post colours: only the visible Sun can bloom', () => {
  it('the visible Sun disc is above the bloom threshold', () => {
    expect(lum(postColors().sun)).toBeGreaterThan(BLOOM_THRESHOLD);
  });
  it('the "Sun blocked" marker (bundle says blocked) stays below it, even before its opacity is applied', () => {
    expect(lum(postColors().sunHidden)).toBeLessThan(BLOOM_THRESHOLD);
    const sky = postColors().sky;
    const blended = postColors().sunHidden.clone().multiplyScalar(SUN_HIDDEN_OPACITY).add(sky.clone().multiplyScalar(1 - SUN_HIDDEN_OPACITY));
    expect(lum(blended)).toBeLessThan(BLOOM_THRESHOLD);
  });
  it('the sky, the Earth disc and its blocked marker never bloom', () => {
    const c = postColors();
    for (const k of ['sky', 'earth', 'earthHidden'] as const) expect(lum(c[k])).toBeLessThan(BLOOM_THRESHOLD);
  });
});
