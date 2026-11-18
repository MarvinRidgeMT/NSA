/**
 * Clickable site scene (S12, 18 Nov 2026): which object the visitor is looking at, and what its card says.
 *
 * One store holds the state the 3D scene (three/ScenePicks.tsx) and the page (SimpleApp.tsx, simple/SceneCards.tsx) share:
 * the object flown to, the object under the pointer or holding keyboard focus, and whether the site's answer card is open.
 * The card builders below are plain functions over the view: every value they return is copied from the bundle (the current
 * sample, the scenario's series, derived.attribution) and only formatted here. Nothing is computed about terrain or sight.
 */
import { create } from 'zustand';
import { fmtRidgeDistance, type RidgeNow } from '../bundle/evidence';
import type { Ridge } from '../bundle/types';
import { attributionApplies, attributionScenarioId } from '../store/ridge';
import { fmtSigned, fmtUtc, type View } from '../store/view';

export type FocusId = 'site' | 'sun' | 'earth' | `ridge:${string}`;

interface SceneFocusState {
  /** the object the camera has flown to (its card is open); null = the visitor's own framing */
  focus: FocusId | null;
  /** opened from the keyboard list: focus moves into the card, and back to the list on return */
  byKeys: boolean;
  /** the object under the pointer, or whose list button holds keyboard focus */
  hover: FocusId | null;
  hoverBy: 'pointer' | 'keys' | null;
  /** the site's answer card (open on arrival; it holds the mast heights) */
  siteCard: boolean;
  /** 'in' while the camera eases to an object, 'out' while it returns, else null (set by the scene) */
  flying: 'in' | 'out' | null;
  open: (id: FocusId, byKeys?: boolean) => void;
  /** Back / Esc: the camera returns to the framing it left */
  back: () => void;
  setHover: (id: FocusId | null, by?: 'pointer' | 'keys') => void;
  setSiteCard: (open: boolean) => void;
  /** a new site or a new visit: nothing flown to, the answer card open */
  reset: () => void;
}

export const useSceneFocus = create<SceneFocusState>((set, get) => ({
  focus: null,
  byKeys: false,
  hover: null,
  hoverBy: null,
  siteCard: true,
  flying: null,
  open: (id, byKeys = false) => set({ focus: id, byKeys, ...(id === 'site' ? { siteCard: true } : {}) }),
  back: () => get().focus !== null && set({ focus: null }),
  setHover: (id, by = 'pointer') => (get().hover !== id || get().hoverBy !== (id ? by : null)) && set({ hover: id, hoverBy: id ? by : null }),
  setSiteCard: (open) => set({ siteCard: open }),
  reset: () => set({ focus: null, byKeys: false, hover: null, hoverBy: null, siteCard: true, flying: null }),
}));

/** The hover label is one DOM element moved by the scene (pointer position, or the object's place on screen for the keyboard). */
export const hoverLabel: { el: HTMLDivElement | null } = { el: null };
export function placeHoverLabel(x: number, y: number, boundsW: number, boundsH: number, shown = true) {
  const el = hoverLabel.el;
  if (!el) return;
  // an object outside the picture has no place to label
  el.style.visibility = shown ? '' : 'hidden';
  if (!shown) return;
  const w = el.offsetWidth;
  const h = el.offsetHeight;
  // below and to the right of the pointer; flipped where that would leave the view
  const px = x + 14 + w > boundsW - 8 ? x - 14 - w : x + 14;
  const py = y + 18 + h > boundsH - 8 ? y - 12 - h : y + 18;
  el.style.transform = `translate(${Math.round(Math.max(8, px))}px, ${Math.round(Math.max(8, py))}px)`;
}

export interface Fact {
  key: string;
  label: string;
  hint?: string;
  value: string;
  sub?: string;
  tone?: 'sun' | 'earth' | 'alert';
}
export interface CardData {
  id: FocusId;
  title: string;
  kind: string;
  facts: Fact[];
  note: string;
  /** one sentence with every value, for screen readers */
  say: string;
}

/** Minimum distance of a ridge (bundle value), metres. */
export const ridgeNearM = (r: Ridge) => (typeof r.distanceM === 'number' ? r.distanceM : r.distanceM.min);

