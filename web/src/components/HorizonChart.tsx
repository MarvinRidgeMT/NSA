import { useMemo, useState } from 'react';
import { fmtSigned, type TargetView, type View } from '../store/view';

const W = 760;
const H = 260;
const M = { l: 44, r: 14, t: 16, b: 30 };

export function HorizonChart({ v }: { v: View }) {
  const sk = v.scenario?.skyline;
  const [hover, setHover] = useState<number | null>(null);

  const [yMin, yMax] = useMemo(() => {
    const vals = [v.sun.el, v.earth.el, 0];
    if (sk) vals.push(...sk.elevationDeg);
    const lo = Math.floor(Math.min(...vals) - 0.5);
    const hi = Math.ceil(Math.max(...vals) + 0.5);
    return [lo, Math.max(hi, lo + 2)];
  }, [sk, v.sun.el, v.earth.el]);

  const x = (az: number) => M.l + (az / 360) * (W - M.l - M.r);
  const y = (el: number) => M.t + ((yMax - el) / (yMax - yMin)) * (H - M.t - M.b);

  const path = useMemo(() => {
    if (!sk) return '';
    const pts = sk.azimuthDeg.map((a, i) => `${x(a).toFixed(1)},${y(sk.elevationDeg[i]).toFixed(1)}`);
    // close the 360° wrap visually with the first bin
    pts.push(`${x(360).toFixed(1)},${y(sk.elevationDeg[0]).toFixed(1)}`);
    return `M${pts.join('L')}`;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sk, yMin, yMax]);

  const ticks: number[] = [];
  const step = yMax - yMin > 12 ? 5 : yMax - yMin > 5 ? 2 : 1;
  for (let t = Math.ceil(yMin / step) * step; t <= yMax; t += step) ticks.push(t);

  const marker = (t: TargetView, cls: string, label: string) => (
    <g className={cls}>
      {t.horizonElDeg !== null && (
        <line x1={x(t.az)} x2={x(t.az)} y1={y(t.horizonElDeg)} y2={y(t.el)} className="margin-line" />
      )}
      <circle cx={x(t.az)} cy={y(t.el)} r={6} className="target-dot" />
      <text x={x(t.az) + 9} y={y(t.el) - 8} className="chart-label">
        {label} {t.marginDeg !== null ? fmtSigned(t.marginDeg) : ''}
      </text>
    </g>
  );

  const hoverIdx = hover !== null && sk ? Math.round((hover / 360) * sk.azimuthDeg.length) % sk.azimuthDeg.length : null;

  return (
    <section className="panel" aria-labelledby="hz-title">
      <div className="panel-head">
        <h2 id="hz-title">Horizon · skyline vs Sun / Earth</h2>
        <span className="muted">azimuth clockwise from local north</span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="chart"
        role="img"
        aria-label={`Horizon chart. Sun at azimuth ${v.sun.az.toFixed(1)}°, elevation ${v.sun.el.toFixed(2)}°. Earth at azimuth ${v.earth.az.toFixed(1)}°, elevation ${v.earth.el.toFixed(2)}°.${sk ? '' : ' Skyline not provided by this bundle.'}`}
        data-testid="horizon-chart"
        onMouseMove={(e) => {
          const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
          const px = ((e.clientX - r.left) / r.width) * W;
          const az = ((px - M.l) / (W - M.l - M.r)) * 360;
          setHover(az >= 0 && az <= 360 ? az : null);
        }}
        onMouseLeave={() => setHover(null)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} className={t === 0 ? 'axis-zero' : 'grid'} />
            <text x={M.l - 6} y={y(t) + 4} className="tick" textAnchor="end">
              {t}°
            </text>
          </g>
        ))}
        {[0, 90, 180, 270, 360].map((a, i) => (
          <text key={a} x={x(a)} y={H - 10} className="tick" textAnchor="middle">
            {['N', 'E', 'S', 'W', 'N'][i]} {a}°
          </text>
        ))}
        {sk ? (
          <path d={`${path}L${x(360)},${y(yMin)}L${x(0)},${y(yMin)}Z`} className="skyline" />
        ) : (
          <text x={W / 2} y={H / 2} className="chart-note" textAnchor="middle" data-testid="no-skyline">
            Skyline not provided by this bundle — not computed by the viewer
          </text>
        )}
        {marker(v.sun, 'sun', 'Sun')}
        {marker(v.earth, 'earth', 'Earth')}
        {hoverIdx !== null && sk && (
          <g className="crosshair">
            <line x1={x(sk.azimuthDeg[hoverIdx])} x2={x(sk.azimuthDeg[hoverIdx])} y1={M.t} y2={H - M.b} />
            <text x={Math.min(x(sk.azimuthDeg[hoverIdx]) + 6, W - 150)} y={M.t + 12} className="chart-label">
              az {sk.azimuthDeg[hoverIdx].toFixed(1)}° · skyline {sk.elevationDeg[hoverIdx].toFixed(2)}°
              {sk.coverage?.[hoverIdx] === 'truncated' ? ' (truncated)' : ''}
            </text>
          </g>
        )}
      </svg>
      <p className="legend">
        <span className="key key-sun" /> Sun <span className="key key-earth" /> Earth <span className="key key-sky" /> Terrain skyline (bundle)
        {v.scenario && <> · vertical bars = bundle margin</>}
      </p>
    </section>
  );
}
