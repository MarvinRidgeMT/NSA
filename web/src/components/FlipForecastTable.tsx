import type { View } from '../store/view';

/** Small, display-only comparison of precomputed forecast and full-solver flips. */
export function FlipForecastTable({ v }: { v: View }) {
  const block = v.dataset.derived?.flipForecast;
  if (!block) return null;
  return (
    <section
      className="panel flip-forecast"
      aria-labelledby="flip-forecast-title"
      data-testid="flip-forecast"
      data-result-id={block.result_id}
      data-label={block.label}
    >
      <div className="panel-head">
        <h2 id="flip-forecast-title">Forecast vs actual</h2>
        <span className="pilot-badge" data-testid="flip-forecast-label">{block.label}</span>
      </div>
      <p className="muted small" data-result-id={block.thresholds.source_result_id} data-label={block.label}>
        Fixed nominal-ridge forecast compared with full solver results for {block.clone_count} terrain clones.
        Mission thresholds come from <code>{block.thresholds.source_result_id}</code>.
      </p>
      <div className="table-scroll">
        <table className="constraints flip-table" data-testid="flip-forecast-table">
          <thead>
            <tr>
              <th scope="col">Scope</th>
              <th scope="col">Cases</th>
              <th scope="col">Forecast flips</th>
              <th scope="col">Actual flips</th>
              <th scope="col">TP / FP / FN</th>
              <th scope="col">Precision</th>
              <th scope="col">Recall</th>
              <th scope="col">Result ID · label</th>
            </tr>
          </thead>
          <tbody>
            {block.forecast_vs_actual.map((row) => (
              <tr
                key={row.result_id}
                data-testid={`flip-forecast-row-${row.row_id}`}
                data-result-id={row.result_id}
                data-label={row.label}
              >
                <th scope="row">{row.scope}</th>
                <td data-value={row.case_count}>{row.case_count}</td>
                <td data-value={row.predicted_flips}>{row.predicted_flips}</td>
                <td data-value={row.actual_flips}>{row.actual_flips}</td>
                <td data-tp={row.true_positive} data-fp={row.false_positive} data-fn={row.false_negative}>
                  {row.true_positive} / {row.false_positive} / {row.false_negative}
                </td>
                <td data-value={row.precision ?? ''}>{row.precision_display}</td>
                <td data-value={row.recall ?? ''}>{row.recall_display}</td>
                <td><code>{row.result_id}</code> · {row.label}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small method-caption" data-result-id={block.result_id} data-label={block.label}>
        {block.method.caption} {block.method.metrics}. {block.method.limitation}.
      </p>
    </section>
  );
}
