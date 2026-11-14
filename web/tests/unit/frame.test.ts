import { describe, expect, it } from 'vitest';
import { basisFromLongitude, gridDirection } from '../../src/bundle/frame';

describe('grid <-> local frame (display only)', () => {
  it('local north points away from the pole (radial) in the polar stereographic grid', () => {
    // Site01 projected position is (-10999, -11999): radial unit vector
    const L = -137.49;
    const b = basisFromLongitude(L);
    const r = Math.hypot(-10999.14, -11999.26);
    expect(b.north[0]).toBeCloseTo(-10999.14 / r, 3);
    expect(b.north[1]).toBeCloseTo(-11999.26 / r, 3);
  });
  it('az 90 is local east and az 270 is local west at L = -137.49', () => {
    const b = basisFromLongitude(-137.49);
    const e = gridDirection(b, 90, 0);
    const w = gridDirection(b, 270, 0);
    expect(e[0]).toBeCloseTo(b.east[0], 12);
    expect(e[1]).toBeCloseTo(b.east[1], 12);
    expect(w[0]).toBeCloseTo(-b.east[0], 12);
    // and NOT the naive grid direction (sin az, cos az) = (1, 0)
    expect(Math.abs(e[0] - 1)).toBeGreaterThan(0.5);
  });
  it('east is north rotated 90 degrees clockwise (seen from above)', () => {
    const b = basisFromLongitude(42);
    expect(b.east[0] * b.north[0] + b.east[1] * b.north[1]).toBeCloseTo(0, 12);
    expect(b.north[0] * b.east[1] - b.north[1] * b.east[0]).toBeCloseTo(-1, 12);
  });
  it('elevation goes into z', () => {
    const d = gridDirection(basisFromLongitude(0), 0, 30);
    expect(d[2]).toBeCloseTo(0.5, 12);
    expect(Math.hypot(...d)).toBeCloseTo(1, 12);
  });
});
