import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { validateBundle } from '../../src/bundle/validate';

// Regression (15 Nov 2026): science/certainty.py writes certainty_curve[].pass as {requirement: "k/N"}. The validator only
// accepted a string, so the whole ROI viewer export was refused and the Explore/Decision views lost their ROI datasets.
const roi = resolve(__dirname, '../../../data/viewer/polaris-x5d-roi-2026-11-14-v2.json');

describe('certainty_curve pass counts', () => {
  it('the committed ROI viewer export (per-requirement pass objects) validates', () => {
    const raw = JSON.parse(readFileSync(roi, 'utf8'));
    const curve = raw.datasets[0].derived.certainty_curve;
    expect(Array.isArray(curve) && typeof curve[0].pass).toBe('object');
    expect(() => validateBundle(raw)).not.toThrow();
  });

  it('still refuses a per-requirement count with k > N', () => {
    const raw = JSON.parse(readFileSync(roi, 'utf8'));
    const row = raw.datasets[0].derived.certainty_curve[0];
    const key = Object.keys(row.pass)[0];
    row.pass[key] = `${row.n_clones + 1}/${row.n_clones}`;
    expect(() => validateBundle(raw)).toThrow(/must be "k\/N"/);
  });
});
