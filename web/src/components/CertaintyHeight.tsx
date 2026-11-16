import { mastScenarios } from '../bundle/evidence';
import type { CertaintyPoint, Metric, Scenario } from '../bundle/types';
import { usePolaris } from '../store/store';
import { sidecarCurveFor } from '../bundle/certaintySidecar';
import type { View } from '../store/view';

/**
 * Certainty Height: how tall a mast must be before the result stops depending on which terrain
 * realization is true. Two distinct quantities, both read from derived.certaintyCurve:
 *   - minimum tested feasible height: smallest sampled mast at which every realization meets the requirements
 *   - agreement height: smallest sampled mast at which the realization spread falls below the declared tolerance
 * Fallback: the bundle's mast-height scenarios (one realization each) as a plain table, explicitly
 * not a certainty curve. The viewer computes nothing; it selects the scenario the user clicks.
 */
const W = 760;
const H = 230;
const M = { l: 44, r: 14, t: 14, b: 30 };

const REQ_LABEL: Record<string, string> = { sun_centre_pct: 'Sun centre', both_centre_pct: 'Sun + Earth', sun_center_visible_pct: 'Sun centre', sun_and_earth_center_visible_pct: 'Sun + Earth' };
const reqLabel = (k: string) => REQ_LABEL[k] ?? k;
const metric = (s: Scenario, id: string): Metric | undefined => s.metrics.find((m) => m.id === id);
const fmtPct = (x: number | undefined | null) => (x === null || x === undefined || !Number.isFinite(x) ? '—' : `${x.toFixed(1)}%`);

