import { describe, expect, it } from 'vitest';
import { QUALITY_TIERS, qualityNote } from '../../src/simple/quality';

describe('"About this view" quality line (Simple mode, display only)', () => {
  it('names the tier and labels the Sun glow as a display-only camera effect and the flare as intro-only (Sid, 18 Nov 2026), on every tier', () => {
    for (const tier of QUALITY_TIERS) {
      const note = qualityNote(tier);
      expect(note).toContain(`Quality: ${tier}`);
      expect(note).toContain('Sun glow: camera effect, display only; lens flare and starburst are in the opening sequence only');
    }
  });
  it('mentions film grain only on the tiers that draw it', () => {
    expect(qualityNote('high')).toContain('Film grain: camera effect, display only');
    expect(qualityNote('medium')).toContain('Film grain: camera effect, display only');
    expect(qualityNote('low')).not.toContain('Film grain:');
    expect(qualityNote('low')).toContain('grain off');
  });
});
