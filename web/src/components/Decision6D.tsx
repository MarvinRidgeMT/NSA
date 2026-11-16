import { useEffect, useMemo, useState } from 'react';
import type { View } from '../store/view';
import {
  DECISION6D_FILE,
  blockDim,
  blockMetric,
  loadDecision6D,
  questionValue,
  type Decision6D as D6,
  type Decision6DQuestion,
} from '../bundle/scenarioCubeV2';
import { Decision6DLanding } from './Decision6DLanding';
import { Decision6DPareto } from './Decision6DPareto';

/**
 * 6D decision panels (prompt §4, docs/v2/PHASE_3_DECISION_PLAN.md): robust choice, regret and value of information over
 * "what we don't know" (X) × "what we choose" (L), plus the landing search and the Pareto view.
 * DISPLAY ONLY — every number is a stored cell of data/cubes/<site>/decision6d.json, computed by science/decision/.
 * Counts are "k of N maps", never probabilities, and are never combined across axes or questions.
 */
export const GEOMETRY_LABEL = 'SOURCE-BASED · UNVALIDATED';
export const ENGINEERING_LABEL = 'ENGINEERING ASSUMPTION · inputs SOURCE-BASED · UNVALIDATED';
const MAX_ROWS = 12;

export function labelFor(q: Pick<Decision6DQuestion, 'label'>): string {
  return q.label.includes('ENGINEERING') ? ENGINEERING_LABEL : GEOMETRY_LABEL;
}

export function fmtVal(v: number | boolean | null | undefined, units: string, digits = 2): string {
  if (v === null || v === undefined || typeof v === 'boolean' || !Number.isFinite(v)) return '—';
  const s = v.toFixed(digits);
  if (units === '%') return `${s} %`;
  if (units === 'deg') return `${s}°`;
  if (units === 'h') return `${v.toFixed(0)} h`;
  return units ? `${s} ${units}` : s;
}

/** A difference of two values in `units` (regret, gain): percentages become percentage points. */
export function fmtDelta(v: number | boolean | null | undefined, units: string, digits = 2): string {
  return fmtVal(v, units === '%' ? 'pct points' : units, digits);
}

function useDecision6D(siteId: string) {
  const [d, setD] = useState<D6 | null | undefined>(undefined);
  useEffect(() => {
    let live = true;
    setD(undefined);
    loadDecision6D(siteId)
      .then((x) => live && setD(x))
      .catch(() => live && setD(null));
    return () => {
      live = false;
    };
  }, [siteId]);
  return d;
}

export function Decision6D({ v }: { v: View }) {
  const siteId = v.dataset.site.id;
  const d = useDecision6D(siteId);
  const [qi, setQi] = useState(0);
  useEffect(() => setQi(0), [siteId]);

  if (d === undefined) return null;
  if (d === null)
    return (
      <section className="panel decision6d" data-testid="decision6d" data-source="decision6d cube">
        <div className="panel-head">
          <h2>Decide under uncertainty · 6D</h2>
        </div>
        <p className="muted small" data-testid="decision6d-missing">
          Decision tools (robust choice, regret, value of information) not computed for this site.
        </p>
      </section>
    );

  const q = d.questions[Math.min(qi, d.questions.length - 1)];
  const idx = d.questions.indexOf(q);
  return (
    <>
      <section
        className="panel decision6d"
        data-testid="decision6d"
        data-source={`decision6d ${d.cube.cube_id}`}
        data-result-id={`${d.cube.cube_id}#${q.id}`}
        data-label={labelFor(q)}
      >
        <div className="panel-head">
          <h2>Decide under uncertainty · 6D</h2>
          <span className="pilot-badge" data-testid="d6-label">
            {labelFor(q)}
          </span>
        </div>
        <p className="muted small">
          <b>What we don&apos;t know</b> (terrain maps, data products) is stressed over; <b>what we choose</b> (mast, position,
          layout, array) is compared. Requirements are filters, never optimised. Every &quot;worst&quot; is the worst of the listed maps, not of
          all possible terrain. <b data-testid="d6-not-prob">k of N maps is not a probability.</b>
        </p>
        <label className="cube-ctl d6-pick">
          <span>Question</span>
          <select value={idx} onChange={(e) => setQi(Number(e.target.value))} data-testid="d6-question">
            {d.questions.map((x, i) => (
              <option key={x.id} value={i}>
                {x.text}
              </option>
            ))}
          </select>
        </label>
        <QuestionView d={d} q={q} qi={idx} />
      </section>
      {q.kind === 'landing' && <Decision6DLanding d={d} q={q} />}
      <Decision6DPareto d={d} />
    </>
  );
}

