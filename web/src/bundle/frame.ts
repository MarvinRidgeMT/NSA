/**
 * Display-only frame handling. Bundle DEM crops are on the south-polar stereographic
 * GRID (x = grid east, y = grid north), but JPL azimuths are LOCAL (clockwise from local
 * north). At longitude L in a south-polar stereographic grid:
 *   local north in grid = ( sin L,  cos L )
 *   local east  in grid = ( cos L, -sin L )
 * so a local azimuth `az` points along  sin(az)·E + cos(az)·N  in the grid.
 *
 * Used only to DRAW rays and cardinal labels over the DEM. If the bundle declares
 * `derived.frame.localNorthInGrid`, that wins over the longitude-derived basis.
 */
import type { Dataset } from './types';

export interface Basis {
  north: [number, number];
  east: [number, number];
  source: 'bundle' | 'derived-from-longitude';
}

export function basisFromLongitude(lonEastDeg: number): Basis {
  const L = (lonEastDeg * Math.PI) / 180;
  return { north: [Math.sin(L), Math.cos(L)], east: [Math.cos(L), -Math.sin(L)], source: 'derived-from-longitude' };
}

export function basisFor(d: Dataset): Basis {
  const f = d.derived?.frame;
  if (f?.localNorthInGrid && f?.localEastInGrid) return { north: f.localNorthInGrid, east: f.localEastInGrid, source: 'bundle' };
  return basisFromLongitude(d.site.longitudeEastDeg);
}

/** Unit 3-vector in grid axes (x grid-east, y grid-north, z up) for local az/el in degrees. */
export function gridDirection(b: Basis, azDeg: number, elDeg: number): [number, number, number] {
  const a = (azDeg * Math.PI) / 180;
  const e = (elDeg * Math.PI) / 180;
  const h = Math.cos(e);
  const gx = Math.sin(a) * b.east[0] + Math.cos(a) * b.north[0];
  const gy = Math.sin(a) * b.east[1] + Math.cos(a) * b.north[1];
  return [gx * h, gy * h, Math.sin(e)];
}
