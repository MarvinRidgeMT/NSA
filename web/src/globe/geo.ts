/**
 * Display geometry for the whole-Moon globe (v2 T2). Nothing here is science: these functions place pixels and markers,
 * and find the nearest precomputed row. The frames are the ones the data files document:
 *  - globe axes: +Y north, +Z lon 0, +X lon 90 E (blender/v2/globe.py web GLB, GlobalMoon.angularPoint), east-positive lon;
 *  - equirectangular PNGs: lon -180..180 left->right, lat 90..-90 top->bottom (tools/globe/*);
 *  - polar PNGs: polar stereographic on the 1,737,400 m sphere, lat_ts = pole (science.terrain.stack.PROJ4),
 *    +x toward 90 E; south: +y toward 0 E, north: -y toward 0 E; row 0 = +y edge, column 0 = -x edge.
 */
export const MOON_R_M = 1_737_400;
const D = Math.PI / 180;

export type Pole = 'sp' | 'np';

/** Polar stereographic forward (sphere, true scale at the pole). Matches pyproj for the PROJ4 strings in science.terrain.stack. */
export function polarStereo(latDeg: number, lonDeg: number, pole: Pole): { x: number; y: number } {
  const phi = Math.abs(latDeg) * D;
  const rho = 2 * MOON_R_M * Math.tan(Math.PI / 4 - phi / 2);
  const lam = lonDeg * D;
  return pole === 'sp' ? { x: rho * Math.sin(lam), y: rho * Math.cos(lam) } : { x: rho * Math.sin(lam), y: -rho * Math.cos(lam) };
}

/** Pixel (column, row from the top, fractional, 0..size) of a point in a polar PNG of half-extent `halfM`. */
export function polarPixel(latDeg: number, lonDeg: number, pole: Pole, halfM: number, width: number, height: number) {
  const { x, y } = polarStereo(latDeg, lonDeg, pole);
  return { col: ((x + halfM) / (2 * halfM)) * width, row: ((halfM - y) / (2 * halfM)) * height };
}

/** Pixel of a point in an equirectangular PNG. */
export function eqcPixel(latDeg: number, lonDeg: number, width: number, height: number) {
  const lon = ((((lonDeg + 180) % 360) + 360) % 360) - 180;
  return { col: ((lon + 180) / 360) * width, row: ((90 - latDeg) / 180) * height };
}

/** Inverse of GlobalMoon.angularPoint: a direction in globe axes -> planetocentric lat, east lon (-180..180]. */
export function latLonFromDir(x: number, y: number, z: number): { lat: number; lon: number } {
  const r = Math.hypot(x, y, z);
  const lat = Math.asin(Math.max(-1, Math.min(1, y / r))) / D;
  let lon = Math.atan2(x, z) / D;
  if (lon <= -180) lon += 360;
  return { lat, lon };
}

/** Great-circle distance on the 1,737.4 km sphere, km (haversine). Used only to pick and report the nearest precomputed row. */
export function greatCircleKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const p1 = lat1 * D;
  const p2 = lat2 * D;
  const dp = p2 - p1;
  const dl = (lon2 - lon1) * D;
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return (2 * MOON_R_M * Math.asin(Math.min(1, Math.sqrt(a)))) / 1000;
}

export function fmtLat(lat: number, digits = 2): string {
  return `${Math.abs(lat).toFixed(digits)}° ${lat < 0 ? 'S' : 'N'}`;
}
export function fmtLon(lon: number, digits = 2): string {
  return `${Math.abs(lon).toFixed(digits)}° ${lon < 0 ? 'W' : 'E'}`;
}

/** Ray (origin o, unit direction d) ∩ sphere at the origin of radius r: nearest positive t, or null. */
export function raySphere(o: [number, number, number], d: [number, number, number], r: number): number | null {
  const b = o[0] * d[0] + o[1] * d[1] + o[2] * d[2];
  const c = o[0] ** 2 + o[1] ** 2 + o[2] ** 2 - r * r;
  const disc = b * b - c;
  if (disc < 0) return null;
  const s = Math.sqrt(disc);
  const t0 = -b - s;
  const t1 = -b + s;
  if (t0 > 0) return t0;
  if (t1 > 0) return t1;
  return null;
}
