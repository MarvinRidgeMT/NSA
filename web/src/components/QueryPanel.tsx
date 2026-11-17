import { useEffect, useState } from 'react';
import {
  SOLVER_START,
  SUMMARY_URL,
  computeNow,
  loadSummary,
  memberRanges,
  membersFor,
  membersNotRun,
  nearestSite,
  probeSolver,
  reproduceCommand,
  type AnysiteRow,
  type AnysiteSummary,
  type SolverAnswer,
  type SolverProbe,
  type SummaryMeta,
} from '../globe/anysite';
import { fmtLat, fmtLon } from '../globe/geo';
import { useGlobe } from '../store/globe';

/**
 * "Query any point" (V2 §2.5, T2). Click the globe (or type a point) -> the nearest PRECOMPUTED any-site row with its
 * provenance and the command that reproduces it, or "compute now" through the local solver API. No science in the
 * browser: the lookup is a nearest-row search; the values shown belong to the row's own lat/lon, never interpolated.
 */
const LABEL = 'SOURCE-BASED · UNVALIDATED';
const PICK_SRC = 'globe pick: ray ∩ 1,737.4 km reference sphere (display geometry)';

let summaryPromise: Promise<{ summary: AnysiteSummary; meta: SummaryMeta | null }> | null = null;
const getSummary = () => (summaryPromise ??= loadSummary().catch((e) => {
  summaryPromise = null;
  throw e;
}));

const f = (v: number | undefined, d = 1) => (typeof v === 'number' && Number.isFinite(v) ? v.toFixed(d) : '—');
const range = (m?: { min: number; max: number }) => (m ? (m.min === m.max ? `${f(m.min, 2)}` : `${f(m.min, 2)}–${f(m.max, 2)}`) : '—');

async function copy(text: string, set: (s: string) => void) {
  try {
    await navigator.clipboard.writeText(text);
    set('copied');
  } catch {
    set('select the text and copy it');
  }
}

function RowView({ row, distanceKm, summary, meta }: { row: AnysiteRow & { lat: number; lon: number }; distanceKm: number; summary: AnysiteSummary; meta: SummaryMeta | null }) {
  const [copied, setCopied] = useState('');
  const cmd = reproduceCommand(row.lat, row.lon, { members: membersFor(row.group), name: row.name });
  const ranges = memberRanges(row);
  const notRun = membersNotRun(row);
  const src = `${SUMMARY_URL} (data/anysite/precompute_summary.json${meta ? `, sha256 ${meta.sha256.slice(0, 12)}…` : ''}) row ${row.id}`;
  return (
    <div className="qp-result" data-testid="query-result" data-site-id={row.id} data-source={src} data-label={LABEL}>
      <span className="chip">{LABEL} · precomputed</span>
      <strong data-testid="query-site-name">{row.name}</strong>
      <span className="qp-sub">
        {row.group.replace(/_/g, ' ')} · {fmtLat(row.lat, 3)}, {fmtLon(row.lon, 3)} ·{' '}
        <span data-testid="query-distance">{distanceKm < 0.05 ? 'at the picked point' : `${f(distanceKm, distanceKm < 10 ? 2 : 0)} km from the picked point`}</span>
      </span>
      {distanceKm >= 0.05 && (
        <p className="gl-note" data-testid="query-not-here">
          These values are for that precomputed site, not for the picked point (nothing is interpolated). Use “Compute now” or the command below for the picked point.
        </p>
      )}
      <dl className="qp-metrics">
        <dt>Sun centre visible</dt>
        <dd data-testid="query-sun">{f(row.sun_pct, 2)} % of hourly samples</dd>
        <dt>Earth centre visible</dt>
        <dd>{f(row.earth_pct, 2)} % of hourly samples</dd>
        <dt>Sun and Earth together</dt>
        <dd>{f(row.sun_earth_pct, 2)} % of hourly samples</dd>
        <dt>Longest Sun gap</dt>
        <dd>{f(row.longest_sun_gap_h, 0)} h</dd>
        <dt>Ground height</dt>
        <dd>{f(row.ground_m, 1)} m vs the 1,737.4 km sphere</dd>
        <dt>Slope (5 m / 50 m baseline)</dt>
        <dd>{f(row.slope_deg, 2)}°</dd>
      </dl>
      {ranges.map((r) => (
        <p key={r.key} className="qp-members">
          {r.label} ({r.set.sun_center_visible_pct_hourly_samples?.n ?? 0} members): Sun {range(r.set.sun_center_visible_pct_hourly_samples)} %, Sun+Earth{' '}
          {range(r.set.sun_and_earth_center_visible_pct_hourly_samples)} %, longest gap {range(r.set.longest_sun_center_hidden_h)} h. Spread across terrain alternatives, not a probability.
        </p>
      ))}
      {notRun.map((n) => (
        <p key={n.key} className="gl-note">
          {n.key}: not run ({n.reason}).
        </p>
      ))}
      <details className="qp-prov" data-testid="query-provenance">
        <summary>Provenance</summary>
        <ul>
          <li>Window: {summary.window}</li>
          <li>Terrain: {summary.terrain}; near field {row.near_product} (zone {row.near_zone}, level {row.near_level}) to {f(row.near_cut_m, 0)} m, far field {row.far_product} to {f((row.max_range_m ?? 0) / 1000, 0)} km (curvature limit {f((row.required_range_world_m ?? 0) / 1000, 0)} km)</li>
          <li>Truncated skyline bins: {row.n_truncated_bins ?? '—'}; unknown Sun samples: {row.n_unknown_sun ?? '—'}</li>
          <li>Site hash {row.site_hash}; JPL Horizons responses (SHA-256): {(row.horizons_raw ?? []).map((h) => h.slice(0, 12)).join(', ') || '—'}</li>
          <li>File: {meta ? `${meta.source}, sha256 ${meta.sha256}` : SUMMARY_URL}</li>
        </ul>
      </details>
      <div className="qp-cmd">
        <span className="lab">Reproduce this row</span>
        <code data-testid="query-command">{cmd}</code>
        <button type="button" className="btn" onClick={() => copy(cmd, setCopied)} data-testid="query-copy">
          Copy command
        </button>
        {copied && <span className="gl-note" role="status">{copied}</span>}
      </div>
    </div>
  );
}

