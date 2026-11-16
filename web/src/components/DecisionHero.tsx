import { usePolaris } from '../store/store';
import type { View } from '../store/view';
import { useCoverageSidecar } from '../bundle/coverageSidecar';
import { fmtRidgeDistance } from '../bundle/evidence';

type Row = { mast_m: number; metric: string; min: number; max: number; nominal: number; pass: string; n_clones: number };
const pct = (x: number) => (Number.isFinite(x) ? `${x.toFixed(1)} %` : '—');
const range = (r?: Row) => (!r ? '—' : r.min === r.max ? pct(r.min) : `${r.min.toFixed(1)}–${r.max.toFixed(1)} %`);

/** min–max band and nominal tick on a fixed 50–100 % scale, so the two heights compare at a glance (values from the sidecar). */
function RangeBar({ r, threshold, kind }: { r?: Row; threshold: number; kind: 'sun' | 'both' }) {
  if (!r) return null;
  const lo = 50;
  const X = (p: number) => `${Math.max(0, Math.min(100, ((p - lo) / (100 - lo)) * 100))}%`;
  return (
    <div className={`rbar ${kind}`} aria-hidden="true">
      <span className="rb-track" />
      <span className="rb-th" style={{ left: X(threshold) }} title={`team requirement ${threshold} %`} />
      <span className="rb-band" style={{ left: X(r.min), width: `calc(${X(r.max)} - ${X(r.min)} + 3px)` }} />
      <span className="rb-nom" style={{ left: X(r.nominal) }} />
    </div>
  );
}

/**
 * Decision hero (V3 Decision board): the two heights that matter, side by side, read only from the certainty sidecar
 * (batch sweep). 1 m = the lowest sampled mast, which already meets the team requirements on every tested realization;
 * the Certainty Height = the lowest sampled mast where the Sun centre stays in view the whole window on every one of them.
 */
