import { useEffect, type RefObject } from 'react';

/**
 * Stop a plain mouse-wheel over a 3D canvas from zooming the scene (it should scroll the page).
 * Zoom still works with a trackpad pinch or ⌘/Ctrl + wheel (both arrive with ctrlKey/metaKey).
 * The capture-phase listener on the wrapper runs before OrbitControls' listener on the canvas.
 */
export function useWheelGuard(ref: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) e.stopPropagation();
    };
    el.addEventListener('wheel', onWheel, { capture: true });
    return () => el.removeEventListener('wheel', onWheel, { capture: true });
  }, [ref]);
}
