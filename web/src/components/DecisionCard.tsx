import { usePolaris } from '../store/store';
import type { View } from '../store/view';
import { useCoverageSidecar } from '../bundle/coverageSidecar';

type Row = { mast_m: number; metric: string; min: number; max: number; nominal: number; pass: string; n_clones: number };
const pct = (x: number) => (Number.isFinite(x) ? x.toFixed(1) : '—');
const range = (a?: Row) => (a ? (a.min === a.max ? `${pct(a.min)} %` : `${pct(a.min)}–${pct(a.max)} %`) : '—');

/**
 * Penumbra Decision Card: a one-page summary in the print palette, filled only from the certainty sidecar (batch CSV),
 * the coverage sidecar and the loaded bundle. Per-requirement pass counts are copied as given ("k/N"); no joint count
 * is inferred from them. Print (Cmd+P) prints the card alone.
 */
export function DecisionCard({ v }: { v: View }) {
  const side = usePolaris((s) => s.certaintySidecar);
  const cov = useCoverageSidecar();
  const site = side?.sites?.[v.dataset.siteId];
  if (!site) return null;
  const rows = site.certainty_curve as Row[];
  const at = (m: number, metric: string) => rows.find((r) => r.mast_m === m && r.metric === metric);
  const s1 = at(1, 'sun_centre_pct');
  const b1 = at(1, 'both_centre_pct');
  const cert = site.all_maps_100pct_sun_mast_m;
  const sC = cert !== null ? at(cert, 'sun_centre_pct') : undefined;
  const c = cov?.sites[v.dataset.siteId];
  const today = new Date(v.times[0]).toISOString().slice(0, 10);
  return (
    <section className="dec-card-wrap" aria-labelledby="dc-title" data-testid="decision-card">
      <div className="dc-head">
        <h2 id="dc-title" className="lab">Decision card · print palette</h2>
        <span className="src-tag batch">batch sweep</span>
      </div>
      <div className="dcard">
        <div className="top">
          <b>POLARIS X</b>
          <span>DECISION CARD · WINDOW FROM {today}</span>
        </div>
        <p className="stmt">
          {cert !== null
            ? `${v.dataset.site.name} keeps the Sun centre in view on all ${s1?.n_clones ?? ''} evaluated alternate terrain realizations from a ${cert} m mast.`
            : `${v.dataset.site.name}: no sampled mast keeps the Sun on every evaluated realization.`}
        </p>
        {c && (
          <p className={`dc-cov${c.sun_pct < 50 ? ' low' : ''}`} data-testid="dc-coverage">
            Coverage {c.sun_pct.toFixed(1)} % (Sun) · {c.earth_pct.toFixed(1)} % (Earth) of window hours set by terrain the realizations vary
            {c.sun_pct < 50 ? ' · below 50 %: agreement covers less than half of what controls the Sun' : ''}
          </p>
        )}
        <div className="nums three">
          {sC && (
            <div data-testid="dc-cert">
              <div className="v sun">{sC.min >= 100 ? '100 %' : range(sC)}</div>
              <div className="d">Sun, {cert} m mast, on all {sC.n_clones} realizations (Certainty Height) · ≥ 70 %: {sC.pass}</div>
            </div>
          )}
          <div>
            <div className="v sun">{range(s1)}</div>
            <div className="d">Sun, 1 m mast, {s1?.n_clones ?? '—'} realizations · team requirement ≥ 70 %: {s1?.pass ?? '—'}</div>
          </div>
          <div>
            <div className="v earth">{range(b1)}</div>
            <div className="d">Sun + Earth, 1 m mast · team requirement ≥ 40 %: {b1?.pass ?? '—'}</div>
          </div>
        </div>
        <p className="fine">
          Geometric centre-of-disk visibility only, not power or a communications link. The spread is “N of N realizations tested”, not a probability; agreement is not certainty.
          {c ? ' Coverage above is at 1 m.' : ''} Requirements
          are the team’s, not NASA standards.
        </p>
        <div className="src">
          PGDA 78 · PGDA 90 · JPL Horizons · batch sweep CSV ({side?.source.files.map((f) => f.sha256.slice(0, 8)).join(', ')})
          <br />
          <span className="st">SOURCE-BASED · UNVALIDATED · solver of record pending</span>
        </div>
      </div>
      <div className="dc-actions">
        <button type="button" className="btn pri" onClick={() => window.print()}>
          Print / save PDF
        </button>
      </div>
    </section>
  );
}
