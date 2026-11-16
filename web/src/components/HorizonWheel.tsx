import { useMemo } from 'react';
import { usePolaris } from '../store/store';
import { fmtSigned, fmtUtc, type View } from '../store/view';

/**
 * Horizon Wheel (Final Apex P9, V3 page 17 "Sky and horizon"): the sky seen from the mast, north up, azimuth clockwise.
 * Radius encodes elevation (higher = nearer the centre) on a stated linear scale; the skyline, the Sun and Earth tracks over the
 * whole window and the current sample are drawn from the bundle (skyline, ephemeris, per-sample visibility). Nothing is computed
 * beyond the plot transform. Click a track point to seek that sample.
 */
const S = 520;
const C = S / 2;
const R_OUT = 230;
const R_IN = 70;

export function HorizonWheel({ v }: { v: View }) {
  const sk = v.series?.skyline;
  const samples = v.dataset.ephemeris.samples;
  const setSampleIndex = usePolaris((s) => s.setSampleIndex);
  const selectedBin = usePolaris((s) => s.selectedBin);

  const scale = useMemo(() => {
    const vals: number[] = [];
    if (sk) for (const e of sk.elevationDeg) if (e !== null && Number.isFinite(e)) vals.push(e);
    for (const s of samples) vals.push(s.sun.el, s.earth.el);
    const lo = Math.floor(Math.min(...vals) - 0.5);
    const hi = Math.ceil(Math.max(...vals) + 0.5);
    return { lo, hi: Math.max(hi, lo + 2) };
  }, [sk, samples]);
  const r = (el: number) => R_OUT - ((el - scale.lo) / (scale.hi - scale.lo)) * (R_OUT - R_IN);
  const xy = (az: number, el: number) => {
    const a = (az * Math.PI) / 180;
    const rr = r(el);
    return [C + rr * Math.sin(a), C - rr * Math.cos(a)] as const;
  };
  const pt = (az: number, el: number) => xy(az, el).map((n) => n.toFixed(1)).join(',');

  const sky = useMemo(() => {
    if (!sk) return { line: '', ground: '' };
    let line = '';
    let pen = false;
    const ok: [number, number][] = [];
    sk.azimuthDeg.forEach((a, i) => {
      const e = sk.elevationDeg[i];
      if (e === null || !Number.isFinite(e)) {
        pen = false;
        return;
      }
      line += `${pen ? 'L' : 'M'}${pt(a, e)}`;
      pen = true;
      ok.push([a, e]);
    });
    if (pen && ok.length && sk.elevationDeg[0] !== null) line += `L${pt(sk.azimuthDeg[0], sk.elevationDeg[0] as number)}`;
    // ground: between the skyline and the outer ring (even-odd ring), only when the skyline is complete
    const complete = ok.length === sk.azimuthDeg.length;
    const ground = complete
      ? `M${C + R_OUT},${C}A${R_OUT},${R_OUT} 0 1,0 ${C - R_OUT},${C}A${R_OUT},${R_OUT} 0 1,0 ${C + R_OUT},${C}Z${line}Z`
      : '';
    return { line, ground };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sk, scale]);

  const track = (key: 'sun' | 'earth') => {
    let d = '';
    let prev: number | null = null;
    samples.forEach((s) => {
      const az = s[key].az;
      // break the path where it wraps through north, so it never draws a chord across the wheel
      d += `${prev === null || Math.abs(az - prev) > 180 ? 'M' : 'L'}${pt(az, s[key].el)}`;
      prev = az;
    });
    return d;
  };
  const vis = v.series?.samples;
  const blockedDots = (key: 'sun' | 'earth') =>
    samples.map((s, i) => (vis?.[key]?.visible?.[i] === false ? <circle key={i} cx={xy(s[key].az, s[key].el)[0]} cy={xy(s[key].az, s[key].el)[1]} r={2.2} className={`hw-blocked ${key}`} /> : null));

  const rings: number[] = [];
  for (let e = Math.ceil(scale.lo); e <= scale.hi; e += scale.hi - scale.lo > 8 ? 2 : 1) rings.push(e);
  const bin = selectedBin !== null && sk ? sk.azimuthDeg[selectedBin] : null;
  const cur = (key: 'sun' | 'earth') => xy(v[key].az, v[key].el);
  const hasData = !!sk;

  return (
    <section className="panel hwheel" aria-labelledby="hw-title" data-testid="horizon-wheel">
      <div className="panel-head">
        <h2 id="hw-title">Horizon wheel · from the mast</h2>
        <span className="muted">
          north up, azimuth clockwise · radius = elevation {scale.lo}° (rim) to {scale.hi}° (inner ring), linear
        </span>
      </div>
      {!hasData ? (
        <p className="note">This scenario carries no skyline.</p>
      ) : (
        <svg viewBox={`0 0 ${S} ${S}`} className="chart hw" role="img" aria-label={`Horizon wheel at ${fmtUtc(v.times[v.nearest])}: Sun ${fmtSigned(v.sun.marginDeg)} against the skyline, Earth ${fmtSigned(v.earth.marginDeg)}.`}>
          {rings.map((e) => (
            <g key={e}>
              <circle cx={C} cy={C} r={r(e)} className={e === 0 ? 'hw-ring zero' : 'hw-ring'} />
              <text x={C + 4} y={C - r(e) - 3} className="tick">
                {e > 0 ? `+${e}` : e}°
              </text>
            </g>
          ))}
          {[0, 90, 180, 270].map((a) => {
            const [x, y] = [C + (R_OUT + 14) * Math.sin((a * Math.PI) / 180), C - (R_OUT + 14) * Math.cos((a * Math.PI) / 180)];
            return (
              <text key={a} x={x} y={y + 4} textAnchor="middle" className="tick hw-card">
                {['N', 'E', 'S', 'W'][a / 90]}
              </text>
            );
          })}
          {sky.ground && <path d={sky.ground} className="hw-ground" fillRule="evenodd" />}
          <path d={sky.line} className="hw-sky" />
          {bin !== null && (
            <line x1={C} y1={C} x2={C + R_OUT * Math.sin((bin * Math.PI) / 180)} y2={C - R_OUT * Math.cos((bin * Math.PI) / 180)} className="hw-bin" />
          )}
          <path d={track('earth')} className="hw-track earth" />
          <path d={track('sun')} className="hw-track sun" />
          {blockedDots('sun')}
          {blockedDots('earth')}
          <circle cx={cur('earth')[0]} cy={cur('earth')[1]} r={6} className={`hw-now earth ${v.earth.visible === false ? 'blocked' : ''}`} data-testid="hw-earth" />
          <circle cx={cur('sun')[0]} cy={cur('sun')[1]} r={7} className={`hw-now sun ${v.sun.visible === false ? 'blocked' : ''}`} data-testid="hw-sun" />
          <text x={cur('sun')[0] + 10} y={cur('sun')[1] - 8} className="hw-label sun">
            Sun {fmtSigned(v.sun.marginDeg)}
          </text>
          <text x={cur('earth')[0] + 10} y={cur('earth')[1] + 16} className="hw-label earth">
            Earth {fmtSigned(v.earth.marginDeg)}
          </text>
          {/* invisible seek targets along the Sun track */}
          {samples.map((s, i) =>
            i % 3 === 0 ? (
              <circle key={i} cx={xy(s.sun.az, s.sun.el)[0]} cy={xy(s.sun.az, s.sun.el)[1]} r={6} className="hw-hit" onClick={() => setSampleIndex(i)}>
                <title>{fmtUtc(v.times[i])}</title>
              </circle>
            ) : null,
          )}
        </svg>
      )}
      <p className="legend">
        <span className="key key-sun" /> Sun track (whole window) <span className="key key-earth" /> Earth track <span className="key key-sky" /> Terrain skyline
        (bundle) · shaded = ground <span className="key key-off" /> blocked samples
      </p>
      <p className="scope">
        Centre-of-disc geometry from the bundle; the radial scale is linear in elevation, so a 1° rise reads the same everywhere. Not a sky photograph and not a
        power or link estimate.
      </p>
    </section>
  );
}
