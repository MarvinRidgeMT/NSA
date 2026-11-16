import { useEffect, useRef, useState } from 'react';
import { cell, cubeBase, loadCube, loadCubeIndex, type CubeIndex, type ScenarioCube } from '../bundle/scenarioCube';

/**
 * Display-only views of precomputed scenario-cube files (docs/SCENARIO_CUBE_CONTRACT.md):
 *  - CubeQuestionRows: one Decision Card row per sub-axis question, from data/cubes/<site>/decision_summary.json
 *  - LaunchCalendar:   start date × arrival slip heatmap of k of 20 (launch_calendar.json.gz)
 *  - SafeLitGrid:      9 × 9 position grid, safe on all 20 maps AND lit on k of 20 (terrain_safety.json)
 * Nothing here computes science: values are copied from the files (stored × declared scale at most).
 */

export interface SummaryRow {
  axis: string;
  question: string;
  answer: string;
  value: string;
  label: string;
  source: string;
}
export interface DecisionSummary {
  schema: 'polaris-decision-summary-v1';
  site_id: string;
  label: string;
  rows: SummaryRow[];
}

function useIndex(siteId: string) {
  const [ix, setIx] = useState<CubeIndex | null | undefined>(undefined);
  useEffect(() => {
    let live = true;
    setIx(undefined);
    loadCubeIndex(siteId)
      .then((i) => live && setIx(i))
      .catch(() => live && setIx(null));
    return () => {
      live = false;
    };
  }, [siteId]);
  return ix;
}

function useCubeFile(siteId: string, ix: CubeIndex | null | undefined, file: string) {
  const [c, setC] = useState<ScenarioCube | null | undefined>(undefined);
  useEffect(() => {
    setC(undefined);
    if (ix === undefined) return;
    if (!ix || !ix.cubes.some((x) => x.file === file)) {
      setC(null);
      return;
    }
    let live = true;
    loadCube(siteId, file)
      .then((x) => live && setC(x))
      .catch(() => live && setC(null));
    return () => {
      live = false;
    };
  }, [siteId, ix, file]);
  return c;
}

export function CubeQuestionRows({ siteId }: { siteId: string }) {
  const [s, setS] = useState<DecisionSummary | null | undefined>(undefined);
  useEffect(() => {
    let live = true;
    setS(undefined);
    fetch(`${cubeBase(siteId)}decision_summary.json`)
      .then(async (r) => {
        if (!r.ok || (r.headers.get('content-type') ?? '').includes('text/html')) return null;
        const j = (await r.json()) as DecisionSummary;
        return j?.schema === 'polaris-decision-summary-v1' ? j : null;
      })
      .then((j) => live && setS(j))
      .catch(() => live && setS(null));
    return () => {
      live = false;
    };
  }, [siteId]);
  if (s === undefined) return null;
  if (s === null)
    return (
      <p className="fine" data-testid="dc-axes-missing">
        Scenario sub-axes: not in bundle for this site.
      </p>
    );
  return (
    <dl className="dc-axes" data-testid="dc-axes" data-label={s.label}>
      {s.rows.map((r) => (
        <div key={r.axis} className="dc-axis" data-testid={`dc-axis-${r.axis}`} data-source={r.source} data-label={r.label}>
          <dt>
            <b>{r.axis}</b> · {r.question}
          </dt>
          <dd>
            <span className="v">{r.value}</span> {r.answer} <small className="st">{r.label}</small>
          </dd>
        </div>
      ))}
    </dl>
  );
}

const kColour = (k: number) => {
  // 0 → alarm red, 20 → selenite; perceptually ordered ramp, hatched elsewhere for missing
  const t = Math.max(0, Math.min(1, k / 20));
  const a = [0x5a, 0x1e, 0x1b];
  const b = [0xe9, 0xe4, 0xd8];
  const c = a.map((x, i) => Math.round(x + (b[i] - x) * t));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
};

