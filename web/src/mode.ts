/**
 * Simple / Expert front door (16 Nov). Simple mode is the default at a bare "/"; Expert mode is the full app, unchanged.
 * Precedence: ?mode= in the URL, then an Expert route in the hash, then the remembered choice, then Simple.
 * The remembered choice is written only when the user presses a mode button. Display choice only: no number changes.
 */
export type Mode = 'simple' | 'expert';

export const MODE_KEY = 'polaris-x.mode';
const EXPERT_HASHES = new Set(['sky', 'decision', 'evidence', 'story']);

function remembered(): Mode | null {
  try {
    const m = window.localStorage.getItem(MODE_KEY);
    return m === 'simple' || m === 'expert' ? m : null;
  } catch {
    return null;
  }
}

export function resolveMode(search: string, hash: string): Mode {
  const q = new URLSearchParams(search).get('mode');
  if (q === 'expert' || q === 'simple') return q;
  if (EXPERT_HASHES.has(hash.replace(/^#/, ''))) return 'expert';
  return remembered() ?? 'simple';
}

export function rememberMode(m: Mode): void {
  try {
    window.localStorage.setItem(MODE_KEY, m);
  } catch {
    /* storage blocked (private window, tests): the URL still carries the choice */
  }
}

/** Switch modes with a fresh page load, so each mode boots exactly as it does on its own. */
export function switchMode(m: Mode): void {
  rememberMode(m);
  window.location.assign(m === 'expert' ? `${location.pathname}?mode=expert` : location.pathname);
}
