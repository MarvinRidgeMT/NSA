import { useEffect, useRef, useState } from 'react';

/**
 * OPTIONAL global context: Cesium Moon 3D Tiles (ion asset 2684829) on Ellipsoid.MOON.
 * - The token is typed by the user at runtime and kept in memory only (never stored, never in the repo).
 * - CesiumJS is loaded from its CDN on demand; any failure (offline, bad token, no WebGL) is shown and
 *   the rest of the app keeps working. Cesium tiles are context imagery, never a numerical elevation source.
 */
const CESIUM_VERSION = '1.123';
const CDN = `https://cesium.com/downloads/cesiumjs/releases/${CESIUM_VERSION}/Build/Cesium`;
const ASSET_ID = 2684829;

type CesiumNS = {
  Ion: { defaultAccessToken: string };
  Ellipsoid: { MOON: unknown; default: unknown };
  Viewer: new (el: HTMLElement, o: Record<string, unknown>) => {
    scene: { primitives: { add: (p: unknown) => void } };
    zoomTo: (t: unknown) => Promise<unknown>;
    destroy: () => void;
  };
  Cesium3DTileset: { fromIonAssetId: (id: number) => Promise<unknown> };
};

function loadCesium(): Promise<CesiumNS> {
  const w = window as unknown as { Cesium?: CesiumNS };
  if (w.Cesium) return Promise.resolve(w.Cesium);
  return new Promise((resolve, reject) => {
    const css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = `${CDN}/Widgets/widgets.css`;
    document.head.appendChild(css);
    const s = document.createElement('script');
    s.src = `${CDN}/Cesium.js`;
    s.async = true;
    s.onload = () => (w.Cesium ? resolve(w.Cesium) : reject(new Error('Cesium script loaded but window.Cesium is missing')));
    s.onerror = () => reject(new Error(`Could not load CesiumJS ${CESIUM_VERSION} from cesium.com (offline or blocked)`));
    document.head.appendChild(s);
  });
}

export function CesiumMoon() {
  const [token, setToken] = useState('');
  const [state, setState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [msg, setMsg] = useState('');
  const host = useRef<HTMLDivElement>(null);
  const viewer = useRef<{ destroy: () => void } | null>(null);

  useEffect(() => () => viewer.current?.destroy(), []);

  async function start() {
    if (!token.trim()) return;
    setState('loading');
    setMsg('');
    try {
      const C = await loadCesium();
      C.Ion.defaultAccessToken = token.trim();
      C.Ellipsoid.default = C.Ellipsoid.MOON;
      viewer.current?.destroy();
      const v = new C.Viewer(host.current!, {
        globe: false,
        baseLayer: false,
        baseLayerPicker: false,
        geocoder: false,
        timeline: false,
        animation: false,
        skyAtmosphere: false,
        sceneModePicker: false,
        navigationHelpButton: false,
        homeButton: false,
        infoBox: false,
        selectionIndicator: false,
      });
      viewer.current = v;
      const tiles = await C.Cesium3DTileset.fromIonAssetId(ASSET_ID);
      v.scene.primitives.add(tiles);
      await v.zoomTo(tiles);
      setState('ready');
    } catch (e) {
      viewer.current?.destroy();
      viewer.current = null;
      setState('error');
      setMsg((e as Error).message || 'Cesium failed');
    }
  }

  return (
    <section className="panel" aria-labelledby="cz-title">
      <div className="panel-head">
        <h2 id="cz-title">Global Moon (optional · Cesium ion asset {ASSET_ID})</h2>
        <span className="muted">context only — never used as elevation data</span>
      </div>
      <form
        className="cesium-form"
        onSubmit={(e) => {
          e.preventDefault();
          void start();
        }}
      >
        <label>
          Cesium ion token (kept in memory only)
          <input type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)} data-testid="cesium-token" />
        </label>
        <button type="submit" className="btn" disabled={!token.trim() || state === 'loading'} data-testid="cesium-load">
          {state === 'loading' ? 'Loading…' : 'Load Moon'}
        </button>
      </form>
      {state === 'error' && (
        <p className="error" role="alert" data-testid="cesium-error">
          Cesium unavailable: {msg}. The local terrain view and all bundle panels are unaffected.
        </p>
      )}
      <div ref={host} className="cesium-host" hidden={state !== 'ready' && state !== 'loading'} />
    </section>
  );
}
