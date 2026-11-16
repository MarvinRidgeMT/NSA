import { usePolaris } from './store';
import { useUi } from './ui';

/**
 * Which site each page opens on in the ROI export (Sid, 15 Nov 2026 18:15 EST):
 *   Explore  -> Site01 ROI6 (Connecting Ridge): the NASA GSFC shape-from-shading relief covers its whole crop;
 *   Story, Decision, Evidence and the guided demo -> Site04 ROI3 (Shackleton rim): the decision story (Sun sometimes blocked,
 *   Certainty Height) is about that site; at Site01 ROI6 the Sun is visible 100 % of the time on all 20 clones.
 * Only a default: once the user picks a site (site menu or a ?site= link), nothing switches it again. Display choice only;
 * no number changes; each page always shows the site it is on by name.
 */
export const EXPLORE_SITE = 'site01_roi6';
export const STORY_SITE = 'site04_roi3';
let userChose = false;

export function markSiteChosen(): void {
  userChose = true;
}

export function siteChosen(): boolean {
  return userChose;
}

export function defaultSiteFor(route: string): string {
  return route === 'sky' ? EXPLORE_SITE : STORY_SITE;
}

/** Switch to the page's default site when the loaded bundle is the ROI export and the user has not chosen a site. */
export function applyRouteSite(route: string): void {
  if (userChose || useUi.getState().guide !== null) return;
  const st = usePolaris.getState();
  const lb = st.loaded;
  if (!lb || !/^polaris-x5d-roi-.*\.json$/.test(lb.name)) return;
  const want = defaultSiteFor(route);
  const i = lb.bundle.datasets.findIndex((d) => d.siteId === want && !!d.dem);
  if (i >= 0 && i !== st.datasetIdx) st.setSite(i);
}

if (typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('site')) userChose = true;

/** The page named by the hash, as App reads it ('' = the story landing). */
function routeFromHash(): string {
  const h = typeof window === 'undefined' ? '' : window.location.hash.replace(/^#/, '');
  return h || 'story';
}

// Apply the page's default site in the same store update that delivers a newly loaded bundle (zustand calls listeners
// synchronously, before React renders), so the hidden 3D scene never builds one site's terrain only to rebuild the other.
// (15 Nov 19:50: building Site01 first and then Site04 on the story page delayed the guided demo's Play timer under test load.)
let lastLoaded: unknown = null;
usePolaris.subscribe((s) => {
  if (s.loaded && s.loaded !== lastLoaded) {
    lastLoaded = s.loaded;
    applyRouteSite(routeFromHash());
  }
});
