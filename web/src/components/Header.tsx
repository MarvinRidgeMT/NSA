import { useRef } from 'react';
import { usePolaris } from '../store/store';
import { StatusBadge } from './StatusBadge';

export function Header({ onOpenProvenance }: { onOpenProvenance: () => void }) {
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
        <strong>
          POLARIS <span>X</span>
        </strong>
        <small>Bundle viewer · reads science-bundle-v2, computes nothing</small>
      </div>
      <div className="controls" role="group" aria-label="Data selection">
        <label>
          Bundle
          <select
            data-testid="bundle-select"
            value={loaded?.name ?? ''}
            onChange={(e) => {
              const ent = index.find((x) => x.file === e.target.value);
              if (ent) void loadFromUrl(`bundles/${ent.file}`, ent.file, ent.origin);
            }}
          >
            {!loaded && <option value="">—</option>}
            {index.map((e) => (
              <option key={e.file} value={e.file}>
                {e.status === 'DEMO_ONLY' ? '[DEMO] ' : ''}
                {e.label}
              </option>
            ))}
            {loaded && !index.some((e) => e.file === loaded.name) && <option value={loaded.name}>{loaded.name} (local file)</option>}
          </select>
        </label>
        <button type="button" className="btn" onClick={() => fileRef.current?.click()}>
          Open file…
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
        <label>
          Site
          <select data-testid="site-select" value={datasetIdx} disabled={!loaded} onChange={(e) => setSite(Number(e.target.value))}>
            {loaded?.bundle.datasets.map((d, i) => (
              <option key={d.siteId} value={i}>
                {d.site.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Scenario
          <select
            data-testid="scenario-select"
            value={scenarioId ?? ''}
            disabled={!scenarios.length}
            onChange={(e) => setScenario(e.target.value)}
          >
            {!scenarios.length && <option value="">none in bundle</option>}
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="right">
        {loaded && <StatusBadge status={loaded.status} />}
        <a className="btn" href={`${import.meta.env.BASE_URL}lab/index.html`} data-testid="decision-lab-link">
          Decision Lab
        </a>
        <button type="button" className="btn" onClick={onOpenProvenance} disabled={!loaded} data-testid="open-provenance">
          Provenance
        </button>
      </div>
    </header>
  );
}
