import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ArrivalSlipStrip } from '../../src/components/ArrivalSlipStrip';
import type { ArrivalSlipBlock } from '../../src/bundle/types';
import type { View } from '../../src/store/view';

const point = {
  result_id: 'arrival-slip-site04-roi3-m1-000h',
  label: 'PILOT' as const,
  slip_h: 0,
  window_start_utc: '2026-11-14T00:00:00.000Z',
  window_stop_utc: '2026-11-28T00:00:00.000Z',
  sample_count: 337,
  nominal: {
    sun_center_visible_pct: 94.362,
    sun_and_earth_center_visible_pct: 72.107,
    sun_pass: true,
    sun_and_earth_pass: true,
    joint_pass: true,
  },
  clones: {
    count: 20,
    sun_center_visible_pct_min: 87.537,
    sun_center_visible_pct_max: 97.329,
    sun_and_earth_center_visible_pct_min: 64.392,
    sun_and_earth_center_visible_pct_max: 74.481,
    sun_pass_count: 20,
    sun_and_earth_pass_count: 20,
    joint_pass_count: 20,
    pass_denominator: 20,
    joint_pass_pct: 100,
    pass_band: 'all' as const,
  },
};

const block: ArrivalSlipBlock = {
  result_id: 'arrival-slip-site04-roi3-m1-20261114-pilot-v1',
  label: 'PILOT',
  validation_status: 'SOURCE-BASED UNVALIDATED',
  site_id: 'site04_roi3',
  input_bundle_id: 'site04_roi3_2026-11-14_14d_mast1m',
  observer_mast_m: 1,
  thresholds: {
    sun_center_visible_pct_min: 70,
    sun_and_earth_center_visible_pct_min: 40,
    joint_rule: 'a clone passes only when both thresholds pass',
  },
  slip_hours: [0],
  points: [point],
  method: {
    mission_window: 'from bundle',
    visibility_percentage: 'from bundle',
    terrain: 'from bundle',
    ephemeris: 'from bundle',
    uncertainty: 'from bundle',
    limitation: 'from bundle',
  },
};

describe('ArrivalSlipStrip', () => {
  it('renders only bundle fields and keeps result traceability', () => {
    const v = { dataset: { derived: { arrivalSlip: block } } } as unknown as View;
    render(<ArrivalSlipStrip v={v} />);
    const row = screen.getByTestId('arrival-slip-row-0');
    expect(row.getAttribute('data-result-id')).toBe(point.result_id);
    expect(row.getAttribute('data-label')).toBe('PILOT');
    expect(within(row).getByText('94.362').getAttribute('data-value')).toBe('94.362');
    expect(within(row).getByText('20/20').getAttribute('data-value')).toBe('20');
    expect(screen.getByTestId('arrival-slip-cell-0').getAttribute('data-pass-pct')).toBe('100');
  });
});