function SolverBlock({ lat, lon }: { lat: number; lon: number }) {
  const [probe, setProbe] = useState<SolverProbe | null>(null);
  const [busy, setBusy] = useState(false);
  const [ans, setAns] = useState<SolverAnswer | null>(null);
  const [withMembers, setWithMembers] = useState(false);
  const check = () => {
    setProbe(null);
    probeSolver().then(setProbe);
  };
  useEffect(check, []);
  useEffect(() => setAns(null), [lat, lon]);
  const run = async () => {
    setBusy(true);
    setAns(null);
    setAns(await computeNow(lat, lon, withMembers ? ['clones', 'assumed', 'products'] : []));
    setBusy(false);
  };
  return (
    <div className="qp-solver" data-testid="query-solver" data-state={probe?.state ?? 'checking'} data-source="local solver API (science/anysite/api.py via the solver-api proxy)" data-label={LABEL}>
      <span className="lab">Compute now · local solver</span>
      {!probe && <p className="gl-note">Checking the local solver API…</p>}
      {probe?.state === 'down' && (
        <p className="gl-note" role="status" data-testid="query-solver-down">
          Solver API not running ({probe.why}). Start it in the project venv with <code>{SOLVER_START}</code> and serve the viewer with <code>npm run dev</code> or <code>npm run preview</code> (they proxy <code>solver-api/</code> to 127.0.0.1:8766), then{' '}
          <button type="button" className="linkish" onClick={check} data-testid="query-solver-retry">
            check again
          </button>
          .
        </p>
      )}
      {probe?.state === 'running' && (
        <p className="gl-note" data-testid="query-solver-up">
          Solver API running: {probe.name} ({probe.endpoint}). The point is solved for the same window and mast as the precomputed rows; the solver typically takes seconds to a minute.
        </p>
      )}
      <label className="qp-check">
        <input type="checkbox" checked={withMembers} onChange={(e) => setWithMembers(e.target.checked)} disabled={probe?.state !== 'running' || busy} /> include uncertainty members (slower)
      </label>
      <button type="button" className="btn primary" onClick={run} disabled={probe?.state !== 'running' || busy} data-testid="query-compute">
        {busy ? 'Computing…' : `Compute now for ${fmtLat(lat)}, ${fmtLon(lon)}`}
      </button>
      {ans?.error && (
        <p className="gl-note" role="alert" data-testid="query-solver-error">
          The solver answered with an error: {ans.error}
        </p>
      )}
      {ans && !ans.error && (
        <div className="qp-result" data-testid="query-computed" data-source={`local solver API · bundle ${ans.bundle_path ?? '—'} · site hash ${ans.site_hash ?? '—'}`} data-label={ans.label ?? LABEL}>
          <span className="chip">{ans.label ?? LABEL} · computed now{ans.cache_hit ? ' (solver cache hit)' : ''}</span>
          <dl className="qp-metrics">
            <dt>Sun centre visible</dt>
            <dd>{f(ans.sun_center_visible_pct_hourly_samples, 2)} % of hourly samples</dd>
            <dt>Sun and Earth together</dt>
            <dd>{f(ans.sun_and_earth_center_visible_pct_hourly_samples, 2)} % of hourly samples</dd>
            <dt>Longest Sun gap</dt>
            <dd>{f(ans.longest_sun_center_hidden_h, 0)} h</dd>
            <dt>Ground height</dt>
            <dd>{f(ans.ground_m, 1)} m vs the 1,737.4 km sphere</dd>
          </dl>
          <p className="gl-note">
            Near field {ans.near_product ?? '—'}, far field {ans.far_product ?? '—'}; truncated bins {ans.n_truncated_bins ?? '—'}. Full bundle: <code>{ans.bundle_path ?? '—'}</code>
          </p>
        </div>
      )}
    </div>
  );
}

