import { useEffect, useMemo, useState } from 'react';

/**
 * "Real vs model" viewer (display only). Pick a real LROC NAC image window; see it next to its POLARIS render twin, the
 * log-ratio difference and the shadow-edge overlay, with the pre-registered scores for that row.
 *
 * Data: `render_vs_real/index.json` + PNG panels written by `python -m tools.validation.render_vs_real.report --web`
 * (git-ignored under web/public/render_vs_real/). Nothing here computes or changes a number. Every number carries
 * data-result-id (row in tools/validation/render_vs_real/results/scores.jsonl), data-source and data-label.
 */

export type RealVsModelRow = {
  id: string; // `${productId}__${site}`
  productId: string;
  site: string;
  product: string; // terrain product of the render shown
  photometry: string;
  iouShadow: number | null;
  edgeMedianM: number | null;
  ssim: number | null;
  wasserstein1: number | null;
  regOffsetM: number | null;
  sunElDeg: number | null;
  startUtc: string;
  image: string; // relative to the index file
  resultId: string;
};

export type RealVsModelIndex = {
  schema: 'polaris-render-vs-real-index-v1';
  label: string;
  protocol: string;
  credit: string;
  generatedUtc: string;
  rows: RealVsModelRow[];
};

export function validateIndex(x: unknown): RealVsModelIndex {
  const o = x as RealVsModelIndex;
  if (!o || o.schema !== 'polaris-render-vs-real-index-v1' || !Array.isArray(o.rows)) {
    throw new Error('render-vs-real index: unexpected schema');
  }
  if (!/SOURCE-BASED/.test(o.label) || !/dev/i.test(o.label)) {
    throw new Error('render-vs-real index: label must state SOURCE-BASED and the dev split');
  }
  return o;
}

const fmt = (v: number | null, d: number) => (v === null || !Number.isFinite(v) ? '—' : v.toFixed(d));

export function RealVsModelView({ index, base }: { index: RealVsModelIndex; base: string }) {
  const [sel, setSel] = useState(0);
  const rows = useMemo(() => [...index.rows].sort((a, b) => a.id.localeCompare(b.id)), [index]);
  const r = rows[Math.min(sel, rows.length - 1)];
  if (!r) return <p data-testid="rvm-empty">No scored rows.</p>;
  const src = 'tools/validation/render_vs_real/results/scores.jsonl';
  return (
    <section className="real-vs-model" data-testid="real-vs-model" data-label={index.label} data-classification="SOURCE-BASED">
      <header>
        <h3>Real vs model</h3>
        <p className="label" data-testid="rvm-label">{index.label}</p>
        <label>
          Image{' '}
          <select data-testid="rvm-select" value={sel} onChange={(e) => setSel(Number(e.target.value))}>
            {rows.map((row, i) => (
              <option key={row.id} value={i}>
                {row.productId} · {row.site}
              </option>
            ))}
          </select>
        </label>
      </header>
      <figure>
        <img
          data-testid="rvm-image"
          src={`${base}${r.image}`}
          alt={`LROC NAC ${r.productId} (${r.site}): real, render twin (${r.product}, ${r.photometry}), difference, shadow edges`}
          style={{ maxWidth: '100%' }}
        />
        <figcaption>
          Panels: real (LROC NAC CDR, {index.credit}) · render twin · log-ratio difference (red render brighter, blue darker) ·
          edges (yellow observed, cyan predicted). Render terrain {r.product}, photometry {r.photometry}, registered.
        </figcaption>
      </figure>
      <dl data-result-id={r.resultId} data-source={src} data-label={index.label}>
        <dt>Start UTC</dt>
        <dd data-testid="rvm-utc">{r.startUtc}</dd>
        <dt>Sun elevation at site</dt>
        <dd data-testid="rvm-sun">{fmt(r.sunElDeg, 2)} °</dd>
        <dt>Shadow IoU</dt>
        <dd data-testid="rvm-iou" data-value={r.iouShadow ?? ''}>{fmt(r.iouShadow, 3)}</dd>
        <dt>Shadow-edge error (median)</dt>
        <dd data-testid="rvm-edge" data-value={r.edgeMedianM ?? ''}>{fmt(r.edgeMedianM, 1)} m</dd>
        <dt>SSIM (non-saturated)</dt>
        <dd data-testid="rvm-ssim">{fmt(r.ssim, 3)}</dd>
        <dt>Histogram distance (W1, log10 I/F)</dt>
        <dd>{fmt(r.wasserstein1, 3)}</dd>
        <dt>Registration offset</dt>
        <dd data-testid="rvm-offset">{fmt(r.regOffsetM, 0)} m</dd>
      </dl>
      <p className="caveat">
        Protocol: {index.protocol}. Dev (training) split only; the held-out run has not been done. A good score validates render
        geometry only, not power or communications.
      </p>
    </section>
  );
}

export function RealVsModel({ indexUrl = './render_vs_real/index.json' }: { indexUrl?: string }) {
  const [state, setState] = useState<{ index?: RealVsModelIndex; error?: string }>({});
  useEffect(() => {
    let live = true;
    fetch(indexUrl)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((j) => live && setState({ index: validateIndex(j) }))
      .catch((e: Error) => live && setState({ error: e.message }));
    return () => {
      live = false;
    };
  }, [indexUrl]);
  if (state.error)
    return (
      <p data-testid="rvm-missing">
        Real-vs-model data not built ({state.error}). Run python -m tools.validation.render_vs_real.report --web.
      </p>
    );
  if (!state.index) return <p data-testid="rvm-loading">Loading real-vs-model index…</p>;
  const base = indexUrl.slice(0, indexUrl.lastIndexOf('/') + 1);
  return <RealVsModelView index={state.index} base={base} />;
}

export default RealVsModel;
