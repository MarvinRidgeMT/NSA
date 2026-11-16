import { useEffect, useState } from 'react';
import type { View } from '../store/view';
import { derivedCell, loadCube, loadCubeIndex, type ScenarioCube } from '../bundle/scenarioCube';

/**
 * "What matters" bar (Phase 7). Display-only: every share is read from the precomputed
 * data/cubes/<site>/sensitivity.json (science/cube/build_sensitivity.py). The bar shows Shapley shares
 * (sum to 100 % of the spread); the table adds first-order and total shares. Nothing is computed here.
 */
export const SENSITIVITY_FILE = 'sensitivity.json';

const AXIS_LABEL: Record<string, string> = {
  T: 'T · terrain map',
  D_mast: 'D · mast height',
  D_pos: 'D · position',
  S: 'S · window start',
};
const AXIS_CLASS: Record<string, string> = { T: 'wm-t', D_mast: 'wm-d', D_pos: 'wm-d', S: 'wm-s' };

function fmt(v: number | null, d = 1) {
  return v === null || !Number.isFinite(v) ? '—' : v.toFixed(d);
}

const list = (s: unknown) => (typeof s === 'string' && s ? s.split(',') : []);

export function WhatMatters({ v }: { v: View }) {
  const siteId = v.dataset.site.id;
  const [cube, setCube] = useState<ScenarioCube | null | undefined>(undefined);
  useEffect(() => {
    let live = true;
    setCube(undefined);
    loadCubeIndex(siteId)
      .then((ix) => {
        if (!live) return;
        if (!ix?.cubes.some((c) => c.file === SENSITIVITY_FILE)) return setCube(null);
        return loadCube(siteId, SENSITIVITY_FILE).then((c) => live && setCube(c));
      })
      .catch(() => live && setCube(null));
    return () => {
      live = false;
    };
  }, [siteId]);
  if (cube === undefined) return null;
  if (cube === null)
    return (
      <section className="panel what-matters" data-testid="what-matters" data-label="SOURCE-BASED · UNVALIDATED">
        <div className="panel-head">
          <h2>What matters</h2>
        </div>
        <p className="muted small" data-testid="what-matters-missing">
          Sensitivity indices not in bundle for this site.
        </p>
      </section>
    );
  return <WhatMattersView cube={cube} />;
}

