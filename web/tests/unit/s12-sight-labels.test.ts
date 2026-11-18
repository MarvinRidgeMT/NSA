import { describe, expect, it } from 'vitest';
import { placeSightBoxes, separateSightBoxes, SIGHT_GAP } from '../../src/simple/sightLayout';

/** Sid, 18 Nov 2026: on the phone the SUN · CLEAR and EARTH · BLOCKED labels were drawn over each other. */
const touch = (a: { x: number; y: number; w: number; h: number }, b: typeof a) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

describe('Sun and Earth sight labels are kept apart', () => {
  it('leaves two separate labels where they are', () => {
    const a = { x: 0, y: 0, w: 100, h: 40 };
    const b = { x: 300, y: 0, w: 100, h: 40 };
    separateSightBoxes(a, b, 800);
    expect([a.y, b.y]).toEqual([0, 0]);
  });
  it('moves the lower of two overlapping labels down, below the upper one with a gap (the 390 × 844 case)', () => {
    // as measured on tmp/s12/card-ridge-R1-390x844.png: Sun flipped left of its anchor, Earth to the right, almost level
    const sun = { x: 180, y: 556, w: 130, h: 44 };
    const earth = { x: 247, y: 562, w: 150, h: 44 };
    separateSightBoxes(sun, earth, 844);
    expect(touch(sun, earth)).toBe(false);
    expect(sun.y).toBe(556);
    expect(earth.y).toBe(556 + 44 + SIGHT_GAP);
  });
  it('moves the upper one up instead when there is no room below', () => {
    const a = { x: 0, y: 760, w: 100, h: 40 };
    const b = { x: 20, y: 780, w: 100, h: 40 };
    separateSightBoxes(a, b, 844);
    expect(touch(a, b)).toBe(false);
    expect(b.y).toBe(780);
    expect(a.y).toBe(780 - 40 - SIGHT_GAP);
  });
  it('keeps both labels above the bottom controls, and apart (the 390 × 844 Sun card case)', () => {
    // tmp/s12/card-sun-390x844.png: the Earth label had dropped onto the light tag at the foot of the stage
    const sun = { x: 190, y: 420, w: 120, h: 36 };
    const earth = { x: 105, y: 500, w: 120, h: 36 };
    placeSightBoxes([sun, earth], 520);
    expect(earth.y + earth.h).toBeLessThanOrEqual(520 - SIGHT_GAP);
    expect(sun.y + sun.h).toBeLessThanOrEqual(520 - SIGHT_GAP);
    expect(touch(sun, earth)).toBe(false);
  });
  it('works whichever label is given first', () => {
    const a = { x: 0, y: 100, w: 100, h: 40 };
    const b = { x: 10, y: 90, w: 100, h: 40 };
    separateSightBoxes(a, b, 844);
    expect(touch(a, b)).toBe(false);
    expect(b.y).toBe(90);
  });
});
