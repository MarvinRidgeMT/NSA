import { useEffect, useMemo, useState } from 'react';
import type { View } from '../store/view';
import {
  cell,
  derivedCell,
  derivedDims,
  derivedSlice1d,
  loadCube,
  loadCubeIndex,
  slice1d,
  type CubeDim,
  type CubeIndex,
  type ScenarioCube,
} from '../bundle/scenarioCube';

/**
 * Scenario-cube slicer (Phase 1, docs/SCENARIO_CUBE_CONTRACT.md). One control per sub-axis; the strip runs
 * along one free axis (S or D) and shows: solid line = the selected map (computed), band = min–max over the
 * 21 terrain maps (precomputed `band_over_T`), hatch = missing cells. Every number is a slice of the cube.
 */
const QUESTION: Record<string, string> = {
  uncertainty_terrain: 'T · how sure?',
  uncertainty_model: 'M · do the data products agree?',
  design: 'D · what fixes it?',
  schedule: 'S · when?',
  requirement: 'R · against which requirement?',
  target: 'link · who can we talk to?',
  site: 'site',
};

function fmt(v: number | null, d = 2) {
  return v === null || !Number.isFinite(v) ? '—' : v.toFixed(d);
}

function valueLabel(d: CubeDim, i: number) {
  const l = d.value_labels?.[i] ?? String(d.values[i]);
  return d.units && !d.value_labels && d.units !== 'grid m (dx,dy)' ? `${l} ${d.units}` : l;
}

export function CubeSlicer({ v }: { v: View }) {
  const siteId = v.dataset.site.id;
  const [index, setIndex] = useState<CubeIndex | null | undefined>(undefined);
  const [file, setFile] = useState<string | null>(null);
  const [cube, setCube] = useState<ScenarioCube | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setIndex(undefined);
    setCube(null);
    setErr(null);
    loadCubeIndex(siteId)
      .then((ix) => {
        if (!live) return;
        setIndex(ix);
        const first = ix?.cubes.find((c) => c.dims.includes('S'))?.file ?? ix?.cubes[0]?.file ?? null;
        setFile(first);
      })
      .catch(() => live && setIndex(null));
    return () => {
      live = false;
    };
  }, [siteId]);

  useEffect(() => {
    if (!file) return;
    let live = true;
    setCube(null);
    loadCube(siteId, file)
      .then((c) => live && setCube(c))
      .catch((e: Error) => live && setErr(e.message));
    return () => {
      live = false;
    };
  }, [siteId, file]);

  if (index === undefined) return null;
  if (index === null)
    return (
      <section className="panel cube-slicer" data-testid="cube-slicer" data-label="SOURCE-BASED · UNVALIDATED">
        <div className="panel-head">
          <h2>Scenario cube</h2>
        </div>
        <p className="muted small" data-testid="cube-missing">
          Scenario cube not in bundle for this site.
        </p>
      </section>
    );
  return (
    <section
      className="panel cube-slicer"
      data-testid="cube-slicer"
      data-source={cube ? `scenario cube ${cube.cube_id}` : 'scenario cube'}
      data-result-id={cube?.cube_id}
      data-label={index.label}
    >
      <div className="panel-head">
        <h2>Scenario cube · named sub-axes</h2>
        <span className="pilot-badge">{index.label}</span>
      </div>
      <label className="cube-ctl">
        <span>Cube</span>
        <select value={file ?? ''} onChange={(e) => setFile(e.target.value)} data-testid="cube-file">
          {index.cubes.map((c) => (
            <option key={c.file} value={c.file}>
              {c.title}
            </option>
          ))}
        </select>
      </label>
      {err && (
        <p className="error" role="alert">
          {err}
        </p>
      )}
      {!cube && !err && <p className="muted small">Loading cube…</p>}
      {cube && (cube.dims.length === 1 ? <ProductTable cube={cube} /> : <Slicer key={cube.cube_id} cube={cube} />)}
    </section>
  );
}

