import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { parseSidecar, sidecarCurveFor } from '../../src/bundle/certaintySidecar';

const p = resolve(__dirname, '../../public/certainty/sidecar.json');
const has = existsSync(p);

describe('Certainty Height sidecar (batch sweep CSVs → tools/certainty/build_certainty_sidecar.py)', () => {
  it('rejects anything that is not the sidecar format', () => {
    expect(parseSidecar(null)).toBeNull();
    expect(parseSidecar({ format: 'x', sites: {} })).toBeNull();
  });
  it.skipIf(!has)('Site04 ROI3: every point equals the sidecar row; exactly the sampled heights; three distinct heights reported', () => {
    const raw = JSON.parse(readFileSync(p, 'utf8'));
    const sc = parseSidecar(raw)!;
    const s = sidecarCurveFor(sc, 'site04_roi3')!;
    expect(s.status).toBe('SOURCE_BASED_UNVALIDATED');
    expect(s.curve.points.map((q) => q.mastM)).toEqual(raw.sites.site04_roi3.sampled_masts_m);
    for (const row of raw.sites.site04_roi3.certainty_curve) {
      const pt = s.curve.points.find((q) => q.mastM === row.mast_m)!;
      const [k, n] = row.pass.split('/').map(Number);
      expect(pt.passBy![row.metric]).toEqual({ k, n });
      if (row.metric === 'sun_centre_pct') expect([pt.nominal.sunPct, pt.min.sunPct, pt.max.sunPct]).toEqual([row.nominal, row.min, row.max]);
      else expect([pt.min.bothPct, pt.max.bothPct]).toEqual([row.min, row.max]);
    }
    // team requirements (>= 70 %, >= 40 %) are met on every tested map already at the lowest sampled mast …
    expect(s.curve.minTestedFeasibleMastM).toBe(raw.sites.site04_roi3.certainty_height_m.sun_centre_pct);
    // … while the maps only agree (spread <= tolerance) and reach 100 % Sun from a taller mast: different quantities
    expect(s.curve.agreementMastM).toBe(raw.sites.site04_roi3.agreement_mast_m);
    expect(s.allMaps100PctSunMastM).toBe(raw.sites.site04_roi3.all_maps_100pct_sun_mast_m);
    expect(s.curve.agreementMastM).toBeGreaterThan(s.curve.minTestedFeasibleMastM!);
    expect(sidecarCurveFor(sc, 'no_such_site')).toBeNull();
  });
});
