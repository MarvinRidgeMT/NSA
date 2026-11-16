import { Component, lazy, Suspense, useEffect, useState, type ReactNode } from 'react';
import { usePolaris } from './store/store';
import { fmtSigned, fmtUtc, useView, type View } from './store/view';
import { useRidgeFocus } from './store/ridge';
import { parseSidecar } from './bundle/certaintySidecar';
import { fmtRidgeDistance, type RidgeNow } from './bundle/evidence';
import { Header, WORKSPACES, type Workspace } from './components/Header';
import { Story } from './components/Story';
import { DecisionCard } from './components/DecisionCard';
import { CAMERA_VIEWS, useCamera } from './store/camera';
import { useUi } from './store/ui';
import { MastInstrument } from './components/MastInstrument';
import { DecisionHero } from './components/DecisionHero';
import { ArrivalSlipStrip } from './components/ArrivalSlipStrip';
import { FlipForecastTable } from './components/FlipForecastTable';
import { Guide } from './components/Guide';
import { firstBlockedRun, ridgesOfRecord } from './bundle/ridgeSeek';
import { ridgeBins } from './bundle/evidence';
import { TimeBar } from './components/TimeBar';
import { HeadingTape } from './components/HeadingTape';
import { HorizonChart } from './components/HorizonChart';
import { HorizonWheel } from './components/HorizonWheel';
import { VisibilityStrips } from './components/VisibilityStrips';
import { MetricsPanel } from './components/MetricsPanel';
import { FailuresPanel } from './components/FailuresPanel';
import { ProvenanceDrawer } from './components/ProvenanceDrawer';
import { CesiumMoon } from './three/CesiumMoon';
import { PolarMap } from './components/PolarMap';
import { EventsPanel, ScenarioTable } from './components/ScenarioTable';
import { MarginRibbon } from './components/MarginRibbon';
import { RidgePanel } from './components/RidgePanel';
import { EvidencePipeline, EvidenceRecord } from './components/EvidenceRecord';
import { CoverageGauge } from './components/CoverageGauge';
import { CertaintyHeight } from './components/CertaintyHeight';
import { CubeSlicer } from './components/CubeSlicer';
import { LaunchCalendar, SafeLitGrid } from './components/CubeViews';
import type { BundleIndexEntry } from './bundle/types';
import { fetchIndex, IndexError } from './bundle/bootIndex';
import { startUrlSync } from './store/urlState';
import { applyRouteSite } from './store/siteDefaults';

import { GlobeButton, SurfaceLayerChip, SurfaceLayerPicker } from './components/SurfaceLayer';
import { useSurface } from './store/surface';
const Scene3D = lazy(() => import('./three/Scene3D'));

type Route = Workspace | 'story';
const fromHash = (): Route => {
  const h = location.hash.replace('#', '');
  if (h === 'story') return 'story';
  if (WORKSPACES.some((w) => w.id === h)) return h as Workspace;
  // no hash: the story opens first, unless a bundle was asked for explicitly (deep links and tests)
  return new URLSearchParams(location.search).has('bundle') ? 'sky' : 'story';
};

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

/** Sun / Earth now: the instrument's first section (bundle values at the current sample; no interpolation of flags). */
function Readouts({ v }: { v: View }) {
  const { focus } = useRidgeFocus(v);
  const { selectBin } = usePolaris.getState();
  const row = (key: 'sun' | 'earth') => {
    const t = v[key];
    const state = t.visible === undefined ? 'not in bundle' : t.visible === null ? 'transition' : t.visible ? 'visible' : 'blocked';
    return (
      <div className={`readout ${key} sky-now ${state}`} data-testid={`sky-${key}`}>
        <span className="who">{key === 'sun' ? 'Sun' : 'Earth'}</span>
        <span className={`state ${state}`}>{state}</span>
        <span className="big">{t.marginDeg !== null ? fmtSigned(t.marginDeg) : '—'}</span>
        <span className="val">
          margin vs skyline
          <br />
          az {t.az.toFixed(1)}° · el {fmtSigned(t.el)}
        </span>
      </div>
    );
  };
  return (
    <div className="sect now-sect">
      <span className="lab">At this sample</span>
      {row('sun')}
      {row('earth')}
      <p className="scope">Centre-of-disk geometric visibility (bundle). Not power, not a DSN link.</p>
      {focus?.source === 'selected' && (
        <button type="button" className="btn btn-small" onClick={() => selectBin(null)} data-testid="ridge-clear">
          Clear ridge highlight
        </button>
      )}
    </div>
  );
}