function ProductTable({ cube }: { cube: ScenarioCube }) {
  const d = cube.dims[0];
  const ms = Object.entries(cube.metrics);
  return (
    <div className="table-scroll" data-testid="cube-products">
      <p className="muted small">{QUESTION[d.kind]} · {cube.description}</p>
      <table className="constraints">
        <thead>
          <tr>
            <th scope="col">{d.label}</th>
            {ms.map(([k, m]) => (
              <th scope="col" key={k}>
                {m.label} ({m.units})
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {d.values.map((_, i) => (
            <tr key={i}>
              <th scope="row">{valueLabel(d, i)}</th>
              {ms.map(([k, m]) => {
                const val = cell(cube, k, { [d.name]: i });
                return (
                  <td key={k} className={val === null ? 'cube-missing-cell' : ''} data-value={val ?? ''}>
                    {val === null ? 'not in source' : `${fmt(val, m.decimals ?? 2)} ${m.units}`}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">{cube.limitations?.join(' ')}</p>
    </div>
  );
}

function Slicer({ cube }: { cube: ScenarioCube }) {
  const metricKeys = Object.keys(cube.metrics);
  const [metric, setMetric] = useState(metricKeys.includes('sun_earth_pct') ? 'sun_earth_pct' : metricKeys[0]);
  const design = cube.dims.find((d) => d.kind === 'design');
  const scheduleDim = (cube.dims.find((d) => d.kind === 'schedule') ?? cube.dims[cube.dims.length - 1]).name;
  const [free, setFree] = useState<string>(scheduleDim);
  const [at, setAt] = useState<Record<string, number>>(() => Object.fromEntries(cube.dims.map((d) => [d.name, d.nominal_index ?? 0])));
  const [r, setR] = useState(0);
  useEffect(() => {
    setAt(Object.fromEntries(cube.dims.map((d) => [d.name, d.nominal_index ?? 0])));
    setFree(scheduleDim);
  }, [cube, scheduleDim]);
  const m = cube.metrics[metric];
  const freeDim = cube.dims.find((d) => d.name === free)!;
  const line = useMemo(() => slice1d(cube, metric, free, at), [cube, metric, free, at]);
  const bandKey = cube.derived?.band_over_T && free !== 'T' ? 'band_over_T' : null;
  const otherAt = useMemo(() => Object.fromEntries(Object.entries(at).filter(([k]) => k !== 'T')), [at]);
  const lo = useMemo(() => (bandKey ? derivedSlice1d(cube, bandKey, `${metric}_min`, free, otherAt) : null), [cube, bandKey, metric, free, otherAt]);
  const hi = useMemo(() => (bandKey ? derivedSlice1d(cube, bandKey, `${metric}_max`, free, otherAt) : null), [cube, bandKey, metric, free, otherAt]);
  const value = cell(cube, metric, at);
  const bandAt = bandKey ? [derivedCell(cube, bandKey, `${metric}_min`, otherAt), derivedCell(cube, bandKey, `${metric}_max`, otherAt)] : null;
  const kd = cube.derived?.k_of_N;
  const kAt = kd && design && at.S !== undefined ? { R: r, [design.name]: at[design.name], S: at.S } : null;
  const k = kAt ? derivedCell(cube, 'k_of_N', 'k_pass', kAt) : null;
  const nomPass = kAt ? derivedCell(cube, 'k_of_N', 'nominal_pass', kAt) : null;
  const regret = cube.derived?.regret && at.S !== undefined ? derivedCell(cube, 'regret', 'regret_max_pct', { S: at.S }) : null;
  const chosen = cube.derived?.regret && at.S !== undefined ? derivedCell(cube, 'regret', 'chosen_index', { S: at.S }) : null;
  const flipShare = design && cube.derived?.decision_changes ? derivedCell(cube, 'decision_changes', 'share_starts_verdict_depends_on_T', { [design.name]: at[design.name] }) : null;
  const rDim = kd ? derivedDims(cube, 'k_of_N').find((d) => d.name === 'R') : undefined;
  const dec = m.decimals ?? 2;

  return (
    <div className="cube-body">
      <div className="cube-ctls" data-testid="cube-controls">
        <label className="cube-ctl">
          <span>Metric</span>
          <select value={metric} onChange={(e) => setMetric(e.target.value)} data-testid="cube-metric">
            {metricKeys.map((k) => (
              <option key={k} value={k}>
                {cube.metrics[k].label}
              </option>
            ))}
          </select>
        </label>
        {cube.dims.map((d) => (
          <div className={`cube-ctl ${free === d.name ? 'free' : ''}`} key={d.name} data-testid={`cube-dim-${d.name}`}>
            <span title={d.label}>
              {QUESTION[d.kind] ?? d.kind} <small className="muted">({d.name})</small>
            </span>
            {d.values.length > 40 ? (
              <input
                type="range"
                min={0}
                max={d.values.length - 1}
                value={at[d.name]}
                onChange={(e) => setAt({ ...at, [d.name]: Number(e.target.value) })}
                aria-label={d.label}
                data-testid={`cube-ctl-${d.name}`}
              />
            ) : (
              <select value={at[d.name]} onChange={(e) => setAt({ ...at, [d.name]: Number(e.target.value) })} aria-label={d.label} data-testid={`cube-ctl-${d.name}`}>
                {d.values.map((_, i) => (
                  <option key={i} value={i}>
                    {valueLabel(d, i)}
                  </option>
                ))}
              </select>
            )}
            <small className="cube-val">{valueLabel(d, at[d.name])}</small>
            {d.kind !== 'uncertainty_terrain' && (
              <button type="button" className={`btn btn-small ${free === d.name ? 'on' : ''}`} onClick={() => setFree(d.name)} data-testid={`cube-free-${d.name}`}>
                strip along {d.name}
              </button>
            )}
          </div>
        ))}
        {rDim && (
          <label className="cube-ctl">
            <span>{QUESTION.requirement}</span>
            <select value={r} onChange={(e) => setR(Number(e.target.value))} data-testid="cube-ctl-R">
              {rDim.values.map((_, i) => (
                <option key={i} value={i}>
                  {valueLabel(rDim, i)}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      <CubeStrip line={line} lo={lo} hi={hi} dim={freeDim} sel={at[free]} units={m.units} label={m.label} />
      <dl className="cube-card" data-testid="cube-card" data-source={`scenario cube ${cube.cube_id}`} data-label={cube.label}>
        <div>
          <dt>{m.label} · this cell</dt>
          <dd data-testid="cube-card-value" data-value={value ?? ''}>
            {value === null ? 'missing' : `${fmt(value, dec)} ${m.units}`}
          </dd>
        </div>
        {bandAt && (
          <div>
            <dt>T · range over 21 maps</dt>
            <dd data-testid="cube-card-band" data-min={bandAt[0] ?? ''} data-max={bandAt[1] ?? ''}>
              {fmt(bandAt[0], dec)}–{fmt(bandAt[1], dec)} {m.units}
            </dd>
          </div>
        )}
        {k !== null && (
          <div>
            <dt>R · clone maps passing</dt>
            <dd data-testid="cube-card-k" data-value={k}>
              {k} of 20 maps · nominal {nomPass ? 'passes' : 'fails'}
            </dd>
          </div>
        )}
        {regret !== null && design && (
          <div>
            <dt>D · regret if chosen on nominal</dt>
            <dd data-testid="cube-card-regret" data-value={regret}>
              {fmt(regret, 2)} pct pts (Sun+Earth) · nominal pick {chosen !== null ? valueLabel(design, chosen) : '—'}
            </dd>
          </div>
        )}
        {flipShare !== null && (
          <div>
            <dt>D · verdict depends on map</dt>
            <dd data-testid="cube-card-flip" data-value={flipShare}>
              {fmt(flipShare, 1)} % of starts
            </dd>
          </div>
        )}
      </dl>
      <details className="dec-more">
        <summary>Method, sources and caveats</summary>
        <p className="muted small">{cube.description} Fixed: {Object.entries(cube.fixed ?? {}).map(([a, b]) => `${a} = ${b}`).join(', ')}.</p>
        {Object.entries(cube.derived ?? {}).map(([key, d]) => (
          <p className="muted small" key={key}>
            <strong>{key}</strong>: {d.method}. {d.caveat}
          </p>
        ))}
        <p className="muted small">{cube.limitations?.join(' ')}</p>
        <p className="muted small">
          Solver: {cube.provenance.solver}. Commit <code>{cube.provenance.code_commit}</code>. Inputs:{' '}
          {cube.provenance.inputs.map((i) => `${i.path} (${i.sha256.slice(0, 12)}…)`).join('; ')}.
        </p>
      </details>
    </div>
  );
}

function CubeStrip({ line, lo, hi, dim, sel, units, label }: { line: (number | null)[]; lo: (number | null)[] | null; hi: (number | null)[] | null; dim: CubeDim; sel: number; units: string; label: string }) {
  const W = 640;
  const H = 120;
  const n = line.length;
  const all = [...line, ...(lo ?? []), ...(hi ?? [])].filter((x): x is number => x !== null);
  const ymax = units === '%' ? 100 : Math.max(1, ...all);
  const x = (i: number) => (n <= 1 ? W / 2 : (i / (n - 1)) * W);
  const y = (val: number) => H - (val / ymax) * H;
  const pts = line.map((val, i) => (val === null ? null : `${x(i).toFixed(1)},${y(val).toFixed(1)}`)).filter(Boolean).join(' ');
  let band = '';
  if (lo && hi) {
    const up = hi.map((val, i) => (val === null ? null : `${x(i).toFixed(1)},${y(val).toFixed(1)}`)).filter(Boolean);
    const dn = lo.map((val, i) => (val === null ? null : `${x(i).toFixed(1)},${y(val).toFixed(1)}`)).filter(Boolean).reverse();
    band = [...up, ...dn].join(' ');
  }
  const missing = line.map((val, i) => (val === null ? i : -1)).filter((i) => i >= 0);
  return (
    <figure className="cube-strip" data-testid="cube-strip" data-n={n} data-sel={sel}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={`${label} along ${dim.label}`}>
        <defs>
          <pattern id="cube-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="currentColor" strokeWidth="1" opacity="0.5" />
          </pattern>
        </defs>
        {band && <polygon points={band} className="cube-band" data-testid="cube-band" />}
        {missing.map((i) => (
          <rect key={i} x={x(i) - W / Math.max(n, 1) / 2} y={0} width={Math.max(1, W / Math.max(n, 1))} height={H} fill="url(#cube-hatch)" className="cube-hatch" />
        ))}
        <polyline points={pts} className="cube-line" fill="none" />
        <line x1={x(sel)} x2={x(sel)} y1={0} y2={H} className="cube-sel" />
      </svg>
      <figcaption className="muted small">
        Along {dim.label} · solid = selected map · band = range over T (21 maps) · hatch = missing. Axis 0–{ymax.toFixed(0)} {units}.
      </figcaption>
    </figure>
  );
}