export default function QueryPanel({ markerLat, markerLon, pickNote }: { markerLat: number; markerLon: number; pickNote?: string }) {
  const { picked, pick } = useGlobe();
  const [data, setData] = useState<{ summary: AnysiteSummary; meta: SummaryMeta | null } | null>(null);
  const [err, setErr] = useState('');
  const [latIn, setLatIn] = useState('');
  const [lonIn, setLonIn] = useState('');
  const [inErr, setInErr] = useState('');
  useEffect(() => {
    if (!picked || data) return;
    getSummary().then(setData, (e) => setErr(e instanceof Error ? e.message : String(e)));
  }, [picked, data]);
  useEffect(() => {
    if (picked) {
      setLatIn(picked.lat.toFixed(4));
      setLonIn(picked.lon.toFixed(4));
    }
  }, [picked]);
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const la = Number(latIn);
    const lo = Number(lonIn);
    if (!Number.isFinite(la) || la < -90 || la > 90 || latIn.trim() === '') return setInErr('Latitude must be between −90 and 90.');
    if (!Number.isFinite(lo) || lo < -180 || lo > 360 || lonIn.trim() === '') return setInErr('Longitude must be between −180 and 360 (east).');
    setInErr('');
    pick({ lat: la, lon: lo > 180 ? lo - 360 : lo, via: 'input' });
  };
  const hit = picked && data ? nearestSite(data.summary.sites, picked.lat, picked.lon) : null;
  const setNearest = useGlobe((s) => s.setNearest);
  const hitId = hit?.row.id;
  useEffect(() => {
    setNearest(hit ? { lat: hit.row.lat, lon: hit.row.lon, name: hit.row.name } : null);
  }, [hitId]); // eslint-disable-line react-hooks/exhaustive-deps
  const nDone = data ? data.summary.sites.filter((s) => s.status === 'done').length : null;
  return (
    <div className="query-panel" data-testid="query-panel">
      <span className="lab">Query any point</span>
      <p className="gl-note">Click the globe, or type a point. The answer is the nearest of the precomputed any-site results, or a new solve through the local solver API.</p>
      <form className="qp-form" onSubmit={submit}>
        <label>
          Lat (°)
          <input inputMode="decimal" value={latIn} onChange={(e) => setLatIn(e.target.value)} data-testid="query-lat" aria-describedby="qp-hint" />
        </label>
        <label>
          Lon (° E)
          <input inputMode="decimal" value={lonIn} onChange={(e) => setLonIn(e.target.value)} data-testid="query-lon" aria-describedby="qp-hint" />
        </label>
        <button type="submit" className="btn" data-testid="query-go">
          Query
        </button>
        <button type="button" className="btn" onClick={() => pick({ lat: markerLat, lon: markerLon, via: 'marker' })} data-testid="query-marker">
          Use site marker
        </button>
      </form>
      <span id="qp-hint" className="gl-note">
        Planetocentric latitude, east longitude.
      </span>
      {inErr && (
        <p className="gl-note" role="alert">
          {inErr}
        </p>
      )}
      {picked && (
        <p className="qp-picked" data-testid="query-picked" data-source={picked.via === 'click' ? PICK_SRC : `typed point (${picked.via})`} data-label={`${LABEL} · display geometry`}>
          Picked {fmtLat(picked.lat, 3)}, {fmtLon(picked.lon, 3)} ({picked.via === 'click' ? 'globe click' : picked.via === 'marker' ? 'site marker' : 'typed'})
          {picked.via === 'click' && pickNote ? `. ${pickNote}` : ''}
        </p>
      )}
      {picked && !data && !err && <p className="gl-note">Loading the precomputed results…</p>}
      {err && (
        <p className="gl-note" role="alert">
          Precomputed results unavailable: {err}
        </p>
      )}
      {picked && data && nDone !== null && (
        <p className="gl-note" data-source={SUMMARY_URL} data-label={LABEL}>
          {nDone} precomputed sites ({data.summary.label}).
        </p>
      )}
      {hit && data && <RowView row={hit.row} distanceKm={hit.distanceKm} summary={data.summary} meta={data.meta} />}
      {picked && <SolverBlock lat={picked.lat} lon={picked.lon} />}
    </div>
  );
}
