import { useMemo } from 'react';
import { ridgeBins, ridgeForTarget, ridgeIndexAtBin, type RidgeNow } from '../bundle/evidence';
import type { Ridge } from '../bundle/types';
import { usePolaris } from './store';
import type { View } from './view';

export interface RidgeFocus {
  /** the ridge to highlight everywhere (chart, 3D, tables); null ridge = a single bin without attribution */
  ridge: Ridge | null;
  ridgeIdx: number | null;
  bins: number[];
  /** why it is highlighted: the user picked it, or it is blocking the Sun / Earth at the current sample */
  source: 'selected' | 'sun' | 'earth';
}

/**
 * Ridge-of-Record focus derived from the ONE store: the user's selection wins; otherwise the ridge that the bundle holds
 * responsible for the target blocked right now (Sun first). Lookups only; nothing is computed about terrain.
 */
export function useRidgeFocus(v: View | null): { sun: RidgeNow | null; earth: RidgeNow | null; focus: RidgeFocus | null } {
  const selectedBin = usePolaris((s) => s.selectedBin);
  return useMemo(() => {
    if (!v) return { sun: null, earth: null, focus: null };
    const att = v.dataset.derived?.attribution ?? null;
    const nBins = v.series?.skyline?.azimuthDeg.length ?? att?.perBin?.ridgeIdx.length ?? 0;
    const eph = v.dataset.ephemeris.samples;
    // attribution describes one scenario's skyline (default baseline); never show it under another scenario's series
    const applies = !!att && (!att.scenarioId || att.scenarioId === v.series?.id);
    const now = (k: 'sun' | 'earth') => (applies && v.br.exact !== null ? ridgeForTarget(att, eph, v.series?.samples?.[k], k, v.nearest, nBins) : null);
    const sun = now('sun');
    const earth = now('earth');
    let focus: RidgeFocus | null = null;
    if (selectedBin !== null) {
      const ri = applies ? ridgeIndexAtBin(att, selectedBin) : null;
      focus = { ridge: ri !== null ? att!.ridges[ri] : null, ridgeIdx: ri, bins: ri !== null ? ridgeBins(att, ri) : [selectedBin], source: 'selected' };
    } else {
      for (const [k, r] of [['sun', sun], ['earth', earth]] as const)
        if (r && v[k].visible === false) {
          focus = { ridge: r.ridge, ridgeIdx: r.ridgeIdx, bins: ridgeBins(att, r.ridgeIdx), source: k };
          break;
        }
    }
    return { sun, earth, focus };
  }, [v, selectedBin]);
}

/** Split sorted bin indices into contiguous runs (for drawing spans). */
export function binRuns(bins: number[]): [number, number][] {
  const out: [number, number][] = [];
  for (const b of bins) {
    const last = out[out.length - 1];
    if (last && b === last[1] + 1) last[1] = b;
    else out.push([b, b]);
  }
  return out;
}
