import { useMemo } from 'react';
import { ridgeBins, ridgeForTarget, ridgeIndexAtBin, type RidgeNow } from '../bundle/evidence';
import type { Ridge } from '../bundle/types';
import { usePolaris } from './store';
import type { View } from './view';
import { useUi } from './ui';
import type { Dataset } from '../bundle/types';

/**
 * The scenario whose skyline a dataset's attribution describes: the one it names, else the scenario called `baseline`
 * (bundle/types.ts: "default = baseline"). Undefined when it names none and the bundle has no `baseline` scenario: then
 * it cannot be said which series the ridges belong to, and it is held to none.
 */
export function attributionScenarioId(ds: Dataset): string | undefined {
  const d = ds.derived;
  if (!d?.attribution) return undefined;
  return d.attribution.scenarioId ?? d.scenarios.find((x) => x.id === 'baseline')?.id;
}
/** True when the attribution is known to describe the series on screen. */
export function attributionApplies(ds: Dataset, seriesId: string | undefined): boolean {
  const id = attributionScenarioId(ds);
  return id !== undefined && id === seriesId;
}

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
  const strict = useUi((s) => s.attributionStrict);
  return useMemo(() => {
    if (!v) return { sun: null, earth: null, focus: null };
    const att = v.dataset.derived?.attribution ?? null;
    const nBins = v.series?.skyline?.azimuthDeg.length ?? att?.perBin?.ridgeIdx.length ?? 0;
    const eph = v.dataset.ephemeris.samples;
    // attribution describes one scenario's skyline (default baseline); never show it under another scenario's series
    // Simple mode (S12) reads an unnamed attribution as the baseline's; Expert keeps the rule it was submitted with
    const applies = !!att && (strict ? attributionApplies(v.dataset, v.series?.id) : !att.scenarioId || att.scenarioId === v.series?.id);
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
  }, [v, selectedBin, strict]);
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
