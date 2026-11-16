import { create } from 'zustand';
import type { VisualLayersDoc } from '../bundle/visualLayers';

/**
 * Display state of the terrain surface. Independent of time, site and scenario: changing it never changes a number.
 * `regolith` = neutral shading (no albedo data); `albedo` = a registered visual layer where one covers the crop.
 * The rest are debug views of the DEM the mesh is built from.
 */
export type SurfaceLayerId = 'regolith' | 'albedo' | 'elevation' | 'slope' | 'normal' | 'coverage' | 'shadow';

export const SURFACE_LAYERS: { id: SurfaceLayerId; label: string; chip: string }[] = [
  { id: 'regolith', label: 'Neutral regolith', chip: 'NEUTRAL REGOLITH · VISUAL shading, no albedo data' },
  { id: 'albedo', label: 'LROC NAC average image', chip: 'LROC NAC AVG · VISUAL' },
  { id: 'elevation', label: 'Elevation', chip: 'ELEVATION · from the DEM values (metres), 10 m contours' },
  { id: 'slope', label: 'Slope', chip: 'SLOPE · derived from the DEM mesh normals (0–25°)' },
  { id: 'normal', label: 'Normals', chip: 'NORMALS · derived from the DEM mesh (grid axes)' },
  { id: 'coverage', label: 'Source coverage', chip: 'SOURCE COVERAGE · 5 m crop, 20 m ring (when present), 80 m context, image footprint' },
  { id: 'shadow', label: 'Sun shadow (display model)', chip: 'SUN SHADOW · display model from the horizon maps, not the solver' },
];

interface SurfaceState {
  layer: SurfaceLayerId;
  /** visual-layers file (validated) or null when absent */
  visualLayers: VisualLayersDoc | null;
  /** what the scene actually has for the current dataset; set by the scene, read by the UI */
  contextLoaded: boolean;
  albedoCoverage: number; // 0..1 of the current 5 m crop covered by a registered image
  /** show the global Moon (visual context) instead of the terrain stage */
  globe: boolean;
  /** draw the NASA GSFC shape-from-shading display surface where the pack has one (display only; the solver keeps the LOLA crop) */
  detail: boolean;
  /** set by the scene: fraction of the current crop the SfS display surface covers (0 = none) and how far it sits from the solver crop */
  detailCoverage: number;
  detailRmsM: number;
  setDetail: (d: boolean) => void;
  setDetailFacts: (f: { detailCoverage: number; detailRmsM: number }) => void;
  setGlobe: (g: boolean) => void;
  setLayer: (l: SurfaceLayerId) => void;
  setVisualLayers: (d: VisualLayersDoc | null) => void;
  setSceneFacts: (f: { contextLoaded: boolean; albedoCoverage: number }) => void;
}

export const useSurface = create<SurfaceState>((set) => ({
  layer: 'regolith',
  visualLayers: null,
  contextLoaded: false,
  albedoCoverage: 0,
  globe: false,
  detail: true,
  detailCoverage: 0,
  detailRmsM: 0,
  setDetail: (detail) => set({ detail }),
  setDetailFacts: (f) => set(f),
  setGlobe: (globe) => set({ globe }),
  setLayer: (layer) => set({ layer }),
  setVisualLayers: (visualLayers) => set({ visualLayers }),
  setSceneFacts: (f) => set(f),
}));
