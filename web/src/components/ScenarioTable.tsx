import { usePolaris } from '../store/store';
import { fmtSigned, fmtUtc, type View } from '../store/view';
import type { Scenario } from '../bundle/types';

/** The fifth dimension: every named scenario the bundle carries, with the bundle's own deltas. Pure display. */
const COLS: { id: string; label: string; unit: string; better: 'up' | 'down' }[] = [
  { id: 'sun_center_visible_pct', label: 'Sun %', unit: '%', better: 'up' },
  { id: 'earth_center_visible_pct', label: 'Earth %', unit: '%', better: 'up' },
  { id: 'sun_and_earth_center_visible_pct', label: 'Both %', unit: '%', better: 'up' },
  { id: 'longest_sun_center_hidden_h', label: 'Max Sun gap (h)', unit: 'h', better: 'down' },
  { id: 'longest_earth_center_hidden_h', label: 'Max Earth gap (h)', unit: 'h', better: 'down' },
];

const FAMILY_ORDER = ['baseline', 'repair', 'position-offset', 'mast-height', 'arrival-shift', 'dem-uncertainty'];
const FAMILY_TITLE: Record<string, string> = {
  baseline: 'Baseline',
  repair: 'Recomputed repair',
  'position-offset': 'Position offsets (±100 m)',
  'mast-height': 'Mast height',
  'arrival-shift': 'Arrival time',
  'dem-uncertainty': 'Terrain uncertainty (NASA error data)',
};

function metric(s: Scenario, id: string) {
  return s.metrics.find((m) => m.id === id);
}

function OffsetGrid({ scs, sel, onPick }: { scs: Scenario[]; sel: string | null; onPick: (id: string) => void }) {
  const cell = (e: number, n: number) => scs.find((s) => Number(s.parameters?.east_m) === e && Number(s.parameters?.north_m) === n);
  const all = scs.map((s) => metric(s, 'sun_center_visible_pct')?.value).filter((x): x is number => x !== undefined);
  if (all.length < 9) return null;
  return (
    <figure className="offset-grid" data-testid="offset-grid" data-classification="SCENARIO">
      <figcaption>
        Sun-centre visibility if the lander moves 100 m (bundle values; each cell fully recomputed). North is up, east is right.
      </figcaption>
      <div className="og">
        {[100, 0, -100].map((n) =>
          [-100, 0, 100].map((e) => {
            const s = cell(e, n);
            const val = s ? metric(s, 'sun_center_visible_pct')?.value : undefined;
            const t = val === undefined ? 0 : val / 100;
            return (
              <button
                key={`${e},${n}`}
                type="button"
                className={`og-cell ${sel === s?.id ? 'sel' : ''} ${e === 0 && n === 0 ? 'centre' : ''}`}
                style={{ background: `color-mix(in oklab, #1a1f27, #f2b84b ${Math.round(t * 100)}%)`, color: t > 0.55 ? '#120d04' : '#e8eef6' }}
                onClick={() => s && onPick(s.id)}
                aria-label={`${e} m east, ${n} m north: Sun ${val?.toFixed(1)} %`}
                data-testid={`og-${e}_${n}`}
              >
                <span className="og-val">{val === undefined ? '—' : `${val.toFixed(0)}%`}</span>
                <span className="og-pos">{e === 0 && n === 0 ? 'site' : `${e > 0 ? '+' : ''}${e}E ${n > 0 ? '+' : ''}${n}N`}</span>
              </button>
            );
          }),
        )}
      </div>
    </figure>
  );
}

export function ScenarioTable({ v }: { v: View }) {
  const scs = v.dataset.derived?.scenarios ?? [];
  const { setScenario } = usePolaris.getState();
  if (scs.length < 2 || !scs.some((s) => s.metrics.some((m) => m.delta !== undefined))) return null;
  const fams = FAMILY_ORDER.filter((f) => scs.some((s) => (s.family ?? s.kind) === f));
  const base = scs.find((s) => (s.family ?? s.kind) === 'baseline');
  const offsets = scs.filter((s) => s.family === 'position-offset');
  return (
    <section className="panel" aria-labelledby="sc-title" data-testid="scenario-table">
      <div className="panel-head">
        <h2 id="sc-title">5D resilience · {scs.length - 1} scenarios</h2>
        <span className="muted">deterministic alternatives, not probabilities · click a row to inspect</span>
      </div>
      <OffsetGrid scs={offsets} sel={v.scenario?.id ?? null} onPick={setScenario} />
      <div className="table-scroll">
        <table className="constraints scen">
          <thead>
            <tr>
              <th scope="col">Scenario</th>
              {COLS.map((c) => (
                <th scope="col" key={c.id}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          {fams.map((f) => (
            <tbody key={f}>
              <tr className="fam">
                <th colSpan={COLS.length + 1} scope="rowgroup">
                  {FAMILY_TITLE[f] ?? f}
                </th>
              </tr>
              {scs
                .filter((s) => (s.family ?? s.kind) === f)
                .map((s) => (
                  <tr
                    key={s.id}
                    className={`${v.scenario?.id === s.id ? 'sel' : ''} ${f === 'repair' ? 'repair' : ''}`}
                    data-testid={`scen-${s.id}`}
                    data-classification={f === 'baseline' ? undefined : 'SCENARIO'}
                  >
                    <th scope="row">
                      <button type="button" className="linkish" onClick={() => setScenario(s.id)} aria-pressed={v.scenario?.id === s.id}>
                        {s.label.replace(/^[^:]+: /, '')}
                      </button>
                    </th>
                    {COLS.map((c) => {
                      const m = metric(s, c.id);
                      const d = m?.delta;
                      const good = d === undefined || d === 0 ? '' : (d > 0) === (c.better === 'up') ? 'ok' : 'bad';
                      return (
                        <td key={c.id} data-value={m?.value ?? ''}>
                          {m ? m.value.toFixed(c.unit === '%' ? 1 : 1) : '—'}
                          {d !== undefined && Math.abs(d) > 1e-9 && <span className={`delta ${good}`}> {fmtSigned(d, 1, '')}</span>}
                        </td>
                      );
                    })}
                  </tr>
                ))}
            </tbody>
          ))}
        </table>
      </div>
      {base && (
        <p className="muted small">
          Deltas are the bundle’s <code>delta_vs_baseline</code>. Green = better for the mission, red = worse. Only the baseline carries a full time series; other rows are
          scenario metrics recomputed by the science pipeline (new skyline, new Horizons queries where needed).
        </p>
      )}
    </section>
  );
}

export function EventsPanel({ v }: { v: View }) {
  const ev = v.dataset.events ?? [];
  const { setTime } = usePolaris.getState();
  if (!ev.length) return null;
  return (
    <section className="panel" aria-labelledby="ev-title" data-testid="events">
      <div className="panel-head">
        <h2 id="ev-title">Rise / set events (baseline)</h2>
        <span className="muted">refined between hourly samples by re-querying Horizons · click to jump to the nearest sample</span>
      </div>
      <ul className="failures">
        {ev.map((e) => (
          <li key={`${e.body}-${e.event}-${e.utc}`}>
            <button type="button" className={`failure ${e.body}`} onClick={() => setTime(Date.parse(e.utc))} data-testid={`event-${e.body}-${e.event}`}>
              <span className="ftag">{e.body === 'sun' ? 'Sun' : 'Earth'}</span> {e.event.replace(/_/g, ' ')} · {fmtUtc(Date.parse(e.utc)).replace(/\.\d+Z$/, 'Z')}
              {e.bracketWidthS !== undefined ? ` · ±${(e.bracketWidthS / 2).toFixed(2)} s` : ''}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
