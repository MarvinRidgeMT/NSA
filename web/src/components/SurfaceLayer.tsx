import { SURFACE_LAYERS, useSurface, type SurfaceLayerId } from '../store/surface';
import { layerCoverageOnCrop, type VisualLayer } from '../bundle/visualLayers';
import type { View } from '../store/view';
import { useUi } from '../store/ui';

export const EXAGGERATIONS = [1, 2, 3, 5, 10] as const;

/** The registered image layer that covers this view's DEM crop best (≥ 20 % of it), or null. Pure lookup, no numbers change. */
export function albedoLayerFor(v: View, layers: VisualLayer[] | undefined): { layer: VisualLayer; coverage: number } | null {
  const dem = v.dataset.dem;
  if (!dem || !layers?.length) return null;
  const site = v.dataset.site.projectedMeters;
  const half = (dem.n * dem.spacing) / 2; // pixel-edge half width
  const centre = { x: site.x + dem.originX + ((dem.n - 1) * dem.spacing) / 2, y: site.y + dem.originY + ((dem.n - 1) * dem.spacing) / 2 };
  let best: { layer: VisualLayer; coverage: number } | null = null;
  for (const layer of layers) {
    if (layer.role !== 'albedo') continue;
    const c = layerCoverageOnCrop(layer, centre, half).overlapFraction;
    if (c >= 0.2 && (!best || c > best.coverage)) best = { layer, coverage: c };
  }
  return best;
}

/** Surface-layer picker (lives in the camera row). Only offered when the scene has a terrain context pack. */
export function SurfaceLayerPicker() {
  const { layer, setLayer, contextLoaded, albedoCoverage } = useSurface();
  if (!contextLoaded) return null;
  return (
    <label className="layer-pick">
      <span className="lab">Surface</span>
      <select value={layer} onChange={(e) => setLayer(e.target.value as SurfaceLayerId)} data-testid="surface-layer" aria-label="Surface layer (display only)">
        {SURFACE_LAYERS.map((l) => (
          <option key={l.id} value={l.id} disabled={l.id === 'albedo' && albedoCoverage <= 0}>
            {l.label}
            {l.id === 'albedo' && albedoCoverage <= 0 ? ' (no registered image here)' : ''}
          </option>
        ))}
      </select>
    </label>
  );
}

/** Vertical exaggeration of the DRAWN scene only. The bundle numbers (visibility, margins, metrics) never change. */
export function ExaggerationPicker() {
  const k = useUi((s) => s.exaggeration);
  return (
    <label className="exag-pick" title="Display only: stretches the drawn terrain, mast, rays and markers vertically together. Visibility, margins and metrics are the bundle's and do not change.">
      <span className="lab">Vertical</span>
      <select value={k} onChange={(e) => useUi.getState().set({ exaggeration: Number(e.target.value) })} data-testid="vertical-exaggeration" aria-label="Vertical exaggeration (display only)">
        {EXAGGERATIONS.map((x) => (
          <option key={x} value={x}>
            {x === 1 ? '1× physical' : `${x}× (display)`}
          </option>
        ))}
      </select>
    </label>
  );
}

/** Chip naming what the surface colour is and where it comes from. Always says VISUAL / derived; never a metric. */
export function SurfaceLayerChip({ v }: { v: View }) {
  const { layer, contextLoaded, albedoCoverage, visualLayers, detail, setDetail, detailCoverage, detailRmsM } = useSurface();
  if (!contextLoaded || !v.dataset.dem) return null;
  const a = albedoLayerFor(v, visualLayers?.layers);
  const active = layer === 'albedo' && !a ? 'regolith' : layer;
  const def = SURFACE_LAYERS.find((l) => l.id === active)!;
  const text =
    active === 'albedo' && a
      ? `${a.layer.label} · ${a.layer.productId} · ${a.layer.pixelSizeM} m/px · covers ${(albedoCoverage * 100).toFixed(0)} % of this crop · not mission-time lighting`
      : def.chip;
  return (
    <span className="mode layer-chip" data-testid="surface-layer-label" data-layer={active} title="Surface colour is display only. Geometry is the bundle DEM; light and shadow follow the bundle's Sun direction.">
      {text}
      {detailCoverage > 0 && (
        // the relief toggle lives on the chip that names the surface (session A, 15 Nov 17:35: in the camera row it pushed the
        // layer picker 91 px past the row at 1440 px and widened the page at 390 px)
        <button type="button" className="detail-toggle" aria-pressed={detail} onClick={() => setDetail(!detail)} data-testid="surface-detail" title="NASA GSFC shape-from-shading relief (LROC NAC images + LOLA), display only. Off = the LOLA crop the solver uses.">
          NAC relief {detail ? 'on' : 'off'}
        </button>
      )}
      {detailCoverage > 0 && detail && (
        <span className="layer-context" data-testid="surface-detail-label">
          {' '}· RELIEF: NASA GSFC shape-from-shading (NAC + LOLA), DISPLAY ONLY, {detailCoverage >= 0.995 ? 'whole crop' : `${(detailCoverage * 100).toFixed(0)} % of crop`}, differs from the solver's LOLA crop by {detailRmsM.toFixed(1)} m rms · fine grain is synthetic
        </span>
      )}
      {detailCoverage > 0 && !detail && <span className="layer-context" data-testid="surface-detail-label"> · RELIEF: LOLA 5 m crop (the solver's surface)</span>}
      <span className="layer-context"> · 80 m PGDA 90 context to ~16 km · shadows: display model</span>
    </span>
  );
}

/** Opens the global Moon (visual context). Lives at the start of the camera row; only for datasets with a terrain mesh. */
export function GlobeButton() {
  const { globe, setGlobe } = useSurface();
  return (
    <button type="button" className="btn" aria-pressed={globe} onClick={() => setGlobe(!globe)} data-testid="globe-open" title="Where on the Moon this site is (NASA SVS global model, visual context only)">
      Moon
    </button>
  );
}
