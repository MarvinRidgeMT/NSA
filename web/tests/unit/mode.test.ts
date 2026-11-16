import { afterEach, describe, expect, it } from 'vitest';
import { MODE_KEY, rememberMode, resolveMode } from '../../src/mode';

describe('Simple / Expert mode resolution', () => {
  afterEach(() => localStorage.clear());
  it('bare "/" opens Simple mode', () => expect(resolveMode('', '')).toBe('simple'));
  it('?mode=expert and Expert routes open Expert mode', () => {
    expect(resolveMode('?mode=expert', '')).toBe('expert');
    for (const h of ['#sky', '#decision', '#evidence']) expect(resolveMode('', h)).toBe('expert');
    expect(resolveMode('?bundle=x.json', '#sky')).toBe('expert');
  });
  it('remembers the choice, and the URL wins over it', () => {
    rememberMode('expert');
    expect(localStorage.getItem(MODE_KEY)).toBe('expert');
    expect(resolveMode('', '')).toBe('expert');
    expect(resolveMode('?mode=simple', '')).toBe('simple');
    rememberMode('simple');
    expect(resolveMode('', '')).toBe('simple');
    expect(resolveMode('', '#evidence')).toBe('expert');
  });
  it('ignores a garbage stored value', () => {
    localStorage.setItem(MODE_KEY, 'nonsense');
    expect(resolveMode('', '')).toBe('simple');
  });
});