export function DecisionHero({ v }: { v: View }) {
  const side = usePolaris((s) => s.certaintySidecar);
  const cov = useCoverageSidecar();
  const site = side?.sites?.[v.dataset.siteId];
  if (!site) return null;
  const rows = site.certainty_curve as Row[];
  const at = (m: number, k: string) => rows.find((r) => r.mast_m === m && r.metric === k);
  // "k/N": every tested realization passes that requirement (parsed as given, nothing inferred)
  const full = (r?: Row) => {
    const m = r?.pass.match(/^(\d+)\/(\d+)$/);
    return !!m && m[1] === m[2];
  };
  // Three different heights (Final Apex P7): lowest meeting the team requirements on every realization; lowest with the Sun
  // centre 100 % on every realization (the Certainty Height); agreement height (Sun spread across realizations <= 1 pt).
  const feasible = site.sampled_masts_m.find((m) => full(at(m, 'sun_centre_pct')) && full(at(m, 'both_centre_pct'))) ?? null;
  const lowM = feasible ?? site.sampled_masts_m[0];
  const cert = site.all_maps_100pct_sun_mast_m;
  const agree = site.agreement_mast_m;
  const c = cov?.sites[v.dataset.siteId];
  const sLow = at(lowM, 'sun_centre_pct');
  const bLow = at(lowM, 'both_centre_pct');
  const sC = cert !== null ? at(cert, 'sun_centre_pct') : undefined;
  const bC = cert !== null ? at(cert, 'both_centre_pct') : undefined;
  const n = sLow?.n_clones;
  const farEarth = (v.dataset.derived?.attribution?.ridges ?? []).filter((r) => r.dem === 'far_80m' && r.hours.earth.lost > 0).sort((a, b) => b.hours.earth.lost - a.hours.earth.lost)[0];
  const bestBoth = Math.max(...rows.filter((r) => r.metric === 'both_centre_pct').map((r) => r.max));
  const col = (label: string, kicker: string, s?: Row, b?: Row, verdict?: string, testId?: string) => (
    <div className="hc-col" data-testid={testId}>
      <div className="lab">{kicker}</div>
      <div className="hc-mast">
        {label.replace(/ m$/, '')}
        <span className="u">m</span>
      </div>
      <div className="hc-line">
        <span className="hc-k">Sun centre visible</span>
        <span className="hc-v sun">{s && s.min >= 100 ? `100 % on all ${s.n_clones}` : range(s)}</span>
      </div>
      <RangeBar r={s} threshold={70} kind="sun" />
      <div className="hc-line">
        <span className="hc-k">Sun + Earth</span>
        <span className="hc-v earth">{range(b)}</span>
      </div>
      <RangeBar r={b} threshold={40} kind="both" />
      <div className="hc-pass">
        Team requirements: Sun ≥ 70 % <b>{s?.pass ?? '—'}</b> · Sun + Earth ≥ 40 % <b>{b?.pass ?? '—'}</b>
      </div>
      {verdict && <p className="hc-verdict">{verdict}</p>}
    </div>
  );
  return (
    <div className="dec-hero-left">
      <div className="height-compare" data-testid="height-compare">
        {col(
          `${lowM} m`,
          feasible !== null ? 'Lowest height meeting the team requirements' : 'Lowest sampled mast (no height meets them on all)',
          sLow,
          bLow,
          sLow
            ? `Meets both team requirements on ${sLow.pass} realizations, but ${sLow.max < 100 ? 'every one of them' : sLow.min < 100 ? 'some of them' : 'none of them'} loses the Sun for part of the window (lowest ${pct(sLow.min)}).`
            : undefined,
          'hc-low',
        )}
        <div className="hc-arrow" aria-hidden="true">
          <span>{cert !== null ? `+${(cert - lowM).toFixed(2)}` : ''}</span>
        </div>
        {cert !== null
          ? col(
              `${cert} m`,
              'Certainty Height',
              sC,
              bC,
              `Lowest sampled mast with the Sun centre in view all window on all ${n ?? ''} evaluated realizations${c ? `; they vary the horizon for only ${c.sun_pct.toFixed(1)} % of Sun hours` : ''}. Not a guarantee of power, comms or mission success.`,
              'hc-cert',
            )
          : (
            <div className="hc-col">
              <div className="lab">Certainty Height</div>
              <p className="hc-verdict">No sampled mast keeps the Sun on every evaluated realization.</p>
            </div>
          )}
      </div>
      <dl className="three-heights" data-testid="three-heights" aria-label="Three different heights">
        <div>
          <dt>Meets the team requirements on all {n ?? '—'}</dt>
          <dd>{feasible !== null ? `${feasible} m` : 'none sampled'}</dd>
        </div>
        <div>
          <dt>Sun 100 % on all {n ?? '—'} (Certainty Height)</dt>
          <dd>{cert !== null ? `${cert} m` : 'none sampled'}</dd>
        </div>
        <div>
          <dt>Agreement height (Sun spread ≤ 1 pt)</dt>
          <dd>{agree !== null ? `${agree} m` : 'none sampled'}</dd>
        </div>
        <p className="th-note">
          Three different questions{cert !== null && agree === cert ? '; here the last two fall on the same sampled height' : ''}. Agreement across tested realizations is not a probability.
        </p>
      </dl>
      <p className="hc-scale">
        Bars: min–max across {n ?? '—'} evaluated alternate NASA terrain realizations, tick = nominal DEM, line = team requirement. Batch sweep, 14–28 Nov 2026,
        hourly; sampled heights only.
      </p>
      <div className="takeaways">
        <div>
          <div className="lab">The mast is the lever</div>
          <div className="tk-big">{cert !== null ? `+${(cert - lowM).toFixed(2)} m` : '—'}</div>
          <p>
            {cert !== null && sLow
              ? `From ${lowM} m to ${cert} m, the realizations that lose the Sun go from ${sLow.max < 100 ? 'all' : sLow.min < 100 ? 'some' : 'none'} of ${sLow.n_clones} to none.`
              : 'No sampled mast removes every Sun loss.'}
          </p>
        </div>
        <div>
          <div className="lab">Earth is the harder limit</div>
          <div className="tk-big earth">≤ {pct(bestBoth)}</div>
          <p>
            best Sun + Earth at any sampled mast.
            {farEarth ? ` Earth is cut off by ${farEarth.label ?? farEarth.id}, ${fmtRidgeDistance(farEarth)} away, which no realization varies.` : ''}
          </p>
        </div>
        <div>
          <div className="lab">What this cannot say</div>
          <p className="tk-text">
            {c ? `Only ${c.sun_pct.toFixed(1)} % of the window's Sun horizon is set by terrain the realizations vary. ` : ''}Geometric centre visibility only: no
            power, thermal or link budget. Agreement is not certainty. Solver of record pending.
          </p>
        </div>
      </div>
    </div>
  );
}
