import { describe, expect, it } from 'vitest';
import { parseUrlState, serializeUrlState } from '../../src/store/urlState';

describe('shareable URL state', () => {
  it('round-trips every field', () => {
    const s = { bundle: 'polaris-x5d-roi-2026-11-14-v2.json', site: 'site04_roi3', t: '2026-11-26T23:00:00Z', sc: 'roi-mast1m', cam: 'ridge' as const, layer: 'shadow' as const };
    const q = serializeUrlState(s);
    expect(q).toContain('t=2026-11-26T23:00:00Z');
    expect(parseUrlState(q).state).toEqual(s);
  });
  it('ignores malformed time, unknown camera and unknown layer, and says so', () => {
    const { state, ignored } = parseUrlState('?t=yesterday&cam=drone&layer=albedo2&site=x');
    expect(state).toEqual({ site: 'x' });
    expect(ignored).toEqual(['t=yesterday', 'cam=drone', 'layer=albedo2']);
  });
  it('writes nothing for an empty state', () => {
    expect(serializeUrlState({})).toBe('');
  });
});
