import { useEffect, useState } from 'react';
import type { View } from '../store/view';
import { derivedCell, loadCube, loadCubeIndex, type ScenarioCube } from '../bundle/scenarioCube';

/**
 * Phase 5 trade view: mast height vs battery needed (docs/5D_UPGRADES_STATUS.md, science/energy/).
 * DISPLAY ONLY — every number is a precomputed cell of data/cubes/<site>/energy.json.gz (stored × declared scale).
 * Label ENGINEERING ASSUMPTION: the array, battery and load parameters are listed next to the values.
 */
const FILE = 'energy.json.gz';
const LABEL = 'ENGINEERING ASSUMPTION · inputs SOURCE-BASED · UNVALIDATED';

function kwh(v: number | null) {
  return v === null || !Number.isFinite(v) ? '—' : `${v.toFixed(1)} kWh`;
}

export function EnergyTrade({ v }: { v: View }) {
  const siteId = v.dataset.site.id;
  const [cube, setCube] = useState<ScenarioCube | null | undefined>(undefined);
  const [arr, setArr] = useState(0);

  useEffect(() => {
    let live = true;
    setCube(undefined);
    loadCubeIndex(siteId)
      .then((ix) => (ix?.cubes.some((c) => c.file === FILE) ? loadCube(siteId, FILE) : null))
      .then((c) => live && setCube(c))
      .catch(() => live && setCube(null));
    return () => {
      live = false;
    };
  }, [siteId]);

  if (cube === undefined) return null;
  if (cube === null || !cube.derived?.trade)
    return (
      <section className="panel energy-trade" data-testid="energy-trade" data-source="energy cube" data-label={LABEL}>
        <div className="panel-head">
          <h2>Energy · does the battery survive?</h2>
        </div>
        <p className="muted small" data-testid="energy-missing">
          Energy margin not in bundle for this site.
        </p>
      </section>
    );

  const arrays = cube.dims.find((d) => d.name === 'D_array')!;
  const masts = cube.dims.find((d) => d.name === 'D_mast')!;
  const f = cube.fixed ?? {};
  const at = (j: number) => ({ D_array: arr, D_mast: j });
  const rows = masts.values.map((m, j) => ({
    mast: Number(m),
    demoNom: derivedCell(cube, 'trade', 'needed_demo_nominal', at(j)),
    demoWorst: derivedCell(cube, 'trade', 'needed_demo_worst20', at(j)),
    allNom: derivedCell(cube, 'trade', 'needed_all_nominal', at(j)),
    allWorst: derivedCell(cube, 'trade', 'needed_all_worst20', at(j)),
    kAll: derivedCell(cube, 'trade', 'k_ok_all', at(j)),
    share: derivedCell(cube, 'trade', 'share_starts_ok_all20', at(j)),
  }));
  const W = 640;
  const H = 140;
  const ymax = Math.max(1, ...rows.flatMap((r) => [r.allWorst ?? 0, r.demoWorst ?? 0]));
  const x = (j: number) => 30 + (j / Math.max(1, rows.length - 1)) * (W - 40);
  const y = (val: number) => H - 14 - (val / ymax) * (H - 24);
  const poly = (k: 'demoNom' | 'demoWorst' | 'allNom' | 'allWorst') =>
    rows.map((r, j) => (r[k] === null ? null : `${x(j).toFixed(1)},${y(r[k]!).toFixed(1)}`)).filter(Boolean).join(' ');
  const capKwh = Number(f.battery_capacity_wh) / 1000;

  return (
    <section className="panel energy-trade" data-testid="energy-trade" data-source={`scenario cube ${cube.cube_id}`} data-result-id={cube.cube_id} data-label={LABEL}>
      <div className="panel-head">
        <h2>Energy · mast height vs battery needed</h2>
        <span className="pilot-badge" data-testid="energy-label">
          {cube.label}
        </span>
      </div>
      <label className="cube-ctl">
        <span>Array type</span>
        <select value={arr} onChange={(e) => setArr(Number(e.target.value))} data-testid="energy-array">
          {arrays.values.map((_, i) => (
            <option key={i} value={i}>
              {arrays.value_labels?.[i] ?? String(arrays.values[i])}
            </option>
          ))}
        </select>
      </label>
      <figure className="cube-strip" data-testid="energy-chart">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Battery needed versus mast height">
          <polyline points={poly('allWorst')} className="cube-line" fill="none" />
          <polyline points={poly('allNom')} className="cube-line" fill="none" strokeDasharray="4 3" />
          <polyline points={poly('demoWorst')} fill="none" stroke="currentColor" strokeWidth={1.2} />
          <polyline points={poly('demoNom')} fill="none" stroke="currentColor" strokeWidth={1.2} strokeDasharray="4 3" />
          {Number.isFinite(capKwh) && capKwh <= ymax && (
            <line x1={30} x2={W - 10} y1={y(capKwh)} y2={y(capKwh)} className="cube-sel" strokeDasharray="2 4" />
          )}
        </svg>
        <figcaption className="muted small">
          x: array top {String(masts.values[0])}–{String(masts.values[masts.values.length - 1])} m · y: battery needed, 0–{ymax.toFixed(1)} kWh. Orange = every daily start over 12 months (solid worst of 20 maps,
          dashed nominal); grey = 2026-11-14 start (solid worst of 20, dashed nominal); dotted = assumed {capKwh.toFixed(1)} kWh battery.
        </figcaption>
      </figure>
      <div className="table-scroll">
        <table className="constraints" data-testid="energy-table">
          <thead>
            <tr>
              <th scope="col">Array top</th>
              <th scope="col">2026-11-14 start · nominal</th>
              <th scope="col">2026-11-14 start · worst of 20</th>
              <th scope="col">Every start · nominal</th>
              <th scope="col">Every start · worst of 20</th>
              <th scope="col">Maps (of 20) where {capKwh.toFixed(1)} kWh holds every start</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.mast} data-mast={r.mast}>
                <th scope="row">{r.mast} m</th>
                <td data-value={r.demoNom ?? ''}>{kwh(r.demoNom)}</td>
                <td data-value={r.demoWorst ?? ''}>{kwh(r.demoWorst)}</td>
                <td data-value={r.allNom ?? ''}>{kwh(r.allNom)}</td>
                <td data-value={r.allWorst ?? ''}>{kwh(r.allWorst)}</td>
                <td data-value={r.kAll ?? ''}>
                  {r.kAll} of 20 maps · {r.share === null ? '—' : `${r.share.toFixed(1)} %`} of starts hold on all 20
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="muted small" data-testid="energy-assumptions">
        <strong>{cube.label} — assumptions shown with the result</strong> ({String(f.assumptions_file)}): array {String(f.array_area_m2)} m² ×
        efficiency {String(f.array_efficiency)}, S = {String(f.solar_constant_w_m2)} W/m² × (1 au / r)²; fixed array normal {String(f.fixed_array_azimuth_deg)}° az (
        {String(f.fixed_array_azimuth_rule)}); battery {capKwh.toFixed(1)} kWh, charge η {String(f.charge_efficiency)}, discharge η {String(f.discharge_efficiency)},
        reserve {(Number(f.min_reserve_fraction) * 100).toFixed(0)} %, initial {(Number(f.initial_soc_fraction) * 100).toFixed(0)} % at each window start; load{' '}
        {String(f.load_constant_w)} W constant + {String(f.load_scheduled)}. Antenna height: {String(f.antenna_height)}.
      </div>
      <details className="dec-more">
        <summary>Method and caveats</summary>
        <p className="muted small">{cube.description}</p>
        <p className="muted small">
          <strong>trade</strong>: {cube.derived.trade.method}. {cube.derived.trade.caveat}
        </p>
        <p className="muted small">{cube.limitations?.join(' ')}</p>
        <p className="muted small">
          Solver: {cube.provenance.solver}. Commit <code>{cube.provenance.code_commit}</code>.
        </p>
      </details>
    </section>
  );
}
