import { usePolaris } from '../store/store';
import { fmtSigned, fmtUtc, type View } from '../store/view';
import type { Failure } from '../bundle/types';

const W = 760;
const H = 220;
const M = { l: 56, r: 14, t: 14, b: 30 };

export function CrossSection({ f }: { f: Failure }) {
  const p = f.profile;
  const xs = p.distanceM;
  const all = [...p.terrainM, ...p.rayM];
  const lo = Math.min(...all);
  const hi = Math.max(...all);
  const pad = (hi - lo) * 0.08 + 1;
  const dMax = xs[xs.length - 1] || 1;
  const x = (d: number) => M.l + (d / dMax) * (W - M.l - M.r);
  const y = (z: number) => M.t + ((hi + pad - z) / (hi - lo + 2 * pad)) * (H - M.t - M.b);
  const terrain = `M${x(xs[0])},${y(lo - pad)}` + xs.map((d, i) => `L${x(d).toFixed(1)},${y(p.terrainM[i]).toFixed(1)}`).join('') + `L${x(dMax)},${y(lo - pad)}Z`;
  const rayPath = 'M' + xs.map((d, i) => `${x(d).toFixed(1)},${y(p.rayM[i]).toFixed(1)}`).join('L');
  const hit = f.firstHit;
  return (
    <figure className="xsec" data-testid="cross-section">
      <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label={`Cross-section along azimuth ${f.azimuthDeg.toFixed(1)}°: ${f.target} ray blocked${hit ? ` by terrain ${(hit.distanceM / 1000).toFixed(2)} km away at ${hit.heightM.toFixed(1)} m` : ''}.`}>
        <path d={terrain} className="terrain" />
        <path d={rayPath} className={`ray ${f.target}`} />
        {hit && (
          <g className="hit">
            <circle cx={x(hit.distanceM)} cy={y(p.terrainM[Math.max(0, xs.findIndex((d) => d >= hit.distanceM))])} r={6} />
            <text x={x(hit.distanceM) + 8} y={M.t + 12} className="chart-label">
              first hit {(hit.distanceM / 1000).toFixed(2)} km · cell [{hit.cell.join(', ')}]
            </text>
          </g>
        )}
        <text x={M.l} y={H - 8} className="tick">
          observer
        </text>
        <text x={W - M.r} y={H - 8} className="tick" textAnchor="end">
          {(dMax / 1000).toFixed(2)} km
        </text>
        <text x={M.l - 6} y={y(hi) + 4} className="tick" textAnchor="end">
          {hi.toFixed(0)} m
        </text>
        <text x={M.l - 6} y={y(lo) + 4} className="tick" textAnchor="end">
          {lo.toFixed(0)} m
        </text>
      </svg>
      <figcaption>
        Profile, ray and critical cell are copied from the bundle (curvature drop applied by the science branch). No vertical exaggeration beyond the chart's own y-scale.
      </figcaption>
    </figure>
  );
}

export function FailuresPanel({ v }: { v: View }) {
  const { selectFailure } = usePolaris.getState();
  const sc = v.scenario;
  if (!sc) return null;
  return (
    <section className="panel" aria-labelledby="fl-title">
      <div className="panel-head">
        <h2 id="fl-title">Failures · click one for its cross-section</h2>
        <span className="muted">{sc.failures.length} blocked intervals in this scenario</span>
      </div>
      <ul className="failures" data-testid="failures">
        {sc.failures.map((f) => (
          <li key={f.id}>
            <button
              type="button"
              className={`failure ${f.target} ${v.failure?.id === f.id ? 'selected' : ''}`}
              aria-pressed={v.failure?.id === f.id}
              data-testid={`failure-${f.id}`}
              onClick={() => selectFailure(v.failure?.id === f.id ? null : f.id)}
            >
              <span className="ftag">{f.target === 'sun' ? 'Sun' : 'Earth'}</span> {fmtUtc(Date.parse(f.time))} · az {f.azimuthDeg.toFixed(1)}° · margin{' '}
              {fmtSigned(f.marginDeg, 3)}
              {f.blockedSamples ? ` · ${f.blockedSamples} samples` : ''}
            </button>
          </li>
        ))}
      </ul>
      {v.failure && <CrossSection f={v.failure} />}
    </section>
  );
}
