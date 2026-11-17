import { Component, lazy, Suspense, useEffect, useId, useLayoutEffect, useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode } from 'react';
import { usePolaris } from './store/store';
import { useUi } from './store/ui';
import { useView, type View } from './store/view';
import { useCamera } from './store/camera';
import { startUrlSync } from './store/urlState';
import { markSiteChosen } from './store/siteDefaults';
import { coldLaunch, loadCertaintySidecar } from './App';
import { PlainAnswer } from './components/PlainAnswer';
import { fmtPctRange, useChooseMast, useMastReading } from './components/MastInstrument';
import { TimeBar } from './components/TimeBar';
import { switchMode } from './mode';
import { pickQuality } from './simple/quality';
import { IconArrow, IconChevronDown, IconChevronUp, IconClose, IconMenu, SoundControl } from './simple/parts';
const Scene3D = lazy(() => import('./three/Scene3D'));

/**
 * Simple mode shell (S2, 17 Nov 2026): light chrome over a full-screen 3D scene. The scene fills the window; the top bar, the
 * answer panel, the numbers panel, the mission-clock slot and the credits strip are laid over it and leave the site clear.
 * Under 640 px the two panels become one bottom sheet. Every number shown is read from the bundle or the certainty sidecar.
 */

/** Evidence and Decision live in Expert mode for now (S9 and S10 bring them in as panels over the scene). */
const EVIDENCE_HREF = '?mode=expert#evidence';
const DECISION_HREF = '?mode=expert#decision';
/** The demo-video banner stays dismissed for this browser session only. */
const BANNER_KEY = 'polaris-x.simple.banner-dismissed';
const PHONE = '(max-width: 639px)';

