import { usePolaris } from '../store/store';
import { useUi } from '../store/ui';
import type { View } from '../store/view';
import type { Scenario } from '../bundle/types';
import { useCoverageSidecar } from '../bundle/coverageSidecar';

type Row = { mast_m: number; metric: string; min: number; max: number; nominal: number; pass: string; n_clones: number };

const pct = (x: number) => (Number.isFinite(x) ? `${x.toFixed(1)} %` : '—');
const range = (r?: Row) => (!r ? '—' : r.min === r.max ? pct(r.min) : `${r.min.toFixed(1)}–${r.max.toFixed(1)} %`);
const mastOf = (sc: Scenario): number | undefined => {
  const pm = sc.parameters ?? {};
  const m = (pm as Record<string, unknown>).mast_m ?? (pm as Record<string, unknown>).mastM;
  if (typeof m === 'number') return m;
  return sc.id === 'baseline' || /mast/.test(`${sc.kind ?? ''}${sc.family ?? ''}`) ? sc.observer?.mastM : undefined;
};
const mastOnly = (sc: Scenario) => Object.keys(sc.parameters ?? {}).every((k) => /mast/i.test(k));

/**
 * Certainty Height instrument (Explore): pick a SAMPLED mast height from the batch sweep and read the result at that height
 * next to the 1 m baseline. Values are copied from the certainty sidecar (batch CSVs). When the bundle has a series for the
 * picked height (e.g. 10 m), the scenario switches so rays, ribbon and clock use it; otherwise the time series stay on the
 * bundle's own mast and the instrument says so. No value between sampled heights is shown or implied.
 */
export function MastInstrument({ v }: { v: View }) {
  const side = usePolaris((s) => s.certaintySidecar);
  const cov = useCoverageSidecar();
  const pick = useUi((s) => s.mastPick);
  const set = useUi((s) => s.set);
  const { setScenario } = usePolaris.getState();
  const site = side?.sites?.[v.dataset.siteId];
  if (!site) return null;
  const rows = site.certainty_curve as Row[];
  const at = (m: number, metric: string) => rows.find((r) => r.mast_m === m && r.metric === metric);
  const scenarios = v.dataset.derived?.scenarios ?? [];
  const seriesMast = v.series?.observer?.mastM ?? null;
  const masts = site.sampled_masts_m;
  const h = pick ?? (seriesMast !== null && masts.includes(seriesMast) ? seriesMast : masts[0]);
  const s = at(h, 'sun_centre_pct');
  const b = at(h, 'both_centre_pct');
  const s1 = at(masts[0], 'sun_centre_pct');
  const cert = site.all_maps_100pct_sun_mast_m;
  const all100 = s ? s.min >= 100 : false;
  const c = cov?.sites[v.dataset.siteId];

  const choose = (m: number) => {
    set({ mastPick: m });
    const sc = scenarios.find((x) => mastOf(x) === m && mastOnly(x));
    if (sc && sc.id !== v.series?.id) setScenario(sc.id);
  };

  return (
    <div className="sect mast-inst" data-testid="mast-instrument">
      <span className="lab">Certainty Height · mast</span>
      <div className="mast-chips" role="radiogroup" aria-label="Mast height (sampled heights only)">
        {masts.map((m) => (
          <button
            key={m}
            type="button"
            role="radio"
            aria-checked={m === h}
            className={`chip ${m === cert ? 'is-cert' : ''}`}
            data-testid={`mast-${m}`}
            onClick={() => choose(m)}
            onKeyDown={(e) => {
              const i = masts.indexOf(m);
              if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                e.preventDefault();
                const j = Math.min(masts.length - 1, Math.max(0, i + (e.key === 'ArrowRight' ? 1 : -1)));
                choose(masts[j]);
                (e.currentTarget.parentElement?.children[j] as HTMLElement | undefined)?.focus();
              }
            }}
          >
            {m}
          </button>
        ))}
        <span className="unit">m</span>
      </div>
      <div className="mast-read" aria-live="polite">
        <div className="mr-big">
          <span className={`v ${all100 ? '' : 'sun'}`}>{range(s)}</span>
          <span className="d">Sun centre visible · {s?.n_clones ?? '—'} evaluated alternate realizations at {h} m · nominal {s ? pct(s.nominal) : '—'}</span>
        </div>
        <dl className="kvs">
          <dt>Sun ≥ 70 % (team)</dt>
          <dd data-testid="mast-pass-sun">{s?.pass ?? '—'}</dd>
          <dt>Sun + Earth</dt>
          <dd className="earth-num">{range(b)}</dd>
          <dt>Sun + Earth ≥ 40 % (team)</dt>
          <dd data-testid="mast-pass-both">{b?.pass ?? '—'}</dd>
          <dt>Sun 100 % on all</dt>
          <dd data-testid="mast-all100">{s ? (all100 ? `yes, ${s.n_clones} of ${s.n_clones}` : `no · lowest ${pct(s.min)}`) : '—'}</dd>
        </dl>
        {s && s1 && h !== masts[0] && (
          <p className="scope" data-testid="mast-compare">
            Lowest realization: <span className="mono">{pct(s1.min)}</span> at {masts[0]} m → <span className="mono">{pct(s.min)}</span> at {h} m.
            {cert !== null && ` ${cert} m is the lowest sampled height where every tested realization keeps the Sun for the whole window.`}
          </p>
        )}
        {seriesMast !== null && seriesMast !== h && (
          <p className="scope series-note" data-testid="mast-series-note">
            No bundle time series at {h} m: clock, sight lines and ribbon stay on the {seriesMast} m series; {h} m is drawn as an outline.
          </p>
        )}
        <details className="inst-more">
          <summary>Where these numbers come from</summary>
          <p className="scope">
          Batch sweep (nominal + {s?.n_clones ?? '—'} PGDA 78 alternate realizations, 14–28 Nov 2026, 1 h), not this bundle's solver.{' '}
          {seriesMast !== null && seriesMast !== h ? '' : `The clock, sight lines and ribbon show the bundle series at ${h} m.`}
          {c && ` Coverage (${c.sun_pct.toFixed(1)} % of Sun hours inside the varied tile) was measured at 1 m only.`} Geometric centre visibility, not power.
          </p>
        </details>
      </div>
    </div>
  );
}
