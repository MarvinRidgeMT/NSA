import { describe, expect, it } from 'vitest';
import { skyBodyPosition } from '../../src/three/Scene3D';

const el = (p: { x: number; y: number; z: number }) => (Math.atan2(p.y, Math.hypot(p.x, p.z)) * 180) / Math.PI;
const az = (p: { x: number; y: number; z: number }) => (Math.atan2(p.x, -p.z) * 180) / Math.PI; // three (x, z, -y) <- grid (x, y, z)

describe('skyBodyPosition (display exaggeration)', () => {
  const e = (1.6 * Math.PI) / 180;
  const dir: [number, number, number] = [Math.cos(e) * Math.sin(0.7), Math.cos(e) * Math.cos(0.7), Math.sin(e)];
  it('at 1x draws the bundle direction at the requested distance', () => {
    const p = skyBodyPosition(dir, 1, 22000);
    expect(p.length()).toBeCloseTo(22000, 6);
    expect(el(p)).toBeCloseTo(1.6, 9);
  });
  it('k scales tan(elevation) exactly like the k-scaled scene group, and never the azimuth', () => {
    for (const k of [2, 3, 5, 10]) {
      const p = skyBodyPosition(dir, k, 22000);
      expect(Math.tan((el(p) * Math.PI) / 180)).toBeCloseTo(k * Math.tan(e), 9);
      expect(az(p)).toBeCloseTo((0.7 * 180) / Math.PI, 9);
    }
  });
});
