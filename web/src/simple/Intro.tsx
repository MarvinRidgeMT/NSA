import { loadFraction, loadLabel, type LoadParts } from './introMath';

/**
 * Opening sequence (S3): what is laid over the picture while it plays. The picture itself is the globe's own canvas
 * (simple/Globe.tsx, phase 'intro'); this is the progress line, what is being waited for, where the light comes from, and Skip.
 *
 * The progress figure is real: `parts` are the loaders' own states (introMath.loadFraction). The light line's time, azimuth
 * and site name are passed in by SimpleApp, which reads them from the bundle. A press anywhere on this layer skips.
 */
export function Intro({ parts, lightLine, leaving, onSkip }: { parts: LoadParts; lightLine: string | null; leaving: boolean; onSkip: () => void }) {
  const frac = loadFraction(parts);
  const pct = Math.floor(frac * 100);
  return (
    <div className="s-intro" data-testid="simple-intro" data-leaving={leaving || undefined} inert={leaving} onClick={onSkip}>
      <div className="s-intro-foot">
        <div className="s-intro-text">
          <p className="s-intro-load">
            <span role="status">{loadLabel(parts)}</span>
            <span className="s-intro-pct" data-testid="intro-pct" aria-hidden="true">
              {pct} %
            </span>
          </p>
          {lightLine && (
            <p className="s-intro-light" data-testid="intro-light">
              {lightLine}
            </p>
          )}
        </div>
        <button type="button" className="s-btn s-btn--sm s-intro-skip" data-testid="intro-skip" onClick={onSkip}>
          Skip
          <kbd aria-hidden="true">Esc</kbd>
        </button>
      </div>
      <div className="s-intro-bar" role="progressbar" aria-label="Loading" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} data-testid="intro-progress">
        <i style={{ transform: `scaleX(${frac.toFixed(4)})` }} />
      </div>
    </div>
  );
}
