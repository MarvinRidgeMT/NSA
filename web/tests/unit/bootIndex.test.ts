import { describe, expect, it } from 'vitest';
import { IndexError, parseIndex } from '../../src/bundle/bootIndex';

const U = 'http://127.0.0.1:4173/bundles/index.json';
const problem = (f: () => unknown) => {
  try {
    f();
  } catch (e) {
    return e instanceof IndexError ? e.problem : 'other';
  }
  return 'none';
};

describe('parseIndex (cold launch, Final Apex P1)', () => {
  it('accepts a valid index and keeps every entry', () => {
    const t = JSON.stringify({ bundles: [{ file: 'a.json', origin: 'x', status: 'DEMO_ONLY', label: 'A', sha256: '0', bytes: 1 }] });
    expect(parseIndex(t, 'application/json', U).map((b) => b.file)).toEqual(['a.json']);
  });
  it('an HTML single-page fallback is reported as the wrong folder, not as a JSON syntax error', () => {
    expect(problem(() => parseIndex('<!DOCTYPE html><html>', 'text/html', U))).toBe('not-json');
    expect(problem(() => parseIndex('<html>', null, U))).toBe('not-json');
  });
  it('malformed JSON, a missing list, unsafe names and an empty list each have their own problem code', () => {
    expect(problem(() => parseIndex('{"bundles": [', 'application/json', U))).toBe('bad-json');
    expect(problem(() => parseIndex('{"files": []}', 'application/json', U))).toBe('bad-shape');
    expect(problem(() => parseIndex('{"bundles": [{"file": "../x.json"}]}', 'application/json', U))).toBe('bad-shape');
    expect(problem(() => parseIndex('{"bundles": []}', 'application/json', U))).toBe('empty');
  });
  it('the empty-index message never offers a demo substitute', () => {
    try {
      parseIndex('{"bundles": []}', 'application/json', U);
    } catch (e) {
      expect((e as Error).message).not.toMatch(/demo/i);
    }
  });
});
