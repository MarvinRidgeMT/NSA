import { useUi } from '../store/ui';
import { useEffect, useMemo, useRef, useState } from 'react';
import { marginFlagMismatches } from '../bundle/evidence';
import { usePolaris } from '../store/store';
import { fmtSigned, fmtUtc, type View } from '../store/view';

/**
 * Margin Ribbon: per-sample angular margin (target elevation − terrain-horizon elevation) copied from the
 * bundle, one ribbon per target. Positive = centre geometrically visible, negative = obstructed, |margin|
 * below the near-zero band = potentially sensitive to terrain uncertainty, non-finite = horizon unknown.
 * When the bundle carries derived.marginRange (margins across terrain realizations) the min–max band is
 * drawn behind the nominal bar. Clicking or arrow keys seek the shared clock (one store, no second clock).
 */
const W0 = 760;
const LBL = 64;
const ROW0 = 46;
const GAP0 = 14;
const DEFAULT_NEAR_ZERO_DEG = 0.25; // display band only; the bundle may declare its own (derived.nearZeroMarginDeg)

export function MarginRibbon({ v, compact = false }: { v: View; compact?: boolean }) {
  const run = useUi((s) => s.run);
  // compact = the Explore stage's temporal instrument: full-width, shorter rows (same data, same scale rules)
  // compact: the viewBox follows the element's pixel width, so the ribbon keeps a fixed height and unscaled text at any screen width
  const svgRef = useRef<SVGSVGElement>(null);
  const [px, setPx] = useState(1400);
  useEffect(() => {
    if (!compact || !svgRef.current || typeof ResizeObserver === 'undefined') return;
    const el = svgRef.current;
    const ro = new ResizeObserver(() => setPx(Math.max(480, Math.round(el.getBoundingClientRect().width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, [compact]);
  const W = compact ? px : W0;
  const ROW = compact ? 30 : ROW0;
  const GAP = compact ? 8 : GAP0;
  const { setSampleIndex, stepSample } = usePolaris.getState();
  const sc = v.series?.samples ? v.series : null;
  const n = v.times.length;
  const cw = (W - LBL) / n;
  const rawRange = v.dataset.derived?.marginRange ?? null;
  // the realization band belongs to one scenario's series (A4 scenario_id); never draw it under another scenario
  const range = rawRange && (!rawRange.scenarioId || rawRange.scenarioId === v.series?.id) ? rawRange : null;
  const nearZero = v.dataset.derived?.nearZeroMarginDeg ?? DEFAULT_NEAR_ZERO_DEG;
  const H = 2 * (ROW + GAP) + 18;
  const [table, setTable] = useState(false);
  // one concise summary for assistive tech instead of one <title> per sample (the per-sample values are in the on-demand table)
  const summary = sc?.samples
    ? (['sun', 'earth'] as const)
        .map((k) => {
          const vis = sc.samples![k].visible;
          const nb = vis.filter((x) => x === false).length;
          return `${k === 'sun' ? 'Sun' : 'Earth'} blocked in ${nb} of ${vis.length} bundle samples`;
        })
        .join('; ')
    : '';
  const cx = LBL + (v.br.exact ?? v.br.i0 + v.br.f) * cw + cw / 2;

  const rows = useMemo(() => {
    if (!sc?.samples) return [];
    return (['sun', 'earth'] as const).map((key) => {
      const m = sc.samples![key].marginDeg;
      const finite = m.filter((x) => Number.isFinite(x));
      const lo = range ? range[key].minDeg.filter((x): x is number => x !== null && Number.isFinite(x)) : [];
      const hi = range ? range[key].maxDeg.filter((x): x is number => x !== null && Number.isFinite(x)) : [];
      const amp = Math.max(1, ...finite.map(Math.abs), ...lo.map(Math.abs), ...hi.map(Math.abs));
      return { key, m, amp, mismatches: marginFlagMismatches(sc.samples![key]), unknown: m.filter((x) => !Number.isFinite(x)).length };
    });
  }, [sc, range]);

  return (
    <section className="panel" aria-labelledby="mr-title">
      <div className="panel-head">
        <h2 id="mr-title">Margin ribbon · target elevation − horizon</h2>
        <span className="muted">
          {sc
            ? `bundle margins per sample · near-zero band ±${nearZero}°${v.dataset.derived?.nearZeroMarginDeg === undefined ? ' (display)' : ' (bundle)'}${range ? ` · band = range over ${range.realizations.length} realizations` : ' · no realization range in bundle'}${v.seriesIsBaseline ? ' · baseline series' : ''}`
            : 'not in bundle'}
        </span>
      </div>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="chart ribbon"
        role="img"
        tabIndex={0}
        aria-label={sc ? `Sun and Earth angular margin per bundle sample. ${summary}. Arrow keys step samples; the sample table below lists every value.` : 'Margins not provided by this bundle'}
        data-testid="margin-ribbon"
        onClick={(e) => {
          const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
          const px = ((e.clientX - r.left) / r.width) * W;
          if (px >= LBL) setSampleIndex(Math.min(n - 1, Math.floor((px - LBL) / cw)));
        }}
        onKeyDown={(e) => {
          if (e.key === 'ArrowRight') { e.preventDefault(); stepSample(1); }
          if (e.key === 'ArrowLeft') { e.preventDefault(); stepSample(-1); }
        }}
      >
        <defs>
          <pattern id="mr-unknown" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" className="hatch" />
          </pattern>
          <pattern id="mr-nearzero" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
            <line x1="0" y1="0" x2="0" y2="5" className="hatch-nz" />
          </pattern>
        </defs>
        {rows.map((row, ri) => {
          const y0 = ri * (ROW + GAP);
          const mid = y0 + ROW / 2;
          const y = (deg: number) => mid - (Math.max(-row.amp, Math.min(row.amp, deg)) / row.amp) * (ROW / 2 - 2);
          const nz = Math.abs(y(nearZero) - mid);
          return (
            <g key={row.key} className={row.key}>
              <text x={0} y={mid + 4} className="tick">
                {row.key === 'sun' ? 'Sun' : 'Earth'}
              </text>
              <rect x={LBL} y={mid - nz} width={W - LBL} height={2 * nz} className="near-zero-band" />
              {range &&
                range[row.key].minDeg.map((lo, i) => {
                  const hi = range[row.key].maxDeg[i];
                  if (lo === null || hi === null || !Number.isFinite(lo) || !Number.isFinite(hi)) return null;
                  return <rect key={`r${i}`} x={LBL + i * cw} y={y(hi)} width={Math.max(cw, 0.5)} height={Math.max(y(lo) - y(hi), 1)} className="range-band" />;
                })}
              {row.m.map((deg, i) => {
                if (!Number.isFinite(deg))
                  return <rect key={i} x={LBL + i * cw} y={y0} width={Math.max(cw, 0.5)} height={ROW} fill="url(#mr-unknown)" className="unknown" data-margin="unknown" />;
                const cls = Math.abs(deg) < nearZero ? 'near-zero' : deg > 0 ? 'pos' : 'neg';
                const top = Math.min(y(deg), mid);
                return (
                  <rect key={i} x={LBL + i * cw} y={top} width={Math.max(cw - 0.6, 0.5)} height={Math.max(Math.abs(y(deg) - mid), 1.5)} className={cls} data-margin={cls} />
                );
              })}
              {run && run.target === row.key && (
                <rect
                  x={LBL + run.i0 * cw - 1}
                  y={y0 - 1}
                  width={(run.i1 - run.i0 + 1) * cw + 2}
                  height={ROW + 2}
                  className="run-outline"
                  data-testid="ribbon-run"
                  data-i0={run.i0}
                  data-i1={run.i1}
                />
              )}
              <line x1={LBL} x2={W} y1={mid} y2={mid} className="axis-zero" />
              <text x={W} y={y0 + 9} className="tick" textAnchor="end">
                +{row.amp.toFixed(0)}°
              </text>
              <text x={W} y={y0 + ROW} className="tick" textAnchor="end">
                −{row.amp.toFixed(0)}°
              </text>
            </g>
          );
        })}
        {sc && <line x1={cx} x2={cx} y1={-2} y2={H - 16} className="cursor" />}
        {!sc && (
          <text x={W / 2} y={H / 2} className="chart-note" textAnchor="middle">
            Margins not provided by this bundle — not computed by the viewer
          </text>
        )}
        <text x={LBL} y={H - 2} className="tick">
          {fmtUtc(v.times[0])}
        </text>
        <text x={W} y={H - 2} className="tick" textAnchor="end">
          {fmtUtc(v.times[n - 1])}
        </text>
      </svg>
      <p className="legend">
        <span className="key key-pos" /> positive = centre visible <span className="key key-neg" /> negative = obstructed <span className="key key-nz" /> near zero (±{nearZero}°, sensitive to terrain error){' '}
        <span className="key key-unknown" /> horizon unknown
        {rows.map((r) =>
          r.mismatches.length ? (
            <strong key={r.key} className="bad" data-testid={`margin-mismatch-${r.key}`}>
              {' '}
              · {r.key}: {r.mismatches.length} sample(s) where the bundle's margin sign disagrees with its visible flag
            </strong>
          ) : null,
        )}
        {rows.some((r) => r.unknown) && <> · unknown bins: {rows.map((r) => `${r.key} ${r.unknown}`).join(', ')}</>}
      </p>
      {sc?.samples && (
        <details className="sample-table" onToggle={(e) => setTable((e.currentTarget as HTMLDetailsElement).open)} data-testid="ribbon-table">
          <summary>Sample table · {n} rows</summary>
          {table && (
            <div className="table-scroll" style={{ maxHeight: 320, overflowY: 'auto' }}>
              <table className="constraints">
                <caption className="sr-only">Bundle margins per sample (degrees above the skyline; negative = blocked)</caption>
                <thead>
                  <tr>
                    <th scope="col">UTC</th>
                    <th scope="col">Sun margin</th>
                    <th scope="col">Sun</th>
                    <th scope="col">Earth margin</th>
                    <th scope="col">Earth</th>
                  </tr>
                </thead>
                <tbody>
                  {v.times.map((t, i) => {
                    const sm = sc.samples!.sun.marginDeg[i];
                    const em = sc.samples!.earth.marginDeg[i];
                    return (
                      <tr key={t} className={i === v.nearest ? 'is-selected' : ''}>
                        <th scope="row" style={{ fontFamily: 'var(--f-mono)', fontWeight: 400 }}>
                          <button type="button" className="linkish" onClick={() => setSampleIndex(i)}>
                            {fmtUtc(t)}
                          </button>
                        </th>
                        <td>{Number.isFinite(sm) ? fmtSigned(sm) : 'unknown'}</td>
                        <td>{sc.samples!.sun.visible[i] === false ? 'blocked' : sc.samples!.sun.visible[i] ? 'visible' : '—'}</td>
                        <td>{Number.isFinite(em) ? fmtSigned(em) : 'unknown'}</td>
                        <td>{sc.samples!.earth.visible[i] === false ? 'blocked' : sc.samples!.earth.visible[i] ? 'visible' : '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </details>
      )}
    </section>
  );
}
