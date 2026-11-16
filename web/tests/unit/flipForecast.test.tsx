import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FlipForecastTable } from '../../src/components/FlipForecastTable';
import type { FlipForecastBlock } from '../../src/bundle/types';
import type { View } from '../../src/store/view';

const row = {
  result_id: 'flip-forecast-site04_roi3-m1-sun-hourly',
  label: 'PILOT' as const,
  row_id: 'sun-hourly',
  scope: 'Hourly Sun-centre visibility',
  case_count: 6740,
  predicted_flips: 241,
  actual_flips: 243,
  true_positive: 240,
  false_positive: 1,
  false_negative: 3,
  true_negative: 6496,
  precision: 0.995851,
  recall: 0.987654,
  precision_display: '99.6 %',
  recall_display: '98.8 %',
  note: 'evaluable',
};

const block: FlipForecastBlock = {
  result_id: 'flip-forecast-site04_roi3-m1-20261114-pilot-v1',
  label: 'PILOT',
  validation_status: 'SOURCE-BASED UNVALIDATED',
  site_id: 'site04_roi3',
  input_bundle_id: 'site04_roi3_2026-11-14_14d_mast1m',
  observer_mast_m: 1,
  clone_count: 20,
  sample_count: 337,
  thresholds: {
    sun_center_visible_pct_min: 70,
    sun_and_earth_center_visible_pct_min: 40,
    source_result_id: 'arrival-slip-site04_roi3-m1-20261114-pilot-v1',
  },
  nominal: { sun_center_visible_pct: 94.362, sun_and_earth_center_visible_pct: 72.107, mission_pass: true },
  ridge_ids_considered: ['ridge-local-rise'],
  forecast_vs_actual: [row, { ...row, result_id: 'flip-forecast-site04_roi3-m1-mission-thresholds', row_id: 'mission-thresholds', scope: 'Mission threshold pass/fail by clone', case_count: 20, predicted_flips: 0, actual_flips: 0, true_positive: 0, false_positive: 0, false_negative: 0, true_negative: 20, precision: null, recall: null, precision_display: 'not evaluable', recall_display: 'not evaluable', note: 'not evaluable: no predicted or actual flips' }],
  per_clone: [],
  method: {
    id: 'nominal-controller-clone-secant-v1',
    caption: 'Bundle method caption.',
    forecast: 'bundle forecast method',
    actual: 'bundle actual method',
    hourly_flip: 'bundle hourly rule',
    mission_flip: 'bundle mission rule',
    metrics: 'Bundle metric rule',
    limitation: 'Bundle limitation',
  },
};

describe('FlipForecastTable', () => {
  it('copies bundle metrics, null displays and result traceability without recomputation', () => {
    const v = { dataset: { derived: { flipForecast: block } } } as unknown as View;
    render(<FlipForecastTable v={v} />);
    const sun = screen.getByTestId('flip-forecast-row-sun-hourly');
    expect(sun.getAttribute('data-result-id')).toBe(row.result_id);
    expect(sun.getAttribute('data-label')).toBe('PILOT');
    expect(within(sun).getByText('99.6 %').getAttribute('data-value')).toBe(String(row.precision));
    expect(within(sun).getByText('98.8 %').getAttribute('data-value')).toBe(String(row.recall));
    const mission = screen.getByTestId('flip-forecast-row-mission-thresholds');
    expect(within(mission).getAllByText('not evaluable')).toHaveLength(2);
    expect(within(mission).getAllByText('not evaluable')[0].getAttribute('data-value')).toBe('');
  });
});
