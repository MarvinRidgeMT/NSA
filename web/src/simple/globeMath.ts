/**
 * South-pole globe (S4): the arithmetic, with no three.js and no DOM so it can be unit-tested.
 *
 * MODEL FRAME of web/public/globe/NASA_SVS_moon_small.glb (three.js world axes, after centring):
 *   +Y = lunar north; longitude 0° (the mean sub-Earth meridian) points along −Z; 90° E points along −X.
 * Found by fitting, not assumed: the model's image was compared with NASA's CGI Moon Kit LROC colour map (SVS 4720,
 * lroc_color_poles_1k.jpg, equirectangular, 0° at the centre) at the model's 46 464 vertices for all 48 axis assignments.
 * This one correlates 0.955; the next best 0.448; turning it half a degree about any axis drops it to 0.92
 * (web/scripts/globe_orientation.mjs repeats the fit). The bundle agrees: the Sun azimuths of Site01 and Site04 give the
 * same sub-solar longitude to 0.01°, and the Earth lies at longitude ≈ 0°, where it must.
 * (three/GlobalMoon.tsx, Expert's older context globe, assumes +Z for longitude 0° and is left as submitted.)
 *
 * The 8k model (NASA_SVS_Moon_NASA_LRO_8k_Topo_Small.glb, a latitude-longitude sphere of 1 015 808 triangles with relief in
 * the mesh and an 8192 x 4096 equirectangular image) has its own axes: +Y = north, longitude 0° along +X, 90° E along −Z.
 * Read from its own texture coordinates (longitude 0° at the image centre, north up; mean misfit 0.17°, largest 1.55°), and
 * the image layout checked against the compact model above: sampled at the compact model's vertices through both frames the
 * two images correlate 0.968, and 0.92 after half a degree of shift either way (web/scripts/globe_orientation_8k.mjs).
 * A quarter turn about +Y (MODEL_YAW_RAD) brings it into the model frame used here, so pins and light need no second path.
 */
export type Vec3 = [number, number, number];
const RAD = Math.PI / 180;

/** Unit vector of a planetocentric latitude / east longitude, in the model frame. */
export function moonDir(latDeg: number, lonEastDeg: number): Vec3 {
  const lat = latDeg * RAD;
  const lon = lonEastDeg * RAD;
  const c = Math.cos(lat);
  return [-c * Math.sin(lon), Math.sin(lat), -c * Math.cos(lon)];
}

/**
 * Direction of a body seen from a site at local azimuth / elevation (bundle convention: azimuth 0° = north, 90° = east, in the
 * site's local east-north-up frame), as a unit vector in the model frame. The Sun and the Earth are far enough away that the
 * direction from the site is the direction from the Moon's centre for drawing a globe (parallax under 0.3° for the Earth).
 */
export function skyDirFromSite(latDeg: number, lonEastDeg: number, azDeg: number, elDeg: number): Vec3 {
  const lat = latDeg * RAD;
  const lon = lonEastDeg * RAD;
  const az = azDeg * RAD;
  const el = elDeg * RAD;
  // Moon-fixed axes: x = lon 0°, y = 90° E, z = north
  const E: Vec3 = [-Math.sin(lon), Math.cos(lon), 0];
  const N: Vec3 = [-Math.sin(lat) * Math.cos(lon), -Math.sin(lat) * Math.sin(lon), Math.cos(lat)];
  const U: Vec3 = [Math.cos(lat) * Math.cos(lon), Math.cos(lat) * Math.sin(lon), Math.sin(lat)];
  const e = Math.cos(el) * Math.sin(az);
  const n = Math.cos(el) * Math.cos(az);
  const u = Math.sin(el);
  const m: Vec3 = [e * E[0] + n * N[0] + u * U[0], e * E[1] + n * N[1] + u * U[1], e * E[2] + n * N[2] + u * U[2]];
  return [-m[1], m[2], -m[0]];
}

/** One row of the certainty sidecar's curve. */
export interface CurveRow {
  mast_m: number;
  metric: string;
  min: number;
  max: number;
  nominal: number;
  pass: string;
  n_clones: number;
}
export interface SidecarSite {
  sampled_masts_m: number[];
  certainty_curve: unknown;
  all_maps_100pct_sun_mast_m: number | null;
}

export interface PinReading {
  /** mast height the reading is for (a sampled height of this site) */
  mastM: number;
  /** the sidecar's Sun-in-sight row at that height; undefined when the site was not sampled there */
  sun: CurveRow | undefined;
  /** Sun-in-sight max − min across the terrain variants, percentage points; null when there is no row */
  spreadPts: number | null;
  all100: boolean;
}

