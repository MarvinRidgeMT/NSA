import { useId } from 'react';
import { LAYER_MANIFEST_URL, SYNC_COMMAND, rgbCss, type GlobeLayer, type LayerManifest } from '../globe/layers';
import { GLOBE_LAYER_CHOICES, useGlobe, type GlobeLayerChoice } from '../store/globe';

/**
 * Layer chooser + legend for the whole-Moon globe (v2 T2, V2 §2.2 item 5 and §2.5). Display only: choosing a layer changes
 * pixels on the globe, never a number. Every legend value carries the layer's source and label for the traceability scan.
 */
export type LayerDocState = { state: 'loading' } | { state: 'missing' } | { state: 'error'; why: string } | { state: 'ok'; doc: LayerManifest };

const stat = (v: unknown, d = 1) => (typeof v === 'number' && Number.isFinite(v) ? v.toFixed(d) : '—');

function Legend({ l }: { l: GlobeLayer }) {
  if (l.legend.kind === 'classes') {
    return (
      <ul className="gl-classes" data-testid="globe-legend">
        {l.legend.classes.map((c) => (
          <li key={c.label}>
            <span className="sw" style={{ background: rgbCss(c.rgb) }} aria-hidden="true" />
            {c.label}
          </li>
        ))}
      </ul>
    );
  }
  const g = l.legend;
  const stops = g.samples.map((s, i) => `${rgbCss(s.rgb)} ${(100 * i) / Math.max(1, g.samples.length - 1)}%`).join(', ');
  const unit = g.unit === 'fraction' ? '' : g.unit;
  return (
    <div className="gl-ramp" data-testid="globe-legend">
      <div className="bar" style={{ background: `linear-gradient(90deg, ${stops})` }} role="img" aria-label={`colour ramp from ${g.min}${unit} to ${g.max}${unit}`} />
      <div className="ends">
        <span>
          {g.min}
          {unit}
        </span>
        <span>
          {g.max}
          {unit}
          {g.unit === 'fraction' ? ' (fraction of samples)' : ''}
        </span>
      </div>
      {g.note && <p className="gl-note">{g.note}</p>}
    </div>
  );
}

function Stats({ l }: { l: GlobeLayer }) {
  const s = l.stats ?? {};
  let line: string | null = null;
  if (l.id === 'coverage-res') {
    const p = (s.percentByResolution ?? {}) as Record<string, number>;
    line = `Moon area by finest real resolution: ≤ 5 m ${stat(p['<= 5 m'], 3)} %, 5–20 m ${stat(p['5-20 m'], 2)} %, 20–40 m ${stat(p['20-40 m'], 2)} %, 40–80 m ${stat(p['40-80 m'], 2)} %`;
  } else if (l.id === 'slope') line = `Moon median slope ${stat(s.medianSlopeDeg)}°, p90 ${stat(s.p90SlopeDeg)}°; ${stat(s.pctAreaSlopeGt10Deg)} % of the area steeper than 10°`;
  else if (l.id === 'roughness') line = `Moon median RMS slope at ~1 km ${stat(s.medianRmsSlopeDeg)}°`;
  else if (l.id === 'earth-vis')
    line = `Earth always above the horizon on ${stat(s.areaPctAlwaysVisible)} % of the area, never on ${stat(s.areaPctNeverVisible)} %. Against PGDA 69 (85–90° S): median |Δ| ${stat(s.pgda69MedianAbsDiff, 4)}, r ${stat(s.pgda69PearsonR, 3)}`;
  else if (l.id === 'sun-vis')
    line = `Median fraction ${stat(s.medianSp, 3)} (south) / ${stat(s.medianNp, 3)} (north). Against PGDA 69 (85–90° S): median |Δ| ${stat(s.pgda69MedianAbsDiff, 4)}, r ${stat(s.pgda69PearsonR, 3)}`;
  if (!line) return null;
  return (
    <p className="gl-stats" data-testid="globe-layer-stats" data-source={`${s.source ?? 'docs/v2'}${s.created_utc ? ` (${s.created_utc})` : ''}`} data-label={l.label}>
      {line} <span className="src">— {s.source}</span>
    </p>
  );
}

export default function GlobeLayers({ doc, drapeOk, drapeNote }: { doc: LayerDocState; drapeOk: boolean; drapeNote?: string }) {
  const { layer, setLayer, opacity, setOpacity } = useGlobe();
  const name = useId();
  if (doc.state === 'loading') return <p className="gl-note">Loading the layer list…</p>;
  if (doc.state !== 'ok') {
    return (
      <div className="globe-layers" data-testid="globe-layers" data-state="missing">
        <p className="gl-note" role="status">
          The v2 analytics layers are not built in this copy ({doc.state === 'error' ? doc.why : `${LAYER_MANIFEST_URL} absent`}). Stage them with <code>{SYNC_COMMAND}</code>.
        </p>
      </div>
    );
  }
  const byId = new Map(doc.doc.layers.map((l) => [l.id, l]));
  const cur = layer === 'none' ? null : byId.get(layer) ?? null;
  return (
    <div className="globe-layers" data-testid="globe-layers" data-state="ok" data-layer={layer} data-source={LAYER_MANIFEST_URL} data-label="SOURCE-BASED · UNVALIDATED (display-only analytics)">
      <fieldset className="gl-choices">
        <legend>Global layers · display only</legend>
        {GLOBE_LAYER_CHOICES.map((id: GlobeLayerChoice) => {
          const l = id === 'none' ? null : byId.get(id);
          const missing = id !== 'none' && (!l || !l.built);
          return (
            <label key={id} className={missing ? 'off' : undefined}>
              <input
                type="radio"
                name={name}
                value={id}
                checked={layer === id}
                disabled={missing || (!drapeOk && id !== 'none')}
                onChange={() => setLayer(id)}
                data-testid={`globe-layer-${id}`}
              />
              {id === 'none' ? 'None (WAC base colour, VISUAL)' : l?.title ?? id}
              {missing ? ' — not built' : ''}
            </label>
          );
        })}
      </fieldset>
      {!drapeOk && <p className="gl-note" role="status">{drapeNote}</p>}
      <label className="gl-opacity">
        Layer opacity
        <input type="range" min={0} max={1} step={0.05} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} disabled={!cur} data-testid="globe-layer-opacity" aria-valuetext={`${Math.round(opacity * 100)} percent`} />
      </label>
      {cur && (
        <div className="gl-detail" data-testid="globe-layer-detail" data-source={`${LAYER_MANIFEST_URL} · ${cur.source}`} data-label={cur.label}>
          <span className="chip" data-testid="globe-layer-label">
            {cur.label}
          </span>
          <strong>{cur.title}</strong>
          <p>{cur.what}</p>
          <Legend l={cur} />
          <Stats l={cur} />
          <p className="gl-note">
            Cells: {cur.cells}
            {cur.cellRule ? `. ${cur.cellRule}` : ''}. Source: {cur.source}.
          </p>
          <p className="gl-note">
            Rebuild: <code>{cur.command}</code>; stage: <code>web/scripts/sync_v2_layers.py</code> (files and SHA-256 in <code>{LAYER_MANIFEST_URL}</code>).
          </p>
        </div>
      )}
    </div>
  );
}
