/**
 * Team pass/fail requirements (Anish, 14 Nov 2026 ~13:50 EST, answering T-ORG-05 q3: "Sun ≥70%, Sun+Earth ≥40%").
 * These are mission REQUIREMENTS (team choices), not science outputs. They are attached to a bundle metric only when the
 * bundle declares no constraint of its own; a bundle-declared constraint always wins. The comparison value − threshold is
 * display arithmetic on two numbers the viewer was given; it is labelled with this source on screen.
 */
export const TEAM_REQUIREMENTS_SOURCE = 'team requirement (Anish, 14 Nov ~13:50 EST; bundle declares none)';

export const TEAM_REQUIREMENTS: Record<string, { op: '>=' | '<='; threshold: number }> = {
  sun_center_visible_pct: { op: '>=', threshold: 70 },
  sun_and_earth_center_visible_pct: { op: '>=', threshold: 40 },
};
