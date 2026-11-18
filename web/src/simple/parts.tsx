/**
 * Simple-mode design system parts (S1, 16 Nov 2026). Static, styled components for later sections to wire up:
 * the object card (S12), the hover label (S12), the map pin with its variant shimmer (S4) and the Sound control (S2).
 * Nothing here holds a number. Every value shown is passed in by the caller, which reads it from a bundle or sidecar.
 * All styles live in styles.css under `.simple`.
 */
import { useId, type CSSProperties, type ReactNode, type Ref } from 'react';

type IconProps = { size?: number };
const svg = (size: number, children: ReactNode) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    {children}
  </svg>
);
export const IconClose = ({ size = 16 }: IconProps) => svg(size, <path d="M4 4l8 8M12 4l-8 8" />);
export const IconBack = ({ size = 16 }: IconProps) => svg(size, <path d="M9.5 3.5L5 8l4.5 4.5M5 8h7" />);
export const IconArrow = ({ size = 16 }: IconProps) => svg(size, <path d="M6.5 3.5L11 8l-4.5 4.5M11 8H4" />);
export const IconChevronUp = ({ size = 16 }: IconProps) => svg(size, <path d="M3.5 10L8 5.5l4.5 4.5" />);
export const IconChevronDown = ({ size = 16 }: IconProps) => svg(size, <path d="M3.5 6L8 10.5 12.5 6" />);
export const IconMenu = ({ size = 16 }: IconProps) => svg(size, <path d="M2.5 4.5h11M2.5 8h11M2.5 11.5h11" />);
export const IconSoundOff = ({ size = 16 }: IconProps) =>
  svg(
    size,
    <>
      <path d="M2.5 6.25h2L7.5 3.5v9L4.5 9.75h-2z" />
      <path d="M10.5 6.25l3 3.5M13.5 6.25l-3 3.5" />
    </>,
  );
export const IconSun = ({ size = 16 }: IconProps) =>
  svg(
    size,
    <>
      <circle cx="8" cy="8" r="2.75" />
      <path d="M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1.05 1.05M11.55 11.55l1.05 1.05M3.4 12.6l1.05-1.05M11.55 4.45l1.05-1.05" />
    </>,
  );

/** The honesty label that sits beside every headline number. */
export function HonestyTag({ href }: { href?: string }) {
  const text = 'SOURCE-BASED · UNVALIDATED';
  return href ? (
    <a className="s-honesty" href={href} title="How this number was made (Evidence page, Expert mode)">
      {text}
    </a>
  ) : (
    <span className="s-honesty">{text}</span>
  );
}

export interface CardFact {
  /** stable name of the fact (S12: tests and the phone sheet's collapsed line find a fact by it) */
  id?: string;
  label: string;
  /** One line under the label saying what the metric means. */
  hint?: ReactNode;
  value: ReactNode;
  sub?: ReactNode;
  tone?: 'sun' | 'earth' | 'alert';
}

/**
 * The glass card that opens beside an object clicked in the 3D scene (S12). `origin` is the side the object is on, so the
 * card grows from there. Close and Back are separate: Back returns the camera to the previous framing.
 */
export function ObjectCard({
  kind,
  title,
  facts,
  note,
  honestyHref,
  origin = 'left',
  onBack,
  onClose,
  children,
  heading: H = 'h3',
  testId,
  backRef,
}: {
  /** the card's heading level: h1 when the card is the page's main panel (S12), h3 inside a page that has its own */
  heading?: 'h1' | 'h3';
  testId?: string;
  backRef?: Ref<HTMLButtonElement>;
  kind: string;
  title: ReactNode;
  facts: CardFact[];
  note?: ReactNode;
  honestyHref?: string;
  origin?: 'left' | 'right';
  onBack?: () => void;
  onClose?: () => void;
  children?: ReactNode;
}) {
  return (
    <section className="s-panel s-objcard" data-origin={origin} data-testid={testId} aria-label={`${kind}: ${typeof title === 'string' ? title : ''}`}>
      <header className="s-objcard-head">
        <div>
          <H className="s-objcard-title">{title}</H>
          <p className="s-objcard-kind">{kind}</p>
        </div>
        <button type="button" className="s-btn s-btn--sm s-btn--icon s-btn--quiet" aria-label="Close card" onClick={onClose}>
          <IconClose />
        </button>
      </header>
      <dl className="s-facts">
        {facts.map((f) => (
          <div className="s-fact" key={f.label} data-tone={f.tone} data-fact={f.id}>
            <dt>
              {f.label}
              {f.hint && <span className="s-fact-hint">{f.hint}</span>}
            </dt>
            <dd>
              <span className="s-fact-value">{f.value}</span>
              {f.sub && <span className="s-fact-sub">{f.sub}</span>}
            </dd>
          </div>
        ))}
      </dl>
      {note && <p className="s-objcard-note">{note}</p>}
      {children}
      <footer className="s-objcard-foot">
        <button type="button" className="s-btn s-btn--sm" onClick={onBack} ref={backRef} data-testid={testId ? `${testId}-back` : undefined}>
          <IconBack />
          Back
        </button>
        <HonestyTag href={honestyHref} />
      </footer>
    </section>
  );
}

/** One-line label that follows the pointer over a clickable scene object. Position it with `style.transform`. */
export function HoverLabel({ name, hint, style, visible = true }: { name: string; hint?: string; style?: CSSProperties; visible?: boolean }) {
  return (
    <div className="s-hoverlabel" data-visible={visible} style={style} role="presentation">
      <i aria-hidden="true" />
      <b>{name}</b>
      {hint && <span>{hint}</span>}
    </div>
  );
}

/**
 * Site pin for the south-pole globe (S4). `spreadPts` is Sun-in-sight max − min across the terrain variants, in percentage
 * points, read from the certainty sidecar at the picked mast. The shimmer amplitude is linear in it and zero means still.
 * Under reduced motion (or `still`) the same value is drawn as the width of a static ring.
 */
export function SitePin({
  label,
  spreadPts,
  selected = false,
  still = false,
  onClick,
}: {
  label: string;
  spreadPts: number;
  selected?: boolean;
  still?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      className="s-pin"
      data-still={still || undefined}
      data-zero={spreadPts === 0 || undefined}
      aria-pressed={selected}
      aria-label={label}
      style={{ '--spread': spreadPts } as CSSProperties}
      onClick={onClick}
    >
      <span className="s-pin-halo" aria-hidden="true" />
      <span className="s-pin-dot" aria-hidden="true" />
    </button>
  );
}

/** Sound is not built yet: the control is visible, focusable and explains itself, but does nothing. */
export function SoundControl() {
  const tipId = useId();
  return (
    <span className="s-tipwrap">
      <button type="button" className="s-btn s-btn--sm s-btn--quiet" aria-disabled="true" aria-describedby={tipId} data-testid="simple-sound">
        <IconSoundOff />
        Sound: off
      </button>
      <span className="s-tip" role="tooltip" id={tipId}>
        Sound coming later
      </span>
    </span>
  );
}
