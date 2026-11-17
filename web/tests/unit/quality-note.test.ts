import { describe, expect, it } from 'vitest';
import { QUALITY_TIERS, qualityNote } from '../../src/simple/quality';

describe('"About this view" quality line (Simple mode, display only)', () => {
  it('names the tier and labels the Sun glow and flare as a display-only camera effect, on every tier', () => {
    for (const tier of QUALITY_TIERS) {
      const note = qualityNote(tier);
      expect(note).toContain(`Quality: ${tier}`);
      expect(note).toContain('Sun glow and flare: camera effect, display only');
    }
  });
  it('mentions film grain only on the tiers that draw it', () => {
    expect(qualityNote('high')).toContain('Film grain: camera effect, display only');
    expect(qualityNote('medium')).toContain('Film grain: camera effect, display only');
    expect(qualityNote('low')).not.toContain('Film grain:');
    expect(qualityNote('low')).toContain('grain off');
  });
});
