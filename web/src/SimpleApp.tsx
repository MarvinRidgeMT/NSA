import { Component, lazy, Suspense, useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode } from 'react';
import { usePolaris } from './store/store';
import { useUi } from './store/ui';
import { fmtUtc, useView, type View } from './store/view';
import { reducedMotion, useCamera } from './store/camera';
import { startUrlSync } from './store/urlState';
import { markSiteChosen } from './store/siteDefaults';
import { coldLaunch, loadCertaintySidecar } from './App';
import { PlainAnswer, verdictWord } from './components/PlainAnswer';
import { fmtPctRange, mastScenarioId, useChooseMast, useMastReading } from './components/MastInstrument';
import { TimeBar } from './components/TimeBar';
import { switchMode } from './mode';
import { pickQuality, QUALITY_NOTE } from './simple/quality';
import { GLOBE_8K, GLOBE_NAV, globePlan, moonDir, pinReading, skyDirFromSite, type CurveRow } from './simple/globeMath';
import type { GlobeSite } from './simple/Globe';
import { Intro } from './simple/Intro';
import { lightCaption } from './simple/introMath';
import { newIntroLink, useMoonLoad } from './simple/introState';
import { IconArrow, IconBack, IconChevronDown, IconChevronUp, IconClose, IconMenu, SoundControl } from './simple/parts';
import { SceneCard, SceneObjectList, useObjectCard } from './simple/SceneCards';
import { useSceneFocus } from './simple/sceneFocus';
import { matchDistanceM } from './simple/spotCheck';
import { ANYSITE_CREDIT } from './simple/anySite';
const Scene3D = lazy(() => import('./three/Scene3D'));
const Globe = lazy(() => import('./simple/Globe'));

/**
 * Simple mode shell (S2, 17 Nov 2026): light chrome over a full-screen 3D scene. The scene fills the window; the top bar, the
 * answer panel, the numbers panel, the mission-clock slot and the credits strip are laid over it and leave the site clear.
 * Under 640 px the two panels become one bottom sheet. Every number shown is read from the bundle or the certainty sidecar.
 *
 * S4 (17 Nov 2026): a visitor first sees the Moon from over its south pole (simple/Globe.tsx) with the bundle's sites as pins.
 * Picking one flies down to that site's terrain view, which is the S2 shell above; "Back to the Moon" returns. A link that
 * names a site (?site=) or asks for the terrain (?view=terrain) opens the terrain view directly.
 *
 * S3 (17 Nov 2026): every visit that opens on the globe starts with the opening sequence, played in the globe's own canvas
 * while the bundle and the Moon model load (simple/Globe.tsx phase 'intro', simple/Intro.tsx). It ends as soon as loading
 * allows; Skip, Esc, Enter or a click ends it sooner. Expert mode never mounts this component, so it never shows there.
 */

/**
 * Opening sequence: 'play' while it runs, 'settle' once the interface is coming in over the last of the camera move, 'done'
 * for a moment after the hand-off (the interface's fade-in finishes), then 'off'.
 */
type IntroState = 'play' | 'settle' | 'done' | 'off';

/** Where the visitor is: on the globe, flying in, at a site's terrain, or flying back out. */
type Place = 'globe' | 'in' | 'site' | 'out';
/**
 * The Moon models are NASA assets kept out of git (.gitignore, docs/DATA_PROVENANCE.md). A build made without one, such as a
 * fresh checkout before the model is fetched, has no globe to draw: Simple mode then opens on the terrain view as it did in S2
 * and offers no "Back to the Moon".
 */
const HAS_GLOBE = __GLOBE_FILES__.length > 0;
function opensOnTerrain(search: string): boolean {
  const p = new URLSearchParams(search);
  return p.has('site') || p.get('view') === 'terrain';
}

/** Evidence and Decision live in Expert mode for now (S9 and S10 bring them in as panels over the scene). */
const EVIDENCE_HREF = '?mode=expert#evidence';
const DECISION_HREF = '?mode=expert#decision';
/** The demo-video banner stays dismissed for this browser session only. */
const BANNER_KEY = 'polaris-x.simple.banner-dismissed';
const PHONE = '(max-width: 639px)';

