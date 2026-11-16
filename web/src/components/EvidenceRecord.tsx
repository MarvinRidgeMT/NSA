import { Fragment } from 'react';
import { usePolaris } from '../store/store';
import { fmtUtc, type View } from '../store/view';
import { useCoverageSidecar } from '../bundle/coverageSidecar';

/**
 * Evidence · dataset record (Final Apex P9). One place that names, for the loaded dataset: identity, every input file with its
 * checksum, solver and schema, conventions, sampling, realizations, validation gates, assumptions and how to reproduce.
 * Every line is copied from the bundle or the sidecars; a missing field shows "not in bundle" rather than a guess.
 */
const NA = 'not in bundle';

function Hash({ h }: { h?: string | null }) {
  if (!h) return <span className="ev-na">{NA}</span>;
  return (
    <code className="ev-hash" title={h}>
      {h}
    </code>
  );
}

export function EvidenceRecord({ v }: { v: View }) {
  const side = usePolaris((s) => s.certaintySidecar);
  const cov = useCoverageSidecar();
  const lb = v.loaded;
  const b = lb.bundle;
  const ds = v.dataset;
  const e = ds.ephemeris;
  const n = v.times.length;
  const site = side?.sites?.[ds.siteId];
  const nClones = (site?.certainty_curve as { n_clones?: number }[] | undefined)?.[0]?.n_clones;
  const gates = ds.validation?.gates ?? [];
  const notRun = gates.filter((g) => g.status !== 'PASS');
  const scen = ds.derived?.scenarios ?? [];
  const listed = usePolaris((s) => s.index.some((x) => x.file === lb.name));
  const hours = n > 1 ? (v.times[n - 1] - v.times[0]) / 3.6e6 : 0;
  return (
    <section className="panel ev-record" aria-labelledby="evr-title" data-testid="evidence-record">
      <div className="panel-head">
        <h2 id="evr-title">Dataset record</h2>
        <span className="src-tag bundle">bundle + sidecars</span>
      </div>
      <dl className="kv">
        <dt>Dataset</dt>
        <dd>
          {ds.site.name} · <code>{ds.siteId}</code>
        </dd>
        <dt>Point</dt>
        <dd>
          {Math.abs(ds.site.latitudePlanetocentricDeg).toFixed(5)}° {ds.site.latitudePlanetocentricDeg < 0 ? 'S' : 'N'} ·{' '}
          {Math.abs(ds.site.longitudeEastDeg).toFixed(5)}° {ds.site.longitudeEastDeg < 0 ? 'W' : 'E'}
          {ds.site.coordinateRole ? ` · ${ds.site.coordinateRole}` : ''}
        </dd>
        <dt>Status</dt>
        <dd data-testid="evr-status">
          {v.status}
          {notRun.length > 0 ? ` · ${notRun.length} gate${notRun.length > 1 ? 's' : ''} not passed: ${notRun.map((g) => `${g.gate} (${g.status})`).join(', ')}` : ''}
        </dd>
        <dt>Sampling</dt>
        <dd data-testid="evr-sampling">
          {n} samples, {e.sampling ?? NA}, {fmtUtc(v.times[0])} → {fmtUtc(v.times[n - 1])} ({hours.toFixed(0)} h, {n - 1} intervals). Sample tallies count
          the {n} samples; window percentages and durations are over the {hours.toFixed(0)} h window, so the two can differ slightly.
        </dd>
        <dt>Realizations</dt>
        <dd>
          {nClones !== undefined
            ? `${nClones} evaluated alternate PGDA 78 terrain realizations + the nominal DEM (batch sweep, sampled masts ${site!.sampled_masts_m.join(', ')} m). Agreement among them is not a probability.`
            : 'no batch sweep for this dataset'}
        </dd>
      </dl>

      <details className="dec-more" data-testid="evr-files">
        <summary>Files and checksums</summary>
        <dl className="kv small">
          <dt>Bundle</dt>
          <dd>
            {lb.name} · {(lb.bytes / 1e6).toFixed(1)} MB · <Hash h={lb.sha256} />
          </dd>
          {ds.dem && (
            <>
              <dt>Terrain (display crop)</dt>
              <dd>
                {ds.dem.source} · source <Hash h={ds.dem.sourceSha256} /> · crop values <Hash h={ds.dem.cropValuesSha256} />
              </dd>
            </>
          )}
          {(ds.sourceLayers ?? []).map((l) => (
            <Fragment key={l.name}>
              <dt>{l.role ?? 'Solver layer'}</dt>
              <dd>
                {l.name}
                {l.stepM ? ` · ${l.stepM} m` : ''} · <Hash h={l.sha256 ?? l.arraySha256} />
              </dd>
            </Fragment>
          ))}
          {e.records.map((r) => (
            <Fragment key={`${r.target}${r.rawFile ?? ''}`}>
              <dt>Ephemeris · {r.target}</dt>
              <dd>
                {String(r.rawFile ?? e.source)} · <Hash h={r.sha256} />
              </dd>
            </Fragment>
          ))}
          {side?.source.files.map((f) => (
            <Fragment key={f.path}>
              <dt>Batch sweep CSV</dt>
              <dd>
                {f.path} · <Hash h={f.sha256} />
              </dd>
            </Fragment>
          ))}
          {cov && (
            <>
              <dt>Coverage gauge</dt>
              <dd>
                {cov.source.path} · <Hash h={cov.source.sha256} />
              </dd>
            </>
          )}
        </dl>
      </details>

      <details className="dec-more" data-testid="evr-method">
        <summary>Solver, schema and conventions</summary>
        <dl className="kv small">
          <dt>Format</dt>
          <dd>
            {b.format} {b.schemaVersion} · generated {b.generatedUTC}
          </dd>
          <dt>Bundle solver</dt>
          <dd>{ds.derived ? `${ds.derived.producer.name} · ${ds.derived.producer.version}` : NA}</dd>
          {side && (
            <>
              <dt>Batch solver</dt>
              <dd>
                {side.source.what}
                {side.source.repo_commit ? ` · ${side.source.repo_commit}` : ''}
                {side.source.solver_note ? ` · ${side.source.solver_note}` : ''}
              </dd>
            </>
          )}
          <dt>Ephemeris</dt>
          <dd>
            {e.source} · {e.frame} · {e.angleType ?? NA} · {e.timeScale}
          </dd>
          <dt>Angles</dt>
          <dd>
            azimuth {e.azimuthConvention}; longitude {e.longitudeConvention}
          </dd>
          {ds.dem && (
            <>
              <dt>Terrain frame</dt>
              <dd>
                {ds.dem.frame}
                {ds.dem.crsConvention ? ` · ${ds.dem.crsConvention}` : ''}
              </dd>
            </>
          )}
          <dt>Observers</dt>
          <dd>{scen.length ? scen.map((s) => `${s.label}${s.observer?.mastM !== undefined ? ` (mast ${s.observer.mastM} m)` : ''}`).join(' · ') : NA}</dd>
        </dl>
      </details>

      <details className="dec-more" data-testid="evr-gates">
        <summary>
          Validation gates · {gates.filter((g) => g.status === 'PASS').length} of {gates.length} pass
        </summary>
        <table className="constraints small">
          <thead>
            <tr>
              <th scope="col">Gate</th>
              <th scope="col">Status</th>
              <th scope="col">Evidence</th>
            </tr>
          </thead>
          <tbody>
            {gates.map((g) => (
              <tr key={g.gate} className={g.status === 'PASS' ? '' : 'gate-open'}>
                <td>{g.gate}</td>
                <td>{g.status}</td>
                <td>{g.evidence ?? NA}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>

      <details className="dec-more" data-testid="evr-assume">
        <summary>Assumptions, limits and how to reproduce</summary>
        <ul className="links small">
          <li>Visibility is of the target's centre ({e.angleType ?? 'apparent centre'}), not its disc; Earth visibility is not a communications link; Sun visibility is not power.</li>
          <li>Visible/blocked states, margins and metrics are read from the bundle; the viewer computes none of them. 3D shading and shadows are a display model.</li>
          {(ds.dem as { note?: string } | undefined)?.note ? <li>Terrain: {(ds.dem as { note?: string }).note}</li> : null}
          {(ds.limitations ?? []).map((l) => (
            <li key={l}>{l}</li>
          ))}
          <li>
            Reproduce the bundle with {ds.derived?.producer.name ?? 'its producer'} at {ds.derived?.producer.version ?? NA}
            {side ? `; the Certainty Height and realization ranges with ${side.source.what}${side.source.repo_commit ? ` at ${side.source.repo_commit}` : ''}` : ''}. Check
            each input against the checksums above.
          </li>
        </ul>
        <p className="ev-raw">
          Raw data:{' '}
          {listed ? (
            <a href={`bundles/${lb.name}`} download data-testid="evr-raw-bundle">
              bundle JSON
            </a>
          ) : (
            <span>bundle opened from a local file</span>
          )}
          {side && (
            <>
              {' · '}
              <a href="certainty/sidecar.json" download>
                Certainty Height sidecar
              </a>
            </>
          )}
          {cov && (
            <>
              {' · '}
              <a href="certainty/coverage.json" download>
                coverage sidecar
              </a>
            </>
          )}
          {' · '}
          <a href="showcase/index.html" target="_blank" rel="noopener" data-testid="evr-showcase" title="Blender Cycles renders of the same sites; boulders and micro-relief are synthetic">
            Blender renders (presentation)
          </a>
        </p>
      </details>
    </section>
  );
}

/**
 * Evidence · the pipeline in five lines (V3 page 19): where each stage's inputs come from, then what is not validated yet.
 * Copied from the bundle and the sidecars; nothing here is a result.
 */
export function EvidencePipeline({ v }: { v: View }) {
  const side = usePolaris((s) => s.certaintySidecar);
  const ds = v.dataset;
  const e = ds.ephemeris;
  const layers = ds.sourceLayers ?? [];
  const gates = ds.validation?.gates ?? [];
  const open = gates.filter((g) => g.status !== 'PASS');
  const rows: [string, string][] = [
    [
      'Terrain',
      ds.dem
        ? `${ds.dem.source.split('/').pop()} (${ds.dem.spacing} m)${layers.length ? ` · solver layers: ${layers.map((l) => l.name + (l.stepM ? ` ${l.stepM} m` : '')).join(', ')}` : ''}`
        : layers.map((l) => l.name).join(', ') || NA,
    ],
    ['Ephemeris', `${e.source} · ${e.sampling ?? NA} · ${e.records.length} raw response${e.records.length === 1 ? '' : 's'} with SHA-256 · ${e.frame}`],
    ['Horizon and visibility', ds.derived ? `${ds.derived.producer.name} · ${ds.derived.producer.version}` : NA],
    ['Realizations', side ? `${side.source.what}${side.source.repo_commit ? ` · ${side.source.repo_commit}` : ''}` : 'no batch sweep for this dataset'],
    ['Status', `${v.status}${open.length ? ` · ${open.length} gate${open.length > 1 ? 's' : ''} open` : ''}`],
  ];
  return (
    <section className="panel ev-pipe" aria-labelledby="evp-title" data-testid="evidence-pipeline">
      <div className="panel-head">
        <h2 id="evp-title">How each number was made</h2>
      </div>
      <ol className="pipe">
        {rows.map(([k, val], i) => (
          <li key={k}>
            <span className="n">{String(i + 1).padStart(2, '0')}</span>
            <span className="k">{k}</span>
            <span className="val">{val}</span>
          </li>
        ))}
      </ol>
      <div className="not-yet" data-testid="not-validated">
        <div className="lab">Not validated yet</div>
        <ul>
          {open.map((g) => (
            <li key={g.gate}>
              {g.gate}: {g.status}
              {g.evidence ? ` · ${g.evidence}` : ''}
            </li>
          ))}
          <li>Solver of record not chosen: the bundle solver and the batch sweep differ slightly; neither is independently validated.</li>
          <li>Visibility is geometric (target centre); no power, thermal or communications model.</li>
        </ul>
      </div>
    </section>
  );
}
