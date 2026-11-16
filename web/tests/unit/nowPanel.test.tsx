import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { NowPanel } from '../../src/live/NowPanel';
import { _resetFeedCache, maskAt, parseHorizonsAzEl, type LiveSite } from '../../src/live/feeds';

const site: LiveSite = {
  id: 'site04_roi3',
  lat_deg: -89.78,
  lon_deg_east: -156.32,
  height_m: 1737.5,
  skyline: { azimuth_deg: [0, 90, 180, 270], elevation_deg: [1, 2, 3, 4] },
};
const now = () => new Date('2026-11-16T04:00:00Z');
const json = (v: unknown) => Promise.resolve(new Response(JSON.stringify(v), { status: 200 }));

const okFetch = ((url: string) => {
  if (url.includes('swpc'))
    return json([
      { time_tag: '2026-11-16T03:50:00Z', energy: '>=10 MeV', flux: 0.4 },
      { time_tag: '2026-11-16T03:55:00Z', energy: '>=10 MeV', flux: 12.5 },
      { time_tag: '2026-11-16T03:55:00Z', energy: '>=100 MeV', flux: 0.1 },
    ]);
  if (url.includes('DONKI'))
    return json([
      { messageType: 'CME', messageIssueTime: '2026-11-14T10:00Z', messageURL: 'https://x/cme' },
      { messageType: 'FLR', messageIssueTime: '2026-11-14T11:00Z', messageURL: 'https://x/flr' },
    ]);
  // Horizons: simulate a CORS block (browsers surface it as TypeError)
  return Promise.reject(new TypeError('Failed to fetch'));
}) as typeof fetch;

const downFetch = (() => Promise.reject(new Error('HTTP 503'))) as unknown as typeof fetch;

describe('NowPanel (LIVE · CONTEXT)', () => {
  beforeEach(() => _resetFeedCache());

  it('renders live rows with fetch times, storm yes at >=10 pfu, and the CORS fallback', async () => {
    render(<NowPanel site={site} fetchImpl={okFetch} now={now} />);
    expect(screen.getByRole('heading').textContent).toBe('LIVE · CONTEXT, not part of the results');
    await waitFor(() => expect(screen.getByText(/radiation storm: yes/)).toBeTruthy());
    expect(screen.getByText(/12.5 pfu/)).toBeTruthy();
    expect(screen.getByText('CME')).toBeTruthy();
    expect(screen.queryByText('FLR')).toBeNull();
    await waitFor(() => expect(screen.getByText('needs the local solver proxy')).toBeTruthy());
    expect(screen.getAllByText(/fetched 2026-11-16T04:00:00.000Z/).length).toBe(2);
  });

  it('shows feed unavailable when every feed fails', async () => {
    render(<NowPanel site={null} fetchImpl={downFetch} now={now} />);
    await waitFor(() => expect(screen.getAllByText(/feed unavailable/).length).toBe(3));
  });

  it('marks the last good value stale after a failure', async () => {
    const a = render(<NowPanel site={null} fetchImpl={okFetch} now={now} />);
    await waitFor(() => expect(screen.getByText(/radiation storm: yes/)).toBeTruthy());
    a.unmount();
    render(<NowPanel site={null} fetchImpl={downFetch} now={now} />);
    await waitFor(() => expect(screen.getAllByTestId('stale').length).toBe(2));
  });

  it('parses Horizons CSV and interpolates the mask', () => {
    const r = '...\n$$SOE\n 2026-Nov-16 04:00, , ,  282.93178,   1.605823,\n$$EOE\n';
    expect(parseHorizonsAzEl(r)).toEqual({ az: 282.93178, el: 1.605823 });
    expect(maskAt(site.skyline, 45)).toBeCloseTo(1.5);
    expect(maskAt(site.skyline, 315)).toBeCloseTo(2.5);
  });
});