/**
 * The sidecar reading that drives one pin. Same rule as the Certainty Height instrument (components/MastInstrument.tsx):
 * the picked mast, else the mast of the bundle's own series when the site was sampled there, else the lowest sampled mast.
 * Nothing is interpolated: a height this site was not sampled at has no row, no spread and no shimmer.
 */
export function pinReading(site: SidecarSite | undefined, pick: number | null, seriesMastM: number | null): PinReading | null {
  if (!site) return null;
  const masts = site.sampled_masts_m;
  const mastM = pick ?? (seriesMastM !== null && masts.includes(seriesMastM) ? seriesMastM : masts[0]);
  const sun = (site.certainty_curve as CurveRow[]).find((r) => r.mast_m === mastM && r.metric === 'sun_centre_pct');
  return { mastM, sun, spreadPts: sun ? sun.max - sun.min : null, all100: sun ? sun.min >= 100 : false };
}

export interface Pt {
  x: number;
  y: number;
}

/**
 * Where to draw the pins. The ROI sites are a few kilometres apart, a few pixels on a whole-Moon view, so each pin stands
 * `ring` pixels out from the middle of the group, on the side its site really lies, and a hairline joins it to the site's true
 * position (the anchor). Pins closer together than `minSepRad` around the ring are eased apart. Deterministic and stateless.
 */
