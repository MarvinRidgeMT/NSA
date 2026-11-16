/**
 * Camera heading for the stage heading tape (display only; never feeds a number).
 * Scene3D writes the camera's view azimuth in the site's LOCAL frame (degrees, 0 = local north, 90 = local east) every frame;
 * the tape reads it in its own requestAnimationFrame loop. A plain module variable, not React state, so a moving camera
 * causes no React renders (14islands, "Using trigonometry to animate direction" / "Developing a performant custom cursor":
 * keep pointer/camera values in refs, animate in rAF, write transforms directly).
 */
let headingDeg: number | null = null;

export function setCameraHeading(deg: number | null): void {
  headingDeg = deg;
}

export function cameraHeading(): number | null {
  return headingDeg;
}

/** The equivalent of `target` (± k·360°) closest to `current`, so an eased angle never spins the long way round. */
export function closestAngle(current: number, target: number): number {
  const d = ((((target - current) % 360) + 540) % 360) - 180;
  return current + d;
}
