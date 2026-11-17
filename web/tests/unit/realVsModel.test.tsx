import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { RealVsModelView, validateIndex, type RealVsModelIndex } from '../../src/components/RealVsModel';

afterEach(cleanup);

const index: RealVsModelIndex = {
  schema: 'polaris-render-vs-real-index-v1',
  label: 'SOURCE-BASED · UNVALIDATED · dev (training) split only',
  protocol: 'docs/v2/RENDER_VS_REAL_PROTOCOL.md + A1–A3',
  credit: 'NASA/GSFC/Arizona State University',
  generatedUtc: '2026-11-16T00:00:00Z',
  rows: [
    { id: 'MB__site01_roi6', productId: 'MB', site: 'site01_roi6', product: 'pgda78_5m', photometry: 'hapke', iouShadow: 0.5,
      edgeMedianM: 12.25, ssim: 0.4, wasserstein1: 0.3, regOffsetM: 40, sunElDeg: 1.2, startUtc: '2010-01-01T00:00:00Z',
      image: 'MB__site01_roi6.png', resultId: 'scores.jsonl:MB__site01_roi6' },
    { id: 'MA__site04_roi3', productId: 'MA', site: 'site04_roi3', product: 'pgda78_5m', photometry: 'hapke', iouShadow: 0.9,
      edgeMedianM: 5.04, ssim: null, wasserstein1: 0.2, regOffsetM: 10, sunElDeg: -0.3, startUtc: '2011-06-12T00:00:00Z',
      image: 'MA__site04_roi3.png', resultId: 'scores.jsonl:MA__site04_roi3' },
  ],
};

describe('RealVsModel', () => {
  it('shows the selected row with traceability and labels, sorted by id', () => {
    render(<RealVsModelView index={index} base="./render_vs_real/" />);
    expect(screen.getByTestId('rvm-label').textContent).toMatch(/SOURCE-BASED/);
    expect(screen.getByTestId('rvm-iou').textContent).toBe('0.900');
    expect(screen.getByTestId('rvm-edge').textContent).toBe('5.0 m');
    expect(screen.getByTestId('rvm-ssim').textContent).toBe('—');
    expect(screen.getByTestId('rvm-image').getAttribute('src')).toBe('./render_vs_real/MA__site04_roi3.png');
    const dl = screen.getByTestId('rvm-iou').closest('dl')!;
    expect(dl.getAttribute('data-result-id')).toBe('scores.jsonl:MA__site04_roi3');
    expect(dl.getAttribute('data-source')).toMatch(/scores\.jsonl$/);
    fireEvent.change(screen.getByTestId('rvm-select'), { target: { value: '1' } });
    expect(screen.getByTestId('rvm-iou').textContent).toBe('0.500');
  });

  it('rejects an index without the dev/SOURCE-BASED label', () => {
    expect(() => validateIndex({ ...index, label: 'VALIDATED' })).toThrow();
    expect(() => validateIndex({ schema: 'x', rows: [] })).toThrow();
    expect(validateIndex(index).rows).toHaveLength(2);
  });
});
