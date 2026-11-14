import { useEffect, useMemo, useRef, useState } from 'react';
import { latLonToXY, loadGrey, loadMeta, lut, rampCss, toPercent, xyToLatLon, type LayerKey, type Pgda69Image, type Pgda69Meta, type Roi } from '../layers/pgda69';
import type { View } from '../store/view';

const SIZE = 560; // SVG view box (square)
type Grey = { w: number; h: number; v: Uint8ClampedArray };

function fmtPct(v: number | null | undefined, d = 1) {
  return v === null || v === undefined ? '—' : `${v.toFixed(d)} %`;
}

/** Map one image's grid extent to the square view box. */
function frameOf(img: Pgda69Image) {
  const span = img.width * img.pixelM;
  const toX = (gx: number) => ((gx - img.x0) / span) * SIZE;
  const toY = (gy: number) => ((img.y0 - gy) / span) * SIZE;
  const toGrid = (sx: number, sy: number): [number, number] => [img.x0 + (sx / SIZE) * span, img.y0 - (sy / SIZE) * span];
  return { span, toX, toY, toGrid };
}

export function PolarMap({ v }: { v: View | null }) {
  const [meta, setMeta] = useState<Pgda69Meta | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [layer, setLayer] = useState<LayerKey>('sun');
  const [area, setArea] = useState<string>('overview'); // 'overview' or a site key
  const [sel, setSel] = useState<string | null>(null);
  const [grey, setGrey] = useState<Grey | null>(null);
  const [hover, setHover] = useState<{ sx: number; sy: number; lat: number; lon: number; pct: number | null } | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    loadMeta().then(setMeta, (e: Error) => setErr(e.message));
  }, []);

  const img: Pgda69Image | null = meta ? (area === 'overview' ? meta.images.overview : meta.images.sites[area]) : null;

  useEffect(() => {
    if (!img) return;
    let live = true;
    setGrey(null);
    loadGrey(img[layer].file).then(
      (g) => live && setGrey(g),
      (e: Error) => live && setErr(e.message),
    );
    return () => {
      live = false;
    };
  }, [img, layer]);

  useEffect(() => {
    const c = canvasRef.current;
    if (!c || !grey) return;
    c.width = grey.w;
    c.height = grey.h;
    const ctx = c.getContext('2d')!;
    const out = ctx.createImageData(grey.w, grey.h);
    const L = lut(layer);
    for (let i = 0; i < grey.v.length; i++) out.data.set(L.subarray(grey.v[i] * 4, grey.v[i] * 4 + 4), i * 4);
    ctx.putImageData(out, 0, 0);
  }, [grey, layer]);

  const sites = useMemo(() => (meta ? [...new Set(meta.rois.map((r) => r.site))] : []), [meta]);

  if (err)
    return (
      <section className="panel" aria-labelledby="pm-title">
        <h2 id="pm-title">South Pole map · NASA PGDA 69</h2>
        <p className="note">Layer not available: {err}</p>
      </section>
    );
  if (!meta || !img) return <section className="panel"><p className="note">Loading NASA PGDA 69 layer…</p></section>;

  const F = frameOf(img);
  const rois = meta.rois.filter((r) => area === 'overview' || r.site === area);
  const graticule = area === 'overview' ? [-89, -88, -87, -86, -85] : [];
  const spokes = area === 'overview' ? [0, 30, 60, 90, 120, 150, 180, -150, -120, -90, -60, -30] : [];
  const pole = [F.toX(0), F.toY(0)];
  const bundleSite = v?.dataset.site;
  const bundleXY = bundleSite ? latLonToXY(bundleSite.latitudePlanetocentricDeg, bundleSite.longitudeEastDeg) : null;
  const selRoi = meta.rois.find((r) => r.id === sel) ?? null;
  const scaleKm = area === 'overview' ? 50 : 1;

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!grey) return;
    const r = e.currentTarget.getBoundingClientRect();
    const sx = ((e.clientX - r.left) / r.width) * SIZE;
    const sy = ((e.clientY - r.top) / r.height) * SIZE;
    const [gx, gy] = F.toGrid(sx, sy);
    const col = Math.floor((gx - img.x0) / img.pixelM);
    const row = Math.floor((img.y0 - gy) / img.pixelM);
    if (col < 0 || row < 0 || col >= grey.w || row >= grey.h) return setHover(null);
    const [lat, lon] = xyToLatLon(gx, gy);
    setHover({ sx, sy, lat, lon, pct: toPercent(grey.v[row * grey.w + col], meta.encoding) });
  };

  const ringPath = (r: Roi) => 'M' + r.ring.map(([x, y]) => `${F.toX(x).toFixed(1)},${F.toY(y).toFixed(1)}`).join('L') + 'Z';
  const sorted = [...meta.rois].sort((a, b) => (b[layer].mean ?? 0) - (a[layer].mean ?? 0));

  return (
    <section className="panel polar" aria-labelledby="pm-title" data-testid="polar-map">
      <div className="panel-head">
        <h2 id="pm-title">South Pole map · where would you land?</h2>
        <span className="badge badge-nasa" data-testid="pgda69-badge">
          NASA PGDA 69 · reference product
        </span>
      </div>
      <div className="polar-controls" role="group" aria-label="Map controls">
        <fieldset className="seg">
          <legend className="sr-only">Layer</legend>
          {(['sun', 'earth'] as const).map((k) => (
            <label key={k} className={`seg-btn ${layer === k ? 'on' : ''} ${k}`}>
              <input type="radio" name="pgda69-layer" value={k} checked={layer === k} onChange={() => setLayer(k)} data-testid={`layer-${k}`} />
              {k === 'sun' ? 'Average Sun visibility' : 'Average Earth visibility'}
            </label>
          ))}
        </fieldset>
        <label>
          Area
          <select value={area} onChange={(e) => setArea(e.target.value)} data-testid="polar-area">
            <option value="overview">South pole 85–90° S (240 m/px)</option>
            {sites.map((s) => (
              <option key={s} value={s}>
                {s} · {meta.rois.find((r) => r.site === s)?.siteName} (60 m/px)
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="polar-body">
        <div className="polar-map">
          <canvas ref={canvasRef} className="polar-canvas" aria-hidden="true" />
          <svg
            viewBox={`0 0 ${SIZE} ${SIZE}`}
            className="polar-overlay"
            role="img"
            aria-label={`${layer === 'sun' ? 'Average Sun' : 'Average Earth'} visibility map, ${area === 'overview' ? 'whole south polar region' : area}, with landing-region outlines.`}
            onMouseMove={onMove}
            onMouseLeave={() => setHover(null)}
          >
            {graticule.map((lat) => {
              const rho = Math.hypot(...latLonToXY(lat, 0));
              return (
                <g key={lat}>
                  <circle cx={pole[0]} cy={pole[1]} r={(rho / F.span) * SIZE} className="grat" />
                  <text x={pole[0] + 3} y={pole[1] - (rho / F.span) * SIZE - 3} className="grat-label">
                    {Math.abs(lat)}° S
                  </text>
                </g>
              );
            })}
            {spokes.map((lon) => {
              const [x, y] = latLonToXY(-85, lon);
              return (
                <g key={lon}>
                  <line x1={pole[0]} y1={pole[1]} x2={F.toX(x)} y2={F.toY(y)} className="grat" />
                  <text x={F.toX(x * 0.93)} y={F.toY(y * 0.93)} className="grat-label" textAnchor="middle">
                    {lon === 0 ? '0°' : lon === 180 ? '180°' : `${Math.abs(lon)}°${lon > 0 ? 'E' : 'W'}`}
                  </text>
                </g>
              );
            })}
            {area === 'overview' &&
              sites.map((s) => {
                const rs = meta.rois.filter((r) => r.site === s);
                const cx = rs.reduce((a, r) => a + r.centroidXY[0], 0) / rs.length;
                const cy = rs.reduce((a, r) => a + r.centroidXY[1], 0) / rs.length;
                return (
                  <g key={s} className="site-pin" onClick={() => setArea(s)} role="button" tabIndex={0} aria-label={`Zoom to ${s}`} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && setArea(s)} data-testid={`pin-${s}`}>
                    <circle cx={F.toX(cx)} cy={F.toY(cy)} r={7} />
                    <text x={F.toX(cx) + 10} y={F.toY(cy) + 4}>
                      {s}
                    </text>
                  </g>
                );
              })}
            {area !== 'overview' &&
              rois.map((r) => (
                <g key={r.id} className={`roi ${sel === r.id ? 'sel' : ''}`} onClick={() => setSel(r.id)} role="button" tabIndex={0} aria-label={`${r.id}: Sun ${fmtPct(r.sun.mean)}, Earth ${fmtPct(r.earth.mean)}`} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && setSel(r.id)} data-testid={`roi-${r.id}`}>
                  <path d={ringPath(r)} />
                  <text x={F.toX(r.centroidXY[0]) + 8} y={F.toY(r.centroidXY[1]) - 6}>
                    ROI{r.roi}
                  </text>
                </g>
              ))}
            {bundleXY && F.toX(bundleXY[0]) >= 0 && F.toX(bundleXY[0]) <= SIZE && F.toY(bundleXY[1]) >= 0 && F.toY(bundleXY[1]) <= SIZE && (
              <g className="bundle-site" data-testid="bundle-site-marker">
                <path d={`M${F.toX(bundleXY[0])},${F.toY(bundleXY[1]) - 8}l7,14h-14z`} />
                <text x={F.toX(bundleXY[0]) + 10} y={F.toY(bundleXY[1]) + 14}>
                  loaded bundle observer
                </text>
              </g>
            )}
            <g className="scalebar" transform={`translate(16, ${SIZE - 22})`}>
              <line x1={0} x2={((scaleKm * 1000) / F.span) * SIZE} y1={0} y2={0} />
              <text x={0} y={-6}>
                {scaleKm} km
              </text>
            </g>
            {hover && (
              <g className="hover-tip" pointerEvents="none">
                <circle cx={hover.sx} cy={hover.sy} r={4} />
                <text x={Math.min(hover.sx + 10, SIZE - 210)} y={Math.max(hover.sy - 10, 16)}>
                  {hover.lat.toFixed(4)}°, {hover.lon.toFixed(3)}°E · {hover.pct === null ? 'no data' : `${hover.pct.toFixed(1)} % (±0.2)`}
                </text>
              </g>
            )}
          </svg>
          <div className="polar-legend">
            <span>0 %</span>
            <span className="ramp" style={{ background: rampCss(layer) }} />
            <span>100 %</span>
            <span className="nodata-key" /> no data
          </div>
          {area !== 'overview' && (
            <button type="button" className="btn" onClick={() => setArea('overview')}>
              ← Whole south pole
            </button>
          )}
        </div>
        <div className="polar-side">
          <table className="constraints rois" data-testid="roi-table">
            <caption className="sr-only">Landing regions from PGDA 78 with PGDA 69 averages</caption>
            <thead>
              <tr>
                <th scope="col">Region</th>
                <th scope="col">Sun avg</th>
                <th scope="col">Earth avg</th>
                <th scope="col">Range ({layer})</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr key={r.id} className={sel === r.id ? 'sel' : ''} data-testid={`roi-row-${r.id}`}>
                  <th scope="row">
                    <button
                      type="button"
                      className="linkish"
                      onClick={() => {
                        setArea(r.site);
                        setSel(r.id);
                      }}
                    >
                      {r.id}
                    </button>
                  </th>
                  <td data-value={r.sun.mean}>{fmtPct(r.sun.mean)}</td>
                  <td data-value={r.earth.mean}>{fmtPct(r.earth.mean)}</td>
                  <td className="muted">
                    {fmtPct(r[layer].min, 0)}–{fmtPct(r[layer].max, 0)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {selRoi && (
            <dl className="kv roi-detail" data-testid="roi-detail">
              <dt>Region</dt>
              <dd>
                {selRoi.id} · {selRoi.siteName}
              </dd>
              <dt>Centroid</dt>
              <dd>
                {selRoi.lat.toFixed(5)}°, {selRoi.lonE.toFixed(5)}°E
              </dd>
              <dt>Area</dt>
              <dd>{(selRoi.areaM2 / 1e4).toFixed(1)} ha · {selRoi.sun.n60mPixels} pixels at 60 m</dd>
              <dt>Sun (mean · min–max)</dt>
              <dd>
                {fmtPct(selRoi.sun.mean)} · {fmtPct(selRoi.sun.min, 0)}–{fmtPct(selRoi.sun.max, 0)}
              </dd>
              <dt>Earth (mean · min–max)</dt>
              <dd>
                {fmtPct(selRoi.earth.mean)} · {fmtPct(selRoi.earth.min, 0)}–{fmtPct(selRoi.earth.max, 0)}
              </dd>
            </dl>
          )}
          <details className="caveats">
            <summary>What these numbers are (and aren't)</summary>
            <p>{meta.meaning.sun}</p>
            <p>{meta.meaning.earth}</p>
            <ul>
              {meta.caveats.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
            <p className="muted small">
              Region outlines: <a href={meta.roiProduct} target="_blank" rel="noopener noreferrer">PGDA 78</a>. Maps:{' '}
              <a href={meta.product} target="_blank" rel="noopener noreferrer">PGDA 69</a>. {meta.citation}.
            </p>
          </details>
        </div>
      </div>
    </section>
  );
}
