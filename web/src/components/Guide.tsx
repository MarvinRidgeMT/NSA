import { useEffect, useRef, useState } from 'react';
import { usePolaris } from '../store/store';
import { fmtUtc, useView, type View } from '../store/view';
import { useUi } from '../store/ui';
import { reducedMotion, useCamera, type CameraViewId } from '../store/camera';
import { ridgeBins, fmtRidgeDistance } from '../bundle/evidence';
import { firstBlockedRun, ridgesOfRecord } from '../bundle/ridgeSeek';
import { useCoverageSidecar } from '../bundle/coverageSidecar';
import type { Scenario } from '../bundle/types';

/**
 * Guided demonstration (five scenes). Every scene drives the SAME live state as the rest of the product (route, clock,
 * camera, mast, ridge selection) and every sentence is filled from the loaded bundle and the sidecars. Nothing is
 * pre-recorded; a missing value shows "—". Esc or "Exit" closes it at any time.
 */
const HERO_SITE = 'site04_roi3';
type Row = { mast_m: number; metric: string; min: number; max: number; nominal: number; pass: string; n_clones: number };
const pct = (x?: number) => (x === undefined || !Number.isFinite(x) ? '—' : `${x.toFixed(1)} %`);
const rng = (r?: Row) => (!r ? '—' : r.min === r.max ? pct(r.min) : `${r.min.toFixed(1)}–${r.max.toFixed(1)} %`);
const mastOf = (sc: Scenario) => (sc.id === 'baseline' || /mast/.test(`${sc.kind ?? ''}${sc.family ?? ''}`) ? sc.observer?.mastM : undefined);

export const GUIDE_STEPS = ['The lunar environment', 'Ridge of Record', 'Certainty Height', 'Coverage', 'The decision'] as const;

/** Seconds each scene stays up when the demo plays on its own (Play / Pause). Manual stepping is the default. */
export const GUIDE_DWELL_MS = 12_000;

type Route = 'sky' | 'decision' | 'evidence' | 'story';
/** Everything the demo changes, captured when it opens and put back exactly when it is exited (Exit, Esc, Finish). */
interface Snapshot {
  route: Route;
  bundle: { name: string; origin: string } | null;
  datasetIdx: number;
  scenarioId: string | null;
  utcMs: number | null;
  selectedBin: number | null;
  selectedFailureId: string | null;
  mastPick: number | null;
  run: ReturnType<typeof useUi.getState>['run'];
  returnTo: ReturnType<typeof useUi.getState>['returnTo'];
  view: CameraViewId;
}
const routeNow = (): Route => {
  // same rule as App's fromHash: no hash = the story, unless a bundle was deep-linked
  const h = location.hash.replace('#', '');
  if (h === 'decision' || h === 'evidence' || h === 'story' || h === 'sky') return h;
  return new URLSearchParams(location.search).has('bundle') ? 'sky' : 'story';
};
function capture(): Snapshot {
  const p = usePolaris.getState();
  const u = useUi.getState();
  return {
    route: routeNow(),
    bundle: p.loaded ? { name: p.loaded.name, origin: p.loaded.origin } : null,
    datasetIdx: p.datasetIdx,
    scenarioId: p.scenarioId,
    utcMs: p.utcMs,
    selectedBin: p.selectedBin,
    selectedFailureId: p.selectedFailureId,
    mastPick: u.mastPick,
    run: u.run,
    returnTo: u.returnTo,
    view: useCamera.getState().view,
  };
}
async function restore(s: Snapshot, go: (r: Route) => void) {
  const p = usePolaris.getState();
  // The demo may have loaded the hero bundle. Reload the previous one only if it came from the bundle folder; a bundle the user
  // opened from disk cannot be re-read without asking again, so the hero stays and the rest of the state is restored around it.
  if (s.bundle && p.loaded?.name !== s.bundle.name && p.index.some((b) => b.file === s.bundle!.name))
    await p.loadFromUrl(`bundles/${s.bundle.name}`, s.bundle.name, s.bundle.origin);
  const now = usePolaris.getState();
  if (s.bundle && now.loaded?.name === s.bundle.name && s.datasetIdx < now.loaded.bundle.datasets.length)
    usePolaris.setState({
      datasetIdx: s.datasetIdx,
      scenarioId: s.scenarioId,
      utcMs: s.utcMs,
      selectedBin: s.selectedBin,
      selectedFailureId: s.selectedFailureId,
      timeError: null,
      timeNote: null,
      playing: false,
    });
  useUi.getState().set({ mastPick: s.mastPick, run: s.run, returnTo: s.returnTo });
  useCamera.getState().request(s.view);
  go(s.route);
}

