import { binForAzimuth, ridgeForTarget } from './evidence';
import type { Ridge } from './types';
import type { View } from '../store/view';

/** Attribution describes one scenario's skyline: never apply it to another scenario's series (same rule as useRidgeFocus). */
const applies = (v: View) => {
  const att = v.dataset.derived?.attribution;
  return !!att && (!att.scenarioId || att.scenarioId === v.series?.id);
};

/**
 * Lookups only: the first bundle sample at which the bundle marks `target` blocked AND attributes the block to `ridge`
 * (nearest skyline bin -> per_bin.ridge_idx), and the contiguous run around it. Nothing about terrain is computed.
 */
export function firstBlockedRun(v: View, ridge: Ridge, target: 'sun' | 'earth'): { i0: number; i1: number } | null {
  const att = v.dataset.derived?.attribution;
  const ser = v.series?.samples?.[target];
  const nBins = v.series?.skyline?.azimuthDeg.length ?? att?.perBin?.ridgeIdx.length ?? 0;
  if (!att?.perBin || !ser || !nBins || !applies(v)) return null;
  const idx = att.ridges.indexOf(ridge);
  if (idx < 0) return null;
  const eph = v.dataset.ephemeris.samples;
  for (let i = 0; i < v.times.length; i++) {
    if (ser.visible[i] !== false) continue;
    if (att.perBin.ridgeIdx[binForAzimuth(eph[i][target].az, nBins)] !== idx) continue;
    const r = ridgeForTarget(att, eph, ser, target, i, nBins);
    return r?.run ?? { i0: i, i1: i };
  }
  return null;
}

/** Ridges the bundle marks "of record" (caused at least one loss), with the target they block. */
export function ridgesOfRecord(v: View): { ridge: Ridge; target: 'sun' | 'earth' }[] {
  const att = v.dataset.derived?.attribution;
  if (!att || !applies(v)) return [];
  const out: { ridge: Ridge; target: 'sun' | 'earth' }[] = [];
  for (const r of att.ridges) {
    if (r.hours.sun.lost > 0) out.push({ ridge: r, target: 'sun' });
    else if (r.hours.earth.lost > 0) out.push({ ridge: r, target: 'earth' });
  }
  // Sun first (the mast decision), then by hours lost
  return out.sort((a, b) => (a.target === b.target ? b.ridge.hours[b.target].lost - a.ridge.hours[a.target].lost : a.target === 'sun' ? -1 : 1));
}
