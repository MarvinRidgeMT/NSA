import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * E5 (15 Nov 2026): the Decision Lab (cloud batch, web/public/lab/viewer_data.json, pinned by SHA-256) and the main
 * viewer (repo bundles + certainty sidecar) must agree on the 14-day demo window at a 1 m mast.
 *
 * Keys (inspected, not guessed):
 *   Lab:     sites.<Site04_ROI3|Site01_ROI6>.demo.nom.{sun,both,gap} and .demo.cl.sun (20 clones)
 *   Bundle:  metrics.sun_center_visible_pct_hourly_samples, metrics.sun_and_earth_center_visible_pct_hourly_samples,
 *            samples[].sun.center_visible (longest run of hidden hourly samples = the Lab's "gap" in hours)
 *   Sidecar: sites.<id>.certainty_curve row {mast_m: 1, metric: 'sun_centre_pct'}.{min,max} (float64 rerun CSV)
 * The Lab rounds to 0.01, so the tolerance is 0.01 pts. Neither file is changed by this test.
 */
const root = resolve(__dirname, '../../..');
const json = (p: string) => JSON.parse(readFileSync(resolve(root, p), 'utf8'));
const lab = json('web/public/lab/viewer_data.json');
const sidecar = json('web/public/certainty/sidecar.json');
const TOL = 0.01;

type Sample = { sun: { center_visible: boolean } };
const longestHiddenRun = (samples: Sample[]) => {
  let best = 0;
  let run = 0;
  for (const s of samples) {
    run = s.sun.center_visible ? 0 : run + 1;
    best = Math.max(best, run);
  }
  return best;
};

const cases = [
  { lab: 'Site04_ROI3', id: 'site04_roi3', expected: { sun: 94.36, both: 72.11, gap: 19, cloneMin: 87.54, cloneMax: 97.33 } },
  { lab: 'Site01_ROI6', id: 'site01_roi6', expected: { sun: 100.0, both: 81.6, gap: 0, cloneMin: 100.0, cloneMax: 100.0 } },
];

describe('Decision Lab ↔ repo bundle parity (demo window 14–28 Nov 2026, 1 m mast)', () => {
  it('Lab index.html is the pinned build', () => {
    const pin = readFileSync(resolve(root, 'web/public/lab/SHA256.txt'), 'utf8');
    expect(pin).toContain('d12e0896f70c34dc389e89a0b47847ad7b569aa95e7dbb6c75c788bcbe4d36dc');
  });

  for (const c of cases) {
    describe(c.id, () => {
      const L = lab.sites[c.lab].demo;
      const b = json(`data/bundles/${c.id}_2026-11-14_14d_mast1m.json`);
      const row = sidecar.sites[c.id].certainty_curve.find((r: { mast_m: number; metric: string }) => r.mast_m === 1 && r.metric === 'sun_centre_pct');

      it('window is the same', () => {
        expect(L.start).toBe('2026-Nov-14 00:00');
        expect(L.end).toBe('2026-Nov-28 00:00');
        expect(b.metrics.window_utc).toEqual(['2026-11-14T00:00:00.000Z', '2026-11-28T00:00:00.000Z']);
      });
      it('Sun % agrees (Lab vs bundle hourly samples) and equals the stated value', () => {
        expect(Math.abs(L.nom.sun - c.expected.sun)).toBeLessThanOrEqual(TOL);
        expect(Math.abs(L.nom.sun - b.metrics.sun_center_visible_pct_hourly_samples)).toBeLessThanOrEqual(TOL);
      });
      it('Sun+Earth % agrees', () => {
        expect(Math.abs(L.nom.both - c.expected.both)).toBeLessThanOrEqual(TOL);
        expect(Math.abs(L.nom.both - b.metrics.sun_and_earth_center_visible_pct_hourly_samples)).toBeLessThanOrEqual(TOL);
      });
      it('longest Sun gap (hourly samples) agrees', () => {
        expect(L.nom.gap).toBe(c.expected.gap);
        expect(longestHiddenRun(b.samples)).toBe(L.nom.gap);
      });
      it('clone range agrees (Lab clones vs float64 certainty sidecar)', () => {
        const lo = Math.min(...L.cl.sun);
        const hi = Math.max(...L.cl.sun);
        expect(L.cl.sun).toHaveLength(20);
        expect(Math.abs(lo - c.expected.cloneMin)).toBeLessThanOrEqual(TOL);
        expect(Math.abs(hi - c.expected.cloneMax)).toBeLessThanOrEqual(TOL);
        expect(Math.abs(lo - row.min)).toBeLessThanOrEqual(TOL);
        expect(Math.abs(hi - row.max)).toBeLessThanOrEqual(TOL);
        expect(Math.abs(L.nom.sun - row.nominal)).toBeLessThanOrEqual(TOL);
      });
    });
  }
});
