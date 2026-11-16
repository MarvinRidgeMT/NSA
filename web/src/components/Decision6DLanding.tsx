import { DECISION6D_FILE, blockDim, blockMetric, type Decision6D, type Decision6DQuestion } from '../bundle/scenarioCubeV2';
import { GEOMETRY_LABEL, fmtVal } from './Decision6D';

/**
 * "Best landing point within R km of here": emulator screen (science/cube/emulator.py) and full-solver re-check
 * (science/anysite/solve.py), from decision6d.json `landing__<R>__candidates` / `__screen`. Display only.
 */
export function Decision6DLanding({ d, q }: { d: Decision6D; q: Decision6DQuestion }) {
  const c = d.cube;
  const cb = q.candidates_block!;
  const sb = q.screen_block!;
  const L = blockDim(c, cb);
  if (!L) return null;
  const g = (m: string) => (blockMetric(c, cb, m) ?? []) as (number | boolean | null)[];
  const s = (m: string) => (blockMetric(c, sb, m) ?? [null])[0] as number | boolean | null;
  const labels = L.value_labels ?? L.values.map(String);
  const emu = g('emulated_sun_pct') as number[];
  const sol = g('solver_sun_pct') as number[];
  const err = g('recheck_error_pct') as number[];
  const worst = g('solver_sun_pct_worst_T') as number[];
  const slope = g('slope_100m_deg') as number[];
  const inGp = g('gp_in_domain') as boolean[];
  const top = g('is_top_pick') as boolean[];
  const pmin = g('product_sun_pct_min') as (number | null)[];
  const pmax = g('product_sun_pct_max') as (number | null)[];
  const tr = (m: string, i?: number) => `${DECISION6D_FILE}#${cb}.${m}${i === undefined ? '' : `[${i}]`}`;
  return (
    <section
      className="panel decision6d-landing"
      data-testid="d6-landing"
      data-source={`decision6d ${c.cube_id} ${cb}`}
      data-result-id={`${c.cube_id}#${cb}`}
      data-label={GEOMETRY_LABEL}
    >
      <div className="panel-head">
        <h2>Best landing point within {q.radius_km} km of here</h2>
        <span className="pilot-badge">{GEOMETRY_LABEL}</span>
      </div>
      <p className="small">
        The emulator screened <b data-testid="d6-land-screened">{String(s('n_screened'))}</b> candidates that pass the 10° landing-slope filter (
        {String(s('n_slope_fail'))} too steep, {String(s('n_off_tile'))} outside the 5 m map); the full solver then re-checked{' '}
        {String(s('n_rechecked'))} of them over 12 months of hourly Sun samples.
      </p>
      <dl className="cube-card" data-testid="d6-land-error" data-trace={`${DECISION6D_FILE}#${sb}`}>
        <div>
          <dt>Re-check error (emulator − solver), mean |·|</dt>
          <dd data-testid="d6-land-mae">{fmtVal(s('recheck_mae_pct') as number, 'pct points')}</dd>
        </div>
        <div>
          <dt>Largest |error|</dt>
          <dd>{fmtVal(s('recheck_max_abs_pct') as number, 'pct points')}</dd>
        </div>
        <div>
          <dt>Rank agreement (Spearman)</dt>
          <dd>{fmtVal(s('recheck_spearman') as number, '', 3)}</dd>
        </div>
        <div>
          <dt>Emulator&apos;s best = solver&apos;s best?</dt>
          <dd data-testid="d6-land-agree">{s('emulator_top_is_solver_top') ? 'yes' : 'no'}</dd>
        </div>
      </dl>
      <div className="table-scroll">
        <table className="constraints flip-table" data-testid="d6-land-table">
          <thead>
            <tr>
              <th>Candidate</th>
              <th>Slope</th>
              <th>Emulator Sun</th>
              <th>Solver Sun (nominal)</th>
              <th>Error</th>
              <th>Worst of 21 maps</th>
              <th>Other products (M)</th>
            </tr>
          </thead>
          <tbody>
            {labels.map((lab, i) => (
              <tr key={i} data-testid={`d6-land-${i}`} data-trace={tr('solver_sun_pct', i)}>
                <td>
                  {lab}
                  {top[i] ? ' · top pick' : i === 0 ? '' : ' · random check'}
                  {inGp[i] ? '' : ' · outside GP square'}
                </td>
                <td>{fmtVal(slope[i], 'deg')}</td>
                <td>{fmtVal(emu[i], '%')}</td>
                <td data-testid={`d6-land-sol-${i}`}>{fmtVal(sol[i], '%')}</td>
                <td>{fmtVal(err[i], 'pct points')}</td>
                <td>{fmtVal(worst[i], '%')}</td>
                <td>{pmin[i] === null ? '—' : `${fmtVal(pmin[i], '%')} – ${fmtVal(pmax[i], '%')}`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        Outside the ±100 m square the emulator&apos;s correction term is only its mean, so the screen there is essentially the coarse skyline:
        the error column is the honest measure. Other terrain products can disagree by tens of points at rim sites; they are shown, not
        optimised over. The robust choice above is over the 21 PGDA 78 maps at the re-checked points only.
      </p>
    </section>
  );
}
