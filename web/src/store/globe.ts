import { create } from 'zustand';
import { GLOBE_LAYER_IDS, type GlobeLayerId } from '../globe/layers';

/**
 * Whole-Moon globe display state (v2 T2). Display only: the layer and opacity change pixels, never a number; the picked
 * point is where the user clicked (or typed), used to look up the nearest precomputed any-site row.
 */
export type GlobeLayerChoice = GlobeLayerId | 'none';
export const GLOBE_LAYER_CHOICES: readonly GlobeLayerChoice[] = ['none', ...GLOBE_LAYER_IDS];

export interface PickedPoint {
  lat: number;
  lon: number;
  via: 'click' | 'input' | 'marker';
}

interface GlobeState {
  layer: GlobeLayerChoice;
  opacity: number; // 0..1
  picked: PickedPoint | null;
  /** which tab of the globe sheet is open (the sheet is tabbed at <= 1023 px, side-by-side above) */
  tab: 'site' | 'layers' | 'query';
  /** nearest precomputed any-site row to the picked point (drawn as a second marker) */
  nearest: { lat: number; lon: number; name: string } | null;
  setNearest: (n: GlobeState['nearest']) => void;
  setLayer: (l: GlobeLayerChoice) => void;
  setOpacity: (o: number) => void;
  pick: (p: PickedPoint | null) => void;
  setTab: (t: GlobeState['tab']) => void;
}

export const useGlobe = create<GlobeState>((set) => ({
  layer: 'none',
  opacity: 0.75,
  picked: null,
  tab: 'site',
  nearest: null,
  setNearest: (nearest) => set({ nearest }),
  setLayer: (layer) => set({ layer }),
  setOpacity: (opacity) => set({ opacity: Math.max(0, Math.min(1, opacity)) }),
  pick: (picked) => set(picked ? { picked, tab: 'query' } : { picked }),
  setTab: (tab) => set({ tab }),
}));

export const isGlobeLayerChoice = (s: string): s is GlobeLayerChoice => (GLOBE_LAYER_CHOICES as readonly string[]).includes(s);
