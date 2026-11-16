import { useState } from 'react';
import { DECISION6D_FILE, blockDim, blockMetric, type Decision6D } from '../bundle/scenarioCubeV2';
import { ENGINEERING_LABEL, GEOMETRY_LABEL, fmtVal } from './Decision6D';

/**
 * Pareto view over the 81 positions (decision6d.json `pareto__positions`, science/decision/pareto.py). Display only.
 * Each axis shows the nominal map value and its range over the 21 maps; each axis carries its own source label.
 */
const BLOCK = 'pareto__positions';
const AXES: { key: string; title: string; units: string; sense: 'max' | 'min' }[] = [
  { key: 'sun_12mo', title: 'Sun (12 mo)', units: '%', sense: 'max' },
  { key: 'earth_12mo', title: 'Earth line of sight (12 mo)', units: '%', sense: 'max' },
  { key: 'slope', title: 'Landing slope', units: 'deg', sense: 'min' },
  { key: 'energy', title: 'Energy: starts the battery survives', units: '%', sense: 'max' },
];

export function Decision6DPareto({ d }: { d: Decision6D }) {
  const c = d.cube;
  const [robust, setRobust] = useState(true);
  const P = blockDim(c, BLOCK);
  if (!P) return null;
  const labels = P.value_labels ?? P.values.map(String);
  const front = (blockMetric(c, BLOCK, robust ? 'on_front_robust' : 'on_front_nominal') ?? []) as boolean[];
  const other = (blockMetric(c, BLOCK, robust ? 'on_front_nominal' : 'on_front_robust') ?? []) as boolean[];
  const m = (k: string) => (blockMetric(c, BLOCK, k) ?? []) as number[];
  const tag = (k: string) => {
    const prov = c.derived?.[BLOCK]?.metrics[`${k}_nominal`]?.provenance ?? '';
    return prov.includes('ENGINEERING') ? ENGINEERING_LABEL : GEOMETRY_LABEL;
  };
  const idx = front.map((f, i) => (f ? i : -1)).filter((i) => i >= 0);
  return (
    <section
      className="panel decision6d-pareto"
      data-testid="d6-pareto"
      data-source={`decision6d ${c.cube_id} ${BLOCK}`}
      data-result-id={`${c.cube_id}#${BLOCK}`}
      data-label={ENGINEERING_LABEL}
    >
      <div className="panel-head">
        <h2>Trade-offs · positions no other position beats on every axis</h2>
      </div>
      <p className="small">
        81 positions of the ±100 m square (1 m mast). A position is on the front when no other position is at least as good on all four axes
        and better on one.{' '}
        <label className="d6-inline">
          <input type="checkbox" checked={robust} onChange={(e) => setRobust(e.target.checked)} data-testid="d6-pareto-robust" /> use the
          worst of the 21 maps on each axis
        </label>
      </p>
      <ul className="small d6-axes" data-testid="d6-pareto-axes">
        {AXES.map((a) => (
          <li key={a.key} data-label={tag(a.key)}>
            <b>{a.title}</b> ({a.sense === 'max' ? 'higher' : 'lower'} is better): {c.derived?.[BLOCK]?.metrics[`${a.key}_nominal`]?.label.replace(/: nominal map$/, '')}{' '}
            <span className="src-tag">{tag(a.key)}</span>
          </li>
        ))}
        <li data-testid="d6-pareto-ice">
          <b>Distance to ice</b>: not shown. No cited public ice layer (LRO LAMP, Diviner, Chandrayaan-1 M3) is in the data cache yet.
        </li>
      </ul>
      <p className="small" data-testid="d6-pareto-count" data-value={idx.length}>
        {idx.length} of {labels.length} positions are on the {robust ? 'worst-case' : 'nominal-map'} front.
      </p>
      <div className="table-scroll">
        <table className="constraints flip-table" data-testid="d6-pareto-table">
          <thead>
            <tr>
              <th>Position</th>
              {AXES.map((a) => (
                <th key={a.key}>{a.title}: nominal [range over 21 maps]</th>
              ))}
              <th>Also on the other front</th>
            </tr>
          </thead>
          <tbody>
            {idx.map((i) => (
              <tr key={i} data-testid={`d6-pareto-${i}`} data-trace={`${DECISION6D_FILE}#${BLOCK}[${i}]`}>
                <td>{labels[i]}</td>
                {AXES.map((a) => (
                  <td key={a.key} data-label={tag(a.key)}>
                    {fmtVal(m(`${a.key}_nominal`)[i], a.units)} [{fmtVal(m(`${a.key}_min`)[i], a.units)} – {fmtVal(m(`${a.key}_max`)[i], a.units)}]
                  </td>
                ))}
                <td>{other[i] ? 'yes' : 'no'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        Worst-case front uses each axis&apos;s worst map separately, a conservative corner rather than one real map. Ranges are over 21
        deterministic maps, not confidence intervals. Earth line of sight is geometry, not link availability. The energy axis is the share of
        the 366 daily start dates on which the assumed 10 kWh battery holds its reserve (a share of dates, not a probability; ENGINEERING
        ASSUMPTION: illustrative array, battery, load). The worst-window margin is not used as an axis: some 14-day windows are fully dark,
        so it is the same zero-generation value at most positions.
      </p>
    </section>
  );
}
