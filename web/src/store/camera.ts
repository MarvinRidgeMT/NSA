import { create } from 'zustand';

/**
 * Named camera views (Penumbra V3 motion board): the user picks a view, the scene eases to it over ~1.4 s
 * (instant under prefers-reduced-motion). The camera never moves on its own during analysis; a request carries a
 * nonce so picking the same view again re-frames it ("reset").
 */
export type CameraViewId = 'approach' | 'regional' | 'context' | 'mast' | 'ridge' | 'overhead' | 'horizon';

export const CAMERA_VIEWS: { id: CameraViewId; label: string; dem: boolean; panorama: boolean; hint: string }[] = [
  { id: 'approach', label: 'Approach', dem: true, panorama: true, hint: 'oblique view toward the site' },
  { id: 'regional', label: 'Regional terrain', dem: true, panorama: false, hint: 'the whole DEM crop' },
  { id: 'context', label: 'South-pole context', dem: true, panorama: false, hint: 'the 5 m crop inside its 80 m regional surroundings (display context)' },
  { id: 'mast', label: 'Mast-eye', dem: true, panorama: true, hint: 'from the observer, looking toward the Sun' },
  { id: 'ridge', label: 'Ridge of Record', dem: true, panorama: true, hint: 'the ridge controlling the current blockage' },
  { id: 'overhead', label: 'Overhead', dem: true, panorama: true, hint: 'map view, north up' },
  { id: 'horizon', label: 'Horizon inspection', dem: false, panorama: true, hint: 'the angular skyline from just outside' },
];

interface CameraState {
  view: CameraViewId;
  nonce: number;
  request: (v: CameraViewId) => void;
}

export const useCamera = create<CameraState>((set, get) => ({
  view: 'approach',
  nonce: 0,
  request: (view) => set({ view, nonce: get().nonce + 1 }),
}));

export const reducedMotion = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Penumbra camera ease: cubic-bezier(0.65, 0, 0.35, 1) approximated by an in-out cubic. */
export const easeCamera = (k: number) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);
export const CAMERA_MS = 1400;
