import { fmtSigned, type TargetView, type View } from '../store/view';
import type { Metric } from '../bundle/types';

function visText(t: TargetView): string {
  if (t.visible === undefined) return 'not in bundle';
  if (t.visible === null) return 'transition (between samples)';
  return t.visible ? 'VISIBLE' : 'BLOCKED';
}

function fmtMetric(m: Metric, v: number) {
  if (m.unit === 'fraction') return v.toFixed(3);
  return `${v.toFixed(m.unit === '%' ? 1 : 2)} ${m.unit}`;
}

function Now({ name, t, cls, v }: { name: 'sun' | 'earth'; t: TargetView; cls: string; v: View }) {
  const ser = v.series?.samples?.[name];
  const k = v.br.exact;
  const disk = ser?.diskFraction && k !== null ? ser.diskFraction[k] : undefined;
  const hitLabel = ser?.firstHitKind === 'horizon-setting-cell' ? 'Blocking cell' : 'First hit';
  return (
    <article className={`now ${cls}`} data-testid={`now-${name}`}>
      <h3>{name === 'sun' ? 'Sun' : 'Earth'}</h3>
      <dl>
        <dt>Azimuth</dt>
        <dd data-testid={`${name}-az`}>{t.az.toFixed(2)}°</dd>
        <dt>Elevation</dt>
        <dd data-testid={`${name}-el`}>{t.el.toFixed(3)}°</dd>
        <dt>Skyline</dt>
        <dd>{t.horizonElDeg === null ? '—' : `${t.horizonElDeg.toFixed(3)}°`}</dd>
        <dt>Margin</dt>
        <dd data-testid={`${name}-margin`} data-value={t.marginDeg ?? ''} className={t.marginDeg === null ? '' : t.marginDeg > 0 ? 'ok' : 'bad'}>
          {t.marginDeg === null ? 'not in bundle' : fmtSigned(t.marginDeg, 4)}
        </dd>
        <dt>Centre</dt>
        <dd data-testid={`${name}-state`}>
          {t.visible === false ? '✕ ' : t.visible ? '● ' : ''}
          {visText(t)}
        </dd>
        {disk !== undefined && (
          <>
            <dt>Disk visible</dt>
            <dd data-testid={`${name}-disk`} data-value={Number.isFinite(disk) ? disk : ''}>
              {Number.isFinite(disk) ? `${(disk * 100).toFixed(1)} %` : '—'}
            </dd>
          </>
        )}
        <dt>{hitLabel}</dt>
        <dd>{t.firstHitM === undefined ? '—' : t.firstHitM === null ? 'clear' : `${(t.firstHitM / 1000).toFixed(2)} km`}</dd>
      </dl>
    </article>
  );
}

export function MetricsPanel({ v }: { v: View }) {
  const sc = v.scenario;
  const hasConstraints = !!sc?.metrics.some((m) => m.constraint);
  const hasDelta = !!sc?.metrics.some((m) => m.delta !== undefined);
  return (
    <section className="panel" aria-labelledby="mx-title">
      <div className="panel-head">
        <h2 id="mx-title">Metrics & constraints</h2>
        <span className="src-tag bundle" data-testid="src-bundle">bundle · repo solver · nominal DEM</span>
        <span className="muted">
          {v.dataset.snapToSamples ? 'exact bundle sample (contract: no interpolation)' : v.br.exact === null ? 'margins interpolated between bundle samples' : 'exact bundle sample'}
        </span>
      </div>
      {v.seriesIsBaseline && (
        <p className="note small" data-testid="series-note">
          “{sc?.label}” carries scenario metrics only. The time-dependent values below are the baseline’s.
        </p>
      )}
      <div className="now-grid">
        <Now name="sun" t={v.sun} cls="sun" v={v} />
        <Now name="earth" t={v.earth} cls="earth" v={v} />
        <article className="now both" data-testid="now-both">
          <h3>Both</h3>
          <p className="big">{v.both === undefined ? 'not in bundle' : v.both === null ? 'transition' : v.both ? '● together' : '✕ not together'}</p>
        </article>
      </div>
      {sc ? (
        <details className="dec-more">
          <summary>
            {sc.metrics
              .filter((m) => m.constraint)
              .map((m) => `${m.label} ${fmtMetric(m, m.value)} ${m.pass === undefined ? '' : m.pass ? '✓' : '✕'} ${m.constraint!.op} ${m.constraint!.threshold} ${m.unit}`)
              .join(' · ') || 'Window metrics'}
            {` — all ${sc.metrics.length} window metrics`}
          </summary>
        <table className="constraints" data-testid="constraints">
          <caption className="sr-only">Scenario metrics from the bundle</caption>
          <thead>
            <tr>
              <th scope="col">Metric ({sc.label})</th>
              <th scope="col">Value</th>
              {hasDelta && <th scope="col">vs baseline</th>}
              {hasConstraints && (
                <>
                  <th scope="col">Limit</th>
                  <th scope="col">Margin</th>
                  <th scope="col">Result</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {sc.metrics.map((m) => (
              <tr key={m.id} data-testid={`metric-${m.id}`}>
                <th scope="row">{m.label}</th>
                <td data-value={m.value}>{fmtMetric(m, m.value)}</td>
                {hasDelta && <td data-value={m.delta ?? ''}>{m.delta === undefined ? '—' : fmtSigned(m.delta, m.unit === 'fraction' ? 3 : m.unit === '%' ? 1 : 2, m.unit === 'fraction' ? '' : ` ${m.unit}`)}</td>}
                {hasConstraints && (
                  <>
                    <td>{m.constraint ? `${m.constraint.op} ${m.constraint.threshold} ${m.unit}` : '—'}</td>
                    <td data-value={m.marginToLimit ?? ''}>{m.marginToLimit === undefined ? '—' : fmtSigned(m.marginToLimit, 2, ` ${m.unit}`)}</td>
                    <td className={m.pass === undefined ? '' : m.pass ? 'ok' : 'bad'}>{m.pass === undefined ? '—' : m.pass ? '✓ PASS' : '✕ FAIL'}</td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        </details>
      ) : (
        <p className="note" data-testid="no-derived">
          This bundle carries raw inputs only (DEM + JPL ephemeris). Visibility, margins and constraint results must come from the science branch
          (`derived` block); the viewer does not compute them.
        </p>
      )}
      {sc && hasConstraints && sc.metrics.some((m) => m.constraintSource) && (
        <p className="muted small" data-testid="constraint-source">
          Limits: {[...new Set(sc.metrics.map((m) => m.constraintSource).filter(Boolean))].join('; ')}. PASS/FAIL is the bundle value compared with that limit; geometric
          visibility only, not power or a DSN link.
        </p>
      )}
      {sc && !hasConstraints && (
        <p className="muted small">No mission limits are defined in this bundle, so no PASS/FAIL is shown. Limits are a team decision, not a viewer default.</p>
      )}
    </section>
  );
}