/** Ridge-of-record callouts for the target(s) blocked at the current sample (bundle attribution; lookups only). */
function SkyRidges({ v }: { v: View }) {
  const { sun, earth } = useRidgeFocus(v);
  const { selectBin, setSampleIndex } = usePolaris.getState();
  const callout = (key: 'sun' | 'earth', r: RidgeNow | null) => {
    if (!r || v[key].visible !== false) return null;
    const rd = r.ridge;
    const far = rd.dem === 'far_80m';
    return (
      <div className={`ridge-callout ${key}`} data-testid={`ridge-callout-${key}`} key={key}>
        <div className="rc-head">
          <span className="rc-kicker">{key === 'sun' ? 'Sun' : 'Earth'} blocked by</span>
          <strong>{rd.label ?? rd.id}</strong>
          <span className="rc-badge">{far ? '80 m regional DEM' : rd.dem === 'near_5m' ? '5 m local DEM' : (rd.dem ?? 'source ?')}</span>
        </div>
        <dl className="rc-facts">
          <div>
            <dt>Distance</dt>
            <dd>{fmtRidgeDistance(rd)}</dd>
          </div>
          <div>
            <dt>Bearing</dt>
            <dd>
              {rd.azimuthDeg[0].toFixed(1)}–{rd.azimuthDeg[1].toFixed(1)}°
            </dd>
          </div>
          <div>
            <dt>{rd.reliefM !== undefined ? 'Height vs site ground' : 'Height'}</dt>
            <dd>{rd.reliefM !== undefined ? fmtSigned(rd.reliefM, Math.abs(rd.reliefM) < 100 ? 2 : 0, ' m') : typeof rd.heightM === 'number' ? `${rd.heightM.toFixed(0)} m` : '—'}</dd>
          </div>
          <div>
            <dt>Blocks {key === 'sun' ? 'Sun' : 'Earth'} (window)</dt>
            <dd>{rd.hours[key].lost.toFixed(0)} h</dd>
          </div>
          {r.run && (
            <div>
              <dt>This obstruction</dt>
              <dd>
                {fmtUtc(v.times[r.run.i0]).slice(5, 16).replace('T', ' ')} → {fmtUtc(v.times[r.run.i1]).slice(5, 16).replace('T', ' ')} UTC · {r.run.i1 - r.run.i0 + 1} samples
              </dd>
            </div>
          )}
        </dl>
        <div className="rc-actions">
          <button
            type="button"
            className="btn btn-small"
            onClick={() => {
              const ui = useUi.getState();
              if (!ui.returnTo) ui.set({ returnTo: { view: useCamera.getState().view, sample: v.nearest } });
              ui.set({ run: r.run ? { ...r.run, target: key } : null });
              selectBin(r.bin);
              useCamera.getState().request('ridge');
            }}
            data-testid={`ridge-inspect-${key}`}
          >
            Inspect
          </button>
          {r.run && r.run.i0 > 0 && (
            <button type="button" className="btn btn-small" onClick={() => setSampleIndex(r.run!.i0 - 1)} title="last sample before this obstruction">
              ← before
            </button>
          )}
          {r.run && r.run.i1 < v.times.length - 1 && (
            <button type="button" className="btn btn-small" onClick={() => setSampleIndex(r.run!.i1 + 1)} title="first sample after this obstruction">
              after →
            </button>
          )}
        </div>
        <p className="rc-note">
          {far
            ? 'Distant terrain (80 m regional DEM), outside the 5 m tile: the alternate terrain realizations do not vary it.'
            : 'Inside the 5 m tile, where the alternate terrain realizations apply.'}
        </p>
      </div>
    );
  };
  const a = callout('sun', sun);
  const b = callout('earth', earth);
  if (!a && !b) return <RidgeList v={v} />;
  return (
    <>
      <div className="sect ridge-callouts">
        <span className="lab">Ridge of Record</span>
        {a}
        {b}
      </div>
      <RidgeList v={v} also />
    </>
  );
}

