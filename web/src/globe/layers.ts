/**
 * v2 global analytics layers for the globe (T2). DISPLAY ONLY: the manifest describes PNGs built by tools/globe/* and staged
 * by web/scripts/sync_v2_layers.py (git-ignored). The viewer never reads a pixel value back into any number it shows.
 */
export const LAYER_MANIFEST_URL = 'layers/v2/manifest.json';
export const SYNC_COMMAND = '$POLARIS_PYTHON web/scripts/sync_v2_layers.py [--from <dir with tools/globe outputs>]';

export const GLOBE_LAYER_IDS = ['coverage-res', 'coverage-src', 'slope', 'roughness', 'earth-vis', 'sun-vis'] as const;
export type GlobeLayerId = (typeof GLOBE_LAYER_IDS)[number];

export interface LayerFile {
  path: string;
  sha256: string;
  bytes: number;
  width: number;
  height: number;
  projection: string; // 'equirectangular: …' | 'polar-stereographic-sp' | 'polar-stereographic-np'
  role?: 'global';
  pole?: 'sp' | 'np';
  halfExtentM?: number;
}
export interface LegendClass {
  label: string;
  rgb: number[];
  sourceId?: number;
}
export type Legend =
  | { kind: 'classes'; classes: LegendClass[] }
  | { kind: 'ramp'; unit: string; min: number; max: number; samples: { value: number; rgb: number[] }[]; note?: string };
export interface GlobeLayer {
  id: GlobeLayerId;
  title: string;
  label: string;
  what: string;
  legend: Legend;
  files: LayerFile[];
  built: boolean;
  cells?: string;
  cellRule?: string;
  stats?: Record<string, unknown> & { source?: string; created_utc?: string };
  source: string;
  command: string;
}
export interface LayerManifest {
  schema: 'polaris-globe-layers-v1';
  label: string;
  created_utc: string;
  script: string;
  layers: GlobeLayer[];
}

/** Validates the manifest shape; drops unknown layers and files with an unknown projection. Throws on a wrong schema. */
export function validateLayerManifest(j: unknown): LayerManifest {
  const m = j as LayerManifest;
  if (!m || m.schema !== 'polaris-globe-layers-v1' || !Array.isArray(m.layers)) throw new Error('not a polaris-globe-layers-v1 manifest');
  const ids = new Set<string>(GLOBE_LAYER_IDS);
  const layers = m.layers
    .filter((l) => ids.has(l.id))
    .map((l) => {
      const files = (l.files ?? []).filter(
        (f) =>
          f &&
          typeof f.path === 'string' &&
          f.width > 0 &&
          f.height > 0 &&
          (f.projection.startsWith('equirectangular') || ((f.projection === 'polar-stereographic-sp' || f.projection === 'polar-stereographic-np') && (f.halfExtentM ?? 0) > 0)),
      );
      return { ...l, files, built: files.length > 0 };
    });
  return { ...m, layers };
}

export function layerTextures(l: GlobeLayer): { eqc?: LayerFile; sp?: LayerFile; np?: LayerFile } {
  const out: { eqc?: LayerFile; sp?: LayerFile; np?: LayerFile } = {};
  for (const f of l.files) {
    if (f.projection.startsWith('equirectangular')) out.eqc = f;
    else if (f.projection === 'polar-stereographic-sp') out.sp = f;
    else if (f.projection === 'polar-stereographic-np') out.np = f;
  }
  return out;
}

export async function loadLayerManifest(fetcher: typeof fetch = fetch): Promise<LayerManifest | null> {
  const r = await fetcher(LAYER_MANIFEST_URL);
  if (!r.ok) return null;
  const ct = r.headers.get('content-type') ?? '';
  if (!ct.includes('json')) return null; // SPA fallback (index.html) means the file is not there
  return validateLayerManifest(await r.json());
}

export const rgbCss = (c: number[]) => `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
