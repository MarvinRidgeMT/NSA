import type { View } from '../store/view';
import { useRidgeFocus } from '../store/ridge';
import { useMastReading } from './MastInstrument';

const pct = (x: number) => `${Math.round(x * 10) / 10}`.replace(/\.0$/, '');

/** The one-word verdict for a Sun-in-sight row (shared with the Simple-mode globe pins so both always say the same). */
export const verdictWord = (min: number, all100: boolean) => (all100 ? 'Yes' : min >= 70 ? 'Mostly' : 'Not reliably');

/**
 * Plain-English answer at the top of the Explore instrument (readability pass, 15 Nov). Every number is copied from the
 * certainty sidecar row the Certainty Height instrument shows (same mast height, same realizations) or from the bundle's
 * current sample; nothing is computed, rounded into a new claim, or interpolated. Geometric centre visibility, not power.
 */
export function PlainAnswer({ v }: { v: View }) {
  const r = useMastReading(v);
  const { sun, earth } = useRidgeFocus(v);
  if (!r?.s) return null;
  const { h, s, all100, cert } = r;
  const sunRange = s.min === s.max ? `${pct(s.min)} %` : `${pct(s.min)}–${pct(s.max)} %`;
  const verdict = verdictWord(s.min, all100);
  const now = (key: 'sun' | 'earth') => {
    const t = v[key];
    if (t.visible === undefined) return 'not in this bundle';
    if (t.visible === null) return 'at the edge of the skyline';
    if (t.visible) return 'in view';
    const rn = key === 'sun' ? sun : earth;
    const name = rn?.ridge?.label ?? rn?.ridge?.id;
    return name ? `blocked by ridge ${name}` : 'blocked by terrain';
  };
  return (
    <div className="sect plain-answer" data-testid="plain-answer" aria-live="polite">
      <span className="lab">The answer</span>
      <p className="pa-verdict">
        <strong className={all100 ? 'ok' : 'sun'}>{verdict}.</strong>{' '}
        {all100
          ? `With a ${h} m mast, the Sun stays in sight for the whole 14–28 Nov window in all ${s.n_clones} terrain variants tested.`
          : `With a ${h} m mast, the Sun is in sight ${sunRange} of the 14–28 Nov window across ${s.n_clones} terrain variants.`}
      </p>
      {!all100 && cert !== null && cert !== h && (
        <p className="pa-hint">
          Raise the mast to <strong>{cert} m</strong> for 100 % in every variant (mast buttons below).
        </p>
      )}
      <ul className="pa-now">
        <li className={`sun ${v.sun.visible === false ? 'blocked' : ''}`}>
          <span>Sun now</span> {now('sun')}
        </li>
        <li className={`earth ${v.earth.visible === false ? 'blocked' : ''}`}>
          <span>Earth now</span> {now('earth')}
        </li>
      </ul>
      <p className="pa-fine">Line of sight to the centre of each disc, from the bundle. Not solar power, not a radio link.</p>
    </div>
  );
}