/** Ridges of record from the bundle attribution, each one a jump to the first obstruction the bundle attributes to it. */
function RidgeList({ v, also = false }: { v: View; also?: boolean }) {
  const list = ridgesOfRecord(v);
  const { selectBin, setSampleIndex } = usePolaris.getState();
  return (
    <div className="sect" data-testid="ridge-list">
      <span className="lab">{also ? 'All ridges of record' : 'Ridge of Record'}</span>
      {list.length === 0 ? (
        <p className="scope" style={{ marginTop: 0 }}>
          {(() => {
            const att = v.dataset.derived?.attribution;
            if (!att) return 'This bundle carries no ridge attribution.';
            if (att.scenarioId && att.scenarioId !== v.series?.id)
              return `Ridge attribution in this bundle describes the “${att.scenarioId}” series only, so no ridge is named for “${v.series?.label ?? v.series?.id}”.`;
            return 'The bundle attributes no Sun or Earth loss to any ridge in this window.';
          })()}
        </p>
      ) : (
        <>
          <p className="scope" style={{ marginTop: 0 }}>
            {also ? 'Jump to the first obstruction each ridge causes:' : 'Neither target is blocked at this sample. These ridges cause the losses in this window:'}
          </p>
          <ul className="ridge-list">
            {list.map(({ ridge: r, target }) => (
              <li key={r.id}>
                <button
                  type="button"
                  className="ridge-row"
                  data-testid={`ridge-go-${r.id}`}
                  onClick={() => {
                    const run = firstBlockedRun(v, r, target);
                    const ui = useUi.getState();
                    if (!ui.returnTo) ui.set({ returnTo: { view: useCamera.getState().view, sample: v.nearest } });
                    if (run) {
                      setSampleIndex(run.i0);
                      ui.set({ run: { ...run, target } });
                    }
                    const bins = ridgeBins(v.dataset.derived?.attribution, v.dataset.derived!.attribution!.ridges.indexOf(r));
                    if (bins.length) selectBin(bins[Math.floor(bins.length / 2)]);
                    useCamera.getState().request('ridge');
                  }}
                >
                  <span className={`who ${target}`}>{target === 'sun' ? 'Sun' : 'Earth'}</span>
                  <span className="rid">{r.label ?? r.id}</span>
                  <span className="rd">{fmtRidgeDistance(r)}</span>
                  <span className="rh">{r.hours[target].lost} h</span>
                </button>
              </li>
            ))}
          </ul>
          <p className="scope">Hours = hourly bundle samples attributed to the ridge (bundle derived.attribution); not hours that removing it would recover.</p>
        </>
      )}
    </div>
  );
}

/** Return from a Ridge of Record inspection to the camera view and sample the user came from. */
function LightToggle() {
  const trueLight = useUi((s) => s.trueLight);
  const set = (v: boolean) => useUi.getState().set({ trueLight: v });
  return (
    <span className="seg" data-testid="light-mode">
      <button
        type="button"
        className="btn"
        aria-pressed={!trueLight}
        data-testid="light-display"
        title="Display: Sun azimuth from the bundle, elevation shown at no less than 0.5°, plus a weak relief fill so shadowed slopes stay readable"
        onClick={() => set(false)}
      >
        Display
      </button>
      <button
        type="button"
        className="btn"
        aria-pressed={trueLight}
        data-testid="light-true"
        title="Scientific: the bundle's true Sun elevation, no fill light; a Sun below the horizon leaves the terrain dark"
        onClick={() => set(true)}
      >
        Scientific
      </button>
    </span>
  );
}

function ReturnBar() {
  const returnTo = useUi((s) => s.returnTo);
  if (!returnTo) return null;
  return (
    <button
      type="button"
      className="btn return-btn"
      data-testid="ridge-return"
      onClick={() => {
        usePolaris.getState().selectBin(null);
        usePolaris.getState().setSampleIndex(returnTo.sample);
        useCamera.getState().request(returnTo.view);
        useUi.getState().set({ returnTo: null, run: null });
      }}
    >
      ← Back to the previous view
    </button>
  );
}

