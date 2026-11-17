/**
 * Which whole-Moon globe GLB the viewer loads (v2 T2, prompt §5.1: web 3D content is exported from Blender).
 * web/scripts/sync-globe.mjs writes globe/globe_manifest.json from each GLB's own glTF JSON. The Blender globe
 * (blender/v2/globe.py, Khronos exporter, Draco) is primary; the NASA SVS 14959 model is a fallback used only when the
 * Blender globe is absent from this build or fails to load.
 */
export const GLOBE_MANIFEST_URL = 'globe/globe_manifest.json';
export const SVS_GLOBE_URL = 'globe/NASA_SVS_moon_small.glb';
export const BLENDER_GLOBE_COMMAND = 'POLARIS_PYTHON=$POLARIS_PYTHON blender -b --python-exit-code 1 -P blender/v2/globe.py -- --no-render';

export interface GlobeEntry {
  url: string;
  role: 'primary' | 'fallback';
  kind: 'blender' | 'svs';
  sha256: string;
  bytes: number;
  generator: string | null;
  draco: boolean;
  builder: string | null;
  tag: string | null;
  blender: string | null;
  units: string | null;
  axes: string | null;
  radiusKm: number | null;
  labels: Record<string, string> | null;
  heightsSource: string | null;
  textureCredit: string | null;
}
export interface GlobeManifest {
  schema: 'polaris-globe-manifest-v1';
  globes: GlobeEntry[];
}

export const SVS_ENTRY: GlobeEntry = {
  url: SVS_GLOBE_URL,
  role: 'fallback',
  kind: 'svs',
  sha256: '',
  bytes: 0,
  generator: null,
  draco: false,
  builder: null,
  tag: null,
  blender: null,
  units: null,
  axes: null,
  radiusKm: null,
  labels: null,
  heightsSource: null,
  textureCredit: null,
};

/** Order to try: the Blender globe (only if it names the POLARIS builder), then the SVS fallback. */
export function globeOrder(m: GlobeManifest | null): GlobeEntry[] {
  const g = m?.globes ?? [];
  const blender = g.find((x) => x.kind === 'blender' && x.builder === 'blender/v2/globe.py');
  const svs = g.find((x) => x.kind === 'svs') ?? SVS_ENTRY;
  return blender ? [blender, svs] : [svs];
}

export async function loadGlobeManifest(fetcher: typeof fetch = fetch): Promise<GlobeManifest | null> {
  try {
    const r = await fetcher(GLOBE_MANIFEST_URL);
    if (!r.ok || !(r.headers.get('content-type') ?? '').includes('json')) return null;
    const j = (await r.json()) as GlobeManifest;
    return j?.schema === 'polaris-globe-manifest-v1' && Array.isArray(j.globes) ? j : null;
  } catch {
    return null;
  }
}
