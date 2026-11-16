import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { blockMetric, readDecision6D } from '../../src/bundle/scenarioCubeV2';
import { Decision6D, fmtDelta, fmtVal } from '../../src/components/Decision6D';
import type { View } from '../../src/store/view';

const root = resolve(__dirname, '../../../data/cubes');
const SITES = ['site04_roi3', 'site01_roi6'].filter((s) => existsSync(resolve(root, s, 'decision6d.json')));
const raw = (s: string) => JSON.parse(readFileSync(resolve(root, s, 'decision6d.json'), 'utf8'));
const view = (id: string) => ({ dataset: { site: { id } } }) as unknown as View;

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('decision6d reader (display only)', () => {
  it.each(SITES)('%s: reads, checks question metadata and every block', (s) => {
    const d = readDecision6D(raw(s));
    expect(d.cube.source_schema).toBe('scenario-cube-v2');
    expect(d.cube.dims[0].role).toBe('context');
    expect(d.questions.map((q) => q.id)).toEqual(d.cube.dims[0].values);
    for (const [qi, q] of d.questions.entries()) {
      const n = (blockMetric(d.cube, `q__${q.id}__by_choice`, 'worst_over_x') ?? []).length;
      const r = d.cube.metrics.robust_choice_index.values[qi] as number;
      expect(r).toBeGreaterThanOrEqual(0);
      expect(r).toBeLessThan(n);
    }
  });

  it('refuses a v1 cube, a non-context Q, and a missing block', () => {
    const c = raw(SITES[0]);
    expect(() => readDecision6D({ ...c, schema: 'scenario-cube-v1' })).toThrow();
    const notCtx = structuredClone(c);
    notCtx.dims[0].role = 'decision';
    expect(() => readDecision6D(notCtx)).toThrow(/context/);
    const noBlock = structuredClone(c);
    delete noBlock.derived[`q__${JSON.parse(c.dims[0].note)[0].id}__voi`];
    expect(() => readDecision6D(noBlock)).toThrow(/missing/);
  });

  it('no count is turned into a probability', () => {
    for (const s of SITES) {
      const txt = JSON.stringify(raw(s)).toLowerCase();
      expect(txt).not.toContain('probability of success');
      expect(txt).toContain('not a probability');
    }
  });
});

describe('Decision6D panel', () => {
  it.each(SITES)('%s: robust choice, nominal choice and regret are the stored cells', async (s) => {
    const c = raw(s);
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(c), { headers: { 'content-type': 'application/json' } })));
    render(<Decision6D v={view(s)} />);
    const d = readDecision6D(c);
    for (const [qi, q] of d.questions.entries()) {
      fireEvent.change(await screen.findByTestId('d6-question'), { target: { value: String(qi) } });
      const L = d.cube.derived![`q__${q.id}__by_choice`].dims[0] as { value_labels: string[] };
      const rob = d.cube.metrics.robust_choice_index.values[qi] as number;
      const nom = d.cube.metrics.nominal_choice_index.values[qi] as number;
      await waitFor(() => expect(screen.getByTestId('d6-robust').getAttribute('data-index')).toBe(String(rob)));
      expect(screen.getByTestId('d6-robust').textContent).toContain(L.value_labels[rob]);
      expect(screen.getByTestId('d6-nominal').textContent).toContain(L.value_labels[nom]);
      const reg = blockMetric(d.cube, `q__${q.id}__summary`, 'max_regret_nominal_choice')![0] as number;
      expect(screen.getByTestId('d6-regret').textContent).toContain(fmtDelta(reg, q.units));
      expect(screen.getByTestId('d6-kchange').textContent).toMatch(/of 21 maps \(a count, not a probability\)/);
    }
    expect(screen.getByTestId('d6-not-prob').textContent).toBe('k of N maps is not a probability.');
    expect(document.body.textContent?.toLowerCase()).not.toContain('probability of success');
  });

  it('shows "not computed" when the file is absent', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('<html></html>', { status: 200, headers: { 'content-type': 'text/html' } })));
    render(<Decision6D v={view('nowhere')} />);
    expect(await screen.findByTestId('decision6d-missing')).toBeTruthy();
  });

  it('formats units without inventing values', () => {
    expect(fmtVal(78.6423, '%')).toBe('78.64 %');
    expect(fmtVal(0.45, 'deg')).toBe('0.45°');
    expect(fmtVal(12, 'h')).toBe('12 h');
    expect(fmtVal(null, '%')).toBe('—');
    expect(fmtVal(true, '%')).toBe('—');
    expect(fmtDelta(3.1, '%')).toBe('3.10 pct points');
    expect(fmtDelta(0.25, 'deg')).toBe('0.25°');
  });
});