export function layoutPins(anchors: Pt[], ring: number, minSepRad: number): { pins: Pt[]; centre: Pt; angles: number[] } {
  const n = anchors.length;
  if (!n) return { pins: [], centre: { x: 0, y: 0 }, angles: [] };
  const centre = { x: anchors.reduce((s, a) => s + a.x, 0) / n, y: anchors.reduce((s, a) => s + a.y, 0) / n };
  const sep = Math.min(minSepRad, (2 * Math.PI) / n);
  const angles = anchors.map((a, i) => {
    const dx = a.x - centre.x;
    const dy = a.y - centre.y;
    // sites on top of each other on screen have no bearing: spread them evenly instead
    return Math.hypot(dx, dy) < 0.05 ? (2 * Math.PI * i) / n - Math.PI / 2 : Math.atan2(dy, dx);
  });
  const order = angles.map((_, i) => i).sort((a, b) => angles[a] - angles[b] || a - b);
  for (let pass = 0; pass < 24 && n > 1; pass++) {
    let moved = false;
    for (let k = 0; k < n; k++) {
      const a = order[k];
      const b = order[(k + 1) % n];
      if (a === b) continue;
      const g = (((angles[b] - angles[a]) % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
      if (g < sep - 1e-6) {
        const push = (sep - g) / 2;
        angles[a] -= push;
        angles[b] += push;
        moved = true;
      }
    }
    if (!moved) break;
  }
  return { pins: angles.map((a) => ({ x: centre.x + ring * Math.cos(a), y: centre.y + ring * Math.sin(a) })), centre, angles };
}

/** Camera distance (in Moon radii) at which the whole disc spans `fill` of the shorter side of a w × h view. */
export function distanceForDisc(fovDeg: number, w: number, h: number, fill: number): number {
  const t = h / (fill * Math.min(w, h) * Math.tan((fovDeg * RAD) / 2));
  return Math.sqrt(t * t + 1);
}

/** Flight ease: the camera curve used elsewhere (store/camera.ts easeCamera), an in-out cubic. */
export const FLIGHT_MS = 1200;
/** Drift of the view around the pole, degrees per second (off under reduced motion). */
export const DRIFT_DEG_PER_S = 0.5;

/**
 * Moon models, best first. Only the compact one is in the repository; the 8k model is 81.5 MB, over the size kept in git, so a
 * clean clone draws the compact model and a machine that has the 8k file draws that.
 */
export const GLOBE_8K = 'NASA_SVS_Moon_NASA_LRO_8k_Topo_Small.glb';
export const GLOBE_FULL = 'NASA_SVS_moon_small.glb';
export const GLOBE_LITE = 'moon_lite.glb';
/** Turn about +Y that brings each model's own axes into the model frame above (see the header). */
export const MODEL_YAW_RAD: Record<string, number> = { [GLOBE_8K]: Math.PI / 2 };
/** Models whose mesh carries relief (their centre is the mesh origin; their normals go through reliefNormals). */
export const MODEL_HAS_RELIEF: Record<string, boolean> = { [GLOBE_8K]: true };
/**
 * Display choices for a model with relief (the 8k model). Its mesh is flat-shaded per quad and its relief stands about three
 * times taller than the real Moon's (radius spread of the mesh ±1.78 % of its mean, globe_orientation_8k.mjs), so its own
 * normals draw a blocky, over-deep day-night line. The normals are therefore smoothed across each shared corner and leaned
 * only RELIEF_SHADE of the way from the smooth-sphere normal. Toward each pole the latitude-longitude mesh pinches into
 * slivers that shade as a starburst, so the lean fades out between RELIEF_CAP_FROM_DEG and RELIEF_CAP_TO_DEG of latitude and
 * the cap is shaded as a smooth sphere. None of this is a shadow calculation.
 */
export const RELIEF_SHADE = 1 / 3;
export const RELIEF_CAP_FROM_DEG = 72;
export const RELIEF_CAP_TO_DEG = 84;

/**
 * Rewrites `nrm` in place for a mesh with relief centred on its origin with +Y north: each vertex gets the average of the
 * normals of every vertex at its position (the flat-shaded quads sharing that corner), leaned `shade` of the way from the
 * radial direction, with the lean fading to nothing between `capFromDeg` and `capToDeg` of latitude (both hemispheres).
 */
export function reliefNormals(pos: ArrayLike<number>, nrm: { [i: number]: number; length: number }, shade: number, capFromDeg: number, capToDeg: number): void {
  const n = Math.floor(pos.length / 3);
  const ids = new Uint32Array(n);
  const seen = new Map<number, number>();
  let m = 0;
  // positions are compared on a grid far finer than the mesh spacing; the key stays an exact integer (< 2^53)
  const Q = 4000;
  const W = 2 * Q * 4 + 1;
  const q = (v: number) => Math.round((v + 4) * Q);
  for (let i = 0; i < n; i++) {
    const key = (q(pos[3 * i]) * W + q(pos[3 * i + 1])) * W + q(pos[3 * i + 2]);
    let j = seen.get(key);
    if (j === undefined) {
      j = m++;
      seen.set(key, j);
    }
    ids[i] = j;
  }
  const acc = new Float32Array(m * 3);
  for (let i = 0; i < n; i++) {
    const j = ids[i] * 3;
    acc[j] += nrm[3 * i];
    acc[j + 1] += nrm[3 * i + 1];
    acc[j + 2] += nrm[3 * i + 2];
  }
  const sa = Math.sin(capFromDeg * RAD);
  const sb = Math.sin(capToDeg * RAD);
  for (let i = 0; i < n; i++) {
    const x = pos[3 * i];
    const y = pos[3 * i + 1];
    const z = pos[3 * i + 2];
    const r = Math.hypot(x, y, z) || 1;
    const rx = x / r;
    const ry = y / r;
    const rz = z / r;
    const j = ids[i] * 3;
    const l = Math.hypot(acc[j], acc[j + 1], acc[j + 2]) || 1;
    let t = Math.min(1, Math.max(0, (sb - Math.abs(ry)) / (sb - sa)));
    t = t * t * (3 - 2 * t);
    const k = shade * t;
    const a = rx + k * (acc[j] / l - rx);
    const b = ry + k * (acc[j + 1] / l - ry);
    const c = rz + k * (acc[j + 2] / l - rz);
    const L = Math.hypot(a, b, c) || 1;
    nrm[3 * i] = a / L;
    nrm[3 * i + 1] = b / L;
    nrm[3 * i + 2] = c / L;
  }
}

/**
 * Which model to draw. Phones and software rendering (`lite`) never get the 8k model while a lighter one is present: the
 * reduced image if it has been built, else the compact model. Everything else gets the 8k model when it is present.
 * `prefer: 'compact'` (the link's ?globe=compact, for measurements) asks for the compact model on any device.
 */
export function globeAsset(present: readonly string[], lite: boolean, prefer?: string | null): string {
  const has = (f: string) => present.includes(f);
  if (lite) return has(GLOBE_LITE) ? GLOBE_LITE : has(GLOBE_FULL) || !has(GLOBE_8K) ? GLOBE_FULL : GLOBE_8K;
  if (prefer === 'compact' && has(GLOBE_FULL)) return GLOBE_FULL;
  return has(GLOBE_8K) ? GLOBE_8K : GLOBE_FULL;
}

/**
 * What to draw first and what to bring in after it. The 8k model is 81.5 MB, too heavy to wait for, so a device that gets it
 * (`best`) opens on the compact model and swaps once the 8k one has loaded; `then` is null when there is nothing better to
 * bring in, and the 8k model is drawn first only when it is the only model present.
 */
export function globePlan(present: readonly string[], lite: boolean, prefer?: string | null): { first: string; then: string | null } {
  const best = globeAsset(present, lite, prefer);
  if (best === GLOBE_8K && present.includes(GLOBE_FULL)) return { first: GLOBE_FULL, then: GLOBE_8K };
  return { first: best, then: null };
}