export function LaunchCalendar({ siteId }: { siteId: string }) {
  const ix = useIndex(siteId);
  const cube = useCubeFile(siteId, ix, 'launch_calendar.json.gz');
  const [mast, setMast] = useState(0);
  const [r, setR] = useState(0);
  const [pick, setPick] = useState<{ d: number; h: number } | null>(null);
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current;
    if (!cv || !cube) return;
    const ctx = cv.getContext('2d');
    if (!ctx) return;
    const nd = cube.dims[2].values.length;
    const nh = cube.dims[3].values.length;
    const cw = cv.width / nd;
    const ch = cv.height / nh;
    for (let d = 0; d < nd; d++)
      for (let h = 0; h < nh; h++) {
        const k = cell(cube, 'k_pass', { D_mast: mast, R: r, S_day: d, S_slip: h });
        ctx.fillStyle = k === null ? '#222' : kColour(k);
        ctx.fillRect(d * cw, h * ch, Math.ceil(cw), Math.ceil(ch));
      }
  }, [cube, mast, r]);
  if (cube === undefined) return null;
  if (cube === null)
    return (
      <section className="panel" data-testid="launch-calendar">
        <h2>Launch-window calendar</h2>
        <p className="muted small">not in bundle for this site.</p>
      </section>
    );
  const days = cube.dims[2].values as string[];
  const k = pick ? cell(cube, 'k_pass', { D_mast: mast, R: r, S_day: pick.d, S_slip: pick.h }) : null;
  const nom = pick ? cell(cube, 'nominal_pass', { D_mast: mast, R: r, S_day: pick.d, S_slip: pick.h }) : null;
  return (
    <section className="panel launch-calendar" data-testid="launch-calendar" data-source={`scenario cube ${cube.cube_id}`} data-label={cube.label}>
      <div className="panel-head">
        <h2>S · when? Launch-window calendar</h2>
        <span className="pilot-badge">{cube.label}</span>
      </div>
      <div className="cube-ctls">
        <label className="cube-ctl">
          <span>D · mast</span>
          <select value={mast} onChange={(e) => setMast(Number(e.target.value))} data-testid="cal-mast">
            {cube.dims[0].values.map((m, i) => (
              <option key={i} value={i}>
                {m} m
              </option>
            ))}
          </select>
        </label>
        <label className="cube-ctl">
          <span>R · requirement</span>
          <select value={r} onChange={(e) => setR(Number(e.target.value))} data-testid="cal-r">
            {cube.dims[1].values.map((_, i) => (
              <option key={i} value={i}>
                {cube.dims[1].value_labels?.[i]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <canvas
        ref={ref}
        width={730}
        height={96}
        className="cal-canvas"
        data-testid="cal-canvas"
        role="img"
        aria-label="Start date (left to right) by arrival slip hour (top to bottom), shade = clone maps passing"
        onClick={(e) => {
          const b = (e.target as HTMLCanvasElement).getBoundingClientRect();
          const d = Math.floor(((e.clientX - b.left) / b.width) * days.length);
          const h = Math.floor(((e.clientY - b.top) / b.height) * 24);
          setPick({ d: Math.max(0, Math.min(days.length - 1, d)), h: Math.max(0, Math.min(23, h)) });
        }}
      />
      <p className="muted small" data-testid="cal-pick" data-value={k ?? ''}>
        {pick && k !== null
          ? `${days[pick.d]} ${String(pick.h).padStart(2, '0')}:00 UTC start · ${k} of 20 maps pass · nominal ${nom ? 'passes' : 'fails'}`
          : 'Click a cell: start date left to right (from ' + days[0] + '), arrival slip 0–23 h top to bottom. Dark = 0 of 20 maps, light = 20 of 20.'}
      </p>
      <p className="muted small">{cube.limitations?.join(' ')}</p>
    </section>
  );
}

export function SafeLitGrid({ siteId }: { siteId: string }) {
  const ix = useIndex(siteId);
  const cube = useCubeFile(siteId, ix, 'terrain_safety.json');
  const [lim, setLim] = useState(0);
  if (cube === undefined) return null;
  if (cube === null)
    return (
      <section className="panel" data-testid="safe-lit">
        <h2>Safe and lit</h2>
        <p className="muted small">not in bundle for this site.</p>
      </section>
    );
  const d = cube.derived!.safe_and_lit;
  const rDim = d.dims[0] as { values: number[]; value_labels?: string[] };
  const pos = cube.dims[1].values as string[];
  const val = (m: string, j: number) => {
    const mm = d.metrics[m];
    const v = mm.values[lim * pos.length + j];
    return typeof v === 'boolean' ? (v ? 1 : 0) : (v as number);
  };
  // grid: dx outer (columns, grid west→east), dy inner (rows drawn grid-north (+y) at the top; +y is NOT local north here)
  const xs = [...new Set(pos.map((p) => Number(p.split(',')[0])))].sort((a, b) => a - b);
  const ys = [...new Set(pos.map((p) => Number(p.split(',')[1])))].sort((a, b) => b - a);
  const nSafeLit = pos.filter((_, j) => val('k_safe_and_lit', j) === 20).length;
  return (
    <section className="panel safe-lit" data-testid="safe-lit" data-source={`scenario cube ${cube.cube_id}`} data-label={cube.label}>
      <div className="panel-head">
        <h2>Safe and lit · position grid</h2>
        <span className="pilot-badge">{cube.label}</span>
      </div>
      <label className="cube-ctl">
        <span>R · landing slope limit (ENGINEERING ASSUMPTION)</span>
        <select value={lim} onChange={(e) => setLim(Number(e.target.value))} data-testid="safe-lim">
          {rDim.values.map((_, i) => (
            <option key={i} value={i}>
              {rDim.value_labels?.[i]}
            </option>
          ))}
        </select>
      </label>
      <div className="sl-grid" role="grid" aria-label="Position grid, 25 m cells, grid north up (polar-stereographic +y, toward the lunar near side), not local north">
        {ys.map((y) => (
          <div className="sl-row" role="row" key={y}>
            {xs.map((x) => {
              const j = pos.indexOf(`${x},${y}`);
              const safe = val('safe_all_20', j) === 1;
              const k = val('k_lit', j);
              return (
                <div
                  role="gridcell"
                  key={x}
                  className={`sl-cell ${safe ? 'safe' : 'unsafe'}${x === 0 && y === 0 ? ' centre' : ''}`}
                  style={{ background: safe ? kColour(k) : undefined }}
                  data-testid={`sl-${x}_${y}`}
                  data-k={k}
                  data-safe={safe ? 1 : 0}
                  title={`dx ${x} m, dy ${y} m · ${safe ? 'slope below limit on all 20 maps' : 'slope above limit on some map'} · lit on ${k} of 20 maps`}
                >
                  {safe ? k : '×'}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <p className="muted small" data-testid="safe-lit-count" data-value={nSafeLit}>
        {nSafeLit} of {pos.length} cells: landing slope below the limit on all 20 maps AND team visibility met on all 20 maps (2026-11-14 window). Number in a
        cell = clone maps lit (k of 20); × = too steep on some map. k of N maps is not a probability.
      </p>
    </section>
  );
}
