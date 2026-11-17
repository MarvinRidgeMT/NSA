import { Component, lazy, Suspense, useEffect, useState, type ReactNode } from 'react';
import { usePolaris } from './store/store';
import { useView, type View } from './store/view';
import { useCamera } from './store/camera';
import { startUrlSync } from './store/urlState';
import { coldLaunch, loadCertaintySidecar } from './App';
import { PlainAnswer } from './components/PlainAnswer';
import { fmtPctRange, useChooseMast, useMastReading } from './components/MastInstrument';
import { TimeBar } from './components/TimeBar';
import { switchMode } from './mode';
import { pickQuality } from './simple/quality';
const Scene3D = lazy(() => import('./three/Scene3D'));

/** Evidence page in Expert mode: where every Simple-mode number is traced to its source. */
const EVIDENCE_HREF = '?mode=expert#evidence';

class Guard extends Component<{ children: ReactNode }, { err: string | null }> {
  state = { err: null as string | null };
  static getDerivedStateFromError(e: Error) {
    return { err: e.message };
  }
  render() {
    if (this.state.err)
      return (
        <p className="error" role="alert">
          3D view unavailable ({this.state.err}). The answer and numbers beside it still read the bundle and the certainty sidecar.
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

function SourceTag() {
  return (
    <a className="s-tag" href={EVIDENCE_HREF} title="How this number was made (Evidence page, Expert mode)">
      SOURCE-BASED · UNVALIDATED
    </a>
  );
}

/** Sampled mast heights from the certainty sidecar only; nothing between them is offered or implied. */
function MastPicker({ v }: { v: View }) {
  const r = useMastReading(v);
  const choose = useChooseMast(v);
  if (!r) return null;
  const { masts, h, seriesMast } = r;
  return (
    <div className="s-mast">
      <span className="s-lab" id="s-mast-lab">
        Mast height
      </span>
      <div className="s-chips" role="radiogroup" aria-labelledby="s-mast-lab" data-testid="simple-mast-picker">
        {masts.map((m, i) => (
          <button
            key={m}
            type="button"
            role="radio"
            aria-checked={m === h}
            tabIndex={m === h ? 0 : -1}
            className="s-chip"
            data-testid={`simple-mast-${m}`}
            onClick={() => choose(m)}
            onKeyDown={(e) => {
              if (e.key === 'ArrowRight' || e.key === 'ArrowLeft' || e.key === 'ArrowUp' || e.key === 'ArrowDown') {
                e.preventDefault();
                const step = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : -1;
                const j = Math.min(masts.length - 1, Math.max(0, i + step));
                choose(masts[j]);
                (e.currentTarget.parentElement?.children[j] as HTMLElement | undefined)?.focus();
              }
            }}
          >
            {m} m
          </button>
        ))}
      </div>
      {seriesMast !== null && seriesMast !== h && (
        <p className="s-note" data-testid="simple-series-note">
          The bundle has no time series at {h} m, so the 3D view and the Sun / Earth now line stay on the {seriesMast} m series.
        </p>
      )}
    </div>
  );
}

function Stats({ v }: { v: View }) {
  const r = useMastReading(v);
  if (!r) return null;
  const { h, s, b, cert } = r;
  const n = s?.n_clones;
  return (
    <div className="s-stats" data-testid="simple-stats">
      <div className="s-stat sun">
        <span className="s-lab">Sun in sight</span>
        <span className="s-num" data-testid="simple-stat-sun">
          {fmtPctRange(s)}
        </span>
        <span className="s-sub">
          at {h} m · {n ?? '—'} terrain variants
        </span>
        <SourceTag />
      </div>
      <div className="s-stat earth">
        <span className="s-lab">Sun + Earth together</span>
        <span className="s-num" data-testid="simple-stat-both">
          {fmtPctRange(b)}
        </span>
        <span className="s-sub">
          at {h} m · {b?.n_clones ?? '—'} terrain variants
        </span>
        <SourceTag />
      </div>
      <div className="s-stat cert">
        <span className="s-lab">Certainty Height</span>
        <span className="s-num" data-testid="simple-stat-cert">
          {cert !== null ? `${cert} m` : '—'}
        </span>
        <span className="s-sub">{cert !== null ? 'lowest sampled mast with the Sun 100 % in every variant' : 'no sampled mast keeps the Sun 100 % in every variant'}</span>
        <SourceTag />
      </div>
    </div>
  );
}

export default function SimpleApp() {
  const loading = usePolaris((s) => s.loading);
  const loadError = usePolaris((s) => s.loadError);
  const sidecar = usePolaris((s) => s.certaintySidecar);
  const v = useView();
  const [gl] = useState(webglAvailable);
  // render quality tier, picked once at start (display only; simple/quality.ts)
  const [quality] = useState(() => pickQuality(location.search));

  useEffect(() => {
    startUrlSync();
    coldLaunch();
    loadCertaintySidecar();
    useCamera.getState().request('approach');
    // fetch the post-effects chunk while the bundle loads, so the first frames already use it
    if (quality.tier !== 'low') void import('./simple/SimplePost');
  }, [quality]);

  return (
    <div className="simple" data-testid="simple-mode">
      <a className="skip" href="#simple-main">
        Skip to content
      </a>
      <header className="s-top">
        <span className="s-brand">POLARIS X</span>
        <span className="s-modetag">Simple mode</span>
        <span className="s-spacer" />
        <button type="button" className="btn" data-testid="mode-expert" onClick={() => switchMode('expert')}>
          Expert mode
        </button>
      </header>
      <div className="s-banner" role="note" data-testid="simple-banner">
        <span>The demo video shows Expert mode — switch anytime.</span>
        <button type="button" className="btn btn-small" data-testid="mode-expert-banner" onClick={() => switchMode('expert')}>
          Switch to Expert mode
        </button>
      </div>
      <main id="simple-main" tabIndex={-1} className="s-main">
        {loading && !loadError && (
          <p className="note" role="status" data-testid="loading">
            Loading bundle…
          </p>
        )}
        {loadError && (
          <p className="error" role="alert" data-testid="load-error">
            {loadError} Expert mode has Retry and Open-a-file.
          </p>
        )}
        {v && (
          <>
            <div className="s-head">
              <h1 data-testid="simple-site">{v.dataset.site.name}</h1>
              <p className="s-question">Does a lander here keep the Sun?</p>
            </div>
            <div className="s-grid">
              <div className="s-hero">
                <section className="stage simple-stage" aria-label="3D view of the site (Approach camera)">
                  {gl ? (
                    <Guard>
                      <Suspense fallback={<p className="note">Loading 3D…</p>}>
                        <Scene3D v={v} active post={quality.tier} />
                      </Suspense>
                    </Guard>
                  ) : (
                    <p className="error" role="alert">
                      WebGL is not available in this browser, so the 3D view is off. The answer and numbers are unaffected.
                    </p>
                  )}
                </section>
                <div className="s-time">
                  <TimeBar v={v} />
                </div>
              </div>
              <div className="s-side">
                <div className="s-card" data-testid="simple-answer">
                  {sidecar === null ? (
                    <p className="s-note">The certainty sidecar has not loaded, so no answer is shown. Nothing is substituted.</p>
                  ) : (
                    <PlainAnswer v={v} />
                  )}
                </div>
                <MastPicker v={v} />
                <Stats v={v} />
              </div>
            </div>
            <section className="s-limits" aria-labelledby="s-limits-h" data-testid="simple-limits">
              <h2 id="s-limits-h">What this cannot say</h2>
              <ul>
                <li>It is geometric line of sight only: whether the centre of the Sun or Earth clears the terrain skyline.</li>
                <li>It is not solar power: no panel, dust, thermal or battery model.</li>
                <li>It is not communications: no radio link, antenna or Deep Space Network schedule.</li>
                <li>It is not validated: the numbers have not been independently checked against another solver or flight data.</li>
              </ul>
            </section>
          </>
        )}
      </main>
      <footer className="s-foot" data-testid="simple-footer">
        Data: NASA LRO (PGDA), JPL Horizons. Not affiliated with NASA. AI disclosure: Claude/Codex helped write code and docs; every number comes from the solver
        outputs, not AI.
      </footer>
    </div>
  );
}