class Guard extends Component<{ children: ReactNode; onError?: () => void }, { err: string | null }> {
  state = { err: null as string | null };
  componentDidCatch() {
    this.props.onError?.();
  }
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
function MastStepper({ v, hidden = false }: { v: View; hidden?: boolean }) {
  const r = useMastReading(v);
  const choose = useChooseMast(v);
  if (!r) return null;
  const { masts, h } = r;
  const i = masts.indexOf(h);
  const lower = i > 0 ? masts[i - 1] : null;
  const higher = i >= 0 && i < masts.length - 1 ? masts[i + 1] : null;
  return (
    <div className="s-stepper" role="group" aria-label="Mast height, sampled heights only" data-testid="simple-mast-stepper" hidden={hidden}>
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

/** True while the window is phone-sized (the answer lives in a bottom sheet there). */
function usePhone(): boolean {
  const [on, setOn] = useState(() => typeof matchMedia === 'function' && matchMedia(PHONE).matches);
  useEffect(() => {
    if (typeof matchMedia !== 'function') return;
    const m = matchMedia(PHONE);
    const f = () => setOn(m.matches);
    m.addEventListener('change', f);
    return () => m.removeEventListener('change', f);
  }, []);
  return on;
}

/** The S12 card for a ridge, the Sun or the Earth, and the keyboard list of everything clickable. Mounted at a site only. */
function ScenePanel({ v, slot }: { v: View; slot: 'card' | 'list' }) {
  const card = useObjectCard(v);
  if (slot === 'card') return card ? <SceneCard card={card} /> : null;
  return <SceneObjectList v={v} card={card} />;
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
  // S4: the globe comes first, unless the link asks for a site's terrain or there is no WebGL to draw a globe with
  const [place, setPlace] = useState<Place>(() => (gl && HAS_GLOBE && !opensOnTerrain(location.search) ? 'globe' : 'site'));
  // S3: the opening sequence plays on every visit that opens on the globe
  const [intro, setIntro] = useState<IntroState>(place === 'globe' ? 'play' : 'off');
  const introLink = useRef(newIntroLink());
  const introByKey = useRef(false); // the visitor used the keyboard during the sequence: focus goes to the globe at the hand-off
  const moonFrac = useMoonLoad((s) => s.frac);
  const moonFailed = useMoonLoad((s) => s.failed);
  const [globeOn, setGlobeOn] = useState(place === 'globe'); // mounted from its first showing on (paused while at a site)
  const [stageOn, setStageOn] = useState(place === 'site'); // the terrain scene: mounted while at a site and during the flight back
  const [target, setTarget] = useState(0);
  const [cover, setCover] = useState(false);
  const [visited, setVisited] = useState(-1);
  const backBtn = useRef<HTMLButtonElement>(null);
  const byKeyboard = useRef(false);
  const loaded = usePolaris((s) => s.loaded);
  const datasetIdx = usePolaris((s) => s.datasetIdx);
  const mastPick = useUi((s) => s.mastPick);
  const shellRef = useRef<HTMLDivElement>(null);
  const menuBtn = useRef<HTMLButtonElement>(null);
  const handle = useRef<HTMLButtonElement>(null);
  const [dock, setDock] = useState<HTMLDivElement | null>(null);
  const [bottom, setBottom] = useState<HTMLDivElement | null>(null);
  const [statsEl, setStatsEl] = useState<HTMLElement | null>(null);
  const menuId = useId();
  const dockId = useId();
  // S12: the object flown to, and whether the site's answer card is open. One mast control at a time: the card's heights
  // while it is on screen, the top bar's stepper otherwise; both read and write the same state (store/ui mastPick).
  const focus = useSceneFocus((s) => s.focus);
  const siteCard = useSceneFocus((s) => s.siteCard);
  const flying = useSceneFocus((s) => s.flying);
  const phone = usePhone();
  const objectOpen = focus !== null && focus !== 'site';
  const siteShown = !objectOpen && (siteCard || focus === 'site');
  const showAnswer = useRef<HTMLButtonElement>(null);
  const cardClose = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    startUrlSync();
    coldLaunch();
    loadCertaintySidecar();
    useCamera.getState().request('approach');
    // fetch the post-effects chunk while the bundle loads, so the first frames already use it
    if (quality.tier !== 'low') void import('./simple/SimplePost');
  }, [quality]);

  // ---- S3 opening sequence ----
  const playing = intro === 'play' || intro === 'settle';
  const skipIntro = () => {
    introLink.current.skip = true;
  };
  useEffect(() => {
    // through the whole sequence, the last of the camera move included ('settle': the Skip button has gone by then, the keys
    // and a press on the picture still work)
    if (intro !== 'play' && intro !== 'settle') return;
    const onClick = (e: MouseEvent) => {
      // 'play' has its own layer for presses; in 'settle' the interface is back and its controls keep their own jobs
      if (intro === 'settle' && !(e.target as Element | null)?.closest?.('a, button, select, input, summary, details, .s-panel, .s-chrome, .s-banner')) skipIntro();
    };
    window.addEventListener('click', onClick);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Tab' || e.key === 'Escape' || e.key === 'Enter') introByKey.current = true;
      if (e.key !== 'Escape' && e.key !== 'Enter') return;
      // Enter on a control does that control's job (Skip's own job is to skip)
      if (e.key === 'Enter' && (e.target as Element | null)?.closest?.('a, button, select, input, summary')) return;
      skipIntro();
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('click', onClick);
    };
  }, [intro]);
  // nothing to hand over to when the bundle cannot be read: show the error instead
  useEffect(() => {
    if (loadError) setIntro('off');
  }, [loadError]);
  useEffect(() => {
    if (intro !== 'done') return;
    // A keyboard visitor (Tab, Esc or Enter during the sequence) lands on the globe: the pin of the site it opened on. By now the Skip
    // button has unmounted, so focus is on <body> (or still on the intro layer); a control the visitor moved to is left alone.
    // The pins are made visible by the globe's next frames, so this tries for a few frames. Pointer visitors are not focused
    // anywhere (no ring or hover label appears on its own).
    let raf = 0;
    let tries = 0;
    const land = () => {
      const a = document.activeElement;
      if (!introByKey.current || (a && a !== document.body && !a.closest('.s-intro'))) return;
      // the site the visitor is on (the bundle's opening site), not the first pin
      const pin = shellRef.current?.querySelector<HTMLElement>(`[data-testid="globe-pin-${pins[usePolaris.getState().datasetIdx]?.id}"] button`);
      pin?.focus();
      if (document.activeElement !== pin && ++tries < 30) raf = requestAnimationFrame(land);
      else if (document.activeElement !== pin) document.getElementById('simple-main')?.focus();
    };
    land();
    const t = window.setTimeout(() => setIntro('off'), 900);
    return () => {
      window.clearTimeout(t);
      cancelAnimationFrame(raf);
    };
  }, [intro]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- S4 globe: everything it shows is read here from the bundle and the certainty sidecar ----
  const curSeriesMast = v?.series?.observer?.mastM ?? null;
  const pins = useMemo(() => {
    const out: (GlobeSite & { n: number | null })[] = [];
    for (const [i, d] of (loaded?.bundle.datasets ?? []).entries()) {
      const seriesMast = i === datasetIdx ? curSeriesMast : (d.derived?.scenarios.find((x) => x.samples)?.observer?.mastM ?? null);
      const r = pinReading(sidecar?.sites?.[d.siteId], mastPick, seriesMast);
      const sun = r?.sun;
      const line = !sidecar
        ? 'No answer yet: the certainty sidecar has not loaded'
        : !r
          ? 'No answer: the certainty sidecar has no rows for this site'
          : !sun
            ? `No answer at a ${r.mastM} m mast: this site was not sampled at that height`
            : `${verdictWord(sun.min, r.all100)}. Sun in sight ${fmtPctRange(sun)} at a ${r.mastM} m mast`;
      const spread = r?.spreadPts ?? null;
      // the Sun + Earth row at the same mast (the row the terrain view's numbers panel shows)
      const both = r ? (sidecar?.sites?.[d.siteId]?.certainty_curve as CurveRow[] | undefined)?.find((x) => x.mast_m === r.mastM && x.metric === 'both_centre_pct') : undefined;
      out.push({
        idx: i,
        id: d.siteId,
        name: d.site.name,
        dir: moonDir(d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg),
        line,
        spreadPts: spread,
        spreadText: sun && spread !== null ? (spread === 0 ? `all ${sun.n_clones} terrain variants agree` : `${sun.n_clones} terrain variants differ by ${spread.toFixed(1)} points`) : '',
        n: sun?.n_clones ?? null,
        // S13: the same sidecar rows as words for "Check a spot", with the site's bundle coordinates
        spot: {
          id: d.siteId,
          name: d.site.name,
          lat: d.site.latitudePlanetocentricDeg,
          lon: d.site.longitudeEastDeg,
          result: r && sun ? { verdict: verdictWord(sun.min, r.all100), sun: fmtPctRange(sun), both: both ? fmtPctRange(both) : null, mastM: r.mastM, variants: sun.n_clones } : null,
          why: line,
        },
        mastM: r?.mastM ?? null,
      });
    }
    return out;
  }, [loaded, datasetIdx, curSeriesMast, sidecar, mastPick]);
  // S13: how close a typed point must be to a computed site (from the bundle's own position steps), and the window our
  // results cover (the bundle's first and last sample)
  const spotMatch = useMemo(() => {
    const m = matchDistanceM(loaded?.bundle.datasets.flatMap((d) => d.derived?.scenarios ?? []));
    return m && loaded ? { ...m, file: loaded.name } : null; // the card names the file the step was read from
  }, [loaded]);
  const spotWindow = useMemo(() => {
    const samples = loaded?.bundle.datasets[0]?.ephemeris.samples;
    if (!samples?.length) return null;
    const day = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
    // the window's length is worked out from the same two samples, not typed in
    const days = (Date.parse(samples[samples.length - 1].time) - Date.parse(samples[0].time)) / 86_400_000;
    return `the ${Number.isInteger(days) ? days : days.toFixed(1)} days from ${day.format(new Date(samples[0].time))} to ${day.format(new Date(samples[samples.length - 1].time))} (UTC)`;
  }, [loaded]);
  const variants = pins.find((p) => p.n !== null)?.n ?? null;
  const legend = `how much the ${variants ?? ''} terrain variants disagree (Sun in sight, max − min) at the mast height picked in the top bar. A still amber pin means they all agree; a grey pin has no sidecar answer at that height.`.replace('the  terrain', 'the terrain');
  const site = v?.dataset.site;
  const sunAz = v?.sun.az;
  const sunEl = v?.sun.el;
  const earthAz = v?.earth.az;
  const earthEl = v?.earth.el;
  const lat = site?.latitudePlanetocentricDeg;
  const lon = site?.longitudeEastDeg;
  const sunDir = useMemo(() => (lat !== undefined && lon !== undefined && sunAz !== undefined && sunEl !== undefined ? skyDirFromSite(lat, lon, sunAz, sunEl) : null), [lat, lon, sunAz, sunEl]);
  const earthDir = useMemo(() => (lat !== undefined && lon !== undefined && earthAz !== undefined && earthEl !== undefined ? skyDirFromSite(lat, lon, earthAz, earthEl) : null), [lat, lon, earthAz, earthEl]);
  // which Moon model this device draws first and which it brings in after (globeMath.globePlan); ?globe=compact keeps the
  // compact one, for measurements. `moonFile` is the one on screen now.
  const moonPlan = useMemo(() => globePlan(__GLOBE_FILES__, quality.tier === 'low', new URLSearchParams(location.search).get('globe')), [quality]);
  const [moonFile, setMoonFile] = useState(moonPlan.first);
  const about = v
    ? (moonFile === GLOBE_8K
        ? `Moon: NASA SVS / LRO model with relief in its mesh and its LROC albedo image. VISUAL: display only, never sampled by a calculation; the relief is drawn taller than the real Moon's and its shading is not a shadow calculation. `
        : `Moon: NASA SVS / LRO compact model (SVS 14959) with its LROC albedo image. VISUAL: display only, never sampled by a calculation; the source notes artifacts near the poles of this model. `) +
      `It is turned to true lunar axes, south pole toward you. ` +
      `Light: the Sun direction in the bundle at ${fmtUtc(v.utcMs)} (azimuth ${v.sun.az.toFixed(1)}°, elevation ${v.sun.el.toFixed(2)}° at ${v.dataset.site.name}). Brightness and the faint earthshine are display choices, and this shading never decides visible or blocked. ` +
      `Pins: each line ends at the site's bundle latitude and longitude; the pins stand apart from it so they can be read and pressed. The slow drift is a display motion. ` +
      `You can turn the Moon by dragging and zoom with the wheel or a pinch; the zoom stops where one pixel of this Moon image would be drawn larger than ${GLOBE_NAV.MAX_TEXEL_CSS_PX} screen pixels, and "Back to south pole" returns to the sites. ` +
      `Quality: ${QUALITY_NOTE[quality.tier].replace('bloom, flare and grain off; the Sun keeps a plain glow', 'lighter Moon image, camera effects off').replace('camera effects on', 'film grain on, a camera effect')}. The Sun itself is outside this view, so there is no glow or flare here. ` +
      `Check a spot: a click is placed on a smooth sphere at the pins' radius, not on the drawn relief, and only supplies coordinates; the values come from the files. ` +
      `${ANYSITE_CREDIT}: the nearest-computed-point answers and slope in Check a spot, and Earth in sight and longest Sun gap on the pin cards. SOURCE-BASED · UNVALIDATED. ` +
      `Opening sequence: the same Moon and the same Sun direction, seen first from the night side; its glare, lens flare and colour fringing are camera effects, display only, and stop before this view.`
    : '';

  const pickSite = (i: number) => {
    const st = usePolaris.getState();
    const lb = st.loaded;
    if (!lb || place !== 'globe') return;
    markSiteChosen();
    if (i !== st.datasetIdx) {
      st.setSite(i);
      // keep the mast picked on the globe when this site was sampled there (and its bundle series, when it has one)
      const pick = useUi.getState().mastPick;
      if (pick !== null) {
        const ds = lb.bundle.datasets[i];
        if (!sidecar?.sites?.[ds.siteId]?.sampled_masts_m.includes(pick)) useUi.getState().set({ mastPick: null });
        else {
          const id = mastScenarioId(ds.derived?.scenarios, pick);
          if (id) usePolaris.getState().setScenario(id);
        }
      }
    }
    useCamera.getState().request('approach');
    byKeyboard.current = !!document.activeElement?.matches(':focus-visible');
    setTarget(i);
    setVisited(i);
    setCover(true);
    if (reducedMotion()) {
      setStageOn(true);
      setPlace('site');
    } else setPlace('in');
  };
  const backToMoon = () => {
    byKeyboard.current = !!document.activeElement?.matches(':focus-visible');
    setTarget(usePolaris.getState().datasetIdx);
    setVisited(usePolaris.getState().datasetIdx);
    // no flight when the globe has not been drawn yet (the page was opened on a site) or motion is reduced
    setPlace(globeOn && !reducedMotion() ? 'out' : 'globe');
    setGlobeOn(true);
    setMenu(false);
  };
  // keyboard users keep their place: on arrival the way back has focus, and on return the pin they left from
  const prevPlace = useRef(place);
  useEffect(() => {
    const was = prevPlace.current;
    prevPlace.current = place;
    if (was === place || !byKeyboard.current) return;
    if (place === 'site') focusBack.current = true; // the button mounts with the terrain scene, one render later
    else if (place === 'globe') shellRef.current?.querySelector<HTMLElement>(`[data-testid="globe-pin-${pins[target]?.id}"] button`)?.focus();
  }, [place]); // eslint-disable-line react-hooks/exhaustive-deps
  const focusBack = useRef(false);
  useEffect(() => {
    if (place === 'site' && stageOn && focusBack.current) {
      focusBack.current = false;
      backBtn.current?.focus();
    }
  }, [place, stageOn]);
  // fetch the terrain scene's code while the visitor looks at the globe, so the fly-in does not wait for it
  useEffect(() => {
    if (place !== 'globe' || playing) return; // not during the opening sequence: its frames come first
    const t = window.setTimeout(() => void import('./three/Scene3D'), 1500);
    return () => window.clearTimeout(t);
  }, [place, playing]);
  const onSite = place === 'site';
  // The terrain scene is built on arrival, not during the dive (building it takes the main thread for a few hundred
  // milliseconds, which would stutter the flight). Until its canvas has drawn, the globe layer stays up as plain black.
  // Back on the globe the terrain scene is unmounted again, so its WebGL context, terrain and images are not kept in memory
  // behind the Moon; the next fly-in rebuilds it under the same black cover.
  useEffect(() => {
    if (place === 'site') setStageOn(true);
    else if (place === 'globe') setStageOn(false);
  }, [place]);
  useEffect(() => {
    if (!onSite || !cover) return;
    let raf = 0;
    let seen = 0;
    const t0 = performance.now();
    const tick = () => {
      if (shellRef.current?.querySelector('.simple-stage canvas')) seen++;
      if (seen >= 3 || performance.now() - t0 > 4000) setCover(false);
      else raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [onSite, cover]);

  // the clock slot's height, and how much of the phone sheet shows when collapsed (down to the end of the verdict)
  useShellVar(bottom, '--s-clock-h', (el) => el.offsetHeight);
  useShellVar(statsEl, '--s-stats-h', (el) => el.offsetHeight);
  useShellVar(
    dock,
    '--s-peek',
    (el) => {
      // the verdict, or in its place the note that says why there is no answer
      const last = el.querySelector('.pa-verdict, .s-answer > .s-note, .s-cardslot [data-fact="state"], .s-cardslot [data-fact="distance"]') ?? el.querySelector('.s-question') ?? el.querySelector('.s-sheet-handle');
      return last ? last.getBoundingClientRect().bottom - el.getBoundingClientRect().top + 14 : 0;
    },
    '.s-answerpanel, .s-cardslot',
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
        return;
      }
      // S12: an object flown to comes before that: Esc returns the camera to where it was
      if (useSceneFocus.getState().focus !== null) {
        useSceneFocus.getState().back();
        return;
      }
      // S4: with nothing left to close, Esc at a site goes back to the Moon (same as the button)
      if (backBtn.current) backBtn.current.click();
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
    <div className="simple s-shell" data-testid="simple-mode" data-banner={banner ? 'on' : 'off'} data-sheet={sheet ? 'open' : 'closed'} data-ready={v ? 'true' : 'false'} data-place={place} data-intro={intro === 'off' ? undefined : intro} data-focus={onSite ? (focus ?? undefined) : undefined} data-fly={onSite ? (flying ?? undefined) : undefined} ref={shellRef}>
      <a className="skip" href="#simple-main">
        Skip to content
      </a>

      <header className="s-chrome">
        <span className="s-brand">POLARIS X</span>
        {onSite && <SiteSelect />}
        {v && <MastStepper v={v} hidden={onSite && siteShown && (!phone || sheet)} />}
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
        {gl && globeOn && (
          <Guard onError={() => setIntro('off')}>
            <Suspense fallback={null}>
              <Globe
                file={moonPlan.first}
                upgrade={moonPlan.then}
                onModel={setMoonFile}
                sites={pins}
                sunDir={sunDir}
                earthDir={earthDir}
                tier={quality.tier}
                phase={place === 'globe' ? (playing ? 'intro' : 'idle') : place === 'site' ? 'hidden' : place}
                intro={introLink}
                onIntroSettle={() => setIntro((s) => (s === 'play' ? 'settle' : s))}
                onIntroEnd={() => setIntro((s) => (s === 'play' || s === 'settle' ? 'done' : s))}
                target={target}
                cover={cover}
                visited={visited}
                legend={legend}
                about={about}
                spotMatch={spotMatch}
                spotWindow={spotWindow}
                topMastM={pins[datasetIdx]?.mastM ?? null}
                onPick={pickSite}
                onArrive={() => setPlace((p) => (p === 'in' ? 'site' : p))}
                onBack={() => setPlace((p) => (p === 'out' ? 'globe' : p))}
              />
            </Suspense>
          </Guard>
        )}
        {playing && (
          <Intro
            parts={{ bundle: !!loaded, sidecar: sidecar !== null, moon: moonFrac, moonFailed }}
            lightLine={v ? lightCaption(v.utcMs, v.sun.az, v.dataset.site.name) : null}
            leaving={intro === 'settle'}
            onSkip={skipIntro}
          />
        )}
        {!onSite && <Credits />}
        {v && stageOn && (
          <>
            {onSite && (
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
              <ScenePanel v={v} slot="card" />
              {siteShown && (
              <section className="s-panel s-answerpanel" aria-labelledby="s-site-h" data-sight-avoid="left" data-testid="site-card" data-flown={focus === 'site' || undefined}>
                <div className="s-sitecard-head">
                  <h1 id="s-site-h" data-testid="simple-site">
                    {v.dataset.site.name}
                  </h1>
                  {/* closing the card clears the view; the mast stepper takes its place in the top bar */}
                  <button
                    type="button"
                    className="s-btn s-btn--sm s-btn--icon s-btn--quiet s-sitecard-close"
                    aria-label="Close the answer card"
                    data-testid="site-card-close"
                    ref={cardClose}
                    onClick={(e) => {
                      const keys = e.detail === 0 || e.currentTarget.matches(':focus-visible');
                      useSceneFocus.getState().back();
                      useSceneFocus.getState().setSiteCard(false);
                      if (keys) requestAnimationFrame(() => showAnswer.current?.focus());
                    }}
                  >
                    <IconClose />
                  </button>
                </div>
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
                {focus === 'site' && (
                  <div className="s-sitecard-foot">
                    <button type="button" className="s-btn s-btn--sm" data-testid="site-card-back" onClick={() => useSceneFocus.getState().back()}>
                      <IconBack />
                      Back
                    </button>
                  </div>
                )}
              </section>
              )}
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
            )}

            <section className="stage simple-stage" aria-label="3D view of the site (Approach camera)">
              {/* the way back to the globe: over the scene, top centre, between the two panels */}
              {onSite && gl && HAS_GLOBE && (
                <button type="button" className="s-btn s-btn--sm s-back" data-testid="simple-back-moon" ref={backBtn} onClick={backToMoon}>
                  <IconBack />
                  Back to the Moon
                </button>
              )}
              {/* S12: the answer card can be closed for a clear view; this brings it back */}
              {onSite && !siteShown && !objectOpen && (
                <button
                  type="button"
                  className="s-btn s-btn--sm s-show-answer"
                  data-testid="simple-show-answer"
                  ref={showAnswer}
                  onClick={(e) => {
                    const keys = e.detail === 0 || e.currentTarget.matches(':focus-visible');
                    useSceneFocus.getState().setSiteCard(true);
                    if (keys) requestAnimationFrame(() => cardClose.current?.focus());
                  }}
                >
                  Show the answer
                </button>
              )}
              {onSite && gl && <ScenePanel v={v} slot="list" />}
              {gl ? (
                <Guard>
                  <Suspense fallback={<p className="note">Loading 3D…</p>}>
                    <Scene3D v={v} active={onSite} post={quality.tier} pick />
                  </Suspense>
                </Guard>
              ) : (
                <p className="error" role="alert">
                  WebGL is not available in this browser, so the 3D view is off. The answer and numbers are unaffected.
                </p>
              )}
            </section>

            {/* Mission clock slot. S5 rebuilds the clock; until then the existing TimeBar works here unchanged. */}
            {onSite && (
              <div className="s-bottom" data-slot="mission-clock" ref={setBottom}>
                <div className="s-clock">
                  <TimeBar v={v} />
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