/**
 * The ridges a visitor can open: the ones the bundle's attribution holds responsible for at least one lost Sun or Earth hour
 * (`of_record`). The attribution describes one scenario's skyline, so under any other scenario's series there are none.
 */
export function blockingRidges(v: View): Ridge[] {
  const att = v.dataset.derived?.attribution;
  if (!att || !attributionApplies(v.dataset, v.series?.id)) return [];
  return att.ridges.filter((r) => r.ofRecord);
}

/** The scenario whose skyline the attribution describes (store/ridge.ts: the baseline when the bundle names none; unknown when it has no baseline either). */
export const attributionSeriesId = (v: View): string | undefined => attributionScenarioId(v.dataset);

/**
 * Why no ridge is offered, when the bundle has ridges of record but for another series than the one on screen (its
 * attribution describes one scenario's skyline: the baseline). Null when ridges are offered, or the bundle names none.
 * The mast height in the sentence is that scenario's own observer height, from the bundle.
 */
export function ridgesNote(v: View): string | null {
  const att = v.dataset.derived?.attribution;
  const id = attributionSeriesId(v);
  if (!att || attributionApplies(v.dataset, v.series?.id) || !att.ridges.some((r) => r.ofRecord)) return null;
  if (id === undefined) return 'No ridges here: the bundle does not say which series its blocking ridges describe, so none are shown.';
  const of = v.dataset.derived?.scenarios.find((x) => x.id === id);
  const at = of?.observer?.mastM;
  const now = v.series?.observer?.mastM;
  return `No ridges here: the bundle names its blocking ridges for ${at !== undefined ? `the ${at} m mast series` : 'another series'} only${now !== undefined && now !== at ? `, not for ${now} m` : ''}.`;
}

/** Half-width of the terrain crop a ridge must lie inside to be drawn on it (bundle DEM), metres. */
export function cropReachM(v: View): number {
  const d = v.dataset.dem;
  return d ? (d.validCoverageRadiusM ?? ((d.n - 1) * d.spacing) / 2) : 0;
}

const metres = (m: number) => `${m > 0 ? '+' : m < 0 ? '−' : ''}${Math.abs(m) < 100 ? Math.abs(m).toFixed(2) : Math.round(Math.abs(m)).toLocaleString('en-US')} m`;

/** Sample spacing of the loaded window, hours (bundle times). */
function stepHours(v: View): number | null {
  return v.times.length > 1 ? (v.times[1] - v.times[0]) / 3.6e6 : null;
}

const say = (title: string, facts: Fact[]) => `${title}. ${facts.map((f) => `${f.label}: ${f.value}${f.sub ? `, ${f.sub}` : ''}`).join('. ')}.`;

export function ridgeCard(r: Ridge, v: View): CardData & { far: boolean } {
  const far = ridgeNearM(r) > cropReachM(v);
  const n = v.times.length;
  const step = stepHours(v);
  const of = step === 1 ? `of the window's ${n} hourly samples` : `of the window's ${n} samples`;
  const layer = r.dem === 'far_80m' ? '80 m regional terrain model' : r.dem === 'near_5m' ? '5 m terrain model' : r.dem;
  const facts: Fact[] = [
    { key: 'distance', label: 'Distance from the site', value: fmtRidgeDistance(r), sub: layer ? `from the ${layer}` : undefined },
    { key: 'bearing', label: 'Bearing', hint: 'clockwise from local north', value: `${r.azimuthDeg[0].toFixed(1)}–${r.azimuthDeg[1].toFixed(1)}°` },
  ];
  if (r.reliefM !== undefined) facts.push({ key: 'height', label: 'Height against the site', hint: 'its crest against the ground at the site', value: metres(r.reliefM) });
  facts.push(
    { key: 'sun-hours', label: 'Sun hidden behind it', value: `${r.hours.sun.lost} h`, sub: of, tone: r.hours.sun.lost > 0 ? 'sun' : undefined },
    { key: 'earth-hours', label: 'Earth hidden behind it', value: `${r.hours.earth.lost} h`, sub: of, tone: r.hours.earth.lost > 0 ? 'earth' : undefined },
  );
  const title = `Ridge ${r.label ?? r.id}`;
  return {
    id: `ridge:${r.id}`,
    title,
    kind: far ? 'Blocking ridge · beyond the terrain drawn here' : 'Blocking ridge · on the terrain drawn here',
    facts,
    far,
    note: far
      ? 'It stands far beyond the terrain drawn in this view, so the ridge itself is not drawn. The bracket on the skyline marks its bearing only.'
      : 'The dots are the points the bundle names as setting the skyline, one per bearing step, on the terrain at true scale. No line is drawn between them.',
    say: say(title, facts),
  };
}

