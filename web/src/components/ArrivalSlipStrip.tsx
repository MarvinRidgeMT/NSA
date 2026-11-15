import type { View } from '../store/view';

function signed(value: number) {
  return `${value > 0 ? '+' : ''}${value}`;
}

/** Decision-screen display of precomputed arrival-slip bundle results. */
export function ArrivalSlipStrip({ v }: { v: View }) {
  const block = v.dataset.derived?.arrivalSlip;
  if (!block) return null;
  return (
    <section
      className="panel arrival-slip"
      aria-labelledby="arrival-slip-title"
      data-testid="arrival-slip"
      data-result-id={block.result_id}
      data-label={block.label}
    >
      <div className="panel-head">
        <h2 id="arrival-slip-title">Arrival-slip resilience</h2>
        <span className="pilot-badge" data-testid="arrival-slip-label">
          {block.label}
        </span>
      </div>
      <p className="muted small" data-result-id={block.result_id} data-label={block.label}>
        Sun centre ≥ <span data-value={block.thresholds.sun_center_visible_pct_min}>{block.thresholds.sun_center_visible_pct_min}</span>% and Sun+Earth ≥{' '}
        <span data-value={block.thresholds.sun_and_earth_center_visible_pct_min}>{block.thresholds.sun_and_earth_center_visible_pct_min}</span>%.{' '}
        {block.thresholds.joint_rule}. Each cell is passing terrain clones / clones tested.
      </p>
      <div className="slip-strip" role="list" aria-label="Arrival-slip clone pass counts">
        {block.points.map((point) => {
          return (
            <div
              role="listitem"
              className={`slip-cell ${point.clones.pass_band}`}
              key={point.result_id}
              data-result-id={point.result_id}
              data-label={point.label}
              data-pass-pct={point.clones.joint_pass_pct}
              data-testid={`arrival-slip-cell-${point.slip_h}`}
              title={`${point.result_id} · ${point.label}`}
            >
              <span className="slip-k">{point.clones.joint_pass_count}/{point.clones.pass_denominator}</span>
              <span>{signed(point.slip_h)} h</span>
              <small>{point.label}</small>
            </div>
          );
        })}
      </div>
      <details className="slip-trace">
        <summary>Exact bundle values and result IDs</summary>
        <div className="table-scroll">
          <table className="constraints slip-table">
          <thead>
            <tr>
              <th scope="col">Slip</th>
              <th scope="col">Nominal Sun %</th>
              <th scope="col">Clone Sun min–max %</th>
              <th scope="col">Nominal Sun+Earth %</th>
              <th scope="col">Clone Sun+Earth min–max %</th>
              <th scope="col">Pass</th>
              <th scope="col">Result ID · label</th>
            </tr>
          </thead>
          <tbody>
            {block.points.map((point) => (
              <tr key={point.result_id} data-result-id={point.result_id} data-label={point.label} data-testid={`arrival-slip-row-${point.slip_h}`}>
                <th scope="row" data-value={point.slip_h}>{signed(point.slip_h)} h</th>
                <td data-value={point.nominal.sun_center_visible_pct}>{point.nominal.sun_center_visible_pct}</td>
                <td data-min={point.clones.sun_center_visible_pct_min} data-max={point.clones.sun_center_visible_pct_max}>
                  {point.clones.sun_center_visible_pct_min}–{point.clones.sun_center_visible_pct_max}
                </td>
                <td data-value={point.nominal.sun_and_earth_center_visible_pct}>{point.nominal.sun_and_earth_center_visible_pct}</td>
                <td data-min={point.clones.sun_and_earth_center_visible_pct_min} data-max={point.clones.sun_and_earth_center_visible_pct_max}>
                  {point.clones.sun_and_earth_center_visible_pct_min}–{point.clones.sun_and_earth_center_visible_pct_max}
                </td>
                <td data-value={point.clones.joint_pass_count}>{point.clones.joint_pass_count}/{point.clones.pass_denominator}</td>
                <td><code>{point.result_id}</code> · {point.label}</td>
              </tr>
            ))}
          </tbody>
          </table>
        </div>
      </details>
      <p className="muted small method-caption" data-result-id={block.result_id} data-label={block.label}>
        {block.method.visibility_percentage}. {block.method.terrain}. {block.method.uncertainty}. {block.method.limitation}.
      </p>
    </section>
  );
}
