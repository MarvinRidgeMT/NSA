import { useRef } from 'react';
import { usePolaris } from '../store/store';
import { markSiteChosen } from '../store/siteDefaults';
import { StatusBadge } from './StatusBadge';

/** Short, unambiguous option text: the file stem (the full label stays in the title attribute and the provenance record). */
const shortLabel = (file: string) =>
  /^polaris-x5d-roi-/.test(file) ? 'ROI export · 3 sites · 5 m DEM' : file.replace(/\.json$/, '').replace(/_2026-11-14_14d/, '').replace(/_/g, ' ');

export type Workspace = 'sky' | 'decision' | 'evidence';
export const WORKSPACES: { id: Workspace; label: string; hint: string }[] = [
  { id: 'sky', label: 'Explore', hint: 'the terrain and sky the observer sees' },
  { id: 'decision', label: 'Decision', hint: 'does the configuration meet its requirements?' },
  { id: 'evidence', label: 'Evidence', hint: 'why the numbers should or should not be trusted' },
];

/**
 * Penumbra global shell: identity, current place, data selection, workspace navigation and status.
 * Workspace tabs keep role=tab + arrow-key navigation (one tablist for the whole app).
 */
export function Header({
  onOpenProvenance,
  ws,
  go,
  story,
  onGuide,
}: {
  onOpenProvenance: () => void;
  onGuide?: () => void;
  ws: Workspace | 'story';
  go: (id: Workspace | 'story') => void;
  story?: boolean;
}) {
  const index = usePolaris((s) => s.index);
  const loaded = usePolaris((s) => s.loaded);
  const datasetIdx = usePolaris((s) => s.datasetIdx);
  const scenarioId = usePolaris((s) => s.scenarioId);
  const { loadFromUrl, loadFromFile, setSite, setScenario } = usePolaris.getState();
  const fileRef = useRef<HTMLInputElement>(null);
  const ds = loaded?.bundle.datasets[datasetIdx];
  const scenarios = ds?.derived?.scenarios ?? [];

  return (
    <header className="topbar">
      <div className="brand">
        <a
          href="#story"
          onClick={(e) => {
            e.preventDefault();
            go('story');
          }}
          aria-label="POLARIS X — story"
        >
          POLARIS X
        </a>
        {ds && <span className="crumb">Moon › South Pole › {ds.site.name}</span>}
      </div>
      {!story && (
        <div className="controls" role="group" aria-label="Data selection">
          <label className="bundle">
            <span className="sr-only">Bundle</span>
                        <select
              data-testid="bundle-select"
              value={loaded?.name ?? ''}
              title={index.find((e) => e.file === loaded?.name)?.label ?? loaded?.name}
              onChange={(e) => {
                const ent = index.find((x) => x.file === e.target.value);
                if (ent) void loadFromUrl(`bundles/${ent.file}`, ent.file, ent.origin);
              }}
            >
              {!loaded && <option value="">—</option>}
              {index.map((e) => (
                <option key={e.file} value={e.file}>
                  {e.status === 'DEMO_ONLY' ? '[DEMO] ' : ''}
                  {shortLabel(e.file)}
                </option>
              ))}
              {loaded && !index.some((e) => e.file === loaded.name) && <option value={loaded.name}>{loaded.name} (local file)</option>}
            </select>
          </label>
          <button type="button" className="btn btn-icon" onClick={() => fileRef.current?.click()} aria-label="Open a bundle file" title="Open a bundle file…">
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.4">
              <path d="M2 4h4l1.5 1.5H14V13H2z" />
            </svg>
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".json,application/json"
            hidden
            data-testid="bundle-file"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void loadFromFile(f);
              e.target.value = '';
            }}
          />
          <a className="btn" href={`${import.meta.env.BASE_URL}lab/index.html`} data-testid="decision-lab-link">
            Decision Lab
          </a>
          <label>
            <span className="sr-only">Site</span>
            <select data-testid="site-select" title="Site" value={datasetIdx} disabled={!loaded} onChange={(e) => { markSiteChosen(); setSite(Number(e.target.value)); }}>
              {loaded?.bundle.datasets.map((d, i) => (
                <option key={d.siteId} value={i}>
                  {d.site.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="sr-only">Scenario</span>
            <select data-testid="scenario-select" title="Scenario (mast height and terrain variant)" value={scenarioId ?? ''} disabled={!scenarios.length} onChange={(e) => setScenario(e.target.value)}>
              {!scenarios.length && <option value="">none in bundle</option>}
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}
      {story && <span style={{ flex: 1 }} />}
      <nav className="navtabs" role="tablist" aria-label="Workspaces" data-testid="workspaces">
        {WORKSPACES.map((w, i) => (
          <button
            key={w.id}
            type="button"
            role="tab"
            id={`tab-${w.id}`}
            aria-selected={ws === w.id}
            aria-controls={`ws-${w.id}`}
            tabIndex={ws === w.id || (ws === 'story' && i === 0) ? 0 : -1}
            title={w.hint}
            className={`navtab tab ${ws === w.id ? 'is-active' : ''}`}
            data-testid={`tab-${w.id}`}
            onClick={() => go(w.id)}
            onKeyDown={(e) => {
              if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                e.preventDefault();
                const j = (i + (e.key === 'ArrowRight' ? 1 : WORKSPACES.length - 1)) % WORKSPACES.length;
                go(WORKSPACES[j].id);
                document.getElementById(`tab-${WORKSPACES[j].id}`)?.focus();
              }
            }}
          >
            {w.label}
            <small>{w.hint}</small>
          </button>
        ))}
      </nav>
      <div className="right">
        {onGuide && (
          <button type="button" className="btn" onClick={onGuide} data-testid="guide-start" title="A five-scene walk through the live data (Esc exits)">
            Guided demo
          </button>
        )}
        {loaded && <StatusBadge status={loaded.status} />}
        {!story && (
          <button type="button" className="btn" onClick={onOpenProvenance} disabled={!loaded} data-testid="open-provenance">
            Provenance
          </button>
        )}
      </div>
    </header>
  );
}
