import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { WhatMatters, WhatMattersView } from '../../src/components/WhatMatters';
import { validateCube, type CubeMetric, type ScenarioCube } from '../../src/bundle/scenarioCube';
import type { View } from '../../src/store/view';

const scalar = (v: number, units = '% of variance'): CubeMetric => ({ units, label: 'x', dtype: 'float64', values: [v], provenance: 'synthetic' });

function block(shares: Record<string, [number, number, number]>, sd: number, inter: number) {
  const metrics: Record<string, CubeMetric> = { sd: scalar(sd, '%'), interaction_pct: scalar(inter) };
  for (const [a, [first, total, shap]] of Object.entries(shares)) {
    metrics[`first_pct__${a}`] = scalar(first);
    metrics[`total_pct__${a}`] = scalar(total);
    metrics[`shapley_pct__${a}`] = scalar(shap);
  }
  return { dims: [], metrics, method: 'Exact functional ANOVA (synthetic method text)', caveat: 'Share of spread within this scenario set (synthetic caveat).' };
}

/** Synthetic sensitivity cube in the committed layout (science/cube/build_sensitivity.py). */
function synth(): ScenarioCube {
  const pos = block({ T: [0.1, 2.0, 0.8], D_pos: [30.0, 62.0, 45.2], S: [36.0, 70.0, 54.0] }, 36.0, 34.0);
  const cen = block({ T: [0.0, 0.7, 0.3], D_mast: [5.8, 13.9, 9.7], S: [86.0, 94.0, 90.0] }, 21.4, 8.2);
  return {
    schema: 'scenario-cube-v1',
    cube_id: 'test-sensitivity-v1',
    site_id: 'test',
    label: 'SOURCE-BASED · UNVALIDATED',
    generated_utc: '2026-11-16T00:00:00Z',
    fixed: {
      sources: 'centre,position',
      axes__centre: 'T,D_mast,S',
      axes__position: 'T,D_pos,S',
      title__centre: 'Centre set',
      title__position: 'Position set',
      metrics: 'sun_pct',
      metric_labels: 'Sun %',
      energy_margin: 'not in bundle',
    },
    dims: [{ name: 'D_cand', kind: 'design', values: ['12.5,0', '-12.5,25'], units: 'grid m (dx,dy)', label: 'candidate' }],
    metrics: { full_sun_12mo: { units: '%', label: 'full', dtype: 'float64', values: [80, 70], provenance: 'synthetic' } },
    missing: { encoding: 'sparse-flat-index', by_metric: { full_sun_12mo: [] } },
    derived: {
      emulator_check: {
        dims: [],
        metrics: { spearman_objective: scalar(0.995, 'rho'), target_rho: scalar(0.99, 'rho'), mae_objective: scalar(0.12, 'pct pts') },
        method: 'Emulator synthetic method.',
        caveat: 'SURROGATE for search only.',
      },
      sobol__position__sun_pct: pos,
      sobol__centre__sun_pct: cen,
    },
    provenance: { inputs: [{ path: 'x', sha256: 'a'.repeat(64) }], command: 'x', code_commit: 'abc' },
    limitations: ['Not a probability.'],
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('WhatMatters bar (Phase 7, display-only)', () => {
  it('copies the stored Shapley / first-order / total shares, with source and label for the traceability scan', () => {
    const cube = validateCube(synth());
    render(<WhatMattersView cube={cube} />);
    const root = screen.getByTestId('what-matters');
    expect(root.getAttribute('data-source')).toBe('scenario cube test-sensitivity-v1 derived sobol__position__sun_pct');
    expect(root.getAttribute('data-label')).toBe('SOURCE-BASED · UNVALIDATED');
    // default set = position; bar widths are the stored Shapley shares, unchanged
    expect(screen.getByTestId('wm-seg-D_pos').style.width).toBe('45.2%');
    expect(screen.getByTestId('wm-seg-S').style.width).toBe('54%');
    expect(screen.getByTestId('wm-seg-T').getAttribute('data-value')).toBe('0.8');
    const row = within(screen.getByTestId('wm-row-D_pos'));
    expect(row.getByText('45.2 %')).toBeTruthy();
    expect(row.getByText('30.0 %')).toBeTruthy();
    expect(row.getByText('62.0 %')).toBeTruthy();
    expect(screen.getByTestId('wm-top').textContent).toContain('S · window start');
    expect(screen.getByTestId('wm-top').textContent).toContain('54.0 %');
    expect(screen.getByTestId('wm-row-energy').textContent).toContain('not in bundle');
    const det = screen.getByTestId('wm-details');
    expect(det.tagName).toBe('DETAILS');
    expect(det.textContent).toContain('Share of spread within this scenario set');
    expect(det.textContent).toContain('Exact functional ANOVA');
    expect(screen.getByTestId('wm-emulator').textContent).toContain('ρ = 0.995');
  });

  it('switching the scenario set shows that set’s stored shares', () => {
    render(<WhatMattersView cube={validateCube(synth())} />);
    fireEvent.change(screen.getByTestId('wm-source'), { target: { value: 'centre' } });
    expect(screen.getByTestId('wm-seg-D_mast').style.width).toBe('9.7%');
    expect(screen.getByTestId('wm-seg-S').style.width).toBe('90%');
    expect(screen.queryByTestId('wm-seg-D_pos')).toBeNull();
    expect(screen.getByTestId('what-matters').getAttribute('data-source')).toContain('sobol__centre__sun_pct');
  });

  it('a set with no spread says so instead of drawing 0 % bars', () => {
    const c = synth();
    const b = c.derived!.sobol__centre__sun_pct;
    for (const k of Object.keys(b.metrics)) if (k.includes('_pct__')) b.metrics[k].values = [null];
    b.metrics.sd.values = [0];
    b.metrics.no_spread = { units: '', label: 'x', dtype: 'bool', values: [true], provenance: 'synthetic' };
    render(<WhatMattersView cube={validateCube(c)} />);
    fireEvent.change(screen.getByTestId('wm-source'), { target: { value: 'centre' } });
    expect(screen.getByTestId('wm-no-spread').textContent).toContain('undefined');
    expect(screen.queryByTestId('wm-bar')).toBeNull();
  });

  it('shows "not in bundle" when the site index has no sensitivity file', async () => {
    const idx = { schema: 'scenario-cube-index-v1', site_id: 'x', label: 'SOURCE-BASED · UNVALIDATED', cubes: [] };
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(idx), { headers: { 'content-type': 'application/json' } })));
    render(<WhatMatters v={{ dataset: { site: { id: 'x' } } } as unknown as View} />);
    await waitFor(() => expect(screen.getByTestId('what-matters-missing').textContent).toContain('not in bundle'));
  });

  it('the committed site files validate and their bars sum to 100 %', () => {
    for (const site of ['site04_roi3', 'site01_roi6']) {
      const p = resolve(__dirname, `../../../data/cubes/${site}/sensitivity.json`);
      if (!existsSync(p)) continue;
      const cube = validateCube(JSON.parse(readFileSync(p, 'utf8')));
      const { unmount } = render(<WhatMattersView cube={cube} />);
      const sum = Array.from(screen.getByTestId('wm-bar').children).reduce((s, el) => s + Number(el.getAttribute('data-value')), 0);
      expect(sum).toBeCloseTo(100, 1);
      unmount();
    }
  });
});