/** Cold-launch / bundle failure: what went wrong, where, and two ways forward (Retry the same thing, or open a file). */
function LoadErrorPanel({ message }: { message: string }) {
  const retry = usePolaris((s) => s.loadRetry);
  const loaded = usePolaris((s) => s.loaded);
  const where = typeof location !== 'undefined' ? `${location.origin === 'null' ? location.protocol + '//' : location.origin}${location.pathname}` : '';
  return (
    <section className="load-fail" aria-labelledby="load-fail-h" data-testid="load-fail">
      <h2 id="load-fail-h">{loaded ? 'That bundle could not be loaded' : 'The viewer could not start'}</h2>
      <p className="error" role="alert" data-testid="load-error">
        {message}
      </p>
      <p className="load-fail-meta">
        Page: <code>{where}</code>
        {loaded ? ` · still showing ${loaded.name}` : ' · no bundle was loaded, and none is substituted'}
      </p>
      <div className="load-fail-actions">
        {retry && (
          <button type="button" className="btn-primary" data-testid="load-retry" onClick={() => retry()}>
            Retry
          </button>
        )}
        <label className="btn-file">
          Open a bundle file…
          <input
            type="file"
            accept=".json,application/json"
            data-testid="load-fail-file"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void usePolaris.getState().loadFromFile(f);
            }}
          />
        </label>
      </div>
    </section>
  );
}

/**
 * Cold launch (Final Apex P1): read bundles/index.json, then load the deep-linked bundle or the hero ROI export.
 * Any failure shows a specific message with Retry (which re-runs this function); nothing is substituted.
 */
function coldLaunch() {
  const st = usePolaris.getState();
  const want = new URLSearchParams(location.search).get('bundle');
  usePolaris.setState({ loading: true, loadError: null, loadRetry: null });
  fetchIndex()
    .then((bundles: BundleIndexEntry[]) => {
      usePolaris.setState({ loading: false });
      st.setIndex(bundles);
      const j = { bundles };

      // Opening view (no ?bundle): prefer the ROI export, whose Site04 ROI3 dataset carries the real 5 m PGDA 78 DEM crop, so the
      // Explore stage starts on true terrain. The a-science results bundle for the same site (skyline only) stays one click away.
      const hero = j.bundles.find((b) => /^polaris-x5d-roi-.*\.json$/.test(b.file));
      const listed = want ? j.bundles.find((b) => b.file === want) : undefined;
      if (want && !listed) {
        // A deep link names a bundle that is not in bundles/index.json: load exactly that file (or show the error).
        // Never substitute a different bundle: a user asking for one site must not silently see another.
        if (/^[\w.-]+\.json$/.test(want)) void st.loadFromUrl(`bundles/${want}`, want, 'deep link (not listed in bundles/index.json)');
        else usePolaris.setState({ loadError: `Bundle name "${want}" is not a plain .json file name.` });
        return;
      }
      const pick = listed ?? hero ?? j.bundles[0];
      if (pick)
        // the opening site of the ROI export depends on the page (Explore: Site01 ROI6; story, Decision, Evidence: Site04 ROI3);
        // see store/siteDefaults.ts. It is applied by the route effect in App once the bundle is loaded.
        void st.loadFromUrl(`bundles/${pick.file}`, pick.file, pick.origin);
    })
    .catch((e: unknown) =>
      usePolaris.setState({
        loading: false,
        loadError: e instanceof IndexError ? e.message : `Could not read bundles/index.json: ${(e as Error).message}`,
        loadRetry: coldLaunch,
      }),
    );
}