function useHeroLoaded(active: boolean) {
  const loaded = usePolaris((s) => s.loaded);
  const datasetIdx = usePolaris((s) => s.datasetIdx);
  useEffect(() => {
    if (!active) return;
    const st = usePolaris.getState();
    const ds = st.loaded?.bundle.datasets[datasetIdx];
    if (ds?.siteId === HERO_SITE && ds.dem) return;
    const i = st.loaded?.bundle.datasets.findIndex((d) => d.siteId === HERO_SITE && d.dem) ?? -1;
    if (i >= 0) return void st.setSite(i);
    const hero = st.index.find((b) => /^polaris-x5d-roi-.*\.json$/.test(b.file));
    if (hero)
      void st.loadFromUrl(`bundles/${hero.file}`, hero.file, hero.origin).then(() => {
        const s2 = usePolaris.getState();
        const j = s2.loaded?.bundle.datasets.findIndex((d) => d.siteId === HERO_SITE) ?? -1;
        if (j > 0) s2.setSite(j);
      });
  }, [active, loaded, datasetIdx]);
}

function sceneText(step: number, v: View | null, side: ReturnType<typeof usePolaris.getState>['certaintySidecar'], cov: ReturnType<typeof useCoverageSidecar>) {
  const site = side?.sites?.[HERO_SITE];
  const rows = (site?.certainty_curve as Row[] | undefined) ?? [];
  const at = (m: number, k: string) => rows.find((r) => r.mast_m === m && r.metric === k);
  const cert = site?.all_maps_100pct_sun_mast_m ?? null;
  const c = cov?.sites[HERO_SITE];
  if (!v) return { title: 'Loading the site…', body: '' };
  const ds = v.dataset;
  if (step === 0)
    return {
      title: 'Shackleton Rim, the lunar south pole',
      body: `Real NASA PGDA 78 terrain around ${ds.site.name} (${Math.abs(ds.site.latitudePlanetocentricDeg).toFixed(5)}° S, ${Math.abs(ds.site.longitudeEastDeg).toFixed(5)}° W): a ${ds.dem ? `${(((ds.dem.n - 1) * ds.dem.spacing) / 1000).toFixed(0)} km crop at ${ds.dem.spacing} m` : 'skyline-only'} model, true scale. Window ${fmtUtc(v.times[0]).slice(0, 10)} → ${fmtUtc(v.times[v.times.length - 1]).slice(0, 10)}, hourly, mast ${v.series?.observer?.mastM ?? '—'} m. Question: does a lander here keep the Sun, and how sure can we be?`,
    };
  if (step === 1) {
    const rr = ridgesOfRecord(v).find((x) => x.target === 'sun');
    if (!rr) return { title: 'Ridge of Record', body: 'This bundle attributes no Sun loss to any ridge.' };
    const run = firstBlockedRun(v, rr.ridge, 'sun');
    const r = rr.ridge;
    return {
      title: `Ridge of Record · ${r.label ?? r.id}`,
      body: `${run ? `From ${fmtUtc(v.times[run.i0]).slice(5, 16).replace('T', ' ')} UTC the Sun is behind ${r.label ?? r.id} for ${run.i1 - run.i0 + 1} hourly samples. ` : ''}It is a rise ${r.reliefM !== undefined ? `${r.reliefM.toFixed(2)} m above the site ground` : ''}, ${fmtRidgeDistance(r)} away, bearing ${r.azimuthDeg[0].toFixed(0)}–${r.azimuthDeg[1].toFixed(0)}°, in the 5 m local DEM. The bundle attributes ${r.hours.sun.lost} Sun-blocked hourly samples to it. With the Sun about a degree up, a rise this small and this close is enough.`,
    };
  }
  if (step === 2) {
    const s1 = at(1, 'sun_centre_pct');
    const sc = cert !== null ? at(cert, 'sun_centre_pct') : undefined;
    const bc = cert !== null ? at(cert, 'both_centre_pct') : undefined;
    return {
      title: 'Certainty Height · raise the mast',
      body: `At 1 m the Sun is visible ${rng(s1)} of the window across ${s1?.n_clones ?? '—'} evaluated alternate NASA terrain realizations (batch sweep). ${cert !== null ? `At ${cert} m, the lowest sampled height that does it, every one of them keeps the Sun centre 100 % of the window (${rng(sc)}); Sun and Earth together ${rng(bc)}.` : ''} Only sampled heights are shown. Geometric visibility, not power.`,
    };
  }
  if (step === 3) {
    const far = ridgesOfRecord(v).find((x) => x.target === 'earth' && x.ridge.dem === 'far_80m');
    return {
      title: 'Coverage · how far agreement goes',
      body: `${at(1, 'sun_centre_pct')?.pass ?? '—'} tested realizations meet the team's Sun ≥ 70 % requirement at 1 m. However, they vary only terrain inside a ${c ? (c.tile_inscribed_radius_m / 1000).toFixed(1) : '—'} km tile: for ${c ? pct(c.sun_pct) : '—'} of the window's hours the Sun-direction horizon is set inside it (every Sun-blocked hour included), for the rest by distant 80 m terrain that every realization shares.${far ? ` Earth is cut off by ${far.ridge.label ?? far.ridge.id}, ${fmtRidgeDistance(far.ridge)} away: no realization varies it.` : ''} Agreement there is not evidence.`,
    };
  }
  return {
    title: 'The decision',
    body: `Team requirements (not NASA standards): Sun ≥ 70 %, Sun and Earth ≥ 40 %. The card states what the evidence supports, with its limits: source-based, not yet independently validated.`,
  };
}

