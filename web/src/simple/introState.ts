import { create } from 'zustand';

/**
 * Opening sequence (S3): what the intro's parts share. Display only.
 *
 * `useMoonLoad` is the Moon model's download progress, written by the globe from its loader's own progress events.
 * `IntroLink` is a plain mutable object (held in a ref) that the camera rig, the post chain and the Skip control read and write
 * every frame without re-rendering React.
 */
export const useMoonLoad = create<{ frac: number; failed: boolean }>(() => ({ frac: 0, failed: false }));

export interface IntroLink {
  /** Skip was pressed (or Esc, Enter, a click) */
  skip: boolean;
  /** the post chain is built and drawing (high and medium tiers); the first light waits for it */
  post: boolean;
  /** strength of the intro-only lens effects this frame, 0-1 (0 from the hand-off on, for good) */
  fx: number;
  /** reduced motion: copy the still frame before the view changes */
  snap: boolean;
  /** where the Moon's disc is in the picture this frame: centre (0-1 across and up) and radius in picture heights */
  moonX: number;
  moonY: number;
  moonR: number;
}
export const newIntroLink = (): IntroLink => ({ skip: false, post: false, fx: 0, snap: false, moonX: 0.5, moonY: 0.5, moonR: 0 });