export function CertaintyHeight({ v }: { v: View }) {
  const { setScenario } = usePolaris.getState();
  const sidecar = usePolaris((st) => st.certaintySidecar);
  // Prefer the batch sidecar when it covers this site (source of record for clone ranges and pass counts, same rule as the
  // coverage gauge); fall back to the bundle's own derived.certaintyCurve (science/certainty.py, per-requirement counts).
  const side = sidecarCurveFor(sidecar, v.dataset.siteId);
  const curve = side?.curve ?? v.dataset.derived?.certaintyCurve ?? null;
  const scenarios = v.dataset.derived?.scenarios ?? [];
  const masts = mastScenarios(scenarios);
  const baseline = scenarios.find((s) => s.id === 'baseline') ?? scenarios[0];

  const cov = v.dataset.derived?.coverage?.sun.controllingHoursInside;
  const lowCoverage = cov !== undefined && Number.isFinite(cov) && cov < 0.5;
  const covPct = cov !== undefined && Number.isFinite(cov) ? `${Math.round(cov * 100)} %` : '';
  const mastOf = (sc: Scenario) => {
    const pm = sc.parameters ?? {};
    const m = pm.mast_m ?? pm.mastM;
    // mast-only scenarios: a-science (family mast-height, parameters.mast_m) or the export/fixture (kind mast_height, observer.mastM)
    return typeof m === 'number' ? m : sc.id === 'baseline' || /mast/.test(sc.kind ?? '') ? sc.observer?.mastM : undefined;
  };
  const isMastOnly = (sc: Scenario) => Object.keys(sc.parameters ?? {}).every((k) => /mast/i.test(k)) && (sc.id === 'baseline' || /mast/.test(`${sc.kind ?? ''}${sc.family ?? ''}`) || Object.keys(sc.parameters ?? {}).length > 0);
  const scenarioForMast = (m: number) => scenarios.find((sc) => mastOf(sc) === m && isMastOnly(sc));

  if (curve) {
    const xs = curve.points.map((p) => p.mastM);
    // sampled heights are placed evenly (ordinal axis): nothing is implied between them, and close heights stay readable
    const x = (m: number) => M.l + 14 + (xs.indexOf(m) / Math.max(xs.length - 1, 1)) * (W - M.l - M.r - 28);
    const lows = [...curve.points.map((q) => q.min.sunPct), ...(curve.requirements ?? []).map((r) => r.threshold)].filter((n) => Number.isFinite(n));
    const yMin = Math.max(0, Math.floor((Math.min(100, ...lows) - 5) / 10) * 10);
    const y = (p: number) => M.t + ((100 - p) / (100 - yMin)) * (H - M.t - M.b);
    const yTicks = Array.from({ length: Math.round((100 - yMin) / 10) + 1 }, (_, i) => yMin + i * 10);
    const hasGap = curve.points.some((q) => q.nominal.longestSunGapH !== undefined);
    const hasCov = curve.points.some((q) => q.coverageInside != null);
    const path = (sel: (p: CertaintyPoint) => number) => curve.points.map((p, i) => `${i ? 'L' : 'M'}${x(p.mastM).toFixed(1)},${y(sel(p)).toFixed(1)}`).join(' ');
    const band = `${path((p) => p.max.sunPct)} ${curve.points
      .slice()
      .reverse()
      .map((p) => `L${x(p.mastM).toFixed(1)},${y(p.min.sunPct).toFixed(1)}`)
      .join(' ')} Z`;
    return (
      <section className="panel" aria-labelledby="ch-title" data-testid="certainty-height">
        <div className="panel-head">
          <h2 id="ch-title">Certainty height · mast sweep across terrain realizations</h2>
          {side && <span className="src-tag batch">batch sweep · hourly · nominal + alternate realizations</span>}
          <span className="muted">
            {side ? 'from the batch sweep sidecar (not this bundle)' : 'from bundle derived.certaintyCurve'} · {curve.realizations.length} realizations tested{curve.rayStepM ? ` · ray step ${curve.rayStepM} m` : ''} · {curve.points.length} sampled heights (no values between them)
          </span>
        </div>
        <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="Sun-centre visibility percent against mast height: nominal value with min–max range over the evaluated terrain realizations, at the sampled heights only">
          {yTicks.map((t) => (
            <g key={t}>
              <line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} className="grid" />
              <text x={M.l - 6} y={y(t) + 4} className="tick" textAnchor="end">
                {t}%
              </text>
            </g>
          ))}
          <path d={band} className="range-band guide" />
          <path d={path((p) => p.nominal.sunPct)} className="curve sun guide" />
          {curve.points.map((p) => (
            <line key={`w${p.mastM}`} x1={x(p.mastM)} x2={x(p.mastM)} y1={y(p.max.sunPct)} y2={y(p.min.sunPct)} className="whisker" data-testid={`cert-whisker-${p.mastM}`} data-min={p.min.sunPct} data-max={p.max.sunPct} />
          ))}
          {(curve.requirements ?? []).filter((r) => /sun/.test((r as { metric?: string; id?: string }).metric ?? r.id ?? '')).map((r) => (
            <g key={r.threshold} className="threshold">
              <line x1={M.l} x2={W - M.r} y1={y(r.threshold)} y2={y(r.threshold)} />
              <text x={W - M.r} y={y(r.threshold) - 4} className="chart-label" textAnchor="end">
                team requirement: Sun {r.op} {r.threshold} %
              </text>
            </g>
          ))}
          {curve.points.map((p) => (
            <g key={p.mastM}>
              <circle cx={x(p.mastM)} cy={y(p.nominal.sunPct)} r={4} className="target-dot sun-dot" />
              {scenarioForMast(p.mastM) ? (
                <text
                  x={x(p.mastM)}
                  y={H - 10}
                  className="tick tick-link"
                  textAnchor="middle"
                  role="button"
                  tabIndex={0}
                  data-testid={`cert-mast-${p.mastM}`}
                  onClick={() => setScenario(scenarioForMast(p.mastM)!.id)}
                  onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && setScenario(scenarioForMast(p.mastM)!.id)}
                >
                  <title>{`select the bundle scenario for the ${p.mastM} m mast`}</title>
                  {p.mastM} m
                </text>
              ) : (
                <text x={x(p.mastM)} y={H - 10} className="tick" textAnchor="middle">
                  {p.mastM} m
                </text>
              )}
            </g>
          ))}
          {curve.minTestedFeasibleMastM !== null && (
            <g className="marker-feasible">
              <line x1={x(curve.minTestedFeasibleMastM)} x2={x(curve.minTestedFeasibleMastM)} y1={M.t} y2={H - M.b} />
              <text x={x(curve.minTestedFeasibleMastM) + 5} y={H - M.b - 8} className="chart-label">
                min tested feasible {curve.minTestedFeasibleMastM} m
              </text>
            </g>
          )}
          {curve.agreementMastM !== null && (
            <g className="marker-agree">
              <line x1={x(curve.agreementMastM)} x2={x(curve.agreementMastM)} y1={M.t} y2={H - M.b} />
              <text x={x(curve.agreementMastM) + 5} y={H - M.b - 24} className="chart-label">
                agreement (spread ≤ {curve.agreementToleranceP} pt) {curve.agreementMastM} m
              </text>
            </g>
          )}
        </svg>
        {curve.heightByRequirement && (
          <ul className="cert-text">
            {Object.entries(curve.heightByRequirement).map(([req, h]) => {
              const row = h === null ? null : curve.points.find((q) => q.mastM === h);
              const pass = row?.passBy?.[req];
              return (
                <li key={req} data-testid={`cert-text-${req}`}>
                  <strong>{reqLabel(req)}:</strong>{' '}
                  {h === null
                    ? `no tested mast up to ${Math.max(...curve.points.map((q) => q.mastM))} m passes on every map`
                    : `passes on ${pass ? `${pass.k}/${pass.n}` : 'every'} evaluated alternate terrain realizations from a ${h} m mast`}
                  {lowCoverage && ` · the maps cover only ${covPct} of the terrain that controls this result`}
                </li>
              );
            })}
          </ul>
        )}
        {curve.note && <p className="warn small">{curve.note}</p>}
        <details className="dec-more" data-testid="cert-details">
          <summary>All {curve.points.length} sampled heights · pass counts · method and sources</summary>
          {side && (
          <p className="note small" data-testid="certainty-source">
            <strong>{side.status.replace(/_/g, ' ')}</strong> · {side.source.what}. a-science {side.source.repo_commit}; CSV SHA-256{' '}
            {side.source.files.map((f) => (
              <span key={f.path} className="mono" title={`${f.path} ${f.sha256}`}>
                {f.sha256.slice(0, 10)}…{' '}
              </span>
            ))}
            {side.source.solver_note}
          </p>
        )}
        <table className="constraints">
          <thead>
            <tr>
              <th scope="col">Mast</th>
              <th scope="col">Sun nominal</th>
              <th scope="col">Sun min–max</th>
              <th scope="col">Both min–max</th>
              <th scope="col">Passing (per requirement, realizations tested)</th>
              {hasGap && <th scope="col">Longest Sun gap</th>}
              {hasCov && <th scope="col">Coverage inside</th>}
            </tr>
          </thead>
          <tbody>
            {curve.points.map((p) => (
              <tr key={p.mastM} className={v.scenario && mastOf(v.scenario) === p.mastM ? 'is-selected' : ''}>
                <th scope="row">
                  {scenarioForMast(p.mastM) ? (
                    <button type="button" className="linkish" onClick={() => setScenario(scenarioForMast(p.mastM)!.id)} title="select the bundle scenario for this mast">
                      {p.mastM} m
                    </button>
                  ) : (
                    `${p.mastM} m`
                  )}
                </th>
                <td>{fmtPct(p.nominal.sunPct)}</td>
                <td>
                  {fmtPct(p.min.sunPct)}–{fmtPct(p.max.sunPct)}
                </td>
                <td>{p.min.bothPct !== undefined ? `${fmtPct(p.min.bothPct)}–${fmtPct(p.max.bothPct)}` : '—'}</td>
                <td data-testid={`cert-pass-${p.mastM}`}>
                  {p.passBy && Object.keys(p.passBy).length
                    ? Object.entries(p.passBy)
                        .map(([k, x]) => `${reqLabel(k)} ${x.k}/${x.n}`)
                        .join(' · ')
                    : p.nPass === null
                      ? 'no requirements'
                      : `${p.nPass} / ${p.nModels}`}
                </td>
                {hasGap && <td>{p.nominal.longestSunGapH !== undefined ? `${p.nominal.longestSunGapH.toFixed(1)} h` : '—'}</td>}
                {hasCov && <td>{p.coverageInside == null ? '—' : `${(p.coverageInside * 100).toFixed(0)}%`}</td>}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="muted small">
          {side ? 'Minimum tested feasible height' : 'Certainty height as the bundle defines it (check the bundle: team requirements, or 100 % Sun on every map)'}: <strong data-testid="min-feasible">{curve.minTestedFeasibleMastM === null ? 'none in sweep' : `${curve.minTestedFeasibleMastM} m`}</strong> · agreement height:{' '}
          <strong data-testid="agreement">{curve.agreementMastM === null ? 'none in sweep' : `${curve.agreementMastM} m`}</strong>
          {Number.isFinite(curve.agreementToleranceP) ? ` (Sun spread ≤ ${curve.agreementToleranceP} pt)` : ''}
          {side && side.allMaps100PctSunMastM !== null && (
            <>
              {' '}
              · Sun 100 % on every tested map from: <strong data-testid="all-100">{side.allMaps100PctSunMastM} m</strong>
            </>
          )}
          . These are different quantities{side ? '; the first uses the team requirements (Sun ≥ 70 %, Sun+Earth ≥ 40 %), not NASA mission requirements' : ''}. Sampled heights only: the
          connecting line is a guide, not extra solver runs. Agreement across the tested realizations is not a guarantee about the real terrain, and never a probability.
        </p>
        </details>
      </section>
    );
  }

  return (
    <section className="panel" aria-labelledby="ch-title" data-testid="certainty-height">
      <div className="panel-head">
        <h2 id="ch-title">Certainty height · mast sweep</h2>
        <span className="muted">{masts.length ? 'not in bundle · showing the bundle’s single-realization mast scenarios instead' : 'not in bundle'}</span>
      </div>
      {masts.length ? (
        <>
          <table className="constraints">
            <thead>
              <tr>
                <th scope="col">Mast</th>
                <th scope="col">Sun centre</th>
                <th scope="col">Earth centre</th>
                <th scope="col">Both</th>
                <th scope="col">Longest Sun gap</th>
                <th scope="col">Longest Earth gap</th>
              </tr>
            </thead>
            <tbody>
              {[...(baseline ? [{ mastM: baseline.observer?.mastM ?? Number.NaN, scenario: baseline, isBase: true }] : []), ...masts.map((m) => ({ ...m, isBase: false }))].map((row) => (
                <tr key={row.scenario.id} className={v.scenario?.id === row.scenario.id ? 'is-selected' : ''}>
                  <th scope="row">
                    <button type="button" className="linkish" onClick={() => setScenario(row.scenario.id)} data-testid="mast-row">
                      {Number.isFinite(row.mastM) ? `${row.mastM} m` : '?'}
                      {row.isBase ? ' (baseline)' : ''}
                    </button>
                  </th>
                  <td>{fmtPct(metric(row.scenario, 'sun_center_visible_pct')?.value)}</td>
                  <td>{fmtPct(metric(row.scenario, 'earth_center_visible_pct')?.value)}</td>
                  <td>{fmtPct(metric(row.scenario, 'sun_and_earth_center_visible_pct')?.value)}</td>
                  <td>{metric(row.scenario, 'longest_sun_center_hidden_h') ? `${metric(row.scenario, 'longest_sun_center_hidden_h')!.value.toFixed(1)} h` : '—'}</td>
                  <td>{metric(row.scenario, 'longest_earth_center_hidden_h') ? `${metric(row.scenario, 'longest_earth_center_hidden_h')!.value.toFixed(1)} h` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">
            One terrain realization per mast: no min/max over clones, no feasible or agreement height. The sweep across PGDA 78 clones (derived.certaintyCurve) is the science branch's P2 item; until it arrives nothing here says a mast is robust.
          </p>
        </>
      ) : (
        <p className="note">No mast-height scenarios in this bundle. The viewer does not recompute horizons for other masts.</p>
      )}
    </section>
  );
}
