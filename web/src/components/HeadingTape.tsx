import { useEffect, useRef } from 'react';
import type { View } from '../store/view';
import { useUi } from '../store/ui';
import { cameraHeading, closestAngle } from '../store/heading';

/**
 * Heading tape (Penumbra stage HUD): which way the camera looks, and where the bundle's Sun and Earth are, in the site's local
 * azimuth (0 = local north). The tape scrolls with the camera; the Sun and Earth marks sit at the bundle azimuths of the current
 * sample. Display only: the marks and readouts are bundle values, never interpolated in time.
 *
 * Applied research (14islands journal): "Using trigonometry to animate direction" — keep live values in refs, take the
 * equivalent angle closest to the current one so nothing spins the long way round, ease it with lerp in a requestAnimationFrame
 * loop; "Developing a performant custom cursor" — write transforms directly from that loop, so a moving camera causes no React
 * renders.
 */
const SPAN = 120; // degrees of azimuth visible across the tape
const W = 340; // CSS px width of the tape (matches styles.css)

export function HeadingTape({ v }: { v: View }) {
  const strip = useRef<HTMLDivElement>(null);
  const sunRef = useRef<HTMLDivElement>(null);
  const earthRef = useRef<HTMLDivElement>(null);
  const readout = useRef<HTMLSpanElement>(null);
  const shown = useRef<number | null>(null);
  const az = useRef({ sun: v.sun.az, earth: v.earth.az });
  az.current = { sun: v.sun.az, earth: v.earth.az };

  useEffect(() => {
    let raf = 0;
    const reduce = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    const pxPerDeg = W / SPAN;
    const place = (el: HTMLDivElement | null, azDeg: number, head: number) => {
      if (!el) return;
      const rel = closestAngle(0, azDeg - head); // -180..180 relative to where the camera looks
      const off = Math.abs(rel) > SPAN / 2;
      el.style.transform = `translateX(${(Math.max(-SPAN / 2, Math.min(SPAN / 2, rel)) * pxPerDeg).toFixed(1)}px)`;
      el.dataset.off = off ? (rel < 0 ? 'left' : 'right') : '';
    };
    const tick = () => {
      const target = cameraHeading();
      if (target !== null) {
        const cur = shown.current ?? target;
        const goal = closestAngle(cur, target);
        const next = reduce ? goal : cur + (goal - cur) * 0.18;
        shown.current = Math.abs(goal - next) < 0.02 ? goal : next;
        const head = ((shown.current % 360) + 360) % 360;
        if (strip.current) strip.current.style.transform = `translateX(${(-shown.current * pxPerDeg).toFixed(1)}px)`;
        place(sunRef.current, az.current.sun, head);
        place(earthRef.current, az.current.earth, head);
        if (readout.current) readout.current.textContent = `${head.toFixed(0).padStart(3, '0')}°`;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  // tick marks every 10°, labels every 30°; drawn three times so the strip can wrap
  const ticks: { a: number; label?: string }[] = [];
  for (let a = -360; a <= 720; a += 10) {
    const m = ((a % 360) + 360) % 360;
    ticks.push({ a, label: m % 90 === 0 ? ['N', 'E', 'S', 'W'][m / 90] : m % 30 === 0 ? String(m) : undefined });
  }
  return (
    <div className="heading-tape" data-testid="heading-tape" aria-label={`Camera heading tape. Sun azimuth ${v.sun.az.toFixed(1)}°, Earth azimuth ${v.earth.az.toFixed(1)}° (bundle, local north = 0°)`} role="img">
      <div className="ht-window">
        <div className="ht-strip" ref={strip}>
          {ticks.map((t) => (
            <span key={t.a} className={`ht-tick${t.label ? ' major' : ''}`} style={{ left: `${(t.a * W) / SPAN}px` }}>
              {t.label && <b>{t.label}</b>}
            </span>
          ))}
        </div>
        <div className="ht-mark sun" ref={sunRef} title="Sun azimuth (bundle)">
          <i />
        </div>
        <div className="ht-mark earth" ref={earthRef} title="Earth azimuth (bundle)">
          <i />
        </div>
        <div className="ht-centre" />
      </div>
      <div className="ht-read">
        <FocusToggle />
        <span>
          view <span ref={readout}>---°</span>
        </span>
        <span className="sun">Sun {v.sun.az.toFixed(1)}°</span>
        <span className="earth">Earth {v.earth.az.toFixed(1)}°</span>
      </div>
    </div>
  );
}

/** Focus: hides the instrument, the stage notes and the temporal panel so the terrain fills the stage (key F). Display only. */
function FocusToggle() {
  const focus = useUi((s) => s.focus);
  const set = useUi((s) => s.set);
  return (
    <button type="button" className="ht-focus" aria-pressed={focus} onClick={() => set({ focus: !focus })} data-testid="stage-focus" title="Focus on the terrain (F): hide the panels; press again to bring them back">
      {focus ? 'Panels' : 'Focus'}
    </button>
  );
}
