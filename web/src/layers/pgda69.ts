/**
 * NASA PGDA product 69 layer (average Sun / Earth visibility, 85-90 S), prepared by
 * tools/pgda69/build_layer.py. This is NASA reference data that the viewer DISPLAYS.
 * The only arithmetic here is decoding the 8-bit encoding and polar-stereographic
 * grid <-> lat/lon for labels and graticule lines.
 */
export const R_MOON = 1737400;

export interface Pgda69Image {
  width: number;
  height: number;
  pixelM: number;
  x0: number; // grid x of the image's left edge (m)
  y0: number; // grid y of the image's top edge (m)
  resample: string;
  sun: { file: string };
  earth: { file: string };
}

export interface ZoneStats {
  n60mPixels: number;
  mean?: number;
  min?: number;
  max?: number;
}

export interface Roi {
  site: string;
  siteName: string;
  roi: number;
  id: string;
  centroidXY: [number, number];
  lat: number;
  lonE: number;
  areaM2: number;
  ring: [number, number][];
  sun: ZoneStats;
  earth: ZoneStats;
  sunAtCentroid: number | null;
  earthAtCentroid: number | null;
}

export interface Pgda69Meta {
  schema: 'POLARIS-X-layer-pgda69-v1';
  kind: 'NASA_REFERENCE_PRODUCT';
  title: string;
  product: string;
  roiProduct: string;
  citation: string;
  meaning: { sun: string; earth: string };
  basis: string;
  caveats: string[];
  crs: string;
  encoding: { scale: number; nodata: number; note: string };
  sources: { file: string; url: string; sha256: string }[];
  images: { overview: Pgda69Image; sites: Record<string, Pgda69Image> };
  rois: Roi[];
}

export type LayerKey = 'sun' | 'earth';

export const BASE = 'layers/pgda69/';

export async function loadMeta(): Promise<Pgda69Meta> {
  const r = await fetch(`${BASE}pgda69.json`);
  if (!r.ok) throw new Error(`layers/pgda69/pgda69.json: HTTP ${r.status}. Run tools/pgda69/build_layer.py.`);
  const m = (await r.json()) as Pgda69Meta;
  if (m.schema !== 'POLARIS-X-layer-pgda69-v1') throw new Error(`unexpected layer schema ${String(m.schema)}`);
  return m;
}

/** Decode an 8-bit grey PNG to its raw values (no colour management). */
export async function loadGrey(file: string): Promise<{ w: number; h: number; v: Uint8ClampedArray }> {
  const blob = await fetch(BASE + file).then((r) => {
    if (!r.ok) throw new Error(`${file}: HTTP ${r.status}`);
    return r.blob();
  });
  const bmp = await createImageBitmap(blob, { colorSpaceConversion: 'none', premultiplyAlpha: 'none' });
  const c = document.createElement('canvas');
  c.width = bmp.width;
  c.height = bmp.height;
  const ctx = c.getContext('2d', { willReadFrequently: true })!;
  ctx.drawImage(bmp, 0, 0);
  const rgba = ctx.getImageData(0, 0, bmp.width, bmp.height).data;
  const v = new Uint8ClampedArray(bmp.width * bmp.height);
  for (let i = 0; i < v.length; i++) v[i] = rgba[i * 4];
  return { w: bmp.width, h: bmp.height, v };
}

/** Encoded grey value -> percent (null = no data). */
export function toPercent(g: number, enc: Pgda69Meta['encoding']): number | null {
  return g === enc.nodata ? null : g * enc.scale * 100;
}

/** South polar stereographic (sphere, true scale at the pole), same as the GeoTIFF CRS. */
export function latLonToXY(lat: number, lonE: number): [number, number] {
  const rho = 2 * R_MOON * Math.tan(((90 + lat) * Math.PI) / 360);
  const l = (lonE * Math.PI) / 180;
  return [rho * Math.sin(l), rho * Math.cos(l)];
}

export function xyToLatLon(x: number, y: number): [number, number] {
  const rho = Math.hypot(x, y);
  const lat = -90 + (2 * Math.atan(rho / (2 * R_MOON)) * 180) / Math.PI;
  const lon = (Math.atan2(x, y) * 180) / Math.PI;
  return [lat, lon];
}

/** Sequential single-hue ramps, dark (0 %) -> bright (100 %), tuned for the dark UI. */
const RAMPS: Record<LayerKey, [number, number, number][]> = {
  sun: [
    [10, 12, 18],
    [62, 42, 16],
    [140, 92, 26],
    [214, 150, 48],
    [250, 214, 140],
  ],
  earth: [
    [10, 12, 18],
    [16, 48, 72],
    [30, 98, 140],
    [70, 160, 214],
    [176, 226, 250],
  ],
};

export function lut(key: LayerKey): Uint8ClampedArray {
  const stops = RAMPS[key];
  const out = new Uint8ClampedArray(256 * 4);
  for (let g = 0; g < 256; g++) {
    if (g === 255) {
      out.set([40, 48, 60, 255], g * 4); // no data: slate (also hatched in CSS legend)
      continue;
    }
    const t = Math.min(g / 250, 1) * (stops.length - 1);
    const i = Math.min(Math.floor(t), stops.length - 2);
    const f = t - i;
    const a = stops[i];
    const b = stops[i + 1];
    out.set([a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, 255], g * 4);
  }
  return out;
}

export function rampCss(key: LayerKey): string {
  const s = RAMPS[key];
  return `linear-gradient(90deg, ${s.map((c, i) => `rgb(${c.join(',')}) ${(i / (s.length - 1)) * 100}%`).join(', ')})`;
}
