/**
 * Clickable site scene (S12, 18 Nov 2026), the part on the page: the card for a ridge or for the Sun / Earth, the list of
 * buttons that gives every clickable object a keyboard and screen-reader path, the one-line label that follows the pointer,
 * and the line that reads a card's values out when it opens. Every value comes from simple/sceneFocus.ts, which copies it
 * from the bundle.
 */
import { useEffect, useMemo, useRef } from 'react';
import { useRidgeFocus } from '../store/ridge';
import type { View } from '../store/view';
import { HoverLabel, ObjectCard } from './parts';
import { blockingRidges, bodyCard, hoverLabel, ridgeCard, ridgesNote, sceneObjects, useSceneFocus, type CardData, type FocusId } from './sceneFocus';

/** The card data for the object flown to, or null (the site's own card is SimpleApp's answer panel). */
export function useObjectCard(v: View): CardData | null {
  const focus = useSceneFocus((s) => s.focus);
  const { sun, earth } = useRidgeFocus(v);
  return useMemo(() => {
    // (the ridge named as blocking comes from the shared lookup, which in Simple mode holds an attribution to its own series)
    if (focus === 'sun' || focus === 'earth') return bodyCard(v, focus, focus === 'sun' ? sun : earth);
    if (focus?.startsWith('ridge:')) {
      const r = blockingRidges(v).find((x) => `ridge:${x.id}` === focus);
      return r ? ridgeCard(r, v) : null;
    }
    return null;
  }, [focus, v, sun, earth]);
}

/** The card beside a ridge, the Sun or the Earth. Back, the close button and Esc all return the camera to where it was. */
export function SceneCard({ card }: { card: CardData }) {
  const back = useSceneFocus((s) => s.back);
  const byKeys = useSceneFocus((s) => s.byKeys);
  const backBtn = useRef<HTMLButtonElement>(null);
  // opened from the keyboard list: focus comes into the card, on the way back
  useEffect(() => {
    if (byKeys) backBtn.current?.focus();
  }, [card.id, byKeys]);
  return (
    <div className="s-cardslot" data-sight-avoid="left">
      <ObjectCard
        heading="h1"
        testId="scene-card"
        kind={card.kind}
        title={card.title}
        facts={card.facts.map((f) => ({ id: f.key, label: f.label, hint: f.hint, value: f.value, sub: f.sub, tone: f.tone }))}
        note={card.note}
        honestyHref="?mode=expert#evidence"
        onBack={back}
        onClose={back}
        backRef={backBtn}
      />
    </div>
  );
}

/**
 * Every clickable object as a real button, outside the canvas: a quiet row under the way back. It is the keyboard and
 * screen-reader path (Tab moves along it, Enter flies), and the pointer's way to an object that is out of the picture, as
 * the Sun and the Earth often are. The scene outlines the object a button names while the button is hovered or focused.
 */
export function SceneObjectList({ v, card }: { v: View; card: CardData | null }) {
  const focus = useSceneFocus((s) => s.focus);
  const hover = useSceneFocus((s) => s.hover);
  const objects = useMemo(() => sceneObjects(v), [v.dataset, v.series?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const note = useMemo(() => ridgesNote(v), [v.dataset, v.series?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const hot = objects.find((o) => o.id === hover);
  const lastHot = useRef(hot);
  if (hot) lastHot.current = hot;
  // on the way back from a card opened by keyboard, focus returns to the button that opened it
  const prev = useRef<FocusId | null>(null);
  const list = useRef<HTMLUListElement>(null);
  useEffect(() => {
    const was = prev.current;
    prev.current = focus;
    if (was && !focus && useSceneFocus.getState().byKeys) list.current?.querySelector<HTMLElement>(`[data-object="${was}"]`)?.focus();
  }, [focus]);
  return (
    <>
      <nav className="s-objlist" aria-label="Things to look at in this view" data-testid="scene-objects">
        <span className="s-objlist-lab" aria-hidden="true">
          Look at
        </span>
        <ul ref={list}>
          {objects.map((o) => (
            <li key={o.id}>
              <button
                type="button"
                className="s-btn s-btn--sm s-btn--quiet"
                data-object={o.id}
                data-testid={`scene-object-${o.id}`}
                aria-label={o.label}
                aria-pressed={focus === o.id}
                onFocus={(e) => e.currentTarget.matches(':focus-visible') && useSceneFocus.getState().setHover(o.id, 'keys')}
                onPointerEnter={(e) => e.pointerType === 'mouse' && useSceneFocus.getState().setHover(o.id, 'keys')}
                onPointerLeave={() => useSceneFocus.getState().hover === o.id && useSceneFocus.getState().setHover(null)}
                onBlur={() => useSceneFocus.getState().hover === o.id && useSceneFocus.getState().setHover(null)}
                onClick={(e) => useSceneFocus.getState().open(o.id, e.detail === 0 || e.currentTarget.matches(':focus-visible'))}
              >
                {o.short}
              </button>
            </li>
          ))}
        </ul>
        {/* ridges exist in the bundle but not for the series on screen: said, not silently dropped */}
        {note && (
          <p className="s-objlist-note" data-testid="scene-ridges-note">
            {note}
          </p>
        )}
      </nav>
      <div className="s-scene-label" data-testid="scene-hover-label" ref={(el) => void (hoverLabel.el = el)}>
        <HoverLabel name={(hot ?? lastHot.current)?.name ?? ''} hint={useSceneFocus.getState().hoverBy === 'keys' ? undefined : (hot ?? lastHot.current)?.hint} visible={!!hot && focus !== hot.id} style={{ position: 'static' }} />
      </div>
      {/* read out when a card opens: its name and every value on it */}
      <p className="sr-only" role="status" aria-live="polite" data-testid="scene-announce">
        {card?.say ?? ''}
      </p>
    </>
  );
}
