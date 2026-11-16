import { useMemo, useState } from 'react';
import { binRuns, useRidgeFocus } from '../store/ridge';
import { fmtSigned, type TargetView, type View } from '../store/view';

const W = 760;
const H = 260;
const M = { l: 44, r: 14, t: 16, b: 30 };

export function HorizonChart({ v }: { v: View }) {
  const sk = v.series?.skyline;
  const [hover, setHover] = useState<number | null>(null);

  const [yMin, yMax] = useMemo(() => {
    const vals = [v.sun.el, v.earth.el, 0];
    if (sk) for (const e of sk.elevationDeg) if (e !== null && Number.isFinite(e)) vals.push(e);
    const lo = Math.floor(Math.min(...vals) - 0.5);
    const hi = Math.ceil(Math.max(...vals) + 0.5);
    return [lo, Math.max(hi, lo + 2)];
  }, [sk, v.sun.el, v.earth.el]);

  const x = (az: number) => M.l + (az / 360) * (W - M.l - M.r);
  const y = (el: number) => M.t + ((yMax - el) / (yMax - yMin)) * (H - M.t - M.b);

  /** Skyline as polyline segments, broken at null bins; truncated runs are drawn separately (lower bounds). */
  const { fill, line, truncated } = useMemo(() => {
    if (!sk) return { fill: '', line: '', truncated: '' };
    const n = sk.azimuthDeg.length;
    const pts: (string | null)[] = sk.azimuthDeg.map((a, i) => {
      const e = sk.elevationDeg[i];
      return e === null || !Number.isFinite(e) ? null : `${x(a).toFixed(1)},${y(e).toFixed(1)}`;
    });
    const wrap = sk.elevationDeg[0];
    const closing = wrap === null || !Number.isFinite(wrap) ? null : `${x(360).toFixed(1)},${y(wrap).toFixed(1)}`;
    let line = '';
    let pen = false;
    for (const p of [...pts, closing]) {
      if (p === null) pen = false;
      else {
        line += `${pen ? 'L' : 'M'}${p}`;
        pen = true;
      }
    }
    let fill = '';
    let run: string[] = [];
    const flush = () => {
      if (run.length > 1) {
        const first = run[0].split(',')[0];
        const last = run[run.length - 1].split(',')[0];
        fill += `M${first},${y(yMin)}L${run.join('L')}L${last},${y(yMin)}Z`;
      }
      run = [];
    };
    for (const p of [...pts, closing]) (p === null ? flush() : run.push(p));
    flush();
    let truncated = '';
    for (let i = 0; i < n; i++) {
      if (sk.coverage?.[i] === 'truncated' && pts[i]) {
        const nx = i + 1 < n ? pts[i + 1] : closing;
        if (nx) truncated += `M${pts[i]}L${nx}`;
      }
    }
    return { fill, line, truncated };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sk, yMin, yMax]);

  const ticks: number[] = [];
  const step = yMax - yMin > 12 ? 5 : yMax - yMin > 5 ? 2 : 1;
  for (let t = Math.ceil(yMin / step) * step; t <= yMax; t += step) ticks.push(t);

  const marker = (t: TargetView, cls: string, label: string) => (
    <g className={cls}>
      {t.horizonElDeg !== null && <line x1={x(t.az)} x2={x(t.az)} y1={y(t.horizonElDeg)} y2={y(t.el)} className="margin-line" />}
      <circle cx={x(t.az)} cy={y(t.el)} r={6} className="target-dot" />
      <text x={x(t.az) + 9} y={y(t.el) - 8} className="chart-label">
        {label} {t.marginDeg !== null ? fmtSigned(t.marginDeg) : ''}
      </text>
    </g>
  );

  const { focus } = useRidgeFocus(v);
  const n = sk?.azimuthDeg.length ?? 0;
  const hoverIdx = hover !== null && sk ? Math.round((hover / 360) * n) % n : null;
  const hEl = hoverIdx !== null && sk ? sk.elevationDeg[hoverIdx] : null;
  const crit = hoverIdx !== null ? sk?.critical?.[hoverIdx] : undefined;
  const nTrunc = sk?.coverage?.filter((c) => c === 'truncated').length ?? 0;
  const nNull = sk?.elevationDeg.filter((e) => e === null || !Number.isFinite(e as number)).length ?? 0;

  return (
    <section className="panel" aria-labelledby="hz-title">
      <div className="panel-head">
        <h2 id="hz-title">Horizon · skyline vs Sun / Earth</h2>
        <span className="muted">
          azimuth clockwise from local north{v.seriesIsBaseline ? ' · skyline: baseline (selected scenario has metrics only)' : ''}
        </span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="chart"
        role="img"
        aria-label={`Horizon chart. Sun at azimuth ${v.sun.az.toFixed(1)}°, elevation ${v.sun.el.toFixed(2)}°. Earth at azimuth ${v.earth.az.toFixed(1)}°, elevation ${v.earth.el.toFixed(2)}°.${sk ? ` Skyline with ${n} bins from the bundle${nTrunc ? `, ${nTrunc} truncated (lower bounds)` : ''}.` : ' Skyline not provided by this bundle.'}`}
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
          <>
            <path d={fill} className="skyline-fill" />
            <path d={line} className="skyline-line" />
            {truncated && <path d={truncated} className="skyline-truncated" data-testid="skyline-truncated" />}
          </>
        ) : (
          <text x={W / 2} y={H / 2} className="chart-note" textAnchor="middle" data-testid="no-skyline">
            Skyline not provided by this bundle — not computed by the viewer
          </text>
        )}
        {focus && sk && focus.bins.length > 0 && (
          <g className={`ridge-mark from-${focus.source}`} data-testid="ridge-mark" data-ridge={focus.ridge?.id ?? ''}>
            {binRuns(focus.bins).map(([b0, b1]) => (
              <rect key={b0} x={x(sk.azimuthDeg[b0]) - 3} y={M.t} width={Math.max(x(sk.azimuthDeg[b1]) - x(sk.azimuthDeg[b0]), 0) + 6} height={H - M.t - M.b} />
            ))}
            <text x={Math.min(x(sk.azimuthDeg[focus.bins[0]]) + 8, W - 260)} y={H - M.b - 6} className="chart-label">
              {focus.ridge ? `${focus.ridge.label ?? focus.ridge.id} · ridge of record` : 'selected bin'} · az {sk.azimuthDeg[focus.bins[0]].toFixed(1)}
              {focus.bins.length > 1 ? `–${sk.azimuthDeg[focus.bins[focus.bins.length - 1]].toFixed(1)}` : ''}°
            </text>
          </g>
        )}
        {marker(v.sun, 'sun', 'Sun')}
        {marker(v.earth, 'earth', 'Earth')}
        {hoverIdx !== null && sk && (
          <g className="crosshair">
            <line x1={x(sk.azimuthDeg[hoverIdx])} x2={x(sk.azimuthDeg[hoverIdx])} y1={M.t} y2={H - M.b} />
            <text x={Math.min(x(sk.azimuthDeg[hoverIdx]) + 6, W - 300)} y={M.t + 12} className="chart-label">
              az {sk.azimuthDeg[hoverIdx].toFixed(1)}° · skyline {hEl === null || !Number.isFinite(hEl) ? 'no data' : `${hEl.toFixed(2)}°`}
              {sk.coverage?.[hoverIdx] === 'truncated' ? ' (lower bound)' : ''}
            </text>
            {crit && crit.distance_m != null && (
              <text x={Math.min(x(sk.azimuthDeg[hoverIdx]) + 6, W - 300)} y={M.t + 28} className="chart-label">
                set by terrain {(crit.distance_m / 1000).toFixed(2)} km away{crit.height_m != null ? ` at ${crit.height_m.toFixed(0)} m` : ''}
                {crit.dem ? ` · ${crit.dem.replace(/ \(PGDA product (\d+)\).*/, ' (PGDA $1)')}` : ''}
              </text>
            )}
          </g>
        )}
      </svg>
      <p className="legend">
        <span className="key key-sun" /> Sun <span className="key key-earth" /> Earth <span className="key key-sky" /> Terrain skyline (bundle)
        {nTrunc > 0 && <> · dashed = truncated bins ({nTrunc}), lower bounds</>}
        {nNull > 0 && <> · gaps = no terrain data ({nNull} bins), never filled</>}
        {v.series && <> · vertical bars = bundle margin</>}
      </p>
    </section>
  );
}
