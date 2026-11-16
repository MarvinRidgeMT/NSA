import type { LodManifest } from '../bundle/lodTiles';
import { useLod } from '../store/lod';

/**
 * Toggle + on-screen statement for the near-field LOD layer (5D Phase 9.4). Shown only when tiles were built for the
 * dataset. Every number here describes the DISPLAY (tile spacing, tile count), carries its source and label, and none comes
 * from or feeds the solver.
 */
export function LodPanel({ manifest }: { manifest: LodManifest }) {
  const { on, setOn, stats } = useLod();
  const finest = manifest.levels[manifest.levels.length - 1]?.spacingM;
  const coarsest = manifest.levels[0]?.spacingM;
  const km = (manifest.halfExtentM / 1000).toFixed(0);
  return (
    <div
      className="lod-panel"
      data-testid="lod-panel"
      data-source={`context/lod/${manifest.datasetId}/manifest.json · ${manifest.source.product} · ${manifest.source.url} (SHA-256 ${manifest.source.sha256.slice(0, 12)}…)`}
      data-label="SOURCE-BASED · UNVALIDATED · DISPLAY ONLY"
      data-drawn={stats?.drawn ?? 0}
      data-finest={stats?.finestM ?? ''}
      data-pending={stats?.pending ?? 0}
    >
      <button
        type="button"
        className="detail-toggle"
        aria-pressed={on}
        onClick={() => setOn(!on)}
        data-testid="lod-toggle"
        title={`Draw the ±${km} km near field from the NASA PGDA 78 ${finest} m tile, streamed as quadtree tiles by camera distance. Display only: no number changes.`}
      >
        Near field ±{km} km · {finest} m {on ? 'on' : 'off'}
      </button>
      {on && (
        <span className="lod-label" data-testid="lod-label">
          {' '}NEAR FIELD · PGDA 78 quadtree {coarsest}–{finest} m · <strong>display only</strong> · solver numbers unchanged, never computed from these tiles
          {stats ? ` · ${stats.drawn} tiles drawn, ${stats.finestM ?? '–'}–${stats.coarsestM ?? '–'} m${stats.pending ? `, ${stats.pending} streaming` : ''}` : ' · loading'}
        </span>
      )}
    </div>
  );
}