function QuestionView({ d, q, qi }: { d: D6; q: Decision6DQuestion; qi: number }) {
  const c = d.cube;
  const B = (part: string) => `q__${q.id}__${part}`;
  const X = blockDim(c, B('by_member'))!;
  const L = blockDim(c, B('by_choice'))!;
  const xl = X.value_labels ?? X.values.map(String);
  const ll = L.value_labels ?? L.values.map(String);
  const nX = xl.length;
  const rob = questionValue(c, 'robust_choice_index', qi) as number;
  const nom = questionValue(c, 'nominal_choice_index', qi) as number;
  const mmr = questionValue(c, 'minimax_regret_choice_index', qi) as number;
  const tied = questionValue(c, 'n_tied_robust', qi) as number;
  const kChange = questionValue(c, 'k_members_choice_changes', qi) as number;
  const same = questionValue(c, 'robust_equals_nominal', qi) as boolean;
  const s1 = (m: string) => (blockMetric(c, B('summary'), m) ?? [null])[0] as number | null;
  const bc = (m: string) => blockMetric(c, B('by_choice'), m) as (number | null)[] | null;
  const worst = bc('worst_over_x')!;
  const best = bc('best_over_x')!;
  const nomv = bc('nominal_value')!;
  const maxr = bc('max_regret')!;
  const meanr = bc('mean_regret_unweighted')!;
  const kmeet = blockMetric(c, B('by_choice'), 'k_members_meeting') as number[] | null;
  const u = q.units;
  const tr = (block: string, m: string, i?: number) => `${DECISION6D_FILE}#${block}.${m}${i === undefined ? '' : `[${i}]`}`;

  const rows = useMemo(() => {
    const sgn = q.sense === 'max' ? 1 : -1;
    const order = worst.map((_, i) => i).sort((a, b) => sgn * ((worst[b] ?? 0) - (worst[a] ?? 0)) || a - b);
    const keep = new Set(order.slice(0, MAX_ROWS));
    keep.add(rob);
    keep.add(nom);
    return order.filter((i) => keep.has(i));
  }, [q.id, q.sense, worst, rob, nom]);

  const voiAxis = blockDim(c, B('voi'))!;
  const voiK = blockMetric(c, B('voi'), 'k_values_choice_changes') as number[];
  const voiN = blockMetric(c, B('voi'), 'n_values') as number[];
  const voiMax = blockMetric(c, B('voi'), 'max_gain') as number[];
  const voiMean = blockMetric(c, B('voi'), 'mean_gain_unweighted') as number[];
  const fixed = Object.entries(q.fixed);

  return (
    <div data-testid={`d6-q-${q.id}`} data-source={`${q.source_file} (sha256 ${q.source_sha256.slice(0, 12)}…)`}>
      <div className="grid d6-xl">
        <div className="col" data-testid="d6-x">
          <h3 className="d6-h">What we don&apos;t know</h3>
          <p className="small">
            <span className="mono" data-testid="d6-nx">
              {nX}
            </span>{' '}
            {X.label.replace(/^What we don't know: /, '')} ({nX === 21 ? 'nominal PGDA 78 map + 20 error clones' : 'listed members'})
            {' · '}stress over these
          </p>
        </div>
        <div className="col" data-testid="d6-l">
          <h3 className="d6-h">What we choose</h3>
          <p className="small">
            <span className="mono">{ll.length}</span> options of {L.label.replace(/^What we choose: /, '')} · compare these
            {fixed.length > 0 && (
              <>
                <br />
                <span className="muted">Held: {fixed.map(([k, val]) => `${k} = ${val}`).join(', ')}</span>
              </>
            )}
            {Object.keys(q.reduce).length > 0 && (
              <>
                <br />
                <span className="muted">Measure averaged over {Object.keys(q.reduce).join(', ')} (unweighted mean of start dates)</span>
              </>
            )}
          </p>
        </div>
      </div>
      <p className="small muted">
        Measure: {q.measure} ({q.sense === 'max' ? 'higher' : 'lower'} is better).
      </p>
      <dl className="cube-card" data-testid="d6-headline">
        <div data-trace={tr('Q', 'robust_choice_index', qi)}>
          <dt>Robust choice (best worst case)</dt>
          <dd data-testid="d6-robust" data-index={rob}>
            {ll[rob]} · worst {fmtVal(s1('robust_worst'), u)}
            {tied > 1 && <span className="muted"> · tied with {tied - 1} other{tied > 2 ? 's' : ''}</span>}
          </dd>
        </div>
        <div data-trace={tr('Q', 'nominal_choice_index', qi)}>
          <dt>Choice made on the nominal map alone</dt>
          <dd data-testid="d6-nominal" data-index={nom}>
            {ll[nom]} · nominal {fmtVal(s1('nominal_choice_nominal_value'), u)} · worst {fmtVal(s1('nominal_choice_worst'), u)}
          </dd>
        </div>
        <div data-trace={tr(B('summary'), 'max_regret_nominal_choice')}>
          <dt>Regret of choosing on the nominal map</dt>
          <dd data-testid="d6-regret" data-value={s1('max_regret_nominal_choice') ?? ''}>
            max {fmtDelta(s1('max_regret_nominal_choice'), u)} · mean {fmtDelta(s1('mean_regret_nominal_choice'), u)}{' '}
            <span className="muted">(unweighted over the {nX} maps)</span>
          </dd>
        </div>
        <div data-trace={tr('Q', 'minimax_regret_choice_index', qi)}>
          <dt>Minimax-regret choice</dt>
          <dd data-testid="d6-mmr">
            {ll[mmr]} · max regret {fmtDelta(s1('minimax_regret'), u)}
          </dd>
        </div>
        <div data-trace={tr('Q', 'k_members_choice_changes', qi)}>
          <dt>Maps under which another option beats the robust choice</dt>
          <dd data-testid="d6-kchange">
            {kChange} of {nX} maps <span className="muted">(a count, not a probability)</span>
          </dd>
        </div>
        <div>
          <dt>Robust = nominal-map choice?</dt>
          <dd data-testid="d6-same">{same ? 'yes' : 'no'}</dd>
        </div>
      </dl>
      {q.threshold !== null && (
        <p className="small" data-testid="d6-requirement" data-trace={tr(B('by_choice'), 'k_members_meeting')}>
          Requirement (a filter): {q.threshold_text}. Robust choice meets it on {kmeet?.[rob] ?? '—'} of {nX} maps; nominal-map choice on{' '}
          {kmeet?.[nom] ?? '—'} of {nX} maps.
          {q.ordered && (
            <>
              {' '}
              Cheapest option meeting it on every map:{' '}
              <b data-testid="d6-first-all">{s1('first_meeting_all') === null ? 'none' : ll[s1('first_meeting_all')!]}</b>; on the nominal map
              alone: <b>{s1('first_meeting_nominal') === null ? 'none' : ll[s1('first_meeting_nominal')!]}</b>.
            </>
          )}
        </p>
      )}
      <h3 className="d6-h">Value of information · which unknown, if resolved, changes the choice</h3>
      <div className="table-scroll">
        <table className="constraints flip-table" data-testid="d6-voi">
          <thead>
            <tr>
              <th>Resolve</th>
              <th>Values where the choice changes</th>
              <th>Largest worst-case gain</th>
              <th>Unweighted mean gain</th>
            </tr>
          </thead>
          <tbody>
            {voiAxis.values.map((a, i) => (
              <tr key={String(a)} data-testid={`d6-voi-${String(a)}`} data-trace={tr(B('voi'), 'max_gain', i)}>
                <td>{voiAxis.value_labels?.[i] ?? String(a)}</td>
                <td>
                  {voiK[i]} of {voiN[i]}
                </td>
                <td>{fmtDelta(voiMax[i], u)}</td>
                <td>{fmtDelta(voiMean[i], u)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        Non-probabilistic: no expected value of information is computed because the maps carry no weights. A gain is how much the
        worst case improves if that unknown were known before choosing.
      </p>
      <h3 className="d6-h">
        Options {rows.length < ll.length ? `(best ${MAX_ROWS} by worst case, plus the robust and nominal choices; ${ll.length} in all)` : ''}
      </h3>
      <div className="table-scroll">
        <table className="constraints flip-table" data-testid="d6-options">
          <thead>
            <tr>
              <th>Option</th>
              <th>Nominal map</th>
              <th>Worst of {nX}</th>
              <th>Best of {nX}</th>
              <th>Max regret</th>
              <th>Mean regret (unweighted)</th>
              {kmeet && <th>Maps meeting requirement</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((i) => (
              <tr key={i} data-testid={`d6-opt-${i}`} className={i === rob ? 'd6-rob' : undefined} data-trace={tr(B('by_choice'), 'worst_over_x', i)}>
                <td>
                  {ll[i]}
                  {i === rob ? ' · robust' : ''}
                  {i === nom ? ' · nominal pick' : ''}
                </td>
                <td>{fmtVal(nomv[i], u)}</td>
                <td data-testid={`d6-worst-${i}`}>{fmtVal(worst[i], u)}</td>
                <td>{fmtVal(best[i], u)}</td>
                <td>{fmtDelta(maxr[i], u)}</td>
                <td>{fmtDelta(meanr[i], u)}</td>
                {kmeet && (
                  <td>
                    {kmeet[i]} of {nX}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small" data-testid="d6-trace">
        Source: <code>{q.source_file}</code> (sha256 {q.source_sha256.slice(0, 12)}…), metric <code>{q.metric}</code>; computed by{' '}
        <code>science/decision/core.py</code> into <code>{DECISION6D_FILE}</code>.
      </p>
    </div>
  );
}
