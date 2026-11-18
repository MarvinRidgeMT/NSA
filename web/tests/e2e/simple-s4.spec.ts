import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * S4 (17 Nov 2026): Simple mode opens on the Moon's south pole with the bundle's sites as pins. Expected numbers and names are
 * read here from the certainty sidecar and the ROI bundle, never typed in. CI draws with software rendering (low tier: the
 * lighter Moon image, no post effects); how the globe looks and what it costs is measured on the Mac (tmp/s4, the S4 report).
 */
test.use({ storageState: { cookies: [], origins: [] } });

const __dirname = dirname(fileURLToPath(import.meta.url));
type Row = { mast_m: number; metric: string; min: number; max: number; n_clones: number };
type Site = { sampled_masts_m: number[]; certainty_curve: Row[]; all_maps_100pct_sun_mast_m: number | null };
const sidecar = JSON.parse(readFileSync(resolve(__dirname, '../../public/certainty/sidecar.json'), 'utf8')) as { sites: Record<string, Site> };
const bundle = JSON.parse(readFileSync(resolve(__dirname, '../../../data/viewer/polaris-x5d-roi-2026-11-14-v2.json'), 'utf8')) as { datasets: { siteId: string; site: { name: string } }[] };
const sites = bundle.datasets.map((d) => ({ id: d.siteId, name: d.site.name }));
const sunRow = (id: string, m: number) => sidecar.sites[id]?.certainty_curve.find((r) => r.mast_m === m && r.metric === 'sun_centre_pct');
const range = (r: Row) => (r.min === r.max ? `${r.min.toFixed(1)} %` : `${r.min.toFixed(1)}–${r.max.toFixed(1)} %`);
// The Moon models are git-ignored NASA assets. Without one the app opens on the terrain view (covered by the S2 specs) and
// there is no globe to test.
const globeDir = resolve(__dirname, '../../public/globe');
const hasGlobe = existsSync(globeDir) && readdirSync(globeDir).some((f) => f.endsWith('.glb'));
test.skip(!hasGlobe, 'no Moon model in web/public/globe (git-ignored NASA asset): Simple mode opens on the terrain view');

const STORY = 'site04_roi3'; // the site Simple mode starts on (store/siteDefaults.ts), whose masts the top-bar stepper steps through

async function openGlobe(page: Page, q = '') {
  await page.goto(`/${q}`);
  await expect(page.getByTestId('simple-mode')).toBeVisible();
  await expect(page.locator('[data-testid=simple-globe][data-shown=true]')).toBeVisible({ timeout: 45_000 });
  await expect(page.getByTestId(`globe-pin-${sites[0].id}`)).toBeVisible();
}
const pin = (page: Page, id: string) => page.getByTestId(`globe-pin-${id}`).getByRole('button');
const spreadOf = (page: Page, id: string) => pin(page, id).evaluate((b) => Number((b as HTMLElement).style.getPropertyValue('--spread')));

test('a visitor first sees the globe, with one labelled pin per bundle site and the legend; not the terrain', async ({ page }) => {
  await openGlobe(page);
  await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'globe');
  await expect(page.getByTestId('plain-answer')).toHaveCount(0);
  await expect(page.getByTestId('scene3d')).toHaveCount(0);
  await expect(page.locator('.s-globe-pin')).toHaveCount(sites.length);
  for (const s of sites) {
    await expect(pin(page, s.id)).toHaveAccessibleName(new RegExp(`^${s.name.replace(/[()]/g, '\\$&')}\\. `));
    await expect(pin(page, s.id)).toHaveAccessibleName(/Open this site’s card\.$/); // 18 Nov layout: a pin opens its card
  }
  const n = sunRow(STORY, sidecar.sites[STORY].sampled_masts_m[0])!.n_clones;
  await expect(page.getByTestId('globe-legend')).toContainText(`how much the ${n} terrain variants disagree (Sun in sight, max − min)`);
  await page.getByTestId('globe-about').locator('summary').click();
  await expect(page.getByTestId('globe-about')).toContainText('LROC albedo image. VISUAL: display only');
  await expect(page.getByTestId('globe-about')).toContainText('Light: the Sun direction in the bundle at');
  await expect(page.getByTestId('simple-footer')).toContainText('Not affiliated with NASA');
});

