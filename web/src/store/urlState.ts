import { usePolaris } from './store';
import { CAMERA_VIEWS, useCamera, type CameraViewId } from './camera';
import { SURFACE_LAYERS, useSurface, type SurfaceLayerId } from './surface';
import { isGlobeLayerChoice, useGlobe, type GlobeLayerChoice } from './globe';

/**
 * Shareable view state in the URL (query string; the workspace stays in the hash):
 *   ?bundle=<file>&site=<siteId>&t=<UTC ISO>&sc=<scenarioId>&cam=<camera view>&layer=<surface layer>&globe=1&gl=<globe layer>#sky
 * (`globe=1` = the whole-Moon globe overlay is open; `gl` = its display layer, only written while the globe is open)
 * Only state that already exists in the stores is written; nothing here computes a value. A time outside the bundle's
 * coverage is refused by the store exactly as when typed (no extrapolation); an unknown site, scenario, camera or layer is
 * ignored and reported in `urlNote`.
 */
export interface UrlState {
  bundle?: string;
  site?: string;
  t?: string;
  sc?: string;
  cam?: CameraViewId;
  layer?: SurfaceLayerId;
  globe?: '1';
  gl?: GlobeLayerChoice;
}

const CAMS = new Set<string>(CAMERA_VIEWS.map((c) => c.id));
const LAYERS = new Set<string>(SURFACE_LAYERS.map((l) => l.id));
const ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?Z$/;

export function parseUrlState(search: string): { state: UrlState; ignored: string[] } {
  const p = new URLSearchParams(search);
  const state: UrlState = {};
  const ignored: string[] = [];
  const b = p.get('bundle');
  if (b) state.bundle = b;
  const site = p.get('site');
  if (site) state.site = site;
  const t = p.get('t');
  if (t) (ISO.test(t) ? (state.t = t) : ignored.push(`t=${t}`));
  const sc = p.get('sc');
  if (sc) state.sc = sc;
  const cam = p.get('cam');
  if (cam) (CAMS.has(cam) ? (state.cam = cam as CameraViewId) : ignored.push(`cam=${cam}`));
  const layer = p.get('layer');
  if (layer) (LAYERS.has(layer) ? (state.layer = layer as SurfaceLayerId) : ignored.push(`layer=${layer}`));
  const globe = p.get('globe');
  if (globe) (globe === '1' ? (state.globe = '1') : ignored.push(`globe=${globe}`));
  const gl = p.get('gl');
  if (gl) (isGlobeLayerChoice(gl) ? (state.gl = gl) : ignored.push(`gl=${gl}`));
  return { state, ignored };
}

export function serializeUrlState(s: UrlState): string {
  const p = new URLSearchParams();
  for (const k of ['bundle', 'site', 't', 'sc', 'cam', 'layer', 'globe', 'gl'] as const) {
    const v = s[k];
    if (v) p.set(k, v);
  }
  const q = p.toString().replace(/%3A/g, ':');
  return q ? `?${q}` : '';
}

/** Current store state as URL state (null until a bundle is loaded). */
export function currentUrlState(): UrlState | null {
  const st = usePolaris.getState();
  if (!st.loaded) return null;
  const ds = st.loaded.bundle.datasets[st.datasetIdx];
  return {
    bundle: st.loaded.name,
    site: ds?.siteId,
    t: st.utcMs !== null ? new Date(st.utcMs).toISOString().replace('.000Z', 'Z') : undefined,
    sc: st.scenarioId ?? undefined,
    cam: useCamera.getState().view,
    layer: useSurface.getState().layer,
    globe: useSurface.getState().globe ? '1' : undefined,
    gl: useSurface.getState().globe && useGlobe.getState().layer !== 'none' ? useGlobe.getState().layer : undefined,
  };
}

/** Apply a parsed URL state to the stores once the named bundle is loaded. Returns notes for anything not applied. */
export function applyUrlState(s: UrlState): string[] {
  const notes: string[] = [];
  const st = usePolaris.getState();
  const lb = st.loaded;
  if (!lb) return ['no bundle loaded'];
  if (s.site) {
    const i = lb.bundle.datasets.findIndex((d) => d.siteId === s.site);
    if (i >= 0) usePolaris.getState().setSite(i);
    else notes.push(`site "${s.site}" is not in ${lb.name}`);
  }
  if (s.sc) {
    const ds = lb.bundle.datasets[usePolaris.getState().datasetIdx];
    if (ds.derived?.scenarios.some((x) => x.id === s.sc)) usePolaris.getState().setScenario(s.sc);
    else notes.push(`scenario "${s.sc}" is not in this dataset`);
  }
  if (s.t && !usePolaris.getState().setTime(Date.parse(s.t))) notes.push(`time ${s.t} is outside this bundle's samples (not extrapolated)`);
  if (s.cam) useCamera.getState().request(s.cam);
  if (s.layer) useSurface.getState().setLayer(s.layer);
  if (s.gl) useGlobe.getState().setLayer(s.gl);
  if (s.globe === '1') useSurface.getState().setGlobe(true);
  return notes;
}

let started = false;
/**
 * Call once at app start. Applies the URL state after the first bundle load (deferred one task so the app's own default site
 * choice runs first and the URL wins), then keeps the query string in sync with the stores (replaceState, debounced, only
 * while a workspace hash is shown, so the story landing at "/" keeps its plain URL).
 */
export function startUrlSync(): void {
  if (started || typeof window === 'undefined') return;
  started = true;
  const { state: initial, ignored } = parseUrlState(location.search);
  let applied = false;
  let timer: number | undefined;
  const write = () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => {
      if (!applied || !location.hash || location.hash === '#story') return;
      const cur = currentUrlState();
      if (!cur) return;
      const q = serializeUrlState(cur);
      if (q !== location.search) history.replaceState(history.state, '', `${location.pathname}${q}${location.hash}`);
    }, 250);
  };
  const unsub = usePolaris.subscribe((s, prev) => {
    if (!applied && s.loaded && !prev.loaded) {
      window.setTimeout(() => {
        const notes = applyUrlState(initial).concat(ignored.map((x) => `ignored ${x}`));
        if (notes.length) usePolaris.setState({ timeNote: `Link: ${notes.join('; ')}` });
        applied = true;
        write();
      }, 0);
      return;
    }
    if (s.loaded !== prev.loaded || s.datasetIdx !== prev.datasetIdx || s.utcMs !== prev.utcMs || s.scenarioId !== prev.scenarioId) write();
  });
  useCamera.subscribe(write);
  useSurface.subscribe((s, p) => {
    if (s.layer !== p.layer || s.globe !== p.globe) write();
  });
  useGlobe.subscribe((s, p) => {
    if (s.layer !== p.layer) write();
  });
  window.addEventListener('hashchange', write);
  void unsub;
}
