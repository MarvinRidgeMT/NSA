import { create } from 'zustand';

/**
 * Near-field LOD layer (5D Phase 9.4): display state only. Turning it on swaps the drawn terrain for the streamed
 * ±7 km PGDA 78 quadtree; no number, state or bundle value changes. Opt-in (off by default), or `?lod=1` in the URL.
 */
export interface LodStats { drawn: number; loaded: number; pending: number; finestM: number | null; coarsestM: number | null; triangles: number }
interface LodState {
  on: boolean;
  stats: LodStats | null;
  setOn: (on: boolean) => void;
  setStats: (s: LodStats | null) => void;
}

const fromUrl = () => {
  try {
    return typeof location !== 'undefined' && new URLSearchParams(location.search).get('lod') === '1';
  } catch {
    return false;
  }
};

export const useLod = create<LodState>((set) => ({
  on: fromUrl(),
  stats: null,
  setOn: (on) => set({ on }),
  setStats: (stats) => set({ stats }),
}));
