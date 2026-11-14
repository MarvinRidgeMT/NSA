import { usePolaris } from '../store/store';
import { fmtUtc, type View } from '../store/view';

const W = 760;
const ROW = 22;
const GAP = 8;
const LBL = 64;

export function VisibilityStrips({ v }: { v: View }) {
  const { setSampleIndex } = usePolaris.getState();
  const sc = v.scenario;
  const n = v.times.length;
  const cw = (W - LBL) / n;
  const rows: { key: string; label: string; flags: boolean[] | null; cls: string }[] = [
    { key: 'sun', label: 'Sun', flags: sc?.samples.sun.visible ?? null, cls: 'sun' },
    { key: 'earth', label: 'Earth', flags: sc?.samples.earth.visible ?? null, cls: 'earth' },
    { key: 'both', label: 'Both', flags: sc?.samples.both.visible ?? null, cls: 'both' },
  ];
  const H = rows.length * (ROW + GAP) + 18;
  const cx = LBL + (v.br.exact ?? v.br.i0 + v.br.f) * cw + cw / 2;

  return (
    <section className="panel" aria-labelledby="vs-title">
      <div className="panel-head">
        <h2 id="vs-title">Visibility strips</h2>
        <span className="muted">{sc ? 'from bundle samples · click to seek' : 'not in bundle'}</span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="chart strips"
        role="img"
        aria-label={sc ? 'Sun, Earth and simultaneous visibility per bundle sample' : 'Visibility not provided by this bundle'}
        data-testid="strips"
        onClick={(e) => {
          const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
          const px = ((e.clientX - r.left) / r.width) * W;
          if (px >= LBL) setSampleIndex(Math.floor((px - LBL) / cw));
        }}
      >
        {rows.map((row, ri) => {
          const y0 = ri * (ROW + GAP);
          return (
            <g key={row.key} className={row.cls}>
              <text x={0} y={y0 + ROW - 6} className="tick">
                {row.label}
              </text>
              {row.flags ? (
                row.flags.map((f, i) => (
                  <rect key={i} x={LBL + i * cw} y={y0} width={Math.max(cw - 1, 0.5)} height={ROW} className={f ? 'vis-on' : 'vis-off'}>
                    <title>
                      {fmtUtc(v.times[i])} · {row.label} {f ? 'visible' : 'blocked'}
                    </title>
                  </rect>
                ))
              ) : (
                <rect x={LBL} y={y0} width={W - LBL} height={ROW} className="vis-none" />
              )}
            </g>
          );
        })}
        <line x1={cx} x2={cx} y1={-2} y2={H - 16} className="cursor" />
        <text x={LBL} y={H - 2} className="tick">
          {fmtUtc(v.times[0])}
        </text>
        <text x={W} y={H - 2} className="tick" textAnchor="end">
          {fmtUtc(v.times[n - 1])}
        </text>
      </svg>
      <p className="legend">
        <span className="key key-on" /> visible <span className="key key-off" /> blocked — values copied from the bundle
      </p>
    </section>
  );
}
