import { useEffect, useState } from 'react';
import type { View } from '../store/view';
import { derivedCell, derivedDims, loadCube, loadCubeIndex, type ScenarioCube } from '../bundle/scenarioCube';

/**
 * Phase 5 trade view: mast height vs battery capacity needed. ENGINEERING ASSUMPTION.
 * Display-only: every number is `derived.trade` of data/cubes/<site>/energy.json.gz (science/energy/build_energy.py).
 * The assumptions (cube `fixed`, from science/energy/assumptions.yaml) are listed next to the chart.
 */
export const ENERGY_FILE = 'energy.json.gz';
export const TRADE_SERIES = [
  { key: 'nominal_demo_kwh', short: 'nominal · 2026-11-14 start', cls: 'et-nom' },
  { key: 'worst20_demo_kwh', short: 'worst of 20 maps · 2026-11-14 start', cls: 'et-w20' },
  { key: 'nominal_worst_start_kwh', short: 'nominal · worst of 366 starts', cls: 'et-nom-s' },
  { key: 'worst20_worst_start_kwh', short: 'worst of 20 maps · worst of 366 starts', cls: 'et-w20-s' },
] as const;

const ASSUMPTION_ROWS: [string, string, string][] = [
  ['solar_constant_w_m2', 'Solar constant at 1 au', 'W/m²'],
  ['array_area_m2', 'Array area (one face)', 'm²'],
  ['array_efficiency', 'Array efficiency (lumped, at bus)', ''],
  ['fixed_azimuth_deg', 'Fixed array azimuth (0 = N, 90 = E)', '°'],
  ['load_constant_w', 'Constant load', 'W'],
  ['load_scheduled', 'Scheduled load', ''],
  ['battery_capacity_wh', 'Battery capacity (for SoC / k of 20)', 'Wh'],
  ['reserve_wh', 'Minimum reserve', 'Wh'],
  ['initial_soc', 'Initial state of charge', '× capacity'],
  ['charge_efficiency', 'Charge efficiency', ''],
  ['discharge_efficiency', 'Discharge efficiency', ''],
  ['window_h', 'Window', 'h'],
];

export function tradeRows(cube: ScenarioCube, arrayIndex: number) {
  const masts = derivedDims(cube, 'trade').find((d) => d.name === 'D_mast')!;
  return masts.values.map((m, j) => ({
    mast: Number(m),
    vals: TRADE_SERIES.map((s) => derivedCell(cube, 'trade', s.key, { D_array: arrayIndex, D_mast: j })),
  }));
}

export function EnergyTrade({ v }: { v: View }) {
  const siteId = v.dataset.site.id;
  const [cube, setCube] = useState<ScenarioCube | null | undefined>(undefined);
  const [arr, setArr] = useState(0);
  useEffect(() => {
    let live = true;
    setCube(undefined);
    loadCubeIndex(siteId)
      .then((ix) => (ix?.cubes.some((c) => c.file === ENERGY_FILE) ? loadCube(siteId, ENERGY_FILE) : null))
      .then((c) => live && setCube(c))
      .catch(() => live && setCube(null));
    return () => {
      live = false;
    };
  }, [siteId]);
  if (cube === undefined) return null;
  if (cube === null || !cube.derived?.trade)
    return (
      <section className="panel energy-trade" data-testid="energy-trade" data-label="ENGINEERING ASSUMPTION">
        <div className="panel-head">
          <h2>Energy · does the battery survive?</h2>
        </div>
        <p className="muted small" data-testid="energy-missing">
          Energy cube not in bundle for this site.
        </p>
      </section>
    );
  const arrays = cube.dims.find((d) => d.name === 'D_array')!;
  const rows = tradeRows(cube, arr);
  const fixed = cube.fixed ?? {};
  return (
    <section className="panel energy-trade" data-testid="energy-trade" data-source={`scenario cube ${cube.cube_id} derived.trade`} data-result-id={cube.cube_id} data-label={cube.label}>
      <div className="panel-head">
        <h2>Energy · does the battery survive? Mast height vs battery needed</h2>
        <span className="pilot-badge">{cube.label}</span>
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
      <TradeChart rows={rows} />
      <div className="table-scroll">
        <table className="constraints" data-testid="energy-table">
          <thead>
            <tr>
              <th scope="col">Mast (array top)</th>
              {TRADE_SERIES.map((s) => (
                <th scope="col" key={s.key}>
                  {s.short} (kWh)
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.mast}>
                <th scope="row">{r.mast} m</th>
                {r.vals.map((x, i) => (
                  <td key={i} data-value={x ?? ''} data-label={cube.label}>
                    {x === null ? 'missing' : x.toFixed(2)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <dl className="energy-assumptions" data-testid="energy-assumptions">
        {ASSUMPTION_ROWS.filter(([k]) => fixed[k] !== undefined).map(([k, lab, u]) => (
          <div key={k}>
            <dt>{lab}</dt>
            <dd>
              {String(fixed[k])} {u}
            </dd>
          </div>
        ))}
      </dl>
      <p className="muted small">
        {cube.label}: battery needed = smallest capacity keeping state of charge ≥ the reserve at every hour of the 14-day window (Python bisection, 1 Wh); it includes the
        reserve. Worst of 20 maps is a range over deterministic PGDA 78 clones, not a probability. Assumptions from <code>{String(fixed.assumptions_file ?? '')}</code>.{' '}
        {cube.limitations?.join(' ')}
      </p>
    </section>
  );
}

function TradeChart({ rows }: { rows: ReturnType<typeof tradeRows> }) {
  const W = 640;
  const H = 180;
  const pad = 28;
  const all = rows.flatMap((r) => r.vals).filter((x): x is number => x !== null);
  const ymax = Math.max(1, ...all) * 1.05;
  const m0 = rows[0]?.mast ?? 0;
  const m1 = rows[rows.length - 1]?.mast ?? 1;
  const x = (m: number) => pad + ((m - m0) / Math.max(m1 - m0, 1)) * (W - 2 * pad);
  const y = (kwh: number) => H - pad - (kwh / ymax) * (H - 2 * pad);
  return (
    <figure className="cube-strip energy-chart" data-testid="energy-chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Battery capacity needed (kWh) against mast height (m)">
        <line x1={pad} x2={W - pad} y1={H - pad} y2={H - pad} className="et-axis" />
        <line x1={pad} x2={pad} y1={pad} y2={H - pad} className="et-axis" />
        {rows.map((r) => (
          <text key={r.mast} x={x(r.mast)} y={H - 8} className="et-tick" textAnchor="middle">
            {r.mast}
          </text>
        ))}
        <text x={pad} y={pad - 8} className="et-tick">
          {ymax.toFixed(0)} kWh
        </text>
        {TRADE_SERIES.map((s, i) => (
          <polyline
            key={s.key}
            className={`et-line ${s.cls}`}
            fill="none"
            points={rows
              .filter((r) => r.vals[i] !== null)
              .map((r) => `${x(r.mast).toFixed(1)},${y(r.vals[i] as number).toFixed(1)}`)
              .join(' ')}
          />
        ))}
      </svg>
      <figcaption className="muted small">
        x = mast height (m), y = battery needed (kWh). {TRADE_SERIES.map((s) => s.short).join(' · ')} (solid / dashed / dotted / dash-dot).
      </figcaption>
    </figure>
  );
}
