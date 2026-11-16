import { useEffect, useState } from 'react';

/**
 * Batch Coverage Gauge sidecar (format polaris-coverage-sidecar-v1), written verbatim by
 * tools/certainty/build_coverage_sidecar.py from the committed a-science batch file
 * data/batch/2026-11-14/certainty_height/coverage_gauge.json. Shown next to clone-agreement claims.
 * A bundle's own derived.coverage always wins. The viewer computes nothing here.
 */
export interface CoverageSidecar {
  format: 'polaris-coverage-sidecar-v1';
  status: string;
  definition: string;
  source: { path: string; sha256: string; repo_commit: string; record?: string };
  sites: Record<string, { tile_inscribed_radius_m: number; sun_pct: number; earth_pct: number }>;
}

let cache: Promise<CoverageSidecar | null> | null = null;
export function loadCoverageSidecar(): Promise<CoverageSidecar | null> {
  cache ??= fetch('certainty/coverage.json')
    .then((r) => (r.ok ? r.json() : null))
    .then((j) => (j && j.format === 'polaris-coverage-sidecar-v1' && j.sites ? (j as CoverageSidecar) : null))
    .catch(() => null);
  return cache;
}

export function useCoverageSidecar(): CoverageSidecar | null {
  const [c, setC] = useState<CoverageSidecar | null>(null);
  useEffect(() => {
    let live = true;
    void loadCoverageSidecar().then((x) => live && setC(x));
    return () => {
      live = false;
    };
  }, []);
  return c;
}