test('shimmer amplitude of every pin equals the sidecar spread at every mast the stepper offers; zero is still', async ({ page }) => {
  await openGlobe(page);
  const masts = sidecar.sites[STORY].sampled_masts_m;
  for (const [k, m] of masts.entries()) {
    if (k > 0) await page.getByTestId('simple-mast-up').click();
    await expect(page.getByTestId('simple-mast-current')).toHaveText(`${m} m`);
    for (const s of sites) {
      const row = sunRow(s.id, m);
      const holder = page.getByTestId(`globe-pin-${s.id}`);
      if (!row) {
        // no sidecar row at this height (or for this site): no shimmer, and the pin says so
        await expect(holder).toHaveAttribute('data-nodata', 'true');
        await expect(pin(page, s.id)).toHaveAccessibleName(/No answer/);
        await expect(pin(page, s.id)).toHaveAttribute('data-zero', 'true');
        continue;
      }
      await expect.poll(() => spreadOf(page, s.id)).toBe(row.max - row.min);
      await expect(pin(page, s.id)).toHaveAccessibleName(new RegExp(`Sun in sight ${range(row).replace(/[.]/g, '\\.')} at a ${String(m).replace('.', '\\.')} m mast`));
      if (row.max === row.min) await expect(pin(page, s.id)).toHaveAttribute('data-zero', 'true');
      else await expect(pin(page, s.id)).not.toHaveAttribute('data-zero', 'true');
    }
  }
});

test('hovering a pin shows its site name and one-line answer', async ({ page }) => {
  await openGlobe(page);
  const m = sidecar.sites[STORY].sampled_masts_m[0];
  await pin(page, STORY).hover();
  const label = page.getByTestId('globe-hover-label');
  await expect(label.locator('.s-hoverlabel')).toHaveAttribute('data-visible', 'true');
  await expect(label).toContainText(sites.find((s) => s.id === STORY)!.name);
  await expect(label).toContainText(`Sun in sight ${range(sunRow(STORY, m)!)} at a ${m} m mast`);
  // the label is inside the window and clear of the box along the bottom (18 Nov layout: the side card is gone)
  const [lb, cb, vp] = [await label.boundingBox(), await page.getByTestId('spot-box').boundingBox(), page.viewportSize()!];
  expect(lb!.x >= 0 && lb!.x + lb!.width <= vp.width).toBe(true);
  expect(lb!.y + lb!.height <= cb!.y || lb!.x >= cb!.x + cb!.width || lb!.x + lb!.width <= cb!.x).toBe(true);
});

test('keyboard: Tab reaches each pin, Enter flies in to that site, Back to the Moon returns to the same pin', async ({ page }) => {
  await openGlobe(page);
  // every pin is in the tab order, in bundle order
  await page.locator('#simple-main').focus();
  const reached: string[] = [];
  for (let i = 0; i < 40 && reached.length < sites.length; i++) {
    await page.keyboard.press('Tab');
    const id = await page.evaluate(() => document.activeElement?.closest('.s-globe-pin')?.getAttribute('data-testid') ?? null);
    if (id) reached.push(id.replace('globe-pin-', ''));
  }
  expect(reached).toEqual(sites.map((s) => s.id));
  const last = sites[sites.length - 1];
  await expect(page.getByTestId('globe-hover-label')).toContainText(last.name);
  // 18 Nov layout: a pin opens its card; the card's button flies down
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('pin-card-fly')).toBeFocused();
  const t0 = Date.now();
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'site', { timeout: 10_000 });
  expect(Date.now() - t0).toBeGreaterThanOrEqual(1100); // the flight takes its 1.2 s
  await expect(page.getByTestId('simple-site')).toHaveText(last.name);
  await expect(page.getByTestId('scene3d')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId('simple-back-moon')).toBeFocused();
  await expect(page.getByTestId('simple-back-moon')).toHaveText('Back to the Moon');
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'globe', { timeout: 10_000 });
  await expect(pin(page, last.id)).toBeFocused();
  await expect(pin(page, last.id)).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('simple-site')).toHaveCount(0);
});

