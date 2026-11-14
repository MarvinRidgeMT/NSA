import { useEffect, useState } from 'react';
import { usePolaris } from '../store/store';
import { fmtUtc, type View } from '../store/view';

export function TimeBar({ v }: { v: View }) {
  const timeError = usePolaris((s) => s.timeError);
  const timeNote = usePolaris((s) => s.timeNote);
  const playing = usePolaris((s) => s.playing);
  const { setSampleIndex, stepSample, setTime, setPlaying } = usePolaris.getState();
  const [draft, setDraft] = useState(fmtUtc(v.utcMs));
  const n = v.times.length;

  useEffect(() => setDraft(fmtUtc(v.utcMs)), [v.utcMs]);

  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => {
      const s = usePolaris.getState();
      const t = s.loaded?.times[s.datasetIdx];
      if (!t || s.utcMs === null) return;
      if (s.utcMs >= t[t.length - 1]) return s.setPlaying(false);
      s.stepSample(1);
    }, 400);
    return () => window.clearInterval(id);
  }, [playing]);

  const between = v.br.exact === null;
  return (
    <section className="timebar" aria-label="Mission clock">
      <div className="clock">
        <span className="eyebrow">UTC</span>
        <output data-testid="utc" aria-live="polite">
          {fmtUtc(v.utcMs)}
        </output>
        <span className="muted" data-testid="sample-pos">
          {between ? `between samples ${v.br.i0 + 1}–${v.br.i1 + 1}` : `sample ${v.nearest + 1} / ${n}`}
        </span>
      </div>
      <div className="scrub">
        <button type="button" className="btn" aria-label="Previous sample" onClick={() => stepSample(-1)}>
          ‹
        </button>
        <button type="button" className="btn" onClick={() => setPlaying(!playing)} aria-pressed={playing} data-testid="play">
          {playing ? 'Pause' : 'Play'}
        </button>
        <button type="button" className="btn" aria-label="Next sample" onClick={() => stepSample(1)}>
          ›
        </button>
        <input
          type="range"
          min={0}
          max={n - 1}
          step={1}
          value={v.nearest}
          data-testid="scrubber"
          aria-label="Sample index"
          aria-valuetext={fmtUtc(v.times[v.nearest])}
          onChange={(e) => setSampleIndex(Number(e.target.value))}
        />
      </div>
      <form
        className="goto"
        onSubmit={(e) => {
          e.preventDefault();
          const ms = Date.parse(draft.trim());
          if (!Number.isFinite(ms) || !/Z$/.test(draft.trim())) {
            usePolaris.setState({ timeError: 'Enter UTC as ISO-8601 ending in Z, e.g. 2026-11-14T18:30:00Z' });
            return;
          }
          setTime(ms);
        }}
      >
        <label>
          Go to UTC
          <input value={draft} onChange={(e) => setDraft(e.target.value)} data-testid="utc-input" spellCheck={false} />
        </label>
        <button type="submit" className="btn">
          Go
        </button>
        <span className="muted">
          coverage {fmtUtc(v.times[0])} → {fmtUtc(v.times[n - 1])}
        </span>
      </form>
      {timeNote && !timeError && (
        <p className="note" role="status" data-testid="time-note">
          {timeNote}
        </p>
      )}
      {timeError && (
        <p className="error" role="alert" data-testid="time-error">
          {timeError}
        </p>
      )}
    </section>
  );
}
