import { Component, lazy, Suspense, useEffect, useState, type ReactNode } from 'react';
import { usePolaris } from './store/store';
import { useView } from './store/view';
import { Header } from './components/Header';
import { TimeBar } from './components/TimeBar';
import { HorizonChart } from './components/HorizonChart';
import { VisibilityStrips } from './components/VisibilityStrips';
import { MetricsPanel } from './components/MetricsPanel';
import { FailuresPanel } from './components/FailuresPanel';
import { ProvenanceDrawer } from './components/ProvenanceDrawer';
import { CesiumMoon } from './three/CesiumMoon';
import { PolarMap } from './components/PolarMap';
import type { BundleIndexEntry } from './bundle/types';

const Scene3D = lazy(() => import('./three/Scene3D'));

class Guard extends Component<{ children: ReactNode; label: string }, { err: string | null }> {
  state = { err: null as string | null };
  static getDerivedStateFromError(e: Error) {
    return { err: e.message };
  }
  render() {
    if (this.state.err)
      return (
        <p className="error" role="alert">
          {this.props.label} unavailable ({this.state.err}). All other panels still read the bundle.
        </p>
      );
    return this.props.children;
  }
}

function webglAvailable(): boolean {
  try {
    const c = document.createElement('canvas');
    return !!(c.getContext('webgl2') || c.getContext('webgl'));
  } catch {
    return false;
  }
}

export default function App() {
  const loaded = usePolaris((s) => s.loaded);
  const loading = usePolaris((s) => s.loading);
  const loadError = usePolaris((s) => s.loadError);
  const v = useView();
  const [prov, setProv] = useState(false);
  const [gl] = useState(webglAvailable);

  useEffect(() => {
    const st = usePolaris.getState();
    const want = new URLSearchParams(location.search).get('bundle');
    fetch('bundles/index.json')
      .then((r) => (r.ok ? r.json() : { bundles: [] }))
      .then((j: { bundles: BundleIndexEntry[] }) => {
        st.setIndex(j.bundles);
        const pick = j.bundles.find((b) => b.file === want) ?? j.bundles[0];
        if (pick) void st.loadFromUrl(`bundles/${pick.file}`, pick.file, pick.origin);
      })
      .catch(() => usePolaris.setState({ loadError: 'No bundles/index.json found. Run `npm run sync-bundles` or open a bundle file.' }));
  }, []);

  const demo = loaded?.status === 'DEMO';
  return (
    <div className={`app ${demo ? 'is-demo' : ''}`}>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <Header onOpenProvenance={() => setProv(true)} />
      {demo && (
        <div className="demo-banner" role="status" data-testid="demo-banner">
          DEMO · synthetic terrain and invented sky · not NASA, not JPL · for viewer development only
        </div>
      )}
      <main id="main" tabIndex={-1}>
        {loading && <p className="note">Loading bundle…</p>}
        {loadError && (
          <p className="error" role="alert" data-testid="load-error">
            {loadError}
          </p>
        )}
        {loaded?.warnings.map((w) => (
          <p className="warn" key={w} data-testid="bundle-warning">
            {w}
          </p>
        ))}
        {v && (
          <>
            <div className="site-line">
              <h1>{v.dataset.site.name}</h1>
              <span className="muted">
                {v.dataset.site.latitudePlanetocentricDeg.toFixed(4)}°, {v.dataset.site.longitudeEastDeg.toFixed(4)}°E · {v.scenario ? v.scenario.label : 'no scenarios in bundle'}
              </span>
            </div>
            <TimeBar v={v} />
            <div className="grid">
              <div className="col">
                <HorizonChart v={v} />
                <VisibilityStrips v={v} />
                <FailuresPanel v={v} />
              </div>
              <div className="col">
                <MetricsPanel v={v} />
                <section className="panel" aria-labelledby="s3-title">
                  <div className="panel-head">
                    <h2 id="s3-title">Local terrain 3D</h2>
                    <span className="muted">drag to orbit · scroll to zoom</span>
                  </div>
                  {gl ? (
                    <Guard label="3D view">
                      <Suspense fallback={<p className="note">Loading 3D…</p>}>
                        <Scene3D v={v} />
                      </Suspense>
                    </Guard>
                  ) : (
                    <p className="error" role="alert">
                      WebGL is not available in this browser, so the 3D view is off. Charts and metrics are unaffected.
                    </p>
                  )}
                </section>
                <Guard label="Cesium">
                  <CesiumMoon />
                </Guard>
              </div>
            </div>
          </>
        )}
        <Guard label="South Pole map">
          <PolarMap v={v} />
        </Guard>
      </main>
      <footer>
        POLARIS X · b-experience viewer · research prototype, not flight software · the viewer reads science-bundle-v2 and computes no skylines, visibility or metrics
      </footer>
      <ProvenanceDrawer v={v} open={prov} onClose={() => setProv(false)} />
    </div>
  );
}
