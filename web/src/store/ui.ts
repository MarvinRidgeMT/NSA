import { create } from 'zustand';
import type { CameraViewId } from './camera';

/**
 * Presentation-only UI state (Penumbra Apex): never feeds a number.
 *  - mastPick: the mast height chosen in the Certainty Height instrument (a SAMPLED batch height); null = follow the bundle series
 *  - trueLight: light the terrain from the true Sun elevation instead of the readable display clamp (>= 0.5 deg)
 *  - returnTo: camera view + sample to go back to after a Ridge of Record inspection
 *  - run: a sample interval to outline on the Margin Ribbon (the obstruction being inspected)
 *  - guide: current step of the guided demonstration (null = closed)
 */
interface UiState {
  mastPick: number | null;
  trueLight: boolean;
  returnTo: { view: CameraViewId; sample: number } | null;
  run: { i0: number; i1: number; target: 'sun' | 'earth' } | null;
  guide: number | null;
  set: (p: Partial<Omit<UiState, 'set'>>) => void;
}
export const useUi = create<UiState>((set) => ({ mastPick: null, trueLight: false, returnTo: null, run: null, guide: null, set: (p) => set(p) }));
