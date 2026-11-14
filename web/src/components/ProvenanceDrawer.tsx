import { useEffect, useRef } from 'react';
import type { View } from '../store/view';
import { StatusBadge } from './StatusBadge';

export function ProvenanceDrawer({ v, open, onClose }: { v: View | null; open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  const lb = v?.loaded;
  const b = lb?.bundle;
  const ds = v?.dataset;
  const dems = ds ? [ds.dem, ds.localDem, ds.uncertainty?.totalZRms].filter(Boolean) : [];
  return (
    <dialog ref={ref} className="drawer" onClose={onClose} aria-labelledby="pv-title" data-testid="provenance">
      <div className="drawer-head">
        <h2 id="pv-title">Provenance</h2>
        <button type="button" className="btn" onClick={onClose} autoFocus>
          Close
        </button>
      </div>
      {lb && b && ds && v && (
        <div className="drawer-body">
          <p>
            <StatusBadge status={lb.status} testId="status-badge-provenance" /> {b.validation.reason}
          </p>
          <h3>Bundle file</h3>
          <dl className="kv">
            <dt>File</dt>
            <dd>{lb.name}</dd>
            <dt>Origin</dt>
            <dd>{lb.origin}</dd>
            <dt>SHA-256 (bytes as loaded)</dt>
            <dd className="mono" data-testid="bundle-sha">
              {lb.sha256}
            </dd>
            <dt>Size</dt>
            <dd>{(lb.bytes / 1e6).toFixed(2)} MB</dd>
            <dt>Format</dt>
            <dd>
              {b.format} · schema {b.schemaVersion} · generated {b.generatedUTC}
            </dd>
            <dt>Producer</dt>
            <dd>{b.producer ? `${b.producer.name} ${b.producer.version}` : '—'}</dd>
            <dt>Derived outputs</dt>
            <dd>{ds.derived ? `${ds.derived.producer.name} ${ds.derived.producer.version} · ${ds.derived.scenarios.length} scenarios` : 'none — raw inputs only'}</dd>
            <dt>Frame for drawing rays</dt>
            <dd>{v.basis.source === 'bundle' ? 'declared by bundle' : `derived from site longitude ${ds.site.longitudeEastDeg}° (display only)`}</dd>
          </dl>
          <h3>Sources</h3>
          <ul className="links">
            {Object.entries(b.sources ?? {}).map(([k, u]) => (
              <li key={k}>
                {k}: {/^https?:/.test(u) ? <a href={u} target="_blank" rel="noopener noreferrer">{u}</a> : u}
              </li>
            ))}
          </ul>
          <h3>Terrain layers</h3>
          <table className="constraints">
            <thead>
              <tr>
                <th scope="col">Layer</th>
                <th scope="col">Grid</th>
                <th scope="col">Source</th>
                <th scope="col">Hashes</th>
              </tr>
            </thead>
            <tbody>
              {dems.map((d) =>
                d ? (
                  <tr key={d.layer ?? d.source}>
                    <th scope="row">{d.layer ?? d.kind}</th>
                    <td>
                      {d.n}×{d.n} @ {d.spacing} m · {d.frame}
                    </td>
                    <td className="wrap">{d.source}</td>
                    <td className="mono small">
                      crop {d.cropValuesSha256 ?? '—'}
                      <br />
                      file {d.sourceSha256 ?? '—'}
                    </td>
                  </tr>
                ) : null,
              )}
            </tbody>
          </table>
          <h3>Ephemeris</h3>
          <p>
            {ds.ephemeris.source} · {ds.ephemeris.frame} · {ds.ephemeris.angleType ?? ''} · {ds.ephemeris.samples.length} samples ({ds.ephemeris.sampling})
          </p>
          <ul className="links">
            {ds.ephemeris.records.map((r) => (
              <li key={r.target} className="mono small">
                {r.target}: {r.sha256 ? String(r.sha256) : 'no hash'} {r.rawFile ? `· ${String(r.rawFile)}` : ''}
              </li>
            ))}
          </ul>
          <h3>Validation gates</h3>
          <ul className="gates">
            {[...b.validation.gates, ...ds.validation.gates].map((g, i) => (
              <li key={i} className={g.status === 'PASS' ? 'ok' : g.status === 'NOT_RUN' ? 'warn' : ''}>
                <strong>{g.status}</strong> {g.gate}
                {g.evidence ? ` — ${g.evidence}` : ''}
              </li>
            ))}
          </ul>
          <p className="muted">Visibility here means the target centre is above a finite-DEM skyline. It is not power, not a DSN link, not flight software.</p>
        </div>
      )}
    </dialog>
  );
}
