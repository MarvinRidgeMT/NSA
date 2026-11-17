import { describe, expect, it } from 'vitest';
import { fxaaPatched } from '../../src/simple/SimplePost';

describe('Simple post chain', () => {
  it("three's FXAA shader still has the two lines the last pass replaces (sub-pixel blending, output)", () => {
    // If a three.js update changes them, the chain falls back to stock FXAA with no grain: this test makes that visible.
    expect(fxaaPatched).toBe(true);
  });
});
