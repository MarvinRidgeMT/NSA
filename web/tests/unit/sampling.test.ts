import { describe, expect, it } from 'vitest';
import { bracket, CoverageError, flagAt, lerpAzimuth, valueAt } from '../../src/bundle/sampling';

const T = [0, 3600e3, 7200e3, 10800e3];

describe('bracket', () => {
  it('finds exact samples', () => {
    expect(bracket(T, 0)).toEqual({ i0: 0, i1: 0, f: 0, exact: 0 });
    expect(bracket(T, 10800e3).exact).toBe(3);
  });
  it('brackets between samples', () => {
    const b = bracket(T, 5400e3);
    expect([b.i0, b.i1, b.exact]).toEqual([1, 2, null]);
    expect(b.f).toBeCloseTo(0.5, 12);
  });
  it('refuses times outside coverage (never extrapolates)', () => {
    expect(() => bracket(T, -1)).toThrow(CoverageError);
    expect(() => bracket(T, 10800e3 + 1)).toThrow(CoverageError);
    expect(() => bracket(T, NaN)).toThrow(CoverageError);
  });
});

describe('circular azimuth interpolation', () => {
  it('crosses 359 -> 1 through 0, not through 180', () => {
    expect(lerpAzimuth(359, 1, 0.5)).toBeCloseTo(0, 9);
    expect(lerpAzimuth(359, 1, 0.25)).toBeCloseTo(359.5, 9);
    expect(lerpAzimuth(1, 359, 0.75)).toBeCloseTo(359.5, 9);
  });
  it('is ordinary inside the circle', () => {
    expect(lerpAzimuth(100, 140, 0.25)).toBeCloseTo(110, 9);
  });
  it('handles 360 as 0', () => {
    expect(lerpAzimuth(360, 10, 0.5)).toBeCloseTo(5, 9);
  });
});

describe('values and flags at a time', () => {
  it('returns bundle values exactly at samples and interpolates between', () => {
    expect(valueAt([1.25, 3.5, 2], bracket([0, 10, 20], 10))).toBe(3.5);
    expect(valueAt([1, 3, 2], bracket([0, 10, 20], 5))).toBeCloseTo(2, 12);
  });
  it('reports transitions as null between disagreeing samples', () => {
    expect(flagAt([true, false], bracket([0, 10], 5))).toBeNull();
    expect(flagAt([true, true], bracket([0, 10], 5))).toBe(true);
  });
});