export function WhatMattersView({ cube }: { cube: ScenarioCube }) {
  const fx = cube.fixed ?? {};
  const sources = list(fx.sources).concat(fx.axes__energy ? ['energy'] : []);
  const [src, setSrc] = useState(sources.includes('position') ? 'position' : sources[0]);
  const metrics = src === 'energy' ? list(fx.metrics__energy) : list(fx.metrics);
  const labels = src === 'energy' ? metrics : list(fx.metric_labels);
  const [metric, setMetric] = useState(metrics[0]);
  const m = metrics.includes(metric) ? metric : metrics[0];
  const key = `sobol__${src}__${m}`;
  const block = cube.derived?.[key];
  const axes = list(fx[`axes__${src}`]);
  const get = (name: string) => (block?.metrics[name] ? derivedCell(cube, key, name, {}) : null);
  const rows = axes.map((a) => ({ a, first: get(`first_pct__${a}`), total: get(`total_pct__${a}`), shap: get(`shapley_pct__${a}`) }));
  const top = rows.reduce<(typeof rows)[number] | null>((b, r) => (r.shap !== null && (!b || (b.shap ?? -1) < r.shap) ? r : b), null);
  const sd = get('sd');
  const noSpread = get('no_spread') === 1;
  const inter = get('interaction_pct');
  const sdUnits = block?.metrics.sd?.units ?? '';
  const chk = cube.derived?.emulator_check;
  const c = (k: string) => (chk?.metrics[k] ? derivedCell(cube, 'emulator_check', k, {}) : null);
  const nCand = cube.dims[0]?.values.length ?? 0;
  const source = `scenario cube ${cube.cube_id} derived ${key}`;
  const energyMissing = fx.energy_margin === 'not in bundle';

  return (
    <section className="panel what-matters" data-testid="what-matters" data-source={source} data-result-id={cube.cube_id} data-label={cube.label}>
      <div className="panel-head">
        <h2>What matters · share of spread by sub-axis</h2>
        <span className="pilot-badge">{cube.label}</span>
      </div>
      <div className="cube-ctls">
        <label className="cube-ctl">
          <span>Scenario set</span>
          <select value={src} onChange={(e) => setSrc(e.target.value)} data-testid="wm-source">
            {sources.map((s) => (
              <option key={s} value={s}>
                {String(fx[`title__${s}`] ?? s)}
              </option>
            ))}
          </select>
        </label>
        <label className="cube-ctl">
          <span>Metric</span>
          <select value={m} onChange={(e) => setMetric(e.target.value)} data-testid="wm-metric">
            {metrics.map((k, i) => (
              <option key={k} value={k}>
                {labels[i] ?? k}
              </option>
            ))}
          </select>
        </label>
      </div>
      {!block ? (
        <p className="muted small" data-testid="wm-block-missing">
          Not in bundle.
        </p>
      ) : noSpread ? (
        <p className="muted small" data-testid="wm-no-spread">
          No spread: every cell of this scenario set has the same value{sd !== null ? ` (SD ${fmt(sd, 2)} ${sdUnits})` : ''}, so the shares are
          undefined.
        </p>
      ) : (
        <>
          <div className="wm-bar" role="img" aria-label={`Shapley shares: ${rows.map((r) => `${r.a} ${fmt(r.shap)} %`).join(', ')}`} data-testid="wm-bar">
            {rows.map((r) => (
              <span
                key={r.a}
                className={`wm-seg ${AXIS_CLASS[r.a] ?? 'wm-o'}`}
                style={{ width: `${Math.max(0, r.shap ?? 0)}%` }}
                data-testid={`wm-seg-${r.a}`}
                data-value={r.shap ?? ''}
                title={`${AXIS_LABEL[r.a] ?? r.a}: ${fmt(r.shap)} %`}
              />
            ))}
          </div>
          <p className="small" data-testid="wm-top">
            Largest share: <strong>{top ? AXIS_LABEL[top.a] ?? top.a : '—'}</strong> {top ? `${fmt(top.shap)} %` : ''} of the spread
            {sd !== null ? ` (spread = SD ${fmt(sd, 2)} ${sdUnits})` : ''}; interactions {fmt(inter)} %.
          </p>
          <table className="constraints wm-table" data-testid="wm-table">
            <thead>
              <tr>
                <th scope="col">Sub-axis</th>
                <th scope="col">Shapley</th>
                <th scope="col">First-order</th>
                <th scope="col">Total</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.a} data-testid={`wm-row-${r.a}`}>
                  <th scope="row">
                    <i className={`wm-key ${AXIS_CLASS[r.a] ?? 'wm-o'}`} aria-hidden="true" /> {AXIS_LABEL[r.a] ?? r.a}
                  </th>
                  <td data-value={r.shap ?? ''}>{fmt(r.shap)} %</td>
                  <td data-value={r.first ?? ''}>{fmt(r.first)} %</td>
                  <td data-value={r.total ?? ''}>{fmt(r.total)} %</td>
                </tr>
              ))}
              <tr data-testid="wm-row-energy">
                <th scope="row">Energy margin</th>
                <td colSpan={3} className={energyMissing ? 'cube-missing-cell' : ''}>
                  {energyMissing ? 'not in bundle' : String(fx.energy_margin ?? '—')}
                </td>
              </tr>
            </tbody>
          </table>
        </>
      )}
      <details className="dec-more" data-testid="wm-details">
        <summary>Method and caveat</summary>
        <p className="muted small">
          <strong>Caveat.</strong> {block?.caveat}
        </p>
        <p className="muted small">
          <strong>Method.</strong> {block?.method}
        </p>
        <p className="muted small">{String(fx.M_axis ?? '')}</p>
        {chk && (
          <p className="muted small" data-testid="wm-emulator">
            <strong>Position emulator (search only).</strong> {chk.method} Re-check on {nCand} off-grid candidates: Spearman ρ ={' '}
            {fmt(c('spearman_objective'), 3)} (target {fmt(c('target_rho'), 2)}), mean error {fmt(c('mae_objective'), 2)} pct pts, max{' '}
            {fmt(c('max_abs_objective'), 2)} pct pts; per window ρ = {fmt(c('spearman_cell_sun_pct'), 3)}. Best re-checked position{' '}
            {fmt(c('best_checked_sun_12mo'), 2)} % 12-month Sun (worst map {fmt(c('best_checked_worst_map_sun_12mo'), 2)} %) vs best grid cell{' '}
            {fmt(c('grid_best_sun_12mo'), 2)} %. {chk.caveat}
          </p>
        )}
        <p className="muted small">{cube.limitations?.join(' ')}</p>
        <p className="muted small">
          Commit <code>{cube.provenance.code_commit}</code>. Inputs: {cube.provenance.inputs.map((i) => `${i.path} (${i.sha256.slice(0, 12)}…)`).join('; ')}.
        </p>
      </details>
    </section>
  );
}
