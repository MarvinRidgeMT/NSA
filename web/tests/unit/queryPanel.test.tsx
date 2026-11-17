import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import QueryPanel from '../../src/components/QueryPanel';
import GlobeLayers from '../../src/components/GlobeLayers';
import { useGlobe } from '../../src/store/globe';

const summary = {
  schema: 'polaris-anysite-precompute-summary-v1',
  label: 'SOURCE-BASED UNVALIDATED',
  window: '2026-11-14 00:00 UTC + 14 d, hourly; mast 1 m',
  terrain: 'merged whole-Moon pyramid',
  counts: {},
  sites: [
    { id: 'g1', name: 'grid 1', group: 'south_grid_1deg', lat: -85, lon: 30, status: 'done', sun_pct: 41.25, earth_pct: 10, sun_earth_pct: 5, longest_sun_gap_h: 120, ground_m: -1500, slope_deg: 3.5, site_hash: 'abc', horizons_raw: ['ffff0000aaaa1111'], uncertainty: {} },
  ],
};
const json = (b: unknown, status = 200, ct = 'application/json') => ({ ok: status < 400, status, headers: { get: () => ct }, json: async () => b }) as unknown as Response;

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  useGlobe.setState({ picked: null, layer: 'none', nearest: null });
});

describe('QueryPanel', () => {
  it('shows the nearest precomputed row with label, source, distance and command; the solver is reported down', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (u: string) =>
        u.endsWith('precompute_summary.json') ? json(summary) : u.endsWith('.meta.json') ? json({ source: 'data/anysite/precompute_summary.json', sha256: 'deadbeef'.repeat(8), bytes: 1 }) : json('', 500, 'text/plain'),
      ),
    );
    useGlobe.setState({ picked: { lat: -85.1, lon: 30, via: 'click' } });
    render(<QueryPanel markerLat={-89.5} markerLon={0} />);
    const res = await screen.findByTestId('query-result');
    expect(res.getAttribute('data-label')).toBe('SOURCE-BASED · UNVALIDATED');
    expect(res.getAttribute('data-source')).toContain('sha256 deadbeefdead');
    expect(screen.getByTestId('query-sun').textContent).toBe('41.25 % of hourly samples');
    expect(screen.getByTestId('query-distance').textContent).toMatch(/^3\.03 km from the picked point$/);
    expect(screen.getByTestId('query-not-here')).toBeTruthy();
    expect(screen.getByTestId('query-command').textContent).toContain("--lat -85 --lon 30 --mast 1 --start '2026-11-14 00:00' --days 14 --members ''");
    await waitFor(() => expect(screen.getByTestId('query-solver').getAttribute('data-state')).toBe('down'));
    expect((screen.getByTestId('query-compute') as HTMLButtonElement).disabled).toBe(true);
    expect(useGlobe.getState().nearest).toEqual({ lat: -85, lon: 30, name: 'grid 1' });
  });
});

describe('GlobeLayers', () => {
  it('says how to stage the layers when the manifest is absent, and disables layers on the SVS fallback', () => {
    const { unmount } = render(<GlobeLayers doc={{ state: 'missing' }} drapeOk />);
    expect(screen.getByTestId('globe-layers').textContent).toContain('sync_v2_layers.py');
    unmount();
    const doc = {
      state: 'ok' as const,
      doc: {
        schema: 'polaris-globe-layers-v1' as const,
        label: '',
        created_utc: '',
        script: '',
        layers: [{ id: 'slope' as const, title: 'Slope', label: 'SOURCE-BASED · UNVALIDATED', what: '', source: 's', command: 'c', built: true, files: [], legend: { kind: 'ramp' as const, unit: '°', min: 0, max: 40, samples: [{ value: 0, rgb: [1, 2, 3] }, { value: 40, rgb: [4, 5, 6] }] } }],
      },
    };
    render(<GlobeLayers doc={doc} drapeOk={false} drapeNote="not on the fallback" />);
    expect((screen.getByTestId('globe-layer-slope') as HTMLInputElement).disabled).toBe(true);
    expect(screen.getByText('not on the fallback')).toBeTruthy();
  });
});