test('the mast picked on the globe is the mast at the site after flying in', async ({ page }) => {
  await openGlobe(page);
  const cert = sidecar.sites[STORY].all_maps_100pct_sun_mast_m!;
  const steps = sidecar.sites[STORY].sampled_masts_m.indexOf(cert);
  for (let i = 0; i < steps; i++) await page.getByTestId('simple-mast-up').click();
  await expect.poll(() => spreadOf(page, STORY)).toBe(0);
  await pin(page, STORY).click();
  // 18 Nov layout: a pin opens its card; the card's button flies down
  await page.getByTestId('pin-card-fly').click();
  await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'site', { timeout: 10_000 });
  await expect(page.getByTestId('simple-mast-current')).toHaveText(`${cert} m`);
  await expect(page.getByTestId('simple-stat-sun')).toHaveText(range(sunRow(STORY, cert)!));
});

test('reduced motion: pins are static rings, there is no drift, and flying in and back are instant', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await openGlobe(page);
  await expect(page.getByTestId('simple-globe')).toHaveAttribute('data-still', 'true');
  await expect(pin(page, STORY)).toHaveAttribute('data-still', 'true');
  expect(await pin(page, STORY).locator('.s-pin-halo').evaluate((h) => getComputedStyle(h).animationName)).toBe('none');
  await expect(page.getByTestId('globe-legend')).toContainText('Ring width =');
  const at = () => page.getByTestId(`globe-pin-${STORY}`).evaluate((e) => (e as HTMLElement).style.transform);
  const before = await at();
  await page.waitForTimeout(1500);
  expect(await at()).toBe(before);
  await pin(page, STORY).click();
  // 18 Nov layout: a pin opens its card; the card's button flies down
  await page.getByTestId('pin-card-fly').click();
  await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'site', { timeout: 300 });
  await expect(page.getByTestId('simple-site')).toBeVisible();
  await page.getByTestId('simple-back-moon').click();
  await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'globe', { timeout: 300 });
});

test('with motion allowed the view drifts slowly around the pole', async ({ page }) => {
  await openGlobe(page);
  const at = () => page.getByTestId(`globe-pin-${sites[0].id}`).evaluate((e) => (e as HTMLElement).style.transform);
  const before = await at();
  await expect.poll(at, { timeout: 15_000 }).not.toBe(before);
});

test('a link that asks for the terrain, or names a site, opens the terrain view; Back to the Moon still works from there', async ({ page }) => {
  await page.goto('/?view=terrain');
  await expect(page.getByTestId('plain-answer')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId('simple-globe')).toHaveCount(0);
  await page.goto(`/?site=${sites[0].id}`);
  await expect(page.getByTestId('simple-site')).toHaveText(sites[0].name, { timeout: 30_000 });
  await page.getByTestId('simple-back-moon').click();
  await expect(page.locator('[data-testid=simple-globe][data-shown=true]')).toBeVisible({ timeout: 45_000 });
  await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'globe');
});

test('phone width: the lighter Moon, pins big enough to press and apart, nothing off the window', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openGlobe(page);
  await expect(page.getByTestId('simple-globe')).toHaveAttribute('data-asset', /moon_lite\.glb|NASA_SVS_moon_small\.glb/);
  expect(await page.evaluate(() => '__polarisPost' in window)).toBe(false);
  const boxes = [];
  for (const s of sites) boxes.push((await pin(page, s.id).boundingBox())!);
  for (const b of boxes) {
    expect(b.width).toBeGreaterThanOrEqual(44);
    expect(b.height).toBeGreaterThanOrEqual(44);
    expect(b.x >= 0 && b.x + b.width <= 390).toBe(true);
  }
  for (let i = 0; i < boxes.length; i++)
    for (let j = i + 1; j < boxes.length; j++)
      expect(Math.hypot(boxes[i].x - boxes[j].x, boxes[i].y - boxes[j].y), 'pin centres at least 44 px apart').toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.scrollHeight])).toEqual([390, 844]);
  // 18 Nov layout: the rows are an off-screen list now; a pin's card (a sheet on a phone) flies in
  await pin(page, sites[0].id).click();
  await expect(page.getByTestId('pin-card')).toBeInViewport({ ratio: 1 });
  await page.getByTestId('pin-card-fly').click();
  await expect(page.getByTestId('simple-site')).toHaveText(sites[0].name, { timeout: 15_000 });
});