export function Guide({ go }: { go: (r: Route) => void }) {
  const step = useUi((s) => s.guide);
  const setUi = useUi((s) => s.set);
  const v = useView();
  const side = usePolaris((s) => s.certaintySidecar);
  const cov = useCoverageSidecar();
  const cam = useCamera.getState();
  const done = useRef<string>('');
  const saved = useRef<Snapshot | null>(null);
  const keep = useRef(false);
  const prev = useRef<number | null>(null);
  const [auto, setAuto] = useState(false);

  // open: capture the state to come back to; close: put it back (unless the demo ended on "Open the evidence")
  useEffect(() => {
    const was = prev.current;
    prev.current = step;
    if (was === null && step !== null) {
      saved.current = capture();
      keep.current = false;
      done.current = '';
      usePolaris.getState().setPlaying(false);
      requestAnimationFrame(() => document.getElementById('guide-title')?.focus());
    } else if (was !== null && step === null) {
      setAuto(false);
      const s = saved.current;
      saved.current = null;
      if (s && !keep.current) void restore(s, go);
      requestAnimationFrame(() => (document.querySelector('[data-testid="guide-start"]') as HTMLElement | null)?.focus());
    }
  }, [step, go]);

  // Play: advance one scene every GUIDE_DWELL_MS; stops on the last scene; any manual step keeps playing from there
  useEffect(() => {
    if (!auto || step === null) return;
    if (step >= GUIDE_STEPS.length - 1) return void setAuto(false);
    const t = window.setTimeout(() => setUi({ guide: step + 1 }), GUIDE_DWELL_MS);
    return () => window.clearTimeout(t);
  }, [auto, step, setUi]);
  // after the open effect, so the snapshot is taken before the hero site is switched in
  useHeroLoaded(step !== null);

  // run each scene's action once its data is present
  useEffect(() => {
    if (step === null || !v || v.dataset.siteId !== HERO_SITE) return;
    const key = `${step}:${v.loaded.name}:${v.dataset.siteId}:${side ? 1 : 0}`;
    if (done.current === key) return;
    done.current = key;
    const st = usePolaris.getState();
    const scen = v.dataset.derived?.scenarios ?? [];
    // Every scene sets the full state it shows (route, scenario, mast, exact sample, selection, camera), so a scene looks the same
    // whether it is reached by Next, Back, a dot, or after the user switched site or mast: nothing carries over from before.
    const baseline = scen.find((x) => x.id === 'baseline') ?? scen[0];
    const toMast = (m: number) => {
      setUi({ mastPick: m });
      const sc = scen.find((x) => mastOf(x) === m) ?? baseline; // no bundle series at this height: show the 1 m series + the note
      if (sc && sc.id !== usePolaris.getState().scenarioId) st.setScenario(sc.id);
    };
    const sunRun = () => {
      const rr = ridgesOfRecord(v).find((x) => x.target === 'sun');
      return rr ? { rr, run: firstBlockedRun(v, rr.ridge, 'sun') } : null;
    };
    st.setPlaying(false);
    st.selectFailure(null);
    setUi({ returnTo: null });
    if (step === 0) {
      go('sky');
      toMast(1);
      st.selectBin(null);
      setUi({ run: null });
      st.setSampleIndex(0);
      cam.request('approach');
    } else if (step === 1 || step === 2) {
      go('sky');
      toMast(1);
      const r = sunRun();
      if (r?.run) {
        st.setSampleIndex(r.run.i0 + Math.floor((r.run.i1 - r.run.i0) / 2));
        setUi({ run: { ...r.run, target: 'sun' } });
      } else {
        st.setSampleIndex(0);
        setUi({ run: null });
      }
      if (step === 1 && r) {
        const idx = v.dataset.derived!.attribution!.ridges.indexOf(r.rr.ridge);
        const bins = ridgeBins(v.dataset.derived?.attribution, idx);
        st.selectBin(bins.length ? bins[Math.floor(bins.length / 2)] : null);
      } else st.selectBin(null);
      if (step === 2) {
        const cert = side?.sites?.[HERO_SITE]?.all_maps_100pct_sun_mast_m;
        if (cert != null) toMast(cert);
      }
      cam.request(step === 1 ? 'ridge' : 'mast');
    } else if (step === 3) {
      go('sky');
      toMast(1);
      st.selectBin(null);
      setUi({ run: null });
      st.setSampleIndex(0);
      cam.request('regional');
    } else if (step === 4) {
      toMast(1);
      st.selectBin(null);
      setUi({ run: null });
      st.setSampleIndex(0);
      go('decision');
      setTimeout(() => document.querySelector('[data-testid="decision-card"]')?.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'center' }), 300);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, v?.loaded.name, v?.dataset.siteId, side]);

  useEffect(() => {
    if (step === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setUi({ guide: null });
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [step, setUi]);

  if (step === null) return null;
  const t = sceneText(step, v && v.dataset.siteId === HERO_SITE ? v : null, side, cov);
  return (
    <aside className="guide" role="dialog" aria-modal="false" aria-labelledby="guide-title" data-testid="guide">
      <div className="guide-top">
        <span className="lab">
          Guided demo · {step + 1} / {GUIDE_STEPS.length}
        </span>
        <span className="guide-top-act">
          {step < GUIDE_STEPS.length - 1 && (
            <button type="button" className="btn btn-small" aria-pressed={auto} onClick={() => setAuto(!auto)} data-testid="guide-play" title={`Advance every ${GUIDE_DWELL_MS / 1000} s`}>
              {auto ? 'Pause' : 'Play'}
            </button>
          )}
          <button type="button" className="btn btn-small" onClick={() => setUi({ guide: null })} data-testid="guide-exit" title="Exit and return to where you were (Esc)">
            Exit
          </button>
        </span>
      </div>
      <h2 id="guide-title" tabIndex={-1}>
        {t.title}
      </h2>
      <p data-testid="guide-body" aria-live="polite">
        {t.body}
      </p>
      <div className="guide-nav">
        <ol className="guide-dots" aria-label="Scenes">
          {GUIDE_STEPS.map((s, i) => (
            <li key={s}>
              <button type="button" aria-current={i === step ? 'step' : undefined} title={s} onClick={() => setUi({ guide: i })}>
                <span className="sr-only">{s}</span>
              </button>
            </li>
          ))}
        </ol>
        <button type="button" className="btn" disabled={step === 0} onClick={() => setUi({ guide: step - 1 })} data-testid="guide-back">
          Back
        </button>
        {step < GUIDE_STEPS.length - 1 ? (
          <button type="button" className="btn pri" onClick={() => setUi({ guide: step + 1 })} data-testid="guide-next">
            Next
          </button>
        ) : (
          <>
            <button
              type="button"
              className="btn"
              data-testid="guide-evidence"
              onClick={() => {
                keep.current = true;
                setUi({ guide: null });
                go('evidence');
              }}
            >
              Open the evidence
            </button>
            <button type="button" className="btn pri" onClick={() => setUi({ guide: null })} data-testid="guide-finish">
              Finish
            </button>
          </>
        )}
      </div>
    </aside>
  );
}