class Guard extends Component<{ children: ReactNode }, { err: string | null }> {
  state = { err: null as string | null };
  static getDerivedStateFromError(e: Error) {
    return { err: e.message };
  }
  render() {
    if (this.state.err)
      return (
        <p className="error" role="alert">
          3D view unavailable ({this.state.err}). The answer and numbers still read the bundle and the certainty sidecar.
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

function bannerDismissed(): boolean {
  try {
    return window.sessionStorage.getItem(BANNER_KEY) === '1';
  } catch {
    return false;
  }
}

/** Publish an element's measured size as a CSS length on the shell, so overlays can keep clear of it. */
function useShellVar(el: HTMLElement | null, name: string, measure: (el: HTMLElement) => number, watch?: string) {
  useLayoutEffect(() => {
    if (!el || typeof ResizeObserver === 'undefined') return;
    const shell = el.closest<HTMLElement>('.s-shell');
    if (!shell) return;
    const set = () => shell.style.setProperty(name, `${Math.round(measure(el))}px`);
    set();
    const ro = new ResizeObserver(set);
    ro.observe(el);
    const inner = watch ? el.querySelector(watch) : null;
    if (inner) ro.observe(inner);
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- measure and watch are fixed per call site
  }, [el, name]);
}

function SourceTag() {
  return (
    <a className="s-tag" href={EVIDENCE_HREF} title="How this number was made (Evidence page, Expert mode)">
      SOURCE-BASED · UNVALIDATED
    </a>
  );
}

/** Sites of the loaded bundle, by the bundle's own names. */
function SiteSelect() {
  const loaded = usePolaris((s) => s.loaded);
  const datasetIdx = usePolaris((s) => s.datasetIdx);
  return (
    <label className="s-site">
      <span className="sr-only">Site</span>
      <select
        className="s-select"
        data-testid="simple-site-select"
        value={loaded ? datasetIdx : ''}
        disabled={!loaded}
        onChange={(e) => {
          markSiteChosen();
          // a mast picked at one site may not be a sampled height at the next: go back to the site's own series
          useUi.getState().set({ mastPick: null });
          usePolaris.getState().setSite(Number(e.target.value));
        }}
      >
        {!loaded && <option value="">Loading sites…</option>}
        {loaded?.bundle.datasets.map((d, i) => (
          <option key={d.siteId} value={i}>
            {d.site.name}
          </option>
        ))}
      </select>
    </label>
  );
}

/** Up / down through the sidecar's sampled mast heights only; the current height is the large figure between the arrows. */
function MastStepper({ v }: { v: View }) {
  const r = useMastReading(v);
  const choose = useChooseMast(v);
  if (!r) return null;
  const { masts, h } = r;
  const i = masts.indexOf(h);
  const lower = i > 0 ? masts[i - 1] : null;
  const higher = i >= 0 && i < masts.length - 1 ? masts[i + 1] : null;
  return (
    <div className="s-stepper" role="group" aria-label="Mast height, sampled heights only" data-testid="simple-mast-stepper">
      <span className="s-stepper-lab" aria-hidden="true">
        Mast
      </span>
      <button
        type="button"
        className="s-btn s-btn--sm s-btn--icon"
        data-testid="simple-mast-down"
        aria-disabled={lower === null}
        aria-label={lower !== null ? `Lower the mast to ${lower} m` : 'Lowest sampled mast height'}
        onClick={() => lower !== null && choose(lower)}
      >
        <IconChevronDown />
      </button>
      <output className="s-stepper-val" aria-live="polite" data-testid="simple-mast-current">
        {h}
        <span> m</span>
      </output>
      <button
        type="button"
        className="s-btn s-btn--sm s-btn--icon"
        data-testid="simple-mast-up"
        aria-disabled={higher === null}
        aria-label={higher !== null ? `Raise the mast to ${higher} m` : 'Highest sampled mast height'}
        onClick={() => higher !== null && choose(higher)}
      >
        <IconChevronUp />
      </button>
    </div>
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

/** Slim credits. The AI disclosure opens on hover, focus or tap; Esc hides it. */
function Credits() {
  const tipId = useId();
  return (
    <footer className="s-credits" data-testid="simple-footer">
      <span>Data: NASA LRO (PGDA), JPL Horizons</span>
      <span>Not affiliated with NASA</span>
      <span className="s-tipwrap">
        <button type="button" className="s-credits-btn" aria-describedby={tipId} data-testid="simple-ai-disclosure">
          AI disclosure
        </button>
        <span className="s-tip s-tip--up s-tip--wrap" role="tooltip" id={tipId}>
          Claude/Codex helped write code and docs; every number comes from the solver outputs, not AI.
        </span>
      </span>
    </footer>
  );
}

export default function SimpleApp() {
  const loading = usePolaris((s) => s.loading);
  const loadError = usePolaris((s) => s.loadError);
  const sidecar = usePolaris((s) => s.certaintySidecar);
  const v = useView();
  // the certainty sidecar has rows for the site on screen
  const reading = !!(v && sidecar?.sites?.[v.dataset.siteId]);
  const [gl] = useState(webglAvailable);
  // render quality tier, picked once at start (display only; simple/quality.ts)
  const [quality] = useState(() => pickQuality(location.search));
  const [banner, setBanner] = useState(() => !bannerDismissed());
  const [menu, setMenu] = useState(false); // phones: the "more" menu in the top row
  const [sheet, setSheet] = useState(false); // phones: the answer sheet, collapsed to its verdict or open
  const shellRef = useRef<HTMLDivElement>(null);
  const menuBtn = useRef<HTMLButtonElement>(null);
  const handle = useRef<HTMLButtonElement>(null);
  const [dock, setDock] = useState<HTMLDivElement | null>(null);
  const [bottom, setBottom] = useState<HTMLDivElement | null>(null);
  const [statsEl, setStatsEl] = useState<HTMLElement | null>(null);
  const menuId = useId();
  const dockId = useId();

  useEffect(() => {
    startUrlSync();
    coldLaunch();
    loadCertaintySidecar();
    useCamera.getState().request('approach');
    // fetch the post-effects chunk while the bundle loads, so the first frames already use it
    if (quality.tier !== 'low') void import('./simple/SimplePost');
  }, [quality]);

  // the clock slot's height, and how much of the phone sheet shows when collapsed (down to the end of the verdict)
  useShellVar(bottom, '--s-clock-h', (el) => el.offsetHeight);
  useShellVar(statsEl, '--s-stats-h', (el) => el.offsetHeight);
  useShellVar(
    dock,
    '--s-peek',
    (el) => {
      // the verdict, or in its place the note that says why there is no answer
      const last = el.querySelector('.pa-verdict, .s-answer > .s-note') ?? el.querySelector('.s-question') ?? el.querySelector('.s-sheet-handle');
      return last ? last.getBoundingClientRect().bottom - el.getBoundingClientRect().top + 14 : 0;
    },
    '.s-answerpanel',
  );

  // phones: a collapsed sheet keeps its scroll offset (overflow: hidden), so go back to the top or the verdict would be hidden
  useEffect(() => {
    if (!sheet && dock) dock.scrollTop = 0;
  }, [sheet, dock]);

  // Esc closes whatever is open, innermost first: tooltip, menu, disclosure, sheet
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      const shell = shellRef.current;
      if (!shell) return;
      const tip = (document.activeElement as HTMLElement | null)?.closest<HTMLElement>('.s-tipwrap') ?? shell.querySelector<HTMLElement>('.s-tipwrap:hover');
      if (tip && !tip.hasAttribute('data-dismissed')) {
        tip.setAttribute('data-dismissed', '');
        const clear = () => tip.removeAttribute('data-dismissed');
        tip.addEventListener('focusout', clear, { once: true });
        tip.addEventListener('pointerleave', clear, { once: true });
        return;
      }
      if (menu) {
        setMenu(false);
        menuBtn.current?.focus();
        return;
      }
      // one disclosure per press: the one holding focus, else the last one open
      const open = [...shell.querySelectorAll<HTMLDetailsElement>('details[open]')];
      const d = open.find((x) => x.contains(document.activeElement)) ?? open[open.length - 1];
      if (d) {
        const inside = d.contains(document.activeElement);
        d.open = false;
        if (inside) d.querySelector('summary')?.focus();
        return;
      }
      if (sheet) {
        setSheet(false);
        handle.current?.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [menu, sheet]);

  // the phone menu closes on a press anywhere outside it
  useEffect(() => {
    if (!menu) return;
    const onDown = (e: PointerEvent) => {
      const t = e.target as Node;
      if (!document.getElementById(menuId)?.contains(t) && !menuBtn.current?.contains(t)) setMenu(false);
    };
    window.addEventListener('pointerdown', onDown);
    return () => window.removeEventListener('pointerdown', onDown);
  }, [menu, menuId]);

  // Phone sheet: the handle follows the finger; a short flick or a drag past a third of the travel opens or closes it.
  const drag = useRef<{ y: number; t: number; from: number; travel: number; moved: boolean } | null>(null);
  const onHandleDown = (e: ReactPointerEvent<HTMLButtonElement>) => {
    if (!dock || !e.isPrimary || !matchMedia(PHONE).matches) return;
    const peek = parseFloat(shellRef.current?.style.getPropertyValue('--s-peek') || '0');
    const travel = Math.max(0, dock.offsetHeight - peek);
    drag.current = { y: e.clientY, t: performance.now(), from: sheet ? 0 : travel, travel, moved: false };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onHandleMove = (e: ReactPointerEvent<HTMLButtonElement>) => {
    const d = drag.current;
    if (!d || !dock) return;
    const dy = e.clientY - d.y;
    if (!d.moved && Math.abs(dy) < 6) return;
    d.moved = true;
    const raw = d.from + dy;
    // past either end the sheet keeps moving, but less and less
    const y = raw < 0 ? raw * 0.2 : raw > d.travel ? d.travel + (raw - d.travel) * 0.2 : raw;
    dock.style.transition = 'none';
    dock.style.transform = `translateY(${y}px)`;
  };
  const onHandleUp = (e: ReactPointerEvent<HTMLButtonElement>) => {
    const d = drag.current;
    if (!d || !dock) return;
    dock.style.transition = '';
    dock.style.transform = '';
    if (d.moved) {
      const dy = e.clientY - d.y;
      const speed = Math.abs(dy) / Math.max(1, performance.now() - d.t);
      const far = Math.abs(dy) > d.travel / 3 || speed > 0.11;
      setSheet(far ? dy < 0 : sheet);
    }
    // a drag ends in a click on the handle too: let that click through only when the finger did not move
    window.setTimeout(() => (drag.current = null), 0);
  };

  const siteMissing = !!v && sidecar !== null && !reading;

  return (
    <div className="simple s-shell" data-testid="simple-mode" data-banner={banner ? 'on' : 'off'} data-sheet={sheet ? 'open' : 'closed'} data-ready={v ? 'true' : 'false'} ref={shellRef}>
      <a className="skip" href="#simple-main">
        Skip to content
      </a>

      <header className="s-chrome">
        <span className="s-brand">POLARIS X</span>
        <SiteSelect />
        {v && <MastStepper v={v} />}
        <span className="s-spacer" />
        <button
          type="button"
          className="s-btn s-btn--sm s-btn--icon s-btn--quiet s-menu-btn"
          aria-label="More"
          aria-expanded={menu}
          aria-controls={menuId}
          data-testid="simple-menu"
          ref={menuBtn}
          onClick={() => setMenu((m) => !m)}
        >
          {menu ? <IconClose /> : <IconMenu />}
        </button>
        <nav className="s-more" id={menuId} data-open={menu} aria-label="Pages and modes">
          <a className="s-btn s-btn--sm s-btn--quiet" href={DECISION_HREF} data-testid="simple-open-decision" title="Opens in Expert mode for now">
            Decision
          </a>
          <a className="s-btn s-btn--sm s-btn--quiet" href={EVIDENCE_HREF} data-testid="simple-open-evidence" title="Opens in Expert mode for now">
            Evidence
          </a>
          <SoundControl />
          <button type="button" className="s-btn s-btn--sm" data-testid="mode-expert" onClick={() => switchMode('expert')}>
            Expert mode
          </button>
        </nav>
      </header>

      {banner && (
        <div className="s-banner" role="note" data-testid="simple-banner">
          <span>The demo video shows Expert mode — switch anytime.</span>
          <button type="button" className="s-btn s-btn--sm" data-testid="mode-expert-banner" onClick={() => switchMode('expert')}>
            Switch to Expert mode
            <IconArrow />
          </button>
          <button
            type="button"
            className="s-btn s-btn--sm s-btn--icon s-btn--quiet s-banner-close"
            aria-label="Dismiss this note"
            data-testid="simple-banner-dismiss"
            onClick={() => {
              try {
                window.sessionStorage.setItem(BANNER_KEY, '1');
              } catch {
                /* storage blocked: the note is still dismissed until the next load */
              }
              setBanner(false);
            }}
          >
            <IconClose />
          </button>
        </div>
      )}

      <main id="simple-main" tabIndex={-1} className="s-main">
        {(loading || loadError) && (
          <div className="s-status">
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
          </div>
        )}
        {v && (
          <>
            <div
              className="s-dock"
              id={dockId}
              ref={setDock}
              onFocus={(e) => {
                // phones: tabbing into the part of the sheet that is off screen opens it
                if (!sheet && (e.target as Element) !== handle.current && matchMedia(PHONE).matches && (e.target as Element).matches(':focus-visible')) setSheet(true);
              }}
            >
              <button
                type="button"
                className="s-sheet-handle"
                aria-expanded={sheet}
                aria-controls={dockId}
                aria-label={sheet ? 'Collapse the answer' : 'Show the full answer and numbers'}
                data-testid="simple-sheet-handle"
                ref={handle}
                onPointerDown={onHandleDown}
                onPointerMove={onHandleMove}
                onPointerUp={onHandleUp}
                onPointerCancel={onHandleUp}
                onClick={() => {
                  if (!drag.current?.moved) setSheet((s) => !s);
                }}
              >
                <i aria-hidden="true" />
              </button>
              <section className="s-panel s-answerpanel" aria-labelledby="s-site-h" data-sight-avoid="left">
                <h1 id="s-site-h" data-testid="simple-site">
                  {v.dataset.site.name}
                </h1>
                <p className="s-question">Does a lander here keep the Sun?</p>
                <div className="s-answer" data-testid="simple-answer">
                  {sidecar === null ? (
                    <p className="s-note">The certainty sidecar has not loaded, so no answer is shown. Nothing is substituted.</p>
                  ) : siteMissing ? (
                    <p className="s-note" data-testid="simple-no-site">
                      The certainty sidecar has no rows for this site, so no answer is shown. Nothing is substituted.
                    </p>
                  ) : (
                    <PlainAnswer v={v} />
                  )}
                </div>
                <MastPicker v={v} />
              </section>
              <section className="s-panel s-statspanel" aria-label="Numbers at this mast height, and their limits" data-sight-avoid="right" ref={setStatsEl}>
                <Stats v={v} />
                <details className="s-limits" data-testid="simple-limits">
                  <summary>What this cannot say</summary>
                  <ul>
                    <li>It is geometric line of sight only: whether the centre of the Sun or Earth clears the terrain skyline.</li>
                    <li>It is not solar power: no panel, dust, thermal or battery model.</li>
                    <li>It is not communications: no radio link, antenna or Deep Space Network schedule.</li>
                    <li>It is not validated: the numbers have not been independently checked against another solver or flight data.</li>
                  </ul>
                </details>
              </section>
              <Credits />
            </div>

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

            {/* Mission clock slot. S5 rebuilds the clock; until then the existing TimeBar works here unchanged. */}
            <div className="s-bottom" data-slot="mission-clock" ref={setBottom}>
              <div className="s-clock">
                <TimeBar v={v} />
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