test('axe: the globe has no serious or critical issues', async ({ page }) => {
  await openGlobe(page);
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === 'serious' || v.impact === 'critical').map((v) => `${v.impact} ${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
});

test('Esc at a site goes back to the Moon, after closing anything open first', async ({ page }) => {
  await openGlobe(page);
  await pin(page, STORY).focus();
  await page.keyboard.press('Enter');
  // 18 Nov layout: a pin opens its card; the card's button flies down
  await expect(page.getByTestId('pin-card-fly')).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'site', { timeout: 10_000 });
  await expect(page.getByTestId('scene3d')).toBeVisible({ timeout: 30_000 });
  // an open disclosure takes the first Esc; the view stays at the site
  const limits = page.getByTestId('simple-limits');
  await limits.locator('summary').click();
  await expect(limits).toHaveAttribute('open', '');
  await page.keyboard.press('Escape');
  await expect(limits).not.toHaveAttribute('open', '');
  await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'site');
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'globe', { timeout: 10_000 });
  await expect(page.locator('[data-testid=simple-globe][data-shown=true]')).toBeVisible();
});

// ---- S4 review (17 Nov): pin answers per site, the shimmer's drawn amplitude, phone axe, the 8k crossfade ----

test('each pin says what the sidecar says for its site, and a site with no sidecar rows says so', async ({ page }) => {
  await openGlobe(page);
  const m = sidecar.sites[STORY].sampled_masts_m[0];
  // the no-rows path must be exercised by the real bundle, not only in theory
  expect(sites.some((s) => !sidecar.sites[s.id]), 'a bundle site without sidecar rows').toBe(true);
  for (const s of sites) {
    const row = sunRow(s.id, m);
    if (!sidecar.sites[s.id]) {
      await expect(pin(page, s.id)).toHaveAccessibleName(`${s.name}. No answer: the certainty sidecar has no rows for this site. Open this site’s card.`); // 18 Nov layout: a pin opens its card
      await expect(page.getByTestId(`globe-pin-${s.id}`)).toHaveAttribute('data-nodata', 'true');
      await expect(page.getByTestId(`globe-row-${s.id}`).locator('.s-globe-site-line')).toHaveText('No answer: the certainty sidecar has no rows for this site');
      await expect(page.getByTestId(`globe-row-${s.id}`).locator('.s-globe-site-spread')).toHaveText('');
      // a still pin must not read as "the variants agree": no-data pins are drawn grey, and the legend says so
      const answered = sites.find((o) => sidecar.sites[o.id])!;
      const colour = (id: string) => pin(page, id).evaluate((b) => getComputedStyle(b).color);
      expect(await colour(s.id)).not.toBe(await colour(answered.id));
      await expect(page.getByTestId('globe-legend')).toContainText('a grey pin has no sidecar answer at that height');
      continue;
    }
    expect(row, `${s.id} has a Sun-in-sight row at ${m} m`).toBeTruthy();
    const verdict = row!.min >= 100 ? 'Yes' : row!.min >= 70 ? 'Mostly' : 'Not reliably';
    await expect(page.getByTestId(`globe-row-${s.id}`).locator('.s-globe-site-line')).toHaveText(`${verdict}. Sun in sight ${range(row!)} at a ${m} m mast`);
    const spread = row!.max - row!.min;
    await expect(page.getByTestId(`globe-row-${s.id}`).locator('.s-globe-site-spread')).toHaveText(
      spread === 0 ? `all ${row!.n_clones} terrain variants agree` : `${row!.n_clones} terrain variants differ by ${spread.toFixed(1)} points`,
    );
  }
});

/** The pin halo's drawn amplitude: the shimmer's peak scale (motion) or the static ring's width in px (reduced motion). */
const drawn = (page: Page, id: string) =>
  pin(page, id).evaluate((b) => {
    const halo = b.querySelector('.s-pin-halo') as HTMLElement;
    const cs = getComputedStyle(halo);
    const tok = getComputedStyle(b);
    const gain = parseFloat(tok.getPropertyValue('--pin-gain'));
    const perPt = parseFloat(tok.getPropertyValue('--pin-ring-per-pt'));
    if (cs.display === 'none') return { display: 'none', gain, perPt, peak: null as number | null, ring: null as number | null };
    const anim = halo.getAnimations().find((a) => (a as CSSAnimation).animationName === 's-pin-shimmer');
    let peak: number | null = null;
    if (anim) {
      // the 'to' keyframe: end of the first (forward) iteration
      anim.pause();
      anim.currentTime = Number(anim.effect!.getTiming().duration);
      peak = new DOMMatrixReadOnly(getComputedStyle(halo).transform).a;
      anim.play();
    }
    const m = /(-?[\d.]+)px\s*$/.exec(cs.boxShadow.replace(/\s*inset\s*/, '')); // spread radius is the last length
    return { display: cs.display, gain, perPt, peak, ring: !anim && m ? parseFloat(m[1]) : null };
  });

for (const reduce of [false, true]) {
  test(`drawn shimmer ${reduce ? '(reduced motion: ring width)' : '(peak scale)'} equals the sidecar spread at every sampled mast`, async ({ page }) => {
    if (reduce) await page.emulateMedia({ reducedMotion: 'reduce' });
    await openGlobe(page);
    const masts = sidecar.sites[STORY].sampled_masts_m;
    for (const [k, m] of masts.entries()) {
      if (k > 0) await page.getByTestId('simple-mast-up').click();
      await expect(page.getByTestId('simple-mast-current')).toHaveText(`${m} m`);
      for (const s of sites) {
        const row = sunRow(s.id, m);
        const spread = row ? row.max - row.min : 0;
        await expect.poll(() => spreadOf(page, s.id)).toBe(spread);
        const d = await drawn(page, s.id);
        if (spread === 0) {
          expect(d.display, `${s.id} at ${m} m: zero spread draws no halo`).toBe('none');
          continue;
        }
        if (reduce) expect(d.ring!, `${s.id} at ${m} m ring width`).toBeCloseTo(2 + spread * d.perPt, 2);
        else expect(d.peak!, `${s.id} at ${m} m peak scale`).toBeCloseTo(1 + spread * d.gain, 3);
      }
    }
  });
}

test('axe at phone width (390 x 844): the globe has no serious or critical issues', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openGlobe(page);
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((v) => v.impact === 'serious' || v.impact === 'critical').map((v) => `${v.impact} ${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
});

test('Esc on a pin does nothing; Esc at a site returns to the globe with focus back on that pin', async ({ page }) => {
  await openGlobe(page);
  await pin(page, STORY).focus();
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'globe');
  await page.keyboard.press('Enter');
  // 18 Nov layout: a pin opens its card; the card's button flies down
  await expect(page.getByTestId('pin-card-fly')).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'site', { timeout: 10_000 });
  await expect(page.getByTestId('simple-back-moon')).toBeFocused({ timeout: 30_000 });
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'globe', { timeout: 10_000 });
  await expect(pin(page, STORY)).toBeFocused();
});