export function bodyCard(v: View, key: 'sun' | 'earth', now: RidgeNow | null): CardData {
  const t = v[key];
  const name = key === 'sun' ? 'Sun' : 'Earth';
  const ridge = now?.ridge ? (now.ridge.label ?? now.ridge.id) : null;
  const state: Fact =
    t.visible === undefined
      ? { key: 'state', label: 'Now', value: 'Not evaluated', sub: 'this bundle has no sight result here' }
      : t.visible === null
        ? { key: 'state', label: 'Now', value: 'At the skyline', sub: 'changes between two samples' }
        : t.visible
          ? { key: 'state', label: 'Now', value: 'In view', tone: key }
          : { key: 'state', label: 'Now', value: 'Blocked', sub: ridge ? `by ridge ${ridge}` : 'by terrain', tone: 'alert' };
  const facts: Fact[] = [
    state,
    { key: 'azimuth', label: 'Azimuth', hint: 'clockwise from local north', value: `${t.az.toFixed(1)}°` },
    { key: 'elevation', label: 'Elevation', hint: 'disc centre against the local horizontal', value: fmtSigned(t.el) },
  ];
  if (t.marginDeg !== null)
    facts.push({
      key: 'margin',
      label: 'Margin against the skyline',
      hint: 'above the terrain skyline in that direction when positive',
      value: fmtSigned(t.marginDeg),
      sub: t.horizonElDeg !== null ? `skyline at ${fmtSigned(t.horizonElDeg)}` : undefined,
      tone: t.marginDeg < 0 ? 'alert' : undefined,
    });
  facts.push({ key: 'time', label: 'At', value: fmtUtc(v.utcMs).replace('T', ' ').replace(/:00Z$/, ' UTC').replace(/Z$/, ' UTC'), sub: v.br.exact !== null ? 'a bundle sample' : 'between two bundle samples: read in between' });
  const mast = v.series?.observer?.mastM;
  return {
    id: key,
    title: name,
    kind: mast !== undefined ? `Seen from the top of the ${mast} m mast` : 'Seen from the site',
    facts,
    note: `Line of sight to the centre of the disc, from the bundle. ${key === 'sun' ? 'Not solar power.' : 'Not a radio link.'}`,
    say: say(name, facts),
  };
}

export interface SceneObject {
  id: FocusId;
  /** name on the hover label */
  name: string;
  /** shortest name: the list button */
  short: string;
  /** what a press does, for the hover label */
  hint: string;
  /** full accessible name of the list button */
  label: string;
}

/** Everything in the site scene that can be opened, in reading order. */
export function sceneObjects(v: View): SceneObject[] {
  const out: SceneObject[] = [
    { id: 'site', name: 'Landing site and mast', short: 'Site and mast', hint: 'Click for the answer', label: 'Landing site and mast. Fly to the mast and open the answer.' },
    { id: 'sun', name: 'Sun', short: 'Sun', hint: 'Click for where it is now', label: 'Sun. Fly to it and open where it is now.' },
    { id: 'earth', name: 'Earth', short: 'Earth', hint: 'Click for where it is now', label: 'Earth. Fly to it and open where it is now.' },
  ];
  for (const r of blockingRidges(v)) {
    const what = [r.hours.sun.lost > 0 ? 'the Sun' : null, r.hours.earth.lost > 0 ? 'the Earth' : null].filter(Boolean).join(' and ');
    const name = `Ridge ${r.label ?? r.id}`;
    out.push({ id: `ridge:${r.id}`, name, short: name, hint: 'Click to see what it blocks', label: `${name}${what ? `, which blocks ${what}` : ''}. Fly to it and open its details.` });
  }
  return out;
}