export default function App() {
  const loaded = usePolaris((s) => s.loaded);
  const loading = usePolaris((s) => s.loading);
  const loadError = usePolaris((s) => s.loadError);
  const v = useView();
  const [prov, setProv] = useState(false);
  const [gl] = useState(webglAvailable);
  const [route, setRoute] = useState<Route>(fromHash);
  const cam = useCamera();
  const stageFocus = useUi((s) => s.focus);
  // F toggles the stage focus (panels hidden, terrain fills the stage); Esc leaves it. Ignored while typing in a field.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el && (el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if ((e.key === 'f' || e.key === 'F') && location.hash.replace('#', '') === 'sky') useUi.getState().set({ focus: !useUi.getState().focus });
      else if (e.key === 'Escape' && useUi.getState().focus) useUi.getState().set({ focus: false });
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  const [wide, setWide] = useState(() => typeof matchMedia !== 'function' || matchMedia('(min-width: 1024px)').matches);
  useEffect(() => {
    if (typeof matchMedia !== 'function') return;
    const mq = matchMedia('(min-width: 1024px)');
    const on = () => setWide(mq.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);

  useEffect(() => {
    startUrlSync(); // shareable link: site, time, scenario, camera, surface layer (src/store/urlState.ts, session A)
    coldLaunch();
    // optional, additive: a missing or malformed sidecar simply leaves the Certainty Height panel on its bundle fallback
    fetch('certainty/sidecar.json')
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => usePolaris.setState({ certaintySidecar: parseSidecar(j) }))
      .catch(() => undefined);
    const onHash = () => setRoute(fromHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const loadedName = usePolaris((s) => s.loaded?.name);
  const guideOpen = useUi((s) => s.guide !== null);
  useEffect(() => {
    if (!guideOpen) applyRouteSite(route);
  }, [route, loadedName, guideOpen]);

  const go = (id: Route) => {
    setRoute(id);
    history.replaceState(null, '', `${location.pathname}${location.search}#${id}`);
    window.scrollTo({ top: 0 });
  };
  const ws: Workspace = route === 'story' ? 'sky' : route;

  const demo = loaded?.status === 'DEMO';
  const hasDem = !!v?.dataset.dem;
  const contextLoaded = useSurface((st) => st.contextLoaded);
  const views = CAMERA_VIEWS.filter((c) => (hasDem ? c.dem : c.panorama) && (c.id !== 'context' || contextLoaded));
  return (
    <div className={`app route-${route} ${demo ? 'is-demo' : ''}`}>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <Header onOpenProvenance={() => setProv(true)} ws={route} go={go} story={route === 'story'} onGuide={() => useUi.getState().set({ guide: 0 })} />
      {demo && (
        <div className="demo-banner" role="status" data-testid="demo-banner">
          DEMO · synthetic terrain and invented sky · not NASA, not JPL · for viewer development only
        </div>
      )}
      {route === 'story' && <Story onEnter={() => go('sky')} onEvidence={() => go('evidence')} onGuide={() => useUi.getState().set({ guide: 0 })} />}
      <Guide go={go} />
      <main
        id="main"
        tabIndex={-1}
        hidden={route === 'story'}
        data-source={loaded ? `bundles/${loaded.name}` : undefined}
        data-classification={loaded?.status}
      >
        {(loading || loadError || (ws !== 'sky' && (loaded?.warnings.filter((w) => !/3D view|DEM grid/.test(w)).length ?? 0) > 0)) && (
          <div className="top-clock">
            {loading && !loadError && (
              <p className="note" role="status" data-testid="loading">
                Loading bundle…
              </p>
            )}
            {loadError && <LoadErrorPanel message={loadError} />}
            {ws !== 'sky' &&
              loaded?.warnings.filter((w) => !/3D view|DEM grid/.test(w)).map((w) => (
                <p className="warn" key={w} data-testid="bundle-warning">
                  {w}
                </p>
              ))}
          </div>
        )}
        {v && (
          <>
            {/* Explore stays mounted (hidden) while another workspace is open: the 3D camera and scene survive tab switches,
                and the canvas is never torn down mid-frame. Its render loop pauses while hidden. */}
            <div id="ws-sky" role="tabpanel" aria-labelledby="tab-sky" hidden={ws !== 'sky'}>
              <section className={`stage${stageFocus ? ' is-focus' : ''}`} aria-label="Immersive stage" data-focus={stageFocus ? 'on' : 'off'}>
                {gl ? (
                  <Guard label="3D view">
                    <Suspense fallback={<p className="note">Loading 3D…</p>}>
                      <Scene3D v={v} active={ws === 'sky' && route !== 'story'} />
                    </Suspense>
                  </Guard>
                ) : (
                  <p className="error" role="alert">
                    WebGL is not available in this browser, so the 3D view is off. Every value is still in the instrument, the charts and the tables below.
                  </p>
                )}
                {gl && hasDem && <HeadingTape v={v} />}
                <div className="stage-title" key={`${v.dataset.siteId}`}>
                  <div className="lab" data-testid="stage-view" data-view={cam.view}>
                    View · {CAMERA_VIEWS.find((c) => c.id === cam.view)?.label ?? 'Approach'} · {hasDem ? 'real surface' : 'horizon geometry'}
                  </div>
                  <h1>{v.dataset.site.name}</h1>
                  <div className="coords">
                    {Math.abs(v.dataset.site.latitudePlanetocentricDeg).toFixed(5)}° {v.dataset.site.latitudePlanetocentricDeg < 0 ? 'S' : 'N'} ·{' '}
                    {Math.abs(v.dataset.site.longitudeEastDeg).toFixed(5)}° {v.dataset.site.longitudeEastDeg < 0 ? 'W' : 'E'} · {v.scenario ? v.scenario.label : 'no scenarios in bundle'}
                  </div>
                  <div className="stage-meta">
                  <span className={`mode ${hasDem ? 'mesh' : 'panorama'}`} data-testid="geometry-mode" title={hasDem ? 'terrain mesh from the bundle DEM grid' : 'angular skyline only; not a terrain surface'}>
                    {hasDem
                      ? `REAL SURFACE · ${v.dataset.dem!.n}² × ${v.dataset.dem!.spacing} m DEM`
                      : 'HORIZON GEOMETRY · angular panorama, not a terrain mesh'}
                  </span>
                  <SurfaceLayerChip v={v} />
                  </div>
                  {loaded?.warnings.map((w) => (
                    <p className="stage-warn" key={w} data-testid="bundle-warning">
                      {w}
                    </p>
                  ))}
                </div>
                <aside className="instrument" aria-label="Site instrument" data-testid="instrument">
                  <MastInstrument v={v} />
                  <Readouts v={v} />
                  <ReturnBar />
                  <SkyRidges v={v} />
                  <div className="sect">
                    <span className="lab">Go deeper</span>
                    <div className="actions">
                      <button type="button" className="btn" onClick={() => go('decision')}>
                        Decision
                      </button>
                      <button type="button" className="btn" onClick={() => go('evidence')}>
                        Evidence
                      </button>
                    </div>
                  </div>
                </aside>
                <div className="stage-bottom">
                {gl && (
                  <div className="views" role="group" aria-label="Camera views" data-testid="camera-views">
                    <span className="lab">View</span>
                    {hasDem && <GlobeButton />}
                    {views.map((c) => (
                      <button
                        key={c.id}
                        type="button"
                        className="btn"
                        aria-pressed={cam.view === c.id}
                        title={c.hint}
                        data-testid={`cam-${c.id}`}
                        onClick={() => cam.request(c.id)}
                      >
                        {c.label}
                      </button>
                    ))}
                    <button
                      type="button"
                      className="btn reset-view"
                      onClick={() => cam.request(cam.view)}
                      data-testid="cam-reset"
                      aria-label={`Reset view (re-frame ${CAMERA_VIEWS.find((c) => c.id === cam.view)?.label ?? 'the view'})`}
                      title="Reset view: re-frame the current view after orbiting or zooming"
                    >
                      ↺
                    </button>
                    {hasDem && (
                      <div className="display-cluster" role="group" aria-label="Display (does not change any number)">
                        <span className="lab">Light</span>
                        <LightToggle />
                        <SurfaceLayerPicker />
                      </div>
                    )}
                  </div>
                )}
                <div className="temporal" aria-label="Temporal instrument">
                  {ws === 'sky' && <TimeBar v={v} />}
                  <div className="ribbon-wrap">
                    <MarginRibbon v={v} compact={wide} />
                  </div>
                </div>
                </div>
              </section>
              <section className="inspect" aria-labelledby="inspect-title">
                <div className="inspect-head">
                  <div>
                    <div className="lab">Inspect</div>
                    <h2 id="inspect-title">The horizon, sample by sample</h2>
                  </div>
                  <p>Everything on the stage, as charts and lists: the skyline with the Sun and Earth tracks, visibility per sample, events and the obstructions the bundle records.</p>
                </div>
                <div className="grid">
                  <div className="col">
                    <HorizonWheel v={v} />
                    <FailuresPanel v={v} />
                  </div>
                  <div className="col">
                    <HorizonChart v={v} />
                    <VisibilityStrips v={v} />
                    <EventsPanel v={v} />
                    <Guard label="Cesium">
                      <CesiumMoon />
                    </Guard>
                  </div>
                </div>
              </section>
            </div>
            {ws === 'decision' && (
              <div id="ws-decision" role="tabpanel" aria-labelledby="tab-decision" className="ws-page dec-page">
                <div className="dec-hero">
                  <div>
                    <div className="page-head">
                      <div>
                        <div className="lab">Decision · {v.dataset.site.name}</div>
                        <h1>Does this ground keep the light?</h1>
                      </div>
                      <a className="btn" href={`${import.meta.env.BASE_URL}lab/index.html`} data-testid="decision-lab-link">
                        Decision Lab · four sites, 12 months
                      </a>
                    </div>
                    <DecisionHero v={v} />
                  </div>
                  <DecisionCard v={v} />
                </div>
                <div className="dec-evidence-head">
                  <h2>The evidence behind it</h2>
                  <details className="dec-more src-legend-wrap">
                    <summary>
                      <span className="src-tag bundle">bundle</span> <span className="src-tag batch">batch sweep</span> what the two sources are
                    </summary>
                    <p className="src-legend" data-testid="src-legend">
                      <span className="src-tag bundle">bundle</span> values come from the loaded results bundle (repo solver, nominal DEM, its own sampling).{' '}
                      <span className="src-tag batch">batch sweep</span> values come from the hourly batch run across the nominal DEM and the alternate realizations. The two
                      solvers sample differently, so a bundle percentage and the batch nominal can differ by a fraction of a percent; neither is independently validated.
                    </p>
                  </details>
                </div>
                <TimeBar v={v} />
                <div className="grid">
                  <div className="col">
                    <CertaintyHeight v={v} />
                    <MetricsPanel v={v} />
                  </div>
                  <div className="col">
                    <CoverageGauge v={v} />
                    <ScenarioTable v={v} />
                    <ArrivalSlipStrip v={v} />
                    <FlipForecastTable v={v} />
                  </div>
                </div>
                <Guard label="Scenario cube">
                  <CubeSlicer v={v} />
                </Guard>
                <div className="grid cube-views">
                  <Guard label="Safe and lit">
                    <SafeLitGrid siteId={v.dataset.site.id} />
                  </Guard>
                  <Guard label="Launch calendar">
                    <LaunchCalendar siteId={v.dataset.site.id} />
                  </Guard>
                </div>
              </div>
            )}
            {ws === 'evidence' && (
              <div id="ws-evidence" role="tabpanel" aria-labelledby="tab-evidence" className="ws-page">
                <div className="page-head">
                  <div>
                    <div className="lab">Evidence · how each number was made</div>
                    <h1>Receipts, not reassurance</h1>
                    <p>Which terrain decides each blocked hour, where the inputs came from, and what has and has not been checked.</p>
                  </div>
                  <button type="button" className="btn" onClick={() => setProv(true)} data-testid="open-provenance-evidence">
                    Open the provenance record
                  </button>
                </div>
                <TimeBar v={v} />
                <div className="grid">
                  <div className="col">
                    <EvidencePipeline v={v} />
                    <RidgePanel v={v} />
                    <section className="panel" aria-labelledby="ev-title">
                      <div className="panel-head">
                        <h2 id="ev-title">Provenance and limits</h2>
                      </div>
                      <dl className="kv">
                        <dt>Bundle</dt>
                        <dd>{v.loaded.name}</dd>
                        <dt>SHA-256</dt>
                        <dd>{v.loaded.sha256}</dd>
                        <dt>Derived outputs</dt>
                        <dd>{v.dataset.derived ? `${v.dataset.derived.producer.name} ${v.dataset.derived.producer.version}` : 'none in bundle'}</dd>
                        <dt>Status</dt>
                        <dd>{v.status}</dd>
                      </dl>
                      {v.dataset.limitations && v.dataset.limitations.length > 0 && (
                        <>
                          <h3>Known limits (from the bundle)</h3>
                          <ul className="links small">
                            {v.dataset.limitations.map((l) => (
                              <li key={l}>{l}</li>
                            ))}
                          </ul>
                        </>
                      )}
                    </section>
                    <EvidenceRecord v={v} />
                  </div>
                  <div className="col">
                    <Guard label="South Pole map">
                      <PolarMap v={v} />
                    </Guard>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
        {!v && !loading && route !== 'story' && (
          <div className="ws-page">
            <Guard label="South Pole map">
              <PolarMap v={v} />
            </Guard>
          </div>
        )}
      </main>
      {route !== 'story' && (
        <footer>
          POLARIS X · research prototype, not flight software · the viewer reads science bundles and computes no skylines, visibility or metrics · SOURCE-BASED · UNVALIDATED until independently checked
        </footer>
      )}
      <ProvenanceDrawer v={v} open={prov} onClose={() => setProv(false)} />
    </div>
  );
}