// The 8k model is git-ignored and too heavy for CI: these run only where it is present (Sid's and Anish's Macs).
const has8k = hasGlobe && readdirSync(globeDir).includes('NASA_SVS_Moon_NASA_LRO_8k_Topo_Small.glb');
const trackUpgrade = (page: Page) =>
  page.addInitScript(() => {
    const seen: string[] = [];
    (window as unknown as { __upgradeSeen: string[] }).__upgradeSeen = seen;
    new MutationObserver(() => {
      const s = document.querySelector('[data-testid=simple-globe]')?.getAttribute('data-upgrade-state');
      if (s && seen[seen.length - 1] !== s) seen.push(s);
    }).observe(document, { subtree: true, attributes: true, attributeFilter: ['data-upgrade-state'], childList: true });
  });
const upgradeSeen = (page: Page) => page.evaluate(() => (window as unknown as { __upgradeSeen: string[] }).__upgradeSeen);

for (const reduce of [false, true]) {
  test(`8k upgrade: ${reduce ? 'an instant cut under reduced motion' : 'a short crossfade from the compact model'}`, async ({ page }) => {
    test.skip(!has8k, 'the 8k model is not in web/public/globe on this machine');
    test.setTimeout(180_000);
    if (reduce) await page.emulateMedia({ reducedMotion: 'reduce' });
    await trackUpgrade(page);
    await openGlobe(page, '?quality=medium');
    await expect(page.getByTestId('simple-globe')).toHaveAttribute('data-upgrade-state', 'shown', { timeout: 150_000 });
    await expect(page.getByTestId('simple-globe')).toHaveAttribute('data-asset', 'NASA_SVS_Moon_NASA_LRO_8k_Topo_Small.glb');
    const seen = await upgradeSeen(page);
    expect(seen[0], 'opens on the compact model, waiting for the 8k one').toBe('wait');
    expect(seen[seen.length - 1]).toBe('shown');
    expect(seen.includes('fading')).toBe(!reduce);
  });
}
