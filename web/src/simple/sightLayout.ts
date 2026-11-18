/**
 * S12 (Sid, 18 Nov 2026): the Sun and Earth sight labels over the Simple-mode scene never overlap. Pure layout, display only;
 * used by three/Scene3D.tsx (SightLabelDriver) when Simple mode passes `pick`. Expert never calls it.
 */
export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

export const SIGHT_GAP = 4;
/** Moves `a` or `b` (in place) so the two boxes keep at least `gap` px apart: the lower one down, or the upper one up when there is no room below. */
export function separateSightBoxes(a: Box, b: Box, viewH: number, gap = SIGHT_GAP): void {
  const overlapX = a.x < b.x + b.w + gap && b.x < a.x + a.w + gap;
  const overlapY = a.y < b.y + b.h + gap && b.y < a.y + a.h + gap;
  if (!overlapX || !overlapY) return;
  const [up, lo] = a.y <= b.y ? [a, b] : [b, a];
  const below = up.y + up.h + gap;
  if (below + lo.h <= viewH - gap) lo.y = below;
  else up.y = lo.y - up.h - gap;
}


/**
 * Keeps both labels above `floor` (the top of the stage's bottom controls: the light tag, the exaggeration picker, About this
 * view), then apart from each other. A label pushed above the top of the view stays at the top (0).
 */
export function placeSightBoxes(boxes: Box[], floor: number, gap = SIGHT_GAP): void {
  for (const b of boxes) if (b.y + b.h > floor - gap) b.y = Math.max(0, floor - gap - b.h);
  if (boxes.length === 2) separateSightBoxes(boxes[0], boxes[1], floor, gap);
}
